from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agent.state import AgentState
from agent.nodes import *

def create_graph():
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("retrieve_memory",     retrieve_memory_node)
    workflow.add_node("sit",                 sequential_intent_tracker_node)  # Sequential Intent Tracker
    workflow.add_node("intent_classifier",   intent_classifier_node)
    workflow.add_node("chitchat",            chitchat_node)
    workflow.add_node("out_of_scope",        out_of_scope_node)
    workflow.add_node("chainbook_detector",  chainbook_detector_node)
    workflow.add_node("chainbook_cache",     chainbook_cache_check_node)
    workflow.add_node("inquiry",             inquiry_node)
    workflow.add_node("executer",            executer_node)
    workflow.add_node("chainbook_prefetch",  chainbook_prefetch_node)
    workflow.add_node("responder",           responder_node)
    workflow.add_node("save_memory",         save_memory_node)
    workflow.add_node("summarizer",          summarizer_node)

    # Set Entry Point
    workflow.set_entry_point("retrieve_memory")
    workflow.add_edge("retrieve_memory", "sit")
    workflow.add_edge("sit", "intent_classifier")

    # Route from intent classifier
    def route_intent(state: AgentState):
        intent = state["intent"]
        if intent == "chitchat":
            return "chitchat"
        elif intent == "inquiry":
            return "chainbook_detector"  # inquiry always goes through chain book first
        else:
            return "out_of_scope"

    workflow.add_conditional_edges(
        "intent_classifier",
        route_intent,
        {
            "chitchat":          "chitchat",
            "out_of_scope":      "out_of_scope",
            "chainbook_detector":"chainbook_detector",
        }
    )

    # Chain book detection → cache check
    workflow.add_edge("chainbook_detector", "chainbook_cache")

    # Cache check: HIT skips inquiry+executer, MISS goes through normal path
    def route_cache(state: AgentState):
        return "cache_hit" if state.get("cache_hit") else "cache_miss"

    workflow.add_conditional_edges(
        "chainbook_cache",
        route_cache,
        {
            "cache_hit":  "chainbook_prefetch",  # skip LLM extraction + DB, go straight to prefetch more + respond
            "cache_miss": "inquiry",              # normal path: extract triples → DB → prefetch → respond
        }
    )

    # Normal inquiry path
    workflow.add_edge("inquiry",  "executer")
    workflow.add_edge("executer", "chainbook_prefetch")

    # Both paths converge at responder
    workflow.add_edge("chainbook_prefetch", "responder")

    # Connect non-inquiry branches to memory processors
    workflow.add_edge("chitchat",    "save_memory")
    workflow.add_edge("out_of_scope","save_memory")
    workflow.add_edge("responder",   "save_memory")

    workflow.add_edge("save_memory", "summarizer")
    workflow.add_edge("summarizer",  END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
