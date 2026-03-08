"""Send download completion notifications to Feishu (飞书) via webhook."""

import logging
import os

import requests

log = logging.getLogger(__name__)


def _webhook_url() -> str:
    return os.environ.get("SPLAZDL_FEISHU_WEBHOOK_URL", "")


def _post_card(card: dict) -> None:
    url = _webhook_url()
    if not url:
        return
    payload = {"msg_type": "interactive", "card": card}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        log.info("Feishu notification sent successfully.")
    except Exception:
        log.exception("Failed to send Feishu notification")


def _format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "-"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def send_download_complete(
    *,
    task_id: str,
    title: str,
    url: str,
    oss_url: str,
    file_size: int,
    duration: int,
) -> None:
    """Send a download completion card to Feishu."""
    oss_md = f"[{oss_url}]({oss_url})" if oss_url else "-"
    content_md = (
        f"**标题**: {title or '未知'}\n\n"
        f"**原始视频链接**: [{url}]({url})\n\n"
        f"**OSS视频链接**: {oss_md}\n\n"
        f"**视频大小**: {_format_size(file_size)}\n\n"
        f"**视频时长**: {_format_duration(duration)}\n\n"
        f"**任务ID**: {task_id}"
    )
    card = {
        "header": {
            "title": {"tag": "plain_text", "content": "SplazDL 下载完成 ✅"},
            "template": "green",
        },
        "elements": [
            {"tag": "markdown", "content": content_md},
        ],
    }
    _post_card(card)
