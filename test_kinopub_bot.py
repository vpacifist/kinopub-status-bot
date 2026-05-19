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


class StatusFromHttpResponseTest(unittest.TestCase):
    def test_internal_server_error_body_is_down_even_with_200(self):
        body = b"<html><body>An internal server error occurred.</body></html>"

        self.assertEqual(
            kinopub_bot.status_from_http_response(200, body),
            kinopub_bot.STATUS_DOWN,
        )

    def test_normal_200_body_is_alive(self):
        self.assertEqual(
            kinopub_bot.status_from_http_response(200, b"<html><body>ok</body></html>"),
            kinopub_bot.STATUS_ALIVE,
        )

    def test_redirect_without_error_body_is_alive(self):
        self.assertEqual(
            kinopub_bot.status_from_http_response(302, b"<html><body>redirect</body></html>"),
            kinopub_bot.STATUS_ALIVE,
        )

    def test_redirect_with_internal_server_error_body_is_down(self):
        self.assertEqual(
            kinopub_bot.status_from_http_response(302, b"An internal server error occurred."),
            kinopub_bot.STATUS_DOWN,
        )


if __name__ == "__main__":
    unittest.main()
