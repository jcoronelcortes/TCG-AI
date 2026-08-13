# The card census — plan, 13 August 2026

[← Documentation index](README.md) · [why it is the top pending item](playbook-vs-meta-2026-08-13.md) · [the night that asked for it](history/the-500-decks-2026-08-13.md)

**Status: written 13 August 2026, HEAD `8192c22`. Every claim in §1 was verified
on this machine while writing, against the real episode already on disk
(`log_analisys/92413910.json`, 173 steps) and against `cg/api.py`.**

**Why.** The night of 13 August found that we lose Crustle Wall (80.0 %) and
Ogerpon Verde (85.4 %) to **board and resource starvation, not misplay** — "stuck
with an escape available and not taken" is flat across four archetypes while
"stuck with no escape" separates by +8.6 to +29.2
([[las-derrotas-de-los-matchups-duros-son-hambre-no-mala-jugada]]). Starvation is
what a **list** change addresses and a scoring rule does not, and the instrument
that acts on it — a census of what each of our 60 cards actually does — does not
exist. This plan builds it.

**Scope.** Three views, as requested: the census **pooled**, the census **per
opponent archetype**, and either of those **split into wins vs losses**. Two
sources: simulated games, and **real games played on the competition ladder**.

---

## 1. What was verified while writing this plan — the design is nearly free

The single most important finding: **the engine already emits semantic card
events.** Nothing has to be inferred from action indices.

### 1.1 Every copy of every card has a unique `serial`

Measured on the real episode: our seat's serials run **3–62**, the opponent's
**63–121**. Serials are global, so **the serial identifies the owner as well as
the copy**. Two copies of card `1121` are serials 36 and 37 — distinguishable.
This is what makes a per-copy census possible rather than a per-id approximation.

### 1.2 `observation.logs` is a per-step event stream with dedicated event types

From `cg/api.py::LogType` — and these are not guesses, they are the enum:

| Event | Carries | What it settles |
|---|---|---|
| `DRAW = 4` | cardId, serial | the card reached our hand from the deck |
| **`PLAY = 10`** | cardId, serial | **"Played a card from hand"** — an actual play |
| `ATTACH = 11` | cardId, serial, target | energy/tool attached, and to whom |
| `EVOLVE = 12` | cardId, serial, target | the evolution was used |
| `MOVE_CARD = 6` | cardId, serial, **fromArea → toArea** | any other movement |
| `ATTACK = 15` | serial, attackId | which body attacked with what |
| `MOVE_CARD_REVERSE = 7` | fromArea, toArea, **no cardId** | face-down: the blind spot of §6 |

`AreaType`: `DECK=1 HAND=2 DISCARD=3 ACTIVE=4 BENCH=5 PRIZE=6 STADIUM=7 ENERGY=8
TOOL=9 PRE_EVOLUTION=10 PLAYER=11 LOOKING=12`.

**⭐ This kills the hard problem before it starts.** The obvious worry with a card
census is that a Supporter *played* and a card *discarded as Ultra Ball fodder*
both look like `HAND → DISCARD`. They do not: a real play emits **`PLAY`**, and
fodder emits only **`MOVE_CARD(HAND→DISCARD)`**. The distinction is the engine's,
not ours ([[el-forraje-barato-es-una-propiedad-de-la-mano-no-el-nombre-de-una-carta]]).

### 1.3 Volume, from one real game

285 unique events over 173 steps. Our seat alone:

    MOVE_CARD 93 · DRAW 44 · PLAY 22 · ATTACH 13 · EVOLVE 4 · ATTACK 3 · SWITCH 1

And the `MOVE_CARD` breakdown is where a second census hides:

    DECK -> LOOKING 28 | DISCARD -> HAND 20 | LOOKING -> DECK 20 | HAND -> DECK 14
    HAND -> DISCARD 14 | LOOKING -> HAND  8 | PRIZE  -> HAND  8 | ENERGY -> DISCARD 7

**`LOOKING` is a free search-quality metric.** In this game we looked at 28 cards,
**took 8, and put 20 back.** Which cards we repeatedly look at and *decline* is a
direct read on search priorities and on dead weight — and it is a signal no
instrument in this repository currently produces. It goes in the census as a
first-class state (§2), not as a footnote.

