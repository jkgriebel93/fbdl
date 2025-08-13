import json
import os
import requests
import time

from pathlib import Path

from bs4 import BeautifulSoup
from yt_dlp import YoutubeDL
MEDIA_BASE_DIR = os.getenv("MEDIA_BASE_DIR")

PLAYOFF_WEEK_NAMES = {
    "Wild Card": "WC",
    "Divisional": "Div",
    "Conference": "Conf"
}



class NFLShowDownloader:
    def __init__(self, episode_list_path: str, cookie_file_path: str, show_dir: str, pause_time: int = 30):
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
                }
            ],
            "embedsubs": True,
            "writesubs": True,
            "subtitleslangs": ["en"],
            "progress_hooks": [lambda d: print(f"Downloading {d['filename']}")
                                if d['status'] == 'downloading' else None]
        }
        self.completed = ["new-york-giants", "fastest-players", "career-finales", "draft-day-moments",
                          "playoff-finishes", "greatest-in-season-trades", "playoff-performances",
                          "free-agent-signings"]
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
            season_directory = self.show_directory / Path("Season " + str(idx + 1).zfill(2))
            season_directory.mkdir(parents=True, exist_ok=True)

            output_tmpl = str(season_directory / "%(title)s.%(ext)s")
            completed_urls = [f"{self.base_url}{ep}" for ep in season if ((ep not in self.completed) and (ep not in self.errors))]
            full_opts = {**self.base_yt_ops, "outtmpl": output_tmpl}

            with YoutubeDL(full_opts) as ydl:
                ydl.download(completed_urls)
                self.completed_seasons.append(idx + 1)

            print(f"Pausing for {self.pause_time} between seasons")
            time.sleep(self.pause_time)


class PFRScraper:
    def __init__(self):
        self.base_url = "https://www.pro-football-reference.com/"
        self.headers = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0",
                        "referrer": "https://www.pro-football-reference.com/"}

    def get_soup_for_url(self, url_suffix: str) -> BeautifulSoup:
        full_url = self.base_url + url_suffix
        response = requests.get(full_url, headers=self.headers)
        response.raise_for_status()
        return BeautifulSoup(response.content, "html.parser")

    def extract_games_for_season(self, team: str, season: int):
        suffix = f"teams/{team}/{season}.htm"
        soup = self.get_soup_for_url(suffix)

        table = soup.find("table", {"id": "games"})
        if not table:
            # TODO: Decide on a better exception class
            print(soup.prettify())
            raise Exception(f"Could not find table for season {season}")

        weeks = {}

        rows = table.find("tbody").find_all("tr")
        for row in rows:
            week_tag = row.find("th", {"data-stat": "week_num"})
            try:
                week_num = int(week_tag.get("csk"))
            except ValueError as e:
                print(f"The csk attribute for row {row.get('data-row')} could not cast to an int.")
                print(f"csk Value: {week_tag.get('csk')}\n"
                      f"Text: {week_tag.text}")
                continue


            date_tag = row.find("td", {"data-stat": "game_date"})

            week_str = f"Wk{str(week_num).zfill(2)}"
            if not week_tag.text.strip().isnumeric():
                print(f"Week {week_num} must be a playoff week.\n"
                      f"Value: {week_tag.text}")
                week_str += PLAYOFF_WEEK_NAMES[week_tag.text.strip()]

            weeks[week_num] = {
                "date": date_tag.get("csk"),
                "display_str": week_str
            }

        return weeks

