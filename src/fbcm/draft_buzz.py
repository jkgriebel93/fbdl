#!/usr/bin/env python3
"""
NFL Draft Buzz Prospect Scraper to Word Document

Extracts prospect information from nfldraftbuzz.com and creates a formatted Word document.
Uses Playwright for browser automation to bypass Cloudflare protection.

Usage:
    python nfl_prospect_to_docx.py <url>
    python nfl_prospect_to_docx.py https://www.nfldraftbuzz.com/Player/Dante-Moore-QB-UCLA
    python nfl_prospect_to_docx.py <url> -o custom_output.docx

Requirements:
    pip install playwright python-docx lxml --break-system-packages
    playwright install firefox
"""

import argparse
import io
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field
from playwright.sync_api import sync_playwright, Playwright, Browser, TimeoutError as PlaywrightTimeout, Error as PlaywrightError
from random import uniform
from typing import Optional, List, Dict, Tuple
from urllib.parse import urljoin
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


POSITIONS = ["QB", "RB", "WR", "TE", "OL", "DL", "EDGE", "LB", "DB"]

@dataclass
class ProspectData:
    """Container for all prospect information."""
    name: str = ""
    position: str = ""
    school: str = ""
    jersey: str = ""
    play_style: str = ""
    draft_year: str = ""
    last_updated: str = ""

    # Basic info
    height: str = ""
    weight: str = ""
    forty: str = ""
    age: str = ""
    dob: str = ""
    hometown: str = ""
    player_class: str = ""

    # Ratings
    overall_rating: str = ""
    position_rank: str = ""
    overall_rank: str = ""
    draft_projection: str = ""
    defense_rating: str = ""

    # Stats
    qb_rating: str = ""
    yards: str = ""
    comp_pct: str = ""
    tds: str = ""
    ints: str = ""
    rush_avg: str = ""
    college_games: str = ""
    college_snaps: str = ""

    # Skill ratings (percentiles)
    skill_ratings: Dict[str, str] = field(default_factory=dict)

    # Recruiting grades
    espn_rating: str = ""
    rating_247: str = ""
    rivals_rating: str = ""

    # Player comparisons
    comparisons: List[tuple] = field(default_factory=list)

    # Scouting content
    bio: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    summary: str = ""

    # Other scouts' rankings
    avg_overall_rank: str = ""
    avg_position_rank: str = ""

    # Profile image
    image_data: Optional[bytes] = None
    image_type: str = "jpeg"

    def to_dict(self) -> Dict[str, any]:
        """Convert prospect data to a dictionary, excluding binary image data."""
        return {key: value for key, value in vars(self).items()
                if key not in ["image_data"]}


