"""
Shared fixtures for the whole test suite.

Config is read from environment variables so this works whether Mirth is
running in Docker on localhost (per Part 1 of the setup guide) or on a
different host later (e.g. a CI runner). Sensible localhost defaults mean
you don't have to set anything for local use.
"""

import os
import pytest

from hl7_qa.mllp_client import MLLPClient
from hl7_qa.mirth_api_client import MirthAPIClient

HOSPITAL_CHANNEL_HOST = os.environ.get("MIRTH_HOST", "127.0.0.1")
HOSPITAL_CHANNEL_PORT = int(os.environ.get("HOSPITAL_CHANNEL_PORT", "6661"))
LAB_CHANNEL_PORT = int(os.environ.get("LAB_CHANNEL_PORT", "6662"))

MIRTH_API_BASE_URL = os.environ.get("MIRTH_API_BASE_URL", "https://localhost:8443/api")
MIRTH_API_USERNAME = os.environ.get("MIRTH_API_USERNAME", "admin")
MIRTH_API_PASSWORD = os.environ.get("MIRTH_API_PASSWORD", "admin")

HOSPITAL_CHANNEL_NAME = "Hospital_to_Lab_ADT_ORM"
LAB_CHANNEL_NAME = "Lab_Receives_ADT_ORM"


@pytest.fixture(scope="session")
def mirth_api():
    """Mirth Administrator REST API client, used to verify actual Filter /
    Transformer outcomes rather than just the MLLP-level ACK."""
    return MirthAPIClient(MIRTH_API_BASE_URL, MIRTH_API_USERNAME, MIRTH_API_PASSWORD)


@pytest.fixture(scope="session")
def hospital_channel_id(mirth_api):
    return mirth_api.get_channel_id(HOSPITAL_CHANNEL_NAME)


@pytest.fixture(scope="session")
def lab_channel_id(mirth_api):
    return mirth_api.get_channel_id(LAB_CHANNEL_NAME)


@pytest.fixture(scope="session")
def hospital_channel():
    """MLLP client pointed at Hospital_to_Lab_ADT_ORM (port 6661)."""
    return MLLPClient(HOSPITAL_CHANNEL_HOST, HOSPITAL_CHANNEL_PORT)


@pytest.fixture(scope="session")
def lab_channel():
    """MLLP client pointed at Lab_Receives_ADT_ORM (port 6662)."""
    return MLLPClient(HOSPITAL_CHANNEL_HOST, LAB_CHANNEL_PORT)


def pytest_collection_modifyitems(config, items):
    """
    Skips only the tests actually located under tests/integration/ when
    Mirth isn't reachable — unit tests are never touched by this check.

    (An earlier version of this used a session-scoped autouse fixture that
    checked "is anything in this session an integration test," which
    accidentally skipped the *entire* suite, unit tests included, any time
    both folders ran together. Caught by actually running the full suite,
    not just each folder individually — worth remembering.)
    """
    has_integration_tests = any("integration" in str(item.fspath) for item in items)
    if not has_integration_tests:
        return

    probe = MLLPClient(HOSPITAL_CHANNEL_HOST, HOSPITAL_CHANNEL_PORT)
    if probe.is_reachable():
        return

    skip_reason = pytest.mark.skip(
        reason=(
            f"Mirth isn't reachable at {HOSPITAL_CHANNEL_HOST}:{HOSPITAL_CHANNEL_PORT} — "
            "start the Docker container (see docs/01_local_environment_setup.md) "
            "before running integration tests."
        )
    )
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(skip_reason)
