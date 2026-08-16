# The front spot goes to the body that can still attack (Archaludon, step 109)

*`records/registro_008` step 109, episode 93497723 vs Archaludon ex — **lost**.
Their Archaludon at 300 HP with its own pile down to **two**, and our Teal Mask
Ogerpon ex on four effective Grass: **270 today, 330 with one more charge**, and
with the Grass that pays its own retreat. The front seat went to a Tapu Bulu at
**0 of 4** with a retreat cost of **4** — by 142 bare points. It neither attacks
nor steps aside.*

## The obvious suspect was not the culprit

`_ko_prefer_basic_general` was the first candidate and it is innocent: that rule
demands that **nobody** can attack. Two things did it instead.

* The escalated match-point veto, `_mp_price_ends_the_game` (**−30000**).
* The guard on `_promote_setup_ko_attacker`, which skips the whole selector
  whenever *some* body can attack.

The Ogerpon **could** attack: for 270, without finishing. So the rule that
exists precisely to rescue it — the almost-ready finisher, **+9500**, and with
it the exemption from the veto — never got to look at it.

## Three sentences, three named switches

| switch | what it says |
| --- | --- |
| `PROMOTION_READS_THE_KNOCKOUT_NOT_THE_ATTACK` | The almost-ready finisher is offered on boards where **nobody knocks out**, not only where nobody can attack. A body that already hits for less than lethal is the same almost-ready body, one charge earlier. |
| `PROMOTE_DEFERS_THE_SACRIFICE` (`_promo_deferred_attacker`, **9200**) | When nothing attacks, nothing knocks out and **nobody survives**, then among the bodies the prize band already considers equal, promote the one closest to attacking that keeps its exit. Deliberately **below** `PROMO_LAST_STAND` (9450). |
| `SACRIFICE_WAITS_FOR_THE_TURN` (`_active_can_still_be_charged`) | The pivot that cashes the sacrifice does not fire while the turn can still charge the active. Generalises the veto from `registro_009` p150. |

## The boundary, which cost two designs

**A body that CAN attack, WILL attack.** The doctrine "the sacrifice is a
deferrable decision" only holds for the body that cannot attack *today*; if it
can, it attacks, and the exit is never used.

Two wider versions were written and both lose a board this project already paid
for:

* Exempting **any** attacker with an exit from the veto loses `registro_005`
  p64 — 270 onto a 400 HP Archaludon, dead for two prizes, instead of the one
  body that survived the 220.
* Promoting the body closest to attacking **whatever it costs** loses
  `registro_005` p99 — a two-prize ex over a one-prize Dipplin to buy 180 onto a
  340.

So the deferred attacker is **never bought with prizes** and never steps over a
survivor, and the match-point veto stays intact except for the finisher.

## The collateral bug: the sixth inline copy of the damage calculation

The loop in `_best_promote_card` was the **sixth** inline copy of the damage
computation, and the last one that applied weakness **without resistance**. It
read 270 as 300 and marked "knocks out" against a 300 HP body — which is the
second half of why the new guard would not have opened on its own.

## Measurement

| instrument | number |
| --- | --- |
| Harvested corpus (`records/`) | 254 decisions → **1 flip**, and it is step 109 |
| Frozen corpus | **0 of 3 580** |
| Census | 4 forced promotions across 14 records (finisher 1, deferred 0) |
| Suite | 3 083 passed |
| `lint_architecture` | clean |

## Files

* `main.py`, `ptcg/calc/damage.py`, `ptcg/cards/scoring.py`,
  `ptcg/turn/ctx_scoring.py`, `ptcg/turn/options/card.py` — the three sentences
  and the canonical damage read that replaced the sixth inline copy.
* `tests/test_the_front_spot_goes_to_the_body_that_can_still_attack.py`
* `tests/fixtures/archaludon_promote_the_charged_attacker_step109.json`
* `utils/census_the_front_spot_goes_to_the_attacker.py` ·
  `utils/gate_the_front_spot_goes_to_the_attacker.py`

---

Related: [The veto that walks back (Archaludon, step
77)](archaludon-the-veto-that-walks-back-2026-08-14.md) is the same match-point
veto, one rung further down and from the other side. And this fix is what
retroactively repaired the episode analysed in [The seat that closes the game is
not a tie-break](alakazam-the-seat-that-closes-the-game-is-not-a-tie-break-2026-08-16.md)
— see that page for why a log has to be **aged** before the agent is accused.
