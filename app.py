"""
VideoFetcher 主程序 - 精简版
"""

import os

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["DO_NOT_TRACK"] = "1"

import logging
import tempfile
import zipfile
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import gradio as gr

from config import get_config
from models import (
    User,
    DownloadTask,
    init_users,
    get_user,
    get_user_tasks,
    get_all_tasks,
    format_size,
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


# ============ 认证 ============

def authenticate(username: str, password: str) -> User | None:
    """验证用户登录"""
    user = get_user(username)
    if user and user.verify_password(password):
        logger.info(f"用户登录成功: {username}")
        return user
    logger.warning(f"登录失败: {username}")
    return None


# ============ 列表 HTML 生成 ============

def generate_task_list_html(tasks: list[DownloadTask]) -> str:
    """生成任务列表 HTML"""
    if not tasks:
        return '<div style="text-align:center;padding:40px;color:#999;">暂无下载任务</div>'

    rows = []
    for t in tasks:
        # 状态和颜色
        status_map = {
            DownloadTask.STATUS_PENDING: ("等待中", "#FF9800"),
            DownloadTask.STATUS_DOWNLOADING: ("下载中", "#2196F3"),
            DownloadTask.STATUS_COMPLETED: ("已完成", "#4CAF50"),
            DownloadTask.STATUS_FAILED: ("失败", "#f44336"),
        }
        status_text, status_color = status_map.get(t.status, (t.status, "#999"))

        # 标题
        title = t.title or t.url[:50]

        # 进度/大小
        if t.status == DownloadTask.STATUS_COMPLETED:
            progress_text = format_size(t.file_size) if t.file_size > 0 else "已完成"
        elif t.status == DownloadTask.STATUS_DOWNLOADING:
            progress_text = f"{t.progress:.1f}%"
        else:
            progress_text = "-"

        rows.append(f"""
        <tr>
            <td style="padding:8px;max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="{title}">{title}</td>
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


# ============ CSS 样式 ============

APP_CSS = """
.section-title {
    font-size: 16px !important;
    font-weight: 600 !important;
    margin: 8px 0 !important;
    padding-bottom: 4px !important;
    border-bottom: 1px solid #e5e5e5 !important;
}
"""


# ============ 界面构建 ============

def create_app() -> gr.Blocks:
    """创建 Gradio 应用"""
    config = get_config()

    load_credentials_js = """
    async () => {
        await new Promise(r => setTimeout(r, 200));
        return [
            localStorage.getItem('vf_username') || '',
            localStorage.getItem('vf_password') || '',
            localStorage.getItem('vf_remember') === 'true'
        ];
    }
    """

    save_credentials_js = """
    () => {
        const form = document.querySelector('form');
        const inputs = form?.querySelectorAll('input') || [];
        const username = inputs[0]?.value || '';
        const password = inputs[1]?.value || '';
        const remember = inputs[2]?.checked || false;
        if (remember && username && password) {
            localStorage.setItem('vf_username', username);
            localStorage.setItem('vf_password', password);
            localStorage.setItem('vf_remember', 'true');
        }
    }
    """

    with gr.Blocks(title="VideoFetcher", css=APP_CSS) as app:
        current_user = gr.State(None)

        # -------- 登录页面 --------
        with gr.Column(visible=True) as login_page:
            gr.Markdown("# VideoFetcher")
            with gr.Row():
                with gr.Column(scale=1):
                    pass
                with gr.Column(scale=2):
                    login_username = gr.Textbox(label="用户名", placeholder="请输入用户名")
                    login_password = gr.Textbox(label="密码", type="password", placeholder="请输入密码")
                    remember_me = gr.Checkbox(label="记住密码", value=False)
                    login_btn = gr.Button("登录", variant="primary")
                    login_msg = gr.Markdown("")
                with gr.Column(scale=1):
                    pass

        # -------- 主界面 --------
        with gr.Column(visible=False) as main_page:
            with gr.Row():
                gr.Markdown("# VideoFetcher")
                user_info = gr.Markdown("")
                logout_btn = gr.Button("退出", size="sm", scale=0)

            # ========== 新建下载 ==========
            gr.Markdown("### 新建下载", elem_classes="section-title")
            with gr.Row():
                url_input = gr.Textbox(
                    label="视频链接",
                    placeholder="粘贴视频链接，每行一个",
                    lines=3,
                    scale=3,
                )
                with gr.Column(scale=1):
                    quality_select = gr.Dropdown(
                        label="画质",
                        choices=["best", "1080p", "720p", "480p", "audio"],
                        value=config.download.default_quality,
                    )
                    download_btn = gr.Button("开始下载", variant="primary")
            download_msg = gr.Markdown("")

            # ========== 下载任务 ==========
            gr.Markdown("### 下载任务", elem_classes="section-title")
            task_list = gr.HTML("")

            # ========== 已完成文件 ==========
            gr.Markdown("### 已完成文件", elem_classes="section-title")
            completed_files = gr.File(
                label="点击下载",
                file_count="multiple",
                interactive=False,
            )
            with gr.Row():
                download_all_btn = gr.Button("打包下载全部", variant="secondary")
            zip_file = gr.File(label="压缩包", visible=False)

            timer = gr.Timer(value=2, active=False)

        # ============ 事件处理函数 ============

        def do_login(username: str, password: str, remember: bool = False):  # noqa: ARG001
            """登录"""
            if not username or not password:
                return gr.update(), gr.update(), None, "请输入用户名和密码", gr.update(active=False)

            user = authenticate(username, password)
            if user:
                return (
                    gr.update(visible=False),
                    gr.update(visible=True),
                    user,
                    f"**{user.username}** ({user.role})",
                    gr.update(active=True),
                )
            return gr.update(), gr.update(), None, "用户名或密码错误", gr.update(active=False)

        def set_credentials(username: str, password: str, remember: bool):
            """从 localStorage 设置凭据到输入框"""
            return username, password, remember

        def try_auto_login(username: str, password: str, remember: bool):
            """尝试自动登录"""
            if remember and username and password:
                user = authenticate(username, password)
                if user:
                    return (
                        gr.update(visible=False),
                        gr.update(visible=True),
                        user,
                        f"**{user.username}** ({user.role})",
                        gr.update(active=True),
                    )
            return gr.update(), gr.update(), None, "", gr.update(active=False)

        def do_logout():
            """退出"""
            return gr.update(visible=True), gr.update(visible=False), None, "", gr.update(active=False)

        def do_download(url: str, quality: str, user: User):
            """开始下载"""
            if not user:
                return "请先登录", gr.update(), gr.update()
            if not url.strip():
                return "请输入视频链接", gr.update(), gr.update()

            try:
                urls = [u.strip() for u in url.strip().split("\n") if u.strip()]
                for u in urls:
                    downloader.start_download(user, u, quality)
                html, files = refresh_list(user)
                return f"已创建 {len(urls)} 个下载任务", html, files
            except Exception as e:
                return f"创建失败: {e}", gr.update(), gr.update()

        def refresh_list(user: User):
            """刷新任务列表和已完成文件"""
            if not user:
                return "", None
            tasks = get_all_tasks() if user.is_admin else get_user_tasks(user.username)
            html = generate_task_list_html(tasks)

            # 获取已完成的文件路径
            completed = [
                t.file_path for t in tasks
                if t.status == DownloadTask.STATUS_COMPLETED
                and t.file_path
                and Path(t.file_path).exists()
            ]

            return html, completed if completed else None

        def download_all_as_zip(user: User):
            """将所有已完成文件打包成 zip"""
            if not user:
                return gr.update(visible=False)

            tasks = get_all_tasks() if user.is_admin else get_user_tasks(user.username)
            completed = [
                t.file_path for t in tasks
                if t.status == DownloadTask.STATUS_COMPLETED
                and t.file_path
                and Path(t.file_path).exists()
            ]

            if not completed:
                return gr.update(visible=False)

            # 创建临时 zip 文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_path = Path(tempfile.gettempdir()) / f"videos_{timestamp}.zip"

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in completed:
                    fp = Path(file_path)
                    zf.write(fp, fp.name)

            return gr.update(value=str(zip_path), visible=True)

        # -------- 绑定事件 --------

        # 页面加载：先设置输入框，再尝试自动登录
        app.load(
            set_credentials,
            outputs=[login_username, login_password, remember_me],
            js=load_credentials_js,
        ).then(
            try_auto_login,
            inputs=[login_username, login_password, remember_me],
            outputs=[login_page, main_page, current_user, user_info, timer],
        )

        # 登录按钮
        login_btn.click(
            do_login,
            inputs=[login_username, login_password, remember_me],
            outputs=[login_page, main_page, current_user, user_info, timer],
        ).then(fn=None, js=save_credentials_js)

        login_password.submit(
            do_login,
            inputs=[login_username, login_password, remember_me],
            outputs=[login_page, main_page, current_user, user_info, timer],
        ).then(fn=None, js=save_credentials_js)
        logout_btn.click(
            do_logout,
            outputs=[login_page, main_page, current_user, login_msg, timer],
        )

        download_btn.click(
            do_download,
            inputs=[url_input, quality_select, current_user],
            outputs=[download_msg, task_list, completed_files],
        )

        timer.tick(
            refresh_list,
            inputs=[current_user],
            outputs=[task_list, completed_files],
        )

        download_all_btn.click(
            download_all_as_zip,
            inputs=[current_user],
            outputs=[zip_file],
        )

    return app


# ============ 主入口 ============

def main():
    """主函数"""
    setup_logging()
    logger.info("启动 VideoFetcher...")

    config = get_config()
    logger.info(f"服务配置: {config.server.host}:{config.server.port}")

    init_users()
    logger.info("用户初始化完成")

    Path(config.download.base_dir).mkdir(parents=True, exist_ok=True)

    app = create_app()
    logger.info(f"启动 Web 服务: http://{config.server.host}:{config.server.port}")

    app.launch(
        server_name=config.server.host,
        server_port=config.server.port,
        share=False,
        show_error=True,
        enable_monitoring=False,
    )


if __name__ == "__main__":
    main()
