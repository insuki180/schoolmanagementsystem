# Role Launchpad Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sidebar-led authenticated shell with a role-aware launchpad home screen, compact top navigation, responsive mobile bottom tabs, and logo-to-dashboard navigation across roles.

**Architecture:** Keep the existing FastAPI route structure and role dashboards, but move navigation responsibility into a shared shell plus reusable dashboard partials. Introduce a navigation configuration layer so existing and future roles can map modules, launchpad cards, mobile tabs, and overflow menu items without hard-coding another layout rewrite.

**Tech Stack:** FastAPI, Jinja2 templates, Tailwind CSS output, custom CSS, vanilla JavaScript, pytest/unittest, Playwright

---

## File Structure

### Files to create

- `app/services/navigation_service.py`  
  Central role-aware navigation and launchpad configuration for desktop and mobile.
- `app/templates/partials/app_topbar.html`  
  Shared top bar with clickable logo/home action and compact menu actions.
- `app/templates/partials/mobile_nav.html`  
  Shared mobile bottom-tab bar with `More`.
- `app/templates/partials/launchpad_card.html`  
  Reusable launchpad card partial.
- `app/templates/partials/launchpad_section.html`  
  Optional grouped module section wrapper.
- `tests/test_dashboard_navigation.py`  
  Unit coverage for navigation config and dashboard shell context.
- `tests/e2e/launchpad-navigation.spec.js`  
  Browser checks for role dashboards, mobile tabs, and logo navigation.

### Files to modify

- `app/routers/dashboard.py`  
  Inject per-role launchpad/navigation context into dashboard templates.
- `app/templates/base.html`  
  Remove sidebar shell and replace it with top-nav + mobile-nav shell.
- `app/templates/dashboard/admin.html`  
  Convert into launchpad-oriented school-admin screen.
- `app/templates/dashboard/teacher.html`  
  Convert into action-first launchpad.
- `app/templates/dashboard/parent.html`  
  Convert into child-first launchpad.
- `app/templates/dashboard/super_admin.html`  
  Convert into network-oriented launchpad.
- `static/css/custom.css`  
  Add launchpad shell, cards, grouped sections, top-nav, and mobile tab styles.
- `static/js/app.js`  
  Replace sidebar-specific behavior with compact-menu and mobile-nav behavior.
- `tests/e2e/full-app-audit.spec.js`  
  Update page assertions if legacy sidebar text or shell expectations change.

### Existing files to inspect while implementing

- `app/templates/partials/nav_links.html`
- `playwright.config.js`
- `package.json`
- `tests/test_page_level_filters.py`

---

### Task 1: Lock navigation config and dashboard shell contract

**Files:**
- Create: `tests/test_dashboard_navigation.py`
- Create: `app/services/navigation_service.py`
- Modify: `app/routers/dashboard.py`

- [ ] **Step 1: Write the failing navigation config tests**

```python
import unittest

from app.models.user import UserRole
from app.services.navigation_service import build_role_navigation


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
        self.assertIn("Timetable", labels)
        self.assertEqual(config["logo_action"]["href"], "/dashboard")

    def test_unknown_role_falls_back_to_safe_dashboard_only_navigation(self):
        config = build_role_navigation("unknown")

        self.assertEqual(config["mobile_tabs"], [{"label": "Dashboard", "href": "/dashboard", "icon": "home"}])
        self.assertEqual(len(config["launchpad_sections"]), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_navigation.py -v`  
Expected: FAIL with `ModuleNotFoundError` for `app.services.navigation_service`

- [ ] **Step 3: Write the minimal navigation service**

