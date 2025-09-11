import ffmpeg
import os
import re

from pathlib import Path
from typing import Any, Optional, Union, Dict

from mutagen.mp4 import MP4
from yt_dlp import YoutubeDL

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
CONCURRENT_FRAGMENTS = os.getenv("CONCURRENT_FRAGMENTS", 1)
DEFAULT_REPLAY_TYPES = ["Full Game", "All-22", "Condensed Game"]
MEDIA_BASE_DIR = os.getenv("MEDIA_BASE_DIR")
THROTTLED_RATE_LIMIT = os.getenv("THROTTLED_RATE_LIMIT", 1000000)


def convert_nfl_playoff_name_to_int(year: int, week_name: str) -> int:
    """
    Given a season and week name, determine the week number of the game.

    :param year: The year during which the regular season associated with the postseason game was played.
    :type year: int
    :param week_name: The game's name. One of 'Wild Card', 'Divisional', 'Conference Championship', or 'Super Bowl'
    :type week_name: str
    :return: The week number that the named game was played during the provided season.
    """
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
    """
    Given a UFL season and a week name, determine the week number of the game.

    :param year: The year the game was played. Included for potential future schedule changes.
    :param week_name: The game's name. One of 'Conference Championship' or 'UFL Championship'
    :return:
    """
    num = None
    if week_name == "Conference Championship":
        num = 11
    elif week_name == "UFL Championship":
        num = 12
    return num


def get_week_int_as_string(
    week: str, year: int = None, is_ufl: bool = False
) -> Union[int, str]:
    """
    Given a week's name and a season, determine the week number of the game.

    :param week: The week name (e.g. 'Wild Card', 'Divisional', etc.)
    :type week: int
    :param year: The season that the game was played.
    :type year: int
    :param is_ufl: A flag used to specify which conversion function is uses.
    :type is_ufl: bool
    :return: A string, left padded to a length of 2, representing the week number of the game.
    rtype: str
    """
    if num := is_playoff_week(week):
        if is_ufl:
            num = convert_ufl_playoff_name_to_int(year, week_name=num)
        else:
            num = convert_nfl_playoff_name_to_int(year, week_name=num)

        return str(num).zfill(2)
    num = ""
    for c in week.lower().replace("wk", ""):
        if not c.isdigit():
            break
        num += c

    return num.zfill(2)


def is_bowl_game(orig_file: Path) -> str:
    """
    Given a (properly named) Path object, determine if it
    represents an NCAA bowl/playoff game and return the game's name.

    :param orig_file: The Path object for the video file we're inspecting.
    :type orig_file: Path
    :return: Either the empty string or the name of the bowl game.
    :rtype: str
    """
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


def is_playoff_week(week_str: str) -> str:
    """
    Given a short string that was stored alongside a week number in a file name,
    determine the corresponding pretty representation.
    :param week_str: The short string that was stored in the file name. One of 'wc', 'div', 'conf', 'uflchamp', or 'sb'
    :return: The title cased, full version of the week's name.
    :rtype: str
    """
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


def transform_file_name(orig_file: Path) -> str:
    """
    A specialized function that takes a file which follows the naming convention of a specific YouTube channel,
    and transforms the name to match our convention and play nice with Plex, Jellyfin, etc.
    :param orig_file: Path object representing the originally downloaded file.
    :type: orig_file: Path
    :return: The transformed file _stem_ as a string.
    :rtype: str
    """
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


