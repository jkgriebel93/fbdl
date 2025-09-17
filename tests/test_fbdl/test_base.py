import os

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from fbdl.base import (
    convert_nfl_playoff_name_to_int,
    convert_ufl_playoff_name_to_int,
    get_week_int_as_string,
    is_bowl_game,
    is_playoff_week,
    transform_file_name,
    BaseDownloader,
    FileOperationsUtil,
)


class TestUtilFunctions:
    def test_convert_nfl_playoff_name_to_int_pre_1978_div(self):
        result = convert_nfl_playoff_name_to_int(year=1977, week_name="Divisional")
        assert result == 15

    def test_convert_nfl_playoff_name_to_int_pre_1978_conf(self):
        result = convert_nfl_playoff_name_to_int(
            year=1977, week_name="Conference Championship"
        )
        assert result == 16

    def test_convert_nfl_playoff_name_to_int_pre_1978_sb(self):
        result = convert_nfl_playoff_name_to_int(year=1977, week_name="Super Bowl")
        assert result == 17

    def test_convert_nfl_playoff_name_to_int_pre_1978_invalid(self):
        result = convert_nfl_playoff_name_to_int(year=1977, week_name="Foo")
        assert result is None

    def test_convert_nfl_playoff_name_to_int_1978_to_89_wild_card(self):
        result = convert_nfl_playoff_name_to_int(year=1985, week_name="Wild Card")
        assert result == 17

    def test_convert_nfl_playoff_name_to_int_1978_to_89_divisional(self):
        result = convert_nfl_playoff_name_to_int(year=1985, week_name="Divisional")
        assert result == 18

    def test_convert_nfl_playoff_name_to_int_1978_to_89_conf(self):
        result = convert_nfl_playoff_name_to_int(
            year=1985, week_name="Conference Championship"
        )
        assert result == 19

    def test_convert_nfl_playoff_name_to_int_1978_to_89_sb(self):
        result = convert_nfl_playoff_name_to_int(year=1985, week_name="Super Bowl")
        assert result == 20

    def test_convert_nfl_playoff_name_to_int_1978_to_89_invalid(self):
        result = convert_nfl_playoff_name_to_int(year=1985, week_name="Fizz")
        assert result is None

    def test_convert_nfl_playoff_name_to_int_1990_to_2019_wild_card(self):
        result = convert_nfl_playoff_name_to_int(year=2000, week_name="Wild Card")
        assert result == 18

    def test_convert_nfl_playoff_name_to_int_1990_to_2019_divisional(self):
        result = convert_nfl_playoff_name_to_int(year=2000, week_name="Divisional")
        assert result == 19

    def test_convert_nfl_playoff_name_to_int_1990_to_2019_conf(self):
        result = convert_nfl_playoff_name_to_int(
            year=2000, week_name="Conference Championship"
        )
        assert result == 20

    def test_convert_nfl_playoff_name_to_int_1990_to_2019_sb(self):
        result = convert_nfl_playoff_name_to_int(year=2000, week_name="Super Bowl")
        assert result == 21

    def test_convert_nfl_playoff_name_to_int_1990_to_2019_invalid(self):
        result = convert_nfl_playoff_name_to_int(year=2000, week_name="Fizz")
        assert result is None

    def test_convert_nfl_playoff_name_to_int_2020_plus_wild_card(self):
        result = convert_nfl_playoff_name_to_int(year=2022, week_name="Wild Card")
        assert result == 19

    def test_convert_nfl_playoff_name_to_int_2020_plus_divisional(self):
        result = convert_nfl_playoff_name_to_int(year=2022, week_name="Divisional")
        assert result == 20

    def test_convert_nfl_playoff_name_to_int_2020_plus_conf(self):
        result = convert_nfl_playoff_name_to_int(
            year=2022, week_name="Conference Championship"
        )
        assert result == 21

    def test_convert_nfl_playoff_name_to_int_2020_plus_sb(self):
        result = convert_nfl_playoff_name_to_int(year=2022, week_name="Super Bowl")
        assert result == 22

    def test_convert_nfl_playoff_name_to_int_2000_plus_invalid(self):
        result = convert_nfl_playoff_name_to_int(year=2022, week_name="Fizz")
        assert result is None

    def test_convert_ufl_playoff_name_to_int_conf(self):
        result = convert_ufl_playoff_name_to_int(
            year=2024, week_name="Conference Championship"
        )
        assert result == 11

    def test_convert_ufl_playoff_name_to_int_champ(self):
        result = convert_ufl_playoff_name_to_int(
            year=2024, week_name="UFL Championship"
        )
        assert result == 12

    def test_convert_ufl_playoff_name_to_int_invalid(self):
        result = convert_ufl_playoff_name_to_int(year=2024, week_name="Fubar")
        assert result is None

    def test_get_week_int_as_string_single_digit_wk(self):
        result = get_week_int_as_string(week="Wk06", year=2024, is_ufl=False)
        assert result == "06"

    def test_get_week_int_as_string_double_digit_wk(self):
        result = get_week_int_as_string(week="Wk11", year=2024, is_ufl=False)
        assert result == "11"

    def test_get_week_int_as_string_nfl_playoff_week(self):
        result = get_week_int_as_string(week="Wk21Conf", year=2024, is_ufl=False)
        assert result == "21"

    def test_get_week_int_as_string_ufl_playoff_week(self):
        result = get_week_int_as_string(week="Wk12UFLChamp", year=2024, is_ufl=True)
        assert result == "12"

    def test_get_week_int_as_string_invalid_returns_empty_str(self):
        result = get_week_int_as_string(week="snafu", year=2024, is_ufl=False)
        assert result == ""

    def test_is_bowl_game_positive(self):
        for name in [
            "SEC Championship ",
            "Orange Bowl ",
            "CFP Final ",
            "Peach Bowl CFP Semi-Final",
        ]:
            result = is_bowl_game(name)
            assert result == name

    def test_is_bowl_game_negative(self):
        result = is_bowl_game("2025_Gm01_Marshall_at_(5)_Georgia.mp4")
        assert result == ""

    def test_is_playoff_week_wild_card(self):
        result = is_playoff_week("Wk19WC")
        assert result == "Wild Card"

    def test_is_playoff_week_divisional(self):
        result = is_playoff_week("Wk20Div")
        assert result == "Divisional"

    def test_is_playoff_week_conf(self):
        result = is_playoff_week("Wk21Conf")
        assert result == "Conference Championship"

    def test_is_playoff_week_super_bowl(self):
        result = is_playoff_week("Wk22SBLIX")
        assert result == "Super Bowl LIX"

    def test_is_playoff_week_negative(self):
        result = is_playoff_week("Wk19")
        assert result == ""

    def test_transform_file_name(self):
        fake_file = "2024 - Game 13 2024-12-07 SEC Championship UGA vs Texas"
        result = transform_file_name(orig_file_stem=fake_file)

        assert result == "NCAA - s2024e13 - 2024_Gm13SECChampionship_Georgia_vs_Texas"


