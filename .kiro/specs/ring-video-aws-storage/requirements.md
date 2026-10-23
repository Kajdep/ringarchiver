# Requirements: Ring Video AWS Storage

Revision: review started 2026-09-22, completed 2026-09-23. Status: implementation specification; application not built or deployed. Review evidence is in the [change log](../../../docs/reviews/2026-09-22-documentation-review.md).

## Purpose and scope

Automatically copy available recorded clips from selected Ring cameras to private AWS S3 storage, retain them independently of Ring, and make backup gaps visible. The MVP is a self-hosted background service for one Ring account, with command-line setup and AWS monitoring. A gallery, mobile app, live recording, Google Drive and commercial multi-user service are outside the MVP.

Python is retained from the existing plan. The baseline uses the community `ring-doorbell` distribution (repository: `python-ring-doorbell`) and polling. Ring also offers an official Partner API; its OAuth and webhooks are a separate integration, not features of that Python package. See [sources.md](sources.md) and [decisions.md](decisions.md).

Setup must verify account control, downloadable recordings, a suitable Ring subscription, AWS region and device allowlist. Device country and developer-program access are unknown; do not infer them from the operator's timezone. Archival cannot recover recordings Ring never stored or has already removed.

## Definitions

- **Processor**: the Python Lambda with Ring, state and storage adapters.
- **Identity**: stable tuple `(account_namespace, device_id, event_id)`.
- **Ledger**: DynamoDB records for discovered recordings and their outcomes.
- **Discovery checkpoint**: upper bound of a completely enumerated interval, not proof of archival.
- **Archived**: the S3 object was verified and that evidence is durably recorded; this is historical evidence, not a claim that an expired/deleted object remains retrievable today.
- **Pending**: discovered footage awaiting download, retry or reconciliation.
- **Attempt**: one application-level operation; default maximum is three total attempts including the initial call.

## Requirement 1: Authentication and setup

User story: Connect once and clearly signal when reconnection is needed.

- **R1.1** WHEN setup runs, the tool SHALL obtain login and MFA interactively and store the resulting token document and stable client hardware identifier in Secrets Manager; it SHALL NOT persist the password or one-time code.
- **R1.2** WHEN a run starts, the Processor SHALL retrieve that secret and authenticate before accessing recordings.
- **R1.3** WHEN a token is refreshed, the Processor SHALL durably save its replacement before reporting health; persistence failure SHALL stop further Ring work and surface an authentication health failure.
- **R1.4** IF authentication is revoked, MFA is required or permissions are denied, the Processor SHALL report reconnection required without repeated interactive login attempts.
- **R1.5** The system SHALL redact credentials, headers, token bodies and signed media URLs from logs, metrics, ledger and deployment output.
- **R1.6** Setup SHALL verify selected devices and recording access and report subscription or capability problems.
- **R1.7** Setup/reconnection and Lambda runs SHALL coordinate through a durable maintenance gate and exclusive account writer; queued invocations SHALL perform no Ring access while maintenance is active. Setup SHALL wait for the previous writer to finish or exceed its hard execution deadline before replacing credentials.

## Requirement 2: Discovery and recovery

User story: Failed recordings stay recoverable after later polls succeed.

