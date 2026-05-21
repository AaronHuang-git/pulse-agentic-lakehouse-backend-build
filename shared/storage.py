"""MinIO/S3 storage helper.

Wraps the official minio-py client with the configuration our services need
and a small set of helpers (put_stream, stat_object, object_url). All methods
are sync; call sites that live inside async code should wrap them with
``await asyncio.to_thread(...)``.
"""
from __future__ import annotations

from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from shared.config import get_settings

settings = get_settings()


def get_client() -> Minio:
    """Return a configured Minio client. Cheap to call repeatedly."""
    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=False,  # local MinIO is plain HTTP
    )


def put_stream(
    object_key: str,
    data: BinaryIO,
    length: int,
    content_type: str = "application/octet-stream",
) -> None:
    """Upload a streamed object to the configured bucket."""
    client = get_client()
    client.put_object(
        bucket_name=settings.minio_bucket,
        object_name=object_key,
        data=data,
        length=length,
        content_type=content_type,
    )


def stat_object(object_key: str) -> dict[str, str | int] | None:
    """Return basic metadata for an object, or None if it does not exist."""
    client = get_client()
    try:
        info = client.stat_object(settings.minio_bucket, object_key)
    except S3Error as e:
        if e.code == "NoSuchKey":
            return None
        raise
    return {
        "key": object_key,
        "size": info.size or 0,
        "etag": info.etag or "",
        "content_type": info.content_type or "",
    }


def object_url(object_key: str) -> str:
    """Return the canonical ``s3://`` URL for an object key."""
    return f"s3://{settings.minio_bucket}/{object_key}"
