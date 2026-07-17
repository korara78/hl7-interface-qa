"""
Unit tests for src/hl7_qa/messages.py

These don't touch the network at all — they just prove our test-data
generator produces exactly the message shape we expect. This matters
because every integration test downstream trusts these builders; if the
builders are wrong, the integration tests are testing the wrong thing
without anyone noticing.

Run with:  pytest tests/unit -v
"""

from hl7_qa.messages import adt_a01, orm_o01, oru_r01, get_field


class TestAdtA01:
    def test_clean_message_has_populated_mrn(self):
        message = adt_a01(mrn="MRN999", broken_pid3=False)
        assert get_field(message, "PID", 3) == "MRN999^^^HOSPITAL^MR"

    def test_broken_message_has_empty_pid3(self):
        message = adt_a01(broken_pid3=True)
        assert get_field(message, "PID", 3) == ""

    def test_message_type_is_adt_a01(self):
        message = adt_a01()
        assert "ADT^A01" in message

    def test_uses_carriage_return_segment_separator(self):
        # A common beginner mistake is joining segments with \n instead of \r.
        # Real HL7 (and Mirth) expects \r.
        message = adt_a01()
        assert "\r" in message
        assert "\n" not in message


class TestOrmO01:
    def test_clean_message_has_populated_obr4(self):
        message = orm_o01(order_id="ORD1", broken_obr4=False)
        assert "BASIC METABOLIC PANEL" in get_field(message, "OBR", 4)

    def test_broken_message_has_empty_obr4(self):
        message = orm_o01(order_id="ORD1", broken_obr4=True)
        assert get_field(message, "OBR", 4) == ""

    def test_order_id_appears_in_both_orc_and_obr(self):
        message = orm_o01(order_id="ORD777")
        assert get_field(message, "ORC", 2) == "ORD777"
        assert get_field(message, "OBR", 2) == "ORD777"


class TestOruR01:
    def test_clean_message_marks_all_results_final(self):
        message = oru_r01(missing_result_status=False)
        obx_lines = [seg for seg in message.split("\r") if seg.startswith("OBX|")]
        assert len(obx_lines) == 3
        for i in range(len(obx_lines)):
            assert get_field(message, "OBX", 11, occurrence=i) == "F"

    def test_broken_message_is_missing_result_status(self):
        message = oru_r01(missing_result_status=True)
        # Field 11 shouldn't exist at all on the broken version -- the line
        # simply ends early, same defect described in hl7_practice_messages.md
        assert get_field(message, "OBX", 11, occurrence=0) == ""

    def test_order_id_links_result_back_to_original_order(self):
        message = oru_r01(order_id="ORD42")
        assert get_field(message, "OBR", 2) == "ORD42"


class TestGetFieldHelper:
    def test_returns_empty_string_for_missing_segment(self):
        message = adt_a01()
        assert get_field(message, "ZZZ", 1) == ""

    def test_returns_empty_string_for_out_of_range_field(self):
        message = adt_a01()
        assert get_field(message, "PID", 999) == ""

    def test_occurrence_selects_the_right_repeated_segment(self):
        message = oru_r01()
        first_obx_value = get_field(message, "OBX", 5, occurrence=0)
        second_obx_value = get_field(message, "OBX", 5, occurrence=1)
        assert first_obx_value != second_obx_value
