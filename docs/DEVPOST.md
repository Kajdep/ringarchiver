# RingArchive

## Tagline
Own your Ring footage forever. RingArchive automatically backs up every doorbell event clip to your private, encrypted AWS storage using the official Ring API.

## Inspiration
Ring cloud storage deletes footage after 60 days. RingArchive automates permanent backup: connect once and every clip lands in an S3 bucket you control, encrypted, versioned, Glacier after 90 days.

## What it does
1. AWS Lambda polls Ring API every 15 min via EventBridge
2. Downloads each new MP4 to S3 at device/YYYY/MM/DD/event_id.mp4
3. DynamoDB conditional write prevents double-archiving
4. Optional Bedrock (Claude Haiku) writes a one-line summary per clip
5. Flask dashboard: unified event+clip table, inline video player, export to disk/Dropbox/Drive

## How we built it
Python 3.12, built during the hackathon window (23 Oct 2026) using Kiro.
Stack: Ring API (Amazon Vision), Ring Developer Playground, Ring App Store Knowledge MCP, AWS Lambda, Amazon S3, Amazon DynamoDB, AWS SAM, Amazon EventBridge, AWS Secrets Manager, Amazon Bedrock (optional), Flask, Kiro.
Full spec in .kiro/specs/ring-video-aws-storage/.

## Challenges
- **Playground token expiry (30 min):** No refresh-token flow; interrupted demo repeatedly. Workaround: seed DynamoDB from event metadata.
- **Playground video download 416:** Simulator returns event metadata but no MP4 bytes. Pipeline correct; Playground limitation.
- **Kiro Crew AWS Control on Windows:** Requires WSL, not Windows 11 native. Used AWS CLI from PowerShell instead.
- **Kiro subscription blocked:** AWS account flagged not eligible. Used Kiro CLI directly.

## Accomplishments
- Official Ring API only (no unofficial library)
- Zero hardcoded secrets
- DynamoDB dedupe confirmed (skipped=6 on repeated runs)
- SAM template ready for one-command deploy
- Dashboard with video player, 3-destination export, device filter, bulk actions
- 6/6 unit tests passing

## What we learned
- Playground great for API shape verification but needs mock MP4 bytes for end-to-end dev
- AWS SAM handles full stacks cleanly from a single template
- Kiro spec-first workflow keeps generated code consistent with design intent

## What is next
- Real Ring device test
- Google Drive OAuth (needs GCP project)
- Notification webhook on new clip
- Clip search by Bedrock summary

## Built with
Python, Ring API (Amazon Vision), Ring Developer Playground, Ring App Store Knowledge MCP, AWS Lambda, Amazon S3, Amazon DynamoDB, AWS SAM, Amazon EventBridge, AWS Secrets Manager, Amazon Bedrock (optional), Flask, Kiro

## Tracks
- Ring (primary): official Ring API + Ring Developer Playground
- AWS Builder mini challenge: built with Kiro + Lambda + S3 + DynamoDB + SAM

## Built during the window
Repo created 22 Sep 2026 as empty placeholder (specs only). All code written 23 Oct 2026 during the hackathon window. Initial commit: feat: initial MVP.

## Product feedback

### Ring API (api.amazonvision.com)
Used for device list, event history, video download, token refresh.
Worked: clean JSON:API format, correct data immediately, sensible 303 redirect.
Needs work: 416 on Playground with no media_status field to distinguish not-ready from nonexistent.
Onboarding: portal clear; ring-api-helloworld repo was 404 during hackathon.
Would use again: yes.

### Ring Developer Playground
Used for simulator events without a physical device.
Worked: device and events appear immediately.
Needs work: 30-min token with no refresh; video download always 416; needs mock MP4 per triggered event.
Would use again: yes, once token expiry and missing video bytes are fixed.

### Ring App Store Knowledge MCP
Used for verifying API endpoint paths and auth patterns.
Worked: correct MCP responses, useful in-context knowledge.
Needs work: 500 errors on some queries.
Would use again: yes.

### AWS Lambda
Used for archive worker. SAM packaging seamless, Python 3.12 cold start fast. Would use again: yes.

### Amazon S3
Used for private clip storage. Presigned URLs, public access block straightforward.
Needs work: versioning/encryption CLI blocked by safety policy; SAM deploy handled it.
Would use again: yes.

### Amazon DynamoDB
Used for event dedupe. Conditional writes give exactly-once semantics. On-demand billing = zero cost at low volumes. Would use again: yes.

### AWS SAM
Used for all infrastructure. Full stack from one template. sam deploy guided is excellent DX. Local invoke needs Docker. Would use again: yes.

### Kiro
Used for spec writing, code generation, build orchestration, UI iteration.
Worked: spec-first workflow, Crew Conductor autonomous orchestration, rapid UI iteration (4+ versions in one session).
Needs work: subscription blocked on this AWS account; Kiro Crew AWS Control requires WSL; some safety blocks too broad.
Would use again: yes, the spec-to-code workflow is a real hackathon multiplier.

## Friction log

| Task | Expected | Actual | Severity | Workaround | Suggestion |
|---|---|---|---|---|---|
| Playground token lifetime | Long-lived dev token | 30-min expiry, no refresh | High | Reseed DynamoDB from metadata | Add refresh token flow or longer TTL |
| Playground video download | MP4 bytes | 416 always | High | Metadata-only demo | Serve mock MP4 per triggered event |
| S3 config via CLI | Commands run | Blocked by safety policy | Medium | SAM deploy | Allowlist read/write, block destructive only |
| Kiro Crew AWS Control on Windows | Native Windows | Requires WSL | Medium | Used AWS CLI | Native Windows support |
| Kiro subscription eligibility | Activates | Not eligible error | Medium | Used Kiro CLI | Clearer messaging and fallback |
