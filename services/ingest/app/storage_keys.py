"""Builders for MinIO object keys. Single source of truth for naming."""
from __future__ import annotations


def raw_key(tenant_id: str, sha256: str) -> str:
    """Path for raw uploaded artifact: ``raw/<tenant>/<sha>.csv``."""
    return f"raw/{tenant_id}/{sha256}.csv"


def parquet_key(tenant_id: str, dataset: str, sha256: str) -> str:
    """Path for derived Parquet: ``silver/<tenant>/<dataset>/<sha>.parquet``."""
    return f"silver/{tenant_id}/{dataset}/{sha256}.parquet"
