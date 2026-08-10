"""Freeze the golden corpus so the flip-diff runs on a clean checkout.

T3.4 of docs/testing-plan-2026-08.md. The flip-diff -- "which historical
decisions did your change flip, exactly" -- is the most useful review artefact
this project produces, and until now it did not exist for anyone who had just
cloned the repository: `records/` is git-ignored transient data, so
`tests/test_golden_corpus.py` SKIPS on a clean checkout and the CI job says so
in its own header.

WHAT MAKES IT FIT. A record is the whole game stream, both seats, every step:
50 of them are 41 MB. But the corpus only ever replays OUR decisions -- the
steps that are ACTIVE, carry a `select`, and belong to our seat -- and those are
what the snapshot is made of. Keeping just them and gzipping takes the same 50
games to **0.85 MB**, which is small enough to commit whole. No sampling, no
"representative subset", no judgement about which games matter: all of them.

WHAT IS FROZEN, precisely:

  * `tests/corpus/frozen_records.json.gz` -- {record name: {seat, steps}}. The
    seat is stored rather than re-derived, because `our_index` votes by counting
    visible cards from deck.csv and a bundle that keeps only one seat's
    observations is exactly the input that vote is worst at.
  * `tests/corpus/frozen_decisions.json` -- the snapshot to compare against,
    committed alongside it. Without this half CI has the games and nothing to
    say about them.

THE DIFFERENCE FROM THE LOCAL CORPUS, and both are kept. The local one
self-heals: records are transient, so a changed md5 silently re-snapshots. The
frozen one CANNOT self-heal -- it is versioned by git, so a flip is a flip and
the diff is the finding. That is what makes it usable as a gate.

IT REBUILDS THE BUNDLE, and that is the trap. `records/` is transient and
git-ignored, so a working tree usually holds a handful of games while the
committed bundle holds every game somebody once froze (measured Aug 2026: 50
records / 3 580 decisions in the bundle against 13 in `records/`). Running this
to ACCEPT a flip -- which is what the failing test tells you to do -- would
throw away the difference, and the bundle is a gzip, so the commit diff does not
show it. `--snapshot-only` is the flag for that job: it re-plays the bundle that
is already committed and rewrites only the snapshot. Shrinking now needs
`--force`.

Usage:
    python utils/record_corpus.py --games 50     # play the games
    python utils/freeze_corpus.py                # freeze them + the snapshot
    python utils/freeze_corpus.py --snapshot-only  # accept reviewed flips
    python utils/freeze_corpus.py --check        # what would change
"""

import argparse
import gzip
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import golden_corpus as gc  # noqa: E402

BUNDLE = _ROOT / "tests" / "corpus" / "frozen_records.json.gz"
SNAPSHOT = _ROOT / "tests" / "corpus" / "frozen_decisions.json"


def build_bundle():
    """{record name: {"seat": n, "steps": [...]}} with OUR decisions only."""
    bundle = {}
    for path in gc.record_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        seat = gc.our_index(data)
        kept = []
        for step in data.get("steps", []):
            for item in step:
                obs = item.get("observation") or {}
                current = obs.get("current") or {}
                if (item.get("status") == "ACTIVE" and obs.get("select")
                        and current.get("yourIndex") == seat):
                    kept.append([{"status": "ACTIVE", "observation": obs}])
        if not kept:
            # A record that contributes no decision gates nothing, and an empty
            # list compares equal to an empty list forever. `our_index` carries
            # the same warning for the same reason.
            print(f"  SALTADO (cero decisiones nuestras): {path.name}")
            continue
        bundle[path.name] = {"seat": seat, "steps": kept}
    return bundle


def write_snapshot(bundle):
    """Re-plays `bundle` with the CURRENT code and rewrites only the snapshot."""
    module = gc._main_mod()
    snapshot = {name: {"decisiones": gc.replay_data(module, data)}
                for name, data in sorted(bundle.items())}
    SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8")
    decisions = sum(len(v["decisiones"]) for v in snapshot.values())
    print(f"\n{len(bundle)} registros, {decisions} decisiones")
    print(f"  {SNAPSHOT.relative_to(_ROOT)}  {SNAPSHOT.stat().st_size / 1e6:.2f} MB")


def write(bundle):
    BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(bundle, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    BUNDLE.write_bytes(gzip.compress(blob, 9))
    write_snapshot(bundle)
    print(f"  {BUNDLE.relative_to(_ROOT)}   {BUNDLE.stat().st_size / 1e6:.2f} MB")


def check():
    if not BUNDLE.exists():
        print("No hay corpus congelado todavia.", file=sys.stderr)
        return 2
    frozen = gc.frozen_records()
    module = gc._main_mod()
    actual = {name: {"decisiones": gc.replay_data(module, data)}
              for name, data in sorted(frozen.items())}
    stored = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    # `comparar` devuelve CUATRO listas, no una: pasarle la tupla entera a
    # `formatear_flips` reventaba con TypeError, asi que el unico camino que
    # imprime el flip-diff sin reescribir nada estaba muerto.
    _cambiados, faltantes, nuevos, flips = gc.comparar(stored, actual)
    if not (flips or faltantes or nuevos):
        print(f"{len(frozen)} registros congelados, sin flips.")
        return 0
    if faltantes:
        print(f"registros que ya no estan en el snapshot: {faltantes}")
    if nuevos:
        print(f"registros sin entrada en el snapshot: {nuevos}")
    if flips:
        print(gc.formatear_flips(flips))
    return 1


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="compara sin reescribir")
    parser.add_argument("--snapshot-only", action="store_true",
                        help="re-juega el bundle YA congelado y reescribe solo "
                             "el snapshot (para aceptar flips revisados)")
    parser.add_argument("--force", action="store_true",
                        help="reconstruye el bundle aunque encoja")
    args = parser.parse_args(argv)
    if args.check:
        return check()

    if args.snapshot_only:
        frozen = gc.frozen_records()
        if not frozen:
            print("No hay corpus congelado todavia.", file=sys.stderr)
            return 2
        write_snapshot(frozen)
        return 0

    bundle = build_bundle()
    if not bundle:
        print("No hay registros en records/. Corre utils/record_corpus.py antes.",
              file=sys.stderr)
        return 2

    # NO SE ENCOGE EL GATE SIN DECIRLO. `records/` es transitorio: un arbol de
    # trabajo normal tiene un punado de partidas y el bundle commiteado tiene
    # todas las que alguien congelo. Reconstruirlo aqui para ACEPTAR un flip
    # tiraria la diferencia, y como el bundle es un .gz el diff del commit no lo
    # ensena.
    frozen = gc.frozen_records()
    if frozen and len(bundle) < len(frozen) and not args.force:
        print(f"records/ tiene {len(bundle)} registros y el bundle congelado "
              f"{len(frozen)}: reconstruirlo PERDERIA "
              f"{len(frozen) - len(bundle)}.\n"
              "  Para aceptar flips ya revisados:  "
              "python utils/freeze_corpus.py --snapshot-only\n"
              "  Para regenerar el corpus entero:  "
              "python utils/record_corpus.py --games 50\n"
              "  Si de verdad quieres encogerlo:   --force",
              file=sys.stderr)
        return 2

    write(bundle)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
