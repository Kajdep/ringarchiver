"""
Optional: use Bedrock (Claude Haiku) to write a one-line clip summary.
Set env BEDROCK_SUMMARY_ENABLED=true to activate.
"""
import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

ENABLED = os.environ.get("BEDROCK_SUMMARY_ENABLED", "false").lower() == "true"
MODEL   = "anthropic.claude-haiku-20240307-v1:0"
REGION  = os.environ.get("AWS_REGION", "eu-west-2")


def summarise_event(device_name: str, event_type: str, timestamp_ms: int) -> str | None:
    """
    Return a one-line summary string, or None if Bedrock is disabled.
    """
    if not ENABLED:
        return None
    prompt = (
        f"Write ONE sentence describing a Ring doorbell event. "
        f"Device: {device_name}. Event type: {event_type}. "
        f"Time (epoch ms): {timestamp_ms}. Be concise and factual."
    )
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body   = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens":        64,
        "messages":          [{"role": "user", "content": prompt}],
    })
    try:
        resp    = client.invoke_model(modelId=MODEL, body=body)
        result  = json.loads(resp["body"].read())
        return result["content"][0]["text"].strip()
    except Exception as e:
        logger.warning("Bedrock summarise failed: %s", e)
        return None
