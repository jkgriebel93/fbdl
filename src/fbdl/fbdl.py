import click
import json
import os

from pathlib import Path
from typing import List

from yt_dlp import YoutubeDL
from .base import FileOperationsUtil, BaseDownloader, DEFAULT_REPLAY_TYPES
from .nfl import NFLShowDownloader, NFLWeeklyDownloader


@click.group()
def cli():
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_directory", type=click.Path(exists=True))
@click.option("--cookie_file", type=click.Path(exists=True))
def download_list(input_file, output_directory, cookie_file: Path = None):
    bd = BaseDownloader(cookie_file_path=cookie_file, destination_dir=output_directory)
    bd.download_from_file(Path(input_file))


@cli.command()
@click.argument("directory_path", type=click.Path(exists=True))
@click.option("--pretend", default=False, is_flag=True)
@click.option("--verbose", default=False, is_flag=True)
def update_metadata(directory_path, pretend, verbose):
    md_updater = FileOperationsUtil(directory_path, pretend, verbose)
    md_updater.iter_and_update_children()


@cli.command()
@click.argument("episode_names_file")
@click.option("--cookies")
@click.option("--show-dir")
def nfl_show(episode_names_file, cookies, show_dir):
    click.echo("Downloading NFL show")
    nfl = NFLShowDownloader(episode_names_file, cookies, show_dir)
    nfl.download_episodes()


@cli.command()
@click.argument("season", type=int)
@click.argument("week", type=int)
@click.option("--team", multiple=True, type=str)
@click.option(
    "--replay-type",
    multiple=True,
    type=click.Choice(DEFAULT_REPLAY_TYPES, case_sensitive=False),
)
def nfl_games(season: int, week: int, team: str, replay_type: str):
    click.echo(f"Season: {season}")
    click.echo(f"Week: {week}")
    click.echo(f"Team: {team}")
    click.echo(f"Replay Type: {replay_type}")

    profile_dir = os.getenv("PROFILE_LOCATION")
    destination_dir = os.getenv("DEST_DIR")
    allowed_extractors = ["nfl.com:plus:replay"]
    extractor_args = {"nfl.com:plus:replay": {"type": ["condensed_game"]}}

    add_opts = {
        "allowed_extractors": allowed_extractors,
        "extractor_args": extractor_args,
    }

    nwd = NFLWeeklyDownloader(
        cookie_file_path=Path(profile_dir),
        destination_dir=destination_dir,
        add_yt_opts=add_opts,
    )
    nwd.download_all_for_week(season, week, [replay_type[0]])


@cli.command()
@click.argument("series_name")
@click.option("--pretend", default=False, is_flag=True)
@click.option("--release-year", type=int)
@click.option("--replace", default=False, is_flag=True)
def rename_series(series_name: str, pretend: bool, release_year: int, replace: bool):
    click.echo(f"Renaming episodes for {series_name}")
    base_dir = os.getenv("MEDIA_BASE_DIR")

    if not base_dir:
        click.echo(
            "No media base directory set. Set the MEDIA_BASE_DIR environment variable."
        )
        return

    # Plex mandates that the release year be included in the
    # Series directory name, but _not_ in the episode title.
    if release_year:
        series_dir = f"{series_name} ({release_year})"
    else:
        series_dir = series_name

    series_directory = Path(base_dir, series_dir)

    fops = FileOperationsUtil(directory_path=series_directory, pretend=pretend)
    fops.rename_files(series_name=series_name, replace=replace)


@cli.command()
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

    for converted_file in conv_dir.rglob("*.mp4"):
        fops_util.update_mp4_title_from_filename(converted_file)
