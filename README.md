# SplazDL

[中文](README.zh-CN.md) | **English**

SplazDL is a Python + `yt-dlp` web downloader with a NiceGUI interface.  
It supports batch jobs, live progress tracking, multi-user isolation, and persistent background tasks.

## Features

- Batch download (multiple URLs at once)
- Multi-platform support (YouTube, Bilibili, Twitter/X, Douyin, etc.)
- Live task status (speed, progress, ETA)
- Multi-user login with role-based permissions
- Download preview before starting (title, duration, thumbnail)
- Download history with filtering, bulk delete, and re-download
- Online playback preview for downloaded videos
- Persistent tasks that continue even after browser close

## Quick Start

### Requirements

- Python 3.9+
- FFmpeg (for media post-processing/merging)

### Install

```bash
git clone <repo-url>
cd SplazDL
pip install -r requirements.txt
```

### Configure

Copy the example config and adjust values:

```bash
cp config.example.yaml config.yaml
```

Minimal example:

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

Each user's files are saved under `{base_dir}/{username}/`.

### Run

```bash
python app.py
# or
just run
```

Open `http://localhost:7860` and sign in with credentials from `config.yaml`.

For production, set `storage_secret` in `config.yaml` or `VIDEOFETCHER_STORAGE_SECRET` in environment variables.

## Usage

### Download Videos

1. Paste one or multiple URLs (one per line)
2. Click parse to preview metadata
3. Choose quality and start download
4. Track progress in task list
5. Download completed files from the UI

### History

- Filter by platform/date/keyword
- Select multiple records for bulk delete or re-download
- Click a record to preview/play details

## Supported Platforms

`yt-dlp` supports 1000+ sites. Common examples:

| Platform | Status |
| --- | --- |
| YouTube | ✅ |
| Bilibili | ✅ |
| Twitter/X | ✅ |
| Douyin/TikTok | ✅ |
| Weibo | ✅ |
| Instagram | ✅ |

Full list: [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

## Project Structure

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

## Storage Strategy

To avoid filename collisions, each task writes into an isolated directory:

```text
downloads/{username}/{task_id}/{filename}.{ext}
```

`task_id` is a short 8-char UUID.

## Related Docs

- `DOUYIN_SOLUTION.md`
- `SETUP_COOKIES.md`
- `QUICK_START_DOUYIN.md`

## Notes

- For personal/educational use only; follow platform ToS
- Some platforms may require cookies (logged-in session)
- Use HTTPS and private-network deployment for production

## License

MIT
