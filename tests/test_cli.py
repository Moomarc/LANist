import os
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.request


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _python():
    return sys.executable


class CliTest(unittest.TestCase):
    def test_version(self):
        out = subprocess.check_output(
            [_python(), "-m", "lanist", "--version"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        ).strip()
        self.assertEqual(out, "LANist 3.0.0")

    def test_invalid_token_exits(self):
        result = subprocess.run(
            [_python(), "-m", "lanist", "--token", "../bad"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--token", result.stderr)

    def test_headless_serves_and_stops(self):
        with tempfile.TemporaryDirectory() as share, tempfile.TemporaryDirectory() as cfg:
            env = os.environ.copy()
            env["APPDATA"] = cfg
            env["XDG_CONFIG_HOME"] = cfg
            proc = subprocess.Popen(
                [
                    _python(),
                    "-m",
                    "lanist",
                    "--no-gui",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "0",
                    "--token",
                    "test-token-42",
                    "--share",
                    share,
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
            try:
                url = None
                for _ in range(40):
                    line = proc.stdout.readline()
                    if not line:
                        break
                    match = re.search(r"http://127\.0\.0\.1:\d+/test-token-42/", line)
                    if match:
                        url = match.group(0)
                        break
                self.assertIsNotNone(url, "headless mode did not print a URL")
                with urllib.request.urlopen(url, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn("共享目录还是空的", response.read().decode("utf-8"))
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                proc.stdout.close()


if __name__ == "__main__":
    unittest.main()
