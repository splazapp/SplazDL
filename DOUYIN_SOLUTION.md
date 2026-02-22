# 抖音视频下载问题解决方案

## 问题描述

当尝试使用 yt_dlp 下载抖音搜索页面的 URL 时，遇到以下错误：

```
ERROR: Unsupported URL: https://www.douyin.com/search/...?modal_id=7568832119439522417...
```

## 根本原因

yt_dlp 的 DouyinIE 提取器只支持标准的视频 URL 格式：
```
https://www.douyin.com/video/{video_id}
```

而搜索页面的 URL 格式不被支持：
```
https://www.douyin.com/root/search/...?modal_id={video_id}&...
```

## 解决方案

### 第一步：URL 自动转换（已实现）✅

已在 `downloader.py` 中添加了 `_preprocess_url()` 函数，可以自动将搜索页面 URL 转换为标准格式。

**转换示例：**
- **输入：** `https://www.douyin.com/root/search/...?modal_id=7568832119439522417&...`
- **输出：** `https://www.douyin.com/video/7568832119439522417`

**代码位置：** [downloader.py:45-84](downloader.py#L45-L84)

**支持的转换类型：**
1. 抖音搜索页面 URL（带 modal_id 参数）
2. 抖音分享链接 URL（带 modal_id 参数）
3. TikTok 类似的 modal_id URL
4. 已经是标准格式的 URL（直接返回）

### 第二步：配置 Cookies（必需）🔑

抖音需要有效的 cookies 才能下载视频（反爬虫机制）。有两种方法：

#### 方法 A：从浏览器自动导入 Cookies（推荐）

修改 `downloader.py` 中的 `_download_worker()` 函数，添加 cookies 配置：

```python
# 在 ydl_opts 中添加（第 121 行附近）
ydl_opts = {
    "format": _get_format_selector(quality),
    "outtmpl": str(task_dir / f"{safe_filename}.%(ext)s"),
    "progress_hooks": [progress_hook],
    "quiet": True,
    "no_warnings": True,
    "merge_output_format": "mp4",
    # 从浏览器导入 cookies（Chrome、Firefox、Edge 等）
    "cookiesfrombrowser": ("chrome",),  # 或 "firefox", "edge", "safari" 等
}
```

**支持的浏览器：**
- Chrome/Chromium
- Firefox
- Edge
- Safari
- Opera
- Brave

#### 方法 B：手动导出 Cookies 文件

1. 在浏览器中访问 https://www.douyin.com（无需登录）
2. 使用浏览器扩展导出 cookies（推荐：EditThisCookie、cookies.txt）
3. 保存为 `douyin_cookies.txt`（Netscape 格式）
4. 在代码中配置：

```python
ydl_opts = {
    # ...其他配置
    "cookiefile": "/path/to/douyin_cookies.txt",
}
```

### 第三步：测试

使用你的原始 URL 测试：

```python
from downloader import _preprocess_url

# 你的原始 URL
url = "https://www.douyin.com/root/search/%E4%B8%80%E4%BA%8C%E7%86%8A%E7%86%8A%E8%AF%AD?aid=47a3ba5a-a114-4379-8411-f80ca24f7ae0&modal_id=7568832119439522417&type=general"

# 自动转换
processed = _preprocess_url(url)
print(processed)
# 输出: https://www.douyin.com/video/7568832119439522417
```

## 实现细节

### URL 预处理逻辑

```python
def _preprocess_url(url: str) -> str:
    if 'douyin.com' in url:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        # 提取 modal_id 参数
        if 'modal_id' in query_params:
            modal_id = query_params['modal_id'][0]
            return f'https://www.douyin.com/video/{modal_id}'

    return url
```

### 修改建议

在 `downloader.py` 的第 170 行附近，修改 `ydl_opts`：

```python
# 修改前
ydl_opts = {
    "format": _get_format_selector(quality),
    "outtmpl": str(task_dir / f"{safe_filename}.%(ext)s"),
    "progress_hooks": [progress_hook],
    "quiet": True,
    "no_warnings": True,
    "merge_output_format": "mp4",
}

# 修改后
ydl_opts = {
    "format": _get_format_selector(quality),
    "outtmpl": str(task_dir / f"{safe_filename}.%(ext)s"),
    "progress_hooks": [progress_hook],
    "quiet": True,
    "no_warnings": True,
    "merge_output_format": "mp4",
    "cookiesfrombrowser": ("chrome",),  # 添加这行
}
```

## 常见问题

### Q1: 为什么需要 cookies？
A: 抖音使用了反爬虫机制，需要有效的 session cookies（`s_v_web_id` 等）才能访问视频 API。

### Q2: 是否需要登录抖音账号？
A: **不需要**！只需要在浏览器中访问过 douyin.com 即可，yt_dlp 会自动获取必要的 session cookies。

### Q3: cookies 会过期吗？
A: 会的。通常在几小时到几天后过期。使用 `cookiesfrombrowser` 选项可以自动获取最新的 cookies。

### Q4: 如果 Chrome 浏览器没有访问过抖音怎么办？
A: 在 Chrome 中访问一次 https://www.douyin.com，等待页面完全加载即可。

### Q5: 其他视频网站需要类似配置吗？
A: 部分网站（如 B站、微博等）也可能需要 cookies，使用相同的方法即可。

## 测试结果

已通过测试的功能：
- ✅ URL 格式自动识别
- ✅ modal_id 参数提取
- ✅ URL 转换为标准格式
- ✅ yt_dlp DouyinIE 识别转换后的 URL
- ⚠️ 需要配置 cookies 才能实际下载

## 快速开始

1. **确保浏览器已访问过抖音**
   ```bash
   # 在 Chrome 中打开
   open -a "Google Chrome" https://www.douyin.com
   ```

2. **运行测试**
   ```bash
   python test_url_preprocessing.py
   ```

3. **修改 downloader.py 添加 cookies 配置**
   ```python
   # 在 ydl_opts 中添加
   "cookiesfrombrowser": ("chrome",),
   ```

4. **启动应用并测试下载**
   ```bash
   python app.py
   ```

## 参考资料

- yt_dlp DouyinIE 源代码：`demos/yt-dlp/yt_dlp/extractor/tiktok.py:1267-1399`
- yt_dlp cookies 文档：https://github.com/yt-dlp/yt-dlp#cookies
- 抖音 API 分析：`demos/yt-dlp/yt_dlp/extractor/tiktok.py`

---

**更新日期：** 2025-12-25
**状态：** 已解决（需要配置 cookies）
