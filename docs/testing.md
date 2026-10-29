# Testing — UniPresence version 2.1

There are 50 automated tests in `tests/test_v2.py`. They run against a real Postgres database, because the things that matter most (two requests racing for the same student, a ticket used twice) are decided by the database. GitHub runs all of them on every commit (`.github/workflows/tests.yml`), so a change that breaks one of these promises shows up as a red cross next to the commit.

Each test is named after the promise it checks. This page groups them by what they protect.

## The QR and the timing

| Promise | Test |
|---|---|
| A photo of an old QR does not work, and the attempt is counted | `test_expired_qr_is_rejected_and_counted` |
| One scan can only be used once | `test_ticket_cannot_be_used_twice` |
| Only the logged-in professor can get the QR | `test_qr_is_teacher_only` |
| A class that ended accepts nothing new | `test_closed_class_accepts_nothing` |
| Scanning again shows the same receipt, not a second attendance | `test_second_scan_same_class_shows_existing_receipt` |
| How old the QR was is kept after class, and the timing export has no names | `test_timing_is_kept_after_class_ends_and_export_is_anonymous` |
| An expired scan from a known phone names the student, and the professor can mark them after class | `test_expired_scan_names_a_known_phone_and_the_professor_can_mark_after_class` |

## Identity and phones

| Promise | Test |
|---|---|
| First time: type the code once. After that: one tap | `test_first_checkin_then_one_tap` |
| A phone that already belongs to someone cannot mark for a friend | `test_known_browser_cannot_mark_for_a_friend` |
| A friend's code typed in a private window is allowed but goes to review | `test_private_window_with_friends_carne_goes_to_review` |
| Unlinking a phone lets the real student link without an alert | `test_unlink_phone_lets_the_real_student_link_without_alert` |
| The professor can fix a mistyped code | `test_professor_corrects_a_mistyped_carne` |
| If the right code already exists, the two records are merged | `test_mistyped_carne_merges_into_the_listed_student` |

## Nobody present is locked out

This is the rule that came from the September 22 pilot, where 7 present students could not check in.

| Promise | Test |
|---|---|
| A code that is not on the list is asked to be checked, then goes to review | `test_carne_not_on_list_asks_for_name_then_goes_to_review` |
| A known phone that is not on this list is pending, not refused | `test_known_phone_not_on_this_list_is_pending_not_refused` |
| A class without a list builds itself and waits for approval | `test_class_without_list_builds_itself_and_needs_approval` |
| A known phone in a class without a list is added as pending | `test_class_without_list_adds_a_known_phone_as_pending` |
| Attendance taken without a list is validated when the list arrives | `test_attendance_without_list_is_validated_when_the_list_arrives` |

## Class lists

| Promise | Test |
|---|---|
| Names with commas are not broken | `test_roster_paste_keeps_names_with_commas` |
| Excel files and CSV with semicolons are read | `test_roster_from_excel_and_semicolon_csv` |
| Brightspace: students are found by the username they know | `test_brightspace_list_matches_the_username_students_know` |
| Brightspace: the # before usernames is ignored | `test_brightspace_hash_prefix_is_ignored` |
| Brightspace: several groups in one file | `test_brightspace_export_with_several_groups` |
| Banner: codes, names and groups (NRC) | `test_banner_export_with_groups` |
| A national ID column is never used as the key | `test_national_id_column_is_never_used_as_key` |
| A second list with other codes updates students instead of duplicating them | `test_second_list_with_other_codes_updates_instead_of_duplicating` |
| Today's groups can be chosen when a class has several | `test_choose_todays_groups_when_class_has_several` |
| Groups can be fixed after uploading too many | `test_fix_groups_after_uploading_too_many` |
| Groups are chosen on the class page, and removing one is tucked away | `test_groups_are_chosen_on_the_class_page_and_removal_is_tucked_away` |
| A list that only has codes asks students for the code, not the username | `test_list_with_only_codes_asks_for_the_code` |
| A student approved by hand can still be joined to their row on the list | `test_a_username_approved_by_hand_can_still_be_joined_to_its_list_row` |

