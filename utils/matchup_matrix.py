"""Matchup matrix: the agent's winrate against EACH opposing deck.

By default it measures against `deck/rivales_reales/` -- the REAL leaderboard
lists (utils/real_opponents.py), with their meta weight.

The synthetic ones in `deck/rivales/` are still there but they are NO LONGER the default, and
it is worth knowing why: measured against the top-300, **8 of its 17 decks are
archetypes that do not exist in the meta** (Comfey, Iron Thorns, Jellicent, Raging
Bolt, Cornerstone/Cubchoo, Hop's, Fire Gouging, Comfey/Yveltal). Since the matrix
weights every deck equally unless --pesos is passed, running it against
that folder spent almost half the game budget on imaginary
opponents -- and a change that won there and lost against Marnie looked
good. They are kept because they are still useful for testing specific MECHANICS
(the Iron Thorns lock, the Comfey mill) that the current meta does not offer.


Phase 8 of the strategy improvement architecture. It walks every CSV in the
opponents folder and plays N games against the generic bot with each of them,
alternating seats. It prints the table sorted from the weakest matchup to the
strongest, with the 95% Wilson interval and the forfeits.

With --base <git-ref> it also prints the per-matchup DELTA against that version:
it detects when a new rule improves one matchup while degrading another (the
Cubchoo/Cornerstone collision class). CAREFUL with the noise: with 200 games the delta
swings +-7 points; only large, consistent deltas are signal.

That +-7 is CONFIRMED by direct measurement (Aug 2026): in a run at 200
games with --base, the 83 decks that could not be affected by the change
-- behaviourally identical code in both arms -- moved between -6.5
and +7.5 points. Hence the --partidas default rising to 400 and the existence of
--control-carta: the warning was written from the start and even so it is easy
to read as signal a delta that fits entirely inside the noise.

With --pesos (and the corpus of utils/real_opponents.py) the summary stops being a
simple average: each matchup weighs what that archetype weighs in the real meta. It is the
difference between "I beat 8 of 17 decks" and "I win X% of the games I am going
to play on ladder" -- with a simple average, a +10 against an archetype that is
1% of the field hides a -1 against the one that is 41%.

`--control-carta <id>` separates the decks that run that card (the ones the change
CAN affect) from the ones that do not, and compares the deltas of both groups. The control
group runs behaviourally identical code in both arms, so its
dispersion IS the noise of that same run. It is the only cheap way to know
whether a delta is signal: measured here, at 200 games per matchup the control gets
to move from -6.5 to +7.5 points, so a small delta without this breakdown
means nothing.

Usage:
    python utils/matchup_matrix.py --partidas 400
    python utils/matchup_matrix.py --partidas 400 --base HEAD~1
    python utils/matchup_matrix.py --base HEAD~1 --control-carta 1266
    python utils/matchup_matrix.py --solo dragapult,hops
    python utils/matchup_matrix.py --rivales deck/rivales_reales --pesos
    python utils/matchup_matrix.py --rivales deck/rivales_reales --pesos --base HEAD~1
"""

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp
from opponent_bot import BotRival


def is_deck(path):
    """Is the CSV a list of 60 ids and not something else?

    The opponents directory also contains `pesos.csv`, and it could contain
    any other auxiliary CSV. Without this filter the matrix tries to read it as a
    deck and blows up AFTER having played all the good matchups.
    """
    try:
        lines = [x for x in path.read_text(encoding="utf-8-sig").split() if x.strip()]
    except (OSError, UnicodeDecodeError):
        return False
    if len(lines) != 60:
        return False
    return all(x.lstrip("-").isdigit() for x in lines)


def load_weights(directorio):
    """Meta weight per deck, from the pesos.csv of utils/real_opponents.py.

    Without this the matrix treats every opponent equally, which is what
    makes a change get approved for winning against archetypes almost nobody
    plays. It returns {} if there is no pesos.csv.
    """
    import csv

    path = Path(directorio) / "pesos.csv"
    if not path.is_file():
        return {}
    pesos = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            name = str(row.get("archivo", ""))
            if name.endswith(".csv"):
                name = name[:-4]
            try:
                pesos[name] = float(row.get("peso_meta") or 0.0)
            except ValueError:
                continue
    return pesos


