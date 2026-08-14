"""Two-arm gate for "the match-point veto yields to the body that can walk
back", isolated to THAT exemption and nothing else in the working tree.

THE RULE. `_mp_price_ends_the_game` removes from the promotion menu any body
whose price is their remaining pile and whose death their projected blow
delivers -- correctly, because that promotion IS the game. What it does not ask
is WHEN the blow arrives. The forced promotion resolves at the END of their
turn, so a whole turn of ours sits between the body going up and their reply,
and a finisher that can pay its own retreat out of the energy it already
carries does not have to be standing there when the reply comes.
`PROMOTE_BET_OUTLIVES_MATCH_POINT` is that exemption, and it reaches exactly one
body: the `_promote_setup_ko_attacker` the selector already named.

WHY IT WAS WORTH ASKING AT ALL. `registro_006` step 77 vs Archaludon ex
(episode 92848103, LOST): six prizes to two, a benched Teal Mask Ogerpon ex one
attachment from finishing their 240 HP Archaludon -- 270 through the Grass
resistance is exactly 240 -- with a Lillie's Determination in hand to go looking
for the Grass and one physical Grass on the body to pay its own retreat if it
does not come. The selector named it at +9500, the veto overwrote it with
-30000, and the front went to a Tapu Bulu that needs four energy, carries none
and costs three to retreat.

WHY NOT `selfplay.py --base HEAD`. The baseline it exports is the git ref, and
the working tree normally carries other work -- here it carries route (f) of the
same selector -- so that delta would answer "everything uncommitted", not "this
exemption". Both arms below are the SAME tree loaded twice, with
`PROMOTE_BET_OUTLIVES_MATCH_POINT` switched off in one of them.

THE CENSUS IS THE HONEST REPORT, and `--census` is what to run first. The
frozen fifty flip ZERO decisions and the harvested records exactly one, so a
winrate is being asked to resolve an event it will almost never see. The census
counts the population (our forced promotions) and the window (the ones the two
arms answer differently) by asking BOTH arms the same observation -- the same
side-by-side walk the rules oracle uses, so neither arm's belief drifts.

ALWAYS RUN `--control` AT THE SAME N. Both arms neutralised is the same code
twice, so whatever separation it shows is that run's noise floor. A delta that
does not clear it is not a delta
([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]).

THE CRITERION, WRITTEN BEFORE THE NUMBER EXISTS. This is not a preference being
tuned: it is a veto whose premise -- "their blow removes this body" -- is false
whenever the body can step aside first, and it is a STRICT NO-OP on every board
where the finisher cannot pay its retreat, which the unit tests pin. So NEUTRAL
DOES NOT ORDER A REVERT here: it orders the mark, the same standing the
Cornerstone, Ultra Ball and reversible-bet rules carry. A LOSS that clears the
noise floor does order the revert.

Usage:
    python utils/gate_the_veto_yields_to_the_body_that_walks_back.py --census
    python utils/gate_the_veto_yields_to_the_body_that_walks_back.py --games 1000
    python utils/gate_the_veto_yields_to_the_body_that_walks_back.py --games 1000 --control
"""

import argparse
import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402

# THE POPULATION IS THE DECKS THAT REACH THEIR MATCH POINT AGAINST US WITH A
# BIG BODY IN FRONT, because everywhere else the veto never fires and both arms
# are the same agent. The record's own list first, then the archetypes whose
# blow removes a 210 HP ex in one hit, plus two controls where the rule cannot
# fire -- they are here to catch a change that leaks OUT of the matchup, which
# is the failure mode a no-op has.
DEFAULT_DECKS = (
    "deck/opponents/archaludon.csv",
    "deck/opponents/marnie_grimmsnarl.csv",
    "deck/opponents/alakazam.csv",
    "deck/opponents/crustle_kangaskhan.csv",
    "deck/opponents/dragapult.csv",
)


