# SplazDL

**中文** | [English](README.md)

SplazDL 是一个基于 Python + `yt-dlp` 的 Web 视频下载工具，使用 NiceGUI 构建界面。  
支持批量下载、实时进度、多用户隔离和后台持久任务。

## 功能特点

- 批量下载（支持多链接同时处理）
- 多平台支持（YouTube、Bilibili、Twitter/X、抖音等）
- 实时任务状态（速度、进度、剩余时间）
- 多用户登录与角色权限管理
- 下载前预览（标题、时长、封面等）
- 历史记录（筛选、批量删除、重新下载）
- 在线预览已下载视频
- 后台持久任务（关闭浏览器不影响下载）

## 快速开始

### 环境要求

- Python 3.9+
- FFmpeg（用于媒体后处理/合并）

### 安装

```bash
git clone <repo-url>
cd SplazDL
pip install -r requirements.txt
```

### 配置

复制配置模板后按需修改：

```bash
cp config.example.yaml config.yaml
```

最小配置示例：

```yaml
server:
  host: 0.0.0.0
  port: 7860

download:
  base_dir: ./downloads
  max_concurrent: 3
  default_quality: best

users:
  - username: admin
    password: changeme
    role: admin
```

每个用户的文件会保存到 `{base_dir}/{username}/` 目录中。

### 运行

```bash
python app.py
# 或
just run
```

浏览器访问 `http://localhost:7860`，使用 `config.yaml` 中配置的账号登录。

生产环境建议在 `config.yaml` 中设置 `storage_secret`，或通过环境变量 `VIDEOFETCHER_STORAGE_SECRET` 提供。

## 使用说明

### 下载视频

1. 粘贴一个或多个视频链接（每行一个）
2. 点击解析并预览视频信息
3. 选择清晰度并开始下载
4. 在任务列表查看实时进度
5. 下载完成后在界面中获取文件

### 历史记录

- 支持按平台、日期、关键词筛选
- 支持批量删除和批量重新下载
- 点击记录可查看详情与在线播放

## 支持平台

`yt-dlp` 支持 1000+ 网站，常见平台包括：

| 平台 | 支持状态 |
| --- | --- |
| YouTube | ✅ |
| Bilibili | ✅ |
| Twitter/X | ✅ |
| 抖音/TikTok | ✅ |
| 微博 | ✅ |
| Instagram | ✅ |

完整站点列表见：[yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

## 项目结构

```text
SplazDL/
├── app.py
├── downloader.py
├── config.py
├── models.py
├── config.yaml
├── config.example.yaml
├── requirements.txt
├── data.db
├── logs/
└── downloads/
    └── {username}/
```

## 文件存储策略

为避免同名冲突，每个任务使用独立目录：

```text
downloads/{username}/{task_id}/{filename}.{ext}
```

`task_id` 为 8 位短 UUID。

## 相关文档

- `DOUYIN_SOLUTION.md`
- `SETUP_COOKIES.md`
- `QUICK_START_DOUYIN.md`

## 注意事项

- 仅用于个人学习与研究，请遵守平台服务条款
- 部分平台可能需要 cookies（登录态）
- 生产部署建议使用 HTTPS，并限制访问范围

## License

MIT
