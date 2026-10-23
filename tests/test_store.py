import os
import tempfile
import unittest

from lanist.store import Store, clean_name, is_temp_name


class CleanNameTest(unittest.TestCase):
    def test_basename_and_invalid_chars(self):
        self.assertEqual(clean_name("../../etc/passwd"), "passwd")
        self.assertEqual(clean_name("..\\..\\boot.ini"), "boot.ini")
        self.assertEqual(clean_name('a<b>c:d"e|f?g*h.txt'), "a_b_c_d_e_f_g_h.txt")

    def test_empty_and_reserved(self):
        self.assertEqual(clean_name(""), "upload.bin")
        self.assertEqual(clean_name("..."), "upload.bin")
        self.assertEqual(clean_name("CON.txt"), "_CON.txt")
        self.assertEqual(clean_name("lpt9.log"), "_lpt9.log")

    def test_long_name_keeps_extension(self):
        name = clean_name("a" * 400 + ".txt")
        self.assertLessEqual(len(name), 180)
        self.assertTrue(name.endswith(".txt"))

    def test_temp_looking_name_is_pushed_out(self):
        name = clean_name(".lanist-deadbeef.part")
        self.assertTrue(name.startswith("_"))
        self.assertFalse(is_temp_name(name))


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "share")
        self.store = Store(self.root)
        self.store.ensure()

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolve_accepts_inside_and_rejects_traversal(self):
        path = os.path.join(self.root, "ok.txt")
        self._write(path, b"x")
        self.assertEqual(os.path.realpath(self.store.resolve("ok.txt")), os.path.realpath(path))
        for bad in ("../x", "..\\x", "sub/x", "..", "", "C:\\Windows\\win.ini"):
            self.assertIsNone(self.store.resolve(bad))

    def test_list_skips_temp_and_symlink(self):
        self._write(os.path.join(self.root, "real.txt"), b"real")
        self._write(os.path.join(self.root, ".lanist-abc.part"), b"temp")
        outside = os.path.join(self.tmp.name, "outside.txt")
        self._write(outside, b"outside")
        try:
            os.symlink(outside, os.path.join(self.root, "link.txt"))
        except (OSError, NotImplementedError):
            pass
        names = [e.name for e in self.store.list()]
        self.assertIn("real.txt", names)
        self.assertNotIn(".lanist-abc.part", names)
        self.assertNotIn("link.txt", names)
        self.assertIsNone(self.store.resolve("link.txt"))

    def test_list_nested_folders_and_files(self):
        os.makedirs(os.path.join(self.root, "资料"))
        os.makedirs(os.path.join(self.root, "data"))
        self._write(os.path.join(self.root, "b.txt"), b"b")
        self._write(os.path.join(self.root, "资料", "a.txt"), b"a")

        root_entries = self.store.list()
        self.assertEqual([e.name for e in root_entries], ["data", "资料", "b.txt"])
        self.assertTrue(root_entries[0].is_dir)
        self.assertFalse(root_entries[-1].is_dir)

        nested = self.store.list("资料")
        self.assertEqual([e.name for e in nested], ["a.txt"])

    def test_resolve_nested_and_reject_escapes(self):
        os.makedirs(os.path.join(self.root, "资料"))
        path = os.path.join(self.root, "资料", "a.txt")
        self._write(path, b"a")
        self.assertEqual(
            os.path.realpath(self.store.resolve("资料/a.txt")),
            os.path.realpath(path),
        )
        self.assertEqual(self.store.resolve("资料"), None)
        for bad in ("资料/", "/资料/a.txt", "资料//a.txt", "资料/../x", "资料/./a.txt"):
            self.assertIsNone(self.store.resolve(bad), bad)
        self.assertIsNotNone(self.store.resolve_dir("资料"))
        self.assertIsNotNone(self.store.resolve_dir(""))
        self.assertIsNone(self.store.resolve_dir("不存在"))
        self.assertIsNone(self.store.resolve_dir(".."))

    def test_commit_into_subfolder(self):
        os.makedirs(os.path.join(self.root, "资料"))
        first = self.store.commit(self._temp(b"one"), "same.txt", "资料")
        second = self.store.commit(self._temp(b"two"), "same.txt", "资料")
        self.assertEqual(first, "same.txt")
        self.assertEqual(second, "same (1).txt")
        self.assertEqual(self._read(os.path.join(self.root, "资料", "same.txt")), b"one")
        self.assertFalse(os.path.exists(os.path.join(self.root, "same.txt")))

    def test_commit_never_overwrites(self):
        first = self.store.commit(self._temp(b"one"), "same.txt")
        second = self.store.commit(self._temp(b"two"), "same.txt")
        self.assertEqual(first, "same.txt")
        self.assertEqual(second, "same (1).txt")
        self.assertEqual(self._read(os.path.join(self.root, "same.txt")), b"one")
        self.assertEqual(self._read(os.path.join(self.root, "same (1).txt")), b"two")

    def _write(self, path, data):
        with open(path, "wb") as f:
            f.write(data)

    def _read(self, path):
        with open(path, "rb") as f:
            return f.read()

    def _temp(self, data):
        path = self.store.new_temp()
        self._write(path, data)
        return path


if __name__ == "__main__":
    unittest.main()
