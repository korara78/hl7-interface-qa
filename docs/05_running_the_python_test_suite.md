# Part 5: Running the Python Test Suite Against Your Mirth Instance

**Prerequisite:** Parts 1–4 complete — Mirth running in Docker, `Hospital_to_Lab_ADT_ORM`
and `Lab_Receives_ADT_ORM` channels deployed with their Filters and Transformers built.

---

## What this actually is

This is an automated **pytest** test suite — not a script you read, a set of test files
pytest discovers and runs, each one making an assertion that either passes or fails.
It replaces the manual workflow from Parts 3–4 (paste a message into Send Message,
eyeball the Dashboard, repeat) with something you run in seconds and trust to catch
regressions.

It has two distinct layers, and it matters which one you're running:

| Layer | Needs Mirth running? | What it proves |
|---|---|---|
| **Unit tests** (`tests/unit/`) | No | The message-building and API-parsing *logic* is correct |
| **Integration tests** (`tests/integration/`) | Yes | Your actual, running Mirth channels behave the way they're supposed to |

Unit tests are fast and safe to run constantly. Integration tests are the ones that
actually talk to your Mirth instance over the network — those are what this guide
focuses on.

---

## Step 1: Confirm Mirth is up

```bash
docker ps
```

You're looking for `myconnect`, status **Up**, with ports `8443`, `6661`, and `6662`
all listed. If it's not running, start the container (see Part 1).

## Step 2: Confirm your channel names match

The test suite looks up channels **by name** through Mirth's REST API. It expects
exactly:

- `Hospital_to_Lab_ADT_ORM`
- `Lab_Receives_ADT_ORM`

Open Mirth Administrator (`https://localhost:8443`) → **Channels** and confirm both
exist, are spelled exactly like that, and show **Deployed / Started**. Also confirm
`Hospital_to_Lab_ADT_ORM` has its Filter, Transformer, and `Exception_Log` destination
from Part 4 already built — the integration tests assert on that specific logic.

> 💡 **Named your channels differently?** Tell me and I'll make the names
> configurable via environment variables instead of hardcoded in `conftest.py` —
> quick change, just didn't want to guess at names you might still want to edit.

## Step 3: Unpack and install

```bash
unzip hl7-interface-qa.zip
cd hl7-interface-qa
pip install -r requirements.txt
```

This installs `pytest` and `requests` — nothing else. No virtual environment is
required, but feel free to use one if you prefer keeping this isolated from other
Python projects on your machine.

> 💡 **Running this from WSL (Windows Subsystem for Linux)?** Two gotchas that
> only show up here, not on native Linux/macOS:
>
> - **Windows paths need translating.** `C:\Program Files\...` becomes
>   `/mnt/c/Program Files/...` inside WSL — forward slashes, and `C:` becomes
>   `/mnt/c`. Quote the whole path if it has spaces:
>   ```bash
>   cd "/mnt/c/Program Files/Mirth Connect Guides/mirth_pytest/hl7-interface-qa"
>   ```
> - **Python isn't automatically there just because Windows has it.** WSL's
>   Ubuntu is a separate environment. If `pip` or `python` come back
>   "command not found," install them first:
>   ```bash
>   sudo apt update
>   sudo apt install python3 python3-pip -y
>   ```
>   Then use `pip3` and `python3 -m pytest` in place of `pip` and `pytest`
>   throughout this guide if the shorter commands aren't on your PATH:
>   ```bash
>   pip3 install -r requirements.txt
>   python3 -m pytest tests/unit -v
>   ```

## Step 4: Set connection details (only if yours differ from the defaults)

Out of the box, the suite assumes:

| Setting | Default |
|---|---|
| Mirth host | `127.0.0.1` |
| Hospital channel port | `6661` |
| Lab channel port | `6662` |
| REST API base URL | `https://localhost:8443/api` |
| REST API username / password | `admin` / `admin` |

If any of these are different for you — especially if you changed the admin
password like Part 1 suggested before a "final walkthrough" — set environment
variables before running:

```bash
export MIRTH_API_USERNAME=admin
export MIRTH_API_PASSWORD=your_actual_password
export MIRTH_HOST=127.0.0.1                      # only if not localhost
export MIRTH_API_BASE_URL=https://localhost:8443/api   # only if different
```

## Step 5: Run the unit tests first (sanity check, no Mirth needed)

```bash
pytest tests/unit -v
```

You should see all tests pass in well under a second. If this fails, something's
wrong with the Python install itself, not with Mirth — worth ruling out before
moving on.

## Step 6: Run the integration tests

```bash
pytest tests/integration -v
```

Each test sends a real HL7 message over MLLP to one of your channels, then asks
Mirth's REST API what actually happened to it, and asserts on the result. For
example, `test_blank_pid3_adt_gets_filtered_not_just_acked` sends an ADT with an
empty MRN and asserts Mirth's own message log shows it as **Filtered** — not just
that the socket accepted it.

### Reading the output

- **`PASSED`** — Mirth did exactly what Part 4 built it to do.
- **`SKIPPED`** — Mirth's MLLP ports weren't reachable at all; nothing else ran.
  Check Step 1.
- **`FAILED`** — Mirth responded, but not the way the test expected. Read the
  assertion message; each one prints Mirth's actual reported status so you can see
  the mismatch directly, e.g.:
  ```
  AssertionError: Expected the blank-PID-3 message to be Filtered, but Mirth reports: {'Source': 'SENT'}
  ```

## What's most likely to go wrong the first time

Be honest with yourself about this one: `mirth_api_client.py` was written against
Mirth's documented, version-stable status values, but its exact JSON field parsing
was **not** tested against a live server before now — I don't have one to test
against directly. The single most likely failure is a `MirthAPIError` or `KeyError`
coming from that file, not from your channels themselves.

If that happens:

1. Copy the full error message — it includes Mirth's raw response body, which is
   the actual clue.
2. Open `https://localhost:8443/api` in a browser. Mirth serves live,
   version-matched API documentation for your exact server — you can see the real
   field names for `GET /channels` and `GET /channels/{id}/messages` directly.
3. Send me what you see (the error, or the real response shape) and I'll adjust
   the parsing in `mirth_api_client.py` to match.

This is a completely normal step, not a sign the project is broken — it's the same
"validated clean, then adjusted based on what actually happened" loop Part 4
describes for the Transformer's own JavaScript.

## Quick reference: commands

```bash
# One-time setup
unzip hl7-interface-qa.zip && cd hl7-interface-qa
pip install -r requirements.txt

# Every time you want to test
pytest tests/unit -v          # fast, no Mirth needed
pytest tests/integration -v   # needs Mirth running, tests real channel behavior

# Everything at once
pytest tests/ -v
```

> 💡 On WSL, if `pip`/`pytest` aren't found, use `pip3` and `python3 -m pytest`
> instead (see the WSL note in Step 3).
