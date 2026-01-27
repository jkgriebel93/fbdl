import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Inches, Pt, RGBColor, Twips
from PIL import Image, ImageDraw, ImageFont

# ─── CONFIGURATION ───────────────────────────────────────────────────────────


# ─── SCHOOL COLORS ───────────────────────────────────────────────────────────


def load_school_colors(colors_file: str) -> Dict:
    """Load school colors from JSON file."""
    with open(colors_file, "r") as f:
        data = json.load(f)

    lookup = {}
    for division in ["FBS", "FCS"]:
        if division not in data:
            continue
        for conference, schools in data[division].items():
            for school, colors in schools.items():
                lookup[school.lower()] = colors

    return lookup


def get_school_colors(school: str, colors_db: Dict) -> Dict:
    """Get colors for a school, with fallback."""
    default = {"primary": "333333", "secondary": "666666", "light": "E8E8E8"}

    if not school:
        return default

    normalized = school.lower().strip()

    # Direct lookup
    if normalized in colors_db:
        return colors_db[normalized]

    # Partial match
    for key, colors in colors_db.items():
        if key in normalized or normalized in key:
            return colors

    return default


def blend_colors(color1: str, color2: str, ratio: float = 0.5) -> str:
    """Blend two hex colors."""
    c1 = color1.lstrip("#")
    c2 = color2.lstrip("#")
    r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
    r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
    r = int(r1 + (r2 - r1) * ratio)
    g = int(g1 + (g2 - g1) * ratio)
    b = int(b1 + (b2 - b1) * ratio)
    return f"{r:02x}{g:02x}{b:02x}"


def darken_color(hex_color: str, factor: float = 0.3) -> str:
    """Darken a hex color."""
    c = hex_color.lstrip("#")
    r = int(int(c[0:2], 16) * (1 - factor))
    g = int(int(c[2:4], 16) * (1 - factor))
    b = int(int(c[4:6], 16) * (1 - factor))
    return f"{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_color: str) -> RGBColor:
    """Convert hex to RGBColor."""
    c = hex_color.lstrip("#")
    return RGBColor(int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


# ─── RATING RING GENERATOR ───────────────────────────────────────────────────


def create_rating_ring(
    rating: float,
    primary_color: str,
    light_color: str,
    size: int = 120,
    output_path: str = None,
) -> str:
    """Create a circular progress ring image."""
    ring_width = 12
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    pc = primary_color.lstrip("#")
    lc = light_color.lstrip("#")
    primary_rgb = tuple(int(pc[i : i + 2], 16) for i in (0, 2, 4))
    light_rgb = tuple(int(lc[i : i + 2], 16) for i in (0, 2, 4))

    padding = 4
    center = size // 2
    outer_radius = size // 2 - padding
    inner_radius = outer_radius - ring_width
    bbox = [padding, padding, size - padding, size - padding]

    draw.arc(bbox, 0, 360, fill=light_rgb, width=ring_width)

    if rating > 0:
        start_angle = -90
        sweep_angle = (rating / 100) * 360
        end_angle = start_angle + sweep_angle
        draw.arc(bbox, start_angle, end_angle, fill=primary_rgb, width=ring_width)

        cap_radius = ring_width // 2
        start_x, start_y = center, padding + ring_width // 2
        draw.ellipse(
            [
                start_x - cap_radius,
                start_y - cap_radius,
                start_x + cap_radius,
                start_y + cap_radius,
            ],
            fill=primary_rgb,
        )

        if rating < 100:
            end_angle_rad = math.radians(end_angle)
            arc_center_radius = outer_radius - ring_width // 2
            end_x = center + arc_center_radius * math.cos(end_angle_rad)
            end_y = center + arc_center_radius * math.sin(end_angle_rad)
            draw.ellipse(
                [
                    end_x - cap_radius,
                    end_y - cap_radius,
                    end_x + cap_radius,
                    end_y + cap_radius,
                ],
                fill=primary_rgb,
            )

    center_radius = inner_radius - 4
    draw.ellipse(
        [
            center - center_radius,
            center - center_radius,
            center + center_radius,
            center + center_radius,
        ],
        fill=primary_rgb,
    )

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size // 4
        )
    except:
        font = ImageFont.load_default()

    text = str(int(rating)) if rating == int(rating) else f"{rating:.1f}"
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    draw.text(
        (center - text_width // 2, center - text_height // 2 - 2),
        text,
        fill=(255, 255, 255),
        font=font,
    )

    if output_path:
        img.save(output_path, "PNG")

    return output_path


# ─── DOCX HELPERS ────────────────────────────────────────────────────────────


def set_cell_shading(cell, hex_color: str):
    """Set cell background color."""
    hex_color = hex_color.lstrip("#").upper()
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    # Remove existing shading
    for shd in tcPr.findall(qn("w:shd")):
        tcPr.remove(shd)
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), hex_color)
    tcPr.append(shading)


