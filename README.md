# Knowledge Graph Agent

A natural language chatbot that extracts facts from conversations and stores them in a Neo4j knowledge graph. Powered by **LlamaIndex**.

## Idea & Workflow
1. **Understand**: User inputs a fact or asks a question.
2. **Extract**: An LLM (Groq via LlamaIndex) parses the input into subject-predicate-object triples.
3. **Execute**: Raw Cypher queries update or search the Neo4j graph database.
4. **Respond**: The LLM synthesizes raw database results into a friendly reply.

## Why LlamaIndex?
- **Data-first design**: LlamaIndex is purpose-built for connecting LLMs to data sources like Neo4j.
- **Clean LLM abstraction**: `Groq` LLM + `ChatMessage` make prompt management simple and explicit.
- **Future-ready**: LlamaIndex's `KnowledgeGraphIndex` enables auto triple extraction from documents.

## Why Neo4j?
- **Relationships First**: The graph structure is perfect for storing interconnected facts natively.
- **Flexible**: Easily add new types of entities and connections on the fly.
- **Fast Traversal**: Finds connections between concepts extremely efficiently.

## Technical Notes
- Requires a `.env` file with `GROQ_API_KEY`, `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`.
- Built using `llama-index-core`, `llama-index-llms-groq`, and the `neo4j` Python driver.
- Uses `openai/gpt-oss-120b` via Groq.
- **database/**: Driver connection and Cypher operations.
- **agent/**: LlamaIndex-powered nodes and state management.
- **main.py**: Chatbot REPL loop with conversation history.

## Architecture Diagram
The system follows a modular state-machine design:

![Architecture Diagram](![alt text](images/graph.PNG))

## Running
```bash
python main.py
```
