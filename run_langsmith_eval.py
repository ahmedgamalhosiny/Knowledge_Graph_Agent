import os
import uuid
import json
import logging
from dotenv import load_dotenv
from langsmith import Client, evaluate
from groq import Groq

from test_bot import TEST_MESSAGES
from agent.graph import create_graph
from database.connection import connect_to_neo4j, init_db
from database.memory_db import init_memory_db

# Suppress debug logs
logging.basicConfig(level=logging.WARNING)

load_dotenv()
client = Client()

DATASET_NAME = "Knowledge Graph Bot Evaluation"

def prepare_dataset():
    """Check if the dataset exists, otherwise create it from TEST_MESSAGES."""
    try:
        # Check if dataset exists
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
        print(f"Found existing dataset: '{DATASET_NAME}'")
        return dataset
    except Exception:
        print(f"Creating new dataset '{DATASET_NAME}' from test_bot.py...")
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Testing the branches and intents of the Knowledge Graph Agent"
        )
        
        for msg in TEST_MESSAGES:
            client.create_example(
                inputs={"user_input": msg["message"]},
                outputs={
                    "expected": msg["expect"], 
                    "branch": msg["branch"],
                    "id": msg["id"]
                },
                dataset_id=dataset.id,
            )
        print("Dataset created successfully.")
        return dataset


def run_agent(inputs: dict) -> dict:
    """The target function invoked by LangSmith's evaluator."""
    graph = create_graph()
    
    # We use a unique thread_id per test run to prevent memory state bleeding between questions
    config = {"configurable": {"thread_id": f"eval-{uuid.uuid4()}"}}
    
    final_state = graph.invoke(inputs, config=config)
    
    return {
        "response": final_state.get("response", ""),
        "intent": final_state.get("intent", ""),
        "db_results": final_state.get("db_results", "")
    }


# --- Programmatic Evaluators ---

def intent_accuracy_evaluator(run, example) -> dict:
    """Evaluates if the agent picked the correct graph branch/intent based on the user question."""
    expected_branch = example.outputs.get("branch", "").lower()
    actual_intent = run.outputs.get("intent", "").lower()
    
    score = 0
    if "chitchat" in expected_branch and actual_intent == "chitchat":
        score = 1
    elif "out_of_scope" in expected_branch and actual_intent == "out_of_scope":
        score = 1
    elif "add" in expected_branch and actual_intent == "add":
        score = 1
    elif "read" in expected_branch and actual_intent == "read":
        score = 1
    elif "edit" in expected_branch and actual_intent == "edit":
        score = 1
    elif "delete" in expected_branch and actual_intent == "delete":
        score = 1
        
    return {"key": "Intent Accuracy", "score": score}

def no_crash_evaluator(run, example) -> dict:
    """A simple pass/fail if the bot successfully returned a response string."""
    response = run.outputs.get("response", "")
    score = 1 if len(response) > 5 else 0
    return {"key": "Successfully Responded", "score": score}


# --- LLM-as-a-Judge Evaluators ---

def ask_llm_judge(prompt: str) -> float:
    """Helper to query Groq to act as an LLM judge and return a float score 0.0 to 1.0"""
    try:
        groq_client = Groq() # uses GROQ_API_KEY from .env
        res = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a strict, objective AI evaluator. Return ONLY a JSON object with a 'score' key containing a float between 0.0 and 1.0."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)
        return float(data.get("score", 0.0))
    except Exception as e:
        print(f"LLM Judge Error: {e}")
        return 0.0

def faithfulness_evaluator(run, example) -> dict:
    """Measures if the response is fully supported by the retrieved context (db_results)."""
    response = run.outputs.get("response", "")
    context = run.outputs.get("db_results", "")
    intent = run.outputs.get("intent", "")
    
    # If it's pure chitchat, faithfulness doesn't apply cleanly, default to 1.0
    if intent in ["chitchat", "out_of_scope"]:
        return {"key": "Faithfulness", "score": 1.0}
        
    prompt = f"Context:\n{context}\n\nResponse:\n{response}\n\nIs the information in the Response strictly and entirely derived from the Context? Answer with 1.0 if fully faithful and grounded, or 0.0 if it hallucinates information."
    return {"key": "Faithfulness", "score": ask_llm_judge(prompt)}

def answer_relevance_evaluator(run, example) -> dict:
    """Measures if the response directly addresses the user's question."""
    question = example.inputs.get("user_input", "")
    response = run.outputs.get("response", "")
    
    prompt = f"Question:\n{question}\n\nResponse:\n{response}\n\nDoes the Response directly and comprehensively answer the Question? Answer 1.0 if perfect, 0.5 if partial, 0.0 if irrelevant."
    return {"key": "Answer Relevance", "score": ask_llm_judge(prompt)}

def context_precision_evaluator(run, example) -> dict:
    """Measures if the retrieved context is actually useful/relevant for answering the question."""
    question = example.inputs.get("user_input", "")
    context = run.outputs.get("db_results", "")
    intent = run.outputs.get("intent", "")
    
    if intent in ["chitchat", "out_of_scope"]:
        return {"key": "Context Precision", "score": 1.0}
        
    if not context:
        return {"key": "Context Precision", "score": 0.0}

    prompt = f"Question:\n{question}\n\nRetrieved Context:\n{context}\n\nIs the Retrieved Context highly relevant and sufficient to answer the Question? Answer 1.0 if perfectly useful, 0.0 if completely irrelevant."
    return {"key": "Context Precision", "score": ask_llm_judge(prompt)}


def main():
    print("==== LangSmith Evaluation Pipeline ====")
    # Initialize Databases so the agent doesn't crash during evaluation
    print("Initializing databases...")
    driver = connect_to_neo4j()
    if driver:
        init_db(driver)
    init_memory_db()
    
    prepare_dataset()
    
    print("\nRunning evaluation against LangSmith with Advanced Groq LLM-as-a-Judge...")
    print("   (This runs 13 tests and evaluates Faithfulness, Answer Relevance, and Context Precision.)\n")
    
    experiment_results = evaluate(
        run_agent,
        data=DATASET_NAME,
        evaluators=[
            intent_accuracy_evaluator, 
            no_crash_evaluator,
            faithfulness_evaluator,
            answer_relevance_evaluator,
            context_precision_evaluator
        ],
        experiment_prefix="LLM-Evaluator-Run",
        description="Run evaluating RAG metrics: Faithfulness, Answer Relevance, Context Precision.",
    )
    
    print("\nEvaluation complete! Go to https://smith.langchain.com/o/default/datasets to view your charts and metrics.")

if __name__ == "__main__":
    main()
