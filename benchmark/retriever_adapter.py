import time
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

from langchain_neo4j import Neo4jGraph, Neo4jVector
from langchain_community.embeddings import InfinityEmbeddings

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.config.settings import settings
from backend.app.config.constants import (
    CHAT_MODE_CONFIG_MAP,
    FULLTEXT_INDEX_NAME,
    CHAT_SEARCH_KWARG_SCORE_THRESHOLD,
)


MODES = ["vector", "fulltext", "graph_vector", "graph_vector_fulltext"]


@dataclass
class RetrievalResult:
    mode: str
    query: str
    chunks: List[str]
    latency_ms: float


class Neo4jRetrieverAdapter:
    def __init__(
        self,
        top_k: int = 5,
        embedding_model: str = "models/Vietnamese_Embedding_v2",
    ):
        self.top_k = top_k
        self.embeddings = InfinityEmbeddings(
            model=embedding_model,
            infinity_api_url=settings.INFINITY_URL,
        )
        self.graph_db = Neo4jGraph(
            url=settings.NEO4J_URI,
            username=settings.NEO4J_USERNAME,
            password=settings.NEO4J_PASSWORD.get_secret_value(),
            refresh_schema=False,
        )

    def retrieve(self, query: str, mode: str) -> RetrievalResult:
        assert mode in MODES, f"Unknown mode: {mode}"

        t0 = time.perf_counter()
        if mode == "vector":
            chunks = self._vector_search(query)
        elif mode == "fulltext":
            chunks = self._fulltext_search(query)
        elif mode == "graph_vector":
            chunks = self._graph_vector_search(query)
        elif mode == "graph_vector_fulltext":
            chunks = self._hybrid_search(query, mode)

        latency_ms = (time.perf_counter() - t0) * 1000
        return RetrievalResult(
            mode=mode, query=query, chunks=chunks, latency_ms=latency_ms
        )

    def _get_config(self, mode: str) -> dict:
        return CHAT_MODE_CONFIG_MAP[mode]

    def _get_store(self, config: dict) -> Neo4jVector:
        return Neo4jVector.from_existing_index(
            embedding=self.embeddings,
            url=settings.NEO4J_URI,
            username=settings.NEO4J_USERNAME,
            password=settings.NEO4J_PASSWORD.get_secret_value(),
            index_name=config["index_name"],
            node_label="Chunk",
            text_node_property="text",
            embedding_node_property="embedding",
            retrieval_query=config["retrieval_query"],
        )

    def _vector_search(self, query: str) -> List[str]:
        config = self._get_config("vector")
        store = self._get_store(config)
        docs = store.similarity_search(query, k=self.top_k)
        return [doc.page_content for doc in docs]

    def _fulltext_search(self, query: str) -> List[str]:
        cypher = f"""
            CALL db.index.fulltext.queryNodes('{FULLTEXT_INDEX_NAME}', $keywords)
            YIELD node, score
            MATCH (node)-[:PART_OF]->(d:Document)
            RETURN node.text AS text
            LIMIT $limit
        """
        rows = self.graph_db.query(cypher, {"keywords": query, "limit": self.top_k})
        return [r["text"] for r in rows] if rows else []

    def _graph_vector_search(self, query: str) -> List[str]:
        config = self._get_config("graph_vector")
        store = self._get_store(config)
        docs = store.similarity_search(query, k=self.top_k)
        return [doc.page_content for doc in docs]

    def _hybrid_search(self, query: str, mode: str) -> List[str]:
        config = self._get_config(mode)

        all_results: Dict[str, Dict[str, Any]] = {}

        vector_results = self._vector_search_with_score(query, mode)
        for r in vector_results:
            chunk_id = r.get("chunk_id") or r["text"][:80]
            if chunk_id not in all_results:
                all_results[chunk_id] = r
            else:
                types = set(all_results[chunk_id].get("search_type", "").split("+"))
                types.add(r.get("search_type", ""))
                all_results[chunk_id]["search_type"] = "+".join(
                    sorted(t for t in types if t)
                )
                if r["score"] > all_results[chunk_id]["score"]:
                    all_results[chunk_id] = r

        if config.get("keyword_index"):
            fulltext_results = self._fulltext_search_with_score(query)
            for r in fulltext_results:
                chunk_id = r.get("chunk_id") or r["text"][:80]
                if chunk_id not in all_results:
                    all_results[chunk_id] = r
                else:
                    types = set(all_results[chunk_id].get("search_type", "").split("+"))
                    types.add(r.get("search_type", ""))
                    all_results[chunk_id]["search_type"] = "+".join(
                        sorted(t for t in types if t)
                    )
                    if r["score"] > all_results[chunk_id]["score"]:
                        all_results[chunk_id] = r

        ranked = sorted(
            all_results.values(),
            key=lambda x: (len(x.get("search_type", "").split("+")), x["score"]),
            reverse=True,
        )
        return [r["text"] for r in ranked[: self.top_k]]

    def _vector_search_with_score(self, query: str, mode: str) -> List[Dict[str, Any]]:
        config = self._get_config(mode)
        store = self._get_store(config)
        results = []
        for doc, score in store.similarity_search_with_score(query, k=self.top_k):
            if score < CHAT_SEARCH_KWARG_SCORE_THRESHOLD:
                continue
            meta = doc.metadata or {}
            results.append(
                {
                    "text": doc.page_content,
                    "chunk_id": (meta.get("chunkdetails") or [{}])[0].get("id", ""),
                    "score": round(float(score), 4),
                    "search_type": "vector" if mode == "vector" else mode,
                }
            )
        return results

    def _fulltext_search_with_score(self, query: str) -> List[Dict[str, Any]]:
        cypher = f"""
            CALL db.index.fulltext.queryNodes('{FULLTEXT_INDEX_NAME}', $keywords)
            YIELD node, score
            MATCH (node)-[:PART_OF]->(d:Document)
            RETURN node.text AS text, node.id AS chunk_id, score AS score
            LIMIT $limit
        """
        rows = self.graph_db.query(cypher, {"keywords": query, "limit": 3})
        return (
            [
                {
                    "text": r["text"],
                    "chunk_id": r.get("chunk_id", ""),
                    "score": round(float(r["score"]) * 0.8, 4),
                    "search_type": "fulltext",
                }
                for r in rows
            ]
            if rows
            else []
        )
