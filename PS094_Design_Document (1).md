# PS-094 — Construction-Linked Customer Accounting Engine
## Design Document

### 1. Purpose
Build a command-file-driven Python application used by a residential developer to register projects, towers, units and customers; book units; certify construction milestones; raise demand notes; calculate taxes and fees; allocate receipts; calculate interest and compensation; process cancellations; and print accounting reports. There is no graphical UI.

### 2. Proposed architecture
- `engine.py`: command parser, validations, business workflows and reports.
- `ps094_data.json`: persistent prototype data.
- `commands.txt`: line-oriented command file.
- Use Python `Decimal` for money calculations. Round monetary lines to the nearest rupee using half-up rounding.
- Every command reports success or a readable validation error. Invalid commands must not silently mutate data.

### 3. Data model
- Project: project ID, name, RERA possession date, completion-certificate date (optional), force-majeure flag, towers, ordered milestone definitions.
- Tower: tower ID and ordered milestone certification states.
- Customer: customer ID, name, first-owner-is-woman flag.
- Unit: unit ID, project/tower, carpet area (sq ft), base rate, floor number, PLC flags, parking slots, circle rate per sq ft, customer/booking details, plan, agreement date, status.
- Booking/account: booking amount, agreement value, eligible discounted value, demands, receipts, advance balance, interest ledger, cancellation/termination data, possession offer date, compensation.
- Demand note: ID, milestone/charge, demand date, due date, base, GST, paid principal, paid GST, outstanding interest allocation and status.
- Receipt: ID, date, amount, allocation breakdown and unapplied advance.
- Ledger entry: date, reference, debit/credit, description, balance.

### 4. Business rules
- **BR-01 — Agreement value:** Base = carpet area × base rate. Add floor rise of ₹50 per sq ft for every floor above the 3rd; add park-facing PLC of 5% of base and corner PLC of 3% of base cumulatively; add ₹3,00,000 per parking slot. Round the agreement value to the nearest rupee.
- **BR-02 — CLP plan:** Booking 10%, agreement 10%, plinth 10%, each of five slabs 8%, brickwork 10%, finishing 10%, possession 10%. Percentages apply to agreement value excluding parking. Parking is demanded fully at possession.
- **BR-03 — Down-payment plan:** 8% discount applies to agreement value excluding parking. 95% of discounted eligible value is due within 30 days of booking; 5% at possession. Parking remains a separate possession charge.
- **BR-04 — Plan switching:** Switching plans after the agreement milestone is rejected.
- **BR-05 — GST:** GST is 1% only if carpet area ≤ 60 sq m and agreement value ≤ ₹45,00,000; otherwise 5%, for under-construction demands. No GST for demands raised after the completion certificate date. Parking uses the unit's GST rate. GST is calculated per demand note, not per line item.
- **BR-06 — Due date:** Demand due date = demand date + 15 calendar days.
- **BR-07 — Customer late interest:** 12% simple interest per annum on overdue amounts, computed daily from due date. Interest is not compounded and is demanded on the next demand note.
- **BR-08 — Receipt allocation:** Allocate receipts first to outstanding interest, then oldest demand principal, then GST for that demand, then the next demand. Excess remains as customer advance and is automatically applied to the next demand.
- **BR-09 — Stamp duty and registration:** Stamp duty base is the greater of (agreement value including parking) and (circle rate per sq ft × carpet area + parking). Stamp duty rate is 5%, with a 1 percentage-point rebate for a first registered owner who is a woman. Registration fee is 1%, capped at ₹30,000. Charges are payable at agreement. (Confirm local applicability before real-world use.)
- **BR-10 — Cancellation forfeiture:** Before agreement milestone, forfeiture = lower of 2% of agreement value and amount paid. After agreement milestone, forfeiture = 10% of agreement value. Calculate refundable balance and GST refund treatment as specified by the brief.
- **BR-11 — Refund deadline:** Refund balance within 45 days. If late, calculate developer interest at 12% simple annual rate for days beyond the deadline.
- **BR-12 — Possession delay:** Compare possession offer date with RERA possession date. Add a one-time six-month grace only if the project's force-majeure flag is set. Compensation is 10.5% simple annual interest on amount paid to date, computed monthly from the RERA date to the offer date.
- **BR-13 — Compensation credit:** Apply possession-delay compensation against the possession demand.
- **BR-14 — Termination notice:** A demand overdue by more than 90 days permits a termination notice. If all dues plus interest are paid within 30 days of notice, withdraw the notice; otherwise cancel under the post-agreement forfeiture rule.
- **BR-15 — Milestone sequencing:** A tower's milestone cannot be certified before the preceding milestone. A demand for an uncertified milestone is rejected.
- **BR-16 — Rounding:** Round each monetary amount to the nearest rupee at line level; GST is computed per demand note.
- **BR-17 — Auditability:** Every receipt allocation, demand, cancellation and compensation adjustment should be recorded with a reference and date.
- **BR-18 — Validation:** Reject duplicate IDs, unknown project/tower/unit/customer IDs, invalid dates, negative values, invalid plan names, percentages outside valid ranges and duplicate milestone certification.

### 5. Suggested command syntax
Commands are one per line. Lines beginning with `#` are comments. IDs should not contain spaces; use underscores where needed.

```text
PROJECT project_id "Project Name" rera_date completion_certificate_date_or_NONE force_majeure_TRUE_or_FALSE
TOWER project_id tower_id
MILESTONE project_id milestone_id percentage
CUSTOMER customer_id "Customer Name" woman_first_owner_TRUE_or_FALSE
UNIT unit_id project_id tower_id carpet_area_sqft base_rate floor_number park_facing_TRUE_or_FALSE corner_TRUE_or_FALSE parking_slots circle_rate_per_sqft
BOOK unit_id customer_id booking_amount CLP_or_DOWNPAYMENT booking_date agreement_date_or_NONE
CERTIFY project_id tower_id milestone_id certification_date
DEMAND unit_id milestone_id_or_charge demand_date
PAY unit_id amount payment_date
SWITCH_PLAN unit_id CLP_or_DOWNPAYMENT switch_date
OFFER_POSSESSION unit_id offer_date
CANCEL unit_id cancellation_date refund_due_date
NOTICE_TERMINATION unit_id notice_date
WITHDRAW_NOTICE unit_id payment_date amount
LEDGER unit_id
DEMAND_REGISTER project_id
FINAL_STATEMENT unit_id statement_date
```

The precise parser syntax may be refined while implementing, but it should remain command-file driven and have no UI.

### 6. Reports
- Customer ledger: dated debits, credits, allocations, interest, advance and running balance.
- Demand register: demand ID, unit, milestone, demand date, due date, base, GST, paid, outstanding and status.
- Final statement at possession/cancellation: agreement value, charges, billed amounts, receipts, interest, advance, compensation, forfeiture, refunds and net balance.

### 7. Important assumptions and clarifications
1. The brief says carpet area is used for circle-rate calculation in sq ft, while the affordable-housing threshold is 60 sq m. Convert sq ft to sq m for that test (1 sq m = 10.7639 sq ft).
2. The exact scope of GST refunds depends on whether GST was deposited and on the quarter rule. Store demand date, quarter and GST-deposited status to support auditable refunds.
3. The brief does not define whether “amount paid to date” for delay compensation includes GST, stamp duty, registration or only developer receipts. Make this basis explicit in the implementation and document it.
4. Monthly compensation needs a documented month-count/day-count convention. The implementation should not silently substitute daily interest.
5. Legal/tax percentages are assignment rules; verify current jurisdiction-specific law before using the software for real transactions.


## 8. Edge-case acceptance tests

- **EC-01:** Exactly 60 sq m and exactly ₹45 lakh qualifies for the inclusive 1% affordable GST threshold.
- **EC-02:** Payment at 23:59 on the due date incurs no late interest.
- **EC-03:** Allocation that clears interest and principal but not GST leaves GST outstanding.
- **EC-04:** Equal circle-rate and agreement values use that exact common value as stamp-duty base.
- **EC-05:** Cancellation on the agreement certification date is treated as post-agreement under the date-inclusive convention.
- **EC-06:** Possession offered on the RERA date yields zero compensation even when force majeure is flagged.
- **EC-07:** A demand dated one day after the completion certificate has 0% GST.
- **EC-08:** Payment of all dues on day 30 withdraws a termination notice; day 31 does not.
