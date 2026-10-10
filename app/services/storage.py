"""Tiny S3-compatible object storage layer (Cloudflare R2 today, AWS S3 tomorrow).

Everything provider-specific lives in `_client()`: moving to S3 means changing env vars
(and dropping the endpoint), not code. The bucket is private — downloads only happen
through short-lived presigned URLs, never public ones.
"""

import asyncio
from functools import lru_cache
from typing import BinaryIO
from urllib.parse import quote

import boto3
from botocore.config import Config

from app.core.config import get_settings


class StorageNotConfiguredError(RuntimeError):
    """Raised when the storage env vars are missing."""


@lru_cache
def _client():
    s = get_settings()
    if not (s.cloudflare_access_key and s.cloudflare_secret_access and s.cloudflare_bucket_name):
        raise StorageNotConfiguredError("Object storage is not configured")
    return boto3.client(
        "s3",
        endpoint_url=s.cloudflare_bucket_endpoint or None,  # omit for AWS S3
        aws_access_key_id=s.cloudflare_access_key,
        aws_secret_access_key=s.cloudflare_secret_access,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def _bucket() -> str:
    return get_settings().cloudflare_bucket_name  # type: ignore[return-value]


def _content_disposition(filename: str) -> str:
    """`attachment` with an ASCII fallback plus the RFC 5987 UTF-8 name."""
    ascii_name = filename.encode("ascii", "ignore").decode().replace('"', "") or "file"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


async def upload_fileobj(key: str, fileobj: BinaryIO, content_type: str) -> None:
    await asyncio.to_thread(
        _client().upload_fileobj, fileobj, _bucket(), key, ExtraArgs={"ContentType": content_type}
    )


async def delete(key: str) -> None:
    await asyncio.to_thread(_client().delete_object, Bucket=_bucket(), Key=key)


def presigned_download_url(key: str, filename: str, expires_in: int = 300) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": _bucket(),
            "Key": key,
            "ResponseContentDisposition": _content_disposition(filename),
        },
        ExpiresIn=expires_in,
    )
