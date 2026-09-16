# AttendAI — Attendance Through Repeated Temporal Observation

A 24-hour hackathon MVP that rethinks classroom attendance: instead of marking a
student present from a single face-recognition hit, AttendAI watches the
classroom at several points across a lecture and requires **repeated,
temporal evidence of presence** before calling someone PRESENT.

> **The idea in one line:** single-frame face recognition can be unreliable.
> Five independent glances across a lecture, with a 3-out-of-5 threshold, are
> far more trustworthy — and every uncertain case is handed to the teacher,
> never silently guessed at.

---

## 1. Problem

Traditional camera-based attendance tools take one snapshot, run face
recognition once, and mark students present or absent from that single
frame. A single frame is fragile: a student looking down, a bad angle, poor
lighting, or a moment of occlusion can flip the result — and there is no way
to tell "this student is genuinely absent" apart from "the camera just
missed them for a second."

## 2. Solution

AttendAI samples the room **multiple times** during a lecture (5 snapshots
by default) and only marks a student **PRESENT** if they were confidently
recognized in at least a configurable minimum number of those snapshots
(3 by default). Anyone below that threshold — including a student never
detected at all — is flagged **NEEDS REVIEW** for the teacher, never
auto-marked "absent."

```
Single-frame recognition  →  can be unreliable
Repeated observations     →  temporal presence evidence
5 snapshots, 3+ required  →  PRESENT
below the threshold       →  NEEDS REVIEW (teacher decides)
```

## 3. Features

- **Student enrollment** — capture 2+ face photos (upload or webcam), compute
  and store a face template (not raw photos).
- **Class configuration** — lecture duration, number of snapshots, minimum
  observations required (2+, enforced), all adjustable per class.
- **REAL and DEMO mode** — REAL mode spreads snapshots across the actual
  lecture length; DEMO mode compresses the identical schedule and logic into
  ~90 seconds so the whole flow can be shown to judges without waiting 50
  minutes. The attendance *result* is never shortcut — only the wait time is.
  Snapshot timing is randomly jittered per session (not fixed 10/30/50/70/90%
  marks) so it can't be learned and gamed — see §11.
- **Live snapshot capture** — from a laptop webcam or an uploaded classroom
  video, with bounding boxes, names, and match scores drawn on each frame.
  Minimum detectable face size is a live slider on the Start Class page, so a
  wider/further-back camera framing can be accommodated without editing code.
- **Temporal attendance engine** — the 3-of-5 rule, applied to every enrolled
  student in the class roster, including those never observed at all.
- **Teacher dashboard** — live Present/Needs-Review/Unknown-face counts, a
  status breakdown chart, and per-student detail table.
- **Student timeline** — a snapshot-by-snapshot ✓/✗ view per student, with a
  one-click manual resolution control for review cases.
- **Attendance history** — browse all past sessions and their outcomes.
- **CSV export** — `Student ID, Name, Class, Observed, Total Snapshots,
  Coverage, Status`.
- **Responsible-AI guardrails** baked in throughout (see §7).

## 4. Architecture

```
attendai/
├── app.py                  # Streamlit entry point, navigation, DB init
├── config.py                # every tunable constant lives here
├── requirements.txt
├── pytest.ini
│
├── ai/
│   ├── detector.py           # face detection (OpenCV Haar Cascade)
│   ├── embeddings.py          # face "template" via grid LBP histograms
│   └── recognizer.py          # chi-square-distance identity matching
│
├── camera/
│   ├── webcam.py              # laptop webcam capture (graceful failure)
│   └── video.py               # pre-recorded classroom video as a source
│
├── attendance/
│   ├── rules.py                # the pure 3/5-style rule (zero AI dependency)
│   ├── scheduler.py            # REAL vs DEMO snapshot timing
│   ├── engine.py                # orchestrates snapshots -> final rollup
│   └── export.py                # CSV export formatting
│
├── database/
│   └── db.py                    # SQLite schema + all data access
│
├── views/                        # Streamlit pages (named `views/`, not
│   ├── dashboard.py                `pages/`, to avoid colliding with
│   ├── enrollment.py                Streamlit's automatic file-based
│   ├── class_session.py             multi-page navigation)
│   ├── timeline.py
│   └── history.py
│
├── data/students/                # (raw enrollment photos are NOT retained here)
├── models/                        # reserved for future model files
└── tests/                          # pytest suite, see §8
```

