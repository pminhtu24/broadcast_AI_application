import json
import sys
import time
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

logging.getLogger("neo4j").setLevel(logging.ERROR)
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from benchmark.retriever_adapter import Neo4jRetrieverAdapter, MODES
from benchmark.dataset import get_test_cases

OUTPUT_DIR = "benchmark_results"

MODE_LABELS = {
    "vector": "Vector Search",
    "fulltext": "Full-text Search",
    "graph_vector": "Graph + Vector",
    "graph_vector_fulltext": "Hybrid (Graph + Vector + Fulltext)",
}


def get_llm():
    return ChatOpenAI(
        api_key=os.getenv("VIETTEL_API_KEY"),
        base_url=os.getenv("VIETTEL_BASE_URL"),
        model=os.getenv("VIETTEL_MODEL", "openai/gpt-oss-120b"),
        temperature=0.1,
    )


def generate_answer(question: str, contexts: List[str], llm) -> str:
    context_text = "\n\n---\n\n".join(contexts)
    system_prompt = """Bạn là trợ lý AI của Đài Phát thanh và Truyền hình Hải Phòng.
Chỉ trả lời dựa trên ngữ cảnh được cung cấp. Nếu không có thông tin, nói rõ.
Trả lời ngắn gọn, có dẫn nguồn."""

    response = llm.invoke(
        [
            SystemMessage(content=system_prompt + f"\n\nNgữ cảnh:\n{context_text}"),
            HumanMessage(content=question),
        ]
    )
    return response.content


def compute_latency_stats(latencies: List[float]) -> Dict:
    if not latencies:
        return {}
    s = sorted(latencies)
    n = len(s)
    return {
        "latency_p50": round(s[int(n * 0.50)], 1),
        "latency_p95": round(s[int(n * 0.95)], 1),
        "latency_p99": round(s[min(int(n * 0.99), n - 1)], 1),
        "latency_mean": round(sum(s) / n, 1),
    }


def run_mode_benchmark(
    adapter: Neo4jRetrieverAdapter,
    generator_llm,
    queries: List[Dict],
    mode: str,
) -> tuple[List[Dict], List[float]]:
    rows = []
    latencies = []

    for i, qa in enumerate(queries, 1):
        question = qa["user_input"]
        reference = qa["reference"]

        logger.info(f"  [{i}/{len(queries)}] {question[:60]}...")

        result = adapter.retrieve(question, mode=mode)
        latencies.append(result.latency_ms)

        row = {
            "user_input": question,
            "retrieved_contexts": result.chunks,
            "reference": reference,
        }

        if generator_llm is not None:
            answer = generate_answer(question, result.chunks, generator_llm)
            row["response"] = answer

        if not result.chunks:
            logger.warning(f"    No chunks retrieved for mode={mode}")
            continue

        rows.append(row)

    return rows, latencies


