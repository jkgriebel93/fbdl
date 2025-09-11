import ffmpeg
import os
import re

from pathlib import Path
from typing import Optional, Union

from mutagen.mp4 import MP4
from yt_dlp import YoutubeDL

MEDIA_BASE_DIR = os.getenv("MEDIA_BASE_DIR")
abbreviation_map = {
    "PIT": "Pittsburgh",
    "CLE": "Cleveland",
    "CIN": "Cincinnati",
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
    "MEM": "Memphis",
}

CITY_TO_ABBR = {city: abbr for abbr, city in abbreviation_map.items()}

DEFAULT_REPLAY_TYPES = ["Full Game", "All-22", "Condensed Game"]


def is_playoff_week(week_str: str) -> str:
    for week_type in ["wc", "div", "conf", "sb"]:
        if week_type in week_str.lower():
            match week_type:
                case "wc":
                    return "Wild Card"
                case "div":
                    return "Divisional"
                case "conf":
                    return "Conference Championship"
                case "uflchamp":
                    return "UFL Championship"
                case "sb":
                    sb_num = week_str.lower().split("sb")[-1]
                    return f"Super Bowl {sb_num.upper()}"
                case _:
                    return ""
    return ""


def convert_nfl_playoff_name_to_int(year: int, week_name: str) -> int:
    num = None
    if year < 1978:
        # Through 1997: 14 week schedule, no bye week, no wildcard
        if week_name == "Divisional":
            num = 15
        elif week_name == "Conference Championship":
            num = 16
        elif "Super Bowl" in week_name:
            num = 17

    elif year < 1990:
        # 1978 - 1989: 16 week schedule, no bye week, wildcard round
        if week_name == "Wild Card":
            num = 17
        elif week_name == "Divisional":
            num = 18
        elif week_name == "Conference Championship":
            num = 19
        elif "Super Bowl" in week_name:
            num = 20
    elif year == 1993 or year > 2020:
        # 1993: 18 week schedule, two bye weeks (16 games), wildcard round
        # 2021 - Current: 18 week schedule (17 games), wildcard round, results in
        # Same numbering as 1993
        if week_name == "Wild Card":
            num = 19
        elif week_name == "Divisional":
            num = 20
        elif week_name == "Conference Championship":
            num = 21
        elif "Super Bowl" in week_name:
            num = 22
    elif year < 2021:
        # 1990 - 2020 (except 1993): 17 week schedule, one bye week, wildcard round
        if week_name == "Wild Card":
            num = 18
        elif week_name == "Divisional":
            num = 19
        elif week_name == "Conference Championship":
            num = 20
        elif "Super Bowl" in week_name:
            num = 21
    return num


def convert_ufl_playoff_name_to_int(year: int, week_name: str) -> int:
    # As of now, we don't need year because the UFL schedule hasn't changed
    # But it surely will, and probably soon
    num = None
    if week_name == "Conference Championship":
        num = 11
    elif week_name == "UFL Championship":
        num = 12
    return num


def get_week_int_as_string(
    week: str, year: int = None, is_ufl: bool = False
) -> Union[int, str]:
    if num := is_playoff_week(week):
        if is_ufl:
            num = convert_ufl_playoff_name_to_int(year, week_name=num)
        else:
            num = convert_nfl_playoff_name_to_int(year, week_name=num)

        return str(num)
    num = ""
    for c in week.lower().replace("wk", ""):
        if not c.isdigit():
            break
        num += c

    return num


