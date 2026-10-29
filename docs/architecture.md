# Architecture — UniPresence version 2.1

How the pieces fit together, and what happens between the moment a student points the camera at the projector and the moment the professor sees them as present. Everything here is in `main.py`; the numbers (10 s, 20 s, 3 min) are constants at the top of that file.

## The pieces

```mermaid
flowchart LR
    subgraph Room["Classroom"]
        P["Professor's computer<br/>live screen + projector"]
        S["Student's phone<br/>camera + browser"]
    end
    subgraph Render["Render (paid plan, always on)"]
        A["main.py<br/>FastAPI app"]
    end
    subgraph Neon["Neon (AWS Oregon)"]
        D[("Postgres")]
    end
    P -- "new QR every 10 s<br/>live counts every 3 s" --> A
    S -- "scan, tap Aceptar" --> A
    A -- "read and write" --> D
    C["cron-job.org"] -. "opens /healthz every 10 min" .-> A
```

- **No app to install.** The student only uses the phone camera and the browser it opens.
- **The server holds the truth.** The QR only carries a short random code (a nonce). Whether it is valid, who the student is and whether they are on the list is decided on the server, never on the phone.
- **Postgres outside the server.** Version 1 kept its data in a file inside Render and lost it on September 22. Now Render can restart without touching anything.

## One check-in, step by step

```mermaid
sequenceDiagram
    participant Prof as Professor's screen
    participant App as main.py
    participant DB as Postgres
    participant Phone as Student's phone

    Prof->>App: GET /session/{id}/qr (teacher only)
    App->>DB: save nonce, valid 20 s
    App-->>Prof: QR image (a new one every 10 s)
    Phone->>App: camera opens /checkin?s={id}&n={nonce}
    App->>DB: does the nonce exist, and is it still valid?
    alt expired or unknown
        App-->>Phone: "Ese QR ya venció", counted in the report
    else valid
        App->>DB: one-use ticket, valid 3 min, and how old the QR was
        App-->>Phone: class name + Aceptar (plus code, name and consent the first time)
        Phone->>App: POST /checkin/accept with the ticket and the device cookie
        App->>DB: ticket locked and used once, student found by cookie or code
        App->>DB: attendance row + any alerts for "Por revisar"
        App-->>Phone: green receipt with a live clock and a receipt code
        Prof->>App: every 3 s, GET /session/{id}/state
        App-->>Prof: present count, missing, last check-ins, alerts
    end
```

Why two steps (nonce, then ticket): the nonce has to die fast, so a photo of the QR is useless a few seconds later. But a student typing their code for the first time needs more than 20 seconds. So the scan is checked right away and turned into a ticket that gives them 3 minutes to tap Aceptar. That split came from Day 1, when the QR expired while I was typing.

## What decides "present", "pending" or "review"

```mermaid
flowchart TD
    A["Valid ticket + Aceptar"] --> B{"Does the server know<br/>this browser's cookie?"}
    B -- yes --> C{"Is that student<br/>on this class list?"}
    C -- yes --> P["Present"]
    C -- no --> Q["Pending + alert:<br/>not on the list"]
    B -- no --> D{"Consent checked<br/>and code typed?"}
    D -- no --> R["Nothing is saved.<br/>Asked again."]
    D -- yes --> E{"Is the code or username<br/>on the list?"}
    E -- yes --> F{"Was that code linked<br/>to another browser?"}
    F -- no --> P
    F -- yes --> G["Present + alert:<br/>device change, recorded"]
    E -- no --> H["Asks to check the code,<br/>then for the name"]
    H --> Q
```

This is for a class with a list. In a class without one (a conference, or a class whose list has not arrived), everyone who checks in waits as pending until the professor approves them or uploads the list and validates them.

Every alert goes to "Por revisar" on the professor's screen and in the report: a code that moves to another browser, three or more new phones from the same browser and system within a minute, a code that is not on the list, a link opened inside WhatsApp or Instagram. They are leads, not proof. The professor confirms or rejects each one, and the decision is written next to the alert, which is never deleted.

Two rules never bend:

1. **A known browser only marks for its owner.** Whatever code is typed is ignored, so a student cannot mark a friend from their own phone.
2. **A present student is never refused.** That is what locked 7 students out on September 22. A device change is allowed and made visible instead.

## Data model

```mermaid
erDiagram
    TEACHERS ||--o{ COURSES : owns
    COURSES ||--o{ ENROLLMENTS : has
    STUDENTS ||--o{ ENROLLMENTS : "is in"
    COURSES ||--o{ SESSIONS : "one per class"
    SESSIONS ||--o{ NONCES : "QR codes"
    SESSIONS ||--o{ SCAN_TICKETS : "valid scans"
    SESSIONS ||--o{ ATTENDANCE : records
    STUDENTS ||--o{ ATTENDANCE : "checks in"
    STUDENTS ||--o{ DEVICE_CHANGES : "moves browser"
    SESSIONS ||--o{ EVENTS : "alerts and logs"
```

- A **student** is one row shared by all their classes, even with different professors, so a student in six classes links their phone once. When a new professor uploads a list, the app finds the students it already knows by their code or username, and their phones just tap Aceptar. If the new list uses a different number for someone (like Brightspace's internal id), that student checks in as pending and the professor validates them by name. Each professor still only sees the students in their own classes.
- An **enrollment** says whether they are approved for that class or pending, and which group (NRC) they are in.
- **Attendance** is unique per session and student, so scanning twice gives back the same receipt instead of a second row.
- Deleting a class or a session deletes everything under it.

What each field is, and why it is stored, is in [`data-handling.md`](data-handling.md). What can still go wrong is in [`threat-model.md`](threat-model.md).

## What is not in this design

- **Location or Bluetooth.** Nothing proves the phone is in the room; a live relay of the current QR still works (tested on October 25). GPS is not precise indoors and Bluetooth would need an app or a beacon, so both were rejected (`threat-model.md`, section 4).
- **The university's login.** Professors have their own accounts.
- **An app on the phone.** On purpose: every extra step lost students in the first pilot.
