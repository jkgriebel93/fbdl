import json
import os
import random
import time
from datetime import date, datetime
from pathlib import Path
from random import uniform
from typing import Tuple

import click
from playwright._impl._errors import TargetClosedError, TimeoutError
from playwright.sync_api import sync_playwright

from .base import (
    BaseDownloader,
    FileOperationsUtil,
    MetaDataCreator,
)
from .constants import DEFAULT_REPLAY_TYPES, OUTPUT_FORMATS, POSITIONS, TEAM_FULL_NAMES
from .models import ProspectDataSoup
from .draft_buzz import DraftBuzzScraper, ProspectProfileListExtractor
from .nfl import NFLShowDownloader, NFLWeeklyDownloader
from .utils import apply_config_to_kwargs, find_config, load_config
from .word_gen import WordDocGenerator


@click.group()
@click.option(
    "--config",
    type=click.Path(exists=False),
    help="Path to config file. Auto-discovers fbcm.yaml in CWD or ~/.config/ if not specified.",
)
@click.pass_context
def cli(ctx, config):
    """fbcm - Football content manager and archiving tools."""
    ctx.ensure_object(dict)
    config_path = find_config(config)
    ctx.obj["config"] = load_config(config_path)
    if config_path:
        click.echo(f"Using config: {config_path}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "--output-directory",
    type=click.Path(exists=True),
    help="The path to store the downloaded videos in.",
)
@click.option(
    "--cookies-file",
    type=click.Path(exists=True),
    help="If authentication is required, you can provide a cookies file via this flag. The file must follow the Netscape format.",
)
@click.pass_context
def download_list(ctx, input_file, output_directory, cookies_file: Path = None):
    """
    Download a list of URLS provided via INPUT_FILE.

    INPUT_FILE is the path to a text file where video URLs are listed, one per line.
    """
    config = ctx.obj.get("config", {})
    kwargs = {"cookies_file": cookies_file, "output_directory": output_directory}
    kwargs = apply_config_to_kwargs(config, "download_list", kwargs)

    if not kwargs.get("output_directory"):
        raise click.UsageError("--output-directory is required (via option or config)")

    bd = BaseDownloader(
        cookie_file_path=kwargs["cookies_file"],
        destination_dir=kwargs["output_directory"],
    )
    bd.download_from_file(Path(input_file))


@cli.command()
@click.argument("input_file")
@click.option(
    "--output-directory",
    type=click.Path(exists=True),
    help="The path to store the downloaded videos in.",
)
@click.option(
    "--cookies-file",
    type=click.Path(exists=True),
    help="A .txt file containing NFL authentication cookies following the Netscape format.",
)
@click.pass_context
def nfl_show(ctx, input_file, output_directory, cookies_file):
    """
    Download episodes from shows available on NFL Plus.

    INPUT_FILE is a JSON file containing the URL leaf nfl.com uses for each episode.
    """
    config = ctx.obj.get("config", {})
    kwargs = {"cookies_file": cookies_file, "output_directory": output_directory}
    kwargs = apply_config_to_kwargs(config, "nfl_show", kwargs)

    click.echo("Downloading NFL show")
    nfl = NFLShowDownloader(
        input_file, kwargs.get("cookies_file"), kwargs.get("output_directory")
    )
    nfl.download_episodes()


