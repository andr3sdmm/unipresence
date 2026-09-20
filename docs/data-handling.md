# Data handling — UniPresence

## What the system stores

UniPresence currently stores only the information needed to register students and record attendance:

- **Student code:** identifies the student during registration.
- **Student name:** obtained from the course list and used to identify attendance records.
- **Device identifier:** a randomly generated identifier used to bind a browser to one student. It is not an IMEI, hardware identifier, phone number, or other identifier obtained from the device itself.
- **Registration/check-in timestamp:** records when an attendance action occurred.
- **Attendance method:** records whether attendance was registered through the QR flow or manually by the professor.
- **Registration context:** records whether the action occurred during pre-class registration or classroom attendance.

The roster is handled in two parts. `roster.example.csv` is committed to this repository and contains fictional names created only for testing. The real course roster lives in `roster.csv`, which is listed in `.gitignore` and is never committed.

In production the real roster is uploaded to Render as a secret file. Render places it next to the application when the service deploys, so it never passes through the public repository.


## What is stored on the student's device

UniPresence stores a cookie on the student's device after registration. The cookie contains only a randomly generated device identifier. It does not contain the student's name, student code, or any hardware identifier from the phone.

The cookie is marked `HttpOnly`, which prevents JavaScript running on the page from reading it, and it is configured to remain on the device for one year.

This cookie allows the server to recognize that a particular browser has already been registered to a student. If the student clears their browser data, deletes the cookie, changes browsers, or moves to another device, that binding is lost and the student must register again.

The server stores the relationship between the random device identifier and the student record; the cookie itself only carries the random identifier.


## What the system does not store

UniPresence does not store:

- GPS coordinates or other location data
- Biometric information
- Photographs
- IP addresses associated with individual students
- Browsing history
- IMEI numbers or other hardware identifiers from students' phones

The system is intentionally designed to avoid collecting information that is not necessary for attendance verification.


## Who can access it

In the current version, attendance information and teacher functions are accessible only after entering the shared teacher password.

Earlier versions did not enforce this restriction. The teacher interface and QR endpoint were initially accessible to anyone who had the corresponding URL. This was identified during security review and corrected by placing both endpoints behind the authenticated teacher session.

The current shared-password approach limits access, but it does not identify which individual professor performed an action if multiple people know the password.


## How long it is kept

The prototype currently has no automatic data-deletion or retention policy.

At the same time, the current free Render deployment does not provide reliable persistent storage for this data. Stored information is lost whenever the service restarts or redeploys, and a redeploy is triggered by any change to the code or the configuration. In practice this means attendance records have to be exported immediately after each class.

These are separate limitations: the application does not intentionally delete records after a defined period, but the current hosting environment also does not guarantee that they will remain stored.

The device cookie is configured to remain on the student's browser for one year unless the student deletes it earlier by clearing their browser data.


## Legal context

UniPresence would handle personal data in Colombia and would therefore need to be evaluated under Colombia's personal-data protection framework, including **Law 1581 of 2012**.

Among other principles, the law requires personal-data processing to have a legitimate and communicated purpose, generally requires prior and informed authorization from the data subject, restricts access to authorized persons, and requires appropriate measures to protect records against unauthorized access, loss, alteration, or fraudulent use.

It also gives data subjects rights regarding their personal information, including the ability to know, update, and correct their data.

This prototype has not undergone a formal legal or institutional compliance review and should not be considered production-ready based on this document alone.


## What a real deployment would need

Before UniPresence could be used with real university student records, it would need at least:

- A defined data-retention and deletion policy
- An appropriate process for informing students and obtaining any authorization required for processing their personal data
- Persistent and backed-up database storage
- Universidad del Norte institutional authentication instead of a shared teacher password
- The real course list stored securely outside the public source-code repository
- Procedures allowing students to access or correct their personal information when required
- A process for handling students who change devices, browsers, or clear their browser data
- Institutional review of the system's privacy, security, and data-handling practices

A production deployment would also need to define who is responsible for the data, who is authorized to access it, why each field is collected, and how incidents or unauthorized access would be handled.