import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException

from app.models.user import User, UserRole


class FinanceAllocationTests(unittest.TestCase):
    def test_exact_payment_marks_month_paid(self):
        from app.services.finance_service import compute_fee_breakdown

        breakdown = compute_fee_breakdown(
            fee_configs=[
                SimpleNamespace(monthly_fee=Decimal("1000"), effective_from=date(2026, 1, 1), status="active")
            ],
            payments=[
                SimpleNamespace(amount_paid=Decimal("1000"), payment_date=date(2026, 1, 5))
            ],
            through_month="2026-01",
        )

        self.assertEqual(len(breakdown), 1)
        self.assertEqual(breakdown[0]["status"], "PAID")
        self.assertEqual(breakdown[0]["amount_paid"], 1000.0)

    def test_partial_payment_marks_month_partial(self):
        from app.services.finance_service import compute_fee_breakdown

        breakdown = compute_fee_breakdown(
            fee_configs=[
                SimpleNamespace(monthly_fee=Decimal("1000"), effective_from=date(2026, 1, 1), status="active")
            ],
            payments=[
                SimpleNamespace(amount_paid=Decimal("400"), payment_date=date(2026, 1, 5))
            ],
            through_month="2026-01",
        )

        self.assertEqual(breakdown[0]["status"], "PARTIAL")
        self.assertEqual(breakdown[0]["amount_due"], 1000.0)
        self.assertEqual(breakdown[0]["amount_paid"], 400.0)

    def test_no_payment_marks_month_due(self):
        from app.services.finance_service import compute_fee_breakdown

        breakdown = compute_fee_breakdown(
            fee_configs=[
                SimpleNamespace(monthly_fee=Decimal("1000"), effective_from=date(2026, 1, 1), status="active")
            ],
            payments=[],
            through_month="2026-01",
        )

        self.assertEqual(breakdown[0]["status"], "DUE")
        self.assertEqual(breakdown[0]["amount_paid"], 0.0)

    def test_overpayment_spills_into_future_as_advance(self):
        from app.services.finance_service import compute_fee_breakdown

        breakdown = compute_fee_breakdown(
            fee_configs=[
                SimpleNamespace(monthly_fee=Decimal("1000"), effective_from=date(2026, 1, 1), status="active")
            ],
            payments=[
                SimpleNamespace(amount_paid=Decimal("2500"), payment_date=date(2026, 1, 5))
            ],
            through_month="2026-02",
        )

        self.assertEqual([row["status"] for row in breakdown[:3]], ["PAID", "PAID", "ADVANCE"])
        self.assertEqual(breakdown[2]["amount_paid"], 500.0)

    def test_multiple_payments_allocate_across_months(self):
        from app.services.finance_service import compute_fee_breakdown

        breakdown = compute_fee_breakdown(
            fee_configs=[
                SimpleNamespace(monthly_fee=Decimal("1000"), effective_from=date(2026, 1, 1), status="active")
            ],
            payments=[
                SimpleNamespace(amount_paid=Decimal("600"), payment_date=date(2026, 1, 4)),
                SimpleNamespace(amount_paid=Decimal("900"), payment_date=date(2026, 2, 4)),
                SimpleNamespace(amount_paid=Decimal("700"), payment_date=date(2026, 3, 4)),
            ],
            through_month="2026-03",
        )

        self.assertEqual(
            [(row["month"], row["status"], row["amount_paid"]) for row in breakdown[:3]],
            [
                ("2026-01", "PAID", 1000.0),
                ("2026-02", "PAID", 1000.0),
                ("2026-03", "PARTIAL", 200.0),
            ],
        )


class FinanceWriteAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_teacher_cannot_add_payment(self):
        from app.routers.finance import add_payment

        teacher = User(
            id=7,
            name="Teacher",
            email="teacher@example.com",
            password_hash="x",
            role=UserRole.TEACHER,
            school_id=2,
        )

        with self.assertRaises(HTTPException) as ctx:
            await add_payment(
                db=AsyncMock(),
                payload=SimpleNamespace(
                    student_id=1,
                    amount_paid=1000.0,
                    payment_date="2026-01-10",
                    payment_mode="cash",
                    note="",
                ),
                current_user=teacher,
            )

        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
