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
en el motor: **intercepta los que el juego ya le pasa a su upscaler cada
fotograma** (depth y motion vectors). Por eso funciona en cualquier título con
upscaler sin trabajo por juego, y por eso no hace absolutamente nada en un juego
que no tenga ninguno. Con menos guías que la integración oficial, el resultado
tampoco es idéntico.

Desde **v0.2.0** (3 sept 2026) el paso ya no exige DLSS: se engancha igual a FSR
y a XeSS, y Vulkan pasó a estar soportado de forma nativa.

## Requisitos reales

| | |
|---|---|
| GPU | **RTX 50** (Blackwell). En RTX 20/30/40 hace falta un DLL modificado |
| Driver | **616.56** o superior |
| Modelo | `nvngx_dlssnr.dll` (~165 MB) — ver abajo, es la parte que atasca |
| Juego | Con **cualquier upscaler temporal** (DLSS, FSR o XeSS). DX11, DX12 y Vulkan |

### El modelo es el problema, y no está en el driver

Puedes tener el 616.64 instalado y no encontrar `nvngx_dlssnr.dll` por ningún
lado. **No viene en el driver.**

Verificado el 5/9/2026 descargando el instalador oficial 616.64 (938 MB desde
`us.download.nvidia.com`) y abriéndolo: sus únicos `nvngx_*` son `nvngx.dll`,
`nvngx_dlssg.dll`, `nvngx_dlisr.dll` y `nvngx_update.exe`. Ni rastro de
`dlssnr`. Tampoco hay interruptor en la NVIDIA App — NVIDIA confirmó que no
habría override por juego.

**El modelo lo distribuye cada juego que implementa DLSS 5.** Se descubrió
dentro de NBA 2K27 (158 MB, se identifica como "NVIDIA DLSSNR" v310.8.0.0). Hoy
lo traen NBA 2K27, Onimusha: Way of the Sword y The Blood of Dawnwalker.

Por eso el botón **Buscar modelo** mira, por este orden: la caché, tus juegos
instalados, y solo después cualquier instalador de driver que tengas suelto.
Basta con tener uno de esos juegos instalado — no hay que jugarlo. El DLL se
copia a la caché y de ahí a todos los demás juegos.

El programa nunca descarga el modelo de repositorios de terceros. Es de NVIDIA,
y los sitios que lo reempaquetan son justo los que conviene evitar.

## Los niveles

- **Sí (DLSS)** — tiene DLSS. El caso ideal.
- **Sí (FSR/XeSS)** — sin DLSS, pero desde v0.2.0 el paso se engancha igual de
  bien a las entradas de FSR o XeSS.
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
5. Copia el modelo `nvngx_dlssnr.dll` desde la caché (hace falta una copia por
   juego: no existe ubicación compartida).
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
| Supersampling | El modelo corre **por encima** de nativo y se promedia de vuelta con Lanczos3: menos ruido. Caro |
| Rendimiento | El modelo trabaja a media resolución. El coste cae al cuadrado |

**F10** enciende y apaga el paso dentro del juego sin abrir el menú. Es la forma
honesta de comprobar si está haciendo algo — a ojo y en movimiento se
autoengaña uno con facilidad. `DebugView=3` en el INI muestra lo que ha
cambiado amplificado: un gris plano significa que no toca nada.

### Lo que hay que tocar a mano

La mejora grande de v0.2.0 es el **proxy reversible**, y su modo recomendado es
*Hybrid proxy + composed*. No se puede dejar preconfigurado desde aquí porque
**no existe como clave del INI**: vive solo en el overlay. Ábrelo con Insert,
sección Colour, y cámbialo ahí. El anclaje multipunto del punto de blanco y el
"Hold frame" para comparar ajustes tampoco tienen clave; también son de overlay.

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
| `dlss5_model.py` | Conseguir `nvngx_dlssnr.dll` del instalador del driver |
| `pruebas.py` | 31 comprobaciones, incluida la de que revertir no deja rastro |

## Créditos

El trabajo duro no es mío:

- **[OptiScaler](https://github.com/optiscaler/OptiScaler)** (cdozdil / Nitec),
  GPL-3.0 — el hook de DirectX y todo el puente entre upscalers.
- **[OptiScaler_DLSSNR](https://github.com/Dagherbou/OptiScaler_DLSSNR)** (dag) —
  el paso de Neural Rendering.
- **[RenoDX](https://github.com/clshortfuse/renodx)** (clshortfuse), MIT — la
  composición de color que hace que el resultado no se rompa.

Esta herramienta es un frontend: detecta, decide, configura y sabe deshacerlo.
