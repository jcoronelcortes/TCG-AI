"""How often the forced promotion is a board where the attacker loses the slot.

THE READING (`PROMOTION_READS_THE_KNOCKOUT_NOT_THE_ATTACK`,
`PROMOTE_DEFERS_THE_SACRIFICE`). The promotion after a knockout resolves at the
END of the opponent's turn, so a whole turn of ours happens before their reply.
Every rule that hands the front spot to a cheap wall prices that reply as if it
arrived at once, and two of them used to remove the only body that could do
anything:

  * the almost-ready finisher (`_promote_setup_ko_attacker`, +9500, and with it
    the exemption from the match-point veto) was offered only the boards where
    NOBODY COULD ATTACK. A body already able to swing for less than lethal --
    which is the same almost-ready body one attachment earlier -- shut the whole
    selector, and the veto then took it at -30000;
  * with nothing able to attack at all, the survival and prize rules fall back
    to raw HP, where a body that will NEVER attack outranks one that attacks
    next turn.

The record is `records/registro_008_pasos_094_hasta_109.json` step 109 (episode
93497723, LOST vs Archaludon ex): our Teal Mask Ogerpon ex on four effective
Grass, one attachment from 330 on their 300 HP Archaludon, lost the slot to a
Tapu Bulu at 0/4 that could neither attack nor pay its retreat of four.

WHY A CENSUS AND NOT A WINRATE. The whole stored corpus contains FOUR forced
promotions, and the frozen fifty move zero decisions: that is exactly the shape
of change a self-play winrate cannot resolve, since the noise floor of this
harness is around half a point. What arbitrates is how often the board even
occurs and what the answer would have been without the reading -- which is what
this counts. `utils/gate_the_front_spot_goes_to_the_attacker.py` is the harm
check, not the evidence.

WHAT IT COUNTS, per forced promotion:

    asked       promotions resolved with the active spot empty
                (`_forced_ko_promote`), which is the only board these rules
                claim.
    knocks      ...of those, the ones where some candidate already knocks the
                opposing active out. There nothing here speaks: +PROMO_KO_BONUS
                owns the decision.
    finisher    ...of the rest, the ones where the widened guard NAMES an
                almost-ready finisher (`_promote_setup_ko_attacker`). Before the
                change, the ones among these where some body could already
                attack were exactly the ones the selector never saw.
    deferred    ...of the rest, the ones where `_promo_deferred_attacker` names
                the body closest to attacking. It never costs prizes and never
                loses on survival, so this is a tie-break count, not a trade.
    wall        ...of the rest, the ones where the cheap-wall family
                (`_ko_prefer_basic_general`) still governs, unchanged.

Usage:
    python utils/census_the_front_spot_goes_to_the_attacker.py
    python utils/census_the_front_spot_goes_to_the_attacker.py --records records
"""

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import main as m  # noqa: E402


def census(record_dir):
    """Replay our seat menu by menu and tally the promotion branches.

    The tally hangs off `score_option`, which is the one function every
    promotion menu goes through with the context already built: reading the
    flags from there needs no hook inside `agent()` and cannot disagree with
    what the scorer actually saw.
    """
    rows, seen_ctx = [], set()
    original = m.score_option

    def spy(ctx, option, score):
        if getattr(ctx, "_forced_ko_promote", False) and id(ctx) not in seen_ctx:
            seen_ctx.add(id(ctx))
            key = getattr(ctx, "_best_promote_key", None)
            rows.append({
                "knocks": bool(key is not None and key[0]),
                "finisher": ctx._promote_setup_ko_attacker is not None,
                "deferred": ctx._promo_deferred_attacker is not None,
                "wall": bool(ctx._ko_prefer_basic_general
                             or ctx._lucario_ko_prefer_basic
                             or ctx._refresh_promote_prefer_basic),
            })
        return original(ctx, option, score)

    m.score_option = spy
    try:
        for record in sorted(Path(record_dir).glob("registro_*.json")):
            log = json.loads(record.read_text(encoding="utf-8"))
            m._init_cards_tracking()
            m.plan = m.AttackPlan()
            m.pre_turn = 0
            for step in log.get("steps", []):
                for entry in step:
                    obs = entry.get("observation") or {}
                    if not obs.get("select"):
                        continue
                    try:
                        m.agent(obs)
                    except Exception:      # a menu this build cannot answer is
                        continue           # not a promotion we can count
    finally:
        m.score_option = original
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", default=str(_ROOT / "records"))
    args = ap.parse_args(argv)

    rows = census(args.records)
    asked = len(rows)
    if not asked:
        print("no forced promotions in the records given: nothing to count")
        return 0

    knocks = sum(1 for r in rows if r["knocks"])
    rest = [r for r in rows if not r["knocks"]]
    finisher = sum(1 for r in rest if r["finisher"])
    deferred = sum(1 for r in rest if r["deferred"] and not r["finisher"])
    wall = sum(1 for r in rest
               if r["wall"] and not r["finisher"] and not r["deferred"])

    def line(label, n):
        print(f"  {label:10s} {n:4d}   {100 * n / asked:5.1f}% of the promotions")

    print(f"forced promotions asked: {asked}\n")
    line("knocks", knocks)
    line("finisher", finisher)
    line("deferred", deferred)
    line("wall", wall)
    print("\nReproduce the 'before' column with the named switches:\n"
          "  main.PROMOTION_READS_THE_KNOCKOUT_NOT_THE_ATTACK = False\n"
          "  main.PROMOTE_DEFERS_THE_SACRIFICE = False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
