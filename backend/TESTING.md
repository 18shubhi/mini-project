# CampusFind System Testing and Performance Report

## 1. Scope and safety

This report records checks actually run during the evaluation. The existing
backend suites were run on an isolated in-memory SQLite test database because
the configured database is PostgreSQL and the project database was not
authorized for access. Django's test runner created and destroyed only its
temporary in-memory test database. No PostgreSQL connection was made, no
configured database was migrated, and no existing user, report, or media was
changed.

The requested browser-driven two-account workflow was not run: it would write
temporary users, reports, claims, and notifications to the configured database.
The browser tests below use the existing static frontend only and make no API
requests.

## 2. Method and environment

| Configuration item | Observed value |
| --- | --- |
| Operating system | Microsoft Windows 11 Home Single Language, 64-bit, build 10.0.26300 |
| Hardware | 13th Gen Intel Core i5-1335U, 12 logical processors, 15.69 GiB visible RAM |
| Python | 3.13.7 (`.venv`) |
| Django | 5.2.18 |
| Django REST Framework | 3.18.3 |
| SimpleJWT | 5.5.1 |
| psycopg | 3.3.6 |
| Pillow | 12.3.0 |
| Configured database engine | PostgreSQL, as declared in Django settings; server was not contacted |
| PostgreSQL client | `psql` 18.6; this is the client version, not a measured server version |
| Test database | SQLite in-memory, created/destroyed by the Django test runner |
| Frontend | Existing HTML, CSS, vanilla JavaScript; Node.js 24.18.0 used for syntax check |
| Matching module | Python standard library; no scikit-learn/NumPy dependency |

`pip check` reported no broken requirements. The frontend directory contains
six HTML pages, one shared stylesheet, and one shared script. The backend
adapter imports and calls the existing root-level `ml.matcher.rank_matches`.

## 3. Automated backend test results

All **44 existing backend API tests passed**. No new backend tests or production
code were added for this evaluation.

### Table E — API Test Cases

“PASS” means the named test completed and its assertions passed on the isolated
SQLite test database; it does not mean that test was run against PostgreSQL.

