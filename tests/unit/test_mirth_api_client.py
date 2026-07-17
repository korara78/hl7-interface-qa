"""
Unit tests for mirth_api_client.py, using unittest.mock to fake the HTTP
layer entirely. This proves our parsing logic is correct against
representative Mirth API responses, without needing a live server —
exactly the kind of test you want fast and running on every commit.

The live-server end of this (does Mirth's *real* response actually match
what we're mocking here?) is what tests/integration/test_mirth_api_client.py
covers instead.
"""

from unittest.mock import patch, MagicMock

import pytest

from hl7_qa.mirth_api_client import MirthAPIClient, MirthAPIError, MessageResult


def _mock_response(json_body, status_code=200, ok=True):
    mock_resp = MagicMock()
    mock_resp.ok = ok
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_body
    mock_resp.text = str(json_body)
    return mock_resp


@pytest.fixture
def client():
    return MirthAPIClient(base_url="https://localhost:8443/api", username="admin", password="admin")


class TestGetChannelId:
    def test_finds_channel_id_by_name_bare_list_response(self, client):
        fake_channels = [
            {"id": "aaa-111", "name": "Hospital_to_Lab_ADT_ORM"},
            {"id": "bbb-222", "name": "Lab_Receives_ADT_ORM"},
        ]
        with patch("requests.get", return_value=_mock_response(fake_channels)):
            channel_id = client.get_channel_id("Lab_Receives_ADT_ORM")
        assert channel_id == "bbb-222"

    def test_finds_channel_id_by_name_wrapped_response(self, client):
        # Some Mirth responses wrap the list under a "channel" key instead
        # of returning a bare list -- the client should handle both.
        fake_channels = {"channel": [{"id": "ccc-333", "name": "Hospital_to_Lab_ADT_ORM"}]}
        with patch("requests.get", return_value=_mock_response(fake_channels)):
            channel_id = client.get_channel_id("Hospital_to_Lab_ADT_ORM")
        assert channel_id == "ccc-333"

    def test_finds_channel_id_in_list_wrapped_response(self, client):
        # The shape actually returned by a live Mirth 4.5.2 server: an
        # extra "list" wrapper around "channel" -- caught by running this
        # against a real instance, not by guessing.
        fake_channels = {
            "list": {
                "channel": [
                    {"id": "ddd-444", "name": "Hospital_to_Lab_ADT_ORM"},
                    {"id": "eee-555", "name": "Lab_Receives_ADT_ORM"},
                ]
            }
        }
        with patch("requests.get", return_value=_mock_response(fake_channels)):
            channel_id = client.get_channel_id("Lab_Receives_ADT_ORM")
        assert channel_id == "eee-555"

    def test_raises_clear_error_when_channel_name_not_found(self, client):
        fake_channels = [{"id": "aaa-111", "name": "Some_Other_Channel"}]
        with patch("requests.get", return_value=_mock_response(fake_channels)):
            with pytest.raises(MirthAPIError, match="No channel named"):
                client.get_channel_id("Does_Not_Exist")


