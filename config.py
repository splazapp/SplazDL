"""
配置管理模块
从 config.yaml 加载配置，提供类型安全的访问接口
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml


@dataclass
class ServerConfig:
    """服务配置"""
    host: str = "0.0.0.0"
    port: int = 7860


@dataclass
class DownloadConfig:
    """下载配置"""
    base_dir: str = "./downloads"
    max_concurrent: int = 3
    default_quality: str = "best"


@dataclass
class LoggingConfig:
    """日志配置"""
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file: str = "./logs/app.log"
    max_size: str = "10MB"
    backup_count: int = 5

    def get_max_bytes(self) -> int:
        """将 max_size 转换为字节数"""
        size = self.max_size.upper()
        if size.endswith("MB"):
            return int(size[:-2]) * 1024 * 1024
        if size.endswith("KB"):
            return int(size[:-2]) * 1024
        return int(size)


@dataclass
class UserConfig:
    """用户配置"""
    username: str
    password: str
    role: Literal["admin", "user"] = "user"


@dataclass
class AppConfig:
    """应用配置"""
    server: ServerConfig = field(default_factory=ServerConfig)
    download: DownloadConfig = field(default_factory=DownloadConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    users: list[UserConfig] = field(default_factory=list)
    # Session 密钥，用于 NiceGUI app.storage.user；未设置时从环境变量 VIDEOFETCHER_STORAGE_SECRET 读取
    storage_secret: str | None = None


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """
    加载配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        AppConfig 实例
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # 解析各配置块
    server = ServerConfig(**data.get("server", {}))
    download = DownloadConfig(**data.get("download", {}))
    logging_cfg = LoggingConfig(**data.get("logging", {}))

    # 解析用户列表
    users = [UserConfig(**u) for u in data.get("users", [])]

    return AppConfig(
        server=server,
        download=download,
        logging=logging_cfg,
        users=users,
        storage_secret=data.get("storage_secret"),
    )


# 全局配置实例（延迟加载）
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> AppConfig:
    """重新加载配置"""
    global _config
    _config = load_config()
    return _config
