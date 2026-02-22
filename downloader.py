"""
下载核心模块 - 简化版
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


# 任务控制标志
_task_controls: dict[str, bool] = {}
_task_controls_lock = threading.Lock()

# 线程池
_executor: ThreadPoolExecutor | None = None


def get_executor() -> ThreadPoolExecutor:
    """获取任务执行器"""
    global _executor
    if _executor is None:
        config = get_config()
        _executor = ThreadPoolExecutor(max_workers=config.download.max_concurrent)
    return _executor


def _preprocess_url(url: str) -> str:
    """
    预处理 URL，转换为 yt-dlp 支持的格式

    支持的转换：
    1. 抖音搜索页面 URL (带 modal_id 参数) -> 标准视频 URL
       例如: https://www.douyin.com/root/search/...?modal_id=123
       转换为: https://www.douyin.com/video/123

    2. 抖音分享链接 URL (带 modal_id 参数)
       例如: https://www.douyin.com/...?modal_id=123
       转换为: https://www.douyin.com/video/123
    """
    # 检查是否是抖音 URL
    if 'douyin.com' in url:
        # 解析 URL
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        # 检查是否有 modal_id 参数
        if 'modal_id' in query_params:
            modal_id = query_params['modal_id'][0]
            # 构造标准的抖音视频 URL
            return f'https://www.douyin.com/video/{modal_id}'

        # 检查是否已经是标准格式
        video_match = re.match(r'https?://(?:www\.)?douyin\.com/video/(\d+)', url)
        if video_match:
            return url

    # TikTok 类似处理（如果需要）
    if 'tiktok.com' in url and 'modal_id' in url:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if 'modal_id' in query_params:
            modal_id = query_params['modal_id'][0]
            return f'https://www.tiktok.com/video/{modal_id}'

    # 其他 URL 直接返回
    return url


def _get_format_selector(quality: str) -> str:
    """根据质量选项生成 yt-dlp format 参数"""
    quality_map = {
        "best": "bestvideo+bestaudio/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "audio": "bestaudio/best",
    }
    return quality_map.get(quality, quality_map["best"])


def start_download(user: User, url: str, quality: str = "best") -> str:
    """启动下载任务"""
    # 预处理 URL（例如：抖音搜索页面 URL -> 标准视频 URL）
    processed_url = _preprocess_url(url)

    # 创建任务时使用处理后的 URL
    task = create_task(user.username, processed_url)

    with _task_controls_lock:
        _task_controls[task.task_id] = False

    get_executor().submit(_download_worker, task, quality)
    return task.task_id


def _sanitize_title_for_filename(title: str) -> str:
    """将视频标题转换为安全的文件名"""
    # 替换不安全的字符
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    filename = title
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    # 限制文件名长度（保留空间给扩展名）
    max_length = 200
    if len(filename) > max_length:
        filename = filename[:max_length]
    return filename.strip()


def _download_worker(task: DownloadTask, quality: str):
    """下载工作线程"""
    task_id = task.task_id

    def progress_hook(d: dict):
        with _task_controls_lock:
            if _task_controls.get(task_id, False):
                raise InterruptedError("任务被终止")

        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            task.progress = (downloaded / total * 100) if total > 0 else 0
            task.status = DownloadTask.STATUS_DOWNLOADING
            task.speed = d.get("_speed_str", "")
            task.eta = d.get("_eta_str", "")

    try:
        user_dir = ensure_user_directory(task.username)
        task_dir = user_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        # 先提取视频信息（不下载）
        extract_opts = {
            "quiet": True,
            "no_warnings": True,
        }

        task.status = DownloadTask.STATUS_DOWNLOADING

        with yt_dlp.YoutubeDL(extract_opts) as ydl:
            info = ydl.extract_info(task.url, download=False)

        # 获取视频标题并生成安全文件名
        video_title = info.get("title", "未知视频")
        safe_filename = _sanitize_title_for_filename(video_title)

        # 更新任务标题
        task.title = video_title

        # 下载视频，使用标题作为文件名
        ydl_opts = {
            "format": _get_format_selector(quality),
            "outtmpl": str(task_dir / f"{safe_filename}.%(ext)s"),
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
            # 从浏览器自动导入 cookies（支持抖音、B站等需要 cookies 的网站）
            # 支持的浏览器: chrome, firefox, edge, safari, opera, brave
            # macOS 推荐使用 safari，更稳定
            "cookiesfrombrowser": ("safari",),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([task.url])

        # 获取下载的文件路径
        video_files = list(task_dir.glob("*.*"))
        filepath = video_files[0] if video_files else None

        # 设置 macOS 来源 URL 元数据
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

        # 更新任务状态
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
    """暂停任务"""
    with _task_controls_lock:
        if task_id in _task_controls:
            _task_controls[task_id] = True
            return True
    return False


def cancel_task(task_id: str) -> bool:
    """取消任务"""
    pause_task(task_id)
    task = get_task(task_id)
    if task:
        task.status = DownloadTask.STATUS_FAILED
        task.error_msg = "用户取消"
        return True
    return False


# 导出供 app.py 使用
__all__ = [
    "start_download",
    "pause_task",
    "cancel_task",
    "get_task",
    "get_user_tasks",
    "get_all_tasks",
    "get_completed_tasks",
]
