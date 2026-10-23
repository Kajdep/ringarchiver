# Design: Ring Video AWS Storage

Revision: review started 2026-09-22, completed 2026-09-23. Proposed implementation; no application or cloud resources created. Operational procedures are specified in [the runbook](../../../docs/operations.md).

## Architecture and boundaries

One account, a configured device allowlist, one Python 3.12 Lambda, scheduled polling and sequential video transfer. Use AWS SAM/CloudFormation for deployment. Production Python packages are `ring-doorbell`, `boto3` and the streaming HTTP dependency; pin tested versions separately from pytest, Hypothesis and AWS test doubles. The final lock and Linux package build are implementation work.

```mermaid
flowchart LR
    E[EventBridge Scheduler: every 15 minutes] --> L[Python Lambda: one concurrent run]
    R[Ring recorded history and media] --> L
    S[Secrets Manager: Ring token] <--> L
    D[DynamoDB: discovery and recording ledger] <--> L
    L --> B[Private versioned S3 bucket]
    B --> G[S3 Glacier Flexible Retrieval]
    L --> C[CloudWatch logs, metrics and alarms]
    E --> Q[SQS delivery failure queue]
    L --> F[SQS async execution failure destination]
```

Glacier is an S3 storage class in the same bucket, not a second bucket or upload destination. API Gateway and a public application are not needed for the polling MVP. The official Partner API is a later adapter with separate prerequisites; see [decisions.md](decisions.md).

## Configuration

| Setting | Proposed default | Validation/meaning |
| --- | --- | --- |
| AWS region | Required deployment input | No region inferred from operator timezone |
| Account namespace | Stable generated UUID | Reuse after redeployment; never use email |
| Device IDs | Required allowlist | Reject unknown or unsupported devices |
| Schedule | 15 minutes | Integer minutes, minimum 15 for MVP |
| Overlap / initial history | 24 hours / 24 hours | Backfill is an explicit separate range |
| Lambda timeout / memory / temporary disk | 600 seconds / 1,024 MiB / 2,048 MiB | Benchmark in staging |
| Stop-new-work reserve | 60 seconds | Every operation also bounded by remaining time |
| Transfer concurrency | 1 | Single account token writer |
| Page size / page budget | 100 / 100 per run | Verify source honours page size |
| Recording budget | 50 attempted identities per run | Fair rotation across devices |
| Maximum recording size | 256 MiB | Oversize becomes a visible failed item |
| HTTP connect / read-idle / total | 10 / 30 / 120 seconds | Cap total by Lambda deadline |
| Application attempts | 3 total | Initial call plus at most two retries |
| Transition / expiration | 90 / 2,555 days | Expiration may be disabled explicitly |
| Noncurrent expiration | 1 day | Protect against indefinite version accumulation |
| Log retention | 30 days | No media, tokens or signed URLs in logs |
| Summary reconciliation | Complete sweep at least hourly | Resume bounded ledger pages; stale/incomplete totals are labelled |

These are limits, not promised throughput. An increasing backlog or discovery lag is a capacity signal; raise budgets only after measurement. If one Lambda cannot keep up, split discovery and transfers with an SQS worker design in a later revision.

## Components and interfaces

| Module | Responsibility |
| --- | --- |
| `config.py`, `models.py` | Validated configuration, aware UTC timestamps, typed records |
| `auth.py` | Secret loading, stable hardware ID, serialized token refresh/persistence |
| `ring_adapter.py` | Device discovery, history pages, normalized records, fresh media URL |
| `state.py` | Conditional inserts, scan continuations, retry eligibility, archive evidence |
| `storage.py` | Stable keys, conditional S3 puts, checksum verification, reconciliation |
| `processor.py` | Fair bounded discovery and transfer orchestration |
| `observability.py` | Redacted logs, summaries and CloudWatch metrics |
| `handler.py` | Lambda entry point, deadlines, dependency construction and cleanup |
| `cli.py` | Setup, device listing, status, bounded backfill, retry and restore guidance |

