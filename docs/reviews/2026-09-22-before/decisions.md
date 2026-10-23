# Architecture decisions: Ring Video AWS Storage

## ADR-001: Polling adapter for the initial personal archive

**Status:** Proposed implementation baseline, retained from the supplied plan.
**Date:** 2026-09-22.
**Deciders:** Project owner; deployment implementer verifies account suitability.

### Context

The existing plan selects Python and a personal Ring account. Device country and official developer access are not supplied. Ring now documents an official Partner API; the spec must not confuse it with the community Python client.

### Decision

Build one self-hosted polling service using a version-pinned `ring-doorbell` adapter. Keep provider-specific authentication and pagination isolated. Defer the official adapter rather than assuming its prerequisites are satisfied.

### Options considered

| Option | Complexity | Operating characteristics | Main consequence |
| --- | --- | --- | --- |
| Community Python polling | Low initial setup | Private API can change; periodic discovery | Fits existing plan; requires compatibility checks and outage alerts |
| Official Partner API | Higher setup: developer access/OAuth | Documented history, media and webhooks | Must establish current geography, scopes and program access |
| Persistent unofficial push bridge | Extra always-running service | Faster hints but another failure mode | Unnecessary for a 15-minute backup goal |

### Trade-off analysis

The community path is provisional, not an assertion that Ring lacks a public developer API. The official guide currently limits testing to US-located devices, and Partner API media has additional watermark/consent/partial-content behaviour. Switching provider is a deliberate feature, not a library substitution. [Official development guide](https://developer.amazon.com/docs/ring/develop.html), [release notes](https://developer.amazon.com/docs/ring/release-notes.html).

### Consequences and action items

- [ ] Confirm account/device downloads and pin the client before coding against it.
- [ ] Surface revoked tokens, changing private endpoints and incomplete coverage.
- [ ] Revisit the provider decision if the owner supplies eligible official developer access.
- [ ] Do not promise original-quality equivalence across providers without comparing actual downloads.

## ADR-002: Per-recording DynamoDB ledger

**Status:** Proposed.
**Date:** 2026-09-22.
**Deciders:** Project owner; implementation follows the documented recovery invariants.

### Context

A single S3 JSON timestamp cannot represent failed older videos, a partially enumerated page or an upload that succeeded just before a crash. Advancing it to the newest successful event can permanently skip older failures.

### Decision

Use DynamoDB conditional inserts for recording identities, separate discovery checkpoints and pending work, and store expected upload evidence. Keep one Lambda writer per account and conditionally create S3 objects.

### Options considered

| Option | Complexity | Recovery capability | Cost/scaling |
| --- | --- | --- | --- |
| Single timestamp in S3 | Lowest | Cannot represent per-event failure safely | Cheap but insufficient |
| Full ledger JSON in S3 | Moderate once conditional updates are added | Requires whole-document concurrency/recovery | Rewrites grow with history |
| DynamoDB ledger | Moderate | Per-item conditions, due-work queries, resumable scans | Extra managed service; measured request/storage cost |
| Discovery plus SQS workers | Highest initially | Independent transfer scaling | Adds token coordination and queue operations |

### Trade-off analysis

DynamoDB adds infrastructure but makes failure recovery explicit. A worker queue is not needed for the initial account scale. S3 remains the video store; DynamoDB holds only bounded metadata and state.

### Consequences and action items

- [ ] Implement strong state rechecks after due-work index queries.
- [ ] Test every crash boundary around discovery, upload and verification.
- [ ] Retain terminal identity tombstones and protect ledger recovery.
- [ ] Add queue workers only after measurements show one Lambda cannot keep up.

## ADR-003: Private versioned archive with explicit lifecycle semantics

**Status:** Proposed; retains the source spec's 90-day transition and approximate seven-year retention.
**Date:** 2026-09-22.
**Deciders:** Operator selects final retention during deployment.

### Context

Versioning protects against accidental replacement, but current-version expiration alone does not permanently remove old data. Archival reduces hot storage at the cost of delayed retrieval.

### Decision

Use private versioned S3, conditional writes, SHA-256 verification and prefix-scoped lifecycle rules. Add noncurrent-version expiration and delete-marker cleanup. Retain bucket/state/secret on stack deletion.

### Options considered

| Option | Complexity | Benefit | Trade-off |
| --- | --- | --- | --- |
| Unversioned bucket | Lower | Simple expiration | No version recovery |
| Versioned bucket with complete lifecycle | Moderate | Recoverable versions and explicit expiry | Must manage noncurrent objects |
| S3 Standard only | Lower retrieval complexity | Immediate access | More hot storage retained |
| Glacier Flexible Retrieval after 90 days | Restore workflow needed | Separate archive tier | Retrieval delay and additional charges |

### Consequences and action items

- [ ] Implement separate current, noncurrent and delete-marker rules.
- [ ] Label 2,555 days accurately; do not promise exact calendar deletion.
- [ ] Explain that lifecycle age begins at upload, including historical backfills.
- [ ] Verify restore/download and estimate cost with the chosen region and actual clip sizes.

Technical evidence and unresolved live checks are listed in [sources.md](sources.md).

