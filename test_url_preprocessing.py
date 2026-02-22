#!/usr/bin/env python3
"""
测试 URL 预处理功能
"""

import sys
from urllib.parse import urlparse, parse_qs
import re


def _preprocess_url(url: str) -> str:
    """
    预处理 URL，转换为 yt-dlp 支持的格式
    """
    # 检查是否是抖音 URL
    if 'douyin.com' in url:
        # 解析 URL
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        # 检查是否有 modal_id 参数
        if 'modal_id' in query_params:
            modal_id = query_params['modal_id'][0]
            # 构造标准的抖音视频 URL
            return f'https://www.douyin.com/video/{modal_id}'

        # 检查是否已经是标准格式
        video_match = re.match(r'https?://(?:www\.)?douyin\.com/video/(\d+)', url)
        if video_match:
            return url

    # TikTok 类似处理
    if 'tiktok.com' in url and 'modal_id' in url:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if 'modal_id' in query_params:
            modal_id = query_params['modal_id'][0]
            return f'https://www.tiktok.com/video/{modal_id}'

    # 其他 URL 直接返回
    return url


def test_url_preprocessing():
    """测试各种 URL 格式"""
    test_cases = [
        {
            "name": "抖音搜索页面 URL（用户提供的）",
            "input": "https://www.douyin.com/root/search/%E4%B8%80%E4%BA%8C%E7%86%8A%E7%86%8A%E8%AF%AD?aid=47a3ba5a-a114-4379-8411-f80ca24f7ae0&modal_id=7568832119439522417&type=general",
            "expected": "https://www.douyin.com/video/7568832119439522417"
        },
        {
            "name": "标准抖音视频 URL",
            "input": "https://www.douyin.com/video/6961737553342991651",
            "expected": "https://www.douyin.com/video/6961737553342991651"
        },
        {
            "name": "YouTube URL（不处理）",
            "input": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "expected": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        },
        {
            "name": "抖音分享链接（假设）",
            "input": "https://www.douyin.com/share/video/?modal_id=1234567890",
            "expected": "https://www.douyin.com/video/1234567890"
        }
    ]

    print("=" * 80)
    print("URL 预处理测试")
    print("=" * 80)

    all_passed = True
    for test in test_cases:
        result = _preprocess_url(test["input"])
        passed = result == test["expected"]
        all_passed = all_passed and passed

        print(f"\n测试: {test['name']}")
        print(f"输入:   {test['input']}")
        print(f"期望:   {test['expected']}")
        print(f"输出:   {result}")
        print(f"结果:   {'✓ 通过' if passed else '✗ 失败'}")

    print("\n" + "=" * 80)
    if all_passed:
        print("所有测试通过！ ✓")
    else:
        print("部分测试失败！ ✗")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = test_url_preprocessing()
    sys.exit(0 if success else 1)