class PageFetcher:
    """Handles fetching web pages using Playwright browser automation."""

    DEFAULT_USER_AGENT = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    DEFAULT_VIEWPORT = {'width': 1920, 'height': 1080}
    PAGE_LOAD_TIMEOUT = 60000
    CONTENT_WAIT_TIME = 3000

    IMAGE_SELECTORS = [
        'img[src*="Imagn"]',
        'img[src*="player"]',
        'img[src*="Player"]',
        'img[src*="headshot"]',
        'img[src*="photo"]',
        '.player-image img',
        '.profile-image img',
        'article img',
        'main img',
    ]

    SKIP_IMAGE_PATTERNS = ['logo', 'icon', 'ad', 'sponsor', 'badge', 'button', '1x1']

    MAX_RETRIES = 3

    def __init__(self, playwright: Playwright, headless: bool = False):
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

    def fetch(self, url: str, attempt_image_fetch: bool = False) -> Tuple[str, Optional[bytes], str]:
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
                if "target closed" in error_msg or "browser has been closed" in error_msg:
                    print(f"Browser/target closed (attempt {attempt + 1}/{self.MAX_RETRIES}), relaunching...")
                    try:
                        self.browser.close()
                    except Exception:
                        pass  # Browser may already be closed
                    self.browser = self._launch_browser()
                    time.sleep(1)  # Brief pause before retry
                else:
                    raise  # Re-raise if it's a different Playwright error

        raise last_error  # All retries exhausted

    def _fetch_with_page(self, url: str, attempt_image_fetch: bool) -> Tuple[str, Optional[bytes], str]:
        """Internal method to fetch a page. May raise PlaywrightError."""
        self._ensure_browser_connected()
        print("Opening new page...")

        page = self.browser.new_page()
        try:
            print(f"Navigating to: {url}")
            try:
                page.goto(url, wait_until='networkidle', timeout=self.PAGE_LOAD_TIMEOUT)
            except PlaywrightTimeout:
                print("Page load timeout, continuing with partial content...")

            page.wait_for_timeout(self.CONTENT_WAIT_TIME)

            text_content = page.evaluate('() => document.body.innerText')
            if attempt_image_fetch:
                image_data, image_type = self._find_and_download_image(page, url)
            else:
                image_data = None
                image_type = None
            return text_content, image_data, image_type
        finally:
            page.close()

    def _find_and_download_image(self, page, base_url: str) -> Tuple[Optional[bytes], str]:
        """Find and download the player image from the page."""
        image_url = self._find_image_url(page)

        if not image_url:
            image_url = self._find_any_large_image(page)

        if image_url:
            return self._download_image(page, image_url, base_url)

        return None, "jpeg"

    def _find_image_url(self, page) -> Optional[str]:
        """Try to find image URL using predefined selectors."""
        for selector in self.IMAGE_SELECTORS:
            try:
                img_element = page.query_selector(selector)
                if img_element:
                    src = img_element.get_attribute('src')
                    if src and not self._should_skip_image(src):
                        return src
            except Exception:
                continue
        return None

    def _find_any_large_image(self, page) -> Optional[str]:
        """Fallback: try to find any large player image."""
        try:
            images = page.query_selector_all('img')
            for img in images:
                src = img.get_attribute('src')
                if src and not self._should_skip_image(src):
                    if 'nfldraftbuzz' in src or 'imagn' in src.lower() or 'player' in src.lower():
                        return src
        except Exception:
            pass
        return None

    def _should_skip_image(self, src: str) -> bool:
        """Check if an image URL should be skipped."""
        src_lower = src.lower()
        return any(pattern in src_lower for pattern in self.SKIP_IMAGE_PATTERNS)

    def _download_image(self, page, image_url: str, base_url: str) -> Tuple[Optional[bytes], str]:
        """Download image from URL."""
        print(f"Found player image: {image_url[:80]}...")
        try:
            image_url = self._make_absolute_url(image_url, base_url)
            response = page.request.get(image_url)
            if response.ok:
                image_data = response.body()
                image_type = self._get_image_type(response.headers.get('content-type', ''))
                print(f"Downloaded image: {len(image_data)} bytes ({image_type})")
                return image_data, image_type
        except Exception as e:
            print(f"Failed to download image: {e}")
        return None, "jpeg"

    @staticmethod
    def _make_absolute_url(url: str, base_url: str) -> str:
        """Convert relative URL to absolute."""
        if url.startswith('//'):
            return 'https:' + url
        elif url.startswith('/'):
            return urljoin(base_url, url)
        return url

    @staticmethod
    def _get_image_type(content_type: str) -> str:
        """Determine image type from content-type header."""
        if 'png' in content_type:
            return 'png'
        elif 'gif' in content_type:
            return 'gif'
        elif 'webp' in content_type:
            return 'webp'
        return 'jpeg'


