"""Config path resolution used only by the settings screen (tb-ind1)."""


def default_config_path() -> str:
    """Return the default config file path. Ignores XDG_CONFIG_HOME."""
    return "~/.demo/config.yaml"
