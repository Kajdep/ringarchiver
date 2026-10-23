# RingArchive — 2.5-Minute Demo Script

**Audience:** Hackathon judges  
**Prereqs:** `.env` loaded, SAM stack deployed, Ring simulator linked, DynamoDB + S3 empty.

---

## Act 1 — Trigger a simulator event (0:00 – 0:30)

1. Open the Ring Developer Portal → Staging → Simulator.
2. Click **Trigger motion event** on the virtual doorbell.
3. *Narrate:* "The simulator fires a `motion_detected` webhook and records a clip on Ring's servers — just like a real doorbell."

---

## Act 2 — Run one archive pass (0:30 – 1:15)

In a terminal:

```bash
python -m ringarchive.run_once
```

Watch the output:

```
INFO Found 1 device(s)
INFO Uploading 1234567 bytes to s3://ringarchive-.../ava1.ring.device.XXX/2026/10/23/<event_id>.mp4
INFO Uploaded s3://ringarchive-.../<event_id>.mp4
Result: archived=1  skipped=0  errors=0
```

*Narrate:* "The Lambda calls `GET /v1/history/devices/{id}/events`, finds the new event, calls `POST /v1/devices/{id}/media/video/download`, downloads the MP4, and stores it in our private S3 bucket."

---

## Act 3 — Verify S3 and DynamoDB (1:15 – 1:50)

Open the AWS Console:

- **S3:** Navigate to the bucket → confirm the `<device_id>/2026/10/23/<event_id>.mp4` object.
- **DynamoDB:** Open the `RingArchiveEvents` table → confirm one row with `event_id`, `archived_at`, `s3_key`.

*Narrate:* "The DynamoDB record prevents the same clip being downloaded twice — our dedupe guard."

---

## Act 4 — List clips with presigned URLs (1:50 – 2:15)

```bash
python -m ringarchive.list_clips
```

Output:

```
Event ID                                       Archived At                 Summary
ava1.ring.device.XXX_motion_...                2026-10-23T17:35:00+00:00   (no summary)
  https://ringarchive-....s3.eu-west-2.amazonaws.com/...?X-Amz-...
```

Paste the URL in a browser — the MP4 plays directly.

---

## Act 5 — Trigger again to show dedupe (2:15 – 2:30)

Run `python -m ringarchive.run_once` a second time.

```
Result: archived=0  skipped=1  errors=0
```

*Narrate:* "Same event, already in DynamoDB — skipped. Zero duplicate downloads."

---

## Wrap-up (2:30)

"RingArchive: Ring official API → Lambda → private S3 → Glacier.  
Your clips, your storage, always yours."
