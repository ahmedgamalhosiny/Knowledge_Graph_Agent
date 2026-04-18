import os
import sys
import logging
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
from agent.graph import create_graph
from database.connection import connect_to_neo4j, init_db
from database.memory_db import init_memory_db

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Silence noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.WARNING)

def main():
    load_dotenv()

    print("\n" + "="*65)
    print("  Knowledge Graph Chatbot (Architect Edition)")
    print("="*65 + "\n")

    # 1. Initialize Database Connection and Indices
    init_memory_db()
    driver = connect_to_neo4j()
    if driver:
        init_db(driver)
    else:
        logging.error("Could not establish initial database connection. Exiting.")
        return

    # 2. Create the Graph
    graph = create_graph()
    
    print("Ready! You can tell facts or ask questions.")
    print("Type exit / quit to stop.\n")

    # We use a static thread_id for this single-user CLI session.
    # In a multi-user app, this would be a user/session ID.
    config = {"configurable": {"thread_id": "cli-session-1"}}

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ("exit", "quit", "q", ""):
                print("\nGoodbye!\n")
                break

            # Run the graph
            # Note: history is now managed by the MemorySaver checkpointer
            initial_state = {
                "user_input": user_input
            }
            
            final_state = graph.invoke(initial_state, config=config)
            
            print(f"Bot: {final_state.get('response', 'I encountered an issue processing that.')}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!\n")
            break
        except Exception as e:
            logging.error(f"Error during execution: {e}")
            print(f"An error occurred. Please try again.\n")

if __name__ == "__main__":
    main()
