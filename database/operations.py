import re
import logging
from typing import Dict, List
from neo4j import Driver

logger = logging.getLogger(__name__)

def normalize_predicate(raw: str) -> str:
    # Normalize predicate for Neo4j
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

def db_inquire(driver: Driver, entities: List[str]) -> List[str]:
    # Search for entity relations in bulk
    cleaned_entities = [e.strip() for e in entities if e and e.strip()]
    if not cleaned_entities:
        return []

    cypher_exact = """
    UNWIND $ents AS ent
    MATCH (e:Entity)-[r]-(other:Entity)
    WHERE toLower(e.name) = toLower(ent)
    RETURN DISTINCT e.name AS center,
           type(r) AS rel,
           other.name AS target,
           CASE WHEN startNode(r) = e THEN '→' ELSE '←' END AS dir
    ORDER BY center, rel
    LIMIT 50
    """

    # Build a single Lucene query string: "EntityA~ OR EntityB~"
    # The '~' suffix enables fuzzy matching in the Lucene engine.
    # CALL db.index.fulltext.queryNodes requires a single string argument,
    # so we cannot UNWIND inside it — we compose the query in Python instead.
    lucene_query = " OR ".join(f"{e}~" for e in cleaned_entities)

    cypher_fuzzy = """
    CALL db.index.fulltext.queryNodes("entityNameIndex", $query_str) YIELD node AS e
    MATCH (e)-[r]-(other:Entity)
    RETURN DISTINCT e.name AS center,
           type(r) AS rel,
           other.name AS target,
           CASE WHEN startNode(r) = e THEN '→' ELSE '←' END AS dir
    ORDER BY center, rel
    LIMIT 50
    """

    entity_label = ", ".join(f"'{e}'" for e in cleaned_entities)

    try:
        with driver.session() as session:
            rows = list(session.run(cypher_exact, ents=cleaned_entities))

            if not rows:
                rows = list(session.run(cypher_fuzzy, query_str=lucene_query))
                if rows:
                    logger.info("Exact match not found for %s; using fuzzy results.", cleaned_entities)
                else:
                    return [f"No information about {entity_label} found in the database."]

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
            else f"Not found: {subj} {pred} {obj}"
        )
    except Exception as e:
        logger.error("Delete failed: %s", e)
        return "Delete operation failed."
