# UniPresence

Privacy-preserving physical presence verification for large classrooms.

## The problem

Some Medicine courses at Universidad del Norte have hundreds of students, while the university requires professors to record attendance. Calling students one by one can take a significant amount of class time, so in practice attendance may not always be recorded.

The challenge is not simply digitizing an attendance list. It is verifying that a student is physically present in the classroom without collecting sensitive data such as their location.

## How it works

Before class, each student registers once using a private code assigned to them. This binds their phone to their student identity without exposing the full course list.

When class begins, the professor starts an attendance session and the projector displays a QR code that changes every 10 seconds. A registered student points their phone camera at the QR code without installing an app or entering information again.

The server checks that the nonce contained in the QR code exists, has not expired, and that the phone is already associated with a registered student before recording attendance.

## What is built

The current prototype includes:

- A QR code that rotates every 10 seconds
- One-time student registration using privately assigned codes
- A two-step registration and attendance flow
- Phone-to-student binding
- Manual attendance override for professors
- Attendance export to CSV
- Password authentication for the teacher interface and QR endpoint
- Deployment on Render

## What is not built yet

The current prototype does not yet include:

- BLE-based proximity verification, which would provide stronger evidence that a device is physically inside the classroom
- Protection against live relay attacks, such as someone sharing the current QR information through a video call
- Universidad del Norte institutional authentication for professors
- Course-list upload through the teacher interface; the current list is loaded from a file in the repository
- Persistent database storage; on the current free Render deployment, stored data can be lost when the service restarts

Because BLE verification is not implemented yet, the current prototype should not be treated as proof of physical presence under every attack scenario.

## Security

UniPresence is designed to reduce simple forms of attendance fraud without collecting student location data. Rotating nonces limit the usefulness of old QR codes, private student codes control initial registration, phone-to-student binding prevents one device from registering multiple students, and teacher-only endpoints require authentication. However, the prototype does not prevent every attack: live relay remains possible, private codes depend on secure distribution, and the current shared teacher password does not provide individual accountability. The full security analysis, including vulnerabilities discovered during development and the alternatives considered, is documented in [`docs/threat-model.md`](docs/threat-model.md).

## Running it locally

Clone the repository:

```bash
git clone https://github.com/andr3sdmm/unipresence.git
cd unipresence
```

Create and activate the virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Set the teacher password and start the server:

```bash
TEACHER_PASSWORD="your-password" uvicorn main:app --reload
```

## Project log

Development decisions, tests, failures, and changes are documented in [`docs/experiments.md`](docs/experiments.md).

## A note on how this was built

AI tools were used to write the application code under my direction. I defined the problem, made the design decisions, tested the system, and analyzed its security behavior.

During testing, I independently found a problem with the manual attendance flow. Three additional security weaknesses were identified during an AI-assisted review of the design, including misuse of student codes and initially unprotected teacher and QR endpoints. I then incorporated the findings into the design and tested the resulting changes.

I wrote the project log and threat model to document the development process, including what worked, what failed, what was changed, and which risks remain open.