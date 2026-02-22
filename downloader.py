"""
ĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ ÄÂĂÂ¸ÄÂÄšÂĂĹĄÄšĹÄÂĂÂÄÂĂÂÄÂĂÂ¨ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ - ĂÂĂÂ§ĂĹĄĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂ
"""

import plistlib
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import yt_dlp

from config import get_config
from models import (
    DownloadTask,
    User,
    create_task,
    get_task,
    get_user_tasks,
    get_all_tasks,
    get_completed_tasks,
    ensure_user_directory,
)


# ĂÂĂÂ¤ĂĹĄĂËĂĹĄĂËÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂÄšÂÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂ ÄÂĂÂÄÂÄšÂĂĹĄÄšĹÄÂĂÂ
_task_controls: dict[str, bool] = {}
_task_controls_lock = threading.Lock()

# ĂÂĂÂ§ĂĹĄĂÂĂĹĄÄšĹĂÂĂÂ§ÄÂĂÂ¨ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ 
_executor: ThreadPoolExecutor | None = None


def get_executor() -> ThreadPoolExecutor:
    """ÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄĂËĂĹĄĂËÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ¨"""
    global _executor
    if _executor is None:
        config = get_config()
        _executor = ThreadPoolExecutor(max_workers=config.download.max_concurrent)
    return _executor


def _preprocess_url(url: str) -> str:
    """
    ĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂ¤ÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂ URLÄÂĂÂĂĹĄÄšÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ĂĹĄĂÂ yt-dlp ÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ ĂĹĄÄšÂÄÂÄšÂĂĹĄÄšÂÄÂĂÂ

    ÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂ
    1. ÄÂĂÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂ´ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂÄšĹžĂÂÄšÂ ÄÂĂÂÄÂĂÂ URL (ÄÂÄšÂÄÂĂÂ¸ĂĹĄĂÂ modal_id ÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ°) -> ÄÂĂÂÄÂĂÂ ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂ URL
       ĂÂĂÂ¤ĂĹĄÄšĹžÄÂĂÂÄÂÄšÂĂĹĄĂÂÄÂĂÂ: https://www.douyin.com/root/search/...?modal_id=123
       ÄÂĂÂÄÂĂÂĂĹĄÄšÄÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ĂĹĄĂÂ: https://www.douyin.com/video/123

    2. ÄÂĂÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄĂÂĂĹĄĂÂ¤ĂÂÄšÂ ÄÂĂÂĂĹĄÄšĹžÄÂĂÂÄÂĂÂÄÂĂÂ URL (ÄÂÄšÂÄÂĂÂ¸ĂĹĄĂÂ modal_id ÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ°)
       ĂÂĂÂ¤ĂĹĄÄšĹžÄÂĂÂÄÂÄšÂĂĹĄĂÂÄÂĂÂ: https://www.douyin.com/...?modal_id=123
       ÄÂĂÂÄÂĂÂĂĹĄÄšÄÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ĂĹĄĂÂ: https://www.douyin.com/video/123
    """
    # ÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂÄšÂÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄĂÂ URL
    if 'douyin.com' in url:
        # ÄÂĂÂÄÂĂÂ§ĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂ URL
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        # ÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂÄšÂÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂ modal_id ÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ°
        if 'modal_id' in query_params:
            modal_id = query_params['modal_id'][0]
            # ÄÂĂÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂ ÄÂĂÂÄÂĂÂ ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂ URL
            return f'https://www.douyin.com/video/{modal_id}'

        # ÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂÄšÂÄÂĂÂĂĹĄĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ§ĂĹĄĂËÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂÄÂĂÂ ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ ĂĹĄÄšÂÄÂÄšÂĂĹĄÄšÂÄÂĂÂ
        video_match = re.match(r'https?://(?:www\.)?douyin\.com/video/(\d+)', url)
        if video_match:
            return url

    # TikTok ĂÂĂÂ§ÄÂĂÂĂĹĄĂËĂÂĂÂ¤ĂĹĄÄšÂĂĹĄÄšÂÄÂÄšÂÄÂĂÂ¤ÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂÄÂÄšÂĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂ
    if 'tiktok.com' in url and 'modal_id' in url:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if 'modal_id' in query_params:
            modal_id = query_params['modal_id'][0]
            return f'https://www.tiktok.com/video/{modal_id}'

    # ÄÂÄšÂÄÂĂÂĂĹĄĂÂĂÂĂÂ¤ĂĹĄĂËÄÂĂÂ URL ĂÂĂÂ§ÄÂĂÂÄÂĂÂ´ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšĹÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ
    return url


