"""
Pruebas de la parte peligrosa: que instalar y revertir deje la carpeta igual.

Monta un juego falso con un archivo que va a ser sobrescrito, instala encima,
comprueba el resultado y revierte. Si un solo byte cambia, falla.

    python pruebas.py
"""

import os
import sys
import shutil
import hashlib
import tempfile

import dlss5_scan as scan
import dlss5_apply as apply_mod
import dlss5_model as model_mod

OK, FAIL = [], []


def check(name: str, cond: bool, detail: str = ""):
    (OK if cond else FAIL).append(name)
    mark = "  ok  " if cond else " FALLO"
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
    """Un juego plausible: ejecutable real, DLSS presente, y un OptiScaler.ini
    previo que la instalacion debera respaldar y la marcha atras restaurar."""
    root = os.path.join(base, "JuegoFalso")
    os.makedirs(root, exist_ok=True)

    shutil.copy2(r"C:\Windows\System32\notepad.exe",
                 os.path.join(root, "JuegoFalso.exe"))
    # Un nvngx_dlss.dll cualquiera basta: solo se comprueba el nombre.
    shutil.copy2(r"C:\Windows\System32\d3d12.dll",
                 os.path.join(root, "nvngx_dlss.dll"))
    # dxgi.dll ocupado -> el proxy debe elegir otro nombre.
    shutil.copy2(r"C:\Windows\System32\version.dll",
                 os.path.join(root, "dxgi.dll"))
    with open(os.path.join(root, "OptiScaler.ini"), "w", encoding="utf-8") as f:
        f.write("; ini previo del usuario, no debe perderse\n[Menu]\nScale=1.5\n")
    return root


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="dlss5_test_")
    print(f"Carpeta de pruebas: {tmp}\n")
    try:
        root = build_fake_game(tmp)
        before = hash_tree(root)
        print(f"Juego falso con {len(before)} archivos.\n")

        # --- deteccion ---------------------------------------------------
        g = scan.analyze(root, "Juego Falso")
        check("detecta el ejecutable", os.path.basename(g.exe or "") == "JuegoFalso.exe",
              str(g.exe))
        check("detecta DLSS", "dlss" in g.upscalers, str(g.upscalers))
        check("nivel A", g.tier == "A", f"{g.tier}: {g.verdict}")

        # --- eleccion de proxy -------------------------------------------
        proxy = apply_mod.pick_proxy(g.exe_dir)
        check("evita el dxgi.dll ocupado", proxy != "dxgi.dll", proxy)

        # --- instalacion --------------------------------------------------
        print("\nInstalando (usa la cache si el paquete ya esta bajado)...")
        manifest = apply_mod.install(g, preset="equilibrado", kind="dlssnr",
                                     neural=True, copy_model=True,
                                     log=lambda m: print("   " + str(m)))

        after_install = hash_tree(root)
        check("OptiScaler colocado como proxy",
              os.path.isfile(os.path.join(root, manifest["proxy"])), manifest["proxy"])
        check("nvngx.dll_dlssnr.dll copiado",
              os.path.isfile(os.path.join(root, "nvngx.dll_dlssnr.dll")))
        check("binarios en la subcarpeta OptiScaler",
              os.path.isdir(os.path.join(root, "OptiScaler")))
        check("manifiesto escrito", apply_mod.read_manifest(root) is not None)
        check("el ini previo quedo respaldado",
              "OptiScaler.ini" in manifest["respaldados"],
              str(list(manifest["respaldados"])))

        # --- contenido del ini -------------------------------------------
        ini = os.path.join(root, "OptiScaler.ini")
        with open(ini, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        sec = text.split("[DlssNr]", 1)[-1]
        check("[DlssNr] Enabled=true", "\nEnabled=true" in sec)
        check("[DlssNr] TransferStrength=1.0", "\nTransferStrength=1.0" in sec)
        check("[DlssNr] WorkingScale=1.0", "\nWorkingScale=1.0" in sec)
        check("no quedan claves duplicadas",
              sec.count("\nEnabled=") == 1, str(sec.count("\nEnabled=")))
        check("los comentarios del ini sobreviven",
              "; DLSS 5 Neural Rendering" in text)

        check("[DlssNr] ToggleKey escrito (F10)", "\nToggleKey=0x79" in sec)

        # --- reanalisis ---------------------------------------------------
        g2 = scan.analyze(root, "Juego Falso")
        check("reconoce su propia instalacion", g2.installed_proxy is not None,
              str(g2.installed_proxy))

        # --- clasificacion v0.2.0 -----------------------------------------
        # NR ya no exige DLSS ni DirectX. Un juego solo-Vulkan con FSR debe
        # quedar como aplicable, no descartado.
        vk = scan.Game(name="vk", root=root, exe="x", exe_dir=root,
                       apis={"vulkan"}, upscalers={"fsr": "FSR"})
        scan._classify(vk)
        check("Vulkan + FSR es aplicable (v0.2.0)", vk.tier == "B",
              f"{vk.tier}: {vk.verdict}")

        xess = scan.Game(name="xe", root=root, exe="x", exe_dir=root,
                         apis={"dx12"}, upscalers={"xess": "XeSS"})
        scan._classify(xess)
        check("XeSS sin DLSS es aplicable", xess.tier == "B",
              f"{xess.tier}: {xess.verdict}")

        nada = scan.Game(name="n", root=root, exe="x", exe_dir=root,
                         apis={"dx12"}, upscalers={})
        scan._classify(nada)
        check("sin upscaler sigue siendo no", nada.tier == "D", nada.tier)

        # ya no se fuerza el upscaler de salida en juegos FSR/XeSS
        cfg = apply_mod.build_config(xess, "equilibrado", neural=True)
        check("no se fuerza Dx12Upscaler", "Upscalers" not in cfg,
              str(cfg.get("Upscalers")))

        # --- modelo --------------------------------------------------------
        check("preset de supersampling existe",
              "supersampling" in apply_mod.PRESETS)
        ss = apply_mod.PRESETS["supersampling"]["DlssNr"]
        check("supersampling pide WorkingScale > 1",
              float(ss["WorkingScale"]) > 1.0, ss["WorkingScale"])
        check("supersampling fija el downscaler",
              ss.get("ScalingDownscaler") == "4", str(ss.get("ScalingDownscaler")))
        check("driver 616.64 se acepta", model_mod.driver_ok("616.64") is True)
        check("driver 580.00 se rechaza", model_mod.driver_ok("580.00") is False)
        check("driver desconocido no miente", model_mod.driver_ok(None) is None)
        check("find_existing ignora DLL pequenos",
              model_mod.find_existing()["path"] is None
              or os.path.getsize(model_mod.find_existing()["path"])
              >= model_mod.MIN_MODEL_MB << 20)

        # --- marcha atras --------------------------------------------------
        print("\nRevirtiendo...")
        apply_mod.revert(root, log=lambda m: print("   " + str(m)))
        after_revert = hash_tree(root)

        missing = sorted(set(before) - set(after_revert))
        extra = sorted(set(after_revert) - set(before))
        changed = sorted(k for k in before
                         if k in after_revert and before[k] != after_revert[k])

        check("no falta ningun archivo original", not missing, str(missing[:5]))
        check("no queda ningun archivo de sobra", not extra, str(extra[:5]))
        check("ningun archivo original quedo alterado", not changed, str(changed[:5]))
        check("la carpeta vuelve a su estado exacto",
              before == after_revert,
              f"{len(missing)} faltan, {len(extra)} sobran, {len(changed)} cambiados")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{len(OK)} correctas, {len(FAIL)} fallidas")
    if FAIL:
        print("Fallos: " + ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
