"""Core downloader implementation."""
import re
import os
import json
import subprocess
import requests
import time
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from pathlib import Path


class BilibiliDownloader:
    """B站视频下载器"""

    def __init__(self, cookie=None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36',
            'Referer': 'https://www.bilibili.com',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        })

        if cookie:
            self.session.headers['Cookie'] = cookie
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
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception:
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
                return None
            j = r.json()
            if j.get('code') != 0:
                return None
            return j
        except Exception:
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

    def download_stream(self, url, filename, backup_urls=None):
        urls_to_try = [url] + (backup_urls or [])

        for attempt, try_url in enumerate(urls_to_try):
            try:
                response = self.session.get(try_url, stream=True, timeout=30)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                with self.progress_lock:
                                    print(f'\r[{os.path.basename(filename)}] {progress:.1f}%', end='', flush=True)

                with self.progress_lock:
                    print(f'\r[{os.path.basename(filename)}] 完成!')
                return True

            except Exception:
                with self.progress_lock:
                    print(f'\r[{os.path.basename(filename)}] 尝试 {attempt+1}/{len(urls_to_try)} 失败')

        return False

    def download_parallel(self, video_info, audio_info, output_dir):
        video_temp = os.path.join(output_dir, f"temp_video_{video_info['id']}.m4s")
        audio_temp = os.path.join(output_dir, f"temp_audio_{audio_info['id']}.m4s")

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_video = executor.submit(
                self.download_stream, video_info['url'], video_temp, video_info.get('backup_urls')
            )
            future_audio = executor.submit(
                self.download_stream, audio_info['url'], audio_temp, audio_info.get('backup_urls')
            )

            results = []
            for future in as_completed([future_video, future_audio]):
                results.append(future.result())

        if all(results):
            return video_temp, audio_temp
        else:
            for f in [video_temp, audio_temp]:
                if os.path.exists(f):
                    os.remove(f)
            return None, None

    def check_ffmpeg(self):
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            return True
        except Exception:
            return False

    def merge_files(self, video_file, audio_file, output_file):
        if not self.check_ffmpeg():
            return False

        cmd = ['ffmpeg', '-i', video_file, '-i', audio_file, '-c', 'copy', '-y', output_file]

        # Capture raw bytes to avoid text-decoding errors on Windows consoles
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            for f in [video_file, audio_file]:
                if os.path.exists(f):
                    os.remove(f)
            return True
        else:
            stderr = None
            try:
                stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''
            except Exception:
                stderr = str(result.stderr)
            print(f"❌ 合并失败: {stderr}")
            return False

    def sanitize_filename(self, filename):
        for char in ['<', '>', ':', '"', '|', '?', '*', '/', '\\', '\n', '\r']:
            filename = filename.replace(char, '_')
        return filename[:80].strip()

    def select_quality(self, videos):
        if not videos:
            return []
        return [videos[0]]

    def download_single_quality(self, video_info, audio_info, output_dir, title, bvid):
        base_name = f"{title}_{video_info['width']}x{video_info['height']}_{bvid}.mp4"
        output_file = os.path.join(output_dir, self.sanitize_filename(base_name))

        if os.path.exists(output_file):
            return True

        video_temp, audio_temp = self.download_parallel(video_info, audio_info, output_dir)

        if not video_temp or not audio_temp:
            return False

        return self.merge_files(video_temp, audio_temp, output_file)

    def download_video(self, url, output_dir='downloads', auto_all=False):
        try:
            normalized_url = self.normalize_url(url)
        except ValueError:
            return False

        info = self.get_video_info(normalized_url)
        if not info or not info['playinfo']:
            return False

        videos, audios = self.parse_streams(info['playinfo'])
        if not videos or not audios:
            return False

        os.makedirs(output_dir, exist_ok=True)

        selected_videos = videos if auto_all else self.select_quality(videos)
        best_audio = audios[0]

        results = []
        for video_info in selected_videos:
            result = self.download_single_quality(video_info, best_audio, output_dir, info['title'], info['bvid'])
            results.append(result)

        success_count = sum(1 for r in results if r)
        return success_count > 0
