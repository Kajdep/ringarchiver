# Implementation plan: Ring Video AWS Storage

Revision: 2026-09-22. **All implementation tasks remain unstarted.** Specification work is complete; no application, tests, AWS resources or live backups exist yet.

Use [requirements.md](requirements.md), [design.md](design.md), [decisions.md](decisions.md) and [sources.md](sources.md) together. Python is selected. The distribution is `ring-doorbell`, not `python-ring-doorbell`. Required recovery/security tests are not optional.

## Delivery tasks

- [ ] 1. Establish the project and dependency contract.
  - Create `src/ringarchive/`, `tests/unit/`, `tests/property/`, `tests/integration/`, `scripts/` and `infra/`.
  - Add pyproject configuration, separate runtime/dev locks, pytest/Hypothesis, linting and type checks; ignore secrets, token files and build output.
  - Pin a released Ring client and boto3; verify actual authentication, history and media methods against it.
  - Build for Python 3.12 and the chosen Linux Lambda architecture; document the Windows workflow.
  - Requirements: R7.5, R7.6.

- [ ] 2. Implement models, configuration and storage identity.
  - Define aware UTC records, explicit ledger states, discovery bounds/cursors, deadline budget and status model.
  - Validate devices, namespace, schedule >= 15 minutes, limits and retention relationships.
  - Implement canonical identity hashing, safe slugs, frozen keys and bounded encoded metadata.
  - Test timezones/DST, Unicode, empty/long names, same-second events, rename/retry stability and invalid configuration.
  - Properties: P8, P9, P10.
  - Requirements: R3.1, R3.2, R3.3, R4.3, R5.1.

- [ ] 3. Implement interactive Ring setup and secret persistence.
  - Securely prompt for login and MFA without logging or storing passwords/codes.
  - Store a token document and stable hardware ID in the specified secret; list and validate selected devices.
  - Wire the token updater to durable replacement saves; serialize refresh and fail visibly if saving fails.
  - Classify missing subscription, revoked authorization and reconnect-required states.
  - Test no pre-auth media access, session reuse, missing/malformed secret, token-save failure, redaction and cold-start reload.
  - Properties: P1, P2, P3, P12.
  - Requirements: R1.1, R1.2, R1.3, R1.4, R1.5, R1.6.

- [ ] 4. Implement paginated history and media adapters.
  - Map actual client history parameters; preserve provider IDs and UTC timestamps.
  - Verify cursor progress and completeness; detect duplicate/bad/empty pages and unsupported device capabilities.
  - Resolve short-lived recording URLs only at transfer time; normalize transient/not-ready/unavailable results.
  - Add saved, sanitized response fixtures for multiple pages and delayed recordings.
  - Implement no Ring deletion, forced recording or public-sharing actions.
  - Properties: P4, P5.
  - Requirements: R2.1, R2.2, R2.4, R2.7, R3.7, R8.1.

- [ ] 5. Implement DynamoDB state and resumable discovery.
  - Create conditional event insertion, frozen keys, per-device live/backfill scans and status records.
  - Advance page cursors only after all events persist; advance checkpoints only for complete intervals.
  - Implement the sparse due-work index and strong primary-record rechecks.
  - Retain pending/failed records independently of discovery age and terminal tombstones after object expiration.
  - Test page crashes, incomplete traversal, invalidated cursors, stale index results, newer-success/older-failure and replay.
  - Properties: P4, P7, P13, P18.
  - Requirements: R2.3, R2.4, R2.5, R2.6, R2.8, R5.2, R5.3, R6.3.

- [ ] 6. Implement bounded streaming and verified S3 writes.
  - Stream with HTTPS/redirect rules, deadlines and size checks; validate media and calculate SHA-256.
  - Persist expected upload evidence before conditional PutObject; request checksum and compare HEAD results.
  - Handle 403/409/412, lost PUT response, mismatched object and successful PUT followed by ledger failure.
  - Distinguish object metadata from tags; avoid ETag-only verification.
  - Test empty, HTML, truncated, oversize and false Content-Length responses plus success/failure cleanup.
  - Properties: P6, P9, P11, P14, P17, P18.
  - Requirements: R3.3, R3.4, R3.5, R7.2, R7.4.

- [ ] 7. Implement retry policy and bounded orchestration.
  - Three total application attempts, jitter, Retry-After, explicit SDK retry limits and fake-clock tests.
  - Persist deferred work and apply the cycle/age ceiling; unavailable and failed are not success.
  - Allocate discovery/transfer time fairly and rotate devices; process recordings sequentially.
  - Respect remaining Lambda time and persist continuation before returning.
  - Test one event failure alongside later successes and pending recordings older than the overlap.
  - Properties: P3, P7, P13, P14, P17.
  - Requirements: R2.5, R2.6, R2.7, R6.2, R6.3, R7.1, R7.3.

- [ ] 8. Implement Lambda entry point, monitoring and operator status.
  - Construct adapters, close HTTP sessions and sweep only app-owned abandoned temporary files.
  - Emit safe structured logs, aggregate counters, service heartbeat, pending age and discovery lag.
  - Persist last healthy scan separately from last upload and reconcile summaries with durable state.
  - Implement read-only status; test empty healthy polls, auth outage, discovery outage and partial failure.
  - Properties: P12, P15, P16, P17.
  - Requirements: R1.5, R6.1, R6.4, R6.5, R6.6, R7.4.