Use Python snake_case APIs and dataclasses. The adapter contract is:
`list_devices()`, `history_page(device_id, cursor, page_size)`, and
`resolve_media(recording)`. A normalized history page returns records, next cursor and a completeness indicator. It must not pretend the community library accepts a `since` timestamp. Filter timestamps locally; translate the library's `older_than` event-ID cursor inside the adapter.

The recorded event model contains account namespace, device ID, event ID, original device name, aware UTC recording time, event type and optional duration. Signed URLs are transient, resolved immediately before transfer and excluded from persisted models.

For the community adapter, normalized `device_id` is `str(device.id)` (the API ID used by history), not the client's separate `device.device_id` hardware/MAC-like identifier. Normalize event IDs as opaque strings. Record `provider = community-ring-doorbell` and the schema version alongside the account namespace; do not mix Partner API directed IDs into that namespace without a migration design. The pinned release must confirm these mappings. [Client identity and history source](https://github.com/python-ring-doorbell/python-ring-doorbell/blob/master/ring_doorbell/generic.py).

## Authentication and token lifecycle

1. A local setup command uses secure password/MFA prompts and completes the client's login flow. Save only its token document, schema version and stable hardware ID in Secrets Manager using the operator's AWS identity.
2. Lambda reads that secret on each invocation and constructs one client session for the run. It never receives a password in environment variables or infrastructure parameters.
3. The token-updater callback persists every actual replacement token before further Ring work. Do not defer persistence until the end of a run. A save failure ends Ring processing and emits an authentication failure; retry the AWS write within the bounded retry policy without logging token content.
4. Share one session; serialize refresh. Configure the underlying SDK retry budgets so hidden retries do not multiply unboundedly.
5. Revoked credentials or required MFA produce reconnect-required health. Transient auth transport failures may retry; invalid credentials do not.
6. Use the maintenance/writer protocol below before replacing credentials. Disabling a schedule alone does not cancel already accepted asynchronous invocations. Keep one deployment as the writer for the account.
7. Secrets Manager is not a per-event state store. Write changed tokens only. Reuse one `ClientRequestToken` for retries of the same immutable secret payload, and use a new token for a genuinely changed payload. A 15-minute schedule does not bound refresh churn: duplicate invocations and 401 responses can cause additional refreshes. Alert and stop repeated churn rather than silently dropping a replacement token. [Secret update API](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_PutSecretValue.html).

