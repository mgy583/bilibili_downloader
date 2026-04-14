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
        print("\n" + "="*60)
        print("从Cookie浏览器提取B站")
        print("="*60)
        
        try:
            import sqlite3
        except ImportError:
            print("❌ 需要sqlite3支持")
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
            
            print(f"✅ 找到 {browser}: {db_path}")

            temp_db = Path('temp_bili_cookie.db')
            try:
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
                    print(f"✅ 提取成功!")
                    break
                else:
                    print(f"❌ {browser} 中未登录B站")
                    continue

            except Exception as e:
                print(f"❌ 读取失败: {e}")
                if 'temp_db' in locals() and temp_db.exists():
                    temp_db.unlink()
                continue

        return cookie

    @staticmethod
    def from_qr():
        """二维码登录"""
        print("\n" + "="*60)
        print("二维码登录获取Cookie")
        print("="*60)
        
        # 检查依赖
        try:
            import qrcode
        except ImportError:
            print("❌ 需要qrcode库: pip install qrcode[pil]")
            return None

        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://passport.bilibili.com/login',
            'Origin': 'https://passport.bilibili.com'
        }

        for attempt in range(3):
            try:
                print(f"正在获取二维码... (尝试 {attempt+1}/3)")
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
                    else:
                        print(f"⚠️  API返回错误: {resp_json.get('message')}")
                        time.sleep(2)
                        continue
                else:
                    print(f"⚠️  HTTP状态码: {response.status_code}")
                    time.sleep(2)
                    continue
                    
            except requests.exceptions.Timeout:
                print("⚠️  请求超时，重试中...")
                time.sleep(2)
                continue
            except Exception as e:
                print(f"⚠️  请求异常: {e}")
                time.sleep(2)
                continue
        else:
            print("❌ 多次尝试后仍无法获取二维码")
            return None

        # 显示二维码
        try:
            qr = qrcode.QRCode(version=1, box_size=1, border=1)
            qr.add_data(data['url'])
            qr.print_ascii(invert=True)
        except Exception as e:
            print(f"❌ 显示二维码失败: {e}")
            print(f"请手动访问: {data['url']}")
        
        print("\n请使用B站APP扫描上方的二维码")
        print("或访问: " + data['url'])
        print("等待登录...")

        check_url = 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll'
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://passport.bilibili.com/login'
        }

        start_time = time.time()
        while True:
            if time.time() - start_time > 180:
                print("❌ 登录超时（3分钟）")
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
                        print("✅ 登录成功!")
                        cookies = response.cookies.get_dict()
                        if 'SESSDATA' in cookies:
                            return f"SESSDATA={cookies['SESSDATA']}"
                        set_cookie = response.headers.get('set-cookie', '')
                        sess_match = re.search(r'SESSDATA=([^;]+)', set_cookie)
                        if sess_match:
                            return f"SESSDATA={sess_match.group(1)}"
                        print("❌ 未找到SESSDATA Cookie")
                        return None
                    elif login_data.get('code') == 86038:
                        print("❌ 二维码已过期")
                        return None
                    elif login_data.get('code') == 86090:
                        print("⏳ 二维码已扫描，等待确认...")
                    elif login_data.get('code') == 86101:
                        print("⏳ 等待扫描二维码...")
                
                time.sleep(2)
                
            except requests.exceptions.Timeout:
                print("⚠️  检查超时，重试中...")
            except Exception as e:
                print(f"⚠️  检查异常: {e}")
                time.sleep(2)
