# 抖音视频下载快速开始指南

## ✅ 问题已解决

你的抖音搜索页面 URL 下载问题已经完全解决！

### 原始错误
```
ERROR: Unsupported URL: https://www.douyin.com/search/...?modal_id=7568832119439522417
```

### 解决方案
已自动将搜索 URL 转换为标准格式，并配置了 cookies 支持。

---

## 🚀 快速开始（3 步）

### 步骤 1: 在浏览器中访问抖音
```bash
# 在 Chrome 中打开抖音（无需登录）
open -a "Google Chrome" https://www.douyin.com
```

等待页面完全加载后关闭即可。这会在浏览器中保存必要的 cookies。

### 步骤 2: 启动应用
```bash
python app.py
```

### 步骤 3: 直接粘贴你的 URL
在 Web 界面中，直接粘贴你的搜索页面 URL：
```
https://www.douyin.com/root/search/%E4%B8%80%E4%BA%8C%E7%86%8A%E7%86%8A%E8%AF%AD?aid=47a3ba5a-a114-4379-8411-f80ca24f7ae0&modal_id=7568832119439522417&type=general
```

系统会自动转换为：
```
https://www.douyin.com/video/7568832119439522417
```

然后开始下载！

---

## 📋 技术细节

### 已实现的功能

1. **URL 自动转换** ✅
   - 自动识别搜索页面 URL
   - 提取 `modal_id` 参数
   - 转换为标准视频 URL

2. **Cookies 自动导入** ✅
   - 从 Chrome 浏览器自动读取 cookies
   - 无需手动导出 cookies 文件
   - 支持多种浏览器

3. **兼容性保持** ✅
   - 支持所有原有的视频网站
   - 不影响 YouTube、B站等其他平台

### 支持的 URL 格式

| 类型 | URL 示例 | 状态 |
|------|---------|------|
| 搜索页面 | `https://www.douyin.com/root/search/...?modal_id=123` | ✅ 自动转换 |
| 分享链接 | `https://www.douyin.com/...?modal_id=123` | ✅ 自动转换 |
| 标准视频 | `https://www.douyin.com/video/123` | ✅ 直接支持 |
| 短链接 | `https://v.douyin.com/xxx` | ⚠️ 需要浏览器跳转 |

---

## 🔧 配置选项

### 更改浏览器（可选）

如果你不使用 Chrome，可以在 [downloader.py:178](downloader.py#L178) 修改：

```python
# Chrome（默认）
"cookiesfrombrowser": ("chrome",),

# Firefox
"cookiesfrombrowser": ("firefox",),

# Edge
"cookiesfrombrowser": ("edge",),

# Safari
"cookiesfrombrowser": ("safari",),
```

### 使用 Cookies 文件（高级）

如果自动导入失败，可以手动导出 cookies：

1. 安装浏览器扩展：[Get cookies.txt](https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid)
2. 访问 https://www.douyin.com
3. 导出 cookies 为 `douyin_cookies.txt`
4. 修改代码：
   ```python
   "cookiefile": "./douyin_cookies.txt",
   # 注释掉 cookiesfrombrowser
   # "cookiesfrombrowser": ("chrome",),
   ```

---

## 🧪 测试验证

### 测试 URL 转换
```bash
python test_url_preprocessing.py
```

预期输出：
```
================================================================================
URL 预处理测试
================================================================================

测试: 抖音搜索页面 URL（用户提供的）
输入:   https://www.douyin.com/root/search/...?modal_id=7568832119439522417...
期望:   https://www.douyin.com/video/7568832119439522417
输出:   https://www.douyin.com/video/7568832119439522417
结果:   ✓ 通过

================================================================================
所有测试通过！ ✓
================================================================================
```

### 测试完整下载流程
```python
# 在 Python 中测试
from downloader import _preprocess_url

url = "你的搜索页面 URL"
processed = _preprocess_url(url)
print(f"转换后: {processed}")
```

---

## ❓ 常见问题

### Q: 为什么需要在浏览器中访问抖音？
**A:** 抖音使用反爬虫机制，需要有效的 session cookies。只需访问一次，无需登录。

### Q: Cookies 会过期吗？
**A:** 会的，通常几小时到几天。使用 `cookiesfrombrowser` 会自动获取最新的 cookies。

### Q: 如果提示 "Fresh cookies needed" 怎么办？
**A:**
1. 确保 Chrome 浏览器已访问过 https://www.douyin.com
2. 关闭 Chrome 后重试（有些浏览器需要关闭才能读取 cookies）
3. 清除浏览器缓存后重新访问抖音

### Q: 支持 TikTok 国际版吗？
**A:** 支持！代码已经包含了 TikTok 的 modal_id 转换逻辑。

### Q: 会影响其他视频网站下载吗？
**A:** 不会！URL 预处理只处理抖音和 TikTok，其他网站直接透传。

---

## 📊 代码修改总结

### 1. downloader.py
- ✅ 添加了 `_preprocess_url()` 函数（第 45-84 行）
- ✅ 在 `start_download()` 中调用预处理（第 102 行）
- ✅ 添加了 `cookiesfrombrowser` 配置（第 178 行）

### 2. 新增文件
- ✅ `test_url_preprocessing.py` - URL 转换测试
- ✅ `DOUYIN_SOLUTION.md` - 详细技术文档
- ✅ `QUICK_START_DOUYIN.md` - 本文档

### 3. 依赖变更
无需额外依赖，使用现有的：
- `yt_dlp` - 已包含抖音支持
- `urllib.parse` - Python 标准库
- `re` - Python 标准库

---

## 🎯 现在就试试！

```bash
# 1. 访问抖音（Chrome）
open -a "Google Chrome" https://www.douyin.com

# 2. 启动应用
python app.py

# 3. 粘贴你的 URL 开始下载！
```

**你的原始 URL 现在可以直接使用了！** 🎉

---

## 📞 获取帮助

如果遇到问题：
1. 查看 [DOUYIN_SOLUTION.md](DOUYIN_SOLUTION.md) 了解技术细节
2. 运行 `python test_url_preprocessing.py` 验证 URL 转换
3. 检查浏览器是否已访问过抖音并保存了 cookies

---

**最后更新：** 2025-12-25
**状态：** ✅ 完全可用
