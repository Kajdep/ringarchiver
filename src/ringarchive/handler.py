"""
AWS Lambda handler.  Triggered by EventBridge every 15 minutes.
"""
import json
import logging
import os

from .ring_client import RingClient
from .archiver    import archive_clip
from .state       import is_archived, mark_archived
from .summariser  import summarise_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_EVENTS_PER_RUN = int(os.environ.get("MAX_EVENTS_PER_RUN", "20"))


def run_once(client: RingClient) -> dict:
    """
    Core logic: list devices, fetch recent events, archive new clips.
    Returns a summary dict for logging / testing.
    """
    archived = []
    skipped  = []
    errors   = []

    devices = client.list_devices()
    logger.info("Found %d device(s)", len(devices))

    for device in devices:
        device_id   = device["id"]
        device_name = device.get("attributes", {}).get("name", device_id)
        processed   = 0

        events, _ = client.list_events(device_id)
        for event in events:
            if processed >= MAX_EVENTS_PER_RUN:
                break
            event_id     = event["id"]
            attrs        = event.get("attributes", {})
            timestamp_ms = attrs.get("start", 0)
            event_type   = attrs.get("event_type", "unknown")

            if is_archived(event_id):
                skipped.append(event_id)
                processed += 1
                continue

            try:
                s3_key = archive_clip(client, device_id, event_id, timestamp_ms)
            except Exception as e:
                logger.error("Failed to archive %s: %s", event_id, e)
                errors.append(event_id)
                processed += 1
                continue

            if s3_key is None:
                # Media not ready; will retry next run
                processed += 1
                continue

            summary = summarise_event(device_name, event_type, timestamp_ms)
            mark_archived(event_id, device_id, s3_key, summary)
            archived.append(event_id)
            processed += 1

    result = {
        "archived": len(archived),
        "skipped":  len(skipped),
        "errors":   len(errors),
        "ids":      archived,
    }
    logger.info("Run complete: %s", json.dumps(result))
    return result


def lambda_handler(event, context):          # noqa: D103
    client = RingClient.from_env()
    return run_once(client)
