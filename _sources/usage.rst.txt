Usage
=====

Installation
------------

Clone the repository and install in editable mode with dependencies:

.. code-block:: powershell

   git clone E:\FootballGames\automation
   cd automation
   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -e .

Building the docs (optional):

.. code-block:: powershell

   .\docs\make.bat html

Quick start
-----------

Once installed, the ``fbdl`` command is available:

.. code-block:: powershell

   fbdl --help

Common commands include:

- ``fbdl download-list <INPUT_FILE> <OUTPUT_DIRECTORY> [--cookie-file cookies.txt]``
- ``fbdl update-metadata <DIRECTORY_PATH> [--pretend] [--verbose]``
- ``fbdl nfl-games <SEASON> <WEEK> [--team PIT] [--replay-type full_game] [--start-ep 0]``
- ``fbdl rename-series <SERIES_NAME> [--release-year 2020] [--pretend] [--replace]``
- ``fbdl convert-format <DIRECTORY> [--pretend] [--delete]``

Environment variables
---------------------

The following environment variables are used by various commands:

- ``PROFILE_LOCATION``: Path to a Netscape-formatted cookie file for authenticated downloads (used by nfl_games).
- ``DEST_DIR``: Default destination directory for downloaded game replays (used by nfl_games).
- ``MEDIA_BASE_DIR``: Base media library directory for organizing shows and episodes (used by NFL show downloads and renaming utilities).
- ``THROTTLED_RATE_LIMIT``: Optional rate limit passed to yt-dlp when throttled downloads are detected.

Cookies
-------

Some endpoints (e.g., NFL Plus) require authentication. Provide cookies exported in Netscape format either via:

- CLI options that accept a cookie file, or
- Setting ``PROFILE_LOCATION`` to point to your cookies file.

See the CLI reference for details on per-command options.