### 1.4 The real-games channel already half exists

`utils/download_player_games.py` sweeps one leaderboard player's public replays
and writes `index.csv` with exactly the columns this plan needs:

    episode_id · fecha · submission_id · asiento · resultado · rival · rival_team_id · rival_submission_id

`resultado` is `victoria`/`derrota`/`empate` — **the wins-vs-losses split comes
labelled from the source.** `submission_id` matters because two submissions are
not the same agent, and possibly not the same 60 cards.

**But: zero replays are on disk** (`find` returns none), and `~/.kaggle/` holds no
`kaggle.json` — only a 37-byte `kaggle_token.txt`. So the real-games track begins
with a credential check that can fail, and §0 Q1 and §8 both cover that.

---

## 2. The data model — the FATE of each serial, per game

One row per (game, serial). Fates are assigned from the event stream, and the
order below is the resolution order:

| Fate | Rule | What it means for the list |
|---|---|---|
| `JUGADA` | a `PLAY` event | the card did its job |
| `ADJUNTADA` | `ATTACH` | energy/tool reached a body |
| `EVOLUCIONO` | `EVOLVE` | the line advanced |
| `FORRAJE` | `MOVE_CARD(HAND→DISCARD)` with **no** `PLAY` for that serial in the same step | paid as a cost — cheap fuel, by design or by accident |
| `MUERTA_EN_MANO` | reached `HAND`, game ended with it still there | **the dead-card signal** |
| `DEVUELTA_AL_MAZO` | `MOVE_CARD(HAND→DECK)` | shuffled back (Marnie and friends) |
| **`MIRADA_Y_RECHAZADA`** | `DECK→LOOKING` then `LOOKING→DECK` | **we searched past it** — §1.3 |
| `PREMIO_TOMADO` | `MOVE_CARD(PRIZE→HAND)` | arrived via prizes |
| `NUNCA_VISTA` | appears in no event and no zone | ⚠️ **deck OR unrevealed prize — ambiguous, see §6** |

Counters per row, not just the terminal fate: `veces_jugada`, `turno_primer_juego`
(tempo), `turnos_en_mano` (how long it sat), `veces_mirada_y_rechazada`.

**Aggregation to the card (`cardId`)** gives the metrics the analysis actually
consumes:

* **tasa de robo** — how often it is seen at all
* **tasa de juego** and **conversión = jugada | robada** ← the headline metric
* **tasa de muerte en mano** — drawn and wasted
* **tasa de forraje** — how much of its value is being spent as fuel
* **tasa de rechazo en búsqueda** — looked at and declined
* **turno medio de primer juego** — is it early tempo or a late-game card

---

## 3. The three views

**V1 · Pooled.** Every game, every opponent. Answers *which of our 60 cards earn
their slot at all*.

**V2 · Per opponent archetype.** Keyed by the archetype label that
`deck/real_opponents_500/pesos.csv` already carries for simulated games, and by
`harvest_opponent_deck.py` for real ones (§4.3). Answers *which cards are dead in
which matchup* — the question that acts on the starvation finding.

**V3 · Wins vs losses, inside V1 and V2.** Reported as `win % · loss % · DIFF`,
the format `autopsy.py --census` established, because **a trait frequent in losses
cannot be told from a trait simply frequent without the control group**
([[autopsia-v3-censo-con-grupo-de-control]]). Two directions, both wanted:

* a card whose conversion is **higher in wins** → a pattern to reinforce;
* a card whose dead-in-hand or fodder rate is **higher in losses** → a pattern to
  fix.

**⚠️ V3 is where the plan can fool itself**, and §6 is the reason.

---

## 4. The two sources

### Track S · Simulated games — `utils/card_census.py`

New tool. Runs games against a chosen corpus and accumulates §2's rows. It should
**reuse `utils/parallel.py`** (the pool, 5.06× at 6 workers) and accept `--seeds`,
because a seeded run makes the census reproducible.

The one integration task, named because it is the only place surprise lives:
`selfplay.play_game` currently returns a summary, not the log stream. The stream
is in each step's `observation.logs`, so the census needs a hook that accumulates
logs per game without changing what `play_game` returns to its existing callers.
**Budget 90 minutes**; if it overruns, fall back to post-processing
`records/*.json` via `split_turns.py`, which is slower but already works.

