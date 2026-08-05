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
    python utils/real_opponents.py --games 60       # a finer screening
    python utils/real_opponents.py --no-filter         # dedupe only (fast)

Afterwards, the matrix consumes the corpus and its weights:
    python utils/matchup_matrix.py --opponents deck/real_opponents --weights
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

# A list this close to OUR OWN 60 is not measuring a matchup. The bot pilots it
# legally -- so the pilotability screen admits it -- but it pilots OUR engine,
# which it plays badly, and the winrate comes back inflated. It is the same
# failure the screen exists to catch, arriving from the other side: there the
# opponent gets stuck, here it is simply us against a worse copy of ourselves.
# The August 2026 corpus carried FIVE, one of them 60/60 identical.
#
# They are NOT thrown away: somebody really does play them on the ladder, so
# dropping them would bias the ladder estimate. They are only marked, so the
# aggregation can say what the number looks like without them.
MIRROR_OVERLAP = 40      # cards in common with the reference deck, out of 60


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
            print(f"  warning: {path.name} tiene {len(deck)} cards, skipped")
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


def cribar(group, games, deck_referencia):
    """Can the generic bot pilot this list? Bot(real) vs Bot(our deck)."""
    import selfplay as sp
    from opponent_bot import BotRival

    # Separate instances: the bot carries per-turn state and sharing it between
    # the two seats would mix up both sides' ability counters.
    stats = sp.torneo(
        BotRival(), BotRival(), games,
        deck_candidato=list(group["mazo"]), deck_base=list(deck_referencia),
    )
    decididas = stats["candidate"] + stats["base"]
    wr = stats["candidate"] / decididas if decididas else 0.0
    forfeits = stats["errores_candidato"] / games if games else 0.0
    limites = stats["limites"] / games if games else 0.0

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


def overlap_with(deck, reference):
    """Cards in common between two 60-card lists, COUNTING COPIES.

    Comparing sets would call two lists twins for sharing a staple; what makes a
    list a mirror is playing the same number of copies of the same cards.
    """
    a, b = Counter(deck), Counter(reference)
    return sum(min(a[cid], b[cid]) for cid in set(a) | set(b))


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
                "solape_propio": ("" if group.get("solape_propio") is None
                                  else group["solape_propio"]),
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
    ap.add_argument("--source", dest="source_path", default=str(_ROOT / "competitor_decks"))
    ap.add_argument("--output", default=str(_ROOT / "deck" / "real_opponents"))
    ap.add_argument("--games", type=int, default=40,
                    help="screening games per unique list (default 40)")
    ap.add_argument("--reference", default=str(_ROOT / "deck.csv"),
                    help="deck to screen against (default: ours)")
    ap.add_argument("--no-filter", action="store_true",
                    help="deduplicate only, without measuring pilotability")
    ap.add_argument("--top", type=int, default=None,
                    help="screen only the N heaviest lists (the rest are skipped)")
    args = ap.parse_args(argv)

    source_path = Path(args.source_path)
    if not source_path.is_dir():
        print(f"ERROR: there is no {source_path}", file=sys.stderr)
        return 1

    print("== 1/3 Deduplicating the corpus ==")
    groups, total = load_corpus(source_path)
    if not groups:
        print("ERROR: no deck was found", file=sys.stderr)
        return 1
    print(f"{total} decks  ->  {len(groups)} listas unique")
    cubierto = sum(g["peso_meta"] for g in groups[: args.top]) if args.top else 1.0
    if args.top:
        groups = groups[: args.top]
        print(f"Limited to the {len(groups)} heaviest ({100 * cubierto:.0f}% of the meta)")

    # The overlap is measured in BOTH branches: it costs nothing and a mirror
    # slipping through --no-filter is exactly as misleading.
    import selfplay as sp
    deck_ref = sp.read_deck(args.reference)
    for group in groups:
        group["solape_propio"] = overlap_with(group["mazo"], deck_ref)

    if args.no_filter:
        for group in groups:
            group.update(admitido=True, wr_criba=None, forfeits=None,
                         limites=None, motivo="sin cribar")
    else:
        print(f"\n== 2/3 Pilotability screening ({args.games} games per list) ==")
        for n, group in enumerate(groups, start=1):
            result = cribar(group, args.games, deck_ref)
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
    print(f"MEASURABLE META COVERAGE: {100 * peso_ok:.1f}%")
    if len(admitidos) < len(groups):
        print("\nNot pilotable (the harness cannot measure this part of the meta):")
        for g in groups:
            if not g["admitido"]:
                print(f"  {g['nombre']:<28} peso {100 * g['peso_meta']:4.0f}%  {g['motivo']}")

    espejos = [g for g in admitidos if g["solape_propio"] >= MIRROR_OVERLAP]
    if espejos:
        peso_esp = sum(g["peso_meta"] for g in espejos)
        print(f"\nNear-copies of our own list ({MIRROR_OVERLAP}+/60 cards in common). "
              "The bot pilots OUR engine here, badly, so the winrate against them "
              "reads high and is not a matchup:")
        for g in sorted(espejos, key=lambda x: -x["solape_propio"]):
            print(f"  {g['nombre']:<28} solape {g['solape_propio']}/60  "
                  f"peso {100 * g['peso_meta']:4.1f}%  [{g['arquetipo']}]")
        print(f"  -> {len(espejos)} listas, {100 * peso_esp:.1f}% del meta. They are KEPT "
              "(somebody plays them), and marked in pesos.csv so the aggregation "
              "can report with and without.")
    print(f"\nPesos en {Path(args.output) / 'pesos.csv'} ({len(filas)} filas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
