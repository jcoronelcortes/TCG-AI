# The night of 15 August 2026 — the tree is red, and the flip is today's own

[← Documentation index](README.md) · [the night before](history/night-2026-08-14.md)

**Status: written 15 August 2026 (01:40), before anything runs.
Branch `main`, HEAD `40b8e09`, working tree **clean**, `lint_architecture` clean.
The suite is **RED**: `1 failed, 2830 passed, 23 skipped` in 33 s — and the
failure is a regression of the merge that closed the day.**

This night has no new idea in it. The two nights before it each bought a
measurement (the list is worth more than the code; eleven variants and none
recommended), and the day added three rule fixes on top. What is missing is not
another hypothesis — it is **ground**: a green tree, a memory index that matches
the repository, and an explanation for the one number last night found and could
not explain.

So the spine is: **make the ground true, then spend what is left on the one
matchup that is losing.**

It is written to run **autonomously, end to end, while the user sleeps.**
Everything it needs is asked in §0, once. If §0 is answered *"todo por
defecto"*, the recommended column applies and nothing stops until the morning
report. §8 is what makes that safe.

> **§0 ANSWERED at 01:52, all six on the recommended default.** Q1: read the
> board before touching the guard. Q2: rules may change, branch per hypothesis,
> NEUTRO reverts. Q3: ~7 h, `JOBS=6`, 400 games, seeded, `--allocation peso`.
> Q4: §4 first, then §5. Q5: commits to `main`, never on a red tree, never
> `push`. Q6: CI stays off, and the report says so.

---

## 0. START HERE — the six questions, asked before anything runs

The executor asks these **once, in a single message**, and does not stop again
until the morning report.

| # | Question | Recommended default | What changes if the answer differs |
|---|---|---|---|
| **Q1 · The red tree** ⚠️ | `test_the_reading_does_not_spread` fails: with `_promoted_lethal_reply` toggled off, **one decision moves** on `registro_007` step 98 — a board today's merge `c841618` did not exist for. How is it greened? | **(a) Read the board first, then decide.** The reading spreading is not by itself a bug: the test asserts *at most the foundational board*, and today's charge band changed what that board scores. If the new decision is better, the guard is re-written around the property with the board documented; if it is worse, today's third fix is bounded until it stops reaching it. **Never re-freeze or relax a guard without reading its flip** ([[corpus-dorado-resnapshot-silencioso]]) | **(b)** revert `c841618` outright — cheapest, and throws away three fixes for one collateral. **(c)** leave it red and reported — but then **nothing else commits tonight** (§8), which costs the whole night |
| **Q2 · Agent edits** | May behaviour change tonight, under written criterion? | **Yes**, a branch per hypothesis, merged only on the criterion written before it ran, and anything measured NEUTRO is reverted unless the user overrides it, MARKED ([[politica-neutro-se-revierte-salvo-valor-ilegal]]) | "Measure only" is legitimate and cheap: §2 and §3 are ground, §4 is a diagnosis, §5/§6 are the only blocks that write rules |
| **Q3 · Budget** | Hours, workers, games per matchup? | **~7 h, `JOBS=6`, 400 games/matchup**, seeded, `--allocation peso` | A 4 h night keeps §2, §3 and §4 and drops §5, §6 and §7. A 10 h night adds a second finding to §6 |
| **Q4 · The deep block** | After the ground, which axis gets the executor's attention? | **§4 (Mega Lopunny / Mega Froslass) first**, then **§5 (the two pending cards)** | §6 (the discovery channel on the fifteen games on disk) is the alternative and it is the channel that produced **13 of 13** real findings ([[el-canal-de-descubrimiento-es-un-humano-leyendo-una-partida-perdida]]) — but it is also the one that needs a human reading, so unattended it returns candidates, not corrections |
| **Q5 · Commits** | May the executor commit? | **Yes to `main`, in the house style, never on a red tree, never `push`.** Branches for anything under criterion | "No commits" leaves the morning a large uncommitted diff on top of a red tree |
| **Q6 · CI** | The gates workflow has had its `push`/`pull_request` triggers commented out since `a9a53ea` (14-ago, deliberate). Does it stay off? | **Stays off, and the morning report says so.** It was the user's decision and a night does not reverse it | "Turn it back on" is four uncommented lines and no other change |

Three things the executor must **not** ask, because they are already decided:

