from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


@dataclass
class MilestoneDef:
    code: str
    name: str
    clp_percent: float


DEFAULT_CLP_MILESTONES: List[MilestoneDef] = [
    MilestoneDef("BOOKING", "On Booking", 10.0),
    MilestoneDef("AGREEMENT", "On Agreement", 10.0),
    MilestoneDef("PLINTH", "On Plinth Completion", 10.0),
    MilestoneDef("SLAB1", "On 1st Slab", 8.0),
    MilestoneDef("SLAB2", "On 2nd Slab", 8.0),
    MilestoneDef("SLAB3", "On 3rd Slab", 8.0),
    MilestoneDef("SLAB4", "On 4th Slab", 8.0),
    MilestoneDef("SLAB5", "On 5th Slab", 8.0),
    MilestoneDef("BRICKWORK", "On Brickwork", 10.0),
    MilestoneDef("FINISHING", "On Finishing", 10.0),
    MilestoneDef("POSSESSION", "On Possession", 10.0),
]


@dataclass
class Project:
    project_id: str
    name: str
    rera_date: date
    cc_date: Optional[date]
    force_majeure: bool
    circle_rate: float
    milestones: List[MilestoneDef] = field(default_factory=lambda: list(DEFAULT_CLP_MILESTONES))
    towers: Dict[str, Dict[str, date]] = field(default_factory=dict)


@dataclass
class Unit:
    unit_id: str
    project_id: str
    tower_id: str
    floor: int
    carpet_sqft: float
    carpet_sqm: float
    base_rate: float
    park_facing: bool
    corner: bool
    parking_slots: int


@dataclass
class Customer:
    customer_id: str
    name: str
    is_female_first_owner: bool


@dataclass
class DemandNote:
    demand_id: str
    booking_id: str
    milestone_code: str
    demand_date: date
    due_date: date
    principal_amount: int
    gst_rate: float
    gst_amount: int
    interest_billed: int = 0
    principal_paid: int = 0
    gst_paid: int = 0
    interest_paid: int = 0
    last_interest_calc_date: Optional[date] = None
    unbilled_interest: int = 0

    def __post_init__(self):
        if self.last_interest_calc_date is None:
            self.last_interest_calc_date = self.due_date

    @property
    def principal_due(self) -> int:
        return max(0, self.principal_amount - self.principal_paid)

    @property
    def gst_due(self) -> int:
        return max(0, self.gst_amount - self.gst_paid)

    @property
    def total_billed(self) -> int:
        return self.principal_amount + self.gst_amount + self.interest_billed


@dataclass
class Payment:
    payment_id: str
    booking_id: str
    payment_date: date
    timestamp: str
    amount: int
    allocated_interest: int = 0
    allocated_principal: int = 0
    allocated_gst: int = 0
    unallocated_advance: int = 0


@dataclass
class LedgerEntry:
    entry_date: date
    ref_id: str
    particulars: str
    debit: int
    credit: int
    balance: int


@dataclass
class Booking:
    booking_id: str
    unit_id: str
    customer_id: str
    plan: str
    booking_date: date
    agreement_date: Optional[date]
    agreement_value_excl_parking: int
    parking_charge: int
    agreement_value_total: int
    discounted_excl_parking: int
    effective_total_value: int
    gst_rate: float
    stamp_duty: int
    registration_fee: int
    status: str = "ACTIVE"
    advance_balance: int = 0
    demands: List[DemandNote] = field(default_factory=list)
    payments: List[Payment] = field(default_factory=list)
    ledger: List[LedgerEntry] = field(default_factory=list)
    termination_notice_date: Optional[date] = None
    termination_withdrawn: bool = False
    possession_offer_date: Optional[date] = None
    delay_compensation: int = 0
    cancellation_date: Optional[date] = None
    forfeiture_amount: int = 0
    gst_refunded: int = 0
    refund_payable: int = 0
    refund_due_date: Optional[date] = None
