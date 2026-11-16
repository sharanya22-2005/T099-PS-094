from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple


def round_rupee(value: float | Decimal | int) -> int:
    # BR-12: Round monetary amounts to nearest integer rupee using standard half-up
    d = Decimal(str(value))
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_agreement_value(
    carpet_sqft: float,
    base_rate: float,
    floor: int,
    park_facing: bool,
    corner: bool,
    parking_slots: int,
) -> Tuple[int, int, int]:
    # BR-01: Compute agreement value excluding parking, parking charge, and total
    base = Decimal(str(carpet_sqft)) * Decimal(str(base_rate))
    extra_floors = max(0, floor - 3)
    floor_rise = Decimal(str(extra_floors * 50)) * Decimal(str(carpet_sqft))

    plc_pct = Decimal("0")
    if park_facing:
        plc_pct += Decimal("0.05")
    if corner:
        plc_pct += Decimal("0.03")
    plc = base * plc_pct

    excl_parking = round_rupee(base + floor_rise + plc)
    parking = round_rupee(parking_slots * 300000)
    return excl_parking, parking, excl_parking + parking


def determine_gst_rate(
    carpet_sqm: float,
    agreement_value_total: int,
    demand_date: date,
    cc_date: Optional[date],
) -> float:
    # BR-04: Determine GST rate (0%, 1% affordable, or 5% standard)
    if cc_date is not None and demand_date > cc_date:
        return 0.0
    if Decimal(str(carpet_sqm)) <= Decimal("60") and agreement_value_total <= 4500000:
        return 1.0
    return 5.0


def calculate_stamp_duty_and_registration(
    agreement_value_total: int,
    carpet_sqft: float,
    circle_rate: float,
    parking_charge: int,
    is_female_first_owner: bool,
) -> Tuple[int, int]:
    # BR-07: Compute stamp duty (5% or 4% with female rebate) and registration fee (1% capped at 30,000)
    circle_val = round_rupee(Decimal(str(carpet_sqft)) * Decimal(str(circle_rate))) + parking_charge
    dutiable_value = max(agreement_value_total, circle_val)

    sd_rate = Decimal("0.04") if is_female_first_owner else Decimal("0.05")
    stamp_duty = round_rupee(Decimal(str(dutiable_value)) * sd_rate)

    raw_reg = round_rupee(Decimal(str(dutiable_value)) * Decimal("0.01"))
    registration_fee = min(30000, raw_reg)
    return stamp_duty, registration_fee


def add_months(start_date: date, months: int) -> date:
    month = start_date.month - 1 + months
    year = start_date.year + month // 12
    month = month % 12 + 1
    days_in_month = [
        31,
        29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
    ][month - 1]
    day = min(start_date.day, days_in_month)
    return date(year, month, day)


def calculate_delay_compensation(
    rera_date: date,
    force_majeure: bool,
    offer_date: date,
    total_principal_paid: int,
) -> int:
    # BR-09: 10.5% p.a. simple interest computed monthly from effective RERA date to offer date
    effective_rera = add_months(rera_date, 6) if force_majeure else rera_date
    if offer_date <= effective_rera or total_principal_paid <= 0:
        return 0

    full_months = (offer_date.year - effective_rera.year) * 12 + (offer_date.month - effective_rera.month)
    anchor = add_months(effective_rera, full_months)
    if anchor > offer_date:
        full_months -= 1
        anchor = add_months(effective_rera, full_months)

    rem_days = (offer_date - anchor).days
    total_months = Decimal(str(full_months)) + (Decimal(str(rem_days)) / Decimal("30"))

    comp = (
        Decimal(str(total_principal_paid))
        * Decimal("0.105")
        * (total_months / Decimal("12"))
    )
    return round_rupee(comp)


def get_quarter(dt: date) -> Tuple[int, int]:
    return (dt.year, (dt.month - 1) // 3 + 1)
