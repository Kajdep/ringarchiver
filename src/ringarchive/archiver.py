"""
Archiver: download a Ring clip and upload it to S3.
S3 key pattern: s3://<bucket>/<device_id>/<YYYY>/<MM>/<DD>/<event_id>.mp4
"""
import logging
import os
from datetime import datetime, timezone

import boto3

from .ring_client import RingClient

logger = logging.getLogger(__name__)

BUCKET = os.environ.get("ARCHIVE_BUCKET", "")
REGION = os.environ.get("AWS_REGION", "eu-west-2")


def _s3_key(device_id: str, event_id: str, timestamp_ms: int) -> str:
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    return f"{device_id}/{dt:%Y}/{dt:%m}/{dt:%d}/{event_id}.mp4"


def archive_clip(client: RingClient, device_id: str, event_id: str,
                 timestamp_ms: int, duration_ms: int = 30_000) -> str | None:
    """
    Download the clip and upload to S3.
    Returns the S3 key on success, None if media is not available.
    """
    try:
        video_bytes = client.download_video(device_id, timestamp_ms, duration_ms)
    except FileNotFoundError as e:
        logger.warning("Media not available: %s", e)
        return None

    key = _s3_key(device_id, event_id, timestamp_ms)
    s3  = boto3.client("s3", region_name=REGION)
    logger.info("Uploading %d bytes to s3://%s/%s", len(video_bytes), BUCKET, key)
    s3.put_object(
        Bucket      = BUCKET,
        Key         = key,
        Body        = video_bytes,
        ContentType = "video/mp4",
    )
    logger.info("Uploaded s3://%s/%s", BUCKET, key)
    return key