def set_cell_margins(cell, top=0, bottom=0, left=0, right=0):
    """Set cell margins in twips (1/20 of a point, 1440 twips = 1 inch)."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    # Remove existing margins
    for tcMar in tcPr.findall(qn("w:tcMar")):
        tcPr.remove(tcMar)

    tcMar = OxmlElement("w:tcMar")
    for margin_name, margin_value in [
        ("top", top),
        ("bottom", bottom),
        ("left", left),
        ("right", right),
    ]:
        margin = OxmlElement(f"w:{margin_name}")
        margin.set(qn("w:w"), str(margin_value))
        margin.set(qn("w:type"), "dxa")
        tcMar.append(margin)
    tcPr.append(tcMar)


def remove_cell_borders(cell):
    """Remove all borders from a cell."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for tcBorders in tcPr.findall(qn("w:tcBorders")):
        tcPr.remove(tcBorders)

    tcBorders = OxmlElement("w:tcBorders")
    for border_name in ["top", "left", "bottom", "right"]:
        border = OxmlElement(f"w:{border_name}")
        border.set(qn("w:val"), "nil")
        tcBorders.append(border)
    tcPr.append(tcBorders)


def add_left_border(cell, hex_color: str, size: int = 24):
    """Add left border to cell."""
    hex_color = hex_color.lstrip("#").upper()
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for tcBorders in tcPr.findall(qn("w:tcBorders")):
        tcPr.remove(tcBorders)

    tcBorders = OxmlElement("w:tcBorders")
    for border_name in ["top", "bottom", "right"]:
        border = OxmlElement(f"w:{border_name}")
        border.set(qn("w:val"), "nil")
        tcBorders.append(border)

    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), str(size))
    left.set(qn("w:color"), hex_color)
    tcBorders.append(left)
    tcPr.append(tcBorders)


def skill_bar(pct: int) -> str:
    """Generate ASCII skill bar."""
    filled = round(pct / 10)
    return "█" * filled + "░" * (10 - filled)


# ─── DATA EXTRACTION ─────────────────────────────────────────────────────────


@dataclass
class ProspectData:
    name: str
    position: str
    school: str
    play_style: str
    height: str
    weight: str
    forty: str
    hometown: str
    class_year: str
    overall_rating: float
    draft_buzz_overall: str
    draft_buzz_position: str
    draft_projection: str
    consensus_overall: str
    consensus_position: str
    stats: Dict[str, Dict[str, Any]]
    skills: Dict[str, int]
    comparisons: List[Dict]
    recruiting: Dict[str, str]
    bio: str
    strengths: List[str]
    weaknesses: List[str]
    summary: Optional[str]
    photo_path: Optional[str]
    colors: Dict[str, str]


