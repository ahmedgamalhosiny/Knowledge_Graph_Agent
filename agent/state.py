from typing import List, Dict, Any, TypedDict, Annotated
import operator

# Maximum number of messages to retain in history (20 = 10 conversation turns)
_MAX_HISTORY = 20

def _replace_or_append(existing: List[Dict[str, str]], new: Any) -> List[Dict[str, str]]:
    """
    Custom LangGraph reducer for conversation history.
    If 'new' is a dict containing {"action": "replace", "messages": [...]}, 
    it replaces the history. Otherwise, it appends.
    """
    if isinstance(new, dict) and new.get("action") == "replace":
        return new["messages"]
    git 
    if not existing:
        existing = []
    
    if isinstance(new, list):
        combined = existing + new
    else:
        combined = existing + [new]
        
    return combined[-_MAX_HISTORY:] if len(combined) > _MAX_HISTORY else combined


# Maximum number of characters to allow in the summary before applying Context Flushing (Hierarchical Paging)
_MAX_SUMMARY_LENGTH = 1500

class AgentState(TypedDict):
    """
    Represents the state of the agent across the LangGraph workflow.
    """
    user_input: str
    intent: str
    intent_sequence: List[str]      # Tracks a historical chain of intents for the Sequential Intent Tracker
    sit_cache: str                  # Cache buffer for Sequential Intent Tracker (renamed from prefetch_cache)
    triples: List[Dict[str, Any]]   # extracted (subject, predicate, object) triples
    db_results: str
    response: str
    conversation_summary: str       # Short-term buffer roll-up
    extracted_memories: List[str]   # Long-term semantic facts from SQLite
    history: Annotated[List[Dict[str, str]], _replace_or_append]
    # --- Chain Book Prefetching ---
    active_chain: str               # Name of the currently active chain (e.g., 'person_inquiry')
    chain_position: int             # Index of the last answered question in the active chain
    chain_cache: Dict[str, Any]     # {question_id: {answer, weight, entity}} — prefetched answer cache
    cache_hit: bool                 # True if the current question was served from chain cache
