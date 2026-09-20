# Attack protocol

Written in English because the results feed straight into `threat-model.md`.

Run every attack exactly as written, even the ones expected to fail. A
defence that has never been attacked is an assumption, not a defence.

---

## Setup

**Devices**

- Mac: teacher screen, logged in, attendance session running
- Phone A: "the student in the room". Registered to a roster code.
- Phone B: "the student at home". Also registered, to a different code.

Both phones must already be registered before starting. Registration is not
what is being attacked here.

**Recording**

Screen-record both phones for the whole session (iPhone: Control Centre →
record button). One continuous recording per phone is easier than starting
and stopping between attacks.

Also screenshot the uvicorn or Render logs at the end. They show the
requests with timestamps, which is independent evidence of what happened.

**Before starting, write down**

- Date and time
- Which code is on which phone
- Where each phone physically is

---

## Attack 1 — delayed screenshot

*Claim being tested: an expired QR is useless.*

1. On phone A, screenshot the QR projected on the Mac.
2. Note the exact second.
3. Wait 30 seconds. Say it out loud on the recording so the delay is visible.
4. Send the screenshot to phone B.
5. On phone B, scan the screenshot from phone A's screen.

**Expected:** rejected, "Este codigo ya expiro".

**Record:** the message shown, and the delay between screenshot and scan.

---

## Attack 2 — live relay

*Claim being tested: nothing stops this. This is the finding.*

This is the most important of the three. It is expected to succeed, and its
success is what justifies the BLE phase.

1. Put phone B in another room, out of sight of the Mac.
2. Video call between phone A and phone B, or just carry phone B while phone
   A points at the screen — whatever simulates a student relaying the QR in
   real time.
3. Phone A shows the live QR to phone B through the call.
4. Phone B scans it from the video, inside the 10-second window.

**Expected:** attendance recorded. The system cannot tell the difference.

**Record:** the success screen, and how many attempts it took to hit the
window. If it takes several tries, that is a finding too: the attack works
but is not effortless.

**Also measure:** how long the whole relay took. If it takes a student 25
seconds of fiddling to mark a friend present, that is a different threat
than if it takes 3.

---

## Attack 3 — two students from one phone

*Claim being tested: one phone belongs to one student.*

1. On phone A, already registered, open `/register`.
2. Try to register with a second, unused roster code.

**Expected:** rejected, "Este telefono ya esta registrado", showing the name
it already belongs to.

**Record:** the message, including the name shown.

---

## Attack 4 — direct access to the QR endpoint

*Claim being tested: the QR only exists where the teacher projects it.*

Already done once, but repeat it properly and keep the evidence.

1. On phone B, in a private tab, open `<url>/qr/<session id>` directly.
2. Try session ids 1, 2 and 3 as well, since they are guessable.

**Expected:** 401, no image.

**Record:** the response, and a note that before authentication this returned
a valid nonce to anyone.

---

## Results table

Fill this in as you go, not afterwards from memory.

| Attack | Expected | What happened | Evidence |
|---|---|---|---|
| 1. Delayed screenshot | rejected | | |
| 2. Live relay | succeeds | | |
| 3. Two students, one phone | rejected | | |
| 4. Direct QR endpoint | 401 | | |

---

## After

**Update `threat-model.md`.** Attack 2 currently says "I have not tested this
attack yet". Replace that with what actually happened, including how long the
relay took. If it succeeded, say so plainly.

**Add a `experiments.md` entry**: what you built the setup out of, what you
tested, what failed, what you decided.

**Save the recordings** in `media/`. Trim them: a 4-minute video of you
fumbling with two phones is not evidence, a 15-second clip of the rejection
message is.

**One warning.** If attack 2 fails — if the relay does not work — do not
write that the system prevents it. It would mean the attempt was too slow,
not that the defence exists. Say what you observed and what you could not
conclude from it.