def run_benchmark(
    modes: List[str] = None, include_ragas: bool = True, limit: int = None
):
    modes = modes or MODES
    queries = get_test_cases()
    if limit:
        queries = queries[:limit]
        logger.info(f"Loaded {len(queries)} test queries (limited to {limit})")
    else:
        logger.info(f"Loaded {len(queries)} test queries")
    logger.info(f"Modes: {modes}")

    results = {mode: {"latencies": [], "rows": []} for mode in modes}

    if include_ragas:
        from ragas import EvaluationDataset, evaluate
        from openai import AsyncOpenAI
        from ragas.llms import llm_factory
        from ragas.embeddings import embedding_factory
        from ragas.metrics.collections.faithfulness import Faithfulness
        from ragas.metrics.collections.context_recall import ContextRecall
        from ragas.metrics.collections.context_precision import ContextPrecision
        from ragas.metrics.collections.answer_relevancy import AnswerRelevancy

        llm = get_llm()
        client = AsyncOpenAI(
            api_key=os.getenv("VIETTEL_API_KEY"),
            base_url=os.getenv("VIETTEL_BASE_URL"),
        )
        evaluator_llm = llm_factory(
            os.getenv("VIETTEL_MODEL", "openai/gpt-oss-120b"),
            client=client,
        )
        evaluator_embeddings = embedding_factory(
            "openai",
            model="text-embedding-ada-002",
            client=client,
            interface="modern",
        )
        ragas_metrics = [
            Faithfulness(llm=evaluator_llm),
            AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings),
            ContextPrecision(llm=evaluator_llm),
            ContextRecall(llm=evaluator_llm),
        ]

    for mode in modes:
        logger.info(f"\n--- Mode: {MODE_LABELS[mode]} ---")
        rows, latencies = run_mode_benchmark(
            adapter=Neo4jRetrieverAdapter(),
            generator_llm=llm if include_ragas else None,
            queries=queries,
            mode=mode,
        )
        results[mode]["latencies"] = latencies
        results[mode]["rows"] = rows

    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)

    print("\n" + "-" * 60)
    print(f"{'Mode':<30} {'Mean (ms)':>10} {'p50':>8} {'p95':>8} {'p99':>8}")
    print("-" * 60)

    for mode in modes:
        lat_stats = compute_latency_stats(results[mode]["latencies"])
        print(
            f"{MODE_LABELS[mode]:<30} "
            f"{lat_stats.get('latency_mean', 0):>10.1f} "
            f"{lat_stats.get('latency_p50', 0):>8.1f} "
            f"{lat_stats.get('latency_p95', 0):>8.1f} "
            f"{lat_stats.get('latency_p99', 0):>8.1f}"
        )

    if include_ragas:
        print("\n" + "-" * 70)
        print(f"{'Mode':<30} {'Faith.':>8} {'Relev.':>8} {'C.Prec':>8} {'C.Recall':>8}")
        print("-" * 70)

        for mode in modes:
            data = results[mode]["rows"]
            if not data:
                continue

            eval_dataset = EvaluationDataset.from_list(data)

            try:
                eval_result = evaluate(
                    dataset=eval_dataset,
                    metrics=ragas_metrics,
                    batch_size=8,
                )

                df = eval_result.to_pandas()
                total = len(df)
                for metric_name in [
                    "faithfulness",
                    "answer_relevancy",
                    "context_precision",
                    "context_recall",
                ]:
                    if metric_name in df.columns:
                        scored = df[metric_name].notna().sum()
                        if scored < total:
                            logger.warning(
                                f"  [{mode}] {metric_name}: chỉ tính được {scored}/{total} samples "
                                f"({total - scored} bị drop do max_tokens hoặc parse fail)"
                            )

                scores = eval_result.scores[0]
                results[mode]["scores"] = scores

                print(
                    f"{MODE_LABELS[mode]:<30} "
                    f"{scores.get('faithfulness', 0):>8.3f} "
                    f"{scores.get('answer_relevancy', 0):>8.3f} "
                    f"{scores.get('context_precision', 0):>8.3f} "
                    f"{scores.get('context_recall', 0):>8.3f}"
                )
            except Exception as e:
                logger.error(f"RAGAS evaluation error for {mode}: {e}")
                print(f"{MODE_LABELS[mode]:<30} ERROR: {e}")

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    output_file = (
        Path(OUTPUT_DIR) / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    output_data = {
        "timestamp": datetime.now().isoformat(),
        "total_questions": len(queries),
        "results": {
            mode: {
                "latency_stats": compute_latency_stats(results[mode]["latencies"]),
                "ragas_scores": results[mode].get("scores"),
            }
            for mode in modes
        },
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    logger.info(f"\nResults saved to: {output_file}")
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG Retrieval Benchmark")
    parser.add_argument("--modes", nargs="+", choices=MODES, default=None)
    parser.add_argument("--no-ragas", action="store_true", help="Skip RAGAS evaluation")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Giới hạn số câu hỏi (dùng để smoke test)",
    )
    args = parser.parse_args()

    run_benchmark(modes=args.modes, include_ragas=not args.no_ragas, limit=args.limit)
