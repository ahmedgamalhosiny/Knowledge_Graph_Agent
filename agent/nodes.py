import os
import json
import logging
import functools
from typing import Dict, Any, List
from llama_index.llms.groq import Groq
from llama_index.core.base.llms.types import ChatMessage, MessageRole

from agent.state import AgentState
from agent.prompts import (
    main_system_template,
    classifier_prompt,
    inquiry_prompt,
    chitchat_prompt,
    out_of_scope_prompt,
    responder_prompt,
    summarizer_prompt,
    memory_extraction_prompt,
    distillation_prompt,
)
from agent.chainbook import (
    load_chains,
    detect_chain,
    evict_if_full,
    prefetch_chain_answers,
    get_cached_answer,
)
from database.connection import connect_to_neo4j
from database.operations import db_add_or_edit, db_inquire, db_delete
from database.memory_db import retrieve_memories, save_memory

logger = logging.getLogger(__name__)

@functools.lru_cache(maxsize=4)
def get_llm(temperature=0, json_mode=False):
    kwargs = {}
    if json_mode:
        kwargs["additional_kwargs"] = {"response_format": {"type": "json_object"}}
        
    return Groq(
        model="openai/gpt-oss-120b",
        temperature=temperature,
        api_key=os.getenv("GROQ_API_KEY"),
        **kwargs
    )

def _convert_history(history: List[Dict[str, str]]) -> List[ChatMessage]:
    """Convert state history to LlamaIndex ChatMessage list."""
    messages = []
    for msg in history:
        role = MessageRole.USER if msg["role"] == "user" else MessageRole.ASSISTANT
        messages.append(ChatMessage(role=role, content=msg["content"]))
    return messages

def _format_context(state: AgentState, prompt_template: str, **kwargs) -> str:
    summary = state.get("conversation_summary", "No summary yet.")
    memories = state.get("extracted_memories", [])
    memory_str = "\n".join(memories) if memories else "No known facts."
    return prompt_template.format(
        conversation_summary=summary,
        extracted_memories=memory_str,
        **kwargs
    )

# --- MEMORY NODES ---

def retrieve_memory_node(state: AgentState) -> Dict[str, Any]:
    user_input = state["user_input"]
    memories = retrieve_memories(user_input, limit=3)
    return {"extracted_memories": memories}


def sequential_intent_tracker_node(state: AgentState) -> Dict[str, Any]:
    """
    Sequential Intent Tracker (SIT): looks at past intents to detect repetitive patterns.
    Formerly known as 'prefetch_node'.
    """
    sequence = state.get("intent_sequence", [])
    if not sequence:
        return {}
        
    last_intent = sequence[-1] if sequence else None
    sit_cache = ""
    
    if last_intent == "inquiry":
        sit_cache = "SIT Cache: User in active inquiry loop. Ready graph indices."
        logger.info(f"Sequential Intent Tracker: Prior intent was '{last_intent}' — graph indices primed.")
        
    return {"sit_cache": sit_cache}


# --- CHAIN BOOK NODES ---

def chainbook_detector_node(state: AgentState) -> Dict[str, Any]:
    """
    Detects if the user's message triggers a predefined chain.
    Sets active_chain and chain_position in state.
    If already in a chain, increments the chain_position.
    """
    chains = load_chains()
    user_input = state["user_input"]
    active_chain = state.get("active_chain", "")
    chain_position = state.get("chain_position", 0)

    # If we're already in a chain, move to next position
    if active_chain and active_chain in chains:
        new_position = chain_position + 1
        chain_def = chains[active_chain]
        if new_position < len(chain_def.get("questions", [])):
            logger.info(f"Chain Book: Continuing chain '{active_chain}' at position {new_position}")
            return {"chain_position": new_position}
        else:
            # Chain exhausted — deactivate
            logger.info(f"Chain Book: Chain '{active_chain}' exhausted. Deactivating.")
            return {"active_chain": "", "chain_position": 0}

    # Otherwise detect a new chain
    chain_name, chain_def = detect_chain(user_input, chains)
    if chain_name:
        return {"active_chain": chain_name, "chain_position": 0}

    return {}