- [ ] 9. Create AWS SAM/CloudFormation infrastructure.
  - Private encrypted versioned archive with TLS-only policy and restricted prefix; retained encrypted DynamoDB with PITR.
  - Retained secret without embedded password/token values; scoped runtime, Scheduler and deployment roles.
  - Lambda defaults from design, reserved concurrency 1, explicit logs and alarms.
  - Separate Scheduler delivery DLQ and Lambda async failure destination; configure both retry policies.
  - Schedule disabled by default; wire an operator-selected notification destination.
  - Validate IAM, bucket policy, retention on replacement/deletion, queue policies and missing-heartbeat alarms.
  - Requirements: R3.6, R3.7, R4.6, R5.1, R5.2, R5.3, R5.4, R5.5, R6.5, R7.5.

- [ ] 10. Add lifecycle and retrieval configuration.
  - Separate prefix-scoped current transition/expiration, noncurrent expiration, delete-marker and multipart cleanup rules.
  - Defaults: GLACIER after 90 days; current expiration after 2,555 days; noncurrent expiration after one day.
  - Support retain-indefinitely and reject retention shorter than minimum archival billing duration.
  - Document upload-age semantics, sub-128-KB behaviour, restore delay/cost and asynchronous permanent deletion.
  - Test rendered lifecycle rules and retrieval workflow; never claim to have waited seven years in staging.
  - Requirements: R4.1, R4.2, R4.3, R4.4, R4.5.

- [ ] 11. Provide packaging and administration commands.
  - Create Windows PowerShell setup/build/deploy instructions with a Linux-compatible package build.
  - Provide device listing, interactive auth, status, bounded backfill, selected retry and archive restore/download guidance.
  - Use IaC updates for schedule/lifecycle changes rather than scripts that silently cause configuration drift.
  - Deployment outputs contain resource identifiers only, not credentials or signed media URLs.
  - Requirements: R1.1, R1.5, R2.8, R4.3, R4.5, R5.1, R6.6, R7.5.

- [ ] 12. Complete required offline verification.
  - Cover all P1–P18 using the test method assigned in design; use at least 100 examples for each property-based test.
  - Run fault-injection integration tests with mocked Ring and AWS test doubles/emulation.
  - Validate the IaC schema and security/retention assertions; lint, type-check and build the Lambda package.
  - Record unsupported emulator behaviours, especially S3 conditional/checksum/versioning semantics.
  - Requirements: R2.1, R2.3, R2.4, R2.5, R3.4, R3.5, R5.2, R6.2, R7.6.

- [ ] 13. Complete live staging acceptance.
  - Verify actual AWS identity/region and selected account/device access; deploy with the schedule disabled.
  - Archive a real recording from each supported selected camera and verify S3 evidence and downloaded playback.
  - Replay identical events and confirm one current archive per identity; test rename behaviour.
  - Inject a recoverable failure, then prove it succeeds on a later run without skipping older work.
  - Prove real token refresh/persistence and cold-start reuse; test real S3 conditional/checksum behaviour.
  - Exercise heartbeat, backlog, auth and failure-queue alarms; verify notification receipt.
  - Validate lifecycle configuration and archive restoration separately; label anything not yet exercised.
  - Record sanitized evidence, then enable the schedule and verify consecutive runs.
  - Requirements: R1.3, R1.6, R3.4, R3.5, R4.5, R5.3, R5.4, R5.5, R6.5, R7.6.

- [ ] 14. Finish operator documentation and handover.
  - Explain the unofficial integration, subscription dependency, completeness limits and measured capacity/cost.
  - Document reconnect, backfill, retry, unavailable footage, Glacier restoration and stopping the service.
  - Document safe retained-resource teardown, ledger restore/reconciliation and explicit missing-object repair.
  - Publish actual validation evidence and unresolved limits; distinguish built, staged, scheduled and live.
  - Requirements: R1.4, R2.8, R4.5, R4.6, R6.6, R7.5, R7.6.

- [ ] 15. Deferred: official Partner API adapter and webhooks.
  - This is outside MVP acceptance. Confirm country/developer eligibility and revise the design before implementation.
  - Implement official OAuth, consent-gated history, fresh media requests, watermark preservation and partial-media handling.
  - Implement signature/replay verification, durable queueing and quick webhook acknowledgement.
  - Test duplicate hints, missed webhooks, media-not-ready, empty history with next cursor, pre-consent requests and 206 partial responses.
  - Do not mark this complete merely because community polling works.
  - Requirements: R8.1, R8.2, R8.3, R8.4, R8.5.

## Release gates

| Gate | Evidence required |
| --- | --- |
| Offline candidate | Tasks 1–12 pass; reproducible package and IaC checks recorded |
| Staging verified | Task 13 evidence, including actual Ring download and S3 reconciliation |
| MVP operational | Tasks 1–14 complete, schedule enabled and observed, notifications delivered |
| Official integration | Task 15 separately complete with its own live eligibility and media tests |

Credentials, account-specific choices and staging access are implementation prerequisites, not gaps in the specification. Do not mark implementation checkboxes based on document review alone.