**Data flow:**

```
Enrollment photos → face detection → face template (embedding) → SQLite
                                                                       ↓
Webcam / video → scheduled snapshot → face detection → per-face embedding
                                                       → match vs enrolled templates
                                                       → observation recorded
                                                                       ↓
All snapshots done → per-student observation count → 3-of-5 rule → PRESENT
                                                                  → NEEDS REVIEW
                                                                       ↓
                                                        Dashboard / Timeline / CSV
```

## 5. Installation

Requires Python 3.10+.

```bash
cd attendai
python3 -m pip install -r requirements.txt --break-system-packages   # or use a venv
streamlit run app.py
```

Then open the URL Streamlit prints (usually `http://localhost:8501`).

## 6. How to use it

### Enroll a student
1. Go to **Student Enrollment**.
2. Enter Student ID, Name, and Section.
3. Upload 2–5 clear, front-facing photos (or use the webcam capture).
4. Click **Enroll Student**. Only the computed face template is stored —
   the raw photos are not retained.

### Start a class
1. Go to **Start Class**.
2. Enter the class name, pick the section, and set lecture duration /
   number of snapshots / minimum observations (defaults: 50 min, 5, 3).
3. Choose **DEMO MODE** (for a quick judge-facing run) or **REAL MODE**.
4. Choose a camera source: laptop webcam, or upload a pre-recorded
   classroom video.
5. Click **Start Class**, then let the snapshot schedule run — each
   snapshot's annotated frame and a live per-student observed count are
   shown as they happen.
6. When the schedule finishes, the final PRESENT / NEEDS REVIEW table is
   shown, along with a CSV export button.

### How DEMO MODE works
DEMO MODE uses the exact same detection → recognition → 3-of-5 pipeline as
REAL MODE. The only difference is timing: instead of spreading 5 snapshots
across 50 real minutes, they're spread across ~90 compressed seconds
(`config.DEMO_MODE_TOTAL_SECONDS`). Nothing about the attendance *result* is
faked or shortcut.

### Resolving a NEEDS REVIEW case
Go to **Student Timeline**, pick the session and student, review their
snapshot-by-snapshot ✓/✗ pattern, and click **Resolve as PRESENT / NEEDS
REVIEW**. The same control is also available inline on the **Dashboard**.
The system's *computed* status is preserved for audit; the manual
resolution is stored separately and takes precedence wherever attendance is
displayed or exported.

## 7. The attendance algorithm

```
for each enrolled student in the class's section:
    observation_count = number of DISTINCT snapshots in which
                         that student was recognized above the
                         configured match-score threshold

    if observation_count >= minimum_required:
        status = PRESENT
    else:
        status = NEEDS REVIEW
```

Key properties:
- A student **never observed at all** (0/5) still gets a row in the
  results with `NEEDS REVIEW` — they are never dropped from the report and
  never automatically labeled "absent."
- A detected face that **doesn't match any enrolled student** is logged as
  an "unknown face" event, shown separately on the dashboard, and never
  attributed to (or counted against) any real student. The same handling
  now applies when two *different* faces in one frame both best-match the
  same enrolled student (a recognizer collision) — the second face is
  logged as ambiguous/unresolved rather than silently discarded, so a
  possibly-present student is never made to vanish from the record without
  a trace (see §11).
- The recognizer's output is called a **match score**, not a probability —
  it is a bounded similarity value derived from a classical (non-deep)
  computer-vision distance metric, not a calibrated statistical confidence.

### Recognition approach (and a note on the model choice)

