# fbcm

A command line application that primarily leverages `yt-dlp` to assist with archiving football content.

This package installs a command named `fbcm` that provides several subcommands. Below are practical examples for each command defined in `src/fbcm/fbcm.py`.

## Installation

- Python 3.12+
- ffmpeg installed and available on PATH (required by ffmpeg-python and yt-dlp post-processing)

Install locally (editable) for development:

```bash
pip install -e .
```

After installation, the `fbcm` command will be available in your shell.

## Configuration

fbcm supports YAML configuration files to avoid repeating common options.

### Config file locations (auto-discovered in order):
1. `fbcm.yaml` in current working directory
2. `~/.config/fbcm.yaml`
3. Explicit path via `--config /path/to/config.yaml`

### Precedence
CLI arguments > Config file > Defaults

### Example config file

See `fbcm.yaml.example` for a complete template. A minimal example:

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
| `cookies_file` | download-list, nfl-show, nfl-games | --cookies-file |
| `credentials_file` | nfl-games | --credentials-file |
| `output_directory` | download-list, nfl-show, nfl-games | --output-directory |
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
fbcm download-list E:\\Downloads\\urls.txt --output-directory E:\\Media\\Misc --cookies-file E:\\Downloads\\cookies.txt
```

- `input_file` is a text file with one URL per line.
- `--output-directory` is where the files will be stored (can also be set via config).
- `--cookies-file` is optional and must be a Netscape-format cookies file if auth is required.

### 2) Update embedded metadata for existing game files

Command: `update-metadata`

```powershell
# Preview what would change (no writes)
fbcm update-metadata E:\\Media\\NFL\\2024 --pretend --verbose

# Perform the updates
fbcm update-metadata E:\\Media\\NFL\\2024
```

### 3) Download episodes from an NFL+ show

Command: `nfl-show`

```powershell
# episode list JSON contains URL leaves for episodes (see show_lists directory for examples)
fbcm nfl-show show_lists\\americas_game.json --cookies-file E:\\Downloads\\cookies.txt --output-directory "E:\\Media\\NFL Shows\\America's Game"
```

- `input_file` is a JSON file containing a `seasons` array of arrays with episode URL leaves.
- `--cookies-file` points to your NFL cookies (Netscape txt format) for authentication.
- `--output-directory` is the base directory where seasons/episodes will be saved.

### 4) Download NFL game replays for a given week

Command: `nfl-games`

**Authentication options** (use one, not both):
- `--credentials-file` - A JSON file containing `accessToken`, `refreshToken`, and `expiresIn` fields
- `--nfl-username` + `--nfl-password` - Your NFL.com login credentials (triggers browser-based login)

Using a credentials file (token-based auth):

```powershell
fbcm nfl-games --season 2024 --week 1 --credentials-file E:\\Downloads\\nfl_tokens.json
```

Using username/password (browser login):

```powershell
fbcm nfl-games --season 2024 --week 1 --nfl-username user@example.com --nfl-password yourpassword
```

Basic full-game downloads (all teams for a week):

```powershell
fbcm nfl-games --season 2024 --week 1 --credentials-file E:\\Downloads\\nfl_tokens.json
```

Download multiple weeks at once:

```powershell
fbcm nfl-games --season 2024 --week 1 --week 2 --week 3 --credentials-file E:\\Downloads\\nfl_tokens.json
```

Filter to a team (you can repeat `--team` multiple times):

```powershell
fbcm nfl-games --season 2024 --week 1 --team PIT --team DAL --credentials-file E:\\Downloads\\nfl_tokens.json
```

Choose replay type (keys come from the tool's supported types, e.g. `full_game`, `condensed_game`, `all_22`):

```powershell
# Download condensed replays only
fbcm nfl-games --season 2024 --week 1 --replay-type condensed_game --credentials-file E:\\Downloads\\nfl_tokens.json
```

Continue episode numbering (useful when combining multiple weeks):

```powershell
fbcm nfl-games --season 2024 --week 2 --start-ep 5 --credentials-file E:\\Downloads\\nfl_tokens.json
```

Notes:
- If `--season` is omitted, defaults to the current year.
- If `--week` is omitted, defaults to all regular season weeks (1-18).
- This command reads `FIREFOX_PROFILE` and `DESTINATION_DIR` from the environment to configure yt-dlp and output directory.
- `--credentials-file` should contain a JSON object with `accessToken`, `refreshToken`, and `expiresIn` fields.
- `--cookies-file` is used by yt-dlp for video downloads (separate from API authentication).
- All options can be set via config file (see Configuration section above).

### 5) Rename a series to Plex-friendly format

Command: `rename-series`

```powershell
# Preview renames for the series; release year influences the series folder name only
fbcm rename-series "America's Game" --release-year 2006 --pretend

# Perform and allow overwriting existing files
fbcm rename-series "America's Game" --release-year 2006 --replace
```

Requires `MEDIA_BASE_DIR` to be set; the tool looks for a directory named `Series Name (Year)` (if year provided), otherwise `Series Name`.

### 6) Convert video formats in a directory

Command: `convert-format`

```powershell
# Convert all mkv files to mp4 in the given directory, keep originals
fbcm convert-format E:\\Media\\NFL\\All22 --orig-format mkv --new-format mp4

# Dry run
fbcm convert-format E:\\Media\\NFL\\All22 --pretend

# Convert and delete originals after successful conversion
fbcm convert-format E:\\Media\\NFL\\All22 --delete
```

## Tips

- Use a config file (`fbcm.yaml`) to avoid repeating common options like cookies paths and output directories. See `fbcm.yaml.example` for a template.
- Many examples above reference the `show_lists` folder in this repo; it contains example JSON files for show downloads.
- If you run into authentication errors with NFL+, export cookies in Netscape format from your browser and pass via the `--cookies-file` option.
- For Windows paths in PowerShell, remember to escape backslashes when using them inside quoted strings in documentation; in the shell itself, normal backslashes are fine.