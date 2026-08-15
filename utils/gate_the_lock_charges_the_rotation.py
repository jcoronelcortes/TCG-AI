"""Two-arm gate for "the lock charges the rotation, not the retreat", isolated to
THAT reading and nothing else in the working tree.

THE RULE. The anti-Cubchoo conservation veto
([[anti-cubchoo-no-retirada-pivote-conservar-energia]]) removes the voluntary
retreat-pivot against a deck that mutes our Active every turn, because every
retreat that discards energy bleeds the resource the control denies us. Its two
exemptions were closed BY CARD ID -- `_cubchoo_lock_stuck` on `== Hydrapple_ex`,
`_cubchoo_mute_cashes_prize` on `NON_ATTACKER_ENERGY_WASTE_IDS` -- and the body
they excluded on purpose, the charged Teal Mask Ogerpon ex, is the one that
stands in front most of the time.

`_cubchoo_mute_rotates` asks the question one step further out. What the veto is
protecting is not this turn's fee but NEXT turn's, the one the lock will charge
on whatever we promote, so it exempts when the cheapest body that CASHES THE
PRIZE is no more expensive to rotate out than the body we are retreating.
`PROMO_KO_ROTATION` is the same number read by the promotion that follows: among
knockers, the seat goes to the one the lock can charge least.

THE BOARD IT COMES FROM (user, `records/registro_010_pasos_079_hasta_081.json`
step 81, episode 93149196 vs a Cubchoo/Dunsparce stall deck, WON). Our Teal Mask
Ogerpon ex muted with 4 Grass on it, its twin charged to 4 effective on the
bench, a 70 HP Cubchoo in front that Myriad Leaf Shower does 180 to. The turn
closed with END -- and so did turns 12, 14, 16 and 18: the same frozen board,
five turns, zero prizes.

WHAT THE PASS OF registro_004 p47 STILL COSTS, and why it stays. There the muted
active is ALSO a charged Teal Mask Ogerpon ex, so no reading of the body in front
separates the two boards; the only bench body that knocks out is a Hydrapple ex
at retreat 3, and promoting it jams our most expensive body into the lock. That
PASS is preserved, pinned by
`tests/test_the_lock_charges_the_rotation_not_the_retreat.py::test_the_pass_of_p47_still_stands_on_its_own_board`.

WHY NOT `selfplay.py --base HEAD`. The baseline it exports is the git ref, and
this working tree carries other work: the delta would answer "everything
uncommitted", not "this reading". Both arms here are the SAME tree loaded twice,
with `CUBCHOO_MUTE_ROTATION` switched off in one of them.

THE CRITERION, WRITTEN BEFORE THE NUMBER EXISTS. The population is thin by
construction -- it needs the lock ON US, a retreat legal, a benched body that
knocks out, and that body no dearer to rotate than the one in front -- and the
reference bot piloting a Cubchoo list is a control that cannot knock us out, so
these games end saturated. That is exactly the wall the parent rule hit: 4 flips
in 40 759 decisions and three self-play gates of the same change reading -3.5,
-2.0 and +0.3 ([[matchpoint-el-gate-no-arbitra-mide-la-frecuencia]]). So:

  * run `--census` FIRST. If the board is rarer than ~1 in 100 decisions the
    honest report is the census and the corpus audit, not a winrate.
  * ALWAYS run `--control` at the same n. Both arms neutralised is the same code
    twice, so whatever separation it shows is that run's noise floor. A delta
    that does not clear it is not a delta.
  * NEUTRAL DOES NOT ORDER A REVERT here: the change is a strict no-op wherever
    the lock is absent, our Active can attack, or no benched body finishes their
    Active -- which the unit tests pin and the frozen corpus confirms (6 flips,
    all in the one episode this came from, none anywhere else). It orders the
    MARK. A LOSS that clears the floor above orders the revert.

Usage:
    python utils/gate_the_lock_charges_the_rotation.py --census
    python utils/gate_the_lock_charges_the_rotation.py --games 1000
    python utils/gate_the_lock_charges_the_rotation.py --games 1000 --control
"""

import argparse
import math
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402

# THE POPULATION IS THE LISTS THAT CARRY THE LOCK, because everywhere else
# `op_is_cubchoo_deck` is False and both arms are the same agent. The last two
# are controls where Cubchoo is absent: they are here to catch a change that
# leaks OUT of the matchup, which is the failure mode a no-op has.
DEFAULT_DECKS = (
    "deck/opponents/cornerstone_cubchoo.csv",
    "deck/opponents/crustle_cubchoo_spheal.csv",
    "deck/opponents/crustle_kangaskhan.csv",
    "deck/opponents/alakazam.csv",
)


