import ffmpeg
import os

from pathlib import Path
from typing import Optional, Union

from mutagen.mp4 import MP4
from yt_dlp import YoutubeDL

MEDIA_BASE_DIR = os.getenv("MEDIA_BASE_DIR")
abbreviation_map = {
                    "PIT": "Pittsburgh",
                    "CLE": "Cleveland",
                    "CIN": "Cincinatti",
                    "BAL": "Baltimore",
                    "IND": "Indianapolis",
                    "HOU": "Houston",
                    "JAX": "Jacksonville",
                    "TEN": "Tennessee",
                    "NWE": "New England",
                    "NYJ": "New York (A)",
                    "MIA": "Miami",
                    "BUF": "Buffalo",
                    "KAN": "Kansas City",
                    "KC": "Kansas City",
                    "OAK": "Oakland",
                    "LV": "Las Vegas",
                    "LVR": "Las Vegas",
                    "DEN": "Denver",
                    "SD": "San Diego",
                    "SDG": "San Diego",
                    "LAC": "Los Angeles (A)",
                    "GNB": "Green Bay",
                    "GB": "Green Bay",
                    "MIN": "Minnesota",
                    "DET": "Detroit",
                    "CHI": "Chicago",
                    "TAM": "Tampa Bay",
                    "TB": "Tampa Bay",
                    "CAR": "Carolina",
                    "ATL": "Atlanta",
                    "NO": "New Orleans",
                    "NOR": "New Orleans",
                    "NYG": "New York (N)",
                    "WAS": "Washington",
                    "DAL": "Dallas",
                    "PHI": "Philadelphia",
                    "ARI": "Arizona",
                    "ARZ": "Arizona",
                    "LAR": "Los Angeles (N)",
                    "STL": "St. Louis",
                    "SEA": "Seattle",
                    "SF": "San Francisco",
                    "SFO": "San Francisco",
                    "RAM": "Los Angeles (N)",
                    "RAI": "Los Angeles Raiders",
                    "PHO": "Phoenix",
                    # CFL
                    "MON": "Montreal",
                    "MTL": "Montreal",
                    "HAM": "Hamilton",
                    "CGY": "Calgary",
                    "TOR": "Toronto",
                    "SSK": "Saskatchewan",
                    "BC": "British Columbia",
                    "OTT": "Ottawa",
                    "WPG": "Winnipeg",
                    "EDM": "Edmonton",
                    # UFL
                    "DC": "Washington DC",
                    "ARL": "Arlington",
                    "SA": "San Antonio",
                    "BHM": "Birmingham",
                    "BHAM": "Birminghame",
                    "MICH": "Michigan",
                    "MEM": "Memphis"
                }


class FileOperationsUtil:
    def __init__(self, directory_path: Path, pretend: bool = False, verbose: bool = False):
        self.directory_path = Path(directory_path)
        self.pretend = pretend
        self.verbose = verbose

    def _log_var(self, name, var):
        if self.verbose:
            print(f"{name} {var}")
            print(f"Type: {type(var)}")

    def update_mp4_title_from_filename(self, file_obj: Path):
        if self.pretend:
            print("Pretend flag was passed. Will not save updates.")

        print(f"Updating metadata for games in {self.directory_path}")

        print(f"Working on {file_obj.name}")

        try:
            audio = MP4(file_obj)

            # Get the filename without extension
            base_name = file_obj.name.split(".")[0]
            self._log_var("Base Name", base_name)

            name_parts = base_name.split("_")
            self._log_var("Name Parts", name_parts)

            year = name_parts[0]
            self._log_var("Year", year)

            away_city = abbreviation_map[name_parts[2]]
            home_city = abbreviation_map[name_parts[4]]
            at_vs = "vs" if "SB" in name_parts[1] else "at"

            self._log_var("@ or vs", at_vs)

            new_name = f"{year} {name_parts[1]} - {away_city} {at_vs} {home_city}"
            self._log_var("New name", new_name)

            audio["\xa9nam"] = new_name  # Tags are often lists in MP4
            audio["\xa9day"] = year

            if not self.pretend:
                print("Saving file.")
                audio.save()

            print(f"Updated title for '{file_obj.name}' to: '{new_name}'")
        except Exception as e:
            print(f"Error processing '{file_obj.name}': {e}")
            raise e

    def iter_and_update_children(self):
        for item in self.directory_path.rglob("*.mp4"):
            self.update_mp4_title_from_filename(item)

    def convert_formats(self,
                        orig_format: str = "mkv",
                        new_format: str = "mp4",
                        delete: bool = False):
        for mkv_file in self.directory_path.rglob(f"*.{orig_format}"):
            stream = ffmpeg.input(str(mkv_file))
            output_path = str(mkv_file.with_suffix(f".{new_format}"))
            stream = ffmpeg.output(stream,
                                   output_path,
                                   vcodec="copy",
                                   acodec="copy",
                                   format="mp4")
            if self.pretend:
                log_str = f"Would convert {mkv_file} to {output_path}."
                if delete:
                    log_str += f"\nWould delete {mkv_file} as well."
                print(log_str)
            else:
                print(f"Converting {mkv_file} to {output_path}")
                ffmpeg.run(stream)
                if delete:
                    print(f"Deleting {mkv_file}.")
                    mkv_file.unlink()


class BaseDownloader:
    def __init__(self,
                 cookie_file_path: Optional[Union[str, Path]],
                 destination_dir: str,
                 add_yt_opts: dict = None):
        self.cookie_file_path = cookie_file_path
        self.base_yt_opts = {
            "cookiefile": self.cookie_file_path,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            "merge_output_format": "mp4",
            "concurrent_fragment_downloads": 1,
            "writethumbnail": True,
            "embedthumbnail": True,
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
        if add_yt_opts:
            self.base_yt_opts.update(add_yt_opts)
        self.destination_dir = Path(destination_dir)

    def download_from_file(self,
                           input_file: Path,
                           dlp_overrides: dict = None):
        print(f"Downloading files from {input_file.name}")
        urls = input_file.read_text().splitlines()
        output_template = str(self.destination_dir / "%(title)s.%(ext)s")
        overridden_opts = {
            **self.base_yt_opts,
            "outtmpl": output_template,
        }
        if dlp_overrides:
            overridden_opts.update(dlp_overrides)

        with YoutubeDL(overridden_opts) as ydl:
            ydl.download(urls)
