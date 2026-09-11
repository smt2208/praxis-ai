"""
app/services/storage.py

S3 image storage service for persisting chat images across conversation turns.
Uploads base64 data-URI images to S3 and returns public URLs that can be
stored in message metadata and reloaded by the vision agent on future turns.
"""
import base64
import logging
import uuid
from io import BytesIO

import boto3
from botocore.exceptions import ClientError

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Lazy-initialised S3 client (created on first call, not at import time)
_s3_client = None


def _get_s3_client():
    """Return a reusable boto3 S3 client, creating it once on first call."""
    global _s3_client
    if _s3_client is None:
        client_kwargs = {"region_name": settings.aws_s3_region}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        _s3_client = boto3.client("s3", **client_kwargs)
    return _s3_client


def _parse_data_uri(data_uri: str) -> tuple[str, bytes]:
    """
    Parse a base64 data URI like 'data:image/png;base64,iVBOR...'
    Returns (content_type, raw_bytes).
    """
    if data_uri.startswith("data:"):
        header, encoded = data_uri.split(",", 1)
        # header = 'data:image/png;base64'
        content_type = header.split(":")[1].split(";")[0]
    else:
        # Raw base64 without data URI prefix — assume PNG
        encoded = data_uri
        content_type = "image/png"

    raw_bytes = base64.b64decode(encoded)
    return content_type, raw_bytes


def _content_type_to_ext(content_type: str) -> str:
    """Map MIME type to file extension."""
    mapping = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/svg+xml": "svg",
    }
    return mapping.get(content_type, "png")


def upload_image_to_s3(data_uri: str, conversation_id: str) -> str | None:
    """
    Upload a base64 data-URI image to S3.

    Returns:
        The public S3 URL of the uploaded image, or None if upload fails.
    """
    if not settings.aws_s3_bucket:
        logger.warning("[Storage] S3 bucket not configured, skipping image upload")
        return None

    try:
        content_type, raw_bytes = _parse_data_uri(data_uri)
        ext = _content_type_to_ext(content_type)
        file_key = f"chat-images/{conversation_id}/{uuid.uuid4().hex}.{ext}"

        client = _get_s3_client()
        client.upload_fileobj(
            BytesIO(raw_bytes),
            settings.aws_s3_bucket,
            file_key,
            ExtraArgs={"ContentType": content_type},
        )

        # Construct the S3 URL
        url = f"https://{settings.aws_s3_bucket}.s3.{settings.aws_s3_region}.amazonaws.com/{file_key}"
        logger.info("[Storage] Uploaded image to S3: %s", file_key)
        return url

    except ClientError as e:
        logger.error("[Storage] S3 upload failed: %s", e)
        return None
    except Exception as e:
        logger.error("[Storage] Unexpected error during S3 upload: %s", e)
        return None


async def upload_images_to_s3(data_uris: list[str], conversation_id: str) -> list[str]:
    """
    Upload multiple base64 images to S3 concurrently (via thread pool).

    Returns:
        List of S3 URLs for successfully uploaded images.
    """
    import asyncio

    if not settings.aws_s3_bucket or not data_uris:
        return []

    tasks = [
        asyncio.to_thread(upload_image_to_s3, uri, conversation_id)
        for uri in data_uris[:5]  # Safety cap at 5 images
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    urls = []
    for r in results:
        if isinstance(r, str) and r:
            urls.append(r)
        elif isinstance(r, Exception):
            logger.error("[Storage] Image upload failed: %s", r)

    return urls


def delete_conversation_s3_images(conversation_id: str) -> None:
    """Delete all S3 objects stored under chat-images/{conversation_id}/."""
    if not settings.aws_s3_bucket:
        return

    try:
        client = _get_s3_client()
        prefix = f"chat-images/{conversation_id}/"
        paginator = client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=settings.aws_s3_bucket, Prefix=prefix):
            contents = page.get("Contents", [])
            if contents:
                delete_keys = [{"Key": item["Key"]} for item in contents]
                client.delete_objects(
                    Bucket=settings.aws_s3_bucket,
                    Delete={"Objects": delete_keys},
                )
        logger.info("[Storage] Purged S3 images for conversation %s", conversation_id)
    except Exception as exc:
        logger.warning("[Storage] Failed to purge S3 images for conversation %s: %s", conversation_id, exc)
