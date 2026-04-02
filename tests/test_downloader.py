import unittest
from bili_downloader.downloader import BilibiliDownloader

class TestDownloader(unittest.TestCase):
    def setUp(self):
        self.d = BilibiliDownloader()

    def test_sanitize_filename(self):
        name = 'a<>:"|?*/test\n.txt'
        out = self.d.sanitize_filename(name)
        self.assertNotIn('<', out)
        self.assertNotIn('>', out)
        self.assertNotIn('\n', out)
        self.assertLessEqual(len(out), 80)

    def test_normalize_url_bv(self):
        result = self.d.normalize_url('BV1xx411c7mD')
        self.assertTrue(result.startswith('https://www.bilibili.com/video/'))

    def test_normalize_url_http(self):
        url = 'https://www.bilibili.com/video/BV1xx411c7mD'
        self.assertEqual(self.d.normalize_url(url), url)

if __name__ == '__main__':
    unittest.main()
