"""
python -m ringarchive.list_clips

Lists archived clips with pre-signed S3 URLs (valid 1 hour).
"""
from __future__ import annotations
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import boto3
from .state import list_recent

BUCKET     = os.environ.get("ARCHIVE_BUCKET", "")
REGION     = os.environ.get("AWS_REGION", "eu-west-2")
EXPIRY_SEC = 3600


def main() -> None:
    items = list_recent(50)
    if not items:
        print("No archived clips found.")
        return

    s3 = boto3.client("s3", region_name=REGION)
    print(f"{'Event ID':<45} {'Archived At':<27} {'Summary'}")
    print("-" * 120)
    for item in items:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": item["s3_key"]},
            ExpiresIn=EXPIRY_SEC,
        )
        summary = item.get("summary", "(no summary)")
        print(f"{item['event_id']:<45} {item['archived_at']:<27} {summary}")
        print(f"  {url}")

if __name__ == "__main__":
    main()
