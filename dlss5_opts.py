"""
Catalogue of editable settings, with their real types and ranges.

Everything here was taken by reading v0.2.0's OptiScaler.ini key by key. The
ranges are the ones the file itself documents, not guesses.

What is NOT here, because it does not exist as an INI key and lives only in the
in-game overlay (F8):
  - The reversible proxy (Off / Neutwo / Hybrid, composed or replace)
  - Multi-point white-point anchoring
  - Hold frame, for comparing settings on one frozen frame
The UI says so instead of pretending they can be touched from outside.
"""

from __future__ import annotations

# Control types:
#   bool   -> dropdown auto/true/false
#   float  -> slider (min, max, step)
#   int    -> integer slider
#   choice -> dropdown [(ini_value, label), ...]

DOWNSCALERS = [("0", "FSR1"), ("1", "Bicubic"), ("2", "Catmull-Rom"),
               ("3", "Lanczos2"), ("4", "Lanczos3"), ("5", "Kaiser2"),
               ("6", "Kaiser3"), ("7", "MAGIC")]

DLSS_PRESETS = [("0", "Default"), ("11", "K  (transformer)"),
                ("12", "L"), ("13", "M"), ("14", "N"), ("15", "O"),
                ("3", "C"), ("5", "E"), ("6", "F"), ("7", "G")]

# Windows virtual-key codes for the overlay shortcut.
OVERLAY_KEYS = [("0x77", "F8  (default here)"), ("0x78", "F9"),
                ("0x7A", "F11"), ("0x7B", "F12"), ("0x2D", "Insert"),
                ("0x24", "Home"), ("0x08", "Backspace"), ("-1", "None")]

# Each group: (id, title, subtitle, [settings])
# Each setting: (ini_section, key, label, kind, extra, help)