def preprocess_url(url: str) -> str:
    """ÄÂÄšÂĂĹĄÄšÄ˝ĂĹĄĂÂÄÂÄšÂÄÂĂÂ¤ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ´ĂÂÄšÂ ÄÂĂÂÄÂĂÂ URL ĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂ¤ÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂĂÂĂÂ¤ĂĹĄÄšĹžÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂĂĹĄĂËĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ§ĂĹĄĂËÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂ"""
    return _preprocess_url(url)


def _get_format_selector(quality: str) -> str:
    """ÄÂĂÂÄÂĂÂ ĂĹĄĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂ´ÄÂĂÂ¨ĂÂÄšÂ ÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ yt-dlp format ÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ°"""
    quality_map = {
        "best": "bestvideo+bestaudio/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "audio": "bestaudio/best",
    }
    return quality_map.get(quality, quality_map["best"])


def _is_douyin_url(url: str) -> bool:
    """ÄÂÄšÂÄÂĂÂÄÂĂÂ¤ÄÂĂÂÄÂĂÂÄÂĂÂ­ÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂÄšÂÄÂĂÂĂĹĄĂÂĂÂĂÂ¤ÄÂĂÂ¸ĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄĂÂ URL"""
    return "douyin.com" in (url or "")


def _is_fresh_cookie_error(exc: Exception) -> bool:
    """ÄÂÄšÂÄÂĂÂÄÂĂÂ¤ÄÂĂÂÄÂĂÂÄÂĂÂ­ÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂÄšÂÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄĂÂ cookie ĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ°ĂÂÄšÂ ÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ĂĹĄÄšÄ˝"""
    msg = str(exc).lower()
    return "fresh cookies" in msg and "douyin" in msg


def _network_candidates(options: dict, url: str) -> list[dict]:
    """
    ĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂĂÂĂÂ§ĂĹĄĂËÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ°ÄÂÄšÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂĂĹĄĂÂĂÂĂÂ¤ÄÂĂÂĂĹĄÄšĹĂÂĂÂ§ÄÂĂÂÄÂĂÂ¨ĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂĂÂĂÂ§ÄÂĂÂ§ÄÂĂÂ cookies ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ
    ĂÂĂÂ¤ĂĹĄĂËÄÂĂÂĂÂĂÂ¤ÄÂĂÂĂĹĄÄšĹĂÂĂÂ§ÄÂĂÂÄÂĂÂ¨ĂÂĂÂ§ÄÂĂÂÄÂĂÂ¨ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšĹžÄÂÄšÂĂĹĄÄšÂÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂ ĂÂĂÂ§ÄÂĂÂÄÂĂÂ cookies ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ¨ÄÂĂÂÄÂĂÂĂĹĄĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂÄÂÄšÂÄÂĂÂĂĹĄĂÂĂÂĂÂ¤ĂĹĄĂËÄÂĂÂÄÂĂÂÄÂÄšĹžÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ¨ÄÂĂÂÄÂĂÂÄÂĂÂ
    """
    proxy = (options.get("proxy") or "").strip()
    cookie_file = (options.get("cookie_file") or "").strip()
    cookies_from_browser = (options.get("cookies_from_browser") or "").strip()

    def _candidate(*, browser: str = "", file_path: str = "") -> dict:
        candidate = {}
        if proxy:
            candidate["proxy"] = proxy
        if file_path:
            candidate["cookiefile"] = file_path
        elif browser:
            candidate["cookiesfrombrowser"] = (browser,)
        return candidate

    if cookie_file:
        return [_candidate(file_path=cookie_file)]

    if cookies_from_browser:
        return [_candidate(browser=cookies_from_browser)]

    return [_candidate()]


