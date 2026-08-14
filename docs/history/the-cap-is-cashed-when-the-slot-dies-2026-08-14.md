# The cap is cashed when the slot dies with the turn

[← Documentation index](../README.md) · A card rule of
[the day of 14 Aug 2026](../day-plan-2026-08-14.md)

**The criterion below was written before the change was measured**, in the
gate's own docstring (`utils/gate_the_cap_cashes_a_dying_slot.py`). That
ordering is the whole point: an acceptance test written after the number is not
an acceptance test.

---

## The record

`records/registro_005_pasos_062_hasta_068.json`, episode 92866795, **step 68**,
turn 5 vs **Mega Lopunny ex / Mega Froslass ex** — LOST.

The turn had already spent itself developing: Poké Pad (fetched a Chikorita),
Bug Catching Set (took a Teal Mask Ogerpon ex and a Bayleef), Chikorita to the
bench, Ogerpon to the bench. What was left on the menu was three options:

    [0] play XEROSIC'S MACHINATIONS      [1] attack (Hydrapple ex, id 195)      [2] end turn

with **the turn's Supporter slot unspent** and their hand on **six** cards. The
replay names those six, because the episode keeps both seats: **two Mega
Froslass ex, two Wally's Compassion, a Pokégear 3.0 and a Boss's Orders**.
Capping would have sent **three of the six to the discard for good**
(`XEROSIC_HAND_CAP` = 3) — their second Mega among them.

The agent attacked. The cap and the slot went into the bin together.

## Why it did that (the ladder, traced)

`PTCG_DEBUG=1 python utils/log_replay.py records/registro_005_pasos_062_hasta_068.json`
prints the answer in one line:

    [reglas xerosic->play] defecto=20

No rule of `_RULES_XEROSIC_PLAY` fires. The opponent is not an Alakazam deck, so
every `_xr_gate_alakazam` branch is shut; their hand is **six**, one card under
`XEROSIC_BIG_HAND` = 7, so `generic_very_big_hand` does not fire either. The
ladder falls to its default, `XEROSIC_SCORE_LAST_RESORT` = **20**.

Then the net that plays the Supporter before the attack that closes the turn
(`finalizar`, "WHAT DIES WITH THE TURN IS PLAYED BEFORE THE ATTACK") refuses to
lift it, because of one guard:

    if scores[_sbai] <= SUPP_SCORE_LAST_RESORT_BAND:   # 20
        continue

whose stated reason is: *the free slot is not a reason to spend the CARD, which
keeps its value for tomorrow.* The attack scores 1000 and wins the menu.

## What is wrong with that reason, in two halves

**1. Tomorrow's price is theirs to set.** "It keeps its value for tomorrow" is
an argument about OUR board, and it is sound for the other Supporters at that
band — a Lana's Aid is worth *more* tomorrow, because the discard pile only
grows. Xerosic's Machinations is priced by the size of **their** hand. How much
it is worth tomorrow is the opponent's decision, and between now and then they
take a whole turn to make it.

And the estate already says so, out loud, in the other scorer: outside the
Alakazam matchup and under `XEROSIC_BIG_HAND` the **discard** ladder prices this
same card at **60** — the most throwable Supporter band there is, cheerful Ultra
Ball fodder (`ptcg/turn/options/card.py`). We were refusing to cash for three of
their cards a card we would happily bin face-down to pay for a search. That is
exactly the contradiction `XEROSIC_BIG_HAND` was introduced to remove, read from
the side nobody had checked: **the card we KEEP and the card we would PLAY
cannot disagree.**

**2. The guard was never consistent with itself.** At the last-resort band the
card *is* spent by elimination whenever the menu is `{play it, END}` — END
scores 0. The estate knows this: it is why `alakazam_needs_the_hand_floor` had
to be written as a **hard veto** instead of a fall-through, and the comment says
so in as many words. So whether the last resort got played was decided by
whether our active happened to have an attack available — which has nothing to
do with keeping a card for tomorrow. Both menus end the turn.

## The rule

`_sba_price_is_theirs` in `ptcg/turn/finalize.py`, read **only** by the net that
fires when the turn is already closing on an attack. One exception to the
last-resort guard, scoped to the property that breaks its premise:

