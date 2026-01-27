import io
import re
import time
from collections import defaultdict
from pathlib import Path
from random import uniform
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from playwright.sync_api import Browser
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from fbcm.constants import POSITION_TO_GROUP_MAP
from fbcm.models import (
    BasicInfo,
    Comparison,
    DefenseStats,
    DefensiveBackSkills,
    DefensiveLinemanSkills,
    InterceptionStats,
    LinebackerSkills,
    OffenseSkillPlayerStats,
    OffensiveLinemanSkills,
    PassCatcherSkills,
    PassingSkills,
    PassingStats,
    ProspectDataSoup,
    RatingsAndRankings,
    ReceivingStats,
    RunningBackSkills,
    RushingStats,
    ScoutingReport,
    SkillRatings,
    Stats,
    TackleStats,
)
from .word_gen import WordDocGenerator

class PageFetcher:
    """Handles fetching web pages using Playwright browser automation."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}
    CONTENT_WAIT_TIME = 3000

    MAX_RETRIES = 3

    def __init__(
        self,
        playwright: Playwright,
        headless: bool = False,
        base_url: str = "https://www.nfldraftbuzz.com",
    ):
        self.base_url = base_url
        self.playwright = playwright
        self.headless = headless
        self.browser = self._launch_browser()

    def _launch_browser(self) -> Browser:
        """Launch a new browser instance."""
        return self.playwright.firefox.launch(headless=self.headless, slow_mo=150)

    def _ensure_browser_connected(self) -> None:
        """Ensure browser is connected, relaunch if necessary."""
        if not self.browser.is_connected():
            print("Browser disconnected, relaunching...")
            self.browser = self._launch_browser()

    def fetch(
        self, url: str, attempt_image_fetch: bool = False
    ) -> Tuple[str, Optional[bytes], str]:
        """
        Fetch page content using Playwright browser automation.

        Args:
            url: The URL to fetch.
            attempt_image_fetch: Whether to attempt downloading the player image.

        Returns:
            Tuple of (page_text, image_bytes, image_type).
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                return self._fetch_with_page(url, attempt_image_fetch)
            except PlaywrightError as e:
                last_error = e
                error_msg = str(e).lower()
                if (
                    "target closed" in error_msg
                    or "browser has been closed" in error_msg
                ):
                    print(
                        f"Browser/target closed (attempt {attempt + 1}/{self.MAX_RETRIES}), relaunching..."
                    )
                    try:
                        self.browser.close()
                    except Exception:
                        pass  # Browser may already be closed
                    self.browser = self._launch_browser()
                    time.sleep(1)  # Brief pause before retry
                else:
                    raise  # Re-raise if it's a different Playwright error

        raise last_error  # All retries exhausted

    def fetch_soup(self, url) -> BeautifulSoup:
        self._ensure_browser_connected()
        page = self.browser.new_page()
        try:
            print(f"Navigating to: {url}")
            page.goto(url=url)
            return BeautifulSoup(page.content(), "lxml")
        finally:
            page.close()

    def _fetch_with_page(
        self, url: str, attempt_image_fetch: bool
    ) -> Tuple[str, Optional[bytes], str]:
        """Internal method to fetch a page. May raise PlaywrightError."""
        self._ensure_browser_connected()
        print("Opening new page...")

        page = self.browser.new_page()
        try:
            print(f"Navigating to: {url}")
            try:
                page.goto(url)
            except PlaywrightTimeout:
                print("Page load timeout, continuing with partial content...")

            text_content = page.evaluate("() => document.body.innerText")
            if attempt_image_fetch:
                image_data, image_type = self._find_and_download_image(page, url)
            else:
                image_data = None
                image_type = None
            # TODO: Returning both text_content and page.content is a temporary kludge
            return text_content, image_data, image_type
        finally:
            page.close()

    def _find_and_download_image(
        self, page, base_url: str
    ) -> Tuple[Optional[bytes], str]:
        """Find and download the player image from the page."""
        image_url = self._find_image_url(page)

        if not image_url:
            image_url = self._find_any_large_image(page)

        if image_url:
            return self._download_image(page, image_url, base_url)

        return None, "jpeg"

    def _find_image_url(self, page) -> Optional[str]:
        """Try to find image URL using predefined selectors."""
        img = page.locator("figure.player-info__photo img")
        src = img.get_attribute("src")
        return self._make_absolute_url(url=src, base_url=self.base_url)

    def _find_any_large_image(self, page) -> Optional[str]:
        """Fallback: try to find any large player image."""
        try:
            images = page.query_selector_all("img")
            for img in images:
                src = img.get_attribute("src")
                if src and not self._should_skip_image(src):
                    if (
                        "nfldraftbuzz" in src
                        or "imagn" in src.lower()
                        or "player" in src.lower()
                    ):
                        return src
        except Exception:
            pass
        return None

    def _should_skip_image(self, src: str) -> bool:
        """Check if an image URL should be skipped."""
        src_lower = src.lower()
        return any(pattern in src_lower for pattern in self.SKIP_IMAGE_PATTERNS)

    def _download_image(
        self, page, image_url: str, base_url: str
    ) -> Tuple[Optional[bytes], str]:
        """Download image from URL."""
        print(f"Found player image: {image_url[:80]}...")
        try:
            image_url = self._make_absolute_url(image_url, base_url)
            response = page.request.get(image_url)
            if response.ok:
                image_data = response.body()
                image_type = self._get_image_type(
                    response.headers.get("content-type", "")
                )
                print(f"Downloaded image: {len(image_data)} bytes ({image_type})")
                return image_data, image_type
        except Exception as e:
            print(f"Failed to download image: {e}")
        return None, "jpeg"

    @staticmethod
    def _make_absolute_url(url: str, base_url: str = None) -> str:
        """Convert relative URL to absolute."""
        if url.startswith("//"):
            return "https:" + url
        elif url.startswith("/"):
            return urljoin(base_url, url)
        return url

    @staticmethod
    def _get_image_type(content_type: str) -> str:
        """Determine image type from content-type header."""
        if "png" in content_type:
            return "png"
        elif "gif" in content_type:
            return "gif"
        elif "webp" in content_type:
            return "webp"
        return "jpeg"