class TestFindMessageByControlId:
    def test_returns_none_when_control_id_not_present_in_any_message(self, client):
        fake_messages = [{"messageId": "1", "connectorMessages": {}, "rawData": "unrelated content"}]
        with patch("requests.get", return_value=_mock_response(fake_messages)):
            result = client.find_message_by_control_id("chan-id", "MSGDOESNOTEXIST")
        assert result is None

    def test_handles_list_wrapped_message_response(self, client):
        # Matches the real shape seen from a live Mirth 4.5.2 server: the
        # message list itself wrapped in "list" -> "message".
        fake_response = {
            "list": {
                "message": [
                    {
                        "messageId": "99",
                        "rawData": "contains MSGWRAPPED somewhere",
                        "connectorMessages": {
                            "entry": [
                                {"int": 0, "connectorMessage": {"connectorName": "Source", "status": "SENT"}},
                            ]
                        },
                    }
                ]
            }
        }
        with patch("requests.get", return_value=_mock_response(fake_response)):
            result = client.find_message_by_control_id("chan-id", "MSGWRAPPED")
        assert result is not None
        assert result.message_id == "99"

    def test_extracts_per_connector_status_from_real_linked_hash_map_shape(self, client):
        # This is the confirmed real shape from a live Mirth 4.5.2 server --
        # connectorMessages is a Java LinkedHashMap serialized as
        # {"entry": [{"int": <metaDataId>, "connectorMessage": {...}}, ...]},
        # not a plain dict keyed by metaDataId (two earlier guesses at this
        # were wrong; this is what real testing against a live server showed).
        fake_messages = [
            {
                "messageId": "42",
                "rawData": "MSH|^~\\&|...|MSG12345||...",
                "connectorMessages": {
                    "@class": "linked-hash-map",
                    "entry": [
                        {"int": 0, "connectorMessage": {"metaDataId": 0, "connectorName": "Source", "status": "TRANSFORMED"}},
                        {"int": 1, "connectorMessage": {"metaDataId": 1, "connectorName": "Destination 1", "status": "FILTERED"}},
                        {"int": 2, "connectorMessage": {"metaDataId": 2, "connectorName": "Exception_Log", "status": "SENT"}},
                    ],
                },
            }
        ]
        with patch("requests.get", return_value=_mock_response(fake_messages)):
            result = client.find_message_by_control_id("chan-id", "MSG12345")

        assert isinstance(result, MessageResult)
        assert result.message_id == "42"
        assert result.status_of("Source") == "TRANSFORMED"
        assert result.status_of("Destination 1") == "FILTERED"
        assert result.status_of("Exception_Log") == "SENT"

    def test_handles_a_single_entry_not_wrapped_in_a_list(self, client):
        # When there's only one connector, some serializers emit a bare
        # dict for "entry" instead of a one-item list -- same "singleton
        # collections don't get wrapped" quirk seen elsewhere in this API.
        fake_messages = [
            {
                "messageId": "43",
                "rawData": "MSGSINGLE",
                "connectorMessages": {
                    "entry": {"int": 0, "connectorMessage": {"connectorName": "Source", "status": "SENT"}}
                },
            }
        ]
        with patch("requests.get", return_value=_mock_response(fake_messages)):
            result = client.find_message_by_control_id("chan-id", "MSGSINGLE")
        assert result.status_of("Source") == "SENT"

    def test_any_connector_has_status_is_case_insensitive(self, client):
        result = MessageResult(
            message_id="1",
            statuses_by_connector={"Destination 1": "FILTERED"},
        )
        assert result.any_connector_has_status("filtered") is True
        assert result.any_connector_has_status("SENT") is False

    def test_any_connector_has_status_ignores_non_string_values_without_crashing(self, client):
        # Guards against the exact bug hit against a live server: a status
        # value that isn't a plain string (e.g. malformed/partial data)
        # shouldn't crash any_connector_has_status, just not match.
        result = MessageResult(
            message_id="1",
            statuses_by_connector={"Weird": None, "Also Weird": ["not", "a", "string"], "Source": "SENT"},
        )
        assert result.any_connector_has_status("SENT") is True
        assert result.any_connector_has_status("FILTERED") is False


class TestErrorHandling:
    def test_non_ok_response_raises_mirth_api_error_with_body(self, client):
        with patch("requests.get", return_value=_mock_response({"error": "unauthorized"}, status_code=401, ok=False)):
            with pytest.raises(MirthAPIError, match="401"):
                client.get_channel_id("Anything")

    def test_connection_failure_raises_mirth_api_error(self, client):
        import requests as requests_module
        with patch("requests.get", side_effect=requests_module.exceptions.ConnectionError("refused")):
            with pytest.raises(MirthAPIError, match="Could not reach Mirth API"):
                client.get_channel_id("Anything")


class TestWaitForMessage:
    def test_returns_immediately_when_message_already_present(self, client):
        fake_messages = [
            {
                "messageId": "7",
                "rawData": "contains MSGFAST somewhere",
                "connectorMessages": {
                    "entry": [{"int": 0, "connectorMessage": {"connectorName": "Source", "status": "SENT"}}]
                },
            }
        ]
        with patch("requests.get", return_value=_mock_response(fake_messages)):
            result = client.wait_for_message("chan-id", "MSGFAST", timeout=2, poll_interval=0.1)
        assert result.message_id == "7"

    def test_raises_timeout_error_when_message_never_appears(self, client):
        with patch("requests.get", return_value=_mock_response([])):
            with pytest.raises(TimeoutError, match="never appeared"):
                client.wait_for_message("chan-id", "MSGNEVER", timeout=0.3, poll_interval=0.1)