- **R2.1** WHEN polled, the Processor SHALL enumerate every history page for each allowlisted device within the requested interval, using the adapter's actual pagination mechanism.
- **R2.2** The Processor SHALL use UTC and a configurable overlap, default 24 hours before the previous completed discovery checkpoint; first run SHALL request the preceding 24 hours unless an explicit backfill boundary is supplied.
- **R2.3** Each discovered identity, frozen object key and metadata SHALL be durably inserted before advancing beyond its page.
- **R2.4** IF pagination fails, repeats without progress or reaches a run budget, the Processor SHALL retain continuation state and SHALL NOT mark the unenumerated interval complete.
- **R2.5** Pending and deferred recordings SHALL remain independently eligible after their discovery timestamp falls behind the checkpoint.
- **R2.6** IF one recording fails, the Processor SHALL preserve its classified outcome and continue independent work within the budget.
- **R2.7** Recordings still processing SHALL be retried; source-unavailable, access-denied, oversize and retry-exhausted outcomes SHALL be distinguished from archived.
- **R2.8** The operator SHALL be able to request bounded backfill and retry selected failed identities; a scan that cannot reach its requested boundary SHALL report incomplete coverage.
- **R2.9** Every discovery, retry and download SHALL respect the current device allowlist and provider authorization. Removed or unauthorized devices SHALL have pending source transfers suspended with a visible reason; re-enabling SHALL require renewed validation and an explicit resume.

## Requirement 3: Verified private storage

User story: Find footage by date and camera without duplicate archives or unnoticed incomplete uploads.

- **R3.1** Keys SHALL follow `videos/YYYY/MM/DD/{camera-slug}-HH-MM-SS-{identity-hash}.mp4` using recording time in UTC; the bucket name SHALL NOT be part of the key.
- **R3.2** An identity SHALL retain its initially assigned key across retries and camera renames; distinct identities at the same timestamp SHALL use identity-derived suffixes to prevent timestamp collisions.
- **R3.3** Each object SHALL include bounded ASCII-safe user metadata for identity, original device name, recording time, event type, byte count and SHA-256; content type SHALL be `video/mp4`.
- **R3.4** Object creation SHALL be conditional; an existing object SHALL be reconciled against persisted expected identity, size and checksum instead of overwritten.
- **R3.5** An identity SHALL be marked archived only after S3 confirms expected object length, identity and SHA-256; the API checksum SHALL use base64 of the digest bytes, with an explicit conversion from stored hex. A verification timeout or permission error SHALL NOT be treated as absence, and source retry limits SHALL NOT discard unresolved upload evidence.
- **R3.6** Storage SHALL block public access, require TLS, enable default server-side encryption and grant narrowly scoped AWS permissions.
- **R3.7** Normal backup SHALL neither delete Ring recordings nor create new recordings, publish media or grant public access.

## Requirement 4: Lifecycle and retrieval

User story: Choose retention and understand when old footage needs restoration.

- **R4.1** Eligible videos SHALL transition to S3 Glacier Flexible Retrieval (`GLACIER`) after 90 days by default, measured from S3 creation time.
- **R4.2** Current versions SHALL become eligible for expiration after 2,555 days from creation; noncurrent versions SHALL become eligible for permanent deletion after one noncurrent day, and expired delete markers SHALL be cleaned up. This approximates seven years; it is not an exact calendar anniversary or guaranteed deletion instant.
- **R4.3** Custom values SHALL be validated; expiration SHALL follow transition by at least the archival class's minimum storage duration. A retain-indefinitely option SHALL omit current-version expiration.
- **R4.4** Lifecycle SHALL apply only to the video prefix, not state, credentials or deployment artifacts; incomplete multipart uploads SHALL have a cleanup rule.
- **R4.5** Documentation SHALL explain restoration delay and charges, small-object transitions, noncurrent-version retention and possible early-deletion charges for archived versions; retain-indefinitely SHALL be labelled as applying to current versions only.
- **R4.6** Stack deletion or replacement SHALL retain the archive, ledger and secret; later destructive cleanup SHALL be an explicit operator action.

## Requirement 5: Scheduling and repeat delivery

User story: Backup runs without my computer and tolerates duplicate invocations.

- **R5.1** EventBridge Scheduler SHALL request a run every 15 minutes by default; the MVP configurable interval SHALL be at least 15 minutes.
- **R5.2** The backup Lambda SHALL have one reserved concurrent execution per account; it SHALL tolerate queued/duplicate invocations rather than assuming the scheduler suppresses them.
- **R5.3** Later scheduled runs SHALL continue after prior failures and reconcile pending work.
- **R5.4** Scheduler delivery failures and accepted Lambda execution failures SHALL each have a failure destination and visible alarm.
- **R5.5** The schedule SHALL start disabled and be enabled after account setup and a verified end-to-end staging archive.

