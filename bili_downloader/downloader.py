"""Core downloader implementation."""

import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import requests
from requests.adapters import HTTPAdapter


class BilibiliDownloader:
    """B站视频下载器"""

    DEFAULT_REFERER = "https://www.bilibili.com"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36"
    )

    def __init__(self, cookie=None):
        self.session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=10,  # 连接池大小
            pool_maxsize=10,  # 最大保持连接数
            max_retries=0,  # 处理重试次数
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.session.headers.update(
            {
                "User-Agent": self.USER_AGENT,
                "Referer": self.DEFAULT_REFERER,
                "Accept": "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Connection": "keep-alive",
            }
        )

        if cookie:
            self.session.headers["Cookie"] = cookie
            print("✅ Cookie已设置")
        else:
            print("⚠️  未设置Cookie，可能只能下载低画质")

        self.progress_lock = Lock()

    # -----------------------------
    # 基础解析能力
    # -----------------------------
    def normalize_url(self, input_str):
        """URL标准化"""
        input_str = input_str.strip()
        if input_str.startswith("http"):
            if "m.bilibili.com" in input_str:
                match = re.search(r"/video/([^/?]+)", input_str)
                if match:
                    return f"https://www.bilibili.com/video/{match.group(1)}"
            return input_str

        if re.match(r"^BV[a-zA-Z0-9]{10}$", input_str):
            return f"https://www.bilibili.com/video/{input_str}"

        if re.match(r"^av\d+$", input_str):
            return f"https://www.bilibili.com/video/{input_str}"

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
        pattern = r"window\.__playinfo__\s*=\s*({.*?})\s*;\s*</script>"
        match = re.search(pattern, html, re.DOTALL)
        return json.loads(match.group(1)) if match else None

    def extract_initial_state(self, html):
        pattern = r"window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;\s*\(function"
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except Exception:
            return None

    def _extract_title(self, html):
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL)
        title_raw = title_match.group(1).strip() if title_match else "video"
        return re.sub(r"_哔哩哔哩.*", "", title_raw).strip()

    def _extract_bvid_from_url(self, url):
        bv_match = re.search(r"/video/(BV[a-zA-Z0-9]+)", url)
        return bv_match.group(1) if bv_match else "unknown"

    def _episode_to_playlist_item(self, episode):
        return {
            "bvid": episode.get("bvid"),
            "cid": episode.get("cid"),
            "page": episode.get("title"),
            "part": episode.get("title"),
        }

    def _build_playlist(self, initial_state, fallback_bvid):
        playlist = []

        sections = initial_state.get("sectionsInfo")
        if isinstance(sections, dict):
            section_iter = sections.values()
        elif isinstance(sections, list):
            section_iter = sections
        else:
            section_iter = []

        for sec in section_iter:
            if not isinstance(sec, dict):
                continue
            for ep in sec.get("episodes", []):
                if isinstance(ep, dict):
                    playlist.append(self._episode_to_playlist_item(ep))

        if not playlist:
            ugc = initial_state.get("ugc_season")
            if ugc:
                for sec in ugc.get("sections", []):
                    for ep in sec.get("episodes", []):
                        playlist.append(self._episode_to_playlist_item(ep))

        if not playlist:
            video_data = initial_state.get("videoData", {})
            pages = video_data.get("pages")
            if isinstance(pages, list) and pages:
                for p in pages:
                    playlist.append(
                        {
                            "bvid": fallback_bvid,
                            "cid": p.get("cid"),
                            "page": p.get("page"),
                            "part": p.get("part", ""),
                        }
                    )

        if not playlist:
            cid = initial_state.get("videoData", {}).get("cid")
            if cid:
                playlist.append(
                    {
                        "bvid": fallback_bvid,
                        "cid": cid,
                        "page": 1,
                        "part": "P1",
                    }
                )
        return playlist

    # -----------------------------
    # API 和元数据
    # -----------------------------
    def call_playurl_api(self, bvid, cid):
        params = {"bvid": bvid, "cid": cid, "fnval": 4048, "fourk": 1, "qn": 120}
        headers = {
            "User-Agent": self.session.headers.get("User-Agent"),
            "Referer": f"https://www.bilibili.com/video/{bvid}",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.bilibili.com",
            "Cookie": self.session.headers.get("Cookie", ""),
        }
        try:
            r = self.session.get(
                "https://api.bilibili.com/x/player/playurl",
                params=params,
                headers=headers,
                timeout=20,
            )
            if r.status_code != 200:
                print(f"⚠️ playurl API状态码: {r.status_code}")
                return None
            j = r.json()
            if j.get("code") != 0:
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

        title = self._extract_title(html)
        bvid = self._extract_bvid_from_url(url)

        print(f"\n📹 视频: {title}")
        print(f"🔖 BV号: {bvid}")

        initial = self.extract_initial_state(html)
        if not initial:
            return {"title": title, "bvid": bvid, "playlist": []}

        playlist = self._build_playlist(initial, bvid)
        return {"title": title, "bvid": bvid, "playlist": playlist}

    # -----------------------------
    # 流解析
    # -----------------------------
    def parse_streams(self, playinfo):
        if not playinfo:
            return None, None

        data = playinfo.get("data") or playinfo
        if not data:
            return None, None

        dash = data.get("dash", {})
        videos = []
        for video in dash.get("video", []):
            videos.append(
                {
                    "id": video.get("id"),
                    "url": video.get("baseUrl")
                    or video.get("base_url")
                    or video.get("backupUrl", [None])[0],
                    "backup_urls": video.get("backupUrl", []),
                    "bandwidth": video.get("bandwidth", 0),
                    "width": video.get("width", 0),
                    "height": video.get("height", 0),
                    "codecs": video.get("codecs", ""),
                }
            )

        audios = []
        for audio in dash.get("audio", []):
            audios.append(
                {
                    "id": audio.get("id"),
                    "url": audio.get("baseUrl")
                    or audio.get("base_url")
                    or audio.get("backupUrl", [None])[0],
                    "backup_urls": audio.get("backupUrl", []),
                    "bandwidth": audio.get("bandwidth", 0),
                }
            )

        videos = [v for v in videos if v["url"]]
        audios = [a for a in audios if a["url"]]
        videos.sort(
            key=lambda x: (
                x["width"] * x["height"],
                x["height"],
                x["width"],
                x["bandwidth"],
            ),
            reverse=True,
        )
        audios.sort(key=lambda x: x["bandwidth"], reverse=True)
        return videos, audios

    # -----------------------------
    # 下载核心
    # -----------------------------
    def _build_url_candidates(self, primary_url, backup_urls=None):
        urls = [primary_url] + (backup_urls or [])
        urls = [u for u in urls if u]
        seen = set()
        deduped = []
        for u in urls:
            if u not in seen:
                deduped.append(u)
                seen.add(u)
        return deduped

    def download_stream(self, url, filename, backup_urls=None, connections=2, position=0):
        # B站CDN对Range分块和多源混用的兼容性并不稳定，
        # 为避免生成损坏的m4s，这里统一走单连接顺序下载。
        return self.download_single(url, filename, backup_urls)

    def download_single(self, url, filename, backup_urls=None):
        urls_to_try = self._build_url_candidates(url, backup_urls)

        for attempt, try_url in enumerate(urls_to_try):
            try:
                response = self.session.get(
                    try_url,
                    stream=True,
                    timeout=30,
                    headers={"Referer": self.DEFAULT_REFERER},
                )
                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                last_pct = -1

                with open(filename, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            if total_size > 0:
                                current_pct = int(downloaded / total_size * 100)
                                if current_pct != last_pct:
                                    last_pct = current_pct
                                    with self.progress_lock:
                                        print(
                                            f"\r[{os.path.basename(filename)}] {current_pct}%",
                                            end="",
                                            flush=True,
                                        )

                if downloaded == 0 or (total_size > 0 and downloaded < total_size):
                    raise IOError("下载不完整")

                with self.progress_lock:
                    print(f'\r[{os.path.basename(filename)}] 完成!{" "*20}')
                return True
            except Exception:
                if os.path.exists(filename):
                    os.remove(filename)
                with self.progress_lock:
                    print(
                        f'\r[{os.path.basename(filename)}] 尝试 {attempt+1}/{len(urls_to_try)} 失败{" "*20}'
                    )

        return False

    # -----------------------------
    # 合并与输出
    # -----------------------------
    def download_parallel(self, video_info, audio_info, output_dir):
        video_temp = os.path.join(output_dir, f"temp_video_{video_info['id']}.m4s")
        audio_temp = os.path.join(output_dir, f"temp_audio_{audio_info['id']}.m4s")

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_video = executor.submit(
                self.download_stream,
                video_info["url"],
                video_temp,
                video_info.get("backup_urls"),
                1,
                1,
            )
            future_audio = executor.submit(
                self.download_stream,
                audio_info["url"],
                audio_temp,
                audio_info.get("backup_urls"),
                1,
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
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            return True
        except Exception:
            print("❌ 未找到ffmpeg")
            return False

    def validate_media_file(self, file_path):
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return False

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_name",
                    "-of",
                    "csv=p=0",
                    file_path,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return True

            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=codec_name",
                    "-of",
                    "csv=p=0",
                    file_path,
                ],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except Exception:
            return True

    def merge_files(self, video_file, audio_file, output_file):
        if not self.check_ffmpeg():
            return False

        if not self.validate_media_file(video_file):
            print(f"❌ 视频文件损坏: {os.path.basename(video_file)}")
            return False

        if not self.validate_media_file(audio_file):
            print(f"❌ 音频文件损坏: {os.path.basename(audio_file)}")
            return False

        cmd = [
            "ffmpeg",
            "-i",
            video_file,
            "-i",
            audio_file,
            "-c",
            "copy",
            "-y",
            output_file,
        ]
        print(f"\n🎬 合并: {os.path.basename(output_file)}")

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            print("✅ 合并成功!")
            for f in [video_file, audio_file]:
                if os.path.exists(f):
                    os.remove(f)
            return True

        try:
            stderr = result.stderr.decode("utf-8", errors="ignore")
        except Exception:
            stderr = str(result.stderr)
        print(f"❌ 合并失败: {stderr}")
        return False

    def sanitize_filename(self, filename):
        for char in ["<", ">", ":", '"', "|", "?", "*", "/", "\\", "\n", "\r"]:
            filename = filename.replace(char, "_")
        return filename[:80].strip()

    # -----------------------------
    # 质量选择与下载编排
    # -----------------------------
    def _format_playlist_label(self, item, index):
        page = item.get("page") or index
        part = (item.get("part") or f"P{page}").strip()
        return f"P{page}: {part}"

    def select_playlist_items(self, playlist):
        if not playlist:
            return []

        if len(playlist) == 1:
            return playlist

        print("\n" + "=" * 70)
        print("  检测到合集/多P视频")
        print("=" * 70)
        for i, item in enumerate(playlist, 1):
            print(f"{i:2d}. {self._format_playlist_label(item, i)}")

        print("\n选项: 回车(全部) / all(全部) / 数字 / 范围(如 1-3) / 多选(如 1,3,5)")
        while True:
            choice = input("\n请选择要下载的条目: ").strip().lower()
            if choice in ("", "all"):
                return playlist

            selected_indices = []
            try:
                parts = [part.strip() for part in choice.split(",") if part.strip()]
                for part in parts:
                    if "-" in part:
                        start_str, end_str = part.split("-", 1)
                        start = int(start_str)
                        end = int(end_str)
                        if start > end:
                            start, end = end, start
                        selected_indices.extend(range(start, end + 1))
                    else:
                        selected_indices.append(int(part))
            except ValueError:
                print("❌ 无效输入，请输入数字、范围或逗号分隔的序号")
                continue

            unique_indices = []
            seen = set()
            for idx in selected_indices:
                if 1 <= idx <= len(playlist) and idx not in seen:
                    unique_indices.append(idx)
                    seen.add(idx)

            if not unique_indices:
                print(f"❌ 请输入 1-{len(playlist)} 范围内的序号")
                continue

            return [playlist[idx - 1] for idx in unique_indices]

    def select_quality(self, videos):
        """质量选择"""
        if not videos:
            print("❌ 无可用视频流")
            return []

        max_res = max(v["width"] for v in videos)
        if max_res < 1280:
            print("\n⚠️  警告：当前只能获取低画质！")
            print("    原因：未提供有效Cookie或需要大会员")

        print("\n" + "=" * 70)
        print("  可用视频质量")
        print("=" * 70)

        codec_map = {"avc1": "H.264", "hev1": "HEVC", "av01": "AV1"}
        for i, v in enumerate(videos, 1):
            codec = v["codecs"].split(".")[0] if v["codecs"] else ""
            codec_name = codec_map.get(codec, codec or "unknown")
            print(
                f"{i:2d}. {v['width']:4d}x{v['height']:4d} | "
                f"码率: {v['bandwidth']/1024:.0f}KB/s | 编码: {codec_name}"
            )

        print("\n选项: 数字/回车(最高)")
        while True:
            choice = input("\n请选择清晰度: ").strip().lower()

            if choice == "":
                return videos[0]

            try:
                index = int(choice) - 1
                if 0 <= index < len(videos):
                    return videos[index]
                print(f"❌ 请输入 1-{len(videos)}")
            except ValueError:
                print("❌ 无效输入")

    def match_quality(self, videos, target):
        for v in videos:
            if (
                v["width"] == target["width"]
                and v["height"] == target["height"]
                and v.get("codecs", "") == target.get("codecs", "")
                and v.get("bandwidth", 0) == target.get("bandwidth", 0)
            ):
                return v

        for v in videos:
            if v["width"] == target["width"] and v["height"] == target["height"]:
                return v
        return videos[0]

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

    def download_video(self, url, output_dir="downloads", auto_all=False):
        print("=" * 70)
        print("B站视频下载")
        print("=" * 70)

        try:
            normalized_url = self.normalize_url(url)
            print(f"解析: {url} → {normalized_url}")
        except ValueError as e:
            print(f"❌ {e}")
            return False

        info = self.get_video_info(normalized_url)
        if not info or not info["playlist"]:
            print("❌ 获取视频信息失败")
            return False

        os.makedirs(output_dir, exist_ok=True)

        selected_items = self.select_playlist_items(info["playlist"])
        if not selected_items:
            print("❌ 未选择要下载的条目")
            return False

        first_item = selected_items[0]
        first_playinfo = self.call_playurl_api(first_item["bvid"], first_item["cid"])
        if not first_playinfo or first_playinfo.get("code") != 0:
            print("❌ 获取视频流失败")
            return False

        first_videos, first_audios = self.parse_streams(first_playinfo)
        if not first_videos or not first_audios:
            print("❌ 无可用音视频流")
            return False

        if auto_all:
            selected_quality = first_videos[0]
        else:
            selected_quality = self.select_quality(first_videos)
            if not selected_quality:
                return False

        results = []
        total_count = len(selected_items)

        for index, item in enumerate(selected_items, 1):
            cid = item["cid"]
            part_title = item.get("part") or f"P{item.get('page', index)}"
            page = item.get("page") or index

            print(f"\n[{index}/{total_count}] 📦 下载 {self._format_playlist_label(item, index)}")

            if index == 1:
                videos, audios = first_videos, first_audios
            else:
                playinfo = self.call_playurl_api(item["bvid"], cid)
                if not playinfo or playinfo.get("code") != 0:
                    print("❌ 获取流失败")
                    results.append(False)
                    continue

                videos, audios = self.parse_streams(playinfo)
                if not videos or not audios:
                    print("❌ 无流")
                    results.append(False)
                    continue

            video_info = self.match_quality(videos, selected_quality)
            best_audio = audios[0]
            title = f"{info['title']}_P{page}_{part_title}"

            result = self.download_single_quality(
                video_info,
                best_audio,
                output_dir,
                title,
                item["bvid"],
            )
            results.append(result)

        success_count = sum(results)

        print("\n" + "=" * 70)
        print(f"完成: {success_count}/{total_count} 成功")
        print(f"路径: {os.path.abspath(output_dir)}")
        print("=" * 70)

        return success_count > 0

