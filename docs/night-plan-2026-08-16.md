# The night the search plan starts running — 16 August 2026

[← Documentation index](README.md) · [the week plan](plan-la-busqueda-en-juego-2026-08-15.md) ·
[the instruments](instruments.md) · [last night](night-plan-2026-08-15.md)

**Status: written 00:10, 16 August 2026. HEAD `2df5967`, tree clean, suite GREEN
(3016 passed, 25 skipped, 39 s), lint clean, golden corpus clean. Written to run
autonomously, end to end, while the user sleeps.**

This night executes the autonomous phases of the week plan (S0.2, S1, S2-shadow,
S6) plus a ladder validation of the thirteen merges shipped during the day of
15 August (10:53–00:02, all on census + rules oracle, none ladder-measured), plus
housekeeping. Everything search-related is built as an **instrument in shadow**:
`main.py`, `deck.csv`, the submission and the frozen corpus are not touched.

---

## §0 — The six questions, answered at 00:05

| # | Question | Answer |
|---|---|---|
| P1 | Build play-time search as shadow only? | **Yes** — new packages `ptcg/opponent/`, `ptcg/search/`; `main.py` never imports them, so the AST packer keeps them out of the submission. S0.1 proper stays a daytime call |
| P2 | Commit to main? | **Yes** — branch per hypothesis (`noche/*`), merge only on green suite+lint+golden. **Never push** |
| P3 | Budget | Until 07:00, JOBS=6, code cutoff 06:20, cut checkpoints 01:30/03:30/05:30 |
| P4 | NEUTRO | Reverts on main, survives on its `noche/*` branch. Exception: T1 is validation (NEUTRO = OK); S1 falling back to the flat prior still merges, documented |
| P5 | CI | Fix the CONTRIBUTING text (it claims per-push CI; off since `a9a53ea`). CI stays off |
| P6 | The nine `_v_*.py`/`main_pre_*.py` in the root | Move to `attic/brazos-2026/`, never delete at night |

Decided before the night and not askable: measurements run from `git archive`
trees with `cg/build` symlinked, never from the working tree; logs only under
`log/noche-2026-08-16/`; `pesos.csv` by absolute path (gitignored, absent from
exported trees); census before winrate; every tool's flags checked with
`--help` before first use; zero questions after §0.

## §1 — What moved in the last 24 hours

Thirteen finding merges between `d34cb15` (10:53) and `2df5967` (00:02), all
shipped on census + oracle, none measured on the ladder. Two carry a design
lesson this night uses directly: the setup-seat oracle flipped sign with the
opponent's rollout policy (+1.89 margin with opponent-as-agent, −0.50 with
random), confirming the pivot-wall finding that `policy="agent"` drives both
seats out of one `AGENT_STATE`. The shadow grader therefore uses the **mixed
policy** (`mixed_rollout` pattern: our seat = agent with belief reset, their
seat = random), and the in-shadow arbiter uses a stateless `fast_policy` —
rule R12 makes that structural.

## §2 — The tracks

| Track | What | Pre-registered criterion |
|---|---|---|
| **T0** ground | suite+lint+golden, export `tree_head` (HEAD) and `tree_ref` (`d34cb15`), this plan committed | red tree aborts the night |
| **T1** ladder validation | `matchup_matrix.py --opponents <abs> --weights --allocation peso --games 400 --seeds 400 --jobs 6`, one arm per tree, `compare_runs.py` on the two outputs | zero forfeits both arms; weighted delta ≥ −2.0 pp (the ±2 pp floor at 400/matchup means this is damage control, not a fine reading). Fail ⇒ RED in the report + bisection worklist; no night-time reverts of day merges |
| **T2** S1 posterior | `ptcg/opponent/prior.py` (coverage matching promoted from the `oracle_*` twins, now × `peso_meta`; a list that cannot host the board gets exact zero) + `utils/opponent_prior_census.py` over the frozen corpus + fresh records; `tests/test_opponent_prior.py` | top-1 correct no later than the flag (median); ≥90 % archetype accuracy at and before flag fire; the four documented flag defects do not reproduce. Fail ⇒ pre-registered fallback `flat_prior()`, merged documented |
| **T3** S0.2+R12+policy | `tests/test_search_from_inside_the_agent.py` (seeded game replayed with a search interleaved must be identical); R12 in the linter (nothing under `ptcg/search/` imports `AGENT_STATE` or calls `main.agent`); `ptcg/search/fast_policy.py` stateless | fast_policy must beat random on the `self_test` sensitivity board; if not, T4 rolls random and fast_policy stays on its branch. S0.2 and R12 merge regardless |
| **T4** S2 shadow | `ptcg/search/arbiter.py`: `determinize(obs, None, …)`, opponent deck resampled from the posterior per rollout, K≥50, `None` unless the best clears the board's own floor (second batch); S5 safety already in shadow (blanket try/except → None, `search_end` **and** `search_release` on every path, wall deadline per rollout and per decision); `utils/shadow_arbiter.py` N=600 over corpus+records, disagreements graded by the omniscient oracle at K=100 with the mixed policy | exception rate <1 % of decisions; frozen-corpus flip-diff stays green; graded disagreements are reported, not acted on (the S4 gate is a daytime job). If done by 04:20, extend to N=2000 |
| **T5** S6 worklist | targeted autopsies (crustle_wall, ogerpon_verde) + top shadow disagreements the omniscient grader endorses ⇒ `log/noche-2026-08-16/lectura-manana.md`, ≤10 items ranked by prizes at stake | a reading deliverable; has no NEUTRO |
| **T6** housekeeping | (a) fresh records for the census — **after checking whether `record_corpus.py` wipes `records/`**; if it does, back up episode 93430769 first and restore after; (b) CONTRIBUTING truth fix, `attic/` move, `notas-memoria.md` for the morning | nothing deleted, frozen corpus untouched |

## §3 — Cut order when the clock bites

1. T4 extension to N=2000 → 2. T5 whole → 3. the shadow run (arbiter code still
merges with its unit tests; the run command goes in the report) → 4. T6b except
CONTRIBUTING → 5. fast_policy (S0.2+R12 are never cut). **Never cut:** T0, T1,
T2, the morning report.

## §8 — What makes this safe to run unattended

Red tree blocks commits · branch per hypothesis · NEUTRO per P4 · **never
`git push`** · never `deck.csv`, `main.py`, `tests/corpus/frozen_records.json.gz` ·
logs only to `log/noche-2026-08-16/` · measurements only from exported trees ·
a block that overruns its window is cut at the next checkpoint and leaves its
resume command in the report.

## §9 — The morning report

`docs/history/night-2026-08-16.md`, answering in order: T1 verdict (forfeits,
weighted delta, RED/OK); S1 census against its four criteria (first line says
if the flat fallback shipped); S0.2/R12/fast_policy green/red per piece; shadow
N, K, abstention and exception rates, graded-disagreement table;
`lectura-manana.md` and `notas-memoria.md` linked; resume commands for
everything cut; the §0 answers that went unused.