class ProspectParserSoup:
    """
    Parses nfldraftbuzz.com prospect profiles using BeautifulSoup
    """

    def __init__(self, soup: BeautifulSoup, position: str):
        self.soup = soup
        self.position = position

    ##### Utility Methods #####
    def _get_tag_with_title_containing(self, tag, search_str) -> Tag:
        return tag.find("span", title=lambda t: t and search_str in t)

    def _get_tag_with_text(self, search_space, tag_name, text):
        # Note that text should be lower case since we use lower()
        return search_space.find(tag_name, string=lambda s: text in s.lower())

    def _get_text_following_label(
        self, label_tag, expected_sibling_name: str = "span"
    ) -> str | None:
        if label_tag is None:
            return None
        return label_tag.find_next_sibling(expected_sibling_name).get_text(strip=True)

    ##### Basic Info Related #####
    def parse_basic_info(self) -> BasicInfo:
        basic_info_dict = {}

        first_name, last_name = self._parse_name()

        info_details_div = self.soup.find("div", class_="player-info-details")
        basic_info_dict.update(
            self._parse_player_info_details_div(div=info_details_div)
        )

        basic_info_table_tag = self.soup.find("table", class_="basicInfoTable")
        basic_info_dict.update(self._parse_basic_info_table(basic_info_table_tag))

        basic_info_dict["class_"] = basic_info_dict.pop("class")
        basic_info_dict["hometown"] = basic_info_dict.pop("home town")
        basic_info_dict["photo_url"] = self.extract_image_url()

        return BasicInfo(
            first_name=first_name,
            last_name=last_name,
            full_name=f"{first_name} {last_name}",
            **basic_info_dict,
        )

    def parse_ratings(self, table: Tag) -> RatingsAndRankings:
        self._perform_rating_checks(table=table)

        table_rows = table.find_all("tr")
        overall = self._extract_ovr_rtg(row=table_rows[0])
        opposition = self._extract_opposition_rtg(row=table_rows[2])

        proj_rank_row = self._get_projection_ranks_row(rows=table_rows)
        proj_ranks = self._extract_proj_and_rankings(row=proj_rank_row)
        avg_ranks = self._extract_average_ranks()

        outlet_ratings = self._extract_outlet_ratings(table=table)

        rate_ranks = RatingsAndRankings(
            overall_rating=overall,
            opposition_rating=opposition,
            **proj_ranks,
            **outlet_ratings,
            **avg_ranks,
        )

        return rate_ranks

    def parse_skills(self, table: Tag) -> SkillRatings:
        rows = table.find_all("tr")[4:]
        skill_rtgs_rows = self._gather_skill_rtg_rows(rows=rows)
        skill_ratings_dict = self._extract_skill_ratings(rows=skill_rtgs_rows)
        return self._construct_skill_ratings_obj(ratings=skill_ratings_dict)

    def parse_comparisons(self, table: Tag) -> List[Comparison]:
        comparisons = []
        comp_rows = table.find("tbody").find_all("tr")

        for row in comp_rows:
            text_parts = row.get_text().split()
            comp_name = f"{text_parts[0]} {text_parts[1]}"
            comp_school = text_parts[3]
            comp_score = int(text_parts[-1].replace("%", ""))

            comparisons.append(
                Comparison(name=comp_name, school=comp_school, similarity=comp_score)
            )

        return comparisons

    def parse_scouting_report(self) -> ScoutingReport:
        intro_div = self.soup.find("div", class_="playerDescIntro")
        if not intro_div:
            return ScoutingReport()

        strengths_div = self.soup.find("div", class_="playerDescPro")
        weak_summary_divs = self.soup.find_all("div", class_="playerDescNeg")
        weaknesses_div = weak_summary_divs[0]

        summary = None
        if len(weak_summary_divs) > 1:
            summary = weak_summary_divs[1].get_text(strip=True)

        strengths = [
            line
            for line in strengths_div.get_text().splitlines()
            if line and "scouting report" not in line.lower()
        ]
        weaknesses = [
            line
            for line in weaknesses_div.get_text().splitlines()
            if line and "scouting report" not in line.lower()
        ]

        return ScoutingReport(
            bio=intro_div.get_text(strip=True),
            strengths=strengths,
            weaknesses=weaknesses,
            summary=None,
        )

    def extract_image_url(self) -> str:
        figure_tag = self.soup.find("figure", class_="player-info__photo")
        image_path = figure_tag.find("img")["src"]
        return f"https://www.nfldraftbuzz.com{image_path}"

    def parse_stats(self, soup: BeautifulSoup) -> Stats:

        stats = None
        table_div = None
        match self.position:
            case "QB":
                table_div = soup.find(id="QBstats")
            case "RB" | "WR" | "TE":
                table_div = soup.find(id="RB-Rush-stats")
            case "OL":
                pass
            case "DL" | "EDGE" | "LB" | "DB":
                table_div = soup.find(id="DBLBDL-stats")
            case _:
                print(f"Could not match position {self.position} to any known group.")

        if table_div is not None:
            stats = self._extract_stats_object(div=table_div)[0]

        return stats

    def _extract_games_and_snaps(self) -> Dict:
        gp_label = self._get_tag_with_title_containing(
            tag=self.soup, search_str="College Games Played"
        )
        games_played = int(self._get_text_following_label(label_tag=gp_label) or "0")
        snaps_label = self._get_tag_with_title_containing(
            tag=self.soup, search_str="College Snap Count"
        )
        snap_count = int(self._get_text_following_label(label_tag=snaps_label) or "0")

        return {"games_played": games_played, "snap_count": snap_count}

    def parse(self):
        basic_info = self.parse_basic_info()
        rtgs_table, comps_table = self._extract_ratings_comps_tables()

        ratings = self.parse_ratings(table=rtgs_table)
        skills = self.parse_skills(table=rtgs_table)
        comparisons = self.parse_comparisons(table=comps_table) if comps_table else None
        scouting_report = self.parse_scouting_report()

        return ProspectDataSoup(
            basic_info=basic_info,
            ratings=ratings,
            skills=skills,
            comparisons=comparisons,
            scouting_report=scouting_report,
            stats=None,
        )

    ##### Basic Info #####
    def _parse_name(self) -> Tuple[str, str]:
        first_name = self.soup.find("span", class_="player-info__first-name").get_text(
            strip=True
        )
        last_name = self.soup.find("span", class_="player-info__last-name").get_text(
            strip=True
        )

        return first_name, last_name

    def _parse_position(self, value: str) -> str:
        position_group_str = ""
        if "/" in value:
            p1, p2 = value.split("/")
            p1_group = POSITION_TO_GROUP_MAP.get(p1.upper())
            p2_group = POSITION_TO_GROUP_MAP.get(p2.upper())

            # Neither correspond to a known group
            if not (p1_group or p2_group):
                raise ValueError(
                    f"Could not find a valid position group for position: {value}"
                )

            # Both correspond to a known group
            if p1_group and p2_group:
                position_group_str = f"{p1_group}/{p2_group}"
            # Only one of the two values corresponds to a known group
            # p1_group is the "real" one
            elif p1_group:
                position_group_str = p1_group
            # If only one value corresponds to a real group, and it's not p1
            # it must be p2
            elif p2:
                position_group_str = p2_group

        else:
            position_group_str = POSITION_TO_GROUP_MAP[value.upper()]

        return position_group_str

    def _parse_player_info_details_div(self, div: Tag) -> Dict:
        # This div contains the values for:
        # height, weight, college, position, player_class, hometown
        basic_info_dict = {}

        for attr_div in div.find_all("div", class_="player-info-details__item"):
            field_tag = attr_div.find("h6", class_="player-info-details__title")
            value_tag = attr_div.find("div", class_="player-info-details__value")

            field = field_tag.get_text(strip=True).lower()
            value = value_tag.get_text(strip=True).lower()

            if field == "position":
                value = self._parse_position(value=value)
            basic_info_dict[field] = value

        return basic_info_dict

    def _parse_basic_info_table(self, tag: Tag) -> Dict:
        # Includes jersery #, sub_position, last_updated, forty_time
        jersey_num = tag.find(text=re.compile(r"#\d+")).get_text(strip=True)

        sub_position_label = self._get_tag_with_title_containing(tag, "Sub-Position")
        sub_position_value = self._get_text_following_label(sub_position_label)

        last_updated_label = self._get_tag_with_title_containing(tag, "Last Updated")
        last_updated_value = self._get_text_following_label(last_updated_label)

        draft_yr_label = self._get_tag_with_title_containing(tag, "Draft Year")
        draft_yr_value = self._get_text_following_label(draft_yr_label)

        forty_label = self._get_tag_with_title_containing(tag, "40 yard dash time")
        forty_value = self._get_text_following_label(forty_label)

        return {
            "jersey": jersey_num,
            "play_style": sub_position_value,
            "last_updated": last_updated_value,
            "draft_year": draft_yr_value,
            "forty": forty_value.split()[0],
        }

    ##### Statistical Related #####
    def _transform_passing_stats(self, season_stats):
        season_stats["cmp_pct"] = season_stats.pop("cmp%")
        season_stats["ints"] = season_stats.pop("int")
        season_stats["qb_rtg"] = season_stats.pop("pro rat")
        season_stats.pop("rat")
        season_stats.pop("avg")

        season_stats["year"] = season_stats.pop("year").split()[0]

        from pprint import pprint

        for fld in ["cmp", "att", "yds", "td", "ints", "sack", "year"]:
            try:
                season_stats[fld] = int(season_stats[fld] or 0)
            except ValueError as e:
                print(f"Invalid value for field {fld}: {season_stats[fld]}")
                print("Full season_stats_dict")
                pprint(season_stats, indent=4)
                raise e

        for fld in ["cmp_pct", "qb_rtg"]:
            try:
                season_stats[fld] = float(season_stats[fld] or 0.0)
            except ValueError as e:
                print(f"Invalid value for field {fld}: {season_stats[fld]}")
                print("Full season_stats_dict")
                pprint(season_stats, indent=4)
                raise e

        return season_stats

    def _transform_stats(self, season_stats):
        match self.position:
            case "QB":
                return self._transform_passing_stats(season_stats=season_stats)
            case "RB":
                pass
            case "WR":
                pass
            case "TE":
                pass
            case "OL":
                pass
            case "DL":
                pass
            case "EDGE":
                pass
            case "LB":
                pass
            case "DB":
                pass
        return season_stats

    def _extract_stats_object(self, div):
        stats_table = div.find("table")
        header_values = [
            th.get_text(strip=True).lower()
            for th in stats_table.thead.find_all("th", class_="player-season-avg__stat")
            if th.get_text(strip=True)
        ]
        seasons = []

        gp_and_snaps = self._extract_games_and_snaps()

        for row in stats_table.tbody.find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all("td")]

            if self.position == "QB":
                season_stats = dict(zip(header_values, cells))
                season_stats = self._transform_stats(season_stats=season_stats)
                stats_obj = PassingStats(**season_stats, **gp_and_snaps)
            elif self.position in ["RB"]:
                season_stats = {
                    "year": cells[0],
                    **gp_and_snaps,
                    "rushing": {
                        "att": int(cells[1] or "0"),
                        "yds": int(cells[2] or "0"),
                        "avg": float(cells[3] or "0"),
                        "td": int(cells[4] or "0"),
                    },
                    "receiving": {
                        "rec": int(cells[5] or "0"),
                        "yds": int(cells[6] or "0"),
                        "avg": float(cells[7] or "0"),
                        "td": int(cells[8] or "0"),
                    },
                }
                rushing_stats = RushingStats(
                    year=season_stats["year"], **season_stats["rushing"]
                )
                receiving_stats = ReceivingStats(
                    year=season_stats["year"], **season_stats["receiving"]
                )
                stats_obj = OffenseSkillPlayerStats(
                    year=season_stats["year"],
                    rushing=rushing_stats,
                    receiving=receiving_stats,
                )
            elif self.position in ["WR", "TE"]:
                season_stats = {
                    "year": cells[0],
                    **gp_and_snaps,
                    "receiving": {
                        "rec": int(cells[1] or "0"),
                        "yds": int(cells[2] or "0"),
                        "avg": float(cells[3] or "0"),
                        "td": int(cells[4] or "0"),
                    },
                    "rushing": {
                        "att": int(cells[5] or "0"),
                        "yds": int(cells[6] or "0"),
                        "avg": float(cells[7] or "0"),
                        "td": int(cells[8] or "0"),
                    },
                }
                rushing_stats = RushingStats(
                    year=season_stats["year"], **season_stats["rushing"]
                )
                receiving_stats = ReceivingStats(
                    year=season_stats["year"], **season_stats["receiving"]
                )
                stats_obj = OffenseSkillPlayerStats(
                    year=season_stats["year"],
                    rushing=rushing_stats,
                    receiving=receiving_stats,
                )
            elif self.position == "OL":
                stats_obj = gp_and_snaps
            elif self.position in ["DL", "EDGE", "LB", "DB"]:
                season_stats = {
                    "year": int(cells[0].split()[0]),
                    **gp_and_snaps,
                    "tackle": {
                        "total": int(cells[1] or "0"),
                        "solo": int(cells[2] or "0"),
                        "ff": int(cells[3] or "0"),
                        "sacks": float(cells[4] or "0"),
                    },
                    "interception": {
                        "ints": int(cells[5] or "0"),
                        "yds": int(cells[6] or "0"),
                        "td": int(cells[7] or "0"),
                        "pds": int(cells[8] or "0"),
                    },
                }
                tackle_stats = TackleStats(
                    year=season_stats["year"], **season_stats["tackle"]
                )
                interception_stats = InterceptionStats(
                    year=season_stats["year"], **season_stats["interception"]
                )
                stats_obj = DefenseStats(
                    year=season_stats["year"],
                    tackle=tackle_stats,
                    interception=interception_stats,
                )
            else:
                raise ValueError(
                    f"Could not match position {self.position} to "
                    f"a position with a defined stats mapping."
                )

            seasons.append(stats_obj)

        seasons.sort(key=lambda stats: stats.year, reverse=True)

        return seasons

    ##### Ratings and Grades #####
    def _perform_rating_checks(self, table: Tag):
        ovr_rtg_label = table.find("th")
        if "overall rating" not in ovr_rtg_label.get_text().lower():
            raise ValueError(
                f"Unexpected label in first <th> element: {ovr_rtg_label.get_text}"
            )

    def _extract_ovr_rtg(self, row: Tag) -> float:
        ovr_rtg = float(row.find("span").get_text(strip=True).replace(" / 100", ""))
        return ovr_rtg

    def _extract_opposition_rtg(self, row: Tag) -> int:
        meter_div = row.find("div", class_="meter")
        rtg_as_str = meter_div["title"].split(":")[-1].strip().replace("%", "")
        return int(rtg_as_str)

    def _extract_skill_ratings(self, rows: List[Tag]) -> Dict:
        skills = {}
        for row in rows:
            skill_name, rating = (
                row.get_text(strip=True)
                .lower()
                .replace(" ", "_")
                .replace("%", "")
                .split(":")
            )

            if "/" in rating:
                rating = rating.split("/")[0]
            rating = float(rating.replace("_", ""))

            skills[skill_name.replace("/", "_")] = int(rating)

        return skills

    def _extract_proj_and_rankings(self, row) -> Dict:
        projection_label = self._get_tag_with_text(
            search_space=row, tag_name="span", text="draft projection"
        )
        projection = self._get_text_following_label(label_tag=projection_label)

        ovr_rank_label = self._get_tag_with_text(
            search_space=row, tag_name="span", text="overall rank"
        )
        ovr_rank = self._get_text_following_label(label_tag=ovr_rank_label)

        pos_rank_label = self._get_tag_with_text(
            search_space=row, tag_name="span", text="position rank"
        )
        pos_rank = self._get_text_following_label(label_tag=pos_rank_label)

        return {
            "draft_projection": projection,
            "overall_rank": ovr_rank,
            "position_rank": pos_rank,
        }

    def _get_projection_ranks_row(self, rows: List[Tag]) -> Optional[Tag]:
        for row in rows:
            if "draft projection" in row.get_text().lower():
                return row
        return None

    def _gather_skill_rtg_rows(
        self, rows: List[Tag], sentinel_val: str = "draft projection"
    ) -> List[Tag]:
        skill_rows = []
        for row in rows:
            if sentinel_val in row.get_text().lower():
                break
            skill_rows.append(row)

        return skill_rows

    def _construct_skill_ratings_obj(self, ratings: Dict) -> SkillRatings:
        skills = None
        match self.position:
            case "QB":
                skills = PassingSkills(**ratings)
            case "RB":
                skills = RunningBackSkills(**ratings)
            case "WR" | "TE":
                skills = PassCatcherSkills(**ratings)
            case "OL":
                skills = OffensiveLinemanSkills(**ratings)
            case "DL" | "EDGE":
                skills = DefensiveLinemanSkills(**ratings)
            case "LB":
                skills = LinebackerSkills(**ratings)
            case "DB":
                skills = DefensiveBackSkills(**ratings)
            case _:
                raise ValueError(
                    f"Could not find skill ratings for position: {self.position}"
                )
        return skills

    ##### Outlet ratings ####
    def _extract_outlet_ratings(self, table: Tag) -> Dict[str, Optional[float]]:
        return {
            "espn": self._extract_espn(table=table),
            "rivals": self._extract_rivals(table=table),
            "rtg_247": self._extract_247(table=table),
        }

    def _extract_rivals(self, table: Tag) -> Optional[float]:
        rivals_row = self._get_tag_with_text(
            search_space=table, tag_name="span", text="rivals"
        )
        if rivals_row:
            rivals_rtg = float(
                rivals_row.get_text(strip=True).split(":")[-1].split()[0]
            )
        else:
            rivals_rtg = None

        return rivals_rtg

    def _extract_247(self, table: Tag) -> Optional[float]:
        rtg = None
        sports_247_rtg_row = self._get_tag_with_text(
            search_space=table, tag_name="span", text="247"
        )
        if sports_247_rtg_row:
            rtg = float(
                sports_247_rtg_row.get_text(strip=True).split()[-1].split("/")[0]
            )

        return rtg

    def _extract_espn(self, table: Tag) -> Optional[float]:
        rtg = None
        espn_rtg_row = self._get_tag_with_text(
            search_space=table, tag_name="span", text="espn"
        )
        if espn_rtg_row:
            rtg = float(espn_rtg_row.get_text(strip=True).split()[-1].split("/")[0])

        return rtg

    def _extract_ratings_comps_tables(self):
        ratings_and_rankings = [
            table
            for table in self.soup.find_all("table", class_="starRatingTable")
            if not table.find("th", string=lambda s: "measurables" in s.lower())
        ]

        ratings = ratings_and_rankings[0]
        if len(ratings_and_rankings) > 1:
            comparisons = ratings_and_rankings[1]
        else:
            comparisons = None
        return ratings, comparisons

    def _extract_average_ranks(self):
        rankings_div = self.soup.find("div", class_="rankingBox")
        avg_ovr, avg_pos = rankings_div.find_all("div", class_="rankVal")
        return {
            "avg_overall_rank": float(avg_ovr.get_text(strip=True)),
            "avg_position_rank": float(avg_pos.get_text(strip=True)),
        }


