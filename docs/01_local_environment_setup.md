# Part 1: Local Interface Engine Setup & Environment (Mirth Connect)

**Project:** Mock hospital-to-lab HL7 routing environment
**Tool used:** Mirth Connect 4.5.2 (Community Edition), containerized via Docker
**Audience:** This guide assumes basic comfort with Windows, but no prior interface engineering experience.

---

## What you're building

Interface engines like Mirth Connect are the software hospitals and labs use to route
clinical messages (HL7) between systems — an EHR sending a patient admission, a lab
system sending back results, and so on. This guide gets a working, local copy of that
engine running on your machine.

Here's the shape of the whole system you'll have running by the end of Part 2:

![Architecture overview: mock hospital, two integration channels, mock lab, and exception log](images/architecture-overview.svg)

## A note on tool choice

This project uses **Mirth Connect 4.5.2**, run via Docker. Mirth Connect is the name
most interface engineering job postings and interviewers actually recognize, and Docker
gives a clean, reproducible setup — no native Windows installer quirks, no separate Java
runtime management, and the whole environment can be torn down and rebuilt identically
at any time.

> 💡 **Why version 4.5.2 specifically:** In March 2025, NextGen Healthcare moved Mirth
> Connect to a commercial-only license starting at version 4.6. Version 4.5.2 is the
> last fully open-source release under the Mozilla Public License. It's frozen (no
> further security patches or features), but it's exactly what many real healthcare
> organizations still run today, since upgrading requires a paid license ($15,000+/year).
> Knowing 4.5.2 well is directly applicable to real-world environments.

---

## Step 1: Install Docker Desktop

Docker lets us run Mirth Connect in an isolated, disposable container rather than
installing it directly on Windows.

1. Go to [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
2. Click **Download for Windows – AMD64** (this is correct for both Intel and AMD Windows
   laptops — "AMD64" is just the historical name for the x86-64 architecture both chip
   makers use)

> ℹ️ **Licensing note:** Docker Desktop is free for individual use, education, and small
> businesses (under 250 employees and under $10M revenue) — this project qualifies. No
> plan selection or payment needed.

3. Run the installer. When the **Configuration** screen appears, keep the defaults:
   - **All-users installation**
   - **Use WSL 2 instead of Hyper-V** (checked)
   - **Allow Windows Containers** (leave unchecked — we only need Linux containers)
   - **Add shortcut to desktop** (checked)
4. Click **OK**, let it install, and **restart your computer** when prompted.

## Step 2: Set up WSL 2 (if not already configured)

Docker Desktop needs the Windows Subsystem for Linux (WSL 2) as its backend. If Docker
opens after your restart and shows a **"WSL not installed"** error, fix it manually:

1. Press **Windows key**, type `powershell`, right-click → **Run as administrator**
2. Run:
   ```powershell
   wsl --install
   ```
3. This downloads and installs WSL 2 and a default Ubuntu distribution.
4. Partway through, it will ask you to create a Linux username and password for this
   Ubuntu instance. **This is separate from your Windows login** — pick any lowercase
   username (avoid `admin`, which conflicts with an existing system group name and will
   fail). Write this password down somewhere — it's easy to forget since you'll only use
   it occasionally (see the Part 6 troubleshooting log for what to do if you forget it
   anyway).
5. Once the username and password are set, Ubuntu finishes provisioning and drops you at
   a working Linux prompt.
6. **Restart your computer again** to fully register WSL 2 with Docker.
7. Launch **Docker Desktop** from the desktop shortcut. It should now open cleanly. You
   can skip the sign-in prompt — a Docker account isn't required for local use.
8. If prompted, click **Accept** on the Docker Subscription Service Agreement.

> 💡 **A step that isn't obvious until you hit it:** by default, Docker Desktop's WSL
> integration isn't automatically turned on for your Ubuntu distro. If a later step says
> `docker: command not found` inside your WSL terminal even though Docker Desktop is
> running, go to Docker Desktop → **Settings → Resources → WSL Integration**, toggle your
> distro on, and **Apply & Restart**. See Part 6 for the full story on this one.

## Step 3: Pull and run Mirth Connect

Open a regular Command Prompt (no admin rights needed) and run:

```bash
docker pull nextgenhealthcare/connect:4.5.2
```

This downloads the Mirth Connect 4.5.2 image — may take a few minutes.

> ⚠️ **Important — don't skip this:** if you just run `docker run` with only the web
> ports exposed, your channel data will be lost every time the container is recreated.
> Set up a persistent volume from the very start:

```bash
docker volume create mirth-appdata
docker run --name myconnect -d -p 8080:8080 -p 8443:8443 -p 6661:6661 -p 6662:6662 -v mirth-appdata:/opt/connect/appdata nextgenhealthcare/connect:4.5.2
```

What this does:
- `-p 8080:8080 -p 8443:8443` — exposes the web/Administrator ports
- `-p 6661:6661 -p 6662:6662` — exposes the two ports our hospital and lab channels will listen on (see Part 2)
- `-v mirth-appdata:/opt/connect/appdata` — mounts a named Docker volume at Mirth's internal data directory, so channels, users, and settings survive container restarts or recreations

Verify it's running:
```bash
docker ps
```

You should see `myconnect` listed with status "Up."

## Step 4: Log into the Administrator

1. In Chrome, go to `https://localhost:8443`
2. Click **Download Administrator Launcher** and install it (a proper installer,
   bundled with a compatible Java runtime — no separate Java setup needed)
3. Open the **Mirth Connect Administrator Launcher**, enter server address
   `https://localhost:8443`
4. Log in with username `admin`, password `admin`
5. You'll be prompted to set a new password on first login (or asked to keep defaults,
   depending on version) — for a portfolio project with no real patient data, `admin`/`admin`
   is fine to keep temporarily, but consider changing it before your final walkthrough,
   since it signals security awareness.

You should land on the full Administrator interface — Dashboard, Channels, Users,
Settings, Alerts, Events, and Extensions all visible in the left nav. The server log at
the bottom confirms a clean start: `Mirth Connect 4.5.2 (Built on September 6, 2024)
server successfully started`.

---

## ℹ️ Note: Free vs. paid editions

Mirth Connect's frozen 4.5.2 release includes a lightweight **Web Dashboard**
(statistics only — Received/Filtered/Queued/Sent/Errored per channel) but **no
browser-based channel builder**. Building channels, filters, and transformers requires
the full **Administrator** client we just installed.

---

You're now ready for **Part 2: Building the Mock Hospital & Lab Channels**.