def _extract_info_with_candidates(url: str, base_opts: dict, candidates: list[dict]) -> tuple[dict, dict]:
    """ÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂĂÂĂÂ§ĂĹĄĂËÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ°ÄÂÄšÂÄÂĂÂ°ÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄÄšĹÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂĂĹĄÄšÂÄÂĂÂÄÂĂÂĂĹĄÄšĹÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ (info, candidate)ÄÂĂÂÄÂĂÂÄÂĂÂ"""
    last_error: Exception | None = None

    for candidate in candidates:
        try:
            with yt_dlp.YoutubeDL({**base_opts, **candidate}) as ydl:
                info = ydl.extract_info(url, download=False)
            return info, candidate
        except Exception as exc:
            last_error = exc
            # ÄÂĂÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄĂÂ cookie ĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ĂĹĄÄšÄ˝ÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ§ĂĹĄĂËÄÂĂÂ§ĂÂĂÂ§ĂĹĄĂËÄÂĂÂ­ĂÂĂÂ§ĂĹĄĂÂ ÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ĂĹĄÄšĹžÄÂÄšÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂÄÂÄšÂÄÂĂÂĂĹĄĂÂĂÂĂÂ¤ĂĹĄĂËÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ĂĹĄÄšÄ˝ĂÂĂÂ§ÄÂĂÂÄÂĂÂ´ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂĂĹĄĂÂ
            if _is_douyin_url(url) and _is_fresh_cookie_error(exc):
                continue
            raise

    if last_error is not None:
        raise RuntimeError(
            "ÄÂĂÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ°ĂÂÄšÂ ÄÂĂÂÄÂĂÂ CookiesÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ¨ÄÂĂÂÄÂÄšĹžÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ¨ÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂĂĹĄÄšÂÄÂĂÂ douyin.com ÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂ"
            "ĂÂĂÂ§ÄÂĂÂĂĹĄĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ¨ĂÂÄšÂ ĂĹĄĂÂ¤ÄÂĂÂĂÂĂÂ§ĂĹĄĂÂÄÂĂÂ§ĂÂÄšÂ ÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂĂĹĄĂÂĂÂĂÂ¤ĂĹĄÄšĹÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂĂÂĂÂ§ÄÂĂÂ§ÄÂĂÂ Cookies ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂÄÂĂÂÄÂÄšĹžÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ¨ÄÂĂÂÄÂĂÂÄÂĂÂ cookies.txtÄÂĂÂĂĹĄÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ"
        ) from last_error
    raise RuntimeError("ÄÂĂÂÄÂĂÂ§ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄÄšĹÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂ¤ÄÂĂÂÄÂĂÂÄÂĂÂ´ÄÂĂÂ")


def probe_info(url: str, options: dict | None = None) -> dict:
    """ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšĹžÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄÄšĹÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂĂĹĄÄšÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂĂÂĂÂ¤ĂĹĄÄšĹžÄÂĂÂ UI ĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂĂÂĂÂ¤ÄÂĂÂĂĹĄÄšĹĂÂĂÂ§ÄÂĂÂÄÂĂÂ¨"""
    options = options or {}
    processed_url = _preprocess_url(url.strip())
    if not processed_url:
        raise ValueError("URL ĂÂĂÂ¤ÄÂĂÂ¸ĂĹĄĂÂĂÂĂÂ§ĂĹĄĂÂ ĂĹĄĂÂ")

    base_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    info, _ = _extract_info_with_candidates(
        processed_url,
        base_opts=base_opts,
        candidates=_network_candidates(options, processed_url),
    )

    formats = info.get("formats", []) or []
    heights = sorted({f.get("height") for f in formats if f.get("height")}, reverse=True)
    video_exts = sorted({f.get("ext") for f in formats if f.get("vcodec") and f.get("vcodec") != "none" and f.get("ext")})
    audio_exts = sorted({f.get("ext") for f in formats if f.get("acodec") and f.get("acodec") != "none" and f.get("ext")})

    return {
        "title": info.get("title") or "ÄÂĂÂÄÂĂÂĂĹĄĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂ",
        "uploader": info.get("uploader") or "-",
        "duration": info.get("duration") or 0,
        "view_count": info.get("view_count") or 0,
        "upload_date": info.get("upload_date") or "-",
        "webpage_url": info.get("webpage_url") or processed_url,
        "available_heights": heights,
        "video_exts": video_exts,
        "audio_exts": audio_exts,
    }


