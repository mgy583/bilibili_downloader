# bili_downloader

🎬 B站视频智能下载器 - 支持高画质、多种Cookie获取方式、交互式质量选择

## 特性

- 🎯 **智能API回退** - 页面提取失败时自动调用官方API
- 📊 **交互式质量选择** - 支持选择特定画质或下载全部质量
- 🔐 **三种Cookie获取方式** - 浏览器提取/二维码登录/手动输入
- ⚡ **并行下载** - 视频和音频同时下载，提升速度
- 🔄 **备用URL重试** - 主URL失败自动尝试备用链接
- 💾 **自动Cookie保存** - 保存到 `~/.bili_cookie` 下次自动加载
- 🎨 **友好的用户界面** - 详细的进度提示和错误信息

## 安装

```bash
# 安装依赖
pip install -r requirements.txt
```

## 使用方法

### 1. 获取Cookie（三选一）

```bash
# 推荐：二维码登录
python -m bili_downloader --qr-login

# 从浏览器提取（支持Chrome/Edge）
python -m bili_downloader --get-cookie

# 手动指定
python -m bili_downloader --cookie "SESSDATA=你的cookie"
```

### 2. 下载视频

```bash
# 下载视频（交互式选择画质）
python -m bili_downloader BV1xx411c7mD

# 使用完整URL
python -m bili_downloader "https://www.bilibili.com/video/BV1xx411c7mD"

# 下载所有可用画质
python -m bili_downloader BV1xx411c7mD --all

# 指定输出目录
python -m bili_downloader BV1xx411c7mD -o ~/Videos
```

### 3. 查看帮助

```bash
python -m bili_downloader --help
```

## 旧版脚本

也可以使用根目录的独立脚本（功能相同）：

```bash
python downloader.py BV1xx411c7mD
```

## 依赖

- `requests` - HTTP请求
- `qrcode[pil]` - 二维码登录（可选）
- `ffmpeg` - 视频音频合并（需要系统安装）

## 测试

```bash
pip install -r requirements.txt
pytest -q
```

## 中文说明

查看完整中文文档：[README_zh.md](README_zh.md)