import os

# Application related
OUTPUT_FORMATS = {
    "json": "JSON",
    "yaml": "YAML",
    "csv": "CSV",
    "docx": "Microsoft Word",
}
MEDIA_BASE_DIR = os.getenv("MEDIA_BASE_DIR")
CONCURRENT_FRAGMENTS = os.getenv("CONCURRENT_FRAGMENTS", 1)
THROTTLED_RATE_LIMIT = os.getenv("THROTTLED_RATE_LIMIT", 1000000)
# TODO: Think harder about this name?
PHOTO_BASE_DIR = os.getenv("PHOTO_BASE_DIR", "/mnt/e/FootballGames/automation/output_data/player_photos")

# Franchise/Team information
ABBREVIATION_MAP = {
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

CITY_TO_ABBR = {city: abbr for abbr, city in ABBREVIATION_MAP.items()}
CITY_TO_ABBR["Los Angeles (A)"] = "LAC"
CITY_TO_ABBR["Los Angeles (N)"] = "LAR"
CITY_TO_ABBR["New York (A)"] = "NYJ"
CITY_TO_ABBR["New York (N)"] = "NYG"


TEAM_FULL_NAMES = {
    "NYJ": "New York Jets",
    "NWE": "New England Patriots",
    "MIA": "Miami Dolphins",
    "BUF": "Buffalo Bills",
    "PIT": "Pittsburgh Steelers",
    "CLE": "Cleveland Browns",
    "BAL": "Baltimore Ravens",
    "CIN": "Cincinnati Bengals",
    "JAX": "Jacksonville Jaguars",
    "IND": "Indianapolis Colts",
    "HOU": "Houston Texans",
    "TEN": "Tennessee Titans",
    "LAC": "Los Angeles Chargers",
    "KC": "Kansas City Chiefs",
    "KAN": "Kansas City Chiefs",
    "LVR": "Las Vegas Raiders",
    "DEN": "Denver Broncos",
    "DAL": "Dallas Cowboys",
    "NYG": "New York Giants",
    "PHI": "Philadelphia Eagles",
    "WAS": "Washington Commanders",
    "GB": "Green Bay Packers",
    "GNB": "Green Bay Packers",
    "CHI": "Chicago Bears",
    "MIN": "Minnesota Vikings",
    "DET": "Detroit Lions",
    "TB": "Tampa Bay Buccaneers",
    "TAM": "Tampa Bay Buccaneers",
    "CAR": "Carolina Panthers",
    "ATL": "Atlanta Falcons",
    "NO": "New Orleans Saints",
    "NOR": "New Orleans Saints",
    "ARI": "Arizona Cardinals",
    "ARZ": "Arizona Cardinals",
    "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers",
    "SFO": "San Francisco 49ers",
    "LAR": "Los Angeles Rams",
    "RAM": "Los Angeles Rams",
}


# Positional/statistical related information
POSITIONS = ["QB", "RB", "WR", "TE", "OL", "DL", "EDGE", "LB", "DB"]


POSITION_STATS = {
    "QB": {
        "Passing": [
            "CMP",
            "ATT",
            "CMP%",
            "YDS",
            "TD",
            "INT",
            "SACK",
            "RTG"
        ]
    },
    "RB": {
        "Rushing": ["ATT", "YDS", "AVG", "TD"],
        "Receiving": ["REC", "YDS", "AVG", "TD"],
    },
    "WR": {
        "Receiving": ["REC", "YDS", "AVG", "TD"],
        "Rushing": ["ATT", "YDS", "AVG", "TD"],
    },
    "TE": {
        "Receiving": ["REC", "YDS", "AVG", "TD"],
        "Rushing": ["ATT", "YDS", "AVG", "TD"],
    },
    "OL": {},
    "DL": {
        "Tackles": ["TOTAL", "SOLO", "FF", "SACKS"],
        "Interceptions": ["INTS", "YDS", "TDS", "PDS"],
    },
    "EDGE": {
        "Tackles": ["TOTAL", "SOLO", "FF", "SACKS"],
        "Interceptions": ["INTS", "YDS", "TDS", "PDS"],
    },
    "LB": {
        "Tackles": ["TOTAL", "SOLO", "FF", "SACKS"],
        "Interceptions": ["INTS", "YDS", "TDS", "PDS"],
    },
    "DB": {
        "Tackles": ["TOTAL", "SOLO", "FF", "SACKS"],
        "Interceptions": ["INTS", "YDS", "TDS", "PDS"],
    },
}


POSITION_TO_GROUP_MAP = {
    "QB": "QB",
    "HB": "RB",
    "FB": "RB",
    "RB": "RB",
    "WR": "WR",
    "TE": "TE",
    "OT": "OL",
    "LT": "OL",
    "RT": "OL",
    "OG": "OL",
    "LG": "OL",
    "RG": "OL",
    "C": "OL",
    "DL": "DL",
    "DT": "DL",
    "NT": "DL",
    "NG": "DL",
    "EDGE": "EDGE",
    "LE": "EDGE",
    "RE": "EDGE",
    "DE": "EDGE",
    "LB": "LB",
    "LOLB": "LB",
    "ROLB": "LB",
    "OLB": "LB",
    "MLB": "LB",
    "ILB": "LB",
    "CB": "DB",
    "LCB": "CB",
    "RCB": "CB",
    "S": "DB",
    "FS": "DB",
    "SS": "DB",
}


# NFL.com specific
DEFAULT_REPLAY_TYPES = {
    "full_game": "Full Game",
    "all_22": "All-22",
    "condensed_game": "Condensed Game",
    "full_game_alternative": "Full Game - Alternative Broadcasts",
}