```python
from __future__ import annotations


def build_role_navigation(role: str) -> dict:
    normalized = (role or "").lower()

    configs = {
        "teacher": {
            "home_href": "/dashboard",
            "logo_action": {"href": "/dashboard", "label": "SchoolMS"},
            "mobile_tabs": [
                {"label": "Dashboard", "href": "/dashboard", "icon": "home"},
                {"label": "Attendance", "href": "/attendance", "icon": "calendar"},
                {"label": "Marks", "href": "/marks", "icon": "chart"},
                {"label": "More", "href": "#more-nav", "icon": "menu"},
            ],
            "launchpad_sections": [
                {
                    "title": "Daily Work",
                    "cards": [
                        {"label": "Mark Attendance", "href": "/attendance/mark", "icon": "attendance"},
                        {"label": "Enter Marks", "href": "/marks/entry", "icon": "marks"},
                    ],
                }
            ],
        },
        "parent": {
            "home_href": "/dashboard",
            "logo_action": {"href": "/dashboard", "label": "SchoolMS"},
            "mobile_tabs": [
                {"label": "Dashboard", "href": "/dashboard", "icon": "home"},
                {"label": "Notifications", "href": "/notifications", "icon": "bell"},
                {"label": "More", "href": "#more-nav", "icon": "menu"},
            ],
            "launchpad_sections": [
                {
                    "title": "Family",
                    "cards": [
                        {"label": "Notifications", "href": "/notifications", "icon": "bell"},
                        {"label": "Timetable", "href": "/dashboard", "icon": "calendar"},
                    ],
                }
            ],
        },
    }

    return configs.get(
        normalized,
        {
            "home_href": "/dashboard",
            "logo_action": {"href": "/dashboard", "label": "SchoolMS"},
            "mobile_tabs": [{"label": "Dashboard", "href": "/dashboard", "icon": "home"}],
            "launchpad_sections": [{"title": "Overview", "cards": [{"label": "Dashboard", "href": "/dashboard", "icon": "home"}]}],
        },
    )
```

- [ ] **Step 4: Extend dashboard route context to expose navigation config**

```python
from app.services.navigation_service import build_role_navigation


def _base_dashboard_context(request: Request, current_user: User) -> dict:
    role = current_user.role.value if hasattr(current_user.role, "value") else current_user.role
    nav = build_role_navigation(role)
    return {
        "request": request,
        "user": current_user,
        "nav_config": nav,
        "launchpad_sections": nav["launchpad_sections"],
        "mobile_tabs": nav["mobile_tabs"],
        "logo_action": nav["logo_action"],
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_dashboard_navigation.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_dashboard_navigation.py app/services/navigation_service.py app/routers/dashboard.py
git commit -m "feat: add role-based launchpad navigation config"
```

---

### Task 2: Replace sidebar shell with top-nav and mobile-nav shell

**Files:**
- Modify: `app/templates/base.html`
- Create: `app/templates/partials/app_topbar.html`
- Create: `app/templates/partials/mobile_nav.html`
- Modify: `static/js/app.js`
- Test: `tests/test_dashboard_navigation.py`

- [ ] **Step 1: Add a failing shell context test**

```python
from types import SimpleNamespace
from starlette.requests import Request

from app.models.user import User, UserRole
from app.routers.dashboard import templates


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


class DashboardShellContextTests(unittest.TestCase):
    def test_base_shell_context_contains_logo_and_mobile_tabs(self):
        user = User(id=1, name="Teacher Demo", email="teacher@example.com", password_hash="x", role=UserRole.TEACHER, school_id=1)
        context = _base_dashboard_context(build_request(), user)

        self.assertEqual(context["logo_action"]["href"], "/dashboard")
        self.assertTrue(any(item["label"] == "More" for item in context["mobile_tabs"]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_navigation.py -v`  
Expected: FAIL because `_base_dashboard_context` is not available or missing the required keys

- [ ] **Step 3: Refactor `base.html` to use shared top bar and bottom mobile nav**

