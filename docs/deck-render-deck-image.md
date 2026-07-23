# Imagen del mazo — `deck/render_deck_image.py`

> Documento descriptivo: se refiere al código por nombres de funciones y constantes, no por líneas.

## Propósito

Genera `deck/deck_en.jpg`: una imagen del mazo actual (en inglés) a partir del `deck.csv` de la raíz del proyecto, usando los datos oficiales del challenge (`EN_Card_Data.csv` y `Card_ID List_EN.pdf`). Útil para revisar de un vistazo la composición del mazo tras cada cambio. Está adaptado del notebook `notebook/deck-image-renderer-visualize-your-ptcg-deck.ipynb`.

## Datos de entrada

- `deck.csv` (raíz del proyecto): 60 Card IDs, uno por línea (`read_deck_ids` valida que sean exactamente 60).
- `EN_Card_Data.csv` y `Card_ID List_EN.pdf`: los datos oficiales del challenge. `_first_existing` los busca en **este orden**: `deck/`, `dataset/`, y la carpeta original del challenge (`/Users/jcoronel/Desktop/Pokemon TCG AI/pokemon-tcg-ai-battle`); falla con `FileNotFoundError` si no aparecen en ninguna.

## Funcionamiento

1. **Conteo ordenado**: `ordered_deck_counts` cuenta las copias de cada ID preservando el orden de primera aparición en el `deck.csv`.
2. **Mapeo Card ID → página del PDF**: `load_unique_card_order` lee el CSV de cartas con pandas (tiene campos multilínea entre comillas: nunca `splitlines`) y extrae los IDs únicos en orden de primera aparición. `build_card_id_to_pdf_page_index` aplica la regla `PDF_CARD_START_PAGE = 40`: la **página 40** (1-indexada) del PDF corresponde a la **primera carta única** del CSV de cartas, y las siguientes van en el mismo orden.
3. **Recorte de carta por página**: `render_pdf_page_to_image` renderiza la página con **pymupdf** (`fitz`) a zoom 4× (`PAGE_RENDER_ZOOM`), y `crop_card_from_page_image` detecta la carta sobre el fondo blanco (umbral de "oscuridad" por filas/columnas, con recorte de respaldo si la detección falla) y ajusta el recorte a la proporción de una carta Pokémon.
4. **Composición**: `make_labeled_card_tile` superpone a cada carta una etiqueta translúcida centrada abajo con el texto `×N  ID:###` (copias e ID), y `render_deck_grid` compone la cuadrícula de **8 columnas** (`GRID_COLUMNS`) sobre fondo negro.
5. **Compresión**: `save_jpeg_under_size` guarda el JPEG bajando calidad (88→45 en pasos de 5) y, si no basta, reduciendo el tamaño de la imagen, hasta quedar por debajo de **1 MB** (`MAX_OUTPUT_BYTES`).

Durante la ejecución imprime el mapeo completo (copias, ID, página del PDF y nombre de carta) y, al final, la ruta, dimensiones, calidad JPEG y bytes del archivo generado.

## Uso

```bash
python deck/render_deck_image.py
```

**Requisitos**: `pymupdf`, `pandas`, `numpy`, `Pillow`. Ojo con el intérprete: el Python de **anaconda** tiene `pymupdf` instalado; el `.venv` del proyecto **no**. Ejecutarlo con el intérprete de anaconda (o instalar `pymupdf` en el entorno elegido).

## Notas

- La salida `deck/deck_en.jpg` se versiona como referencia visual del mazo actual; regenerarla tras cualquier cambio en `deck.csv`.
- `dataset/Card_ID List_EN.pdf` está en `.gitignore` (el PDF oficial no se versiona); por eso el script acepta encontrarlo también en la carpeta original del challenge.
