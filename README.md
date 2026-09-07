# DLSS5 Toolkit

Finds which of your installed games can take **DLSS 5 Neural Rendering**,
installs it in one click, and removes it byte-for-byte.

[![Download](https://img.shields.io/badge/Download-DLSS5--Toolkit.exe-76b900?style=for-the-badge)](https://github.com/daniel-madrid-07/DLSS5-Toolkit/releases/latest)

![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?logo=windows&logoColor=white)
![No install](https://img.shields.io/badge/install-none-76b900)
![License](https://img.shields.io/badge/license-MIT-blue)

## Download

Grab **`DLSS5-Toolkit.exe`** from the
[latest release](https://github.com/daniel-madrid-07/DLSS5-Toolkit/releases/latest)
and run it. One ~11 MB file: **no Python, no installer, no registry changes.**

<details>
<summary>Running from source</summary>

Needs Python 3.10+ and nothing else — it never calls `pip`:

```
DLSS5.bat          (or:  python dlss5.py)
```

To build your own executable: `python build.py` (requires `pyinstaller`).
</details>

> [!WARNING]
> This drops a DLL next to your game executables — exactly what anti-cheat
> looks for. **Don't use it in competitive multiplayer.** The tool detects EAC,
> BattlEye, Vanguard and Denuvo AC and asks for confirmation, but the ban risk
> is yours.

---

## In-game controls

| Key | |
|---|---|
| **F8** | Opens the OptiScaler overlay — live sliders for Neural Rendering, the reversible proxy, upscaler and frame generation |
| **F10** | Toggles the neural pass on and off |

Both are set up automatically on install. F8 replaces OptiScaler's default
Insert key, which several games and the Steam overlay already use — you can
change it under **Settings... → System**.

The overlay is where the real-time work happens: the sliders live in the game's
memory, so they respond instantly. The INI is only read at startup.

## What DLSS 5 is, and what it isn't

DLSS 5 shipped on **3 September 2026** and it is not an upscaler. It is
*3D-Guided Neural Rendering*: a diffusion model that rewrites lighting and
materials on the already-rendered frame. DLSS 4.5 still handles Super
Resolution, Ray Reconstruction and Multi Frame Generation; DLSS 5 is a separate
layer on top.

**It can't be applied to just any game, and the reason matters.** The model
needs to know where things are in the scene. NVIDIA's official integration
feeds it through Streamline: colour, motion vectors, albedo, normals and
lighting buffers. A game that hands over none of that has nothing to give it.

The shortcut this tool relies on — the OptiScaler fork — doesn't hunt for those
buffers in the engine. It **intercepts the ones the game already passes to its
own upscaler** every frame (depth and motion vectors). That's why it works in
any title with an upscaler and no per-game work, and why it does nothing at all
in a game without one. With fewer guides than the official integration, the
result isn't identical to native DLSS 5 either.

Since fork **v0.2.0** (3 Sept 2026) the pass no longer requires DLSS: it hooks
FSR and XeSS just as well, and Vulkan is natively supported.

## Requirements

| | |
|---|---|
| **GPU** | RTX 50 (Blackwell). RTX 20/30/40 need a modified DLL this tool does not provide |
| **Driver** | 616.56 or newer |
| **Model** | `nvngx_dlssnr.dll` (~158 MB) — see below, this is the sticking point |
| **Game** | Any temporal upscaler (DLSS, FSR or XeSS), on DX11, DX12 or Vulkan |

The tool checks all four on startup and tells you which one is missing.

## The model is not in the driver

You can have the right driver installed and still find no `nvngx_dlssnr.dll`
anywhere. **It isn't shipped there.**

Verified on 5 Sept 2026 by downloading the official 616.64 installer (938 MB
from `us.download.nvidia.com`) and opening it: its only `nvngx_*` files are
`nvngx.dll`, `nvngx_dlssg.dll`, `nvngx_dlisr.dll` and `nvngx_update.exe`. No
`dlssnr`. There's no switch in the NVIDIA App either — NVIDIA confirmed there
would be no per-game override.

**Each game that implements DLSS 5 ships the model itself.** It was first found
inside NBA 2K27, at `data\streamline\nvngx_dlssnr.dll` (158 MB, identifying
itself as "NVIDIA DLSSNR"), and today that is the only game carrying it.

> [!NOTE]
> NVIDIA's announcement bundles two different things together. **Onimusha: Way
> of the Sword**, **The Blood of Dawnwalker** and **STAR WARS Zero Company**
> appear in the same article but only get DLSS 4.5. **They do not carry the
> model**, and neither does Onimusha's free demo. Installing them for this is
> 100 GB wasted.

> [!TIP]
> **Already have the file? Drop it next to the `.exe` and you're done.** It is
> picked up on startup with nothing to click. The first install copies it to
> the cache, so afterwards you can move or delete the executable.

**Search order:** the program's own folder → cache → your installed games →
any loose driver installer. Having the game installed is enough; you don't have
to play it. The DLL is copied to `%LOCALAPPDATA%\DLSS5\model` and reused for
every other game, so the source game can be uninstalled afterwards.

**The tool never downloads the model from third parties.** It belongs to NVIDIA,
and the sites that repackage it are precisely the ones worth avoiding.

> [!IMPORTANT]
> **Why the `.exe` doesn't bundle the model.** `nvngx_dlssnr.dll` is NVIDIA's
> proprietary software. Redistributing it is no more legal embedded inside an
> executable than loose in a ZIP — the container doesn't change the licence,
> and an `.exe` doesn't hide it either: PyInstaller packs, it doesn't encrypt.
> On top of that, a 170 MB executable that drops DLLs into game folders is the
> exact profile antivirus engines flag as a trojan.
>
> So the tool **locates** the model on your own disk instead of shipping it.
> Everything else works without it.

### You don't have to wait for the model

The neural pass is **optional inside OptiScaler**, not a startup requirement.
Without the DLL everything else still installs and runs: swapping the upscaler,
frame generation, RCAS sharpening, DLSS preset overrides, and 22 of the 35
settings. Only the neural pass stays off, and the overlay says exactly why
(`"nvngx_dlssnr.dll was not found"`) instead of failing silently. Once you have
the DLL, hit Apply again and it gets copied in.

## Usage

1. **Scan installed games** — walks Steam, Epic and GOG. About 6 seconds for
   40 games.
2. Pick one, choose a preset.
3. **Apply DLSS 5**.
4. In game: **F8** for the overlay, **F10** to toggle the pass.

### Tiers

- **Yes (DLSS)** — has DLSS. The ideal case.
- **Yes (FSR/XeSS)** — no DLSS, but since v0.2.0 the pass hooks FSR or XeSS
  inputs just as well.
- **No** — no temporal upscaler. There is no depth or motion vector to
  intercept, and no trick works around that.

### What Apply does

1. Downloads the fork's official release and caches it in `%LOCALAPPDATA%\DLSS5`.
2. Copies the files next to the **real** game executable — which isn't always in
   the root: Cyberpunk keeps it in `bin\x64`, Unreal games in
   `<Game>\Binaries\Win64`.
3. Renames `OptiScaler.dll` to a free name the game loads on its own
   (`dxgi.dll`, or the next available one if it's taken).
4. Writes `[DlssNr]` with the chosen preset, keeping the file's comments intact.
5. Copies the model from the cache (one copy per game is required — there is no
   shared location).
6. Upgrades the game's `nvngx_dlss*.dll` files if a newer version exists
   elsewhere on your PC. It never downloads NVIDIA DLLs: it uses what you have.

Anything overwritten is saved to `_DLSS5_backup\` with a manifest first.
**Revert** restores the folder byte-for-byte.

## Presets

| Preset | For |
|---|---|
| **Subtle** | Respects the original art. Only luminance carries the model's verdict |
| **Balanced** | The recommended one |
| **Maximum detail** | Pushes past what the model asks for. Visible |
| **Supersampling** | The model runs above native and is averaged back down with Lanczos3: less noise, higher cost |
| **Performance** | The model works at half resolution. Cost falls with the square |

### Per-game editor

**Settings...** opens an editor over the game's `OptiScaler.ini`: 35 options in
five collapsible groups — Neural Rendering, Upscaler, Quality & sharpening,
Frame Generation and System. Each control carries its explanation underneath,
with the ranges the file itself documents.

It saves **only what you changed**; everything else stays untouched, comments
included. A value left at `auto` stays `auto` — clicking a slider's number
returns it to `auto`. Changes take effect when the game starts.

### Overlay-only controls

The big improvement in v0.2.0 is the **reversible proxy**, and its recommended
mode is *Hybrid proxy + composed*: it keeps the midtones while recovering the
detail the old curve crushed in highlights. It **doesn't exist as an INI key**,
so no external window can pre-configure it. Change it in the overlay under
Colour. The same goes for multi-point white-point anchoring and Hold frame.

### Telling whether it actually does anything

Eyes lie, especially in motion. Two honest ways:

- **F10** toggles the pass without opening any menu. Stand still in a scene with
  interesting lighting and flick it.
- **DebugView → "Difference ×20"** paints what the model changed, amplified.
  A **flat grey** frame means it is doing nothing at all.

## Anti-cheat

If EAC, BattlEye, Vanguard, mhyprot or Denuvo AC is detected, the game is
flagged in the list and an explicit confirmation is required before installing.
Dropping a DLL next to a game executable is exactly what those systems hunt for.

## A note on fake repositories

Repositories circulate promising "DLSS 5 in any game, D3D9 included". That is
impossible: a D3D9 game has no motion vectors to give. One doing the rounds at
the time of writing was two days old, 677 MB of opaque binaries, and faked the
buffers with ReShade shaders.

The OptiScaler team also warns about fake websites and "manager apps": their
only legitimate homes are their GitHub, their Discord, and Nitec's NexusMods
page.

This tool only downloads from the official repositories listed in `SOURCES`
(`dlss5_apply.py`) and records the SHA-256 of everything it fetches.

## Layout

| File | |
|---|---|
| `dlss5.py` | Main window |
| `dlss5_scan.py` | Detection: PE parsing, engine, API, upscalers, GPU, anti-cheat |
| `dlss5_apply.py` | Download, install, INI editing and rollback |
| `dlss5_model.py` | Locating `nvngx_dlssnr.dll` |
| `dlss5_opts.py` | Settings catalogue with real types and ranges |
| `dlss5_editor.py` | Per-game visual editor |
| `build.py` | Builds the release executable |
| `tests.py` | 55 checks |

The project's history, including the assumptions that turned out to be wrong,
is in [CHANGELOG.md](CHANGELOG.md).

### Tests

```
python tests.py
```

Builds a fake game, installs over it, verifies the result and reverts, comparing
SHA-256 across the whole tree. If a single byte changes, it fails. It also
verifies that **every key in the catalogue actually exists** in the INI — an
invented key writes without error and does nothing, which is exactly the bug
`Log.LoggingEnabled` had.

## Credits

The hard work isn't mine:

- **[OptiScaler](https://github.com/optiscaler/OptiScaler)** (cdozdil / Nitec),
  GPL-3.0 — the DirectX hook and the whole upscaler bridge.
- **[OptiScaler_DLSSNR](https://github.com/Dagherbou/OptiScaler_DLSSNR)** (dag),
  GPL-3.0 — the Neural Rendering pass.
- **[RenoDX](https://github.com/clshortfuse/renodx)** (clshortfuse), MIT — the
  colour composition that keeps the result from falling apart.

This tool is a front-end: it detects, decides, configures, and knows how to undo
itself. It bundles none of the above — they are downloaded from their own
releases when you press Apply.

## Licence

MIT — see [LICENSE](LICENSE). It covers only the code in this repository.

Software downloaded at run time keeps its own licence and is not redistributed
here; the per-component details are in [NOTICE.md](NOTICE.md).

Not affiliated with NVIDIA or the OptiScaler team.