```html
{% if request.state.user is defined and request.state.user or (request.cookies.get('access_token')) %}
{% set user = user if user is defined else None %}

<div id="app-shell" class="app-shell">
  {% include "partials/app_topbar.html" %}

  <main id="app-main" class="app-main">
    {% if request.query_params.get('msg') %}
    <div class="mx-4 mt-4 success-banner fade-in" data-auto-dismiss="6000" role="alert">
      <span class="success-banner-icon">✓</span>
      <span>{{ request.query_params.get('msg') }}</span>
    </div>
    {% endif %}

    <div class="app-content p-4 md:p-6 pb-24 md:pb-6">
      {% block content %}{% endblock %}
    </div>
  </main>

  {% include "partials/mobile_nav.html" %}
</div>
{% else %}
<main class="min-h-screen flex items-center justify-center p-4" role="main">
  {% block content %}{% endblock %}
</main>
{% endif %}
```

- [ ] **Step 4: Add compact-menu JS instead of sidebar toggling**

```javascript
const CompactMenu = {
  init() {
    document.querySelectorAll("[data-menu-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const target = document.getElementById(button.dataset.menuToggle);
        if (!target) return;
        target.classList.toggle("hidden");
      });
    });
  }
};

document.addEventListener("DOMContentLoaded", () => {
  CompactMenu.init();
});

window.CompactMenu = CompactMenu;
```

- [ ] **Step 5: Run targeted tests**

Run: `pytest tests/test_dashboard_navigation.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/templates/base.html app/templates/partials/app_topbar.html app/templates/partials/mobile_nav.html static/js/app.js tests/test_dashboard_navigation.py
git commit -m "feat: replace sidebar shell with compact navigation shell"
```

---

### Task 3: Build reusable launchpad cards and grouped dashboard sections

**Files:**
- Create: `app/templates/partials/launchpad_card.html`
- Create: `app/templates/partials/launchpad_section.html`
- Modify: `static/css/custom.css`
- Modify: `app/services/navigation_service.py`
- Test: `tests/test_dashboard_navigation.py`

- [ ] **Step 1: Add a failing config test for grouped launchpad cards**

```python
    def test_school_admin_navigation_groups_cards_for_growth(self):
        config = build_role_navigation("school_admin")

        titles = [section["title"] for section in config["launchpad_sections"]]
        self.assertIn("Administration", titles)
        self.assertIn("Academics", titles)
        self.assertTrue(any(card["href"] == "/finance" for section in config["launchpad_sections"] for card in section["cards"]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_navigation.py -v`  
Expected: FAIL because `school_admin` config is still incomplete

- [ ] **Step 3: Expand navigation config and create reusable card partials**

```python
"school_admin": {
    "home_href": "/dashboard",
    "logo_action": {"href": "/dashboard", "label": "SchoolMS"},
    "mobile_tabs": [
        {"label": "Dashboard", "href": "/dashboard", "icon": "home"},
        {"label": "Students", "href": "/classes", "icon": "users"},
        {"label": "Finance", "href": "/finance", "icon": "wallet"},
        {"label": "More", "href": "#more-nav", "icon": "menu"},
    ],
    "launchpad_sections": [
        {
            "title": "Administration",
            "cards": [
                {"label": "Teachers & Staff", "href": "/users/teachers", "icon": "staff", "eyebrow": "People"},
                {"label": "Settings", "href": "/dashboard", "icon": "settings", "eyebrow": "Control"},
            ],
        },
        {
            "title": "Academics",
            "cards": [
                {"label": "Classes", "href": "/classes", "icon": "classroom"},
                {"label": "Finance", "href": "/finance", "icon": "wallet"},
            ],
        },
    ],
}
```

```html
<a href="{{ card.href }}" class="launchpad-card" data-nav-link>
  <span class="launchpad-card__icon">{{ card.icon }}</span>
  <span class="launchpad-card__copy">
    {% if card.eyebrow %}<span class="launchpad-card__eyebrow">{{ card.eyebrow }}</span>{% endif %}
    <span class="launchpad-card__title">{{ card.label }}</span>
  </span>
  {% if card.badge %}<span class="launchpad-card__badge">{{ card.badge }}</span>{% endif %}
</a>
```

- [ ] **Step 4: Add CSS for responsive launchpad cards**

