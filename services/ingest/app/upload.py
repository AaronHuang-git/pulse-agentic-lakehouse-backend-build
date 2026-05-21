"""Streaming upload helper: write request body to disk + hash in one pass."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from fastapi import UploadFile

CHUNK_SIZE = 1024 * 1024  # 1 MiB


async def spool_and_hash(upload: UploadFile) -> tuple[Path, str, int]:
    """Stream the upload to a temp file while computing SHA256.

    Returns ``(temp_path, sha256_hex, total_bytes)``. Caller must delete the
    temp file when done.
    """
    hasher = hashlib.sha256()
    total = 0

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    tmp_path = Path(tmp.name)
    try:
        while True:
            chunk = await upload.read(CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
            total += len(chunk)
            tmp.write(chunk)
    finally:
        tmp.close()

    return tmp_path, hasher.hexdigest(), total
