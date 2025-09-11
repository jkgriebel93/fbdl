import json
import logging
import time

import requests

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union, List
from yt_dlp import YoutubeDL
from yt_dlp.extractor.nfl import NFLBaseIE
from yt_dlp.cookies import load_cookies, _parse_browser_specification, extract_cookies_from_browser
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
    def __init__(
        self,
        episode_list_path: str,
        cookie_file_path: str,
        show_dir: str,
        pause_time: int = 30,
    ):
        self.base_url = "https://www.nfl.com/plus/episodes/"
        self.cookie_file_path = cookie_file_path
        self.pause_time = pause_time

        self.show_directory = Path(MEDIA_BASE_DIR, show_dir)
        self.show_directory.mkdir(parents=True, exist_ok=True)

        with open(episode_list_path, "r") as infile:
            data = json.load(infile)
            self.episodes = data["seasons"]

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

    def download_episodes(self):
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
    def __init__(self,
        cookie_file_path: Optional[Union[str, Path]],
        destination_dir: Union[str, Path],
        add_yt_opts: dict = None,
    ):
        super().__init__(cookie_file_path, destination_dir, add_yt_opts)
        self._api_base_url = "https://api.nfl.com/football/v2/"
        self._replay_base_url = "https://www.nfl.com/plus/games/"
        # self.headers = self._construct_headers()
        self._fbdl_get_account_info()

    def _initialize_cookies(self, browser: str = "firefox"):
        browser_specification = (browser, self.cookie_file_path)
        browser_name, profile, keyring, container = _parse_browser_specification(*browser_specification)
        cookies = extract_cookies_from_browser(browser_name=browser_name,
                                               profile=profile,
                                               logger=logger,
                                               keyring=keyring,
                                               container=container)
        return cookies.get_cookies_for_url("https://auth-id.nfl.com/")

    def _fbdl_get_auth_token(self):
        if self._TOKEN and self._TOKEN_EXPIRY > int(time.time() + 30):
            return

        token_url = "https://api.nfl.com/identity/v3/token"
        if self._ACCOUNT_INFO.get("refreshToken"):
            token_url += "/refresh"

        token_request_data = json.dumps({**self._CLIENT_DATA, **self._ACCOUNT_INFO}, separators=(',', ':')).encode()
        response = requests.post(token_url,
                                 headers={"Content-Type": "application/json"},
                                 data=token_request_data)
        response.raise_for_status()
        token = response.json()

        self._TOKEN = token["accessToken"]
        self._TOKEN_EXPIRY = token["expiresIn"]
        self._ACCOUNT_INFO["refreshToken"] = token["refreshToken"]

    def _fbdl_get_account_info(self):
        nfl_cookies = self._initialize_cookies()
        login_token = traverse_obj(nfl_cookies, (
            (f'glt_{self._API_KEY}', lambda k, _: k.startswith('glt_')), {lambda x: x.value}), get_all=False)
        account = requests.post(
            'https://auth-id.nfl.com/accounts.getAccountInfo',
            data=urlencode_postdata({
                'include': 'profile,data',
                'lang': 'en',
                'APIKey': self._API_KEY,
                'sdk': 'js_latest',
                'login_token': login_token,
                'authMode': 'cookie',
                'pageURL': 'https://www.nfl.com/',
                'sdkBuild': traverse_obj(nfl_cookies, (
                    'gig_canary_ver', {lambda x: x.value.partition('-')[0]}), default='15170'),
                'format': 'json',
            }),
            headers={'Content-Type': 'application/x-www-form-urlencoded'})

        self._ACCOUNT_INFO = traverse_obj(account, {
            'signatureTimestamp': 'signatureTimestamp',
            'uid': 'UID',
            'uidSignature': 'UIDSignature',
        })

    @property
    def _headers(self):
        self._fbdl_get_auth_token()
        return {
            "Authorization": f"Bearer {self._TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def get_games_for_week(self, season: int, week: int, season_type: str = "REG") -> Dict:

        weekly_endpoint = f"{self._api_base_url}experience/weekly-game-details"
        params = {
            "includeReplays": True,
            "includeStandings": False,
            "season": season,
            "type": season_type,
            "week": week
        }
        response = requests.get(weekly_endpoint, headers=self._headers, params=params)
        response.raise_for_status()

        return response.json()

    def extract_game_info(self, game: Dict, replay_types: Optional[List] = None) -> Dict:
        fields = ["season", "week", "weekType", "date"]
        game_info = {key: value for key, value in game.items() if key in fields}
        game_info["homeTeam"] = game["homeTeam"]["fullName"]
        game_info["awayTeam"] = game["awayTeam"]["fullName"]
        game_info["divider"] = "vs" if game["neutralSite"] else "at"

        for ex_id in game["externalIds"]:
            if ex_id["source"] == "slug":
                game_info["slug"] = ex_id["id"]

        if not replay_types:
            replay_types = DEFAULT_REPLAY_TYPES

        game_info["replays"] = {}
        for replay in game["replays"]:
            subType = replay["subType"]

            if subType in replay_types:
                game_info["replays"][subType] = {
                    "mcpPlaybackId": replay["mcpPlaybackId"],
                    "thumbnailUrl": replay["thumbnail"]["thumbnailUrl"]
                }

                game_info["replays"][subType]["url"] = self._construct_replay_url(game_info, subType)

        return game_info

    def construct_metadata_for_game(self, game: Dict, ep_num: int):
        divider = "vs" if game["neutralSite"] else "at"
        title = (f"{game['season']} Week {game['week']} - "
                 f"{game['awayTeam']} {divider} {game['homeTeam']}")

        return (
            f"<episodedetails>\n"
            f"\t<title>{title}</title>\n"
            f"\t<season>{game['season']}</season>\n"
            f"\t<episode>{ep_num}</episode>\n"
            f"\t<aired>{game['date']}</aired>\n"
            f"</episodedetails>"
        )

    def _construct_replay_url(self, game, replay_type):
        try:
            url = f"{self._replay_base_url}{game['slug']}?mcpid={game['replays'][replay_type]['mcpPlaybackId']}"
            return url
        except KeyError as e:
            with open("error_file.json", "w") as outfile:
                json.dump(game, outfile, indent=4)
            raise e

    def construct_file_name(self, game, replay_type, ep_num):
        print(f"Constructing file name for {game['slug']}")

        away_tm = CITY_TO_ABBR[game["awayTeam"].split(" ")[0]]
        home_tm = CITY_TO_ABBR[game["homeTeam"].split(" ")[0]]
        return (f"NFL {replay_type} - "
                       f"s{game['season']}e{str(ep_num).zfill(3)} - "
                       f"{game['season']}_Wk{str(game['week']).zfill(2)}_"
                       f"{away_tm}_{game['divider']}_{home_tm}")

    def download_game(self, game: Dict, ep_num: int):
        for replay_type, info in game["replays"].items():
            file_name = self.construct_file_name(game, replay_type, ep_num)
            outtmpl = Path(self.destination_dir, file_name)

            outtmpl = f"{outtmpl}.%(ext)s"
            print(f"Output path: {outtmpl}")

            self.base_yt_opts["outtmpl"] = str(outtmpl)

            with YoutubeDL(self.base_yt_opts) as ydl:
                ydl.download(info["url"])

    def download_all_for_week(self, season: int, week: int, replay_types: List[str], sleep_time: int = 15):
        print(f"Downloading {replay_types} for {season} week {week}")
        raw_games_list = self.get_games_for_week(season=season,
                                                 week=week)
        print(f"Found {len(raw_games_list)} games for week {week}")
        extracted_games = [self.extract_game_info(game=game,
                                                  replay_types=replay_types)
                           for game in raw_games_list]

        for idx, game in enumerate(extracted_games):
            self.download_game(game=game, ep_num=idx + 1)
            print(f"Downloaded {idx + 1}/{len(extracted_games)}")
            print(f"Pausing for {sleep_time} seconds")
            time.sleep(sleep_time)





@dataclass
class MetaDataCreator:
    base_dir: Path
    # season_premieres: Dict
    game_dates: Dict

    def _create_title_string(self, file_stem):
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

    def create_nfo_for_season(self, year: int):
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

    def rename_files_for_season(self, year: int):
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