| Test ID | API/module | Test description | Expected result | Actual result |
| --- | --- | --- | --- | --- |
| AUTH-01 | Accounts | `test_current_user_requires_jwt_and_returns_safe_details` | JWT required; return safe current-user details | PASS |
| AUTH-02 | Accounts | `test_login_rejects_invalid_password` | Invalid credentials rejected | PASS |
| AUTH-03 | Accounts | `test_login_returns_jwt_tokens_and_safe_user_details` | Valid login returns access/refresh tokens and safe user data | PASS |
| AUTH-04 | Accounts | `test_refresh_rejects_token_for_deleted_user` | Refresh for deleted user rejected | PASS |
| AUTH-05 | Accounts | `test_registration_hashes_password_and_omits_it_from_response` | Registration creates hashed-password user; response omits password | PASS |
| AUTH-06 | Accounts | `test_registration_rejects_duplicate_email_and_invalid_role` | Duplicate email and unsupported role rejected | PASS |
| ITEM-01 | Items | `test_create_lost_and_found_reports_associates_authenticated_user` | Both report types created for authenticated reporter | PASS |
| ITEM-02 | Items | `test_create_requires_authentication_and_jwt_token_works` | Anonymous create denied; valid JWT create accepted | PASS |
| ITEM-03 | Items | `test_filters_by_type_category_name_location_and_date` | Combined filters return matching report | PASS |
| ITEM-04 | Items | `test_image_upload_validates_type_and_size` | Valid image accepted; oversized/non-image uploads rejected | PASS |
| ITEM-05 | Items | `test_invalid_date_filter_returns_validation_error` | Invalid date filter returns validation error | PASS |
| ITEM-06 | Items | `test_invalid_item_data_is_rejected` | Invalid type/date payload rejected | PASS |
| ITEM-07 | Items | `test_list_and_retrieve_reports` | List and detail endpoints return reports | PASS |
| ITEM-08 | Items | `test_only_owner_or_django_staff_can_modify_or_delete` | Other user denied; staff can update | PASS |
| ITEM-09 | Items | `test_owner_can_update_and_delete_report` | Owner can update/delete; client cannot set status through update | PASS |
| MATCH-01 | Matching | `test_closed_source_is_rejected_and_closed_candidates_are_omitted` | Closed candidates excluded; closed source rejected | PASS |
| MATCH-02 | Matching | `test_endpoint_requires_authentication` | Anonymous suggestions request rejected | PASS |
| MATCH-03 | Matching | `test_found_source_can_request_lost_suggestions` | FOUND source receives LOST suggestions | PASS |
| MATCH-04 | Matching | `test_invalid_item_id_and_limit_are_rejected` | Missing item and invalid/out-of-range limit rejected | PASS |
| MATCH-05 | Matching | `test_other_users_cannot_access_source_report_matches_but_staff_can` | Non-owner denied; staff allowed | PASS |
| MATCH-06 | Matching | `test_owner_gets_ranked_opposite_type_open_suggestions` | Owner receives ranked suggestions with score and explanations | PASS |
| REC-01 | Recovery | `test_approval_rejects_other_pending_claims_for_the_item` | Approving one claim rejects other pending claims | PASS |
| REC-02 | Recovery | `test_authenticated_user_can_submit_claim_for_found_item` | Authenticated user can submit claim on eligible FOUND item | PASS |
| REC-03 | Recovery | `test_authorized_staff_can_approve_claim` | Authorized staff can approve | PASS |
| REC-04 | Recovery | `test_claim_creation_requires_authentication_and_accepts_jwt` | Anonymous claim denied; valid JWT accepted | PASS |
| REC-05 | Recovery | `test_claim_lists_and_details_are_visible_only_to_related_users_or_staff` | Claim visible only to claimant/reporter/staff | PASS |
| REC-06 | Recovery | `test_claimant_can_cancel_pending_claim_but_reporter_cannot` | Claimant can cancel; reporter cannot | PASS |
| REC-07 | Recovery | `test_duplicate_active_claim_is_rejected_but_cancelled_claim_can_be_resubmitted` | Active duplicate rejected; cancelled claim can be re-submitted | PASS |
| REC-08 | Recovery | `test_invalid_claim_requests_are_rejected` | Blank reason and missing item rejected | PASS |
| REC-09 | Recovery | `test_only_approved_claims_can_be_confirmed` | Pending claim cannot confirm recovery | PASS |
| REC-10 | Recovery | `test_only_reporter_or_staff_can_approve_claim` | Claimant denied decision; reporter can approve | PASS |
| REC-11 | Recovery | `test_recovery_requires_claimant_and_reporter_confirmation` | Item resolves only after both confirmations | PASS |
| REC-12 | Recovery | `test_reporter_can_reject_pending_claim_with_a_note` | Reporter can reject and save note | PASS |
| REC-13 | Recovery | `test_unrelated_user_cannot_confirm_handover` | Unrelated user cannot confirm | PASS |
| REC-14 | Recovery | `test_user_cannot_claim_own_item_or_a_lost_item` | Own item and LOST item claims rejected | PASS |
| NOT-01 | Notifications | `test_claim_submission_approval_rejection_and_cancellation_notify_relevant_users` | Claim lifecycle notifications go to relevant recipients | PASS |
| NOT-02 | Notifications | `test_new_report_creates_ranked_match_notifications_for_both_owners` | Eligible new match notifies both report owners with score | PASS |
| NOT-03 | Notifications | `test_notification_endpoints_require_authentication` | Notification endpoints require authentication | PASS |
| NOT-04 | Notifications | `test_notification_list_count_and_read_actions_are_recipient_scoped` | List/count/read actions are recipient-scoped | PASS |
| NOT-05 | Notifications | `test_notification_model_rejects_similarity_scores_outside_range` | Out-of-range similarity score rejected by constraint | PASS |
| NOT-06 | Notifications | `test_recovery_completion_notifies_both_parties_after_both_confirm` | Completion notification waits for both parties | PASS |
| NOT-07 | Notifications | `test_repeated_match_processing_does_not_duplicate_pair_notifications` | Repeated processing does not duplicate notifications | PASS |
| NOT-08 | Notifications | `test_same_type_resolved_candidates_and_below_threshold_do_not_notify` | Same-type/resolved/below-cutoff candidates do not notify | PASS |
| NOT-09 | Notifications | `test_users_are_not_notified_about_their_own_report_as_a_match` | Same reporter does not receive own-report match notification | PASS |

The matching API tests also exercise the Django-to-ML adapter and the actual
root-level matcher. The matching endpoint's score is a similarity score, not a
probability. The notification cutoff does not filter the suggestions endpoint.

## 4. Django and dependency checks

| Check | Actual result |
| --- | --- |
| Django system check | PASS — no issues identified |
| Migration consistency (`makemigrations --check --dry-run`) | PASS — no changes detected |
| Dependency consistency (`pip check`) | PASS — no broken requirements found |
| Schema changes applied to configured database | None |

The system/migration checks used a runtime-only SQLite `:memory:` override.
Existing migrations were not edited or applied to PostgreSQL. The backend test
runner did apply the existing migrations to its disposable in-memory test
schema.

## 5. Frontend and functional checks

Browser-based checks ran against a temporary local static HTTP server serving
the existing `Frontend/` directory. They did not call Django or make API
requests.

### Table F — Functional Test Cases

