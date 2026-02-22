# 🍪 抖音视频下载 Cookies 配置指南

## 问题说明

下载抖音视频时遇到错误：
```
ERROR: [Douyin] Fresh cookies (not necessarily logged in) are needed
```

这是抖音的反爬虫机制，需要有效的浏览器 cookies。

---

## ✅ 推荐方案：使用 Safari（最简单）

### 步骤 1：在 Safari 中访问抖音

```bash
# 自动在 Safari 中打开抖音
open -a Safari https://www.douyin.com
```

或者手动：
1. 打开 Safari 浏览器
2. 访问 `https://www.douyin.com`
3. 等待页面完全加载（看到视频推荐）
4. 随便浏览几个视频
5. 关闭 Safari

### 步骤 2：测试 cookies

```bash
python test_cookies.py
```

### 步骤 3：开始下载

```bash
python app.py
```

现在可以直接粘贴你的 URL 下载了！

---

## 🔧 备用方案 B：手动导出 Cookies

如果 Safari 也不行，使用手动方式：

### 方法 1：使用在线工具（最快）

1. **在 Safari 中访问抖音**
   - 打开 https://www.douyin.com
   - 等待页面加载完成

2. **获取 cookies**
   - 按 `⌘ + ⌥ + I` 打开开发者工具
   - 点击 "存储" 标签
   - 选择 "Cookies" > "https://www.douyin.com"
   - 找到 `s_v_web_id` 这个 cookie
   - 复制它的值

3. **创建 cookies 文件**

创建文件 `douyin_cookies.txt`，内容如下：

```
# Netscape HTTP Cookie File
.douyin.com	TRUE	/	FALSE	0	s_v_web_id	你复制的值
```

### 方法 2：使用浏览器扩展

1. **安装扩展**
   - Chrome: [Get cookies.txt](https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid)
   - Firefox: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

2. **导出 cookies**
   - 访问 https://www.douyin.com
   - 点击扩展图标
   - 选择 "Export" 或"导出"
   - 保存为 `douyin_cookies.txt`

3. **修改代码**

编辑 [downloader.py:179](downloader.py#L179)，修改为：

```python
# 注释掉浏览器导入
# "cookiesfrombrowser": ("safari",),

# 使用 cookies 文件
"cookiefile": "./douyin_cookies.txt",
```

---

## 🧪 测试和验证

### 测试 cookies 是否有效

```bash
python -c "
import yt_dlp

url = 'https://www.douyin.com/video/7568832119439522417'
opts = {
    'quiet': False,
    'cookiesfrombrowser': ('safari',),
}

with yt_dlp.YoutubeDL(opts) as ydl:
    try:
        info = ydl.extract_info(url, download=False)
        print(f'✓ 成功! 视频标题: {info.get(\"title\")}')
    except Exception as e:
        print(f'✗ 失败: {e}')
"
```

---

## 📝 常见问题

### Q1: 为什么 Chrome 不能用？
**A:** 在某些情况下，yt_dlp 无法正确读取 Chrome 的 cookies 数据库。Safari 在 macOS 上更可靠。

### Q2: 必须要关闭浏览器吗？
**A:** 不一定。但如果遇到"数据库被锁定"错误，需要关闭浏览器。

### Q3: cookies 会过期吗？
**A:** 会的，通常几小时到几天后过期。过期后重新访问抖音即可。

### Q4: 需要登录抖音账号吗？
**A:** **不需要**！只需要访问 douyin.com，浏览器会自动获取必要的 session cookies。

### Q5: 可以用 Firefox 吗？
**A:** 可以！修改 [downloader.py:179](downloader.py#L179) 为：
```python
"cookiesfrombrowser": ("firefox",),
```

---

## 🎯 快速诊断

运行诊断脚本：
```bash
python test_cookies.py
```

这会告诉你：
- ✓ 哪些浏览器可用
- ✓ 是否成功读取到 cookies
- ✓ 是否找到关键的 `s_v_web_id` cookie
- ⚠️ 如果失败，会给出具体原因和解决方案

---

## 🚀 完整流程（从零开始）

```bash
# 1. 在 Safari 中访问抖音
open -a Safari https://www.douyin.com
# 等待页面加载，浏览几个视频，然后关闭

# 2. 测试 cookies
python test_cookies.py

# 3. 如果测试通过，启动应用
python app.py

# 4. 在 Web 界面粘贴你的 URL
# https://www.douyin.com/root/search/...?modal_id=7568832119439522417
```

---

## 📊 当前配置

- **浏览器：** Safari（[downloader.py:179](downloader.py#L179)）
- **URL 转换：** 自动（[downloader.py:43-82](downloader.py#L43-L82)）
- **Cookies 方式：** 自动从浏览器读取

---

**更新日期：** 2025-12-25
**状态：** 已配置使用 Safari 浏览器
