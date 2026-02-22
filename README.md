# VideoFetcher

基于 Python + yt-dlp 的视频下载工具，提供 NiceGUI Web 界面，支持批量下载、实时进度显示。

## 功能特点

- **批量下载**：支持多个视频链接同时下载
- **多平台支持**：YouTube、Bilibili、Twitter/X、抖音等主流平台
- **实时进度**：显示下载速度、进度、剩余时间
- **文件下载**：支持将服务端文件下载到本地浏览器
- **多用户支持**：支持多用户登录，用户间数据隔离
- **权限管理**：区分管理员/普通用户，管理员可查看所有用户数据
- **存储统计**：展示用户已占用存储空间
- **下载预览**：解析链接后预览视频信息（标题、时长、封面），确认后再下载
- **历史记录**：保存下载历史，支持搜索筛选、批量删除、批量重新下载
- **视频预览**：在线预览已下载的视频，支持从历史记录直接播放
- **任务管理**：后台持久化下载，关闭浏览器也不中断，支持暂停/终止/重启

## 快速开始

### 环境要求

- Python 3.9+
- FFmpeg（用于视频合并）

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd VideoFetcher

# 安装依赖（使用当前 Python 环境，无需虚拟环境）
pip install -r requirements.txt
```

### 配置

创建 `config.yaml` 文件：

```yaml
# 服务配置
server:
  host: 0.0.0.0
  port: 7860

# 下载配置
download:
  base_dir: ./downloads
  max_concurrent: 3
  default_quality: best  # best/1080p/720p/480p/audio

# 日志配置
logging:
  level: INFO            # DEBUG/INFO/WARNING/ERROR
  file: ./logs/app.log
  max_size: 10MB
  backup_count: 5

# 用户配置
users:
  - username: admin
    password: admin123
    role: admin          # 管理员：可查看所有用户数据
  - username: wangtong
    password: pass123
    role: user           # 普通用户：仅查看自己的数据
  - username: caotong
    password: pass456
    role: user

# 可选：NiceGUI 会话密钥（用于登录态）。未设置时从环境变量 VIDEOFETCHER_STORAGE_SECRET 读取；生产环境建议设置
# storage_secret: "your-random-secret"
```

每个用户的下载文件存储在 `{base_dir}/{username}/` 目录下，互不干扰。

### 运行

```bash
python app.py
# 或使用 just
just run
```

访问 `http://localhost:7860`，使用配置的用户名密码登录。生产环境建议设置 `storage_secret`（config.yaml）或环境变量 `VIDEOFETCHER_STORAGE_SECRET`。

## 使用说明

### 下载视频

1. 在输入框中粘贴视频链接（每行一个）
2. 点击「解析」预览视频信息（标题、时长、封面）
3. 选择视频质量，点击「下载」
4. 在任务列表查看下载进度
5. 下载完成后，点击文件名保存到本地

### 历史记录

- 支持按平台、日期范围、关键词筛选
- 勾选多条记录进行批量删除或重新下载
- 点击记录可预览视频或查看详情

## 支持的平台

yt-dlp 支持 1000+ 网站，常用的包括：

| 平台 | 支持状态 |
|------|----------|
| YouTube | ✅ |
| Bilibili | ✅ |
| Twitter/X | ✅ |
| 抖音/TikTok | ✅ |
| 微博 | ✅ |
| Instagram | ✅ |

完整列表参见 [yt-dlp 支持站点](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

## 项目结构

```text
VideoFetcher/
├── app.py               # 主程序入口
├── downloader.py        # 下载核心逻辑
├── config.py            # 配置管理
├── models.py            # 数据模型
├── config.yaml          # 配置文件（需自行创建）
├── config.example.yaml  # 配置示例
├── requirements.txt     # 依赖清单
├── .gitignore
├── data.db              # SQLite 数据库（运行时生成）
├── logs/                # 日志目录
└── downloads/           # 下载文件目录
    └── {username}/      # 每个用户独立目录
```

## 数据模型

使用 SQLite + Peewee 存储数据：

```python
# 用户
class User(Model):
    username = CharField(unique=True)
    password_hash = CharField()  # 密码哈希存储
    role = CharField()           # admin/user
    storage_used = BigIntegerField(default=0)  # 已用存储(bytes)
    created_at = DateTimeField()

# 下载任务（进行中）
class DownloadTask(Model):
    task_id = CharField()        # 任务ID（8位短UUID，用于文件目录）
    user = ForeignKeyField(User) # 所属用户
    url = CharField()            # 视频链接
    title = CharField()          # 视频标题
    status = CharField()         # pending/downloading/paused/completed/failed
    progress = FloatField()      # 下载进度(0-100)
    speed = CharField()          # 当前速度
    eta = CharField()            # 预计剩余时间
    error_msg = TextField()      # 错误信息
    created_at = DateTimeField()
    updated_at = DateTimeField()

# 下载历史（已完成）
class DownloadHistory(Model):
    user = ForeignKeyField(User) # 所属用户
    url = CharField()            # 视频链接
    title = CharField()          # 视频标题
    filename = CharField()       # 原始文件名
    file_path = CharField()      # 本地存储路径（相对于用户目录）
    platform = CharField()       # 来源平台
    status = CharField()         # completed/failed
    file_size = IntegerField()   # 文件大小(bytes)
    duration = IntegerField()    # 时长(秒)
    width = IntegerField()       # 视频宽度
    height = IntegerField()      # 视频高度
    format = CharField()         # 视频格式(mp4/webm等)
    created_at = DateTimeField() # 下载时间
```

任务完成后自动从 `DownloadTask` 移至 `DownloadHistory`。

### 文件存储策略

为避免文件名冲突，每个下载任务使用独立目录：

```text
downloads/{username}/{task_id}/{filename}.{ext}
```

示例：

```text
downloads/
└── admin/
    ├── a1b2c3d4/
    │   └── 视频标题.mp4
    └── e5f6g7h8/
        └── 视频标题.mp4    # 同名文件不冲突
```

`task_id` 为 8 位短 UUID，确保唯一性的同时保持路径简洁。

## 依赖

```text
nicegui>=2.0
yt-dlp
pyyaml
```

## 注意事项

- 仅供个人学习使用，请遵守相关平台的服务条款
- 部分平台可能需要 cookies 才能下载（登录态）
- 建议部署在内网或配置 HTTPS

## License

MIT
