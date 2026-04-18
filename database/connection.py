import os
import atexit
import logging
from typing import Optional
from neo4j import GraphDatabase, Driver

logger = logging.getLogger(__name__)

_global_driver: Optional[Driver] = None

def connect_to_neo4j() -> Optional[Driver]:
    global _global_driver
    if _global_driver is not None:
        return _global_driver

    uri      = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri or not password:
        logger.error("Missing credentials")
        return None

    try:
        _global_driver = GraphDatabase.driver(uri, auth=(username, password))
        with _global_driver.session() as session:
            session.run("RETURN 1")
        logger.info("Connected to Neo4j")
        return _global_driver
    except Exception as e:
        logger.error("Connection failed: %s", e)
        return None

def close_driver():
    global _global_driver
    if _global_driver is not None:
        _global_driver.close()
        _global_driver = None
        logger.info("Closed Neo4j driver connection.")

atexit.register(close_driver)

def init_db(driver: Driver):
    """
    Initializes the database by creating necessary constraints and indexes.
    Safe to run even on an empty or completely brand new database.
    """
    if not driver:
        return
    
    constraint_query = '''
    CREATE CONSTRAINT entity_name IF NOT EXISTS 
    FOR (e:Entity) REQUIRE e.name IS UNIQUE
    '''
    
    # We use vector indexes or full text indexes. In older neo4j 4.x it's db.index.fulltext.createNodeIndex, 
    # but in 5.x the syntax is standard CREATE. We will use the standard 5.x approach.
    index_query = '''
    CREATE FULLTEXT INDEX entityNameIndex IF NOT EXISTS 
    FOR (n:Entity) ON EACH [n.name]
    '''
    
    try:
        with driver.session() as session:
            session.run(constraint_query)
            # Try to create the index
            session.run(index_query)
        logger.info("Database constraints and indexes initialized successfully.")
    except Exception as e:
        logger.warning(f"Warning during index initialization (safe to ignore if using Neo4j <5.x): {e}")