def chainbook_cache_check_node(state: AgentState) -> Dict[str, Any]:
    """
    Checks if the current question's answer is already in the chain cache.
    Sets cache_hit=True and populates db_results if found.
    """
    chains = load_chains()
    active_chain = state.get("active_chain", "")
    chain_position = state.get("chain_position", 0)
    chain_cache = state.get("chain_cache", {})

    if not active_chain or not chain_cache:
        return {"cache_hit": False}

    chain_def = chains.get(active_chain)
    if not chain_def:
        return {"cache_hit": False}

    result = get_cached_answer(chain_cache, active_chain, chain_def, chain_position - 1)
    if result:
        question_id, cached_answer = result
        # Remove the consumed cache entry
        updated_cache = {k: v for k, v in chain_cache.items() if k != question_id}
        return {
            "cache_hit": True,
            "db_results": cached_answer if cached_answer else "No data found for this query.",
            "chain_cache": updated_cache
        }

    return {"cache_hit": False}


def chainbook_prefetch_node(state: AgentState) -> Dict[str, Any]:
    """
    After answering the current question, fires parallel Neo4j queries
    for all remaining chain questions and stores them in chain_cache.
    Evicts lowest-weight entries if cache is full.
    """
    chains = load_chains()
    active_chain = state.get("active_chain", "")
    chain_position = state.get("chain_position", 0)
    chain_cache = dict(state.get("chain_cache") or {})

    if not active_chain:
        return {}

    chain_def = chains.get(active_chain)
    if not chain_def:
        return {}

    # Extract the entity from the last used triples or db_results
    triples = state.get("triples", [])
    entity = ""
    if triples:
        entity = triples[0].get("subject", "") or triples[0].get("object", "")

    if not entity:
        return {}

    driver = connect_to_neo4j()
    if not driver:
        return {}

    new_answers = prefetch_chain_answers(driver, chain_def, entity, chain_position)
    chain_cache.update(new_answers)
    chain_cache = evict_if_full(chain_cache)

    return {"chain_cache": chain_cache}


def save_memory_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm(temperature=0)
    user_input = state["user_input"]
    prompt = memory_extraction_prompt.format(user_input=user_input)
    
    response = llm.chat([ChatMessage(role=MessageRole.USER, content=prompt)])
    fact = response.message.content.strip()
    
    if fact and fact.upper() != "NONE":
        save_memory(fact)
        logger.info(f"Saved new memory: {fact}")
    return {}


def summarizer_node(state: AgentState) -> Dict[str, Any]:
    from agent.state import _MAX_SUMMARY_LENGTH
    history = state.get("history", [])
    if len(history) < 6:
        return {} # No need to summarize yet
    
    # Take the oldest 4 messages to summarize
    to_summarize = history[:4]
    remaining = history[4:]
    
    current_summary = state.get("conversation_summary", "No prior summary.")
    new_turns = "\n".join([f"{msg['role']}: {msg['content']}" for msg in to_summarize])
    
    prompt = summarizer_prompt.format(
        current_summary=current_summary,
        new_turns=new_turns
    )
    
    llm = get_llm(temperature=0.3)
    response = llm.chat([ChatMessage(role=MessageRole.USER, content=prompt)])
    new_summary = response.message.content.strip()
    
    # Context Flushing (Hierarchical Paging)
    if len(new_summary) > _MAX_SUMMARY_LENGTH:
        logger.warning(f"Summary length ({len(new_summary)}) exceeds max ({_MAX_SUMMARY_LENGTH}). Distilling...")
        distill_prompt = distillation_prompt.format(long_summary=new_summary)
        distill_response = llm.chat([ChatMessage(role=MessageRole.USER, content=distill_prompt)])
        new_summary = distill_response.message.content.strip()
    
    return {
        "conversation_summary": new_summary,
        "history": {"action": "replace", "messages": remaining}
    }


