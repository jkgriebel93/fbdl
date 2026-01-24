from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, TypeAlias

@dataclass
class BaseModel:
    exclude_fields = []

    def to_dict(self) -> Dict[str, Any]:
        return {key: value for key, value in asdict(self).items()
                if key not in self.exclude_fields}


@dataclass
class BaseStats(BaseModel):
    year: int | None = None


@dataclass
class PassingStats(BaseStats):
    cmp: int | None = None
    att: int | None = None
    cmp_pct: float | None = None
    yds: int | None = None
    td: int | None = None
    ints: int | None = None
    sack: int | None = None
    qb_rtg: float | None = None


@dataclass
class RushingStats(BaseStats):
    att: int | None = None
    yds: int | None = None
    avg: float | None = None
    td: int | None = None


@dataclass
class ReceivingStats(BaseStats):
    rec: int | None = None
    yds: int | None = None
    avg: float | None = None
    td: int | None = None


@dataclass
class OffenseSkillPlayerStats(BaseStats):
    rushing: RushingStats | None = None
    receiving: ReceivingStats | None = None


@dataclass
class TackleStats(BaseStats):
    total: int | None = None
    solo: int | None = None
    ff: int | None = None
    sacks: float | None = None


@dataclass
class InterceptionStats(BaseStats):
    ints: int | None = None
    yds: int | None = None
    td: int | None = None
    pds: int | None = None


@dataclass
class DefenseStats(BaseStats):
    tackle: TackleStats | None = None
    interception: InterceptionStats | None = None


Stats: TypeAlias = PassingStats | RushingStats | ReceivingStats | OffenseSkillPlayerStats | DefenseStats


@dataclass
class PassRushRatings(BaseModel):
    tackling: int | None = None
    pass_rush: int | None = None
    run_defense: int | None = None

SkillRatings: TypeAlias = PassRushRatings


@dataclass
class RatingsAndRankings(BaseModel):
    overall_rating: float | None = None
    opposition_rating: int | None = None
    skill_ratings: SkillRatings | None = None
    espn_rating: int | None = None
    rating_247: int | None = None
    rivals_rating: float | None = None

    draft_projection: str | None = None
    overall_rank: int | None = None
    position_rank: str | None = None

    avg_overall_rank: float | None = None
    avg_position_rank: float | None = None

    comparisons: List[tuple] = field(default_factory=list)


@dataclass
class BasicInfo(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
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


@dataclass
class ScoutingReport(BaseModel):
    bio: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class ProspectDataSoup(BaseModel):
    basic_info: BasicInfo | None = None
    ratings: RatingsAndRankings | None = None
    stats: Stats | None = None
    scouting_report: ScoutingReport | None = None

@dataclass
class ProspectData(BaseModel):
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
    stats: Stats | None = None
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
    image_data: Optional[bytes] = field(default=None, metadata={"exclude_from_asdict": True}, repr=False)
    image_type: str = "jpeg"

    exclude_fields = ["image_data"]