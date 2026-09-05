# Avisos de terceros

La licencia [MIT](LICENSE) de este repositorio cubre **solo el código que hay
aquí**.

No cubre el software que la herramienta descarga en tiempo de ejecución. Ese
software conserva su propia licencia y **nunca se redistribuye en este
repositorio**: se baja de sus propios releases oficiales cuando pulsas Aplicar.

| Componente | Licencia | Cómo se usa |
|---|---|---|
| [OptiScaler](https://github.com/optiscaler/OptiScaler) (cdozdil / Nitec) | GPL-3.0 | Se descarga su release. Este proyecto no incluye su código ni enlaza contra sus binarios: solo copia los archivos publicados y escribe su archivo `.ini` |
| [OptiScaler_DLSSNR](https://github.com/Dagherbou/OptiScaler_DLSSNR) (dag) | GPL-3.0 | Igual que el anterior. Es el fork que añade el paso de Neural Rendering |
| [RenoDX](https://github.com/clshortfuse/renodx) (clshortfuse) | MIT | Su composición de color la usa el fork internamente, no este código |
| `nvngx_dlssnr.dll` y demás librerías NGX | Propietaria — NVIDIA | **Nunca se descargan ni se redistribuyen.** La herramienta solo copia archivos que ya están en tu máquina, procedentes de un juego que los instaló o de tu driver |

## Sobre el modelo de NVIDIA

`nvngx_dlssnr.dll` es propiedad de NVIDIA. Este proyecto:

- **no** lo incluye en el repositorio,
- **no** lo descarga de internet,
- **no** lo obtiene de repositorios de terceros que lo reempaquetan,
- solo lo **copia** desde una ubicación de tu propio disco a la carpeta del
  juego donde lo necesitas.

Si no tienes una copia legítima en tu máquina, la herramienta te lo dice y no
hace nada más.

## Sin afiliación

Este proyecto no está afiliado, patrocinado ni respaldado por NVIDIA
Corporation, por el equipo de OptiScaler, ni por ninguno de los autores citados.
Todas las marcas pertenecen a sus respectivos propietarios.
