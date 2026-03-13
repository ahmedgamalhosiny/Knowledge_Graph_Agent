import os
import logging
from dotenv import load_dotenv
from agent.graph import create_graph

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

    print("\n" + "═"*65)
    print("  Knowledge Graph Chatbot (LangGraph Edition)")
    print("═"*65 + "\n")

    graph = create_graph()
    
    print("Ready! You can tell facts or ask questions.")
    print("Type exit / quit to stop.\n")

    history = []

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ("exit", "quit", "q", ""):
                print("\nGoodbye!\n")
                break

            # Run the graph
            # Note: LangGraph expects a dict as input matching the AgentState
            initial_state = {
                "user_input": user_input,
                "history": history
            }
            
            final_state = graph.invoke(initial_state)
            
            print(f"Bot: {final_state['response']}\n")

            # Update history (keep last 10 messages)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": final_state['response']})
            if len(history) > 10:
                history = history[-10:]

        except KeyboardInterrupt:
            print("\nGoodbye!\n")
            break
        except Exception as e:
            logging.error(f"Error: {e}")
            print(f"An error occurred. Please try again.\n")

if __name__ == "__main__":
    main()