* the local engine is legitimate for measurement — what is forbidden is
  redistribution, enforced by lint **R11** and `.gitignore`;
* logs go to `log/noche-2026-08-15/`, never `/tmp`
  ([[corridas-largas-loguean-en-log-no-en-tmp]]);
* **census before winrate** ([[el-delta-de-el-coste-y-la-busqueda]]), any
  self-play number needs n ≥ 1000 ([[selfplay-gate-tamano-de-muestra]]), and
  **a gate row without its `--control` at the same N is not a reading** — vs
  Marnie the noise floor alone is 1.50 points and looks significant
  ([[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]]).

---

## 1. What moved in the last 24 hours

| When | What | Where |
|---|---|---|
| 14-ago, late | **The last bridge of a line is not fodder** — a seat can be searched for and a discarded card cannot; the Ultra Ball ate both Bayleef and the Meganium sat in hand 127 of 191 steps | `f40c0f6` |
| 14-ago, late | **The split refutes the loss the first row showed** — the winrate is unresolvable at this exposure, so the change entered marked NEUTRO | `2442f27` |
| 15-ago, 01:19 | **The turn that takes the prize leaves nothing ready for the next one** — three decisions of one turn (`registro_005` 70/74/75, episode 93173834 vs Marnie, LOST): the Grass to a Bayleef, Dawn buying tomorrow's Meganium over today's Hydrapple ex, the Fezandipiti ex left in hand | `c841618` / `40b8e09` |

Five named switches shipped with the last one, and they are the handles §2 needs:
`CHARGE_THE_BODY_THAT_NEEDS_IT` (+ `CHARGE_ALREADY_KOS_COMPLETES_STEP` /
`…_PARTIAL_STEP`, 500 each, half a rung), `DAWN_SEAT_WAITS_A_TURN` (+
`DAWN_SEAT_TOMORROW_CAP` 870) and `FEZ_ABILITY_BEFORE_THE_KNOCKOUT` (+
`FEZ_BENCH_FOR_TOMORROWS_DRAW` 3000).

**The gate row on record for it is `+0.00 / +0.00 / +0.10` pp over three
matchups against a `+0.00` control — that is NEUTRO, and it is in `main`.**

---

## 2. Track G — the red test, and it is the night's ground

**Blocking. Nothing commits until this is green** (§8).

    tests/test_the_prize_is_cashed_by_the_body_that_outlasts.py:379
    AssertionError: sin el registro fundacional en el corpus la lectura no debe
    tocar NADA; cambio 1 de 157 decisiones:
      [('registro_007_pasos_092_hasta_103.json', 98)]

> ### ⚠️ RESOLVED WHILE THE NIGHT RAN, and the plan's own premise was wrong
>
> This section was written saying "the cause is today's merge and nothing else",
> on the evidence of a worktree at `2442f27` where the file was green. **It was
> green because `records/` is git-ignored: the worktree had no records and the
> test skipped.** With the records copied in, `2442f27` fails identically, and so
> does every single-file revert of the merge. Nothing that day shipped put the
> board there — `utils/split_turns.py` did, re-cutting the corpus onto episode
> 93173834 at 00:31. **A control arm that cannot run the measurement is not a
> control arm**, and that is the transferable half of this.
>
> What the board turned out to be is in §2.2. The work is in `main`
> (`utils/diag_the_reading_spread_step098.py` is the attribution instrument).

What the test does: for every one of our decisions in `records/`, it decides
twice — once with `_promoted_lethal_reply` as written, once forced to zero — and
asserts the reading changes **at most the board it was written for**
(`registro_006` step 54, which is no longer on disk, so the assertion is
`== []`).

The board that now moves: `registro_007`, **episode 93173834** — the *same lost
game vs Marnie* today's three fixes came from — **turn 7, step 98**, an
attack-or-end menu with three options (`attackId 120`, type 12, type 14).

### 2.2 What the board was — the reading was right, and the guard was pinned wrong

Turn 7, step 98, three prizes to six in our favour:

| | US (seat 0) | THEM |
|---|---|---|
| active | Teal Mask Ogerpon ex **20**/210 (3G) | Marnie's Impidimp 70/70 |
| bench | Teal Mask Ogerpon ex **200**/210 (4G), Dipplin 70/80 (1G), Bayleef 80/110 (1G), Applin 40/40 | Munkidori ×2 (1D each), Froslass, Marnie's Morgrem, Impidimp |

