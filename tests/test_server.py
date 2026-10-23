import concurrent.futures
import http.client
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from urllib.parse import quote

from lanist import server as srv


BOUNDARY = "----lanist-test-boundary"


def write_file(path, data):
    with open(path, "wb") as f:
        f.write(data)


def read_file(path):
    with open(path, "rb") as f:
        return f.read()


def multipart(files):
    chunks = []
    for name, data in files:
        chunks.append(("--{}\r\n".format(BOUNDARY)).encode("utf-8"))
        chunks.append(
            'Content-Disposition: form-data; name="file"; filename="{}"\r\n'.format(
                name
            ).encode("utf-8")
        )
        chunks.append(b"Content-Type: application/octet-stream\r\n\r\n")
        chunks.append(data)
        chunks.append(b"\r\n")
    chunks.append(("--{}--\r\n".format(BOUNDARY)).encode("utf-8"))
    return b"".join(chunks)


class ServerTest(unittest.TestCase):
    token = "amber-otter-42"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.share = os.path.join(self.tmp.name, "share")
        self.server, self.port = srv.create_server(
            self.share, self.token, host="127.0.0.1", port=0
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            data = response.read()
            headers = {k.lower(): v for k, v in response.getheaders()}
            return response.status, headers, data
        finally:
            conn.close()

    def upload(self, files, token=None):
        body = multipart(files)
        status, headers, data = self.request(
            "POST",
            "/{}/u".format(token or self.token),
            body,
            {
                "Content-Type": "multipart/form-data; boundary=" + BOUNDARY,
                "Content-Length": str(len(body)),
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        return status, headers, data

    def test_listing_and_auth(self):
        status, headers, body = self.request("GET", "/{}/".format(self.token))
        self.assertEqual(status, 200)
        self.assertIn("共享目录还是空的", body.decode("utf-8"))
        self.assertNotIn(self.token.encode(), body)
        self.assertEqual(self.request("GET", "/wrong-token-99/")[0], 404)
        self.assertEqual(self.request("GET", "/")[0], 404)

    def test_trailing_slash_redirect(self):
        status, headers, _ = self.request("GET", "/{}".format(self.token))
        self.assertEqual(status, 301)
        self.assertEqual(headers["location"], "/{}/".format(self.token))

    def test_wrong_token_page_does_not_leak_token(self):
        status, _, body = self.request("GET", "/wrong-token-99/")
        self.assertEqual(status, 404)
        self.assertNotIn(self.token.encode(), body)
        self.assertNotIn(b"<form", body)

    def test_upload_list_download_roundtrip(self):
        status, _, body = self.upload([("中文 文件.txt", "hello 你好".encode("utf-8"))])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["files"], ["中文 文件.txt"])

        status, _, listing = self.request("GET", "/{}/".format(self.token))
        text = listing.decode("utf-8")
        self.assertIn("中文 文件.txt", text)
        self.assertIn("1 个文件", text)

        status, headers, data = self.request(
            "GET", "/{}/d/{}".format(self.token, quote("中文 文件.txt", safe=""))
        )
        self.assertEqual(status, 200)
        self.assertEqual(data, "hello 你好".encode("utf-8"))
        self.assertIn("filename*=UTF-8''", headers["content-disposition"])

    def test_duplicate_names_are_not_overwritten(self):
        status, _, body = self.upload([("dup.txt", b"one"), ("dup.txt", b"two")])
        self.assertEqual(status, 200)
        names = json.loads(body.decode("utf-8"))["files"]
        self.assertEqual(names, ["dup.txt", "dup (1).txt"])
        self.assertEqual(read_file(os.path.join(self.share, "dup.txt")), b"one")
        self.assertEqual(read_file(os.path.join(self.share, "dup (1).txt")), b"two")

    def test_upload_filename_traversal_is_flattened(self):
        status, _, body = self.upload([("../evil.txt", b"evil")])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["files"], ["evil.txt"])
        self.assertTrue(os.path.isfile(os.path.join(self.share, "evil.txt")))
        self.assertFalse(os.path.isfile(os.path.join(self.share, "..", "evil.txt")))

    def test_listing_escapes_html_in_filename(self):
        name = "a&b'c.txt"
        status, _, _ = self.upload([(name, b"x")])
        self.assertEqual(status, 200)
        status, _, body = self.request("GET", "/{}/".format(self.token))
        text = body.decode("utf-8")
        self.assertIn("a&amp;b&#x27;c.txt", text)
        self.assertNotIn("a&b'c.txt", text)

    def test_download_traversal_rejected(self):
        outside = os.path.join(self.tmp.name, "secret.txt")
        write_file(outside, b"secret")
        for bad in ("../secret.txt", "a/../../secret.txt", "..\\secret.txt"):
            status, _, _ = self.request(
                "GET", "/{}/d/{}".format(
                    self.token, "/".join(quote(p, safe="") for p in bad.split("/"))
                )
            )
            self.assertEqual(status, 404, bad)

    def test_folder_browsing_list_and_download(self):
        os.makedirs(os.path.join(self.share, "资料", "图片"))
        write_file(os.path.join(self.share, "资料", "说明.txt"), b"doc")
        write_file(os.path.join(self.share, "资料", "图片", "图.png"), b"png")

        status, _, body = self.request(
            "GET", "/{}/?p={}".format(self.token, quote("资料", safe=""))
        )
        text = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertIn("说明.txt", text)
        self.assertIn("图片/</a>", text)
        self.assertIn("1 个文件夹 · 1 个文件", text)
        self.assertIn('href="?p=%E8%B5%84%E6%96%99%2F%E5%9B%BE%E7%89%87"', text)

        path = "/{}/d/{}".format(
            self.token,
            "/".join(quote(part, safe="") for part in ("资料", "图片", "图.png")),
        )
        status, headers, data = self.request("GET", path)
        self.assertEqual((status, data), (200, b"png"))
        self.assertIn("filename*=UTF-8''%E5%9B%BE.png", headers["content-disposition"])

    def test_missing_folder_is_404(self):
        status, _, _ = self.request(
            "GET", "/{}/?p={}".format(self.token, quote("没有这个目录", safe=""))
        )
        self.assertEqual(status, 404)

    def test_folder_traversal_rejected(self):
        os.makedirs(os.path.join(self.tmp.name, "private"))
        write_file(os.path.join(self.tmp.name, "private", "x.txt"), b"x")
        for bad in ("..", "../private", "a/../../private", "C:\\Windows"):
            status, _, _ = self.request(
                "GET", "/{}/?p={}".format(self.token, quote(bad, safe=""))
            )
            self.assertEqual(status, 404, bad)

    def test_upload_always_lands_in_root(self):
        os.makedirs(os.path.join(self.share, "分类"))
        status, _, _ = self.upload([("up.txt", b"up")])
        self.assertEqual(status, 200)
        self.assertTrue(os.path.isfile(os.path.join(self.share, "up.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.share, "分类", "up.txt")))

    def test_auth_throttle(self):
        self.server.state.throttle = srv.Throttle(limit=2, window=60, block=60)
        self.assertEqual(self.request("GET", "/bad-token-1/")[0], 404)
        status, headers, _ = self.request("GET", "/bad-token-2/")
        self.assertEqual(status, 429)
        self.assertIn("retry-after", headers)
        self.assertEqual(self.request("GET", "/{}/".format(self.token))[0], 429)

    def test_empty_upload_rejected(self):
        body = ("--{}--\r\n".format(BOUNDARY)).encode("ascii")
        status, _, _ = self.request(
            "POST",
            "/{}/u".format(self.token),
            body,
            {
                "Content-Type": "multipart/form-data; boundary=" + BOUNDARY,
                "Content-Length": str(len(body)),
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        self.assertEqual(status, 400)

    def test_interrupted_upload_leaves_no_temp_file(self):
        conn = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        head = (
            "POST /{}/u HTTP/1.0\r\n"
            "Host: 127.0.0.1\r\n"
            "Content-Type: multipart/form-data; boundary={}\r\n"
            "Content-Length: 999999\r\n\r\n"
        ).format(self.token, BOUNDARY).encode("ascii")
        partial = (
            "--{}\r\n"
            'Content-Disposition: form-data; name="file"; filename="cut.bin"\r\n\r\n'
            "abc"
        ).format(BOUNDARY).encode("ascii")
        conn.sendall(head + partial)
        conn.close()
        time.sleep(0.8)
        leftovers = [
            name for name in os.listdir(self.share) if name.startswith(".lanist-")
        ]
        self.assertEqual(leftovers, [])
        self.assertFalse(os.path.exists(os.path.join(self.share, "cut.bin")))

    def test_concurrent_uploads_keep_every_file(self):
        payloads = [("same.txt", ("value-{}".format(i)).encode()) for i in range(8)]

        def send(item):
            return self.upload([item])[0]

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(send, payloads))
        self.assertEqual(statuses, [200] * 8)
        names = [e.name for e in srv.Store(self.share).list()]
        self.assertEqual(len(names), 8)
        contents = {read_file(os.path.join(self.share, name)) for name in names}
        self.assertEqual(contents, {data for _, data in payloads})

    def test_fragment_json(self):
        self.upload([("one.txt", b"1")])
        status, headers, body = self.request(
            "GET", "/{}/?fragment=1".format(self.token)
        )
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["content-type"])
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["count"], 1)
        self.assertIn("one.txt", data["html"])

    def test_wrong_token_upload_rejected(self):
        status, _, _ = self.upload([("x.txt", b"x")], token="wrong-token-99")
        self.assertEqual(status, 404)
        self.assertFalse(os.path.exists(os.path.join(self.share, "x.txt")))


if __name__ == "__main__":
    unittest.main()
