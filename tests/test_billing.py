import unittest
from pathlib import Path

from realty_ledger import DeveloperAccountingEngine


class TestRealtyBillingRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample_dir = Path(__file__).resolve().parents[1] / "sample_data"
        cls.engine = DeveloperAccountingEngine()
        cls.engine.load_csv_inputs(str(cls.sample_dir))
        with open(cls.sample_dir / "commands.txt", encoding="utf-8") as fh:
            for line in fh:
                cls.engine.run_command(line)

    def test_affordable_unit_exact_limits(self):
        b = self.engine.active_bookings["BKG-027"]
        self.assertEqual(b.total_agreement_price, 4500000)
        self.assertEqual(b.invoices[0].gst_pct, 1.0)

    def test_payment_on_due_date_late_night(self):
        b = self.engine.active_bookings["BKG-003"]
        ev = next(e for e in b.events if e.ref_code == "PAY-0027")
        self.assertEqual(ev.int_part, 0)

    def test_allocation_priority_order(self):
        b = self.engine.active_bookings["BKG-004"]
        ev17 = next(e for e in b.events if e.ref_code == "PAY-0017")
        ev20 = next(e for e in b.events if e.ref_code == "PAY-0020")
        self.assertGreater(ev17.int_part, 0)
        self.assertGreater(ev17.prin_part, 0)
        self.assertGreater(ev20.gst_part, 36000)
        self.assertEqual(ev20.net_outstanding, 0)

    def test_stamp_duty_when_circle_matches_agreement(self):
        da = next(d for d in self.engine.duty_assessments if d.booking_id == "BKG-024")
        self.assertEqual(da.agreement_val, 11627500)
        self.assertEqual(da.circle_val, 11627500)
        self.assertEqual(da.stamp_duty_amt, 581375)
        self.assertEqual(da.reg_fee_amt, 30000)

    def test_same_day_agreement_cancellation(self):
        b = self.engine.active_bookings["BKG-012"]
        self.assertEqual(b.booking_status, "CANCELLED")
        self.assertEqual(b.forfeited_amt, round(b.total_agreement_price * 0.10))

    def test_handover_on_rera_date_with_grace(self):
        b1 = self.engine.active_bookings["BKG-003"]
        b2 = self.engine.active_bookings["BKG-009"]
        self.assertEqual(b1.rera_compensation, 0)
        self.assertGreater(b2.rera_compensation, 0)

    def test_post_cc_booking_zero_gst(self):
        b = self.engine.active_bookings["BKG-035"]
        self.assertEqual(b.invoices[0].gst_pct, 0.0)
        self.assertEqual(b.invoices[0].gst_amount, 0)

    def test_termination_notice_cured_on_day_30(self):
        b = self.engine.active_bookings["BKG-001"]
        self.assertTrue(b.notice_revoked)
        self.assertNotEqual(b.booking_status, "CANCELLED")

    def test_validation_guards(self):
        self.assertEqual(self.engine.active_bookings["BKG-013"].payment_plan, "CLP")
        self.assertEqual(self.engine.active_bookings["BKG-002"].booking_status, "CANCELLED")
        b11 = self.engine.active_bookings["BKG-011"]
        self.assertEqual(b11.booking_status, "CANCELLED")
        self.assertEqual(b11.forfeited_amt, min(round(b11.total_agreement_price * 0.02), b11.cumulative_paid))


if __name__ == "__main__":
    unittest.main()