```css
.launchpad-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
}

.launchpad-card {
  min-height: 168px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.75rem;
  padding: 1.25rem;
  border-radius: 1rem;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
  transition: transform var(--transition), box-shadow var(--transition), border-color var(--transition);
}

.launchpad-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

@media (max-width: 640px) {
  .launchpad-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_dashboard_navigation.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/navigation_service.py app/templates/partials/launchpad_card.html app/templates/partials/launchpad_section.html static/css/custom.css tests/test_dashboard_navigation.py
git commit -m "feat: add reusable launchpad card system"
```

---

### Task 4: Convert each role dashboard to the launchpad layout

**Files:**
- Modify: `app/templates/dashboard/super_admin.html`
- Modify: `app/templates/dashboard/admin.html`
- Modify: `app/templates/dashboard/teacher.html`
- Modify: `app/templates/dashboard/parent.html`
- Modify: `app/routers/dashboard.py`
- Test: `tests/e2e/launchpad-navigation.spec.js`

- [ ] **Step 1: Write the failing Playwright role-launchpad test**

```javascript
const { test, expect } = require("@playwright/test");

const roles = [
  { name: "super-admin", email: "admin@school.com", password: "admin123", expectedCard: "Schools" },
  { name: "school-admin", email: "admin.greenfield@demo.school", password: "demo123", expectedCard: "Teachers & Staff" },
  { name: "teacher", email: "teacher.greenfield.g1a.home@demo.school", password: "demo123", expectedCard: "Mark Attendance" },
  { name: "parent", email: "parent.greenfield.g1a.01@demo.school", password: "demo123", expectedCard: "Notifications" },
];

test.describe("launchpad dashboards", () => {
  for (const role of roles) {
    test(`${role.name} sees role launchpad`, async ({ page, request, baseURL }) => {
      const response = await request.post(`${baseURL}/login`, {
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        data: { email: role.email, password: role.password },
      });
      const payload = await response.json();
      await page.context().addCookies([{ name: "access_token", value: payload.token, url: baseURL, httpOnly: true, sameSite: "Lax" }]);

      await page.goto("/dashboard");
      await expect(page.getByRole("link", { name: role.expectedCard })).toBeVisible();
      await expect(page.getByRole("link", { name: /SchoolMS/i })).toBeVisible();
    });
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx playwright test tests/e2e/launchpad-navigation.spec.js --reporter=list`  
Expected: FAIL because the current dashboards do not render the new launchpad cards/top bar yet

- [ ] **Step 3: Rebuild dashboard templates around shared launchpad sections**

```html
<section class="launchpad-hero">
  <div>
    <p class="launchpad-hero__eyebrow">School Administration</p>
    <h2 class="launchpad-hero__title">Dashboard Overview</h2>
    <p class="launchpad-hero__body">Select a module to manage daily operations.</p>
  </div>
  <div class="launchpad-hero__stats">
    <span class="launchpad-stat">Pending Fees: {{ pending_fee_count }}</span>
  </div>
</section>

{% for section in launchpad_sections %}
  {% include "partials/launchpad_section.html" %}
{% endfor %}
```

```python
context = _base_dashboard_context(request, current_user)
context.update(
    {
        "class_stats": class_stats,
        "recent_notifications": notifs.scalars().all(),
        "teachers": teachers,
        "students": students,
        "pending_fee_count": finance_summary["pending_count"],
    }
)
return templates.TemplateResponse("dashboard/admin.html", context)
```

- [ ] **Step 4: Add parent child summary and teacher action summaries without breaking the shared shell**

```html
{% for child in children %}
<article class="launchpad-child-summary">
  <div>
    <h3>{{ child.student.name }}</h3>
    <p>{{ child.class_name }}</p>
  </div>
  <div class="launchpad-child-summary__metrics">
    <span>Attendance {{ child.attendance|length }}</span>
    <span>Marks {{ child.marks|length }}</span>
  </div>
</article>
{% endfor %}
```

- [ ] **Step 5: Run browser test to verify it passes**

