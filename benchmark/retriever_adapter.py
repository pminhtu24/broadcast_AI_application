import time
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

from langchain_neo4j import Neo4jGraph, Neo4jVector
from langchain_community.embeddings import InfinityEmbeddings

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.config.settings import settings


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
            chunks = self._graph_vector_fulltext_search(query)

        latency_ms = (time.perf_counter() - t0) * 1000
        return RetrievalResult(
            mode=mode, query=query, chunks=chunks, latency_ms=latency_ms
        )

    def _get_config(self, mode: str) -> dict:
        from backend.app.config.constants import CHAT_MODE_CONFIG_MAP

        return CHAT_MODE_CONFIG_MAP[mode]

    def _vector_search(self, query: str) -> List[str]:
        config = self._get_config("vector")
        store = Neo4jVector.from_existing_index(
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
        docs = store.similarity_search(query, k=self.top_k)
        return [doc.page_content for doc in docs]

    def _fulltext_search(self, query: str) -> List[str]:
        config = self._get_config("fulltext")
        store = Neo4jVector.from_existing_index(
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
        docs = store.similarity_search(query, k=self.top_k)
        return [doc.page_content for doc in docs]

    def _graph_vector_search(self, query: str) -> List[str]:
        config = self._get_config("graph_vector")
        store = Neo4jVector.from_existing_index(
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
        docs = store.similarity_search(query, k=self.top_k)
        return [doc.page_content for doc in docs]

    def _graph_vector_fulltext_search(self, query: str) -> List[str]:
        config = self._get_config("graph_vector_fulltext")
        store = Neo4jVector.from_existing_index(
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
        docs = store.similarity_search(query, k=self.top_k)
        return [doc.page_content for doc in docs]
