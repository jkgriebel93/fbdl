# fbdl

A command line application that primarily leverages `yt-dlp` to assist with archiving football content.

This package installs a command named `fbdl` that provides several subcommands. Below are practical examples for each command defined in `src/fbdl/fbdl.py`.

## Installation

- Python 3.12+
- ffmpeg installed and available on PATH (required by ffmpeg-python and yt-dlp post-processing)

Install locally (editable) for development:

```bash
pip install -e .
```

After installation, the `fbdl` command will be available in your shell.

## Configuration

fbdl supports YAML configuration files to avoid repeating common options.

### Config file locations (auto-discovered in order):
1. `fbdl.yaml` in current working directory
2. `~/.config/fbdl.yaml`
3. Explicit path via `--config /path/to/config.yaml`

### Precedence
CLI arguments > Config file > Defaults

### Example config file

See `fbdl.yaml.example` for a complete template. A minimal example:

```yaml
# Common options applied across commands
cookies_file: E:\Downloads\cookies.txt
output_directory: E:\Media\NFL
pretend: false

# Command-specific options
nfl_games:
  season: 2025
  week: [1, 2, 3]
  team: [PIT]
  replay_type: [full_game]
```

Common config keys are mapped to command-specific parameter names:
| Config Key | Commands | Maps To |
|------------|----------|---------|
| `cookies_file` | download-list, nfl-show, nfl-games | --cookies-file, --cookies, --raw-cookies |
| `output_directory` | download-list, nfl-show, nfl-games | OUTPUT_DIRECTORY, --output-directory, --destination-dir |
| `pretend` | update-metadata, rename-series, convert-format | --pretend |
| `verbose` | update-metadata | --verbose |

## Environment variables used by some commands

- `MEDIA_BASE_DIR` – Base directory where shows/games are stored (used by rename-series and internally by some downloaders).
- `FIREFOX_PROFILE` – Path to a Firefox profile directory with cookies/session for yt-dlp (used by nfl-games).
- `DESTINATION_DIR` – Default destination directory for downloaded videos (used by nfl-games).

On Windows PowerShell you can set them like:

```powershell
$env:MEDIA_BASE_DIR = "E:\Media"
$env:FIREFOX_PROFILE = "C:\\Users\\YourName\\AppData\\Roaming\\Mozilla\\Firefox\\Profiles\\abcd.default-release"
$env:DESTINATION_DIR = "E:\\Media\\NFL"
```

## Usage examples

Below are examples you can copy/paste. Replace paths with your own.

### 1) Download a list of URLs

Command: `download-list`

```powershell
# urls.txt contains one video URL per line
fbdl download-list E:\\Downloads\\urls.txt E:\\Media\\Misc --cookies-file E:\\Downloads\\cookies.txt
```

- `input_file` is a text file with one URL per line.
- `output_directory` is where the files will be stored (can also be set via config).
- `--cookies-file` is optional and must be a Netscape-format cookies file if auth is required.

### 2) Update embedded metadata for existing game files

Command: `update-metadata`

```powershell
# Preview what would change (no writes)
fbdl update-metadata E:\\Media\\NFL\\2024 --pretend --verbose

# Perform the updates
fbdl update-metadata E:\\Media\\NFL\\2024
```

### 3) Download episodes from an NFL+ show

Command: `nfl-show`

```powershell
# episode list JSON contains URL leaves for episodes (see show_lists directory for examples)
fbdl nfl-show show_lists\\americas_game.json --cookies E:\\Downloads\\cookies.txt --output-directory "E:\\Media\\NFL Shows\\America's Game"
```

- `input_file` is a JSON file containing a `seasons` array of arrays with episode URL leaves.
- `--cookies` points to your NFL cookies (Netscape txt format) for authentication.
- `--output-directory` is the base directory where seasons/episodes will be saved.

### 4) Download NFL game replays for a given week

Command: `nfl-games`

Basic full-game downloads (all teams for a week):

```powershell
fbdl nfl-games --season 2024 --week 1 --raw-cookies E:\\Downloads\\nfl_api_cookies.txt
```

Download multiple weeks at once:

```powershell
fbdl nfl-games --season 2024 --week 1 --week 2 --week 3 --raw-cookies E:\\Downloads\\nfl_api_cookies.txt
```

Filter to a team (you can repeat `--team` multiple times):

```powershell
fbdl nfl-games --season 2024 --week 1 --team PIT --team DAL --raw-cookies E:\\Downloads\\nfl_api_cookies.txt
```

Choose replay type (keys come from the tool's supported types, e.g. `full_game`, `condensed_game`, `all_22`):

```powershell
# Download condensed replays only
fbdl nfl-games --season 2024 --week 1 --replay-type condensed_game --raw-cookies E:\\Downloads\\nfl_api_cookies.txt
```

Continue episode numbering (useful when combining multiple weeks):

```powershell
fbdl nfl-games --season 2024 --week 2 --start-ep 5 --raw-cookies E:\\Downloads\\nfl_api_cookies.txt
```

Notes:
- If `--season` is omitted, defaults to the current year.
- If `--week` is omitted, defaults to all regular season weeks (1-18).
- This command reads `FIREFOX_PROFILE` and `DESTINATION_DIR` from the environment to configure yt-dlp and output directory.
- `--raw-cookies` should point to a txt file with cookies needed for the NFL API.
- All options can be set via config file (see Configuration section above).

### 5) Rename a series to Plex-friendly format

Command: `rename-series`

```powershell
# Preview renames for the series; release year influences the series folder name only
fbdl rename-series "America's Game" --release-year 2006 --pretend

# Perform and allow overwriting existing files
fbdl rename-series "America's Game" --release-year 2006 --replace
```

Requires `MEDIA_BASE_DIR` to be set; the tool looks for a directory named `Series Name (Year)` (if year provided), otherwise `Series Name`.

### 6) Convert video formats in a directory

Command: `convert-format`

```powershell
# Convert all mkv files to mp4 in the given directory, keep originals
fbdl convert-format E:\\Media\\NFL\\All22 --orig-format mkv --new-format mp4

# Dry run
fbdl convert-format E:\\Media\\NFL\\All22 --pretend

# Convert and delete originals after successful conversion
fbdl convert-format E:\\Media\\NFL\\All22 --delete
```

## Tips

- Use a config file (`fbdl.yaml`) to avoid repeating common options like cookies paths and output directories. See `fbdl.yaml.example` for a template.
- Many examples above reference the `show_lists` folder in this repo; it contains example JSON files for show downloads.
- If you run into authentication errors with NFL+, export cookies in Netscape format from your browser and pass via the `--cookies` or `--raw-cookies` options as appropriate.
- For Windows paths in PowerShell, remember to escape backslashes when using them inside quoted strings in documentation; in the shell itself, normal backslashes are fine.