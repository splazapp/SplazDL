"""
下载核心模块 - 简化版
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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
    task = create_task(user.username, url)

    with _task_controls_lock:
        _task_controls[task.task_id] = False

    get_executor().submit(_download_worker, task, quality)
    return task.task_id


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

        ydl_opts = {
            "format": _get_format_selector(quality),
            "outtmpl": str(task_dir / "%(title)s.%(ext)s"),
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
        }

        task.status = DownloadTask.STATUS_DOWNLOADING

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(task.url, download=True)

        # 获取下载的文件路径
        filename = ydl.prepare_filename(info)
        filepath = Path(filename)

        if not filepath.exists():
            video_files = list(task_dir.glob("*.*"))
            if video_files:
                filepath = video_files[0]

        # 更新任务状态
        task.status = DownloadTask.STATUS_COMPLETED
        task.title = info.get("title", "未知")
        task.progress = 100
        task.file_path = str(filepath) if filepath.exists() else ""
        task.file_size = filepath.stat().st_size if filepath.exists() else 0

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