def extract_prospect_data(
    name: str, data: Dict, position: str, colors_db: Dict, photos_dir: str
) -> ProspectData:
    """Extract and normalize prospect data from JSON."""
    basic = data.get("basic_info", {})
    ratings = data.get("ratings", {})
    raw_stats = data.get("stats", {})
    skills_raw = data.get("skills", {})
    comparisons = data.get("comparisons", [])
    report = data.get("scouting_report", {})

    # Get school
    school_display = basic.get("college", "").title()
    school_lookup = basic.get("college", "").lower().strip()
    colors = get_school_colors(school_lookup, colors_db)

    # Photo path
    photo_filename = f"{basic.get('first_name', '')} {basic.get('last_name', '')}.png"
    photo_path = os.path.join(photos_dir, photo_filename)
    if not os.path.exists(photo_path):
        photo_path = None

    # Extract stats
    stats = {}
    pos_upper = position.upper()

    if raw_stats and pos_upper in POSITION_STATS:
        pos_config = POSITION_STATS[pos_upper]

        if pos_upper == "QB":
            category = "Passing"
            stats[category] = {}
            for label in pos_config.get(category, []):
                key = label.lower().replace("%", "_pct")
                if key == "int":
                    key = "ints"
                if key == "rtg":
                    key = "qb_rtg"
                value = raw_stats.get(key, "—")
                if isinstance(value, float):
                    if key == "cmp_pct":
                        value = f"{value:.1f}%"
                    elif key == "qb_rtg":
                        value = f"{value:.1f}"
                    else:
                        value = str(int(value)) if value == int(value) else str(value)
                elif isinstance(value, int):
                    value = f"{value:,}" if value >= 1000 else str(value)
                stats[category][label] = value if value else "—"

        elif pos_upper in ["RB", "WR", "TE"]:
            for category, stat_labels in pos_config.items():
                cat_key = category.lower()
                cat_data = raw_stats.get(cat_key, {})
                stats[category] = {}
                for label in stat_labels:
                    key = label.lower()
                    value = cat_data.get(key, "—")
                    if isinstance(value, float):
                        value = (
                            f"{value:.1f}" if value != int(value) else str(int(value))
                        )
                    elif isinstance(value, int):
                        value = f"{value:,}" if value >= 1000 else str(value)
                    stats[category][label] = value if value else "—"

        elif pos_upper in ["DL", "EDGE", "LB", "DB"]:
            category_map = {"Tackles": "tackle", "Interceptions": "interception"}
            for category, stat_labels in pos_config.items():
                cat_key = category_map.get(category, category.lower())
                cat_data = raw_stats.get(cat_key, {})
                stats[category] = {}
                for label in stat_labels:
                    key = label.lower()
                    value = cat_data.get(key, "—")
                    if isinstance(value, float):
                        value = (
                            f"{value:.1f}" if value != int(value) else str(int(value))
                        )
                    elif isinstance(value, int):
                        value = str(value)
                    stats[category][label] = value if value else "—"

    def format_rank(val):
        if val is None:
            return "—"
        if isinstance(val, float):
            return f"#{val:.1f}" if val != int(val) else f"#{int(val)}"
        return str(val) if str(val).startswith("#") else f"#{val}"

    recruiting = {}
    if ratings.get("rtg_247"):
        recruiting["247"] = (
            f"{ratings['rtg_247']}/100"
            if isinstance(ratings["rtg_247"], (int, float))
            else str(ratings["rtg_247"])
        )
    if ratings.get("rivals"):
        recruiting["Rivals"] = str(ratings["rivals"])

    return ProspectData(
        name=basic.get("full_name", name).upper(),
        position=position.upper(),
        school=school_display,
        play_style=basic.get("play_style", "").upper(),
        height=basic.get("height", ""),
        weight=basic.get("weight", ""),
        forty=basic.get("forty", ""),
        hometown=basic.get("hometown", "").title(),
        class_year=basic.get("class_", "").title(),
        overall_rating=ratings.get("overall_rating", 0) or 0,
        draft_buzz_overall=format_rank(ratings.get("overall_rank", "")),
        draft_buzz_position=format_rank(ratings.get("position_rank", "")).split()[0],
        draft_projection=(
            ratings.get("draft_projection", "—").upper()
            if ratings.get("draft_projection")
            else "—"
        ),
        consensus_overall=format_rank(ratings.get("avg_overall_rank")),
        consensus_position=format_rank(ratings.get("avg_position_rank")),
        stats=stats,
        skills=skills_raw,
        comparisons=comparisons or [],
        recruiting=recruiting,
        bio=report.get("bio", ""),
        strengths=report.get("strengths", []),
        weaknesses=report.get("weaknesses", []),
        summary=report.get("summary"),
        photo_path=photo_path,
        colors=colors,
    )