| Test ID | Feature | Test scenario | Expected output | Actual output | Status |
| --- | --- | --- | --- | --- | --- |
| UI-01 | Static site | Open existing landing page | Page loads and displays role choices | HTTP 200; title “CampusFind \| Choose Role”; role choices rendered | PASS |
| UI-02 | Role validation | Continue without selecting role | Prompt user to select role | “Please select your campus role first.” | PASS |
| UI-03 | Role navigation | Select Student and continue | Persist role and open account page | Navigated to login page; “student account” heading rendered | PASS |
| UI-04 | Registration client validation | Submit mismatched passwords | Show client-side validation error and remain on the form | “Passwords do not match.”; remained on the account page | PASS |
| UI-05 | Protected page guard | Open dashboard without an access/refresh token | Redirect to login | Redirected to existing login page | PASS |
| UI-06 | Mobile login layout | Inspect at 375 CSS-pixel viewport | No horizontal overflow | `clientWidth=375`, `scrollWidth=375` | PASS |
| UI-07 | JavaScript syntax | Run `node --check` on existing script | No syntax errors | Exit code 0 | PASS |
| UI-08 | HTML parsing | Parse all six existing HTML pages | All pages parse | All six parsed | PASS |
| FLOW-01 | Live authentication workflow | Register/login/logout two accounts; test expired/invalid backend sessions | Complete authenticated two-user workflow | Not run; would access/write configured database | NOT EXECUTED |
| FLOW-02 | Reports and suggestions UI | Create LOST/FOUND reports; inspect item details, filters, scores and explanations | Actual API-backed workflow succeeds | Not run; no live Django API/database session was authorized | NOT EXECUTED |
| FLOW-03 | Report management UI | Upload/display image; edit/delete as owner and deny other user | Owner succeeds; unauthorized action denied | Not run in browser; API upload/owner tests passed separately | NOT EXECUTED |
| FLOW-04 | Claims UI | Submit, approve/reject/cancel, confirm separately as both parties | Claim and item state follow recovery rules | Not run in browser; backend recovery API tests passed separately | NOT EXECUTED |
| FLOW-05 | Notifications UI | Observe new notifications, unread counts, single/all-read actions | Recipient isolation and read state work | Not run in browser; backend notification API tests passed separately | NOT EXECUTED |
| FLOW-06 | Mobile dashboard | Inspect dashboard filters/cards at mobile viewport | No horizontal overflow | Not run; dashboard is protected and no API was mocked or contacted | NOT EXECUTED |

These are not full end-to-end results. Backend API tests and static browser
checks are reported separately; the static UI check does not establish that
the frontend/API integration works in a live deployment.

## 6. Table G — Overall Test Summary

| Test category | Total | Passed | Failed | Not executed |
| --- | ---: | ---: | ---: | ---: |
| Existing ML unit tests | 8 | 8 | 0 | 0 |
| ML labelled benchmark decisions (reported separately from test suites) | 32 | 19 correct labels | 13 mismatches | 0 |
| Backend API regression tests | 44 | 44 | 0 | 0 |
| Django system and migration checks | 2 | 2 | 0 | 0 |
| Python dependency check | 1 | 1 | 0 | 0 |
| Frontend syntax and HTML checks | 7 | 7 | 0 | 0 |
| Static browser checks | 6 | 6 | 0 | 0 |
| Full live browser/API workflow | 0 | 0 | 0 | Not run |
| Configured PostgreSQL server checks | 0 | 0 | 0 | Not run |

There were no failed executed software tests. The 13 ML mismatches are
evaluation outcomes (false positives), not test-run failures. The full live
workflow and database-specific checks remain unresolved/unexecuted.

## 7. Limitations and unverified behavior

* SQLite in-memory tests validate Django/API behavior but do not validate
  PostgreSQL-specific SQL, constraints, or transaction/row-lock behavior.
* The configured PostgreSQL server was not connected to; its server version,
  migration state, connectivity, and existing data were not inspected.
* No live users, reports, claims, notifications, or media were created for
  browser integration, so no cleanup operation was needed.
* Frontend registration/login against Django, matching suggestion rendering,
  dashboard filters, report edit/delete, image display/upload, claims,
  notifications, expiry/refresh behavior, and mobile dashboard layout remain
  unverified in a live integration.
* Some requested scenarios have no dedicated existing backend test (for
  example, successful token refresh, invalid access JWT, the generic
  `?search=` filter (the named `name` filter is covered), an empty-match API
  result, actual browser logout, and live API behavior against PostgreSQL). No
  test was reported as passing for those scenarios.

## 8. Reproduction commands

Run commands from the repository root. The following test invocation overrides
the database **in the current Python process only**; it does not use
PostgreSQL:

```powershell
@'
import os, sys
sys.path.insert(0, os.path.abspath('backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'campusfind.settings'
import campusfind.settings as project_settings
project_settings.DATABASES = {
    'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}
}
import django
django.setup()
from django.core.management import call_command
call_command(
    'test',
    'accounts', 'items', 'matching', 'recovery', 'notifications',
    verbosity=2,
)
'@ | & .\.venv\Scripts\python.exe -
```

System and migration checks were run using the same in-process database override,
then:

```python
call_command('check', verbosity=2)
call_command('makemigrations', check=True, dry_run=True, verbosity=2)
```

Other commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s ml\tests -v
.\.venv\Scripts\python.exe -m ml.evaluate_model
.\.venv\Scripts\python.exe -m pip check
node --check Frontend\script.js
```

The local static browser server was started with
`.\.venv\Scripts\python.exe -m http.server 5500 --directory Frontend` and
stopped after browser checks.
