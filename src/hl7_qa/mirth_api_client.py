"""
mirth_api_client.py

Thin wrapper around the Mirth Connect Administrator REST API. This exists
to close the gap called out in mllp_client.py: an MLLP ACK only proves
Mirth *received* a message, not what its Filter or Transformer decided to
do with it. This client asks Mirth directly, after the fact, what
actually happened — which is the only way to really assert "the blank
PID-3 message got Filtered" instead of just hoping it did.

Auth: uses HTTP Basic Auth (an Authorization header), which Mirth
supports as an alternative to session-cookie auth. Simpler for test code
— no login/logout lifecycle or cookie jar to manage.

⚠️ A note on API shape, in the spirit of this project's own docs
Mirth's connector message statuses (RECEIVED, FILTERED, TRANSFORMED,
SENT, QUEUED, ERROR, PENDING) are stable, documented values straight from
Mirth's own Status enum. The connectorMessages shape below was guessed
twice and wrong both times before being confirmed against a real Mirth
4.5.2 server's actual response -- it's the classic Java LinkedHashMap
XStream serialization (see `_extract_connector_statuses`'s docstring for
the exact shape). The channel-list and message-list wrapping
(`_extract_items`) is confirmed against a live server too. If a future
Mirth version changes any of this, the error will point at the exact
line to adjust -- that's the same "confirmed by actually testing it"
loop Part 4 of the setup guide describes for the Transformer scripts.
"""

import base64
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

requests.packages.urllib3.disable_warnings()  # local Mirth uses a self-signed cert


class MirthAPIError(Exception):
    """Raised for any non-2xx response from the Mirth REST API, with the
    response body attached so the real error message isn't swallowed."""


@dataclass
class MessageResult:
    """A normalized view of one message's outcome across every connector
    (Source, each Destination) it passed through."""

    message_id: str
    statuses_by_connector: dict = field(default_factory=dict)  # {"Source": "TRANSFORMED", "Destination 1": "FILTERED", ...}

    def status_of(self, connector_name: str) -> Optional[str]:
        return self.statuses_by_connector.get(connector_name)

    def any_connector_has_status(self, status: str) -> bool:
        target = status.upper()
        return any(isinstance(s, str) and s.upper() == target for s in self.statuses_by_connector.values())


