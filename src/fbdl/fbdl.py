import json
import os
from datetime import date
from pathlib import Path
from typing import Tuple

import click
from pygments.lexer import default

from .base import (
    DEFAULT_REPLAY_TYPES,
    TEAM_FULL_NAMES,
    BaseDownloader,
    FileOperationsUtil,
    MetaDataCreator,
)
from .nfl import NFLShowDownloader, NFLWeeklyDownloader
from .utils import apply_config_to_kwargs, find_config, load_config


@click.group()
@click.option(
    "--config",
    type=click.Path(exists=False),
    help="Path to config file. Auto-discovers fbdl.yaml in CWD or ~/.config/ if not specified.",
)
@click.pass_context
def cli(ctx, config):
    """fbdl - Football download and archiving tools."""
    ctx.ensure_object(dict)
    config_path = find_config(config)
    ctx.obj["config"] = load_config(config_path)
    if config_path:
        click.echo(f"Using config: {config_path}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_directory", type=click.Path(exists=True), required=False)
@click.option(
    "--cookies-file",
    type=click.Path(exists=True),
    help="If authentication is required, you can provide a cookies file via this flag. The file must follow the Netscape format.",
)
@click.pass_context
def download_list(ctx, input_file, output_directory, cookies_file: Path = None):
    """
    Download a list of URLS provided via INPUT_FILE and store the files in OUTPUT_DIRECTORY.

    INPUT_FILE is the path to a text file where video URLs are listed, one per line.
    OUTPUT_DIRECTORY is the path to store the downloaded videos in.
    """
    config = ctx.obj.get("config", {})
    kwargs = {"cookies_file": cookies_file, "output_directory": output_directory}
    kwargs = apply_config_to_kwargs(config, "download_list", kwargs)

    if not kwargs.get("output_directory"):
        raise click.UsageError("OUTPUT_DIRECTORY is required (via argument or config)")

    bd = BaseDownloader(
        cookie_file_path=kwargs["cookies_file"],
        destination_dir=kwargs["output_directory"],
    )
    bd.download_from_file(Path(input_file))


@cli.command()
@click.argument("directory_path", type=click.Path(exists=True))
@click.option(
    "--pretend",
    default=None,
    is_flag=True,
    flag_value=True,
    help="Don't perform any updates; preview only.",
)
@click.option(
    "--verbose",
    default=None,
    is_flag=True,
    flag_value=True,
    help="Enable extra logging.",
)
@click.pass_context
def update_metadata(ctx, directory_path, pretend, verbose):
    """
    A largely one-off command to update embedded metadata for already downloaded NFL games based on the file's name.

    DIRECTORY_PATH is the directory fbdl will search for mp4 files.
    """
    config = ctx.obj.get("config", {})
    kwargs = {"pretend": pretend, "verbose": verbose}
    kwargs = apply_config_to_kwargs(config, "update_metadata", kwargs)

    md_updater = FileOperationsUtil(
        directory_path,
        kwargs.get("pretend", False),
        kwargs.get("verbose", False),
    )
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
@click.pass_context
def nfl_show(ctx, input_file, output_directory, cookies):
    """
    Download episodes from shows available on NFL Plus.

    INPUT_FILE is a JSON file containing the URL leaf nfl.com uses for each episode.
    """
    config = ctx.obj.get("config", {})
    kwargs = {"cookies": cookies, "output_directory": output_directory}
    kwargs = apply_config_to_kwargs(config, "nfl_show", kwargs)

    click.echo("Downloading NFL show")
    nfl = NFLShowDownloader(
        input_file, kwargs.get("cookies"), kwargs.get("output_directory")
    )
    nfl.download_episodes()


@cli.command()
@click.option("--nfl-username", type=str, help="The username/email associated with your NFL.com account.")
@click.option("--nfl-password", type=str, help="The password associated with your NFL.com account.")
@click.option("--show-login",
    type=bool,
    is_flag=True,
    help="When passed, show the browser window while performing automated login.")
