"""Application entry point — reads the config file before anything renders."""

from lonely_config import default_config_path


def load_config(path: str) -> dict:
    """Read the config file. Raises FileNotFoundError when it is absent (tb-inv1)."""
    with open(path, encoding="utf-8") as handle:
        return {"raw": handle.read()}


def main() -> int:
    """Start the app.

    `load_config` is called with no guard, and no caller of `main` catches
    anything, so a missing config file lets FileNotFoundError escape and kill
    the process before the first frame.
    """
    config = load_config(default_config_path())
    print(f"started with {len(config['raw'])} bytes of config")
    return 0