def start_download(user: User, url: str, quality: str = "best", options: dict | None = None) -> str:
    """ÄÂÄšÂÄÂĂÂĂĹĄÄšÄ˝ÄÂÄšÂÄÂĂÂÄÂĂÂ¨ĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄĂËĂĹĄĂËÄÂÄšÂÄÂĂÂÄÂĂÂ"""
    # ĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂ¤ÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂ URLÄÂĂÂĂĹĄÄšÂÄÂĂÂĂÂĂÂ¤ĂĹĄÄšĹžÄÂĂÂÄÂÄšÂĂĹĄĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂ´ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂÄšĹžĂÂÄšÂ ÄÂĂÂÄÂĂÂ URL -> ÄÂĂÂÄÂĂÂ ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂ URLÄÂĂÂĂĹĄÄšÂÄÂĂÂ
    processed_url = _preprocess_url(url)

    # ÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂĂĹĄĂËĂĹĄĂÂĂÂĂÂ¤ĂĹĄĂËĂĹĄĂËÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂĂÂĂÂ¤ÄÂĂÂĂĹĄÄšĹĂÂĂÂ§ÄÂĂÂÄÂĂÂ¨ÄÂÄšÂÄÂĂÂ¤ÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂ URL
    task = create_task(user.username, processed_url)

    return start_download_for_task(task, quality, options)


def start_download_for_task(task: DownloadTask, quality: str = "best", options: dict | None = None) -> str:
    """ÄÂÄšÂÄÂĂÂĂĹĄĂÂĂÂĂÂ¤ĂĹĄĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂĂĹĄĂËĂĹĄĂÂĂÂĂÂ¤ĂĹĄĂËĂĹĄĂËÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂĂĹĄÄšÄ˝ĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂĂĹĄÄšÄ˝ÄÂÄšÂÄÂĂÂÄÂĂÂ¨ĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂ¨ĂÂĂÂ¤ĂĹĄĂÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂ­ÄÂĂÂÄÂÄšÂÄÂĂÂĂĹĄĂËĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄĂÂÄÂĂÂ¤ÄÂĂÂĂĹĄÄšÂÄÂĂÂ"""
    with _task_controls_lock:
        _task_controls[task.task_id] = False

    get_executor().submit(_download_worker, task, quality, options or {})
    return task.task_id


def _sanitize_title_for_filename(title: str) -> str:
    """ÄÂÄšÂÄÂĂÂ°ÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ĂĹĄĂÂÄÂÄšÂĂĹĄĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ¨ĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄĂËĂĹĄĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ"""
    # ÄÂĂÂÄÂĂÂĂĹĄÄšĹÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂÄšÂĂĹĄĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ¨ĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂ­ÄÂĂÂĂÂĂÂ§ĂĹĄÄšÄĂĹĄĂÂ
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    filename = title
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    # ĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄĂËĂĹĄĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄÄšĹÄÂÄšÂĂĹĄĂÂĂĹĄĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂĂÂĂÂ¤ĂĹĄÄšĹÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂĂÂĂÂ§ĂĹĄĂÂ ĂĹĄĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂ´ĂÂĂÂ§ĂĹĄĂËÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂ ÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂ
    max_length = 200
    if len(filename) > max_length:
        filename = filename[:max_length]
    return filename.strip()


def _clean_progress_text(value: str | None) -> str:
    """ÄÂĂÂÄÂĂÂ¸ÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšĹÄÂĂÂÄÂÄšÂĂĹĄĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂ­ĂÂĂÂ§ÄÂĂÂÄÂĂÂ ANSI ĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂÄšÂÄÂĂÂĂĹĄĂÂĂÂĂÂ§ĂĹĄÄšÄĂĹĄĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄÄšĹÄÂÄšÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ¨ Web UI ÄÂÄšÂÄÂĂÂĂĹĄĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂ°ĂÂĂÂ¤ĂĹĄĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂ ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ"""
    text = (value or "").strip()
    if not text:
        return ""
    # ÄÂĂÂÄÂĂÂ ÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ ANSI ÄÂĂÂÄÂĂÂĂĹĄÄšÄĂÂĂÂ¤ĂĹĄĂÂÄÂĂÂÄÂÄšÂĂĹĄĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂÄÂÄšÂĂĹĄĂÂÄÂĂÂ \x1b[0;32mÄÂĂÂĂĹĄÄšÂÄÂĂÂ
    text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)
    # ÄÂÄšÂÄÂĂÂĂĹĄÄšÂÄÂÄšÂĂĹĄĂÂĂĹĄĂÂÄÂÄšÂÄÂĂÂ°ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ°ÄÂÄšÂÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂĂÂĂĹĄĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂ ESC ÄÂÄšÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂÄÂĂÂ§ÄÂĂÂÄÂÄšÂÄÂĂÂ­ÄÂĂÂĂÂĂÂ§ĂĹĄÄšÄĂĹĄĂÂ
    text = text.replace("\x1b", "").replace("", "")
    return text.strip()


