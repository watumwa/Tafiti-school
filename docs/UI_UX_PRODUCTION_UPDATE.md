# Production UI/UX Update — 16 September 2026

This update modernizes the School MIS presentation and interaction layer while preserving the existing production business engine.

## Production invariants

This package intentionally does **not** change:

- Django models or database schema
- migrations
- URL names or routes
- permissions or role capability calculations
- payment/result/attendance/timetable business rules
- form field names or POST endpoints
- stored school data

No database migration is required for this UI update.

## Main improvements

- Added a production-safe UI layer (`static/css/production_ui.css`).
- Added a small progressive-enhancement layer (`static/js/production_ui.js`).
- Sidebar branding now uses the configured school name rather than a hard-coded institution name.
- Sidebar terminology is clearer: **Results Work Queue** and **Fees & Payments**.
- Bursars/admin users have a direct **Record Payment** navigation path.
- Sidebar active state remains visible on deeper pages.
- Global search was redesigned into a clearer school-wide search centre.
- Student Register actions are clearer and registration is blocked in the UI when the current academic setup is incomplete.
- Student list remains server-paginated and responsive.
- High-value data-entry screens warn users before leaving with unsaved work.
- Dynamically loaded edit forms receive the same unsaved-work protection.
- The generic table-edit modal is now opt-in so complex edit screens are no longer intercepted automatically.
- Submit feedback follows the button actually used and does not disable named submit buttons, preserving Django POST semantics.
- Attendance mobile statuses use full labels instead of P/A/L/E abbreviations.
- Results now distinguish **Save Draft** from **Submit for Verification** more clearly and show a final submission summary.
- Verification can filter directly to mark differences/mismatches.
- Timetable filters are applied together with **Load Timetable**, avoiding repeated reloads; auto-generation has an explicit confirmation.
- Student Bills no longer mixes browser-side DataTables pagination/search with Django server pagination.
- Quick Payment is more prominent in Finance navigation.
- Settings navigation is hidden from roles that should not normally configure the school (backend authorization remains unchanged by this UI package).
- Legacy/light/dark pages receive additional visual consistency and responsive improvements.

## Static files

The source static files and corresponding `staticfiles/` copies are included. On a normal Django production deployment, still run:

```bash
python manage.py collectstatic --noinput
```

This ensures the current server's static collection is authoritative.

## Recommended production deployment

1. Take a server/database backup according to the school's existing procedure.
2. Merge the update into the existing project directory.
3. Do **not** run `makemigrations` for this package; there are no model changes.
4. Run the application's normal environment checks.
5. Run `python manage.py collectstatic --noinput`.
6. Restart the application service using the server's existing process manager.
7. Hard-refresh a browser (`Ctrl+Shift+R`) so old cached CSS/JS is not reused.

## Smoke test after deployment

Test with the actual roles used by the school:

- Administrator: dashboard, Students, search, settings visibility, Results, Finance.
- Teacher: Results Work Queue, mark entry, Save Draft, submit for verification, Attendance.
- Verification/DOS role: verification queue and differences-only filter.
- Bursar: Record Payment, Student Bills search/filter/pagination, receipt access.
- Class Teacher: student access and academic reporting navigation.
- Admissions: open and edit an application without losing form data.
- Librarian: Issue and Return workflows.
- Mobile/tablet: sidebar, Student Register, Attendance and timetable review.

## Rollback

The update is template/static-only. If a production issue is discovered, restore the previous versions of the files from the pre-deployment backup and run `collectstatic` again. No database rollback is required for this update because the package contains no database migration or schema change.
