# Part 6: Troubleshooting Log — What Actually Broke, and How It Got Fixed

This isn't a hypothetical "things that might go wrong" list — it's a record of
the real issues hit while setting up this project on Windows/WSL and running
the test suite against a live Mirth instance for the first time, in the order
they actually happened. Kept here deliberately, rather than cleaned up and
hidden, because working through exactly this kind of thing — vague error,
find the real cause, fix it, verify, move on — is the actual day-to-day job
of an interface analyst or SDET, not a sign anything was "wrong" with the
setup to begin with.

---

## Environment setup issues (WSL / Windows)

### `bash: cd: too many arguments`
**Cause:** Windows paths with spaces (`C:\Program Files\...`) need quoting in
bash, and need translating from `C:\...` to `/mnt/c/...` format.
**Fix:**
```bash
cd "/mnt/c/Program Files/Mirth Connect Guides/mirth_pytest/hl7-interface-qa"
```

### Forgot the WSL Linux user password
**Cause:** happens to everyone eventually — it's a separate password from
your Windows login, set once during initial WSL setup and easy to forget.
**Fix:** reset it from an elevated (admin) PowerShell window, not from
inside the WSL session itself:
```powershell
wsl -d Ubuntu -u root
```
```bash
passwd kevin   # your actual WSL username
exit
```

### `pip install` fails with `error: externally-managed-environment`
**Cause:** modern Ubuntu (PEP 668) blocks `pip` from touching the
system-wide Python directly, to avoid breaking OS-level tools that depend
on it.
**Fix:** use a virtual environment instead of installing system-wide —
see Part 5, Step 3.

### `python3 -m venv venv` fails silently / `venv/bin/activate: No such file or directory`
**Cause:** Ubuntu splits the `venv` module into its own installable
package, separate from `python3` itself.
**Fix:**
```bash
sudo apt install python3.14-venv -y   # exact version-suffixed name apt suggests
```

### `Permission denied` creating the venv, even in what looks like a normal folder
**Cause:** the project had been copied from a Windows-mounted path
(`/mnt/c/...`), which can carry over as read-only to WSL — confirmed via
`ls -ld`, which showed `dr-xr-xr-x` (no `w` anywhere, even for the owner).
**Fix:**
```bash
chmod -R u+w ~/hl7-interface-qa
```

### `Permission denied: '/mnt/c/Program Files/.../venv'`
**Cause:** separate from the read-only issue above — `Program Files` is a
Windows-protected system directory, and WSL can't write new files there
regardless of permissions.
**Fix:** work from WSL's own home directory instead of a Windows-mounted
path at all:
```bash
cp -r "/mnt/c/Program Files/Mirth Connect Guides/mirth_pytest/hl7-interface-qa" ~/hl7-interface-qa
cd ~/hl7-interface-qa
```

### `docker: command not found` inside WSL
**Cause:** Docker Desktop was running, but WSL integration for this
specific distro hadn't been enabled.
**Fix:** Docker Desktop → Settings → Resources → WSL Integration → toggle
the distro on → Apply & Restart.

### `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`
**Cause:** showed up right after enabling WSL integration — a stale
session hadn't picked up the new permissions yet.
**Fix:** fully restart WSL from PowerShell (not just the terminal tab),
then reopen fresh:
```powershell
wsl --shutdown
```

### Downloaded zip file is 0 bytes / `zipfile is empty`
**Cause:** an interrupted or incomplete browser download — not something
done wrong, just an occasional flaky download.
**Fix:** delete the bad file, re-download, and check the actual byte size
before trying to unzip it again:
```bash
ls -la /mnt/c/Users/<user>/Downloads/hl7-interface-qa.zip
```

---

## Real Mirth REST API surprises (all confirmed by testing against a live 4.5.2 server)

Each of these was a reasonable guess based on Mirth's public documentation
and its source code's `Status` enum — and each one turned out to need a
correction once tested against real output. That's expected: documentation
describes the stable parts (the status values themselves); the exact JSON
serialization shape is the part you confirm empirically.

1. **Missing `X-Requested-With` header** — every request returned
   `400: All requests must have 'X-Requested-With' header` until this was
   added. A CSRF-protection quirk of the Jersey/Glassfish framework Mirth's
   API is built on.
2. **Wrong assumption about MLLP ACKs** — assumed the ACK couldn't reveal
   Filter outcome; this channel's configuration actually reflects it
   directly (`AR` for a Filtered message, not just `AA` for "received").
3. **`GET /channels` response shape** — actual shape came back as the
   classic Java/JAXB `{"list": {"channel": [...]}}` wrapper, not a bare
   list or a single-level `{"channel": [...]}`.
4. **`connectorMessages` shape, guessed twice, both wrong** — first guess:
   nested objects keyed by metaDataId. Second guess: plain status strings
   keyed by metaDataId. Real shape: a serialized Java `LinkedHashMap`,
   `{"entry": [{"int": <metaDataId>, "connectorMessage": {...}}, ...]}`,
   with the connector's real name (`"Source"`, `"Destination 1"`,
   `"Exception_Log"`) already present on each entry.
5. **Conceptual test bug: "any connector Filtered" ≠ "message rejected"** —
   a destination-level filter (like `Exception_Log`'s own "only fire for
   exceptions" rule) legitimately reports `FILTERED` for messages that
   simply don't match *that destination's* filter — completely different
   from the channel-level Filter rejecting a message before it reaches any
   destination at all. Fixed by checking the `Source` connector's status
   specifically for the channel-level Filter's decision, rather than
   treating any `FILTERED` anywhere as equivalent.

---

## The pattern across all of this

Nothing above was a sign the project, the code, or the setup was broken.
Every single one was: get an error → read what it actually says → check
what's really happening (not what was assumed) → fix the specific thing →
re-run to confirm → move on. That loop, repeated a dozen times, is what
got this from "should work in theory" to "confirmed working, 38/38, against
a real live server" — which is a meaningfully stronger thing to say in an
interview than "I followed a tutorial and it worked."