def _select_downloaded_media_file(task_dir: Path) -> Path | None:
    """Pick the most likely media file from task directory."""
    if not task_dir.exists():
        return None

    media_exts = {
        ".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv",
        ".m4a", ".mp3", ".wav", ".flac", ".opus", ".aac", ".ogg",
    }
    ignored_exts = {
        ".part", ".ytdl", ".json", ".jpg", ".jpeg", ".png", ".webp",
        ".srt", ".vtt", ".ass", ".lrc", ".txt", ".description", ".html", ".htm",
    }

    files = [p for p in task_dir.iterdir() if p.is_file()]
    media_candidates = [p for p in files if p.suffix.lower() in media_exts]
    if media_candidates:
        return max(media_candidates, key=lambda p: p.stat().st_size)

    fallback = [p for p in files if p.suffix.lower() not in ignored_exts]
    if fallback:
        return max(fallback, key=lambda p: p.stat().st_size)
    return None


def _find_existing_media_for_same_url(task: DownloadTask) -> Path | None:
    """Find an existing completed media file for the same user+URL."""
    candidates: list[DownloadTask] = []
    for t in get_user_tasks(task.username):
        if t.task_id == task.task_id:
            continue
        if t.url != task.url:
            continue
        if t.status != DownloadTask.STATUS_COMPLETED:
            continue
        if not t.file_path:
            continue
        p = Path(t.file_path)
        if p.exists() and p.is_file():
            candidates.append(t)

    if not candidates:
        return None
    best = max(candidates, key=lambda x: x.created_at)
    return Path(best.file_path)


def _collect_output_paths_from_info(info: dict | None) -> list[Path]:
    """Collect output file paths from yt-dlp extract_info result."""
    if not info:
        return []

    paths: list[Path] = []

    def _add(v):
        if isinstance(v, str) and v.strip():
            paths.append(Path(v))

    def _walk(node):
        if not isinstance(node, dict):
            return
        _add(node.get("filepath"))
        _add(node.get("_filename"))
        requested = node.get("requested_downloads")
        if isinstance(requested, list):
            for item in requested:
                if isinstance(item, dict):
                    _add(item.get("filepath"))
                    _add(item.get("_filename"))
        entries = node.get("entries")
        if isinstance(entries, list):
            for e in entries:
                if isinstance(e, dict):
                    _walk(e)

    _walk(info)
    # ĺťéä˝äżçéĄşĺş
    deduped: list[Path] = []
    seen = set()
    for p in paths:
        key = str(p)
        if key not in seen:
            deduped.append(p)
            seen.add(key)
    return deduped


