#!/usr/bin/env python3
"""
测试从浏览器读取 cookies 的功能
"""

import sys


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

    # 测试读取 Safari cookies（macOS 推荐）
    print("\n" + "-" * 80)
    print("测试读取 Safari 浏览器的 douyin.com cookies...")
    print("-" * 80)

    try:
        from yt_dlp.cookies import extract_cookies_from_browser

        # 尝试读取 Safari 的 douyin.com cookies
        jar = extract_cookies_from_browser('safari', logger=None)

        # 查找 douyin.com 的 cookies
        douyin_cookies = [c for c in jar if 'douyin.com' in c.domain]

        if douyin_cookies:
            print(f"\n✓ 成功读取 Safari cookies！")
            print(f"✓ 找到 {len(douyin_cookies)} 个 douyin.com 相关的 cookies")
            print("\nCookies 列表:")
            for cookie in douyin_cookies:
                print(f"  - {cookie.name}: {cookie.value[:20]}..." if len(cookie.value) > 20 else f"  - {cookie.name}: {cookie.value}")

            # 检查关键的 cookie
            cookie_names = [c.name for c in douyin_cookies]
            if 's_v_web_id' in cookie_names:
                print("\n✓ 找到关键 cookie 's_v_web_id'，应该可以下载抖音视频！")
                return True
            else:
                print("\n⚠️  警告: 没有找到关键 cookie 's_v_web_id'")
                print("   请在 Safari 中访问 https://www.douyin.com 并等待页面完全加载")
                return False
        else:
            print("\n⚠️  警告: 没有找到 douyin.com 的 cookies")
            print("\n请执行以下步骤:")
            print("1. 在 Safari 浏览器中打开: https://www.douyin.com")
            print("   或运行: open -a Safari https://www.douyin.com")
            print("2. 等待页面完全加载（看到视频推荐）")
            print("3. 浏览几个视频")
            print("4. 关闭 Safari 浏览器（可选）")
            print("5. 重新运行此测试")
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
            print("1. Safari 浏览器未访问过 douyin.com")
            print("2. Safari 用户配置文件路径不标准")
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

    print("\n然后修改 downloader.py，将第 178 行的:")
    print('  "cookiesfrombrowser": ("chrome",),')
    print("\n替换为:")
    print('  "cookiefile": "./douyin_cookies.txt",')


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