Myriad Leaf Shower is 30 + 30 per Energy on **both** Actives, so the front reads
120 over 70: **the prize is there without moving.** The retreat takes the *same*
prize — one Grass off the front, the twin comes up with four Grass and its own
150 knocks the same Impidimp out — and ends the turn with **200 HP in front
instead of 20**, the wounded ex parked on the bench where its own Tera prevents
all damage from attacks. Leaving it in front hands two prizes to anything at
all, and their Froslass drips a counter onto it at every checkup on top.

**It is the line the game actually played** (steps 99–102), and it is the
foundational board of this very test with different cards.

So the reading is not spreading, it is *working*, and what was wrong is the
guard: it identified a board by **filename**, which `split_turns.py` rewrites
every run. It now identifies one by **episode and step** — neither moves — and
carries both read boards with what each decided. A third board still fails it,
which is the whole point. The new board is pinned by three tests off its own
fixture, so it survives the next rotation of `records/`.

### 2.1 The order of work, and it is not "make it pass"

1. **Read the board.** Dump step 98 with both readings and record which option
   each takes, with the board written out (`utils/turn_explorer.py`).
2. **Attribute it to one switch.** Toggle the three of §1 one at a time
   (`CHARGE_THE_BODY_THAT_NEEDS_IT`, `DAWN_SEAT_WAITS_A_TURN`,
   `FEZ_ABILITY_BEFORE_THE_KNOCKOUT`) and re-run the test. One of them owns it —
   naming it is what makes the fix small.
3. **Judge the new decision against the rules, not against the old one:**
   `utils/search_oracle.py` on that board, K ≥ 50, worst-floor
   ([[el-oraculo-de-busqueda-es-un-estimador-no-una-repeticion]]).
4. **Then** either bound the switch (if the oracle says the old decision was
   better) or re-write the guard around the property with this board named and
   documented (if it says the new one is). A fixture is written either way.

⚠️ **The trap:** `records/` is transient and the replay seeds the deck belief
from `deck.csv` (`main.py:165`). If the flip survives with the record's own list
(`tests/recorded_deck.py:deck_of_record()`) it is a real spread; if it does not,
it is the stale-list class of failure this project already named and fixed once
([[una-repeticion-es-una-partida-de-la-lista-de-su-dia]]) — **check this before
touching any rule.**

---

## 3. Track M — the memory index is stale, and a wrong map costs a night

Seven entries in `MEMORY.md` are marked **"sin commitear"** and **all seven are
in `main`**, verified by `git merge-base --is-ancestor`:

| Memory | Actually merged at |
|---|---|
| la promoción es el asiento que la búsqueda completa | `f858bc5` |
| la promoción apuesta el robo del turno si el cuerpo puede volver | `85d75eb` |
| el precio que no es nuestro no se guarda para mañana | `25e21df` |
| el veto de su match point cobra una respuesta de la que puede salirse | `85d75eb` |
| Neutralization Zone es el tercer muro | `62bf2bf` |
| la segunda ola no toma un premio, toma la partida | `e29fde2` |
| el turno que remata no deja nada listo para el siguiente | `c841618` |

This is cheap and it is not cosmetic: the index is what the next session reads
before deciding what to work on, and seven false "pending" entries is how a night
re-implements something that shipped. **Each line gets its commit; nothing else
in the file is rewritten.**

While in there, three genuine pendings are re-checked against the code rather
than trusted (`grep` before writing): the Search API (`Search.h`) still unused;
`pendiente-promover-un-tera-saca-un-cuerpo-inmune-de-la-banca`;
`pendiente-modelar-deluxe-bomb-12-contadores-al-atacante` (the reader half
shipped, the reply-at-less-life half did not).

---

## 4. Track L — Mega Lopunny / Mega Froslass, −0.90 pp, and nobody knows why

**The only thing last night found and did not explain**
([[la-lista-nueva-vale-mas-que-los-trece-commits-del-dia]]): with 7.2 % of the
meta and third by weight, this archetype lost **−0.90 pp and −0.093 prizes** on
the arm that changed the four cards, while every other weighted archetype gained.
Four lists carry it: `mega_lopunny_1..3` and `mega_lopunny_mega_froslass_1`.

