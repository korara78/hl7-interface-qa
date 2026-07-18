# HL7 practice messages: spot the difference

Three pairs of messages below, each covering a message type you'll see constantly as an integration analyst: patient admit (ADT), lab result (ORU), and order (ORM). In each pair, one message is clean and one has a real-world defect.

**How to use this:** read each pair field by field before scrolling to the answer key. Try to name the exact field that's wrong and explain the *downstream* consequence — that's the skill hiring managers are actually testing for, not just "can you spot a typo."

## Quick segment legend

- `MSH` — message header: who sent it, what type, when
- `EVN` — event info (used with ADT messages)
- `PID` — patient identification (name, DOB, sex, MRN, address)
- `PV1` — patient visit info (location, attending provider, patient class)
- `ORC` — order control (new/cancel/hold, order IDs)
- `OBR` — observation request (what test/procedure was ordered)
- `OBX` — observation result (the actual value, with type and status)

Note: these are simplified for readability — real-world messages from production systems often carry more segments and trailing fields.

---

## Set 1 — ADT^A01 (patient admit)

**Message 1A**
```
MSH|^~\&|REGISTRATION|GENHOSP|EHR|GENHOSP|20260615143000||ADT^A01|MSG00001|P|2.5.1
EVN|A01|20260615143000
PID|1||MRN100245^^^GENHOSP^MR||DOE^JANE^M||19850312|F|||123 MAIN ST^^SPRINGFIELD^IL^62701
PV1|1|I|3W^301^A^GENHOSP||||1234^SMITH^ROBERT^^^^MD|||MED|||||||1234^SMITH^ROBERT^^^^MD|INP
```

**Message 1B**
```
MSH|^~\&|REGISTRATION|GENHOSP|EHR|GENHOSP|20260615151500||ADT^A01|MSG00002|P|2.5.1
EVN|A01|20260615151500
PID|1||||DOE^JANE^M||19850312|F|||123 MAIN ST^^SPRINGFIELD^IL^62701
PV1|1|I|3W^301^A^GENHOSP||||1234^SMITH^ROBERT^^^^MD|||MED|||||||1234^SMITH^ROBERT^^^^MD|INP
```

**Question:** One of these would process cleanly. The other parses without any syntax error, but has a problem that would cause real trouble downstream. What field is wrong, and what happens because of it?

---

## Set 2 — ORU^R01 (lab result)

**Message 2A**
```
MSH|^~\&|LAB|GENHOSP|EHR|GENHOSP|20260615160000||ORU^R01|MSG00003|P|2.5.1
PID|1||MRN100245^^^GENHOSP^MR||DOE^JANE^M||19850312|F
OBR|1|ORD7788|FIL9931|CBC^COMPLETE BLOOD COUNT^L|||20260615154500
OBX|1|NM|718-7^HEMOGLOBIN^LN|1|13.5|g/dL|12.0-16.0|N|||F
OBX|2|NM|4544-3^HEMATOCRIT^LN|2|40.2|%|36.0-46.0|N|||F
```

**Message 2B**
```
MSH|^~\&|LAB|GENHOSP|EHR|GENHOSP|20260615162000||ORU^R01|MSG00004|P|2.5.1
PID|1||MRN100245^^^GENHOSP^MR||DOE^JANE^M||19850312|F
OBR|1|ORD7789|FIL9932|UA^URINALYSIS^L|||20260615160500
OBX|1|NM|5778-6^COLOR^LN|1|YELLOW
OBX|2|NM|664-3^BACTERIA^LN|2|POSITIVE|||A
```

**Question:** Look closely at OBX-2 (value type) versus OBX-5 (the actual value) in both messages. Also check whether each OBX line tells the receiving system if the result is final. What's wrong in 2B, and why would each issue matter to a clinician reading this result?

---

## Set 3 — ORM^O01 (order)

**Message 3A**
```
MSH|^~\&|CPOE|GENHOSP|LAB|GENHOSP|20260615173000||ORM^O01|MSG00005|P|2.5.1
PID|1||MRN100245^^^GENHOSP^MR||DOE^JANE^M||19850312|F
ORC|NW|ORD7790|||||||20260615173000
OBR|1|ORD7790||BMP^BASIC METABOLIC PANEL^L|||20260615173000
```

