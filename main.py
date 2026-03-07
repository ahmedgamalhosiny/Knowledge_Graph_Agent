import logging
from typing import List
from dotenv import load_dotenv

from llama_index.core.llms import ChatMessage, MessageRole

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
    print("  Knowledge Graph Chatbot  (powered by LlamaIndex)")
    print("═"*65 + "\n")

    llm    = create_llm()
    driver = connect_to_neo4j()

    if not driver:
        print("Cannot start without database connection.")
        return

    print("Ready! You can tell facts or ask questions.")
    print("Type exit / quit to stop.\n")

    history: List[ChatMessage] = []

    while True:
        try:
            inp = input("You: ").strip()
            if inp.lower() in ("exit", "quit", "q", ""):
                print("\nGoodbye!\n")
                break

            parsed = parse_command(llm, inp, history)
            raw_db = execute(driver, parsed, inp)
            answer = natural_response(llm, inp, raw_db)

            print(f"Bot: {answer}\n")

            # Keep rolling window of last 10 messages (5 turns)
            history.append(ChatMessage(role=MessageRole.USER,      content=inp))
            history.append(ChatMessage(role=MessageRole.ASSISTANT,  content=answer))
            if len(history) > 10:
                history = history[-10:]

        except KeyboardInterrupt:
            print("\nGoodbye!\n")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
