import click
import os

from pathlib import Path
from typing import Tuple

from .base import FileOperationsUtil, BaseDownloader, DEFAULT_REPLAY_TYPES
from .nfl import NFLShowDownloader, NFLWeeklyDownloader


@click.group()
def cli():
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_directory", type=click.Path(exists=True))
@click.option(
    "--cookie_file",
    type=click.Path(exists=True),
    help="If authentication is required, you can provide a cookies file via this flag. The file must follow the Netscape format.",
)
def download_list(input_file, output_directory, cookie_file: Path = None):
    """
    Download a list of URLS provided via INPUT_FILE and store the files in OUTPUT_DIRECTORY.

    INPUT_FILE is the path to a text file where video URLs are listed, one per line.
    OUTPUT_DIRECTORY is the path to store the downloaded videos in.
    """
    bd = BaseDownloader(cookie_file_path=cookie_file, destination_dir=output_directory)
    bd.download_from_file(Path(input_file))


@cli.command()
@click.argument("directory_path", type=click.Path(exists=True))
@click.option(
    "--pretend",
    default=False,
    is_flag=True,
    help="Don't perform any updates; preview only.",
)
@click.option("--verbose", default=False, is_flag=True, help="Enable extra logging.")
def update_metadata(directory_path, pretend, verbose):
    """
    A largely one-off command to update embedded metadata for already downloaded NFL games based on the file's name.

    DIRECTORY_PATH is the directory fbdl will search for mp4 files.
    """
    md_updater = FileOperationsUtil(directory_path, pretend, verbose)
    md_updater.iter_and_update_children()


@cli.command()
@click.argument("input_file")
@click.option(
    "--output-directory",
    type=click.Path(exists=True),
    help="The path to store the downloaded videos in.",
)
@click.option(
    "--cookies",
    type=click.Path(exists=True),
    help="A .txt file containing NFL authentication cookies following the Netscape format.",
)
def nfl_show(episode_names_file, cookies, show_dir):
    """
    Download episodes from shows available on NFL Plus.

    INPUT_FILE is a JSON file containing the URL leaf nfl.com uses for each episode.
    """
    click.echo("Downloading NFL show")
    nfl = NFLShowDownloader(episode_names_file, cookies, show_dir)
    nfl.download_episodes()


@cli.command()
@click.argument("season", type=int)
@click.argument("week", type=int)
@click.option(
    "--team",
    multiple=True,
    type=str,
    help="Restrict downloads to a single team by providing the team's three letter abbreviation here. "
    "If blank, all are fetched.",
)
@click.option(
    "--replay-type",
    multiple=True,
    type=click.Choice(DEFAULT_REPLAY_TYPES.keys(), case_sensitive=False),
    help="Specify which replay types to download. If blank, the full game is downloaded.",
)
@click.option("--start-ep", type=int, help="Where to pick up episode numbering from.")
@click.option(
    "--raw-cookies",
    type=click.Path(exists=True),
    help="A txt file containing cookies needed for NFL API authentication.",
)
def nfl_games(
    season: int,
    week: int,
    team: Tuple[str],
    replay_type: Tuple[str] = ("full_game",),
    start_ep: int = 0,
    raw_cookies: str = "cookies.txt",
):
    """
    Download NFL game replays of the specified SEASON and WEEK

    SEASON Is the year (2009 or later) for which to download replays.
    WEEK The season week number to download replays for.
    """

    click.echo(f"Season: {season}")
    click.echo(f"Week: {week}")
    click.echo(f"Team: {team}")
    click.echo(f"Replay Type: {replay_type}")
    click.echo(f"Start episode: {start_ep}")
    click.echo(f"Cookies file: {raw_cookies}")

    profile_dir = os.getenv("PROFILE_LOCATION")
    destination_dir = os.getenv("DEST_DIR")
    allowed_extractors = ["nfl.com:plus:replay"]
    extractor_args = {"nflplusreplay": {"type": [replay_type[0]]}}

    add_opts = {
        "allowed_extractors": allowed_extractors,
        "extractor_args": extractor_args,
    }

    nwd = NFLWeeklyDownloader(
        firefox_profile_path=profile_dir,
        cookie_file_path=raw_cookies,
        destination_dir=destination_dir,
        add_yt_opts=add_opts,
    )

    replay_type = [DEFAULT_REPLAY_TYPES[r] for r in replay_type]

    nwd.download_all_for_week(
        season=season,
        week=week,
        teams=list(team),
        replay_types=replay_type,
        start_ep=start_ep,
    )


@cli.command()
@click.argument("series_name")
@click.option(
    "--pretend",
    default=False,
    is_flag=True,
    help="If passed, don't perform actual updates. Preview only.",
)
@click.option("--release-year", type=int, help="The year that the show first aired.")
@click.option(
    "--replace",
    default=False,
    is_flag=True,
    help="If passed, overwrite any file that already exists with the new name.",
)
def rename_series(series_name: str, pretend: bool, release_year: int, replace: bool):
    """
    A one-off command used to change file format names from SEE to <Series Name> (YYYY) - sSeEE - <episode_name>

    SERIES_NAME is the name of the TV series
    """
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
@click.option(
    "--orig-format",
    type=str,
    default="mkv",
    help="fbdl will attempt to convert all videos with the file extension provided here.",
)
@click.option(
    "--new-format", type=str, default="mp4", help="The desired output file type."
)
@click.option(
    "--pretend",
    default=False,
    is_flag=True,
    help="If passed, don't perform actual updates. Preview only.",
)
@click.option(
    "--delete",
    default=False,
    is_flag=True,
    help="If passed, remove the mkv files after conversion.",
)
def convert_format(
    directory: str,
    orig_format: str = "mkv",
    new_format: str = "mp4",
    pretend: bool = False,
    delete: bool = False,
):
    """
    Convert mkv files stored in DIRECTORY to mp4 files. Other formats will be added eventually.

    DIRECTORY is the directory fbdl will search for mkv files to convert.
    """
    conv_dir = Path(directory)
    if not conv_dir.is_dir():
        raise FileNotFoundError(f"Directory {conv_dir} does not exist.")

    fops_util = FileOperationsUtil(conv_dir, pretend)
    fops_util.convert_formats(
        orig_format=orig_format, new_format=new_format, delete=delete
    )
