import os
import json
import logging
from typing import Dict, Any, List
from llama_index.llms.groq import Groq
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from agent.state import AgentState
from agent.prompts import (
    classifier_prompt,
    inquiry_prompt,
    chitchat_prompt,
    out_of_scope_prompt,
    responder_prompt,
)
from database.connection import connect_to_neo4j
from database.operations import db_add_or_edit, db_inquire, db_delete

logger = logging.getLogger(__name__)

def get_llm(temperature=0):
    return Groq(
        model="openai/gpt-oss-120b",
        temperature=temperature,
        api_key=os.getenv("GROQ_API_KEY"),
    )

def _convert_history(history: List[Dict[str, str]]) -> List[ChatMessage]:
    """Convert state history to LlamaIndex ChatMessage list."""
    messages = []
    for msg in history:
        role = MessageRole.USER if msg["role"] == "user" else MessageRole.ASSISTANT
        messages.append(ChatMessage(role=role, content=msg["content"]))
    return messages


def _get_entities_heuristic(text: str) -> List[str]:
    """Simple heuristic to find potential entities (Capitalized words)."""
    import re
    # Match words starting with capital letters
    words = re.findall(r'\b[A-Z][a-z]+\b', text)
    # Also include any word > 4 chars just to be safe for lowercase inputs
    long_words = [w for w in re.findall(r'\b\w{5,}\b', text) if w not in words]
    return list(set(words + long_words))

def intent_classifier_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    user_input = state["user_input"]
    
    # 1. Search DB for context
    db_context = "No relevant context found."
    potential_entities = _get_entities_heuristic(user_input)
    
    if potential_entities:
        driver = connect_to_neo4j()
        if driver:
            try:
                context_results = []
                for ent in potential_entities:
                    res = db_inquire(driver, {"subject": ent})
                    if res: context_results.extend(res)
                if context_results:
                    db_context = "\n".join(context_results)
            finally:
                driver.close()

    # 2. Format Prompt with Context
    prompt = classifier_prompt.format(db_context=db_context)
    
    history_messages = _convert_history(state.get("history", []))
    messages = history_messages + [
        ChatMessage(role=MessageRole.SYSTEM, content=prompt),
        ChatMessage(role=MessageRole.USER, content=user_input),
    ]
    
    response = llm.chat(messages)
    intent = response.message.content.strip().lower()
    return {"intent": intent}


def chitchat_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm(temperature=0.7)
    history_messages = _convert_history(state.get("history", []))
    messages = history_messages + [
        ChatMessage(role=MessageRole.SYSTEM, content=chitchat_prompt),
        ChatMessage(role=MessageRole.USER, content=state["user_input"]),
    ]
    response = llm.chat(messages)
    return {"response": response.message.content}


def out_of_scope_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    history_messages = _convert_history(state.get("history", []))
    messages = history_messages + [
        ChatMessage(role=MessageRole.SYSTEM, content=out_of_scope_prompt),
        ChatMessage(role=MessageRole.USER, content=state["user_input"]),
    ]
    response = llm.chat(messages)
    return {"response": response.message.content}


def inquiry_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=inquiry_prompt),
        ChatMessage(role=MessageRole.USER, content=state["user_input"]),
    ]
    response = llm.chat(messages)
    content = response.message.content.strip()
    
    # Simple JSON repair/extraction
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    
    try:
        data = json.loads(content)
        return {
            "triples": data.get("triples", []),
            "intent": data.get("intent", "add")
        }
    except Exception as e:
        logger.error(f"Failed to parse inquiry output: {e}")
        return {"triples": [], "intent": "unknown"}


def executer_node(state: AgentState) -> Dict[str, Any]:
    driver = connect_to_neo4j()
    if not driver:
        return {"db_results": "Database connection failed."}
    
    intent = state.get("intent")
    triples = state.get("triples", [])
    user_text = state["user_input"]
    
    # If intent is unknown but we have triples, try to infer or use default
    if intent == "unknown" and triples:
        intent = "add"

    results = []
    try:
        # If intent is read, we primarily care about the entity (subject)
        if intent == "read":
            entities = set()
            for t in triples:
                if t.get("subject"): entities.add(t["subject"])
                if t.get("object") and t["object"] != "?": entities.add(t["object"])
            
            if not entities:
                # Last resort: use the input as the entity if nothing else was extracted
                res_list = db_inquire(driver, {"subject": user_text})
                results.extend(res_list)
            else:
                for ent in entities:
                    res_list = db_inquire(driver, {"subject": ent})
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
    finally:
        driver.close()


def responder_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = responder_prompt.format(
        user_input=state["user_input"],
        db_results=state["db_results"]
    )
    history_messages = _convert_history(state.get("history", []))
    messages = history_messages + [
        ChatMessage(role=MessageRole.USER, content=prompt)
    ]
    response = llm.chat(messages)
    return {"response": response.message.content}
