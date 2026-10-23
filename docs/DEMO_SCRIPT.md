# RingArchive — 2.5-Minute Demo Script

**Audience:** hackathon judges  
**Goal:** show Ring API → Lambda pipeline → S3/DynamoDB → dashboard UI end to end

---

## Setup (before you go live)

1. `.env` has `RING_ACCESS_TOKEN` (Playground token), `ARCHIVE_BUCKET`, `DYNAMO_TABLE`, `AWS_REGION=eu-west-2`
2. AWS credentials configured (`aws configure`)
3. S3 bucket and DynamoDB table already created
4. Terminal open in `D:\ringarchive`

---

## Script

### 0:00 — Intro (15 s)

> "RingArchive is a personal backup service for Ring doorbell clips.
> It uses the official Ring API to pull events, stores each clip in
> your own private S3 bucket, and tracks them in DynamoDB — so you
> own your footage forever."

### 0:15 — Show the Ring Playground event (20 s)

Open [developer.amazon.com/api/ring](https://developer.amazon.com/api/ring).

> "Here's the Ring Developer Playground. I'll trigger a doorbell event."

Click **Ring doorbell** or **Trigger motion**.

### 0:35 — Run the archive pass (30 s)

```bash
python -m ringarchive.run_once
```

Expected output:
```
INFO Found 1 device(s)
=== RingArchive — single run ===
Result: archived=1  skipped=0  errors=0
```

> "One new clip archived. Skipped means it was already stored — the
> DynamoDB dedupe table prevents double-archiving."

Run again immediately:
```bash
python -m ringarchive.run_once
```

```
Result: archived=0  skipped=1  errors=0
```

> "Same clip, skipped. Exactly once, guaranteed."

### 1:05 — Show the dashboard (45 s)

```bash
python -m ringarchive.ui
```

Open `http://localhost:5000`.

> "This is the archive dashboard. It shows both live Ring API events
> and what's been archived to S3 in one unified table."

Point out:
- **Device badge** (purple) — which Ring device
- **Archived / Event only** status badges
- **Filter dropdowns** — by device and event type
- Click a row → **video viewer modal** opens

> "Click any row to inspect the clip. If the S3 URL resolves, it
> plays inline. Export buttons let you save to disk, Dropbox, or
> Google Drive — individually or in bulk."

### 1:50 — Show SAM template (20 s)

Open `template.yaml` briefly.

> "The production deployment is a SAM stack — Lambda polling every
> 15 minutes via EventBridge, private S3 with versioning and
> AES-256 encryption, DynamoDB on-demand, and Ring credentials
> stored in Secrets Manager. One command to deploy."

```bash
sam build && sam deploy --guided
```

### 2:10 — Wrap up (20 s)

> "RingArchive was built in one day during the hackathon using Kiro.
> Kiro wrote the Ring client against the official Amazon Vision API,
> the SAM infrastructure, the dedupe logic and the dashboard — all
> from the spec in .kiro/specs. The Ring App Store Knowledge MCP
> helped verify the correct API endpoints."

> "MIT licensed, no unofficial libraries, no hardcoded secrets."

---

## Fallback (if Playground token has expired)

Show the 6 seeded events in the dashboard — the UI still demonstrates:
- Unified event+clip table
- Device filter
- Viewer modal with the "Playground doesn't serve MP4s" message
- Export buttons
- Bulk select and download

The pipeline is correct; the Playground simply doesn't return MP4 bytes.
