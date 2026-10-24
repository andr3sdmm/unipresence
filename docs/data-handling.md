# Data handling — UniPresence

This describes version 2.1, the one used in the October 2026 classes.

## What the system stores

For each student:

- **Student code or username:** the code the student types the first time, or their institutional username (the part of the email before the @). The full email address is never saved.
- **Name:** from the class list, or typed by the student in a class without a list. The surname is kept separately when the list has it, so reports can be sorted by last name.
- **Group:** the group or NRC from the list, when the list has it.
- **Device identifier:** a random code created by the server and saved in a cookie, used to recognize the browser the student links. It is not the phone number, an IMEI or anything read from the phone.
- **When they accepted the data policy.**

For each check-in:

- The time, and whether it was done with the QR or marked by hand by the professor.
- The browser, the phone's operating system, and whether the link was opened inside an app such as WhatsApp. This is how the system notices patterns like several new phones linked in a few seconds.
- How old the QR was when it was scanned and how long the student took to tap "Aceptar". These are for the relay test in `docs/attack-protocol.md`.
- A receipt code, the same one the student sees on their phone.

For each change of phone or browser, and for each alert under "Por revisar": what happened, when, and the professor's decision.

For each professor: email, name, institution and a password stored only as a bcrypt hash.

## What the system does not store

- Location (GPS or any other kind)
- Photos or biometric data
- Phone numbers, IMEI or other hardware identifiers
- IP addresses
- Full email addresses of students

## What is stored on the student's phone

One cookie, `device_id`, with the random identifier and nothing else. It is `HttpOnly` (JavaScript on the page cannot read it) and lasts one year unless the student clears their browser data. If they do, or change browsers or phones, they type their code again; the change is allowed and recorded.

## Consent

The first time a phone is linked, the student has to check "Acepto la política de tratamiento de datos" before anything is saved. The policy is at `/privacidad`, in Spanish: what is saved, what is not, what for, who sees it, and that the student can ask to see, correct or delete their data. If they do not accept, nothing is saved and the professor can mark them by hand. This follows the prior, informed authorization that Colombia's Law 1581 of 2012 asks for.

## Who can access it

- **Professors:** each one has their own account and only sees their own classes. Sessions expire after 12 hours.
- **Students:** only see their own receipt on their own phone.
- **Me:** as the owner of the database, I can technically see everything stored in it. That is a real limitation of a student project; a university deployment would need the database to be run by the university.

## Where it is stored and for how long

Since October 18, 2026, everything is stored in a Postgres database on Neon, outside the Render server, so restarts and new deploys no longer erase anything (that is what happened on September 22). The database is in Neon's AWS region in Oregon, United States. Under Law 1581, storing Colombian personal data in another country is an international transfer, which a real deployment would have to review.

There is no automatic deletion yet. Data stays for the whole semester, until the professor deletes it:

- Deleting a class deletes its sessions, its attendance and its alerts.
- Deleting a session (for example, a test) deletes its attendance, and also the students who only existed because of that test.
- Removing a student from their only class deletes that student's data.
