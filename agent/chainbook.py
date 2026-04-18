"""
chainbook.py — Chain Book Prefetching Logic
============================================
Pure-Python helper module (no LLM calls) for the Chain Book feature.

Responsibilities:
  1. Load and parse chain definitions from chains.json
  2. Detect which chain (if any) a user's message triggers
  3. Query Neo4j for all prefetch questions in a chain (in parallel)
  4. Manage the priority-weighted cache — evict lowest-weight entry when full
  5. Serve cached answers when the user's next question matches a chain step
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

logger = logging.getLogger(__name__)

# Maximum number of prefetched answers to hold in the chain cache at once
MAX_CHAIN_CACHE_SIZE = 10

# Path to the chain definitions config
_CHAINS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chains.json")


def load_chains() -> dict:
    """Load chain definitions from chains.json."""
    try:
        with open(_CHAINS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Chain Book: Failed to load chains.json: {e}")
        return {}


def detect_chain(user_input: str, chains: dict) -> tuple[Optional[str], Optional[dict]]:
    """
    Detect if a user's message triggers a predefined chain.
    Returns (chain_name, chain_def) or (None, None) if no match.
    Uses simple case-insensitive keyword matching against trigger_keywords.
    """
    user_lower = user_input.lower()
    for chain_name, chain_def in chains.items():
        for keyword in chain_def.get("trigger_keywords", []):
            if keyword.lower() in user_lower:
                logger.info(f"Chain Book: Activated chain '{chain_name}' via keyword '{keyword}'")
                return chain_name, chain_def
    return None, None


def evict_if_full(chain_cache: dict) -> dict:
    """
    If the chain cache exceeds MAX_CHAIN_CACHE_SIZE, evict the lowest-weight entry.
    Returns the updated cache.
    """
    if len(chain_cache) <= MAX_CHAIN_CACHE_SIZE:
        return chain_cache

    # Find and remove the item with the lowest weight
    evict_key = min(chain_cache, key=lambda k: chain_cache[k].get("weight", 0))
    evicted_weight = chain_cache[evict_key].get("weight", 0)
    del chain_cache[evict_key]
    logger.info(f"Chain Book: Evicted cached answer '{evict_key}' (weight={evicted_weight}) — cache was full.")
    return chain_cache


def _fetch_single(driver, query_template: str, entity: str) -> str:
    """Execute a single Neo4j entity lookup and return a string result."""
    try:
        from database.operations import db_inquire
        results = db_inquire(driver, [entity])
        return "\n".join(results) if results else ""
    except Exception as e:
        logger.warning(f"Chain Book prefetch failed for entity '{entity}': {e}")
        return ""


def prefetch_chain_answers(driver, chain_def: dict, entity: str, start_position: int) -> dict:
    """
    Fire parallel Neo4j queries for all remaining chain questions (after start_position).
    Returns a dict: {question_id: {"answer": str, "weight": int}}
    """
    questions = chain_def.get("questions", [])
    remaining = questions[start_position + 1:]  # skip the question user just asked

    if not remaining:
        return {}

    cache_additions = {}

    with ThreadPoolExecutor(max_workers=min(len(remaining), 4)) as executor:
        future_map = {
            executor.submit(_fetch_single, driver, q["query_template"], entity): q
            for q in remaining
        }
        for future in as_completed(future_map):
            q = future_map[future]
            try:
                answer = future.result()
                cache_additions[q["id"]] = {
                    "answer": answer,
                    "weight": q["weight"],
                    "entity": entity,
                    "query_template": q["query_template"]
                }
                logger.info(f"Chain Book: Prefetched '{q['id']}' for entity '{entity}' (weight={q['weight']})")
            except Exception as e:
                logger.warning(f"Chain Book: Prefetch error for '{q['id']}': {e}")

    return cache_additions


def get_cached_answer(chain_cache: dict, active_chain: str, chain_def: dict, chain_position: int) -> Optional[tuple[str, str]]:
    """
    Check if the next expected question in the chain has a cached answer.
    Returns (question_id, cached_answer) if found, or None if cache miss.
    """
    if not chain_def or not chain_cache:
        return None

    questions = chain_def.get("questions", [])
    next_position = chain_position + 1

    if next_position >= len(questions):
        return None  # Chain exhausted

    next_question_id = questions[next_position]["id"]
    cached = chain_cache.get(next_question_id)

    if cached and cached.get("answer"):
        logger.info(f"Chain Book: Cache HIT for question '{next_question_id}'")
        return next_question_id, cached["answer"]

    logger.info(f"Chain Book: Cache MISS for question '{next_question_id}'")
    return None
