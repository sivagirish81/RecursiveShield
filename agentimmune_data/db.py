from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .config import Settings
from agentimmune.contracts import AttackSpec


COLLECTIONS = ("traces", "attacks", "attack_embeddings", "model_versions", "eval_runs")


def get_database(settings: Settings):
    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is required for MongoDB access")
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise RuntimeError("Install pymongo to use MongoDB access") from exc
    client_kwargs: dict[str, Any] = {"serverSelectionTimeoutMS": 30000}
    try:
        import certifi
    except ImportError:
        pass
    else:
        client_kwargs["tlsCAFile"] = certifi.where()
    client = MongoClient(settings.mongodb_uri, **client_kwargs)
    return client[settings.mongodb_db]


def ensure_collections(db: Any) -> None:
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
    db.attacks.create_index("attack_id", unique=True)
    db.attack_embeddings.create_index("attack_id", unique=True)
    db.attack_embeddings.create_index([("family", 1), ("seed", 1)])
    db.eval_runs.create_index("eval_run_id", unique=True)
    db.eval_runs.create_index("model_version_id")
    db.model_versions.create_index("model_version_id", unique=True)


def ensure_vector_index(db: Any, *, dimension: int) -> None:
    db.command(
        {
            "createSearchIndexes": "attack_embeddings",
            "indexes": [
                {
                    "name": "attack_embedding_vector_index",
                    "type": "vectorSearch",
                    "definition": {
                        "fields": [
                            {
                                "type": "vector",
                                "path": "embedding",
                                "numDimensions": dimension,
                                "similarity": "cosine",
                            },
                            {"type": "filter", "path": "family"},
                            {"type": "filter", "path": "seed"},
                        ]
                    },
                }
            ],
        }
    )


def upsert_attacks(db: Any, specs: Iterable[AttackSpec]) -> dict[str, int]:
    accepted = 0
    for spec in specs:
        db.attacks.update_one(
            {"attack_id": spec.attack_id},
            {"$set": spec.model_dump(mode="json")},
            upsert=True,
        )
        accepted += 1
    return {"accepted": accepted}


def write_embedding(
    db: Any,
    *,
    attack_id: str,
    family: str,
    seed: str,
    model: str,
    dimension: int,
    vector: list[float],
) -> None:
    if len(vector) != dimension:
        raise ValueError(f"Expected embedding dimension {dimension}, got {len(vector)}")
    db.attack_embeddings.update_one(
        {"attack_id": attack_id},
        {
            "$set": {
                "attack_id": attack_id,
                "family": family,
                "seed": seed,
                "model": model,
                "dimension": dimension,
                "embedding": vector,
            }
        },
        upsert=True,
    )
