"""
SplazDL 主程序 - NiceGUI 版
"""

import os

os.environ["DO_NOT_TRACK"] = "1"

import html
import json
import logging
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from nicegui import app, ui

from config import get_config
from models import (
    User,
    DownloadTask,
    init_users,
    get_user,
    get_user_tasks,
    get_all_tasks,
    create_tasks_if_new,
    format_size,
    clear_tasks,
)
import downloader


# ============ 日志配置 ============

def setup_logging():
    """配置日志"""
    config = get_config()
    log_cfg = config.logging

    log_path = Path(log_cfg.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_cfg.file,
        maxBytes=log_cfg.get_max_bytes(),
        backupCount=log_cfg.backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_cfg.level))
    root_logger.addHandler(handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root_logger.addHandler(console_handler)


logger = logging.getLogger(__name__)


# ============ Cloudflare Access 认证 ============

def _get_request_header(name: str) -> str:
    """兼容不同上下文读取请求头。"""
    try:
        request = getattr(app, "request", None)
        if request and getattr(request, "headers", None):
            return (request.headers.get(name) or "").strip()
    except Exception:
        pass

    try:
        client = ui.context.client
        request = getattr(client, "request", None)
        if request and getattr(request, "headers", None):
            return (request.headers.get(name) or "").strip()
    except Exception:
        pass
    return ""


def get_runtime_user_from_headers() -> tuple[User, str]:
    """优先使用 Cloudflare Access 邮箱头映射用户；本地无头回退 admin。"""
    config = get_config()
    email = _get_request_header("Cf-Access-Authenticated-User-Email")
    if email:
        mapped = get_user(email)
        if mapped:
            return mapped, email
        logger.warning("Cloudflare Access 邮箱未配置到用户: %s，将回退 admin", email)

    for user_cfg in config.users:
        if user_cfg.role == "admin":
            admin_user = get_user(user_cfg.username)
            if admin_user:
                return admin_user, email

    for user_cfg in config.users:
        fallback = get_user(user_cfg.username)
        if fallback:
            return fallback, email

    raise RuntimeError("config.yaml 未配置可用用户，请至少添加一个 users 项")


def _download_url(task_id: str) -> str:
    return f"/download/{task_id}"


def _download_all_url() -> str:
    return "/download-all"


@app.get("/download/{task_id}")
def download_by_task_id(task_id: str):
    task = downloader.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    user, _ = get_runtime_user_from_headers()
    if not user.is_admin and task.username != user.username:
        raise HTTPException(status_code=403, detail="无权限访问该任务文件")
    if task.status != DownloadTask.STATUS_COMPLETED:
        raise HTTPException(status_code=400, detail="任务未完成，暂不可下载")
    if not task.file_path:
        raise HTTPException(status_code=404, detail="任务缺少文件路径")

    fp = Path(task.file_path)
    if not fp.exists() or not fp.is_file():
        raise HTTPException(status_code=404, detail="文件不存在，可能已被移动或删除")

    return FileResponse(path=str(fp), filename=_build_safe_download_name(task))


@app.get("/download-all")
def download_all_completed_files():
    user, _ = get_runtime_user_from_headers()
    zip_path = build_zip_path(user)
    if not zip_path:
        raise HTTPException(status_code=404, detail="暂无已完成文件")
    filename = f"videos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return FileResponse(path=zip_path, filename=filename)


# ============ 列表 HTML 生成 ============

def generate_task_list_html(tasks: list[DownloadTask]) -> str:
    """生成任务列表 HTML"""
    if not tasks:
        return '<div style="text-align:center;padding:40px;color:#999;">暂无下载任务</div>'

    rows = []
    for t in tasks:
        status_map = {
            DownloadTask.STATUS_PENDING: ("等待中", "#FF9800"),
            DownloadTask.STATUS_DOWNLOADING: ("下载中", "#2196F3"),
            DownloadTask.STATUS_COMPLETED: ("已完成", "#4CAF50"),
            DownloadTask.STATUS_FAILED: ("失败", "#f44336"),
        }
        status_text, status_color = status_map.get(t.status, (t.status, "#999"))
        title = t.title or "获取中..."
        if t.status == DownloadTask.STATUS_COMPLETED:
            progress_text = format_size(t.file_size) if t.file_size > 0 else "已完成"
        elif t.status == DownloadTask.STATUS_DOWNLOADING:
            progress_text = f"{t.progress:.1f}%"
        else:
            progress_text = "-"
        speed_eta_html = ""
        if t.status == DownloadTask.STATUS_DOWNLOADING and (t.speed or t.eta):
            speed = t.speed or "-"
            eta = t.eta or "-"
            speed_eta_html = (
                f'<div style="font-size:11px;color:#666;margin-top:2px;">'
                f'速度: {speed} · 剩余: {eta}</div>'
            )
        error_html = ""
        if t.status == DownloadTask.STATUS_FAILED and t.error_msg:
            error_escaped = html.escape(t.error_msg)
            error_html = f'<div style="font-size:11px;color:#f44336;margin-top:2px;word-break:break-all;">{error_escaped}</div>'
        rows.append(f"""
        <tr>
            <td style="padding:8px;">
                <div style="font-weight:500;">{title}</div>
                <div style="font-size:12px;color:#888;word-break:break-all;">{t.url}</div>
                {speed_eta_html}
                {error_html}
            </td>
            <td style="padding:8px;text-align:center;"><span style="color:{status_color};font-weight:500;">{status_text}</span></td>
            <td style="padding:8px;text-align:center;">{progress_text}</td>
        </tr>
        """)
    return f"""
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
            <tr style="background:#f5f5f5;border-bottom:2px solid #ddd;">
                <th style="padding:10px;text-align:left;">标题</th>
                <th style="padding:10px;text-align:center;width:80px;">状态</th>
                <th style="padding:10px;text-align:center;width:120px;">进度/大小</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
    """


def generate_completed_info_html(tasks: list[DownloadTask]) -> str:
    """生成已完成文件信息 HTML"""
    completed_tasks = [
        t for t in tasks
        if t.status == DownloadTask.STATUS_COMPLETED
        and t.file_path
        and Path(t.file_path).exists()
    ]
    if not completed_tasks:
        return '<div style="text-align:center;padding:20px;color:#999;">暂无已完成文件</div>'
    rows = []
    for t in completed_tasks:
        title = t.title or "未知"
        size_text = format_size(t.file_size) if t.file_size > 0 else "-"
        rows.append(f"""
        <tr>
            <td style="padding:6px;">
                <div style="font-weight:500;">{title}</div>
                <div style="font-size:12px;color:#888;word-break:break-all;">{t.url}</div>
            </td>
            <td style="padding:6px;text-align:center;">{size_text}</td>
        </tr>
        """)
    return f"""
    <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:8px;">
        <thead>
            <tr style="background:#f0f9f0;border-bottom:1px solid #ddd;">
                <th style="padding:8px;text-align:left;">文件信息</th>
                <th style="padding:8px;text-align:center;width:80px;">大小</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
    """


# ============ 业务逻辑（纯函数，无 UI） ============

def do_download(url: str, quality: str, user: User | None, options: dict | None = None) -> str:
    """解析 URL、去重、创建下载任务；返回提示消息"""
    if not user:
        return "未找到运行用户，请检查 config.yaml 的 users 配置"
    if not url.strip():
        return "请输入视频链接"
    try:
        seen = set()
        urls = []
        for line in url.strip().split("\n"):
            u = line.strip()
            if u and u not in seen:
                seen.add(u)
                urls.append(u)
        if not urls:
            return "请输入有效的视频链接"
        normalized_urls = [downloader.preprocess_url(u) for u in urls]
        created_tasks, skipped_count = create_tasks_if_new(user.username, normalized_urls)
        if not created_tasks:
            return f"所有链接已在下载任务中（跳过 {skipped_count} 个重复链接）"
        for task in created_tasks:
            downloader.start_download_for_task(task, quality, options or {})
        msg = f"已创建 {len(created_tasks)} 个下载任务"
        if skipped_count > 0:
            msg += f"（跳过 {skipped_count} 个重复链接）"
        return msg
    except Exception as e:
        return f"创建失败: {e}"


def _format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "-"
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h:d}:{m:02d}:{sec:02d}"
    return f"{m:d}:{sec:02d}"


