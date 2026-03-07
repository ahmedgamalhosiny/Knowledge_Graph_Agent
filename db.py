import os
import re
import logging
from typing import Dict, List, Optional

from neo4j import GraphDatabase, Driver

logger = logging.getLogger(__name__)


def connect_to_neo4j() -> Optional[Driver]:
    uri      = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri or not password:
        logger.error("Missing NEO4J_URI or NEO4J_PASSWORD in .env")
        return None

    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        # connection test
        with driver.session() as session:
            session.run("RETURN 1")
        logger.info("Connected to Neo4j successfully")
        return driver
    except Exception as e:
        logger.error("Neo4j connection failed: %s", e, exc_info=True)
        return None


def normalize_predicate(raw: str) -> str:
    """Make predicate safe for Neo4j relationship type."""
    if not raw:
        return "RELATED_TO"
    s = re.sub(r'[^A-Z0-9_ ]', '', raw.upper())
    s = re.sub(r'\s+', '_', s.strip())
    s = re.sub(r'_+', '_', s)
    return s or "RELATED_TO"


def db_add_or_edit(driver: Driver, triple: Dict, original_text: str) -> str:
    subj     = triple.get("subject", "").strip()
    obj      = triple.get("object", "").strip()
    pred_raw = triple.get("predicate", "")
    pred     = normalize_predicate(pred_raw)

    if not subj or not pred or not obj:
        return ""

    cypher = f"""
    OPTIONAL MATCH (s_old:Entity {{name: $subj}})-[old:{pred}]->()
    DELETE old
    WITH 1 AS dummy
    MERGE (s:Entity {{name: $subj}})
    MERGE (o:Entity {{name: $obj}})
    MERGE (s)-[r:{pred}]->(o)
    SET r.source_text = $text,
        r.updated = datetime()
    RETURN 1
    """

    try:
        with driver.session() as session:
            session.run(cypher, subj=subj, obj=obj, text=original_text[:400])
        return f"Stored/updated: {subj} {pred} {obj}"
    except Exception as e:
        logger.error("Add/Edit error: %s", e)
        return f"Failed to store {subj} {pred} {obj}"


def db_inquire(driver: Driver, triple: Dict) -> List[str]:
    entity = (triple.get("subject") or triple.get("object") or "").strip()
    if not entity:
        return []

    cypher_exact = """
    MATCH (e:Entity)-[r]-(other:Entity)
    WHERE toLower(e.name) = toLower($ent)
    RETURN e.name AS center,
           type(r) AS rel,
           other.name AS target,
           CASE WHEN startNode(r) = e THEN '→' ELSE '←' END AS dir
    ORDER BY rel
    LIMIT 15
    """

    cypher_fuzzy = """
    MATCH (e:Entity)-[r]-(other:Entity)
    WHERE toLower(e.name) CONTAINS toLower($ent)
    RETURN e.name AS center,
           type(r) AS rel,
           other.name AS target,
           CASE WHEN startNode(r) = e THEN '→' ELSE '←' END AS dir
    ORDER BY e.name, rel
    LIMIT 15
    """

    try:
        with driver.session() as session:
            rows = list(session.run(cypher_exact, ent=entity))

            if not rows:
                rows = list(session.run(cypher_fuzzy, ent=entity))
                if rows:
                    logger.info("Exact match not found for '%s'; using fuzzy results.", entity)
                else:
                    return [f"No information about '{entity}' found in the database."]

        return [
            f"{r['center']} {r['dir']} [{r['rel']}] {r['target']}"
            for r in rows
        ]
    except Exception as e:
        logger.error("Inquire failed: %s", e)
        return ["Search failed — try again later."]


def db_delete(driver: Driver, triple: Dict) -> str:
    subj = triple.get("subject", "").strip()
    obj  = triple.get("object", "").strip()
    pred = normalize_predicate(triple.get("predicate", ""))

    if not subj or not pred or not obj:
        return ""

    cypher = f"""
    MATCH (s:Entity {{name: $subj}})-[r:{pred}]->(o:Entity {{name: $obj}})
    DELETE r
    RETURN count(r) AS cnt
    """

    try:
        with driver.session() as session:
            result = session.run(cypher, subj=subj, obj=obj)
            record = result.single()
            cnt = record["cnt"] if record else 0
        return (
            f"Deleted: {subj} {pred} {obj}"
            if cnt > 0
            else f"Did not find {subj} {pred} {obj} to delete."
        )
    except Exception as e:
        logger.error("Delete failed: %s", e)
        return "Delete operation failed."


def execute(driver: Driver, parsed: Dict, user_text: str) -> str:
    intent  = parsed.get("intent", "unknown")
    triples = parsed.get("triples", [])

    if intent == "unknown":
        return "Sorry, I didn't understand what you want to do."

    if not triples:
        return "I understood the intent but couldn't extract clear facts."

    lines = []

    for t in triples:
        if intent in ("add", "edit"):
            msg = db_add_or_edit(driver, t, user_text)
        elif intent == "inquire":
            facts = db_inquire(driver, t)
            lines.extend(facts)
            continue
        elif intent == "delete":
            msg = db_delete(driver, t)
        else:
            msg = ""

        if msg:
            lines.append(msg)

    if intent == "inquire":
        return "\n".join(lines) if lines else f"Nothing found about {triples[0].get('subject','?')[:20]}."

    return "\n".join(lines) or "Operation finished."
