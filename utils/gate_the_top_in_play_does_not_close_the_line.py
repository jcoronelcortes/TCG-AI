"""Two-arm gate for "a copy of a line's TOP in play does not close that line",
isolated to THAT reading and nothing else in the working tree.

THE RULE. `_eval_ub_best_target` opens its two evolution ladders with
`if not meganium_in_play:` and `if not has_hydrapple:`. Both say the same thing
-- "we already have one of those, there is nothing to search for" -- and both are
wrong about a board that still has a BODY waiting underneath: the second copy is
a second attacker, not a duplicate. The per-target gates of `_offer` already
refuse anything the hand covers, anything with no bench seat and any evolution
nothing can wear today, so the species gates add exactly one refusal on top of
those, and it is that one.

The candidate lifts them as a LAST RESORT only: the ladders are asked a second
time, for the line whose top is in play, when the first pass left the Ultra Ball
with NO target at all -- the state that prices it at `SCORE_CANCEL` and hands the
turn to the attack. Asked unconditionally instead, a second Meganium at 1000
outranks targets the board wanted more, and thirteen curated boards said so the
first time it was tried. The FETCH menu reads the same switch through
`_line_closed_by_its_top()`, so the two menus cannot buy the Item for one target
and spend it on another.

THE BOARD IT COMES FROM (user, `records/registro_007_pasos_060_hasta_074.json`
step 72, episode 93493222 vs Marnie -- WON in spite of this). Turn 7, bench FULL,
our Forest of Vitality in play, Hydrapple ex active, a **Dipplin at 2 effective
energies** on the bench and the second Hydrapple ex in the deck. Menu: two Ultra
Balls, the attack, pass. Both Ultra Balls scored **-100** and not for their price
-- every `_ub_cancel_*` came back False -- so the turn attacked and the Dipplin
stayed an 80 HP body. With the switch on, the same board prices the Ultra Ball at
**12250** and plays it.

WHAT THE READING COSTS, stated before the number exists. An Ultra Ball that was
dead becomes live, and a live Ultra Ball is worth 10000-12500 -- ABOVE plays that
take a prize but score lower, such as the wall retreat of `_wall_ko_promote`
(6700). It does not remove those plays from the turn (an Item does not end it),
but it does go first and it does spend two cards from hand on the way. That
band inversion is pre-existing and is not this gate's to fix; what this gate
measures is whether exposing it costs games.

THE CRITERION, WRITTEN BEFORE THE NUMBER EXISTS.

  * run `--census` FIRST (`utils/census_the_top_in_play_does_not_close_the_line.py`)
    and read it against this gate's resolution: 0.09-0.16 turns a game.
  * ALWAYS run `--control` at the same n. Both arms neutralised is the same code
    twice, so whatever separation it shows is that run's noise floor -- on this
    project the Marnie floor has measured 1.50 points at z=3.13 with identical
    code ([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]).
    A delta that does not clear its own control is not a delta.
  * A LOSS that clears the floor orders the REVERT, and that outcome is live
    here: the reading spends an Item and two cards to go first on boards where
    something else was already winning the turn.
  * NEUTRAL orders the MARK, not the merge, while the eleven curated boards
    below still disagree with it. They are the ones that price the change:

        tests/test_lethal_relief_against_the_wall.py            (3)
        tests/test_the_pivot_wall_must_survive_the_reply.py     (2)
        tests/test_main_regressions_4.py                        (2)
        tests/test_boss_the_chip_is_not_a_prize.py              (2)
        tests/test_main_regressions_6.py                        (1)
        tests/test_the_front_spot_among_the_ones_that_knock_out.py (1)

    Every one of them pins the FIRST option of a menu, and on each the change
    puts the Ultra Ball ahead of a play that is still available afterwards. That
    is an argument, not a measurement, and it is exactly why the gate decides.

Usage:
    python utils/gate_the_top_in_play_does_not_close_the_line.py --games 1000
    python utils/gate_the_top_in_play_does_not_close_the_line.py --games 1000 --control
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

# THE POPULATION IS OUR OWN BOARD, not a matchup: the reading fires on the shape
# of our lines and never asks who is across the table. The list is a SPREAD --
# the deck that produced the board, the wall that makes the Meganium/Dipplin
# rungs the answer (where the census puts most of its Dipplin hits), a disruptor
# that empties the hand and a fast deck that ends games before the second copy
# matters.
DEFAULT_DECKS = (
    "deck/opponents/marnie_grimmsnarl.csv",
    "deck/opponents/crustle_great_tusk_nz.csv",
    "deck/opponents/alakazam.csv",
    "deck/opponents/dragapult.csv",
)

_SWITCH = "TOP_IN_PLAY_DOES_NOT_CLOSE_THE_LINE"


def _ub_ns(agent_module):
    """`ptcg.decision.ultra_ball` as THIS arm owns it, reached by reference.

    NOT through `sys.modules`: `selfplay.load_agent` drops the arm's `ptcg`
    branch and restores the ambient tree as soon as the load finishes, so a
    lookup by name hands back a copy nobody plays with -- and a gate that
    neutralises the wrong copy measures its own noise floor and calls it a
    result. main.py binds `_eval_ub_best_target` by star-import, so the arm's
    own namespace is one `__globals__` hop from `agent`.
    """
    return agent_module.agent.__globals__['_eval_ub_best_target'].__globals__


def neutralise(agent_module):
    """Switch the reading off in `agent_module`, permanently, in place.

    ONE assignment covers both menus: the PLAY branch reads the flag directly
    and the FETCH ladders read it through `_line_closed_by_its_top()`, which
    resolves it from this same namespace at call time.
    """
    ns = _ub_ns(agent_module)
    if _SWITCH not in ns:
        raise SystemExit("el gate no alcanza al interruptor: mediria cero")
    ns[_SWITCH] = False
    return agent_module


def provenance(candidate, base, control):
    """Refuse to measure two arms that are secretly the same agent.

    The gate has been blind before (`selfplay --base` used to share the whole
    `ptcg` package between arms, so any change there measured exactly zero), so
    the arms are asked for the flag directly, through the same reference walk
    `neutralise` writes through.
    """
    if candidate is base:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    _cand = _ub_ns(candidate)[_SWITCH]
    if _ub_ns(base)[_SWITCH]:
        raise SystemExit("el brazo baseline NO esta neutralizado: no hay nada que medir")
    if _cand is bool(control):
        raise SystemExit("el brazo candidato no esta como dice estar "
                         f"(control={bool(control)}, lectura={_cand})")
    print(f"procedencia OK (candidato {'NEUTRALIZADO: control' if control else 'con la lectura'}, "
          f"baseline sin ella)\n", flush=True)


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
    args = ap.parse_args(argv)

    decks = (args.opponent.split(",") if args.opponent else list(DEFAULT_DECKS))

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
        print(f"{Path(rel).stem:32s} con {cw:5d}/{args.games}  sin {bw:5d}/{args.games}  "
              f"delta {100 * d:+6.2f} pp  (z={z:+5.2f} p={p:.3f})   "
              f"premios {_cp:+.2f} vs {_bp:+.2f} ({_cp - _bp:+.2f})", flush=True)

    n = args.games * len(decks)
    d, z, p = wilson_delta(tot_c, n, tot_b, n)
    print(f"\nTOTAL  con {tot_c}/{n}  sin {tot_b}/{n}  "
          f"delta {100 * d:+.2f} pp  (z={z:+.2f} p={p:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
