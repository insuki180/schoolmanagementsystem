"""Role-aware launchpad and navigation configuration."""

from __future__ import annotations


def _card(label: str, href: str, icon: str, eyebrow: str | None = None, badge: str | None = None) -> dict:
    return {
        "label": label,
        "href": href,
        "icon": icon,
        "eyebrow": eyebrow,
        "badge": badge,
    }


def _item(label: str, href: str, icon: str) -> dict:
    return {"label": label, "href": href, "icon": icon}


def build_role_navigation(role: str) -> dict:
    normalized = (role or "").lower()

    configs = {
        "super_admin": {
            "home_href": "/dashboard",
            "logo_action": {"href": "/dashboard", "label": "SchoolMS"},
            "mobile_tabs": [
                _item("Dashboard", "/dashboard", "home"),
                _item("Schools", "/schools", "school"),
                _item("Logs", "/logs", "activity"),
                _item("More", "#more-nav", "menu"),
            ],
            "top_items": [
                _item("Schools", "/schools", "school"),
                _item("Admins", "/users/create-admin", "users"),
                _item("Logs", "/logs", "activity"),
            ],
            "more_items": [
                _item("Finance", "/finance", "wallet"),
                _item("Student CSV", "/import/students", "upload"),
            ],
            "launchpad_sections": [
                {
                    "title": "Network",
                    "cards": [
                        _card("Schools", "/schools", "school", "Overview"),
                        _card("Create School Admin", "/users/create-admin", "users", "Access"),
                        _card("Logs", "/logs", "activity", "Monitoring"),
                    ],
                },
                {
                    "title": "Operations",
                    "cards": [
                        _card("Finance", "/finance", "wallet", "Collections"),
                        _card("Student CSV", "/import/students", "upload", "Bulk data"),
                    ],
                },
            ],
        },
        "school_admin": {
            "home_href": "/dashboard",
            "logo_action": {"href": "/dashboard", "label": "SchoolMS"},
            "mobile_tabs": [
                _item("Dashboard", "/dashboard", "home"),
                _item("Classes", "/classes", "classroom"),
                _item("Finance", "/finance", "wallet"),
                _item("More", "#more-nav", "menu"),
            ],
            "top_items": [
                _item("Classes", "/classes", "classroom"),
                _item("Teachers", "/users/teachers", "users"),
                _item("Finance", "/finance", "wallet"),
            ],
            "more_items": [
                _item("Create Teacher", "/users/create-teacher", "plus"),
                _item("Student CSV", "/import/students", "upload"),
                _item("Logs", "/logs", "activity"),
                _item("Notifications", "/notifications", "bell"),
            ],
            "launchpad_sections": [
                {
                    "title": "Administration",
                    "cards": [
                        _card("Students", "/classes", "student", "Records"),
                        _card("Teachers & Staff", "/users/teachers", "users", "People"),
                        _card("Create Teacher", "/users/create-teacher", "plus", "Access"),
                    ],
                },
                {
                    "title": "Academics",
                    "cards": [
                        _card("Classes", "/classes", "classroom", "Structure"),
                        _card("Attendance", "/attendance", "attendance", "Daily work"),
                        _card("Marks", "/marks", "marks", "Assessment"),
                    ],
                },
                {
                    "title": "Operations",
                    "cards": [
                        _card("Finance", "/finance", "wallet", "Collections"),
                        _card("Notifications", "/notifications", "bell", "Updates"),
                        _card("Logs", "/logs", "activity", "Audit"),
                    ],
                },
            ],
        },
        "teacher": {
            "home_href": "/dashboard",
            "logo_action": {"href": "/dashboard", "label": "SchoolMS"},
            "mobile_tabs": [
                _item("Dashboard", "/dashboard", "home"),
                _item("Attendance", "/attendance", "attendance"),
                _item("Marks", "/marks", "marks"),
                _item("More", "#more-nav", "menu"),
            ],
            "top_items": [
                _item("Attendance", "/attendance", "attendance"),
                _item("Marks", "/marks", "marks"),
                _item("Alerts", "/notifications", "bell"),
            ],
            "more_items": [
                _item("Classes", "/dashboard#teacher-classes", "classroom"),
                _item("Create Student", "/users/create-student", "student"),
                _item("Finance", "/finance", "wallet"),
            ],
            "launchpad_sections": [
                {
                    "title": "Daily Work",
                    "cards": [
                        _card("Mark Attendance", "/attendance/mark", "attendance", "Today"),
                        _card("Enter Marks", "/marks/entry", "marks", "Assessment"),
                        _card("Send Alert", "/notifications/send", "bell", "Parents"),
                        _card("Create Student + Parent", "/users/create-student", "student", "Enrollment"),
                    ],
                },
                {
                    "title": "Classroom",
                    "cards": [
                        _card("Assigned Classes", "/dashboard#teacher-classes", "classroom", "Overview"),
                        _card("Finance", "/finance", "wallet", "Pending fees"),
                    ],
                },
            ],
        },
        "class_teacher": {
            "home_href": "/dashboard",
            "logo_action": {"href": "/dashboard", "label": "SchoolMS"},
            "mobile_tabs": [
                _item("Dashboard", "/dashboard", "home"),
                _item("Attendance", "/attendance", "attendance"),
                _item("Marks", "/marks", "marks"),
                _item("More", "#more-nav", "menu"),
            ],
            "top_items": [
                _item("Attendance", "/attendance", "attendance"),
                _item("Marks", "/marks", "marks"),
                _item("Alerts", "/notifications", "bell"),
            ],
            "more_items": [
                _item("Classes", "/dashboard#teacher-classes", "classroom"),
                _item("Create Student", "/users/create-student", "student"),
                _item("Finance", "/finance", "wallet"),
            ],
            "launchpad_sections": [
                {
                    "title": "Daily Work",
                    "cards": [
                        _card("Mark Attendance", "/attendance/mark", "attendance", "Today"),
                        _card("Enter Marks", "/marks/entry", "marks", "Assessment"),
                        _card("Send Alert", "/notifications/send", "bell", "Parents"),
                        _card("Create Student + Parent", "/users/create-student", "student", "Enrollment"),
                    ],
                },
                {
                    "title": "Homeroom",
                    "cards": [
                        _card("Assigned Classes", "/dashboard#teacher-classes", "classroom", "Overview"),
                        _card("Absence Alerts", "/dashboard#teacher-alerts", "activity", "Follow up"),
                    ],
                },
            ],
        },
        "parent": {
            "home_href": "/dashboard",
            "logo_action": {"href": "/dashboard", "label": "SchoolMS"},
            "mobile_tabs": [
                _item("Dashboard", "/dashboard", "home"),
                _item("Updates", "/notifications", "bell"),
                _item("Children", "/dashboard#children-overview", "student"),
                _item("More", "#more-nav", "menu"),
            ],
            "top_items": [
                _item("Updates", "/notifications", "bell"),
                _item("Children", "/dashboard#children-overview", "student"),
                _item("Contacts", "/dashboard#family-contacts", "users"),
            ],
            "more_items": [
                _item("Student Details", "/dashboard#family-details", "file"),
                _item("Notifications", "/notifications", "bell"),
            ],
            "launchpad_sections": [
                {
                    "title": "Family",
                    "cards": [
                        _card("Notifications", "/notifications", "bell", "Updates"),
                        _card("Children Overview", "/dashboard#children-overview", "student", "Today"),
                        _card("Student Details", "/dashboard#family-details", "file", "Profile"),
                        _card("Contact Teachers", "/dashboard#family-contacts", "users", "Support"),
                    ],
                }
            ],
        },
    }

    fallback = {
        "home_href": "/dashboard",
        "logo_action": {"href": "/dashboard", "label": "SchoolMS"},
        "mobile_tabs": [_item("Dashboard", "/dashboard", "home")],
        "top_items": [_item("Dashboard", "/dashboard", "home")],
        "more_items": [],
        "launchpad_sections": [{"title": "Overview", "cards": [_card("Dashboard", "/dashboard", "home")]}],
    }

    return configs.get(normalized, fallback)
