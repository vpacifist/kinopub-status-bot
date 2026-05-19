import unittest

import kinopub_bot


class StatusFromHttpCodeTest(unittest.TestCase):
    def test_404_is_down(self):
        self.assertEqual(kinopub_bot.status_from_http_code(404), kinopub_bot.STATUS_DOWN)

    def test_5xx_is_down(self):
        for code in (500, 502, 503, 504, 599):
            with self.subTest(code=code):
                self.assertEqual(kinopub_bot.status_from_http_code(code), kinopub_bot.STATUS_DOWN)

    def test_other_http_codes_are_alive(self):
        for code in (200, 301, 302, 401, 403, 429):
            with self.subTest(code=code):
                self.assertEqual(kinopub_bot.status_from_http_code(code), kinopub_bot.STATUS_ALIVE)


if __name__ == "__main__":
    unittest.main()