def _format_dt(dt: datetime | None) -> str:
    if not dt:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _build_safe_download_name(task: DownloadTask) -> str:
    """生成可读且安全的下载文件名。"""
    src_path = Path(task.file_path) if task.file_path else None
    suffix = src_path.suffix if src_path and src_path.suffix else ".bin"
    raw_title = (task.title or "").strip() or "video"
    # 保留中英文和常见可读字符，去掉容易影响 URL/文件系统的符号。
    safe_title = re.sub(r'[\\/:*?"<>|#%&{}$!`\'@+=;,]', "_", raw_title)
    safe_title = re.sub(r"\s+", " ", safe_title).strip(" ._")
    if not safe_title:
        safe_title = "video"
    if len(safe_title) > 80:
        safe_title = safe_title[:80].rstrip(" ._")
    return f"{safe_title}_{task.task_id}{suffix}"


def get_completed_file_paths(user: User | None) -> list[str]:
    """获取当前用户已完成且存在的文件路径列表"""
    if not user:
        return []
    tasks = get_all_tasks() if user.is_admin else get_user_tasks(user.username)
    return [
        t.file_path for t in tasks
        if t.status == DownloadTask.STATUS_COMPLETED
        and t.file_path
        and Path(t.file_path).exists()
    ]


def build_zip_path(user: User | None) -> str | None:
    """将所有已完成文件打包成 zip，返回临时 zip 路径；无文件则返回 None"""
    if not user:
        return None
    config = get_config()
    tasks = get_all_tasks() if user.is_admin else get_user_tasks(user.username)
    completed = [
        t.file_path for t in tasks
        if t.status == DownloadTask.STATUS_COMPLETED
        and t.file_path
        and Path(t.file_path).exists()
    ]
    if not completed:
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = Path(tempfile.gettempdir()) / f"videos_{timestamp}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    for file_path in completed:
        fp = Path(file_path)
        dest = temp_dir / fp.name
        shutil.copy2(fp, dest)
        try:
            subprocess.run(["xattr", "-r", "-c", str(dest)], check=False, capture_output=True)
            for attr in ["kMDItemWhereFroms", "kMDItemFinderComment"]:
                result = subprocess.run(
                    ["xattr", "-px", f"com.apple.metadata:{attr}", str(fp)],
                    capture_output=True, text=True,
                )
                if result.returncode == 0 and result.stdout.strip():
                    subprocess.run(
                        ["xattr", "-wx", f"com.apple.metadata:{attr}",
                         result.stdout.strip().replace("\n", "").replace(" ", ""), str(dest)],
                        check=False, capture_output=True,
                    )
        except Exception:
            pass
    zip_path = Path(tempfile.gettempdir()) / f"videos_{timestamp}.zip"
    try:
        subprocess.run(
            ["ditto", "-c", "-k", "--keepParent", "--rsrc", str(temp_dir), str(zip_path)],
            check=True, capture_output=True,
        )
    except Exception:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in completed:
                fp = Path(file_path)
                zf.write(fp, fp.name)
    shutil.rmtree(temp_dir, ignore_errors=True)
    return str(zip_path)


