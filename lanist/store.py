import os
import re
import tempfile
import threading
from dataclasses import dataclass

TEMP_PREFIX = ".lanist-"
TEMP_SUFFIX = ".part"
MAX_NAME = 180
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    "COM{}".format(i) for i in range(1, 10)
} | {"LPT{}".format(i) for i in range(1, 10)}


@dataclass(frozen=True)
class Entry:
    name: str
    size: int
    mtime: float
    is_dir: bool = False


def clean_name(raw):
    """Turn any client supplied string into a safe single file name."""
    name = raw.replace("\\", "/").split("/")[-1].strip().rstrip(".")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", name)
    if not name or name in (".", ".."):
        name = "upload.bin"
    if name.split(".")[0].upper() in RESERVED_NAMES:
        name = "_" + name
    if is_temp_name(name):
        name = "_" + name
    if len(name) > MAX_NAME:
        stem, ext = os.path.splitext(name)
        ext = ext[:20]
        name = stem[: MAX_NAME - len(ext)] + ext
    return name


def is_temp_name(name):
    return name.startswith(TEMP_PREFIX) and name.endswith(TEMP_SUFFIX)


def split_rel(rel):
    """Split a client supplied relative path; None means unsafe."""
    if not isinstance(rel, str):
        return None
    rel = rel.replace("\\", "/")
    if rel in ("", "."):
        return []
    parts = []
    for part in rel.split("/"):
        if not part or part in (".", "..") or "\x00" in part:
            return None
        if part.rstrip(". ") != part:
            return None
        parts.append(part)
    return parts


class Store:
    def __init__(self, root):
        self.root = os.path.abspath(os.path.expanduser(root))
        self._lock = threading.RLock()

    def ensure(self):
        try:
            os.makedirs(self.root, exist_ok=True)
        except OSError as e:
            raise RuntimeError("建不了共享目录 {}：{}".format(self.root, e)) from e

    def _inside(self, rel):
        parts = split_rel(rel)
        if parts is None:
            return None
        root = os.path.realpath(self.root)
        target = os.path.realpath(os.path.join(root, *parts)) if parts else root
        try:
            common = os.path.commonpath([root, target])
        except ValueError:
            return None
        if os.path.normcase(common) != os.path.normcase(root):
            return None
        return parts, target

    def list(self, rel=""):
        found = self._inside(rel)
        if found is None:
            return []
        _, folder = found
        dirs, files = [], []
        try:
            with os.scandir(folder) as it:
                for entry in it:
                    if is_temp_name(entry.name):
                        continue
                    try:
                        if entry.is_symlink():
                            continue
                        st = entry.stat(follow_symlinks=False)
                        if entry.is_dir(follow_symlinks=False):
                            dirs.append(Entry(entry.name, 0, st.st_mtime, True))
                        elif entry.is_file(follow_symlinks=False):
                            files.append(Entry(entry.name, st.st_size, st.st_mtime))
                    except OSError:
                        continue
        except OSError:
            return []
        dirs.sort(key=lambda item: item.name.casefold())
        files.sort(key=lambda item: item.mtime, reverse=True)
        return dirs + files

    def resolve(self, rel):
        """Return the real path of a shared file, or None if it escapes the folder."""
        found = self._inside(rel)
        if found is None:
            return None
        parts, target = found
        if not parts or not os.path.isfile(target):
            return None
        return target

    def resolve_dir(self, rel):
        """Return the real path of a shared sub folder; the root maps to itself."""
        found = self._inside(rel)
        if found is None:
            return None
        _, target = found
        if not os.path.isdir(target):
            return None
        return target

    def _unique_name(self, folder, name):
        if not os.path.exists(os.path.join(folder, name)):
            return name
        stem, ext = os.path.splitext(name)
        i = 1
        while True:
            candidate = "{} ({}){}".format(stem, i, ext)
            if not os.path.exists(os.path.join(folder, candidate)):
                return candidate
            i += 1

    def new_temp(self):
        self.ensure()
        fd, path = tempfile.mkstemp(
            dir=self.root, prefix=TEMP_PREFIX, suffix=TEMP_SUFFIX
        )
        os.close(fd)
        return path

    def commit(self, temp_path, name, rel=""):
        """Move a finished upload in place; never overwrite an existing file."""
        found = self._inside(rel)
        if found is None:
            found = self._inside("")
        _, folder = found
        if not os.path.isdir(folder):
            folder = self.root
        final = clean_name(name)
        with self._lock:
            final = self._unique_name(folder, final)
            os.replace(temp_path, os.path.join(folder, final))
        return final

    def discard(self, temp_path):
        try:
            os.remove(temp_path)
        except OSError:
            pass
