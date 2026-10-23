import gc
import os
import socket
import tempfile
import unittest


@unittest.skipUnless(os.name == "nt", "window test is Windows-only")
class GuiTest(unittest.TestCase):
    def test_start_stop_and_refresh(self):
        from lanist import gui

        errors = []
        original = gui.messagebox.showerror
        gui.messagebox.showerror = lambda *args, **kwargs: errors.append(args)
        root = gui._create_root()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as share:
                with open(os.path.join(share, "hello.txt"), "wb") as f:
                    f.write(b"hi")
                app = gui.App(root, share, "amber-otter-42", port=0)
                root.update()
                app.start_service()
                root.update()
                self.assertIsNotNone(app.server)
                self.assertIn("/amber-otter-42/", app.url)
                app.show_qr()
                root.update()
                self.assertIsNotNone(app._qr_win)
                self.assertTrue(app._qr_win.winfo_exists())
                app._close_qr()
                root.update()
                self.assertIsNone(app._qr_win)
                self.assertEqual(
                    app.tree.item(app.tree.get_children()[0], "values")[0],
                    "hello.txt",
                )
                port = app.port
                app.stop_service()
                root.update()
                self.assertIsNone(app.server)
                self.assertEqual(app.url, "")
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.3)
                    self.assertNotEqual(s.connect_ex(("127.0.0.1", port)), 0)
                app.on_close()
                del app
                # Tk variables and images must be finalized while this thread
                # still owns the Tcl interpreter; otherwise a later test's GC
                # can block on the dead interpreter.
                del root
                gc.collect()
        finally:
            gui.messagebox.showerror = original
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
