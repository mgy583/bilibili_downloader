"""Command-line interface for the bili_downloader package."""
import argparse
import sys
from pathlib import Path

from .cookie import CookieHelper
from .downloader import BilibiliDownloader


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='B站视频下载器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用方法:
  # 获取Cookie（三选一）
  --qr-login           # 二维码登录
  --get-cookie         # 从浏览器提取
  --cookie "SESSDATA=xx"  # 手动输入

下载视频:
  BV1xx411c7mD
  "https://www.bilibili.com/video/BV1xx411c7mD"
''')

    parser.add_argument('input', nargs='?', help='BV号/视频URL')
    parser.add_argument('-o', '--output-dir', default='downloads', help='输出目录')
    parser.add_argument('--cookie', help='手动指定Cookie')
    parser.add_argument('--get-cookie', action='store_true', help='从浏览器提取Cookie')
    parser.add_argument('--qr-login', action='store_true', help='二维码登录')
    parser.add_argument('--all', action='store_true', help='下载所有质量')
    args = parser.parse_args(argv)

    if args.get_cookie:
        cookie = CookieHelper.from_browser()
        if cookie:
            config_path = Path.home() / '.bili_cookie'
            with open(config_path, 'w') as f:
                f.write(cookie)
            print(f"✅ Cookie已保存: {config_path}")
        sys.exit(0)

    if args.qr_login:
        cookie = CookieHelper.from_qr()
        if cookie:
            config_path = Path.home() / '.bili_cookie'
            with open(config_path, 'w') as f:
                f.write(cookie)
            print(f"✅ Cookie已保存: {config_path}")
        sys.exit(0)

    if not args.input:
        print("❌ 错误: 必须提供视频URL或BV号")
        parser.print_help()
        sys.exit(1)

    cookie = args.cookie
    config_path = Path.home() / '.bili_cookie'
    if not cookie and config_path.exists():
        try:
            with open(config_path, 'r') as f:
                cookie = f.read().strip()
            print("✅ 已加载配置文件中的Cookie")
        except Exception:
            print("⚠️  读取配置文件失败")

    downloader = BilibiliDownloader(cookie)
    success = downloader.download_video(args.input, args.output_dir, auto_all=args.all)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
