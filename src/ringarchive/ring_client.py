"""
Ring client using the official Amazon Vision API.
Reads credentials from environment or AWS Secrets Manager.

Access-token-only mode: set RING_ACCESS_TOKEN (no client_id/secret/refresh needed).
Token refresh is skipped in this mode.
"""
import json
import os
import uuid
import logging
import boto3
import requests
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

RING_OAUTH_URL = "https://oauth.ring.com/oauth/token"
AVA_BASE_URL   = "https://api.amazonvision.com"
APP_NAME       = "RingArchive/1.0"


class TokenExpiredError(Exception):
    pass


def _hardware_id() -> str:
    raw = os.environ.get("RING_HARDWARE_ID")
    if raw:
        return raw
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "ringarchive.internal"))


def _load_secret(secret_name: str) -> dict:
    sm = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "eu-west-2"))
    try:
        resp = sm.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise RuntimeError(f"Cannot load secret {secret_name}: {e}") from e
    return json.loads(resp["SecretString"])


def _save_secret(secret_name: str, payload: dict) -> None:
    sm = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "eu-west-2"))
    try:
        sm.put_secret_value(SecretId=secret_name, SecretString=json.dumps(payload))
    except ClientError as e:
        logger.error("Failed to persist refreshed token: %s", e)
        raise


class RingClient:
    """Thin wrapper around the official Ring (Amazon Vision) API."""

    def __init__(self, access_token: str, refresh_token: str | None = None,
                 client_id: str | None = None, client_secret: str | None = None,
                 secret_name: str | None = None):
        self._access_token  = access_token
        self._refresh_token = refresh_token
        self._client_id     = client_id
        self._client_secret = client_secret
        self._secret_name   = secret_name
        self._can_refresh   = bool(refresh_token and client_id and client_secret)
        self._session       = requests.Session()
        self._session.headers.update({
            "User-Agent":   APP_NAME,
            "Hardware_Id":  _hardware_id(),
            "Content-Type": "application/json",
        })

    @classmethod
    def from_env(cls) -> "RingClient":
        secret_name = os.environ.get("RING_SECRET_NAME")
        if secret_name:
            creds = _load_secret(secret_name)
        else:
            creds = {
                "access_token":  os.environ["RING_ACCESS_TOKEN"],
                "refresh_token": os.environ.get("RING_REFRESH_TOKEN"),
                "client_id":     os.environ.get("RING_CLIENT_ID"),
                "client_secret": os.environ.get("RING_CLIENT_SECRET"),
            }
        return cls(
            access_token  = creds["access_token"],
            refresh_token = creds.get("refresh_token"),
            client_id     = creds.get("client_id"),
            client_secret = creds.get("client_secret"),
            secret_name   = secret_name,
        )

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _refresh(self) -> None:
        if not self._can_refresh:
            logger.warning("Token expired and no refresh credentials available.")
            raise TokenExpiredError("No refresh credentials; get a new access token from the Playground.")
        logger.info("Refreshing Ring access token")
        resp = self._session.post(
            RING_OAUTH_URL,
            data={
                "grant_type":    "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id":     self._client_id,
                "client_secret": self._client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        tokens = resp.json()
        self._access_token  = tokens["access_token"]
        self._refresh_token = tokens["refresh_token"]
        if self._secret_name:
            payload = _load_secret(self._secret_name)
            payload["access_token"]  = self._access_token
            payload["refresh_token"] = self._refresh_token
            _save_secret(self._secret_name, payload)

    def _get(self, path: str, **kwargs) -> dict:
        url = f"{AVA_BASE_URL}{path}"
        resp = self._session.get(url, headers=self._auth_headers(), **kwargs)
        if resp.status_code == 401:
            self._refresh()
            resp = self._session.get(url, headers=self._auth_headers(), **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict, **kwargs) -> requests.Response:
        url = f"{AVA_BASE_URL}{path}"
        resp = self._session.post(url, json=body, headers=self._auth_headers(), **kwargs)
        if resp.status_code == 401:
            self._refresh()
            resp = self._session.post(url, json=body, headers=self._auth_headers(), **kwargs)
        return resp

    def list_devices(self) -> list[dict]:
        data = self._get("/v1/devices")
        return data.get("data", [])

    def list_events(self, device_id: str, event_types: str = "motion,ding",
                    page_key: str | None = None) -> tuple[list[dict], str | None]:
        params: dict = {"event_types": event_types}
        if page_key:
            params["page[key]"] = page_key
        data = self._get(f"/v1/history/devices/{device_id}/events", params=params)
        events    = data.get("data", [])
        next_link = data.get("links", {}).get("next")
        next_key  = None
        if next_link and "page[key]=" in next_link:
            next_key = next_link.split("page[key]=", 1)[1]
        return events, next_key

    def download_video(self, device_id: str, timestamp_ms: int,
                       duration_ms: int = 30_000) -> bytes:
        body = {
            "timestamp": timestamp_ms,
            "duration":  duration_ms,
            "video_options": {
                "codec":      "avc",
                "frame_rate": 15,
                "resolution": {"width": 1280, "height": 720},
            },
            "audio_options": {"audio_enabled": False},
        }
        resp = self._post(f"/v1/devices/{device_id}/media/video/download",
                          body, allow_redirects=True)
        if resp.status_code in (416, 425):
            raise FileNotFoundError(f"Media not ready for {device_id}@{timestamp_ms}: {resp.status_code}")
        if resp.status_code not in (200, 206):
            resp.raise_for_status()
        return resp.content
