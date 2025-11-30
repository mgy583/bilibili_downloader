"""Cookie helper utilities extracted from original script."""
from pathlib import Path
import shutil
import sys
import re
import time
import requests


class CookieHelper:
    """Cookie获取助手"""

    @staticmethod
    def from_browser():
        """从浏览器自动提取Cookie"""
        try:
            import sqlite3
        except ImportError:
            return None

        paths = {
            'Chrome': {
                'win32': r'AppData\Local\Google\Chrome\User Data\Default\Network\Cookies',
                'darwin': 'Library/Application Support/Google/Chrome/Default/Cookies',
                'linux': '.config/google-chrome/Default/Cookies'
            },
            'Edge': {
                'win32': r'AppData\Local\Microsoft\Edge\User Data\Default\Network\Cookies',
                'darwin': 'Library/Application Support/Microsoft Edge/Default/Cookies',
                'linux': '.config/microsoft-edge/Default/Cookies'
            }
        }

        home = Path.home()
        cookie = None

        for browser, platform_paths in paths.items():
            db_path = home / platform_paths.get(sys.platform, '')

            if not db_path.exists():
                parent = db_path.parent.parent
                if parent.exists():
                    for profile in parent.glob('*/Network/Cookies'):
                        if profile.exists():
                            db_path = profile
                            break

            if not db_path.exists():
                continue

            try:
                temp_db = Path('temp_bili_cookie.db')
                if temp_db.exists():
                    temp_db.unlink()
                shutil.copy2(db_path, temp_db)

                import sqlite3
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT value FROM cookies 
                    WHERE host_key='.bilibili.com' AND name='SESSDATA' LIMIT 1
                """)
                result = cursor.fetchone()
                conn.close()
                temp_db.unlink()

                if result and result[0]:
                    cookie = f"SESSDATA={result[0]}"
                    break
                else:
                    continue

            except Exception:
                if 'temp_db' in locals() and temp_db.exists():
                    temp_db.unlink()
                continue

        return cookie

    @staticmethod
    def from_qr():
        """二维码登录（在需要时使用）。

        返回: cookie 字符串或 None
        """
        try:
            import qrcode
        except ImportError:
            return None

        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://passport.bilibili.com/login',
            'Origin': 'https://passport.bilibili.com'
        }

        for attempt in range(3):
            try:
                response = requests.get(
                    'https://passport.bilibili.com/x/passport-login/web/qrcode/generate',
                    headers=headers,
                    timeout=10
                )
                if response.status_code == 200:
                    resp_json = response.json()
                    if resp_json.get('code') == 0:
                        data = resp_json['data']
                        break
            except Exception:
                time.sleep(1)
        else:
            return None

        try:
            qr = qrcode.QRCode(version=1, box_size=1, border=1)
            qr.add_data(data['url'])
            qr.print_ascii(invert=True)
        except Exception:
            pass

        check_url = 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll'
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://passport.bilibili.com/login'
        }

        start_time = time.time()
        while True:
            if time.time() - start_time > 180:
                return None
            try:
                response = requests.get(
                    check_url,
                    params={'qrcode_key': data['qrcode_key']},
                    headers=headers,
                    timeout=10
                )
                if response.status_code != 200:
                    time.sleep(2)
                    continue
                result = response.json()
                if result.get('code') == 0:
                    login_data = result.get('data', {})
                    if login_data.get('code') == 0:
                        cookies = response.cookies.get_dict()
                        if 'SESSDATA' in cookies:
                            return f"SESSDATA={cookies['SESSDATA']}"
                        set_cookie = response.headers.get('set-cookie', '')
                        sess_match = re.search(r'SESSDATA=([^;]+)', set_cookie)
                        if sess_match:
                            return f"SESSDATA={sess_match.group(1)}"
                        return None
                time.sleep(2)
            except Exception:
                time.sleep(2)
