from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import *

def create_graph():
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("intent_classifier", intent_classifier_node)
    workflow.add_node("chitchat", chitchat_node)
    workflow.add_node("out_of_scope", out_of_scope_node)
    workflow.add_node("inquiry", inquiry_node)
    workflow.add_node("executer", executer_node)
    workflow.add_node("responder", responder_node)

    # Set Entry Point
    workflow.set_entry_point("intent_classifier")

    # Add Conditional Edges from Intent Classifier
    def route_intent(state: AgentState):
        intent = state["intent"]
        if intent == "chitchat":
            return "chitchat"
        elif intent == "inquiry":
            return "inquiry"
        else:
            return "out_of_scope"

    workflow.add_conditional_edges(
        "intent_classifier",
        route_intent,
        {
            "chitchat": "chitchat",
            "out_of_scope": "out_of_scope",
            "inquiry": "inquiry"
        }
    )

    # Add Normal Edges
    workflow.add_edge("inquiry", "executer")
    workflow.add_edge("executer", "responder")

    # Connect to END
    workflow.add_edge("chitchat", END)
    workflow.add_edge("out_of_scope", END)
    workflow.add_edge("responder", END)

    return workflow.compile()