## Alerts under "Por revisar"

| Promise | Test |
|---|---|
| Several new phones in a row from the same browser are flagged | `test_burst_of_new_links_is_flagged` |
| The alert names the students and the report sorts by surname | `test_rename_class_sort_by_surname_and_burst_names_students` |
| A link opened inside Instagram is flagged | `test_link_opened_inside_instagram_is_flagged` |
| A rejected check-in stays on record with the decision | `test_professor_rejects_a_flagged_checkin_and_it_stays_on_record` |
| Alerts about one student come before general notices | `test_report_lists_alerts_about_one_student_before_the_general_notice` |
| Old "not on the list" alerts get the student's name back | `test_old_not_on_list_alerts_get_their_name_back` |

## Privacy and safety

| Promise | Test |
|---|---|
| Professors cannot see each other's classes | `test_teachers_cannot_see_each_others_classes` |
| The projected screen shows no names, and the report shows the alerts first | `test_projected_screen_hides_names_and_report_shows_alerts_first` |
| Nothing is stored without accepting the data policy | `test_nothing_is_stored_without_accepting_the_data_policy` |
| A name typed by a student cannot run code on the professor's page | `test_student_typed_name_is_escaped_on_teacher_pages` |
| A name that starts with = cannot become an Excel formula | `test_a_typed_name_cannot_become_an_excel_formula` |
| Deleting a class needs its name typed, and keeps students shared with other classes | `test_delete_class_needs_its_name_and_keeps_shared_students` |
| Deleting a test session removes the data it created | `test_delete_one_test_session_and_the_data_it_created` |
| Removing a student from their only class deletes their data | `test_removing_a_student_from_their_only_class_deletes_their_data` |

## Reports and pages

| Promise | Test |
|---|---|
| Marking by hand works and shows up in every report format | `test_manual_mark_and_reports` |
| History has its own page, separate from the list | `test_history_has_its_own_page_and_cards_link_both` |
| A student who arrives late can be marked present with a note, and the timing export has the seconds since the start | `test_professor_marks_a_late_student_with_a_note_and_timing_has_seconds` |

## Many students at the same time

Added on October 24, before the first class of about 100 students.

| Promise | Test |
|---|---|
| 30 students tapping Aceptar at the same instant: 30 receipts, 30 rows, none lost or doubled | `test_a_whole_class_tapping_at_once_loses_and_doubles_nobody` |
| Tapping Aceptar twice at the same instant creates one attendance | `test_double_tap_on_aceptar_creates_one_attendance` |

The tests use a simulated client. To check a real server, `analysis/load_test.py` starts a local server with an empty database and sends real HTTP requests from one thread per student, all released at the same instant, each with its own cookies, typing its code for the first time.

Results on October 24 (local server and local Postgres, one run each):

| Students at once | Receipts | Attendance rows | Median response | Slowest |
|---|---|---|---|---|
| 100 | 100 | 100 | 0.12 s | 0.23 s |
| 300 | 300 | 300 | 0.41 s | 0.88 s |

And two taps on Aceptar at the same instant with the same ticket: one receipt, one refusal ("Ese escaneo ya se usó"), one attendance row.

What this does not show: the real server is on Render and the database is on Neon, so every request also travels over the internet. Real students also do not all tap at exactly the same instant. This test is the harder case for the database and the easier case for the network.

## What is not tested automatically

- A live relay of the current QR (someone sends it to a friend at home). It works; that is the main open risk. It was tested by hand on October 25, 2026, following `attack-protocol.md`: 5 out of 5 relays worked.
- Real phones and real browsers. Covered by the classroom pilots in `experiments.md`.

## Running them

```bash
pip install -r requirements.txt -r requirements-dev.txt
TEST_DATABASE_URL="postgresql://..." pytest -q
```

Use an empty database the tests are allowed to wipe, never the production one.