@click.option("--season", type=int, help="Season games were played in")
@click.option("--week", type=int, multiple=True, help="Week the games were played in")
@click.option(
    "--team",
    multiple=True,
    type=str,
    help="Restrict downloads to a single team by providing the team's three letter abbreviation here. "
    "If blank, all are fetched.",
)
@click.option("--exclude", multiple=True, type=str, help="Teams to exclude")
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
@click.option(
    "--destination-dir",
    envvar="DESTINATION_DIR",
    type=click.Path(exists=True),
    help="Directory the downloaded games should be saved to.",
)
@click.option(
    "--list-only",
    type=bool,
    default=None,
    is_flag=True,
    flag_value=True,
    help="Don't download the games, only list them to stdout.",
)
@click.pass_context
def nfl_games(
    ctx,
        nfl_username: str,
        nfl_password: str,
        show_login: bool,
    season: int,
    week: Tuple[int],
    team: Tuple[str],
    exclude: Tuple[str],
    replay_type: Tuple[str],
    start_ep: int,
    raw_cookies: str,
    destination_dir: str,
    list_only: bool,
):
    # TODO: Ensure jellyfin isn't running..it borks the post processing
    """
    Download NFL game replays of the specified SEASON and WEEK

    SEASON Is the year (2009 or later) for which to download replays.
    WEEK The season week number to download replays for.
    """
    config = ctx.obj.get("config", {})

    # Build kwargs, converting tuples to lists for config merging
    kwargs = {
        "nfl_username": nfl_username if nfl_username else None,
        "nfl_password": nfl_password if nfl_password else None,
        "show_login": show_login if show_login else None,
        "season": season if season else None,
        "week": list(week) if week else None,
        "team": list(team) if team else None,
        "exclude": list(exclude) if exclude else None,
        "replay_type": list(replay_type) if replay_type else None,
        "start_ep": start_ep,
        "raw_cookies": raw_cookies,
        "destination_dir": destination_dir,
        "list_only": list_only,
    }
    kwargs = apply_config_to_kwargs(config, "nfl_games", kwargs)
    # Apply defaults for values still not set
    nfl_username = kwargs.get("nfl_username", None)
    nfl_password = kwargs.get("nfl_password", None)
    show_login = kwargs.get("show_login", False)
    season = kwargs.get("season", date.today().year)
    week = kwargs.get("week", [wk for wk in range(1, 19)])
    team = kwargs.get("team") or []
    exclude = kwargs.get("exclude") or []
    replay_type = kwargs.get("replay_type") or ["full_game"]
    start_ep = kwargs.get("start_ep") or 0
    raw_cookies = kwargs.get("raw_cookies") or "cookies.txt"
    destination_dir = kwargs.get("destination_dir") or os.getcwd()
    list_only = kwargs.get("list_only") or False

    click.echo(f"NFL Username: {nfl_username}")
    click.echo(f"Show Login: {show_login}")
    click.echo(f"Season: {season}")
    click.echo(f"Week: {week}")
    click.echo(f"Team: {team}")
    click.echo(f"Exclude: {exclude}")
    click.echo(f"Replay Type: {replay_type}")
    click.echo(f"Start episode: {start_ep}")
    click.echo(f"Cookies file: {raw_cookies}")
    click.echo(f"Destination directory: {destination_dir}")

    profile_dir = os.getenv("FIREFOX_PROFILE")
    allowed_extractors = ["nfl.com:plus:replay"]
    extractor_args = {"nflplusreplay": {"type": [replay_type[0]]}}

    add_opts = {
        "allowed_extractors": allowed_extractors,
        "extractor_args": extractor_args,
    }

    nwd = NFLWeeklyDownloader(
        firefox_profile_path=profile_dir,
        nfl_username=nfl_username,
        nfl_password=nfl_password,
        destination_dir=destination_dir,
        show_login=show_login,
        add_yt_opts=add_opts,
    )

    if team:
        teams_to_fetch = [tm for tm in team if tm not in exclude]
    else:
        teams_to_fetch = [tm for tm in TEAM_FULL_NAMES if tm not in exclude]

    replay_type = [DEFAULT_REPLAY_TYPES[r] for r in replay_type]

    if list_only:
        games = []
        for wk in week:
            click.echo(f"Working on games for Week {wk}")
            wk_games = nwd.get_and_extract_games_for_week(
                season=season, week=wk, teams=teams_to_fetch, replay_types=replay_type
            )
            games.extend(wk_games)

        from pprint import pprint

        pprint(games, indent=4)

    else:
        for wk in week:
            click.echo(f"Working on games for Week {wk}")
            nwd.download_all_for_week(
                season=season,
                week=wk,
                teams=teams_to_fetch,
                replay_types=replay_type,
                start_ep=start_ep,
            )


