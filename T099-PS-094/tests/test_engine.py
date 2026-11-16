import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from billing_engine import BillingEngine


class TestBillingEngineEdgeCases(unittest.TestCase):
    def setUp(self):
        self.engine = BillingEngine()
        self.engine.register_project("P1", "Test Residency", "2026-06-30", "2026-10-01", "TRUE", "6000")
        self.engine.add_tower("P1", "T1")

    def test_edge_case_1_affordable_exact_boundary(self):
        self.engine.register_unit("U-AFF", "P1", "T1", "1", "700", "60.0", "6000", "FALSE", "FALSE", "1")
        self.engine.register_customer("C1", "Meera", "TRUE")
        self.engine.book_unit("B1", "U-AFF", "C1", "CLP", "2025-01-10", "0")
        b = self.engine.bookings["B1"]
        self.assertEqual(b.agreement_value_total, 4500000)
        self.assertEqual(b.gst_rate, 1.0)
        self.assertEqual(b.demands[0].gst_amount, 4200)

    def test_edge_case_2_payment_on_due_date_2359_no_interest(self):
        self.engine.register_unit("U1", "P1", "T1", "1", "1000", "92.9", "6000", "FALSE", "FALSE", "0")
        self.engine.register_customer("C1", "Arjun", "FALSE")
        self.engine.book_unit("B1", "U1", "C1", "CLP", "2025-01-01", "0")
        self.engine.record_payment("PAY1", "B1", "2025-01-16", "630000", "23:59")
        b = self.engine.bookings["B1"]
        self.assertEqual(b.payments[0].allocated_interest, 0)
        self.assertEqual(b.demands[0].principal_due, 0)
        self.assertEqual(b.demands[0].gst_due, 0)

    def test_edge_case_3_allocation_clears_interest_and_principal_not_gst(self):
        self.engine.register_unit("U1", "P1", "T1", "1", "1000", "92.9", "6000", "FALSE", "FALSE", "0")
        self.engine.register_customer("C1", "Arjun", "FALSE")
        self.engine.book_unit("B1", "U1", "C1", "CLP", "2025-01-01", "0")
        self.engine.record_payment("PAY1", "B1", "2025-02-15", "605918", "14:00")
        b = self.engine.bookings["B1"]
        self.assertEqual(b.payments[0].allocated_interest, 5918)
        self.assertEqual(b.payments[0].allocated_principal, 600000)
        self.assertEqual(b.payments[0].allocated_gst, 0)
        self.assertEqual(b.demands[0].gst_due, 30000)

    def test_edge_case_4_circle_rate_equal_agreement_value(self):
        self.engine.register_unit("U1", "P1", "T1", "1", "1000", "92.9", "6000", "FALSE", "FALSE", "1")
        self.engine.register_customer("C1", "Kavya", "TRUE")
        self.engine.book_unit("B1", "U1", "C1", "CLP", "2025-01-01", "0")
        b = self.engine.bookings["B1"]
        self.assertEqual(b.stamp_duty, 252000)
        self.assertEqual(b.registration_fee, 30000)

    def test_edge_case_5_cancellation_on_agreement_date(self):
        self.engine.register_unit("U1", "P1", "T1", "1", "1000", "92.9", "6000", "FALSE", "FALSE", "0")
        self.engine.register_customer("C1", "Dev", "FALSE")
        self.engine.book_unit("B1", "U1", "C1", "CLP", "2025-01-01", "1000000")
        self.engine.certify_milestone("P1", "T1", "BOOKING", "2025-01-01")
        self.engine.certify_milestone("P1", "T1", "AGREEMENT", "2025-02-10")
        self.engine.raise_demand("B1", "AGREEMENT", "2025-02-10")
        self.engine.cancel_booking("B1", "2025-02-10")
        b = self.engine.bookings["B1"]
        self.assertEqual(b.forfeiture_amount, 600000)

    def test_edge_case_6_possession_on_rera_date_with_force_majeure(self):
        self.engine.register_unit("U1", "P1", "T1", "1", "1000", "92.9", "6000", "FALSE", "FALSE", "0")
        self.engine.register_customer("C1", "Dev", "FALSE")
        self.engine.book_unit("B1", "U1", "C1", "CLP", "2025-01-01", "630000")
        self.engine.offer_possession("B1", "2026-06-30")
        self.assertEqual(self.engine.bookings["B1"].delay_compensation, 0)

    def test_edge_case_7_demand_one_day_after_cc_date_zero_gst(self):
        self.engine.register_unit("U1", "P1", "T1", "1", "1000", "92.9", "6000", "FALSE", "FALSE", "0")
        self.engine.register_customer("C1", "Dev", "FALSE")
        self.engine.book_unit("B1", "U1", "C1", "CLP", "2025-01-01", "0")
        self.engine.certify_milestone("P1", "T1", "BOOKING", "2025-01-01")
        self.engine.certify_milestone("P1", "T1", "AGREEMENT", "2026-10-02")
        dn = self.engine.raise_demand("B1", "AGREEMENT", "2026-10-02")
        self.assertEqual(dn.gst_rate, 0.0)
        self.assertEqual(dn.gst_amount, 0)

    def test_edge_case_8_termination_withdrawn_on_day_30(self):
        self.engine.register_unit("U1", "P1", "T1", "1", "1000", "92.9", "6000", "FALSE", "FALSE", "0")
        self.engine.register_customer("C1", "Dev", "FALSE")
        self.engine.book_unit("B1", "U1", "C1", "CLP", "2025-01-01", "0")
        issued = self.engine.issue_termination("B1", "2025-05-01")
        self.assertTrue(issued)
        self.engine.record_payment("PAY-CLEAR", "B1", "2025-05-31", str(600000 + 30000 + 26630), "18:00")
        b = self.engine.bookings["B1"]
        self.assertTrue(b.termination_withdrawn)
        self.assertEqual(b.status, "ACTIVE")


if __name__ == "__main__":
    unittest.main()
