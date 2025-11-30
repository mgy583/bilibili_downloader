# bili_downloader

A small refactor of the original `script/downloader.py` into a package-style project.

Usage
- Run the original script wrapper:

```
python script/downloader.py <BV号 or URL>
```

- Or use the package CLI directly:

```
python -m bili_downloader.cli <args>
```

Cookie handling
- Use `--get-cookie` to attempt extracting SESSDATA from local browser cookie DB (requires sqlite3)
- Use `--qr-login` to perform QR login (requires `qrcode`)

Testing

Install dev deps and run tests:

```powershell
pip install -r requirements.txt
pytest -q
```
