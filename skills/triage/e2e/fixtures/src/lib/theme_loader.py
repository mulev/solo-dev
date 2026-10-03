"""Loads the active theme file. Plain JSON — no anchors, no aliases."""


def load_theme(path: str) -> dict:
    """Read and parse a theme file. tb-park claims a YAML-anchor crash here,
    but this loader only ever reads JSON — the file cannot confirm or refute
    that claim."""
    import json
    return json.loads(open(path).read())