class TestBaseDownloader:
    fake_urls_list = [
        "https://www.youtube.com/watch?v=abcdefgh",
        "https://www.youtube.com/watch?v=ijklmonpq",
    ]

    def test_cookies_from_browser_set_correctly_when_passed(self, tmp_path):
        d = tmp_path / "base_downloader"
        d.mkdir()
        cookies_file = d / "cookies.txt"
        bd = BaseDownloader(cookie_file_path=cookies_file, browser="firefox")

        assert bd.cookie_file_path == cookies_file
        assert bd.base_yt_opts["cookiesfrombrowser"] == ("firefox", cookies_file)

    def test_destination_dir_set_as_cwd_when_not_passed(self):
        bd = BaseDownloader()
        assert bd.destination_dir == Path(os.getcwd())

    def test_init_overrides_yt_opts_when_passed(self):
        bd = BaseDownloader(add_yt_opts={"merge_output_format": "mkv"})
        assert bd.base_yt_opts["merge_output_format"] == "mkv"

    @patch("fbdl.base.YoutubeDL")
    def test_download_from_file(self, mock_ytdl_class, tmp_path):
        # TODO: Make the mocking cleaner
        d = tmp_path / "base_downloader"
        d.mkdir()
        input_file = d / "urls.txt"
        input_file.write_text("\n".join(self.fake_urls_list), encoding="utf-8")

        fname_template = "%(title)s.%(ext)s"

        mock_ytdl_instance = Mock()
        mock_ytdl_instance.__enter__ = MagicMock(return_value=mock_ytdl_instance)
        mock_ytdl_instance.__exit__ = MagicMock(return_value=None)
        mock_ytdl_instance.download = MagicMock(return_value=None)

        mock_ytdl_class.return_value = mock_ytdl_instance

        bd = BaseDownloader()
        bd.download_from_file(
            input_file=input_file, output_file_name_template=fname_template
        )

        outtmpl_actual_val = mock_ytdl_class.call_args.kwargs["params"]["outtmpl"]

        assert outtmpl_actual_val == f"{os.getcwd()}/{fname_template}"
        mock_ytdl_instance.download.assert_called_once_with(self.fake_urls_list)


