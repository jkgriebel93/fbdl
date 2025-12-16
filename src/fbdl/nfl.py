import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from griddy.nfl import GriddyNFL
from griddy.nfl.models import WeeklyGameDetail
from yt_dlp import YoutubeDL
from yt_dlp.extractor.nfl import NFLBaseIE

from .base import (
    CITY_TO_ABBR,
    DEFAULT_REPLAY_TYPES,
    MEDIA_BASE_DIR,
    TEAM_FULL_NAMES,
    BaseDownloader,
    abbreviation_map,
    get_week_int_as_string,
    is_playoff_week,
)

logger = logging.getLogger(__name__)


class NFLShowDownloader:
    """
    A wrapper around YoutubeDL that specializes in downloading TV Series available on NFL Plus.
    TODO: This class requires a lot of work to leverage yt-dlp fully.
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

    var _replay_base_url: str - The base URL of game replays.

    """

    def __init__(
        self,
        firefox_profile_path: Union[str, Path],
        cookie_file_path: Union[str, Path],
        destination_dir: Union[str, Path],
        add_yt_opts: Optional[Dict] = None,
    ) -> None:
        """
        Create the downloader; set its download and storage parameters

        :param firefox_profile_path: Path to the user's Firefox profile.
            This is needed because yt_dlp doesn't work with a raw cookies file.
        :type firefox_profile_path: str | Path

        :param cookie_file_path: The Netscape format cookies file used for auth.
        :type cookie_file_path: str | Path

        :param destination_dir: The directory to store the replays in.
            This needs some tweaking in order to properly handle different replay types.
        :type destination_dir: str | Path

        :param add_yt_opts: Any yt-dlp options that should override the base options,
            and apply to all download invocations by this object.
        :type add_yt_opts: Dict | None
        """
        super().__init__(firefox_profile_path, destination_dir, add_yt_opts)
        self._replay_base_url = "https://www.nfl.com/plus/games/"
        self.nfl_client = GriddyNFL(cookies_file=str(cookie_file_path))

    def _should_extract(self, game: WeeklyGameDetail, teams: List[str]) -> bool:
        """
        Determine whether we should proceed with extracting this game.

        :param game: The (parsed) game JSON returned by the NFL API.
        :type game: Dict

        :param teams: A list of teams that games should be extracted for. Values are expected to be abbreviations.
        :type teams: List[str]

        :return: A boolean indicating yes or no.
        :rtype: bool
        """
        if teams == ["all"]:
            return True

        game_participants = [game.home_team.full_name, game.away_team.full_name]

        for team in teams:
            if TEAM_FULL_NAMES[team.upper()] in game_participants:
                return True

        return False

    def extract_game_info(
        self, game: WeeklyGameDetail, replay_types: Optional[List] = None
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
        fields = ["season", "week", "week_type", "date_"]

        game_info = {attr: getattr(game, attr) for attr in fields}
        game_info["homeTeam"] = game.home_team.full_name
        game_info["awayTeam"] = game.away_team.full_name
        game_info["divider"] = "vs" if game.neutral_site else "at"

        for ex_id in game.external_ids:
            if ex_id.source == "slug":
                game_info["slug"] = ex_id.id

        if not replay_types:
            replay_types = DEFAULT_REPLAY_TYPES.values()

        game_info["replays"] = {}
        for replay in game.replays:
            subType = replay.sub_type

            if subType in replay_types:
                game_info["replays"][subType] = {
                    "mcpPlaybackId": replay.mcp_playback_id,
                    "thumbnailUrl": replay.thumbnail.get("thumbnailUrl"),
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
            f"{game['season']} Week {game['week']} - ({replay_type}) "
            f"{game['awayTeam']} {game['divider']} {game['homeTeam']}"
        )

        return (
            f"<episodedetails>\n"
            f"\t<title>{title}</title>\n"
            f"\t<season>{game['season']}</season>\n"
            f"\t<episode>{ep_num}</episode>\n"
            f"\t<aired>{game['date_']}</aired>\n"
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
        self,
        season: int,
        week: int,
        teams: Optional[List[str]] = None,
        replay_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Combine the tasks of 1.) Fetching the list of games, 2.) Extracting the info we care about.

        :param season: The season we're downloading replays for.
        :type season: int

        :param week: The week number we're downloading replays for.
        :type week: int

        :param teams: Only extract games involving these teams. If None, download all games.
        :type teams: Optional[List[str]]

        :param replay_types: A list of the replay types we want to download. If None, download all replay types.
        :type replay_types: Optional[List[str]]

        :return: A list of dict objects containing only the information we need in order to download replays.
        :rtype: List[Dict]
        """
        print(f"Downloading {replay_types} for {season} week {week}")
        raw_games_list = self.nfl_client.football.get_weekly_game_details(
            season=season, type_="REG", week=week, include_replays=True
        )
        print(f"Found {len(raw_games_list)} games for week {week}")

        if not teams:
            teams = ["all"]

        extracted_games = []
        for game in raw_games_list:
            if self._should_extract(game=game, teams=teams):
                extracted_games.append(
                    self.extract_game_info(game=game, replay_types=replay_types)
                )

        return extracted_games

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
        teams: Optional[List[str]] = None,
        replay_types: Optional[List[str]] = None,
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

        :param teams: A list of teams to extract games for. Should be a list of abbreviations.
        :type teams: Optional[List[str]]

        :param replay_types: The list of replay types we want to download.
        :type replay_types: Optional[List[str]]

        :param sleep_time: The number of seconds to wait between downloads.
        :type sleep_time: int

        :param start_ep: The number to start episode labeling with.
        :type start_ep: int
        """
        extracted_games = self.get_and_extract_games_for_week(
            season=season, week=week, teams=teams, replay_types=replay_types
        )

        for idx, game in enumerate(extracted_games):
            ep_num = start_ep + idx + 1

            self.download_game(game=game, ep_num=ep_num)
            print(f"Downloaded {idx + 1}/{len(extracted_games)}")
            print(f"Pausing for {sleep_time} seconds")
            time.sleep(sleep_time)
