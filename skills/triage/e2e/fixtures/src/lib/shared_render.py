"""Card rendering helpers shared by the library and theme views."""


def render_card(title: str, subtitle: str) -> str:
    """Render a single card. Long titles are not wrapped (tb-col1)."""
    return f"{title} — {subtitle}"


def card_theme_color(name: str) -> str:
    """Pick a background color for a card theme (tb-col2 contrast issue)."""
    return {"light": "#ffffff", "dark": "#111111"}.get(name, "#ffffff")
