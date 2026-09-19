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

Now, each student receives a secret code privately. The security of this system depends on keeping that code secret, not just on the code being single-use.

If an attacker gets another student's code before the real owner registers, the attack can still work. The single-use system does not prevent this situation, but it makes the attack noticeable because when the real student tries to register, the code has already been used and will be rejected.

### Registering several people from one phone

One student could try to register attendance for several classmates using the same phone. The system prevents this by associating the device with the first registered student. I tested this attack, and the system displayed: "Este teléfono ya está registrado — Andres Marino."

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

The assigned-code system also depends on how the codes are distributed. If the professor reads the codes aloud or sends them to a class WhatsApp group, the protection provided by secret individual codes can fail. This means part of the system's security depends on a step that happens outside the application.

Teacher authentication also has an important limitation. The current prototype uses a shared password, so it can verify that someone knows the teacher password but cannot identify which individual teacher performed an action. If three people know the password, for example, there is no way to determine which one manually marked a student as present or performed another action.

If the shared password is leaked, it must be changed and the new password must be communicated to every authorized user. A stronger solution would be to integrate UniPresence with Universidad del Norte's institutional authentication system so that each professor has an individual account and actions can be associated with a specific user. This is outside the scope of the current prototype.

Finally, the free Render plan can put the service to sleep after inactivity, which means the first request may take almost a minute to respond. This is not a security vulnerability, but it is an operational limitation of the current prototype.