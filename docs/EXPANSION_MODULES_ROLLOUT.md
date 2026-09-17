# Parent Portal, Admissions and Library rollout

All three modules deploy disabled. Migrations `0113`–`0117` add new tables, fields and role choices; they do not modify historical student, result, attendance, bill or payment rows.

## Deployment sequence

1. Deploy the code with all three flags unset/false.
2. Run `python manage.py check` and `python manage.py migrate` in the normal maintenance window.
3. Create admission cycles and library policies/categories through Django administration.
4. Enable one module at a time for a pilot group.

Environment flags:

```text
PARENT_PORTAL_ENABLED=false
ADMISSIONS_ENABLED=false
PUBLIC_ADMISSIONS_ENABLED=false
LIBRARY_ENABLED=false
PUBLIC_ADMISSION_MAX_SUBMISSIONS=5
PUBLIC_ADMISSION_RATE_SECONDS=3600
PARENT_TEMP_PASSWORD_HOURS=24
PARENT_LOGIN_MAX_ATTEMPTS=5
PARENT_LOGIN_LOCK_SECONDS=900
```

## Parent Portal pilot

1. Set `PARENT_PORTAL_ENABLED=true` in staging/pilot deployment.
2. Open an existing student and use **Verify / activate parent portal access**.
3. Give the verified guardian their registered telephone username and temporary password `123` privately.
4. The temporary password expires and can open only the password-change page.
5. Confirm results shown are verified, fees match the existing ledger and unrelated students cannot be accessed.

The existing `Student.guardian`, `Student.relationship` and `Student.contact` fields remain the guardian source. A repeated normalized contact reuses the existing parent login and does not reset its private password.

## Admissions pilot

1. Create an admission cycle in Django administration.
2. Set `ADMISSIONS_ENABLED=true`.
3. Create and process internal applications.
4. Test enrollment with a configured current term, academic class and preferred stream.

Enrollment is atomic, duplicate-aware and available only from `accepted`. Direct student registration remains unchanged.

### Public admissions

Keep `PUBLIC_ADMISSIONS_ENABLED=false` until the internal admissions pilot is complete. Then:

1. Confirm at least one active admission cycle is currently open.
2. Set both `ADMISSIONS_ENABLED=true` and `PUBLIC_ADMISSIONS_ENABLED=true`.
3. Link the school website to `/admissions/apply/` and optionally `/admissions/track/`.
4. Submit and track a test application before publishing the link.

Public applications enter as `submitted`. Tracking requires both the application number and the normalized guardian contact. Public pages never expose internal notes or enrollment controls.

## Library pilot

1. Create student/staff loan policies, categories and initial catalogue records.
2. Set `LIBRARY_ENABLED=true`.
3. Pilot circulation with a small borrower group.
4. Reconcile physical copies before wider rollout.

Library charges are deliberately not posted into Finance in this release. Parent pages display current loans only after both Parent Portal and Library flags are enabled.

## Deliberately excluded from the first release

- Online parent payments
- SMS/OTP messaging
- Automatic admission-fee or library-fine posting
- Library reservations and digital resources
- Automatic bulk activation of parent accounts