**Both halves, mandatory** ([[validar-el-arnes-son-dos-mitades-sensibilidad-y-especificidad]]):

* *Sensitivity* — plant a card that cannot be played (e.g. an evolution whose
  pre-evolution is absent) and the census must report conversion 0 for it;
* *Specificity* — the sum over fates must equal 60 per game, every game. A serial
  with two fates or none is a bug in the resolver, not a finding.

### Track R · Real ladder games — the ground truth

**This is the part that fixes the deepest weakness of everything measured so
far.** Every number in the playbook comes from games against the *generic bot*,
and the winrate against it is **saturated** — 18 of 22 archetypes above 92 %. Real
opponents are not saturated. A card census from real games is measured against
people who are actually trying.

1. **Download.** `python utils/download_player_games.py --player <team>`. Resumable,
   one JSON per episode plus `index.csv`.
2. **Group by `submission_id`.** Two submissions are two agents and possibly two
   decks; pooling them silently averages different lists. **Verify our 60 per
   submission** by reading the serials seen and comparing against `deck.csv`, and
   report any submission whose list differs rather than folding it in.
3. **Label the opponent.** `harvest_opponent_deck.py` rebuilds a 60-card list from
   the opponent's visible zones by serial; match it against the 133 admitted lists
   by overlap (`real_opponents.py::overlap_with`) to assign an archetype. **An
   unmatched opponent is reported as `desconocido`, never forced into the nearest
   archetype.**
4. **Split by `resultado`**, which the index already provides.

**Track R's own honest bound:** we see our own zones fully, so *our* card census is
sound; the opponent's is partial by construction. This plan censuses **our 60
only**.

---

## 5. Statistical power — the constraint that shapes everything

We win ~94.5 % of simulated games. **Losses are rare, and V3 lives entirely on the
losses.** Games needed for ~200 losses:

| Opponent | Loss rate | Games for ~200 losses |
|---|---|---|
| crustle_wall_1 | 23.5 % | **~850** |
| ogerpon_verde_1 | 12.7 % | ~1 570 |
| alakazam_1 | 5.3 % | ~3 800 |
| marnie_grimmsnarl_1 | 3.3 % | ~6 150 |
| *the field, weighted* | 5.5 % | ~3 640 |

**Consequences, decided now rather than discovered at 04:00:**

* **V3 per archetype is only affordable against Crustle Wall and Ogerpon Verde**
  at ordinary game counts. Those are also the two matchups the finding is about,
  so this is a happy constraint rather than a compromise.
