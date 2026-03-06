# Knowledge Graph Agent

A natural language chatbot that extracts facts from conversations and stores them in a knowledge graph.

## Idea & Workflow
1. **Understand**: User inputs a fact or asks a question.
2. **Extract**: An LLM (Groq) parses the input into subject-predicate-object triples.
3. **Execute**: Cypher queries update or search the Neo4j graph database.
4. **Respond**: The LLM synthesizes raw database results into a friendly reply.

## Why Neo4j?
- **Relationships First**: The graph structure is perfect for storing interconnected facts natively (e.g., `Ahmed -[LIVES_IN]-> Cairo`).
- **Flexible**: Easily add new types of entities and connections on the fly without rigid schemas.
- **Fast Traversal**: Finds connections between concepts extremely efficiently.

## Technical Notes
- Requires a `.env` file with `GROQ_API_KEY`, `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`.
- Built simply using `langchain-groq` and `langchain-neo4j`.
- **db.py**: Cypher queries and database operations.
- **llm.py**: LLM configurations, prompt definitions, and structured parsing.
- **main.py**: Chatbot REPL loop.