GROUPS = [
    ("nr", "Neural Rendering", "The DLSS 5 pass. Needs nvngx_dlssnr.dll.", [
        ("DlssNr", "Enabled", "Enabled", "bool", None,
         "Turns the neural pass on. Without the model it will not start even "
         "when set to true."),
        ("DlssNr", "TransferStrength", "Detail strength", "float", (0.0, 2.0, 0.05),
         "How far the frame moves toward the model's picture. 0 gives back "
         "exactly what the upscaler produced; 1 is the model's picture; above "
         "that it carries on past what the model asked for."),
        ("DlssNr", "ColourStrength", "Colour strength", "float", (0.0, 4.0, 0.05),
         "Whether the model's colour arrives with its light. 0 keeps the game's "
         "own hue exactly. Very high values can flicker."),
        ("DlssNr", "MaxRatio", "Highlight guard", "float", (1.0, 4.0, 0.1),
         "The most the pass may brighten any pixel. Stops a bright light from "
         "turning into coloured cells. Darkening is not capped."),
        ("DlssNr", "WorkingScale", "Model resolution", "float", (0.25, 2.0, 0.05),
         "What fraction of the frame the model works at. Cost falls with the "
         "square. Above 1.0 it supersamples: cleaner, more expensive."),
        ("DlssNr", "ScalingDownscaler", "Downscale filter", "choice", DOWNSCALERS,
         "Only used when model resolution goes above 1.0. Lanczos3 is the "
         "default and the recommended one."),
        ("DlssNr", "WhitePointScale", "White point", "float", (0.1, 4.0, 0.05),
         "Multiplies the white point before the model sees the frame. This is "
         "the paper-white control."),
        ("DlssNr", "Intensity", "Intensity", "float", (0.0, 2.0, 0.05),
         "One of NVIDIA's own parameters. Undocumented."),
        ("DlssNr", "AutoMask", "Automatic masking", "bool", None,
         "Lets the model recognise objects and apply itself selectively."),
        ("DlssNr", "DebugView", "Debug view", "choice",
         [("0", "Off"), ("1", "What the model sees"),
          ("2", "Its raw answer"), ("3", "Difference x20")],
         "Option 3 is the useful one: it shows what changed, amplified. A flat "
         "grey frame means the pass is doing nothing."),
    ]),

    ("upscaler", "Upscaler", "Which scaling technique the game uses.", [
        ("Upscalers", "Dx12Upscaler", "DirectX 12", "choice",
         [("auto", "Automatic"), ("dlss", "DLSS"), ("xess", "XeSS"),
          ("ffx", "FSR 3.1 / 4.x"), ("fsr22", "FSR 2.2"), ("fsr21", "FSR 2.1")],
         "Automatic picks DLSS on NVIDIA cards."),
        ("Upscalers", "Dx11Upscaler", "DirectX 11", "choice",
         [("auto", "Automatic"), ("dlss", "DLSS"), ("xess", "XeSS"),
          ("fsr22", "FSR 2.2 native"), ("fsr31", "FSR 3.1 native")], ""),
        ("Upscalers", "VulkanUpscaler", "Vulkan", "choice",
         [("auto", "Automatic"), ("dlss", "DLSS"), ("xess", "XeSS native"),
          ("ffx", "FSR 2.3 / 3.1 native"), ("fsr21", "FSR 2.1 native")], ""),
        ("DLSS", "RenderPresetOverride", "Force a DLSS preset", "bool", None,
         "Lets you impose one preset instead of whatever the game picks."),
        ("DLSS", "RenderPresetForAll", "Preset for all modes", "choice",
         DLSS_PRESETS,
         "K is the current transformer model. Only has an effect with the "
         "option above turned on."),
    ]),

    ("quality", "Quality & sharpening", "Output scaling and sharpening.", [
        ("OutputScaling", "Enabled", "Output scaling", "bool", None,
         "Renders above display resolution and scales down after. DX12 and "
         "DX11-on-DX12 only."),
        ("OutputScaling", "Multiplier", "Multiplier", "float", (0.5, 3.0, 0.1),
         "How far above native to render. 1.5 is the default."),
        ("OutputScaling", "Downscaler", "Downscale filter", "choice", DOWNSCALERS, ""),
        ("CAS", "Enabled", "RCAS sharpening", "bool", None,
         "Contrast-adaptive sharpening."),
        ("Sharpness", "OverrideSharpness", "Force sharpness", "bool", None,
         "Ignores whatever sharpness value the game asks for."),
        ("Sharpness", "Sharpness", "Sharpness", "float", (0.0, 1.0, 0.05),
         "0.3 by default. With RCAS the useful ceiling reaches 1.3."),
        ("CAS", "MotionSharpnessEnabled", "Motion sharpness", "bool", None,
         "Adds or removes sharpening according to how far a pixel moves."),
        ("CAS", "MotionSharpness", "Motion amount", "float", (-1.3, 1.3, 0.05),
         "Negative removes sharpening in motion; positive adds it."),
    ]),

    ("fg", "Frame Generation", "Interpolated frames. Mind the latency.", [
        ("FrameGen", "Enabled", "Enabled", "bool", None,
         "Turns frame generation on."),
        ("FrameGen", "FGOutput", "Method", "choice",
         [("auto", "Automatic"), ("dlssg", "DLSS-G (NVIDIA)"),
          ("fsrfg", "FSR-FG"), ("xefg", "XeSS-FG"), ("optifg", "OptiFG")],
         "DLSS-G requires the game to support it already."),
        ("FrameGen", "AllowedFrameAhead", "Frames ahead", "int", (1, 3, 1),
         "How far ahead it may run. Less lead, less latency."),
        ("Framerate", "FramerateLimit", "FPS limit", "float", (0.0, 360.0, 5.0),
         "0 disables it. Uses Reflex where available, so it lowers latency "
         "better than an external limiter."),
        ("FrameGen", "DebugView", "Debug view", "bool", None,
         "Visually marks the generated frames."),
    ]),

    ("system", "System", "Overlay, display and diagnostics.", [
        ("Menu", "ShortcutKey", "Overlay key", "choice", OVERLAY_KEYS,
         "Which key opens the OptiScaler overlay in game. Change it if the "
         "game already uses F8 for something else."),
        ("Menu", "OverlayMenu", "In-game overlay", "bool", None,
         "OptiScaler's own menu. Without it you lose the reversible proxy and "
         "the live sliders."),
        ("Menu", "Scale", "Overlay size", "float", (0.5, 2.0, 0.1),
         "Scale of the in-game menu. Useful at 4K, where it comes out small."),
        ("HDR", "ForceHDR", "Force HDR", "bool", None,
         "Forces the HDR colour space. Only if your display supports it."),
        ("HDR", "UseHDR10", "Use HDR10", "bool", None,
         "R10G10B10A2 instead of R16G16B16A16 float."),
        ("V-Sync", "OverrideVsync", "Control V-Sync", "bool", None,
         "Lets OptiScaler manage vertical sync."),
        ("Log", "LogToFile", "Log to file", "bool", None,
         "Writes OptiScaler.log next to the game. Turn it on before reporting "
         "any problem. Costs a little performance."),
    ]),
]


def all_settings():
    """Flattens the catalogue: [(group, section, key, label, kind, extra, help)]"""
    out = []
    for gid, _t, _s, items in GROUPS:
        for sect, key, label, kind, extra, help_ in items:
            out.append((gid, sect, key, label, kind, extra, help_))
    return out


def group_of(section: str, key: str) -> str | None:
    for gid, _t, _s, items in GROUPS:
        for sect, k, *_ in items:
            if sect == section and k == key:
                return gid
    return None


# Settings that exist only inside the in-game overlay. Listed so nobody hunts
# for them here and comes up empty.
OVERLAY_ONLY = [
    ("Reversible proxy",
     "Colour -> Off / Neutwo / Hybrid, in composed or replace form. "
     "\"Hybrid proxy + composed\" is the v0.2.0 recommendation: it keeps the "
     "midtones and recovers the detail crushed in highlights."),
    ("White-point anchoring",
     "Several calibration points, so white holds when the scene's lighting "
     "changes a lot."),
    ("Hold frame",
     "Freezes the frame the model works on, so two settings can be compared "
     "on the same image."),
    ("Apply the model",
     "With a frame held, turns the effect off without stopping the model: the "
     "same frozen frame with and without Neural Rendering."),
]
