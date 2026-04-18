"""
Knowledge Graph Bot - Sequential Flow Test Script
==================================================
Acts as a senior AI engineer test harness.
Tests all graph branches: chitchat, out_of_scope, add, read, edit, delete.
"""

import os
import time
import logging
from dotenv import load_dotenv

# Suppress noisy logs for clean test output
logging.basicConfig(level=logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.WARNING)
logging.getLogger("llama_index").setLevel(logging.WARNING)

load_dotenv()

from database.connection import connect_to_neo4j, init_db
from database.memory_db import init_memory_db
from agent.graph import create_graph

# ─────────────────────────────────────────────────────────
# TEST MESSAGES — Covering ALL graph branches in sequence
# ─────────────────────────────────────────────────────────
TEST_MESSAGES = [
    # ── BRANCH 1: Chitchat ──────────────────────────────
    {
        "id":       "T01",
        "branch":   "chitchat",
        "message":  "Hello! How are you doing today?",
        "expect":   "Should respond with a warm, professional greeting. NO database activity.",
    },
    # ── BRANCH 2: Out of Scope ───────────────────────────
    {
        "id":       "T02",
        "branch":   "out_of_scope",
        "message":  "Can you write me a poem about the ocean?",
        "expect":   "Should politely decline and explain its knowledge management purpose.",
    },
    # ── BRANCH 3: Inquiry → Add ──────────────────────────
    {
        "id":       "T03",
        "branch":   "inquiry/add",
        "message":  "Albert Einstein was born in Ulm, Germany.",
        "expect":   "Should extract triple and store: Einstein BORN_IN Ulm.",
    },
    {
        "id":       "T04",
        "branch":   "inquiry/add",
        "message":  "Albert Einstein developed the Theory of Relativity.",
        "expect":   "Should store: Einstein DEVELOPED Theory_of_Relativity.",
    },
    {
        "id":       "T05",
        "branch":   "inquiry/add",
        "message":  "Marie Curie discovered Polonium.",
        "expect":   "Should store: Marie_Curie DISCOVERED Polonium.",
    },
    {
        "id":       "T06",
        "branch":   "inquiry/add",
        "message":  "Marie Curie was born in Warsaw, Poland.",
        "expect":   "Should store: Marie_Curie BORN_IN Warsaw.",
    },
    # ── BRANCH 4: Inquiry → Read (single entity) ─────────
    {
        "id":       "T07",
        "branch":   "inquiry/read",
        "message":  "What do you know about Albert Einstein?",
        "expect":   "Should retrieve and present all stored facts about Einstein.",
    },
    # ── BRANCH 5: Inquiry → Read (multi-entity) ──────────
    {
        "id":       "T08",
        "branch":   "inquiry/read (bulk)",
        "message":  "Tell me everything about Marie Curie and Polonium.",
        "expect":   "Should batch-query both entities in one DB call and present combined results.",
    },
    # ── BRANCH 6: Inquiry → Edit ─────────────────────────
    {
        "id":       "T09",
        "branch":   "inquiry/edit",
        "message":  "Update Einstein's birthplace to the Kingdom of Württemberg.",
        "expect":   "Should update the BORN_IN relationship for Einstein via MERGE.",
    },
    # ── BRANCH 7: Inquiry → Read (verify edit) ───────────
    {
        "id":       "T10",
        "branch":   "inquiry/read (verify edit)",
        "message":  "Where was Albert Einstein born?",
        "expect":   "Should now return the updated birthplace: Kingdom of Württemberg.",
    },
    # ── BRANCH 8: Inquiry → Delete ───────────────────────
    {
        "id":       "T11",
        "branch":   "inquiry/delete",
        "message":  "Forget that Marie Curie discovered Polonium.",
        "expect":   "Should delete the DISCOVERED relationship between Marie_Curie and Polonium.",
    },
    # ── BRANCH 9: Inquiry → Read (verify delete) ─────────
    {
        "id":       "T12",
        "branch":   "inquiry/read (verify delete)",
        "message":  "What do you know about Marie Curie?",
        "expect":   "Should NOT show Polonium discovery anymore. Only BORN_IN Warsaw should remain.",
    },
    # ── BRANCH 10: Chitchat with context (memory check) ──
    {
        "id":       "T13",
        "branch":   "chitchat (memory context)",
        "message":  "That was very helpful, thank you!",
        "expect":   "Should respond warmly. MemorySaver should retain prior conversation context.",
    },
]

# ─────────────────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────────────────
DIVIDER    = "=" * 70
SUBDIV     = "-" * 70

def run_tests():
    print(f"\n{DIVIDER}")
    print("  Knowledge Graph Bot - Senior Engineer Test Suite")
    print(f"{DIVIDER}\n")

    # Init DB
    print("*  Initializing database connection and schema...")
    driver = connect_to_neo4j()
    if not driver:
        print("x  FATAL: Could not connect to Neo4j. Aborting tests.")
        return
    init_db(driver)
    init_memory_db()
    print("V  Database ready.\n")

    # Create graph (single instance, shared thread_id like a real session)
    graph  = create_graph()
    config = {"configurable": {"thread_id": "test-session-engineer"}}

    results = []

    for test in TEST_MESSAGES:
        print(f"{SUBDIV}")
        print(f"  [{test['id']}]  Branch : {test['branch']}")
        print(f"          Message: {test['message']}")
        print(f"          Expect : {test['expect']}")
        print()

        start = time.perf_counter()
        try:
            final_state = graph.invoke(
                {"user_input": test["message"]},
                config=config
            )
            elapsed = time.perf_counter() - start
            response = final_state.get("response", "[No response field in state]")

            print(f"  ⏱  Latency : {elapsed:.2f}s")
            print(f"  🤖 Bot     : {response}")
            results.append({"id": test["id"], "status": "PASS", "latency": elapsed})

        except Exception as e:
            elapsed = time.perf_counter() - start
            print(f"  ✗  ERROR   : {e}")
            results.append({"id": test["id"], "status": "FAIL", "latency": elapsed, "error": str(e)})

        print()

    # ─── Summary ───────────────────────────────────────────
    print(f"\n{DIVIDER}")
    print("  TEST SUMMARY")
    print(f"{DIVIDER}")
    passed  = sum(1 for r in results if r["status"] == "PASS")
    failed  = sum(1 for r in results if r["status"] == "FAIL")
    avg_lat = sum(r["latency"] for r in results) / len(results)

    for r in results:
        mark = "✓" if r["status"] == "PASS" else "✗"
        print(f"  {mark}  [{r['id']}]  {r['status']}  ({r['latency']:.2f}s)  {r.get('error', '')}")

    print(f"\n  Total : {len(results)} tests  |  Passed: {passed}  |  Failed: {failed}")
    print(f"  Avg Latency : {avg_lat:.2f}s")
    print(f"{DIVIDER}\n")


if __name__ == "__main__":
    run_tests()
