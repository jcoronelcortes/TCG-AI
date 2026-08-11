# The ability and the attachment tie at 31300, and they are not the same play

[← Documentation index](../README.md) · Queue item 4 of
[the night of 11 Aug 2026](night-2026-08-11.md)

**Outcome: the rule was written, measured, and REVERTED.** The tie is real and
the menu order does decide it, but the two options are not interchangeable —
breaking the tie toward the free ability sends the charge to the bench in 29 % of
the boards where it fires, on a band that exists precisely to stop the active
closing the turn without attacking.

---

## What the queue said, and the two things it had wrong

> 415 of the 3 224 order-dependent decisions are `ABILITY:Hydrapple` against
> `ATTACH:Grass -> the same Hydrapple`: two routes to the same body, and the
> menu order decides. They are not the same resource — the attachment is one per
> turn and the ability is separate, so spending the ability first leaves the
> attachment free.

**First correction: `ABILITY:150` is the ability's OWNER, not a destination.**
`utils/permutation_probe.py` renders an ability option as
`ABILITY:{card(area, index)}` — the body whose ability it is. The `150` on both
sides of the pair is a coincidence of the Hydrapple ex being both the ability's
owner and the active, which is the attach's usual target. They are not "two
routes to the same body": **the ability's destination is a separate, later
choice**, and the agent's own comment says so — "Ripening Charge (once
activated) FORCES an attachment to some Pokemon".

**Second correction: the resource claim is true, and it is not the whole of it.**
The engine confirms the half the queue asserted and nobody had measured. Over 61
activations of the active Hydrapple ex's ability, driven through `libcg`:

    energyAttached  before -> after:  (True, True) x47,  (False, False) x14
    ATTACH options left in the next menu: 0 in all 61

`energyAttached` never moves, and in 47 of the 61 the ability was used with the
turn's attachment **already spent**. They are genuinely independent resources.
What that does not establish is that the two plays have the same effect.

## The population, measured before writing anything

Over the 665 dumped ABILITY-vs-ATTACH ties, the 415 of this class:

| | |
| --- | --- |
| the ability's owner IS the active, the attach's target | 415 / 415 |
| exactly ONE Grass in hand (the two are genuinely exclusive) | **311 / 415** |
| the Hydrapple ex is damaged, so the +30 heal is worth something | 21 / 415 |
| of the 311, the turn still has a route to another Grass | 203 (65 %) |

A first count said 92 %, counting "another ability is on offer" as a route to
another Grass. **Teal Dance consumes a hand Grass, it does not fetch one** — it
draws, which is an indirect route at best. Recounted with only what really
brings cards (Ultra Ball, Lillie's, Night Stretcher, Lana's Aid, Dawn): 65 %.

## The tie is exact, and the fix looked cheap

Replaying a dumped board through the agent with a score spy:

    option  2  ATTACH  Grass -> ACTIVE Hydrapple ex     31300
    option 12  ABILITY ACTIVE Hydrapple ex              31300     <- tie
    ...the agent takes index 2 because the simulator listed it first

`SCORE_CHARGE_ACTIVE_ATTACK` is assigned twice for one sentence — *"without this
charge the active does not attack and the turn closes blank"* — once for the
manual attachment (`ptcg/turn/energy.py`) and once for a charging ability
(`ptcg/turn/options/ability.py`, both Teal Dance and Ripening Charge). So the
repair looked like a tie-break of +50, not a band change, and it had a
precedent: the project already wrote this doctrine for Teal Dance in its
development band — *"the manual attachment is not lost: it is postponed"*.

## Why it was reverted

`test_archaludon_step58_attaches_when_bench_developed` went red. That test is a
**counterfactual with a DEVELOPED bench**, and it is not over-specified — it is
the control that catches what the change actually does.

Followed through the engine, restricted to the activations that score in this
very band:

    247 menus where the ability scored in the band
    121 followed to where the Grass landed:
         86  onto the ACTIVE
         35  onto the BENCH        <- 29 %

The manual attachment **names its destination**. The ability does not: a second
scorer aims it, and in 29 % of the boards where the tie-break would fire it aims
at the bench. On a band whose entire purpose is "otherwise the turn closes
blank", that is the charge failing to reach the body that needed it — in roughly
one board in three.

(The unrestricted figure is worse still: over all 209 charging-ability
activations, 162 of them — 78 % — put the Grass on the bench.)

So neither option dominates. The manual attachment guarantees the destination;
the ability preserves the turn's attachment and heals 30. They cannot be ordered
without knowing where the ability will aim, and the scorer does not know that at
the time it prices the option — asking it to would be
[[detectar-no-es-ejecutar-replicar-los-tableros-del-flip]] all over again.

**The five corpus flips were all of the intended shape**
(`ATTACH->Hydrapple ex` becoming `ABILITY Hydrapple ex`, in registros 021 t8 and
t16, 027 t8, 034 t14 and one more) — which is worth recording: the flips looked
right and the change was still wrong. The finding came from the engine, not from
the diff.

## What is left standing

The tie is real: 415 boards where the order the simulator emits decides. It is
now an **honest** tie in the precise sense that neither route is better on its
own terms. A rule that wanted to break it would have to answer the question this
measurement opened — *where would the ability aim?* — and that is a different
piece of work, on the sub-scorer that aims it, not on the band.

Suite 2264 green, linter clean, nothing changed in the agent.
