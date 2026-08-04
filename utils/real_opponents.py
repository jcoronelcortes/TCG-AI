"""Turns the leaderboard decks into MEASURABLE opponents for self-play.

Phase 9 of the strategy improvement architecture. `utils/build_meta_decks.py`
hand-defines synthetic opponents that "do not claim to be the exact lists of the
meta"; here we start from the EXACT lists that
`utils/download_competitor_decks.py` downloaded from the leaderboard.

It does two things, and the second is the important one:

1. IT DEDUPLICATES. The 100 decks of the top-100 are ~39 unique lists: the 49 decks
   of the dominant archetype are 6 lists with a similarity of 0.99. Measuring against the
   100 spends the game budget on repeating the same matchup instead of
   on reducing the noise. Each unique list keeps the META WEIGHT it
   deserves (how many of the 100 decks were that list).

2. IT SCREENS BY PILOTABILITY. These are real lists, with trainers the generic
   bot (utils/opponent_bot.py) may not know how to use: its policy for an
   unknown select is "the first minCount options". A deck the bot
   cannot pilot does not measure the matchup, it measures the bot getting stuck -- and it returns
   a very high and FALSE winrate for us.

   It is the same lesson as the bot without abilities (project memory: the
   harness was BLIND to the decks whose engine is an ability, and every rule
   against that engine came out NEUTRAL by construction). Before believing a
   matchup number one has to check that the opponent can EXECUTE its deck.

   The screening pits the bot piloting the real list against the bot piloting
   our deck.csv, and requires three things:
     * that it makes no illegal plays (forfeits ~ 0),
     * that the games FINISH (few of them hitting the step cap),
     * that it wins something (a deck the bot cannot get going loses almost always).

   What does not pass the screening is NOT thrown away: it is kept in no_pilotables/ and
   reported, because knowing which part of the meta we cannot measure is information,
   not a failure.

Output in deck/real_opponents/:
    <archetype>_<n>.csv   one real list per file (60 ids, the project's format)
    pesos.csv             the meta weight and screening result of each list
    no_pilotables/        the rejected lists, for inspection

Usage:
    python utils/real_opponents.py                     # dedupe + screening
    python utils/real_opponents.py --partidas 60       # a finer screening
    python utils/real_opponents.py --sin-criba         # dedupe only (fast)

Afterwards, the matrix consumes the corpus and its weights:
    python utils/matchup_matrix.py --rivales deck/real_opponents --pesos
"""

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Screening thresholds. Deliberately lax: the goal is to discard the deck
# the bot canNOT play, not to demand that it plays it well.
#
# MIN_WINRATE is CALIBRATED against a trap deck (the 17 Pokemon of a real
# list + 43 energies of a type none of their attacks pay): legal, but
# with no engine. That deck wins 10%, while the 39 real lists run from 26.7%
# to 88.3%. The 15% falls in the gap between the two. With the initial 5% the trap deck
# passed the screening, which is exactly the false negative this screening exists to
# avoid -- if this threshold is changed, that check has to be redone.
MAX_FORFEITS = 0.02      # illegal plays on the opponent's side
MAX_LIMITES = 0.15       # games that do not finish within the step cap
MIN_WINRATE = 0.15       # below this, the deck does not get going (see the calibration above)


def slug(text):
    """A stable file name derived from the archetype."""
    t = unicodedata.normalize("NFKD", str(text or ""))
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t or "sin_arquetipo"


def load_corpus(source_path):
    """Reads the downloaded decks and groups them by IDENTICAL list.

    It returns the list of groups sorted from the largest to the smallest meta weight.
    """
    index = {}
    index_path = source_path / "indice.csv"
    if index_path.is_file():
        with index_path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                index[row.get("archivo", "")] = row.get("arquetipo", "")

    groups = {}
    total = 0
    for path in sorted(source_path.glob("mazo_*.csv")):
        deck = [int(x) for x in path.read_text(encoding="utf-8").split() if x.strip()]
        if len(deck) != 60:
            print(f"  aviso: {path.name} tiene {len(deck)} cartas, se omite")
            continue
        total += 1
        key = tuple(sorted(Counter(deck).items()))
        group = groups.setdefault(
            key, {"mazo": sorted(deck), "copias": 0, "arquetipos": Counter()}
        )
        group["copias"] += 1
        group["arquetipos"][index.get(path.name, "")] += 1

    output = []
    for group in groups.values():
        arq = group["arquetipos"].most_common(1)[0][0] if group["arquetipos"] else ""
        output.append(
            {
                "mazo": group["mazo"],
                "copias": group["copias"],
                "peso_meta": group["copias"] / total if total else 0.0,
                "arquetipo": arq,
            }
        )
    output.sort(key=lambda g: (-g["peso_meta"], g["arquetipo"], g["mazo"]))

    # A name per archetype, numbered by descending weight within the archetype.
    by_archetype = Counter()
    for group in output:
        base = slug(group["arquetipo"])
        by_archetype[base] += 1
        group["nombre"] = f"{base}_{by_archetype[base]}"
    return output, total