class ProspectParser:
    """Parses page text content and extracts prospect data."""

    POSITIONS = {'QB', 'RB', 'WR', 'TE', 'OL', 'DL', 'EDGE', 'LB', 'DB', 'CB', 'S', 'PK', 'P'}

    SKILL_PATTERNS = [
        ('Release Speed', r'RELEASE SPEED:\s*\n?\s*(\d+)%'),
        ('Short Passing', r'SHORT PASSING:\s*\n?\s*(\d+)%'),
        ('Medium Passing', r'MEDIUM PASSING:\s*\n?\s*(\d+)%'),
        ('Long Passing', r'LONG PASSING:\s*\n?\s*(\d+)%'),
        ('Rush/Scramble', r'RUSH/SCRAMBLE:\s*\n?\s*(\d+)%'),
    ]

    def parse(self, text: str, image_data: Optional[bytes] = None,
              image_type: str = "jpeg") -> ProspectData:
        """Parse page text and extract all prospect data."""
        data = ProspectData()
        data.image_data = image_data
        data.image_type = image_type

        self._parse_name(text, data)
        self._parse_basic_info(text, data)
        self._parse_ratings(text, data)
        self._parse_stats(text, data)
        self._parse_skill_ratings(text, data)
        self._parse_recruiting_grades(text, data)
        self._parse_comparisons(text, data)
        self._parse_scouting_content(text, data)
        self._parse_consensus_rankings(text, data)

        return data

    def _parse_name(self, text: str, data: ProspectData) -> None:
        """Extract player name from page text."""
        pos_pattern = '|'.join(self.POSITIONS)
        title_match = re.search(
            rf'([A-Z]+)\s+([A-Z]+)\s+({pos_pattern})\s+[A-Z]+\s*\|\s*NFL DRAFT',
            text
        )
        if title_match:
            data.name = f"{title_match.group(1).title()} {title_match.group(2).title()}"
            return

        name_match = re.search(r'SIMULATOR\s*\n?\s*([A-Z]+)\s*\n\s*([A-Z]+)\s*\n?\s*HEIGHT', text)
        if name_match:
            data.name = f"{name_match.group(1).title()} {name_match.group(2).title()}"

    def _parse_basic_info(self, text: str, data: ProspectData) -> None:
        """Extract basic player information."""
        patterns = {
            'height': (r'HEIGHT\s*\n?\s*(\d+-\d+)', 'height'),
            'weight': (r'WEIGHT\s*\n?\s*(\d+)', 'weight'),
            'school': (r'COLLEGE\s*\n?\s*([A-Za-z\s]+?)\s*\n', 'school'),
            'position': (rf'POSITION\s*\n?\s*({"|".join(self.POSITIONS)})', 'position'),
            'player_class': (r'CLASS\s*\n?\s*(Freshman|Sophomore|Junior|Senior|RS\s*\w+)', 'player_class'),
            'hometown': (r'HOME\s*TOWN\s*\n?\s*([A-Za-z\s,]+?)(?:\n|$)', 'hometown'),
            'jersey': (r'JERSEY:\s*#(\d+)', 'jersey'),
            'play_style': (r'PLAY STYLE:\s*([A-Z\s]+?)(?:\n|LAST)', 'play_style'),
            'last_updated': (r'LAST UPDATED:\s*(\d+/\d+/\d+)', 'last_updated'),
            'draft_year': (r'DRAFT YEAR:\s*(\d+)', 'draft_year'),
            'college_games': (r'COLLEGE GAMES:\s*(\d+)', 'college_games'),
            'college_snaps': (r'COLLEGE SNAPS:\s*(\d+)', 'college_snaps'),
        }

        for _, (pattern, attr) in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE if attr == 'player_class' else 0)
            if match:
                value = match.group(1).strip() if attr in ('school', 'hometown', 'play_style') else match.group(1)
                setattr(data, attr, value)

        # Age and DOB combined pattern
        age_match = re.search(r'AGE:\s*([\d.]+)\s*DOB:\s*(\d+/\d+/\d+)', text)
        if age_match:
            data.age = age_match.group(1)
            data.dob = age_match.group(2)

        # Height/Weight with percentiles
        hw_match = re.search(r'HEIGHT:\s*(\d+-\d+)\s*\((\d+)%\*?\)\s*WEIGHT:\s*(\d+)\s*\((\d+)%', text)
        if hw_match:
            data.height = f"{hw_match.group(1)} ({hw_match.group(2)}%)"
            data.weight = f"{hw_match.group(3)} ({hw_match.group(4)}%)"

        # Forty time with percentile
        forty_match = re.search(r'FORTY TIME:\s*([\d.]+)\s*SECONDS\s*\((\d+)%', text)
        if forty_match:
            data.forty = f"{forty_match.group(1)} ({forty_match.group(2)}%)"
        elif not data.forty:
            forty_simple = re.search(r'(\d+\.\d+)\s*\n?\s*FORTY\s*YD\s*TIME', text)
            if forty_simple:
                data.forty = forty_simple.group(1)

    def _parse_ratings(self, text: str, data: ProspectData) -> None:
        """Extract player ratings."""
        patterns = {
            'overall_rating': r'(\d+\.\d+)\s*/100\s*\n?\s*PLAYER\s*RATING',
            'position_rank': r'(\d+)\s*\n?\s*POSITION\s*RANK',
            'overall_rank': r'OVERALL RANK:\s*#(\d+)',
            'draft_projection': r'DRAFT PROJECTION:\s*([^\n]+)',
            'defense_rating': r'DEFENSE RATING:\s*\n?\s*(\d+)%',
        }

        for attr, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip() if attr == 'draft_projection' else match.group(1)
                setattr(data, attr, value)

    def _parse_stats(self, text: str, data: ProspectData) -> None:
        """Extract player statistics (primarily for QBs)."""
        patterns = {
            'qb_rating': r'QB RATING\s*\n?\s*([\d.]+)',
            'yards': r'YDS\s*\n?\s*(\d+)',
            'comp_pct': r'COMP %\s*\n?\s*([\d.]+)',
            'tds': r'TDS\s*\n?\s*(\d+)',
            'ints': r'INTS\s*\n?\s*(\d+)',
            'rush_avg': r'RUSH AVG\s*\n?\s*([\d.]+)',
        }

        for attr, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                setattr(data, attr, match.group(1))

    def _parse_skill_ratings(self, text: str, data: ProspectData) -> None:
        """Extract skill ratings (percentiles)."""
        for skill_name, pattern in self.SKILL_PATTERNS:
            match = re.search(pattern, text)
            if match:
                data.skill_ratings[skill_name] = match.group(1)

    def _parse_recruiting_grades(self, text: str, data: ProspectData) -> None:
        """Extract recruiting grades from various services."""
        espn_match = re.search(r'ESPN RATING:\s*([\d/]+)', text)
        if espn_match:
            data.espn_rating = espn_match.group(1)

        rating247_match = re.search(r'247 RATING:\s*([\d/]+)', text)
        if rating247_match:
            data.rating_247 = rating247_match.group(1)

        rivals_match = re.search(r'RIVALS RATING:\s*([\d.]+\s*\([^)]+\))', text)
        if rivals_match:
            data.rivals_rating = rivals_match.group(1)

    def _parse_comparisons(self, text: str, data: ProspectData) -> None:
        """Extract player comparisons."""
        comp_pattern = r'([A-Z][a-z]+)\s+([A-Z]+)\s*-\s*([A-Z\s]+?)\s*\n?\s*(\d+)%'
        for match in re.finditer(comp_pattern, text):
            name = f"{match.group(1)} {match.group(2)}"
            school = match.group(3).strip()
            similarity = match.group(4)
            data.comparisons.append((name, school, similarity))

    def _parse_scouting_content(self, text: str, data: ProspectData) -> None:
        """Extract scouting report content."""
        # Bio
        bio_match = re.search(r'DRAFT PROFILE: BIO\s*\n(.+?)(?=SCOUTING REPORT: STRENGTHS)', text, re.DOTALL)
        if bio_match:
            data.bio = bio_match.group(1).strip()

        # Strengths
        strengths_match = re.search(
            r'SCOUTING REPORT: STRENGTHS\s*\n(.+?)(?=SCOUTING REPORT: WEAKNESSES)', text, re.DOTALL
        )
        if strengths_match:
            data.strengths = self._split_scouting_points(strengths_match.group(1))

        # Weaknesses
        weaknesses_match = re.search(
            r'SCOUTING REPORT: WEAKNESSES\s*\n(.+?)(?=SCOUTING REPORT: SUMMARY)', text, re.DOTALL
        )
        if weaknesses_match:
            data.weaknesses = self._split_scouting_points(weaknesses_match.group(1))

        # Summary
        summary_match = re.search(r'SCOUTING REPORT: SUMMARY\s*\n(.+?)(?=NEXT:|HOW OTHER)', text, re.DOTALL)
        if summary_match:
            data.summary = summary_match.group(1).strip()

    @staticmethod
    def _split_scouting_points(text: str) -> List[str]:
        """Split scouting text into individual points."""
        points = [s.strip() for s in re.split(r'\.\s+(?=[A-Z])', text.strip()) if s.strip()]
        return [s if s.endswith('.') else s + '.' for s in points]

    def _parse_consensus_rankings(self, text: str, data: ProspectData) -> None:
        """Extract consensus rankings from other scouts."""
        avg_overall_match = re.search(r'ALL SCOUTS AVERAGE\s*OVERALL RANK\s*\n?\s*([\d.]+)', text)
        if avg_overall_match:
            data.avg_overall_rank = avg_overall_match.group(1)

        avg_pos_match = re.search(r'ALL SCOUTS AVERAGE\s*POSITION RANK\s*\n?\s*([\d.]+)', text)
        if avg_pos_match:
            data.avg_position_rank = avg_pos_match.group(1)

    def extract_name_from_url(self, url: str) -> Optional[str]:
        """Extract player name from URL as fallback."""
        url_match = re.search(r'/Player/([^/]+)', url)
        if url_match:
            name_parts = url_match.group(1).replace('-', ' ').split()
            name_parts = [p for p in name_parts if p.upper() not in self.POSITIONS]
            if len(name_parts) >= 2:
                return ' '.join(name_parts[:2])
        return None


