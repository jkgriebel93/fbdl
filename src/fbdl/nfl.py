import json
import os
import time

from pathlib import Path
from yt_dlp import YoutubeDL
MEDIA_BASE_DIR = os.getenv("MEDIA_BASE_DIR")

class NFLShowDownloader:
    def __init__(self, episode_list_path: str, cookie_file_path: str, show_dir: str, pause_time: int = 30):
        self.base_url = "https://www.nfl.com/plus/episodes/"
        self.cookie_file_path = cookie_file_path
        self.pause_time = pause_time

        self.show_directory = Path(MEDIA_BASE_DIR, show_dir)
        self.show_directory.mkdir(parents=True, exist_ok=True)

        with open(episode_list_path, "r") as infile:
            self.episodes = json.load(infile)

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
        self.completed = ["christian-okoye", "dexter-manley", "jerome-bettis",
                          "terrell-owens", "alan-page", "steve-largent",
                          "dick-vermeil", "paul-brown", "mike-singletary",
                          "charles-haley", "bruce-arians", "dan-marino", "emmitt-smith", "jim-kelly", "sam-mills",
                          "wes-welker", "carson-palmer-x3229", "tony-romo", "dwight-clark", "brian-dawkins-x9863",
                          "nick-saban", "james-harrison"]
        self.errors = ["ladanian-tomlinson", "derrick-thomas", "matt-millen",
                       "sean-taylor", "marshall-faulk", "john-madden", "larry-fitzgerald",
                       "lawrence-taylor", "willie-mcginest", "bill-cowher", "mike-holmgren", "cris-collinsworth"]
        self.completed_seasons = [1, 2, 3, 4, 5, 6, 7, 8, 9]

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

            print(f"Pausing for {self.pause_time} between seasons")
            time.sleep(self.pause_time)