def _download_worker(task: DownloadTask, quality: str, options: dict):
    """ĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂÄÂĂÂĂÂĂÂ§ĂĹĄĂÂĂĹĄÄšĹĂÂĂÂ§ÄÂĂÂ¨ÄÂĂÂ"""
    task_id = task.task_id

    def progress_hook(d: dict):
        with _task_controls_lock:
            if _task_controls.get(task_id, False):
                raise InterruptedError("ĂÂĂÂ¤ĂĹĄĂËĂĹĄĂËÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂ¤ĂÂĂÂ§ĂĹĄĂËÄÂĂÂÄÂĂÂÄÂĂÂ­ÄÂĂÂ")

        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            task.progress = (downloaded / total * 100) if total > 0 else 0
            task.status = DownloadTask.STATUS_DOWNLOADING
            task.speed = _clean_progress_text(d.get("_speed_str"))
            task.eta = _clean_progress_text(d.get("_eta_str"))

    try:
        user_dir = ensure_user_directory(task.username)
        task_dir = user_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        # ĂÂĂÂ§ÄÂĂÂÄÂĂÂ¨ÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂĂĹĄÄšÄ˝ĂÂÄšÂ ÄÂĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂĂĹĄĂÂĂÂÄšÂ ĂĹĄĂÂ¤ÄÂĂÂĂÂĂÂ§ĂĹĄĂÂÄÂĂÂ§ĂÂÄšÂ ÄÂĂÂÄÂĂÂĂÂÄšÂ ÄÂĂÂĂĹĄĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ yt-dlp README ÄÂÄšÂÄÂĂÂ¸ÄÂĂÂ¸ĂÂĂÂ§ÄÂĂÂÄÂĂÂ¨ÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ°ÄÂĂÂĂĹĄÄšÂÄÂĂÂ
        audio_only = bool(options.get("audio_only", False)) or quality == "audio"
        audio_format = (options.get("audio_format") or "mp3").strip()
        write_subs = bool(options.get("write_subs", False))
        sub_langs_raw = (options.get("sub_langs") or "").strip()
        write_thumbnail = bool(options.get("write_thumbnail", False))
        embed_thumbnail = bool(options.get("embed_thumbnail", False))
        embed_metadata = bool(options.get("embed_metadata", False))
        download_playlist = bool(options.get("download_playlist", False))
        rate_limit = (options.get("rate_limit") or "").strip()
        retries = int(options.get("retries") or 10)
        fragment_retries = int(options.get("fragment_retries") or 10)
        concurrent_fragments = int(options.get("concurrent_fragments") or 1)
        use_download_archive = bool(options.get("use_download_archive", False))

        # ÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄÄšĹÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÄ˝ÄÂĂÂĂĹĄÄšÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂ
        base_extract_opts = {
            "quiet": True,
            "no_warnings": True,
        }
        if not download_playlist:
            base_extract_opts["noplaylist"] = True

        task.status = DownloadTask.STATUS_DOWNLOADING

        info, selected_network_opts = _extract_info_with_candidates(
            task.url,
            base_opts=base_extract_opts,
            candidates=_network_candidates(options, task.url),
        )

        # ÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂÄšÂĂĹĄĂÂĂĹĄĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂĂĹĄĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ¨ÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄĂËĂĹĄĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ
        video_title = info.get("title", "ÄÂĂÂÄÂĂÂĂĹĄĂÂĂÂĂÂ§ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂ")
        safe_filename = _sanitize_title_for_filename(video_title)

        # ÄÂĂÂÄÂĂÂÄÂĂÂ´ÄÂĂÂÄÂĂÂÄÂĂÂ°ĂÂĂÂ¤ĂĹĄĂËĂĹĄĂËÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂ
        task.title = video_title

        # ĂÂĂÂ¤ÄÂĂÂ¸ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ§ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄÄšÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂĂĹĄÄšĹĂÂĂÂ§ÄÂĂÂÄÂĂÂ¨ÄÂĂÂÄÂĂÂ ÄÂĂÂĂÂÄšÂ ÄÂĂÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂÄÂĂÂĂÂĂÂ¤ÄÂĂÂ¸ĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄĂËĂĹĄĂÂÄÂÄšÂÄÂĂÂÄÂĂÂ
        ydl_opts = {
            "format": "bestaudio/best" if audio_only else _get_format_selector(quality),
            "outtmpl": str(task_dir / f"{safe_filename}.%(ext)s"),
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "merge_output_format": "mp4",
            "retries": retries,
            "fragment_retries": fragment_retries,
            "concurrent_fragment_downloads": concurrent_fragments,
        }
        if not download_playlist:
            ydl_opts["noplaylist"] = True
        ydl_opts.update(selected_network_opts)
        if rate_limit:
            ydl_opts["ratelimit"] = rate_limit
        if write_subs:
            ydl_opts["writesubtitles"] = True
            ydl_opts["writeautomaticsub"] = True
            if sub_langs_raw:
                ydl_opts["subtitleslangs"] = [s.strip() for s in sub_langs_raw.split(",") if s.strip()]
        if write_thumbnail:
            ydl_opts["writethumbnail"] = True
        if embed_thumbnail:
            ydl_opts["embedthumbnail"] = True
        if embed_metadata:
            ydl_opts["addmetadata"] = True
        if audio_only:
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_format,
                }
            ]
        if use_download_archive:
            archive_path = user_dir / ".download_archive.txt"
            ydl_opts["download_archive"] = str(archive_path)

        downloaded_info = None
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            downloaded_info = ydl.extract_info(task.url, download=True)

        filepath: Path | None = None
        info_paths = _collect_output_paths_from_info(downloaded_info)
        existing_info_paths = [p for p in info_paths if p.exists() and p.is_file()]
        if existing_info_paths:
            filepath = max(existing_info_paths, key=lambda p: p.stat().st_size)
        if not filepath:
            filepath = _select_downloaded_media_file(task_dir)
        if (not filepath or not filepath.exists()) and use_download_archive:
            filepath = _find_existing_media_for_same_url(task)
        if (not filepath or not filepath.exists()) and use_download_archive:
            # Archive may skip actual file writing for known IDs; retry once without archive.
            retry_opts = dict(ydl_opts)
            retry_opts.pop("download_archive", None)
            with yt_dlp.YoutubeDL(retry_opts) as ydl:
                downloaded_info = ydl.extract_info(task.url, download=True)
            info_paths = _collect_output_paths_from_info(downloaded_info)
            existing_info_paths = [p for p in info_paths if p.exists() and p.is_file()]
            if existing_info_paths:
                filepath = max(existing_info_paths, key=lambda p: p.stat().st_size)
            if not filepath:
                filepath = _select_downloaded_media_file(task_dir)
        if not filepath or not filepath.exists():
            raise RuntimeError("Download finished but media file not found")

        # ÄÂĂÂĂĹĄĂÂĂĹĄÄšĹžĂÂĂÂ§ÄÂĂÂĂĹĄĂÂ macOS ÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂÄÂĂÂ URL ÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂÄÂĂÂ°ÄÂĂÂÄÂĂÂĂĹĄĂÂ
        if filepath and filepath.exists():
            try:
                plist_data = plistlib.dumps([task.url], fmt=plistlib.FMT_BINARY)
                subprocess.run(
                    ["xattr", "-wx", "com.apple.metadata:kMDItemWhereFroms",
                     plist_data.hex(),
                     str(filepath)],
                    check=False,
                    capture_output=True
                )
            except Exception:
                pass

        # ÄÂĂÂÄÂĂÂÄÂĂÂ´ÄÂĂÂÄÂĂÂÄÂĂÂ°ĂÂĂÂ¤ĂĹĄĂËĂĹĄĂËÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ§ÄÂĂÂĂĹĄĂÂÄÂĂÂÄÂĂÂÄÂĂÂ
        task.status = DownloadTask.STATUS_COMPLETED
        task.progress = 100
        task.file_path = str(filepath) if filepath and filepath.exists() else ""
        task.file_size = filepath.stat().st_size if filepath and filepath.exists() else 0

    except InterruptedError:
        task.status = DownloadTask.STATUS_PAUSED

    except Exception as e:
        task.status = DownloadTask.STATUS_FAILED
        task.error_msg = str(e)

    finally:
        with _task_controls_lock:
            _task_controls.pop(task_id, None)


