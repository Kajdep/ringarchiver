# Ring Archive

Specification for a Python service that copies available Ring recordings to private AWS S3 storage every 15 minutes.

**Current status: specification reviewed and revised; application not implemented or deployed.**

Document validation: 49 unique acceptance criteria all mapped to tasks; 18 correctness properties; 15 ordered implementation tasks; 15 local document links checked. These are specification checks, not application test results.

## Read the specification

Folder: `D:\ringarchive\.kiro\specs\ring-video-aws-storage`

- [Requirements](.kiro/specs/ring-video-aws-storage/requirements.md): eight requirement groups with testable acceptance criteria.
- [Design](.kiro/specs/ring-video-aws-storage/design.md): architecture, durable recovery, storage, security, lifecycle and 18 correctness properties.
- [Implementation tasks](.kiro/specs/ring-video-aws-storage/tasks.md): 15 ordered tasks, including a separately deferred official API integration.
- [Architecture decisions](.kiro/specs/ring-video-aws-storage/decisions.md): provider, state-store and archive tradeoffs.
- [Research sources](.kiro/specs/ring-video-aws-storage/sources.md): Ring/AWS evidence checked on 2026-09-22 and remaining live checks.

## What changed from the supplied Kiro draft

- Corrected the installable Python distribution to `ring-doorbell`.
- Distinguished community polling from Ring's now-documented official Partner API.
- Replaced a single last-check timestamp with durable per-recording retry state.
- Added stable identity suffixes, conditional uploads and checksum-based verification.
- Specified interactive MFA setup, persisted token refresh and credential redaction.
- Corrected retry counts, pagination, duplicate invocation handling and forced-timeout cleanup.
- Completed lifecycle handling for versioned objects and documented restoration.
- Made essential tests required and separated offline validation from live backup evidence.

The original three files are preserved in:
`D:\ringarchive\.kiro\specs\ring-video-aws-storage\original-2026-09-22`

## Proposed MVP

One Ring account, selected cameras, scheduled Lambda, DynamoDB ledger, Secrets Manager and private versioned S3. The local computer is needed for setup and administration, not continuous operation. A Ring subscription with accessible recordings is a prerequisite.

No public webhook or gallery is required for the MVP. An official Partner API adapter is deferred until geography and developer access are verified. Its documentation currently restricts testing to US-located devices; it must not be assumed suitable for this operator.

Implementation begins with task 1. AWS region, device allowlist and final retention are deployment inputs; credentials are entered through a local secure setup flow, not committed to the repository.