class DraftBuzzScraper:
    """Main orchestrator for scraping NFL Draft Buzz prospect pages."""

    def __init__(
        self,
        playwright: Playwright,
        profile_root_dir: Path = None,
        fetcher: PageFetcher = None,
    ):
        self.profile_root_dir = profile_root_dir
        self.base_url = "https://www.nfldraftbuzz.com"
        self.fetcher = fetcher or PageFetcher(
            playwright=playwright, base_url=self.base_url
        )
        self.parser = None
        self.position_rankings_used = defaultdict(list)

        self.current_prospect_data: ProspectDataSoup | None = None

    def scrape_from_url(self, url: str, position: str) -> ProspectDataSoup:
        """Scrape prospect data from a URL."""
        self.current_prospect_data = None
        print("Parsing prospect data...")
        full_url = f"{self.base_url}{url}"
        base_soup = self.fetcher.fetch_soup(url=full_url)
        self.parser = ProspectParserSoup(soup=base_soup, position=position)
        prospect_data = self.parser.parse()

        print("Fetching stats page")
        slug_parts = url.split("/")
        player_stats_slug = f"/{slug_parts[1]}/stats/{slug_parts[-1]}"
        stats_full_url = f"{self.base_url}{player_stats_slug}"

        stats_soup = self.fetcher.fetch_soup(url=stats_full_url)
        print("Attempting to parse stats")
        stats_data = self.parser.parse_stats(soup=stats_soup)
        prospect_data.stats = stats_data

        self.current_prospect_data = prospect_data
        return prospect_data

    def save_player_photo_to_disk(self):
        print(f"Saving photo for {self.current_prospect_data.basic_info.full_name}")
        print(f"Fetching image from {self.current_prospect_data.basic_info.photo_url}")

        response = requests.get(self.current_prospect_data.basic_info.photo_url)
        response.raise_for_status()
        file_name = f"{self.current_prospect_data.basic_info.full_name}.png"

        output_path = Path(self.profile_root_dir, "player_photos", file_name)
        output_path.write_bytes(response.content)
        print(f"Wrote image to disk at {output_path}")

    def print_summary(self, data: ProspectDataSoup) -> None:
        """Print summary of extracted data."""
        print("\nExtracted data summary:")
        print(f"  Name: {data.basic_info.full_name}")
        print(f"  Position: {data.basic_info.position}")
        print(f"  School: {data.basic_info.college}")
        print(f"  Rating: {data.ratings.overall_rating}/100")
        print(f"  Draft Projection: {data.ratings.draft_projection}")
        print(f"  Strengths: {len(data.scouting_report.strengths)} items")
        print(f"  Weaknesses: {len(data.scouting_report.weaknesses)} items")
        print(f"  Image: {'Yes' if data.basic_info.photo_path.exists() else 'No'}")