@cli.command()
@click.option(
    "--output-directory",
    envvar="DESTINATION_DIR",
    type=click.Path(exists=True),
    help="Directory the downloaded games should be saved to.",
)
@click.option(
    "--cookies-file",
    type=click.Path(exists=True),
    help="A txt file containing cookies needed for NFL API authentication.",
)
@click.option(
    "--credentials-file",
    type=click.Path(exists=True),
    help="A JSON file containing NFL auth tokens (accessToken, refreshToken, expiresIn). "
    "Cannot be used with --nfl-username/--nfl-password.",
)
@click.option(
    "--nfl-username",
    type=str,
    help="The username/email associated with your NFL.com account. "
    "Cannot be used with --credentials-file.",
)
@click.option(
    "--nfl-password",
    type=str,
    help="The password associated with your NFL.com account. "
    "Cannot be used with --credentials-file.",
)
@click.option(
    "--show-login",
    type=bool,
    is_flag=True,
    help="When passed, show the browser window while performing automated login.",
)
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
    output_directory: str,
    cookies_file: str,
    credentials_file: str,
    nfl_username: str,
    nfl_password: str,
    show_login: bool,
    season: int,
    week: Tuple[int],
    team: Tuple[str],
    exclude: Tuple[str],
    replay_type: Tuple[str],
    start_ep: int,
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
        "output_directory": output_directory,
        "cookies_file": cookies_file,
        "credentials_file": credentials_file,
        "nfl_username": nfl_username if nfl_username else None,
        "nfl_password": nfl_password if nfl_password else None,
        "show_login": show_login if show_login else None,
        "season": season if season else None,
        "week": list(week) if week else None,
        "team": list(team) if team else None,
        "exclude": list(exclude) if exclude else None,
        "replay_type": list(replay_type) if replay_type else None,
        "start_ep": start_ep,
        "list_only": list_only,
    }
    kwargs = apply_config_to_kwargs(config, "nfl_games", kwargs)
    # Apply defaults for values still not set
    output_directory = kwargs.get("output_directory") or os.getcwd()
    cookies_file = kwargs.get("cookies_file") or "cookies.txt"
    credentials_file = kwargs.get("credentials_file")
    nfl_username = kwargs.get("nfl_username", None)
    nfl_password = kwargs.get("nfl_password", None)
    show_login = kwargs.get("show_login", False)
    season = kwargs.get("season", date.today().year)
    week = kwargs.get("week", [wk for wk in range(1, 19)])
    team = kwargs.get("team") or []
    exclude = kwargs.get("exclude") or []
    replay_type = kwargs.get("replay_type") or ["full_game"]
    start_ep = kwargs.get("start_ep") or None
    list_only = kwargs.get("list_only") or False

    # Validate mutual exclusivity: credentials_file vs username/password
    has_credentials_file = credentials_file is not None
    has_username_password = nfl_username is not None or nfl_password is not None

    if has_credentials_file and has_username_password:
        raise click.UsageError(
            "--credentials-file cannot be used with --nfl-username/--nfl-password. "
            "Use one authentication method or the other."
        )

    # Load credentials from file if provided
    nfl_auth = None
    if credentials_file:
        with open(credentials_file, "r") as f:
            nfl_auth = json.load(f)
        click.echo(f"Using credentials file: {credentials_file}")
    else:
        click.echo(f"NFL Username: {nfl_username}")

    click.echo(f"Output directory: {output_directory}")
    click.echo(f"Cookies file: {cookies_file}")
    click.echo(f"Show Login: {show_login}")
    click.echo(f"Season: {season}")
    click.echo(f"Week: {week}")
    click.echo(f"Team: {team}")
    click.echo(f"Exclude: {exclude}")
    click.echo(f"Replay Type: {replay_type}")
    click.echo(f"Start episode: {start_ep}")

    profile_dir = os.getenv("FIREFOX_PROFILE")
    allowed_extractors = ["nfl.com:plus:replay"]
    extractor_args = {"nflplusreplay": {"type": [replay_type[0]]}}

    add_opts = {
        "allowed_extractors": allowed_extractors,
        "extractor_args": extractor_args,
    }

    nwd = NFLWeeklyDownloader(
        firefox_profile_path=profile_dir,
        destination_dir=output_directory,
        nfl_username=nfl_username,
        nfl_password=nfl_password,
        nfl_auth=nfl_auth,
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
@click.option(
    "--output-directory",
    envvar="DESTINATION_DIR",
    type=click.Path(exists=True),
    help="Directory the downloaded games should be saved to.",
)
@click.option(
    "--output-format",
    default="json",
    type=click.Choice(OUTPUT_FORMATS.keys(), case_sensitive=False),
    help="Format to generate the draft profile(s) in.",
)
@click.option(
    "--player-slug",
    type=str,
    help="The slug used by nfldraftbuzz.com for the Player's profile.",
)
@click.option(
    "--position",
    type=str,
    multiple=True,
    help="Extract draft profiles for the specified position",
)
@click.option(
    "--input-file",
    type=click.Path(exists=True),
    help="A text file containing multiple player slugs "
    "(one per line) to extract profiles for.",
)
@click.option(
    "--generate-inline",
    default=None,
    is_flag=True,
    flag_value=True,
    help="When this flag is passed, the application will generate reports for each "
    "player as there are fetched, instead of at the end of the process.",
)
@click.pass_context
def extract_draft_profiles(
    ctx,
    output_directory: str,
    output_format: str,
    player_slug: str,
    position: str,
    input_file: str,
    generate_inline: bool,
):
    selected_positions = list(position)
    if not selected_positions:
        print("No positions selected. Defaulting to all.")
        selected_positions = POSITIONS
    print(f"Position: {selected_positions}")

    with open(input_file, "r") as infile:
        profile_urls = json.load(infile)

    with sync_playwright() as playwright:
        scraper = DraftBuzzScraper(
            playwright=playwright, profile_root_dir=Path(output_directory)
        )

        completed_profiles = []
        with open(f"{output_directory}/completed.json", "r") as infile:
            completed_profiles = json.load(infile)

        click.echo(f"Loaded {len(completed_profiles)} completed profiles.")

        for pos in selected_positions:
            if pos not in profile_urls:
                raise click.BadParameter(f"{pos} is not present in the input file.")

            position_profiles = profile_urls[pos]
            click.echo(f"Found {len(position_profiles)} {pos} profile URLs to extract.")

            position_player_data = {}

            for prof_slug in position_profiles:
                if prof_slug in completed_profiles:
                    click.echo(f"Already completed {prof_slug}. Skipping.")
                    continue

                click.echo(f"Processing player profile: {prof_slug}")
                time.sleep(uniform(3.5, 4.5))

                try:
                    player_data = scraper.scrape_from_url(url=prof_slug, position=pos)
                    position_player_data[player_data.basic_info.full_name] = (
                        player_data.to_dict()
                    )
                    scraper.save_player_photo_to_disk()

                    completed_profiles.append(prof_slug)

                except Exception as e:
                    print(e)
                    break
            rn = datetime.now()
            suffix = f"{rn.hour}_{rn.minute}_{rn.second}"
            fname = f"{pos}_{suffix}.json"
            with open(f"{output_directory}/{fname}", "w") as outfile:
                json.dump(position_player_data, outfile, indent=4)

            with open(f"{output_directory}/completed.json", "w") as outfile:
                json.dump(completed_profiles, outfile, indent=4)

            time.sleep(random.uniform(10, 15))


@cli.command()
@click.pass_context
def update_draft_prospect_urls(ctx):
    profile_lists = {}
    with sync_playwright() as playwright:
        pple = ProspectProfileListExtractor(playwright=playwright)

        for position in POSITIONS:
            try:
                profile_lists[position] = pple.extract_prospect_urls_for_position(
                    pos=position
                )
            except TimeoutError:
                print(
                    f"Position {position} timed out. Sleeping, then moving on to next position."
                )
                time.sleep(5)

    with open("prospect_urls.json", "w") as outfile:
        json.dump(profile_lists, outfile, indent=4)


@cli.command()
@click.pass_context
def draft_sandbox(ctx):
    click.echo("Draft profile sandbox...")
    with open("output_data/QB.json", "r") as infile:
        qb_data = json.load(infile)

    fm_data = qb_data["Fernando Mendoza"]
    mendoza_obj = ProspectDataSoup.from_dict(fm_data)
    wdg = WordDocGenerator(prospect=mendoza_obj,
                           output_path="output_data",
                           ring_image_base_dir="output_data",
                           colors_path="input_files/school_colors.json")
    wdg.generate_complete_document()


@cli.command()
@click.argument("directory")
@click.option(
    "--pretend",
    default=None,
    is_flag=True,
    flag_value=True,
    help="If passed, don't perform actual updates. Preview only.",
)
@click.option(
    "--orig-format",
    type=str,
    default=None,
    help="fbcm will attempt to convert all videos with the file extension provided here.",
)
@click.option(
    "--new-format", type=str, default=None, help="The desired output file type."
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
    pretend: bool,
    orig_format: str,
    new_format: str,
    delete: bool,
):
    """
    Convert mkv files stored in DIRECTORY to mp4 files. Other formats will be added eventually.

    DIRECTORY is the directory fbcm will search for mkv files to convert.
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
    help="Passing this flag tells fbcm to overwrite any existing .nfo files it may encounter for a given video.",
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
