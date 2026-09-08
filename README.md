<div align="center">

# DLSS5 Toolkit

**Finds which of your installed games can take DLSS 5 Neural Rendering, installs it in one click, and removes it byte-for-byte.**

[![Download](https://img.shields.io/badge/Download-DLSS5--Toolkit.exe-76b900?style=for-the-badge)](https://github.com/daniel-madrid-07/DLSS5-Toolkit/releases/latest)

![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?logo=windows&logoColor=white)
![No install](https://img.shields.io/badge/install-none-76b900)
![License](https://img.shields.io/badge/license-MIT-blue)

</div>

---

> [!WARNING]
> This drops a DLL next to your game executables — exactly what anti-cheat looks for. **Don't use it in competitive multiplayer.** The tool detects EAC, BattlEye, Vanguard and Denuvo AC and asks for confirmation, but the ban risk is yours.

## What it does

DLSS 5 shipped on 3 September 2026 and it is not an upscaler — it's *3D-Guided Neural Rendering*, a diffusion model that rewrites lighting and materials on the already-rendered frame, layered on top of DLSS 4.5. This tool scans your installed games (Steam, Epic, GOG), tells you which ones can carry the pass, and installs, configures or reverts it in one click — no manual DLL wrangling, no hand-edited INI files.

It relies on the OptiScaler fork of the Neural Rendering pass, which intercepts the depth and motion vectors a game already passes to its own upscaler (DLSS, FSR or XeSS). That's why it works in any title with an upscaler and does nothing in a game without one.

## Features

- **Scan installed games** — walks Steam, Epic and GOG in about 6 seconds for 40 games, and reports whether each one supports DLSS, FSR/XeSS, or nothing at all
- **One-click install and revert** — installs the pass next to the real game executable and can restore the folder byte-for-byte from a manifest-backed backup
- **In-game overlay (F8)** — live sliders for Neural Rendering, the reversible proxy, upscaler and frame generation; **F10** toggles the pass on and off
- **Five presets** — Subtle, Balanced, Maximum detail, Supersampling and Performance, trading fidelity for cost
- **Per-game settings editor** — 35 options in five collapsible groups (Neural Rendering, Upscaler, Quality & sharpening, Frame Generation, System), each explained, saving only what changed
- **Model auto-detection** — locates `nvngx_dlssnr.dll` on your own disk (its own folder, cache, installed games, or a loose driver installer) instead of shipping or downloading it from third parties
- **DLL upgrades** — upgrades a game's `nvngx_dlss*.dll` files using newer versions already on your PC, never downloading NVIDIA DLLs
- **Anti-cheat detection** — flags EAC, BattlEye, Vanguard, mhyprot and Denuvo AC before letting you install
- **Hooks FSR and XeSS too** — since fork v0.2.0, the pass no longer requires DLSS, and Vulkan is natively supported

## Installation / Usage

### Download

Grab **`DLSS5-Toolkit.exe`** from the [latest release](https://github.com/daniel-madrid-07/DLSS5-Toolkit/releases/latest) and run it. One ~11 MB file: no Python, no installer, no registry changes.

<details>
<summary>Running from source</summary>

Needs Python 3.10+ and nothing else — it never calls `pip`:

```
DLSS5.bat          (or:  python dlss5.py)
```

To build your own executable: `python build.py` (requires `pyinstaller`).
</details>

### Requirements

| | |
|---|---|
| **GPU** | RTX 50 (Blackwell). RTX 20/30/40 need a modified DLL this tool does not provide |
| **Driver** | 616.56 or newer |
| **Model** | `nvngx_dlssnr.dll` (~158 MB) — see below, this is the sticking point |
| **Game** | Any temporal upscaler (DLSS, FSR or XeSS), on DX11, DX12 or Vulkan |

The tool checks all four on startup and tells you which one is missing.

### The model is not in the driver

You can have the right driver installed and still find no `nvngx_dlssnr.dll` anywhere — it isn't shipped there. Each game that implements DLSS 5 ships the model itself; it was first found inside NBA 2K27, at `data\streamline\nvngx_dlssnr.dll`.

> [!TIP]
> Already have the file? Drop it next to the `.exe` and you're done — it's picked up on startup with nothing to click. The first install copies it to the cache, so afterwards you can move or delete the executable.

**Search order:** the program's own folder → cache → your installed games → any loose driver installer. The DLL is copied to `%LOCALAPPDATA%\DLSS5\model` and reused for every other game.

The neural pass is optional inside OptiScaler, not a startup requirement — without the DLL, everything else still installs and runs (upscaler swap, frame generation, sharpening, DLSS preset overrides).

### Usage

1. **Scan installed games**.
2. Pick one, choose a preset.
3. **Apply DLSS 5**.
4. In game: **F8** for the overlay, **F10** to toggle the pass.

### Tests

```
python tests.py
```

Builds a fake game, installs over it, verifies the result and reverts, comparing SHA-256 across the whole tree. Also verifies that every key in the settings catalogue actually exists in the INI.

### Layout

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

The project's full history, including the assumptions that turned out to be wrong, is in [CHANGELOG.md](CHANGELOG.md).

## Tech stack

- Python 3.10+
- PyInstaller (for building the standalone executable)
- OptiScaler / OptiScaler_DLSSNR (GPL-3.0) — the DirectX hook, upscaler bridge and Neural Rendering pass
- RenoDX (MIT) — the colour composition used by the pass

## Credits

The hard work isn't the toolkit's own:

- **[OptiScaler](https://github.com/optiscaler/OptiScaler)** (cdozdil / Nitec), GPL-3.0 — the DirectX hook and the whole upscaler bridge.
- **[OptiScaler_DLSSNR](https://github.com/Dagherbou/OptiScaler_DLSSNR)** (dag), GPL-3.0 — the Neural Rendering pass.
- **[RenoDX](https://github.com/clshortfuse/renodx)** (clshortfuse), MIT — the colour composition that keeps the result from falling apart.

This tool is a front-end: it detects, decides, configures, and knows how to undo itself. It bundles none of the above — they are downloaded from their own releases when you press Apply. Not affiliated with NVIDIA or the OptiScaler team.

## License

MIT — see [LICENSE](LICENSE). It covers only the code in this repository. Software downloaded at run time keeps its own licence and is not redistributed here; per-component details are in [NOTICE.md](NOTICE.md).