def _carries_card(path, card_id):
    try:
        return card_id in [int(x) for x in path.read_text().split() if x.strip()]
    except (OSError, ValueError):
        return False


def informe_control(filas, base_by_deck, paths, card_id):
    """Separates the AFFECTED decks (those with the card) from the CONTROL and compares their deltas.

    It is the only cheap way to know whether a delta is signal: the decks that do NOT
    run the card execute behaviourally identical code in both arms,
    so their dispersion IS the noise of that same run -- with no need to
    run a separate calibration.

    Measured in this session: at 200 games per matchup the control group gets
    to move from -6.5 to +7.5 points. Any delta of the affected decks that fits
    in that range is not signal.
    """
    by_name = {r.stem: r for r in paths}
    con, sin = [], []
    for f in filas:
        if f["mazo"] not in base_by_deck:
            continue
        delta = f["wr"] - base_by_deck[f["mazo"]]["wr"]
        dprem = None
        bp = base_by_deck[f["mazo"]].get("dif_premios")
        if f["dif_premios"] is not None and bp is not None:
            dprem = f["dif_premios"] - bp
        path = by_name.get(f["mazo"])
        destino = con if (path is not None and _carries_card(path, card_id)) else sin
        destino.append((f["mazo"], delta, dprem))

    if not con or not sin:
        print(f"\n(control: no se puede separar por la carta {card_id}; "
              f"afectados={len(con)}, control={len(sin)})")
        return

    print(f"\n=== GRUPO DE CONTROL (carta {card_id}) ===")
    for etiqueta, group in (("AFECTADOS", con), ("CONTROL  ", sin)):
        ds = [d for _, d, _ in group]
        ps = [p for _, _, p in group if p is not None]
        positivos = sum(1 for d in ds if d > 0)
        line = (f"  {etiqueta} n={len(ds):>2}  delta wr {100 * sum(ds) / len(ds):+6.2f}"
                 f"  rango {100 * min(ds):+.1f} a {100 * max(ds):+.1f}"
                 f"  positivos {positivos}/{len(ds)}")
        if ps:
            line += f"  delta premios {sum(ps) / len(ps):+.3f}"
        print(line)
    print("  Si el delta de AFECTADOS cabe en el rango de CONTROL, es ruido: "
          "el control corre codigo identico en los dos brazos.")


def winrate_ponderado(filas, pesos):
    """(expected ladder winrate, measured meta coverage).

    The winrate is normalised over what was ACTUALLY measured, and the coverage is
    returned separately: a number over 60% of the meta is not comparable with one
    over 100%, and hiding that would be the very error this metric exists to correct.
    """
    cobertura = sum(pesos.get(f["mazo"], 0.0) for f in filas)
    if cobertura <= 0:
        return None, 0.0
    total = sum(pesos.get(f["mazo"], 0.0) * f["wr"] for f in filas)
    return total / cobertura, cobertura


