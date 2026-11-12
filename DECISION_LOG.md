# Engineering Decision Log — Team T099

1. **Integer Rupee Representation**: Stored all monetary amounts as Python `int` values after `Decimal(..., ROUND_HALF_UP)` arithmetic to prevent floating-point drift across multi-year ledgers.
2. **Whole-Note Overdue Balance**: Computed daily simple interest on the unpaid balance of each overdue invoice and crystallized it at payment or new invoice dates so carried-forward interest is never compounded.
3. **Timestamp Precision for Same-Day Events**: Stored booking, agreement, payment, and cancellation timestamps as `datetime` objects to cleanly resolve same-day ordering (such as `BKG-012` agreement at 11:00 vs cancellation at 16:30).
4. **Month-by-Month RERA Compensation**: Stepped calendar months from the grace-adjusted RERA date to the possession offer date, rounding each full month and pro-rating remaining days by the actual days in that month.
