from typing import List, Dict, Any, TypedDict, Annotated
import operator

class AgentState(TypedDict):
    """
    Represents the state of the agent.
    """
    user_input: str
    intent: str
    triples: List[Dict[str, Any]]
    db_results: str
    response: str
    history: Annotated[List[Dict[str, str]], operator.add]
