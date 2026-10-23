# Ring Archive operations specification

Reviewed 2026-09-23. **The service and its CLI are not implemented.** These procedures are acceptance requirements for implementation and staging. Step names below describe required behaviour; they are not runnable application commands.

File: `D:\ringarchive\docs\operations.md`  
Folder: `D:\ringarchive\docs`

Read alongside the [design](../.kiro/specs/ring-video-aws-storage/design.md), [tasks](../.kiro/specs/ring-video-aws-storage/tasks.md) and [source notes](../.kiro/specs/ring-video-aws-storage/sources.md).

## Before first deployment

Record the AWS account/region, archive bucket, ledger, secret ARN, account namespace, device API IDs, selected provider/version, device country, subscription/access check, retention choices and notification destination. Store resource identifiers in an operator record; keep passwords, tokens, one-time codes and signed URLs out of it.

Evaluate official private-app eligibility at this point. Keep the community adapter as the proposed baseline unless eligibility and media requirements justify a documented change. Test one existing downloadable recording per selected camera; no operation should start a live session to manufacture a backup.

The required deployment sequence is:

1. Complete offline/package/IaC checks and create retained resources with scheduling disabled and CONTROL in maintenance mode.
2. Acquire the setup owner, perform interactive MFA login, validate device API IDs/access, persist the token and close the local Ring session.
3. Release the setup owner, switch CONTROL to running, keep scheduling disabled and invoke controlled Lambda validation.
4. Verify the S3 object/version, byte count and checksum; download and play the actual clip. Record any quality/audio differences and measured transfer time.
5. Exercise later-run recovery, token refresh/cold-start reuse, missing/denied HEAD, maintenance races, device removal and notification delivery.
6. Enable scheduling through IaC, observe consecutive runs and document coverage. A successful deployment is not evidence of a successful backup.

## Pause, reconnect and resume

Use the design's shared CONTROL protocol; a local setup process must not race a Lambda refreshing the same token.

1. Enter maintenance atomically, preserving any active owner. Disable scheduling through IaC. Record the maintenance reason/time.
2. Wait for the current Lambda to release ownership or exceed its recorded reclaim time (hard deadline plus the safety margin). Already queued invocations must check the gate and skip Ring work.
3. Acquire the exclusive local maintenance owner. Prompt securely for login/MFA, retain the stable hardware ID, and persist each replacement token before continuing.
4. Revalidate selected devices. On failure, leave maintenance active with a visible error and close the local session.
5. On success, close the session, release setup ownership and switch to running with scheduling still disabled. Run controlled Lambda validation, then re-enable scheduling.
6. If setup crashes, confirm that the exact local process is no longer running before clearing its owner. Do not auto-expire an owner that may still be interacting with Ring.

A maintenance skip is not a healthy poll. Record any deliberate alarm suppression and its expiry; restore alarms on resume. Do not use reserved concurrency zero as proof that all queued events were safely drained.

## Diagnose a coverage gap

| Observation | Action | Evidence needed before resolving |
| --- | --- | --- |
| No healthy heartbeat for one hour | Check maintenance state, Lambda errors/throttling, Scheduler delivery and async failure queues | New complete discovery plus delivered notification |
| Discovery lag over one hour | Check pagination progress, device ordering, provider errors and scan budgets | Complete bounded interval; do not advance a stuck checkpoint manually |
| Old unfinished work | Inspect first-seen age, source expiry, classification and retry time | Archived evidence or explicit failed/unavailable outcome |
| Empty retry index but reported gaps | Inspect terminal failed/unavailable/suspended rows and acknowledgements | Operator acknowledges or repairs each gap; empty index is not success |
| Status totals older than one hour | Resume/recover ledger summary reconciliation and inspect capacity | Complete consistent sweep with an updated timestamp |
| Token write or refresh failure | Stop Ring processing, verify Secrets Manager permissions/quota, then reconnect if necessary | Saved token reused by a new invocation |
| Unknown PUT outcome | Preserve prior size/digest; reconcile S3 before source download | Matching checksum/identity/version or confirmed absence |
| S3 HEAD 403 | Check runtime IAM, bucket policy and optional KMS permissions | Resolve permissions; never treat 403 as a missing object |

