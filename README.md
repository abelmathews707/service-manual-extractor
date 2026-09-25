# service-manual-extractor

Formerly `abelmathews707/ford-service-disc`. This fork is expanding toward
multiple service-manual formats and vehicle makes. **Ford support is implemented;
GM HTML and PDF inputs have been inspected, the shared v1 extraction contract
is frozen, and safe ZIP/folder/PDF source reading plus HTML/PDF content
normalization, Repair Buddy integration and the shared offline viewer are
implemented.**

Start the GM work from [the current handoff](docs/CURRENT_HANDOFF.md), then use
the [staged implementation plan](docs/GM_HTML_PLAN.md) and
[test plan](docs/GM_HTML_TEST_PLAN.md). The existing `python -m fsd` commands
remain compatible. Existing local checkouts do not need to be renamed.

The manufacturer-neutral contract is documented in
[docs/SERVICE_MANUAL_CONTRACT_V1.md](docs/SERVICE_MANUAL_CONTRACT_V1.md). Step 2
adds `python3 -m sme contract` and `validate-manifest` for contract inspection;
Step 3 adds neutral `probe` and staged `extract` readers. See the
[source reader guide](docs/SOURCE_READER_V1.md).
Step 4 adds `sme normalize`; see the
[content normalization guide](docs/CONTENT_NORMALIZATION_V1.md) for requirements
and remaining HTML acceptance limits.
Step 7 adds `sme build-viewer`; see the
[shared viewer guide](docs/SHARED_VIEWER_V1.md).

**Read your Ford service manual DVD without the original Windows software.**
Extracts the workshop manual, wiring diagrams and PCED off a Ford Technical
Service Publications disc and rebuilds them as a fast, searchable website you
can host on your own machine or home server.

Works on macOS, Linux and Windows. Python 3.9+, no dependencies.
**Ships no Ford content — bring your own disc.**

```bash
git clone https://github.com/abelmathews707/service-manual-extractor
cd service-manual-extractor
python3 -m fsd all /Volumes/20SLB -o site --serve
```

That reads the disc, unpacks it, builds the site and opens it on
<http://localhost:8848>.

---

## Release notes — 0.1.0 Foundation (2026-09-14)

