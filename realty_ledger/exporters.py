import csv
from pathlib import Path

from .accounting import DeveloperAccountingEngine
from .calculations import clean_pct_str


class StatementExporter:
    @staticmethod
    def write_all_csvs(engine: DeveloperAccountingEngine, output_folder: str):
        dest = Path(output_folder)
        dest.mkdir(parents=True, exist_ok=True)

        # 1. demand_register.csv
        with open(dest / "demand_register.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "demand_no",
                "booking_id",
                "demand_date",
                "due_date",
                "line_type",
                "milestone_code",
                "amount",
                "gst_rate_pct",
                "note_gst",
                "note_total",
            ])
            for inv in engine.issued_invoices:
                for item in inv.items:
                    writer.writerow([
                        inv.demand_no,
                        inv.booking_id,
                        inv.issued_date.isoformat(),
                        inv.due_date.isoformat(),
                        item.item_type,
                        item.stage_code,
                        f"{item.amount:.2f}",
                        clean_pct_str(inv.gst_pct) if item.is_taxable else "0",
                        f"{inv.gst_amount:.2f}",
                        f"{inv.total_payable:.2f}",
                    ])

        # 2. customer_ledger.csv
        with open(dest / "customer_ledger.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "booking_id",
                "event_ts",
                "event",
                "reference",
                "debit",
                "credit",
                "interest_component",
                "principal_component",
                "gst_component",
                "advance_balance",
                "outstanding",
            ])
            for b_id in sorted(engine.active_bookings.keys()):
                booking = engine.active_bookings[b_id]
                for ev in booking.events:
                    writer.writerow([
                        ev.booking_id,
                        ev.timestamp_str,
                        ev.event_type,
                        ev.ref_code,
                        f"{ev.debit_amt:.2f}",
                        f"{ev.credit_amt:.2f}",
                        f"{ev.int_part:.2f}",
                        f"{ev.prin_part:.2f}",
                        f"{ev.gst_part:.2f}",
                        f"{ev.wallet_advance:.2f}",
                        f"{ev.net_outstanding:.2f}",
                    ])

        # 3. stamp_duty.csv
        with open(dest / "stamp_duty.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "booking_id",
                "agreement_value",
                "circle_value",
                "duty_base",
                "duty_rate_pct",
                "stamp_duty",
                "registration_fee",
            ])
            for da in sorted(engine.duty_assessments, key=lambda x: x.booking_id):
                writer.writerow([
                    da.booking_id,
                    f"{da.agreement_val:.2f}",
                    f"{da.circle_val:.2f}",
                    f"{da.assessed_base:.2f}",
                    clean_pct_str(da.duty_pct),
                    f"{da.stamp_duty_amt:.2f}",
                    f"{da.reg_fee_amt:.2f}",
                ])

        # 4. final_statements.csv
        with open(dest / "final_statements.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "booking_id",
                "status",
                "agreement_value",
                "total_demanded",
                "total_paid",
                "interest_charged",
                "forfeiture",
                "gst_refund",
                "refund_due",
                "delay_compensation",
                "possession_balance",
            ])
            for b_id in sorted(engine.active_bookings.keys()):
                b = engine.active_bookings[b_id]
                pos_due = 0 if b.booking_status == "CANCELLED" else engine.get_net_balance(b)
                writer.writerow([
                    b.booking_id,
                    b.booking_status,
                    f"{b.total_agreement_price:.2f}",
                    f"{b.cumulative_billed:.2f}",
                    f"{b.cumulative_paid:.2f}",
                    f"{b.cumulative_interest:.2f}",
                    f"{b.forfeited_amt:.2f}",
                    f"{b.refunded_gst:.2f}",
                    f"{b.net_refund_due:.2f}",
                    f"{b.rera_compensation:.2f}",
                    f"{pos_due:.2f}",
                ])

    @staticmethod
    def render_demand_register(engine: DeveloperAccountingEngine) -> str:
        rows = [
            "=" * 116,
            "DEMAND REGISTER",
            "=" * 116,
            f"{'Demand No':<10} {'Booking':<9} {'Date':<11} {'Due Date':<11} {'Line Type':<18} "
            f"{'Milestone':<11} {'Amount':>11} {'GST%':>5} {'Note GST':>10} {'Note Total':>12}",
            "-" * 116,
        ]
        for inv in engine.issued_invoices:
            for item in inv.items:
                rows.append(
                    f"{inv.demand_no:<10} {inv.booking_id:<9} {inv.issued_date.isoformat():<11} "
                    f"{inv.due_date.isoformat():<11} {item.item_type:<18} {item.stage_code:<11} "
                    f"{item.amount:>11,d} {clean_pct_str(inv.gst_pct) if item.is_taxable else '0':>5} "
                    f"{inv.gst_amount:>10,d} {inv.total_payable:>12,d}"
                )
        rows.append("=" * 116)
        return "\n".join(rows)

    @staticmethod
    def render_customer_ledger(engine: DeveloperAccountingEngine, booking_id: str) -> str:
        b = engine.active_bookings[booking_id.strip()]
        buyer = engine.buyers[b.customer_id]
        rows = [
            "=" * 124,
            f"CUSTOMER LEDGER | {b.booking_id} | {buyer.full_name} ({buyer.customer_id}) | Unit: {b.unit_id} | Plan: {b.payment_plan} | Status: {b.booking_status}",
            "=" * 124,
            f"{'Timestamp':<20} {'Event':<8} {'Reference':<14} {'Debit':>11} {'Credit':>11} "
            f"{'Int':>9} {'Prin':>11} {'GST':>10} {'Advance':>10} {'Outstanding':>12}",
            "-" * 124,
        ]
        for ev in b.events:
            rows.append(
                f"{ev.timestamp_str:<20} {ev.event_type:<8} {ev.ref_code:<14} {ev.debit_amt:>11,d} {ev.credit_amt:>11,d} "
                f"{ev.int_part:>9,d} {ev.prin_part:>11,d} {ev.gst_part:>10,d} "
                f"{ev.wallet_advance:>10,d} {ev.net_outstanding:>12,d}"
            )
        rows.append("=" * 124)
        return "\n".join(rows)

    @staticmethod
    def render_final_statement(engine: DeveloperAccountingEngine, booking_id: str) -> str:
        b = engine.active_bookings[booking_id.strip()]
        buyer = engine.buyers[b.customer_id]
        pos_due = 0 if b.booking_status == "CANCELLED" else engine.get_net_balance(b)
        rows = [
            "=" * 76,
            f"FINAL STATEMENT — {b.booking_id} ({b.booking_status})",
            "=" * 76,
            f"Customer             : {buyer.full_name} ({buyer.customer_id})",
            f"Unit / Plan          : {b.unit_id} / {b.payment_plan}",
            f"Agreement Value      : Rs {b.total_agreement_price:,d}",
            f"Total Demanded       : Rs {b.cumulative_billed:,d}",
            f"Total Paid           : Rs {b.cumulative_paid:,d}",
            f"Interest Charged     : Rs {b.cumulative_interest:,d}",
            f"Forfeiture           : Rs {b.forfeited_amt:,d}",
            f"GST Refund           : Rs {b.refunded_gst:,d}",
            f"Refund Due           : Rs {b.net_refund_due:,d}",
            f"Delay Compensation   : Rs {b.rera_compensation:,d}",
            f"Possession Balance   : Rs {pos_due:,d}",
            "=" * 76,
        ]
        return "\n".join(rows)