def medir(agent_state, partidas, paths):
    bot = BotRival()
    filas = []
    for path in paths:
        opponent_deck = sp.read_deck(path)
        stats = sp.torneo(agent_state, bot, partidas, deck_base=opponent_deck)
        dec = stats["candidato"] + stats["base"]
        wr = stats["candidato"] / dec if dec else 0.0
        lo, hi = sp.wilson_95(stats["candidato"], dec)
        pc, pb, prize_diff = sp.prizes_per_game(stats)
        filas.append({
            "mazo": path.stem, "wr": wr, "lo": lo, "hi": hi,
            "decididas": dec, "limites": stats["limites"],
            "forfeits": stats["errores_candidato"],
            "forfeits_bot": stats["errores_base"],
            "premios": pc, "premios_bot": pb, "dif_premios": prize_diff,
        })
        extra = "" if prize_diff is None else f" premios {prize_diff:+.2f}"
        print(f"  {path.stem}: {100 * wr:.1f}% "
              f"[{100 * lo:.1f}-{100 * hi:.1f}]{extra} "
              f"(forfeits nuestros {stats['errores_candidato']})", flush=True)
    return filas


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--control-carta", type=int, default=None, metavar="ID",
                    help="id de carta que define el grupo AFECTADO: separa los "
                         "mazos que la llevan de los que no y compara los dos "
                         "deltas. Sin esto, un delta no se distingue del ruido")
    ap.add_argument("--partidas", type=int, default=400,
                    help="partidas por matchup (default 400). Medido: a 200 el "
                         "ruido por matchup llega a +-6.5 puntos")
    ap.add_argument("--candidato", default="main.py")
    ap.add_argument("--base", default=None,
                    help="ref de git: imprime el delta por matchup")
    ap.add_argument("--solo", default=None,
                    help="lista de mazos separada por comas (default: todos)")
    ap.add_argument("--rivales", default=str(_ROOT / "deck" / "rivales_reales"),
                    help="carpeta de mazos rivales (default: deck/rivales_reales, "
                         "las listas REALES del leaderboard con sus pesos)")
    ap.add_argument("--pesos", action="store_true",
                    help="pondera por frecuencia real en el meta (necesita el "
                         "pesos.csv de utils/real_opponents.py)")
    args = ap.parse_args(argv)

    todos = sorted(Path(args.rivales).glob("*.csv"))
    paths = [r for r in todos if is_deck(r)]
    omitidos = [r.name for r in todos if r not in paths]
    if omitidos:
        print(f"(no son mazos, se omiten: {', '.join(omitidos)})")
    if args.solo:
        quiere = {s.strip() for s in args.solo.split(",")}
        paths = [r for r in paths if r.stem in quiere]
    if not paths:
        print("sin mazos rivales que medir")
        return 1

    # The weights are loaded BEFORE playing: if they are missing, the error must come out now and
    # not after an hour of games.
    pesos = load_weights(args.rivales) if args.pesos else {}
    if args.pesos and not pesos:
        print(f"ERROR: no hay pesos.csv en {args.rivales}. "
              f"Generalo con: python utils/real_opponents.py", file=sys.stderr)
        return 1

    agent_state = sp.load_agent(_ROOT / args.candidato, "agente_matriz")
    print(f"candidato={args.candidato}, {args.partidas} partidas por matchup")
    filas = medir(agent_state, args.partidas, paths)

    base_by_deck = {}
    if args.base:
        base = sp.load_agent_from_git(args.base, "agente_matriz_base")
        print(f"\nbaseline={args.base}")
        base_by_deck = {f["mazo"]: f for f in
                         medir(base, args.partidas, paths)}

    sin_peso = [f["mazo"] for f in filas if f["mazo"] not in pesos] if pesos else []

    print("\n=== MATRIZ DE MATCHUPS (peor -> mejor) ===")
    width = max(len(f["mazo"]) for f in filas)
    for f in sorted(filas, key=lambda x: x["wr"]):
        line = (f"{f['mazo']:<{width}}  {100 * f['wr']:5.1f}%  "
                 f"[{100 * f['lo']:.1f}-{100 * f['hi']:.1f}]"
                 f"  n={f['decididas']}")
        if pesos:
            line += f"  meta={100 * pesos.get(f['mazo'], 0.0):4.1f}%"
        if f["forfeits"]:
            line += f"  FORFEITS={f['forfeits']}"
        if f["dif_premios"] is not None:
            line += f"  prem={f['dif_premios']:+.2f}"
        if f["mazo"] in base_by_deck:
            delta = f["wr"] - base_by_deck[f["mazo"]]["wr"]
            line += f"  delta={100 * delta:+.1f}"
            if pesos:
                # What that delta moves the ladder winrate by: a +10 against an
                # archetype that is 1% is worth ten times less than a +1 against the one that is 41%.
                line += f" (pond {100 * delta * pesos.get(f['mazo'], 0.0):+.2f})"
            base_prem = base_by_deck[f["mazo"]].get("dif_premios")
            if f["dif_premios"] is not None and base_prem is not None:
                line += f"  dprem={f['dif_premios'] - base_prem:+.2f}"
        print(line)
    worst = min(filas, key=lambda x: x["wr"])
    print(f"\nMatchup mas debil: {worst['mazo']} ({100 * worst['wr']:.1f}%)")

    if args.control_carta is not None and base_by_deck:
        informe_control(filas, base_by_deck, paths, args.control_carta)
    elif args.control_carta is not None:
        print("\n(--control-carta necesita --base: sin baseline no hay deltas "
              "que separar)")

    if pesos:
        wr_pond, cobertura = winrate_ponderado(filas, pesos)
        media = sum(f["wr"] for f in filas) / len(filas)
        print("\n=== WINRATE ESPERADO EN LADDER (ponderado por meta) ===")
        if wr_pond is None:
            print("sin cobertura: ninguno de los mazos medidos tiene peso")
            return 0
        print(f"  ponderado : {100 * wr_pond:5.1f}%   sobre el "
              f"{100 * cobertura:.1f}% del meta cubierto")
        print(f"  sin pesar : {100 * media:5.1f}%   (media simple, para comparar)")

        # The weakest matchup is NOT where the most is lost: a 40% against an
        # archetype that is 1% costs less than an 80% against the one that is 41% of the field.
        # This orders by ladder points lost, which is where it is worth
        # investing the effort.
        sangria = [t for t in sorted(
            ((pesos.get(f["mazo"], 0.0) * (1 - f["wr"]), f) for f in filas),
            key=lambda t: -t[0],
        )[:3] if t[0] > 0]
        if sangria:
            print("\n  Donde se pierden mas puntos de ladder:")
            for cost, f in sangria:
                print(f"    {f['mazo']:<28} {100 * cost:5.2f} pts  "
                      f"(meta {100 * pesos.get(f['mazo'], 0.0):.0f}%, "
                      f"ganamos {100 * f['wr']:.1f}%)")
        if sin_peso:
            print(f"  aviso: {len(sin_peso)} mazo(s) sin peso, excluidos del "
                  f"ponderado: {', '.join(sorted(sin_peso)[:5])}"
                  + (" ..." if len(sin_peso) > 5 else ""))
        # The weighted prize differential: the metric with resolution. The
        # winrate against the bot is saturated (>93%) and cannot arbitrate a
        # change; the prizes do grade it.
        prem = [f for f in filas if f["dif_premios"] is not None]
        if prem:
            cob_p = sum(pesos.get(f["mazo"], 0.0) for f in prem)
            if cob_p > 0:
                dif_pond = sum(pesos.get(f["mazo"], 0.0) * f["dif_premios"]
                               for f in prem) / cob_p
                print(f"\n  DIFERENCIAL DE PREMIOS ponderado: {dif_pond:+.3f} "
                      f"por partida")
                print("  (premios que cobramos menos los que cobra el rival; "
                      "tiene resolucion donde el winrate ya no)")

        if base_by_deck:
            filas_base = [base_by_deck[f["mazo"]] for f in filas
                          if f["mazo"] in base_by_deck]
            wr_base, _ = winrate_ponderado(filas_base, pesos)
            if wr_base is not None:
                print(f"\n  baseline  : {100 * wr_base:5.1f}%   "
                      f"DELTA PONDERADO = {100 * (wr_pond - wr_base):+.2f} puntos")
                print("  (este delta, y no la media simple, es lo que decide "
                      "si el cambio gana partidas en ladder)")
            base_prem = [b for b in filas_base if b.get("dif_premios") is not None]
            if prem and base_prem:
                cob_b = sum(pesos.get(b["mazo"], 0.0) for b in base_prem)
                if cob_b > 0 and cob_p > 0:
                    dif_b = sum(pesos.get(b["mazo"], 0.0) * b["dif_premios"]
                                for b in base_prem) / cob_b
                    print(f"  premios baseline: {dif_b:+.3f}   "
                          f"DELTA DE PREMIOS = {dif_pond - dif_b:+.3f} por partida")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
