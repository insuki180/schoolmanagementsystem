import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.models.user import User, UserRole


class FeeGenerationTests(unittest.TestCase):
    def test_quarterly_fee_generation_creates_period_windows(self):
        from app.services.finance_service import build_fee_periods

        periods = build_fee_periods(
            fee_type="quarterly",
            effective_from=date(2026, 1, 1),
            through_date=date(2026, 6, 30),
        )

        self.assertEqual(
            periods,
            [
                (date(2026, 1, 1), date(2026, 3, 31)),
                (date(2026, 4, 1), date(2026, 6, 30)),
            ],
        )

    def test_payment_allocation_handles_partial_and_advance(self):
        from app.services.finance_service import allocate_payment_to_student_fees

        fees = [
            SimpleNamespace(
                id=1,
                amount_due=1000.0,
                amount_paid=200.0,
                carry_forward=0.0,
                status="PARTIAL",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
            ),
            SimpleNamespace(
                id=2,
                amount_due=1000.0,
                amount_paid=0.0,
                carry_forward=0.0,
                status="DUE",
                period_start=date(2026, 2, 1),
                period_end=date(2026, 2, 28),
            ),
        ]

        remaining = allocate_payment_to_student_fees(fees, payment_amount=2100.0)

        self.assertEqual(remaining, 300.0)
        self.assertEqual(fees[0].amount_paid, 1000.0)
        self.assertEqual(fees[0].status, "PAID")
        self.assertEqual(fees[1].amount_paid, 1000.0)
        self.assertEqual(fees[1].status, "PAID")

    def test_advance_allocation_spans_multiple_future_periods(self):
        from app.services.finance_service import allocate_advance_payment_to_periods

        current_fees = [
            SimpleNamespace(
                id=1,
                amount_due=1000.0,
                amount_paid=1000.0,
                carry_forward=0.0,
                status="PAID",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                fee_type="monthly",
            )
        ]

        created = allocate_advance_payment_to_periods(
            current_fees=current_fees,
            remaining_amount=2500.0,
            class_id=3,
            student_id=7,
            fee_amount=1000.0,
            fee_type="monthly",
        )

        self.assertEqual(len(created), 3)
        self.assertEqual([row.status for row in created], ["ADVANCE", "ADVANCE", "PARTIAL"])
        self.assertEqual([row.amount_paid for row in created], [1000.0, 1000.0, 500.0])


class ConsecutiveAbsenceTests(unittest.TestCase):
    def test_consecutive_absence_detection_requires_true_streak(self):
        from app.services.smart_alert import detect_consecutive_absence_alerts

        alerts = detect_consecutive_absence_alerts(
            [
                {
                    "student_id": 4,
                    "student_name": "Asha",
                    "class_id": 2,
                    "parent_id": 8,
                    "class_name": "Grade 5",
                    "dates": [
                        date(2026, 4, 1),
                        date(2026, 4, 2),
                        date(2026, 4, 3),
                    ],
                },
                {
                    "student_id": 5,
                    "student_name": "Rahul",
                    "class_id": 2,
                    "parent_id": 9,
                    "class_name": "Grade 5",
                    "dates": [
                        date(2026, 4, 1),
                        date(2026, 4, 3),
                        date(2026, 4, 4),
                    ],
                },
            ],
            streak_length=3,
        )

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["student_id"], 4)
        self.assertEqual(alerts[0]["streak_length"], 3)

    def test_present_day_resets_absence_streak(self):
        from app.services.smart_alert import calculate_consecutive_absence_streak

        streak_length, latest_absence_date = calculate_consecutive_absence_streak(
            [
                {"date": date(2026, 4, 1), "is_present": False},
                {"date": date(2026, 4, 2), "is_present": True},
                {"date": date(2026, 4, 3), "is_present": False},
                {"date": date(2026, 4, 4), "is_present": False},
            ]
        )

        self.assertEqual(streak_length, 2)
        self.assertEqual(latest_absence_date, date(2026, 4, 4))

    def test_holiday_between_absences_does_not_break_streak(self):
        from app.services.smart_alert import detect_consecutive_absence_alerts

        alerts = detect_consecutive_absence_alerts(
            [
                {
                    "student_id": 4,
                    "student_name": "Asha",
                    "class_id": 2,
                    "parent_id": 8,
                    "class_name": "Grade 5",
                    "dates": [
                        date(2026, 4, 1),
                        date(2026, 4, 3),
                        date(2026, 4, 4),
                    ],
                }
            ],
            streak_length=3,
            holiday_dates={date(2026, 4, 2)},
        )

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["student_id"], 4)


class NotificationDedupTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_notification_skips_when_dedup_key_exists(self):
        from app.services.notification_service import send_notification

        existing = SimpleNamespace(id=55)
        db = Mock()
        db.execute = AsyncMock(side_effect=[
            SimpleNamespace(scalar_one_or_none=lambda: existing),
        ])
        db.add = Mock()
        db.flush = AsyncMock()

        result = await send_notification(
            db,
            title="Holiday",
            message="Holiday tomorrow",
            school_id=1,
            sent_by=2,
            dedup_key="1:2026-04-01:holiday",
        )

        self.assertEqual(result.id, 55)
        db.add.assert_not_called()
        db.flush.assert_not_awaited()


class TimetableConflictTests(unittest.IsolatedAsyncioTestCase):
    async def test_overlap_validation_rejects_same_teacher_time(self):
        from app.services.timetable_service import validate_timetable_slot_conflict

        db = Mock()
        db.execute = AsyncMock(return_value=SimpleNamespace(first=lambda: (SimpleNamespace(id=1),)))

        with self.assertRaises(ValueError):
            await validate_timetable_slot_conflict(
                db,
                class_id=3,
                teacher_id=9,
                day_of_week=1,
                start_time="09:00:00",
                end_time="09:45:00",
            )

    async def test_period_number_conflict_rejects_same_class_assignment(self):
        from app.services.timetable_service import validate_timetable_slot_conflict

        db = Mock()
        db.execute = AsyncMock(
            side_effect=[
                SimpleNamespace(first=lambda: None),
                SimpleNamespace(first=lambda: (SimpleNamespace(id=7),)),
            ]
        )

        with self.assertRaises(ValueError):
            await validate_timetable_slot_conflict(
                db,
                class_id=3,
                teacher_id=9,
                day_of_week=1,
                period_number=2,
                start_time="10:00:00",
                end_time="10:45:00",
            )

    def test_teacher_timetable_can_be_grouped_by_day(self):
        from app.services.timetable_service import group_timetable_slots_by_day

        grouped = group_timetable_slots_by_day(
            [
                SimpleNamespace(day_of_week=2, period_number=3, start_time="11:00"),
                SimpleNamespace(day_of_week=1, period_number=2, start_time="10:00"),
                SimpleNamespace(day_of_week=1, period_number=1, start_time="09:00"),
            ]
        )

        self.assertEqual([bucket["day"] for bucket in grouped], [1, 2])
        self.assertEqual([slot.period_number for slot in grouped[0]["slots"]], [1, 2])


class HolidayTests(unittest.IsolatedAsyncioTestCase):
    async def test_bulk_attendance_rejects_holiday(self):
        from app.services.attendance_service import bulk_mark_attendance

        db = Mock()
        db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(id=4, school_id=2)))

        with patch("app.services.attendance_service.is_holiday_for_class", AsyncMock(return_value=True)):
            with self.assertRaises(ValueError):
                await bulk_mark_attendance(db, 4, date(2026, 5, 1), [1], 99)

    def test_timetable_model_includes_class_day_index(self):
        from app.models.timetable import TimetableSlot

        index_names = {index.name for index in TimetableSlot.__table__.indexes}
        self.assertIn("ix_timetable_slots_class_day", index_names)


class AttendanceMessageTests(unittest.IsolatedAsyncioTestCase):
    async def test_parent_reply_creates_thread_message(self):
        from app.services.attendance_service import create_attendance_message

        db = Mock()
        db.add = Mock()
        db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(id=1)))
        db.flush = AsyncMock()
        parent = User(
            id=12,
            role=UserRole.PARENT,
            school_id=3,
            name="Parent",
            email="p@example.com",
            password_hash="x",
        )

        with patch("app.services.attendance_service.can_view_student", AsyncMock(return_value=True)):
            message = await create_attendance_message(
                db,
                student_id=9,
                attendance_date=date(2026, 4, 30),
                sender=parent,
                message="He had a fever and will return tomorrow.",
            )

        self.assertEqual(message.student_id, 9)
        self.assertEqual(message.sender_role, "parent")
        self.assertEqual(message.message, "He had a fever and will return tomorrow.")
        db.add.assert_called_once()
        db.flush.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
