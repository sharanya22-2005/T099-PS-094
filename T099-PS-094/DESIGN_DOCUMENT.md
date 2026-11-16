# Design Document — PS-094 Billing Engine (Team T099)

## 1. Architecture Overview
The engine is structured into four decoupled modules inside `src/billing_engine/`:
1. **`models.py`**: Pure dataclasses representing core domain entities (`Project`, `Unit`, `Customer`, `Booking`, `DemandNote`, `Payment`, `LedgerEntry`). All monetary values are stored as integer Rupees (`int`) to avoid floating-point drift.
2. **`rules.py`**: Stateless pure functions implementing statutory and contractual calculations (`round_rupee`, `calculate_agreement_value`, `determine_gst_rate`, `calculate_stamp_duty_and_registration`, `calculate_delay_compensation`).
3. **`engine.py`**: Stateful orchestration engine (`BillingEngine`) managing registries, enforcing sequential milestone validation, maintaining running demand balances, applying payment precedence, tracking termination notices, and executing cancellations.
4. **`reporter.py`**: Deterministic formatting for Demand Registers, Customer Ledgers, Stamp Duty summaries, and Final Statements at Possession or Cancellation.

---

## 2. Business Rules Registry

| Rule ID | Title | Implementation & Formula |
| :--- | :--- | :--- |
| **BR-01** | Agreement Value Computation | `base = carpet_sqft * base_rate`; `floor_rise = max(0, floor - 3) * 50 * carpet_sqft`; `plc = base * (0.05 if park_facing else 0) + base * (0.03 if corner else 0)`; `parking = slots * 300000`. Rounded to nearest rupee (`Decimal` `ROUND_HALF_UP`). |
| **BR-02** | CLP Milestone Schedule | Default schedule: Booking (10%), Agreement (10%), Plinth (10%), Slab 1–5 (8% each = 40%), Brickwork (10%), Finishing (10%), Possession (10%). Percentages apply to `agreement_value_excl_parking`. Full `parking_charge` is added to the Possession demand. |
| **BR-03** | Down-Payment Plan (DPP) & Switching | 8% discount applied on `agreement_value_excl_parking`. Schedule: 95% due within 30 days of booking, 5% + full parking at Possession. Switching plans after the Agreement milestone is certified/demanded is strictly rejected. |
| **BR-04** | GST Applicability & Rate | 5% standard on under-construction demands; 1% for affordable units (`carpet_sqm <= 60` AND `agreement_value <= 45,00,000`); 0% if `demand_date > completion_certificate_date`. Parking GST matches the unit's applicable GST rate. |
| **BR-05** | Due Dates & Delayed Interest | Due date = `demand_date + 15 days`. Simple interest at 12% p.a. (`principal_overdue * 0.12 * days_overdue / 365`) accrues daily after due date. Payment received on the due date up to `23:59` incurs 0 interest. Accrued interest is billed on the next demand note (not compounded). |
| **BR-06** | Payment Allocation Precedence | Incoming payments + existing unallocated advance are applied strictly in order: (1) Accrued overdue interest, (2) Oldest unpaid demand principal, (3) GST of that same demand, (4) Subsequent demands chronologically. Remaining surplus stays as `advance_balance`. |
| **BR-07** | Stamp Duty & Registration | Stamp duty = `5%` of `max(agreement_value_incl_parking, circle_rate * carpet_sqft + parking)`. 1% rebate (`4%` net) if `is_female_first_owner` is True. Registration fee = `min(30,000, round(1% of dutiable_value))`. Payable at Agreement. |
| **BR-08** | Cancellation & Forfeiture | Before Agreement milestone: forfeit `min(2% of agreement_value, total_paid)`. On or after Agreement milestone: forfeit `10% of agreement_value`. GST paid is refunded only if cancellation occurs within the same calendar quarter as the demand; otherwise forfeited/deposited. Refund due within 45 days (12% p.a. developer interest thereafter). |
| **BR-09** | RERA Delay Compensation | Effective RERA date = `rera_date + 6 months` if `force_majeure` flag is True, else `rera_date`. If `offer_date > effective_rera_date`, developer pays 10.5% p.a. simple interest monthly on total principal paid to date, netted directly against the Possession demand. |
| **BR-10** | 90-Day Default & Termination Notice | Any demand overdue > 90 days allows `ISSUE_TERMINATION`. Paying full dues + accrued interest within 30 days (`<= 30 days`) withdraws the notice; failure triggers automatic cancellation under the post-agreement forfeiture rule. |
| **BR-11** | Milestone Sequencing | Milestones in a tower must be certified in strict defined sequence. Raising a demand for an uncertified milestone is rejected. |
| **BR-12** | Line-Level Rounding | All line items (`principal`, `gst`, `interest`, `stamp_duty`, `compensation`) are rounded to the nearest integer Rupee (`ROUND_HALF_UP`). GST is calculated per demand note total, not per sub-component line. |
