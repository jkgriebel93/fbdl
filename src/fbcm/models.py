from dataclasses import dataclass, field


@dataclass
class PassingStats:
    year: int | None = None
    cmp: int | None = None
    att: int | None = None
    cmp_pct: float | None = None
    yds: int | None = None
    td: int | None = None
    ints: int | None = None
    sack: int | None = None
    qb_rtg: float | None = None


@dataclass
class RushingStats:
    att: int | None = None
    yds: int | None = None
    avg: float | None = None
    td: int | None = None


@dataclass
class ReceivingStats:
    rec: int | None = None
    yds: int | None = None
    avg: float | None = None
    td: int | None = None


@dataclass
class OffenseSkillPlayerStats:
    rushing: RushingStats | None = None
    receiving: ReceivingStats | None = None


@dataclass
class DefenseStats:
    total: int | None = None
    solo: int | None = None
    ff: int | None = None
    sacks: float | None = None
    ints: int | None = None
    yds: int | None = None
    pds: int | None = None
