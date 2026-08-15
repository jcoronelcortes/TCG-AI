# The cost keeps the Supporter the turn plays (Mega Lucario ex, turn 4)

[← Documentation index](README.md) · [improving the agent](improving-the-agent.md) ·
[the instruments](instruments.md)

`records/registro_004_pasos_040_hasta_055.json`, steps 44–45, episode 93428975 —
**LOST**. Found by the user, reading the turn. The channel has not changed.

## The board

```text
US (6 prizes)                        OPPONENT (6 prizes)
active  Teal Mask Ogerpon ex, 2 {G}  active  Solrock, 1 {F}
bench   Applin, Chikorita,           bench   Hariyama, Riolu + Hero's Cape,
        Teal Mask Ogerpon ex 1 {G}           Lunatone, Makuhita
hand    Boss's Orders, Hydrapple ex,
        Meganium, Dawn,              stadium OUR Forest of Vitality
        Lillie's Determination
                                     Supporter slot free, attachment unspent
already played this turn: Teal Dance, Forest of Vitality, ULTRA BALL
```

`Forest of Vitality`: *each player's {G} Pokémon can evolve into {G} Pokémon
during the turn they play those Pokémon.* We had played it ourselves three
actions earlier. So a Bayleef out of the deck was **Chikorita → Bayleef →
Meganium in one turn**, and Meganium's Wild Growth then doubles every Basic {G}:
the two physical Grass on the Active pay for a Myriad Leaf Shower that costs
three. `_ogerpon_base_phys_cap` caps the manual attachment at two physical *for
this reason* — "Wild Growth doubles them ⇒ 4 effective, more than enough".

`Lillie's Determination` at **exactly six prizes** draws **8**.

## What the agent did, with the numbers

| step | menu | scores | chose |
| --- | --- | --- | --- |
| 43 | play | Ultra Ball **11900** · Lillie's 5900 · Dawn 3660 | Ultra Ball |
| 44 | cost | Boss's **36** · **Lillie's 8** · Hydrapple 3 · Meganium 3 · Dawn 2 | Boss's + **Lillie's** |
| 45 | fetch | **Meowth ex 1150** · Bayleef 950 | Meowth ex |
| 46–50 | — | Last-Ditch → Lana's Aid (3730) → Applin + 1 {G} | — |

Turn ends: a 2-prize Meowth ex on the bench, **three** cards in hand, the
Chikorita still unevolved, both Bayleef still in the deck, the Lillie's in the
discard. The Supporter slot went to the third-best Supporter of the turn.

## Four rules, one wrong question

All four ask *"what can this hand do today?"* of a hand the card being resolved
was about to change.

1. **The cost**, `DISCARD_SUPPORTER_LIVE_KEEP`. It ranks the Supporters of the
   hand on `_supp_values` — a **fetch** scale, built so searchers can price a
   card still in the deck. On this board the value layer read **Dawn 900 over
   Lillie's 750**, and correctly by its own lights: `ptcg/turn/supporters.py`
   lifts Dawn 50 above the refill *when a Forest is in play*, because a search
   for bodies then assembles a whole chain in one turn. The **play** scale,
   asked in the same tick, said `refresh_short_hand` = **5000** for the
   Lillie's. The keep floor went to the card the turn would not play; the card
   it would play fell to the ladder's generic "turn ≤ 5 and the slot is free"
   rung, which is 8.
   *The `<= 1` gate is the visible half*: `_protect_refresh_supporter` protects a
   **lone** refill, so holding two switched the protection off for both — and
   Dawn kept its own floor through this block while Lillie's had none.
2. **The fetch**, `_ub_mega_dead_prefer_meowth`. `_ub_mega_chain_now` reads the
   missing bridge **only in hand**, so it called the Meganium line dead — while
   the discard ladder of that same menu was keeping the Meganium at
   `DISCARD_LINK_THE_SEARCH_BUYS` **because the search can buy the Bayleef**.
   One Ultra Ball, two halves, opposite answers.
3. `_ub_no_attacker_prefer_meowth` and 4. `refill_after_a_ko` (`_RULES_UB_FEZ`).
   Both gated on the refill being in the **deck**; both went silent the moment
   the cost put ours in the **discard**. The price had erased its own vetoes.

## What shipped

Two changes, both deck-agnostic, both mutation-validated (each one turned off
turns two tests red).

