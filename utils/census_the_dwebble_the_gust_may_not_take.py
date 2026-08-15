"""How often the Dwebble the gust may not take is the only prize on the table.

THE BOARD IT COMES FROM (night of 15 August 2026,
`records/autopsy/crustle_wall_1_p247.json` turn 8, LOST):

    US (5 prizes)                        THEM (6 prizes)
    active  Dipplin 80/80 (1G)           active  Mega Kangaskhan ex 400/400
    bench   Bayleef, 3x Ogerpon ex,      bench   Dwebble 70, Dwebble 70,
            Applin                               Cornerstone Mask Ogerpon ex
    hand    Boss's Orders, Grass, Unfair Stamp, Dawn, Meowth ex, 2 Poke Pad...

*Do the Wave* is 20 x our five benched = 100 over a 70 HP Dwebble: a prize, and
one future wall fewer. The turn closed with END and nine cards in hand.

THE RULE THAT DECIDES IT IS DELIBERATE, and this census exists to scope it, not
to argue with it. `_boss_prize_rank` (main.py) skips the Dwebble outright in a
Crustle deck -- "log 86339758 step 98: Dwebble is vetoed as a gust target" -- so
`_boss_reason_with_prize` is False and `gust_without_purpose` vetoes the Boss's
at -1. The exclusion is UNCONDITIONAL, and the board above is the case it was
not written for: the body in front is one nothing of ours can dent, so the turn
is dead anyway and the Supporter is on its way to the discard with the hand.

WHAT IT COUNTS, per MAIN menu of ours in which the Boss's is a legal play:

    boss        menus where Boss's Orders is on the menu
    dwebble     ...where a Dwebble on their bench is one our ACTIVE knocks out
                this turn (the turn's own attachment included if unspent).
                This is the prize the exclusion is refusing
    front_mute  ...and where our active does NOT knock out the body in front:
                the gust is not competing with a prize we already have
    no_prize    ...and the turn took NO PRIZE: it either closed without
                attacking or swung for chip that knocked nothing out. THIS is
                the population the scope question is about -- a prize the gust
                may not take, on a turn that took none
    dead        ...and the narrower half of it: the turn closed with END

⚠️ WHICH LINE THE CRITERION NAMED, written before this file ran and NOT moved
afterwards: `dead` -- the turn closed with END -- BELOW 0.5 PER GAME against
Crustle means no code is touched. `no_prize` was added after the first 20 games
came back with `dead` at zero, and it is a WIDER question (a turn that swings
for chip took no prize either, and the gust it is being compared against takes
one). It is reported as context, never as a pass: a criterion that grows a
looser clause the moment the strict one fails is not a criterion.

⚠️ IT IS NOT A CONTROL GROUP. Every count here is a board TRAIT, not a decision
the agent would change, so a rule that acted on it would still need its own gate
with a `--control` arm at the same N ([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]).
What this answers is the cheaper question that comes first: is the window wide
enough to be worth a rule at all.

Usage:
    python utils/census_the_dwebble_the_gust_may_not_take.py --games 200
    python utils/census_the_dwebble_the_gust_may_not_take.py --games 200 \
        --opponent deck/real_opponents/crustle_wall_3.csv
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "tests", _ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp                                   # noqa: E402
from autopsy import play_recording                      # noqa: E402
from cg.api import OptionType, SelectContext            # noqa: E402

DEFAULT_OPPONENT = "deck/real_opponents/crustle_wall_1.csv"


class _P:
    """A Pokemon of the raw observation, wearing the interface main's
    calculators read. The same minimal adapter `utils/autopsy.py` uses."""

    def __init__(self, d):
        self.id = d["id"]
        self.hp = d.get("hp")
        self.maxHp = d.get("maxHp")
        self.energies = list(d.get("energies") or [])

        class _C:
            def __init__(self, dd):
                self.id = dd["id"]
        self.energyCards = [_C(c) for c in (d.get("energyCards") or [])]
        self.tools = [_C(c) for c in (d.get("tools") or [])]


def _our_best_damage(m, obs, target):
    """What our ACTIVE does to `target` this turn, the turn's attachment
    included when it is still unspent -- which is the projection the gust's own
    prize reading makes (`_bpr_active_can_ko`)."""
    cur = obs["current"]
    yo = cur["players"][cur["yourIndex"]]
    if not (yo.get("active") and yo["active"][0]):
        return 0
    act = yo["active"][0]
    bench = [b for b in (yo.get("bench") or []) if b]
    total_grass = sum(len(p.get("energies") or [])
                      for p in [act] + bench)
    hand = yo.get("hand") or []
    can_attach = (any(c["id"] == m.Basic_Grass_Energy for c in hand)
                  and not cur.get("energyAttached"))
    e = len(act.get("energies") or []) + (1 if can_attach else 0)
    a, o = _P(act), _P(target)
    base = m._attacker_base_damage(a.id, o, e, grass_scale=total_grass,
                                   teal_self_energy=e, bench_count=len(bench))
    if base <= 0:
        return 0
    meganium = any(p["id"] == m.Meganium for p in [act] + bench)
    return m._our_effective_damage(a, o, base, meganium, False)


def _is_dwebble(m, card_id):
    return card_id in (m.Dwebble_Grass, m.Dwebble_Fighting)


def census_game(m, decisiones):
    """The four counts, over one game's decisions of ours."""
    out = Counter()
    per_turn = {}
    for d in decisiones:
        per_turn.setdefault(d["obs"]["current"]["turn"], []).append(d)

    for _turn, ds in sorted(per_turn.items()):
        mains = [d for d in ds
                 if (d["obs"].get("select") or {}).get("context")
                 == int(SelectContext.MAIN)]
        if not mains:
            continue
        attacked = any(
            int(d["obs"]["select"]["option"][d["eleccion"][0]].get("type", -1))
            == int(OptionType.ATTACK)
            for d in mains if d["eleccion"])
        # A TURN THAT SWINGS FOR CHIP TOOK NO PRIZE EITHER, and the gust it is
        # being compared against takes one. The prize count of OUR side is read
        # off the last menu of the turn against the first: a `None` entry is a
        # prize still to take, so the pile SHRINKING is a knockout of ours.
        _first = mains[0]["obs"]["current"]
        _last = ds[-1]["obs"]["current"]
        def _pile(cur):
            side = cur["players"][cur["yourIndex"]]
            return sum(1 for p in (side.get("prize") or []) if p is None)
        took_a_prize = _pile(_last) < _pile(_first)

        for d in mains:
            obs = d["obs"]
            cur = obs["current"]
            yo = cur["players"][cur["yourIndex"]]
            op = cur["players"][1 - cur["yourIndex"]]
            hand = yo.get("hand") or []
            boss_on_menu = any(
                o.get("type") == int(OptionType.PLAY)
                and o.get("index") is not None
                and o["index"] < len(hand)
                and hand[o["index"]]["id"] == m.Boss_Orders
                for o in obs["select"]["option"])
            if not boss_on_menu:
                continue
            out['boss'] += 1

            dwebble = [b for b in (op.get("bench") or [])
                       if b and _is_dwebble(m, b["id"])
                       and _our_best_damage(m, obs, b) >= (b.get("hp") or 0) > 0]
            if not dwebble:
                continue
            out['dwebble'] += 1

            front = op["active"][0] if (op.get("active") and op["active"][0]) else None
            if front is None:
                continue
            if _our_best_damage(m, obs, front) >= (front.get("hp") or 0) > 0:
                continue          # the prize in front is already ours
            out['front_mute'] += 1

            if not took_a_prize:
                out['no_prize'] += 1
            if not attacked:
                out['dead'] += 1
            break                 # one menu per turn is enough: it is the turn
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--opponent", default=DEFAULT_OPPONENT)
    ap.add_argument("--progress", type=int, default=50)
    args = ap.parse_args(argv)

    import main as m
    from opponent_bot import OpponentBot

    agent_state = sp.load_agent(_ROOT / "main.py", "arm_census_dwebble")
    own_deck = sp.read_deck()
    opponent_deck = sp.read_deck(_ROOT / args.opponent)

    counts = Counter()
    board = Counter()
    for i in range(args.games):
        result, decisiones, _final = play_recording(
            agent_state, OpponentBot(), own_deck, opponent_deck, seat=i % 2)
        board[result] += 1
        counts.update(census_game(m, decisiones))
        if args.progress and (i + 1) % args.progress == 0:
            print(f"  ... {i + 1}/{args.games}", flush=True)

    n = args.games or 1
    print(f"\n{args.games} partidas contra {Path(args.opponent).stem}: "
          f"{dict(board)}")
    print(f"  menus con el Boss's jugable                {counts['boss']:6d} "
          f"({counts['boss'] / n:7.2f}/partida)")
    print(f"  ...con un Dwebble suyo que MATAMOS hoy     {counts['dwebble']:6d} "
          f"({counts['dwebble'] / n:7.2f}/partida)")
    print(f"  ...y sin premio en el cuerpo de delante    {counts['front_mute']:6d} "
          f"({counts['front_mute'] / n:7.2f}/partida)")
    print(f"  ...y el turno NO COBRO PREMIO              {counts['no_prize']:6d} "
          f"({counts['no_prize'] / n:7.2f}/partida)   (contexto, mas ancho)")
    print(f"  ...y el turno cerro con END                {counts['dead']:6d} "
          f"({counts['dead'] / n:7.2f}/partida)   <- EL CRITERIO ESCRITO")
    if counts['dead'] / n < 0.5:
        print("\nPOR DEBAJO DEL CRITERIO (0.50/partida, escrito antes de "
              "correr esto): no se toca el codigo.")
    else:
        print("\nPOR ENCIMA DEL CRITERIO: la ventana existe y la regla se "
              "escribe, con su gate y su --control a la misma N.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
