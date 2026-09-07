# Changelog

How this tool came together, and what had to be corrected along the way. Dates
are the real commit dates.

DLSS 5 shipped on 3 September 2026, so most of what is written about it is
days old and some of it is wrong. Several entries below exist because an
assumption was checked and turned out to be false.

---

## v1.2.0 — 7 September 2026

### F8 opens the overlay

Install now writes `Menu.ShortcutKey=0x77`, so **F8** opens the OptiScaler
overlay instead of the default Insert, which several games and the Steam/RTSS
layers already claim. **F10** still toggles the neural pass.

A custom overlay drawn over the game was considered and rejected: it would need
DLL injection and a DirectX swapchain hook in C++, and it still could not move
the sliders. Those live in the game process's memory, and OptiScaler does not
re-read the INI at run time. Retargeting the real overlay solves the actual
problem.

Two new editor settings back this up: `Menu.ShortcutKey` to rebind the key if a
game already uses F8, and `Menu.Scale` for overlay size on 4K displays.

### English throughout

README, NOTICE, every UI string, presets, the settings catalogue, log messages,
dialogs, comments and docstrings. `pruebas.py` became `tests.py`, keeping its
history.

**Fixed while translating:** the cache folder was `modelo` in code but
documented as `model`. The code now uses `model`, and the existing cache was
migrated rather than orphaned.

### The rollback was not complete

`upgrade_dlss_dll()` copied the game's old `nvngx_dlss.dll` into the backup
folder but never recorded it in the manifest. `revert()` walks the manifest,
not the folder, so the old DLL was never put back — and was then deleted along
with the backup directory.

The "reverts byte-for-byte" promise was **false** whenever the DLL upgrade ran.

Hit for real on Red Dead Redemption 2: after reverting, the game was left on
DLSS 310.1.0 with its original 2.2.10 gone. None of the 52 tests caught it,
because none called `upgrade_dlss_dll` before reverting. The new test does, and
was verified to fail — three failures, naming `nvngx_dlss.dll` — when the fix
is removed.

### Scan on startup

The library scan takes about 3 seconds for 40 games, so it now runs
automatically after the system check instead of hiding behind a button. When it
finishes, the best candidate is preselected: never an anti-cheat title, never
one already installed, preferring native DLSS and then the oldest DLSS DLL —
that game gains a version bump on top of the neural pass, so it shows the most.

Opening the app and pressing Apply is the whole flow. "Scan installed games"
became "Rescan games".

---

## v1.1.0 — 5 September 2026

### Drop the model next to the executable

`find_existing()` did not look in the program's own folder, which is the first
place anyone who obtains the DLL will put it. It is now the first path checked.
The first install copies it to the cache, so the executable can be moved or
deleted afterwards.

New `app_dir()`: under PyInstaller, `__file__` points at the temporary
extraction directory and is useless. `sys.executable` is the right answer when
`sys.frozen` is set. Verified by building a diagnostic binary — `frozen=True`,
`app_dir()` returns the .exe folder, and a model beside it is found.

---

## v1.0.0 — 5 September 2026

### Single executable

`build.py` produces `DLSS5-Toolkit.exe` with PyInstaller (~11 MB, `--onefile
--windowed`). No Python install, no installer, no registry changes.

**Found while building it:** the exclusion list included `email`, `http` and
`xml` to slim the binary, but `urllib.request` pulls those in to download the
OptiScaler package. The .exe died at startup with `ModuleNotFoundError`. Only
third-party packages are excluded now, never the standard library. Verified by
running it isolated in an empty folder.

What deliberately stays out, and why:

- **`nvngx_dlssnr.dll`** — NVIDIA's property. Embedding it in an .exe is
  redistribution just as much as shipping it loose: the container does not
  change the licence, and PyInstaller packs rather than encrypts. A 170 MB
  executable that drops DLLs into game folders is also the exact profile
  antivirus engines flag as a trojan.
