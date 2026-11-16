from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional


@dataclass
class PropertyProject:
    project_id: str
    title: str
    city: str
    rera_number: str
    rera_handover_date: date
    has_force_majeure: bool
    circle_rate_sqft: float
    cc_received_date: Optional[date]


@dataclass
class TowerBlock:
    tower_id: str
    project_id: str
    tower_name: str
    total_floors: int
    wings: List[str]
    base_rate_sqft: float


@dataclass
class StageSchedule:
    stage_code: str
    seq_no: int
    clp_share_pct: float
    cert_scope: str


@dataclass
class FlatUnit:
    unit_id: str
    tower_id: str
    wing: str
    floor_no: int
    area_sqm: float
    area_sqft: float
    is_park_facing: bool
    is_corner: bool
    parking_count: int


@dataclass
class BuyerProfile:
    customer_id: str
    full_name: str
    gender: str
    female_primary_owner: bool
    pan_no: str
    phone: str
    city: str


@dataclass
class StageCertification:
    cert_id: str
    tower_id: str
    wing: str
    stage_code: str
    cert_date: date
    approved_by: str


@dataclass
class ReceiptEntry:
    payment_id: str
    booking_id: str
    paid_ts: datetime
    amount: int
    pay_mode: str
    utr_ref: str


@dataclass
class InvoiceItem:
    item_type: str
    stage_code: str
    amount: int
    is_taxable: bool


@dataclass
class BillingInvoice:
    demand_no: str
    booking_id: str
    issued_date: date
    due_date: date
    items: List[InvoiceItem]
    gst_pct: float
    gst_amount: int
    total_payable: int
    non_gst_total: int
    principal_settled: int = 0
    gst_settled: int = 0
    accrued_interest: int = 0
    interest_settled: int = 0
    interest_calc_upto: Optional[date] = None

    def __post_init__(self):
        if self.interest_calc_upto is None:
            self.interest_calc_upto = self.due_date

    @property
    def unpaid_principal(self) -> int:
        return max(0, self.non_gst_total - self.principal_settled)

    @property
    def unpaid_gst(self) -> int:
        return max(0, self.gst_amount - self.gst_settled)

    @property
    def pending_note_dues(self) -> int:
        return self.unpaid_principal + self.unpaid_gst


@dataclass
class AccountEvent:
    booking_id: str
    timestamp_str: str
    event_type: str
    ref_code: str
    debit_amt: int
    credit_amt: int
    int_part: int
    prin_part: int
    gst_part: int
    wallet_advance: int
    net_outstanding: int


@dataclass
class DutyAssessment:
    booking_id: str
    agreement_val: int
    circle_val: int
    assessed_base: int
    duty_pct: float
    stamp_duty_amt: int
    reg_fee_amt: int


@dataclass
class UnitBooking:
    booking_id: str
    unit_id: str
    customer_id: str
    booked_ts: datetime
    payment_plan: str
    planned_agreement_ts: Optional[datetime]
    price_excl_parking: int
    parking_total: int
    total_agreement_price: int
    discounted_base_price: int
    dpp_initial_95: int = 0
    signed_agreement_ts: Optional[datetime] = None
    booking_status: str = "BOOKED"
    excess_advance: int = 0
    invoices: List[BillingInvoice] = field(default_factory=list)
    events: List[AccountEvent] = field(default_factory=list)
    notice_issued_ts: Optional[datetime] = None
    notice_revoked: bool = False
    handover_offer_date: Optional[date] = None
    rera_compensation: int = 0
    cancelled_ts: Optional[datetime] = None
    forfeited_amt: int = 0
    refunded_gst: int = 0
    net_refund_due: int = 0
    cumulative_billed: int = 0
    cumulative_paid: int = 0
    cumulative_interest: int = 0
