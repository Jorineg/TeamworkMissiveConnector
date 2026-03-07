"""Download Craft document media and re-host in Supabase Storage.

Craft media URLs (r.craft.do) are temporary and rotate on each API fetch.
This module downloads images, files, drawings, and videos via the fresh URLs
from the JSON blocks API, uploads them to a `craft-files` Supabase Storage
bucket, and replaces the Craft URLs in the markdown with stable self-hosted URLs.
"""
import time
from typing import Dict, List, Optional, Tuple

import requests

from src import settings
from src.logging_conf import logger

BUCKET = "craft-files"
MEDIA_BLOCK_TYPES = {"image", "file", "drawing", "video"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

_MIME_TO_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
    "image/heic": "heic",
    "application/pdf": "pdf",
    "video/mp4": "mp4",
    "video/quicktime": "mov",
}


def process_document_media(
    doc_id: str,
    json_blocks: dict,
    parsed_markdown: str,
    session: requests.Session,
) -> str:
    """Download media from Craft, upload to Storage, replace URLs in markdown.

    Returns the markdown with Craft URLs replaced by self-hosted URLs.
    If storage is not configured, returns markdown unchanged.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return parsed_markdown

    media_blocks = _extract_media_blocks(json_blocks)
    if not media_blocks:
        return parsed_markdown

    public_base = settings.SUPABASE_PUBLIC_URL or settings.SUPABASE_URL
    url_mapping: Dict[str, str] = {}

    for block in media_blocks:
        craft_url = block.get("url")
        block_id = block.get("id")
        if not craft_url or not block_id:
            continue

        if (block.get("fileSize") or 0) > MAX_FILE_SIZE:
            logger.info("Skipping large craft file %s (%d bytes)", block.get("fileName", block_id), block.get("fileSize"))
            continue

        storage_path = _build_storage_path(doc_id, block, None)
        public_url = f"{public_base}/storage/v1/object/public/{BUCKET}/{storage_path}"

        if _asset_exists_in_storage(storage_path, session):
            url_mapping[craft_url] = public_url
            continue

        data, content_type = _download(craft_url, session)
        if not data:
            continue

        # Recompute path with actual content type if block had no mime/filename
        final_path = _build_storage_path(doc_id, block, content_type)
        if final_path != storage_path:
            if _asset_exists_in_storage(final_path, session):
                url_mapping[craft_url] = f"{public_base}/storage/v1/object/public/{BUCKET}/{final_path}"
                continue
            storage_path = final_path

        public_url = f"{public_base}/storage/v1/object/public/{BUCKET}/{storage_path}"

        if _upload_to_storage(storage_path, data, content_type or "application/octet-stream", session):
            url_mapping[craft_url] = public_url
            logger.debug("Uploaded craft %s %s → %s", block.get("type"), block_id, storage_path)

        time.sleep(0.05)

    if url_mapping:
        logger.info("Processed %d/%d craft media for doc %s", len(url_mapping), len(media_blocks), doc_id)

    return _replace_urls(parsed_markdown, url_mapping)


def _extract_media_blocks(node: dict) -> List[dict]:
    """Recursively extract all media blocks from a JSON block tree."""
    results = []
    if node.get("type") in MEDIA_BLOCK_TYPES:
        results.append(node)
    for child in node.get("content", []):
        results.extend(_extract_media_blocks(child))
    return results


def _build_storage_path(doc_id: str, block: dict, content_type: Optional[str]) -> str:
    """Build storage path: {doc_id}/{block_id}_{filename} or {doc_id}/{block_id}.{ext}."""
    block_id = block["id"]
    file_name = block.get("fileName")
    if file_name:
        safe_name = file_name.replace("/", "_").replace("\\", "_")
        return f"{doc_id}/{block_id}_{safe_name}"

    ext = _mime_to_ext(block.get("mimeType") or content_type)
    return f"{doc_id}/{block_id}.{ext}"


def _mime_to_ext(mime: Optional[str]) -> str:
    if not mime:
        return "bin"
    return _MIME_TO_EXT.get(mime.lower().split(";")[0].strip(), "bin")


def _download(url: str, session: requests.Session) -> Tuple[Optional[bytes], Optional[str]]:
    try:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
        if len(resp.content) > MAX_FILE_SIZE:
            logger.info("Skipping download, content too large: %d bytes from %s", len(resp.content), url)
            return None, None
        return resp.content, resp.headers.get("Content-Type")
    except Exception as e:
        logger.warning("Failed to download craft media %s: %s", url, e)
        return None, None


def _asset_exists_in_storage(storage_path: str, session: requests.Session) -> bool:
    """HEAD check on storage to avoid re-uploading existing assets."""
    url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
    try:
        resp = session.head(url, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def _upload_to_storage(
    storage_path: str,
    data: bytes,
    content_type: str,
    session: requests.Session,
) -> bool:
    url = f"{settings.SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}"
    headers = {
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Content-Type": content_type,
    }
    try:
        resp = session.post(url, data=data, headers=headers, timeout=60)
        if resp.status_code == 400 and "already exists" in resp.text.lower():
            resp = session.put(url, data=data, headers=headers, timeout=60)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.warning("Failed to upload craft media %s: %s", storage_path, e)
        return False


def _replace_urls(markdown: str, url_mapping: Dict[str, str]) -> str:
    """Replace all Craft media URLs in markdown with self-hosted URLs."""
    for old_url, new_url in url_mapping.items():
        markdown = markdown.replace(old_url, new_url)
    return markdown