# ─── DOCUMENT GENERATION ─────────────────────────────────────────────────────


def generate_prospect_document(
    prospect: ProspectData, output_path: str, temp_dir: str, default_photo: str = None
):
    """Generate a complete prospect profile document."""
    doc = Document()

    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.5)
    section.bottom_margin = Inches(0.5)
    section.left_margin = Inches(1)
    section.right_margin = Inches(0.75)

    # School colors - strip any # prefix
    primary = prospect.colors["primary"].lstrip("#")
    light = prospect.colors["light"].lstrip("#")
    dark = darken_color(primary, 0.3)
    medium = blend_colors(light, primary, 0.20)

    primary_rgb = hex_to_rgb(primary)
    light_rgb = hex_to_rgb(light)

    # Generate rating ring
    ring_path = os.path.join(temp_dir, f"{prospect.name.replace(' ', '_')}_ring.png")
    create_rating_ring(prospect.overall_rating, primary, light, output_path=ring_path)

    # ─── HEADER TABLE ────────────────────────────────────────────────────────
    header_table = doc.add_table(rows=1, cols=3)
    header_table.autofit = False

    photo_cell = header_table.cell(0, 0)
    photo_cell.width = Inches(1.5)
    remove_cell_borders(photo_cell)
    photo_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    photo_para = photo_cell.paragraphs[0]
    photo_to_use = (
        prospect.photo_path
        if prospect.photo_path and os.path.exists(prospect.photo_path)
        else default_photo
    )
    if photo_to_use and os.path.exists(photo_to_use):
        photo_para.add_run().add_picture(photo_to_use, width=Inches(1.3))

    name_cell = header_table.cell(0, 1)
    name_cell.width = Inches(4.0)
    remove_cell_borders(name_cell)
    name_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    name_para = name_cell.paragraphs[0]
    name_para.paragraph_format.space_after = Pt(0)
    run = name_para.add_run(prospect.name)
    run.font.size = Pt(28)
    run.font.bold = True
    run.font.color.rgb = primary_rgb

    info_para = name_cell.add_paragraph()
    info_para.paragraph_format.space_before = Pt(2)
    info_para.paragraph_format.space_after = Pt(4)
    run = info_para.add_run(
        f"{prospect.position}  •  {prospect.school}  •  {prospect.play_style}"
    )
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    measurables_para = name_cell.add_paragraph()
    run = measurables_para.add_run(
        f"{prospect.height}  •  {prospect.weight} lbs  •  {prospect.forty}s  •  {prospect.hometown}  •  {prospect.class_year}"
    )
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x77, 0x77, 0x77)

    ring_cell = header_table.cell(0, 2)
    ring_cell.width = Inches(1.25)
    remove_cell_borders(ring_cell)
    ring_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    ring_para = ring_cell.paragraphs[0]
    ring_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if os.path.exists(ring_path):
        ring_para.add_run().add_picture(ring_path, width=Inches(0.95))

    label_para = ring_cell.add_paragraph()
    label_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    label_para.paragraph_format.space_before = Pt(2)
    run = label_para.add_run("PROSPECT RATING")
    run.font.size = Pt(6.5)
    run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    # Spacer
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(8)

    # ─── RANKINGS BAR ────────────────────────────────────────────────────────
    rankings_table = doc.add_table(rows=1, cols=5)
    rankings_table.autofit = False

    rankings_data = [
        ("DRAFT BUZZ", prospect.draft_buzz_overall, "OVERALL", primary),
        ("DRAFT BUZZ", prospect.draft_buzz_position, "POSITION", dark),
        ("DRAFT", prospect.draft_projection, "PROJECTION", primary),
        ("CONSENSUS", prospect.consensus_overall, "OVERALL", dark),
        ("CONSENSUS", prospect.consensus_position, "POSITION", primary),
    ]

    for i, (source, value, label, bg_color) in enumerate(rankings_data):
        cell = rankings_table.cell(0, i)
        cell.width = Inches(1.35)
        remove_cell_borders(cell)
        set_cell_shading(cell, bg_color)
        set_cell_margins(cell, top=140, bottom=100, left=80, right=80)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

        # Source label
        p1 = cell.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p1.paragraph_format.space_after = Pt(1)
        run = p1.add_run(source)
        run.font.size = Pt(6)
        run.font.color.rgb = light_rgb

        # Value
        p2 = cell.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p2.paragraph_format.space_before = Pt(0)
        p2.paragraph_format.space_after = Pt(1)
        font_size = Pt(11) if label == "PROJECTION" else Pt(18)
        run = p2.add_run(value)
        run.font.size = font_size
        run.font.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)

        # Category label
        p3 = cell.add_paragraph()
        p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p3.paragraph_format.space_before = Pt(0)
        run = p3.add_run(label)
        run.font.size = Pt(6.5)
        run.font.color.rgb = light_rgb

    # ─── STATS BAR ───────────────────────────────────────────────────────────
    pos_config = POSITION_STATS.get(prospect.position, {})
    categories = list(pos_config.keys())

    if categories:
        is_multiple = len(categories) > 1

        if is_multiple:
            total_stats = sum(len(pos_config[cat]) for cat in categories)
            stats_table = doc.add_table(rows=2, cols=total_stats)
            stats_table.autofit = False

            col_idx = 0
            for cat_idx, category in enumerate(categories):
                stat_labels = pos_config[category]
                num_stats = len(stat_labels)
                bg_color = light if cat_idx == 0 else medium
                label_color = "666666" if cat_idx == 0 else primary
                label_rgb = hex_to_rgb(label_color)

                # Merge header cells
                if num_stats > 1:
                    start_cell = stats_table.cell(0, col_idx)
                    end_cell = stats_table.cell(0, col_idx + num_stats - 1)
                    start_cell.merge(end_cell)

                header_cell = stats_table.cell(0, col_idx)
                remove_cell_borders(header_cell)
                set_cell_shading(header_cell, bg_color)
                set_cell_margins(header_cell, top=80, bottom=40, left=40, right=40)
                header_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

                p = header_cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_after = Pt(0)
                run = p.add_run(category.upper())
                run.font.size = Pt(9)
                run.font.bold = True
                run.font.color.rgb = label_rgb

                cat_stats = prospect.stats.get(category, {})
                for j, stat_label in enumerate(stat_labels):
                    stat_cell = stats_table.cell(1, col_idx + j)
                    stat_cell.width = Inches(6.75 / total_stats)
                    remove_cell_borders(stat_cell)
                    set_cell_shading(stat_cell, bg_color)
                    set_cell_margins(stat_cell, top=80, bottom=60, left=40, right=40)
                    stat_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

                    p1 = stat_cell.paragraphs[0]
                    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p1.paragraph_format.space_after = Pt(2)
                    run = p1.add_run(str(cat_stats.get(stat_label, "—")))
                    run.font.size = Pt(14)
                    run.font.bold = True
                    run.font.color.rgb = primary_rgb

                    p2 = stat_cell.add_paragraph()
                    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p2.paragraph_format.space_before = Pt(0)
                    run = p2.add_run(stat_label)
                    run.font.size = Pt(7)
                    run.font.color.rgb = label_rgb

                col_idx += num_stats

        else:
            # Single category
            category = categories[0]
            stat_labels = pos_config[category]
            cat_stats = prospect.stats.get(category, {})

            stats_table = doc.add_table(rows=1, cols=len(stat_labels))
            stats_table.autofit = False

            for i, stat_label in enumerate(stat_labels):
                cell = stats_table.cell(0, i)
                cell.width = Inches(6.75 / len(stat_labels))
                remove_cell_borders(cell)
                set_cell_shading(cell, light)
                set_cell_margins(cell, top=100, bottom=70, left=40, right=40)
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

                p1 = cell.paragraphs[0]
                p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p1.paragraph_format.space_after = Pt(3)
                run = p1.add_run(str(cat_stats.get(stat_label, "—")))
                run.font.size = Pt(14)
                run.font.bold = True
                run.font.color.rgb = primary_rgb

                p2 = cell.add_paragraph()
                p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p2.paragraph_format.space_before = Pt(0)
                run = p2.add_run(stat_label)
                run.font.size = Pt(7)
                run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    else:
        # OL - no stats
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(8)
        run = p.add_run("(Statistics not tracked for Offensive Linemen)")
        run.font.size = Pt(9)
        run.font.italic = True
        run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    # Spacer
    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # ─── SKILLS + COMPARISONS ────────────────────────────────────────────────
    skills_table = doc.add_table(rows=1, cols=2)
    skills_table.autofit = False

    skills_cell = skills_table.cell(0, 0)
    skills_cell.width = Inches(3.8)
    remove_cell_borders(skills_cell)

    skills_header = skills_cell.paragraphs[0]
    skills_header.paragraph_format.space_after = Pt(4)
    run = skills_header.add_run("SKILL RATINGS")
    run.font.size = Pt(9)
    run.font.bold = True
    run.font.color.rgb = primary_rgb

    for skill_name, skill_pct in prospect.skills.items():
        if skill_pct is None:
            continue
        p = skills_cell.add_paragraph()
        p.paragraph_format.space_after = Pt(2)

        display_name = skill_name.replace("_", " ").title()
        run = p.add_run(f"{display_name:<20} ")
        run.font.name = "Consolas"
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

        run = p.add_run(skill_bar(skill_pct))
        run.font.name = "Consolas"
        run.font.size = Pt(8)
        run.font.color.rgb = primary_rgb

        run = p.add_run(f" {skill_pct}%")
        run.font.name = "Consolas"
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    comp_cell = skills_table.cell(0, 1)
    comp_cell.width = Inches(3.0)
    remove_cell_borders(comp_cell)

    comp_header = comp_cell.paragraphs[0]
    comp_header.paragraph_format.space_after = Pt(4)
    run = comp_header.add_run("PLAYER COMPARISONS")
    run.font.size = Pt(9)
    run.font.bold = True
    run.font.color.rgb = primary_rgb

    for comp in prospect.comparisons[:3]:
        p = comp_cell.add_paragraph()
        p.paragraph_format.space_after = Pt(2)

        run = p.add_run(f"{comp.get('name', '')} ")
        run.font.size = Pt(9)
        run.font.bold = True

        run = p.add_run(f"({comp.get('school', '')}) ")
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

        run = p.add_run(f"{comp.get('similarity', '')}%")
        run.font.size = Pt(9)
        run.font.bold = True
        run.font.color.rgb = primary_rgb

    if prospect.recruiting:
        p = comp_cell.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run("RECRUITING")
        run.font.size = Pt(9)
        run.font.bold = True
        run.font.color.rgb = primary_rgb

        p = comp_cell.add_paragraph()
        recruiting_text = "  •  ".join(
            [f"{k}: {v}" for k, v in prospect.recruiting.items()]
        )
        run = p.add_run(recruiting_text)
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ─── BACKGROUND ──────────────────────────────────────────────────────────
    if prospect.bio:
        header = doc.add_paragraph()
        header.paragraph_format.space_after = Pt(4)
        run = header.add_run("BACKGROUND")
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = primary_rgb

        bio_text = prospect.bio.replace("Draft Profile: Bio", "").strip()
        if len(bio_text) > 1500:
            bio_text = bio_text[:1500] + "..."

        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(bio_text)
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # ─── STRENGTHS & WEAKNESSES ──────────────────────────────────────────────
    sw_table = doc.add_table(rows=1, cols=2)
    sw_table.autofit = False

    str_cell = sw_table.cell(0, 0)
    str_cell.width = Inches(3.375)
    remove_cell_borders(str_cell)

    str_header = str_cell.paragraphs[0]
    str_header.paragraph_format.space_after = Pt(4)
    run = str_header.add_run("STRENGTHS")
    run.font.size = Pt(11)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x1D, 0x6A, 0x4D)

    for strength in prospect.strengths[:6]:
        p = str_cell.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.left_indent = Inches(0.15)

        run = p.add_run("+ ")
        run.font.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x1D, 0x6A, 0x4D)

        run = p.add_run(strength[:200] if len(strength) > 200 else strength)
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    weak_cell = sw_table.cell(0, 1)
    weak_cell.width = Inches(3.375)
    remove_cell_borders(weak_cell)

    weak_header = weak_cell.paragraphs[0]
    weak_header.paragraph_format.space_after = Pt(4)
    run = weak_header.add_run("WEAKNESSES")
    run.font.size = Pt(11)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0xA6, 0x5D, 0x21)

    for weakness in prospect.weaknesses[:5]:
        p = weak_cell.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.left_indent = Inches(0.15)

        run = p.add_run("– ")
        run.font.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0xA6, 0x5D, 0x21)

        run = p.add_run(weakness[:200] if len(weakness) > 200 else weakness)
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    # ─── SCOUTING SUMMARY ────────────────────────────────────────────────────
    if prospect.summary:
        doc.add_paragraph().paragraph_format.space_after = Pt(4)

        summary_table = doc.add_table(rows=1, cols=1)
        summary_table.autofit = False

        cell = summary_table.cell(0, 0)
        cell.width = Inches(6.75)
        set_cell_shading(cell, light)
        set_cell_margins(cell, top=100, bottom=70, left=160, right=120)
        add_left_border(cell, primary, 24)

        header = cell.paragraphs[0]
        header.paragraph_format.space_after = Pt(4)
        run = header.add_run("SCOUTING SUMMARY")
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = primary_rgb

        p = cell.add_paragraph()
        run = p.add_run(prospect.summary)
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    doc.save(output_path)

    if os.path.exists(ring_path):
        os.remove(ring_path)