| what | where |
| --- | --- |
| plays whose price hangs on their side of the table | `OP_HAND_PRICED_PLAY_IDS` = {Xerosic's Machinations} |
| how big their hand has to be | `XEROSIC_FREE_SLOT_HAND` = `2 * XEROSIC_HAND_CAP` = **6** |

The floor is the printed number read twice — **the cap has to send to the
discard at least as many cards as it leaves behind** — not a tuned threshold. It
lands one card below `XEROSIC_BIG_HAND`, which is the right distance: the
difference between the two is the price of the Supporter slot, and here the slot
is free.

What the exception cannot do, by construction:

* **it cannot resurrect a veto** — the loop's `scores[_sbai] <= _sba_best`
  starts at 0 and drops every negative, so the Alakazam hand floor
  (`alakazam_needs_the_hand_floor`, `SCORE_VETO`) is untouched;
* **it cannot steal the slot from the card the ladder yielded it to** — a live
  Lillie's or Dawn scores in the thousands and wins the same loop. When that
  card is not on the menu, the attack was going to bury it anyway;
* **it cannot delay the finisher** — the net only fires when the menu winner is
  an attack **in tier 0**, which excludes `_TIER_WIN_ATTACK`.

## The criterion (written first)

This rule removes a contradiction the estate states in its own words, plus an
incoherence that has nothing to do with keeping cards (the `{play it, END}`
asymmetry above). Both stand on the game's own arithmetic, so **neutral does not
order a revert here: it orders the mark.** A LOSS that clears the noise floor
does order the revert.

## The exposure

**The golden corpus (`records/`, the harvested real games) flips exactly ONE
decision** — step 68 itself, the record this was written from. Nothing else in
thirteen records moves.

**The frozen fifty (`tests/corpus/`) flip ZERO**, and that is the point rather
than an absence of evidence: all fifty are Alakazam games, the matchup where the
floor vetoes below and the cap scores in the thousands above, so the exception
is unreachable **by construction**. The oracle walks it anyway so the claim "this
rule does not touch the matchup the card exists for" is measured and not
asserted.

**The self-play firing census** (`--census`, 1 000 games per deck) is where the
window is actually visible — and it also carries the one finding this change did
NOT act on:

| deck | asked / game | **fires** / game | their hand when asked |
| --- | --- | --- | --- |
| mega_lopunny_mega_froslass_1 | 0.14 | **0.03** | 4:65 · 5:43 · 6:28 |
| marnie_grimmsnarl | 0.21 | **0.03** | 4:104 · 5:70 · 6:33 |
| dragapult | 0.07 | **0.02** | 4:29 · 5:24 · 6:21 |
| crustle_kangaskhan | 0.23 | **0.05** | 4:79 · 5:93 · 6:54 |
| **mean** | 0.16 | **0.03** | 4:277 · 5:230 · 6:136 |

The window is real and it is **dominated by hands of four and five**, which the
floor of six excludes: **136 of 643** boards where the net reaches the cap with
the slot dying actually clear it — about one in five. That is deliberate — at four the
cap discards ONE card, which is the mistake `alakazam_needs_the_hand_floor` was
written about — but **whether the floor should be five is an open question this
change does not answer**, and it is the queued next step. It needs boards at
those hand sizes, and neither corpus has any.

## The measurement

### The rules oracle, K=100 (`utils/oracle_the_cap_cashes_a_dying_slot.py`)

At 0.03 firings per game the self-play winrate cannot resolve this rule at any N
worth paying for, so the question was asked the other way round: on the boards
where the rule changed the choice, does the choice it now makes **roll out
better under the engine's own rules**? Two gradeable boards, and both were in
the estate before this rule existed. Each opponent list is **found by coverage**,
not assumed — the first draft of the instrument graded a Dragapult board under
an Alakazam list, which is the failure the coverage column now prevents.

**Board 1 — `dragapult` step 138** (fixture captured for another rule; rival
`dragapult_12`, 94 % of their visible board):

| option | rollouts won | prize margin |
| --- | --- | --- |
| with the rule (cash the cap, then attack) | **61/100** | **−0.12** |
| without it (attack, cap dies) | 49/100 | −0.56 |
| delta | **+12 pp** | **+0.44** |
| the board's own floor (same option, other seeds) | 3 pp | 0.09 |

**Clears its own floor by four times on both columns, in favour of the rule.**

**Board 2 — the record, `registro_005` step 68** (rival
`mega_lopunny_mega_froslass_1`, **100 %** of their visible board):

| option | rollouts won | prize margin |
| --- | --- | --- |
| with the rule | 100/100 | +5.63 |
| without it | 100/100 | +5.66 |
| delta | +0 pp | −0.03 |
| the board's own floor | 0 pp | 0.08 |

**Inside the floor — saturated.** From that board the rollouts win every time
either way (we were ahead on prizes, 5 to their 6), so this instrument has no
resolution left on it. It is reported because hiding a board that grades nothing
is how a two-board sample becomes a one-board claim.

The hand is SAMPLED on both boards (`opponent_obs=None`: the records keep one
seat's observations), so every grade is against a legal world rather than the
true one — the same one for both options of a board, which is what keeps the
comparison fair.

### The self-play gate, 5 000 games per arm per deck

Both arms are the same tree loaded twice, with `XEROSIC_FREE_SLOT_HAND` rebound
out of reach in the baseline — the code as it was, one number out of place and
nothing else. Provenance is asserted before a game is played.

| deck | with the rule | without | delta | prizes/game | forfeits |
| --- | --- | --- | --- | --- | --- |
| mega_lopunny_mega_froslass_1 | 97.44 % | 97.38 % | +0.06 pts (z 0.19) | 5.08 vs 5.12 | 0/0 |
| marnie_grimmsnarl | 93.92 % | 94.50 % | −0.58 pts (z −1.24) | 5.55 vs 5.54 | 0/0 |
| dragapult | 97.70 % | 97.84 % | −0.14 pts (z −0.47) | 4.17 vs 4.14 | 0/0 |
| crustle_kangaskhan | 77.36 % | 76.54 % | +0.82 pts (z 0.97) | 4.25 vs 4.28 | 0/0 |
| **aggregate (20 000 games/arm)** | **91.61 %** | **91.56 %** | **+0.04 pts** (z 0.14) | | 0/0 |

**The noise floor of the same session** (`--control`: both arms neutralised, the
same code twice, same N):

| deck | arm A | arm B | delta |
| --- | --- | --- | --- |
| mega_lopunny_mega_froslass_1 | 97.68 % | 97.56 % | +0.12 pts |
| marnie_grimmsnarl | 94.64 % | 93.14 % | **+1.50 pts (z 3.13, p 0.002)** |
| dragapult | 97.62 % | 97.30 % | +0.32 pts |
| crustle_kangaskhan | 76.40 % | 76.78 % | −0.38 pts |
| **aggregate (20 000 games/arm)** | **91.58 %** | **91.19 %** | **+0.39 pts** (z 1.39) |

The Marnie row is the reason this gate is never read without its control. With
the rule that cell says **−0.58 pts**, which reads as damage — and the SAME CODE
against itself, same N, separates that deck by **+1.50 pts at z 3.13**. A naive
significance test calls the noise floor significant. The measured delta is a
third of it and the wrong sign for it.

## The verdict: NEUTRAL on the bot, POSITIVE on the rules, and it ships marked

**Winrate: neutral, and it costs nothing.** +0.04 pts aggregate over 20 000
games per arm, against a noise floor of +0.39 pts taken in the same session with
identical code in both arms. Not one cell clears its own control, in either
direction, and **no arm forfeited a single game** — the change reorders legal
menu options and nothing else. The exposure explains the reading: 0.03 firings
per game and one corpus decision. A winrate against a bot we beat 91–97 % of the
time cannot resolve that, which is the same saturation
`utils/search_oracle.py` was built for.

**Rules: positive where the instrument had resolution.** The one board that
graded — Dragapult step 138, a fixture captured for an unrelated rule — puts the
new choice **+12 pp and +0.44 prize margin ahead**, over that board's own floor
of 3 pp / 0.09. The record's own board saturates at 100/100 and grades nothing,
and that is reported rather than dropped.

**So it ships, marked.** The criterion written before the numbers said neutral
orders the mark and not a revert, because the rule stands on two things the
estate can check without a bot: the discard scorer and the play scorer were
contradicting each other about the same card, and the last-resort band was
spending it or not depending on whether our active happened to have an attack.
Both are still true after the measurement. What the gate earned is the sentence
it was asked for: **this costs nothing measurable**, and the corpus is clean —
the single flip is the board the rule was written about.

**What it does NOT claim.** That six is the right floor. See the census above:
four in five of the boards in this window have their hand at four or five, and
this change leaves every one of them behaving exactly as before.

## What changed

| file | what |
| --- | --- |
| `ptcg/cards/ids.py` | `OP_HAND_PRICED_PLAY_IDS`, `XEROSIC_FREE_SLOT_HAND` |
| `ptcg/turn/finalize.py` | `_sba_price_is_theirs`, the exception in the pre-attack net, `DYING_SLOT_CENSUS_SINK` |
| `tests/test_the_supporter_slot_dies_with_the_attack.py` | the guard's test now reads the board WITHOUT the cap; two new tests for the exception and for its floor |
| `tests/main_support.py` | `spend_the_supporter_slot`, the "one action later" helper |
| `tests/test_main_regressions_5.py`, `tests/test_the_prize_is_cashed_by_the_body_that_outlasts.py` | two claims about the ATTACK, re-asked on the menu where the reorder is already done |
| `utils/gate_the_cap_cashes_a_dying_slot.py` | the two-arm gate and the firing census |
| `utils/oracle_the_cap_cashes_a_dying_slot.py` | the rules oracle |
