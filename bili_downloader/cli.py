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
  # 1. 获取Cookie（三选一）
  python -m bili_downloader --qr-login           # 推荐：二维码登录
  python -m bili_downloader --get-cookie         # 从浏览器提取
  python -m bili_downloader --cookie "SESSDATA=xx"  # 手动输入
  
  # 2. 下载视频
  python -m bili_downloader BV1xx411c7mD
  python -m bili_downloader "https://www.bilibili.com/video/BV1xx411c7mD"
  python -m bili_downloader BV1xx411c7mD -o ~/Videos --all
''')

    parser.add_argument('input', nargs='?', help='BV号/视频URL')
    parser.add_argument('-o', '--output-dir', default='downloads', help='输出目录')
    parser.add_argument('--cookie', help='手动指定Cookie')
    parser.add_argument('--get-cookie', action='store_true', help='从浏览器提取Cookie')
    parser.add_argument('--qr-login', action='store_true', help='二维码登录')
    parser.add_argument('--all', action='store_true', help='下载所有质量')
    args = parser.parse_args(argv)

    # Cookie获取模式
    if args.get_cookie:
        print("\n" + "="*60)
        print("Cookie提取模式")
        print("="*60)
        cookie = CookieHelper.from_browser()
        if cookie:
            config_path = Path.home() / '.bili_cookie'
            with open(config_path, 'w') as f:
                f.write(cookie)
            print(f"\n✅ Cookie已保存: {config_path}")
        sys.exit(0)

    if args.qr_login:
        print("\n" + "="*60)
        print("二维码登录模式")
        print("="*60)
        try:
            cookie = CookieHelper.from_qr()
            if cookie:
                config_path = Path.home() / '.bili_cookie'
                with open(config_path, 'w') as f:
                    f.write(cookie)
                print(f"\n✅ Cookie已保存: {config_path}")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ 二维码登录失败: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    # 下载模式
    if not args.input:
        print("❌ 错误: 必须提供视频URL或BV号")
        print("运行: python -m bili_downloader --help 查看帮助")
        sys.exit(1)

    # 加载Cookie优先级：命令行 > 配置文件 > 无
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
