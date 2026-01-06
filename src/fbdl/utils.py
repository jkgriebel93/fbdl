from pathlib import Path
from typing import Any, Dict, Optional

import yaml

CONFIG_FILE_NAME = "fbdl.yaml"

# Mapping of common config keys to command-specific parameter names
# Since option names are now standardized, these mappings are identity mappings
COMMON_OPTION_MAPPINGS = {
    "download_list": {
        "output_directory": "output_directory",
        "cookies_file": "cookies_file",
    },
    "update_metadata": {
        "pretend": "pretend",
        "verbose": "verbose",
    },
    "nfl_show": {
        "output_directory": "output_directory",
        "cookies_file": "cookies_file",
    },
    "nfl_games": {
        "output_directory": "output_directory",
        "cookies_file": "cookies_file",
        "nfl_username": "nfl_username",
        "nfl_password": "nfl_password",
    },
    "rename_series": {
        "pretend": "pretend",
    },
    "convert_format": {
        "pretend": "pretend",
    },
    "generate_nfo_files": {},
}


def find_config(explicit_path: Optional[str] = None) -> Optional[Path]:
    """
    Find the config file using auto-discovery or explicit path.

    Search order:
    1. Explicit path (if provided)
    2. Current working directory (fbdl.yaml)
    3. ~/.config/fbdl.yaml

    :param explicit_path: User-provided path to config file
    :return: Path to config file or None if not found
    """
    if explicit_path:
        path = Path(explicit_path)
        if path.exists():
            return path
        return None

    # Check current working directory
    cwd_config = Path.cwd() / CONFIG_FILE_NAME
    if cwd_config.exists():
        return cwd_config

    # Check ~/.config/fbdl.yaml
    home_config = Path.home() / ".config" / CONFIG_FILE_NAME
    if home_config.exists():
        return home_config

    return None


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.

    :param config_path: Path to the config file
    :return: Dict containing the configuration, or empty dict if no config
    """
    if config_path is None:
        return {}

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config if config else {}


def get_config_value(
    config: Dict[str, Any],
    command_name: str,
    param_name: str,
    common_key: Optional[str] = None,
) -> Any:
    """
    Get a config value for a specific command parameter.

    Checks command-specific section first, then common options.

    :param config: The loaded config dict
    :param command_name: Name of the command (e.g., "nfl_games")
    :param param_name: The parameter name to look up in command section
    :param common_key: The common config key that maps to this param (if any)
    :return: The config value or None if not found
    """
    # Check command-specific section first
    command_config = config.get(command_name, {})
    if command_config and param_name in command_config:
        return command_config[param_name]

    # Check common options using the mapping
    if common_key and common_key in config:
        return config[common_key]

    return None


def apply_config_to_kwargs(
    config: Dict[str, Any],
    command_name: str,
    kwargs: Dict[str, Any],
    cli_source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Apply config values to kwargs, respecting CLI > Config > Default precedence.

    :param config: The loaded config dict
    :param command_name: Name of the command (snake_case, e.g., "nfl_games")
    :param kwargs: Current kwargs dict (may contain CLI values or defaults)
    :param cli_source: Dict tracking which params were explicitly set via CLI
    :return: Updated kwargs dict
    """
    if not config:
        return kwargs

    # Get the mapping for this command
    common_mappings = COMMON_OPTION_MAPPINGS.get(command_name, {})

    # Get command-specific config section
    command_config = config.get(command_name, {})

    # Apply command-specific values (for params not set via CLI)
    for param_name, value in command_config.items():
        if cli_source and param_name in cli_source:
            # CLI explicitly set this, skip
            continue
        if kwargs.get(param_name) is None or (
            cli_source and param_name not in cli_source
        ):
            kwargs[param_name] = value

    # Apply common values using the mapping
    for common_key, param_name in common_mappings.items():
        if common_key in config:
            if cli_source and param_name in cli_source:
                # CLI explicitly set this, skip
                continue
            if kwargs.get(param_name) is None or (
                cli_source and param_name not in cli_source
            ):
                kwargs[param_name] = config[common_key]

    return kwargs
