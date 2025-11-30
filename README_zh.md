# bili_downloader（中文说明）

这是对原始 `script/downloader.py` 的轻量重构，将功能拆分为包 `bili_downloader`、命令行入口与基础测试。

快速开始

1. 在项目目录下创建并激活虚拟环境（推荐）:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. 安装依赖：

```powershell
pip install -r requirements.txt
```

运行方式（二选一）：

- 使用原始脚本（向后兼容）:

```powershell
python script/downloader.py <BV号或视频URL>
```

- 或直接使用包的 CLI:

```powershell
python -m bili_downloader.cli <args>
```

常用选项

- `--cookie "SESSDATA=xx"`：直接传入 Cookie（优先）。
- `--get-cookie`：尝试从浏览器 Cookie DB 提取 `SESSDATA` 并保存到用户主目录下的 `.bili_cookie`。
- `--qr-login`：通过二维码登录获取 Cookie（需要 `qrcode` 库）。
- `-o, --output-dir`：指定下载目录（默认 `downloads`）。
- `--all`：下载所有可用清晰度（默认只下载最高或所选质量）。

关于 Cookie

- 程序会先使用命令行传入的 `--cookie`，若未指定则尝试读取用户主目录下的 `.bili_cookie` 文件。

关于 ffmpeg

- 合并音视频需要 `ffmpeg` 在系统 PATH 可用。可用以下命令检查：

```powershell
ffmpeg -version
```

- Windows 上可使用 Chocolatey：

```powershell
choco install ffmpeg -y
```

测试

- 已包含一个轻量测试脚本：

```powershell
python run_local_tests.py
```

- 或安装并使用 `pytest`：

```powershell
pip install pytest
pytest -q
```

日志与调试

- 合并（ffmpeg）过程会捕获并以安全方式打印 stderr（避免因控制台编码导致崩溃）。

常见问题

- 如果运行 `python script/downloader.py` 报 `ModuleNotFoundError: No module named 'bili_downloader'`，请在项目根目录执行命令，或将包安装到环境（`pip install -e .`）后再运行。

想要我继续做的事（可选）:
- 为项目创建 `pyproject.toml` 并添加 `console_scripts` 入口；
- 将包移动到 `src/` 目录以符合打包最佳实践；
- 添加更多测试并用 mocking 覆盖网络调用。

如果需要我现在实现其中任意一项，请告诉我你要哪个选项。
