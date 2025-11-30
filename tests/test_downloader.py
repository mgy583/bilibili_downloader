import pytest

from bili_downloader.downloader import BilibiliDownloader


def test_sanitize_filename():
    d = BilibiliDownloader()
    name = 'a<>:"|?*\/test\n.txt'
    out = d.sanitize_filename(name)
    assert '<' not in out and '>' not in out and '\n' not in out
    assert len(out) <= 80


def test_normalize_url_bv():
    d = BilibiliDownloader()
    assert d.normalize_url('BV1xx411c7mD').startswith('https://www.bilibili.com/video/')


def test_normalize_url_http():
    d = BilibiliDownloader()
    assert d.normalize_url('https://www.bilibili.com/video/BV1xx411c7mD') == 'https://www.bilibili.com/video/BV1xx411c7mD'
