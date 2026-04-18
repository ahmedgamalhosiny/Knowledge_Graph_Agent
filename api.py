import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from agent.graph import create_graph
from database.connection import connect_to_neo4j, init_db
from database.memory_db import init_memory_db

# Configure minimal logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

# Single global dependencies to optimize speed across requests
GLOBAL_STATE = {
    "graph": None,
    "driver": None,
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    load_dotenv()
    logger.info("Initializing Neo4j and SQLite databases...")
    init_memory_db()
    
    driver = connect_to_neo4j()
    if driver:
        init_db(driver)
        GLOBAL_STATE["driver"] = driver
    else:
        logger.error("Failed to connect to Neo4j on startup.")
    
    logger.info("Compiling LangGraph agent...")
    GLOBAL_STATE["graph"] = create_graph()
    
    yield
    # --- Shutdown ---
    logger.info("Closing Neo4j connections...")
    if GLOBAL_STATE["driver"]:
        GLOBAL_STATE["driver"].close()


app = FastAPI(
    title="Knowledge Graph API",
    description="REST API wrapping the LangGraph state machine.",
    version="1.0.0",
    lifespan=lifespan
)


# --- Models ---
class ChatRequest(BaseModel):
    session_id: str
    text: str


class ChatResponse(BaseModel):
    response: str
    intent: str
    db_results: str
    extracted_memories: list[str]


# --- Endpoints ---
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    graph = GLOBAL_STATE["graph"]
    if not graph:
        raise HTTPException(status_code=500, detail="Graph not initialized")

    config = {"configurable": {"thread_id": request.session_id}}
    
    initial_state = {
        "user_input": request.text
    }

    try:
        # We use invoke synchronously, but you could use ainvoke if your nodes supported full async.
        final_state = graph.invoke(initial_state, config=config)
        
        return ChatResponse(
            response=final_state.get("response", ""),
            intent=final_state.get("intent", "unknown"),
            db_results=final_state.get("db_results", ""),
            extracted_memories=final_state.get("extracted_memories", [])
        )
        
    except Exception as e:
        logger.error(f"Error during agent execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "healthy", "neo4j_connected": GLOBAL_STATE["driver"] is not None}