class ProspectProfileListExtractor:
    MAX_RETRIES = 3

    def __init__(self, playwright: Playwright):
        self.playwright = playwright
        self.browser = self._launch_browser()
        self.base_url = "https://www.nfldraftbuzz.com"

    def _launch_browser(self) -> Browser:
        """Launch a new browser instance."""
        return self.playwright.firefox.launch(headless=False)

    def _ensure_browser_connected(self) -> None:
        """Ensure browser is connected, relaunch if necessary."""
        if not self.browser.is_connected():
            print("Browser disconnected, relaunching...")
            self.browser = self._launch_browser()

    def _navigate_with_retry(self, page, url: str) -> None:
        """Navigate to URL with retry logic for browser crashes."""
        for attempt in range(self.MAX_RETRIES):
            try:
                page.goto(url)
                return
            except PlaywrightError as e:
                error_msg = str(e).lower()
                if (
                    "target closed" in error_msg
                    or "browser has been closed" in error_msg
                ):
                    print(
                        f"Browser/target closed during navigation (attempt {attempt + 1}/{self.MAX_RETRIES})"
                    )
                    raise  # Let caller handle browser relaunch
                raise

    def extract_prospect_hrefs(self, page):
        print(f"Extracting prospect hrefs for {page.url}")
        rows = page.locator("#positionRankTable tbody tr")
        data_hrefs = rows.evaluate_all(
            "rows => rows.map(row => row.getAttribute('data-href'))"
        )
        return data_hrefs

    def extract_prospect_urls_for_position(self, pos: str) -> List[str]:
        all_profiles = []

        path = f"/positions/{pos}/1/2026"
        full_url = f"{self.base_url}{path}"

        page = self._create_page_with_retry(full_url)
        all_profiles.extend(self.extract_prospect_hrefs(page=page))
        links = page.locator("ul.pagination li.page-item a.page-link[href]")
        position_page_hrefs = links.evaluate_all(
            "anchors => anchors.map(a => a.getAttribute('href'))"
        )

        for path in position_page_hrefs:
            page.close()
            full_url = f"{self.base_url}{path}"
            page = self._create_page_with_retry(full_url)
            time.sleep(uniform(4.5, 5.5))

            prospect_hrefs = self.extract_prospect_hrefs(page)
            all_profiles.extend(prospect_hrefs)
        page.close()
        return all_profiles

    def _create_page_with_retry(self, url: str):
        """Create a new page and navigate to URL with retry on browser crash."""
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                self._ensure_browser_connected()
                page = self.browser.new_page()
                page.goto(url, timeout=0)
                return page
            except PlaywrightError as e:
                last_error = e
                error_msg = str(e).lower()
                if (
                    "target closed" in error_msg
                    or "browser has been closed" in error_msg
                ):
                    print(
                        f"Browser/target closed (attempt {attempt + 1}/{self.MAX_RETRIES}), relaunching..."
                    )
                    try:
                        self.browser.close()
                    except Exception:
                        pass
                    self.browser = self._launch_browser()
                    time.sleep(1)
                else:
                    raise
        raise last_error
