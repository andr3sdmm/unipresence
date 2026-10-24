# Pilot plan — classes with version 2.1

How we run and measure a real class with the app. We follow this same plan in every measured class, so the numbers can be compared.

## What we want to know

1. Does the QR take less of the professor's time than calling names, when both are measured the same way, from start to finish?
2. Does every student who is in the room end up marked, and only them?
3. What does the professor still have to do by hand?

## Before class

- The class list (Banner, with the 9-digit codes) is uploaded and the right groups are checked.
- Students who were pending from earlier classes are validated with "Validar con la lista".
- Nothing in the app changes on the day of a measured class. A change in the middle would make the numbers impossible to compare.

## During class

The order matters: first the QR, then the roll call. Calling names afterwards gives an independent check of who was really in the room.

**With the QR.** The server saves the time the session opens, every check-in to the second, and the time it ends. The professor only has to:

1. Tap "Tomar asistencia" when she is ready to start, not before.
2. Check "Por revisar" and mark by hand whoever needs it.
3. Tap "Terminar asistencia" as soon as she finishes reviewing. That is the end of the QR time.

**By hand.** A stopwatch or a video from the moment she opens the list until she finishes correcting it. She marks who answers.

**On paper:** start and end time of the roll call, students who arrived between the two methods, and anything that went wrong (the page did not load, someone could not scan, questions students asked).

## Right after class

A five-minute interview with the professor:

1. How long does the roll call usually take in this class? Was today a normal day?
2. Which part of the QR took the most time?
3. Could you tell quickly who was missing and who needed review?
4. Did any student fail to check in? Why?
5. If you only used the QR tomorrow, what would you still need the paper list for?

## What we compare

| Measure | QR | By hand |
|---|---|---|
| Total time | session opened → session ended (server) | list opened → last correction (stopwatch or video) |
| Capture time | first check-in → last check-in (server) | first name → last name |
| Review time | last check-in → session ended | — |

And who was present, crossing both methods:

| | Answered the roll call | Did not answer |
|---|---|---|
| Checked in with the QR | correct | check: arrived late, or marked from outside? |
| Did not check in | check: why not? | absent |

Unclear cases stay in their own group instead of being forced into one.

## What goes into the repository

- The anonymous timing export ("Tiempos (anónimo)"), which only has seconds.
- The numbers and the interview answers, without names.
- Screenshots only with every name and code covered.

The report with names, the class list and any video stay with the professor and never go into the repository.

## If something fails

- **A student cannot check in:** do not debug it in class. Write down what the screen said, mark them by hand, keep going.
- **The page does not load:** wait a minute. If it still fails, take attendance on paper and write it down as a result, not as a failure.
- **The browser closes:** log in again; the session is still under the class history.
