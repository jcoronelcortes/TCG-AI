# The cost and the fuel: measured, and the change NOT made

[← Documentation index](../README.md) · Queue item 2 of
[the night of 11 Aug 2026](night-2026-08-11.md) · sibling of
[the second copy](the-second-copy-2026-08-11.md)

**Outcome: the census answered the question and the policy change is not
justified.** No rule was touched. What changed is the instrument, which had been
reporting its own coarseness as a defect of the agent — and the number the
project's memory carried.

---

## The claim on the queue

> `registro_002` step 15 (episode 91529732, turn 2 vs Cynthia's Garchomp ex,
> LOST). The hand was {Bayleef 50, Grass 80, Meganium 40, Hydrapple ex 3,
> Grass 80} and the cost of an Ultra Ball took **both Grass** to buy a Teal Mask
> Ogerpon ex whose only route to doing anything is Teal Dance — attach a Grass
> **from hand**. It kept a Bayleef and a Meganium that could not enter play for
> two turns.
>
> What makes energy cheap is the QUANTITY, not the ACCESS.

Measured by `utils/fodder_ladder_audit.py`, the first run said **12 of 118
discard menus (10.2 %)** drop an energy ahead of an evolution the agent itself
calls orphaned. That number is what put this second on the queue and what earned
it the line "the only one self-play can really arbitrate".

## First finding: five of the twelve were the tool

`_evo_link_state` is the **coarse** reading — *pre-evolution neither in play nor
in hand*. The ladder deliberately asks a finer question that it does not, and in
five menus the audit was scoring the agent against the coarse one:

| record | the board | why the ladder is right |
| --- | --- | --- |
| 031 t4, 031 t6, 045 t2, 007 t3 | an **Applin on the bench**, the Dipplin in the deck | the Hydrapple ex in hand has no pre-evolution, but the line is one link from complete — the ladder scores it 3 for exactly that |
| 037 t4 | a **Chikorita in play**, the Bayleef in the deck, our own Ultra Ball paying | verbatim the board `DISCARD_LINK_THE_SEARCH_BUYS` was written for: the cost is priced against a board the card being paid for is about to change |

The agent already owns the function that says it — `_evo_top_unlocked_by_the_
search`, which puts the missing link on the board and asks whether the top is
then one evolution away. `lectura_de_eslabon` now calls it (calls, not
reimplements) through a new generic `extra(tc)` hook on the shared capture, and
`clasificar` splits the report. **The rescued rows are printed as their own
population, never dropped**: a tool that silently shrinks its own finding reads
as "there was less" when it means "we looked better".

    the number is SEVEN of 118 menus (5.9 %), not twelve (10.2 %)

This is the fifth detector in this repository to report its own reading as a
defect of the agent, and the reason each one carries two halves. The audit's
auto-test gained a pair for the new reading: it must **fire** somewhere in the
corpus (an unwired hook silently restores the old, bigger number) and it may
only ever **narrow** the orphan set, never widen it.

## Second finding: the seven that survive do not support the change

| delta | energy | orphan | Grass in hand | Grass in DECK | refill in hand | where |
| --- | --- | --- | --- | --- | --- | --- |
| 55 | 95 | Meganium 40 | 3 | 10 | — | 022 t2 [cost] |
| 45 | 85 | Meganium 40 | 2 | 11 | **Night Stretcher** | 003 t2 [cost] |
| 45 | 85 | Meganium 40 | 2 | 11 | **Night Stretcher** | 018 t2 [cost] |
| 10 | 85 | Bayleef 75 | 3 | 8 | — | 026 t3 forced |
| 5 | 45 | Meganium 40 | 1 | 12 | — | 028 t1 forced |
| 5 | 17 | Hydrapple ex 12 | 1 | 8 | **Lillie's + NS** | 036 t4 [cost] |
| 4 | 12 | Dipplin 8 | 1 | 8 | Ultra Ball, Meowth ex | 017 t9 forced |

Three readings, and they point the same way:

1. **The access argument does not hold on these boards.** The claim was "with no
   Lillie's and no Night Stretcher there is no way to touch another one this turn
   or the next". Every one of the seven has **8 to 12 more Grass in the deck**,
   and three of them hold the very refill whose absence was the argument.
2. **Where the fuel really is scarce, the ladder already nearly agrees.** The
   three menus down to their last Grass have deltas of 4, 5 and 5 — the two
   cards are within a nudge of each other, not 40 points apart.
3. **The big deltas are the cases where the ladder is reasoning correctly.** 45
   to 55 points of gap all sit on hands holding **two or three** Grass, which is
   precisely the "quantity" the branch is pricing.

And the energy branch is not the blunt instrument the claim assumed. It already
prices by access: under Teal Dance it scores four-or-more at 85 and **the last
one at 2**, the most protected band the ladder has.

There is no sub-population here that is both frequent and harmful. A change
aimed at the three last-Grass menus would be moving three corpus decisions by
four points — a patch, whose self-play signal would be indistinguishable from
noise, on a ladder that orders **every forced discard**.

## What remains true

`registro_002` step 15 is still a real mistake, and this does not explain it
away: on that board the cost took the last two Grass to buy the very body that
needed them. The corpus says it is **not representative**, and the queue already
recorded that with [[el-motor-espera-al-turno-que-puede-ejecutarlo]] that Ultra
Ball no longer gets played at all.

If the board ever recurs, the sharper hypothesis is not "re-order the ladder"
but the one the two existing constants already embody: the cost is priced
against a board its own card is about to change. `_teal_dance_possible` reads
the field **before** the fetch resolves, so an Ultra Ball buying the Teal Dance
user prices the hand's Grass as if nothing were about to use it. That is a
question about one branch and one flag — measurable, narrow, and nothing like
re-ordering the ladder.

## Verdict

**Not made.** Queue item 2 is closed by measurement, not by a change. The
deliverable is the corrected instrument and the corrected number; the suite is
2250 green and the linter clean across eight rules, with no rule of the agent
touched.
