"""
Integration tests against the real Hospital_to_Lab_ADT_ORM channel
(port 6661), over a genuine TCP/MLLP socket — the same thing the
PowerShell script in Part 2 proved by hand, now repeatable and assertable.

IMPORTANT — what an ACK does and doesn't prove:
MLLP's ACK (MSA|AA|... or MSA|AR|...) confirms Mirth received the message,
and — as confirmed by running this against a live instance — *can* also
reflect the Filter's decision (AR for rejected), depending on how the
channel's source connector is configured to respond. Don't assume this
generalizes to every channel, though: a channel configured to always
respond "Success" regardless of downstream processing would ACK "AA" even
for a Filtered message. The REST-API-based tests in
test_mirth_api_verification.py check the actual Mirth-reported status
directly, which is the configuration-independent way to know for sure —
treat the ACK-level checks here as a fast first signal, not the final word.

What these tests DO prove, and it's real, useful coverage:
  - the channel is up and actually listening on the right port
  - Mirth accepts well-formed messages at the transport level
  - a completely different message type doesn't crash the channel
"""

import pytest

from hl7_qa import messages
from hl7_qa.mllp_client import get_ack_code

pytestmark = pytest.mark.integration


class TestChannelIsReachable:
    def test_hospital_channel_accepts_a_clean_adt(self, hospital_channel):
        message = messages.adt_a01(mrn="MRN700001", broken_pid3=False)
        ack = hospital_channel.send(message)
        assert get_ack_code(ack) == "AA", f"Expected Application Accept, got raw ACK: {ack!r}"

    def test_hospital_channel_accepts_a_clean_orm(self, hospital_channel):
        message = messages.orm_o01(order_id="ORD70001", broken_obr4=False)
        ack = hospital_channel.send(message)
        assert get_ack_code(ack) == "AA", f"Expected Application Accept, got raw ACK: {ack!r}"

    def test_ack_echoes_back_the_original_message_control_id(self, hospital_channel):
        # MSH-10 is the control ID; a compliant ACK includes it in MSA-2
        # so the sender can match the ACK to the message it sent.
        message = messages.adt_a01(mrn="MRN700002")
        control_id = messages.get_field(message, "MSH", 9)  # MSH-1 offsets the split by one
        ack = hospital_channel.send(message)
        assert control_id in ack


class TestKnownDefectsStillReachTheChannel:
    """
    These don't assert Filtered/Exception status yet (see module docstring)
    — they confirm the malformed-but-technically-valid messages at least
    reach Mirth without the socket itself erroring out, which is the
    prerequisite for the Filter/Transformer logic getting a chance to run
    at all.
    """

    def test_blank_pid3_message_is_rejected_at_transport_level(self, hospital_channel):
        """
        Originally written assuming the ACK can't reveal Filter outcome --
        that assumption was wrong for this channel's configuration.
        Running this against a live Mirth instance showed the ACK itself
        comes back as AR (Application Reject) for a Filtered message, not
        AA. That's actually stronger, simpler proof the Filter works than
        the REST-API round trip in test_mirth_api_verification.py -- for
        *this* channel, anyway. (A channel configured to always ACK 'AA'
        regardless of downstream processing wouldn't show this, which is
        exactly why that REST-API-based test still exists as a
        configuration-independent check.)
        """
        message = messages.adt_a01(broken_pid3=True)
        ack = hospital_channel.send(message)
        assert get_ack_code(ack) == "AR", f"Expected the Filter's rejection to surface as AR, got raw ACK: {ack!r}"

    def test_blank_obr4_message_is_still_accepted_at_transport_level(self, hospital_channel):
        message = messages.orm_o01(broken_obr4=True)
        ack = hospital_channel.send(message)
        assert get_ack_code(ack) == "AA"


class TestLabChannelReceivesOruDirectly:
    def test_lab_channel_accepts_a_clean_oru(self, lab_channel):
        message = messages.oru_r01(missing_result_status=False)
        ack = lab_channel.send(message)
        assert get_ack_code(ack) == "AA"
