# Empaquetado de la submission — `utils/empaquetar_proyecto.py`

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Propósito

Genera `submission.tar.gz` en la **raíz del proyecto**, el paquete que se sube al *PTCG AI Battle Challenge*. Contiene exactamente lo que la competencia necesita para ejecutar el agente:

- `main.py` — el agente.
- `deck.csv` — el mazo (60 Card IDs).
- `cg/` — el simulador de la competencia (código Python + librerías nativas).

Está adaptado del notebook `notebook/empaquetar.ipynb`, convertido en script reproducible.

## Funcionamiento

- **Rutas resueltas desde la ubicación del script**: `SCRIPT_DIR = Path(__file__).resolve().parent` y `PROJECT_ROOT = SCRIPT_DIR.parent` fijan `MAIN_PY`, `DECK_CSV`, `CG_DIR` y `OUTPUT` sin depender del directorio de trabajo — puede ejecutarse desde cualquier sitio.
- **Validación previa**: `main()` falla con `FileNotFoundError` si falta `main.py`, `deck.csv` o la carpeta `cg/`.
- **Exclusión de compilados**: el filtro `_filtro_sin_pycache` descarta cualquier ruta con `__pycache__` y los archivos `.pyc`/`.pyo` al añadir `cg/` al tar.
- **Salida informativa**: al terminar imprime las rutas empaquetadas, el tamaño del `submission.tar.gz` y, releyendo el tar, el **contenido completo** con el tamaño de cada archivo — verificación rápida de que el paquete está bien formado.

## Uso

```bash
python utils/empaquetar_proyecto.py
```

El resultado es `submission.tar.gz` en la raíz del proyecto. Ese archivo está en `.gitignore` (`/submission.tar.gz`): es un artefacto generado, no se versiona.

## Relación con el resto del proyecto

- El contenido del paquete es lo mismo que evalúa la suite de pruebas local (`main.py` + `cg/`), así que un `pytest` verde antes de empaquetar es la mejor garantía.
- Si el mazo cambia (`deck.csv`), conviene regenerar también la imagen del mazo con [`deck/render_deck_image.py`](deck-render-deck-image.md).
