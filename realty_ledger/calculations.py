
import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple, Union


def nearest_rupee(val: Union[float, Decimal, int]) -> int:
    """Round a value to the nearest rupee using half-up rounding."""
    return int(
        Decimal(str(val)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP
        )
    )


def clean_pct_str(pct: float) -> str:
    """Convert percentage into a clean string."""
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

    if (
        area_sqft < 0
        or rate_sqft < 0
        or floor_no < 1
        or parking_slots < 0
    ):
        raise ValueError("Invalid unit pricing input.")

    sqft = Decimal(str(area_sqft))
    rate = Decimal(str(rate_sqft))

    # Base cost
    base_cost = sqft * rate

    # Floor rise above 3rd floor
    high_floors = max(0, floor_no - 3)
    rise_cost = Decimal(high_floors * 50) * sqft

    # Preferential Location Charges (PLC)
    plc_ratio = Decimal("0")

    if park_facing:
        plc_ratio += Decimal("0.05")

    if corner:
        plc_ratio += Decimal("0.03")

    plc_cost = base_cost * plc_ratio

    # Parking charges
    parking_cost = Decimal(parking_slots * 300000)

    excl_parking = nearest_rupee(
        base_cost + rise_cost + plc_cost
    )

    parking_int = nearest_rupee(parking_cost)

    grand_total = nearest_rupee(
        base_cost + rise_cost + plc_cost + parking_cost
    )

    return excl_parking, parking_int, grand_total


def get_applicable_gst(
    area_sqm: float,
    total_agreement_price: int,
    invoice_date: date,
    cc_date: Optional[date],
) -> float:

    if area_sqm < 0 or total_agreement_price < 0:
        raise ValueError("Invalid GST input.")

    # Zero GST after completion certificate
    if cc_date is not None and invoice_date > cc_date:
        return 0.0

    # Affordable housing
    if (
        Decimal(str(area_sqm)) <= Decimal("60")
        and total_agreement_price <= 4500000
    ):
        return 1.0

    # Standard GST
    return 5.0


def compute_stamp_and_reg(
    total_agreement_price: int,
    area_sqft: float,
    circle_rate_sqft: float,
    parking_total: int,
    is_woman_first_owner: bool,
) -> Tuple[int, int, float, int, int]:

    if (
        min(
            total_agreement_price,
            area_sqft,
            circle_rate_sqft,
            parking_total
        ) < 0
    ):
        raise ValueError("Invalid stamp duty input.")

    # Circle rate valuation
    circle_valuation = (
        nearest_rupee(
            Decimal(str(area_sqft))
            * Decimal(str(circle_rate_sqft))
        )
        + parking_total
    )

    # Use the higher of agreement value and circle valuation
    higher_val = max(
        total_agreement_price,
        circle_valuation
    )

    # Stamp duty calculation
    sd_pct = 4.0 if is_woman_first_owner else 5.0

    stamp_duty = nearest_rupee(
        Decimal(higher_val)
        * Decimal(str(sd_pct))
        / Decimal("100")
    )

    # Registration fee capped at Rs. 30,000
    reg_fee = min(
        30000,
        nearest_rupee(
            Decimal(higher_val) * Decimal("0.01")
        )
    )

    return (
        circle_valuation,
        higher_val,
        sd_pct,
        stamp_duty,
        reg_fee
    )


def shift_months(dt: date, count: int) -> date:
    """Add or subtract months while handling month-end dates."""

    m_idx = dt.month - 1 + count

    yr = dt.year + m_idx // 12
    mo = m_idx % 12 + 1

    last_day = calendar.monthrange(yr, mo)[1]

    return date(
        yr,
        mo,
        min(dt.day, last_day)
    )


def compute_rera_delay_comp(
    rera_date: date,
    force_majeure: bool,
    offer_date: date,
    paid_principal_to_date: int,
) -> int:

    if paid_principal_to_date < 0:
        raise ValueError(
            "Paid principal cannot be negative."
        )

    # Add 6-month grace period during force majeure
    deadline = (
        shift_months(rera_date, 6)
        if force_majeure
        else rera_date
    )

    if (
        offer_date <= deadline
        or paid_principal_to_date == 0
    ):
        return 0

    # Monthly interest at 10.5% annual rate
    monthly_interest = (
        Decimal(paid_principal_to_date)
        * Decimal("0.105")
        / Decimal("12")
    )

    comp_sum = 0
    step = 0
    cursor = deadline

    while True:

        next_mark = shift_months(
            deadline,
            step + 1
        )

        if next_mark <= offer_date:

            comp_sum += nearest_rupee(
                monthly_interest
            )

            step += 1
            cursor = next_mark

        else:

            extra_days = (
                offer_date - cursor
            ).days

            if extra_days > 0:

                days_in_mo = calendar.monthrange(
                    cursor.year,
                    cursor.month
                )[1]

                prorated = (
                    monthly_interest
                    * Decimal(extra_days)
                    / Decimal(days_in_mo)
                )

                comp_sum += nearest_rupee(
                    prorated
                )

            break

    return comp_sum


def year_quarter(dt: date) -> Tuple[int, int]:
    """Return year and quarter for a given date."""

    return (
        dt.year,
        (dt.month - 1) // 3 + 1
    )
