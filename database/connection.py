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
        logger.error("Missing credentials")
        return None

    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        with driver.session() as session:
            session.run("RETURN 1")
        logger.info("Connected to Neo4j")
        return driver
    except Exception as e:
        logger.error("Connection failed: %s", e)
        return None
