from langchain_neo4j import Neo4jGraph, Neo4jVector
from langchain_community.embeddings import InfinityEmbeddings
from typing import List, Dict
from settings import settings
from constants import (
    CHAT_DEFAULT_MODE,
    CHAT_MODE_CONFIG_MAP,
    VECTOR_SEARCH_TOP_K,
    CHAT_SEARCH_KWARG_SCORE_THRESHOLD,
    FULLTEXT_INDEX_NAME,
)


embeddings = InfinityEmbeddings(
    model="models/Vietnamese_Embedding_v2",
    infinity_api_url=settings.INFINITY_URL,
)

graph_db = Neo4jGraph(
    url=settings.NEO4J_URI,
    username=settings.NEO4J_USERNAME,
    password=settings.NEO4J_PASSWORD.get_secret_value(),
    refresh_schema=False,
)


def _get_vector_store(retrieval_query: str) -> Neo4jVector:
    return Neo4jVector.from_existing_index(
        embedding=embeddings,
        url=settings.NEO4J_URI,
        username=settings.NEO4J_USERNAME,
        password=settings.NEO4J_PASSWORD.get_secret_value(),
        index_name="vector",
        node_label="Chunk",
        text_node_property="text",
        embedding_node_property="embedding",
        retrieval_query=retrieval_query,
    )


# Vector search
def vector_search(
    question: str,
    mode: str = CHAT_DEFAULT_MODE,
    k: int = VECTOR_SEARCH_TOP_K,
) -> List[Dict]:
    config = CHAT_MODE_CONFIG_MAP[mode]
    store = _get_vector_store(config["retrieval_query"])
    results = []
    try:
        docs_and_scores = store.similarity_search_with_score(question, k=k)
        for doc, score in docs_and_scores:
            if score < CHAT_SEARCH_KWARG_SCORE_THRESHOLD:
                continue
            meta = doc.metadata or {}
            results.append(
                {
                    "text": doc.page_content,
                    "document_name": meta.get("source", "unknown"),
                    "excerpt": doc.page_content[:300],
                    "chunk_id": (meta.get("chunkdetails") or [{}])[0].get("id", ""),
                    "score": round(float(score), 4),
                    "search_type": mode,
                    "entities": meta.get("entities", {}),
                }
            )
    except Exception as e:
        print(f"[VectorSearch ERROR] {e}")
    print(f"[VectorSearch:{mode}] {len(results)} results")
    return results


# Fulltext search
def fulltext_search(question: str, k: int = 3) -> List[Dict]:
    results = []
    try:
        cypher = f"""
        CALL db.index.fulltext.queryNodes('{FULLTEXT_INDEX_NAME}', $keywords)
        YIELD node, score
        MATCH (node)-[:PART_OF]->(d:Document)
        RETURN
            node.text                       AS text,
            d.fileName                      AS document_name,
            substring(node.text, 0, 300)    AS excerpt,
            node.id                         AS chunk_id,
            score                           AS score
        LIMIT $limit
        """
        rows = graph_db.query(cypher, {"keywords": question, "limit": k})
        for row in rows:
            results.append(
                {
                    "text": row["text"],
                    "document_name": row["document_name"],
                    "excerpt": row["excerpt"],
                    "chunk_id": row["chunk_id"],
                    "score": round(float(row["score"]) * 0.8, 4),
                    "search_type": "fulltext",
                    "entities": {},
                }
            )
    except Exception as e:
        print(f"[FulltextSearch ERROR] {e}")
    print(f"[FulltextSearch] {len(results)} results")
    return results


# Hybrid retrieve — main entry point
def hybrid_retrieve(
    question: str,
    top_k: int = VECTOR_SEARCH_TOP_K,
    mode: str = CHAT_DEFAULT_MODE,
) -> List[Dict]:
    all_results = []
    all_results.extend(vector_search(question, mode=mode, k=top_k))

    if CHAT_MODE_CONFIG_MAP[mode].get("keyword_index"):
        all_results.extend(fulltext_search(question, k=3))

    seen: Dict[str, dict] = {}
    for r in all_results:
        cid = r.get("chunk_id") or r["text"][:80]
        if cid not in seen:
            seen[cid] = r.copy()
        else:
            types = set(seen[cid].get("search_type", "").split("+"))
            types.add(r.get("search_type", ""))
            seen[cid]["search_type"] = "+".join(sorted(t for t in types if t))
            if r["score"] > seen[cid]["score"]:
                seen[cid]["score"] = r["score"]

    ranked = sorted(
        seen.values(),
        key=lambda x: (len(x.get("search_type", "").split("+")), x["score"]),
        reverse=True,
    )
    top = ranked[:top_k]
    print(f"[HybridRetrieve:{mode}] {len(top)}/{len(all_results)} chunks")
    return top


# Format LLM
def format_for_llm(chunks: List[Dict]) -> tuple[str, List[Dict]]:
    context_parts = []
    citations = []
    for i, chunk in enumerate(chunks, 1):
        doc_name = chunk.get("document_name", "unknown")
        s_type = chunk.get("search_type", "")
        context_parts.append(
            f"[Tài liệu {i}: {doc_name} | via {s_type}]\n{chunk['text']}"
        )
        citations.append(
            {
                "filename": doc_name,
                "excerpt": chunk.get("excerpt", chunk["text"][:200]),
                "score": chunk["score"],
                "search_type": s_type,
            }
        )
    return "\n\n---\n\n".join(context_parts), citations


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    tests = [
        "HP8 đơn giá bao nhiêu?",
        "Giá quảng cáo khung giờ vàng kênh THP?",
        "Gói 3 bao gồm những gì?",
    ]
    for q in tests:
        print(f"\n{'=' * 60}")
        print(f"Q: {q}")
        chunks = hybrid_retrieve(q, top_k=10)
        _, citations = format_for_llm(chunks)
        for c in citations:
            print(
                f"  [{c['search_type']:30s}] score={c['score']:.3f} | {c['filename']}"
            )
            print(f"  └─ {c['excerpt'][:120].strip()}...")