# ─── MAIN BATCH PROCESSOR ────────────────────────────────────────────────────


def batch_generate_profiles(
    json_dir: str,
    photos_dir: str,
    output_dir: str,
    colors_file: str,
    positions: List[str] = None,
    default_photo: str = None,
):
    """Generate prospect profiles for all positions."""
    print("Loading school colors...")
    colors_db = load_school_colors(colors_file)
    print(f"  Loaded {len(colors_db)} schools")

    os.makedirs(output_dir, exist_ok=True)
    temp_dir = os.path.join(output_dir, ".temp")
    os.makedirs(temp_dir, exist_ok=True)

    all_positions = ["QB", "RB", "WR", "TE", "OL", "DL", "EDGE", "LB", "DB"]
    if positions:
        all_positions = [p.upper() for p in positions]

    total_generated = 0

    for position in all_positions:
        json_file = os.path.join(json_dir, f"{position}.json")

        if not os.path.exists(json_file):
            print(f"Skipping {position}: No JSON file found")
            continue

        print(f"\nProcessing {position}...")

        with open(json_file, "r") as f:
            players_data = json.load(f)

        pos_output_dir = os.path.join(output_dir, position)
        os.makedirs(pos_output_dir, exist_ok=True)

        for rank, (player_name, player_data) in enumerate(players_data.items(), 1):
            try:
                prospect = extract_prospect_data(
                    player_name, player_data, position, colors_db, photos_dir
                )

                safe_name = (
                    player_name.replace(" ", "_").replace(".", "").replace("'", "")
                )
                output_file = os.path.join(
                    pos_output_dir, f"{rank:02d}_{safe_name}.docx"
                )

                generate_prospect_document(
                    prospect, output_file, temp_dir, default_photo
                )

                print(
                    f"  [{rank:3d}] {player_name} ({prospect.school}) - #{prospect.colors['primary']}"
                )
                total_generated += 1

            except Exception as e:
                print(f"  ERROR: {player_name} - {str(e)}")
                import traceback

                traceback.print_exc()

    import shutil

    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    print(f"\n{'=' * 50}")
    print(f"COMPLETE: Generated {total_generated} prospect profiles")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate NFL Draft Prospect Profiles")
    parser.add_argument("--json-dir", required=True)
    parser.add_argument("--photos-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--colors-file", required=True)
    parser.add_argument("--positions", nargs="+")
    parser.add_argument("--default-photo")

    args = parser.parse_args()

    batch_generate_profiles(
        json_dir=args.json_dir,
        photos_dir=args.photos_dir,
        output_dir=args.output_dir,
        colors_file=args.colors_file,
        positions=args.positions,
        default_photo=args.default_photo,
    )