* **`THE_COST_KEEPS_THE_SUPPORTER_THE_TURN_PLAYS`** — the keep floor is decided
  by `_best_supporter_in_hand`, the PLAY scale, instead of `_supp_values`. Only
  the KEEP half; the DROP half still reads the value layer, because "this card
  is dead today" is a statement about the board and the two scales do not
  disagree about it. It closes 1 and, with it, 3 and 4.
* **`the_turns_refill_is_already_in_hand`** in `_RULES_UB_FEZ` — a body bought
  for the cards it draws yields to a Supporter already in hand that draws more.
  It is the sentence `_RULES_UB_MEOWTH` already carries one ladder over
  (`the_turns_supporter_is_already_in_hand`), reading the same
  `_supp_in_hand_takes_the_turn`. Without it the corrected cost hands the fetch
  to a Fezandipiti ex at 1050 instead of a Meowth ex at 1150 — a different
  2-prize body for the same three cards.

The corrected turn: Ultra Ball paying **Dawn + Boss's** → **Bayleef** → Chikorita
→ Bayleef → Meganium → attach → **Lillie's Determination while still at six
prizes (8 cards)** → attack. Lillie's shuffles the hand into the deck, so it goes
**after** the evolutions and **before** the knockout.

## What was written, measured and reverted

Defect 2. Teaching `_ub_mega_dead_prefer_meowth` to count a bridge the search
still reaches in the DECK — over `EVO_LINES`, plus a `GRASS_DOUBLER_IDS` clause
for `_ub_no_attacker_prefer_meowth`, since Wild Growth is what pays for the
Active's attack — is the correct reading and it **changed no decision**:

* with the refill back in hand both flags are already silent through their own
  `Lillie's == 0` clause;
* on a hand with no refill at all the ladder hands the same fetch to
  `no_attacker_prefers_meowth` (1250) and then to `refill_after_a_ko` (1050) —
  same Meowth ex, different rule name.

Dead by ordering, in the sense `utils/rule_census.py` means it. Correcting the
*reason* a rule gives, when the consequence never lands, is folklore. Reopening
it means moving the whole refill family below a line the search can complete,
which is a re-pricing and needs its own measurement.

## Measurement

| gate | result |
| --- | --- |
| Unit suite | **2961 passed**, 25 skipped |
| New tests | 8, mutation-validated on both switches |
| Golden corpus | **1 flip in 74 decisions / 12 records**, and it is the target decision. Collateral **0** |
| Frozen corpus (`freeze_corpus --check`) | **50 records, 0 flips** |
| Census of the population | **3 of 118** discard menus with a visible hand, in 3 distinct games — **0.060/game** |
| `log_replay` on the record | 14/15 matched, 1 mismatch = the cost |
| `lint_architecture` | no violations |
| Winrate | **not run.** See below |

The two corpus numbers have to be read together. The conjunction that used to
switch the protection off — slot free, two refill Supporters in hand — arms at
**0.060/game**, the same order as other shipped-neutral findings of the
fortnight. But it arms on three frozen boards and flips **none** of them: on
those three the fetch scale and the play scale happen to name the *same*
Supporter, so the change is inert there. The population that actually moves is
the sub-population where the two scales **disagree**, and outside the record
that produced the finding the frozen corpus contains none of it. That is the
honest size of this: real, rare, and far below what any affordable winrate run
can resolve.

**The corpus arm nearly lied.** `records/golden_decisions.json` did not exist when
this started; `tests/test_golden_corpus.py` bootstraps it and then *skips*, so the
first `pytest` run wrote the baseline **from the patched code** and
`golden_corpus.py` duly reported "no changes". The real diff above was taken by
stashing the change, deleting the snapshot, regenerating from the clean tree and
restoring. Same shape as
[[un-brazo-de-control-que-no-corre-la-medicion-no-es-un-control]]: a control arm
that cannot run the measurement is not a control arm.

**Status: shipping as NEUTRAL-in-winrate.** No selfplay, no matchup matrix, no
census of how often the board happens has been run for this. It is kept on the
same ground as the other neutral merges of the fortnight — the discard of a
Supporter the turn's own scorers rank first, while the slot is free, is a
demonstrably wrong value — and it stays a candidate for reversal, not folklore,
until a census says how often two refill Supporters sit in one hand with the slot
unspent.
