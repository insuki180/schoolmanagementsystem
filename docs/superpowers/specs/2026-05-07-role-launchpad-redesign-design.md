# Role Launchpad Redesign

Date: 2026-05-07
Project: School Management System
Status: Approved for planning

## Summary

Replace the current sidebar-first authenticated experience with a role-aware launchpad home screen and a compact in-module navigation model. The redesign should preserve support for existing roles while making it easy to add new modules and role variations over time, especially for parent, teacher, class teacher, school admin, and super admin users.

## Context

The current authenticated shell is defined in `app/templates/base.html` and uses:

- a fixed left sidebar with role-based links
- a top bar for page title and user identity
- role-specific dashboard templates in `app/templates/dashboard/`

The requested experience is:

- a card-based opening screen inspired by the provided reference image
- adapted to the school app's real modules
- responsive for mobile
- scalable as features and roles continue to expand

## Constraint: Truthpack Gap

The repository currently includes `.vibecheck/`, but the expected `.vibecheck/truthpack/` files referenced by `AGENTS.md` are not present. Because of that, implementation must avoid assuming missing truthpack-verified copy or route metadata beyond what is already present in the codebase. If the team wants strict truthpack validation before implementation, regenerate the truthpack first.

## Goals

- Remove dependency on the sidebar as the primary navigation model
- Introduce a launchpad-style first screen after login for all roles
- Keep navigation compact and usable inside modules
- Make the layout responsive on mobile without crowding
- Support future roles and future modules without redesigning the shell again
- Preserve role-specific priorities while sharing one design system

## Non-Goals

- No attempt to redesign every detail of every module page in this phase
- No new feature creation beyond navigation and opening-screen UX
- No role or permission model changes
- No route or backend contract changes unless implementation reveals a small compatibility need

## Information Architecture

### Global model

Authenticated navigation will have three layers:

1. Launchpad home screen
2. Compact top navigation inside modules
3. Overflow navigation through a More menu

The sidebar is removed from the default authenticated layout.

### Launchpad home screen

The first screen after login becomes a role-aware command center:

- top bar with brand, search/alerts/profile affordances, and current context
- welcome block tuned to the role
- optional quick summary or status strip
- grid of primary module cards
- grouped secondary actions when needed

This screen should work like a launcher, not just a passive dashboard.

### In-module navigation

Once the user enters a module:

- the page keeps a compact top bar
- the current module title and local actions stay visible
- cross-module jumps happen through the top menu and mobile bottom navigation
- secondary destinations live under More rather than permanent chrome

## Responsive Navigation

### Desktop

Desktop uses:

- a slim top navigation bar
- a brand area on the left
- utility actions on the right
- optional compact module switcher or More dropdown for secondary destinations

The launchpad grid can expand to more columns depending on viewport width.

### Mobile

Mobile uses:

- a compact sticky top bar for identity and utility actions
- a bottom tab bar for the highest-frequency destinations
- a More destination for overflow modules and settings

The bottom tab bar should be role-aware. Only the most important destinations should be promoted into tabs. Everything else stays accessible through More to prevent overload.

## Role Strategy

Use one shared layout system with role-specific content priorities.

This means:

- shared card components
- shared top nav behavior
- shared mobile bottom-nav behavior
- shared spacing, breakpoints, typography, and interaction rules
- role-specific welcome copy, summary blocks, priority cards, and module order

Do not build fully separate dashboard architectures for each role unless a future role has fundamentally different needs.

## Role-by-Role Opening Screen Plan

### Parent

The first viewport should answer the parent's immediate questions quickly:

- child status
- recent notifications
- attendance
- marks
- timetable
- fees
- teacher contact

If multiple children are linked, the screen should use compact child summary sections before or alongside module cards so the parent can orient immediately.

### Teacher

Teacher launchpad should prioritize daily operational work:

- mark attendance
- marks entry
- class schedule
- notifications
- assigned classes
- follow-ups or alerts

The screen should feel action-first and time-sensitive.

### Class Teacher

Class teacher can share the teacher layout framework, but with elevated visibility for:

- class management
- parent communication
- absence alerts
- student administration shortcuts

This should be implemented as a priority variation, not a separate design language.

### School Admin

School admin launchpad should emphasize operations:

- students
- staff
- classes
- timetable
- exams
- fees and finance
- reports
- settings

This role benefits from a stronger overview strip at the top plus a broad module grid below.

### Super Admin

Super admin should focus on network-level oversight:

- schools
- administrators
- system activity
- reporting
- configuration

The layout remains the same, but the content focus shifts from campus operations to multi-school governance.

## Module Card System

Each launchpad card should support:

- icon
- module name
- short supporting label where useful
- optional badge or count
- large tap/click target

Card rules:

- cards must remain stable in size across breakpoints
- icons should do most of the recognition work
- text must wrap cleanly on smaller widths
- hover and focus states must be obvious
- cards should be reusable across roles with content configuration rather than custom markup per role

## Grouping Strategy For Future Features

As modules increase, features should be categorized into stable groups such as:

- Daily Work
- Academics
- Communication
- Administration
- Reports
- Settings

Rules for future additions:

- primary, high-frequency features get launchpad placement
- frequent mobile destinations may be promoted to bottom tabs
- lower-frequency features go into More or grouped sections
- adding a feature should require content configuration, not shell redesign

## Layout Behavior

### Desktop launchpad

- hero or welcome area at top
- card grid below
- section grouping available when module count increases
- no floating sidebar

### Mobile launchpad

- top area stays concise
- card grid should collapse to two columns where practical
- large spacing and tap targets
- bottom tab bar remains persistent for major destinations

### In-module pages

- keep the compact top nav
- remove dependence on left-side persistent navigation
- preserve content width and scanning comfort

## Implementation Direction

The redesign should likely be implemented in these layers:

1. Refactor `base.html` to replace sidebar shell with top-nav shell
2. Introduce reusable launchpad and top-nav partials
3. Rebuild dashboard templates for each role using shared card and section patterns
4. Add responsive mobile bottom navigation
5. Update module pages so they still feel navigable without the sidebar

## Risks

- Some existing pages may implicitly rely on sidebar presence for discoverability
- Mobile nav can become crowded if too many destinations are promoted
- Role differences may tempt copy-paste layouts unless shared components are enforced
- Missing truthpack data increases the chance of copy drift unless the team regenerates it first

## Testing Expectations

Implementation should be verified across:

- desktop authenticated shell
- mobile authenticated shell
- each current role dashboard
- navigation into and out of major modules
- long module labels and future-card overflow behavior

Recommended verification should include browser checks for:

- no overlap in card grids
- stable card sizing
- usable mobile bottom nav
- acceptable first-viewport hierarchy on parent, teacher, admin, and super admin screens

## Acceptance Criteria

- Users land on a card-based launchpad instead of a sidebar-led screen
- Sidebar is no longer required for authenticated navigation
- Compact top navigation works across modules
- Mobile uses bottom tabs plus More
- Each role sees the same design system with role-specific priorities
- The layout can absorb future modules without structural redesign

## Planning Note

The next step after spec approval is to produce a concrete implementation plan covering:

- shared shell refactor
- reusable partial/component strategy
- role dashboard migration order
- responsive navigation behavior
- verification approach
