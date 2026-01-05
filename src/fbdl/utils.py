import click
import tomllib  # Python 3.11+, or use `tomli` for earlier versions
from pathlib import Path
from functools import wraps

def with_config(config_option='--config', config_file=None):
    """Decorator that adds config file support to a Click command."""
    def decorator(cmd):
        @click.option(config_option, type=click.Path(exists=True),
                      default=config_file, help='Path to config file')
        @wraps(cmd)
        def wrapper(config, *args, **kwargs):
            if config:
                with open(config, 'rb') as f:
                    file_config = tomllib.load(f)
                # CLI args take precedence over config file
                for key, value in file_config.items():
                    if kwargs.get(key) is None:
                        kwargs[key] = value
            return cmd(*args, **kwargs)
        return wrapper
    return decorator