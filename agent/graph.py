from typing import Any, Dict, List, Optional
from llama_index.core.workflow import (
    Workflow,
    Event,
    StartEvent,
    StopEvent,
    step,
    Context
)
from agent.state import AgentState
from agent.nodes import (
    intent_classifier_node,
    chitchat_node,
    out_of_scope_node,
    inquiry_node,
    executer_node,
    responder_node
)

# Events
class IntentEvent(Event):
    intent: str
    user_input: str

class InquiryEvent(Event):
    user_input: str

class ExecuterEvent(Event):
    user_input: str
    db_results: str

class KGWorkflow(Workflow):
    @step
    async def classify_intent(self, ctx: Context, ev: StartEvent) -> IntentEvent:
        # Initialize state in context if needed
        state = await ctx.store.get("state", default={
            "user_input": ev.user_input,
            "history": ev.history,
            "intent": None,
            "triples": [],
            "db_results": "",
            "response": ""
        })
        
        # update user input for current turn
        state["user_input"] = ev.user_input
        
        result = intent_classifier_node(state)
        state.update(result)
        await ctx.store.set("state", state)
        
        return IntentEvent(intent=state["intent"], user_input=state["user_input"])

    @step
    async def handle_intent(self, ctx: Context, ev: IntentEvent) -> InquiryEvent | StopEvent:
        state = await ctx.store.get("state")
        
        if ev.intent == "chitchat":
            result = chitchat_node(state)
            return StopEvent(result=result["response"])
        elif ev.intent == "inquiry":
            return InquiryEvent(user_input=ev.user_input)
        else:
            result = out_of_scope_node(state)
            return StopEvent(result=result["response"])

    @step
    async def inquiry(self, ctx: Context, ev: InquiryEvent) -> ExecuterEvent:
        state = await ctx.store.get("state")
        result = inquiry_node(state)
        state.update(result)
        await ctx.store.set("state", state)
        return ExecuterEvent(user_input=ev.user_input, db_results="")

    @step
    async def execute_db(self, ctx: Context, ev: ExecuterEvent) -> ExecuterEvent:
        state = await ctx.store.get("state")
        result = executer_node(state)
        state.update(result)
        await ctx.store.set("state", state)
        return ExecuterEvent(user_input=ev.user_input, db_results=state["db_results"])

    @step
    async def respond(self, ctx: Context, ev: ExecuterEvent) -> StopEvent:
        state = await ctx.store.get("state")
        result = responder_node(state)
        return StopEvent(result=result["response"])

def create_graph():
    # Kept for compatibility or can be removed if main.py is updated
    return KGWorkflow(timeout=60, verbose=True)
