"""
DynamoDB state: deduplicate events so we never archive the same clip twice.
Table schema: event_id (PK, S), device_id (S), archived_at (S), s3_key (S).
"""
import logging
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

TABLE_NAME = os.environ.get("DYNAMO_TABLE", "RingArchiveEvents")
REGION     = os.environ.get("AWS_REGION", "eu-west-2")


def _table():
    ddb = boto3.resource("dynamodb", region_name=REGION)
    return ddb.Table(TABLE_NAME)


def is_archived(event_id: str) -> bool:
    """Return True if event_id already exists in the table."""
    resp = _table().get_item(
        Key            = {"event_id": event_id},
        ProjectionExpression = "event_id",
    )
    return "Item" in resp


def mark_archived(event_id: str, device_id: str, s3_key: str,
                  summary: str | None = None) -> None:
    """
    Conditionally insert a record.  Raises if it already exists (race safety).
    """
    item = {
        "event_id":    event_id,
        "device_id":   device_id,
        "archived_at": datetime.now(tz=timezone.utc).isoformat(),
        "s3_key":      s3_key,
    }
    if summary:
        item["summary"] = summary
    try:
        _table().put_item(
            Item                = item,
            ConditionExpression = Attr("event_id").not_exists(),
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.warning("Race: event %s already marked, skipping", event_id)
        else:
            raise


def list_recent(limit: int = 50) -> list[dict]:
    """Scan for the most recent `limit` items (for the demo CLI)."""
    resp = _table().scan(Limit=limit)
    items = resp.get("Items", [])
    return sorted(items, key=lambda x: x.get("archived_at", ""), reverse=True)[:limit]
