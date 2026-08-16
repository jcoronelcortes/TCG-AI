# The wall that reads our Tera (Milotic ex, steps 74–103)

[← Documentation index](README.md)

Ten turns of a game we **won**, spent hitting a body that cannot be hit. Episode
93490495 vs a Milotic ex / Sylveon list, `records/registro_009` … `registro_019`.

The card is one line long:

> **Sparkling Scales** — Prevent all damage from and effects of attacks from
> your opponent's **Tera** Pokémon done to this Pokémon.

Our only Tera is **Teal Mask Ogerpon ex**, and the deck runs four of them. So
one opposing body switches off the attacker the whole deck is built to charge —
and switches off **nothing else**: Hydrapple ex is an ex and hits it, Dipplin
has an Ability and hits it, Tapu Bulu and Meganium hit it.

---

## The board, six times over

`_our_effective_damage` did not know the card, so it priced *Myriad Leaf Shower*
at 30 + 30·(4 own + 0 theirs) = **150** against a body that takes **zero**. Six
consecutive turns of ours, the same picture:

| step | turn | our active | their active | what we did |
| --- | --- | --- | --- | --- |
| 74 | 9 | *(knocked out)* | Milotic ex **50**/270, 0 energy | promoted a charged **Ogerpon ex** |
| 83 | 11 | Teal Mask Ogerpon ex, 4 eff. | Milotic ex 80/270, 0 energy | **attacked for 0** |
| 87 | 13 | Teal Mask Ogerpon ex, 4 eff. | Milotic ex 80/270, 0 energy | **attacked for 0** |
| 90 | 15 | Teal Mask Ogerpon ex, 4 eff. | Milotic ex 80/270, 0 energy | **attacked for 0** |
| 94/96 | 17 | Teal Mask Ogerpon ex, 4 eff. | Milotic ex 80/270, 0 energy | **attacked for 0** |
| 103 | 19 | Teal Mask Ogerpon ex, 4 eff. | Milotic ex **110**/270, 0 energy | **attacked for 0** |

Two details make it worse than a wasted swing.

**Their Milotic never had an energy on it.** It could not attack back, all game.
The board was not a stalemate we were losing — it was a body standing still in
front of us, healing itself (80 → 110, their Potion and Fennel) while we swung.

**The knockout was on our bench the whole time.** At step 74 the promotion menu
offered a **Dipplin at 2 effective energy**: *Do the Wave* is 20 × our bench,
four bodies after the promotion = **80** into a Milotic at **50**. By step 96
the bench held *three* separate finishers — Tapu Bulu at 4 (Wood Hammer 220),
Meganium at 4 (Solar Beam 140), Dipplin at 2 (Do the Wave 100) — and the menu
that turn offered exactly three things: **attack for 0, retreat, or pass**.

The game was still won. That is the point: the winrate never reported this, and
would not have.

---

## The cause

The agent already knows two walls, and both are questions about the **attacker**:

| table | the question it asks | our bodies it blanks |
| --- | --- | --- |
| `EX_IMMUNE_IDS` (Crustle, Sylveon) | is the attacker a Pokémon **ex**? | Ogerpon ex, Hydrapple ex, Meowth ex, Fezandipiti ex |
| `ABILITY_IMMUNE_IDS` (Cornerstone) | does the attacker **have an Ability**? | Ogerpon ex, Hydrapple ex, Meganium, Dipplin, … |

Sparkling Scales is a **third question** — *is the attacker Tera?* — and both
existing tables give the wrong answer to it. Filed under `EX_IMMUNE_IDS` it
would blank our Hydrapple ex, which damages a Milotic perfectly well; filed
under `ABILITY_IMMUNE_IDS` it would blank the Dipplin that finishes it. It
blanks **one** body, and there is no way to say that with either table.

---

## The rule

`TERA_IMMUNE_IDS` ([ptcg/cards/ids.py](../ptcg/cards/ids.py)), read against
`OUR_TERA_IDS` — the set the Nighttime Mine tax already uses to name our Tera.
Four call sites, because three of them are inline copies of the damage
arithmetic that do not go through the canonical model:

* **[ptcg/calc/damage.py](../ptcg/calc/damage.py)** — `_our_effective_damage`,
  the model every projection consults. This one line alone is what fixes the
  **promotion**: the forced-promotion chain prices its candidates through it, so
  the mute Ogerpon drops to zero and the Dipplin that finishes wins the seat.
* **[main.py](../main.py)** — the ATTACK menu's own copy, plus
  `SCORE_USELESS_ATTACK` for the swing that lands zero.