Status must show counts and gaps per device, last complete discovery, last verified upload and the age of the status calculation. A verified upload timestamp is historical; lifecycle or a later deletion can make that object unavailable now.

## Backfill, retry and device removal

- Backfill uses an explicit UTC range and a separate cursor; it cannot move the live checkpoint. Work older than the source's retention/consent boundary may be unrecoverable.
- Retry identifies explicit failed records, validates current device access, and preserves their frozen keys and evidence. Do not delete the ledger to force a retry.
- Remove a device through maintenance and a controlled configuration change after the prior writer has stopped. The new allowlist takes effect before resuming processing. Suspend its pending source work; queued retries must also check the current allowlist. S3-only reconciliation of an uncertain earlier upload may continue.
- Re-enable only after validating access and explicitly resuming suspended identities. Retain prior outcomes and reasons.
- Acknowledge a gap with operator/time/reason. Acknowledgement affects alert status, not whether the recording is archived.

## Retrieve footage

Use the ledger to find the exact object key and recorded version ID. Check that version's current storage/restore status using an operator role; the normal writer does not need restore/delete permissions. S3 Standard objects can be downloaded directly. For GLACIER objects, request restoration for a chosen availability period and retrieval tier, wait for completion, then download the restored version. Restoration does not move the original to Standard or reset its lifecycle.

Compare the downloaded file's length and SHA-256 with ledger evidence, then verify playback. In PowerShell, an actual downloaded file can be checked using:

```powershell
# Replace this example with the absolute path to the downloaded recording.
Get-FileHash -Algorithm SHA256 -LiteralPath 'D:\ringarchive\downloads\recording.mp4'
```

The command reports hex; the S3 checksum API uses base64 of the same digest bytes. Conversion and equality must be tested by the implemented storage adapter. Restore requests/copies may incur charges; choose options using current regional AWS documentation/pricing when performing a restore.

## Retention and recovery

Defaults apply from S3 upload age, so a backfilled old recording receives a new S3 retention clock. The 2,555-day expiration approximates seven years; deletion is asynchronous. Current-version expiration creates a delete marker before noncurrent data is removed.

The one-day noncurrent expiration leaves a short recovery window after accidental replacement/deletion. Removing a recently archived version can incur minimum-storage charges. Retain-indefinitely omits current-version expiration only. Versioning is not Object Lock; this specification does not promise immutable footage.

For ledger recovery, enter maintenance and stop writers first. Restore the table into a separate recovery table using the chosen backup/PITR point; compare it with the existing archive and any recoverable newer ledger evidence. Reconcile frozen keys, versions, checksums, scan continuations and tombstones before switching the deployed table reference through IaC. Do not start with an empty ledger against an existing bucket. Where lost ledger data makes intent impossible to establish, retain the uncertainty and require explicit repair decisions. Prove the recovery procedure in staging before calling it supported.

For a missing object whose ledger says archived, determine whether retention/manual deletion was intentional. Repair requires an explicit identity selection and audit record; do not automatically recreate expired footage.

## Stop the service and hand over

Enter maintenance, disable scheduling and let the active writer finish. Stop/close local setup processes. Confirm Lambda, schedule and alarms state. Retained S3, DynamoDB, secret and any retained logs continue to exist and may accrue charges after stack deletion. Archive deletion is a separate deliberate procedure and is not part of normal backup or this review.

The implementation handover must include the actual command syntax, pinned dependencies, infrastructure revision, sanitized staging evidence, measured workload/cost assumptions, notification receipt, recovery/restore results and outstanding gaps. Use the [release gates](../.kiro/specs/ring-video-aws-storage/tasks.md); document any procedure that has not been exercised.
