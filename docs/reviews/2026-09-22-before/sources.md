# Research notes and sources

Checked 2026-09-22. These establish integration constraints, not proof of this operator's account or deployment. Defaults and recovery algorithms are project choices.

## Ring

1. [Managing Ring videos](https://ring.com/gb/en/support/articles/6shp7/managing-your-ring-videos): recorded clips require a Ring subscription. Verify the account and cameras; S3 does not replace Ring's recording service.
2. [Community Python client](https://github.com/python-ring-doorbell/python-ring-doorbell) and [package metadata](https://github.com/python-ring-doorbell/python-ring-doorbell/blob/master/pyproject.toml): repository `python-ring-doorbell`, distribution `ring-doorbell`, import `ring_doorbell`. Lock a tested release during implementation.
3. [Client authentication](https://github.com/python-ring-doorbell/python-ring-doorbell/blob/master/ring_doorbell/auth.py): token-updater callback, refresh tokens, MFA exceptions and explicit hardware ID. Verify these against the pinned release.
4. [Client history](https://github.com/python-ring-doorbell/python-ring-doorbell/blob/master/ring_doorbell/generic.py): `async_history` exposes `limit` and `older_than`; the latter is an event ID, not a timestamp. Do not invent a server-side `since` parameter.
5. [Client recording download](https://github.com/python-ring-doorbell/python-ring-doorbell/blob/master/ring_doorbell/doorbot.py): URL and download methods exist, but the convenience download buffers content. Implement bounded streaming for Lambda.
6. [Official Ring development guide](https://developer.amazon.com/docs/ring/develop.html): developer registration, OAuth and webhooks are supported. The testing section currently says only US-located devices are supported. Verify operator eligibility.
7. [Official API reference](https://developer.amazon.com/docs/ring/api-documentation.html): history and media APIs are separate from the community client's private endpoints.
8. [Release notes](https://developer.amazon.com/docs/ring/release-notes.html): the June 8, 2026 entry describes mandatory visible watermarks on Partner API media. Playground access is not production authorization.

Ring documentation MCP was consulted using search_docs and get_doc. Full documents read: `amazon_vision_api/media_clips.md` and `amazon_vision_api/event_history.md`. They document consent-gated, newest-first history; empty pages that may retain a next link; and two-step downloads (303, then binary GET). Media can return 206 partial content or 425 recording-not-ready. No Ring account was connected.

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

## Live checks still needed

- Exact client release, pagination completeness, delayed-event behaviour and media quality.
- Device country, subscription, configured Ring retention and recording availability.
- AWS region, real workload, IAM, alarms, token refresh and Lambda package compatibility.
- Developer access and current limits before implementing the official adapter.

No storage-price promise is made. Calculate from measured clip sizes, chosen region, request counts, retention and restore workload using current regional AWS pricing.