def neutralise(agent_module):
    """Switch the reading off in `agent_module`, permanently, in place.

    Both halves hang off this one flag: `_cubchoo_mute_rotates` is built inside
    `agent()` from main.py's own globals, and `_cubchoo_ko_rotation_min` -- the
    number the promotion penalty reads -- is left None by the same guard, so the
    `PROMO_KO_ROTATION` branch in ptcg/turn/options/card.py cannot fire either.
    One assignment switches the retreat and the promotion together, which is
    right: they are one turn and there is no measuring them apart.
    """
    agent_module.CUBCHOO_MUTE_ROTATION = False
    return agent_module


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero), so
    the arms are asked directly for the flag the run will compare against.
    """
    if candidate is base:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    if base.CUBCHOO_MUTE_ROTATION:
        raise SystemExit("el brazo baseline NO esta neutralizado: no hay nada que medir")
    if candidate.CUBCHOO_MUTE_ROTATION is bool(control):
        raise SystemExit("el brazo candidato no esta como dice estar "
                         f"(control={bool(control)}, "
                         f"lectura={candidate.CUBCHOO_MUTE_ROTATION})")
    print(f"procedencia OK (candidato {'NEUTRALIZADO: control' if control else 'con la lectura'}, "
          f"baseline sin ella)\n", flush=True)


def census(games, decks, progress):
    """HOW OFTEN THE BOARD THE READING IS ABOUT ACTUALLY HAPPENS.

    Four nested numbers, and the gaps between them are the whole point:

      matchup    decisions taken with the lock in their deck at all;
      mute       ...of those, the ones where OUR Active cannot attack;
      prize      ...of those, the ones where a benched body knocks their Active
                 out and a retreat is legal -- a turn with a prize in it;
      rotates    ...of those, the ones where the cheapest such body is no dearer
                 to rotate than the one in front. That last line is the
                 population: everywhere above it the two arms are identical.

    The corpus flips six decisions and all six are one game, so the exposure has
    to be measured where the boards come from: self-play against the lists that
    carry the card.
    """
    from opponent_bot import OpponentBot

    agent = sp.load_agent(_ROOT / "main.py", "arm_census")
    counts = Counter()
    plain = agent._bench_ko_cheapest_retreat

    def counted(my_state, target, meganium_active, bench_count,
                retreat_grass_after, neutral_zone):
        out = plain(my_state, target, meganium_active, bench_count,
                    retreat_grass_after, neutral_zone)
        counts['asked'] += 1
        if out is not None:
            counts['prize'] += 1
        return out

    # The helper is reached through the AGENT's own reference, not through
    # `sys.modules`: `load_agent` gives each arm its own `ptcg` tree and then
    # returns the ambient one, so a scan there rebinds the copy nobody plays with
    # and the census reports a confident zero. If the binding is missing this
    # raises rather than reporting that zero.
    _globals = agent.agent.__globals__
    if _globals.get('_bench_ko_cheapest_retreat') is not plain:
        raise SystemExit("el censo no alcanza al consumidor: mediria cero")
    _globals['_bench_ko_cheapest_retreat'] = counted
    try:
        total = 0
        for rel in decks:
            their = sp.read_deck(_ROOT / rel)
            counts.clear()
            sp.torneo(agent, OpponentBot(), games,
                      progress=progress or None, deck_base=their)
            asked, prize = counts['asked'], counts['prize']
            total += prize
            print(f"{Path(rel).stem:36s} mudos con retirada {asked:7d} "
                  f"({asked / games:7.2f}/partida)   CON PREMIO EN BANCA "
                  f"{prize:6d} ({prize / games:6.2f}/partida)", flush=True)
        print(f"\nCENSO DE DISPARO: {total / (games * len(decks)):.2f} tableros "
              f"con premio en banca por partida de media.")
        if total / (games * len(decks)) < 0.01:
            print("AVISO: el evento es RARO. Con una exposicion asi el gate de "
                  "self-play puede no resolver la diferencia por muchas partidas "
                  "que juegue; el informe honesto es este censo, no un winrate.")
    finally:
        _globals['_bench_ko_cheapest_retreat'] = plain
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
                    help="how often the board happens at all (run this first)")
    args = ap.parse_args(argv)

    decks = (args.opponent.split(",") if args.opponent else list(DEFAULT_DECKS))

    if args.census:
        return census(args.games, decks, args.progress)

    from opponent_bot import OpponentBot

    candidate = sp.load_agent(_ROOT / "main.py", "arm_with")
    base = neutralise(sp.load_agent(_ROOT / "main.py", "arm_without"))
    if args.control:
        neutralise(candidate)
    provenance(candidate, base, args.control)

    tot_c = tot_b = 0
    for rel in decks:
        their = sp.read_deck(_ROOT / rel)
        c = sp.torneo(candidate, OpponentBot(), args.games,
                      progress=args.progress or None, deck_base=their)
        b = sp.torneo(base, OpponentBot(), args.games,
                      progress=args.progress or None, deck_base=their)
        cw, bw = c['candidate'], b['candidate']
        tot_c += cw
        tot_b += bw
        d, z, p = wilson_delta(cw, args.games, bw, args.games)
        # The PRIZE DIFFERENTIAL is the metric with resolution left once the
        # winrate saturates against the bot (docs/improving-the-agent.md), and
        # against a thin population it is the one that moves first.
        _cp = (c['premios_candidato'] - c['premios_base']) / max(1, c['partidas_con_premios'])
        _bp = (b['premios_candidato'] - b['premios_base']) / max(1, b['partidas_con_premios'])
        print(f"{Path(rel).stem:36s} con {cw:5d}/{args.games}  sin {bw:5d}/{args.games}  "
              f"delta {100 * d:+6.2f} pp  (z={z:+5.2f} p={p:.3f})   "
              f"premios {_cp:+.2f} vs {_bp:+.2f} ({_cp - _bp:+.2f})", flush=True)

    n = args.games * len(decks)
    d, z, p = wilson_delta(tot_c, n, tot_b, n)
    print(f"\nTOTAL  con {tot_c}/{n}  sin {tot_b}/{n}  "
          f"delta {100 * d:+.2f} pp  (z={z:+.2f} p={p:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