def do_clear_all(user: User | None) -> None:
    """清空任务并将目录移动到 .trash"""
    if not user:
        return
    config = get_config()
    username = None if user.is_admin else user.username
    task_dirs = clear_tasks(username)
    trash_base = Path(config.download.base_dir) / ".trash"
    for task_dir_path in task_dirs:
        try:
            task_dir = Path(task_dir_path)
            if task_dir.exists():
                task_username = task_dir.parent.name
                user_trash_dir = trash_base / task_username
                user_trash_dir.mkdir(parents=True, exist_ok=True)
                dest = user_trash_dir / task_dir.name
                if dest.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    dest = user_trash_dir / f"{task_dir.name}_{timestamp}"
                shutil.move(str(task_dir), str(dest))
        except Exception as e:
            logger.warning("移动目录到回收站失败: %s, 错误: %s", task_dir_path, e)
    logger.info("用户 %s 清空了 %s 个任务", user.username, len(task_dirs))


# ============ 页面 ============

@ui.page("/")
def main_page() -> None:
    """主页面：新建下载、任务列表、已完成文件、打包/清空（增强版）"""
    config = get_config()
    user, access_email = get_runtime_user_from_headers()
    preview_state = {"items": [], "error": ""}
    task_filter_state = {"status": "all", "keyword": ""}
    task_column_state = {
        "visible": ["task_id", "title", "status", "progress", "speed", "eta", "action"],
    }

    with ui.column().classes("w-full max-w-[1400px] mx-auto p-3 gap-3"):
        # 头部
        with ui.row().classes("w-full items-center"):
            ui.label("SplazDL").classes("text-h6")
            ui.space()
            display_identity = access_email or "local-admin"
            ui.badge(f"管理员: {display_identity}").props("outline")
            ui.badge(f"映射用户: {user.username} ({user.role})").props("outline")

        # 新建下载
        with ui.card().classes("w-full p-4"):
            ui.label("新建下载").classes("text-subtitle1")
            with ui.row().classes("w-full items-start gap-3"):
                url_input = ui.textarea(
                    label="视频链接",
                    placeholder="粘贴视频链接，每行一个",
                ).classes("grow min-w-[460px]")
                with ui.column().classes("w-64 gap-2"):
                    quality_select = ui.select(
                        {"best": "best", "1080p": "1080p", "720p": "720p", "480p": "480p", "audio": "audio"},
                        value=config.download.default_quality,
                        label="画质",
                    ).classes("w-full")
                    audio_format_select = ui.select(
                        {"mp3": "mp3", "m4a": "m4a", "wav": "wav", "flac": "flac", "opus": "opus"},
                        value="mp3",
                        label="音频格式（仅 audio）",
                    ).classes("w-full")
                    download_btn = ui.button("开始下载", on_click=None).props("unelevated color=primary").classes("w-full")
                    preview_btn = ui.button("批量预览链接", on_click=None).props("outline").classes("w-full")

            with ui.expansion("高级选项（yt-dlp）", value=False).classes("w-full q-mt-sm"):
                with ui.row().classes("w-full items-end gap-2 q-mb-sm"):
                    preset_select = ui.select(
                        {
                            "default": "默认（通用）",
                            "douyin": "抖音/TikTok（稳定优先）",
                            "bilibili": "B站（字幕封面元数据）",
                            "youtube": "YouTube（字幕+封面）",
                            "audio": "音频提取（Podcast/Music）",
                        },
                        value="default",
                        label="参数预设",
                    ).classes("w-72")
                    apply_preset_btn = ui.button("应用预设").props("outline")
                    export_cfg_btn = ui.button("导出配置").props("outline")
                    cfg_upload = ui.upload(
                        label="导入配置(JSON)",
                        auto_upload=True,
                        max_file_size=1_000_000,
                    ).props("accept=.json").classes("w-52")
                    refresh_cookie_btn = ui.button("打开抖音刷新Cookies").props("outline")
                    detect_cookie_btn = ui.button("检测并自动选择Cookies来源").props("outline")

                with ui.row().classes("w-full items-start gap-3"):
                    with ui.column().classes("w-[320px] gap-1"):
                        download_playlist = ui.switch("下载整个播放列表", value=False)
                        write_subs = ui.switch("下载字幕（含自动字幕）", value=False)
                        sub_langs = ui.input("字幕语言", value="zh.*,en.*", placeholder="如: zh.*,en.*").classes("w-full")
                        write_thumbnail = ui.switch("下载缩略图", value=False)
                        embed_thumbnail = ui.switch("嵌入封面图", value=False)
                        embed_metadata = ui.switch("写入媒体元数据", value=True)
                        use_download_archive = ui.switch("启用下载去重档案（避免重复下载）", value=True)

                    with ui.column().classes("w-[360px] gap-1"):
                        cookies_from_browser = ui.select(
                            {
                                "": "不使用",
                                "safari": "safari",
                                "chrome": "chrome",
                                "firefox": "firefox",
                                "edge": "edge",
                                "brave": "brave",
                            },
                            value="safari",
                            label="从浏览器读取 Cookies",
                        ).classes("w-full")
                        cookie_file = ui.input("Cookies 文件路径", placeholder="Netscape cookies.txt 路径，可选").classes("w-full")
                        proxy = ui.input("代理地址", placeholder="如: socks5://127.0.0.1:1080").classes("w-full")
                        rate_limit = ui.input("限速", placeholder="如: 2M / 500K").classes("w-full")
                        retries = ui.number("重试次数", value=10, min=0, step=1, format="%.0f").classes("w-full")
                        fragment_retries = ui.number("分片重试次数", value=10, min=0, step=1, format="%.0f").classes("w-full")
                        concurrent_fragments = ui.number("分片并发数", value=1, min=1, step=1, format="%.0f").classes("w-full")

            @ui.refreshable
            def preview_ui():
                items = preview_state["items"]
                error = preview_state["error"]
                if error:
                    ui.label(f"预览失败: {error}").classes("text-negative")
                    return
                if not items:
                    ui.label("预览区：点击“批量预览链接”逐条探测可下载性、标题和清晰度").classes("text-grey-7")
                    return

                columns = [
                    {"name": "idx", "label": "#", "field": "idx", "sortable": True},
                    {"name": "status", "label": "状态", "field": "status", "sortable": True},
                    {"name": "title", "label": "标题", "field": "title"},
                    {"name": "duration", "label": "时长", "field": "duration", "sortable": True},
                    {"name": "uploader", "label": "发布者", "field": "uploader"},
                    {"name": "heights", "label": "可选清晰度", "field": "heights"},
                    {"name": "error", "label": "失败原因", "field": "error"},
                ]
                rows = []
                for i, item in enumerate(items, start=1):
                    rows.append({
                        "idx": i,
                        "status": "可下载" if item["ok"] else "失败",
                        "title": item.get("title", "-"),
                        "duration": _format_duration(item.get("duration")),
                        "uploader": item.get("uploader", "-"),
                        "heights": ", ".join(f"{h}p" for h in item.get("available_heights", [])) or "-",
                        "error": item.get("error", ""),
                    })
                ui.table(columns=columns, rows=rows, row_key="idx", pagination=8).classes("w-full")

            preview_ui()

    def get_scoped_tasks() -> list[DownloadTask]:
        return get_all_tasks() if user.is_admin else get_user_tasks(user.username)

    def get_filtered_tasks() -> list[DownloadTask]:
        tasks = get_scoped_tasks()
        status = task_filter_state["status"]
        keyword = (task_filter_state["keyword"] or "").strip().lower()
        if status != "all":
            tasks = [t for t in tasks if t.status == status]
        if keyword:
            tasks = [
                t for t in tasks
                if keyword in (t.title or "").lower() or keyword in (t.url or "").lower() or keyword in t.task_id.lower()
            ]
        return tasks

    def _status_text(status: str) -> str:
        return {
            DownloadTask.STATUS_PENDING: "等待中",
            DownloadTask.STATUS_DOWNLOADING: "下载中",
            DownloadTask.STATUS_COMPLETED: "已完成",
            DownloadTask.STATUS_FAILED: "失败",
            DownloadTask.STATUS_PAUSED: "已暂停",
        }.get(status, status)

    def _task_row(task: DownloadTask) -> dict:
        if task.status == DownloadTask.STATUS_COMPLETED:
            progress = format_size(task.file_size) if task.file_size > 0 else "已完成"
        elif task.status == DownloadTask.STATUS_DOWNLOADING:
            progress = f"{task.progress:.1f}%"
        else:
            progress = "-"
        return {
            "task_id": task.task_id,
            "title": task.title or "获取中...",
            "status": _status_text(task.status),
            "status_raw": task.status,
            "progress": progress,
            "speed": task.speed or "-",
            "eta": task.eta or "-",
            "url": task.url,
            "error": task.error_msg or "",
        }

    def handle_task_action(action: str, task_id: str):
        task = downloader.get_task(task_id)
        if not task:
            ui.notify("任务不存在", color="negative")
            return

        if action == "download":
            if task.status != DownloadTask.STATUS_COMPLETED:
                ui.notify("任务未完成，暂不可下载", color="warning")
            elif not task.file_path:
                ui.notify("任务缺少文件路径，请重试下载", color="negative")
            elif not Path(task.file_path).exists():
                ui.notify("文件不存在，可能已被移动或删除", color="negative")
            else:
                ui.run_javascript(f"window.open({json.dumps(_download_url(task.task_id))}, '_blank')")
        elif action == "pause":
            ok = downloader.pause_task(task.task_id)
            ui.notify("已请求暂停" if ok else "任务不可暂停", color="warning" if ok else "negative")
        elif action == "cancel":
            ok = downloader.cancel_task(task.task_id)
            ui.notify("已取消任务" if ok else "任务取消失败", color="warning" if ok else "negative")
        elif action == "retry":
            downloader.start_download(
                user,
                task.url,
                quality_select.value or "best",
                collect_download_options(),
            )
            ui.notify("已重新创建下载任务", color="positive")
        elif action == "copy_error":
            if not task.error_msg:
                ui.notify("该任务暂无错误信息", color="warning")
            else:
                ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(task.error_msg)})")
                ui.notify("错误信息已复制到剪贴板", color="positive")

        task_table_ui.refresh()
        completed_ui.refresh()
        history_ui.refresh()

    @ui.refreshable
    def task_table_ui():
        tasks = get_filtered_tasks()
        if not tasks:
            ui.label("暂无下载任务").classes("text-grey-7 q-mt-sm")
            return

        all_columns = [
            {"name": "task_id", "label": "任务ID", "field": "task_id", "sortable": True},
            {"name": "title", "label": "标题", "field": "title"},
            {"name": "status", "label": "状态", "field": "status", "sortable": True},
            {"name": "progress", "label": "进度/大小", "field": "progress", "sortable": True},
            {"name": "speed", "label": "速度", "field": "speed"},
            {"name": "eta", "label": "剩余", "field": "eta"},
            {"name": "action", "label": "操作", "field": "action"},
        ]
        visible = set(task_column_state["visible"])
        columns = [c for c in all_columns if c["name"] in visible]
        rows = [_task_row(t) for t in tasks]
        table = ui.table(columns=columns, rows=rows, row_key="task_id", pagination=8).classes("w-full")
        if "action" in visible:
            with table.add_slot("body-cell-action"):
                with table.cell("action"):
                    with ui.row().classes("q-gutter-xs no-wrap"):
                        ui.button("下载").props("flat dense size=sm color=positive").on(
                            "click",
                            js_handler='() => emit(["download", props.row.task_id])',
                            handler=lambda e: handle_task_action(e.args[0], e.args[1]),
                        )
                        ui.button("暂停").props("flat dense size=sm").on(
                            "click",
                            js_handler='() => emit(["pause", props.row.task_id])',
                            handler=lambda e: handle_task_action(e.args[0], e.args[1]),
                        )
                        ui.button("取消").props("flat dense size=sm color=negative").on(
                            "click",
                            js_handler='() => emit(["cancel", props.row.task_id])',
                            handler=lambda e: handle_task_action(e.args[0], e.args[1]),
                        )
                        ui.button("重试").props("flat dense size=sm color=primary").on(
                            "click",
                            js_handler='() => emit(["retry", props.row.task_id])',
                            handler=lambda e: handle_task_action(e.args[0], e.args[1]),
                        )
                        ui.button("复制错误").props("flat dense size=sm").on(
                            "click",
                            js_handler='() => emit(["copy_error", props.row.task_id])',
                            handler=lambda e: handle_task_action(e.args[0], e.args[1]),
                        )

    @ui.refreshable
    def completed_ui():
        def trigger_file_download(task_id: str):
            ui.run_javascript(f"window.open({json.dumps(_download_url(task_id))}, '_blank')")

        tasks = get_scoped_tasks()
        completed = [
            t for t in tasks
            if t.status == DownloadTask.STATUS_COMPLETED and t.file_path and Path(t.file_path).exists()
        ]
        if not completed:
            ui.label("暂无已完成文件").classes("text-grey-7")
            return

        rows = [
            {
                "task_id": t.task_id,
                "title": t.title or "未知",
                "size": format_size(t.file_size),
                "created_at": _format_dt(t.created_at),
                "file_path": t.file_path,
            }
            for t in sorted(completed, key=lambda x: x.created_at, reverse=True)
        ]
        columns = [
            {"name": "task_id", "label": "任务ID", "field": "task_id", "sortable": True},
            {"name": "title", "label": "标题", "field": "title"},
            {"name": "size", "label": "大小", "field": "size", "sortable": True},
            {"name": "created_at", "label": "完成时间", "field": "created_at", "sortable": True},
            {"name": "action", "label": "操作", "field": "action"},
        ]
        table = ui.table(columns=columns, rows=rows, row_key="task_id", pagination=8).classes("w-full")
        with table.add_slot("body-cell-action"):
            with table.cell("action"):
                ui.button("下载").props("flat dense size=sm color=primary").on(
                    "click",
                    js_handler='() => emit(props.row.task_id)',
                    handler=lambda e: trigger_file_download(e.args),
                )

    @ui.refreshable
    def history_ui():
        tasks = sorted(get_scoped_tasks(), key=lambda x: x.created_at, reverse=True)
        if not tasks:
            ui.label("暂无历史任务").classes("text-grey-7")
            return
        rows = [
            {
                "task_id": t.task_id,
                "title": t.title or "获取中...",
                "status": _status_text(t.status),
                "created_at": _format_dt(t.created_at),
                "error": t.error_msg or "",
            }
            for t in tasks
        ]
        columns = [
            {"name": "task_id", "label": "任务ID", "field": "task_id", "sortable": True},
            {"name": "title", "label": "标题", "field": "title"},
            {"name": "status", "label": "状态", "field": "status", "sortable": True},
            {"name": "created_at", "label": "创建时间", "field": "created_at", "sortable": True},
            {"name": "error", "label": "失败原因", "field": "error"},
        ]
        ui.table(columns=columns, rows=rows, row_key="task_id", pagination=10).classes("w-full")

    def collect_download_options() -> dict:
        cookie_file_value = (cookie_file.value or "").strip()
        cookies_from_browser_value = (cookies_from_browser.value or "").strip()
        if cookie_file_value:
            # cookie_file 优先，避免两种来源混用造成行为不确定
            cookies_from_browser_value = ""
        return {
            "audio_only": (quality_select.value or "best") == "audio",
            "audio_format": audio_format_select.value or "mp3",
            "write_subs": bool(write_subs.value),
            "sub_langs": sub_langs.value or "",
            "write_thumbnail": bool(write_thumbnail.value),
            "embed_thumbnail": bool(embed_thumbnail.value),
            "embed_metadata": bool(embed_metadata.value),
            "download_playlist": bool(download_playlist.value),
            "proxy": proxy.value or "",
            "cookie_file": cookie_file_value,
            "cookies_from_browser": cookies_from_browser_value,
            "rate_limit": rate_limit.value or "",
            "retries": int(retries.value or 10),
            "fragment_retries": int(fragment_retries.value or 10),
            "concurrent_fragments": int(concurrent_fragments.value or 1),
            "use_download_archive": bool(use_download_archive.value),
        }

    def apply_preset():
        preset = preset_select.value or "default"
        # 先恢复通用默认
        download_playlist.set_value(False)
        write_subs.set_value(False)
        sub_langs.set_value("zh.*,en.*")
        write_thumbnail.set_value(False)
        embed_thumbnail.set_value(False)
        embed_metadata.set_value(True)
        use_download_archive.set_value(True)
        cookies_from_browser.set_value("safari")
        cookie_file.set_value("")
        proxy.set_value("")
        rate_limit.set_value("")
        retries.set_value(10)
        fragment_retries.set_value(10)
        concurrent_fragments.set_value(1)
        quality_select.set_value(config.download.default_quality)
        audio_format_select.set_value("mp3")

        if preset == "douyin":
            download_playlist.set_value(False)
            write_subs.set_value(False)
            write_thumbnail.set_value(True)
            embed_metadata.set_value(True)
            cookies_from_browser.set_value("safari")
            retries.set_value(15)
            fragment_retries.set_value(15)
            concurrent_fragments.set_value(1)
        elif preset == "bilibili":
            download_playlist.set_value(False)
            write_subs.set_value(True)
            sub_langs.set_value("zh.*,en.*")
            write_thumbnail.set_value(True)
            embed_thumbnail.set_value(True)
            embed_metadata.set_value(True)
            retries.set_value(10)
            fragment_retries.set_value(10)
            concurrent_fragments.set_value(2)
        elif preset == "youtube":
            download_playlist.set_value(False)
            write_subs.set_value(True)
            sub_langs.set_value("en.*,zh.*")
            write_thumbnail.set_value(True)
            embed_thumbnail.set_value(True)
            embed_metadata.set_value(True)
            retries.set_value(10)
            fragment_retries.set_value(10)
            concurrent_fragments.set_value(2)
        elif preset == "audio":
            quality_select.set_value("audio")
            audio_format_select.set_value("mp3")
            write_subs.set_value(False)
            write_thumbnail.set_value(True)
            embed_thumbnail.set_value(True)
            embed_metadata.set_value(True)

        preset_names = {
            "default": "默认（通用）",
            "douyin": "抖音/TikTok（稳定优先）",
            "bilibili": "B站（字幕封面元数据）",
            "youtube": "YouTube（字幕+封面）",
            "audio": "音频提取（Podcast/Music）",
        }
        ui.notify(f"已应用预设: {preset_names.get(preset, preset)}", color="positive")
        save_ui_prefs()

    def save_ui_prefs():
        app.storage.user[f"ui_prefs:{user.username}"] = {
            "quality": quality_select.value,
            "audio_format": audio_format_select.value,
            "download_playlist": bool(download_playlist.value),
            "write_subs": bool(write_subs.value),
            "sub_langs": sub_langs.value or "",
            "write_thumbnail": bool(write_thumbnail.value),
            "embed_thumbnail": bool(embed_thumbnail.value),
            "embed_metadata": bool(embed_metadata.value),
            "use_download_archive": bool(use_download_archive.value),
            "cookies_from_browser": cookies_from_browser.value or "",
            "cookie_file": cookie_file.value or "",
            "proxy": proxy.value or "",
            "rate_limit": rate_limit.value or "",
            "retries": int(retries.value or 10),
            "fragment_retries": int(fragment_retries.value or 10),
            "concurrent_fragments": int(concurrent_fragments.value or 1),
            "preset": preset_select.value or "default",
            "task_filter_status": task_filter_state["status"],
            "task_filter_keyword": task_filter_state["keyword"],
            "task_visible_columns": task_column_state["visible"],
        }

    def load_ui_prefs():
        prefs = app.storage.user.get(f"ui_prefs:{user.username}", {}) or {}
        quality_select.set_value(prefs.get("quality", quality_select.value))
        audio_format_select.set_value(prefs.get("audio_format", audio_format_select.value))
        download_playlist.set_value(bool(prefs.get("download_playlist", download_playlist.value)))
        write_subs.set_value(bool(prefs.get("write_subs", write_subs.value)))
        sub_langs.set_value(prefs.get("sub_langs", sub_langs.value))
        write_thumbnail.set_value(bool(prefs.get("write_thumbnail", write_thumbnail.value)))
        embed_thumbnail.set_value(bool(prefs.get("embed_thumbnail", embed_thumbnail.value)))
        embed_metadata.set_value(bool(prefs.get("embed_metadata", embed_metadata.value)))
        use_download_archive.set_value(bool(prefs.get("use_download_archive", use_download_archive.value)))
        cookies_from_browser.set_value(prefs.get("cookies_from_browser", cookies_from_browser.value))
        cookie_file.set_value(prefs.get("cookie_file", cookie_file.value))
        proxy.set_value(prefs.get("proxy", proxy.value))
        rate_limit.set_value(prefs.get("rate_limit", rate_limit.value))
        retries.set_value(int(prefs.get("retries", retries.value or 10)))
        fragment_retries.set_value(int(prefs.get("fragment_retries", fragment_retries.value or 10)))
        concurrent_fragments.set_value(int(prefs.get("concurrent_fragments", concurrent_fragments.value or 1)))
        preset_select.set_value(prefs.get("preset", preset_select.value))
        task_filter_state["status"] = prefs.get("task_filter_status", task_filter_state["status"])
        task_filter_state["keyword"] = prefs.get("task_filter_keyword", task_filter_state["keyword"])
        task_column_state["visible"] = prefs.get("task_visible_columns", task_column_state["visible"])

    def open_douyin_for_cookie_refresh():
        """打开抖音页面，让浏览器生成/刷新会话 cookies。"""
        browser = (cookies_from_browser.value or "safari").strip() or "safari"
        app_name_map = {
            "safari": "Safari",
            "chrome": "Google Chrome",
            "firefox": "Firefox",
            "edge": "Microsoft Edge",
            "brave": "Brave Browser",
        }
        app_name = app_name_map.get(browser)
        cmd = ["open", "https://www.douyin.com"] if not app_name else ["open", "-a", app_name, "https://www.douyin.com"]
        try:
            subprocess.run(cmd, check=False, capture_output=True)
            ui.notify("已打开抖音页面，请滑动几条视频后点击“检测并自动选择Cookies来源”", color="positive")
        except Exception as ex:
            ui.notify(f"打开浏览器失败: {ex}", color="negative")

    def _probe_cookie_from_browser(browser_name: str) -> tuple[bool, str]:
        """检查指定浏览器是否存在抖音关键 cookie。"""
        try:
            from yt_dlp.cookies import extract_cookies_from_browser

            class _NoopLogger:
                def debug(self, msg, *args, **kwargs):
                    return None

                def info(self, msg, *args, **kwargs):
                    return None

                def warning(self, msg, *args, **kwargs):
                    return None

                def error(self, msg, *args, **kwargs):
                    return None

            jar = extract_cookies_from_browser(browser_name, logger=_NoopLogger())
            douyin_cookies = [c for c in jar if "douyin.com" in c.domain]
            if not douyin_cookies:
                return False, "未读取到 douyin.com cookies"
            cookie_names = {c.name for c in douyin_cookies}
            if "s_v_web_id" in cookie_names:
                return True, f"找到 {len(douyin_cookies)} 个 douyin cookies（含 s_v_web_id）"
            return False, f"读取到 {len(douyin_cookies)} 个 cookies，但缺少 s_v_web_id"
        except Exception as ex:
            return False, str(ex)

    def detect_and_select_cookie_source():
        """检测可用浏览器 cookies，并自动设置到高级选项。"""
        if (cookie_file.value or "").strip():
            ui.notify("已填写 cookie_file，已优先使用文件来源", color="warning")
            return

        try:
            from yt_dlp.cookies import SUPPORTED_BROWSERS
        except Exception as ex:
            ui.notify(f"无法加载 yt-dlp cookies 模块: {ex}", color="negative")
            return

        preferred_order = ["safari", "chrome", "firefox", "edge", "brave"]
        candidates = [b for b in preferred_order if b in SUPPORTED_BROWSERS]
        for browser in candidates:
            ok, detail = _probe_cookie_from_browser(browser)
            if ok:
                cookies_from_browser.set_value(browser)
                save_ui_prefs()
                ui.notify(f"已自动选择 {browser}: {detail}", color="positive")
                return

        ui.notify("未检测到可用抖音 cookies，请先点击“打开抖音刷新Cookies”并浏览几条视频", color="warning")

    def toggle_task_column(col_key: str, enabled: bool):
        visible = task_column_state["visible"]
        if enabled and col_key not in visible:
            visible.append(col_key)
        elif not enabled and col_key in visible:
            if len(visible) == 1:
                ui.notify("至少保留一列可见", color="warning")
                return
            visible.remove(col_key)
        save_ui_prefs()
        task_table_ui.refresh()

    def export_ui_config():
        payload = {
            "version": 1,
            "preset": preset_select.value or "default",
            "quality": quality_select.value or "best",
            "options": collect_download_options(),
            "task_filter_status": task_filter_state["status"],
            "task_filter_keyword": task_filter_state["keyword"],
            "task_visible_columns": task_column_state["visible"],
        }
        ui.download.content(
            json.dumps(payload, ensure_ascii=False, indent=2),
            f"videofetcher-config-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )
        ui.notify("配置已导出", color="positive")

    async def import_ui_config(e):
        try:
            text = await e.file.text()
            data = json.loads(text)
            quality_select.set_value(data.get("quality", quality_select.value))
            opts = data.get("options", {})
            audio_format_select.set_value(opts.get("audio_format", audio_format_select.value))
            write_subs.set_value(bool(opts.get("write_subs", write_subs.value)))
            sub_langs.set_value(opts.get("sub_langs", sub_langs.value))
            write_thumbnail.set_value(bool(opts.get("write_thumbnail", write_thumbnail.value)))
            embed_thumbnail.set_value(bool(opts.get("embed_thumbnail", embed_thumbnail.value)))
            embed_metadata.set_value(bool(opts.get("embed_metadata", embed_metadata.value)))
            download_playlist.set_value(bool(opts.get("download_playlist", download_playlist.value)))
            proxy.set_value(opts.get("proxy", proxy.value))
            cookie_file.set_value(opts.get("cookie_file", cookie_file.value))
            cookies_from_browser.set_value(opts.get("cookies_from_browser", cookies_from_browser.value))
            rate_limit.set_value(opts.get("rate_limit", rate_limit.value))
            retries.set_value(int(opts.get("retries", retries.value or 10)))
            fragment_retries.set_value(int(opts.get("fragment_retries", fragment_retries.value or 10)))
            concurrent_fragments.set_value(int(opts.get("concurrent_fragments", concurrent_fragments.value or 1)))
            use_download_archive.set_value(bool(opts.get("use_download_archive", use_download_archive.value)))

            preset_select.set_value(data.get("preset", preset_select.value))
            task_filter_state["status"] = data.get("task_filter_status", task_filter_state["status"])
            task_filter_state["keyword"] = data.get("task_filter_keyword", task_filter_state["keyword"])
            task_column_state["visible"] = data.get("task_visible_columns", task_column_state["visible"])
            save_ui_prefs()
            task_table_ui.refresh()
            completed_ui.refresh()
            history_ui.refresh()
            ui.notify("配置导入成功", color="positive")
        except Exception as ex:
            ui.notify(f"配置导入失败: {ex}", color="negative")

    def on_download_click():
        msg = do_download(
            url_input.value or "",
            quality_select.value or "best",
            user,
            collect_download_options(),
        )
        ui.notify(msg, color="positive" if msg.startswith("已创建") else None)
        task_table_ui.refresh()
        completed_ui.refresh()
        history_ui.refresh()
        save_ui_prefs()

    download_btn.on("click", on_download_click)

    def on_preview_click():
        lines = [line.strip() for line in (url_input.value or "").split("\n") if line.strip()]
        if not lines:
            ui.notify("请先输入至少一个链接", color="warning")
            return
        dedup_urls = list(dict.fromkeys(lines))[:10]
        if len(lines) > 10:
            ui.notify("仅预览前 10 条链接（其余请分批）", color="warning")

        preview_state["items"] = []
        preview_state["error"] = ""
        opts = collect_download_options()
        try:
            for u in dedup_urls:
                try:
                    info = downloader.probe_info(u, opts)
                    preview_state["items"].append({
                        "ok": True,
                        "url": u,
                        **info,
                    })
                except Exception as e:
                    preview_state["items"].append({
                        "ok": False,
                        "url": u,
                        "title": "-",
                        "uploader": "-",
                        "duration": 0,
                        "available_heights": [],
                        "video_exts": [],
                        "audio_exts": [],
                        "webpage_url": u,
                        "error": str(e),
                    })
        except Exception as e:
            preview_state["error"] = str(e)
        preview_ui.refresh()

    preview_btn.on("click", on_preview_click)
    apply_preset_btn.on("click", apply_preset)
    export_cfg_btn.on("click", export_ui_config)
    cfg_upload.on("upload", import_ui_config)
    refresh_cookie_btn.on("click", open_douyin_for_cookie_refresh)
    detect_cookie_btn.on("click", detect_and_select_cookie_source)
    for element in [
        quality_select, audio_format_select, download_playlist, write_subs, sub_langs,
        write_thumbnail, embed_thumbnail, embed_metadata, use_download_archive,
        cookies_from_browser, cookie_file, proxy, rate_limit, retries, fragment_retries,
        concurrent_fragments, preset_select,
    ]:
        element.on("update:model-value", lambda _: save_ui_prefs())
    load_ui_prefs()

    with ui.column().classes("w-full max-w-[1400px] mx-auto px-3 pb-3 gap-3"):
        with ui.card().classes("w-full p-4"):
            ui.label("下载任务").classes("text-subtitle1")
            with ui.row().classes("w-full items-end gap-2 q-mb-sm"):
                ui.select(
                    {
                        "all": "全部",
                        DownloadTask.STATUS_PENDING: "等待中",
                        DownloadTask.STATUS_DOWNLOADING: "下载中",
                        DownloadTask.STATUS_COMPLETED: "已完成",
                        DownloadTask.STATUS_FAILED: "失败",
                    },
                    value=task_filter_state["status"],
                    label="状态筛选",
                    on_change=lambda e: (
                        task_filter_state.update(status=e.value),
                        task_table_ui.refresh(),
                        save_ui_prefs(),
                    ),
                ).classes("w-40")
                ui.input(
                    "关键词",
                    value=task_filter_state["keyword"],
                    placeholder="按标题/链接/task_id搜索",
                    on_change=lambda e: (
                        task_filter_state.update(keyword=e.value or ""),
                        task_table_ui.refresh(),
                        save_ui_prefs(),
                    ),
                ).classes("w-80")
            with ui.expansion("任务表列显示设置", value=False).classes("w-full q-mb-sm"):
                with ui.row().classes("q-gutter-sm q-gutter-y-xs"):
                    for col_key, col_label in [
                        ("task_id", "任务ID"),
                        ("title", "标题"),
                        ("status", "状态"),
                        ("progress", "进度/大小"),
                        ("speed", "速度"),
                        ("eta", "剩余"),
                        ("action", "操作"),
                    ]:
                        ui.switch(
                            col_label,
                            value=col_key in task_column_state["visible"],
                            on_change=lambda e, key=col_key: toggle_task_column(key, bool(e.value)),
                        )
            with ui.row().classes("q-gutter-sm q-mb-sm"):
                def on_retry_failed_all():
                    failed = [t for t in get_scoped_tasks() if t.status == DownloadTask.STATUS_FAILED]
                    if not failed:
                        ui.notify("暂无失败任务", color="warning")
                        return
                    for t in failed:
                        downloader.start_download(
                            user,
                            t.url,
                            quality_select.value or "best",
                            collect_download_options(),
                        )
                    ui.notify(f"已重新创建 {len(failed)} 个失败任务", color="positive")
                    task_table_ui.refresh()
                    history_ui.refresh()
                ui.button("重试全部失败", on_click=on_retry_failed_all).props("outline")
            task_table_ui()

        with ui.card().classes("w-full p-4"):
            ui.label("已完成文件").classes("text-subtitle1")
            completed_ui()

            with ui.row().classes("q-gutter-sm q-mt-sm"):
                def on_download_all():
                    if not get_completed_file_paths(user):
                        ui.notify("暂无可打包的已完成文件", color="warning")
                        return
                    ui.run_javascript(f"window.open({json.dumps(_download_all_url())}, '_blank')")
                    ui.notify("已开始打包下载", color="positive")

                def on_clear_all():
                    do_clear_all(user)
                    task_table_ui.refresh()
                    completed_ui.refresh()
                    ui.notify("已清空", color="warning")

                ui.button("打包下载全部", on_click=on_download_all).props("outline")
                ui.button("清空全部", on_click=on_clear_all).props("flat color=negative")

        with ui.card().classes("w-full p-4"):
            ui.label("历史任务（分页）").classes("text-subtitle1")
            history_ui()

    ui.timer(2.0, lambda: (task_table_ui.refresh(), completed_ui.refresh(), history_ui.refresh()))


# ============ 样式 ============

ui.add_head_html("""
<style>
body { background: #f7f8fa; }
.q-card { border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.q-field__label { font-size: 12px; }
.q-table th { font-weight: 600; }
</style>
""", shared=True)


# ============ 主入口 ============

def main() -> None:
    """主函数"""
    setup_logging()
    logger.info("启动 SplazDL...")

    config = get_config()
    logger.info("服务配置: %s:%s", config.server.host, config.server.port)

    init_users()
    logger.info("用户初始化完成")

    Path(config.download.base_dir).mkdir(parents=True, exist_ok=True)

    storage_secret = (
        (config.storage_secret or "").strip()
        or os.environ.get("VIDEOFETCHER_STORAGE_SECRET", "")
        or "videofetcher-local-ui-state"
    )

    logger.info("启动 Web 服务: http://%s:%s", config.server.host, config.server.port)
    ui.run(
        host=config.server.host,
        port=config.server.port,
        reload=False,
        storage_secret=storage_secret,
        title="SplazDL",
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