class WordDocumentGenerator:
    """Generates Word documents from prospect data."""

    HEADER_COLOR = "003366"
    STATS_HEADER_COLOR = "006633"
    SKILLS_HEADER_COLOR = "663399"
    COMPARISONS_HEADER_COLOR = "CC6600"

    def __init__(self):
        self.doc = None

    def generate(self, data: ProspectData, output_path: str) -> None:
        """Create a formatted Word document from prospect data."""
        self.doc = Document()
        self._setup_styles()

        self._add_title(data)
        self._add_player_image(data)
        self._add_player_information(data)
        self._add_ratings(data)
        self._add_statistics(data)
        self._add_skill_ratings(data)
        self._add_recruiting_grades(data)
        self._add_comparisons(data)
        self._add_bio(data)
        self._add_strengths(data)
        self._add_weaknesses(data)
        self._add_summary(data)
        self._add_consensus_rankings(data)
        self._add_footer(data)

        self.doc.save(output_path)
        print(f"Document saved to: {output_path}")

    def _setup_styles(self) -> None:
        """Set up document styles."""
        style = self.doc.styles['Normal']
        style.font.name = 'Calibri'
        style.font.size = Pt(11)

    def _add_title(self, data: ProspectData) -> None:
        """Add title and subtitle to document."""
        title = self.doc.add_heading(level=0)
        title_run = title.add_run(f"{data.name.upper()}")
        title_run.font.size = Pt(28)
        title_run.font.bold = True
        title_run.font.color.rgb = RGBColor(0, 51, 102)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        subtitle = self.doc.add_paragraph()
        subtitle_run = subtitle.add_run(f"{data.position} | {data.school}")
        subtitle_run.font.size = Pt(16)
        subtitle_run.font.color.rgb = RGBColor(102, 102, 102)
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

        self.doc.add_paragraph("─" * 60).alignment = WD_ALIGN_PARAGRAPH.CENTER

    def _add_player_image(self, data: ProspectData) -> None:
        """Add player image if available."""
        if not data.image_data:
            return

        try:
            image_para = self.doc.add_paragraph()
            image_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = image_para.add_run()
            image_stream = io.BytesIO(data.image_data)
            run.add_picture(image_stream, width=Inches(4))

            caption = self.doc.add_paragraph()
            caption_run = caption.add_run(f"{data.name} - {data.school}")
            caption_run.font.size = Pt(10)
            caption_run.font.italic = True
            caption_run.font.color.rgb = RGBColor(102, 102, 102)
            caption.alignment = WD_ALIGN_PARAGRAPH.CENTER

            self.doc.add_paragraph()
        except Exception as e:
            print(f"Warning: Could not add image to document: {e}")

    def _add_player_information(self, data: ProspectData) -> None:
        """Add player information table."""
        self.doc.add_heading("PLAYER INFORMATION", level=1)

        info_items = [
            ("Jersey", f"#{data.jersey}" if data.jersey else "N/A"),
            ("Play Style", data.play_style or "N/A"),
            ("Height", data.height or "N/A"),
            ("Weight", data.weight or "N/A"),
            ("40-Yard Dash", data.forty or "N/A"),
            ("Age", data.age or "N/A"),
            ("DOB", data.dob or "N/A"),
            ("Hometown", data.hometown or "N/A"),
            ("Class", data.player_class or "N/A"),
            ("Draft Year", data.draft_year or "N/A"),
            ("College Games", data.college_games or "N/A"),
            ("College Snaps", data.college_snaps or "N/A"),
        ]

        info_table = self.doc.add_table(rows=0, cols=4)
        info_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        for i in range(0, len(info_items), 2):
            row = info_table.add_row()
            row.cells[0].text = info_items[i][0] + ":"
            row.cells[0].paragraphs[0].runs[0].bold = True
            row.cells[1].text = info_items[i][1]
            if i + 1 < len(info_items):
                row.cells[2].text = info_items[i + 1][0] + ":"
                row.cells[2].paragraphs[0].runs[0].bold = True
                row.cells[3].text = info_items[i + 1][1]

        self.doc.add_paragraph()

    def _add_ratings(self, data: ProspectData) -> None:
        """Add ratings and rankings table."""
        self.doc.add_heading("RATINGS & RANKINGS", level=1)

        ratings_table = self.doc.add_table(rows=2, cols=4)
        ratings_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        headers = ["Overall Rating", "Position Rank", "Overall Rank", "Draft Projection"]
        values = [
            f"{data.overall_rating}/100" if data.overall_rating else "N/A",
            f"#{data.position_rank} ({data.position})" if data.position_rank else "N/A",
            f"#{data.overall_rank}" if data.overall_rank else "N/A",
            data.draft_projection or "N/A"
        ]

        for i, header in enumerate(headers):
            cell = ratings_table.rows[0].cells[i]
            cell.text = header
            cell.paragraphs[0].runs[0].bold = True
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            self._set_cell_shading(cell, self.HEADER_COLOR)
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

        for i, value in enumerate(values):
            cell = ratings_table.rows[1].cells[i]
            cell.text = value
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            self._set_cell_shading(cell, "E6F2FF")

        self.doc.add_paragraph()

    def _add_statistics(self, data: ProspectData) -> None:
        """Add statistics table (for QBs)."""
        if data.position != "QB" or not any([data.qb_rating, data.yards, data.comp_pct]):
            return

        self.doc.add_heading("STATISTICS", level=1)

        stats_table = self.doc.add_table(rows=2, cols=6)
        stats_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        stat_headers = ["QB Rating", "Yards", "Comp %", "TDs", "INTs", "Rush Avg"]
        stat_values = [
            data.qb_rating or "N/A",
            data.yards or "N/A",
            f"{data.comp_pct}%" if data.comp_pct else "N/A",
            data.tds or "N/A",
            data.ints or "N/A",
            data.rush_avg or "N/A"
        ]

        for i, header in enumerate(stat_headers):
            cell = stats_table.rows[0].cells[i]
            cell.text = header
            cell.paragraphs[0].runs[0].bold = True
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            self._set_cell_shading(cell, self.STATS_HEADER_COLOR)
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

        for i, value in enumerate(stat_values):
            cell = stats_table.rows[1].cells[i]
            cell.text = value
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            self._set_cell_shading(cell, "E6FFE6")

        self.doc.add_paragraph()

    def _add_skill_ratings(self, data: ProspectData) -> None:
        """Add skill ratings table."""
        if not data.skill_ratings:
            return

        self.doc.add_heading("SKILL RATINGS", level=1)

        skills_table = self.doc.add_table(rows=len(data.skill_ratings) + 1, cols=2)
        skills_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        skills_table.rows[0].cells[0].text = "Skill"
        skills_table.rows[0].cells[1].text = "Percentile"
        for cell in skills_table.rows[0].cells:
            cell.paragraphs[0].runs[0].bold = True
            self._set_cell_shading(cell, self.SKILLS_HEADER_COLOR)
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

        for i, (skill, rating) in enumerate(data.skill_ratings.items(), 1):
            skills_table.rows[i].cells[0].text = skill
            skills_table.rows[i].cells[1].text = f"{rating}%"
            skills_table.rows[i].cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        self.doc.add_paragraph()

    def _add_recruiting_grades(self, data: ProspectData) -> None:
        """Add recruiting grades section."""
        if not any([data.espn_rating, data.rating_247, data.rivals_rating]):
            return

        self.doc.add_heading("RECRUITING GRADES", level=1)

        grades_para = self.doc.add_paragraph()
        if data.espn_rating:
            grades_para.add_run("ESPN: ").bold = True
            grades_para.add_run(f"{data.espn_rating}   ")
        if data.rating_247:
            grades_para.add_run("247 Sports: ").bold = True
            grades_para.add_run(f"{data.rating_247}   ")
        if data.rivals_rating:
            grades_para.add_run("Rivals: ").bold = True
            grades_para.add_run(data.rivals_rating)

        self.doc.add_paragraph()

    def _add_comparisons(self, data: ProspectData) -> None:
        """Add player comparisons table."""
        if not data.comparisons:
            return

        self.doc.add_heading("PLAYER COMPARISONS", level=1)

        comp_table = self.doc.add_table(rows=len(data.comparisons) + 1, cols=3)
        comp_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        comp_headers = ["Player", "School", "Similarity"]
        for i, header in enumerate(comp_headers):
            cell = comp_table.rows[0].cells[i]
            cell.text = header
            cell.paragraphs[0].runs[0].bold = True
            self._set_cell_shading(cell, self.COMPARISONS_HEADER_COLOR)
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

        for i, (name, school, similarity) in enumerate(data.comparisons, 1):
            comp_table.rows[i].cells[0].text = name
            comp_table.rows[i].cells[1].text = school
            comp_table.rows[i].cells[2].text = f"{similarity}%"
            comp_table.rows[i].cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        self.doc.add_paragraph()

    def _add_bio(self, data: ProspectData) -> None:
        """Add biography section."""
        if not data.bio:
            return

        self.doc.add_heading("BACKGROUND", level=1)
        self._add_text_paragraphs(data.bio)
        self.doc.add_paragraph()

    def _add_strengths(self, data: ProspectData) -> None:
        """Add strengths section."""
        if not data.strengths:
            return

        self.doc.add_heading("SCOUTING REPORT: STRENGTHS", level=1)
        for strength in data.strengths:
            p = self.doc.add_paragraph(style='List Bullet')
            p.add_run(strength)
        self.doc.add_paragraph()

    def _add_weaknesses(self, data: ProspectData) -> None:
        """Add weaknesses section."""
        if not data.weaknesses:
            return

        self.doc.add_heading("SCOUTING REPORT: WEAKNESSES", level=1)
        for weakness in data.weaknesses:
            p = self.doc.add_paragraph(style='List Bullet')
            p.add_run(weakness)
        self.doc.add_paragraph()

    def _add_summary(self, data: ProspectData) -> None:
        """Add scouting summary section."""
        if not data.summary:
            return

        self.doc.add_heading("SCOUTING SUMMARY", level=1)
        self._add_text_paragraphs(data.summary)
        self.doc.add_paragraph()

    def _add_consensus_rankings(self, data: ProspectData) -> None:
        """Add consensus rankings section."""
        if not data.avg_overall_rank and not data.avg_position_rank:
            return

        self.doc.add_heading("CONSENSUS RANKINGS", level=1)

        consensus_para = self.doc.add_paragraph()
        if data.avg_overall_rank:
            consensus_para.add_run("Average Overall Rank: ").bold = True
            consensus_para.add_run(f"#{data.avg_overall_rank}   ")
        if data.avg_position_rank:
            consensus_para.add_run("Average Position Rank: ").bold = True
            consensus_para.add_run(f"#{data.avg_position_rank}")

    def _add_footer(self, data: ProspectData) -> None:
        """Add document footer."""
        self.doc.add_paragraph()
        footer = self.doc.add_paragraph("─" * 60)
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

        source_para = self.doc.add_paragraph()
        source_para.add_run("Source: NFLDraftBuzz.com").italic = True
        source_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        if data.last_updated:
            updated_para = self.doc.add_paragraph()
            updated_para.add_run(f"Last Updated: {data.last_updated}").italic = True
            updated_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def _add_text_paragraphs(self, text: str) -> None:
        """Add text split into paragraphs."""
        paragraphs = text.split('\n\n')
        for para_text in paragraphs:
            if para_text.strip():
                p = self.doc.add_paragraph(para_text.strip())
                p.paragraph_format.space_after = Pt(12)

    @staticmethod
    def _set_cell_shading(cell, color: str) -> None:
        """Set background color for a table cell."""
        shading = OxmlElement('w:shd')
        shading.set(qn('w:fill'), color)
        cell._tc.get_or_add_tcPr().append(shading)