Run: `npx playwright test tests/e2e/launchpad-navigation.spec.js --reporter=list`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/templates/dashboard/super_admin.html app/templates/dashboard/admin.html app/templates/dashboard/teacher.html app/templates/dashboard/parent.html app/routers/dashboard.py tests/e2e/launchpad-navigation.spec.js
git commit -m "feat: redesign role dashboards as launchpads"
```

---

### Task 5: Add responsive top-nav behavior, logo-home action, and mobile bottom tabs

**Files:**
- Modify: `app/templates/partials/app_topbar.html`
- Modify: `app/templates/partials/mobile_nav.html`
- Modify: `static/css/custom.css`
- Modify: `static/js/app.js`
- Test: `tests/e2e/launchpad-navigation.spec.js`

- [ ] **Step 1: Add failing mobile/logo navigation assertions**

```javascript
test("logo returns user to dashboard and mobile bottom nav is visible", async ({ page, request, baseURL }) => {
  const response = await request.post(`${baseURL}/login`, {
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    data: { email: "teacher.greenfield.g1a.home@demo.school", password: "demo123" },
  });
  const payload = await response.json();
  await page.context().addCookies([{ name: "access_token", value: payload.token, url: baseURL, httpOnly: true, sameSite: "Lax" }]);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/marks?class_id=1");
  await page.getByRole("link", { name: /SchoolMS/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("navigation", { name: "Mobile" })).toBeVisible();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx playwright test tests/e2e/launchpad-navigation.spec.js --reporter=list`  
Expected: FAIL because the top bar logo and mobile nav are not fully wired

- [ ] **Step 3: Implement interactive logo and responsive mobile nav**

```html
<header class="app-topbar">
  <a href="{{ logo_action.href }}" class="app-topbar__brand" aria-label="SchoolMS dashboard home">
    <span class="app-topbar__mark">S</span>
    <span class="app-topbar__brand-copy">
      <span class="app-topbar__brand-title">SchoolMS</span>
      <span class="app-topbar__brand-subtitle">{{ role|replace('_', ' ')|title if role else "Dashboard" }}</span>
    </span>
  </a>
  <button type="button" class="app-topbar__menu-button md:hidden" data-menu-toggle="more-menu">Menu</button>
</header>
```

```html
<nav class="mobile-nav md:hidden" aria-label="Mobile">
  {% for item in mobile_tabs %}
  <a href="{{ item.href }}" class="mobile-nav__item{% if item.href == '#more-nav' %} mobile-nav__item--menu{% endif %}" data-nav-link>
    <span class="mobile-nav__label">{{ item.label }}</span>
  </a>
  {% endfor %}
</nav>
```

- [ ] **Step 4: Add CSS/JS to keep bottom nav stable and More menu usable**

```css
.mobile-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  padding: 0.75rem;
  border-top: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(16px);
}

.mobile-nav__item {
  min-height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.9rem;
}
```

- [ ] **Step 5: Run browser test to verify it passes**

Run: `npx playwright test tests/e2e/launchpad-navigation.spec.js --reporter=list`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/templates/partials/app_topbar.html app/templates/partials/mobile_nav.html static/css/custom.css static/js/app.js tests/e2e/launchpad-navigation.spec.js
git commit -m "feat: add responsive top nav and mobile tabs"
```

---

### Task 6: Reconcile shell styling with existing module pages and regression tests

**Files:**
- Modify: `static/css/custom.css`
- Modify: `tests/e2e/full-app-audit.spec.js`
- Modify: `tests/test_dashboard_navigation.py`

- [ ] **Step 1: Add a failing regression assertion for role pages**

```javascript
test("teacher audit still renders module pages without sidebar chrome", async ({ page, request, baseURL }) => {
  const response = await request.post(`${baseURL}/login`, {
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    data: { email: "teacher.greenfield.g1a.home@demo.school", password: "demo123" },
  });
  const payload = await response.json();
  await page.context().addCookies([{ name: "access_token", value: payload.token, url: baseURL, httpOnly: true, sameSite: "Lax" }]);

  await page.goto("/attendance?class_id=1");
  await expect(page.locator("body")).not.toContainText("Academic Control Center");
  await expect(page.getByRole("link", { name: /SchoolMS/i })).toBeVisible();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx playwright test tests/e2e/full-app-audit.spec.js --reporter=list`  
Expected: FAIL if old shell text or old nav assumptions remain

- [ ] **Step 3: Finish shell polish and update audit expectations**

```css
.app-main {
  min-height: 100vh;
  background: var(--color-bg);
}

.app-content {
  width: min(100%, 1440px);
  margin: 0 auto;
}

@media (min-width: 768px) {
  .app-content {
    padding-bottom: 2rem;
  }
}
```

```javascript
{ path: "/dashboard", text: "Dashboard" }
```

- [ ] **Step 4: Run regression checks**

Run: `pytest tests/test_dashboard_navigation.py tests/test_page_level_filters.py -v`  
Expected: PASS

Run: `npx playwright test tests/e2e/full-app-audit.spec.js tests/e2e/launchpad-navigation.spec.js --reporter=list`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add static/css/custom.css tests/e2e/full-app-audit.spec.js tests/test_dashboard_navigation.py
git commit -m "test: cover launchpad shell regressions"
```

---

### Task 7: Build assets, run full verification, and push `main`

**Files:**
- Modify: `static/css/output.css`
- Inspect: `git status`

- [ ] **Step 1: Rebuild the compiled CSS**

Run: `npm run build:css`  
Expected: Tailwind rebuild completes without errors and updates `static/css/output.css`

- [ ] **Step 2: Run backend regression tests**

Run: `pytest tests/test_dashboard_navigation.py tests/test_page_level_filters.py tests/test_parent_portal_and_contacts.py tests/test_permissions_and_absence_response.py -v`  
Expected: PASS

- [ ] **Step 3: Run browser regression tests**

Run: `npx playwright test tests/e2e/full-app-audit.spec.js tests/e2e/launchpad-navigation.spec.js --reporter=list`  
Expected: PASS

- [ ] **Step 4: Review the final diff**

Run: `git status --short`  
Expected: only intended template, CSS, JS, and test files are modified

- [ ] **Step 5: Create the final delivery commit**

```bash
git add app/routers/dashboard.py app/services/navigation_service.py app/templates/base.html app/templates/dashboard/admin.html app/templates/dashboard/parent.html app/templates/dashboard/super_admin.html app/templates/dashboard/teacher.html app/templates/partials/app_topbar.html app/templates/partials/launchpad_card.html app/templates/partials/launchpad_section.html app/templates/partials/mobile_nav.html static/css/custom.css static/css/output.css static/js/app.js tests/test_dashboard_navigation.py tests/e2e/full-app-audit.spec.js tests/e2e/launchpad-navigation.spec.js
git commit -m "feat: ship role launchpad dashboard redesign"
```

- [ ] **Step 6: Push the verified result to `main`**

Run: `git push origin main`  
Expected: push succeeds after all tests are green

---

## Self-Review

### Spec coverage

- Launchpad-first home screen: covered in Tasks 2, 3, and 4
- Compact top nav and no sidebar dependency: covered in Tasks 2 and 5
- Mobile bottom tabs plus More: covered in Task 5
- Role-specific priorities with one shared system: covered in Tasks 1, 3, and 4
- Clickable/tappable logo returning to dashboard: covered in Task 5
- Future growth without shell rewrite: covered in Tasks 1 and 3
- Final verified push to `main`: covered in Task 7

### Placeholder scan

- No `TODO`, `TBD`, or unresolved placeholders remain
- Each task includes concrete file paths, commands, and code examples
- Verification commands are spelled out

### Type consistency

- `build_role_navigation`, `_base_dashboard_context`, `nav_config`, `launchpad_sections`, `mobile_tabs`, and `logo_action` are used consistently across route, template, and test tasks

