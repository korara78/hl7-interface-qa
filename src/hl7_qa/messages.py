"""
messages.py

Builds HL7 v2 test messages for our mock patient (Jane Doe). Each function
returns a ready-to-send message string, using \\r as the segment separator
(the actual HL7 standard — not \\n, which is a common beginner mistake).

Two flavors of each message type:
  - a clean version (should sail through the pipeline)
  - a defective version (matches the exact real-world bugs documented in
    hl7_practice_messages.md — blank PID-3, blank OBR-4, missing OBX-11)

Keeping these in one place means every test — unit or integration —
references the same known-good and known-bad data, instead of copy-pasted
HL7 strings scattered across test files.
"""

from datetime import datetime


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _control_id(prefix: str) -> str:
    # Unique-ish per test run so repeated runs don't collide in Mirth's message log
    return f"{prefix}{datetime.now().strftime('%H%M%S%f')}"


def adt_a01(mrn: str = "MRN100001", broken_pid3: bool = False) -> str:
    """ADT^A01 patient admit. Set broken_pid3=True to reproduce the
    real-world 'empty PID-3' defect (parses fine, breaks patient matching)."""
    pid3 = "" if broken_pid3 else f"{mrn}^^^HOSPITAL^MR"
    return "\r".join([
        f"MSH|^~\\&|HOSPITAL|MAINCAMPUS|LAB|LABSYSTEM|{_timestamp()}||ADT^A01|{_control_id('MSG')}|P|2.3",
        f"EVN|A01|{_timestamp()}",
        f"PID|1||{pid3}||DOE^JANE^A||19850315|F|||123 MAIN ST^^PHOENIX^AZ^85001||6235551234",
        "PV1|1|I|WARD1^101^A|||||1234^SMITH^JOHN^A|||||||||||1",
    ])


def orm_o01(order_id: str = "ORD5001", mrn: str = "MRN100001", broken_obr4: bool = False) -> str:
    """ORM^O01 lab order. Set broken_obr4=True to reproduce the
    'blank Universal Service ID' defect — passes basic validation,
    still a dangerous order with no test named on it."""
    obr4 = "" if broken_obr4 else "BMP^BASIC METABOLIC PANEL^L"
    return "\r".join([
        f"MSH|^~\\&|CPOE|MAINCAMPUS|LAB|LABSYSTEM|{_timestamp()}||ORM^O01|{_control_id('MSG')}|P|2.3",
        f"PID|1||{mrn}^^^HOSPITAL^MR||DOE^JANE^A||19850315|F",
        f"ORC|NW|{order_id}|||||||{_timestamp()}",
        f"OBR|1|{order_id}||{obr4}|||{_timestamp()}",
    ])


def oru_r01(order_id: str = "ORD5001", mrn: str = "MRN100001", missing_result_status: bool = False) -> str:
    """ORU^R01 lab result. Set missing_result_status=True to reproduce
    the 'no OBX-11' defect — no way to tell preliminary from final."""
    def obx(set_id, loinc, name, value, units, ref_range):
        base = f"OBX|{set_id}|NM|{loinc}^{name}^LN|{set_id}|{value}|{units}|{ref_range}|N|||"
        return base if missing_result_status else base + "F"

    lines = [
        f"MSH|^~\\&|LAB|LABSYSTEM|CPOE|MAINCAMPUS|{_timestamp()}||ORU^R01|{_control_id('MSG')}|P|2.3",
        f"PID|1||{mrn}^^^HOSPITAL^MR||DOE^JANE^A||19850315|F",
        f"OBR|1|{order_id}|FIL5001|BMP^BASIC METABOLIC PANEL^L|||{_timestamp()}",
        obx(1, "2345-7", "GLUCOSE", 92, "mg/dL", "70-99"),
        obx(2, "2951-2", "SODIUM", 140, "mmol/L", "136-145"),
        obx(3, "2823-3", "POTASSIUM", 4.1, "mmol/L", "3.5-5.1"),
    ]
    return "\r".join(lines)


def get_field(message: str, segment_name: str, field_index: int, occurrence: int = 0) -> str:
    """
    Small helper for unit tests: pull a single field out of a raw HL7
    string without needing a full parsing library. field_index is 1-based
    to match how everyone talks about HL7 fields (PID-3, OBR-4, etc).

    occurrence lets you pick which segment to read when there's more than
    one of the same type (e.g. the 2nd OBX line).
    """
    matches = [seg for seg in message.split("\r") if seg.startswith(segment_name + "|")]
    if occurrence >= len(matches):
        return ""
    fields = matches[occurrence].split("|")
    if field_index >= len(fields):
        return ""
    return fields[field_index]