def pause_task(task_id: str) -> bool:
    """ÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄĂËĂĹĄĂËÄÂÄšÂÄÂĂÂÄÂĂÂ"""
    with _task_controls_lock:
        if task_id in _task_controls:
            _task_controls[task_id] = True
            return True
    return False


def cancel_task(task_id: str) -> bool:
    """ÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂÄÂĂÂĂÂĂÂ¤ĂĹĄĂËĂĹĄĂËÄÂÄšÂÄÂĂÂÄÂĂÂ"""
    pause_task(task_id)
    task = get_task(task_id)
    if task:
        task.status = DownloadTask.STATUS_FAILED
        task.error_msg = "ĂÂĂÂ§ÄÂĂÂÄÂĂÂ¨ÄÂĂÂÄÂĂÂÄÂĂÂÄÂÄšÂÄÂĂÂÄÂĂÂÄÂĂÂĂĹĄĂÂÄÂĂÂ"
        return True
    return False


# ÄÂÄšÂĂĹĄÄšÄ˝ĂĹĄÄšÂÄÂÄšÂÄÂĂÂĂĹĄĂÂĂÂĂÂ¤ĂĹĄÄšĹžÄÂĂÂ app.py ĂÂĂÂ¤ÄÂĂÂĂĹĄÄšĹĂÂĂÂ§ÄÂĂÂÄÂĂÂ¨
__all__ = [
    "preprocess_url",
    "start_download",
    "start_download_for_task",
    "probe_info",
    "pause_task",
    "cancel_task",
    "get_task",
    "get_user_tasks",
    "get_all_tasks",
    "get_completed_tasks",
]
