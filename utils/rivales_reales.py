"""Turns the leaderboard decks into MEASURABLE opponents for self-play.

Phase 9 of the strategy improvement architecture. `utils/construir_mazos_meta.py`
hand-defines synthetic opponents that "do not claim to be the exact lists of the
meta"; here we start from the EXACT lists that
`utils/descargar_mazos_competidores.py` downloaded from the leaderboard.

It does two things, and the second is the important one:

1. IT DEDUPLICATES. The 100 decks of the top-100 are ~39 unique lists: the 49 decks
   of the dominant archetype are 6 lists with a similarity of 0.99. Measuring against the
   100 spends the game budget on repeating the same matchup instead of
   on reducing the noise. Each unique list keeps the META WEIGHT it
   deserves (how many of the 100 decks were that list).

2. IT SCREENS BY PILOTABILITY. These are real lists, with trainers the generic
   bot (utils/bot_rival.py) may not know how to use: its policy for an
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

Output in deck/rivales_reales/:
    <archetype>_<n>.csv   one real list per file (60 ids, the project's format)
    pesos.csv             the meta weight and screening result of each list
    no_pilotables/        the rejected lists, for inspection

Usage:
    python utils/rivales_reales.py                     # dedupe + screening
    python utils/rivales_reales.py --partidas 60       # a finer screening
    python utils/rivales_reales.py --sin-criba         # dedupe only (fast)

Afterwards, the matrix consumes the corpus and its weights:
    python utils/matriz_matchups.py --rivales deck/rivales_reales --pesos
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


def slug(texto):
    """A stable file name derived from the archetype."""
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t or "sin_arquetipo"


def cargar_corpus(origen):
    """Reads the downloaded decks and groups them by IDENTICAL list.

    It returns the list of groups sorted from the largest to the smallest meta weight.
    """
    indice = {}
    ruta_indice = origen / "indice.csv"
    if ruta_indice.is_file():
        with ruta_indice.open(encoding="utf-8-sig", newline="") as fh:
            for fila in csv.DictReader(fh):
                indice[fila.get("archivo", "")] = fila.get("arquetipo", "")

    grupos = {}
    total = 0
    for ruta in sorted(origen.glob("mazo_*.csv")):
        mazo = [int(x) for x in ruta.read_text(encoding="utf-8").split() if x.strip()]
        if len(mazo) != 60:
            print(f"  aviso: {ruta.name} tiene {len(mazo)} cartas, se omite")
            continue
        total += 1
        clave = tuple(sorted(Counter(mazo).items()))
        grupo = grupos.setdefault(
            clave, {"mazo": sorted(mazo), "copias": 0, "arquetipos": Counter()}
        )
        grupo["copias"] += 1
        grupo["arquetipos"][indice.get(ruta.name, "")] += 1

    salida = []
    for grupo in grupos.values():
        arq = grupo["arquetipos"].most_common(1)[0][0] if grupo["arquetipos"] else ""
        salida.append(
            {
                "mazo": grupo["mazo"],
                "copias": grupo["copias"],
                "peso_meta": grupo["copias"] / total if total else 0.0,
                "arquetipo": arq,
            }
        )
    salida.sort(key=lambda g: (-g["peso_meta"], g["arquetipo"], g["mazo"]))

    # A name per archetype, numbered by descending weight within the archetype.
    por_arquetipo = Counter()
    for grupo in salida:
        base = slug(grupo["arquetipo"])
        por_arquetipo[base] += 1
        grupo["nombre"] = f"{base}_{por_arquetipo[base]}"
    return salida, total


def cribar(grupo, partidas, deck_referencia):
    """Can the generic bot pilot this list? Bot(real) vs Bot(our deck)."""
    import selfplay as sp
    from bot_rival import BotRival

    # Separate instances: the bot carries per-turn state and sharing it between
    # the two seats would mix up both sides' ability counters.
    stats = sp.torneo(
        BotRival(), BotRival(), partidas,
        deck_candidato=list(grupo["mazo"]), deck_base=list(deck_referencia),
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


def escribir(grupos, salida):
    salida.mkdir(parents=True, exist_ok=True)
    rechazados = salida / "no_pilotables"
    for viejo in salida.glob("*.csv"):
        viejo.unlink()
    if rechazados.is_dir():
        for viejo in rechazados.glob("*.csv"):
            viejo.unlink()

    filas = []
    for grupo in grupos:
        destino = salida if grupo["admitido"] else rechazados
        destino.mkdir(parents=True, exist_ok=True)
        (destino / f"{grupo['nombre']}.csv").write_text(
            "\n".join(str(cid) for cid in grupo["mazo"]) + "\n", encoding="utf-8"
        )
        filas.append(
            {
                "archivo": f"{grupo['nombre']}.csv",
                "arquetipo": grupo["arquetipo"],
                "peso_meta": round(grupo["peso_meta"], 4),
                "mazos_origen": grupo["copias"],
                "estado": "admitido" if grupo["admitido"] else "no_pilotable",
                "wr_criba": ("" if grupo.get("wr_criba") is None
                             else round(grupo["wr_criba"], 3)),
                "forfeits": ("" if grupo.get("forfeits") is None
                             else round(grupo["forfeits"], 3)),
                "limites": ("" if grupo.get("limites") is None
                            else round(grupo["limites"], 3)),
                "motivo": grupo.get("motivo", ""),
            }
        )
    with (salida / "pesos.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)
    return filas


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origen", default=str(_ROOT / "decks_competidores"))
    ap.add_argument("--salida", default=str(_ROOT / "deck" / "rivales_reales"))
    ap.add_argument("--partidas", type=int, default=40,
                    help="partidas de criba por lista unica (default 40)")
    ap.add_argument("--referencia", default=str(_ROOT / "deck.csv"),
                    help="mazo contra el que se criba (default: el nuestro)")
    ap.add_argument("--sin-criba", action="store_true",
                    help="solo deduplicar, sin medir pilotabilidad")
    ap.add_argument("--top", type=int, default=None,
                    help="cribar solo las N listas de mayor peso (el resto se omite)")
    args = ap.parse_args(argv)

    origen = Path(args.origen)
    if not origen.is_dir():
        print(f"ERROR: no existe {origen}", file=sys.stderr)
        return 1

    print("== 1/3 Deduplicando el corpus ==")
    grupos, total = cargar_corpus(origen)
    if not grupos:
        print("ERROR: no se encontro ningun mazo", file=sys.stderr)
        return 1
    print(f"{total} mazos  ->  {len(grupos)} listas unicas")
    cubierto = sum(g["peso_meta"] for g in grupos[: args.top]) if args.top else 1.0
    if args.top:
        grupos = grupos[: args.top]
        print(f"Limitado a las {len(grupos)} de mayor peso ({100 * cubierto:.0f}% del meta)")

    if args.sin_criba:
        for grupo in grupos:
            grupo.update(admitido=True, wr_criba=None, forfeits=None,
                         limites=None, motivo="sin cribar")
    else:
        print(f"\n== 2/3 Criba de pilotabilidad ({args.partidas} partidas por lista) ==")
        import selfplay as sp
        deck_ref = sp.leer_deck(args.referencia)
        for n, grupo in enumerate(grupos, start=1):
            resultado = cribar(grupo, args.partidas, deck_ref)
            grupo.update(resultado)
            marca = "ok " if grupo["admitido"] else "NO "
            print(f"  {marca}{grupo['nombre']:<28} peso {100 * grupo['peso_meta']:4.0f}%  "
                  f"gana {100 * grupo['wr_criba']:5.1f}%  "
                  f"({n}/{len(grupos)}) {grupo['motivo']}", flush=True)

    print("\n== 3/3 Escritura ==")
    filas = escribir(grupos, Path(args.salida))
    admitidos = [g for g in grupos if g["admitido"]]
    peso_ok = sum(g["peso_meta"] for g in admitidos)
    print(f"Listas admitidas: {len(admitidos)}/{len(grupos)}  ->  {args.salida}")
    print(f"COBERTURA DE META MEDIBLE: {100 * peso_ok:.1f}%")
    if len(admitidos) < len(grupos):
        print("\nNo pilotables (el harness no puede medir esta parte del meta):")
        for g in grupos:
            if not g["admitido"]:
                print(f"  {g['nombre']:<28} peso {100 * g['peso_meta']:4.0f}%  {g['motivo']}")
    print(f"\nPesos en {Path(args.salida) / 'pesos.csv'} ({len(filas)} filas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
