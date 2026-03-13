import os
import logging
from typing import Optional
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
