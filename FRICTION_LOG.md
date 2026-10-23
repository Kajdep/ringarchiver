# RingArchive Friction Log
1) Task: Run the archiver unattended. Steps: generated Playground token, set RING_ACCESS_TOKEN, deployed Lambda. Expected: runs on schedule indefinitely. Actual: token expired after ~30 min; no refresh option in access-token mode. Severity: High. Workaround: manual token rotation via .env for demo. Suggestion: allow refresh tokens or longer-lived dev tokens for Playground apps.

2) Task: Download a clip right after a motion event. Expected: media available immediately. Actual: recording not finalized yet, download fails/empty. Severity: Medium. Workaround: delayed fetch + retry on next 15-min run, DynamoDB dedupe. Suggestion: "media ready" webhook or a status field on the event.

3) Task: Bill Kiro to my AWS account with credits. Steps: Kiro console > create subscription via IAM Identity Center. Actual: "Your account is not currently eligible to create new subscriptions". Severity: Medium. Workaround: kept using personal Kiro login; opened AWS Support case. Suggestion: clearer eligibility message and self-serve fix.

4) Task: Set up AWS tooling on Windows. Actual: AWS Control could not read Windows AWS profiles and required WSL. Severity: Low. Workaround: used plain aws configure + SAM. Suggestion: native Windows profile support or a clear prerequisite note.
