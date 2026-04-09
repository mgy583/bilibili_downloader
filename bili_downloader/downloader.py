"""Core downloader implementation."""
import re
import os
import json
import subprocess
import requests
import random
import time
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Thread


class BilibiliDownloader:
    """B站视频下载器"""

    def __init__(self, cookie=None):
        self.session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=10,   # 连接池大小
            pool_maxsize=10,       # 最大保持连接数
            max_retries=0          # 处理重试次数
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36',
            'Referer': 'https://www.bilibili.com',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
        })

        if cookie:
            self.session.headers['Cookie'] = cookie
            print("✅ Cookie已设置")
        else:
            print("⚠️  未设置Cookie，可能只能下载低画质")
        
        self.progress_lock = Lock()

    def normalize_url(self, input_str):
        """URL标准化"""
        input_str = input_str.strip()
        if input_str.startswith('http'):
            if 'm.bilibili.com' in input_str:
                match = re.search(r'/video/([^/?]+)', input_str)
                if match:
                    return f'https://www.bilibili.com/video/{match.group(1)}'
            return input_str

        if re.match(r'^BV[a-zA-Z0-9]{10}$', input_str):
            return f'https://www.bilibili.com/video/{input_str}'

        if re.match(r'^av\d+$', input_str):
            return f'https://www.bilibili.com/video/{input_str}'

        raise ValueError(f"无效格式: {input_str}")

    def get_video_page(self, url):
        """获取视频页面"""
        try:
            print(f"请求: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return None

    def extract_playinfo(self, html):
        pattern = r'window\.__playinfo__\s*=\s*({.*?})\s*;\s*</script>'
        match = re.search(pattern, html, re.DOTALL)
        return json.loads(match.group(1)) if match else None

    def extract_initial_state(self, html):
        pattern = r'window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;\s*\(function'
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
            return data
        except Exception:
            return None

    def call_playurl_api(self, bvid, cid):
        params = {
            'bvid': bvid,
            'cid': cid,
            'fnval': 4048,
            'fourk': 1,
            'qn': 120
        }
        headers = {
            'User-Agent': self.session.headers.get('User-Agent'),
            'Referer': f'https://www.bilibili.com/video/{bvid}',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://www.bilibili.com',
            'Cookie': self.session.headers.get('Cookie', '')
        }
        try:
            r = self.session.get('https://api.bilibili.com/x/player/playurl', params=params, headers=headers, timeout=20)
            if r.status_code != 200:
                print(f"⚠️ playurl API状态码: {r.status_code}")
                return None
            j = r.json()
            if j.get('code') != 0:
                print(f"⚠️ playurl API错误: code={j.get('code')} message={j.get('message')}")
                return None
            return j
        except Exception as e:
            print(f"⚠️ playurl API异常: {e}")
            return None

    def get_video_info(self, url):
        html = self.get_video_page(url)
        if not html:
            return None

        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL)
        title_raw = title_match.group(1).strip() if title_match else 'video'
        title = re.sub(r'_哔哩哔哩.*', '', title_raw).strip()

        bv_match = re.search(r'/video/(BV[a-zA-Z0-9]+)', url)
        bvid = bv_match.group(1) if bv_match else 'unknown'
        
        print(f"\n📹 视频: {title}")
        print(f"🔖 BV号: {bvid}")

        playinfo = self.extract_playinfo(html)
        initial = self.extract_initial_state(html)
        cid = None

        if initial:
            try:
                cid = initial['videoData']['cid']
            except Exception:
                try:
                    pages = initial.get('videoData', {}).get('pages', [])
                    if pages:
                        cid = pages[0].get('cid')
                except Exception:
                    pass

        api_playinfo = None
        if not playinfo and cid and bvid != 'unknown':
            api_playinfo = self.call_playurl_api(bvid, cid)

        final_playinfo = api_playinfo if api_playinfo else playinfo
        return {
            'title': title,
            'bvid': bvid,
            'cid': cid,
            'playinfo': final_playinfo
        }

    def parse_streams(self, playinfo):
        if not playinfo:
            return None, None

        data = playinfo.get('data') if 'data' in playinfo else playinfo.get('data', playinfo)
        if not data:
            return None, None

        dash = data.get('dash', {})

        videos = []
        for video in dash.get('video', []):
            videos.append({
                'id': video.get('id'),
                'url': video.get('baseUrl') or video.get('base_url') or video.get('backupUrl', [None])[0],
                'backup_urls': video.get('backupUrl', []),
                'bandwidth': video.get('bandwidth', 0),
                'width': video.get('width', 0),
                'height': video.get('height', 0),
                'codecs': video.get('codecs', '')
            })

        audios = []
        for audio in dash.get('audio', []):
            audios.append({
                'id': audio.get('id'),
                'url': audio.get('baseUrl') or audio.get('base_url') or audio.get('backupUrl', [None])[0],
                'backup_urls': audio.get('backupUrl', []),
                'bandwidth': audio.get('bandwidth', 0)
            })

        videos = [v for v in videos if v['url']]
        audios = [a for a in audios if a['url']]

        videos.sort(key=lambda x: x['bandwidth'], reverse=True)
        audios.sort(key=lambda x: x['bandwidth'], reverse=True)
        return videos, audios

    def download_stream(self, url, filename, backup_urls=None, connections=2, position=0):
        urls_to_try = [url] + (backup_urls or [])
        random.shuffle(urls_to_try)

        total_size = 0
        for try_url in urls_to_try:
            try:
                head = self.session.head(
                    try_url,
                    timeout=10,
                    headers={'Referer': 'https://www.bilibili.com'}
                )
                total_size = int(head.headers.get('content-length', 0))
                if total_size > 0:
                    break
            except:
                continue

        if total_size == 0 or connections <= 1:
            return self.download_single(url, filename, backup_urls)

        def measure_speed(test_url):
            try:
                headers = {'Range': 'bytes=0-524288'}  # 1MB
                r = self.session.get(test_url, headers=headers, stream=True, timeout=10)

                start = time.time()
                size = 0

                for chunk in r.iter_content(262144):
                    size += len(chunk)
                    if size >= 1024 * 1024:
                        break

                duration = time.time() - start
                return size / duration if duration > 0 else 0
            except:
                return 0

        url_speeds = []
        for u in urls_to_try:
            speed = measure_speed(u)
            if speed > 20 * 1024:  # 过滤极慢源（20KB/s）
                url_speeds.append((u, speed))

        if not url_speeds:
            url_speeds = [(u, 1) for u in urls_to_try]  # fallback

        # 按速度排序
        url_speeds.sort(key=lambda x: x[1], reverse=True)
        url_speeds = url_speeds[:2]

        total_speed = sum(s for _, s in url_speeds)

        assigned_urls = []
        for i in range(connections):
            r = i / connections
            acc = 0
            for u, s in url_speeds:
                acc += s / total_speed
                if r <= acc:
                    assigned_urls.append(u)
                    break

        chunk_size = total_size // connections
        ranges = [
            (i * chunk_size,
            (i + 1) * chunk_size - 1 if i < connections - 1 else total_size - 1)
            for i in range(connections)
        ]

        temp_files = [f"{filename}.part{i}" for i in range(connections)]
        success_flags = [False] * connections

        pbar = tqdm(
            total=total_size,
            desc=os.path.basename(filename),
            unit='B',
            unit_scale=True,
            position=position,
            leave=False,
            dynamic_ncols=True
        )

        lock = Lock()

        def download_part(idx, start, end):
            primary_url = assigned_urls[idx]

            headers = {
                'Range': f'bytes={start}-{end}',
                'Referer': 'https://www.bilibili.com'
            }

            # 优先主URL
            try:
                r = self.session.get(primary_url, headers=headers, stream=True, timeout=30)
                if r.status_code in (200, 206):
                    with open(temp_files[idx], 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
                                with lock:
                                    pbar.update(len(chunk))
                    success_flags[idx] = True
                    return
            except:
                pass

            # fallback
            for try_url in urls_to_try:
                if try_url == primary_url:
                    continue
                try:
                    r = self.session.get(try_url, headers=headers, stream=True, timeout=30)
                    if r.status_code in (200, 206):
                        with open(temp_files[idx], 'wb') as f:
                            for chunk in r.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                                    with lock:
                                        pbar.update(len(chunk))
                        success_flags[idx] = True
                        return
                except:
                    continue

        threads = []
        for i, (s, e) in enumerate(ranges):
            t = Thread(target=download_part, args=(i, s, e))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        pbar.close()

        if not all(success_flags):
            for f in temp_files:
                if os.path.exists(f):
                    os.remove(f)
            return False

        try:
            with open(filename, 'wb') as outfile:
                for temp in temp_files:
                    with open(temp, 'rb') as infile:
                        outfile.write(infile.read())
                    os.remove(temp)
            return True
        except:
            return False            
        
    def download_single(self, url, filename, backup_urls=None):
        urls_to_try = [url] + (backup_urls or [])
        
        for attempt, try_url in enumerate(urls_to_try):
            try:
                response = self.session.get(
                    try_url, 
                    stream=True, 
                    timeout=30,
                    headers={'Referer': 'https://www.bilibili.com'}
                )
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                last_pct = -1

                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if total_size > 0:
                                current_pct = int(downloaded / total_size * 100)
                                if current_pct != last_pct:
                                    last_pct = current_pct
                                    with self.progress_lock:
                                        print(f'\r[{os.path.basename(filename)}] {current_pct}%', end='', flush=True)

                with self.progress_lock:
                    print(f'\r[{os.path.basename(filename)}] 完成!{" "*20}')
                return True

            except Exception:
                with self.progress_lock:
                    print(f'\r[{os.path.basename(filename)}] 尝试 {attempt+1}/{len(urls_to_try)} 失败{" "*20}')

            return False

    def download_parallel(self, video_info, audio_info, output_dir):
        video_temp = os.path.join(output_dir, f"temp_video_{video_info['id']}.m4s")
        audio_temp = os.path.join(output_dir, f"temp_audio_{audio_info['id']}.m4s")

        with ThreadPoolExecutor(max_workers=2) as executor:
            # 视频用4连接（大文件），音频用2连接（小文件）
            future_video = executor.submit(
                self.download_stream,
                video_info['url'],
                video_temp,
                video_info.get('backup_urls'),
                4,  # 视频多连接
                1
            )
            future_audio = executor.submit(
                self.download_stream,
                audio_info['url'],
                audio_temp,
                audio_info.get('backup_urls'),
                2,  # 音频少连接
                0
            )

            video_ok = future_video.result()
            audio_ok = future_audio.result()

        if video_ok and audio_ok:
            return video_temp, audio_temp

        for f in [video_temp, audio_temp]:
            if os.path.exists(f):
                os.remove(f)
        return None, None

    def check_ffmpeg(self):
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            return True
        except Exception:
            print("❌ 未找到ffmpeg")
            return False

    def merge_files(self, video_file, audio_file, output_file):
        if not self.check_ffmpeg():
            return False

        cmd = ['ffmpeg', '-i', video_file, '-i', audio_file, '-c', 'copy', '-y', output_file]
        print(f"\n🎬 合并: {os.path.basename(output_file)}")
        
        # 使用 PIPE 但不解码，避免 Windows 下的编码问题
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            print("✅ 合并成功!")
            for f in [video_file, audio_file]:
                if os.path.exists(f):
                    os.remove(f)
            return True
        else:
            # 尝试解码错误信息，失败则显示原始字节
            try:
                stderr = result.stderr.decode('utf-8', errors='ignore')
            except Exception:
                stderr = str(result.stderr)
            print(f"❌ 合并失败: {stderr}")
            return False

    def sanitize_filename(self, filename):
        for char in ['<', '>', ':', '"', '|', '?', '*', '/', '\\', '\n', '\r']:
            filename = filename.replace(char, '_')
        return filename[:80].strip()

    def select_quality(self, videos):
        """质量选择"""
        if not videos:
            print("❌ 无可用视频流")
            return []
        
        max_res = max(v['width'] for v in videos)
        if max_res < 1280:
            print("\n⚠️  警告：当前只能获取低画质！")
            print("    原因：未提供有效Cookie或需要大会员")
        
        print("\n" + "="*70)
        print("  可用视频质量")
        print("="*70)
        
        codec_map = {'avc1': 'H.264', 'hev1': 'HEVC', 'av01': 'AV1'}
        
        for i, v in enumerate(videos, 1):
            codec = v['codecs'].split('.')[0] if v['codecs'] else ''
            codec_name = codec_map.get(codec, codec or 'unknown')
            print(f"{i:2d}. {v['width']:4d}x{v['height']:4d} | "
                  f"码率: {v['bandwidth']/1024:.0f}KB/s | 编码: {codec_name}")
        
        print("\n选项: 数字/回车(最高)/all(全部)")
        
        while True:
            choice = input("\n请选择: ").strip().lower()
            
            if choice == '':
                return [videos[0]]
            
            if choice == 'all':
                return videos
            
            try:
                index = int(choice) - 1
                if 0 <= index < len(videos):
                    return [videos[index]]
                else:
                    print(f"❌ 请输入 1-{len(videos)}")
            except ValueError:
                print("❌ 无效输入")

    def download_single_quality(self, video_info, audio_info, output_dir, title, bvid):
        base_name = f"{title}_{video_info['width']}x{video_info['height']}_{bvid}.mp4"
        output_file = os.path.join(output_dir, self.sanitize_filename(base_name))

        if os.path.exists(output_file):
            print(f"\n⏭️  已存在: {os.path.basename(output_file)}")
            return True
        
        print(f"\n🎯 正在下载: {video_info['width']}x{video_info['height']}")

        video_temp, audio_temp = self.download_parallel(video_info, audio_info, output_dir)

        if not video_temp or not audio_temp:
            return False

        return self.merge_files(video_temp, audio_temp, output_file)

    def download_video(self, url, output_dir='downloads', auto_all=False):
        """主流程"""
        print("="*70)
        print("B站视频智能下载器")
        print("="*70)
        
        try:
            normalized_url = self.normalize_url(url)
            print(f"解析: {url} → {normalized_url}")
        except ValueError as e:
            print(f"❌ {e}")
            return False
        
        info = self.get_video_info(normalized_url)
        if not info or not info['playinfo']:
            print("\n❌ 无法获取视频数据")
            print("提示：请确认SESSDATA有效，或尝试使用二维码登录刷新Cookie。")
            return False
        
        videos, audios = self.parse_streams(info['playinfo'])
        if not videos or not audios:
            print("\n❌ 未解析到视频/音频流")
            return False
        
        os.makedirs(output_dir, exist_ok=True)
        
        selected_videos = self.select_quality(videos) if not auto_all else videos
        
        best_audio = audios[0]
        
        results = []
        for video_info in selected_videos:
            result = self.download_single_quality(video_info, best_audio, output_dir, info['title'], info['bvid'])
            results.append(result)
        
        success_count = sum(results)
        total_count = len(selected_videos)
        
        print("\n" + "="*70)
        print(f"完成: {success_count}/{total_count} 成功")
        print(f"路径: {os.path.abspath(output_dir)}")
        print("="*70)
        
        return success_count > 0
