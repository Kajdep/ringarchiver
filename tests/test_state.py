"""
Unit tests for the deduplication / state layer.
Uses moto to mock DynamoDB — no real AWS required.
"""
import os
import pytest

# Ensure moto intercepts before any boto3 calls
os.environ.setdefault("DYNAMO_TABLE",    "RingArchiveEvents")
os.environ.setdefault("AWS_REGION",      "eu-west-2")
os.environ.setdefault("AWS_ACCESS_KEY_ID",     "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

import boto3
from moto import mock_aws

from ringarchive.state import is_archived, mark_archived, list_recent


@pytest.fixture(autouse=True)
def dynamo_table():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="eu-west-2")
        ddb.create_table(
            TableName            = "RingArchiveEvents",
            KeySchema            = [{"AttributeName": "event_id", "KeyType": "HASH"}],
            AttributeDefinitions = [{"AttributeName": "event_id", "AttributeType": "S"}],
            BillingMode          = "PAY_PER_REQUEST",
        )
        yield


def test_new_event_not_archived():
    assert not is_archived("evt-001")


def test_mark_and_detect():
    mark_archived("evt-002", "dev-a", "dev-a/2024/01/01/evt-002.mp4")
    assert is_archived("evt-002")


def test_idempotent_mark():
    """Second mark_archived for the same id should not raise (race path)."""
    mark_archived("evt-003", "dev-a", "dev-a/2024/01/01/evt-003.mp4")
    # Second call must not raise
    mark_archived("evt-003", "dev-a", "dev-a/2024/01/01/evt-003.mp4")


def test_different_events_are_independent():
    mark_archived("evt-004", "dev-a", "dev-a/2024/01/01/evt-004.mp4")
    assert not is_archived("evt-005")


def test_list_recent_returns_items():
    mark_archived("evt-010", "dev-b", "dev-b/2024/01/01/evt-010.mp4", summary="Motion detected")
    mark_archived("evt-011", "dev-b", "dev-b/2024/01/01/evt-011.mp4")
    items = list_recent(10)
    ids = [i["event_id"] for i in items]
    assert "evt-010" in ids
    assert "evt-011" in ids


def test_summary_stored():
    mark_archived("evt-020", "dev-c", "dev-c/2024/01/01/evt-020.mp4", summary="Front door motion")
    items = list_recent(10)
    match = [i for i in items if i["event_id"] == "evt-020"]
    assert match[0]["summary"] == "Front door motion"