@cli.command()
@click.argument("series_name")
@click.option(
    "--pretend",
    default=None,
    is_flag=True,
    flag_value=True,
    help="If passed, don't perform actual updates. Preview only.",
)
@click.option("--release-year", type=int, help="The year that the show first aired.")
@click.option(
    "--replace",
    default=None,
    is_flag=True,
    flag_value=True,
    help="If passed, overwrite any file that already exists with the new name.",
)
@click.pass_context
def rename_series(
    ctx, series_name: str, pretend: bool, release_year: int, replace: bool
):
    """
    A one-off command used to change file format names from SEE to <Series Name> (YYYY) - sSeEE - <episode_name>

    SERIES_NAME is the name of the TV series
    """
    config = ctx.obj.get("config", {})
    kwargs = {"pretend": pretend, "release_year": release_year, "replace": replace}
    kwargs = apply_config_to_kwargs(config, "rename_series", kwargs)

    pretend = kwargs.get("pretend", False)
    release_year = kwargs.get("release_year")
    replace = kwargs.get("replace", False)

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
    default=None,
    help="fbdl will attempt to convert all videos with the file extension provided here.",
)
@click.option(
    "--new-format", type=str, default=None, help="The desired output file type."
)
@click.option(
    "--pretend",
    default=None,
    is_flag=True,
    flag_value=True,
    help="If passed, don't perform actual updates. Preview only.",
)
@click.option(
    "--delete",
    default=None,
    is_flag=True,
    flag_value=True,
    help="If passed, remove the mkv files after conversion.",
)
@click.pass_context
def convert_format(
    ctx,
    directory: str,
    orig_format: str,
    new_format: str,
    pretend: bool,
    delete: bool,
):
    """
    Convert mkv files stored in DIRECTORY to mp4 files. Other formats will be added eventually.

    DIRECTORY is the directory fbdl will search for mkv files to convert.
    """
    config = ctx.obj.get("config", {})
    kwargs = {
        "orig_format": orig_format,
        "new_format": new_format,
        "pretend": pretend,
        "delete": delete,
    }
    kwargs = apply_config_to_kwargs(config, "convert_format", kwargs)

    orig_format = kwargs.get("orig_format") or "mkv"
    new_format = kwargs.get("new_format") or "mp4"
    pretend = kwargs.get("pretend", False)
    delete = kwargs.get("delete", False)

    conv_dir = Path(directory)
    if not conv_dir.is_dir():
        raise FileNotFoundError(f"Directory {conv_dir} does not exist.")

    fops_util = FileOperationsUtil(conv_dir, pretend)
    fops_util.convert_formats(
        orig_format=orig_format, new_format=new_format, delete=delete
    )


@cli.command()
@click.argument("directory", type=click.Path(exists=True))
@click.argument("season", type=int)
@click.argument("dates", type=click.Path(exists=True))
@click.option("--league", type=str, default=None, help="One of nfl, ufl, cfl")
@click.option(
    "--overwrite",
    type=bool,
    default=None,
    is_flag=True,
    flag_value=True,
    help="Passing this flag tells fbdl to overwrite any existing .nfo files it may encounter for a given video.",
)
@click.pass_context
def generate_nfo_files(
    ctx,
    directory: str,
    season: int,
    dates: str,
    league: str,
    overwrite: bool,
):
    """
    Construct .nfo files for games of the given league + season combo.

    DIRECTORY is the league's base directory, i.e. the one containing all season directories.
    SEASON is the year we should generate .nfo files for, e.g. 2025
    DATES is a JSON file mapping game numbers to the date they were played.

    """
    config = ctx.obj.get("config", {})
    kwargs = {"league": league, "overwrite": overwrite}
    kwargs = apply_config_to_kwargs(config, "generate_nfo_files", kwargs)

    league = kwargs.get("league") or "nfl"
    overwrite = kwargs.get("overwrite", False)

    click.echo(f"Generating .nfo files for {league.upper()} season {season}.")
    click.echo(f"Looking for relevant video files in {directory}")
    with open(dates, "r") as infile:
        game_dates = json.load(infile)

    mdc = MetaDataCreator(base_dir=directory, game_dates=game_dates, league=league)

    mdc.create_nfo_for_season(year=season, overwrite=overwrite)
    click.echo("Done")