def neutralise(agent_module):
    """Switch the exemption off in `agent_module`, permanently, in place.

    The flag is read from main.py's own globals when `_promo_bet_walks_back` is
    built, so rebinding the module attribute puts the veto back the way it was
    and leaves every other promotion rule -- routes (a)-(f) of the selector
    included -- exactly as it is.
    """
    agent_module.PROMOTE_BET_OUTLIVES_MATCH_POINT = False
    return agent_module


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero), so
    the arms are asked directly for the flag the run will compare against.
    """
    if candidate is base:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if base.PROMOTE_BET_OUTLIVES_MATCH_POINT:
        raise SystemExit("el brazo baseline NO esta neutralizado: no hay nada que medir")
    if candidate.PROMOTE_BET_OUTLIVES_MATCH_POINT is bool(control):
        raise SystemExit(
            "el brazo candidato no esta como dice estar "
            f"(control={bool(control)}, "
            f"bandera={candidate.PROMOTE_BET_OUTLIVES_MATCH_POINT})")
    print(f"procedencia OK (candidato "
          f"{'NEUTRALIZADO: control' if control else 'con la salida'}, "
          f"baseline sin ella)\n", flush=True)


def _is_forced_promotion(obs):
    """This menu is the one the rule speaks at: our active spot is EMPTY."""
    cur = obs.get("current") or {}
    sel = obs.get("select") or {}
    if sel.get("context") != 4:
        return False
    yo = cur.get("yourIndex")
    try:
        return not (cur.get("players") or [])[yo].get("active")
    except (IndexError, TypeError, KeyError):
        return False


def census(games, decks, progress):
    """HOW MANY FORCED PROMOTIONS THE EXEMPTION CHANGES, per game.

    The corpus flips one decision, so the exposure has to be measured where the
    boards come from -- self-play. The candidate arm plays; at every one of our
    decisions the BASE arm is asked the same observation as well, so both build
    the same belief from the same history and the disagreement is the rule's and
    nobody else's. The first number is the population (forced promotions), the
    second is the window (the ones the two arms answer differently).
    """
    from opponent_bot import OpponentBot

    candidate = sp.load_agent(_ROOT / "main.py", "census_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "census_without"))
    provenance(candidate, base, False)

    counts = {"menus": 0, "promos": 0, "changed": 0}
    played = candidate.agent

    def watched(obs):
        out = played(obs)
        try:
            other = list(base.agent(obs))
        except Exception:                       # noqa: BLE001 - a blind arm never blocks the game
            return out
        counts["menus"] += 1
        if _is_forced_promotion(obs):
            counts["promos"] += 1
            if list(out) != other:
                counts["changed"] += 1
        return out

    candidate.agent = watched
    try:
        total_p = total_c = 0
        for rel in decks:
            their = sp.read_deck(_ROOT / rel)
            for k in counts:
                counts[k] = 0
            sp.torneo(candidate, OpponentBot(), games,
                      progress=progress or None, deck_base=their)
            total_p += counts["promos"]
            total_c += counts["changed"]
            print(f"{Path(rel).stem:32s} decisiones {counts['menus']:7d}   "
                  f"PROMOCIONES FORZADAS {counts['promos']:5d} "
                  f"({counts['promos'] / games:5.2f}/partida)   "
                  f"CAMBIA {counts['changed']:4d} "
                  f"({counts['changed'] / games:5.3f}/partida)", flush=True)
        n = games * len(decks)
        print(f"\nCENSO DE DISPARO: {total_p} promociones forzadas, "
              f"{total_c} cambiadas ({total_c / n:.3f} por partida).")
        if total_c / n < 0.01:
            print("AVISO: el evento es RARO. Con una exposicion asi el gate de "
                  "self-play puede no resolver la diferencia por muchas partidas "
                  "que juegue; el informe honesto es este censo y el oraculo de "
                  "reglas, no un winrate.")
    finally:
        candidate.agent = played
    return 0


def wilson_delta(w1, n1, w2, n2):
    """Two-proportion z test. It ASSUMES independent Bernoulli, which the bot
    does not honour -- so read the p it prints as an optimistic bound."""
    if not n1 or not n2:
        return 0.0, 0.0, 1.0
    p1, p2 = w1 / n1, w2 / n2
    p = (w1 + w2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) or 1e-9
    z = (p1 - p2) / se
    return p1 - p2, z, 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--progress", type=int, default=500)
    ap.add_argument("--opponent", default=None,
                    help="csv of an opponent deck; repeatable via commas")
    ap.add_argument("--control", action="store_true",
                    help="neutralise BOTH arms: the noise floor of this very run")
    ap.add_argument("--census", action="store_true",
                    help="how often the exemption changes a promotion (run this first)")
    args = ap.parse_args(argv)

    decks = (args.opponent.split(",") if args.opponent else list(DEFAULT_DECKS))
    decks = [d for d in decks if (_ROOT / d).exists()]
    if not decks:
        raise SystemExit("ninguna de las listas pedidas existe")

    if args.census:
        return census(args.games, decks, args.progress)

    from opponent_bot import OpponentBot

    candidate = sp.load_agent(_ROOT / "main.py", "arm_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "arm_without"))
    if args.control:
        neutralise(candidate)
    provenance(candidate, base, args.control)

    label_c = "con la salida" + (" (NEUTRALIZADO: control)" if args.control else "")

    totals = [0, 0, 0, 0]
    for rel in decks:
        their = sp.read_deck(_ROOT / rel)
        name = Path(rel).stem
        rows = []
        for agent in (candidate, base):
            st = sp.torneo(agent, OpponentBot(), args.games,
                           progress=args.progress or None, deck_base=their)
            rows.append((st["candidate"], st["candidate"] + st["base"], st))
        (wc, nc, stc), (wb, nb, stb) = rows
        totals[0] += wc; totals[1] += nc; totals[2] += wb; totals[3] += nb
        d, z, p = wilson_delta(wc, nc, wb, nb)
        print(f"{name:32s} {label_c} {100 * wc / nc:5.2f}%   sin ella "
              f"{100 * wb / nb:5.2f}%   delta {100 * d:+5.2f} pts  z={z:5.2f} p={p:.3f}   "
              f"premios {sp.prizes_per_game(stc)[0]:.2f} vs {sp.prizes_per_game(stb)[0]:.2f}   "
              f"forfeits {stc['errores_candidato']}/{stb['errores_candidato']}",
              flush=True)

    d, z, p = wilson_delta(*totals)
    print(f"\nAGREGADO ({totals[1]} partidas por brazo)  "
          f"{100 * totals[0] / totals[1]:.2f}% vs {100 * totals[2] / totals[3]:.2f}%   "
          f"DELTA {100 * d:+.2f} pts  z={z:.2f}  p={p:.3f} (cota optimista)")
    if args.control:
        print("Esto es el SUELO DE RUIDO: mismo codigo en los dos brazos. "
              "Un delta real tiene que superarlo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
