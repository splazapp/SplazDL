"""OSS upload helper for SplazDL."""
import logging
import os
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger(__name__)

_CONTENT_TYPES = {
    ".mp4": "video/mp4", ".mkv": "video/x-matroska", ".webm": "video/webm",
    ".mov": "video/quicktime", ".avi": "video/x-msvideo",
    ".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".flac": "audio/flac",
    ".opus": "audio/ogg", ".aac": "audio/aac", ".wav": "audio/wav",
}


def upload_to_oss(task_id: str, filepath: Path) -> str:
    """Upload file to Aliyun OSS. Returns CDN URL or "" on failure/unconfigured."""
    import oss2

    access_key_id     = os.environ.get("SPLAZDL_OSS_ACCESS_KEY_ID", "")
    access_key_secret = os.environ.get("SPLAZDL_OSS_ACCESS_KEY_SECRET", "")
    bucket_name       = os.environ.get("SPLAZDL_OSS_BUCKET", "")
    endpoint          = os.environ.get("SPLAZDL_OSS_ENDPOINT", "")
    cdn_domain        = os.environ.get("SPLAZDL_OSS_CDN_DOMAIN", "")
    prefix            = os.environ.get("SPLAZDL_OSS_PREFIX", "splazdl")

    if not endpoint:
        return ""

    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)
    key = f"{prefix}/{task_id}/{filepath.name}"
    content_type = _CONTENT_TYPES.get(filepath.suffix.lower(), "application/octet-stream")

    try:
        bucket.put_object_from_file(key, str(filepath), headers={"Content-Type": content_type})
        encoded_key = quote(key, safe="/")
        if cdn_domain:
            return f"https://{cdn_domain}/{encoded_key}"
        return f"{endpoint}/{bucket_name}/{encoded_key}"
    except Exception:
        log.exception("OSS upload failed for %s", filepath)
        return ""
