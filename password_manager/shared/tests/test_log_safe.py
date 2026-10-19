import logging

from django.test import SimpleTestCase

from shared.log_safe import log_safe

BACKSLASH = chr(92)
CR, LF = chr(13), chr(10)


class LogSafeTests(SimpleTestCase):
    def test_line_breaks_are_escaped_not_dropped(self):
        self.assertEqual(
            log_safe("alice" + CR + LF + "INFO forged"),
            "alice" + BACKSLASH + "r" + BACKSLASH + "n" + "INFO forged",
        )
        self.assertEqual(log_safe("a" + LF + "b"), "a" + BACKSLASH + "nb")

    def test_unicode_line_boundaries_are_escaped(self):
        for code in (0x2028, 0x2029, 0x85, 0x0B, 0x0C, 0x1C, 0x1D, 0x1E):
            escaped = log_safe("a" + chr(code) + "b")
            self.assertNotIn(chr(code), escaped)
            self.assertTrue(escaped.startswith("a" + BACKSLASH))
            self.assertEqual(len(escaped.splitlines()), 1)

    def test_non_strings_and_plain_text_pass_through(self):
        self.assertEqual(log_safe(42), "42")
        self.assertEqual(log_safe(None), "None")
        self.assertEqual(log_safe("plain user@example.com"), "plain user@example.com")

    def test_a_logged_value_cannot_start_a_new_record(self):
        with self.assertLogs("log_safe_test", level="INFO") as cm:
            logging.getLogger("log_safe_test").info(
                "login for %s", log_safe("bob" + LF + "CRITICAL root: admin password reset")
            )
        self.assertEqual(len(cm.output), 1)
        self.assertEqual(len(cm.output[0].splitlines()), 1)
