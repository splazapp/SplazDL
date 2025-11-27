"""
数据模型模块 - 纯内存存储版本
"""

import hashlib
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from config import get_config


@dataclass
class User:
    """用户（从配置文件读取）"""
    username: str
    password_hash: str
    role: str = "user"

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str) -> bool:
        return self.password_hash == self.hash_password(password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@dataclass
class DownloadTask:
    """下载任务（内存存储）"""
    STATUS_PENDING = "pending"
    STATUS_DOWNLOADING = "downloading"
    STATUS_PAUSED = "paused"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    task_id: str
    username: str
    url: str
    title: str = ""
    status: str = STATUS_PENDING
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    error_msg: str = ""
    file_path: str = ""
    file_size: int = 0
    created_at: datetime = field(default_factory=datetime.now)


# ============ 内存存储 ============

_users: dict[str, User] = {}
_tasks: dict[str, DownloadTask] = {}
_lock = threading.Lock()


def init_users():
    """从配置文件初始化用户"""
    config = get_config()
    for user_cfg in config.users:
        _users[user_cfg.username] = User(
            username=user_cfg.username,
            password_hash=User.hash_password(user_cfg.password),
            role=user_cfg.role,
        )


def get_user(username: str) -> User | None:
    """获取用户"""
    return _users.get(username)


def generate_task_id() -> str:
    """生成8位任务ID"""
    return uuid.uuid4().hex[:8]


def create_task(username: str, url: str) -> DownloadTask:
    """创建任务"""
    task = DownloadTask(
        task_id=generate_task_id(),
        username=username,
        url=url,
    )
    with _lock:
        _tasks[task.task_id] = task
    return task


def get_task(task_id: str) -> DownloadTask | None:
    """获取任务"""
    return _tasks.get(task_id)


def get_user_tasks(username: str) -> list[DownloadTask]:
    """获取用户的所有任务"""
    with _lock:
        return [t for t in _tasks.values() if t.username == username]


def get_all_tasks() -> list[DownloadTask]:
    """获取所有任务"""
    with _lock:
        return list(_tasks.values())


def get_existing_urls(username: str | None = None) -> set[str]:
    """获取已存在的任务链接集合

    Args:
        username: 如果指定，只返回该用户的链接；否则返回所有链接
    """
    with _lock:
        if username:
            return {t.url for t in _tasks.values() if t.username == username}
        return {t.url for t in _tasks.values()}


def get_completed_tasks(username: str | None = None) -> list[DownloadTask]:
    """获取已完成的任务"""
    with _lock:
        tasks = _tasks.values()
        if username:
            tasks = [t for t in tasks if t.username == username]
        return [t for t in tasks if t.status == DownloadTask.STATUS_COMPLETED]


def delete_task(task_id: str):
    """删除任务"""
    with _lock:
        _tasks.pop(task_id, None)


def clear_tasks(username: str | None = None) -> list[str]:
    """清空任务并返回任务目录路径列表

    Args:
        username: 如果指定，只清空该用户的任务；否则清空所有任务

    Returns:
        任务目录路径列表
    """
    config = get_config()
    base_dir = Path(config.download.base_dir)

    with _lock:
        if username:
            # 只清空指定用户的任务
            tasks_to_remove = [t for t in _tasks.values() if t.username == username]
        else:
            # 清空所有任务
            tasks_to_remove = list(_tasks.values())

        # 收集任务目录路径
        task_dirs = []
        for t in tasks_to_remove:
            task_dir = base_dir / t.username / t.task_id
            if task_dir.exists():
                task_dirs.append(str(task_dir))

        # 删除任务
        for task in tasks_to_remove:
            _tasks.pop(task.task_id, None)

        return task_dirs


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    return f"{size:.1f} {units[unit_index]}"


def ensure_user_directory(username: str) -> Path:
    """确保用户目录存在"""
    config = get_config()
    user_dir = Path(config.download.base_dir) / username
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir
