from .engine import BillingEngine


class Reporter:
    @staticmethod
    def format_demand_register(engine: BillingEngine) -> str:
        lines = [
            "=" * 108,
            "DEMAND REGISTER",
            "=" * 108,
            f"{'Demand ID':<10} {'Booking':<10} {'Milestone':<12} {'Date':<12} {'Due Date':<12} "
            f"{'Principal':>11} {'GST':>9} {'Int Billed':>11} {'Total':>12}",
            "-" * 108,
        ]
        for d in engine.all_demands:
            lines.append(
                f"{d.demand_id:<10} {d.booking_id:<10} {d.milestone_code:<12} "
                f"{d.demand_date.isoformat():<12} {d.due_date.isoformat():<12} "
                f"{d.principal_amount:>11,d} {d.gst_amount:>9,d} {d.interest_billed:>11,d} {d.total_billed:>12,d}"
            )
        lines.append("=" * 108)
        return "\n".join(lines)

    @staticmethod
    def format_customer_ledger(engine: BillingEngine, booking_id: str) -> str:
        b = engine.bookings[booking_id.strip()]
        c = engine.customers[b.customer_id]
        u = engine.units[b.unit_id]

        lines = [
            "=" * 104,
            f"CUSTOMER LEDGER | Booking: {b.booking_id} | Customer: {c.name} ({c.customer_id}) | Unit: {u.unit_id}",
            f"Plan: {b.plan} | Status: {b.status} | Agreement Value: Rs {b.effective_total_value:,d} | GST Rate: {b.gst_rate:.1f}%",
            f"Stamp Duty: Rs {b.stamp_duty:,d} | Registration Fee: Rs {b.registration_fee:,d}",
            "=" * 104,
            f"{'Date':<12} {'Ref ID':<16} {'Particulars':<44} {'Debit':>10} {'Credit':>10} {'Balance':>10}",
            "-" * 104,
        ]
        for entry in b.ledger:
            lines.append(
                f"{entry.entry_date.isoformat():<12} {entry.ref_id:<16} {entry.particulars[:44]:<44} "
                f"{entry.debit:>10,d} {entry.credit:>10,d} {entry.balance:>10,d}"
            )
        lines.append("-" * 104)
        lines.append(f"Unallocated Advance Balance: Rs {b.advance_balance:,d}")
        lines.append("=" * 104)
        return "\n".join(lines)

    @staticmethod
    def format_final_statement(engine: BillingEngine, booking_id: str) -> str:
        b = engine.bookings[booking_id.strip()]
        c = engine.customers[b.customer_id]
        u = engine.units[b.unit_id]

        total_prin_billed = sum(d.principal_amount for d in b.demands)
        total_gst_billed = sum(d.gst_amount for d in b.demands)
        total_int_billed = sum(d.interest_billed for d in b.demands)
        total_cash_paid = sum(p.amount for p in b.payments)

        lines = [
            "=" * 84,
            f"FINAL STATEMENT ({b.status}) — Booking {b.booking_id}",
            "=" * 84,
            f"Customer            : {c.name} ({c.customer_id}) | Female 1st Owner: {c.is_female_first_owner}",
            f"Unit                : {u.unit_id} (Tower {u.tower_id}, Floor {u.floor}, {u.carpet_sqft} sq ft)",
            f"Payment Plan        : {b.plan}",
            f"Base Agreement Val  : Rs {b.agreement_value_excl_parking:,d}",
            f"Parking Charges     : Rs {b.parking_charge:,d}",
            f"Effective Total Val : Rs {b.effective_total_value:,d}",
            f"Stamp Duty Payable  : Rs {b.stamp_duty:,d}",
            f"Registration Fee    : Rs {b.registration_fee:,d}",
            "-" * 84,
            f"Total Principal Billed : Rs {total_prin_billed:,d}",
            f"Total GST Billed       : Rs {total_gst_billed:,d}",
            f"Total Interest Billed  : Rs {total_int_billed:,d}",
            f"Total Cash Paid        : Rs {total_cash_paid:,d}",
        ]

        if b.status == "CANCELLED":
            lines.extend([
                "-" * 84,
                f"Cancellation Date      : {b.cancellation_date.isoformat()}",
                f"Forfeiture Amount      : Rs {b.forfeiture_amount:,d}",
                f"GST Refunded (Same Qtr): Rs {b.gst_refunded:,d}",
                f"Net Refund Payable     : Rs {b.refund_payable:,d}",
                f"Refund Due By (45d)    : {b.refund_due_date.isoformat()} (12% p.a. interest thereafter)",
            ])
        else:
            net_due = (
                sum(d.principal_due + d.gst_due + (d.interest_billed - d.interest_paid) + d.unbilled_interest for d in b.demands)
                - b.advance_balance
            )
            lines.extend([
                "-" * 84,
                f"Possession Offer Date  : {b.possession_offer_date.isoformat() if b.possession_offer_date else 'PENDING'}",
                f"RERA Delay Compensation: Rs {b.delay_compensation:,d}",
                f"Net Balance Payable    : Rs {max(0, net_due):,d}",
            ])

        lines.append("=" * 84)
        return "\n".join(lines)
