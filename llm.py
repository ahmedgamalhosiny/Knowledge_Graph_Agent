import os
import json
import logging
from typing import Dict, List, Any

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

MODEL_NAME = "openai/gpt-oss-120b"

CLASSIFIER_SYSTEM = """
**ROLE**
You are a precise knowledge graph command parser.

**OBJECTIVE**
Extract ALL relevant subject-predicate-object triples from the user's input and classify the intent.
The user may write with typos, informal phrasing, or incomplete sentences — always infer the most
likely meaning (e.g. "wrok" → "work", "ahmed wrok for" → inquire about Ahmed's employer).

**VALID INTENTS**
- "add"     → store new information
- "inquire" → ask a question / retrieve information
- "edit"    → correct or update existing information
- "delete"  → remove a fact
- "unknown" → cannot understand at all

**RULES & EXTRACTION**
- Edit signals include: "instead", "rather", "actually", "no longer", "not anymore", "change", "update", "correct", "fix".
- Predicates MUST be in UPPERCASE_WITH_UNDERSCORES.
- For questions like "X works for?", "where does X live?", "who is X?" → intent is ALWAYS "inquire".
- Use the most natural, properly capitalised form of entity names (e.g. "ahmed" → "Ahmed").

**OUTPUT FORMAT**
Output ONLY valid JSON — no explanation, no markdown:
{
  "intent": "add|inquire|edit|delete|unknown",
  "triples": [
    {"subject": "Ahmed", "predicate": "WORKS_FOR", "object": ""}
  ]
}
For inquire triples, leave the unknown side as an empty string "".
""".strip()

SYNTHESIS_PROMPT = """
**ROLE**
You are a helpful and friendly knowledge graph assistant.

**OBJECTIVE**
Turn the raw database result into a short, natural, friendly conversational answer.

**MUST DO / RULES**
- Do NOT talk about technical terms (Cypher, nodes, relations, JSON, triples...).
- The database result is the ONLY source of truth — never hallucinate or invent facts.
- If the database says "No information about X found in the database" → clearly tell the user
  that you don't have any stored information about that entity yet. Be honest and brief.
- If conflicting facts: mention the most recent or list them clearly.
- Keep answers concise — 1 to 3 sentences max.

**EXAMPLES**
- DB: "Stored/updated: Ahmed LIVES_IN Cairo"  
  Output: "Got it! Ahmed now lives in Cairo."

- DB: "No information about 'Banana' found in the database."  
  Output: "I don't have any information about Banana stored yet."

- DB: Multiple facts about Ahmed  
  Output: "Ahmed lives in Cairo and works at ODC."
""".strip()

def create_llm(temperature: float = 0.1) -> ChatGroq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment")

    return ChatGroq(
        model=MODEL_NAME,
        api_key=api_key,
        temperature=temperature,
    )

def parse_command(
    llm: ChatGroq,
    text: str,
    history: List[Any]
) -> Dict[str, Any]:
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=CLASSIFIER_SYSTEM),
        MessagesPlaceholder("history"),
        HumanMessage(content=text),
    ])

    try:
        chain = prompt | llm
        resp = chain.invoke({"history": history})
        content = resp.content.strip()

        # Cleanup common LLM junk
        if content.startswith("```json"):
            content = content.split("```json", 1)[1].rsplit("```", 1)[0].strip()
        content = content.strip()

        data = json.loads(content)

        if "intent" not in data or "triples" not in data:
            raise ValueError("Missing intent or triples")

        if not isinstance(data["triples"], list):
            data["triples"] = []

        return data

    except Exception as e:
        logger.warning("Parse failed: %s\nRaw:\n%s", e, resp.content if 'resp' in locals() else '—')
        return {"intent": "unknown", "triples": []}

def natural_response(llm: ChatGroq, question: str, db_text: str) -> str:
    p = ChatPromptTemplate.from_messages([
        SystemMessage(content=SYNTHESIS_PROMPT),
        HumanMessage(content=f"User: {question}\n\nDatabase result:\n{db_text}")
    ])

    try:
        chain = p | llm
        resp = chain.invoke({})
        return resp.content.strip()
    except Exception as e:
        logger.error("Synthesis failed: %s", e)
        return "Something went wrong while preparing the answer."
