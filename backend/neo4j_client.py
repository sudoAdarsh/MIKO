from neo4j import GraphDatabase
from .config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def init_schema(self):
        q1 = "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE"
        q2 = "CREATE INDEX user_username IF NOT EXISTS FOR (u:User) ON (u.username)"
        with self.driver.session() as s:
            s.run(q1)
            s.run(q2)

    def ensure_user_node(self, user_id: str, username: str):
        q = """
        MERGE (u:User {user_id: $user_id})
        SET u.username = $username
        RETURN u
        """
        with self.driver.session() as s:
            s.run(q, user_id=user_id, username=username)

    def add_memory(self, user_id: str, memory: dict):
        q = """
        MATCH (u:User {user_id: $user_id})
        CREATE (m:Memory {
          memory_id: $memory_id,
          text: $text,
          kind: $kind,
          confidence: $confidence,
          source: $source,
          created_at: datetime()
        })
        CREATE (u)-[:HAS_MEMORY]->(m)
        RETURN m
        """
        with self.driver.session() as s:
            s.run(q, user_id=user_id, **memory)

    def get_memories(self, user_id: str, limit: int = 10):
        q = """
        MATCH (u:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory)
        RETURN m.memory_id AS memory_id, m.text AS text, m.kind AS kind, m.confidence AS confidence,
               m.source AS source, m.created_at AS created_at
        ORDER BY m.created_at DESC
        LIMIT $limit
        """
        with self.driver.session() as s:
            rows = s.run(q, user_id=user_id, limit=limit)
            return [dict(r) for r in rows]