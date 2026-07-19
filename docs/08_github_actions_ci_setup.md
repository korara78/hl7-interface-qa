# Part 8: GitHub Actions CI — Running the Full Suite Against a Fresh Mirth on Every Push

**Prerequisite:** Part 7 (CI/CD concepts) read, and the working local test suite from
Part 5 already passing.

---

## What this actually builds

Locally, `pytest tests/ -v` runs against Mirth running in your own Docker container,
with channels you built once by hand and that persist in a Docker volume forever
after. GitHub Actions doesn't have that volume, and it doesn't have your Docker
container — every run starts from **nothing**: a brand-new, empty Mirth instance,
spun up fresh, with zero channels deployed.

So this isn't just "run pytest in the cloud." It's three real problems to solve:

1. Get a real Mirth instance running inside the CI job at all
2. Get your actual channels — with their Filters and Transformers — into that fresh
   instance automatically, with no human clicking through the Administrator GUI
3. Only then run the same test suite you already trust locally

---

## Step 1: Export your channels

Everything Part 2 and Part 4 built lives only inside your local Docker volume right
now — nowhere else. CI needs a portable copy of that configuration to import.

1. Mirth Administrator → **Channels**
2. Select both `Hospital_to_Lab_ADT_ORM` and `Lab_Receives_ADT_ORM` (Ctrl+click)
3. Right-click → **Export Channels**
4. Save with these **exact filenames** — the import script looks for them specifically:
   - `Hospital_to_Lab_ADT_ORM.xml`
   - `Lab_Receives_ADT_ORM.xml`
5. Move both files into `mirth-config/` at the project root

> 💡 **Why commit these to the repo at all, beyond CI?** This is also just a real
> backup. Right now, if the `mirth-appdata` Docker volume were ever deleted, every
> hour spent building the Filter/Transformer logic in Part 4 would be gone. These XML
> files are that logic, portable and versioned.

---

## Step 2: The channel-import script

`scripts/import_mirth_channels.py` is what turns a fresh, empty Mirth into a working
one, automatically. Three things it has to do, in order:

1. **Wait for Mirth to actually be ready.** A container reporting "started" and the
   REST API actually accepting requests are not the same moment — Mirth needs real
   boot time. The script polls `/server/status` in a loop rather than assuming a
   fixed sleep is long enough.
2. **Import each channel XML.** `POST /channels` with the raw exported XML as the
   body — the same shape Mirth's own Administrator produces when you export.
3. **Deploy it.** Importing a channel doesn't start it; a separate
   `POST /channels/_deploy` call, with the channel's ID, is what actually makes it
   live and listening.

> ⚠️ **Honest flag, matching this project's own pattern from Parts 5–6:** the exact
> shape of Mirth's import/deploy REST endpoints here is based on Mirth's own API
> documentation, not yet confirmed against a real run — unlike `mirth_api_client.py`,
> which went through several rounds of correction against a live server before it was
> trustworthy. Expect this script to need at least one similar round of adjustment
> the first time the workflow actually runs. That's not a sign anything is wrong; it's
> the same loop this whole project has followed from the start.

---

## Step 3: The workflow file

`.github/workflows/tests.yml` is what GitHub actually runs. Breaking down the parts
that differ from a simpler "just run unit tests" workflow:

```yaml
services:
  mirth:
    image: nextgenhealthcare/connect:4.5.2
    ports:
      - 8443:8443
      - 6661:6661
      - 6662:6662
```

This is a **service container** — GitHub Actions' built-in mechanism for spinning up
a dependency (a database, a message broker, or here, an interface engine) alongside
your actual job, reachable at `localhost` from the job's own steps. No manual
`docker run`, no volume — GitHub manages its lifecycle for the duration of the job
and tears it down after.

```yaml
- name: Run unit tests
  run: pytest tests/unit -v

- name: Import and deploy Mirth channels
  run: python scripts/import_mirth_channels.py

- name: Run integration tests
  run: pytest tests/integration -v
```

Unit tests run first and don't depend on Mirth being ready at all — if they fail,
there's no reason to even wait on Mirth or attempt the import. Only once those pass
does the import script run, and only once channels are confirmed deployed do the
integration tests run against them.

---

## Step 4: The status badge

The badge at the top of the README:

```markdown
[![Tests](https://github.com/korara78/hl7-interface-qa/actions/workflows/tests.yml/badge.svg)](https://github.com/korara78/hl7-interface-qa/actions/workflows/tests.yml)
```

pulls live status directly from GitHub — green "passing" or red "failing," always
reflecting the *most recent* run, not something anyone has to remember to update by
hand. This only starts working once the workflow file has been pushed and run at
least once; until then, GitHub shows a neutral/gray badge.

---

## What to expect the first real run to look like

Given everything else in this project, the honest expectation is: **the first run
will probably fail somewhere in the import/deploy step**, and that's fine — it's the
same "confirmed by actually testing it" loop as every other real fix documented in
`docs/06_troubleshooting_log.md`. Likely failure points, in rough order of
likelihood:

- The import endpoint's exact request shape (body format, required query params)
  doesn't match what's assumed above
- Timing — Mirth takes longer to become ready than expected, even with the polling
  loop
- The exported XML references something environment-specific that doesn't translate
  cleanly into the CI container

Whatever the actual error turns out to be, the fix follows the same pattern as
always: read what GitHub Actions' log actually says, adjust the script to match
reality, push again, confirm.

---

**Next steps (not yet built):**
- Once this workflow is confirmed working end-to-end, consider adding branch
  protection rules (Part 7, Section 2) so `main` requires this workflow to pass
  before a PR can merge — the step that turns CI from informational into a real gate.
