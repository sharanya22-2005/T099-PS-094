# System Design Document — PS-094 (Team T099)

## Module Breakdown
- `realty_ledger/domain.py`: Core data structures (`PropertyProject`, `TowerBlock`, `FlatUnit`, `BuyerProfile`, `UnitBooking`, `BillingInvoice`, `InvoiceItem`, `AccountEvent`, `DutyAssessment`) storing currency in whole rupees.
- `realty_ledger/calculations.py`: Pure calculation routines for unit pricing, floor rise, PLC, GST tier checks, stamp duty/registration caps, and monthly/pro-rata RERA delay compensation.
- `realty_ledger/accounting.py`: `DeveloperAccountingEngine` managing CSV ingestion, milestone certification sequence checks, invoice generation, interest crystallization, payment allocation precedence, termination notices, and cancellations.
- `realty_ledger/exporters.py`: `StatementExporter` generating formatted console registers/ledgers and the four CSV files (`demand_register.csv`, `customer_ledger.csv`, `stamp_duty.csv`, `final_statements.csv`).

## Business Rules Mapping (BR-01 to BR-12)
- **BR-01 (Agreement Value)**: `base + floor_rise (Rs 50/sqft above 3rd floor) + PLC (5% park, 3% corner) + parking (Rs 3,00,000/slot)` summed and rounded half-up once.
- **BR-02 (CLP Schedule)**: Milestone percentages applied to agreement value excluding parking; catch-up lines included if milestones were certified prior to booking; parking billed at possession.
- **BR-03 (Down-Payment Plan & Plan Switch)**: 8% discount on base agreement value (excl. parking); 95% due in 30 days, balance 5% + parking at possession; plan changes rejected once the agreement milestone is reached.
- **BR-04 (GST Rules)**: 1% for affordable units (`<= 60 sq m` and `<= Rs 45,00,000`), 5% standard, 0% on demands dated after the completion certificate date; no GST on stamp duty, registration, or interest lines.
- **BR-05 (Due Dates & Interest)**: 15-day due window (30 days for 95% DPP); 12% p.a. daily simple interest after due date; payments dated on the due date incur zero interest; unpaid accrued interest carries forward onto the next invoice.
- **BR-06 (Payment Precedence)**: Applied strictly to crystallized interest first, then oldest invoice principal, then that invoice's GST, before moving to newer invoices; surplus stays in `excess_advance`.
- **BR-07 (Stamp Duty & Registration)**: 5% of `max(agreement_value, circle_value)` with a 1% rebate (`4%`) if the primary owner is female; registration fee at 1% capped at Rs 30,000.
- **BR-08 (Cancellation & Forfeiture)**: Pre-agreement forfeits `min(2% of agreement_value, total_paid)`; at/after agreement forfeits `10% of agreement_value`; GST paid in the same calendar quarter as cancellation is refunded.
- **BR-09 (RERA Delay Compensation)**: 10.5% p.a. simple interest per whole month plus pro-rata days in the final partial month after the RERA date (+ 6 months if force majeure applies), credited against the possession invoice.
- **BR-10 (90-Day Default & Termination)**: Notice permitted once an invoice is > 90 days overdue; full clearance within 30 days revokes the notice; otherwise `ENFORCE_TERMINATION` cancels under post-agreement rules.
- **BR-11 (Milestone Sequencing)**: Tower-wing certifications must follow strict sequence without duplicates.
- **BR-12 (Line Rounding)**: Half-up integer rupee rounding across all line items and interest accruals.