def cribar(group, partidas, deck_referencia):
    """Can the generic bot pilot this list? Bot(real) vs Bot(our deck)."""
    import selfplay as sp
    from opponent_bot import BotRival

    # Separate instances: the bot carries per-turn state and sharing it between
    # the two seats would mix up both sides' ability counters.
    stats = sp.torneo(
        BotRival(), BotRival(), partidas,
        deck_candidato=list(group["mazo"]), deck_base=list(deck_referencia),
    )
    decididas = stats["candidato"] + stats["base"]
    wr = stats["candidato"] / decididas if decididas else 0.0
    forfeits = stats["errores_candidato"] / partidas if partidas else 0.0
    limites = stats["limites"] / partidas if partidas else 0.0

    motivos = []
    if forfeits > MAX_FORFEITS:
        motivos.append(f"jugadas ilegales {100 * forfeits:.0f}%")
    if limites > MAX_LIMITES:
        motivos.append(f"partidas sin terminar {100 * limites:.0f}%")
    if wr < MIN_WINRATE:
        motivos.append(f"no arranca (gana {100 * wr:.0f}%)")
    return {
        "wr_criba": wr, "forfeits": forfeits, "limites": limites,
        "admitido": not motivos, "motivo": "; ".join(motivos),
    }


def write_out(groups, output):
    output.mkdir(parents=True, exist_ok=True)
    rechazados = output / "no_pilotables"
    for viejo in output.glob("*.csv"):
        viejo.unlink()
    if rechazados.is_dir():
        for viejo in rechazados.glob("*.csv"):
            viejo.unlink()

    filas = []
    for group in groups:
        target_path = output if group["admitido"] else rechazados
        target_path.mkdir(parents=True, exist_ok=True)
        (target_path / f"{group['nombre']}.csv").write_text(
            "\n".join(str(cid) for cid in group["mazo"]) + "\n", encoding="utf-8"
        )
        filas.append(
            {
                "archivo": f"{group['nombre']}.csv",
                "arquetipo": group["arquetipo"],
                "peso_meta": round(group["peso_meta"], 4),
                "mazos_origen": group["copias"],
                "estado": "admitido" if group["admitido"] else "no_pilotable",
                "wr_criba": ("" if group.get("wr_criba") is None
                             else round(group["wr_criba"], 3)),
                "forfeits": ("" if group.get("forfeits") is None
                             else round(group["forfeits"], 3)),
                "limites": ("" if group.get("limites") is None
                            else round(group["limites"], 3)),
                "motivo": group.get("motivo", ""),
            }
        )
    with (output / "pesos.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)
    return filas


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origen", default=str(_ROOT / "competitor_decks"))
    ap.add_argument("--salida", default=str(_ROOT / "deck" / "real_opponents"))
    ap.add_argument("--partidas", type=int, default=40,
                    help="partidas de criba por lista unica (default 40)")
    ap.add_argument("--referencia", default=str(_ROOT / "deck.csv"),
                    help="mazo contra el que se criba (default: el nuestro)")
    ap.add_argument("--sin-criba", action="store_true",
                    help="solo deduplicar, sin medir pilotabilidad")
    ap.add_argument("--top", type=int, default=None,
                    help="cribar solo las N listas de mayor peso (el resto se omite)")
    args = ap.parse_args(argv)

    source_path = Path(args.source_path)
    if not source_path.is_dir():
        print(f"ERROR: no existe {source_path}", file=sys.stderr)
        return 1

    print("== 1/3 Deduplicando el corpus ==")
    groups, total = load_corpus(source_path)
    if not groups:
        print("ERROR: no se encontro ningun mazo", file=sys.stderr)
        return 1
    print(f"{total} mazos  ->  {len(groups)} listas unicas")
    cubierto = sum(g["peso_meta"] for g in groups[: args.top]) if args.top else 1.0
    if args.top:
        groups = groups[: args.top]
        print(f"Limitado a las {len(groups)} de mayor peso ({100 * cubierto:.0f}% del meta)")

    if args.sin_criba:
        for group in groups:
            group.update(admitido=True, wr_criba=None, forfeits=None,
                         limites=None, motivo="sin cribar")
    else:
        print(f"\n== 2/3 Criba de pilotabilidad ({args.partidas} partidas por lista) ==")
        import selfplay as sp
        deck_ref = sp.read_deck(args.referencia)
        for n, group in enumerate(groups, start=1):
            result = cribar(group, args.partidas, deck_ref)
            group.update(result)
            marca = "ok " if group["admitido"] else "NO "
            print(f"  {marca}{group['nombre']:<28} peso {100 * group['peso_meta']:4.0f}%  "
                  f"gana {100 * group['wr_criba']:5.1f}%  "
                  f"({n}/{len(groups)}) {group['motivo']}", flush=True)

    print("\n== 3/3 Escritura ==")
    filas = write_out(groups, Path(args.output))
    admitidos = [g for g in groups if g["admitido"]]
    peso_ok = sum(g["peso_meta"] for g in admitidos)
    print(f"Listas admitidas: {len(admitidos)}/{len(groups)}  ->  {args.output}")
    print(f"COBERTURA DE META MEDIBLE: {100 * peso_ok:.1f}%")
    if len(admitidos) < len(groups):
        print("\nNo pilotables (el harness no puede medir esta parte del meta):")
        for g in groups:
            if not g["admitido"]:
                print(f"  {g['nombre']:<28} peso {100 * g['peso_meta']:4.0f}%  {g['motivo']}")
    print(f"\nPesos en {Path(args.output) / 'pesos.csv'} ({len(filas)} filas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
