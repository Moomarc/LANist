import gc
import os
import unittest


@unittest.skipUnless(os.name == "nt", "window test is Windows-only")
class QrTest(unittest.TestCase):
    def test_qr_image_renders(self):
        from lanist import gui

        self.assertIsNotNone(gui.QrCode)
        root = gui._create_root()
        root.withdraw()
        try:
            img = gui.qr_photo("http://192.168.1.2:8000/fox-42/", master=root)
            self.assertEqual(img.width(), img.height())
            self.assertGreater(img.width(), 100)
            del img
        finally:
            root.destroy()
            gc.collect()


if __name__ == "__main__":
    unittest.main()
