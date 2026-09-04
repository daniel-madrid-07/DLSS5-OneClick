# DLSS 5 One-Click

Detecta qué juegos de tu PC admiten **DLSS 5 Neural Rendering**, lo instala en
uno o dos clics y sabe deshacerlo entero.

```
DLSS5.bat        (o:  python dlss5.py)
```

Solo necesita Python 3.10+. No usa `pip` ni descarga nada hasta que tú le das a
aplicar.

---

## Qué es DLSS 5 y qué no es

DLSS 5 salió el **3 de septiembre de 2026** y no es un upscaler. Es
*3D-Guided Neural Rendering*: un modelo de difusión que reescribe la
iluminación y los materiales del fotograma ya renderizado. DLSS 4.5 sigue
encargándose de Super Resolution, Ray Reconstruction y Multi Frame Generation;
DLSS 5 es una capa aparte que se suma.

**No se puede aplicar a cualquier juego, y conviene saber por qué.** El modelo
necesita saber dónde está cada cosa en la escena. En la integración oficial de
NVIDIA eso llega por Streamline: color, motion vectors, albedo, normales y los
buffers de iluminación. Un juego que no entrega esos datos no tiene nada que
darle al modelo.

El atajo que usa esta herramienta —el fork de OptiScaler— no busca esos buffers
en el motor: **intercepta los que el juego ya le pasa a DLSS cada fotograma**
(depth y motion vectors). Por eso funciona en cualquier título con DLSS sin
trabajo por juego, y por eso no hace absolutamente nada en un juego sin DLSS.
Con menos guías que la integración oficial, el resultado tampoco es idéntico.

## Requisitos reales

| | |
|---|---|
| GPU | **RTX 50** (Blackwell). El modelo no corre en nada anterior |
| Driver | Uno que incluya `nvngx_dlssnr.dll` (~165 MB) |
| Juego | Con **DLSS**, en **DX12** o **DX11**. Vulkan no está implementado |

La herramienta comprueba las tres cosas al arrancar y te dice cuál falta. Si
todavía no tienes el driver con el modelo, puedes instalar todo lo demás y
añadirlo después: el aviso te lo recuerda.

## Los cuatro niveles

Al analizar tu biblioteca cada juego cae en uno:

- **Sí** — tiene DLSS nativo sobre DirectX. Neural Rendering se aplica.
- **Parcial** — tiene FSR o XeSS pero no DLSS. OptiScaler puede inyectar DLSS,
  aunque hay que aportar `nvngx_dlss.dll` y el paso neuronal puede no arrancar.
- **Solo upscaler** — Vulkan. Se puede cambiar el upscaler, pero NR no existe ahí.
- **No** — sin upscaler temporal. No hay depth ni motion vectors que
  interceptar. No hay truco que valga.

## Qué hace al aplicar

1. Descarga el release oficial (se cachea en `%LOCALAPPDATA%\DLSS5`).
2. Copia los archivos junto al ejecutable **real** del juego — que no siempre
   está en la raíz: Cyberpunk lo tiene en `bin\x64` y los Unreal en
   `<Juego>\Binaries\Win64`.
3. Renombra `OptiScaler.dll` a un nombre libre que el juego cargue solo
   (`dxgi.dll`, y si está ocupado el siguiente que quede libre).
4. Escribe la sección `[DlssNr]` del INI con el ajuste elegido, respetando los
   comentarios del archivo.
5. Copia el modelo `nvngx_dlssnr.dll` desde tu driver, si lo encuentra.
6. Actualiza los `nvngx_dlss*.dll` del juego si tienes una versión más nueva en
   otro sitio del PC. No descarga DLL de NVIDIA de ningún sitio raro: usa los
   que ya tienes.

Todo lo que sobrescribe va antes a `_DLSS5_backup\`, con un manifiesto.
**Revertir** deja la carpeta byte a byte como estaba; hay una prueba que lo
verifica (`python pruebas.py`).

Dentro del juego, **Insert** abre el overlay de OptiScaler.

## Ajustes

Salen de los controles reales del fork:

| Ajuste | Para qué |
|---|---|
| Suave | Respeta el arte original. Solo la luz lleva la opinión del modelo |
| Equilibrado | El recomendado |
| Máximo detalle | Empuja más allá de lo que el modelo pide. Se nota |
| Rendimiento | El modelo trabaja a media resolución. El coste cae al cuadrado |

Si quieres ver si el paso hace algo, pon `DebugView=3` en el INI: un gris plano
significa que no está tocando nada.

## Anticheat

Si detecta EAC, BattlEye, Vanguard o Denuvo AC, avisa y pide confirmación.
Poner un DLL junto al ejecutable es justo lo que esos sistemas buscan. En
multijugador competitivo puede acabar en baneo de cuenta. Fortnite y Apex
aparecen marcados por esto.

## Aviso sobre repositorios falsos

Hay repos que prometen "DLSS 5 en cualquier juego, incluido D3D9 y Vulkan".
Es imposible: un juego de D3D9 no tiene motion vectors que dar. El que circulaba
al escribir esto tenía dos días de vida, cuatro estrellas, 677 MB de binarios
opacos y falsificaba los buffers con shaders de ReShade. El propio equipo de
OptiScaler avisa de webs y "manager apps" falsas: sus únicos sitios legítimos
son su GitHub, su Discord y la página de Nitec en NexusMods.

Esta herramienta solo descarga de los repos oficiales listados en
`SOURCES` (`dlss5_apply.py`) y guarda el SHA-256 de todo lo que baja.

## Archivos

| | |
|---|---|
| `dlss5.py` | Interfaz |
| `dlss5_scan.py` | Detección: PE, motor, API, upscalers, GPU, anticheat |
| `dlss5_apply.py` | Descarga, instalación, INI y marcha atrás |
| `pruebas.py` | Comprueba que revertir no deja rastro |

## Créditos

El trabajo duro no es mío:

- **[OptiScaler](https://github.com/optiscaler/OptiScaler)** (cdozdil / Nitec),
  GPL-3.0 — el hook de DirectX y todo el puente entre upscalers.
- **[OptiScaler_DLSSNR](https://github.com/Dagherbou/OptiScaler_DLSSNR)** (dag) —
  el paso de Neural Rendering.
- **[RenoDX](https://github.com/clshortfuse/renodx)** (clshortfuse), MIT — la
  composición de color que hace que el resultado no se rompa.

Esta herramienta es un frontend: detecta, decide, configura y sabe deshacerlo.