class TestFileOperationsUtil:
    def test_construct_mp4_title_reg_season(self, tmp_path):
        example_file_stem = "2025_Wk05_PIT_at_LVR"
        d = tmp_path / "fops"
        fops = FileOperationsUtil(directory_path=d)
        result = fops._construct_mp4_title(file_stem=example_file_stem)

        assert result == "2025 Wk05 - Pittsburgh at Las Vegas"

    def test_construct_mp4_title_super_bowl(self, tmp_path):
        d = tmp_path / self.__class__.__name__
        fops = FileOperationsUtil(directory_path=d)
        example_file_stem = "2005_Wk21SBXL_PIT_vs_SEA"
        result = fops._construct_mp4_title(file_stem=example_file_stem)
        assert result == "2005 Wk21SBXL - Pittsburgh vs Seattle"

    @patch("fbdl.base.MP4")
    def test_save_is_called_when_not_pretending(self, mock_MP4_class, tmp_path):
        d = tmp_path / self.__class__.__name__

        mock_MP4_instance = MagicMock()
        mock_MP4_class.return_value = mock_MP4_instance

        fops = FileOperationsUtil(directory_path=d, pretend=False)
        fake_file = d / "2025_Wk01_PIT_at_NYJ.mp4"
        fops.update_mp4_title_from_filename(file_obj=fake_file)

        mock_MP4_instance.save.assert_called_once()

    @patch("fbdl.base.MP4")
    def test_save_is_not_called_when_pretending(self, mock_MP4_class, tmp_path):
        d = tmp_path / self.__class__.__name__
        fops = FileOperationsUtil(directory_path=d, pretend=True)

        fake_file = d / "2025_Wk01_PIT_at_NYJ.mp4"
        fops.update_mp4_title_from_filename(file_obj=fake_file)

        mock_MP4_instance = Mock()
        mock_MP4_instance.save = MagicMock(return_value=None)
        mock_MP4_class.return_value = mock_MP4_instance

        mock_MP4_instance.save.assert_not_called()

    @patch("ffmpeg.input")
    @patch("ffmpeg.output")
    @patch("ffmpeg.run")
    def test_convert_formats_only_converts_orig_format(
        self, mock_run, mock_output, mock_input, tmp_path
    ):
        mock_stream = MagicMock()
        mock_input.return_value = mock_stream
        mock_output.return_value = mock_stream

        fake_mkv = tmp_path / "fake.mkv"
        fake_mkv.write_text("this is a fake mkv")

        fake_mp4 = tmp_path / "also_fake.mp4"
        fake_mp4.write_text("Another fake video")

        fops = FileOperationsUtil(directory_path=tmp_path)
        fops.convert_formats(orig_format="mkv", new_format="mp4")

        mock_input.assert_called_once_with(str(fake_mkv))
        output_path = str(fake_mkv.with_suffix(".mp4"))
        mock_output.assert_called_once_with(
            mock_stream, output_path, vcodec="copy", acodec="copy", format="mp4"
        )
        mock_run.assert_called_once_with(mock_stream)
