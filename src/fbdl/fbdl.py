import click
import os

from pathlib import Path

from .base import FileOperationsUtil, BaseDownloader
from .nfl import NFLShowDownloader
from .utils import rename_files



@click.group()
def cli():
    pass


@click.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_directory", type=click.Path(exists=True))
@click.option("--cookie_file", type=click.Path(exists=True))
def download_list(input_file, output_directory, cookie_file: Path = None):
    bd = BaseDownloader(cookie_file_path=cookie_file,
                        destination_dir=output_directory)
    bd.download_from_file(Path(input_file))


@click.command()
@click.argument("directory_path", type=click.Path(exists=True))
@click.option("--pretend", default=False, is_flag=True)
@click.option("--verbose", default=False, is_flag=True)
def update_metadata(directory_path, pretend, verbose):
    md_updater = FileOperationsUtil(directory_path, pretend, verbose)
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
@click.option("--release-year", type=int)
@click.option("--replace", default=False, is_flag=True)
def rename_series(series_name: str, pretend: bool, release_year: int, replace: bool):
    click.echo(f"Renaming episodes for {series_name}")
    base_dir = os.getenv("MEDIA_BASE_DIR")

    if not base_dir:
        click.echo("No media base directory set. Set the MEDIA_BASE_DIR environment variable.")
        return

    # Plex mandates that the release year be included in the
    # Series directory name, but _not_ in the episode title.
    if release_year:
        series_dir = f"{series_name} ({release_year})"
    else:
        series_dir = series_name

    series_directory = Path(base_dir, series_dir)

    rename_files(series_directory, series_name, pretend, replace)


@click.command()
@click.argument("directory")
@click.option("--pretend", default=False, is_flag=True)
@click.option("--update-meta", default=False, is_flag=True)
@click.option("--delete", default=False, is_flag=True)
def convert_format(directory, pretend, update_meta, delete):
    conv_dir = Path(directory)
    if not conv_dir.is_dir():
        raise FileNotFoundError(f"Directory {conv_dir} does not exist.")

    fops_util = FileOperationsUtil(conv_dir, pretend)
    fops_util.convert_formats(delete=delete)


cli.add_command(nfl_show)
cli.add_command(update_metadata)
cli.add_command(rename_series)
cli.add_command(convert_format)
cli.add_command(download_list)