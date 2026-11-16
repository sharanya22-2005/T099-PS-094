import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple


def nearest_rupee(val: float | Decimal | int) -> int:
    # Standard half-up rounding to whole rupees
    return int(Decimal(str(val)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def clean_pct_str(pct: float) -> str:
    if float(pct).is_integer():
        return str(int(pct))
    return f"{pct:.2f}".rstrip("0").rstrip(".")


def compute_unit_pricing(
    area_sqft: float,
    rate_sqft: float,
    floor_no: int,
    park_facing: bool,
    corner: bool,
    parking_slots: int,
) -> Tuple[int, int, int]:
    # Base cost + floor rise above 3rd floor + cumulative PLC + parking
    sqft = Decimal(str(area_sqft))
    rate = Decimal(str(rate_sqft))
    base_cost = sqft * rate

    high_floors = max(0, floor_no - 3)
    rise_cost = Decimal(str(high_floors * 50)) * sqft

    plc_ratio = Decimal("0")
    if park_facing:
        plc_ratio += Decimal("0.05")
    if corner:
        plc_ratio += Decimal("0.03")
    plc_cost = base_cost * plc_ratio

    parking_cost = Decimal(str(parking_slots * 300000))

    excl_parking = nearest_rupee(base_cost + rise_cost + plc_cost)
    parking_int = nearest_rupee(parking_cost)
    grand_total = nearest_rupee(base_cost + rise_cost + plc_cost + parking_cost)
    return excl_parking, parking_int, grand_total


def get_applicable_gst(
    area_sqm: float,
    total_agreement_price: int,
    invoice_date: date,
    cc_date: Optional[date],
) -> float:
    # Zero GST after completion certificate; 1% for affordable units; 5% otherwise
    if cc_date is not None and invoice_date > cc_date:
        return 0.0
    if Decimal(str(area_sqm)) <= Decimal("60") and total_agreement_price <= 4500000:
        return 1.0
    return 5.0


def compute_stamp_and_reg(
    total_agreement_price: int,
    area_sqft: float,
    circle_rate_sqft: float,
    parking_total: int,
    is_woman_first_owner: bool,
) -> Tuple[int, int, float, int, int]:
    circle_valuation = nearest_rupee(Decimal(str(area_sqft)) * Decimal(str(circle_rate_sqft))) + parking_total
    higher_val = max(total_agreement_price, circle_valuation)

    # 1% stamp duty rebate when the primary registered buyer is a woman
    sd_pct = 4.0 if is_woman_first_owner else 5.0
    stamp_duty = nearest_rupee(Decimal(str(higher_val)) * Decimal(str(sd_pct)) / Decimal("100"))
    reg_fee = min(30000, nearest_rupee(Decimal(str(higher_val)) * Decimal("0.01")))
    return circle_valuation, higher_val, sd_pct, stamp_duty, reg_fee


def shift_months(dt: date, count: int) -> date:
    m_idx = dt.month - 1 + count
    yr = dt.year + m_idx // 12
    mo = m_idx % 12 + 1
    last_day = calendar.monthrange(yr, mo)[1]
    return date(yr, mo, min(dt.day, last_day))


def compute_rera_delay_comp(
    rera_date: date,
    force_majeure: bool,
    offer_date: date,
    paid_principal_to_date: int,
) -> int:
    # Add 6-month grace period only when force majeure is active
    deadline = shift_months(rera_date, 6) if force_majeure else rera_date
    if offer_date <= deadline or paid_principal_to_date <= 0:
        return 0

    monthly_interest = Decimal(str(paid_principal_to_date)) * Decimal("0.105") / Decimal("12")
    comp_sum = 0
    step = 0
    cursor = deadline

    while True:
        next_mark = shift_months(deadline, step + 1)
        if next_mark <= offer_date:
            comp_sum += nearest_rupee(monthly_interest)
            step += 1
            cursor = next_mark
        else:
            extra_days = (offer_date - cursor).days
            if extra_days > 0:
                days_in_mo = calendar.monthrange(cursor.year, cursor.month)[1]
                prorated = monthly_interest * Decimal(str(extra_days)) / Decimal(str(days_in_mo))
                comp_sum += nearest_rupee(prorated)
            break

    return comp_sum


def year_quarter(dt: date) -> Tuple[int, int]:
    return (dt.year, (dt.month - 1) // 3 + 1)
