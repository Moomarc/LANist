import json
import os
import re
import secrets

APP_NAME = "LANist"
VERSION = "3.0.0"

TOKEN_RE = re.compile(r"^[a-z]+-[0-9]{2}$")
OLD_TOKEN_RE = re.compile(r"^[a-z]+-[a-z]+-[0-9]{2}$")
CUSTOM_TOKEN_RE = re.compile(r"^[A-Za-z0-9._~-]{3,64}$")

NOUNS = (
    "acorn", "badger", "bamboo", "beacon", "berry", "bison", "brook", "cabin",
    "camel", "cedar", "cherry", "cloud", "comet", "cricket", "dawn", "delta",
    "dune", "eagle", "ember", "falcon", "fern", "finch", "fjord", "forest",
    "fox", "garden", "gecko", "globe", "grove", "harbor", "heron", "hill",
    "island", "juniper", "kite", "lake", "lantern", "leaf", "lily", "maple",
    "meadow", "mesa", "moon", "moss", "oak", "ocean", "otter", "panda",
    "pearl", "pine", "pond", "quartz", "raven", "reef", "river", "robin",
    "rock", "sail", "sparrow", "star", "stone", "storm", "tide", "trail",
    "valley", "willow",
)


def new_token():
    """One short word and two digits, e.g. fox-42."""
    return "{}-{:02d}".format(
        secrets.choice(NOUNS),
        secrets.randbelow(90) + 10,
    )


def valid_token(value):
    if not isinstance(value, str) or not value:
        return False
    if len(value) > 64:
        return False
    return bool(TOKEN_RE.match(value) or CUSTOM_TOKEN_RE.match(value))


def config_dir():
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Roaming"
        )
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config"
        )
    return os.path.join(base, APP_NAME)


def default_share_dir():
    return os.path.join(os.path.expanduser("~"), APP_NAME)


class Config:
    """Small JSON file holding the persistent access token."""

    def __init__(self, path=None):
        self.path = path or os.path.join(config_dir(), "config.json")
        self.data = {}
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            self.data = data

    def _save(self):
        folder = os.path.dirname(self.path)
        os.makedirs(folder, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.path)
        if os.name != "nt":
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def ensure_token(self):
        token = self.data.get("token")
        if isinstance(token, str) and OLD_TOKEN_RE.match(token):
            token = None
        if not isinstance(token, str) or not valid_token(token):
            token = new_token()
            self.data["token"] = token
            self._save()
        return token

    def set_token(self, token):
        if not valid_token(token):
            raise ValueError("口令只能包含字母、数字、点、下划线、波浪线和短横线，长度 3-64。")
        self.data["token"] = token
        self._save()
        return token

    def reset_token(self):
        return self.set_token(new_token())
