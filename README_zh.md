# bili_downloader（中文说明）

一个命令行 B 站视频下载器。

本文档已经按当前代码实现同步整理，内容与 `README.md` 保持一致。

## 当前功能

当前代码实际提供这些能力：

- 支持传入 `BV` 号、`av` 号或完整视频链接
- 自动解析普通视频、合集、多 P 内容
- 交互式选择要下载的分 P
- 交互式选择清晰度，或用 `--all` 直接使用最高可用清晰度
- 视频流和音频流并行下载，再调用 `ffmpeg` 合并为 `mp4`
- 支持命令行 Cookie、浏览器提取 Cookie、二维码登录获取 Cookie
- 自动读取和保存 `~/.bili_cookie`
- 保留旧入口 `script/downloader.py`

## 环境要求

- Python 3
- `ffmpeg` 与 `ffprobe` 需要在系统 `PATH` 中可用

可先检查是否已安装：

```bash
ffmpeg -version
ffprobe -version
```

## 安装

安装依赖：

```bash
pip install -r requirements.txt
```

当前 `requirements.txt` 包含：

- `requests`
- `qrcode`
- `pytest`

其中：

- 二维码登录依赖 `qrcode`
- 运行测试依赖 `pytest`

## 运行方式

推荐使用模块入口：

```bash
python -m bili_downloader --help
```

也可以继续使用兼容脚本：

```bash
python script/downloader.py --help
```

## 命令格式

```bash
python -m bili_downloader [选项] <BV号/av号/视频URL>
```

当前可用选项：

- `-o, --output-dir`：输出目录，默认 `downloads`
- `--cookie`：手动传入 Cookie
- `--get-cookie`：从本机浏览器提取 `SESSDATA`
- `--qr-login`：通过二维码登录获取 Cookie
- `--all`：下载所选视频中的最高可用清晰度，不进入清晰度选择

## 获取 Cookie

程序支持 3 种方式获取 Cookie。

### 1. 手动传入

```bash
python -m bili_downloader --cookie "SESSDATA=你的Cookie" BV1xx411c7mD
```

### 2. 从浏览器提取

当前代码内置对这些浏览器默认 Cookie 路径的读取：

- Chrome
- Edge

执行：

```bash
python -m bili_downloader --get-cookie
```

提取成功后会保存到：

```bash
~/.bili_cookie
```

### 3. 二维码登录

```bash
python -m bili_downloader --qr-login
```

登录成功后同样会保存到：

```bash
~/.bili_cookie
```

## 下载示例

### 下载单个视频

```bash
python -m bili_downloader BV1xx411c7mD
```

### 使用完整链接

```bash
python -m bili_downloader "https://www.bilibili.com/video/BV1xx411c7mD"
```

### 使用 `av` 号

```bash
python -m bili_downloader av170001
```

### 指定输出目录

```bash
python -m bili_downloader BV1xx411c7mD -o ~/Videos
```

### 先登录，再下载

```bash
python -m bili_downloader --qr-login
python -m bili_downloader BV1xx411c7mD
```

### 使用兼容脚本入口

```bash
python script/downloader.py BV1xx411c7mD
```

## 实际下载流程

运行下载命令后，程序会按当前代码逻辑执行：

1. 规范化输入内容，转换为标准视频 URL
2. 请求视频页面并提取标题、BV 号、分 P / 合集信息
3. 如果检测到多 P 或合集，交互式选择要下载的条目
4. 调用 `playurl` 接口获取 DASH 视频流和音频流
5. 若未指定 `--all`，交互式选择一个清晰度
6. 对每个选中的条目：
   - 下载对应视频流
   - 下载最佳音频流
   - 使用 `ffmpeg` 合并为 `mp4`

## 输出文件

默认输出目录：

```bash
downloads
```

文件名大致格式为：

```text
{标题}_P{分页号}_{分P标题}_{分辨率}_{BV号}.mp4
```

程序会自动替换文件名中的非法字符。

## 关于画质和 Cookie

如果没有有效 Cookie，程序通常仍可工作，但可能只能拿到较低清晰度。

当前实现中：

- 优先使用命令行传入的 `--cookie`
- 如果没有传入，则尝试读取 `~/.bili_cookie`
- 若两者都没有，就以未登录状态请求

某些高清或会员清晰度依赖登录态，甚至依赖账号权限。

## 兼容性说明

### 浏览器 Cookie 提取

当前代码针对不同系统写了浏览器默认路径，其中 Linux、macOS、Windows 都有路径映射，但实际是否可读取成功仍取决于：

- 浏览器是否安装
- 是否已登录 B 站
- Cookie 数据库是否未被锁定
- 系统环境是否允许直接读取

### 二维码登录

二维码登录需要安装 `qrcode`。程序会在终端中打印 ASCII 二维码，并轮询登录状态。

## 测试

运行测试：

```bash
pytest -q
```

当前仓库中的测试主要覆盖：

- 文件名清洗
- BV 号规范化
- URL 规范化

## 项目结构

```text
bili_downloader/
├── bili_downloader/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── cookie.py
│   └── downloader.py
├── script/
│   └── downloader.py
├── tests/
│   └── test_downloader.py
├── requirements.txt
├── README.md
└── README_zh.md
```

## 已知实现特征

这是根据当前代码整理出的说明，不额外扩展未实现功能。需要注意：

- 下载逻辑目前使用 DASH 视频流 + 音频流，再通过 `ffmpeg` 合并
- 清晰度选择是交互式的；`--all` 的当前行为是直接选择最高可用清晰度，并不是把所有清晰度都各下载一遍
- 多 P / 合集选择支持输入单个序号、范围和逗号分隔多选
- 旧脚本 `script/downloader.py` 只是一个兼容包装层，实际逻辑在包 `bili_downloader` 中
