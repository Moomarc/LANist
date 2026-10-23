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
