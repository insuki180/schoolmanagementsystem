import unittest
from pathlib import Path
import sys

from starlette.requests import Request

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models.user import User, UserRole
from app.routers.dashboard import _base_dashboard_context
from app.services.navigation_service import build_role_navigation


def build_request(path: str = "/dashboard") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


class NavigationConfigTests(unittest.TestCase):
    def test_teacher_navigation_exposes_launchpad_and_mobile_tabs(self):
        config = build_role_navigation("teacher")

        self.assertEqual(config["home_href"], "/dashboard")
        self.assertGreaterEqual(len(config["launchpad_sections"]), 1)
        self.assertEqual([item["label"] for item in config["mobile_tabs"]], ["Dashboard", "Attendance", "Marks", "More"])
        self.assertTrue(any(card["href"] == "/attendance/mark" for section in config["launchpad_sections"] for card in section["cards"]))

    def test_parent_navigation_keeps_child_features_in_primary_launchpad(self):
        config = build_role_navigation("parent")

        labels = [card["label"] for section in config["launchpad_sections"] for card in section["cards"]]
        self.assertIn("Notifications", labels)
        self.assertIn("Contact Teachers", labels)
        self.assertEqual(config["logo_action"]["href"], "/dashboard")

    def test_school_admin_navigation_groups_cards_for_growth(self):
        config = build_role_navigation("school_admin")

        titles = [section["title"] for section in config["launchpad_sections"]]
        self.assertIn("Administration", titles)
        self.assertIn("Academics", titles)
        self.assertTrue(any(card["href"] == "/finance" for section in config["launchpad_sections"] for card in section["cards"]))

    def test_unknown_role_falls_back_to_safe_dashboard_only_navigation(self):
        config = build_role_navigation("unknown")

        self.assertEqual(config["mobile_tabs"], [{"label": "Dashboard", "href": "/dashboard", "icon": "home"}])
        self.assertEqual(len(config["launchpad_sections"]), 1)


class DashboardShellContextTests(unittest.TestCase):
    def test_base_shell_context_contains_logo_and_mobile_tabs(self):
        user = User(id=1, name="Teacher Demo", email="teacher@example.com", password_hash="x", role=UserRole.TEACHER, school_id=1)
        context = _base_dashboard_context(build_request(), user)

        self.assertEqual(context["logo_action"]["href"], "/dashboard")
        self.assertTrue(any(item["label"] == "More" for item in context["mobile_tabs"]))
        self.assertEqual(context["nav_config"]["top_items"][0]["label"], "Attendance")


class ParentContextTests(unittest.TestCase):
    def test_parent_base_context_keeps_dashboard_home_action(self):
        current_user = User(
            id=5,
            name="Parent Example",
            email="parent@example.com",
            password_hash="x",
            role=UserRole.PARENT,
            school_id=1,
        )

        context = _base_dashboard_context(build_request(), current_user)

        self.assertEqual(context["logo_action"]["href"], "/dashboard")
        self.assertEqual(context["mobile_tabs"][0]["label"], "Dashboard")
