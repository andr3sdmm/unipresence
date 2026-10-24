# Threat model — UniPresence

## 1. The attacker

The attacker can be a student who is not physically in the classroom but wants to be marked present. They may have access to a phone, WhatsApp or another messaging app, and a friend who is actually in the classroom.

The attacker could also be any person who obtains the URL of the teacher screen. In the initial version of the system, this attacker did not need to be a student or have someone inside the classroom because the teacher screen did not require authentication. The teacher screen and the related QR endpoint are now protected by the authenticated teacher session.

## 2. What we are trying to prevent

We want to prevent students who are not physically present in class from successfully registering attendance.

## 3. Attacks considered

### Old QR / screenshot

A student could take a screenshot of the QR code and send it to someone who is not in class. The short expiration time helps prevent this because an old code stops working quickly. During development, I saw the message "Este código ya expiró" after taking too long to enter a code. However, I have not formally tested this attack using two different phones yet.

### Registering with someone else's code

A student could get another student's code and try to register attendance with it. Before the assigned-code system was added, nothing prevented this because anyone could register using any valid code.

**Version 1.** Each student received a secret code privately on a printed slip. Security depended on keeping that code secret. If an attacker got another student's code before the real owner registered, the attack could still work, but it became noticeable: when the real student tried to register, the code was rejected as already used.

**What the pilot showed.** On September 22, 2026, that same rejection hit 7 honest students. Their registration was stored in a browser cookie; they had registered inside WhatsApp's browser and then checked in from Safari, so the system treated them as new and refused their own code. A rule meant to stop impostors was locking out present students.

**Version 2.** Students bind their phone with their university code, which is not secret. A student who knows a classmate's code can therefore move that classmate's registration to another phone. The system allows this on purpose, but never silently: every device change is recorded, counted on the teacher's screen while class runs, and marked in the export, together with the browser used. The attack is not prevented; it is made visible to the person who can act on it.

### Registering several people from one phone

One student could try to register attendance for several classmates using the same phone. Version 1 prevented this by associating the device with the first registered student. I tested this attack, and the system displayed: "Este teléfono ya está registrado — Andres Marino." In version 2 this cannot happen: a browser the app already knows only marks for its owner, and its check-in page has no field to type another code (`test_known_browser_cannot_mark_for_a_friend`).

### Device binding narrower than a device

Found in the September 22 pilot, not in testing. Binding a student to a "phone" through a cookie actually binds them to one browser on that phone. Messaging apps open links in their own built-in browser, so a single phone can look like several devices. This caused false rejections rather than fraud, but it means the binding is weaker evidence of "same phone" than it appears.

### Live relay over video call

A student outside the classroom could communicate live with a friend inside the classroom and receive the current attendance information before it expires. I have not tested this attack yet, and currently I expect that it could succeed.

### Unauthenticated teacher screen

The teacher screen originally did not require a password or any other form of authentication. Anyone who had the link could access it, start an attendance session, manually mark students from the course list as present, and download the CSV containing student names and attendance information.

Nothing prevented this attack when it was discovered. I found the vulnerability while writing this threat model rather than through a formal test of the system.

I fixed it the same day by adding password authentication to the teacher screen. The password is stored as an environment variable and is never included in the repository.

While implementing this protection, I discovered a more serious related vulnerability: the `/qr/{session_id}` endpoint was also publicly accessible and returned a valid nonce to anyone who requested it. This meant that a student who had already registered their device could obtain the current nonce remotely and mark themselves present from home, without needing an accomplice in the classroom or access to the projected QR code.

Both the teacher interface and the QR endpoint are now protected by the same authenticated teacher session.

## 4. Alternatives evaluated and rejected

### GPS geolocation

GPS was considered as a way to verify that students were physically near the classroom, but it was rejected for three main reasons. First, GPS does not provide enough precision indoors to reliably determine whether a student is actually inside a specific classroom. Second, a student could fake their location using a free location-spoofing app. Third, collecting students' location data, even only at the moment of check-in, would go against the privacy-focused design of the system.

## 5. Open risks

The system still has some risks that it does not completely solve. A student may be able to relay attendance information live to someone outside the classroom.

University codes are not secret, so in version 2 a student can move a classmate's registration to their own phone. The system records and displays this instead of preventing it. Detection depends on the teacher looking at the device-change count and the export.

Version 1 used a shared teacher password, which could not identify which teacher performed an action. Version 2 replaces it with individual teacher accounts, so actions can be associated with a specific account. Anyone who knows the optional signup code can still create a teacher account; the signup code is a shared secret. Integrating the university's institutional login would close this gap and is outside the scope of the current prototype.

Version 1 ran on the free Render plan, which put the service to sleep after inactivity and lost stored data during the September 22 pilot. Version 2 stores all data in Postgres, so data survives restarts.