The original goal was to use a modern pretrained deep face detector/embedder
(OpenCV Zoo's YuNet + SFace ONNX models). Those model weights are hosted via
Git-LFS, and the LFS object storage domain (`media.githubusercontent.com`)
was not reachable on this development network — only the LFS *pointer*
files downloaded, not the actual weights. Rather than lose hours fighting
network/mirror issues mid-hackathon, we substituted a fully offline,
zero-download classical CV pipeline:

- **Detection:** OpenCV's built-in Haar Cascade (ships inside every OpenCV
  install).
- **Embedding:** grid-based uniform Local Binary Pattern (LBP) histograms —
  a well-established, hand-engineered face descriptor (this is the same
  family of features behind OpenCV's own `LBPHFaceRecognizer`), computed
  per-face so students can be enrolled incrementally without retraining a
  global model.
- **Matching:** chi-square distance between histograms (the standard metric
  for comparing LBP histograms), converted to a bounded `[0, 1]` match
  score.

This was empirically validated during development (see
`tests/test_ai_pipeline.py`): two photos of the same person scored ~0.56–0.97
in testing, while a different real person scored ~0.03–0.22 — a clear,
usable separation for a small enrolled class. It is **not** as robust as a
modern deep embedding model, especially across pose/lighting variation (see
Limitations below), but it is reliable, fully local, and required no
external downloads — a good trade for a 24-hour build.

## 8. Testing

```bash
python3 -m pytest
```

52 tests covering:
- Student creation, update-in-place, section filtering, deletion
- Session creation and lifecycle, including the **`min_observations >= 2`
  guard** rejecting single-frame-equivalent configuration
- Observation recording, **duplicate-observation deduplication**, and
  unknown-face handling
- The core rule at the **3/5, 4/5, 5/5, and 2/5** boundary cases, plus 0/5
  and custom-threshold variants
- The full engine rollup — including a student **never observed** correctly
  landing on NEEDS REVIEW (not dropped, not "absent")
- Manual override precedence
- CSV export format and content
- The snapshot scheduler (REAL vs DEMO timing, monotonicity/bounds, that a
  session's schedule is **reproducible for the same seed** but **varies
  across seeds** so it isn't a fixed, learnable pattern)
- The AI pipeline (detection, embedding round-trip, same-vs-different-person
  discrimination) using real, public-domain test photos bundled with
  scikit-image — no network access needed to run the suite

The rule and engine tests (`test_rules.py`, `test_engine.py`,
`test_observations.py`, `test_export.py`) deliberately have **no dependency
on the AI pipeline** — they write synthetic observations directly — so the
attendance logic itself is verified independently of face recognition, per
the project's own design goal.

## 9. Privacy & responsible AI

- This is a **hackathon prototype**, not a certified or production-grade
  attendance system, and makes **no claim of 100% accuracy**.
- Facial data requires appropriate **authorization and consent** — only
  consenting participants should ever be enrolled.
- Access to biometric templates should be **restricted** in any real
  deployment.
- **"Not observed" never means "absent."** A ✗ in the timeline means the
  system did not confidently see that student in that snapshot — they may
  have been out of camera view, occluded, turned away, or the lighting was
  poor.
- Every NEEDS REVIEW case is routed to a **teacher for manual resolution**,
  never auto-decided.
- All face processing happens **locally** on the machine running the app —
  no classroom imagery is uploaded to any external service.
- Raw enrollment photos are **not retained**; only the computed face
  template is stored.
- A real deployment would need a formal consent, retention, and deletion
  policy, and likely a more robust/audited recognition model than the
  classical CV approach used here.

## 10. Known limitations

- **Frontal faces only.** The Haar Cascade detector does not reliably find
  profile or heavily angled faces (verified during testing — it correctly
  failed to detect a side-profile photo). Students should face the camera
  roughly straight-on during snapshots.
- **Pose/lighting sensitivity.** The LBP-histogram recognizer is more
  sensitive to pose and lighting changes than a modern deep embedding model
  would be; a slight head rotation can push a genuine match toward the
  UNKNOWN threshold (see the rotation test in
  `tests/test_ai_pipeline.py`/earlier development notes).
- **Small-class scale.** Recognition accuracy has been validated on a
  handful of enrolled identities during development, not stress-tested
  against a large roster with many visually similar faces.
- **Camera framing matters.** A single fixed webcam has a limited field of
  view, and small/distant faces (e.g. a wide shot of a full room) may fall
  below the detector's minimum-face-size floor. This is now a live,
  per-session slider on the Start Class page (see §11) rather than a fixed
  constant, so it can be tuned to the actual camera setup — but it doesn't
  change the fact that one camera can't guarantee full-room coverage.
- **Single-machine, single-session design.** No multi-teacher/multi-room
  concurrency handling — appropriate for the hackathon scope, not a
  production deployment.
- **No liveness/anti-spoofing check** — a printed photo or a phone screen
  held up to the camera could, in principle, be matched. Combined with
  §11's scheduling jitter this is harder to time deliberately than with a
  fixed schedule, but it remains out of scope for this MVP.
- **No authentication/access control.** Anyone who can open the app can
  enroll/delete students, start sessions, and resolve NEEDS REVIEW cases.
  Fine for a single-teacher hackathon demo; a real deployment would need
  logins and role-based access before any of this touches real student
  data.
- **Biometric data at rest is unencrypted.** Face templates are stored as
  plain BLOBs in a local, unencrypted SQLite file. Not storing raw photos
  (see §9) reduces exposure, but the derived templates themselves aren't
  protected beyond OS file permissions.
- **REAL MODE capture is a single blocking browser session.** The snapshot
  loop runs as a synchronous wait inside the Streamlit script for the whole
  configured lecture; if the tab is closed or the connection drops
  mid-lecture, the session is left at status=`running` with only partial
  observations. §11 added a manual "finalize now" recovery button on the
  History page, but there's still no automatic resume — a background job
  runner would be the real fix for a non-hackathon deployment.

## 11. Hardening changes made after the first pass

The first build surfaced a few gaps that were worth fixing even within
hackathon scope, because they undercut the project's own core pitch or
could visibly break during a live demo. None of these required new
dependencies or schema changes.

1. **Snapshot timing is now jittered, not fixed** (`attendance/scheduler.py`).
   Previously every session placed its 5 snapshots at exactly 10/30/50/70/90%
   of the lecture — a predictable pattern a student could learn and game
   ("only be in frame for the five brief instants"). Snapshots are now
   placed in randomized positions within evenly-sized time slots, seeded by
   the session ID so a given session's real-time countdown and its
   video-fraction mapping still agree with each other, while every session
   gets a different, unpredictable schedule.
2. **`min_observations` can no longer be set to 1**
   (`views/class_session.py`, `database/db.py`). A minimum of 1 observation
   collapses the "3-of-5 temporal presence" design back into ordinary
   single-frame recognition. The UI floor is now 2, and `db.create_session`
   rejects it server-side too, so it can't be bypassed by any caller.
3. **Recognizer collisions are no longer silently dropped**
   (`attendance/engine.py`). If two different detected faces in one frame
   both best-matched the same enrolled student, the second face used to be
   discarded with no record at all. It's now logged as an ambiguous/
   unresolved observation (visible in the unknown-face count and labeled
   `AMBIGUOUS` on the annotated frame) instead of vanishing.
4. **Stuck "running" sessions can now be recovered**
   (`views/history.py`). If a REAL MODE session is interrupted (tab closed,
   connection dropped), it used to stay at status=`running` forever with no
   way to compute a final rollup. Attendance History now detects this and
   offers a "Finalize this session now" button that runs the rollup on
   whatever snapshots were captured.
5. **Minimum detectable face size is now a live per-session control**
   (`views/class_session.py`, `attendance/engine.py`). Previously fixed at
   `config.MIN_FACE_SIZE_PX = 60`px, which can cause a wider/further-back
   camera framing to miss distant faces entirely with no way to fix it short
   of editing `config.py`. It's now a slider (20–150px) on the Start Class
   form, threaded through the capture loop for that session.
