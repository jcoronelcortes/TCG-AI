"""Builds the meta representation report from the harvested competitor decks.

Input: `competitor_decks/indice.csv` (written by `utils/download_competitor_decks.py`),
which already carries the leaderboard position, the score and the archetype of every
recovered deck.

Two questions are answered separately, because they are NOT the same question:

  * PRESENCE - how much of the top does an archetype occupy (share of the N decks).
  * WHERE IT WINS - how that presence is distributed across leaderboard bands of 30
    positions (1-30, 31-60, ...). An archetype can be 10% of the field and still own
    the first band, or be everywhere and never reach the top 30.

The band matrix is the honest way to read "the most winning ones": the leaderboard
position IS the ranking, so an archetype that concentrates in the first bands is
beating the field, no matter its global share.

Usage:

    python utils/meta_representation_report.py                 # top 300, bands of 30
    python utils/meta_representation_report.py --band-size 50
    python utils/meta_representation_report.py --output docs/meta.md
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "competitor_decks"


def read_index(index_path: Path) -> list[dict[str, Any]]:
    """Reads indice.csv and keeps only the rows with a usable position."""
    rows: list[dict[str, Any]] = []
    with index_path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                position = int(str(row.get("posicion_leaderboard", "")).strip())
            except (TypeError, ValueError):
                continue
            try:
                score = float(str(row.get("puntaje", "")).strip())
            except (TypeError, ValueError):
                score = float("nan")
            rows.append(
                {
                    "archivo": row.get("archivo", ""),
                    "posicion": position,
                    "puntaje": score,
                    "arquetipo": (row.get("arquetipo") or "Desconocido").strip(),
                }
            )
    return sorted(rows, key=lambda r: r["posicion"])


def deck_fingerprint(deck_dir: Path, file_name: str) -> str:
    """The 60 sorted IDs: two decks with the same fingerprint are the same list."""
    path = deck_dir / file_name
    try:
        ids = sorted(int(x) for x in path.read_text(encoding="utf-8").split() if x.strip())
    except (OSError, ValueError):
        return ""
    return ",".join(str(i) for i in ids)


def bands(rows: list[dict[str, Any]], size: int) -> list[tuple[str, list[dict[str, Any]]]]:
    """Splits the decks into position bands: 1-30, 31-60, ... (the label is 1-indexed)."""
    if not rows:
        return []
    top = max(r["posicion"] for r in rows)
    output: list[tuple[str, list[dict[str, Any]]]] = []
    start = 1
    while start <= top:
        end = start + size - 1
        block = [r for r in rows if start <= r["posicion"] <= end]
        output.append((f"{start}-{end}", block))
        start = end + 1
    return output


def pct(part: int, total: int) -> str:
    return f"{100.0 * part / total:.1f}%" if total else "-"


def table_presence(rows: list[dict[str, Any]]) -> list[str]:
    """Global presence: how much of the harvested top each archetype occupies."""
    total = len(rows)
    by_archetype: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_archetype[row["arquetipo"]].append(row)

    order = sorted(
        by_archetype.items(),
        key=lambda kv: (-len(kv[1]), min(r["posicion"] for r in kv[1])),
    )
    lines = [
        "| # | Arquetipo | Mazos | % de presencia | Mejor puesto | Puntaje max | Puesto mediano |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for n, (archetype, group) in enumerate(order, start=1):
        scores = [r["puntaje"] for r in group if r["puntaje"] == r["puntaje"]]
        lines.append(
            "| {n} | {a} | {c} | {p} | {best} | {smax} | {med} |".format(
                n=n,
                a=archetype,
                c=len(group),
                p=pct(len(group), total),
                best=min(r["posicion"] for r in group),
                smax=f"{max(scores):.1f}" if scores else "-",
                med=int(statistics.median([r["posicion"] for r in group])),
            )
        )
    return lines


def table_band_matrix(rows: list[dict[str, Any]], size: int) -> list[str]:
    """Archetype x band matrix: where in the leaderboard each archetype lives."""
    blocks = bands(rows, size)
    total = len(rows)
    by_archetype: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_archetype[row["arquetipo"]].append(row)

    order = sorted(
        by_archetype.items(),
        key=lambda kv: (-len(kv[1]), min(r["posicion"] for r in kv[1])),
    )

    header = "| Arquetipo | " + " | ".join(label for label, _ in blocks) + " | Total | % |"
    sep = "|---|" + "---:|" * (len(blocks) + 2)
    lines = [header, sep]
    for archetype, group in order:
        cells = []
        for _, block in blocks:
            n = sum(1 for r in block if r["arquetipo"] == archetype)
            cells.append(str(n) if n else "·")
        lines.append(
            f"| {archetype} | " + " | ".join(cells) + f" | {len(group)} | {pct(len(group), total)} |"
        )
    footer = [str(len(block)) for _, block in blocks]
    lines.append("| **Mazos en la banda** | " + " | ".join(footer) + f" | {total} | 100% |")
    return lines


def table_band_leaders(rows: list[dict[str, Any]], size: int, top_k: int) -> list[str]:
    """The dominant archetypes inside each band, with their share OF THAT BAND."""
    lines = [
        "| Banda | Mazos | Arquetipos dominantes (% de la banda) | Puntaje del 1o | Puntaje del ultimo |",
        "|---|---:|---|---:|---:|",
    ]
    for label, block in bands(rows, size):
        if not block:
            lines.append(f"| {label} | 0 | - | - | - |")
            continue
        conteo = Counter(r["arquetipo"] for r in block)
        head = ", ".join(
            f"**{name}** {pct(n, len(block))}" for name, n in conteo.most_common(top_k)
        )
        ordenada = sorted(block, key=lambda r: r["posicion"])
        first = ordenada[0]["puntaje"]
        last = ordenada[-1]["puntaje"]
        lines.append(
            "| {label} | {n} | {head} | {p1} | {p2} |".format(
                label=label,
                n=len(block),
                head=head,
                p1=f"{first:.1f}" if first == first else "-",
                p2=f"{last:.1f}" if last == last else "-",
            )
        )
    return lines


def table_exact_lists(
    rows: list[dict[str, Any]], deck_dir: Path, min_copies: int
) -> tuple[list[str], int]:
    """Identical 60-card lists: the same deck piloted by several competitors."""
    by_fingerprint: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        fingerprint = deck_fingerprint(deck_dir, row["archivo"])
        if fingerprint:
            by_fingerprint[fingerprint].append(row)

    order = sorted(
        by_fingerprint.values(),
        key=lambda g: (-len(g), min(r["posicion"] for r in g)),
    )
    total = len(rows)
    lines = [
        "| # | Arquetipo | Copias | % del top | Mejor puesto | Mazo representante |",
        "|---:|---|---:|---:|---:|---|",
    ]
    n = 0
    for group in order:
        if len(group) < min_copies:
            break
        n += 1
        best = min(group, key=lambda r: r["posicion"])
        lines.append(
            f"| {n} | {best['arquetipo']} | {len(group)} | {pct(len(group), total)} "
            f"| {best['posicion']} | `{best['archivo']}` |"
        )
    return lines, len(by_fingerprint)


def build_report(
    rows: list[dict[str, Any]], deck_dir: Path, size: int, top_k: int, min_copies: int
) -> str:
    exact, n_unique = table_exact_lists(rows, deck_dir, min_copies)
    top = max(r["posicion"] for r in rows) if rows else 0
    parts = [
        f"# Representacion del meta - top {top} del leaderboard",
        "",
        f"Fuente: `{deck_dir.name}/indice.csv` | mazos recuperados: **{len(rows)}** "
        f"| listas unicas de 60 cartas: **{n_unique}**",
        "",
        "## 1. Presencia por arquetipo",
        "",
        "El % es sobre los mazos recuperados, no sobre las posiciones del leaderboard:",
        "un competidor sin replay publico no aporta mazo.",
        "",
        *table_presence(rows),
        "",
        f"## 2. Los mas ganadores: bandas de {size} puestos",
        "",
        "El puesto del leaderboard ES el ranking. Un arquetipo que se concentra en las",
        "primeras bandas gana, aunque su presencia global sea pequena.",
        "",
        *table_band_leaders(rows, size, top_k),
        "",
        f"## 3. Matriz arquetipo x banda de {size}",
        "",
        *table_band_matrix(rows, size),
        "",
        f"## 4. Listas exactas repetidas (>= {min_copies} copias)",
        "",
        *exact,
        "",
    ]
    return "\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--decks", default=str(DEFAULT_DIR), help="folder with mazo_XXX.csv + indice.csv")
    parser.add_argument("--band-size", type=int, default=30, help="positions per band (default 30)")
    parser.add_argument("--top-k", type=int, default=3, help="dominant archetypes shown per band")
    parser.add_argument("--min-copies", type=int, default=2, help="minimum copies to list an exact deck")
    parser.add_argument("--output", default=None, help="markdown file (default <decks>/reporte_representacion.md)")
    args = parser.parse_args(argv)

    deck_dir = Path(args.decks)
    index_path = deck_dir / "indice.csv"
    if not index_path.is_file():
        print(f"ERROR: no existe {index_path}", file=sys.stderr)
        return 1

    rows = read_index(index_path)
    if not rows:
        print(f"ERROR: {index_path} no tiene filas con posicion utilizable", file=sys.stderr)
        return 1

    report = build_report(rows, deck_dir, args.band_size, args.top_k, args.min_copies)
    target = Path(args.output) if args.output else deck_dir / "reporte_representacion.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report, encoding="utf-8")
    print(report)
    print(f"Informe escrito en {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