## Requirement 6: Failure handling and visibility

User story: Distinguish an empty healthy poll from an unattended outage.

- **R6.1** Logs SHALL include UTC time, run ID, operation, safe recording ID and classified error without raw sensitive exception payloads.
- **R6.2** Retryable network, throttling and service failures SHALL use at most three total application attempts with jittered backoff and bounded HTTP timeouts; valid `Retry-After` SHALL be respected or deferred.
- **R6.3** Retry exhaustion SHALL persist a retry time and reason; permanent source absence SHALL be recorded as unavailable without endless immediate retries.
- **R6.4** Completed runs SHALL emit discovered/archived/deferred/unavailable/failed/suspended counts, uploaded bytes, duration, oldest unfinished age, discovery lag and authentication health; healthy empty polls SHALL publish a heartbeat. Aggregate status SHALL include records outside the due-work index and report the time of its last complete reconciliation.
- **R6.5** Monitoring SHALL alarm on authentication failure, pending age over 24 hours, discovery lag over one hour, failure-queue messages and no healthy heartbeat for one hour.
- **R6.6** A status command SHALL show per-device discovery coverage, pending/failed counts, last healthy run and last verified upload without media access.
- **R6.7** New terminal failures, unavailable recordings and suspended work SHALL produce an alert. Unacknowledged gaps SHALL remain visible after removal from the retry index; acknowledgement SHALL preserve their outcome and audit history.

## Requirement 7: Bounded execution and deployment

User story: Resource use is predictable and interruption is recoverable.

- **R7.1** The Processor SHALL stop starting new work before its deadline, persist resumable discovery and leave unfinished recordings eligible. Deadlines SHALL include authentication/refresh, streamed reads, AWS calls and underlying SDK retries, not just time between operations.
- **R7.2** Downloads SHALL stream bounded chunks to private temporary files, enforce a configurable size ceiling and validate nonempty media before upload.
- **R7.3** The MVP SHALL transfer one recording at a time with bounded page/recording counts and fair progress across devices and old/new work.
- **R7.4** Temporary files SHALL be removed on normal completion and handled exceptions; the next invocation SHALL sweep only app-owned abandoned files after forced termination.
- **R7.5** The project SHALL provide reproducible Lambda-compatible packaging, infrastructure as code, Windows PowerShell instructions and pinned production dependencies separate from test dependencies.
- **R7.6** Validation SHALL distinguish offline checks, AWS staging tests and live Ring evidence; simulations SHALL NOT be described as live proof.

## Requirement 8: Optional official Partner API

User story: Eligible devices can later use supported developer access and event hints.

- **R8.1** The MVP SHALL poll without API Gateway. The official adapter SHALL require verified developer access, supported geography, scopes and OAuth account linking; eligibility assessment SHALL consider the documented private-app route as well as public apps.
- **R8.2** WHERE official webhooks exist, the receiver SHALL validate documented signatures and replay controls, durably enqueue a hint and respond within the documented deadline; transfer SHALL be asynchronous.
- **R8.3** Webhooks and polling SHALL use the same ledger; a motion notification SHALL NOT count as archival or proof of media readiness.
- **R8.4** The official adapter SHALL respect consent-time boundaries, distinguish partial media, preserve supplied watermarks and record actual returned time ranges.
- **R8.5** The official adapter SHALL have separate acceptance tests and a release gate; its deferred status SHALL not block the polling MVP.

## MVP acceptance

Archive and play at least one real clip from each selected supported device; replay without duplicate current objects; recover an injected failure on a later run; persist refreshed tokens across cold starts; prevent incomplete scans from advancing checkpoints; and pass all required offline and staging gates in [tasks.md](tasks.md).

