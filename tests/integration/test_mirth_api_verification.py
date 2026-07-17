"""
Integration tests that close the gap left in test_hospital_to_lab_channel.py:
send a message over real MLLP, then ask Mirth's REST API what actually
happened to it (Filtered? Transformed? Routed to the exception log?)
instead of only trusting the transport-level ACK.

These map directly onto the three defects this whole project is built
around, and the exact outcomes Part 4 of the setup guide documents as
"confirmed working":
  - blank PID-3      -> Filtered on Hospital_to_Lab_ADT_ORM
  - blank OBR-4      -> Destination 1 Filtered, Exception_Log Sent
  - missing OBX-11   -> Transformer runs on Lab_Receives_ADT_ORM

Requires both Mirth's MLLP listeners (6661/6662) AND its REST API
(8443 by default) to be reachable -- see docs/01_local_environment_setup.md.
"""

import pytest

from hl7_qa import messages

pytestmark = pytest.mark.integration


def _control_id(message: str) -> str:
    """MSH-10 (control ID) — see messages.get_field's docstring for why
    the index is 9, not 10, specifically for the MSH segment."""
    return messages.get_field(message, "MSH", 9)


class TestPid3FilterIsActuallyEnforced:
    def test_blank_pid3_adt_gets_filtered_not_just_acked(
        self, hospital_channel, mirth_api, hospital_channel_id
    ):
        message = messages.adt_a01(broken_pid3=True)
        control_id = _control_id(message)

        hospital_channel.send(message)  # MLLP ACK alone can't prove the filter caught it

        result = mirth_api.wait_for_message(hospital_channel_id, control_id, timeout=8)
        # The channel-level Filter (the PID-3 check) runs as part of the
        # Source connector's own processing, so its rejection shows up as
        # the Source connector's status -- not any particular destination's.
        assert result.status_of("Source") == "FILTERED", (
            f"Expected the blank-PID-3 message to be Filtered at the Source, but Mirth reports: "
            f"{result.statuses_by_connector}"
        )

    def test_clean_adt_is_not_filtered(self, hospital_channel, mirth_api, hospital_channel_id):
        message = messages.adt_a01(mrn="MRN800001", broken_pid3=False)
        control_id = _control_id(message)

        hospital_channel.send(message)

        result = mirth_api.wait_for_message(hospital_channel_id, control_id, timeout=8)
        # Checking the Source specifically, not any_connector_has_status:
        # a destination like Exception_Log can legitimately report FILTERED
        # for a message that simply doesn't match *that destination's own*
        # filter (e.g. "isException != true") without the message being
        # rejected by the channel-level Filter at all. Confirmed by running
        # this against a live server -- Exception_Log reports FILTERED for
        # every non-exception message, which is correct, expected behavior,
        # not a sign anything's wrong.
        assert result.status_of("Source") != "FILTERED", (
            f"A clean ADT shouldn't be Filtered at the Source, but Mirth reports: {result.statuses_by_connector}"
        )


class TestObr4ExceptionRouting:
    def test_blank_obr4_orm_is_flagged_to_exception_log(
        self, hospital_channel, mirth_api, hospital_channel_id
    ):
        message = messages.orm_o01(order_id="ORDEXC001", broken_obr4=True)
        control_id = _control_id(message)

        hospital_channel.send(message)

        result = mirth_api.wait_for_message(hospital_channel_id, control_id, timeout=8)
        # Per Part 4: the original TCP Sender destination should be Filtered,
        # and the Exception_Log destination should be Sent instead.
        assert result.status_of("Exception_Log") == "SENT", (
            f"Expected Exception_Log to receive the blank-OBR-4 order. Got: {result.statuses_by_connector}"
        )

    def test_clean_orm_reaches_the_lab_not_the_exception_log(
        self, hospital_channel, mirth_api, hospital_channel_id
    ):
        message = messages.orm_o01(order_id="ORDCLEAN001", broken_obr4=False)
        control_id = _control_id(message)

        hospital_channel.send(message)

        result = mirth_api.wait_for_message(hospital_channel_id, control_id, timeout=8)
        assert result.status_of("Exception_Log") != "SENT", (
            f"A clean order shouldn't reach Exception_Log. Got: {result.statuses_by_connector}"
        )


class TestObx11DefaultingTransformerRuns:
    def test_missing_result_status_message_is_transformed_not_errored(
        self, lab_channel, mirth_api, lab_channel_id
    ):
        """
        Confirms the Transformer actually ran (rather than the message
        erroring out) on an ORU missing OBX-11 entirely. This checks the
        connector *status*, not yet the transformed field content itself
        (see README 'Next steps' — reading back the actual transformed
        OBX-11 value via the message content API is the next layer to add).
        """
        message = messages.oru_r01(missing_result_status=True)
        control_id = _control_id(message)

        lab_channel.send(message)

        result = mirth_api.wait_for_message(lab_channel_id, control_id, timeout=8)
        assert not result.any_connector_has_status("ERROR"), (
            f"Expected the Transformer to handle the missing OBX-11 cleanly, "
            f"not error out. Got: {result.statuses_by_connector}"
        )
