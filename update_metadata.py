import argparse
import os

from mutagen.mp4 import MP4
parser = argparse.ArgumentParser(
    prog="UpdateMetadata",
    description="Script to update an MP4 file's 'Name' attribute so it displays correctly in Plex"
)
parser.add_argument("directory_path")
parser.add_argument("start_year")
parser.add_argument("end_year")
parser.add_argument("-p", "--pretend", action="store_true")
parser.add_argument("-v", "--verbose", action="store_true")
parser.add_argument("-c", "--cfl", action="store_true")

args = parser.parse_args()
verbose = args.verbose
start_year = int(args.start_year)
end_year = int(args.end_year)
is_cfl = args.cfl

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

                    # "Wk": "Week" # Example: to make "Wk01" into "Week 01"
                }


def log_var(name, var):
    if verbose:
        print(f"{name} {var}")
        print(f"Type: {type(var)}")


def update_mp4_title_from_filename(directory_path, pretend=False):
    if pretend:
        print("Pretend flag was passed. Will not save updates.")

    print(f"Updating metadata for games in {directory_path}")
    
    
    for filename in os.listdir(directory_path):
        if filename.lower().endswith(".mp4"):
            filepath = os.path.join(directory_path, filename)
            
            print(f"Working on {filename}")
            
            try:
                audio = MP4(filepath)

                # Get the filename without extension
                base_name = os.path.splitext(filename)[0]
                log_var("Base Name", base_name)
                
                name_parts = base_name.split("_")
                log_var("Name Parts", name_parts)
                
                
                year = name_parts[0]
                log_var("Year", year)
                away_city = abbreviation_map[name_parts[2]]
                home_city = abbreviation_map[name_parts[4]]
                at_vs = "vs" if "SB" in name_parts[1] else "at"
                log_var("@ or vs", at_vs)

                new_name = f"{year} {name_parts[1]} - {away_city} {at_vs} {home_city}"
                log_var("New name", new_name)

                audio["\xa9nam"] = new_name # Tags are often lists in MP4
                audio["\xa9day"] = year

                if not pretend:
                    print("Saving file.")
                    audio.save()
                    

                print(f"Updated title for '{filename}' to: '{new_name}'")
            except Exception as e:
                print(f"Error processing '{filename}': {e}")
                raise e


if is_cfl:
    print("--is-cfl flag passed. Treating year params as weeks.")
    print(f"Start week: {start_year}\tEnd week: {end_year}")
    for week in range(start_year, end_year + 1):
        wk_str = f"Wk{str(week).zfill(2)}"
        dir_path = f"{args.directory_path}/{wk_str}"
        update_mp4_title_from_filename(dir_path, args.pretend)
else:
    # Run the function
    for yr in range(start_year, end_year + 1):
        dir_path = f"{args.directory_path}/{yr}"
        update_mp4_title_from_filename(dir_path, args.pretend)
