"""
import_mirth_channels.py

Bootstraps a *fresh* Mirth instance (like the one GitHub Actions spins up
from scratch) into the same working state as the local dev instance: waits
for the API to come up, imports the two exported channels from
mirth-config/, and deploys them.

This only exists for CI. Locally, channels are built once by hand in the
Administrator and just sit there in the Docker volume -- there's never a
need to "import" them on your own machine. In CI, every run starts from a
genuinely empty Mirth container, so this script is what recreates the
Hospital_to_Lab_ADT_ORM / Lab_Receives_ADT_ORM setup Part 2 and Part 4 walk
through building manually.

⚠️ Confirmed against a real GitHub Actions run (not just Mirth's docs): the
import endpoint (POST /channels, raw XML body) worked on the first guess.
The deploy endpoint (POST /channels/_deploy) did not -- two reasonable
JSON-body shapes (a bare array of IDs, and a wrapped object) both failed
identically with a generic 500, which turned out to mean the endpoint
doesn't consume a body at all. It expects channelId as a query parameter
instead. Same "guess, run it for real, fix it" loop mirth_api_client.py
went through against the live Mirth server -- just one more example of it.
"""

import sys
import time
import base64
from pathlib import Path

import requests

requests.packages.urllib3.disable_warnings()

MIRTH_API_BASE = "https://localhost:8443/api"
MIRTH_USERNAME = "admin"
MIRTH_PASSWORD = "admin"
CHANNEL_DIR = Path(__file__).parent.parent / "mirth-config"
READY_TIMEOUT_SECONDS = 120


def _headers():
    credentials = base64.b64encode(f"{MIRTH_USERNAME}:{MIRTH_PASSWORD}".encode()).decode()
    return {
        "Authorization": f"Basic {credentials}",
        "Accept": "application/json",
        "X-Requested-With": "OpenAPI",
    }


def wait_for_mirth_api():
    """Mirth's REST API isn't reachable the instant the container starts --
    the server needs time to fully boot. Poll /server/status (a lightweight,
    unauthenticated-friendly endpoint) until it responds, or give up after
    READY_TIMEOUT_SECONDS."""
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    print(f"Waiting for Mirth API at {MIRTH_API_BASE} ...")
    while time.monotonic() < deadline:
        try:
            resp = requests.get(f"{MIRTH_API_BASE}/server/status", headers=_headers(), verify=False, timeout=5)
            if resp.ok:
                print("Mirth API is up.")
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(3)
    raise TimeoutError(f"Mirth API never became reachable within {READY_TIMEOUT_SECONDS}s")


def import_and_deploy_channel(xml_path: Path):
    """Imports one channel from its exported XML, then deploys it by ID.
    Mirth's import endpoint accepts the raw channel XML directly."""
    print(f"Importing {xml_path.name} ...")
    channel_xml = xml_path.read_text()

    import_headers = _headers()
    import_headers["Content-Type"] = "application/xml"

    resp = requests.post(
        f"{MIRTH_API_BASE}/channels",
        headers=import_headers,
        data=channel_xml.encode("utf-8"),
        verify=False,
        params={"override": "true"},
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"Failed to import {xml_path.name}: {resp.status_code} {resp.text}")

    # Pull the channel's id back out of the XML we just sent, so we know what to deploy.
    # Mirth channel XML has a top-level <id>...</id> element.
    import re
    match = re.search(r"<id>([a-f0-9-]+)</id>", channel_xml)
    if not match:
        raise RuntimeError(f"Could not find a channel <id> in {xml_path.name}")
    channel_id = match.group(1)

    print(f"Deploying {xml_path.name} (id={channel_id}) ...")
    # Confirmed against a real GitHub Actions run: this endpoint does NOT
    # consume a JSON request body (neither a bare array of IDs nor a
    # wrapped object -- both tried first and both failed identically with
    # a generic 500, which was the tell that the body wasn't being parsed
    # at all). It expects channelId as a query parameter instead.
    deploy_resp = requests.post(
        f"{MIRTH_API_BASE}/channels/_deploy",
        headers=_headers(),
        params={"channelId": channel_id, "returnErrors": "true"},
        verify=False,
        timeout=60,
    )

    if not deploy_resp.ok:
        raise RuntimeError(f"Failed to deploy {xml_path.name}: {deploy_resp.status_code} {deploy_resp.text}")

    print(f"{xml_path.name} imported and deployed.")


def main():
    wait_for_mirth_api()

    xml_files = sorted(CHANNEL_DIR.glob("*.xml"))
    if not xml_files:
        print(f"No channel XML files found in {CHANNEL_DIR} -- nothing to import.")
        sys.exit(1)

    for xml_path in xml_files:
        import_and_deploy_channel(xml_path)

    print(f"Done. Imported and deployed {len(xml_files)} channel(s).")


if __name__ == "__main__":
    main()