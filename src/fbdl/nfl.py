import json
import time

from dataclasses import dataclass
from pathlib import Path
from typing import Dict
from yt_dlp import YoutubeDL

from .base import (
    MEDIA_BASE_DIR,
    abbreviation_map,
    is_playoff_week,
    get_week_int_as_string,
    BaseDownloader,
)


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


class NFLWeeklyDownloader(BaseDownloader):
    pass


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
