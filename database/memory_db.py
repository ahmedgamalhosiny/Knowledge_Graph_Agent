import sqlite3
import os
import logging
from typing import List

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "memory.db")

def init_memory_db():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact TEXT UNIQUE,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to init memory db: {e}")

def save_memory(fact: str) -> bool:
    if not fact or not fact.strip():
        return False
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO user_memories (fact) VALUES (?)
            ''', (fact.strip(),))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to save memory: {e}")
        return False

def retrieve_memories(query: str, limit: int = 5) -> List[str]:
    # Very basic text search for SQLite.
    # Split query into words to find matching facts.
    words = [w for w in query.replace('?', '').replace('.', '').replace(',', '').split() if len(w) > 3]

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if words:
                # Try finding facts containing key words
                conditions = " OR ".join([f"fact LIKE ?" for w in words])
                params = [f"%{w}%" for w in words]
                params.append(limit)
                cursor.execute(f'''
                    SELECT fact FROM user_memories WHERE {conditions} ORDER BY timestamp DESC LIMIT ?
                ''', tuple(params))
                results = cursor.fetchall()
                if not results:
                    # Fallback to recent generic memories
                    cursor.execute('SELECT fact FROM user_memories ORDER BY timestamp DESC LIMIT 2')
                    results = cursor.fetchall()
            else:
                cursor.execute('SELECT fact FROM user_memories ORDER BY timestamp DESC LIMIT ?', (limit,))
                results = cursor.fetchall()
            return [r[0] for r in results]
    except Exception as e:
        logger.error(f"Failed to retrieve memories: {e}")
        return []
