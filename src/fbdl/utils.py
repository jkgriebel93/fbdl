import os
import re

from pathlib import Path


def rename_files(directory: Path, series_name: str, pretend: bool = True):
    # Regular expression to match the xyy-<Episode Name>.mp4 format
    pattern = r'^(\d{1})(\d{2,3})-(.+)\.mp4$'

    # Iterate through all subdirectories
    for file_path in directory.rglob('*.mp4'):
        # Check if file matches the expected pattern
        match = re.match(pattern, file_path.name)
        if match:
            season = match.group(1)  # Extract season number (x)
            episode = match.group(2)  # Extract episode number (yy)
            episode_name = match.group(3)  # Extract episode name

            new_filename = f"{series_name} - s{season.zfill(2)}e{episode.zfill(2)}-{episode_name}.mp4"

            if pretend:
                print(f"Would rename {file_path.name} to {new_filename}."
                      f" --pretend was passed, so we will not attempt the operation.")
            else:
                new_file_path = file_path.with_name(new_filename)
                print(f"Renaming {file_path.name} to {new_file_path.name}")
                file_path.rename(new_file_path)
                print("Success.")
