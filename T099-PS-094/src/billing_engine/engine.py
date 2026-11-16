from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from .models import (
    Booking,
    Customer,
    DemandNote,
    LedgerEntry,
    Payment,
    Project,
    Unit,
)
from .rules import (
    calculate_agreement_value,
    calculate_delay_compensation,
    calculate_stamp_duty_and_registration,
    determine_gst_rate,
    get_quarter,
    round_rupee,
)


def parse_date(dt_str: str) -> date:
    return date.fromisoformat(dt_str.strip())


class BillingEngine:
    def __init__(self):
        self.projects: Dict[str, Project] = {}
        self.units: Dict[str, Unit] = {}
        self.customers: Dict[str, Customer] = {}
        self.bookings: Dict[str, Booking] = {}
        self.all_demands: List[DemandNote] = []
        self._demand_seq = 1
        self.logs: List[str] = []

    def _log(self, msg: str):
        self.logs.append(msg)

    def register_project(
        self,
        project_id: str,
        name: str,
        rera_date: str,
        cc_date: str,
        force_majeure: str,
        circle_rate: str,
    ):
        cc = parse_date(cc_date) if cc_date and cc_date.upper() != "NONE" else None
        fm = force_majeure.strip().upper() in ("TRUE", "YES", "1")
        proj = Project(
            project_id=project_id.strip(),
            name=name.strip(),
            rera_date=parse_date(rera_date),
            cc_date=cc,
            force_majeure=fm,
            circle_rate=float(circle_rate),
        )
        self.projects[proj.project_id] = proj
        self._log(f"[OK] Project {proj.project_id} registered.")

    def add_tower(self, project_id: str, tower_id: str):
        proj = self.projects[project_id.strip()]
        tid = tower_id.strip()
        if tid not in proj.towers:
            proj.towers[tid] = {}
        self._log(f"[OK] Tower {tid} added to {proj.project_id}.")

    def register_unit(
        self,
        unit_id: str,
        project_id: str,
        tower_id: str,
        floor: str,
        carpet_sqft: str,
        carpet_sqm: str,
        base_rate: str,
        park_facing: str,
        corner: str,
        parking_slots: str,
    ):
        unit = Unit(
            unit_id=unit_id.strip(),
            project_id=project_id.strip(),
            tower_id=tower_id.strip(),
            floor=int(floor),
            carpet_sqft=float(carpet_sqft),
            carpet_sqm=float(carpet_sqm),
            base_rate=float(base_rate),
            park_facing=park_facing.strip().upper() in ("TRUE", "YES", "1"),
            corner=corner.strip().upper() in ("TRUE", "YES", "1"),
            parking_slots=int(parking_slots),
        )
        self.units[unit.unit_id] = unit
        self._log(f"[OK] Unit {unit.unit_id} registered.")

    def register_customer(self, customer_id: str, name: str, is_female_first_owner: str):
        cust = Customer(
            customer_id=customer_id.strip(),
            name=name.strip(),
            is_female_first_owner=is_female_first_owner.strip().upper() in ("TRUE", "YES", "1"),
        )
        self.customers[cust.customer_id] = cust
        self._log(f"[OK] Customer {cust.customer_id} registered.")

    def book_unit(
        self,
        booking_id: str,
        unit_id: str,
        customer_id: str,
        plan: str,
        booking_date: str,
        booking_amount: str,
        agreement_date: str = "",
    ):
        unit = self.units[unit_id.strip()]
        proj = self.projects[unit.project_id]
        cust = self.customers[customer_id.strip()]
        b_date = parse_date(booking_date)
        a_date = parse_date(agreement_date) if agreement_date and agreement_date.strip().upper() != "NONE" else None
        plan_code = plan.strip().upper()

        excl_pkg, pkg_charge, total_val = calculate_agreement_value(
            unit.carpet_sqft,
            unit.base_rate,
            unit.floor,
            unit.park_facing,
            unit.corner,
            unit.parking_slots,
        )

        if plan_code == "DPP":
            disc_excl = round_rupee(Decimal(str(excl_pkg)) * Decimal("0.92"))
        else:
            disc_excl = excl_pkg

        effective_total = disc_excl + pkg_charge
        gst_rate = determine_gst_rate(unit.carpet_sqm, total_val, b_date, proj.cc_date)
        stamp_duty, reg_fee = calculate_stamp_duty_and_registration(
            effective_total,
            unit.carpet_sqft,
            proj.circle_rate,
            pkg_charge,
            cust.is_female_first_owner,
        )

        booking = Booking(
            booking_id=booking_id.strip(),
            unit_id=unit.unit_id,
            customer_id=cust.customer_id,
            plan=plan_code,
            booking_date=b_date,
            agreement_date=a_date,
            agreement_value_excl_parking=excl_pkg,
            parking_charge=pkg_charge,
            agreement_value_total=total_val,
            discounted_excl_parking=disc_excl,
            effective_total_value=effective_total,
            gst_rate=gst_rate,
            stamp_duty=stamp_duty,
            registration_fee=reg_fee,
        )
        self.bookings[booking.booking_id] = booking
        self._log(f"[OK] Booking {booking.booking_id} created ({plan_code}).")

        if plan_code == "CLP":
            self._create_demand(booking, "BOOKING", b_date)
        elif plan_code == "DPP":
            self._create_demand(booking, "DPP_95", b_date + timedelta(days=15))

        if int(booking_amount) > 0:
            self.record_payment(
                f"PAY-INIT-{booking.booking_id}",
                booking.booking_id,
                b_date.isoformat(),
                booking_amount,
                "10:00",
            )

    def switch_plan(self, booking_id: str, new_plan: str, switch_date: str):
        booking = self.bookings[booking_id.strip()]
        unit = self.units[booking.unit_id]
        proj = self.projects[unit.project_id]
        tower_certs = proj.towers.get(unit.tower_id, {})

        agreement_demanded = any(d.milestone_code == "AGREEMENT" for d in booking.demands)
        if "AGREEMENT" in tower_certs or agreement_demanded:
            self._log(f"[REJECTED] Switch plan for {booking.booking_id}: Agreement milestone already reached.")
            return False

        target = new_plan.strip().upper()
        booking.plan = target
        if target == "DPP":
            booking.discounted_excl_parking = round_rupee(
                Decimal(str(booking.agreement_value_excl_parking)) * Decimal("0.92")
            )
        else:
            booking.discounted_excl_parking = booking.agreement_value_excl_parking
        booking.effective_total_value = booking.discounted_excl_parking + booking.parking_charge
        self._log(f"[OK] Booking {booking.booking_id} switched to {target}.")
        return True

    def certify_milestone(self, project_id: str, tower_id: str, milestone_code: str, cert_date: str):
        proj = self.projects[project_id.strip()]
        tid = tower_id.strip()
        m_code = milestone_code.strip().upper()
        c_date = parse_date(cert_date)

        seq_codes = [m.code for m in proj.milestones]
        if m_code not in seq_codes:
            self._log(f"[REJECTED] Unknown milestone {m_code}.")
            return False

        idx = seq_codes.index(m_code)
        certified = proj.towers.setdefault(tid, {})

        if idx > 0:
            prev_code = seq_codes[idx - 1]
            if prev_code not in certified:
                self._log(
                    f"[REJECTED] Milestone {m_code} in {proj.project_id}/{tid}: "
                    f"previous milestone {prev_code} not certified."
                )
                return False

        certified[m_code] = c_date
        self._log(f"[OK] Milestone {m_code} certified for {proj.project_id}/{tid} on {c_date}.")
        return True

    def _accrue_interest_up_to(self, booking: Booking, as_of_date: date):
        # BR-05: Compute daily simple interest at 12% p.a. on overdue principal from due_date
        for d in booking.demands:
            if d.principal_due > 0 and as_of_date > d.due_date:
                start = max(d.due_date, d.last_interest_calc_date or d.due_date)
                if as_of_date > start:
                    days = (as_of_date - start).days
                    interest = round_rupee(
                        Decimal(str(d.principal_due))
                        * Decimal("0.12")
                        * Decimal(str(days))
                        / Decimal("365")
                    )
                    d.unbilled_interest += interest
                    d.last_interest_calc_date = as_of_date

    def _create_demand(self, booking: Booking, milestone_code: str, d_date: date) -> DemandNote:
        unit = self.units[booking.unit_id]
        proj = self.projects[unit.project_id]

        self._accrue_interest_up_to(booking, d_date)
        carried_interest = sum(d.unbilled_interest for d in booking.demands)
        for d in booking.demands:
            d.unbilled_interest = 0

        if booking.plan == "CLP":
            m_def = next(m for m in proj.milestones if m.code == milestone_code)
            principal = round_rupee(
                Decimal(str(booking.agreement_value_excl_parking))
                * Decimal(str(m_def.clp_percent))
                / Decimal("100")
            )
            if milestone_code == "POSSESSION":
                principal += booking.parking_charge
        else:
            if milestone_code == "DPP_95":
                principal = round_rupee(Decimal(str(booking.discounted_excl_parking)) * Decimal("0.95"))
            else:
                principal = (
                    booking.discounted_excl_parking
                    - round_rupee(Decimal(str(booking.discounted_excl_parking)) * Decimal("0.95"))
                    + booking.parking_charge
                )

        if milestone_code == "POSSESSION" and booking.delay_compensation > 0:
            principal = max(0, principal - booking.delay_compensation)

        gst_rate = determine_gst_rate(unit.carpet_sqm, booking.agreement_value_total, d_date, proj.cc_date)
        gst_amount = round_rupee(Decimal(str(principal)) * Decimal(str(gst_rate)) / Decimal("100"))

        demand = DemandNote(
            demand_id=f"DN-{self._demand_seq:04d}",
            booking_id=booking.booking_id,
            milestone_code=milestone_code,
            demand_date=d_date,
            due_date=d_date + timedelta(days=15),
            principal_amount=principal,
            gst_rate=gst_rate,
            gst_amount=gst_amount,
            interest_billed=carried_interest,
        )
        self._demand_seq += 1
        booking.demands.append(demand)
        self.all_demands.append(demand)

        if milestone_code == "AGREEMENT" and booking.agreement_date is None:
            booking.agreement_date = d_date

        self._record_ledger(
            booking,
            d_date,
            demand.demand_id,
            f"Demand: {milestone_code} (Prin {principal}, GST {gst_amount}, Int {carried_interest})",
            debit=demand.total_billed,
            credit=0,
        )

        if booking.advance_balance > 0:
            adv = booking.advance_balance
            booking.advance_balance = 0
            self._allocate_funds(booking, adv)

        return demand

    def raise_demand(self, booking_id: str, milestone_code: str, demand_date: str) -> Optional[DemandNote]:
        booking = self.bookings[booking_id.strip()]
        if booking.status != "ACTIVE":
            self._log(f"[REJECTED] Raise demand on non-active booking {booking.booking_id}.")
            return None

        unit = self.units[booking.unit_id]
        proj = self.projects[unit.project_id]
        m_code = milestone_code.strip().upper()
        d_date = parse_date(demand_date)

        if m_code != "DPP_95":
            tower_certs = proj.towers.get(unit.tower_id, {})
            if m_code not in tower_certs:
                self._log(
                    f"[REJECTED] Demand for {m_code} on {booking.booking_id}: "
                    f"milestone not certified in tower {unit.tower_id}."
                )
                return None

        if any(d.milestone_code == m_code for d in booking.demands):
            self._log(f"[REJECTED] Duplicate demand {m_code} for {booking.booking_id}.")
            return None

        dn = self._create_demand(booking, m_code, d_date)
        self._log(f"[OK] Raised {dn.demand_id} for {booking.booking_id} ({m_code}).")
        return dn

    def _allocate_funds(self, booking: Booking, available: int) -> tuple[int, int, int, int]:
        # BR-06: Precedence -> Interest first, then oldest demand principal, then GST of that demand
        alloc_int = 0
        alloc_prin = 0
        alloc_gst = 0

        for d in booking.demands:
            unpaid_billed_int = max(0, d.interest_billed - d.interest_paid)
            if unpaid_billed_int > 0 and available > 0:
                take = min(available, unpaid_billed_int)
                d.interest_paid += take
                available -= take
                alloc_int += take

            if d.unbilled_interest > 0 and available > 0:
                take = min(available, d.unbilled_interest)
                d.unbilled_interest -= take
                available -= take
                alloc_int += take

        for d in booking.demands:
            if d.principal_due > 0 and available > 0:
                take = min(available, d.principal_due)
                d.principal_paid += take
                available -= take
                alloc_prin += take

            if d.gst_due > 0 and available > 0:
                take = min(available, d.gst_due)
                d.gst_paid += take
                available -= take
                alloc_gst += take

        booking.advance_balance += available
        return alloc_int, alloc_prin, alloc_gst, available

    def record_payment(
        self,
        payment_id: str,
        booking_id: str,
        payment_date: str,
        amount: str,
        timestamp: str = "12:00",
    ):
        booking = self.bookings[booking_id.strip()]
        p_date = parse_date(payment_date)
        amt = int(amount)

        self._accrue_interest_up_to(booking, p_date)

        total_pool = amt + booking.advance_balance
        booking.advance_balance = 0
        a_int, a_prin, a_gst, rem_adv = self._allocate_funds(booking, total_pool)

        pay = Payment(
            payment_id=payment_id.strip(),
            booking_id=booking.booking_id,
            payment_date=p_date,
            timestamp=timestamp.strip(),
            amount=amt,
            allocated_interest=a_int,
            allocated_principal=a_prin,
            allocated_gst=a_gst,
            unallocated_advance=rem_adv,
        )
        booking.payments.append(pay)

        self._record_ledger(
            booking,
            p_date,
            pay.payment_id,
            f"Payment Received (Int {a_int}, Prin {a_prin}, GST {a_gst}, Adv {rem_adv})",
            debit=0,
            credit=amt,
        )

        if booking.termination_notice_date is not None and booking.status == "ACTIVE":
            days_since_notice = (p_date - booking.termination_notice_date).days
            all_cleared = all(
                d.principal_due == 0
                and d.gst_due == 0
                and (d.interest_billed - d.interest_paid) == 0
                and d.unbilled_interest == 0
                for d in booking.demands
            )
            if days_since_notice <= 30 and all_cleared:
                booking.termination_withdrawn = True
                booking.termination_notice_date = None
                self._log(f"[OK] Termination notice for {booking.booking_id} WITHDRAWN on day {days_since_notice}.")

    def issue_termination(self, booking_id: str, notice_date: str):
        booking = self.bookings[booking_id.strip()]
        n_date = parse_date(notice_date)
        overdue_90 = any(
            (d.principal_due + d.gst_due) > 0 and (n_date - d.due_date).days > 90
            for d in booking.demands
        )
        if not overdue_90:
            self._log(f"[REJECTED] Termination notice for {booking.booking_id}: no demand overdue > 90 days.")
            return False

        booking.termination_notice_date = n_date
        booking.termination_withdrawn = False
        self._log(f"[OK] Termination notice issued for {booking.booking_id} on {n_date}.")
        return True

    def check_termination_expiry(self, booking_id: str, check_date: str):
        booking = self.bookings[booking_id.strip()]
        c_date = parse_date(check_date)
        if (
            booking.status == "ACTIVE"
            and booking.termination_notice_date is not None
            and (c_date - booking.termination_notice_date).days > 30
        ):
            self.cancel_booking(booking.booking_id, c_date.isoformat(), "TERMINATION_NOTICE_EXPIRED", force_post_agreement=True)

    def offer_possession(self, booking_id: str, offer_date: str):
        booking = self.bookings[booking_id.strip()]
        unit = self.units[booking.unit_id]
        proj = self.projects[unit.project_id]
        o_date = parse_date(offer_date)

        total_prin_paid = sum(d.principal_paid for d in booking.demands) + booking.advance_balance
        comp = calculate_delay_compensation(
            proj.rera_date,
            proj.force_majeure,
            o_date,
            total_prin_paid,
        )
        booking.possession_offer_date = o_date
        booking.delay_compensation = comp
        if comp > 0:
            self._record_ledger(
                booking,
                o_date,
                f"COMP-{booking.booking_id}",
                "RERA Delay Compensation Credit (10.5% p.a.)",
                debit=0,
                credit=comp,
            )
        self._log(f"[OK] Possession offered for {booking.booking_id} on {o_date}; compensation = {comp}.")

    def cancel_booking(
        self,
        booking_id: str,
        cancel_date: str,
        reason: str = "CUSTOMER_REQUEST",
        force_post_agreement: bool = False,
    ):
        booking = self.bookings[booking_id.strip()]
        if booking.status == "CANCELLED":
            return

        c_date = parse_date(cancel_date)
        unit = self.units[booking.unit_id]
        proj = self.projects[unit.project_id]
        tower_certs = proj.towers.get(unit.tower_id, {})

        agreement_reached = (
            force_post_agreement
            or ("AGREEMENT" in tower_certs and c_date >= tower_certs["AGREEMENT"])
            or any(d.milestone_code == "AGREEMENT" and c_date >= d.demand_date for d in booking.demands)
            or (booking.agreement_date is not None and c_date >= booking.agreement_date)
        )

        total_cash_paid = sum(p.amount for p in booking.payments)
        total_gst_paid = sum(d.gst_paid for d in booking.demands)

        if not agreement_reached:
            two_pct = round_rupee(Decimal(str(booking.effective_total_value)) * Decimal("0.02"))
            forfeiture = min(two_pct, total_cash_paid)
        else:
            forfeiture = round_rupee(Decimal(str(booking.effective_total_value)) * Decimal("0.10"))

        c_quarter = get_quarter(c_date)
        gst_refund = sum(
            d.gst_paid for d in booking.demands if get_quarter(d.demand_date) == c_quarter
        )
        gst_non_refundable = total_gst_paid - gst_refund

        refund_payable = max(0, total_cash_paid - forfeiture - gst_non_refundable)

        booking.status = "CANCELLED"
        booking.cancellation_date = c_date
        booking.forfeiture_amount = forfeiture
        booking.gst_refunded = gst_refund
        booking.refund_payable = refund_payable
        booking.refund_due_date = c_date + timedelta(days=45)

        self._record_ledger(
            booking,
            c_date,
            f"CANC-{booking.booking_id}",
            f"Booking Cancelled ({reason}) | Forfeiture: {forfeiture} | GST Refund: {gst_refund}",
            debit=forfeiture,
            credit=0,
        )
        self._log(
            f"[OK] Booking {booking.booking_id} CANCELLED on {c_date}. "
            f"Forfeiture={forfeiture}, Refund={refund_payable}."
        )

    def _record_ledger(
        self,
        booking: Booking,
        dt: date,
        ref_id: str,
        particulars: str,
        debit: int,
        credit: int,
    ):
        prev_bal = booking.ledger[-1].balance if booking.ledger else 0
        new_bal = prev_bal + debit - credit
        booking.ledger.append(
            LedgerEntry(
                entry_date=dt,
                ref_id=ref_id,
                particulars=particulars,
                debit=debit,
                credit=credit,
                balance=new_bal,
            )
        )

    def execute_command_line(self, line: str) -> Optional[str]:
        raw = line.strip()
        if not raw or raw.startswith("#"):
            return None

        parts = [p.strip() for p in raw.split("|")]
        cmd = parts[0].upper()

        if cmd == "REGISTER_PROJECT":
            self.register_project(*parts[1:7])
        elif cmd == "ADD_TOWER":
            self.add_tower(*parts[1:3])
        elif cmd == "REGISTER_UNIT":
            self.register_unit(*parts[1:11])
        elif cmd == "REGISTER_CUSTOMER":
            self.register_customer(*parts[1:4])
        elif cmd == "BOOK_UNIT":
            self.book_unit(*parts[1:])
        elif cmd == "SWITCH_PLAN":
            self.switch_plan(*parts[1:4])
        elif cmd == "CERTIFY_MILESTONE":
            self.certify_milestone(*parts[1:5])
        elif cmd == "RAISE_DEMAND":
            self.raise_demand(*parts[1:4])
        elif cmd == "RECORD_PAYMENT":
            self.record_payment(*parts[1:])
        elif cmd == "ISSUE_TERMINATION":
            self.issue_termination(*parts[1:3])
        elif cmd == "CHECK_TERMINATION_EXPIRY":
            self.check_termination_expiry(*parts[1:3])
        elif cmd == "OFFER_POSSESSION":
            self.offer_possession(*parts[1:3])
        elif cmd == "CANCEL_BOOKING":
            self.cancel_booking(*parts[1:])
        elif cmd == "PRINT_DEMAND_REGISTER":
            from .reporter import Reporter
            return Reporter.format_demand_register(self)
        elif cmd == "PRINT_LEDGER":
            from .reporter import Reporter
            return Reporter.format_customer_ledger(self, parts[1])
        elif cmd == "PRINT_FINAL_STATEMENT":
            from .reporter import Reporter
            return Reporter.format_final_statement(self, parts[1])
        else:
            raise ValueError(f"Unknown command: {cmd}")
        return None
