"""Generates the deck image (in English) from the project's deck.csv.

Adapted from the notebook `notebook/deck-image-renderer-visualize-your-ptcg-deck.ipynb`:
it reads the deck.csv at the project root (60 Card IDs, one per line), maps each
ID to its page in the official PDF (page 40 of the PDF corresponds to the first
unique card of the card CSV), crops the card from each page, composes a
grid with an "xN  ID:###" label per card and saves a compressed JPG
(<1MB) in this folder.

Usage:
    python deck/render_deck_image.py

Requires: pymupdf, pandas, numpy, Pillow.
"""

import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DECK_CSV = PROJECT_ROOT / "deck.csv"
OUTPUT_EN = SCRIPT_DIR / "deck_en.jpg"


def _first_existing(candidates, label):
    for p in candidates:
        if Path(p).exists():
            return Path(p)
    raise FileNotFoundError(
        f"{label} no encontrado. Buscado en: " + ", ".join(str(c) for c in candidates))


# The challenge's official data: it is looked for in deck/, dataset/ and the
# competition's original folder, in that order.
_DATA_DIRS = [
    SCRIPT_DIR,
    PROJECT_ROOT / "dataset",
    Path("/Users/jcoronel/Desktop/Pokemon TCG AI/pokemon-tcg-ai-battle"),
]
CARD_CSV_EN = _first_existing(
    [d / "EN_Card_Data.csv" for d in _DATA_DIRS], "EN_Card_Data.csv")
CARD_PDF_EN = _first_existing(
    [d / "Card_ID List_EN.pdf" for d in _DATA_DIRS], "Card_ID List_EN.pdf")

# Page 40 (1-indexed) of the PDF is the first unique card of the CSV.
PDF_CARD_START_PAGE = 40

GRID_COLUMNS = 8
CARD_DISPLAY_WIDTH = 320
GRID_GAP = 8
GRID_PADDING = 0
LABEL_ALPHA = 180
PAGE_RENDER_ZOOM = 4.0

MAX_OUTPUT_BYTES = 1_000_000
JPEG_START_QUALITY = 88
JPEG_MIN_QUALITY = 45
JPEG_DOWNSCALE_STEP = 0.92
JPEG_MIN_WIDTH = 1200


def read_deck_ids(deck_csv_path):
    deck_csv_path = Path(deck_csv_path)
    if not deck_csv_path.exists():
        raise FileNotFoundError(f"deck.csv no encontrado: {deck_csv_path}")
    with open(deck_csv_path, "r", encoding="utf-8") as f:
        deck_ids = [int(line.strip()) for line in f.read().splitlines() if line.strip()]
    if len(deck_ids) != 60:
        raise ValueError(f"El mazo debe tener exactamente 60 cartas, tiene {len(deck_ids)}.")
    return deck_ids


def ordered_deck_counts(deck_ids):
    """Counts the IDs preserving the order of first appearance."""
    counts = Counter(deck_ids)
    ordered_ids = []
    seen = set()
    for card_id in deck_ids:
        if card_id not in seen:
            ordered_ids.append(card_id)
            seen.add(card_id)
    return ordered_ids, counts


def read_card_data_csv(csv_path):
    """Reads the official card CSV (it has multi-line fields between quotes:
    use pandas, never splitlines)."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV de cartas no encontrado: {csv_path}")
    df = pd.read_csv(csv_path, encoding="utf-8-sig", keep_default_na=False)
    df.columns = [str(c).strip().lstrip("﻿") for c in df.columns]
    if "Card ID" not in df.columns:
        raise ValueError(f"Columna 'Card ID' no encontrada. Columnas: {list(df.columns)}")
    card_id_numeric = pd.to_numeric(df["Card ID"], errors="coerce")
    df = df.loc[card_id_numeric.notna()].copy()
    df["Card ID"] = card_id_numeric.loc[card_id_numeric.notna()].astype(int)
    if "Card Name" not in df.columns:
        df["Card Name"] = ""
    return df


def load_unique_card_order(csv_path):
    """Unique IDs in order of first appearance (the CSV repeats rows per
    attack/effect; the PDF's order follows the unique IDs)."""
    df = read_card_data_csv(csv_path)
    unique_df = df.drop_duplicates(subset=["Card ID"], keep="first").reset_index(drop=True)
    card_id_to_order = {cid: i for i, cid in enumerate(unique_df["Card ID"].tolist())}
    card_names = dict(zip(unique_df["Card ID"], unique_df["Card Name"].astype(str)))
    return card_id_to_order, card_names


def build_card_id_to_pdf_page_index(deck_unique_ids, card_id_to_order,
                                    pdf_card_start_page=PDF_CARD_START_PAGE):
    missing = [cid for cid in deck_unique_ids if cid not in card_id_to_order]
    if missing:
        raise ValueError("IDs del mazo no encontrados en el CSV de cartas: "
                         + ", ".join(map(str, missing)))
    start_page_index = pdf_card_start_page - 1
    return {cid: start_page_index + card_id_to_order[cid] for cid in deck_unique_ids}


def render_pdf_page_to_image(doc, page_index, zoom=PAGE_RENDER_ZOOM):
    import fitz
    if page_index < 0 or page_index >= len(doc):
        raise IndexError(f"Pagina {page_index} fuera de rango (el PDF tiene {len(doc)}).")
    page = doc.load_page(page_index)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def crop_card_from_page_image(page_img, expected_card_aspect=0.714):
    """Crops the card from the page (a white background, the card at the top centre) and
    adjusts the crop to the proportions of a Pokemon card."""
    img = page_img.convert("RGB")
    arr = np.asarray(img)
    h, w = arr.shape[:2]

    x0, x1 = int(w * 0.05), int(w * 0.95)
    y0, y1 = int(h * 0.02), int(h * 0.72)
    roi = arr[y0:y1, x0:x1, :]

    darkness = np.max(255 - roi.astype(np.int16), axis=2)
    mask = darkness > 18
    row_counts = mask.sum(axis=1)
    col_counts = mask.sum(axis=0)

    if row_counts.max() <= 0 or col_counts.max() <= 0:
        left, right = int(w * 0.36), int(w * 0.64)
        top, bottom = int(h * 0.07), int(h * 0.62)
    else:
        row_threshold = max(10, int(row_counts.max() * 0.055))
        col_threshold = max(10, int(col_counts.max() * 0.055))
        ys = np.where(row_counts > row_threshold)[0]
        xs = np.where(col_counts > col_threshold)[0]
        if len(xs) < 10 or len(ys) < 10:
            left, right = int(w * 0.36), int(w * 0.64)
            top, bottom = int(h * 0.07), int(h * 0.62)
        else:
            left = x0 + int(xs.min())
            right = x0 + int(xs.max()) + 1
            top = y0 + int(ys.min())
            bottom = y0 + int(ys.max()) + 1
            pad = max(8, int(max(w, h) * 0.004))
            left, right = max(0, left - pad), min(w, right + pad)
            top, bottom = max(0, top - pad), min(h, bottom + pad)

    box_w, box_h = right - left, bottom - top
    if box_w <= 0 or box_h <= 0:
        raise RuntimeError("Recorte invalido; revisar el mapeo de paginas del PDF.")

    current_aspect = box_w / box_h
    center_x = (left + right) / 2
    if (current_aspect > expected_card_aspect * 1.18
            or current_aspect < expected_card_aspect * 0.82):
        target_w = int(round(box_h * expected_card_aspect))
        left = int(round(center_x - target_w / 2))
        right = left + target_w

    if left < 0:
        right -= left
        left = 0
    if right > w:
        shift = right - w
        left = max(0, left - shift)
        right = w

    final_pad = max(2, int(max(w, h) * 0.0015))
    left, right = max(0, left - final_pad), min(w, right + final_pad)
    top, bottom = max(0, top - final_pad), min(h, bottom + final_pad)

    cropped = img.crop((left, top, right, bottom))
    if cropped.width < 50 or cropped.height < 80:
        raise RuntimeError(f"Recorte demasiado pequeno: {cropped.size}. "
                           "Revisar PDF_CARD_START_PAGE.")
    return cropped


def extract_card_images_from_pdf(pdf_path, card_id_to_page_index, zoom=PAGE_RENDER_ZOOM):
    import fitz
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF de cartas no encontrado: {pdf_path}")
    images = {}
    with fitz.open(pdf_path) as doc:
        for card_id, page_index in card_id_to_page_index.items():
            page_img = render_pdf_page_to_image(doc, page_index, zoom=zoom)
            images[card_id] = crop_card_from_page_image(page_img)
    return images


def get_font(size):
    font_candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for font_path in font_candidates:
        if Path(font_path).exists():
            try:
                return ImageFont.truetype(font_path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def resize_keep_aspect(img, target_width):
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    scale = int(target_width) / img.width
    return img.resize((int(target_width), max(1, int(round(img.height * scale)))),
                      resampling)


def make_labeled_card_tile(card_img, card_id, count,
                           card_width=CARD_DISPLAY_WIDTH, label_alpha=LABEL_ALPHA):
    """A card with a translucent label centred at the bottom: 'xN  ID:###'."""
    card = resize_keep_aspect(card_img, card_width).convert("RGBA")
    label_h = max(48, int(card.height * 0.155))

    overlay = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle(
        [0, card.height - label_h, card.width, card.height],
        fill=(0, 0, 0, int(label_alpha)))
    tile = Image.alpha_composite(card, overlay)
    draw = ImageDraw.Draw(tile)

    text = f"×{count}  ID:{card_id}"
    font_size = max(24, int(label_h * 0.62))
    font = get_font(font_size)
    max_text_width = int(card.width * 0.94)
    while font_size > 10:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_text_width:
            break
        font_size -= 1
        font = get_font(font_size)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (card.width - text_w) // 2
    y = card.height - label_h + (label_h - text_h) // 2 - 1
    try:
        draw.text((x, y), text, fill=(255, 255, 255, 255), font=font,
                  stroke_width=max(1, int(font_size * 0.035)),
                  stroke_fill=(0, 0, 0, 230))
    except TypeError:
        draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
    return tile


def render_deck_grid(ordered_ids, counts, card_images, columns=GRID_COLUMNS,
                     card_width=CARD_DISPLAY_WIDTH, gap=GRID_GAP,
                     padding=GRID_PADDING, label_alpha=LABEL_ALPHA):
    tiles = []
    for card_id in ordered_ids:
        if card_id not in card_images:
            raise KeyError(f"Falta la imagen extraida del Card ID {card_id}")
        tiles.append(make_labeled_card_tile(
            card_images[card_id], card_id, counts[card_id],
            card_width=card_width, label_alpha=label_alpha))

    columns = max(1, int(columns))
    rows = math.ceil(len(tiles) / columns)
    tile_w = max(t.width for t in tiles)
    tile_h = max(t.height for t in tiles)
    width = padding * 2 + columns * tile_w + (columns - 1) * gap
    height = padding * 2 + rows * tile_h + (rows - 1) * gap
    canvas = Image.new("RGB", (width, height), (0, 0, 0))

    for idx, tile in enumerate(tiles):
        row, col = idx // columns, idx % columns
        cell_x = padding + col * (tile_w + gap)
        cell_y = padding + row * (tile_h + gap)
        canvas.paste(tile.convert("RGB"),
                     (cell_x + (tile_w - tile.width) // 2,
                      cell_y + (tile_h - tile.height) // 2))
    return canvas


def save_jpeg_under_size(image, output_path, max_bytes=MAX_OUTPUT_BYTES,
                         start_quality=JPEG_START_QUALITY,
                         min_quality=JPEG_MIN_QUALITY,
                         downscale_step=JPEG_DOWNSCALE_STEP,
                         min_width=JPEG_MIN_WIDTH):
    """It lowers the quality and, if that is not enough, reduces the size until it is under max_bytes."""
    output_path = Path(output_path)
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    working = image.convert("RGB")
    while True:
        for quality in range(start_quality, min_quality - 1, -5):
            working.save(output_path, format="JPEG", quality=quality,
                         optimize=True, progressive=True, subsampling=2)
            size_bytes = output_path.stat().st_size
            if size_bytes <= max_bytes:
                return working, quality, size_bytes
        if working.width <= min_width:
            working.save(output_path, format="JPEG", quality=min_quality,
                         optimize=True, progressive=True, subsampling=2)
            return working, min_quality, output_path.stat().st_size
        new_width = max(min_width, int(working.width * downscale_step))
        scale = new_width / working.width
        working = working.resize(
            (new_width, max(1, int(round(working.height * scale)))), resampling)


def main():
    deck_ids = read_deck_ids(DECK_CSV)
    ordered_ids, counts = ordered_deck_counts(deck_ids)
    card_id_to_order, card_names = load_unique_card_order(CARD_CSV_EN)
    card_id_to_page_index = build_card_id_to_pdf_page_index(ordered_ids, card_id_to_order)

    print("Deck:", DECK_CSV)
    print("Cartas:", len(deck_ids), "| unicas:", len(ordered_ids))
    for card_id in ordered_ids:
        page = card_id_to_page_index[card_id] + 1
        print(f"  x{counts[card_id]}  ID {card_id:>5} -> PDF pag. {page:>4}  "
              f"{card_names.get(card_id, '')}")

    card_images = extract_card_images_from_pdf(CARD_PDF_EN, card_id_to_page_index)
    deck_image = render_deck_grid(ordered_ids, counts, card_images)
    saved, quality, size_bytes = save_jpeg_under_size(deck_image, OUTPUT_EN)

    print("\nGuardado:", OUTPUT_EN)
    print("Tamano imagen:", saved.size, "| calidad JPEG:", quality,
          "| bytes:", f"{size_bytes:,}")


if __name__ == "__main__":
    main()
