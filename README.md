# Knowledge Graph Agent

A natural language chatbot that extracts facts from conversations and stores them in a Neo4j knowledge graph. Now powered by **LlamaIndex**.

## Idea & Workflow
1. **Understand**: User inputs a fact or asks a question.
2. **Extract**: An LLM (Groq via LlamaIndex) parses the input into subject-predicate-object triples.
3. **Execute**: Raw Cypher queries update or search the Neo4j graph database.
4. **Respond**: The LLM synthesizes raw database results into a friendly reply.

## Why LlamaIndex?
- **Data-first design**: LlamaIndex is purpose-built for connecting LLMs to data sources like Neo4j.
- **Clean LLM abstraction**: `Groq` LLM + `ChatMessage` make prompt management simple and explicit.
- **Future-ready**: LlamaIndex's `KnowledgeGraphIndex` enables auto triple extraction from documents (Phase 2).

## Why Neo4j?
- **Relationships First**: The graph structure is perfect for storing interconnected facts natively (e.g., `Ahmed -[LIVES_IN]-> Cairo`).
- **Flexible**: Easily add new types of entities and connections on the fly without rigid schemas.
- **Fast Traversal**: Finds connections between concepts extremely efficiently.

## Technical Notes
- Requires a `.env` file with `GROQ_API_KEY`, `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`.
- Built using `llama-index-core`, `llama-index-llms-groq`, and the raw `neo4j` Python driver.
- **db.py**: Raw `neo4j` driver — Cypher queries and all database operations.
- **llm.py**: LlamaIndex `Groq` LLM, `ChatMessage`-based prompts, parsing & synthesis.
- **main.py**: Chatbot REPL loop with `ChatMessage` conversation history.

## Branches
- `main` — Original LangChain implementation
- `llamaindex` — This branch: LlamaIndex implementation

## Running
```bash
python main.py
```