* **[main.py](../main.py)** — the wall region: `_op_wall_active`,
  `_dmg_vs_wall`, `_active_blocked_by_wall` and the `_wall_ko_promote` relief.
  This is what turns "our Tera is stuck in front of it" into the retreat
  (`_ex_stuck_promo_ready`, 6000) that promotes a body which hits.
* **[ptcg/turn/supporters.py](../ptcg/turn/supporters.py)** — the gust's price,
  so a Boss's Orders is not spent buying a Milotic ex out of their bench while
  the only charged attacker we own is the one it blanks.

It enters as **its own term** in each of those sentences rather than widening
`op_has_ex_immune_active`. Swapping our *ex* out is the answer to Crustle; here
it is the answer to nothing — what has to leave the front seat is our **Tera**,
and both of our other ex are among the bodies that replace it.

The other half of the user's rule — *prepare an attacker on the bench* — needed
no new code once the wall is visible: with the bench drained of energy on the
step-96 board, the turn's Grass goes to **Tapu Bulu**, not to the Ogerpon in
front.

---

## What it measures

**Golden corpus:** **7 flipped decisions**, all in this game, all the same
sentence — step 74 promotes the Dipplin instead of the Ogerpon, and steps 83,
87, 90, 94, 96 and 103 retreat instead of swinging for zero. **0 flips** in the
3 580 frozen decisions: the frozen corpus contains no Milotic board.

**Self-play** vs `deck/opponents/milotic_sylveon.csv` (harvested from this same
episode: Milotic ex / Feebas / Sylveon / Eevee, so it carries *both* walls),
n = 1 000 per arm, seats alternated:

| arm | winrate | prizes/game |
| --- | --- | --- |
| candidate | **94.4 %** [92.8–95.7] | +3.61 |
| HEAD | 83.1 % [80.7–85.3] | +2.73 |

**+11.3 points**, intervals that do not touch.

**Collateral**, `utils/matchup_matrix.py --games 200 --base HEAD --weights
--control-card 207`: **87 of 87 real lists are the control group** — not one of
them plays card 207, so both arms run behaviourally identical code in every one.
Weighted delta **−0.28 points**, prize delta −0.030/game; the control group's own
dispersion is sd 2.88 with a range of −11.5 to +5.5, which is what the noise of
this run looks like and why the −0.28 means nothing either way. The five widest
negatives are all `crustle_wall`, which are simply the only matchups far enough
from saturation (71–86 %) to swing at all — everything else sits at 95–100 %.

Re-measured there on **paired seeds** — identical shuffles in both arms, so the
seed lottery is gone and any difference left is the code — 16 lists × 400 games
per arm:

> **delta = +0.0 and dprem = +0.00, on all sixteen, exactly.**

Which is what the guard already promised: every branch this change adds is
gated on the opposing **active** being card 207, so outside that board the two
arms are the same program. The −11.5 was the lottery, and this is the receipt.

**Exposure:** **0 of the 408** opposing lists in the corpus play Milotic ex —
and the user met it on ladder. That is the honest number, and it is the same
shape as the Crustle 533 correction of 11 August: the fix is worth making
because the meta rotates, not because the corpus is bleeding.

---

## The instrument that should have caught it

`utils/op_immunity_census.py` exists precisely so that "a table of ids rots
silently" is not how we find the next wall. It reported **0 unmodelled** while
this game was being played, and it took **two** failures at once:

1. There was no claim for this shape, so Milotic's text matched no pattern —
   fixed by the fourth claim, `TERA_IMMUNE_IDS`.
2. The search for unmodelled immunities only ever read the cards that appear in
   a **corpus deck file**, and Milotic ex appears in none of them. A card the
   meta plays and the corpus does not was invisible twice over.

`--all-cards` is the second half: it sweeps the whole card table instead of the
corpus. Run today it comes back **empty** — the only two hits are Farigiraf ex's
Armor Tail and the Survival Brace tool, both already modelled by name rather
than by table, and both now written down in `_EXCLUDED` with the reason, so

```bash
python utils/op_immunity_census.py --all-cards --unmodelled
```

exits 0 and can be a gate.

---

## Tests

[tests/test_the_tera_wall_is_read_off_the_attacker.py](../tests/test_the_tera_wall_is_read_off_the_attacker.py),
on the two real boards. Besides the two decisions it pins:

* the ability is read as what it says — our Tera goes to 0, our **other ex**
  (Hydrapple ex) and our body **with an Ability** (Dipplin) do not;
* the two boards with their active swapped for **Feebas** (its own
  pre-evolution, no ability) return the pre-fix answers, one for one;
* and the mutant-killer: emptying `TERA_IMMUNE_IDS` in every module holding a
  reference to it — the four call sites live in four files — brings **both**
  pre-fix decisions back. A rule that fired on these boards for some other
  reason would survive that, and it does not.
