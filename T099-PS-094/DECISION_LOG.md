# Decision Log — Team T099 (PS-094)

1. **Integer Rupee Arithmetic with `Decimal` Rounding (`ROUND_HALF_UP`)**:
   - *Decision*: Use Python's `decimal.Decimal` with `ROUND_HALF_UP` for all percentage multiplications and interest calculations, storing final line items as `int`.
   - *Rationale*: Standard floating-point arithmetic (`float`) introduces 1-rupee rounding discrepancies on boundary cases like `45,00,000` or `60.0` sq m.

2. **Quarter Boundary Rule for GST Refund on Cancellation (BR-08)**:
   - *Decision*: Map months `1-3 -> Q1`, `4-6 -> Q2`, `7-9 -> Q3`, `10-12 -> Q4` within the same calendar year `(year, quarter)`. If a demand was raised in `(cancel_date.year, cancel_quarter)`, the GST collected on that demand is treated as not yet deposited and refunded to the customer.

3. **Monthly Interest Calculation for RERA Delay Compensation (BR-09)**:
   - *Decision*: Compute complete and fractional months between `effective_rera_date` and `offer_date` using exact calendar month difference plus remaining days divided by 30, applying `amount_paid * 0.105 * (months / 12)`. When `offer_date <= effective_rera_date` (including on the exact date), compensation is `0`.

4. **Accrued Interest Crystallization (BR-05)**:
   - *Decision*: Interest on overdue demand principal is computed up to the payment date (when a payment arrives) or up to the new demand date (when a new demand note is raised, carrying forward any unbilled overdue interest onto the new demand note).
