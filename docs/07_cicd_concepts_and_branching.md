# Part 7: CI/CD Concepts and Branching Strategy for This Project

**Purpose of this guide:** knowledge transfer, not setup. This is the conceptual
groundwork — what CI/CD actually means, how branches fit in, and a naming
convention for this specific project — so it can be explained clearly to a
hiring manager, whether or not GitHub Actions has been switched on yet.

---

## 1. What CI/CD actually means, without the tool names

Strip away GitHub Actions, Jenkins, GitLab CI, and every other product name, and
CI/CD is just this: **automating a discipline a developer would otherwise have
to remember to do by hand.**

Look at the actual loop this project has been following the whole time, every
time `mirth_api_client.py` changed:

1. Make a code change
2. Run `pytest tests/unit -v` by hand
3. Check the output — all green, or something red?
4. Only then commit and push

That loop **is** Continuous Integration, in spirit. The only thing missing is
the word "automatically." A human is currently the CI system — remembering to
run the tests, reading the result, deciding whether it's safe to push.
GitHub Actions (or any CI tool) doesn't introduce a new concept; it takes that
exact loop and makes a machine run it, every time, without depending on memory
or discipline.

### The vocabulary, mapped to what's already familiar here

| Term | What it means | Where it already shows up in this project |
|---|---|---|
| **Pipeline** | The whole sequence of automated steps | The manual loop above, once automated |
| **Trigger** | What kicks the pipeline off | Every `git push` |
| **Build** | Getting a clean environment ready | `pip install -r requirements.txt` |
| **Test stage** | Actually running the tests | `pytest tests/unit -v` |
| **Pass/fail gate** | Should this be allowed to merge/deploy? | Right now: manual judgment. With CI: automatic |
| **Environment** | Where code runs (dev/staging/prod) | Only "local" exists so far — no staging/prod |

### CI vs. the two flavors of CD

- **Continuous Integration (CI):** every push automatically builds and tests
  the code. Catches problems early, before they pile up.
- **Continuous Delivery:** every change that passes CI is automatically
  packaged into a release-ready state — but a **human still clicks a button**
  to actually release it.
- **Continuous Deployment:** goes one step further — passing CI means it goes
  live **automatically, with no human involved at all.**

**The honest scoping note for this project:** `hl7-interface-qa` is a testing
tool, not a deployed service. There's no production environment, and no
customer receiving a release. So CD in the classic sense doesn't apply here —
and claiming it does would be an easy thing for an interviewer to catch with
one follow-up question. What *does* apply, and is worth building, is the CI
half: automated build-and-test on every push.

---

## 2. Why branches exist

`main` is meant to represent **the one true, always-working version of the
code.** If everyone (or even just one person, mid-experiment) edited `main`
directly, it might sit broken at any given moment. Branches solve this by
letting work happen in isolation until it's actually ready.

```
main:        A---B---------------E---F
                  \               /
feature-branch:    C---D---------
```

Each letter is one commit — one saved snapshot of the code — left to right in
the order it happened:

- **A** — an earlier commit on `main`, before this particular piece of work started
- **B** — the commit where new work began, and a branch was created from this exact point
- **C, D** — commits made *on the branch*, not on `main` — the actual work in progress (e.g. "fix parsing bug," "add tests for it")
- **E** — the **merge commit**: where the branch's work (C and D) folds back into `main`. It sits back on the `main` line — that's the moment the branch's changes officially become part of `main`.
- **F** — any later, unrelated commit on `main` after that merge

`main` skips over C and D entirely because those commits never happened on
`main` — they only existed on the branch, isolated, until E merged them in.

### Mapped onto something this project actually lived through

The five-round debugging saga on `mirth_api_client.py`'s `connectorMessages`
parsing — wrong guess, test against live Mirth, still wrong, adjust, repeat —
is a clean real-world example of exactly what a branch is for:

- **B** = the last known-good commit (the original 38/38-passing state, before that debugging session started)
- **C, D, (and a few more)** = each of the five rounds of "try a fix, it's still wrong, try again" — all happening on a branch, invisible to `main`
- **E** = the single merge commit, once the fix was *actually* confirmed working against live Mirth, bringing all that work into `main` at once
- **F** = whatever came next

**The value:** while mid-debugging (rounds 1 through 4, all still broken),
`main` was never touched — it stayed at a clean, working, 38/38 state the
entire time. Only the final, confirmed-working result ever touched `main`.
As it actually happened in this project, every one of those rounds was
committed straight to `main` — which worked out fine solo, but is exactly the
habit branches exist to replace once more than one person (or more than one
piece of work) is involved.

### Branch protection rules — what makes this a real gate, not just a suggestion

On GitHub, `main` can be configured so that no one can push to it directly —
changes must come through a Pull Request, and CI must show passing before the
merge button even becomes clickable. This is what turns CI from "informational"
into an actual gate. Without it, nothing stops a push straight to `main` even
if tests would fail.

---

## 3. A branch naming convention for this project

A consistent naming scheme makes a repo's history readable at a glance — both
for a hiring manager skimming it, and for future-you six months from now. The
convention below follows a common industry pattern (`type/short-description`),
with the description grounded in this project's actual HL7 vocabulary rather
than generic placeholders.

### Format

```
<type>/<short-description>
```

### Types used in this project

