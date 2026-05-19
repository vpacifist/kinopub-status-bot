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

    def test_slow_response_is_down_even_with_200(self):
        self.assertEqual(
            kinopub_bot.status_from_http_response(
                200,
                b"<html><body>ok</body></html>",
                kinopub_bot.SLOW_RESPONSE_SECONDS + 0.1,
            ),
            kinopub_bot.STATUS_DOWN,
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

    def test_login_redirect_is_down_when_cookie_is_configured(self):
        original_cookie = kinopub_bot.CHECK_COOKIE
        kinopub_bot.CHECK_COOKIE = "PHPSESSID=test"
        try:
            self.assertEqual(
                kinopub_bot.status_from_http_response(
                    302,
                    b"",
                    headers={"Location": "https://kino.pub/user/login"},
                ),
                kinopub_bot.STATUS_DOWN,
            )
        finally:
            kinopub_bot.CHECK_COOKIE = original_cookie


class CheckSiteAndNotifyTest(unittest.TestCase):
    def setUp(self):
        self.original_get_site_status = kinopub_bot.get_site_status
        self.original_save_state = kinopub_bot.save_state
        self.original_notify_subscribers = kinopub_bot.notify_subscribers
        self.saved_states = []
        self.notifications = []

        kinopub_bot.save_state = lambda state: self.saved_states.append(dict(state))
        kinopub_bot.notify_subscribers = (
            lambda state, text: self.notifications.append(text)
        )

    def tearDown(self):
        kinopub_bot.get_site_status = self.original_get_site_status
        kinopub_bot.save_state = self.original_save_state
        kinopub_bot.notify_subscribers = self.original_notify_subscribers

    def test_recovery_requires_consecutive_alive_checks(self):
        raw_statuses = iter(
            [kinopub_bot.STATUS_ALIVE] * kinopub_bot.RECOVERY_CONFIRMATION_CHECKS
        )
        kinopub_bot.get_site_status = lambda: next(raw_statuses)
        state = {"status": kinopub_bot.STATUS_DOWN, "alive_checks": 0, "subscribers": [1]}

        for _ in range(kinopub_bot.RECOVERY_CONFIRMATION_CHECKS - 1):
            kinopub_bot.check_site_and_notify(state)
            self.assertEqual(state["status"], kinopub_bot.STATUS_DOWN)
            self.assertEqual(self.notifications, [])

        kinopub_bot.check_site_and_notify(state)

        self.assertEqual(state["status"], kinopub_bot.STATUS_ALIVE)
        self.assertEqual(self.notifications, ["kinopub is alive"])


if __name__ == "__main__":
    unittest.main()