# --- EXISTING CORE NODES ---

def intent_classifier_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    user_input = state["user_input"]
    
    new_history = [{"role": "user", "content": user_input}]
    history_messages = _convert_history(state.get("history", []))
    
    system_prompt = _format_context(state, classifier_prompt)
    messages = history_messages + [
        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
        ChatMessage(role=MessageRole.USER, content=user_input),
    ]
    
    response = llm.chat(messages)
    intent = response.message.content.strip().lower()
    
    old_seq = state.get("intent_sequence", [])
    new_seq = old_seq + [intent]
    # Keep only the last 5 intents to avoid unbounded array growth
    new_seq = new_seq[-5:]
    
    return {"intent": intent, "history": new_history, "intent_sequence": new_seq}


def chitchat_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm(temperature=0.7)
    history_messages = _convert_history(state.get("history", []))
    system_prompt = _format_context(state, chitchat_prompt)
    
    messages = history_messages + [
        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
        ChatMessage(role=MessageRole.USER, content=state["user_input"]),
    ]
    response = llm.chat(messages)
    content = response.message.content
    return {
        "response": content,
        "history": [{"role": "assistant", "content": content}]
    }


def out_of_scope_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    history_messages = _convert_history(state.get("history", []))
    system_prompt = out_of_scope_prompt # static no memory context needed
    
    messages = history_messages + [
        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
        ChatMessage(role=MessageRole.USER, content=state["user_input"]),
    ]
    response = llm.chat(messages)
    content = response.message.content
    return {
        "response": content,
        "history": [{"role": "assistant", "content": content}]
    }


def inquiry_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm(json_mode=True)
    system_prompt = _format_context(state, inquiry_prompt)
    
    history_messages = _convert_history(state.get("history", []))
    messages = history_messages + [
        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
        ChatMessage(role=MessageRole.USER, content=state["user_input"]),
    ]
    
    response = llm.chat(messages)
    content = response.message.content.strip()
    
    try:
        data = json.loads(content)
        return {
            "triples": data.get("triples", []),
            "intent": data.get("intent", "add")
        }
    except Exception as e:
        logger.error(f"Failed to parse native JSON inquiry output: {e}")
        return {"triples": [], "intent": "unknown"}


def executer_node(state: AgentState) -> Dict[str, Any]:
    driver = connect_to_neo4j()
    if not driver:
        return {"db_results": "Database connection failed."}
    
    intent = state.get("intent")
    triples = state.get("triples", [])
    user_text = state["user_input"]
    
    if intent == "unknown" and triples:
        intent = "add"

    results = []
    
    if intent == "read":
        entities = set()
        for t in triples:
            if t.get("subject"): entities.add(t["subject"])
            if t.get("object") and t["object"] != "?": entities.add(t["object"])
        
        if not entities:
            res_list = db_inquire(driver, [user_text])
            results.extend(res_list)
        else:
            res_list = db_inquire(driver, list(entities))
            results.extend(res_list)
    else:
        for t in triples:
            if intent in ("add", "edit"):
                res = db_add_or_edit(driver, t, user_text)
            elif intent == "delete":
                res = db_delete(driver, t)
            else:
                res = ""
            if res:
                results.append(res)
            
    return {"db_results": "\n".join(results) if results else "No operations performed or no data found."}


def responder_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = _format_context(
        state, 
        responder_prompt, 
        user_input=state["user_input"], 
        db_results=state["db_results"]
    )
    
    history_messages = _convert_history(state.get("history", []))
    messages = history_messages + [
        ChatMessage(role=MessageRole.USER, content=prompt)
    ]
    response = llm.chat(messages)
    content = response.message.content
    return {
        "response": content,
        "history": [{"role": "assistant", "content": content}]
    }