* **For the rest, V3 is pooled** (all archetypes' losses together) or it is not
  reported. A per-archetype loss column built on 20 losses is decoration.
* **Track R inverts this.** Real games are ~50 % losses at the top of a ladder, so
  **a few hundred real games give more loss-side signal than several thousand
  simulated ones.** This is the strongest argument for Track R and it should be
  stated in the report.

---

## 6. Where this census can lie, written before it runs

1. ⚠️ **`NUNCA_VISTA` conflates "still in the deck" with "sat in an unrevealed
   prize".** Prizes are `[None × 6]` until taken. Six of 60 cards — 10 % — are
   systematically invisible. **Never report `NUNCA_VISTA` as "we never drew it"**;
   report it as `no vista (mazo o premio)` and, where it matters, subtract the
   expected prize occupancy.
2. ⚠️ **`MOVE_CARD_REVERSE` has no `cardId`.** Face-down movements are unattributable
   by construction. Count them as a labelled residue per game; if that residue is
   large, the census is proportionally blind and must say so.
3. **`FORRAJE` depends on same-step correlation.** The rule "a `HAND→DISCARD` with
   no `PLAY` for that serial in the same step" must be validated against a known
   case — an Ultra Ball discarding two cards — before any fodder number is
   believed. One recorded episode is enough to check it.
4. **A low conversion is not a bad card.** A counter-stadium that sits in hand all
   game because the opponent never played a stadium did its job by being
   available. **The census ranks candidates for a human to judge; it does not cut
   cards.** ([[el-silencio-de-una-capa-de-valor-no-es-un-cero]])
5. **The 8 `PRIZE→HAND` events in one game exceed the 6 prizes a game awards.**
   Either the dedup key collapsed distinct events or prizes moved by an effect.
   **Resolve this before trusting any prize-related count** — it is exactly the
   kind of small arithmetic impossibility that means the reader is wrong.

---

## 7. Blocks, in dependency order

| # | Block | Output | Box |
|---|---|---|---|
| **B0** | Preflight: Kaggle credentials, `~/.kaggle/kaggle.json`, one test replay | go/no-go for Track R | 20 min |
| **B1** | The fate resolver — pure function over an event stream → §2 rows. **No games, no network: a unit-testable core.** Validated against `log_analisys/92413910.json` | `utils/card_census.py` core + tests | 90 min |
| **B2** | §6.3 and §6.5 resolved on the recorded episode | two written answers | 30 min |
| **B3** | Track S harness: pool, `--seeds`, both halves of §4 | census over simulated games | 90 min |
| **B4** | V1 + V2 on the simulated corpus, allocation by meta weight | two tables | 60 min |
| **B5** | V3 on Crustle Wall + Ogerpon Verde at ~850/~1570 games | the loss-side diff | 90 min |
| **B6** | Track R: download, group by submission, label opponents, V1–V3 | the ground-truth census | 120 min |
| **B7** | Cross-check: does Track R agree with Track S on which cards are dead? | the report's headline | 45 min |

**B1 before everything.** It is a pure function over a stream that already exists
on disk, so it can be written and fully tested without playing a single game or
touching the network — and if §6's ambiguities sink the design, they sink it in the
first 90 minutes rather than after 5 000 games.

**B7 is the block that makes this more than bookkeeping.** If the simulated census
and the real census disagree about which cards are dead, then the generic bot has
been shaping our list — and that is a bigger finding than any individual card.

---

## 8. When something breaks

| If | Then |
|---|---|
| Kaggle credentials fail (B0) | **Track R is cut, not retried blindly.** Do B1–B5, report Track R as blocked with the exact error. The simulated census is independently useful |
| The player has few public episodes | Report the count. Under ~50 games per submission, V3 on real games is not reported — say so instead of printing a thin table |
| §6.5's prize arithmetic does not resolve | Ship the census **without** prize-related states, labelled. Do not ship a number that cannot be made to add up |
| Fates do not sum to 60 (B3 specificity) | Stop. That is a resolver bug and every table downstream is void |
| A submission's 60 differ from `deck.csv` | Report it as a separate list; never pool two decks into one census |
| `MOVE_CARD_REVERSE` residue is large | Report the blindness as a percentage next to every affected table |

---

## 9. What this delivers

1. ⭐ **`utils/card_census.py`** — the resolver plus the two tracks, with both
   halves passing and §6's caveats in its docstring.
2. **`docs/card-census-2026-08-XX.md`** — V1, V2 and V3 for both sources, and B7's
   cross-check.
3. **A ranked list of list-change candidates**, each with conversion, dead-in-hand,
   fodder and search-rejection rates, and the matchups where it is dead —
   **proposed for a human to judge, never applied** ([[politica-neutro-se-revierte-salvo-valor-ilegal]]).
4. **A memory** for whatever turns out non-obvious, above all B7's verdict.

---

## 10. How this plan can be found to have been wrong

* **Every card converts well everywhere.** Then the 60 are not the problem, the
  starvation is about sequencing rather than composition, and the next instrument
  should measure *when* cards arrive rather than *whether* they are played. This is
  a real possible outcome and it would still close the top pending item.
* **The dead cards turn out to be the counter-cards** (§6.4) — cards whose value is
  in being available. Then the census has rediscovered its own bias and the useful
  output is the *tempo* column, not the conversion column.
* **Track R disagrees with Track S everywhere.** Then no simulated number in this
  repository describes the list's real behaviour, this plan's V1/V2 are void — and
  that finding alone would be worth the work.

---

Next: [the playbook](playbook-vs-meta-2026-08-13.md) · [Instruments](instruments.md) · [Tools](tools.md) · [Testing](testing.md)