**The first question is free, and it may close the whole block:** that number was
measured at `5ee49b1`. Since then the day of 14-ago shipped
`_op_hp_for_our_ko` — *their own Freezing Shroud finishes the body in front*
(`0e9fed2`), which is **a Froslass rule**. It is entirely possible the regression
is already fixed and nobody looked.

    python utils/matchup_matrix.py --only mega_lopunny,mega_lopunny_mega_froslass \
        --base 5ee49b1 --games 400 --seeds 400 --jobs 6 \
        --allocation peso > log/noche-2026-08-15/L1.txt

* **If the delta is positive and its interval excludes zero** → the block closes
  with a memory correcting the open question, and §5 gets the hours.
* **If it is still negative** → census before hypothesis: `utils/autopsy.py` and
  `utils/rule_census.py` on the losses of that matchup, then **one** hypothesis,
  a gate with its own `--control` at the same N, and the neutral policy.

⚠️ The list is **not** touched whatever this says: the sixty cards are the deck
owner's decision (the night of 14-ago, Q1), and this is a code question until a
measurement says otherwise.

---

## 5. Track P — the two pending cards, in the order the boards justify

Only if §2, §3 and §4 are done and the tree is green.

**P1 · The promotion does not price the immunity it gives up.** Teal Mask
Ogerpon ex is untouchable on the bench; the retreat branch respects it
(`main.py` ~6103) and the post-KO promotion branch charges nothing for pulling it
out — it hands over a 2-prize body *and* the immunity in one move. It is a
**price, not a veto**: there are boards where the ex is the only body that
survives or the only one that finishes (`_promote_setup_ko_attacker`).

**P2 · Deluxe Bomb's reply half.** The reader shipped with the four-card
punisher family; what is still unmodelled is the reply at less life — the
attacker takes 120 whether or not the KO is cashed, which decides *who can
attack*, not only *who to promote*.

Each one: board → census of how often it fires → fixture → rule behind a named
switch → gate with control → memory. **Nothing merges on a census alone**; the
policy is unchanged.

---

## 6. Track D — the discovery channel, unattended

**13 of 13 findings on record came from a human reading a lost game.**
Unattended, this block does not produce corrections; it produces a **ranked
worklist** so the morning has boards to read instead of a directory:

* `utils/sterile_turn_census.py`, `utils/turn_waste_census.py` and
  `utils/blind_window_census.py` over the fifteen records on disk;
* `utils/differential_oracle.py` (with its self-test — a detector that cannot
  prove it works and then reports nothing is the most misleading of the three
  outcomes);
* every candidate ranked by *prizes at stake*, not by frequency, with the
  episode, the step and one sentence of what looks wrong.

Episode 93173834 (vs Marnie, LOST) is already half-read: three fixes came out of
it today and §2's flip is on another of its turns.

---

## 7. Track C — housekeeping, only if the clock allows

* `records/` holds fifteen games and the suite skips **23** tests for boards
  that rotated off disk. The durable fix is the one already started: pin each
  record to *the list it was played with*.
* CI: per Q6 it stays off. The morning report states it, because a workflow that
  exists and never runs reads as a gate to anyone who does not open the file.

---

## 8. What makes this safe to run unattended

1. **A red tree stops commits.** Not "mostly" — the suite runs before every
   commit and a failure means the commit does not happen.
2. **No block fixes findings in flight** except §2, which is the ground.
3. **Every rule change is a branch**, merged only on the criterion written
   before it ran. NEUTRO reverts unless the user overrides it, and an override
   is written down as an override.
4. **No `push`, ever.** No network beyond what §4 needs (none).
5. **Nothing touches `deck.csv`.**
6. Every block writes its raw log to `log/noche-2026-08-15/`, and
   `utils/informe_noche.py` walks them at the end. A block whose self-test failed
   is reported INVALID, not summarised.
7. If a block overruns its slot, it is **cut and reported**, never extended into
   the next one's hours.

---

## 9. The morning report

`docs/history/night-2026-08-15.md`, and it answers, in this order:

1. is the tree green, and **what the flip on step 98 turned out to be**;
2. what the memory index said that was false, and what it says now;
3. Mega Lopunny / Mega Froslass: fixed by the day of 14-ago, or still open with
   a diagnosis;
4. what shipped, with its gate row and its control row side by side;
5. what was measured NEUTRO and reverted;
6. the ranked worklist for the next reading session.
