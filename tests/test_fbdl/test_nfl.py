import json
from pathlib import Path

import pytest

from fbdl.nfl import MetaDataCreator


@pytest.fixture(scope="session")
def game_dates():
    with open("tests/data/game_dates.json", "r") as infile:
        return json.load(infile)


def _create_fake_mp4_files(base_path):
    season_dir = Path(base_path, "Season 2024")
    if not season_dir.exists():
        season_dir.mkdir()

    for mock_name in [
        "2024_Wk01_PIT_at_ATL",
        "2024_LAC_at_PIT",
        "2024_Wk19WC_PIT_at_BAL",
        "2024_Wk22SBLIX_KAN_vs_PHI",
    ]:
        mock_mp4 = base_path / f"{mock_name}.mp4"
        mock_mp4.write_text(mock_name)


class TestMetaDataCreator:
    def test_create_title_string(self, tmp_path, game_dates):
        mdc = MetaDataCreator(base_dir=tmp_path, game_dates=game_dates)
        result = mdc._create_title_string(file_stem="2024_Wk22SBLIX_KAN_vs_PHI")

        assert result == "2024 Week 22 Super Bowl LIX - Kansas City vs Philadelphia"

    def test_construct_metadata_xml_for_game(self, tmp_path, game_dates):
        mdc = MetaDataCreator(base_dir=tmp_path, game_dates=game_dates)
        xml_string = mdc.construct_metadata_xml_for_game(
            game_stem="NFL Condensed Games - s2025e18 - 2025_Wk02_CLE_at_BAL"
        )
        assert xml_string == (
            f"<episodedetails>\n"
            f"\t<title>2025 Week 2 - Cleveland at Baltimore</title>\n"
            f"\t<season>2025</season>\n"
            f"\t<episode>18</episode>\n"
            f"\t<aired>2025-09-14</aired>\n"
            f"</episodedetails>"
        )

    def test_create_nfo_for_season(self, tmp_path, game_dates):
        _create_fake_mp4_files(base_path=tmp_path)
        mdc = MetaDataCreator(base_dir=tmp_path, game_dates=game_dates)