| Type | Use for | Example |
|---|---|---|
| `feature` | New capability that didn't exist before | `feature/oru-loinc-mapping` |
| `fix` | Correcting a real bug | `fix/connector-name-parsing` |
| `test` | Adding or restructuring tests, no behavior change | `test/obx11-edge-cases` |
| `docs` | Documentation only | `docs/cicd-branching-guide` |
| `chore` | Maintenance — deps, cleanup, config | `chore/pin-pytest-version` |
| `refactor` | Restructuring code with no behavior change | `refactor/split-api-client-parsing` |

### Worked examples, using this project's real history

Reconstructing the actual work already done in this project as if it had used
branches from the start:

| What actually happened | Branch name it would have used |
|---|---|
| Fixing the missing `X-Requested-With` header | `fix/mirth-api-auth-header` |
| Correcting the wrong ACK-code assumption (AA vs AR) | `fix/pid3-filter-ack-assertion` |
| The five-round `connectorMessages` parsing saga | `fix/connector-status-parsing` |
| Adding Parts 1–4 guides with diagrams | `docs/setup-guides-with-diagrams` |
| Adding the troubleshooting log | `docs/troubleshooting-log` |
| Adding the HL7 practice messages reference doc | `docs/hl7-practice-messages` |
| A hypothetical future addition: mapping LOINC codes in the Transformer (mentioned as a "next step" in Part 4) | `feature/loinc-code-mapping` |
| A hypothetical future addition: rejecting an ORU missing OBX-11 entirely, not just blank | `feature/reject-missing-obx11` |

### Why domain-specific naming matters here specifically

A branch like `fix/bug1` communicates nothing. A branch like
`fix/connector-status-parsing` tells a reviewer — or an interviewer looking at
the repo — exactly what problem it addresses, in the project's own vocabulary
(HL7 segments, message types, Mirth connector concepts), without needing to
open the diff to find out.

---

## 4. How this would change the actual day-to-day workflow

### Editing setup: VS Code connected directly to WSL

Before the git side of this matters, it's worth having a clean, single source
of truth for the files themselves. Early in this project, files were
maintained in three places at once — a Windows `Program Files` copy, this
WSL project folder, and re-uploads to a Claude Project — which is exactly the
kind of setup that causes stale-file bugs (an outdated README pushed by
accident, a guide silently missing from a commit, and so on).

The fix: **edit the real WSL files directly, with no copying step at all.**

1. Install **VS Code** on Windows: [code.visualstudio.com](https://code.visualstudio.com)
2. Inside VS Code, open the Extensions panel and install **"WSL"** (by Microsoft)
3. From the Ubuntu terminal:
   ```bash
   cd ~/hl7-interface-qa
   code .
   ```
   This opens VS Code already connected to WSL, with the project folder open.
   The bottom-left corner should read **`WSL: Ubuntu`** — that's the
   confirmation it's editing the real files, not a copy.
4. Open a terminal inside VS Code itself: `` Ctrl+` `` (Ctrl + backtick), or
   **Terminal → New Terminal**. The prompt should show
   `kevin@DESKTOP-URHOMDC:~/hl7-interface-qa$` — a genuine bash/WSL terminal,
   not PowerShell.
5. Edit any file in the left-hand file explorer, save with `Ctrl+S`, and the
   change is immediately live in the real project — `git status` in that same
   terminal will show it as modified right away.

With this in place, the only two "copies" of this project that matter are:
**this WSL folder** (the only place edits happen) and **GitHub** (the backup
and the thing other people actually see). The old Program Files copy and
Claude Project re-uploads are no longer needed once this is set up.

### The actual git workflow, once editing directly

Concretely, going forward, a change would follow this shape instead of
committing straight to `main`:

```bash
git checkout main
git pull
git checkout -b fix/connector-status-parsing

# ... make changes directly in VS Code, then in the same terminal: ...
git add .
git commit -m "Parse connectorMessages as LinkedHashMap entry list"

git push -u origin fix/connector-status-parsing
```

Then, on GitHub: open a **Pull Request** from that branch into `main`. If CI
is wired up (Part 8, not yet built), it runs automatically on the PR and shows
pass/fail right there before anything merges. Once satisfied — tests passing,
changes reviewed (even self-reviewed, solo) — click **Merge**, which is commit
E in the diagram. `main` only ever receives that final, confirmed-good state.

---

## 5. Explaining this to a hiring manager — a short, honest version

> "I've been enforcing a test-before-push discipline manually throughout this
> project — running the suite locally before every commit. The next layer is
> automating that with GitHub Actions so it can't be skipped, and using
> feature branches with Pull Requests so `main` only ever receives confirmed-
> working code, the same pattern a team would use with multiple contributors.
> This project is a QA/testing tool rather than a deployed service, so I can
> speak to CI concretely here — build and automated test on every push — and
> explain Continuous Delivery vs. Deployment conceptually, including how I'd
> extend this if the project needed to actually ship somewhere."

That's a precise, defensible answer: it claims exactly what's true, names the
real next step, and shows the boundary of the project is understood rather
than papered over.

---

**Next steps (not yet built):**
- Part 8 (future): actually wiring up the GitHub Actions workflow file for the
  unit test suite, with a status badge on the README.
- Applying branch protection rules to `main` once CI exists to gate against.
