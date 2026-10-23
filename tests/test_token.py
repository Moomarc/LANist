import json
import os
import tempfile
import unittest

from lanist.config import TOKEN_RE, Config, new_token, valid_token


class TokenTest(unittest.TestCase):
    def test_format_is_memorable(self):
        for _ in range(200):
            token = new_token()
            self.assertRegex(token, TOKEN_RE)
            self.assertTrue(valid_token(token))
            self.assertLessEqual(len(token), 12)

    def test_two_word_token_still_valid(self):
        self.assertTrue(valid_token("amber-otter-42"))
        self.assertTrue(valid_token("fox-42"))
        self.assertFalse(valid_token("a"))
        self.assertFalse(valid_token("中文"))

    def test_old_generated_token_rotates_once(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"token": "amber-otter-42"}, f)
            token = Config(path).ensure_token()
            self.assertRegex(token, TOKEN_RE)
            self.assertNotEqual(token, "amber-otter-42")
            self.assertEqual(Config(path).ensure_token(), token)

    def test_token_persists(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "config.json")
            first = Config(path).ensure_token()
            second = Config(path).ensure_token()
            self.assertEqual(first, second)

    def test_reset_changes_token(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "config.json")
            cfg = Config(path)
            old = cfg.ensure_token()
            new = cfg.reset_token()
            self.assertNotEqual(old, new)
            self.assertEqual(Config(path).ensure_token(), new)

    def test_custom_token_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg = Config(os.path.join(folder, "config.json"))
            cfg.set_token("my-lan_2026")
            self.assertEqual(cfg.ensure_token(), "my-lan_2026")
            for bad in ("", "a", "../x", "a/b", "中文", "x" * 65):
                with self.assertRaises(ValueError):
                    cfg.set_token(bad)


if __name__ == "__main__":
    unittest.main()