class FileOperationsUtil:
    def __init__(
        self, directory_path: Path, pretend: bool = False, verbose: bool = False
    ):
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

    def convert_formats(
        self, orig_format: str = "mkv", new_format: str = "mp4", delete: bool = False
    ):
        for mkv_file in self.directory_path.rglob(f"*.{orig_format}"):
            stream = ffmpeg.input(str(mkv_file))
            output_path = str(mkv_file.with_suffix(f".{new_format}"))
            stream = ffmpeg.output(
                stream, output_path, vcodec="copy", acodec="copy", format="mp4"
            )
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

    def rename_files(self, series_name: str, replace: bool = False):
        # Regular expression to match the xyy-<Episode Name>.mp4 format
        pattern = r"^(\d{1})(\d{2,3})-(.+)\.mp4$"

        # Iterate through all subdirectories
        for file_path in self.directory_path.rglob("*.mp4"):
            # Check if file matches the expected pattern
            match = re.match(pattern, file_path.name)
            if match:
                season = match.group(1)  # Extract season number (x)
                episode = match.group(2)  # Extract episode number (yy)
                episode_name = match.group(3)  # Extract episode name

                new_filename = f"{series_name} - s{season.zfill(2)}e{episode.zfill(2)} - {episode_name}.mp4"
                new_file_path = file_path.with_name(new_filename)
                delete_ = new_file_path.exists()

                if self.pretend:
                    if delete_:
                        print(f"{new_filename} already exists, would be replaced.")
                    print(
                        f"Would rename {file_path.name} to {new_filename}."
                        f" --pretend was passed, so we will not attempt the operation."
                    )
                else:
                    if delete_ and not replace:
                        raise FileExistsError(
                            f"File {new_filename} already exists and replace is False"
                        )

                    print(f"Renaming {file_path.name} to {new_file_path.name}")
                    file_path.replace(new_file_path)
                    print("Success.")


class BaseDownloader:
    def __init__(
        self,
        cookie_file_path: Optional[Union[str, Path]],
        destination_dir: Optional[str] = None,
        add_yt_opts: dict = None,
    ):
        # self.cookie_file_path = cookie_file_path
        self.cookie_file_path = cookie_file_path
        self.base_yt_opts = {
            "cookiesfrombrowser": ("firefox", cookie_file_path),
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            "merge_output_format": "mp4",
            "concurrent_fragment_downloads": 1,
            # "writethumbnail": True,
            # "embedthumbnail": True,
            "addmetadata": True,
            "throttledratelimit": 1000000,
            "embedsubs": True,
            "writesubs": True,
            "subtitleslangs": ["en"],
        }
        if add_yt_opts:
            self.base_yt_opts.update(add_yt_opts)
        if destination_dir is None:
            destination_dir = os.getcwd()

        self.destination_dir = Path(destination_dir)

    def download_from_file(self, input_file: Path, dlp_overrides: dict = None):
        print(f"Downloading files from {input_file.name}")
        urls = input_file.read_text().splitlines()
        output_template = str(self.destination_dir / "%(title)s.%(ext)s")
        overridden_opts = {
            **self.base_yt_opts,
            "outtmpl": output_template,
        }
        if dlp_overrides:
            overridden_opts.update(dlp_overrides)
        from pprint import pprint

        pprint(overridden_opts, indent=4)
        with YoutubeDL(overridden_opts) as ydl:
            ydl.download(urls)


def is_bowl_game(orig_file):
    bowl_str = ""
    for named_game in [
        "SEC Championship ",
        "Orange Bowl ",
        "CFP Final ",
        "Peach Bowl CFP Semi-Final",
    ]:
        if named_game in orig_file.stem:
            bowl_str = named_game
            break
    return bowl_str


def transform_file_name(orig_file):
    stem = orig_file.stem.replace("UGA", "Georgia").replace("@", "at")

    if bowl_str := is_bowl_game(orig_file):
        stem = stem.replace(bowl_str, "")
        bowl_str = bowl_str.strip().replace(" ", "").replace("-Final", "")

    stem_parts = stem.split(" ")

    year = stem_parts[0]
    game_num = stem_parts[3]
    date = stem_parts[4]

    try:
        divider_index = stem_parts.index("at")
    except ValueError:
        divider_index = stem_parts.index("vs")

    divider = stem_parts[divider_index]

    team_one = "_".join(stem_parts[5:divider_index])
    team_two = "_".join(stem_parts[divider_index + 1 :])

    prefix = f"NCAA - s{year}e{game_num.zfill(2)}"

    game_str = f"{game_num.zfill(2)}{bowl_str}"
    new_stem = f"{prefix} - " f"{year}_Gm{game_str}_" f"{team_one}_{divider}_{team_two}"
    return new_stem