- **OptiScaler's binaries** — GPL-3.0. Redistributing them would force this
  project to be GPL instead of MIT.

Both are downloaded or located at run time.

### Published

MIT licence, chosen after confirming this project neither includes nor links
OptiScaler: it downloads their releases and writes their INI, so GPL-3.0 does
not propagate. `NOTICE.md` documents each component's licence separately —
GitHub reported `NOASSERTION` until the third-party notes were moved out of
`LICENSE`, because its detector requires that file to hold only the licence
text.

`.gitignore` hardened so no `.dll`, `.zip`, `.7z` or `nvngx*` can be committed
by accident.

---

## Pre-release — 4–5 September 2026

### Per-game settings editor

A **Settings...** window over the game's `OptiScaler.ini`: 35 options in five
collapsible groups, each with its real range and a line of help. Saves only
what changed; the rest of the file stays untouched, comments included.

Two bugs surfaced while building it:

- **`[Log] LoggingEnabled` does not exist** in v0.2.0. The key is `LogToFile`.
  The installer had been writing an invented key that sat at the end of the
  section doing nothing. A test now fails if any catalogue key is missing from
  the real INI.
- **`ttk.Scale.set()` fires its callback on construction**, so opening the
  editor marked all twelve sliders as modified. Saving would have overwritten
  everything left at `auto` with the slider minimum — silently destroying a
  configuration. Two tests guard it now.

### Only NBA 2K27 ships the model

`SHIPPING_GAMES` listed three games as sources for `nvngx_dlssnr.dll`. Only one
is. NVIDIA's announcement bundles two different things: NBA 2K27 gets Neural
Rendering, while Onimusha: Way of the Sword, The Blood of Dawnwalker and STAR
WARS Zero Company only get DLSS 4.5. Onimusha's free demo does not carry it
either. Sending someone to install one of those would have wasted ~100 GB.

### The model is not in the driver

The previous entry assumed `nvngx_dlssnr.dll` lived inside the driver installer
and merely needed extracting. That was never checked, and it is false.

The official 616.64 installer (938 MB, `us.download.nvidia.com`) was downloaded
and opened: its only `nvngx_*` files are `nvngx.dll`, `nvngx_dlssg.dll`,
`nvngx_dlisr.dll` and `nvngx_update.exe`. No `dlssnr`. The files are dated
26 August, before DLSS 5 launched.

Each game that implements DLSS 5 ships the model itself. `find_in_games()` now
searches installed libraries — the real source — before any driver installer,
and `help_text()` no longer sends anyone after a 1 GB download that cannot help.

### Adapted to the real DLSS 5

The 3 September launch invalidated three assumptions in the original code:

- **Neural Rendering no longer requires DLSS.** Since fork v0.2.0 it reads FSR
  and XeSS inputs just as well, so forcing `Dx12Upscaler=dlss` was removed —
  it added risk for nothing.
- **Vulkan is natively supported.** The old "limited" tier wrongly discarded
  games like Wuthering Waves, which now comes out as applicable.
- **The model does not install with the driver.** NVIDIA also confirmed there
  would be no per-game override in the NVIDIA App.

`ScalingDownscaler` and `ToggleKey` (F10) were added to the presets, plus a
supersampling preset, all verified against v0.2.0's own INI.

---

## Initial commit — 4 September 2026

Detection, install and rollback, with a test that builds a fake game, installs
over it, reverts, and compares SHA-256 across the whole tree.

Three bugs were caught by testing against a real library rather than assuming:

- Hogwarts Legacy dropped to "partial" because the walk pruned `Engine/` — the
  exact folder where Unreal hides `nvngx_dlss.dll`, at depth 7.
- Counter-Strike 2 picked `vconsole2.exe` over `cs2.exe`, because the scoring
  favoured file size and a dev tool was larger.
- Fortnite fell to "no" because its API could not be proven. Failing to prove
  an API is not proof that it is Vulkan.

A Tk widget was also being read from a worker thread, which would have hung the
window sooner or later.
