from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeAlias, get_args, get_origin, Union
from docx.shared import RGBColor

from .constants import PHOTO_BASE_DIR

@dataclass
class BaseModel:
    exclude_fields = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            key: value
            for key, value in asdict(self).items()
            if key not in self.exclude_fields
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseModel":
        """Create an instance from a dictionary, handling nested dataclasses."""
        if data is None:
            return None

        field_info = {f.name: f.type for f in fields(cls)}
        kwargs = {}

        for key, value in data.items():
            if key not in field_info:
                continue

            if value is None:
                kwargs[key] = None
                continue

            field_type = field_info[key]
            kwargs[key] = cls._convert_value(value, field_type)

        return cls(**kwargs)

    @classmethod
    def _convert_value(cls, value: Any, field_type: Any) -> Any:
        """Convert a value to the appropriate type, handling unions and nested types."""
        origin = get_origin(field_type)

        # Handle Union types (e.g., SomeType | None)
        if origin is Union:
            args = get_args(field_type)
            # Find the non-None type in the union
            for arg in args:
                if arg is type(None):
                    continue
                return cls._convert_value(value, arg)

        # Handle List types
        if origin is list:
            item_type = get_args(field_type)[0]
            return [cls._convert_value(item, item_type) for item in value]

        # Handle nested dataclasses that have from_dict
        if isinstance(value, dict) and hasattr(field_type, "from_dict"):
            return field_type.from_dict(value)

        return value


@dataclass
class ColorScheme(BaseModel):
    primary: str
    secondary: str
    light: str

    dark : str | None = None
    medium: str | None = None
    primary_rgb: RGBColor | None = None
    light_rgb: RGBColor | None = None


@dataclass
class BaseStats(BaseModel):
    year: int | None = None
    games_played: int | None = None
    snap_count: int | None = None


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


Stats: TypeAlias = (
    PassingStats
    | RushingStats
    | ReceivingStats
    | OffenseSkillPlayerStats
    | DefenseStats
)


@dataclass
class PassingSkills(BaseModel):
    release_speed: int | None = None
    short_passing: int | None = None
    medium_passing: int | None = None
    long_passing: int | None = None
    rush_scramble: int | None = None


@dataclass
class RunningBackSkills(BaseModel):
    rushing: int | None = None
    break_tackles: int | None = None
    receiving_hands: int | None = None
    pass_blocking: int | None = None
    run_blocking: int | None = None


@dataclass
class PassCatcherSkills(BaseModel):
    qb_rating_when_targeted: float | None = None
    hands: int | None = None
    short_receiving: int | None = None
    intermediate_routes: int | None = None
    deep_threat: int | None = None
    blocking: int | None = None


@dataclass
class OffensiveLinemanSkills(BaseModel):
    pass_blocking: int | None = None
    run_blocking: int | None = None


@dataclass
class DefensiveLinemanSkills(BaseModel):
    qb_rating_when_targeted: float | None = None
    tackling: int | None = None
    pass_rush: int | None = None
    run_defense: int | None = None
    coverage: int | None = None
    zone: int | None = None
    man_press: int | None = None


@dataclass
class LinebackerSkills(BaseModel):
    qb_rating_when_targeted: float | None = None
    tackling: int | None = None
    pass_rush: int | None = None
    run_defense: int | None = None
    coverage: int | None = None
    zone: int | None = None
    man_press: int | None = None


@dataclass
class DefensiveBackSkills(BaseModel):
    qb_rating_when_targeted: float | None = None
    tackling: int | None = None
    run_defense: int | None = None
    coverage: int | None = None
    zone: int | None = None
    man_press: int | None = None


SkillRatings: TypeAlias = (
    PassingSkills
    | RunningBackSkills
    | PassCatcherSkills
    | OffensiveLinemanSkills
    | DefensiveLinemanSkills
    | LinebackerSkills
    | DefensiveBackSkills
)


@dataclass
class RatingsAndRankings(BaseModel):
    overall_rating: float | None = None
    opposition_rating: int | None = None
    espn: int | None = None
    rtg_247: int | None = None
    rivals: float | None = None

    draft_projection: str | None = None
    overall_rank: int | None = None
    position_rank: str | None = None

    avg_overall_rank: float | None = None
    avg_position_rank: float | None = None

    def get_recruiting_str(self) -> str:
        outlet_rtgs = []
        if self.espn:
            outlet_rtgs.append(f"ESPN: {self.espn}")
        if self.rtg_247:
            outlet_rtgs.append(f"247: {self.rtg_247}")
        if self.rivals:
            outlet_rtgs.append(f"Rivals: {self.rivals}")

        return "  •  ".join(outlet_rtgs)


@dataclass
class Comparison(BaseModel):
    name: str | None = None
    school: str | None = None
    similarity: int | None = None


@dataclass
class BasicInfo(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    position: str = ""
    college: str = ""
    class_: str = ""
    jersey: str = ""
    play_style: str = ""
    draft_year: str = ""
    last_updated: str = ""

    # Basic info
    height: str = ""
    weight: str = ""
    forty: str = ""
    # TODO: Find a source for age and DOB, DraftBuzz doesn't
    # provide it, apparently
    age: str = ""
    dob: str = ""
    hometown: str = ""

    @property
    def photo_path(self):
        return Path(PHOTO_BASE_DIR, f"{self.full_name}.png")


@dataclass
class ScoutingReport(BaseModel):
    bio: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    summary: str | None = None


@dataclass
class ProspectDataSoup(BaseModel):
    basic_info: BasicInfo | None = None
    ratings: RatingsAndRankings | None = None
    skills: SkillRatings | None = None
    comparisons: List[Comparison] | None = None
    stats: Stats | None = None
    scouting_report: ScoutingReport | None = None