class BaseDownloader:
    """
    A wrapper around YoutubeDL that allows for download a list of generic URLs stored in a file.
    """

    def __init__(
        self,
        cookie_file_path: Optional[Union[str, Path]] = None,
        destination_dir: Optional[Union[str, Path]] = None,
        add_yt_opts: Optional[Dict] = None,
    ) -> None:
        """
        Construct the BaseDownloader and store specification information to be passed to ydl.

        :param cookie_file_path: A Netscape formatted .txt file containing cookies to be used for authentication.
        :type cookie_file_path: str | Path | None

        :param destination_dir: The directory downloaded files should be stored in. Can be a string or a Path object.
        :type destination_dir: str | Path | None

        :param add_yt_opts: A dict of options to pass along to YoutubeDL in addition to the base parameters used by
            fbdl. The values passed in this parameter will supersede any base parameters, and can be overriden when
            download_from_file is invoked.
        :type add_yt_opts: Dict
        """
        self.cookie_file_path = cookie_file_path
        self.base_yt_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            "merge_output_format": "mp4",
            "concurrent_fragment_downloads": CONCURRENT_FRAGMENTS,
            "addmetadata": True,
            "throttledratelimit": THROTTLED_RATE_LIMIT,
            "embedsubs": True,
            "writesubs": True,
            "subtitleslangs": ["en"],
        }

        if self.cookie_file_path is not None:
            self.base_yt_opts["cookiefrombrowser"] = ("firefox", self.cookie_file_path)

        if add_yt_opts:
            self.base_yt_opts.update(add_yt_opts)

        if destination_dir is None:
            destination_dir = os.getcwd()

        if isinstance(destination_dir, str):
            destination_dir = Path(destination_dir)

        self.destination_dir = destination_dir

    def download_from_file(
        self, input_file: Path, dlp_overrides: Optional[Dict] = None
    ) -> None:
        """
        Use YoutubeDL to download the videos stored at each URL from input_file.

        :param input_file: The file where URLs are listed, one per line, to be downloaded.
        :type input_file: Path

        :param dlp_overrides: A dict storing YoutubeDL parameters to be used for this invocation of download_from_file
        :type dlp_overrides: Dict | None
        :return:
        """
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


class FileOperationsUtil:
    """
    A utility class for file operations such as renaming, converting, etc.
    """

    def __init__(
        self,
        directory_path: Union[str, Path],
        pretend: bool = False,
        verbose: bool = False,
    ) -> None:
        """
        Create a util object, storing the directory we will be working in.
            TODO: Is this really the right place for directory_path?

        :param directory_path: The directory containing the files on which we will be operating.
        :type directory_path: str | Path
        :param pretend: If True, only simulate operations.
        :type pretend: bool
        :param verbose: If True, enable verbose logging.
        :type verbose: bool
        """

        if isinstance(directory_path, str):
            directory_path = Path(directory_path)

        self.directory_path = directory_path
        self.pretend = pretend
        self.verbose = verbose

    def _log_var(self, name: str, var: Any) -> None:
        """
        Log (or print) the variable's name, and its string representation
        # TODO: Change this from print calls to logger invocations

        :param name: (Typically) the name of the object being logged.
        :type name: str
        :param var: The object to log.
        :type var: Any
        """

        if self.verbose:
            print(f"Variable: {name}")
            print(f"Value: {var}")

    def update_mp4_title_from_filename(self, file_obj: Path) -> None:
        """
        Using information stored in a mp4 file's name, update the title stored in its metadata

        :param file_obj: The file to update.
        :type file_obj: Path
        """
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

    def iter_and_update_children(self) -> None:
        """
        Update all mp4 files in the current directory and all its children.
        """
        for item in self.directory_path.rglob("*.mp4"):
            self.update_mp4_title_from_filename(item)

    def convert_formats(
        self, orig_format: str = "mkv", new_format: str = "mp4", delete: bool = False
    ) -> None:
        """
        Use ffmpeg to convert video files in self.directory_path from one format to another.

        :param orig_format: Convert all videos of this format
        :type orig_format: str

        :param new_format: The new format to store the videos in.
        :type new_format: str

        :param delete: If True, delete the original files of the old format.
        """
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

    def rename_files(self, series_name: str, replace: bool = False) -> None:
        """
        A specialized method to rename TV series episode files from the format
            XYY-<episode_name>.mp4 to <series_name> - sXXeYY - <episode_name>.mp4
            Where X is the episode season, and YY is the episode number within that season.

        :param series_name: Name of the TV series we should rename files for.
        :type series_name: str
        :param replace: If True, overwrite any files which happen to exist with the
            target name already.
        """
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
