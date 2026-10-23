# Research notes and sources

Initial source list dated 2026-09-22; targeted recheck completed 2026-09-23. These establish integration constraints, not proof of this operator's account or deployment. Defaults and recovery algorithms are project choices. Items 1-17 preserve the previous review's bibliography; the recheck section identifies what was actually read again in this review.

## Ring

1. [Managing Ring videos](https://ring.com/gb/en/support/articles/6shp7/managing-your-ring-videos): recorded clips require a Ring subscription. Verify the account and cameras; S3 does not replace Ring's recording service.
2. [Community Python client](https://github.com/python-ring-doorbell/python-ring-doorbell) and [package metadata](https://github.com/python-ring-doorbell/python-ring-doorbell/blob/master/pyproject.toml): repository `python-ring-doorbell`, distribution `ring-doorbell`, import `ring_doorbell`. Lock a tested release during implementation.
3. [Client authentication](https://github.com/python-ring-doorbell/python-ring-doorbell/blob/master/ring_doorbell/auth.py): synchronous token-updater callback, refresh tokens, MFA exceptions, injected HTTP session and explicit hardware ID. Verify these against the pinned release; do not pass an unawaited async token updater.
4. [Client history](https://github.com/python-ring-doorbell/python-ring-doorbell/blob/master/ring_doorbell/generic.py): `async_history` exposes `limit` and `older_than`; the latter is an event ID, not a timestamp. The client's `id` is the API ID; `device_id` is a different hardware/MAC-like identifier. Do not invent a server-side `since` parameter or interchange identifiers.
5. [Client recording download](https://github.com/python-ring-doorbell/python-ring-doorbell/blob/master/ring_doorbell/doorbot.py): URL and download methods exist, but the convenience download buffers content. Implement bounded streaming for Lambda.
6. [Official Ring development guide](https://developer.amazon.com/docs/ring/develop.html): developer registration, OAuth and webhooks are supported. Its testing section says only US-located devices are supported; private-app eligibility for this operator must be checked rather than inferred from that statement alone.
7. [Official API reference](https://developer.amazon.com/docs/ring/api-documentation.html): history and media APIs are separate from the community client's private endpoints.
8. [Release notes](https://developer.amazon.com/docs/ring/release-notes.html): the June 8, 2026 entry describes mandatory visible watermarks on Partner API media. Playground access is not production authorization.

Ring documentation MCP was consulted using search_docs and get_doc. Full documents read: `amazon_vision_api/media_clips.md` and `amazon_vision_api/event_history.md`. They document consent-gated, newest-first history; empty pages that may retain a next link; and two-step downloads (303, then binary GET). Media can return 206 partial content or 425 recording-not-ready. No Ring account was connected.

18. [Official getting-started guide](https://developer.amazon.com/docs/ring/getting-started.html), retrieved through Ring MCP as `dev_portal/getting-started.md`: private apps connect up to five accounts and skip public certification/publishing. Registration, linking and device eligibility still apply. The development guide was also retrieved in full as `dev_portal/develop.md`.

The full history reference has a discrepancy: its prose says next links include original filters, while its pagination sample comment says to reapply them. Preserve filter values without duplication and validate actual responses. The media reference's 15-minute limit is requested footage duration (900,000 ms); audio defaults off. A 180-day request bound does not establish actual retention. Its record-then-download example is outside this archive's read-only purpose and must not be adopted.

## AWS

9. [Scheduler with Lambda](https://docs.aws.amazon.com/lambda/latest/dg/with-eventbridge-scheduler.html): invokes asynchronously and requires an execution role.
10. [Lambda async failures](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html): duplicates/retries remain possible after success. Concurrency does not deduplicate.
11. [S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html): `If-None-Match: *` protects current objects; reconcile 412. Delete markers do not prevent new creation, so ledger tombstones also matter.
12. [S3 lifecycle rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intro-lifecycle-rules.html): current and noncurrent expiration are separate; age starts at S3 creation.
13. [Lifecycle API](https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutBucketLifecycleConfiguration.html): objects smaller than 128 KB do not transition by default.
14. [Archival storage](https://docs.aws.amazon.com/AmazonS3/latest/userguide/archival-storage.html): Glacier Flexible Retrieval requires restoration; requests and restored copies affect cost.
15. [Lambda timeout](https://docs.aws.amazon.com/lambda/latest/dg/configuration-timeout.html) and [runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html): execution is bounded; Python 3.12 is the proposed target, subject to package verification.
16. [Secrets Manager updates](https://docs.aws.amazon.com/secretsmanager/latest/userguide/manage_update-secret.html): updates create versions; sustained writes more than once per ten minutes risk quota exhaustion. Persist actual changes, not one copy per clip.
17. [Lifecycle transition considerations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html): Glacier Flexible Retrieval has a 90-day minimum storage duration; transitions and restoration are asynchronous, and archived objects have per-object metadata overhead.

19. [S3 HeadObject reference](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html): checksum mode, base64 SHA-256 representation, missing-object 403/404 permission differences and version handling. Test under the exact deployed role; mocked success is insufficient.
20. [IAM condition operators](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html): a positive condition on a missing context key does not match. Together with the HEAD reference, this motivates the dedicated-bucket ListBucket policy in the design; its runtime behaviour remains a real-AWS acceptance gate.
21. [PutSecretValue](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_PutSecretValue.html): `ClientRequestToken` supplies idempotency for a version/payload. Reuse it on an uncertain retry of that same payload. Avoid fresh version IDs for each retry.

## Skills, tools and targeted recheck

- Read the installed Amazon Devices `amazon-devices-vega-best-practices` SKILL.md and its complete `react_native_for_vega_development_best_practices.md` reference through the Amazon Devices Builder Tools MCP. Listed its WORKFLOW and SKILL catalogs after setting the empty project context; no `.adbt-config.json` exists here. These capabilities target Fire OS/Vega, not this Python AWS service, so no TV build workflow was applied.
- No standalone Ring SKILL.md was found in the installed skill roots, plugin cache or local Claude skill directory. Ring development guidance was instead read in full from the available Ring Appstore knowledge MCP: getting-started, development, event-history and media-clips documents named above. This is a documentation capability, not access to a Ring account.
- Read the installed `engineering:documentation` skill for documentation structure and maintenance. Exact local skill paths and tool limitations are in the [review log](../../../docs/reviews/2026-09-22-documentation-review.md).
- Fresh web reads: community `auth.py`, `generic.py`, `doorbot.py`; AWS Scheduler-to-Lambda, Lambda async error handling, Secrets Manager updates/PutSecretValue, S3 conditional writes/HeadObject, IAM conditions and lifecycle transition considerations. GitHub `master` links are moving references, not a dependency lock; task 1 must record an immutable release/commit.
- No current Ring credentials, cloud resources, recordings, installed app runtime or package lock were verified. No claimed live result is derived from these documentation reads.

## Live checks still needed

- Exact client release, pagination completeness, delayed-event behaviour and media quality.
- Device country, subscription, configured Ring retention and recording availability.
- AWS region, real workload, IAM, alarms, token refresh and Lambda package compatibility.
- Developer access and current limits before implementing the official adapter.

No storage-price promise is made. Calculate from measured clip sizes, chosen region, request counts, retention and restore workload using current regional AWS pricing.

