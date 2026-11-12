import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .calculations import (
    compute_rera_delay_comp,
    compute_stamp_and_reg,
    compute_unit_pricing,
    get_applicable_gst,
    nearest_rupee,
    year_quarter,
)
from .domain import (
    AccountEvent,
    BillingInvoice,
    BuyerProfile,
    DutyAssessment,
    FlatUnit,
    InvoiceItem,
    PropertyProject,
    ReceiptEntry,
    StageCertification,
    StageSchedule,
    TowerBlock,
    UnitBooking,
)


def to_date(text: str) -> date:
    return date.fromisoformat(text.strip())


def to_datetime(text: str) -> datetime:
    return datetime.fromisoformat(text.strip())


def to_bool(text: str) -> bool:
    return text.strip().lower() in ("true", "1", "yes")


class DeveloperAccountingEngine:
    def __init__(self):
        self.projects: Dict[str, PropertyProject] = {}
        self.towers: Dict[str, TowerBlock] = {}
        self.stage_map: Dict[str, StageSchedule] = {}
        self.ordered_stages: List[StageSchedule] = []
        self.units: Dict[str, FlatUnit] = {}
        self.buyers: Dict[str, BuyerProfile] = {}
        self.cert_catalog: Dict[str, StageCertification] = {}
        self.booking_rows: Dict[str, dict] = {}
        self.payment_catalog: Dict[str, ReceiptEntry] = {}

        # Runtime accounting state
        self.wing_approvals: Dict[Tuple[str, str], Dict[str, date]] = {}
        self.active_bookings: Dict[str, UnitBooking] = {}
        self.issued_invoices: List[BillingInvoice] = []
        self.duty_assessments: List[DutyAssessment] = []
        self._invoice_counter = 1
        self.audit_trail: List[str] = []

    def record_audit(self, note: str):
        self.audit_trail.append(note)

    # --- CSV Input Ingestion ---

    def load_csv_inputs(self, folder: str):
        root = Path(folder)

        with open(root / "projects.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                cc_dt = to_date(r["completion_certificate_date"]) if r["completion_certificate_date"].strip() else None
                proj = PropertyProject(
                    project_id=r["project_id"].strip(),
                    title=r["project_name"].strip(),
                    city=r["city"].strip(),
                    rera_number=r["rera_reg_no"].strip(),
                    rera_handover_date=to_date(r["rera_possession_date"]),
                    has_force_majeure=to_bool(r["force_majeure"]),
                    circle_rate_sqft=float(r["circle_rate_per_sqft"]),
                    cc_received_date=cc_dt,
                )
                self.projects[proj.project_id] = proj

        with open(root / "towers.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                twr = TowerBlock(
                    tower_id=r["tower_id"].strip(),
                    project_id=r["project_id"].strip(),
                    tower_name=r["tower_name"].strip(),
                    total_floors=int(r["floors"]),
                    wings=[w.strip() for w in r["wings"].split(";") if w.strip()],
                    base_rate_sqft=float(r["base_rate_per_sqft"]),
                )
                self.towers[twr.tower_id] = twr
                for wing_code in twr.wings:
                    self.wing_approvals[(twr.tower_id, wing_code)] = {}

        with open(root / "milestones.csv", newline="", encoding="utf-8") as fh:
            stages = []
            for r in csv.DictReader(fh):
                st = StageSchedule(
                    stage_code=r["milestone_code"].strip(),
                    seq_no=int(r["sequence"]),
                    clp_share_pct=float(r["clp_pct"]),
                    cert_scope=r["certified_per"].strip(),
                )
                self.stage_map[st.stage_code] = st
                stages.append(st)
            self.ordered_stages = sorted(stages, key=lambda x: x.seq_no)

        with open(root / "units.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                u = FlatUnit(
                    unit_id=r["unit_id"].strip(),
                    tower_id=r["tower_id"].strip(),
                    wing=r["wing"].strip(),
                    floor_no=int(r["floor"]),
                    area_sqm=float(r["carpet_area_sqm"]),
                    area_sqft=float(r["carpet_area_sqft"]),
                    is_park_facing=to_bool(r["park_facing"]),
                    is_corner=to_bool(r["corner"]),
                    parking_count=int(r["parking_slots"]),
                )
                self.units[u.unit_id] = u

        with open(root / "customers.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                buyer = BuyerProfile(
                    customer_id=r["customer_id"].strip(),
                    full_name=r["customer_name"].strip(),
                    gender=r["gender"].strip(),
                    female_primary_owner=to_bool(r["first_owner_woman"]),
                    pan_no=r["pan"].strip(),
                    phone=r["mobile"].strip(),
                    city=r["city"].strip(),
                )
                self.buyers[buyer.customer_id] = buyer

        with open(root / "certifications.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                cert = StageCertification(
                    cert_id=r["cert_id"].strip(),
                    tower_id=r["tower_id"].strip(),
                    wing=r["wing"].strip(),
                    stage_code=r["milestone_code"].strip(),
                    cert_date=to_date(r["certified_date"]),
                    approved_by=r["engineer"].strip(),
                )
                self.cert_catalog[cert.cert_id] = cert

        with open(root / "bookings.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                self.booking_rows[r["booking_id"].strip()] = r

        with open(root / "payments.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rec = ReceiptEntry(
                    payment_id=r["payment_id"].strip(),
                    booking_id=r["booking_id"].strip(),
                    paid_ts=to_datetime(r["payment_ts"]),
                    amount=nearest_rupee(float(r["amount"])),
                    pay_mode=r["mode"].strip(),
                    utr_ref=r["reference"].strip(),
                )
                self.payment_catalog[rec.payment_id] = rec

    # --- Internal Accounting Mechanics ---

    def _allocate_demand_id(self) -> str:
        code = f"DMD-{self._invoice_counter:04d}"
        self._invoice_counter += 1
        return code

    def get_net_balance(self, booking: UnitBooking) -> int:
        note_dues = sum(inv.pending_note_dues for inv in booking.invoices)
        int_dues = sum(max(0, inv.accrued_interest - inv.interest_settled) for inv in booking.invoices)
        return max(0, note_dues + int_dues - booking.excess_advance)

    def _update_overdue_interest(self, booking: UnitBooking, cutoff_date: date):
        # 12% simple interest per annum calculated daily after due date
        for inv in booking.invoices:
            overdue_amt = inv.pending_note_dues
            if overdue_amt > 0 and cutoff_date > inv.due_date:
                from_dt = max(inv.due_date, inv.interest_calc_upto or inv.due_date)
                if cutoff_date > from_dt:
                    late_days = (cutoff_date - from_dt).days
                    added_int = nearest_rupee(
                        Decimal(str(overdue_amt)) * Decimal("0.12") * Decimal(str(late_days)) / Decimal("365")
                    )
                    if added_int > 0:
                        inv.accrued_interest += added_int
                        booking.cumulative_interest += added_int
                    inv.interest_calc_upto = cutoff_date

    def _raise_invoice(
        self,
        booking: UnitBooking,
        issue_date: date,
        event_ts: str,
        line_items: List[InvoiceItem],
        grace_days: int = 15,
    ) -> BillingInvoice:
        unit = self.units[booking.unit_id]
        tower = self.towers[unit.tower_id]
        project = self.projects[tower.project_id]

        # Roll any unpaid accrued interest from older invoices onto this demand note
        self._update_overdue_interest(booking, issue_date)
        carried_interest = 0
        for inv in booking.invoices:
            unpaid_int = max(0, inv.accrued_interest - inv.interest_settled)
            if unpaid_int > 0:
                carried_interest += unpaid_int
                inv.interest_settled += unpaid_int

        if carried_interest > 0:
            line_items.append(
                InvoiceItem(
                    item_type="INTEREST",
                    stage_code="INTEREST",
                    amount=carried_interest,
                    is_taxable=False,
                )
            )

        gst_rate = get_applicable_gst(
            unit.area_sqm,
            booking.total_agreement_price,
            issue_date,
            project.cc_received_date,
        )
        taxable_total = sum(item.amount for item in line_items if item.is_taxable)
        gst_val = nearest_rupee(Decimal(str(taxable_total)) * Decimal(str(gst_rate)) / Decimal("100")) if taxable_total > 0 else 0
        non_gst_sum = sum(item.amount for item in line_items)
        invoice_total = non_gst_sum + gst_val

        invoice = BillingInvoice(
            demand_no=self._allocate_demand_id(),
            booking_id=booking.booking_id,
            issued_date=issue_date,
            due_date=issue_date + timedelta(days=grace_days),
            items=line_items,
            gst_pct=gst_rate if taxable_total > 0 else 0.0,
            gst_amount=gst_val,
            total_payable=invoice_total,
            non_gst_total=non_gst_sum,
        )
        booking.invoices.append(invoice)
        self.issued_invoices.append(invoice)
        booking.cumulative_billed += invoice_total

        if invoice_total < 0:
            booking.excess_advance += abs(invoice_total)
            invoice.principal_settled = invoice.non_gst_total

        if booking.excess_advance > 0 and invoice_total > 0:
            wallet = booking.excess_advance
            booking.excess_advance = 0
            self.settle_payment_dues(booking, wallet)

        self._log_account_event(
            booking,
            ts_str=event_ts,
            ev_type="DEMAND",
            ref=invoice.demand_no,
            debit=max(0, invoice_total),
            credit=abs(invoice_total) if invoice_total < 0 else 0,
            int_amt=0,
            prin_amt=0,
            gst_amt=0,
        )
        return invoice

    def settle_payment_dues(self, booking: UnitBooking, funds: int) -> Tuple[int, int, int]:
        # Precedence: 1. Interest -> 2. Oldest principal -> 3. That invoice's GST -> 4. Next invoice
        paid_int = 0
        paid_prin = 0
        paid_gst = 0

        for inv in booking.invoices:
            pending_int = max(0, inv.accrued_interest - inv.interest_settled)
            if pending_int > 0 and funds > 0:
                used = min(funds, pending_int)
                inv.interest_settled += used
                funds -= used
                paid_int += used

        for inv in booking.invoices:
            if inv.unpaid_principal > 0 and funds > 0:
                used = min(funds, inv.unpaid_principal)
                inv.principal_settled += used
                funds -= used
                paid_prin += used

            if inv.unpaid_gst > 0 and funds > 0:
                used = min(funds, inv.unpaid_gst)
                inv.gst_settled += used
                funds -= used
                paid_gst += used

        booking.excess_advance += funds
        return paid_int, paid_prin, paid_gst

    def _log_account_event(
        self,
        booking: UnitBooking,
        ts_str: str,
        ev_type: str,
        ref: str,
        debit: int,
        credit: int,
        int_amt: int,
        prin_amt: int,
        gst_amt: int,
    ):
        booking.events.append(
            AccountEvent(
                booking_id=booking.booking_id,
                timestamp_str=ts_str,
                event_type=ev_type,
                ref_code=ref,
                debit_amt=debit,
                credit_amt=credit,
                int_part=int_amt,
                prin_part=prin_amt,
                gst_part=gst_amt,
                wallet_advance=booking.excess_advance,
                net_outstanding=self.get_net_balance(booking),
            )
        )

    # --- Command Handlers ---

    def handle_book(self, booking_id: str):
        row = self.booking_rows[booking_id]
        unit = self.units[row["unit_id"].strip()]
        tower = self.towers[unit.tower_id]
        booked_dt = to_datetime(row["booking_ts"])
        plan_type = row["plan"].strip()
        planned_ag = to_datetime(row["agreement_ts"]) if row["agreement_ts"].strip() else None

        base_excl, pkg_cost, grand_val = compute_unit_pricing(
            unit.area_sqft,
            tower.base_rate_sqft,
            unit.floor_no,
            unit.is_park_facing,
            unit.is_corner,
            unit.parking_count,
        )
        # 8% discount on base agreement value (excluding parking) for down-payment plan
        disc_base = nearest_rupee(Decimal(str(base_excl)) * Decimal("0.92")) if plan_type == "DOWN_PAYMENT" else base_excl

        booking = UnitBooking(
            booking_id=booking_id,
            unit_id=unit.unit_id,
            customer_id=row["customer_id"].strip(),
            booked_ts=booked_dt,
            payment_plan=plan_type,
            planned_agreement_ts=planned_ag,
            price_excl_parking=base_excl,
            parking_total=pkg_cost,
            total_agreement_price=grand_val,
            discounted_base_price=disc_base,
            booking_status="ACTIVE",
        )
        self.active_bookings[booking.booking_id] = booking

        items: List[InvoiceItem] = []
        if plan_type == "CLP":
            book_stage = self.stage_map["BOOKING"]
            items.append(
                InvoiceItem(
                    item_type="MILESTONE",
                    stage_code="BOOKING",
                    amount=nearest_rupee(Decimal(str(base_excl)) * Decimal(str(book_stage.clp_share_pct)) / Decimal("100")),
                    is_taxable=True,
                )
            )
            # Add catch-up lines for stages already certified in this wing
            approved_stages = self.wing_approvals.get((unit.tower_id, unit.wing), {})
            for st in self.ordered_stages:
                if st.cert_scope == "TOWER_WING" and st.stage_code in approved_stages:
                    catchup_amt = nearest_rupee(Decimal(str(base_excl)) * Decimal(str(st.clp_share_pct)) / Decimal("100"))
                    items.append(
                        InvoiceItem(
                            item_type="MILESTONE",
                            stage_code=st.stage_code,
                            amount=catchup_amt,
                            is_taxable=True,
                        )
                    )
            self._raise_invoice(booking, booked_dt.date(), row["booking_ts"].strip(), items, grace_days=15)
        else:
            initial_95 = nearest_rupee(Decimal(str(disc_base)) * Decimal("0.95"))
            booking.dpp_initial_95 = initial_95
            items.append(
                InvoiceItem(
                    item_type="MILESTONE",
                    stage_code="BOOKING",
                    amount=initial_95,
                    is_taxable=True,
                )
            )
            self._raise_invoice(booking, booked_dt.date(), row["booking_ts"].strip(), items, grace_days=30)

        self.record_audit(f"[OK] BOOK {booking.booking_id} ({plan_type})")

    def handle_agreement(self, booking_id: str, ts_text: str):
        booking = self.active_bookings[booking_id]
        if booking.booking_status != "ACTIVE":
            self.record_audit(f"[REJECTED] AGREEMENT on inactive booking {booking_id}")
            return

        ag_dt = to_datetime(ts_text)
        booking.signed_agreement_ts = ag_dt

        unit = self.units[booking.unit_id]
        tower = self.towers[unit.tower_id]
        project = self.projects[tower.project_id]
        buyer = self.buyers[booking.customer_id]

        c_val, base_val, sd_rate, sd_amt, reg_amt = compute_stamp_and_reg(
            booking.total_agreement_price,
            unit.area_sqft,
            project.circle_rate_sqft,
            booking.parking_total,
            buyer.female_primary_owner,
        )
        self.duty_assessments.append(
            DutyAssessment(
                booking_id=booking.booking_id,
                agreement_val=booking.total_agreement_price,
                circle_val=c_val,
                assessed_base=base_val,
                duty_pct=sd_rate,
                stamp_duty_amt=sd_amt,
                reg_fee_amt=reg_amt,
            )
        )

        items: List[InvoiceItem] = []
        if booking.payment_plan == "CLP":
            ag_stage = self.stage_map["AGREEMENT"]
            ag_val = nearest_rupee(
                Decimal(str(booking.price_excl_parking)) * Decimal(str(ag_stage.clp_share_pct)) / Decimal("100")
            )
            items.append(
                InvoiceItem(
                    item_type="MILESTONE",
                    stage_code="AGREEMENT",
                    amount=ag_val,
                    is_taxable=True,
                )
            )
        items.append(InvoiceItem(item_type="STAMP_DUTY", stage_code="AGREEMENT", amount=sd_amt, is_taxable=False))
        items.append(InvoiceItem(item_type="REGISTRATION", stage_code="AGREEMENT", amount=reg_amt, is_taxable=False))

        self._raise_invoice(booking, ag_dt.date(), ts_text.strip(), items, grace_days=15)
        self.record_audit(f"[OK] AGREEMENT {booking.booking_id}")

    def handle_certify(self, cert_id: str) -> bool:
        cert = self.cert_catalog[cert_id]
        wing_key = (cert.tower_id, cert.wing)
        done_map = self.wing_approvals.setdefault(wing_key, {})

        if cert.stage_code in done_map:
            self.record_audit(f"[REJECTED] CERTIFY {cert_id}: already certified")
            return False

        wing_stages = [s for s in self.ordered_stages if s.cert_scope == "TOWER_WING"]
        stage_names = [s.stage_code for s in wing_stages]
        if cert.stage_code not in stage_names:
            self.record_audit(f"[REJECTED] CERTIFY {cert_id}: invalid stage")
            return False

        pos = stage_names.index(cert.stage_code)
        if pos > 0 and stage_names[pos - 1] not in done_map:
            self.record_audit(f"[REJECTED] CERTIFY {cert_id}: previous stage {stage_names[pos - 1]} pending")
            return False

        done_map[cert.stage_code] = cert.cert_date
        stage_info = self.stage_map[cert.stage_code]

        for booking in self.active_bookings.values():
            if booking.booking_status == "ACTIVE" and booking.payment_plan == "CLP":
                u = self.units[booking.unit_id]
                if u.tower_id == cert.tower_id and u.wing == cert.wing:
                    stage_amt = nearest_rupee(
                        Decimal(str(booking.price_excl_parking)) * Decimal(str(stage_info.clp_share_pct)) / Decimal("100")
                    )
                    items = [
                        InvoiceItem(
                            item_type="MILESTONE",
                            stage_code=cert.stage_code,
                            amount=stage_amt,
                            is_taxable=True,
                        )
                    ]
                    self._raise_invoice(
                        booking,
                        cert.cert_date,
                        f"{cert.cert_date.isoformat()} 09:00:00",
                        items,
                        grace_days=15,
                    )

        self.record_audit(f"[OK] CERTIFY {cert_id}")
        return True

    def handle_payment(self, payment_id: str) -> bool:
        rec = self.payment_catalog[payment_id]
        booking = self.active_bookings[rec.booking_id]

        if booking.booking_status == "CANCELLED":
            self.record_audit(f"[REJECTED] PAYMENT {payment_id}: booking cancelled")
            return False

        pay_dt = rec.paid_ts.date()
        self._update_overdue_interest(booking, pay_dt)

        available_funds = rec.amount + booking.excess_advance
        booking.excess_advance = 0
        p_int, p_prin, p_gst = self.settle_payment_dues(booking, available_funds)
        booking.cumulative_paid += rec.amount

        self._log_account_event(
            booking,
            ts_str=rec.paid_ts.strftime("%Y-%m-%d %H:%M:%S"),
            ev_type="PAYMENT",
            ref=rec.payment_id,
            debit=0,
            credit=rec.amount,
            int_amt=p_int,
            prin_amt=p_prin,
            gst_amt=p_gst,
        )

        # Withdraw termination notice if full dues cleared within 30 days
        if booking.notice_issued_ts is not None and booking.booking_status == "ACTIVE":
            notice_age = (pay_dt - booking.notice_issued_ts.date()).days
            if notice_age <= 30 and self.get_net_balance(booking) == 0:
                booking.notice_revoked = True
                booking.notice_issued_ts = None
                self.record_audit(f"[OK] Termination notice withdrawn for {booking.booking_id}")

        return True

    def handle_change_plan(self, booking_id: str, ts_text: str, target_plan: str) -> bool:
        booking = self.active_bookings[booking_id]
        if booking.signed_agreement_ts is not None:
            self.record_audit(f"[REJECTED] CHANGE_PLAN {booking_id}: agreement already signed")
            return False
        booking.payment_plan = target_plan.strip()
        if booking.payment_plan == "DOWN_PAYMENT":
            booking.discounted_base_price = nearest_rupee(Decimal(str(booking.price_excl_parking)) * Decimal("0.92"))
        else:
            booking.discounted_base_price = booking.price_excl_parking
        self.record_audit(f"[OK] CHANGE_PLAN {booking_id} -> {booking.payment_plan}")
        return True

    def handle_termination_notice(self, booking_id: str, ts_text: str) -> bool:
        booking = self.active_bookings[booking_id]
        n_ts = to_datetime(ts_text)
        n_dt = n_ts.date()

        overdue_90 = any(
            inv.pending_note_dues > 0 and (n_dt - inv.due_date).days > 90
            for inv in booking.invoices
        )
        if not overdue_90 or booking.booking_status != "ACTIVE":
            self.record_audit(f"[REJECTED] TERMINATION_NOTICE {booking_id}")
            return False

        booking.notice_issued_ts = n_ts
        booking.notice_revoked = False
        self.record_audit(f"[OK] TERMINATION_NOTICE {booking_id}")
        return True

    def handle_enforce_termination(self, booking_id: str, ts_text: str) -> bool:
        booking = self.active_bookings[booking_id]
        e_ts = to_datetime(ts_text)
        if booking.booking_status != "ACTIVE" or booking.notice_issued_ts is None:
            self.record_audit(f"[REJECTED] ENFORCE_TERMINATION {booking_id}: no active notice")
            return False

        if (e_ts.date() - booking.notice_issued_ts.date()).days <= 30:
            self.record_audit(f"[REJECTED] ENFORCE_TERMINATION {booking_id}: within 30-day window")
            return False

        self.handle_cancel(booking_id, ts_text, "Termination enforced", post_agreement_override=True)
        return True

    def handle_cancel(
        self,
        booking_id: str,
        ts_text: str,
        reason: str = "",
        post_agreement_override: bool = False,
    ):
        booking = self.active_bookings[booking_id]
        if booking.booking_status == "CANCELLED":
            return

        c_ts = to_datetime(ts_text)
        c_dt = c_ts.date()

        is_post_agreement = post_agreement_override or (
            booking.signed_agreement_ts is not None and c_ts >= booking.signed_agreement_ts
        )

        if not is_post_agreement:
            cap_2pct = nearest_rupee(Decimal(str(booking.total_agreement_price)) * Decimal("0.02"))
            forfeit = min(cap_2pct, booking.cumulative_paid)
        else:
            forfeit = nearest_rupee(Decimal(str(booking.total_agreement_price)) * Decimal("0.10"))

        cancel_qtr = year_quarter(c_dt)
        gst_back = sum(inv.gst_settled for inv in booking.invoices if year_quarter(inv.issued_date) == cancel_qtr)
        total_gst_collected = sum(inv.gst_settled for inv in booking.invoices)
        retained_gst = total_gst_collected - gst_back

        refund = max(0, booking.cumulative_paid - forfeit - retained_gst)

        booking.booking_status = "CANCELLED"
        booking.cancelled_ts = c_ts
        booking.forfeited_amt = forfeit
        booking.refunded_gst = gst_back
        booking.net_refund_due = refund
        booking.notice_issued_ts = None

        self._log_account_event(
            booking,
            ts_str=ts_text.strip(),
            ev_type="CANCEL",
            ref=f"CANC-{booking.booking_id}",
            debit=forfeit,
            credit=0,
            int_amt=0,
            prin_amt=0,
            gst_amt=0,
        )
        self.record_audit(f"[OK] CANCEL {booking.booking_id}")

    def handle_offer_possession(self, tower_id: str, offer_dt_str: str):
        t_id = tower_id.strip()
        offer_dt = to_date(offer_dt_str)
        tower = self.towers[t_id]
        project = self.projects[tower.project_id]

        for booking in self.active_bookings.values():
            if booking.booking_status != "ACTIVE":
                continue
            unit = self.units[booking.unit_id]
            if unit.tower_id != t_id:
                continue

            unit_principal_paid = sum(
                min(
                    inv.principal_settled,
                    sum(i.amount for i in inv.items if i.item_type in ("MILESTONE", "POSSESSION", "PARKING")),
                )
                for inv in booking.invoices
            ) + booking.excess_advance

            comp = compute_rera_delay_comp(
                project.rera_handover_date,
                project.has_force_majeure,
                offer_dt,
                unit_principal_paid,
            )
            booking.handover_offer_date = offer_dt
            booking.rera_compensation = comp

            items: List[InvoiceItem] = []
            if booking.payment_plan == "CLP":
                pos_stage = self.stage_map["POSSESSION"]
                pos_val = nearest_rupee(
                    Decimal(str(booking.price_excl_parking)) * Decimal(str(pos_stage.clp_share_pct)) / Decimal("100")
                )
            else:
                pos_val = booking.discounted_base_price - booking.dpp_initial_95

            items.append(
                InvoiceItem(
                    item_type="POSSESSION",
                    stage_code="POSSESSION",
                    amount=pos_val,
                    is_taxable=True,
                )
            )
            if booking.parking_total > 0:
                items.append(
                    InvoiceItem(
                        item_type="PARKING",
                        stage_code="POSSESSION",
                        amount=booking.parking_total,
                        is_taxable=True,
                    )
                )
            if comp > 0:
                items.append(
                    InvoiceItem(
                        item_type="DELAY_COMPENSATION",
                        stage_code="POSSESSION",
                        amount=-comp,
                        is_taxable=False,
                    )
                )

            self._raise_invoice(
                booking,
                offer_dt,
                f"{offer_dt.isoformat()} 09:00:00",
                items,
                grace_days=15,
            )
            booking.booking_status = "POSSESSED"

        self.record_audit(f"[OK] OFFER_POSSESSION {t_id}")

    # --- Command Dispatcher ---

    def run_command(self, line: str) -> Optional[str]:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            return None

        tokens = [t.strip() for t in cleaned.split("|")]
        action = tokens[0].upper()

        if action == "BOOK":
            self.handle_book(tokens[1])
        elif action == "AGREEMENT":
            self.handle_agreement(tokens[1], tokens[2])
        elif action == "CERTIFY":
            self.handle_certify(tokens[1])
        elif action == "PAYMENT":
            self.handle_payment(tokens[1])
        elif action == "CHANGE_PLAN":
            self.handle_change_plan(tokens[1], tokens[2], tokens[3])
        elif action == "CANCEL":
            reason = tokens[3] if len(tokens) > 3 else ""
            self.handle_cancel(tokens[1], tokens[2], reason)
        elif action == "TERMINATION_NOTICE":
            self.handle_termination_notice(tokens[1], tokens[2])
        elif action == "ENFORCE_TERMINATION":
            self.handle_enforce_termination(tokens[1], tokens[2])
        elif action == "OFFER_POSSESSION":
            self.handle_offer_possession(tokens[1], tokens[2])
        elif action == "PRINT_DEMAND_REGISTER":
            from .exporters import StatementExporter
            return StatementExporter.render_demand_register(self)
        elif action == "PRINT_LEDGER":
            from .exporters import StatementExporter
            return StatementExporter.render_customer_ledger(self, tokens[1])
        elif action == "PRINT_FINAL_STATEMENT":
            from .exporters import StatementExporter
            return StatementExporter.render_final_statement(self, tokens[1])
        else:
            raise ValueError(f"Unsupported command: {action}")
        return None