class MirthAPIClient:
    def __init__(self, base_url: str, username: str = "admin", password: str = "admin", verify_ssl: bool = False):
        """base_url example: https://localhost:8443/api (no trailing slash)"""
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            # Mirth's REST API (Jersey/Glassfish underneath) rejects any
            # request without this header with a 400 -- a CSRF-protection
            # quirk, confirmed by actually hitting a live server with it
            # missing. The exact value doesn't matter, just its presence.
            "X-Requested-With": "OpenAPI",
        }

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{path}"
        try:
            response = requests.get(url, headers=self._headers, params=params, verify=self.verify_ssl, timeout=10)
        except requests.exceptions.RequestException as exc:
            raise MirthAPIError(f"Could not reach Mirth API at {url}: {exc}") from exc

        if not response.ok:
            raise MirthAPIError(
                f"GET {url} returned {response.status_code}: {response.text[:500]}"
            )
        return response.json()

    @staticmethod
    def _extract_items(payload, *candidate_keys) -> list:
        """
        Mirth's REST API wraps list responses differently depending on
        version/config -- confirmed by hitting a live server that it can
        come back as the classic JAXB-style {"list": {"channel": [...]}},
        not just a bare list or a single {"channel": [...]}. This walks
        through whichever of candidate_keys are actually present, peeling
        off wrapper layers one at a time, until it lands on the real
        items -- then normalizes a lone dict into a one-item list so
        callers can always just iterate.
        """
        current = payload
        for key in candidate_keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
        if isinstance(current, dict):
            current = [current]
        if not isinstance(current, list):
            current = []
        return current

    def get_channel_id(self, channel_name: str) -> str:
        """Look up a channel's UUID by its display name (e.g. 'Hospital_to_Lab_ADT_ORM').
        Mirth's REST API addresses channels by ID, not name, everywhere else."""
        raw = self._get("/channels")
        channel_list = self._extract_items(raw, "list", "channel")

        for ch in channel_list:
            if isinstance(ch, dict) and ch.get("name") == channel_name:
                return ch["id"]

        available = [ch.get("name") if isinstance(ch, dict) else ch for ch in channel_list]
        raise MirthAPIError(
            f"No channel named '{channel_name}' found. Channels Mirth reported: {available}"
        )

    def get_messages(self, channel_id: str, limit: int = 20, include_content: bool = False) -> list:
        """Raw list of recent messages for a channel, most recent first."""
        params = {"limit": limit, "includeContent": str(include_content).lower()}
        raw = self._get(f"/channels/{channel_id}/messages", params=params)
        return self._extract_items(raw, "list", "message")

    @staticmethod
    def _extract_connector_statuses(raw_message: dict) -> dict:
        """
        Turns Mirth's connectorMessages map into {connector_name: status}.

        Confirmed against a live Mirth 4.5.2 server's actual response (both
        earlier guesses -- nested per-connector dicts, and plain metaDataId
        -> status strings -- were wrong). The real shape is the classic
        Java LinkedHashMap-as-XStream serialization:

            "connectorMessages": {
                "@class": "linked-hash-map",
                "entry": [
                    {"int": 0, "connectorMessage": {"connectorName": "Source", "status": "TRANSFORMED", ...}},
                    {"int": 1, "connectorMessage": {"connectorName": "Destination 1", "status": "FILTERED", ...}},
                    {"int": 2, "connectorMessage": {"connectorName": "Exception_Log", "status": "SENT", ...}}
                ]
            }

        Each connectorMessage already carries its own real connector name
        directly, which turned out to make the separate channel-definition
        lookup (an earlier version of this method) unnecessary -- removed
        once the real data confirmed it wasn't needed.
        """
        connector_messages = raw_message.get("connectorMessages", {})
        entries = connector_messages.get("entry", []) if isinstance(connector_messages, dict) else []
        if isinstance(entries, dict):
            entries = [entries]  # a single entry can come back unwrapped, same pattern seen elsewhere

        statuses = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            connector_msg = entry.get("connectorMessage")
            if not isinstance(connector_msg, dict):
                continue
            meta_id = connector_msg.get("metaDataId", entry.get("int"))
            name = connector_msg.get("connectorName") or f"metaDataId-{meta_id}"
            statuses[name] = connector_msg.get("status")
        return statuses

    def find_message_by_control_id(
        self, channel_id: str, control_id: str, search_limit: int = 50
    ) -> Optional[MessageResult]:
        """
        Finds the message whose raw content contains the given MSH-10
        control ID (the unique ID our message builders stamp on every
        test message) and returns its per-connector status breakdown.

        Fetches with includeContent=True and filters client-side rather
        than relying on a server-side text-search parameter, since exact
        query-param support has varied across Mirth versions — matching
        content locally is slower but far more predictable.
        """
        messages = self.get_messages(channel_id, limit=search_limit, include_content=True)
        for raw_message in messages:
            raw_text = str(raw_message)  # cheap, good-enough substring search across the whole payload
            if control_id in raw_text:
                return MessageResult(
                    message_id=str(raw_message.get("messageId", "unknown")),
                    statuses_by_connector=self._extract_connector_statuses(raw_message),
                )
        return None

    def wait_for_message(
        self, channel_id: str, control_id: str, timeout: float = 5.0, poll_interval: float = 0.5
    ) -> MessageResult:
        """
        Polls until the message shows up in Mirth's message log or the
        timeout elapses. Processing is usually near-instant, but polling
        beats a fixed sleep — it returns as soon as the message is found
        instead of always waiting the full timeout.
        """
        deadline = time.monotonic() + timeout
        last_seen = None
        while time.monotonic() < deadline:
            last_seen = self.find_message_by_control_id(channel_id, control_id)
            if last_seen is not None:
                return last_seen
            time.sleep(poll_interval)

        raise TimeoutError(
            f"Message with control ID {control_id!r} never appeared in channel {channel_id} "
            f"within {timeout}s"
        )