This fork builds on [shad0wca7/ford-service-disc](https://github.com/shad0wca7/ford-service-disc).
It retains the existing BAY POD v2 reader, searchable static viewer,
self-hosting setup, and Android offline/Chrome 74 compatibility fixes.

`v0.1.0` marks this fork's first consolidated foundation. Fork versioning starts
at 0.1.0 independently of the upstream 1.0.0 baseline. This checkpoint pairs
with [Repair Buddy 0.1.0](https://github.com/abelmathews707/repair-buddy/releases/tag/v0.1.0).
Future work builds on these tagged versions; `main` may continue to advance.

- Added POD BAY v1 archive support, including full 8.3 filenames and
  extensions, stored payload lengths, and strict structural validation.
- Deep probe output now distinguishes a complete decode from a sampled check.
- Added exact archive selection with `--archive` and separate extraction
  directories for same-code archives from different source folders.
- Documented the v1 layout and validation of six unique owned archives:
  26,162 entries strictly decode and all six manifests parse.

The v1 evidence covers archive reading and decompression. A complete v1
viewer build and link audit remain unverified. See
[compatibility and known limits](docs/COMPATIBILITY.md) for the supported
scope and the pre-existing strict decoder warning on one older v2 archive.
No Ford content is included.

## The problem this solves

You own a Ford service disc. It is a Windows application from around 2005 and
it will not install on Windows 10 or 11 — the installer is 32-bit, it wants a
disc volume label it cannot find, and if you do get it running it may tell you:

> Error. This volume has expired and can no longer be used.

The usual workaround is a Windows XP virtual machine. This tool skips all of
that. It reads the content directly off the disc and gives you a static
website — no installer, no VM, no date checks, no DVD drive needed once you
have an image.

The content is stored in an undocumented Ford archive family with two observed
container layouts—**"POD BAY" version 1** and **"BAY POD" version 2**—and an
LZ77 variant called **IDICOMP**. They are specified in
[docs/FORMAT.md](docs/FORMAT.md) and
[docs/POD_BAY_V1.md](docs/POD_BAY_V1.md).

## Quick start

You need Python 3.9 or newer and the disc — mounted, copied to a folder, or as
an image file.

**1. Check the disc can be read.** This is fast and changes nothing:

```bash
python3 -m fsd probe /Volumes/20SLB
```

```
Disc label : 20SLB
Read as    : directory

  ELB         24.6 MB  v2    1882 entries  EVTM     2020 Mustang
         xml:1193, svg:686, csv:1, epl:1, wcf:1
         decoded 25 sampled
  SLB        512.3 MB  v2    7843 entries  SERVICE  2020 Mustang
         jpg:6130, htm:1707, gif:2, pdf:2, epl:1, wcf:1
         decoded 25 sampled
  VL2          4.6 MB  v2     505 entries  PCED     2020 Explorer, Escape, Aviator, Mustang +19 more [Gasoline Engines]
         gif:252, htm:250, epl:1, wcf:1, css:1
         decoded 25 sampled

Result: this disc looks readable.
```

**2. Build and serve it:**

```bash
python3 -m fsd all /Volumes/20SLB -o site --serve
```

To reach it from a phone or tablet in the garage, serve it on your network:

```bash
python3 -m fsd serve site --host 0.0.0.0
```

### No DVD drive?

Image the disc on a machine that has one, then point `fsd` at the image file.
Raw dumps (CloneCD `.img`, Alcohol, 2352-byte sectors) are read **in place** —
no conversion and no mounting, so no root or admin rights either:

```bash
python3 -m fsd all IMAGE.img -o site
```

## Commands

| Command | What it does |
|---|---|
| `fsd probe DISC` | Identify a disc and decode a sample from each archive. Start here. |
| `fsd extract DISC -o extracted` | Unpack the archives to plain files and stop. |
| `fsd build extracted -o site` | Build the website from unpacked files. |
| `fsd all DISC -o site` | Extract and build in one step. |
| `fsd serve site` | Serve a built site over HTTP. |
| `fsd iso IMAGE out.iso` | Convert a raw dump to a plain ISO, if you want to mount it. |
| `sme build-viewer normalized -o site` | Build the shared viewer from neutral records. |

`DISC` can be a mount point (`/Volumes/20SLB`, `D:\`), a folder holding a copy
of one, or an image file (`.iso`, `.img`, `.bin`).

Run `python3 -m fsd COMMAND --help` for the options.

### Neutral source inspection

The new neutral reader verifies supported HTML/PDF ZIPs, unpacked folders and
standalone PDFs without changing the established Ford commands:

```bash
python3 -m sme probe /path/to/manual-source --json
python3 -m sme extract /path/to/manual-source -o verified-source
python3 -m sme normalize verified-source -o normalized-source --json
python3 -m sme build-viewer normalized-source -o site --json
```

Extraction requires a fresh output path and publishes only after every selected
file is copied and hash-verified. Normalization preserves HTML structure and
cited PDF pages; PDF text reading requires Poppler. See
[the source reader guide](docs/SOURCE_READER_V1.md) for exact
selection, safety rules and partial-source behavior.

The neutral viewer lists every selected publication, searches across them,
preserves nested navigation and backlinks, opens cited local PDF pages, and
shows unavailable links or diagrams explicitly. It uses the same offline viewer
shell as the Ford builder without passing non-Ford inputs through Ford `.EPL`
parsing.

### Select an exact archive

Some discs contain the same archive code in several language folders. Use
`probe --json` to find each archive's `identity` and `output_dir`, then copy
the desired identity into `--archive`:

```bash
python3 -m fsd probe /path/to/disc --json
python3 -m fsd extract /path/to/disc -o extracted --archive content/useni4/v22.arc
python3 -m fsd all /path/to/disc -o site --archive content/useni4/v22.arc
```

The path above is an example; use an identity present on your disc. Identities
are case-insensitive, source-relative paths with forward slashes. Repeat
`--archive` to select multiple archives. `--book V22` selects every archive
with that code; combining `--book` and `--archive` includes matches from
either option.

Unique codes still extract to `<CODE>/`. Duplicate codes use distinct
directories, such as `V22--USENI4/` and `V22--CNFRI4/`, so their files stay
separate. Start with a fresh extraction directory when upgrading from an
older version that may have combined duplicate codes. The legacy `fsd build`
path currently uses only one book per role (SERVICE, EVTM, or PCED); select
the desired archives before building when your disc contains several books of
one role. The neutral `sme build-viewer` path keeps every selected publication.

## What you get

From the 2020 Mustang disc this was developed against, the site contains:

- **1,542 workshop procedures** — diagnosis and testing, removal and
  installation, specifications and torque values
- **394 wiring sheets** — schematics and component locations as zoomable
  vector graphics, not scans
- **594 connector face views** — pin-by-pin circuit, wire colour, gauge,
  function and terminal part number
- **233 PCED pages** — pinpoint tests, DTC charts and reference values

Everything is cross-searchable, and pages link both ways: each procedure lists
what links *to* it, and each connector lists the sheets it appears on.

The viewer is a static site — plain HTML, CSS and JavaScript with no
framework, no build step and no external requests. Any web server will do, and
it works fine from a subdirectory. It works on a phone, and it renders
documents on a light background on purpose: inverting a wiring diagram would
misrepresent the wire colours.

### It also repairs the disc

Some links were already dead on the original DVD. Those are fixed here:
procedures stored without their filename prefix, "back to index" links
pointing at a server-side URL Ford never shipped, references to location
sheets that were never pressed, and frame-based tables of contents that
rendered as unstyled duplicate navigation.

## Self-hosting it

The built site is static files, so any web server works — but if you want it
running permanently on a home server, there is a Compose setup in
[`docker/`](docker/) that serves it with Caddy (gzip, cache headers, health
check):

```bash
cd docker
cp .env.example .env      # point SITE at your built site
docker compose up -d
```

Build the site on your laptop and copy it over, or let the server unpack the
disc itself — mount the image and run the one-shot builder:

```bash
docker compose --profile build run --rm build
```

**The site is always a bind mount, never baked into an image.** An image with
the content in it would be a copyrighted 600 MB artefact one `docker push`
away from being published by accident.

`fsd serve` is fine for a quick look, but it is a development server. Use
Caddy, nginx or Apache for anything permanent.


## Offline on a tablet

The built site is static, so it runs fully offline on a phone or tablet. For a
diagnostic tablet in the garage, there is a tiny WebView wrapper in
[`viewer/android/`](viewer/android/): it serves the local copy through an HTTP
server bound only to the device's loopback interface, which gives the
fetch-based viewer a real same-origin URL without exposing it to the network.
Android 10 WebView requires the wrapper's app-level cleartext opt-in even for
that local origin; the server socket itself remains loopback-only. No Gradle,
no content included. Build it with the Android SDK command-line tools, copy
the built site to `/sdcard/FordManual/`, install the APK, done.

## Compatibility

**Confirmed end to end against one disc so far** — 2020 Mustang (`20SLB`),
which carries a SERVICE, an EVTM and a PCED book. The archive reader and
IDICOMP decoder have also been deep-validated against six unique `POD BAY`
version 1 archives containing 26,162 entries; a complete version 1 site build
has not yet been validated.

Nothing in the tool is specific to that title. It asks each archive's own
manifest what book it is and derives every filename pattern from that, so
other discs in the same product line should work. Ford sold these under the
generic "Technical Service Publications" name for many years and many models,
and the PCED volume alone covers 23 different vehicles, so the format almost
certainly spans a large part of the range.

But "should work" is not "does work". **If you have a disc, please run
`fsd probe` and [open an issue](../../issues/new?template=disc-report.yml) —
successes are as useful as failures.** See
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) for what is confirmed.

Book types other than SERVICE, EVTM and PCED will still extract to files; the
viewer will skip them and tell you it did.

## How it works

```
                  ┌─ POD BAY v1 ─┐
disc ──► archive ─┤              ├─► IDICOMP ──► files ──► static site
                  └─ BAY POD v2 ─┘
                     (fsd/arc.py)    (fsd/idicomp.py) (fsd/build.py)
```

`fsd/iso.py` reads ISO9660 directly out of an image, handling 2048, 2352 and
2448-byte sectors, so nothing needs mounting.

The archive layouts and compression format were reverse-engineered for this
project. The write-ups in [docs/FORMAT.md](docs/FORMAT.md) and
[docs/POD_BAY_V1.md](docs/POD_BAY_V1.md) are released into the public domain so
anyone can write another implementation. The test suite synthesises its own
archives and needs no Ford content, so it doubles as an executable spec:

```bash
python3 -m unittest discover -s tests -v
```

## Legal

This repository contains **software only**. It includes no Ford service
content, no disc images and no extracted files, and it never will — CI fails
the build if any appear.

The service content on your disc is copyrighted by Ford Motor Company, who
still sell access to it. This tool is for reading a disc **you own**. Do not
redistribute what comes out of it.

No access control is circumvented. The content is compressed, not encrypted,
and there is no key: the `VOLUME.ENC` file on the disc is a licence token that
plays no part in reading it, and this tool never consults it. The formats were
worked out by inspecting data on media I own, in order to keep using it on
current hardware.

Ford, Lincoln, Mercury and Motorcraft are trademarks of Ford Motor Company,
used here only to say which discs this reads. This project is not affiliated
with, endorsed by, or sponsored by Ford Motor Company.

Software is MIT licensed ([LICENSE](LICENSE)). The format documentation is
CC0 / public domain.

## See also

- [fetch-ford-service-manuals](https://github.com/iamtheyammer/fetch-ford-service-manuals)
  — downloads manuals from Ford's live PTS subscription portal. Different
  source, complementary problem: that one needs a paid subscription and an
  internet connection, this one needs a disc.

<sub>Keywords: Ford service manual DVD, Ford workshop manual CD, Ford service
disc Windows 11, Ford .ARC file, POD BAY, BAY POD, IDICOMP, Technical Service
Publications, TSP, EVTM wiring diagram, PCED, volume has expired, extract Ford
service CD, offline service manual, right to repair.</sub>
