import json
import logging
import time

import requests

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union, List, Any
from yt_dlp import YoutubeDL
from yt_dlp.extractor.nfl import NFLBaseIE
from yt_dlp.cookies import (
    _parse_browser_specification,
    extract_cookies_from_browser,
)
from yt_dlp.utils import urlencode_postdata
from yt_dlp.utils.traversal import traverse_obj

from .base import (
    MEDIA_BASE_DIR,
    DEFAULT_REPLAY_TYPES,
    CITY_TO_ABBR,
    abbreviation_map,
    is_playoff_week,
    get_week_int_as_string,
    BaseDownloader,
)

logger = logging.getLogger(__name__)


class NFLShowDownloader:
    """
    A wrapper around YoutubeDL that specializes in downloading TV Series available on NFL Plus.
    TODO: This class requires a lot of work to leverage yt-dlp fully.

    ivar base_url: str - The base URL the NFL uses for its TV episodes
    """

    def __init__(
        self,
        episode_list_path: Union[str, Path],
        cookie_file_path: Union[str, Path],
        show_dir: Union[str, Path],
        pause_time: int = 30,
    ) -> None:
        """
        Create the NFLShowDownloader with the given arguments.

        :param episode_list_path: The JSON file containing an array of arrays,
            each containing URL leaves for the season's episodes.
        :type episode_list_path: str | Path

        :param cookie_file_path: The Netscape format cookies file to use for authentication.
        :type cookie_file_path: str | Path

        :param show_dir: The directory to store the show's seasons and episodes in.
        :type show_dir: str | Path

        :param pause_time: Number of seconds to sleep the program between season downloads
            to avoid being banned or throttled.
        """
        self.base_url = "https://www.nfl.com/plus/episodes/"

        with open(str(episode_list_path), "r") as infile:
            data = json.load(infile)
            self.episodes = data["seasons"]

        if isinstance(cookie_file_path, str):
            cookie_file_path = Path(cookie_file_path)
        self.cookie_file_path = cookie_file_path

        self.show_directory = Path(MEDIA_BASE_DIR, show_dir)
        self.show_directory.mkdir(parents=True, exist_ok=True)

        self.base_yt_ops = {
            "cookiefile": self.cookie_file_path,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            "merge_output_format": "mp4",
            # "concurrent_fragment_downloads": 4,
            # "writethumbnail": True,
            # "embedthumbnail": True,
            "addmetadata": True,
            "throttledratelimit": 1000000,
            "postprocessors": [
                {
                    "key": "FFmpegMetadata",
                    "add_chapters": True,
                    "add_metadata": True,
                },
                {
                    "key": "EmbedThumbnail",
                    "already_have_thumbnail": True,
                },
            ],
            "embedsubs": True,
            "writesubs": True,
            "subtitleslangs": ["en"],
            "progress_hooks": [
                lambda d: (
                    print(f"Downloading {d['filename']}")
                    if d["status"] == "downloading"
                    else None
                )
            ],
        }
        self.completed = []
        self.errors = []
        self.errors = []
        self.completed_seasons = []
        self.pause_time = pause_time

    def download_episodes(self) -> None:
        """
        Donwload the show episodes as specified in __init__
        :return:
        """
        print("Downloading episodes")
        for idx, season in enumerate(self.episodes):
            print(f"Working on season {idx + 1}")
            if idx + 1 in self.completed_seasons:
                print(f"Skipping Season {idx + 1}")
                continue
            season_directory = self.show_directory / Path(
                "Season " + str(idx + 1).zfill(2)
            )
            season_directory.mkdir(parents=True, exist_ok=True)

            output_tmpl = str(season_directory / "%(title)s.%(ext)s")
            completed_urls = [
                f"{self.base_url}{ep}"
                for ep in season
                if ((ep not in self.completed) and (ep not in self.errors))
            ]
            full_opts = {**self.base_yt_ops, "outtmpl": output_tmpl}

            with YoutubeDL(full_opts) as ydl:
                ydl.download(completed_urls)
                self.completed_seasons.append(idx + 1)

            print(f"Pausing for {self.pause_time} between seasons")
            time.sleep(self.pause_time)


