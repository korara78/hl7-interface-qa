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

## Prerequisites — everything this actually needs installed

The steps below assume all of these already work. In practice, a fresh
WSL/Ubuntu install is missing most of them — here's the full list and how
to check/install each, so you don't have to discover them one error at a
time like we did the first time through.

| Tool | Check if installed | Install if missing |
|---|---|---|
| **WSL2 + Ubuntu** | You're reading this in a WSL terminal | Covered in Part 1 |
| **Docker Desktop, with WSL integration ON for your distro** | `docker ps` runs without error | Docker Desktop → Settings → Resources → WSL Integration → toggle your distro on → Apply & Restart |
| **git** | `git --version` | `sudo apt install git -y` |
| **unzip** | `unzip -v` | `sudo apt install unzip -y` |
| **python3** | `python3 --version` | `sudo apt install python3 -y` (usually already present) |
| **python3-pip** | `pip3 --version` | `sudo apt install python3-pip -y` |
| **python3-venv** (note: version-specific, e.g. `python3.14-venv`) | `python3 -m venv --help` | `sudo apt install python3-venv -y` (or the exact versioned package apt suggests, e.g. `python3.14-venv`) |

Run this once to catch everything in one pass:
```bash
sudo apt update
sudo apt install git unzip python3 python3-pip python3-venv -y
```
If `python3-venv` fails to install by that generic name, apt's error message
will suggest the exact versioned package name (e.g. `python3.14-venv`) —
install that instead.

> 💡 **Why a virtual environment (venv) at all?** Modern Ubuntu blocks
> `pip install` from touching the system-wide Python directly (a safety
> feature called PEP 668, shows up as an `externally-managed-environment`
> error). A venv is just an isolated, project-local copy of Python where
> installing packages is always safe — Step 3 below creates one.

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

## Step 3: Unpack, place it correctly, and install

If you downloaded the zip through Windows (e.g. to your Downloads folder),
**don't work from that Windows-mounted location directly** — copy it into
WSL's own Linux filesystem first. Two real reasons this matters, both
things that actually broke for us:

- Files under `/mnt/c/...` (anywhere on your `C:` drive) can come through
  as **read-only** to WSL, which breaks creating a Python virtual
  environment with a `Permission denied` error, even though `ls` and `cd`
  work fine there.
- If the folder happens to sit under a protected Windows path like
  `C:\Program Files\...`, WSL can't write there at all regardless of file
  permissions.

So, unzip Windows-side as usual, then bring it into your Linux home
directory:

```bash
cp -r "/mnt/c/Users/<your-windows-username>/Downloads/hl7-interface-qa" ~/hl7-interface-qa
cd ~/hl7-interface-qa
chmod -R u+w .   # in case the copy came through read-only
```

(Replace `<your-windows-username>` with your actual Windows username —
run `ls /mnt/c/Users/` if you're not sure what it is; it doesn't have to
match your WSL/Linux username.)

Now create a virtual environment and install into that, rather than the
system Python directly:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Your prompt should now start with `(venv)` — that confirms it's active.
From here on, plain `pip` and `python` both refer to this project's own
isolated copies, not the system-wide ones.

> ⚠️ **`python3 -m venv venv` failing with no clear error, or `venv/bin/activate: No such file or directory`?**
> Ubuntu splits the venv module into its own package, separate from
> `python3` itself. Install the matching one apt suggests (it's
> version-specific, e.g. `python3.14-venv` for Python 3.14):
> ```bash
> sudo apt install python3.14-venv -y
> ```
> Then retry the two commands above.

> 💡 **Every new terminal session**, you'll need to re-activate before
> running tests — packages stay installed, but activation doesn't persist
> across terminal windows:
> ```bash
> cd ~/hl7-interface-qa
> source venv/bin/activate
> ```



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

### What a full run actually looks like

Every test, individually named, all passing — this is a real run against a live
Mirth 4.5.2 instance, not a mock or a staged example:

![Full pytest run: all 38 tests individually listed as PASSED](images/pytest_results_full.png)

![Final summary: 38 passed, 5 warnings in 7.33s](images/pytest_results_summary.png)

## Status: confirmed working end-to-end

The `mirth_api_client.py` parsing described above as "untested against a
live server" has since been run against a real Mirth 4.5.2 instance and
fixed through several rounds of real errors — wrong auth header, wrong
ACK assumption, two wrong guesses at the connectorMessages JSON shape,
and one wrong test assumption about what "Filtered" means across
different connectors. All 38 tests (unit + integration) pass against a
live instance as of this writing. See `docs/06_troubleshooting_log.md`
for the full blow-by-blow if you hit something similar on your own setup
— chances are it's already been through this exact loop once.

## Quick reference: commands

```bash
# One-time setup
cp -r "/mnt/c/Users/<your-windows-username>/Downloads/hl7-interface-qa" ~/hl7-interface-qa
cd ~/hl7-interface-qa
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Every new terminal session, before running tests
cd ~/hl7-interface-qa
source venv/bin/activate

# Every time you want to test
pytest tests/unit -v          # fast, no Mirth needed
pytest tests/integration -v   # needs Mirth running, tests real channel behavior

# Everything at once
pytest tests/ -v
```

