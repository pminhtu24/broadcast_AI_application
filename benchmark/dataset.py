import json
from pathlib import Path
from typing import List, Dict


DATASET_PATH = "/home/tupham/Documents/Development/broadcast-AI-application/tests/rag_evaluation_dataset.json"


def load_dataset(path: str = DATASET_PATH) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["questions"]


def get_test_cases() -> List[Dict]:
    queries = load_dataset()
    return [
        {
            "user_input": q["question"],
            "reference": q["ground_truth"]["expected_answer"],
            "id": q["id"],
            "category": q["category"],
            "intent": q.get("intent"),
            "difficulty": q.get("difficulty"),
        }
        for q in queries
    ]