class NFLWeeklyDownloader(BaseDownloader, NFLBaseIE):
    """
    A YoutubeDL wrapper that leverages the NFL tools included with yt-dlp.
    The class (especially authentication + authorization) is a bit messy
    due to its custom nature. This can certainly be cleaned up.

    ivar _api_base_url: str - The base URL of the NFL's data API, i.e. not its auth API
    ivar _replay_base_url: str - The base URL of game replays.

    """

    def __init__(
        self,
        cookie_file_path: Union[str, Path],
        destination_dir: Union[str, Path],
        add_yt_opts: Optional[Dict] = None,
    ) -> None:
        """
        Create the downloader; set its download and storage parameters

        :param cookie_file_path: The Netscape format cookies file used for auth.
        :type cookie_file_path: str | Path

        :param destination_dir: The directory to store the replays in.
            This needs some tweaking in order to properly handle different replay types.
        :type destination_dir: str | Path

        :param add_yt_opts: Any yt-dlp options that should override the base options,
            and apply to all download invocations by this object.
        :type add_yt_opts: Dict | None
        """
        super().__init__(cookie_file_path, destination_dir, add_yt_opts)
        self._api_base_url = "https://api.nfl.com/football/v2/"
        self._replay_base_url = "https://www.nfl.com/plus/games/"
        # self.headers = self._construct_headers()
        self._fbdl_get_account_info()

    def _initialize_cookies(self, browser: str = "firefox") -> Any:
        """
        Setup the relevant cookies based on the provided browser.

        :param browser: Only implementing firefox for now.
        :type browser: str
        """
        browser_specification = (browser, self.cookie_file_path)
        browser_name, profile, keyring, container = _parse_browser_specification(
            *browser_specification
        )
        cookies = extract_cookies_from_browser(
            browser_name=browser_name,
            profile=profile,
            logger=logger,
            keyring=keyring,
            container=container,
        )
        return cookies.get_cookies_for_url("https://auth-id.nfl.com/")

    def _fbdl_get_auth_token(self) -> None:
        """
        A custom method to get an auth token. The _fbdl prefix of the method name is necessary because
        the naming collision results in the parent class' version being called, and it fails.
        """
        if self._TOKEN and self._TOKEN_EXPIRY > int(time.time() + 30):
            return

        token_url = "https://api.nfl.com/identity/v3/token"
        if self._ACCOUNT_INFO.get("refreshToken"):
            token_url += "/refresh"

        token_request_data = json.dumps(
            {**self._CLIENT_DATA, **self._ACCOUNT_INFO}, separators=(",", ":")
        ).encode()
        response = requests.post(
            token_url,
            headers={"Content-Type": "application/json"},
            data=token_request_data,
        )
        response.raise_for_status()
        token = response.json()

        self._TOKEN = token["accessToken"]
        self._TOKEN_EXPIRY = token["expiresIn"]
        self._ACCOUNT_INFO["refreshToken"] = token["refreshToken"]

    def _fbdl_get_account_info(self) -> None:
        """
        A custom method to get and store account info. The _fbdl prefix of the method name is necessary because
        the naming collision results in the parent class' version being called, and it fails.
        """
        nfl_cookies = self._initialize_cookies()
        login_token = traverse_obj(
            nfl_cookies,
            (
                (f"glt_{self._API_KEY}", lambda k, _: k.startswith("glt_")),
                {lambda x: x.value},
            ),
            get_all=False,
        )
        account = requests.post(
            "https://auth-id.nfl.com/accounts.getAccountInfo",
            data=urlencode_postdata(
                {
                    "include": "profile,data",
                    "lang": "en",
                    "APIKey": self._API_KEY,
                    "sdk": "js_latest",
                    "login_token": login_token,
                    "authMode": "cookie",
                    "pageURL": "https://www.nfl.com/",
                    "sdkBuild": traverse_obj(
                        nfl_cookies,
                        ("gig_canary_ver", {lambda x: x.value.partition("-")[0]}),
                        default="15170",
                    ),
                    "format": "json",
                }
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        self._ACCOUNT_INFO = traverse_obj(
            account,
            {
                "signatureTimestamp": "signatureTimestamp",
                "uid": "UID",
                "uidSignature": "UIDSignature",
            },
        )

    @property
    def _headers(self) -> Dict[str, str]:
        """
        Headers to be used in HTTP requests.
        :return:
        """
        self._fbdl_get_auth_token()
        return {
            "Authorization": f"Bearer {self._TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_games_for_week(
        self, season: int, week: int, season_type: str = "REG"
    ) -> Dict:
        """
        Get the list of games played during the given season and week.

        :param season: The season we're fetching games for.
        :type season: int

        :param week: The week number to fetch games for.
        :type week: int

        :param season_type: Currently only 'REG' is implemented.

        :returns: The response JSON from the NFL's API
        :rtype: Dict
        """
        weekly_endpoint = f"{self._api_base_url}experience/weekly-game-details"
        params = {
            "includeReplays": True,
            "includeStandings": False,
            "season": season,
            "type": season_type,
            "week": week,
        }
        response = requests.get(weekly_endpoint, headers=self._headers, params=params)
        response.raise_for_status()

        return response.json()

    def extract_game_info(
        self, game: Dict, replay_types: Optional[List] = None
    ) -> Dict:
        """
        Extract only the information relevant to downloading and storing the replays properly.

        :param game: A dict containing all the information about a given game returned by the NFL's API
        :type game: Dict

        :param replay_types: Which replay type(s) to grab the necessary information for.
            Must be one of 'full', 'condensed', or 'all_22'.
            (Currently I actually use the pretty string because it's a bit easier in some ways).
        :type replay_types: List[str]

        :returns: A dict containing only the relevant information.
        :rtype: Dict
        """
        fields = ["season", "week", "weekType", "date"]
        game_info = {key: value for key, value in game.items() if key in fields}
        game_info["homeTeam"] = game["homeTeam"]["fullName"]
        game_info["awayTeam"] = game["awayTeam"]["fullName"]
        game_info["divider"] = "vs" if game["neutralSite"] else "at"

        for ex_id in game["externalIds"]:
            if ex_id["source"] == "slug":
                game_info["slug"] = ex_id["id"]

        if not replay_types:
            replay_types = DEFAULT_REPLAY_TYPES.values()

        game_info["replays"] = {}
        for replay in game["replays"]:
            subType = replay["subType"]

            if subType in replay_types:
                game_info["replays"][subType] = {
                    "mcpPlaybackId": replay["mcpPlaybackId"],
                    "thumbnailUrl": replay["thumbnail"].get("thumbnailUrl"),
                }

                game_info["replays"][subType]["url"] = self._construct_replay_url(
                    game_info, subType
                )

        return game_info

    def construct_metadata_for_game(
        self, game: Dict, replay_type: str, ep_num: int
    ) -> str:
        """
        Given information about the game, construct the XML string that
        will be stored in the related nfo file for Plex/Jellyfin parsing.

        :param game: The game's information.
        :type game: Dict

        :param replay_type: Which replay type we're creating the metadata for.
        :type replay_type: str

        :param ep_num: The 'episode number' to assign to the replay. In practice this ends up being
            the game's placement amongst all games played in the entire season.
            e.g. The 87th game played in the NFL season will be 87.
        :return: A string containing XML information that defines the metadata Jellyfin wants.
        :rtype: str
        """
        title = (
            f"{game['season']} Week {game['week']} - ({replay_type})"
            f"{game['awayTeam']} {game['divider']} {game['homeTeam']}"
        )

        return (
            f"<episodedetails>\n"
            f"\t<title>{title}</title>\n"
            f"\t<season>{game['season']}</season>\n"
            f"\t<episode>{ep_num}</episode>\n"
            f"\t<aired>{game['date']}</aired>\n"
            f"</episodedetails>"
        )

    def write_metadata_file(self, game: Dict, replay_type: str, ep_num: int) -> None:
        """
        Construct metadata for the given game and store it in an nfo file.

        :param game: The game to create metadata for.
        :type game: Dict

        :param replay_type: The replay type of the video we're creating metadata for.
        :type replay_type: str

        :param ep_num: The position of this game in the sequence of all NFL games played in the season
        :type ep_num: int
        """
        file_stem = self.construct_file_name(
            game=game, replay_type=replay_type, ep_num=ep_num
        )
        nfo_file = Path(self.destination_dir, f"{file_stem}.nfo")
        xml_string = self.construct_metadata_for_game(
            game=game, replay_type=replay_type, ep_num=ep_num
        )
        nfo_file.write_text(xml_string)

    def _construct_replay_url(self, game: Dict, replay_type: str) -> str:
        """
        Simple helper method to construct the URL yt-dlp should use to extract the video file.

        :param game: Data for the game we're working on.
        :type game: Dict

        :param replay_type: The type of replay we want to download/
        :type replay_type: str

        :return: The full URL of the game replay.
        :rtype: str
        """
        return f"{self._replay_base_url}{game['slug']}?mcpid={game['replays'][replay_type]['mcpPlaybackId']}"

    def construct_file_name(self, game: Dict, replay_type: str, ep_num: int) -> str:
        """
        Create the video file's name according to the established format.

        :param game: Data for the game we're working on.
        :type game: Dict

        :param replay_type: The replay type we're currently storing.
        :type replay_type: str

        :param ep_num: The position of this game in the sequence of all NFL games played in the season.
        :type ep_num: int

        :return: The stem to be used in the video file's name.
        :rtype: str
        """
        print(f"Constructing file name for {game['slug']}")

        away_city = " ".join(game["awayTeam"].split(" ")[:-1])
        home_city = " ".join(game["homeTeam"].split(" ")[:-1])

        if "Jets" in game["awayTeam"] or "Chargers" in game["awayTeam"]:
            away_city += " (A)"
        elif "Giants" in game["awayTeam"] or "Rams" in game["awayTeam"]:
            away_city += " (N)"

        if "Jets" in game["homeTeam"] or "Chargers" in game["homeTeam"]:
            home_city += " (A)"
        elif "Giants" in game["homeTeam"] or "Rams" in game["homeTeam"]:
            home_city += " (N)"

        away_tm = CITY_TO_ABBR[away_city]
        home_tm = CITY_TO_ABBR[home_city]
        return (
            f"NFL {replay_type} - "
            f"s{game['season']}e{str(ep_num).zfill(3)} - "
            f"{game['season']}_Wk{str(game['week']).zfill(2)}_"
            f"{away_tm}_{game['divider']}_{home_tm}"
        )

    def get_and_extract_games_for_week(
        self, season: int, week: int, replay_types: List[str]
    ) -> List[Dict]:
        """
        Combine the tasks of 1.) Fetching the list of games, 2.) Extracting the info we care about.

        :param season: The season we're downloading replays for.
        :type season: int

        :param week: The week number we're downloading replays for.
        :type week: int

        :param replay_types: A list of the replay types we want to download.
        :type replay_types: List[str]

        :return: A list of dict objects containing only the information we need in order to download replays.
        :rtype: List[Dict]
        """
        print(f"Downloading {replay_types} for {season} week {week}")
        raw_games_list = self.get_games_for_week(season=season, week=week)
        print(f"Found {len(raw_games_list)} games for week {week}")
        return [
            self.extract_game_info(game=game, replay_types=replay_types)
            for game in raw_games_list
        ]

    def download_game(self, game: Dict, ep_num: int) -> None:
        """
        Download all the replay types we specified for this game.

        :param game: Data for the game we're downloading.
        :type game: Dict

        :param ep_num: The position of this game in the sequence of all NFL games played in the season.
        :type ep_num: int
        """
        for replay_type, info in game["replays"].items():
            print(f"Replay type: {replay_type}")
            file_name = self.construct_file_name(game, replay_type, ep_num)
            outtmpl = Path(self.destination_dir, file_name)

            outtmpl = f"{outtmpl}.%(ext)s"
            print(f"Output path: {outtmpl}")
            self.base_yt_opts["outtmpl"] = str(outtmpl)

            with YoutubeDL(self.base_yt_opts) as ydl:
                ydl.download(info["url"])

            self.write_metadata_file(game=game, replay_type=replay_type, ep_num=ep_num)

    def download_all_for_week(
        self,
        season: int,
        week: int,
        replay_types: List[str],
        sleep_time: int = 15,
        start_ep: int = 0,
    ) -> None:
        """
        Combine the tasks of
            1.) Fetching the list of games,
            2.) Extracting their information, and
            3.) Downloading the replays

        :param season: The season we're downloading games for.
        :type season: int

        :param week: The week we're downloading games for.
        :type week: int

        :param replay_types: The list of replay types we want to download.
        :type replay_types: List[str]

        :param sleep_time: The number of seconds to wait between downloads.
        :type sleep_time: int
        """
        extracted_games = self.get_and_extract_games_for_week(
            season=season, week=week, replay_types=replay_types
        )

        for idx, game in enumerate(extracted_games):
            ep_num = start_ep + idx + 1
            if ep_num in [17, 18]:
                print("Already downloaded this game, skipping.")
                continue

            self.download_game(game=game, ep_num=ep_num)
            print(f"Downloaded {idx + 1}/{len(extracted_games)}")
            print(f"Pausing for {sleep_time} seconds")
            time.sleep(sleep_time)


@dataclass
class MetaDataCreator:
    """
    Create and store metadata based on information stored in file name.
    Used for replays downloaded before NFLWeeklyDownloader was implemented.
    """

    # season_premieres: Dict

    def __init__(self, base_dir: Union[str, Path], game_dates: Dict) -> None:
        """
        Initialize the utility, set basic config.

        :param base_dir: The directory containing the videos to generate metadata for.
        :type base_dir: str | Path

        :param game_dates: A dict mapping seasons to a dict of week numbers -> date the game was played on.
        :type game_dates: Dict
        """
        self.base_dir = base_dir
        self.game_dates = game_dates

    def _create_title_string(self, file_stem: str) -> str:
        """
        Given the file name, create the title that should be displayed in viewing clients.

        :param file_stem: The file's base name.
        :type file_stem: str

        :return: The name to be stored in metadata.
        :rtype: str
        """
        # file_stem will be something like "2024_Wk01_PIT_at_ATL"
        base_name = file_stem.split(" - ")[-1]
        parts = base_name.split("_")

        year = parts[0]
        week = parts[1]

        week_repr = get_week_int_as_string(week, int(year))
        if suffix := is_playoff_week(week):
            week_repr += f" {suffix}"

        team_one_abbr = parts[2]
        team_two_abbr = parts[4]

        team_one_city = abbreviation_map.get(team_one_abbr)
        if team_one_city is None:
            raise ValueError(
                f"Could not find team {team_one_abbr} in abbreviation map."
            )

        team_two_city = abbreviation_map.get(team_two_abbr)
        if team_two_city is None:
            raise ValueError(
                f"Could not find team {team_two_city} in abbreviation map."
            )

        # parts[3] is either "at" (for any game _not_ at a neutral site)
        # or "vs" (for neutral site games, i.e. the Super Bowl)
        return f"{year} Week {week_repr} - {team_one_city} {parts[3]} {team_two_city}"

    def create_nfo_for_season(self, year: int) -> None:
        """
        Create metadata files for all games in the provided year

        :param year: The year to create metadata for.
        :type year: int
        """
        season_dir = Path(self.base_dir, f"Season {year}")
        if not season_dir.exists():
            raise FileNotFoundError(f"{season_dir} does not exist.")

        for game in season_dir.rglob("*.mp4"):
            game_stem = game.stem
            nfo_file = Path(season_dir, f"{game_stem}.nfo")
            print(f"Creating {nfo_file}")
            nfo_file.touch()
            title = self._create_title_string(game_stem)

            episode_num = game_stem.split("-")[1].split("e")[-1].strip()

            aired = self.game_dates[str(year)][episode_num.lstrip("0")]

            xml_str = (
                f"<episodedetails>\n"
                f"\t<title>{title}</title>\n"
                f"\t<season>{year}</season>\n"
                f"\t<episode>{episode_num.lstrip("0")}</episode>\n"
                f"\t<aired>{aired}</aired>\n"
                f"</episodedetails>"
            )
            nfo_file.write_text(xml_str)

    def rename_files_for_season(self, year: int) -> None:
        """
        Add the necessary prefix to file names so that Jellyfin will parse
        the game replays as TV seasons.

        :param year: The season to rename video files for.
        :type year: int
        """
        season_dir = Path(self.base_dir, f"Season {year}")
        for f in season_dir.rglob(f"{year}*"):
            old_name = f.name
            week_substring = f.stem.split("_")[1]
            episode_number = "".join([c for c in week_substring if c.isdigit()])
            new_filename = (
                f"NFL Games - s{year}e{episode_number.zfill(3)} - {f.stem}{f.suffix}"
            )
            new_path = f.with_name(new_filename)
            f.replace(new_path)
            print(f"Moved {old_name} -> {f.name}")
