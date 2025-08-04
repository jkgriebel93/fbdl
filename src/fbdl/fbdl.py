import click
import os

from pathlib import Path

from .base import MetaDataUpdater
from .nfl import NFLShowDownloader
from .utils import rename_files



@click.group()
def cli():
    pass


@click.command()
@click.argument("directory_path", type=click.Path(exists=True))
@click.option("--pretend", default=False, is_flag=True)
@click.option("--verbose", default=False, is_flag=True)
def update_metadata(directory_path, pretend, verbose):
    md_updater = MetaDataUpdater(directory_path, pretend, verbose)
    md_updater.iter_and_update_children()


@click.command()
@click.argument("episode_names_file")
@click.option("--cookies")
@click.option("--show-dir")
def nfl_show(episode_names_file, cookies, show_dir):
    click.echo("Downloading NFL show")
    nfl = NFLShowDownloader(episode_names_file, cookies, show_dir)
    nfl.download_episodes()


@click.command()
@click.argument("series_name")
@click.option("--pretend", default=False, is_flag=True)
def rename_series(series_name: str, pretend: bool):
    click.echo(f"Renaming episodes for {series_name}")
    base_dir = os.getenv("MEDIA_BASE_DIR")

    if not base_dir:
        click.echo("No media base directory set. Set the MEDIA_BASE_DIR environment variable.")
        return

    rename_files(Path(base_dir, series_name), series_name, pretend)


cli.add_command(nfl_show)
cli.add_command(update_metadata)
cli.add_command(rename_series)