The reviewed client calls `token_updater` synchronously, including from async refresh. Passing an `async def` callback would not ensure it is awaited. The implementation must use a bounded synchronous persistence callback, or a tested adapter that explicitly awaits persistence before releasing the next request. Inject an HTTP session with explicit timeouts: token fetch/refresh must not inherit an unbounded/default session timeout. These are release-pin verification points, not completed code. [Authentication source](https://github.com/python-ring-doorbell/python-ring-doorbell/blob/master/ring_doorbell/auth.py).

External token rotation and secret persistence cannot be a distributed transaction. If the process dies in that gap and the previous token no longer works, reconnection is required and must be visible.

### Maintenance and exclusive writer protocol

Use an account `CONTROL` item with mode (`running` or `maintenance`), owner/run ID, and the Lambda owner's hard deadline. Create it in maintenance mode during initial setup. A Lambda must conditionally acquire ownership only in running mode, before loading Ring credentials. Fail closed if the control store is unavailable. Skip safely, with a maintenance/busy status, when acquisition is denied; do not emit a healthy poll heartbeat.

Acquisition, release and reclamation are conditional updates. Store the hard deadline and a reclaim time that includes the invocation's remaining hard runtime plus the 60-second safety margin, not a short renewable lease. Automatic reclamation is allowed only after that reclaim time, when the old Lambda cannot still execute. State writes require the expected owner. Reserve concurrency one and prohibit a second independent deployment for the same account.

Setup first atomically sets maintenance mode (preserving any current owner), disables scheduling through IaC, then waits for owner release or the hard deadline. A racing invocation either acquired ownership before maintenance and must finish, or is denied afterwards. Setup then conditionally acquires its own maintenance owner; this local owner does not auto-expire. All Ring-reading CLI operations that may refresh a token use this path. A crashed setup leaves maintenance active until an operator confirms that local process has stopped and clears its owner. After successful local validation and secret persistence, release the setup owner and switch to running mode while the schedule remains disabled. Run controlled Lambda validation before re-enabling the schedule; stale queued events always re-read the gate and use the current secret. Read-only status needs no Ring session.

## Durable discovery and ledger

Use one encrypted, on-demand DynamoDB table with point-in-time recovery. Retain it on stack deletion/replacement. Do not expire unfinished work.

- Partition key: `ACCOUNT#{account_namespace}`.
- Recording sort key: `EVENT#{device_id}#{event_id}`, with bounded, escaped IDs.
- Per-device discovery keys: `SCAN#{device_id}#LIVE` and `SCAN#{device_id}#BACKFILL`.
- Account status key: `STATUS`.
- Writer/maintenance key: `CONTROL`; it is separate from observational status.
- Sparse work index: `work_partition = ACCOUNT#{namespace}#PENDING`, numeric `next_attempt_at` as sort key. Remove index attributes on terminal outcomes.
- Due-work index results are hints: strongly re-read each primary record before work. Stale index entries cannot cause an archived record to be processed again.

A ledger item stores identity, normalized event metadata, frozen object key, status, attempt count, next retry time, safe failure code, first-seen time and archive evidence. Evidence includes expected byte count, lowercase hex SHA-256, S3 version ID and verification timestamp. Track gap acknowledgement separately from outcome. No signed URLs or tokens belong here.

States:

```mermaid
stateDiagram-v2
    [*] --> pending: conditional discovery insert
    pending --> pending: transient error or media not ready
    pending --> uploaded_unverified: expected digest persisted and PUT attempted
    uploaded_unverified --> archived: HEAD matches persisted evidence
    uploaded_unverified --> pending: confirmed no object, retry
    pending --> unavailable: source confirms permanent absence
    pending --> failed: invalid media, oversize or retry ceiling
    uploaded_unverified --> failed: object evidence conflicts
    failed --> pending: explicit operator retry
    pending --> suspended: device removed or access revoked
    suspended --> pending: validated explicit resume
```

`uploaded_unverified` is also indexed for due work. It covers an uncertain PUT result; it does not assert that an object exists. Permanent states retain identity tombstones to prevent accidental re-creation after S3 expiration. No automatic TTL is set for completed identities in the MVP; document ledger growth and explicit cleanup. Restoring or deleting ledger state requires a reconciliation procedure, not a blank reset.

Recheck the allowlist and authorization before source work, including old retries and backfills. Apply allowlist changes through maintenance after the prior writer stops, then load the new selection before resuming runs. Suspend affected pending items and remove their due-work attributes; keep metadata, reason and acknowledgement visible. For an uncertain prior upload, allow S3-only reconciliation without Ring access. If S3 confirms absence and the device remains excluded, suspend rather than download. Previously archived objects follow the selected retention policy; removing a device does not silently delete its archive.

### Discovery algorithm

1. Rotate the starting device each invocation. Allocate budget to both discovery and pending transfer, rather than draining one indefinitely.
2. For a new live scan, capture `high = now_utc` and `low = completed_checkpoint - overlap`; first scan uses `now - initial_history`. Freeze both in a scan record.
3. Start from newest history and follow actual provider cursors. Persist each qualifying event with a conditional insert. A duplicate must not replace its frozen key, status or evidence.
4. Only after every item in a page is durably represented may the continuation advance. If the process dies earlier, replay that page.
5. Stop once the sorted provider history crosses the lower bound or genuinely ends. Validate order, detect repeated cursors and bound page calls. If the provider cannot prove completeness, mark the scan incomplete and alert.
6. Advance the completed checkpoint to the frozen high bound only after enumeration is complete. This is safe even when downloads remain pending because those identities are already durable.
7. If the run budget ends, save the current scan and continue next invocation. A rejected/expired cursor restarts the same bounded interval from its newest page; idempotent inserts make replay safe.
8. Backfill has independent bounds/cursor and cannot move the live checkpoint. Share time fairly with live discovery and pending work.

The overlap handles delayed visibility within its configured window. Delays longer than the overlap, source expiration during an outage, and undocumented API truncation cannot be covered by an absolute no-loss promise. Report coverage/lag and use explicit reconciliation backfills where footage is still available.

## Download, identity and upload protocol

Freeze an object key on first discovery:

```text
s3://<bucket>/videos/2026/09/22/front-door-15-09-03-<64-hex-identity-hash>.mp4
```

The suffix is SHA-256 of a canonical JSON array containing the complete account/device/event identity, not a timestamp or random retry suffix. Camera slug is lowercase ASCII, trimmed and capped at 64 characters, with `camera` as fallback. Store the chosen key in the ledger so renaming a camera cannot move an existing identity. A hash collision or mismatching identity is a hard conflict, never permission to overwrite. Validate full key length.

For each due identity:

1. Strongly read status and current device eligibility. Skip archived/unavailable/suspended items and failed items unless explicitly requeued after validation. Uncertain prior uploads may perform S3-only reconciliation even when source access is suspended.
2. If prior expected evidence exists, HEAD the frozen key first. Match identity, size and S3 SHA-256 to reconcile an upload that completed before a crash. Archived-class objects can be checked without restoring their media.
3. Resolve a fresh URL only when transfer is needed. Require HTTPS, bound redirects, and never forward Ring authorization headers to a redirected media host. Do not accept download URLs from invocation payloads.
4. Stream to an app-owned temporary directory in bounded chunks. Enforce actual byte limits even when Content-Length is missing or false. Reject empty, truncated and non-media responses; inspect the MP4 container signature in addition to MIME type. This is a sanity check, not proof that every frame decodes.
5. Calculate SHA-256 while streaming. Persist the expected size/digest and `uploaded_unverified` state BEFORE putting the object. On replay, retain prior evidence until a HEAD result proves whether its upload exists.
6. Use a single bounded `PutObject` with file body, explicit ContentLength, `IfNoneMatch="*"`, `ChecksumSHA256`, content type and user metadata. `ChecksumSHA256` is base64 of the 32 digest bytes, not the 64-character hex string stored in the ledger/metadata. Normalize the HEAD checksum to the same representation before comparing. Rewind the file body before each retry. The 256 MiB cap avoids a multipart implementation in the MVP.
7. HEAD with checksum retrieval enabled. Match size, stored identity and SHA-256; record the version ID and atomically mark archived. An ETag alone is not checksum verification.
8. For 412, reconcile; for 409 or transient error, retry/reconcile within budget. Treat only a confirmed not-found as absence. Access denied, network failures or conflicting content leave work unresolved or failed.
9. Clean up in finally. A later invocation sweeps only abandoned paths beneath the app-owned temp root after a forced kill.

S3 and DynamoDB do not commit atomically. This protocol provides repeat-safe archival with reconciliation; it does not promise exactly one network request or exactly-once execution. Retained ledger tombstones prevent automatic recreation after an intentional deletion or lifecycle expiration. Repair of a missing object for an already archived identity must be an explicit operator action.

Metadata is S3 user metadata, not object tags. Percent-encode non-ASCII text, cap the combined metadata budget below S3's limit, and keep full normalized metadata in DynamoDB. Avoid exposing device names as metric dimensions.

## Retry classification and deadlines

One operation gets three total application attempts: immediate, then jitter in [0, 2] seconds, then [0, 4] seconds. Never sleep after the last attempt. Bound SDK attempts explicitly; tests must count actual underlying calls. A 429 Retry-After longer than remaining budget schedules later work instead of sleeping past the deadline.

| Condition | Outcome |
| --- | --- |
| Transient network/5xx/throttle | Bounded retry, then persist deferred work |
| Media still processing | Later retry with fresh URL; no archived state |
| Expired media URL | Resolve once again within the operation budget |
| Revoked token/MFA required | Stop Ring work, reconnect-required alarm |
| Access denied | Visible configuration/permission failure, no retry loop |
| Source explicitly expired/deleted | Unavailable with reason, not success |
| Ambiguous 404 or missing media | Defer until source meaning is established |
| Invalid/truncated/oversize video | Failed with reason, retain identity |
| Unknown S3 outcome | Reconcile before another conditional upload |

After operation exhaustion, schedule exponential deferred retries starting at 15 minutes and capped at six hours. Count a failed processing cycle only when source processing was actually attempted, not when skipped for budget/maintenance. After 24 failed source-processing cycles or seven days waiting for source media, pause source acquisition as failed and alert; explicit operator retry remains available while the source exists. Keep `uploaded_unverified` evidence and S3 reconciliation independently eligible: the source retry ceiling or source expiry must not discard a possibly successful upload. A durable permission/conflict failure remains visible for operator repair. One event failure does not abort other events, but shared auth/state-store failures do stop unsafe progress.

Check remaining Lambda time before every request and retry. Keep 60 seconds for state/metrics/cleanup; reduce individual request deadlines accordingly. Set transport timeouts for token fetch/refresh as well as media/history. Enforce the total streaming deadline even if a server keeps sending small chunks before each read-idle timeout. Bound blocking AWS SDK calls and their retries; cancelling an async wrapper does not by itself stop an underlying thread or socket operation.

## AWS security and operations

- Private bucket, Block Public Access enabled, BucketOwnerEnforced ownership, versioning, default SSE-S3 and TLS-only bucket policy. SSE-KMS is an optional configuration with explicit key permissions.
- Processor role: GetObject/PutObject for `videos/*`, exact table/index read/write/query operations, GetSecretValue/PutSecretValue for one secret, its log group, and namespace-scoped metrics. Grant `s3:ListBucket` on this dedicated archive bucket for reliable missing-object HEAD results. Do not assume a positive `s3:prefix` condition grants that permission for HEAD; it is not a ListObjects request. This bucket contains archive data only. If bucket-wide name visibility is unacceptable, design and stage-test an exact-prefix listing fallback before changing this permission. Never convert a 403 into absence. This policy choice is an inference from [HEAD permissions](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html) and [IAM condition semantics](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html), with a required real-AWS gate.
- No runtime S3 deletion, bucket-policy changes, public ACL writes or Ring destructive operations.
- Scheduler role: invoke only the backup Lambda and send only to its delivery DLQ. Lambda execution role: send only to its configured async failure destination.
- Scheduler delivery retry age/count and Lambda async retry age/count are configured separately (proposed 15-minute age, two retries). Use two SQS queues and queue alarms; no worker queue is required in the MVP.
- CloudFormation retains archive/table/secret on deletion and replacement. The deployment artifact bucket is separate.
- No VPC by default: the function needs outbound Ring access. If a private VPC is introduced, design its internet egress and cost explicitly.
- Build/install dependencies for the chosen Linux Lambda architecture; do not zip Windows native packages.

CloudWatch emits aggregate metrics with low-cardinality dimensions. Empty successful scans publish a heartbeat; auth/discovery failure must not do so. A per-event failure can coexist with a service heartbeat. Emit an alert for every new failed/unavailable/suspended outcome and retain an `unacknowledged_gap_count` alarm until acknowledgement or resolution. An acknowledgement never changes a recording to archived. Retain latest complete discovery and last verified upload separately in the status row.

The due-work index cannot answer total failed/suspended counts or oldest unfinished age: its ordering is by retry time and terminal rows are absent. Maintain status counts transactionally with conditional state transitions (including gap acknowledgements), so replay cannot increment twice. Reconcile them with a resumable, paginated base-table query at least hourly. At this account scale, each reconciliation slice uses the same exclusive writer; checkpoint its accumulator, and account for intervening transitions or restart the sweep. Only publish complete, consistent totals as current. Derive unfinished age from first-seen time across unfinished rows, not the first due index entry. Label stale totals and alarm on reconciliation older than one hour; do not turn incomplete scans into zero backlog. Model growth and move to a dedicated aggregate/index design if hourly sweeps exceed the budget.

Alarm actions use an operator-configured notification destination. Staging must prove delivery; creating an alarm alone does not prove someone will receive it.

## Lifecycle, retrieval and cost

Use separate lifecycle rules for current transition/expiration, noncurrent expiration, expired-delete-marker cleanup, and aborting incomplete multipart uploads. Filter all video rules to `videos/`. Do not apply a transition to state or deployment artifacts.

Default current transition: 90 days to GLACIER; current expiration: 2,555 days; noncurrent expiration: one day; multipart abort: one day. Keep AWS's default exclusion for transition of objects smaller than 128 KB. Glacier Flexible Retrieval has a 90-day minimum storage charge; validate expiration >= transition + 90 when expiration is enabled. This validation covers normal current-version expiration only. An operator deleting/replacing a recently archived object can make its old version eligible for removal after one noncurrent day and incur early-deletion charges. Retain-indefinitely disables current-version expiration only; it does not disable noncurrent expiration. Versioning with this short recovery window is not immutable storage or an Object Lock retention guarantee.

Versioned expiration first creates a delete marker. Permanent deletion of the noncurrent data is later and lifecycle evaluation is asynchronous. Never describe this as guaranteed deletion at exactly seven years. Changing a policy can make existing objects immediately eligible; show that in the deployment change review.

To retrieve archived footage, request a restore, wait for its completion, then download the temporary restored copy. Document expedited/standard/bulk options and their current cost/availability at implementation time. Routine lookup should use the ledger, not repeated whole-bucket scans.

Estimate capacity from measured data:
`daily bytes = device count × average clips per device/day × mean clip bytes`.
Then model Standard bytes for the first 90 days, archival bytes thereafter, uploads/HEAD requests, transitions, secret storage, DynamoDB, Lambda, logs and restores. Do not reuse an unqualified S3 price from the initial pasted proposal.

## Correctness properties and verification

Properties P1-P18 preserve the established numbering; P19-P20 add maintenance ownership and device removal coverage. Hypothesis is useful for state transitions, pagination, keys and failure sequences; real service configuration needs template/staging checks instead of artificial randomized tests.

| Property | Invariant | Requirements | Verification |
| --- | --- | --- | --- |
| P1 | No media access before secret loading/authentication | R1.1, R1.2, R1.6 | Auth unit and setup integration |
| P2 | Token replacement is durably saved; session reused | R1.3, R1.4 | Callback failure and cold-start integration |
| P3 | Retry policy distinguishes transient/permanent auth failure | R1.4, R6.2 | Table-driven unit |
| P4 | A checkpoint never crosses unpersisted discovery pages | R2.1, R2.2, R2.3, R2.4, R2.8 | Generated pagination/crash sequences |
| P5 | Media URL is resolved at use and never persisted | R1.5, R2.7 | Unit and secret-redaction checks |
| P6 | Accepted media is nonempty, bounded and structurally plausible | R7.2 | Truncation/oversize HTTP fixtures |
| P7 | Individual failure does not lose other identities | R2.5, R2.6, R2.7 | Generated partial-failure runs |
| P8 | UTC path and safe slug match the frozen record | R3.1, R3.2 | Generated timezone/name cases |
| P9 | Metadata is complete, bounded and ASCII-safe | R3.3 | Generated Unicode/long-name cases |
| P10 | Retry/rename keeps the same key; same-second identities remain distinct | R3.2, R3.4 | Generated identity/replay cases |
| P11 | Archived requires verified size, identity and checksum | R3.5 | Crash points around PUT/HEAD/ledger write |
| P12 | Logs/metrics never leak token or signed URL test canaries | R1.5, R6.1 | Redaction regression |
| P13 | Exhausted work remains queryable and retryable or visibly failed | R2.5, R6.3 | Generated deferred-work transitions |
| P14 | Ambiguous/conditional S3 outcomes reconcile before archival | R3.4, R3.5, R6.2 | Fault injection including 403/409/412 |
| P15 | Heartbeats distinguish healthy empty polls from failed discovery | R6.4, R6.5 | Metrics unit and staging alarms |
| P16 | Summary/status include terminal gaps, acknowledgements and freshness | R6.4, R6.6, R6.7 | Mixed-state integration, replay and bounded sweep reconciliation |
| P17 | Work respects deadline; cleanup handles both graceful and forced stops | R7.1, R7.3, R7.4 | Fake clock and crash/reinvoke fixtures |
| P18 | Duplicate triggers converge on one archived identity/current key | R3.4, R5.2, R5.3, R8.3 | Replay integration with real S3 gate |
| P19 | Setup and queued/manual runs cannot concurrently refresh credentials | R1.7, R5.2 | Maintenance/acquisition race, crash deadline and cold-start tests |
| P20 | Removed or unauthorized devices cannot continue source retries | R2.9, R1.6 | Allowlist change, revoked access, S3-only reconciliation and explicit resume |

Use at least 100 generated examples for each adopted property-based test; save failing examples. Mandatory deterministic scenarios include: failed oldest event with newer successes, more history than one page, camera rename, same-second events, API ID versus hardware ID, missing subscription, synchronous token callback, rotated token save failure, lost secret-write response, PUT success followed by state failure, hex/base64 mismatch, access-denied HEAD, page crash, timeout cleanup, pending work older than overlap, retry-ceiling upload reconciliation, terminal gap persistence and maintenance/device-removal races.

Template/staging checks additionally cover R3.6, R3.7, all of R4, R5.1, R5.4, R5.5, R7.5, R7.6 and R8.1. R8.2–R8.5 are separately gated if the official adapter is built. Traceability to delivery tasks is in [tasks.md](tasks.md).

## Optional official adapter

Before implementation verify developer onboarding, device geography and required scopes. Ring documents private apps for up to five explicitly connected accounts, without public certification/publishing; this is relevant to a personal archive. The development guide's US-located-device warning is in its testing flow. Do not extend it into an independently verified worldwide production rule, or assume private apps bypass it. Record portal confirmation for this account/device combination before changing ADR-001. Use official OAuth rather than community-library tokens. [Getting started](https://developer.amazon.com/docs/ring/getting-started.html), [development guide](https://developer.amazon.com/docs/ring/develop.html).

History and media access are consent-gated. Follow returned history cursors, stop on empty pages even if a next link remains, preserve requested filters without duplicating them, and detect repeated cursors. Accept only the expected API origin/path before attaching a bearer token to a next link. The history reference prose says next links include filters while its sample comment says to reapply them; resolve this with fixtures and live acceptance rather than copying the sample literally. Distinguish provider exhaustion from proof of complete source coverage. Do not use the provider's reviewed flag as evidence that our S3 upload succeeded.

Media uses a POST followed by a 303 URL and separate GET without forwarding bearer credentials. The documented maximum is 900,000 milliseconds of footage per request, not a request timeout. Audio defaults to disabled; select and document it explicitly. Timestamp/duration fields are milliseconds; record actual returned ranges, the requested range, and 206 partial footage. The documented 180-day timestamp bound is not a promise of 180 days of available recordings. Partial footage must remain distinct from full archival and use a separately specified segment/retry design. Preserve the provider watermark. Never use the source guide's record-then-download example in this archive: normal backup retrieves existing footage only.

A webhook receiver validates the current documented HMAC/replay scheme, durably queues a hint, and acknowledges promptly. The hint accelerates discovery; polling still reconciles missed or premature notifications. A complete official adapter requires its own design extension and acceptance tests before enabling it.

