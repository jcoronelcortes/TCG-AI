"""How often the ACTIVE SEAT is what pays for the promoted body's attack.

THE READING (`PROMOTE_SEAT_UNLOCKS_ITS_CHARGE`, `_promoted_grass_charges_eff`).
Every projection of a forced promotion used to price the body it brings up with
ONE charge, the manual attachment. That is half of what the promotion buys:
*Teal Dance* reads "once during your turn, IF THIS POKEMON IS IN THE ACTIVE
SPOT, you may attach a Basic Grass Energy from your hand to it", so on the bench
it is dead wood and the promotion is the act that switches it on. A body two
Grass short of its attack cost read as one Grass short with one route to pay it
-- mute -- and `_attacker_base_damage` returns 0 below the requirement, so a
finisher was priced at zero (user, `records/registro_004_pasos_038_hasta_047.json`
step 47, episode 93166555, LOST: their Teal Mask Ogerpon ex knocked out our Tapu
Bulu, we held two Grass, our own Ogerpon ex sat on the bench at 1/3 and their
active carried FOUR energy -- 30+30x(3+4) = 240 over its 210 HP, two prizes, on
our turn -- and a 40 HP Applin took the seat).

WHY A CENSUS AND NOT A WINRATE. The whole golden corpus moves ONE decision (79
compared, 1 flip, and it is that step 47), which is exactly the shape of change
a self-play winrate cannot resolve: the noise floor of this harness is around
half a point and a rule that fires on a fraction of the promotions after a
knockout cannot clear it. What arbitrates is how OFTEN the seat is the thing
that pays, and what the answer would have been without it -- which is what this
counts.

WHAT IT COUNTS, per call to the promotion projection:

    asked      candidates priced by a forced promotion (`_forced_ko_promote`),
               the only context that claims the seat's charge.
    seat       ...of those, the ones where the dance actually ADDS energy the
               manual attachment alone does not give. Everywhere else the two
               arms return the same number, by construction.
    arms       ...of those, the ones where the extra energy carries the body
               from BELOW its attack cost to at or above it: the population the
               reading is really about, since that is where the projection goes
               from "mute" to "attacker" and a finisher stops being priced at
               zero.

Two sources, answering different questions:

    --records   the recorded games in `records/` (default). Exact and in slow
                motion: it replays our seat menu by menu with the agent as it
                stands today, and names the steps.
    --games N   self-play. Wider, and the only way to reach boards the corpus
                never recorded.

Usage:
    python utils/census_the_seat_unlocks_its_charge.py
    python utils/census_the_seat_unlocks_its_charge.py --games 1000
    python utils/census_the_seat_unlocks_its_charge.py --games 1000 \
        --opponent competitor_decks_500/<list>.csv

Reproduce the "before" column by switching the reading off, which is what its
named flag is for:

    python -c "import main; main.PROMOTE_SEAT_UNLOCKS_ITS_CHARGE = False; ..."

Related: `tests/test_the_promotion_counts_the_charge_the_seat_unlocks.py` pins
the record itself, and `tests/golden_corpus.py` is what said the flip is one.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "utils"), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _instrument(agent_module, counts):
    """Wrap the projection where its CONSUMERS see it, and prove we reached it.

    The helper is reached through the agent's OWN global binding (main.py does
    `from ptcg.calc.energy import *`), not through `sys.modules`: `load_agent`
    gives each arm its own `ptcg` tree, so rebinding the ambient module patches
    a copy nobody plays with and the census reports a confident zero. If the
    binding is not there this raises instead of reporting that zero.
    """
    plain = agent_module._promoted_grass_charges_eff
    req_table = agent_module.AGENT_STATE.ATTACK_ENERGY_REQ

    def counted(candidate, hand_grass, manual_open, abilities_off=False,
                seat_unlocks=True, deficit=0):
        out = plain(candidate, hand_grass, manual_open, abilities_off,
                    seat_unlocks, deficit)
        if not seat_unlocks:
            return out
        counts['asked'] += 1
        without = plain(candidate, hand_grass, manual_open, abilities_off,
                        False, deficit)
        if out > without:
            counts['seat'] += 1
            have = len(getattr(candidate, 'energies', None) or [])
            req = req_table.get(getattr(candidate, 'id', None))
            if req is not None and have + without < req <= have + out:
                counts['arms'] += 1
        return out

    globals_ = agent_module.agent.__globals__
    if globals_.get('_promoted_grass_charges_eff') is not plain:
        raise SystemExit("el censo no alcanza al consumidor: mediria cero")
    globals_['_promoted_grass_charges_eff'] = counted
    return globals_, plain


def census_records(verbose):
    import golden_corpus as gc

    agent_module = gc._main_mod()
    counts = Counter()
    globals_, plain = _instrument(agent_module, counts)
    try:
        menus = 0
        for path in gc.record_files():
            gc.reset_agent(agent_module)
            before = dict(counts)
            gc.replay_record(agent_module, path)
            menus += 1
            if verbose:
                delta = {k: counts[k] - before.get(k, 0)
                         for k in ('asked', 'seat', 'arms')}
                if delta['seat']:
                    print(f"  {path.name:44s} preguntas {delta['asked']:4d}  "
                          f"la danza suma {delta['seat']:3d}  "
                          f"ARMA {delta['arms']:3d}", flush=True)
    finally:
        globals_['_promoted_grass_charges_eff'] = plain
    print(f"\nregistros: {menus} ficheros")
    _report(counts, menus, unit="registro")
    return 0


def census_selfplay(games, opponent, progress):
    import selfplay as sp
    from opponent_bot import OpponentBot

    agent_module = sp.load_agent(_ROOT / "main.py", "arm_census")
    counts = Counter()
    globals_, plain = _instrument(agent_module, counts)
    try:
        their = sp.read_deck(_ROOT / opponent) if opponent else None
        sp.torneo(agent_module, OpponentBot(), games,
                  progress=progress or None, deck_base=their)
    finally:
        globals_['_promoted_grass_charges_eff'] = plain
    print(f"\nself-play: {games} partidas contra "
          f"{opponent or 'deck.csv (espejo del bot)'}")
    _report(counts, games, unit="partida")
    return 0


def _report(counts, denom, unit):
    asked, seat, arms = counts['asked'], counts['seat'], counts['arms']
    denom = denom or 1
    print(f"  candidatos evaluados en promocion forzada  {asked:7d} "
          f"({asked / denom:7.2f}/{unit})")
    print(f"  la danza SUMA energia                      {seat:7d} "
          f"({seat / denom:7.2f}/{unit})")
    print(f"  ...y ARMA un cuerpo que sin ella era mudo  {arms:7d} "
          f"({arms / denom:7.2f}/{unit})")
    if arms / denom < 0.01:
        print("\nAVISO: el evento es RARO. Con una exposicion asi el gate de "
              "self-play no resuelve la diferencia por muchas partidas que "
              "juegue; el informe honesto es este censo, no un winrate.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=0,
                    help="self-play games; 0 = replay the records instead")
    ap.add_argument("--opponent", default=None,
                    help="deck csv for the opposing seat (self-play only)")
    ap.add_argument("--progress", type=int, default=250)
    ap.add_argument("--verbose", action="store_true",
                    help="one line per record that fires")
    args = ap.parse_args(argv)
    if args.games:
        return census_selfplay(args.games, args.opponent, args.progress)
    return census_records(args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
