"""
Tests for the dangerous part: install and revert must leave the folder identical.

Builds a fake game with a file that will be overwritten, installs on top,
verifies the result and reverts. If a single byte changes, it fails.

    python tests.py
"""

import os
import sys
import shutil
import hashlib
import tempfile

import dlss5_scan as scan
import dlss5_apply as apply_mod
import dlss5_model as model_mod
import dlss5_opts as opts

OK, FAIL = [], []


def check(name: str, cond: bool, detail: str = ""):
    (OK if cond else FAIL).append(name)
    mark = "  ok  " if cond else " FAIL "
    print(f"[{mark}] {name}" + (f"   -> {detail}" if detail and not cond else ""))


def hash_tree(root: str) -> dict:
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            h = hashlib.sha256()
            with open(full, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            out[rel] = h.hexdigest()
    return out


def build_fake_game(base: str) -> str:
    """A plausible game: real executable, DLSS present, and a pre-existing
    OptiScaler.ini that install must back up and revert must restore."""
    root = os.path.join(base, "FakeGame")
    os.makedirs(root, exist_ok=True)

    shutil.copy2(r"C:\Windows\System32\notepad.exe",
                 os.path.join(root, "FakeGame.exe"))
    # Any nvngx_dlss.dll will do: only the file name is checked.
    shutil.copy2(r"C:\Windows\System32\d3d12.dll",
                 os.path.join(root, "nvngx_dlss.dll"))
    # dxgi.dll taken -> the proxy must pick another name.
    shutil.copy2(r"C:\Windows\System32\version.dll",
                 os.path.join(root, "dxgi.dll"))
    with open(os.path.join(root, "OptiScaler.ini"), "w", encoding="utf-8") as f:
        f.write("; user previous ini, must not be lost\n[Menu]\nScale=1.5\n")
    return root


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="dlss5_test_")
    print(f"Test folder: {tmp}\n")
    try:
        root = build_fake_game(tmp)
        before = hash_tree(root)
        print(f"Fake game with {len(before)} files.\n")

        # --- detection ---------------------------------------------------
        g = scan.analyze(root, "Fake Game")
        check("finds the executable", os.path.basename(g.exe or "") == "FakeGame.exe",
              str(g.exe))
        check("detects DLSS", "dlss" in g.upscalers, str(g.upscalers))
        check("tier A", g.tier == "A", f"{g.tier}: {g.verdict}")

        # --- proxy choice -------------------------------------------
        proxy = apply_mod.pick_proxy(g.exe_dir)
        check("avoids the taken dxgi.dll", proxy != "dxgi.dll", proxy)

        # --- install --------------------------------------------------
        print("\nInstalling (uses the cache if already downloaded)...")
        manifest = apply_mod.install(g, preset="balanced", kind="dlssnr",
                                     neural=True, copy_model=True,
                                     log=lambda m: print("   " + str(m)))

        after_install = hash_tree(root)
        check("OptiScaler placed as proxy",
              os.path.isfile(os.path.join(root, manifest["proxy"])), manifest["proxy"])
        check("nvngx.dll_dlssnr.dll copied",
              os.path.isfile(os.path.join(root, "nvngx.dll_dlssnr.dll")))
        check("binaries in the OptiScaler subfolder",
              os.path.isdir(os.path.join(root, "OptiScaler")))
        check("manifest written", apply_mod.read_manifest(root) is not None)
        check("the previous ini was backed up",
              "OptiScaler.ini" in manifest["respaldados"],
              str(list(manifest["respaldados"])))

        # --- ini contents -------------------------------------------
        ini = os.path.join(root, "OptiScaler.ini")
        with open(ini, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        sec = text.split("[DlssNr]", 1)[-1]
        check("[DlssNr] Enabled=true", "\nEnabled=true" in sec)
        check("[DlssNr] TransferStrength=1.0", "\nTransferStrength=1.0" in sec)
        check("[DlssNr] WorkingScale=1.0", "\nWorkingScale=1.0" in sec)
        check("no duplicated keys",
              sec.count("\nEnabled=") == 1, str(sec.count("\nEnabled=")))
        check("the ini comments survive",
              "; DLSS 5 Neural Rendering" in text)

        check("[DlssNr] ToggleKey written (F10)", "\nToggleKey=0x79" in sec)

        # --- re-analysis ---------------------------------------------------
        g2 = scan.analyze(root, "Fake Game")
        check("recognises its own install", g2.installed_proxy is not None,
              str(g2.installed_proxy))

        # --- v0.2.0 classification -----------------------------------------
        # NR no longer requires DLSS or DirectX. A Vulkan-only game with FSR
        # must come out applicable, not discarded.
        vk = scan.Game(name="vk", root=root, exe="x", exe_dir=root,
                       apis={"vulkan"}, upscalers={"fsr": "FSR"})
        scan._classify(vk)
        check("Vulkan + FSR is applicable (v0.2.0)", vk.tier == "B",
              f"{vk.tier}: {vk.verdict}")

        xess = scan.Game(name="xe", root=root, exe="x", exe_dir=root,
                         apis={"dx12"}, upscalers={"xess": "XeSS"})
        scan._classify(xess)
        check("XeSS without DLSS is applicable", xess.tier == "B",
              f"{xess.tier}: {xess.verdict}")

        nada = scan.Game(name="n", root=root, exe="x", exe_dir=root,
                         apis={"dx12"}, upscalers={})
        scan._classify(nada)
        check("no upscaler is still a no", nada.tier == "D", nada.tier)

        # the output upscaler is no longer forced on FSR/XeSS games
        cfg = apply_mod.build_config(xess, "balanced", neural=True)
        check("Dx12Upscaler is not forced", "Upscalers" not in cfg,
              str(cfg.get("Upscalers")))

        # --- model --------------------------------------------------------
        check("supersampling preset exists",
              "supersampling" in apply_mod.PRESETS)
        ss = apply_mod.PRESETS["supersampling"]["DlssNr"]
        check("supersampling asks for WorkingScale > 1",
              float(ss["WorkingScale"]) > 1.0, ss["WorkingScale"])
        check("supersampling sets the downscaler",
              ss.get("ScalingDownscaler") == "4", str(ss.get("ScalingDownscaler")))
        check("looks for the model in games, not only the driver",
              callable(getattr(model_mod, "find_in_games", None)))

        # The new-user flow: drop the DLL next to the program and done.
        # app_dir() must be the .exe folder, not the temporary directory
        # PyInstaller unpacks into.
        check("app_dir points at a real folder",
              os.path.isdir(model_mod.app_dir()), model_mod.app_dir())
        # Actually verified: a model-sized file placed in a folder passed as an
        # extra root must be found.
        # Sparse file: claims the size without writing 100 MB. Deliberately made
        # LARGER than any real copy on this machine, because find_existing
        # keeps the biggest one.
        falso = os.path.join(root, "nvngx_dlssnr.dll")
        grande = 400 << 20
        with open(falso, "wb") as f:
            f.seek(grande - 1)
            f.write(b"\0")
        hallado = model_mod.find_existing(extra_roots=[root])
        check("finds a model dropped in a folder",
              hallado["path"] and os.path.normcase(hallado["path"])
              == os.path.normcase(falso), str(hallado["path"]))
        os.remove(falso)

        # And one below the minimum must not pass as the model.
        pequeno = os.path.join(root, "nvngx_dlssnr.dll")
        with open(pequeno, "wb") as f:
            f.write(b"\0" * 1024)
        tras = model_mod.find_existing(extra_roots=[root])
        check("rejects files too small to be the model",
              os.path.normcase(str(tras["path"])) != os.path.normcase(pequeno),
              str(tras["path"]))
        os.remove(pequeno)
        check("the help says dropping it alongside is enough",
              "junto al programa" in model_mod.help_text("616.64"))
        check("the help does not send you after the driver",
              "NO viene en el driver" in model_mod.help_text("616.64"))
        check("the help names the games that do ship it",
              "NBA 2K27" in model_mod.help_text("616.64"))
        # Onimusha and Dawnwalker appear in the NVIDIA announcement but only
        # carry DLSS 4.5. Sending someone to install them wastes 100 GB.
        check("Onimusha is NOT listed as a model source",
              not any("onimusha" in g.lower() for g in model_mod.SHIPPING_GAMES),
              str(model_mod.SHIPPING_GAMES))
        check("Onimusha is flagged as not carrying it",
              any("Onimusha" in k for k in model_mod.NOT_SHIPPING))
        check("the help says you can install without the model",
              "sin el modelo" in model_mod.help_text("616.64"))
        check("driver 616.64 is accepted", model_mod.driver_ok("616.64") is True)
        check("driver 580.00 is rejected", model_mod.driver_ok("580.00") is False)
        check("unknown driver does not lie", model_mod.driver_ok(None) is None)
        check("find_existing ignores small DLLs",
              model_mod.find_existing()["path"] is None
              or os.path.getsize(model_mod.find_existing()["path"])
              >= model_mod.MIN_MODEL_MB << 20)

        # --- settings editor ---------------------------------------------
        # Every catalogue key must actually exist in the INI. An invented key
        # writes without error and does nothing: exactly the Log.LoggingEnabled
        # bug.
        ini_data = apply_mod.read_ini(ini)
        inventadas = [f"{s}.{k}" for _g, s, k, _l, _t, _e, _h
                      in opts.all_settings()
                      if k not in ini_data.get(s, {})]
        check("no catalogue setting is invented", not inventadas,
              str(inventadas))

        check("read_ini reads every section", len(ini_data) >= 38,
              str(len(ini_data)))

        # Writing from the editor must not grow or duplicate the file.
        antes = open(ini, encoding="utf-8", errors="replace").read()
        apply_mod.set_ini(ini, {"DlssNr": {"ColourStrength": "0.80"},
                                "CAS": {"Enabled": "true"}})
        despues = open(ini, encoding="utf-8", errors="replace").read()
        check("editing does not change the line count",
              antes.count("\n") == despues.count("\n"),
              f"{antes.count(chr(10))} -> {despues.count(chr(10))}")
        vuelto = apply_mod.read_ini(ini)
        check("the edited value reads back the same",
              vuelto["DlssNr"]["ColourStrength"] == "0.80",
              vuelto["DlssNr"].get("ColourStrength"))
        check("editing one section leaves another alone",
              vuelto["CAS"]["Enabled"] == "true")
        check("no keys duplicated when editing",
              despues.count("\nColourStrength=") == 1,
              str(despues.count("\nColourStrength=")))

        # The editor must not invent changes merely by drawing itself:
        # ttk.Scale.set() fires its callback on construction, and without a
        # guard that turns every auto into the slider minimum on save.
        try:
            import tkinter as tk
            import dlss5_editor as editor_mod

            r = tk.Tk()
            r.withdraw()
            ed = editor_mod.Editor(r, g)
            ed.open_groups = {gid for gid, _t, _s, _i in opts.GROUPS}
            ed._render()
            ed.update()
            ed.update_idletasks()

            check("opening the editor marks no false changes",
                  not ed._collect(), str(ed._collect())[:120])

            ed.vars[("DlssNr", "ColourStrength")].set("0.75")
            solo = ed._collect()
            check("one change counts as one",
                  sum(len(v) for v in solo.values()) == 1, str(solo))
            check("the editor exposes every catalogue setting",
                  len(ed.vars) == len(opts.all_settings()),
                  f"{len(ed.vars)} vs {len(opts.all_settings())}")
            ed.destroy()
            r.destroy()
        except tk.TclError as e:                     # no desktop available
            print(f"[ note ] editor not tested: {e}")

        # --- DLSS DLL upgrade must be undoable ------------------------
        # Found the hard way: upgrade_dlss_dll copied the old DLL into the
        # backup folder but never recorded it in the manifest. revert() walks
        # the manifest, not the folder, so the old DLL was left behind and then
        # wiped along with the backup directory. "Reverts byte-for-byte" was
        # simply false whenever the upgrade ran.
        game_dll = os.path.join(root, "nvngx_dlss.dll")
        original = hash_tree(root)[os.path.relpath(game_dll, root)]

        newer = os.path.join(tmp, "newer_dlss.dll")
        shutil.copy2(r"C:\Windows\System32\kernel32.dll", newer)
        upgraded = apply_mod.upgrade_dlss_dll(
            g, {"nvngx_dlss.dll": (newer, "999.0.0.0")}, log=lambda m: None)
        check("a newer DLSS DLL is actually installed", upgraded)

        after = apply_mod.read_manifest(root) or {}
        check("the upgraded DLL is recorded in the manifest",
              "nvngx_dlss.dll" in after.get("respaldados", {}),
              str(list(after.get("respaldados", {}))))
        check("the game DLL really changed",
              hash_tree(root)[os.path.relpath(game_dll, root)] != original)

        # --- revert --------------------------------------------------
        print("\nReverting...")
        apply_mod.revert(root, log=lambda m: print("   " + str(m)))
        after_revert = hash_tree(root)

        missing = sorted(set(before) - set(after_revert))
        extra = sorted(set(after_revert) - set(before))
        changed = sorted(k for k in before
                         if k in after_revert and before[k] != after_revert[k])

        check("no original file is missing", not missing, str(missing[:5]))
        check("no leftover file remains", not extra, str(extra[:5]))
        check("no original file was altered", not changed, str(changed[:5]))
        check("the folder returns to its exact state",
              before == after_revert,
              f"{len(missing)} missing, {len(extra)} extra, {len(changed)} changed")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{len(OK)} passed, {len(FAIL)} failed")
    if FAIL:
        print("Failures: " + ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
