#!/usr/bin/env python3
"""
测试从浏览器读取 cookies 的功能
"""

import sys


class _NoopLogger:
    def debug(self, msg, *args, **kwargs):
        return None

    def info(self, msg, *args, **kwargs):
        return None

    def warning(self, msg, *args, **kwargs):
        return None

    def error(self, msg, *args, **kwargs):
        return None


def _test_single_browser(browser_name: str) -> tuple[bool, str]:
    """测试单个浏览器是否可读取到抖音关键 cookies"""
    from yt_dlp.cookies import extract_cookies_from_browser

    try:
        jar = extract_cookies_from_browser(browser_name, logger=_NoopLogger())
        douyin_cookies = [c for c in jar if 'douyin.com' in c.domain]
        if not douyin_cookies:
            return False, "未读取到 douyin.com cookies"

        cookie_names = [c.name for c in douyin_cookies]
        if 's_v_web_id' in cookie_names:
            return True, f"可用（{len(douyin_cookies)} 个 douyin cookies，含 s_v_web_id）"
        return False, f"读到 {len(douyin_cookies)} 个 cookies，但缺少 s_v_web_id"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def test_browser_cookies():
    """测试从不同浏览器读取 cookies"""
    print("=" * 80)
    print("浏览器 Cookies 读取测试")
    print("=" * 80)

    # 测试 yt_dlp 读取 cookies
    try:
        import yt_dlp
        from yt_dlp.cookies import SUPPORTED_BROWSERS

        print("\n✓ yt_dlp 已安装")
        print(f"✓ 支持的浏览器: {', '.join(SUPPORTED_BROWSERS)}")

    except ImportError as e:
        print(f"\n✗ yt_dlp 未安装: {e}")
        return False

    # 测试多个浏览器，优先推荐首个可用项
    print("\n" + "-" * 80)
    print("测试读取浏览器的 douyin.com cookies...")
    print("-" * 80)

    try:
        from yt_dlp.cookies import SUPPORTED_BROWSERS

        preferred_order = ["safari", "chrome", "firefox", "edge", "brave"]
        candidates = [b for b in preferred_order if b in SUPPORTED_BROWSERS]
        results: list[tuple[str, bool, str]] = []

        for browser in candidates:
            ok, detail = _test_single_browser(browser)
            results.append((browser, ok, detail))
            icon = "✓" if ok else "✗"
            print(f"{icon} {browser}: {detail}")

        available = [item for item in results if item[1]]
        if available:
            best_browser = available[0][0]
            print(f"\n✓ 推荐使用浏览器来源: {best_browser}")
            print("在应用高级选项中设置:")
            print(f'  cookies_from_browser = "{best_browser}"')
            print("  cookie_file = 空")
            return True

        print("\n⚠️  所有浏览器来源均不可用，建议改用 cookie_file 方式")
        return False

    except Exception as e:
        print(f"\n✗ 读取 cookies 失败: {e}")
        print(f"错误类型: {type(e).__name__}")

        # 提供详细的错误诊断
        if "database is locked" in str(e).lower():
            print("\n原因: Safari 浏览器正在运行，数据库被锁定")
            print("解决方案: 请完全关闭 Safari 浏览器后重试")
        elif "permission" in str(e).lower() or "access" in str(e).lower():
            print("\n原因: 权限问题")
            print("解决方案: 在 macOS 系统偏好设置中允许终端访问")
        else:
            print("\n可能的原因:")
            print("1. 浏览器未访问过 douyin.com")
            print("2. 浏览器用户配置文件路径不标准")
            print("3. macOS 系统权限限制")
            print("\n建议: 使用手动导出 cookies 的方式（见下方备用方案）")

        return False


def test_manual_cookies():
    """测试手动 cookies 文件"""
    print("\n" + "=" * 80)
    print("备用方案: 手动导出 Cookies")
    print("=" * 80)

    print("\n如果自动读取失败，可以手动导出 cookies:")
    print("\n方法 1: 使用浏览器扩展")
    print("  1. 安装 Chrome 扩展: 'Get cookies.txt'")
    print("     https://chrome.google.com/webstore/detail/bgaddhkoddajcdgocldbbfleckgcbcid")
    print("  2. 访问 https://www.douyin.com")
    print("  3. 点击扩展图标，导出 cookies")
    print("  4. 保存为 'douyin_cookies.txt'")

    print("\n方法 2: 使用开发者工具")
    print("  1. 在 Chrome 中打开 https://www.douyin.com")
    print("  2. 按 F12 打开开发者工具")
    print("  3. 切换到 Application 标签")
    print("  4. 左侧选择 Cookies > https://www.douyin.com")
    print("  5. 复制所有 cookies")

    print("\n然后在应用高级选项中设置:")
    print('  cookie_file = "./douyin_cookies.txt"')
    print('  cookies_from_browser = 空')
    print("\n你也可以先用命令行验证:")
    print('  yt-dlp --cookies ./douyin_cookies.txt "https://www.douyin.com/video/<id>"')


if __name__ == "__main__":
    print("\n")
    success = test_browser_cookies()

    if not success:
        test_manual_cookies()

    print("\n" + "=" * 80)
    if success:
        print("✓ Cookies 配置正确，可以开始下载抖音视频！")
    else:
        print("⚠️  需要配置 cookies 后才能下载抖音视频")
    print("=" * 80)
    print("\n")

    sys.exit(0 if success else 1)
