import logging
from typing import List, Any
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from db import connect_to_neo4j, execute
from llm import create_llm, parse_command, natural_response


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Silence noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.WARNING)
logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)

def main():
    load_dotenv()
    
    print("\n" + "═"*65)
    print("  Knowledge Graph Chatbot")
    print("═"*65 + "\n")

    llm = create_llm()
    graph = connect_to_neo4j()

    if not graph:
        print("Cannot start without database connection.")
        return

    print("Ready! You can tell facts or ask questions.\n")
    print("\nType exit / quit to stop.\n")

    history: List[Any] = []

    while True:
        try:
            inp = input("You: ").strip()
            if inp.lower() in ("exit", "quit", "q", ""):
                print("\nGoodbye!\n")
                break

            parsed = parse_command(llm, inp, history)
            raw_db = execute(graph, parsed, inp)
            answer = natural_response(llm, inp, raw_db)

            print(f"Bot: {answer}\n")

            history.append(HumanMessage(content=inp))
            history.append(AIMessage(content=answer))
            if len(history) > 10:
                history = history[-10:]

        except KeyboardInterrupt:
            print("\nGoodbye!\n")
            break
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()