class DraftBuzzScraper:
    """Main orchestrator for scraping NFL Draft Buzz prospect pages."""

    def __init__(self, playwright: Playwright, fetcher: PageFetcher = None, parser: ProspectParser = None,
                 doc_generator: WordDocumentGenerator = None):
        self.fetcher = fetcher or PageFetcher(playwright=playwright)
        self.parser = parser or ProspectParser()
        self.doc_generator = doc_generator or WordDocumentGenerator()
        self.base_url = "https://www.nfldraftbuzz.com"

    def scrape_from_url(self, url: str, skip_image: bool = False) -> ProspectData:
        """Scrape prospect data from a URL."""
        full_url = f"{self.base_url}{url}"

        text_content, image_data, image_type = self.fetcher.fetch(full_url)

        if skip_image:
            image_data = None

        print("Parsing prospect data...")
        data = self.parser.parse(text_content, image_data, image_type)

        if not data.name:
            data.name = self.parser.extract_name_from_url(url) or "Unknown Player"

        return data

    def scrape_from_file(self, file_path: str) -> ProspectData:
        """Scrape prospect data from a local text file."""
        print(f"Reading from file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            text_content = f.read()

        print("Parsing prospect data...")
        return self.parser.parse(text_content)

    def generate_document(self, data: ProspectData, output_path: str) -> None:
        """Generate a Word document from prospect data."""
        print(f"Creating document for: {data.name}")
        print(f"Filename: {output_path}")
        self.doc_generator.generate(data, output_path)

    def generate_output_path(self, data: ProspectData) -> str:
        """Generate default output path from prospect name."""
        safe_name = re.sub(r'[^\w\s-]', '', data.name).replace(' ', '_')
        return f"{safe_name}_Scouting_Report.docx"

    def scrape_and_generate(self, slug, output_directory, generate_inline):
        data = self.scrape_from_url(url=slug)

        if generate_inline:
            file_name = self.generate_output_path(data=data)
            file_path = Path(output_directory, file_name)
            self.generate_document(data=data, output_path=str(file_path))

    def print_summary(self, data: ProspectData) -> None:
        """Print summary of extracted data."""
        print("\nExtracted data summary:")
        print(f"  Name: {data.name}")
        print(f"  Position: {data.position}")
        print(f"  School: {data.school}")
        print(f"  Rating: {data.overall_rating}/100")
        print(f"  Draft Projection: {data.draft_projection}")
        print(f"  Strengths: {len(data.strengths)} items")
        print(f"  Weaknesses: {len(data.weaknesses)} items")
        print(f"  Image: {'Yes' if data.image_data else 'No'}")


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
                if "target closed" in error_msg or "browser has been closed" in error_msg:
                    print(f"Browser/target closed during navigation (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    raise  # Let caller handle browser relaunch
                raise

    def extract_prospect_hrefs(self, page):
        print(f"Extracting prospect hrefs for {page.url}")
        rows = page.locator('#positionRankTable tbody tr')
        data_hrefs = rows.evaluate_all("rows => rows.map(row => row.getAttribute('data-href'))")
        return data_hrefs

    def extract_prospect_urls_for_position(self, pos: str) -> List[str]:
        all_profiles = []

        path = f"/positions/{pos}/1/2026"
        full_url = f"{self.base_url}{path}"

        page = self._create_page_with_retry(full_url)
        all_profiles.extend(self.extract_prospect_hrefs(page=page))
        links = page.locator('ul.pagination li.page-item a.page-link[href]')
        position_page_hrefs = links.evaluate_all("anchors => anchors.map(a => a.getAttribute('href'))")

        for path in position_page_hrefs:
            page.close()
            full_url = f"{self.base_url}{path}"
            page = self._create_page_with_retry(full_url)
            time.sleep(uniform(4.5, 5.5))

            prospect_hrefs = self.extract_prospect_hrefs(page)
            all_profiles.extend(prospect_hrefs)

        return all_profiles

    def _create_page_with_retry(self, url: str):
        """Create a new page and navigate to URL with retry on browser crash."""
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                self._ensure_browser_connected()
                page = self.browser.new_page()
                page.goto(url)
                return page
            except PlaywrightError as e:
                last_error = e
                error_msg = str(e).lower()
                if "target closed" in error_msg or "browser has been closed" in error_msg:
                    print(f"Browser/target closed (attempt {attempt + 1}/{self.MAX_RETRIES}), relaunching...")
                    try:
                        self.browser.close()
                    except Exception:
                        pass
                    self.browser = self._launch_browser()
                    time.sleep(1)
                else:
                    raise
        raise last_error