**Message 3B**
```
MSH|^~\&|CPOE|GENHOSP|LAB|GENHOSP|20260615174500||ORM^O01|MSG00006|P|2.5.1
PID|1||MRN100245^^^GENHOSP^MR||DOE^JANE^M||19850312|F
ORC|NW|ORD7791|||||||20260615174500
OBR|1|ORD7791|||||20260615174500
```

**Question:** Check OBR-4, the Universal Service ID. What's missing in 3B, and why is this defect more dangerous than a typo — i.e., why might it pass basic schema validation and still cause a real problem?

---
---

# Answer key

## Set 1 — ADT^A01

**1A is clean.** PID-3 (Patient Identifier List) is populated with `MRN100245^^^GENHOSP^MR` — a fully formed MRN tied to the assigning authority.

**1B is broken.** PID-3 is empty — there are four consecutive pipes after `PID|1` where the MRN should be: `PID|1||||DOE^JANE^M...`

This is a textbook "parses fine, fails operationally" defect. The message is syntactically valid HL7 — nothing will throw a parsing error. But the receiving system (usually the EHR's master patient index) relies on PID-3 to match this admit to an existing patient record. With it empty, you typically get one of two bad outcomes: the message gets rejected by validation rules further downstream, or — worse — the system creates a brand-new patient record with no MRN link, producing a duplicate patient. Duplicate-patient cleanup is one of the most expensive, time-consuming problems in healthcare IT, which is exactly why this field gets flagged in real interface testing.

**As a test case, you'd assert:** PID-3 is non-empty and contains a recognized assigning authority for every ADT message type.

## Set 2 — ORU^R01

**2A is clean.** OBX-2 says `NM` (numeric) and OBX-5 values are actual numbers (13.5, 40.2). OBX-11 (Result Status) is `F` (final) on both lines, so the receiving system and the clinician both know these are finished, trustworthy results.

**2B has two separate issues:**
1. **Type mismatch:** OBX-2 says `NM` but OBX-5 holds text (`YELLOW`, `POSITIVE`). The correct value type here would be `ST` (string) or `CE` (coded entry). A strict receiving system may reject these lines outright; a lenient one may silently coerce or drop the value — either way, the result is unreliable.
2. **Missing result status:** Neither OBX line includes OBX-11. Without it, there's no way to know if this is a preliminary or final result. In practice, this can mean a clinician acts on a value that was never actually finalized, or a result sits invisible in a "pending" queue indefinitely.

**Why this matters more than it looks:** the first issue is a data-typing bug; the second is a workflow-safety bug. Hiring managers care about candidates who can tell these apart, because they get triaged completely differently — one's a mapping fix, the other can be a patient-safety conversation.

## Set 3 — ORM^O01

**3A is clean.** OBR-4 (Universal Service ID) contains `BMP^BASIC METABOLIC PANEL^L` — the order clearly states what's being requested.

**3B is broken.** OBR-4 is empty: `OBR|1|ORD7791|||||20260615174500` — the order has an ID, a timestamp, everything administratively correct, but never says what test or procedure to perform.

This is the most dangerous kind of defect to catch, because it often *passes* basic interface testing. If your test only checks "does OBR-4 exist as a field" rather than "is OBR-4 populated with a valid, recognized code," this slips right through. Downstream, the lab system either hard-rejects the order (best case — delays care, generates a support ticket) or, in a poorly built integration, accepts a blank order that someone has to manually chase down. This is a good example of why integration testing has to validate field *content*, not just field *presence* — a distinction that's easy to state and easy to forget under deadline pressure.

---

### One pattern across all three sets

Every "broken" message in this set is syntactically valid HL7. None of them would throw a parser error. That's intentional — the defects that actually matter in this job are almost never "the message is malformed garbage." They're "the message is well-formed and still wrong," which is a much harder thing to test for and exactly the skill that separates someone who can run a validator from someone who understands what the data is supposed to *mean*.
