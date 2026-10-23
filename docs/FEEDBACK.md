# Feedback — RingArchive Hackathon

## Ring API

**What worked well:**
- The official Ring Partner API documentation at `developer.amazon.com/docs/ring` is comprehensive and well-structured.  
  The JSON:API device discovery, event history, and media clip download flows are clearly documented with request/response examples.
- The two required extra headers (`User-Agent` and `Hardware_Id`) were documented prominently and easy to implement.
- Token refresh via `POST https://oauth.ring.com/oauth/token` with `grant_type=refresh_token` is standard OAuth2 and Just Works.
- The staging/simulator environment is a genuine time-saver — no real doorbell needed for a hackathon.

**What was hard:**
- The `github.com/amzn/ring-api-helloworld` URL in the hackathon brief returned 404; the repo appears to have moved or been removed.  
  We had to fall back to reading the official documentation directly.
- The media clips endpoint (`POST /v1/devices/{id}/media/video/download`) returns a `303 See Other` redirect rather than inline bytes.  
  Python `requests` follows redirects automatically when `allow_redirects=True`, but the behaviour is not obvious from the quick-reference table.
- The `Hardware_Id` header must be a stable UUID per user — the docs note this but do not specify how to generate or persist it.  
  We derived it via `uuid.uuid5` from a fixed namespace string, which is deterministic across Lambda cold starts.
- Account linking (the full nonce flow) is not necessary for a private single-account backup, but the docs default to describing the full partner flow.  
  For a hackathon MVP with a pre-issued refresh token, you can skip straight to the refresh-token-to-access-token step, which is buried in the "Quick Start: If You Already Have a Refresh Token" section.
- No official Python SDK exists; the docs say to use standard `requests`. That is fine but means re-implementing retry, token refresh, and redirect handling from scratch.

## AWS Lambda + S3 + DynamoDB

**What worked well:**
- SAM with `Transform: AWS::Serverless-2016-10-31` made Lambda + EventBridge schedule + S3 + DynamoDB + Secrets Manager deployable in one YAML.
- DynamoDB conditional writes (`ConditionExpression = Attr("event_id").not_exists()`) provide race-free deduplication for free.
- S3 lifecycle rules (Glacier after 90 days) are one block of YAML.

**What was hard:**
- The DynamoDB condition check returns a `ConditionalCheckFailedException` on a duplicate, which must be caught explicitly — not obvious from the boto3 docs without searching.
- SAM `sam deploy --guided` asks for every Parameter including `RingAccessToken` as plaintext on the terminal; there is no built-in SecureString prompt. For a real deployment you would pre-create the secret and pass only the ARN.

## Kiro

**What worked well:**
- Kiro read the official Ring API docs directly from `developer.amazon.com` in real time, which caught the 404 on the sample repo and let the project pivot instantly.
- Code generation was fast and accurate — `ring_client.py`, `archiver.py`, `state.py`, and the SAM template were produced in one pass without structural errors.
- The conductor/worker model handled the sequential build well without losing context between steps.

**What was hard:**
- Memory pressure on the host (0.7 GB free) prevented parallel sub-agent dispatch; the entire build had to be single-threaded.
  A machine with more headroom would let Kiro parallelize writing tests, docs, and infrastructure at the same time.
- Kiro does not have direct access to the Ring simulator, so we cannot verify a live end-to-end flow without manual steps.
