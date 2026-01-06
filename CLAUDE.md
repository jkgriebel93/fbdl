# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`fbcm` is a CLI tool for archiving football content (primarily NFL, also CFL and UFL). It wraps `yt-dlp` with specialized functionality for NFL Plus downloads, metadata generation, and media file management for Plex/Jellyfin compatibility.

## Build and Development Commands

```bash
# Install in editable mode for development
pip install -e .

# Install with dev dependencies (pytest)
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file
pytest tests/test_fbcm/test_base.py

# Run a specific test
pytest tests/test_fbcm/test_base.py::test_function_name -v

# Format code
black src/
```

## Architecture

### CLI Entry Point
- `src/fbcm/fbcm.py` - Click-based CLI with commands: `download-list`, `update-metadata`, `nfl-show`, `nfl-games`, `rename-series`, `convert-format`, `generate-nfo-files`

### Core Modules
- `src/fbcm/base.py` - Contains `BaseDownloader` (yt-dlp wrapper), `FileOperationsUtil` (file renaming, format conversion, metadata updates), `MetaDataCreator` (NFO file generation), and league-specific helper functions for week/playoff calculations
- `src/fbcm/nfl.py` - `NFLShowDownloader` for NFL Plus TV series, `NFLWeeklyDownloader` (inherits BaseDownloader + NFLBaseIE) for game replays using the griddy NFL client

### Key Data Structures
- `base.py` contains team abbreviation mappings (`abbreviation_map`, `TEAM_FULL_NAMES`, `CITY_TO_ABBR`) used throughout for NFL/CFL/UFL team lookups
- `DEFAULT_REPLAY_TYPES` maps CLI options to NFL API replay type names

### File Naming Convention
Games are named: `{League} {replay_type} - s{season}e{episode} - {year}_Wk{week}_{away_abbr}_{at|vs}_{home_abbr}`

NFO metadata files (XML format) are generated alongside videos for Jellyfin/Plex parsing.

## Environment Variables

- `MEDIA_BASE_DIR` - Base directory for media storage (used by rename-series, nfl-show)
- `FIREFOX_PROFILE` - Firefox profile path for yt-dlp cookie extraction
- `DESTINATION_DIR` - Default output directory for nfl-games
- `CONCURRENT_FRAGMENTS` - yt-dlp concurrent fragment downloads (default: 1)
- `THROTTLED_RATE_LIMIT` - yt-dlp rate limit (default: 1000000)

## Configuration File

The CLI supports YAML config files (`fbcm.yaml`) with auto-discovery:
1. Current working directory
2. `~/.config/fbcm.yaml`
3. Explicit `--config /path/to/config.yaml`

Precedence: CLI args > Config file > Defaults

See `fbcm.yaml.example` for the config file structure. Common options (`cookies_file`, `output_directory`, `pretend`, `verbose`) are mapped to command-specific parameter names via `src/fbcm/utils.py:COMMON_OPTION_MAPPINGS`.

## Dependencies

- `yt-dlp` - Core video downloading
- `griddy` - NFL API client for game data
- `ffmpeg-python` - Video format conversion (requires ffmpeg on PATH)
- `mutagen` - MP4 metadata manipulation
- `click` - CLI framework
- `pyyaml` - Config file parsing
