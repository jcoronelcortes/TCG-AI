"""THE ENTRY POINT. The competition calls `agent(obs_dict)` and we return a move.

WHAT THE CONTRACT IS. The engine hands us an observation containing a MENU of
legal options and asks which one we take; we return a list of indices into it.
`agent()` is called many times per turn -- once per menu, including menus that
open during the OPPONENT's turn for forced selections -- so "one call" is one
decision, not one turn.

WHERE THE LOGIC LIVES. Almost all of it is in the `ptcg/` package, imported
with `import *` at the top: card data, the pure calculators, the per-card
decision modules and the turn pipeline. What is left in this file is the
ORCHESTRATION -- reading the observation into the several hundred flags the
rules consult, and running the phases in order:

    read the observation, refresh the belief and the per-turn state
    build the TURN PLAN (what the prize count says the turn is for)
    price the Supporters, rank the energy destinations
    score every option in the menu       -> ptcg/turn/scoring.py
    order by tier and choose             -> ptcg/turn/finalize.py

...plus the handful of scorers not yet moved out (Boss's Orders, Lillie's,
Night Stretcher's play branch, Ultra Ball's, Forest of Vitality's).

FOUR CONSTRAINTS THIS FILE IS SHAPED BY, all enforced by
`utils/lint_architecture.py`, and none of them obvious from reading the code:

  * IT RUNS UNDER `exec()`, NOT `import`. The Kaggle container loads this file
    into a bare dict, so there is no module object and `__name__` may not
    exist. That is why the imports are at the very top (the agent's directory
    is only on `sys.path` while this module runs, so a deferred import would
    not resolve) and why the state bridge below installs itself only when a
    module object is actually present.
  * NOTHING BINDS A NEW NAME AFTER `def agent` (R3). Under `exec()` the
    definition order is the only order there is.
  * NO THIRD-PARTY DEPENDENCIES. The container installs nothing.
  * NEVER IMPORT A MUTABLE BY NAME (R1). `from x import flag` binds a COPY, so
    the importer keeps reading the value it had at import time. State goes
    through `AGENT_STATE`, always.

FAILING IS WORSE THAN DECIDING BADLY. An exception here forfeits the game,
which is why the option scorers swallow their errors and fall back to a legal
move rather than propagating.

Start with docs/code-map.md for the layout and docs/how-the-agent-thinks.md for
the reasoning; `ptcg/__init__.py` documents the package layers.
"""

import os
import sys
from collections import defaultdict
from dataclasses import dataclass, replace as _dc_replace
from math import comb as _comb
from typing import NamedTuple

from cg.api import AreaType, CardType, EnergyType, Observation, SelectContext, OptionType, Card, Pokemon, SpecialConditionType, LogType, all_card_data, all_attack, to_observation_class

# Card constants (IDs, groups and tables). Extracted in wave 1 of the
# refactor; see docs/project-history.md. It goes AT THE TOP on purpose:
# in the Kaggle container the agent's directory is only on sys.path
# while this module runs, so a deferred import would not resolve.
from ptcg.state.agent_state import AGENT_STATE, AgentState  # noqa: F401
from ptcg.cards.costs import ATTACK_ENERGY_REQ_BASE  # noqa: F401
from ptcg.cards.groups import *  # noqa: F401,F403
from ptcg.cards.ids import *  # noqa: F401,F403
from ptcg.cards.lines import *  # noqa: F401,F403
from ptcg.cards.tables import *  # noqa: F401,F403
from ptcg.engine.context import *  # noqa: F401,F403
from ptcg.engine.plan import *  # noqa: F401,F403
from ptcg.engine.rules import *  # noqa: F401,F403
from ptcg.state.zones import *  # noqa: F401,F403
from ptcg.state.logs import *  # noqa: F401,F403
from ptcg.state.tracking import *  # noqa: F401,F403
from ptcg.calc.card import *  # noqa: F401,F403
from ptcg.calc.damage import *  # noqa: F401,F403
from ptcg.calc.energy import *  # noqa: F401,F403
from ptcg.calc.grass import *  # noqa: F401,F403
from ptcg.calc.probability import *  # noqa: F401,F403
from ptcg.calc.opponent import *  # noqa: F401,F403
from ptcg.calc.board import *  # noqa: F401,F403
from ptcg.decision.boss_orders import *  # noqa: F401,F403
from ptcg.decision.bug_catching_set import *  # noqa: F401,F403
from ptcg.decision.disruption import *  # noqa: F401,F403
from ptcg.decision.stadiums import *  # noqa: F401,F403
from ptcg.decision.meowth import *  # noqa: F401,F403
from ptcg.decision.night_stretcher import *  # noqa: F401,F403
from ptcg.decision.poke_pad import *  # noqa: F401,F403
from ptcg.decision.supporters import *  # noqa: F401,F403
from ptcg.decision.ultra_ball import *  # noqa: F401,F403
from ptcg.cards.scoring import *  # noqa: F401,F403
from ptcg.engine.debug import *  # noqa: F401,F403
from ptcg.turn.game_plan import build_turn_plan, _recovery_creates_the_ko  # noqa: F401
from ptcg.turn.ctx import TurnCtx  # noqa: F401
from ptcg.turn.finalize import finalizar  # noqa: F401
from ptcg.turn.ctx_scoring import ScoringCtx  # noqa: F401
from ptcg.turn.scoring import score_option, _SALTAR  # noqa: F401
from ptcg.turn.supporters import evaluate_supporters as _evaluate_supporters_impl  # noqa: F401
from ptcg.turn.supporters_ctx import CtxEvaluateSupporters  # noqa: F401
from ptcg.turn.energy import _energy_score_base as _energy_score_base_impl  # noqa: F401
from ptcg.turn.energy_ctx import CtxEnergyScoreBase  # noqa: F401

# =============================================================================
# Compatibility bridge: `main.<state field>` <-> `AGENT_STATE.<field>`
# -----------------------------------------------------------------------------
# The state that persists between turns lives in `AGENT_STATE` (ptcg/state/agent_state.py),
# but the suite sets and reads it as an attribute of `main` in ~1,285 places.
# Without this bridge those writes would go to a dead attribute: the tests WOULD
# KEEP PASSING while the agent reads state that nobody updates -- exactly the
# silent failure wave 3 exists to eliminate.
#
# Rewriting the suite at the same time as changing what the suite watches is the
# worst way to do this step. The bridge allows migrating the state with the
# harness intact; removing it (and updating the tests) is a later cleanup, with
# the refactor already green.
#
# In the Kaggle container it is NOT installed: there main.py runs with exec()
# over an empty dict, so there is no module object and `__name__` does not even
# exist. The submission runs the pure `AGENT_STATE.x` path, which is the one
# tests/test_submission.py exercises (loading with the real loader, not with
# `import`).
# =============================================================================
_STATE_FIELDS = frozenset(vars(AgentState()))
_mod = sys.modules.get(globals().get('__name__') or '')
if _mod is not None:
    class _MainWithState(type(_mod)):
        def __getattr__(self, name):
            if name in _STATE_FIELDS:
                return getattr(AGENT_STATE, name)
            raise AttributeError(name)

        def __setattr__(self, name, value):
            if name in _STATE_FIELDS:
                setattr(AGENT_STATE, name, value)
            else:
                super().__setattr__(name, value)

    _mod.__class__ = _MainWithState


# =============================================================================
# AGENT CONVENTIONS (read before touching scores or energy)
# -----------------------------------------------------------------------------
# ENERGY:
#   * `len(pokemon.energies)` is ALREADY the EFFECTIVE energy. The observation
#     applies Meganium's Wild Growth by duplicating every PHYSICAL basic Grass
#     energy, so it must NEVER be multiplied by 2 again. That is why
#     `_grass_mult()` returns 1. Compare `len(energies)` directly with
#     ATTACK_ENERGY_REQ.
#   * `_grass_attach_unit()` = EFFECTIVE energy provided by attaching ONE basic
#     Grass: 2 if Meganium is in play, 1 if not.
#   * The OPPONENT's energies in our observation are NOT doubled.
#
# SCORING:
#   * `agent(obs)` scores every option; the highest one is played.
#   * Energy requirements to attack: ATTACK_ENERGY_REQ (the single source).
#   * Base damage of our attackers: _attacker_base_damage(...) (the single
#     source). Weakness/resistance/immunity are applied separately in
#     _our_effective_damage.
#
# OPTION TYPES (OptionType, numeric values in the log):
#   7 = PLAY (play a card from hand)    13 = ATTACK
#   12 = PASS                           14 = END TURN        3 = target selection
# =============================================================================


file_path = "deck.csv"
if not os.path.exists(file_path):
    file_path = "/kaggle_simulations/agent/" + file_path
with open(file_path, "r") as file:
    csv = file.read().split("\n")
my_deck = []
for i in range(60):
    my_deck.append(int(csv[i]))

















try:
    _ID_AUDIT_MISMATCHES = _validate_id_constants()
except Exception:
    _ID_AUDIT_MISMATCHES = []







# =============================================================================
# RULES ENGINE (phase 4): rules with a NAME and a TRACE.
#
# The problem it solves: inline scoring buries every rule as an if with
# magic numbers; when two rules collide (e.g. a clamp that overrides a high
# score), finding the culprit means instrumenting by hand. Here every
# rule is an object with a name; the resolver leaves a readable trace of which
# rule set the score and which adjustments transformed it (visible with
# PTCG_DEBUG).
#
# Semantics IDENTICAL to the code it replaces:
#   - _FixedRule: an if/elif chain -> the FIRST one whose `when` is True wins.
#   - _Adjustment: sequential transformations applied afterwards (clamps, ceilings).
# Migrated blocks: the Ultra Ball fetch (11 branches), Night Stretcher (12),
# _score_boss_orders_play. Zero behaviour change in each migration
# (suite + golden corpus + invariants + self-play).
# =============================================================================






























# =============================================================================
# EVOLUTION CHAINS DERIVED FROM THE DECK (deck-agnostic)
# -----------------------------------------------------------------------------
# `EVO_LINES` is hand-written for THIS deck. The Grand Tree engine (see
# `_gt_*`) has to work with ANY deck.csv, so it derives the
# Basic -> Stage 1 -> Stage 2 chains by reading `CardData.evolvesFrom` (which is
# the NAME of the pre-evolution, not an id) from the cards that are really in
# the deck. It is computed ONCE when the module is imported.
# =============================================================================

_CARD_NAME = {cid: (c.name or "") for cid, c in card_table.items()}

for _cbn in card_table.values():
    _CARD_BY_NAME.setdefault(_cbn.name or "", _cbn)










for _epn in card_table.values():
    _epn_pre = getattr(_epn, 'evolvesFrom', None)
    if _epn_pre:
        _EVOLUTIONS_BY_NAME.setdefault(_epn_pre, []).append(_epn)








_EVO_BY_NAME, _DECK_CHAINS = _build_deck_chains(my_deck)

# Pokemon that are REALLY in deck.csv. It serves to distinguish "a body the
# curated configuration (ATTACK_ENERGY_REQ / MAIN_ATTACKERS / per-card caps)
# knows and excludes on purpose" from "a body it simply does not know". The
# former must stay excluded; the latter can be resolved from the card data.
# See `_ns_useful_energy_threshold`.
_DECK_POKEMON_IDS = frozenset(
    cid for cid in set(my_deck)
    if (card_table.get(cid) is not None
        and card_table[cid].cardType == CardType.POKEMON))

# Deck basics that OPEN a chain (they have at least one Stage 1 in the deck).
_GT_BASICS_WITH_CHAIN = frozenset(b for b, _s1, _s2 in _DECK_CHAINS)










def _gt_planes(my_state, cards_in_deck, field_counts, our_first_turn,
               vetoes_ex_stage=False, doomed_active=False):
    """All Grand Tree plans that are EXECUTABLE now, best to worst.

    A plan is executable if the Basic is in play, did NOT come down this turn
    (`appearThisTurn`), we are not on our first turn, and its Stage 1 is still
    in the deck. The Stage 2 is only added if it is also left in the deck and the
    matchup does not advise against it.
    """
    if our_first_turn:
        return []
    planes = []
    for area, idx, pkmn in _gt_slots_propios(my_state):
        if not isinstance(pkmn, Pokemon) or getattr(pkmn, 'appearThisTurn', False):
            continue
        data = card_table.get(pkmn.id)
        if data is None or not data.basic:
            continue
        energy = len(getattr(pkmn, 'energies', None) or [])
        for basico, s1, s2 in _DECK_CHAINS:
            if basico != pkmn.id:
                continue
            if cards_in_deck.get(s1, {}).get(ZONE_DECK, 0) <= 0:
                continue
            s2_ok = bool(s2) and cards_in_deck.get(s2, {}).get(ZONE_DECK, 0) > 0
            if s2_ok and vetoes_ex_stage:
                s2_data = card_table.get(s2)
                if s2_data is not None and (s2_data.ex or s2_data.megaEx):
                    s2_ok = False
            final = s2 if s2_ok else s1
            value = _gt_body_value(final) + energy
            if s2_ok:
                value += GT_VALUE_STAGE2
            if field_counts.get(final, 0) == 0:
                value += GT_VALUE_DIVERSIFY
            if (doomed_active and area == AreaType.ACTIVE
                    and _gt_prizes_of(final) > _gt_prizes_of(basico)):
                # The active is doomed: turning it into a body worth MORE
                # prizes before it is knocked out gives away the difference. It is not
                # a veto (if it is the only plan, it is still worth it for the
                # HP), it merely yields the turn to any BENCHED Basic.
                value -= GT_PENALTY_DOOMED_ACTIVE
            planes.append(_GrandTreePlan(
                area=area, index=idx, serial=getattr(pkmn, 'serial', -1),
                basic_id=basico, stage1_id=s1,
                stage2_id=(s2 if s2_ok else 0), value=value,
                # Two copies of the same Basic produce two IDENTICAL plans and
                # the sort used to keep the one in the lowest slot. Evolving
                # does not heal, so the copy that gains from the chain is the
                # damaged one. The attack projected against the ACTIVE does not
                # travel in this signature (`doomed_active` already covers that
                # case), so up front it is measured with 0: the drip and the
                # movable counters only, which never over-states the danger.
                body_bias=evolution_body_bias(
                    pkmn, final, area == AreaType.ACTIVE,
                    0 if area == AreaType.ACTIVE
                    else AGENT_STATE._op_bench_snipe_dmg)))
    planes.sort(key=lambda p: (-p.value, -p.body_bias, int(p.area), p.index))
    return planes


def _gt_score_selection(o, card, plan, planes, my_state, field_counts):
    """Scores ONE option of the sub-selections opened by the Grand Tree ability
    (`select.effect.id == Grand_Tree`). The simulator emits them in later calls
    to `agent()` and with different contexts depending on the step, so here they
    are not told apart by `context` but by WHERE the card is:

      * area ACTIVE/BENCH -> "which Pokemon OF MINE evolves": the plan's serial
        rules; if it does not appear (e.g. the plan was recomputed after step
        1), it falls back to the ranking of plans and, as a last resort, to
        preferring a Basic with an available chain.
      * any other area (DECK / LOOKING) -> "which card do I bring": the plan's
        Stage 2 first, then the Stage 1, and underneath a deck-agnostic
        criterion (any evolution whose pre-evolution is in play, valued by
        `_gt_body_value` and with a bonus if we do not have that body yet).

    It never returns a veto: these selections are usually mandatory once the
    ability has been activated, and being left with no valid option would be
    worse than choosing the least bad one.
    """
    cid = getattr(card, 'id', 0)

    if o.area in (AreaType.ACTIVE, AreaType.BENCH):
        serial = getattr(card, 'serial', None)
        for pos, p in enumerate(planes):
            if serial is not None and serial == p.serial:
                # The order of `planes` is ALREADY the order of preference.
                return 10000 - pos
        data = card_table.get(cid)
        if data is not None and data.basic and cid in _GT_BASICS_WITH_CHAIN:
            return 100
        return 1

    if plan is not None and plan.stage2_id and cid == plan.stage2_id:
        return 10000
    if plan is not None and cid == plan.stage1_id:
        return 9000

    data = card_table.get(cid)
    if data is not None and data.cardType == CardType.POKEMON:
        pre = getattr(data, 'evolvesFrom', None)
        if pre and any(_CARD_NAME.get(getattr(p, 'id', 0)) == pre
                       for _a, _i, p in _gt_slots_propios(my_state)):
            return (1000 + _gt_body_value(cid)
                    + (500 if field_counts.get(cid, 0) == 0 else 0))
    return 1


def _gt_wanted_basics(cards_in_deck, field_counts, vetoes_ex_stage=False):
    """Basics that, ONCE PUT INTO PLAY, open a Grand Tree chain for the
    next turn, ordered by the value of the body they lead to. It feeds the
    fetch (deck / discard) and putting them down from hand."""
    ranking = {}
    for basico, s1, s2 in _DECK_CHAINS:
        if cards_in_deck.get(s1, {}).get(ZONE_DECK, 0) <= 0:
            continue
        s2_ok = bool(s2) and cards_in_deck.get(s2, {}).get(ZONE_DECK, 0) > 0
        if s2_ok and vetoes_ex_stage:
            s2_data = card_table.get(s2)
            if s2_data is not None and (s2_data.ex or s2_data.megaEx):
                s2_ok = False
        final = s2 if s2_ok else s1
        value = _gt_body_value(final) + (GT_VALUE_STAGE2 if s2_ok else 0)
        if field_counts.get(final, 0) == 0:
            value += GT_VALUE_DIVERSIFY
        if value > ranking.get(basico, -1):
            ranking[basico] = value
    return ranking














# BASE cost, immutable. `ATTACK_ENERGY_REQ` is the "single source of truth" that
# ~50 places read, so the Nighttime Mine tax is applied by adjusting that
# dictionary ONCE per call to agent() (see `_aplicar_impuesto_tera`) instead of
# touching the 50 reading points. It is ALWAYS recomputed from this base, so
# that the value does not accumulate between calls or between games.



# Main attackers evaluated in the ready-to-attack blocks.
MAIN_ATTACKERS = (
    Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex,
    Tapu_Bulu, Fezandipiti_ex, Meganium, Pinsir,
)










# --- FINISHER FISHING: the attack that today depends only on the DRAW --------
# `_grass_plan` answers "how many NEW Grass energies from HAND unlock an
# attack today". When those Grass energies are NOT in hand but in the DECK and
# we have a playable refill (Lillie's draws 6/8), the right question is no
# longer boolean but PROBABILISTIC: with what probability does the draw bring
# the missing cards, and is what they unlock worth more than the other use of
# the Supporter slot? These two pieces are the single source of that answer.









# =============================================================================
# THE KO WINDOW: "Knocked Out DURING YOUR OPPONENT'S LAST TURN"
# -----------------------------------------------------------------------------
# `ko_last_turn` does not mean "we lost a body": it means EXACTLY the
# clause shared by Flip the Script (Fezandipiti ex) and Unfair Stamp --
# "if any of your Pokemon were Knocked Out during your opponent's LAST TURN".
# All of its consumers score one of those two cards.
#
# The old detector infers it from the opponent HAVING TAKEN A PRIZE (`op_prize`
# drops). That is a KO of ours, yes -- but it does not say WHEN. And there is a
# gap of a turn in which a KO does not count: the window BETWEEN TURNS (after
# the opponent's TURN_END and before our TURN_START), where the "between turns"
# effects fire, such as Freezing Shroud (Froslass: 1 counter on each Pokemon
# WITH AN ABILITY). That KO does not happen "during the opponent's turn": it
# happens in no-man's land.
#
# Measured in episode 88914948 (registro_008 step 74, vs Marnie/Grimmsnarl with
# double Froslass + double Munkidori), LOST:
#
#   TURN_END(opponent) -> 14 Freezing Shroud counters (x2 Froslass) -> our
#   Dipplin dies -> the opponent takes a prize -> TURN_START(ours)
#
# The engine did NOT offer Unfair Stamp in the menu (we had it in hand) nor the
# ability after putting the body down: as far as the game is concerned there was
# NO KO "during the opponent's last turn". The agent, with `ko_last_turn=True`,
# benched a Fezandipiti ex to cash in a 3-card draw that did not exist: it gave
# away a 2-prize body and the last bench slot in exchange for nothing.
#
# The line is NOT "attack vs ability" (the same episode refutes it): in
# registro_011 step 105 Munkidori MOVED 3 counters with Adrena-Brain and killed
# our Ogerpon ex INSIDE the opponent's turn -- and there the engine DID offer the
# Stamp the following turn. What decides is the WINDOW, not the source of the
# damage.
#
# Hence these markers, which are fed by the TURN_START / TURN_END of the
# logs (the log stream is contiguous between batches, so the window is carried
# from one call to the next) and can only LOWER `ko_last_turn`: with no
# positive evidence the previous behaviour is kept.
_TURN_LOG_UNKNOWN = -1



# Terminal PROMOTION adjustment (see "SURVIVAL WHEN PROMOTING"). The doomed body
# drops far enough to yield to any real survivor (the measured case: a charged
# Ogerpon 4557 -> -1443, below the Hydrapple ex at 259).
PROMO_DOOMED_PENALTY = 6000
# With no survivors, each extra prize we hand over costs this much.
PROMO_PRIZE_PENALTY = 1500
# Whoever KNOCKS OUT the opposing active is promoted above anyone who does not,
# tank included (user). Above the maximum score of the promotion branches
# (9500 = `_promote_setup_ko_attacker`) so that it is a GUARANTEE and does not
# depend on the knocker scoring higher base than the tank:
# `_ko_prefer_basic_general` gives 8500+ to a 1-prize basic and the sturdy wall
# 6100, so a knocker at ~4500 could lose. Among several knockers the base score
# decides.
PROMO_KO_BONUS = 20000
# MATCH POINT: the opponent only needs to knock this body out to take the last
# prize. That is not a bad trade, it is losing the game -> veto, not a penalty.
# It goes BELOW SCORE_NEVER (-10000) on purpose: other promotion vetoes use that
# exact value (e.g. "the Meganium line does not go active") and a tie at -10000
# would leave the tie-break to the random order of the options, exactly between
# the body that endures and the one that makes us lose.
PROMO_MATCH_POINT_VETO = -30000







def _init_cards_tracking():
    AGENT_STATE.ACTIVE_CARDS_IN_DECK = {}
    AGENT_STATE._cards_first_scan_done = False
    AGENT_STATE._cards_prizes_identified = False
    for card_id in my_deck:
        if card_id not in AGENT_STATE.ACTIVE_CARDS_IN_DECK:
            AGENT_STATE.ACTIVE_CARDS_IN_DECK[card_id] = {
                ZONE_DECK: 0,
                ZONE_BENCH: 0,
                ZONE_HAND: 0,
                ZONE_PRIZE: 0,
                ZONE_DISCARD: 0,
            }
        AGENT_STATE.ACTIVE_CARDS_IN_DECK[card_id][ZONE_DECK] += 1

    # The KO window markers span TWO turns (see
    # `_rastrear_ventana_de_ko`), so `agent()`'s per-turn reset does not clear
    # them. They are cleared here, which is the NEW GAME hook: it is called by
    # `_update_cards_tracking` when the turn counter goes back to 1 (the
    # self-play harness chains thousands of episodes in the same process) and
    # also by the test resets. Without this, a between-turns KO from the
    # previous episode would lower a legitimate `ko_last_turn` of the next one.
    _reset_ventana_de_ko()


def _reset_ventana_de_ko():
    """Clears the window trace of our own KOs (a new game)."""
    AGENT_STATE._log_current_turn = _TURN_LOG_UNKNOWN
    AGENT_STATE._own_ko_inside_op_turn = -99
    AGENT_STATE._own_ko_outside_op_turn = -99


_init_cards_tracking()









# --- SELF-DAMAGE FROM OUR OWN ATTACK (Wood Hammer and company) --------------
# Many attacks damage THEMSELVES ("This Pokemon also does 30 damage to
# itself"). That datum does NOT live in any field of `Attack`: only in its TEXT,
# so it is parsed once per attackId and cached. Deck-agnostic: it covers the ~49
# attacks with self-damage in the database, not just our Tapu Bulu's Wood Hammer.
#
# Three families, and only the FIRST is certain damage:
#   * MANDATORY fixed -- "This Pokemon also does 30 damage to itself." -> 30.
#   * OPTIONAL -- "You may do 30 more damage. If you do, this Pokemon also does
#     30 damage to itself." / "You may have this Pokemon also do 60 damage to
#     itself..." -> 0: the decision is OURS, the self-damage is not assumed.
#   * CHANCE -- "Flip 2 coins. If both of them are tails, this Pokemon also does
#     90 damage to itself." -> 0 in the CERTAIN calculation; the worst case is
#     obtained with `incierto=True` (which the prudent brakes consult).
# And one that scales: "...10 damage to itself for each damage counter on it"
# (Vanguard Punch), which is resolved with the damage the attacker has already
# taken.
import re as _re_self_damage

# `do` without the -s covers the optional form "You may have this Pokemon also DO
# 60 damage to itself..." (Voltaic Fist), which would otherwise be left
# unclassified.
_RE_SELF_DAMAGE = _re_self_damage.compile(
    r"do(?:es)?\s+(\d+)\s+damage\s+to\s+itself", _re_self_damage.IGNORECASE)
_RE_SELF_DAMAGE_SCALE = _re_self_damage.compile(
    r"to\s+itself\s+for\s+each\s+damage\s+counter", _re_self_damage.IGNORECASE)
_SELF_DAMAGE_CACHE: dict = {}


def _self_damage_spec(attack_id):
    """(n, optional, chance, per_counter) of the attack's self-damage; None if it
    does not have any. The "You may" and the "Flip 2 coins" that condition the
    self-damage often live in the PREVIOUS sentence, so the context spans both."""
    if attack_id in _SELF_DAMAGE_CACHE:
        return _SELF_DAMAGE_CACHE[attack_id]
    spec = None
    _atk = attack_table.get(attack_id)
    text = (getattr(_atk, 'text', None) or '') if _atk is not None else ''
    _m = _RE_SELF_DAMAGE.search(text)
    if _m is not None:
        _ini = text.rfind('.', 0, _m.start()) + 1
        _fin = text.find('.', _m.end())
        _frase = text[_ini:_fin if _fin != -1 else len(text)]
        _prev = text[text.rfind('.', 0, max(0, _ini - 1)) + 1:_ini]
        _ctx = (_prev + ' ' + _frase).lower()
        spec = (int(_m.group(1)),
                'you may' in _ctx,
                any(_w in _ctx for _w in ('flip', 'coin', 'heads', 'tails')),
                bool(_RE_SELF_DAMAGE_SCALE.search(_frase)))
    _SELF_DAMAGE_CACHE[attack_id] = spec
    return spec


def _attack_self_damage(attack_id, attacker=None, incierto=False):
    """Self-damage the attack `attack_id` inflicts on its OWN bearer.

    It returns the CERTAIN damage: 0 if it is optional (we decide it) or if it
    depends on a coin flip. With `incierto=True` it returns the WORST case."""
    spec = _self_damage_spec(attack_id)
    if spec is None:
        return 0
    _n, _opcional, _azar, _per_counter = spec
    if _opcional:
        return 0
    if _azar and not incierto:
        return 0
    if _per_counter:
        if attacker is None:
            return 0
        _cont = max(0, ((attacker.maxHp or 0) - (attacker.hp or 0)) // 10)
        return _n * _cont
    return _n


def _self_damage_of_pokemon(pokemon, incierto=False):
    """Self-damage of the attack `pokemon` would use TODAY: the WORST among the
    attacks whose energy cost it can already pay.

    The suicidal-finisher brakes are computed BEFORE the option loop, where the
    chosen attackId is not known yet; taking the maximum is the safe side,
    because its only consequence is to STOP claiming an absolute victory (the
    agent goes back to normal scoring), never to claim one that does not exist.
    `len(energies)` is already EFFECTIVE energy and `Attack.energies` is the list
    of cost units, so they are compared directly."""
    if pokemon is None:
        return 0
    _data = card_table.get(pokemon.id)
    if _data is None or not getattr(_data, 'attacks', None):
        return 0
    _disp = len(pokemon.energies)
    _worst = 0
    for _aid in _data.attacks:
        _atk = attack_table.get(_aid)
        if _atk is None:
            continue
        if len(getattr(_atk, 'energies', []) or []) > _disp:
            continue  # it cannot pay for that attack
        _worst = max(_worst, _attack_self_damage(_aid, pokemon, incierto))
    return _worst


def _self_ko_by_own_attack(pokemon, incierto=False):
    """True if the self-damage of `pokemon`'s attack KNOCKS IT OUT itself."""
    if pokemon is None:
        return False
    _auto = _self_damage_of_pokemon(pokemon, incierto)
    return _auto > 0 and _auto >= (pokemon.hp or 0)











# =============================================================================
# ATTACKS THAT CHOOSE A TARGET (SNIPE): the opposing active is not always best
# -----------------------------------------------------------------------------
# Cruel Arrow (Fezandipiti ex) does a fixed 100 to ANY ONE of the opponent's
# Pokemon, active or bench ("don't apply Weakness and Resistance to Benched
# Pokemon"). All the rest of the scorer measures the ACTIVE's attack against the
# opposing ACTIVE, so with a wall in front it declared the turn sterile: in
# registro_004 step 54 (vs Alakazam) the active Fezandipiti ex, with 4 effective
# energies, could not reach the 140 HP Alakazam and the agent RETREATED it to
# bring up an Ogerpon that could not even attack -- with a knockable 80 HP
# Kadabra on the opposing bench.
#
# These pieces are the SINGLE source of truth for the snipe and they are shared
# by the planner (which decides whether to attack or retreat) and the actual
# target selection in the DAMAGE menu, which therefore cannot disagree.
#
# They now live in `ptcg/cards/ids.py` (the id set) and `ptcg/calc/damage.py`
# (`_snipe_best_target`, `_bench_snipe_best`), and arrive here through the star
# imports at the top. They were moved because the reading was needed from BOTH
# sides of a retreat, and while it lived here only the active side could see it
# -- registro_014 step 129, documented on `_bench_snipe_best`.










import os as _os_dbg





def _rastrear_ventana_de_ko(logs, my_index, turn):
    """Classifies OUR KOs by the turn window in which they happened.

    It walks the batch of logs keeping track of the current turn (`TURN_START` /
    `TURN_END`) and, every time one of OUR Pokemon leaves Active/Bench for the
    discard, it notes the `state.turn` in the appropriate marker:

      * inside the OPPONENT's turn -> `_own_ko_inside_op_turn`
        (this is the KO that enables Flip the Script and Unfair Stamp; it does
        not matter whether it was done by an attack or by an ability that moves
        counters)
      * BETWEEN TURNS or during OUR turn -> `_own_ko_outside_op_turn`
        (it enables nothing: Freezing Shroud and company kill in no-man's land,
        and a recoil self-KO happens on our own turn)

    The turn state is CARRIED between calls: the log batches are
    contiguous, so the opponent's `TURN_END` may have arrived in the previous
    observation (a forced selection during their turn) and the KO in the
    next one. While we have not seen any turn marker the state is
    `_TURN_LOG_UNKNOWN` and nothing is classified: with no evidence nothing
    is lowered.
    """

    for log in logs or ():
        _tipo = getattr(log, 'type', None)

        if _tipo == LogType.TURN_START:
            AGENT_STATE._log_current_turn = getattr(log, 'playerIndex', None)
            continue

        if _tipo == LogType.TURN_END:
            AGENT_STATE._log_current_turn = None
            continue

        if _tipo != LogType.MOVE_CARD:
            continue
        if getattr(log, 'playerIndex', None) != my_index:
            continue
        if getattr(log, 'fromArea', None) not in (AreaType.ACTIVE, AreaType.BENCH):
            continue
        if getattr(log, 'toArea', None) != AreaType.DISCARD:
            continue
        # Bodies only: the attached energies/tools leave with fromArea
        # ENERGY/TOOL and the pre-evolution with PRE_EVOLUTION, but the explicit
        # filter avoids depending on that.
        _data_ko = card_table.get(getattr(log, 'cardId', 0))
        if _data_ko is None or not getattr(_data_ko, 'hp', 0):
            continue

        if AGENT_STATE._log_current_turn == _TURN_LOG_UNKNOWN:
            continue
        if AGENT_STATE._log_current_turn == 1 - my_index:
            AGENT_STATE._own_ko_inside_op_turn = turn
        else:
            AGENT_STATE._own_ko_outside_op_turn = turn




def _update_cards_tracking(obs, my_index, my_state):

    if obs.current.turn == 1 and AGENT_STATE._cards_last_turn > 1:
        _init_cards_tracking()
        AGENT_STATE.op_is_crustle_deck = False
        AGENT_STATE.op_is_cornerstone_deck = False
        AGENT_STATE.op_has_mega_kangaskhan = False
        AGENT_STATE.op_is_starmie_deck = False
    AGENT_STATE._cards_last_turn = obs.current.turn

    if not AGENT_STATE._cards_first_scan_done and obs.current is not None:

        _first_turn_scan(my_state)
    else:

        _process_logs(obs, my_index)

        _sync_from_state(my_state)

    _identify_prizes(obs, my_state)































_RULES_BOSS_PLAY = [
    # IT NEVER FIRES, AND IT IS KEPT ON PURPOSE (user, August 2026,
    # `utils/rule_census.py`: this veto and its two twins in the other Supporter
    # PLAY chains were evaluated ~222 000 times over the frozen corpus and 2 400
    # games and fired ZERO between them). The reason is not a wrong premise --
    # the failure mode of `_protect_last_supporter`, which was gated on a flag
    # that on a forced discard belongs to the OPPONENT -- it is that the ENGINE
    # already enforces one Supporter per turn and never offers a second one to
    # play. The guard is therefore redundant with a rule of the game, not with
    # another rule of ours, and it costs one comparison to keep saying so.
    _FixedRule("supporter_already_played",
               lambda c: c.state.supporterPlayed,
               lambda c: SCORE_VETO),
    # With a playable Unfair Stamp (we were knocked out), the Stamp goes first. Only
    # if the Stamp is REALLY going to be played (`_stamp_pendiente`): if its card
    # rule vetoes it, the Boss's yields the turn to nobody.
    _FixedRule("yields_to_unfair_stamp",
               _stamp_pendiente,
               lambda c: SCORE_VETO),
    # Rule (user): vs Alakazam with a Dunsparce as the opposing active and our active
    # WITHOUT an attack, do NOT gust: it would clear the wall and give them a free
    # road; it is better to keep the Dunsparce jammed up front.
    _FixedRule("do_not_clear_the_dunsparce_wall",
               lambda c: (c.op_is_alakazam_deck and c.op_active_is_dunsparce
                          and c.active_cant_attack),
               lambda c: SCORE_VETO),
    # WINNING gust: the ACTIVE knocks out a bench target and WINS the
    # game. It has to beat ANY retreat/pivot (~6500-6600); it used to be
    # scored as win_via_bench (5600) and the agent RETREATED instead of finishing
    # (user, registro 019 step 190 vs Dragapult, WON).
    _FixedRule("winning_gust",
               lambda c: c.win_via_boss_gust,
               lambda c: BOSS_SCORE_WIN_NOW + c.supporter_boost),
    # MATCH POINT ON THE ACTIVE (user, registro_010 step 144 vs Marnie's Grimmsnarl
    # ex, LOST): the opposing ACTIVE is already worth the prizes we are missing and a
    # BENCHED body finishes it after a payable retreat. The game is closed by
    # retreating -- without spending the Supporter and without changing the opposing
    # active, which is exactly the body we want to knock out. Gusting anything else
    # swaps the target for one worth FEWER prizes and throws the winning turn away:
    # a VETO. It yields to `winning_gust` (above): that finisher already wins with
    # the current active, without paying the retreat.
    _FixedRule("winning_finisher_on_the_active_after_retreating",
               lambda c: (c.win_ko_active_via_promote
                          and not c.win_via_boss_gust),
               lambda c: SCORE_VETO),
    # THE EX-IMMUNE WALL FIRST (user, registro_006 step 47 vs Crustle,
    # LOST): with a Crustle/Sylveon as the opposing ACTIVE and our active able to
    # KNOCK IT OUT this turn, Boss's is NOT played. Gusting changes the opposing
    # active: the wall goes to the bench healthy and the turn is spent on another
    # body, when the one thing our deck (all ex: Ogerpon, Hydrapple, Meowth,
    # Fezandipiti) cannot do afterwards is touch that wall. In the record
    # the gust took 2 prizes from the Ogerpon ex on their bench (`gust_for_2_prizes`,
    # 6800) and left the Crustle alive. Exceptions: the gusts that WIN the
    # game right now (`win_via_boss_gust` / `boss_win_via_bench`) still rule.
    # It only applies to Crustle/Sylveon (`EX_IMMUNE_IDS`): an Ability wall
    # (Cornerstone) is solved the other way round, by gusting it.
    _FixedRule("finish_the_immune_wall_before_gusting",
               lambda c: (c.ex_immune_wall_ko_ready
                          and not c.win_via_boss_gust
                          and not c.boss_win_via_bench),
               lambda c: SCORE_VETO),
    # A 2-PRIZE gust (user, registro_008 step 119 vs TR Mewtwo ex,
    # WON): the active already knocks out the opposing active (1 prize) but a
    # knockable benched ex gives 2; `gust_2prize_via_boss` already requires a KO,
    # >= 2 prizes, > the active's prizes and no trade-down. Below WIN_NOW, above
    # the pivots.
    _FixedRule("gust_for_2_prizes",
               lambda c: c.gust_2prize_via_boss,
               lambda c: BOSS_SCORE_GUST_2PRIZE + c.supporter_boost),
    # FINISHER FISHING (user, registro_004 step 49 vs Marnie, LOST): with
    # no attack possible this turn, the Supporter slot is worth more fishing
    # with Lillie's for the energy that unlocks a prize KO (see
    # `_finisher_fishing`) than gusting. The gust also changes the opposing
    # active exactly when that active IS the target of the finisher being fished for.
    # It comes after the CERTAIN finishers (winning gust, 2 prizes, match point),
    # which `_finisher_fishing_valid` already exempts.
    _FixedRule("yields_to_finisher_fishing",
               lambda c: (_finisher_fishing_valid(c)
                          and c.hand_counts.get(Lillie_Determination, 0) >= 1),
               lambda c: BOSS_SCORE_EMPTY_GUST),
    _FixedRule("first_turn_yields_to_lillie",
               _boss_first_turn_yields,
               lambda c: BOSS_SCORE_EMPTY_GUST),
    _FixedRule("empty_gust_yields_to_lillie",
               _boss_empty_gust,
               lambda c: BOSS_SCORE_EMPTY_GUST),
    _FixedRule("no_bench_attacker_yields_to_lillie",
               _boss_yields_to_dig,
               lambda c: BOSS_SCORE_EMPTY_GUST),
    _FixedRule("immune_wall",
               lambda c: ((c.op_has_ability_immune_active
                           or c.op_has_ex_immune_active)
                          and _boss_val_de(c) >= 900),
               lambda c: BOSS_SCORE_WALL_GUST + c.supporter_boost),
    _FixedRule("dodge_redirect",
               lambda c: c.boss_dodge_redirect,
               lambda c: BOSS_SCORE_DODGE_REDIRECT + c.supporter_boost),
    _FixedRule("win_via_bench",
               lambda c: c.boss_win_via_bench,
               lambda c: BOSS_SCORE_WIN_VIA_BENCH + c.supporter_boost),
    # Cut the Alakazam line: gust+knock out their benched pre-evolution when
    # the opposing active is outside the line (a wall). Registro 010, step 64.
    _FixedRule("cut_the_alakazam_line",
               lambda c: c.boss_deny_alakazam_line,
               lambda c: BOSS_SCORE_PRIZE_RANK_BASE + c.supporter_boost),
    # Priority between copies of the same threat (user, registro_007 step 80
    # vs Archaludon): the opposing active (Hero's Cape + 3 energies) dominates its
    # weak benched copy -> ATTACK the active and KEEP the Boss's. It cuts off
    # the low/medium value branches; the finishers already returned earlier.
    _FixedRule("active_threat_dominates",
               lambda c: c.boss_active_threat_dominates,
               lambda c: BOSS_SCORE_EMPTY_GUST),
    # Un-lock the abilities by gusting a non-locker (see the docstring
    # of _boss_unlock_gust). After the finishers and the yields to Lillie's;
    # above low_value/defensive/no_value, which is where it used to die (-1).
    _FixedRule("gust_unlocks_abilities",
               _boss_unlock_gust,
               lambda c: BOSS_SCORE_UNLOCK_GUST + c.supporter_boost),
    # The two VETOES of the PURPOSELESS gust (see their docstrings). They go here,
    # with every prize/wall/lock reason already resolved above, and above
    # the three branches that require neither a KO nor a threat: `gust_low_value`,
    # `defensive_gust` and above all the `supporter_value` reserve, which is
    # the one that played the Boss's of registro_002 step 20 (2400 + 200*1.4 = 2680).
    # Both conditions exempt themselves with `_boss_reason_with_prize`,
    # so `gust_by_prize_rank` (which requires a KO) and `defensive_gust` (which
    # requires the opponent's finisher) are still reachable below.
    _FixedRule("do_not_give_away_the_alakazam_line",
               _boss_gives_away_alakazam_line,
               lambda c: SCORE_VETO),
    _FixedRule("gust_without_purpose",
               _boss_gust_without_purpose,
               lambda c: SCORE_VETO),
    _FixedRule("gust_low_value",
               lambda c: c.boss_low_value_gust,
               lambda c: BOSS_SCORE_LOW_VALUE_GUST + c.supporter_boost),
    _FixedRule("gust_by_prize_rank",
               lambda c: c.boss_prize_rank >= 1,
               lambda c: (BOSS_SCORE_PRIZE_RANK_BASE
                          + (8 - c.boss_prize_rank) * 20
                          + c.supporter_boost)),
    _FixedRule("defensive_gust",
               lambda c: c.boss_defensive_gust,
               lambda c: BOSS_SCORE_DEFENSIVE_GUST + c.supporter_boost),
    # THE GUST THAT TRAPS THEIR TURN (user, registro_004 step 60 vs Alakazam,
    # LOST -- deck-agnostic). The last branch before the "no value" veto, and the
    # one that answers the dead turn: we cannot attack, nothing on the board
    # knocks anything out, and the Supporter of the turn is on its way to being
    # thrown away with the hand. If their bench holds a body that cannot answer
    # from the active spot even after an attachment and cannot pay its own
    # retreat, bringing it up is not a nuisance, it is a denial: they lose the
    # attack, or they lose the energy they have to attach to it to get it out.
    #
    # It is the LAST branch on purpose. Every reason with a prize behind it has
    # already returned above; the yields to Lillie's (an empty gust, no benched
    # attacker, the first turn) come first too, so a refill still takes the
    # Supporter slot when there is one to take. And it sits UNDER the two
    # deck-agnostic vetoes, which is what keeps it from handing over the
    # pre-evolution of their only attacking line or from paying their retreat for
    # an active that was not going to hit us anyway. See `_boss_trap_gust`.
    _FixedRule("gust_traps_their_turn",
               lambda c: c.boss_trap_gust,
               lambda c: BOSS_SCORE_TRAP_GUST + c.supporter_boost),
    _FixedRule("no_value",
               lambda c: _boss_val_de(c) <= 0,
               lambda c: SCORE_VETO),
    # Fallback: the supporter's generic value.
    _FixedRule("supporter_value",
               lambda c: True,
               lambda c: (SCORE_SUPPORTER_VALUE_BASE
                          + int(_boss_val_de(c) * 1.4)
                          + c.supporter_boost)),
]

def _score_boss_orders_play(ctx: DecisionContext) -> int:
    """Scores playing Boss's Orders (id 1182). Body migrated to the RULES
    ENGINE (phase 4): the rules and their strategic comments live in
    _RULES_BOSS_PLAY; PTCG_DEBUG prints the trace."""
    return _resolve_with_trace("boss->play", _RULES_BOSS_PLAY, [], ctx,
                               default=0)



































# Threshold of "energy still useful on the ACTIVE", by body family.
# This used to be a chain of `if act.id == ...` inside
# `_ns_active_below_its_cost`; extracting it to tables makes it possible to add
# the deck-agnostic fallback without touching any of the already measured
# decisions.
#
# MEGANIUM LINE: what rules is the RETREAT cost, not the attack one. It is a
# STRATEGY decision, not card data: we do not want these bodies attacking
# (Chikorita never uses Growl, Meganium is the Wild Growth engine), we want them
# able to pivot. That is why Meganium cuts at 2 (retreat) and not at 4 (Solar
# Beam). See [[retirar-chikorita-para-linea-meganium]].
_NS_THRESHOLD_BY_RETREAT = frozenset({Chikorita, Bayleef, Meganium})
# ATTACKERS whose threshold is their attack cost (source: ATTACK_ENERGY_REQ).
# Fezandipiti ex and Meowth ex are deliberately LEFT OUT: they are utility
# bodies (Cruel Arrow costs 3, Last-Ditch Catch does not attack), and pouring a
# single energy into them advances no plan. When the active is one of them and
# there is a finisher on the bench, the right play is not to charge them but to
# RETREAT them -- that is covered by `_ns_e_retreat_lethal` /
# `_ns_e_retreat_chip`.
_NS_THRESHOLD_BY_ATTACK = frozenset({Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex,
                                   Tapu_Bulu, Pinsir})


def _ns_useful_energy_threshold(card_id):
    """Energy from which one more Grass on the ACTIVE stops
    contributing. `None` = recovering energy for that body contributes nothing.

    Three levels, from most specific to most general:
      1. CURATED tables of the current deck (`_NS_THRESHOLD_BY_RETREAT` /
         `_NS_THRESHOLD_BY_ATTACK`): they encode measured strategy and always rule;
      2. the other Pokemon of deck.csv (`_DECK_POKEMON_IDS`) -> `None`: the
         configuration knows them and excludes them ON PURPOSE (Meowth ex,
         Fezandipiti ex); deriving them from the card data would undo that
         decision;
      3. any other body -> `_min_attack_cost`, derived from the card data.
         This is the DECK-AGNOSTIC branch: with another deck.csv the function
         stops returning `False` blindly and reasons with the real attack cost.
    """
    if card_id in _NS_THRESHOLD_BY_RETREAT:
        return RETREAT_COST.get(card_id, 1)
    if card_id in _NS_THRESHOLD_BY_ATTACK:
        return AGENT_STATE.ATTACK_ENERGY_REQ.get(card_id)
    if card_id in _DECK_POKEMON_IDS:
        return None
    return _min_attack_cost(card_id)


def _ns_active_below_its_cost(w):
    """The ACTIVE still does not reach its useful energy threshold
    (`_ns_useful_energy_threshold`), neither in EFFECTIVE energy nor in PHYSICAL
    cards.

    Both are checked because with Meganium in play `len(energies)` comes
    doubled by Wild Growth: the effective cap avoids attacking short and the
    physical one avoids piling up energy cards that are no longer needed.
    """
    act = _active_of(w.my_state)
    if act is None:
        return False
    threshold = _ns_useful_energy_threshold(act.id)
    if threshold is None:
        return False
    e, eff = len(act.energies), len(act.energies) * _grass_mult()
    return eff < threshold and e < threshold


def _ns_e_active_needs(w):
    """Energy from the discard for the ACTIVE that still does not reach its attack
    cost (or its retreat cost, for the Meganium line) and is not at the cap."""
    return (_ns_useful_energy_without_grass(w)
            and not w.state.energyAttached
            and _ns_active_below_its_cost(w))


def _ns_e_active_below_cost(w):
    """Like `_ns_e_active_needs` but also accepting the charge by
    ABILITY when the turn's manual attachment has already been spent."""
    return (_ns_useful_energy_without_grass(w)
            and _ns_active_below_its_cost(w)
            and _ns_charge_route_to_active(w))

















_ESC_NS_RECUPERACION = [
    # Complete combos (recover the piece + evolve the whole line).
    _E("applin_combo_completo",
       lambda w: (Applin in w.basics and w.hand_counts.get(Dipplin, 0) >= 1
                  and w.hand_counts.get(Hydrapple_ex, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 980),
    _E("dipplin_combo_completo",
       lambda w: (Dipplin in w.evos and w.hand_counts.get(Applin, 0) >= 1
                  and w.hand_counts.get(Hydrapple_ex, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 970),
    _E("applin_con_dipplin_mano",
       lambda w: (Applin in w.basics and w.hand_counts.get(Dipplin, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 900),
    _E("dipplin_con_applin_mano",
       lambda w: (Dipplin in w.evos and w.hand_counts.get(Applin, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 880),
    _E("hydra_con_applin_campo",
       lambda w: (Hydrapple_ex in w.evos
                  and w.field_counts.get(Applin, 0) >= 1
                  and w.hand_counts.get(Dipplin, 0) >= 1
                  and w.forest_in_play), 960),
    _E("hydra_dipplin_evolucionable",
       lambda w: (Hydrapple_ex in w.evos
                  and w.evolvable.get(Dipplin, 0) >= 1), 950),
    _E("chikorita_combo_completo",
       lambda w: (Chikorita in w.basics and not w.meganium_in_play
                  and w.hand_counts.get(Bayleef, 0) >= 1
                  and w.hand_counts.get(Meganium, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 990),
    _E("bayleef_combo_completo",
       lambda w: (Bayleef in w.evos and not w.meganium_in_play
                  and w.hand_counts.get(Chikorita, 0) >= 1
                  and w.hand_counts.get(Meganium, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 985),
    _E("chikorita_con_bayleef_mano",
       lambda w: (Chikorita in w.basics and not w.meganium_in_play
                  and w.hand_counts.get(Bayleef, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 920),
    _E("bayleef_con_chikorita_mano",
       lambda w: (Bayleef in w.evos and not w.meganium_in_play
                  and w.hand_counts.get(Chikorita, 0) >= 1
                  and w.forest_in_play and w.bench_count < 5), 910),
    _E("meganium_con_chikorita_campo",
       lambda w: (Meganium in w.evos and not w.meganium_in_play
                  and w.field_counts.get(Chikorita, 0) >= 1
                  and w.hand_counts.get(Bayleef, 0) >= 1
                  and w.forest_in_play), 975),
    _E("meganium_bayleef_evolucionable",
       lambda w: (Meganium in w.evos and not w.meganium_in_play
                  and w.evolvable.get(Bayleef, 0) >= 1), 970),
    # Starting lines from scratch.
    _E("applin_arrancar_linea",
       lambda w: (Applin in w.basics and not w.has_hydrapple
                  and (w.field_counts.get(Applin, 0)
                       + w.field_counts.get(Dipplin, 0)) == 0
                  and w.bench_count < 5), 700),
    _E("chikorita_arrancar_linea",
       lambda w: (Chikorita in w.basics and not w.meganium_in_play
                  and (w.field_counts.get(Chikorita, 0)
                       + w.field_counts.get(Bayleef, 0)
                       + w.field_counts.get(Meganium, 0)) == 0
                  and w.bench_count < 5), 750),
    # Direct evolution of a pre-evolution ALREADY in play (value depending on Forest).
    _E("dipplin_applin_evolucionable",
       lambda w: (Dipplin in w.evos and not w.has_hydrapple
                  and w.hand_counts.get(Dipplin, 0) == 0
                  and w.evolvable.get(Applin, 0) >= 1),
       lambda w: 880 if w.forest_in_play else 750),
    _E("bayleef_chikorita_evolucionable",
       lambda w: (Bayleef in w.evos and not w.meganium_in_play
                  and w.hand_counts.get(Bayleef, 0) == 0
                  and w.evolvable.get(Chikorita, 0) >= 1),
       lambda w: 900 if w.forest_in_play else 780),
    _E("meganium_directo",
       lambda w: (Meganium in w.evos and not w.meganium_in_play
                  and w.hand_counts.get(Meganium, 0) == 0
                  and w.evolvable.get(Bayleef, 0) >= 1),
       lambda w: 970 if w.forest_in_play else 900),
    _E("hydra_directo",
       lambda w: (Hydrapple_ex in w.evos and not w.has_hydrapple
                  and w.hand_counts.get(Hydrapple_ex, 0) == 0
                  and w.evolvable.get(Dipplin, 0) >= 1),
       lambda w: 960 if w.forest_in_play else 950),
    # Future with Forest (the evolution is in hand or in the deck).
    _E("applin_futuro_con_forest",
       lambda w: (w.forest_in_play and w.bench_count < 5
                  and Applin in w.basics
                  and (w.field_counts.get(Applin, 0)
                       + w.field_counts.get(Dipplin, 0)
                       + w.field_counts.get(Hydrapple_ex, 0)) == 0
                  and not w.has_hydrapple
                  and (w.hand_counts.get(Dipplin, 0) >= 1
                       or w.cards_in_deck.get(
                           Dipplin, {}).get(ZONE_DECK, 0) > 0)), 870),
    _E("chikorita_futuro_con_forest",
       lambda w: (w.forest_in_play and w.bench_count < 5
                  and Chikorita in w.basics
                  and (w.field_counts.get(Chikorita, 0)
                       + w.field_counts.get(Bayleef, 0)
                       + w.field_counts.get(Meganium, 0)) == 0
                  and not w.meganium_in_play
                  and (w.hand_counts.get(Bayleef, 0) >= 1
                       or w.cards_in_deck.get(
                           Bayleef, {}).get(ZONE_DECK, 0) > 0)), 890),
    # Bodies of situational value.
    #
    # `tapu_vs_crustle` LIVED HERE AND COULD NEVER FIRE (user, August 2026,
    # `utils/rule_census.py`: evaluated 11 706 times over the frozen corpus and
    # 2 400 games, fired ZERO). Not rare -- IMPOSSIBLE, and provably so rather
    # than by counting: `_score_night_stretcher_play` picks THIS chain only
    # under `not (op_is_crustle_deck or op_is_cornerstone_deck)`, and the rule
    # asked for `w.op_is_crustle_deck`. `_CtxNSPlay.__getattr__` delegates
    # straight to the ctx, so the two readings are the same object and the
    # contradiction is airtight.
    #
    # Its intent was already served, and better, by the chain that DOES run
    # against that wall: `_ESC_NS_CRUSTLE[0] basico_whitelist` opens its
    # whitelist with Tapu Bulu and scores it 900, above the 850 this rule would
    # have given. Removing it changes no decision; that it changes none is the
    # argument for removing it.
    _E("fez_tras_ko",
       lambda w: (Fezandipiti_ex in w.basics
                  and w.field_counts.get(Fezandipiti_ex, 0) == 0
                  and w.ko_last_turn and w.bench_count < 5), 840),
    _E("ogerpon_con_energia_mano",
       lambda w: (Teal_Mask_Ogerpon_ex in w.basics
                  and w.hand_counts.get(Basic_Grass_Energy, 0) >= 1
                  and w.bench_count <= 3), 820),
    # Recover Meowth ex for the refill engine (Last-Ditch ->
    # Lillie's). Registro 006, step 51 vs Alakazam.
    _E("meowth_motor_refresco",
       lambda w: (Meowth_ex in w.basics and not w.meowth_ability_lock
                  and w.field_counts.get(Meowth_ex, 0) == 0
                  and w.bench_count < 5 and not w.state.supporterPlayed
                  and w.best_supp_in_hand_val < 500
                  and w.best_supp_in_deck_val >= 400), 830),
    # Energy from the discard.
    _E("energia_activo_necesita", _ns_e_active_needs, 860),
    _E("energia_hydra_ripening",
       lambda w: (_ns_useful_energy_without_grass(w) and w.my_state.active
                  and w.my_state.active[0] is not None
                  and w.my_state.active[0].id == Hydrapple_ex
                  and len(w.my_state.active[0].energies)
                      * _grass_mult() < 2), 860),
    _E("energia_syrup_letal", _ns_e_syrup_letal, 950),
    # Same tier as finishing with the active: today's prize rules.
    _E("energia_remate_con_el_activo", _ns_e_finisher_with_active, 950),
    _E("energia_remate_via_promocion", _ns_e_finisher_via_promotion, 950),
    # THE GRASS THAT PAYS THE RETREAT (user, registro_021 turn 21): a blocked
    # active with no energy + a READY benched attacker that finishes, and the only
    # copy of Grass is in the DISCARD. `_ns_e_finisher_via_promotion` does NOT cover
    # this case -- it requires `len(act.energies) >= cost`, that is, that the retreat
    # can ALREADY be paid -- and neither does `_ns_e_active_needs`: it goes
    # through `_ns_active_below_its_cost`, a per-card table that returns False
    # for everything that is not of the Meganium/Hydrapple/Ogerpon/Tapu/Pinsir line
    # (Fezandipiti ex, Meowth ex and any body from another deck fall outside).
    # Without these two scenarios the ARGMAX gave 0 -> SCORE_VETO -> END with the
    # finisher on the table. Tier 950 (lethal) = the other finishers: today's prize
    # rules. Tier 860 (chip) = the same band as `energia_activo_necesita`.
    _E("energia_retirada_letal", _ns_e_retreat_lethal, 950),
    _E("energia_retirada_chip", _ns_e_retreat_chip, 860),
    _E("energia_teal_dance",
       lambda w: (_ns_useful_energy_without_grass(w)
                  and w.field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
                  and _ns_has_ogerpon_teal(w)), 800),
    _E("energia_activo_sin_teal",
       lambda w: (_ns_useful_energy_without_grass(w)
                  and w.field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
                  and not _ns_has_ogerpon_teal(w)
                  and not w.state.energyAttached
                  and w.active_needs_energy), 860),
    _E("energia_linea_mega_activa",
       lambda w: (w.mega_line_active and _ns_useful_energy_without_grass(w)
                  and not w.state.energyAttached), 950),
]



_ESC_NS_CRUSTLE = [
    # vs Crustle/Cornerstone ONLY recoveries from the non-ex whitelist are
    # considered (the original block REPLACES the accumulator).
    _E("basico_whitelist",
       lambda w: (w.bench_count < 5
                  and any(b in w.basics
                          for b in _ns_crustle_allowed_basics(w))), 900),
    _E("dipplin_con_applin",
       lambda w: (Dipplin in _ns_crustle_evos_permitidas(w)
                  and Dipplin in w.evos and not w.has_hydrapple
                  and (w.field_counts.get(Applin, 0) >= 1
                       or w.hand_counts.get(Applin, 0) >= 1)), 880),
    _E("bayleef_con_chikorita",
       lambda w: (Bayleef in _ns_crustle_evos_permitidas(w)
                  and Bayleef in w.evos and not w.meganium_in_play
                  and (w.field_counts.get(Chikorita, 0) >= 1
                       or w.hand_counts.get(Chikorita, 0) >= 1)), 880),
    _E("meganium_con_bayleef",
       lambda w: (Meganium in _ns_crustle_evos_permitidas(w)
                  and Meganium in w.evos and not w.meganium_in_play
                  and (w.field_counts.get(Bayleef, 0) >= 1
                       or w.hand_counts.get(Bayleef, 0) >= 1)), 900),
    _E("energia_dipplin_activo_cero",
       lambda w: (_ns_useful_energy_without_grass(w)
                  and not w.state.energyAttached
                  and w.my_state.active
                  and w.my_state.active[0] is not None
                  and w.my_state.active[0].id == Dipplin
                  and len(w.my_state.active[0].energies) == 0), 900),
    # Recover Hydrapple ex for the KO on the Kangaskhan (op_kang_ko_target).
    _E("hydra_para_kang_ko",
       lambda w: (w.op_kang_ko_target and Hydrapple_ex in w.evos
                  and not w.has_hydrapple
                  and (w.field_counts.get(Dipplin, 0) >= 1
                       or w.hand_counts.get(Dipplin, 0) >= 1)), 960),
    # Charge a benched attacker before refilling with Lillie's.
    _E("energia_cargar_banca", _ns_e_charge_bench_crustle, 850),
]

def _ns_full_bench_keep(w, ns_score):
    """Full-bench cut-off (like UB/Poke Pad) with exceptions: useful
    energy or a pre-evolution in play whose evolution is in the discard."""
    if w.bench_count < 5 or ns_score <= 0:
        return False
    useful_energy = _ns_useful_energy_without_grass(w) and not w.state.energyAttached
    if (_ns_useful_energy_without_grass(w) and w.my_state.active
            and w.my_state.active[0] is not None
            and w.my_state.active[0].id == Hydrapple_ex
            and len(w.my_state.active[0].energies) * _grass_mult() < 2):
        useful_energy = True
    # The recovered energy does NOT stop being useful because the turn's MANUAL
    # attachment has already been spent: Teal Dance and Ripening Charge are
    # ABILITIES and can put it on the field anyway (user, registro_006 step 68 vs
    # Mega Abomasnow ex, LOST). There, with a full bench and `energyAttached`, this
    # cut-off vetoed the Night Stretcher that enabled the finisher: Syrup Storm
    # 30+30x10 = 330 against 350 HP, and the Grass from the discard (via Teal Dance
    # on a benched Ogerpon) raised it to 390. A real charging route is required
    # (`_ns_charge_route_open`) so as not to recover a dead Grass.
    if not useful_energy:
        if _ns_e_syrup_letal(w) and _ns_charge_route_open(w):
            useful_energy = True
        elif _ns_e_finisher_with_active(w):
            useful_energy = True
        elif _ns_e_finisher_via_promotion(w):
            useful_energy = True
        elif _ns_e_active_below_cost(w):
            useful_energy = True
        elif _ns_e_active_pays_retreat(w):
            useful_energy = True
    something_to_evolve = w.evolve_possible_in_play or (
        (w.field_counts.get(Chikorita, 0) >= 1 and Bayleef in w.evos) or
        (w.field_counts.get(Bayleef, 0) >= 1 and Meganium in w.evos) or
        (w.field_counts.get(Applin, 0) >= 1 and Dipplin in w.evos) or
        (w.field_counts.get(Dipplin, 0) >= 1 and Hydrapple_ex in w.evos))
    return not something_to_evolve and not useful_energy

_AJUSTES_NS_PLAY = [
    _Adjustment("full_bench_keep_it",
            lambda w, s: _ns_full_bench_keep(w, s),
            lambda w, s: SCORE_VETO),
    # Anti-Kangaskhan rescue: recovering the Hydrapple ex that knocks out the
    # projected Mega Kangaskhan ex (op_kang_ko_target) dominates everything.
    _Adjustment("hydra_rescue_anti_kangaskhan",
            lambda w, s: (w.op_kang_ko_target and Hydrapple_ex in w.evos
                          and not w.has_hydrapple
                          and (w.field_counts.get(Dipplin, 0) >= 1
                               or w.hand_counts.get(Dipplin, 0) >= 1)),
            lambda w, s: 34000),
]

def _score_night_stretcher_play(ctx: DecisionContext) -> int:
    """Scores playing Night Stretcher (it recovers a Pokemon or Energy from the
    discard). Body migrated to the RULES ENGINE (phase 4) with the ARGMAX mode
    (_resolve_max): ~30 recovery scenarios compete and the best one is
    mapped to score tiers; vs Crustle/Cornerstone ONLY the whitelist competes
    (the original replaces the accumulator)."""
    w = _CtxNSPlay(ctx)
    if ctx.op_is_crustle_deck or ctx.op_is_cornerstone_deck:
        best, traza_max = _resolve_max(_ESC_NS_CRUSTLE, w)
    else:
        best, traza_max = _resolve_max(_ESC_NS_RECUPERACION, w)
    if best >= 900:
        base = 11800
    elif best >= 800:
        base = 11000
    elif best >= 700:
        base = 10400
    elif best > 0:
        base = 9800
    else:
        base = SCORE_VETO
    score, traza = _resolve_rules([], _AJUSTES_NS_PLAY, w, default=base)
    if os.environ.get("PTCG_DEBUG"):
        print("[reglas ns->play]", traza_max, "|", " | ".join(traza))
    return score






_RULES_FOREST_PLAY = [
    _FixedRule("t1_going_first",
               lambda c: c.we_go_first and c.state.turn == 1,
               lambda c: SCORE_VETO),
    # A REDUNDANT copy of Forest on the first turn going second
    # (cornerstone_cubchoo autopsy p004, jul 2026 plan): with >=2 Forest in
    # HAND and an evolution chain that Forest helps (Applin/Chikorita
    # with its evolution available), keeping them all is over-conservative. One is
    # played even if the opponent has no stadium: the deck runs 4 copies, the
    # extra one is dead weight and if the stadium survives the chain fires
    # next turn. The `_fv_evolution_chain` gate avoids spending it on hands
    # with no line (measurement vs comfey: without the gate the matchup dropped ~10pts).
    # The veto below still covers the single-copy case.
    _FixedRule("t1_second_redundant_copy",
               lambda c: ((not c.we_go_first) and c.state.turn == 2
                          and c.stadium_id == 0
                          and c.hand_counts.get(Forest_of_Vitality, 0) >= 2
                          and _fv_evolution_chain(c)),
               lambda c: 12000),
    # vs CRUSTLE: THE STADIUM BEFORE THE LILLIE'S (user's rule).
    # The general veto on stadiums during OUR first turn exists so as not to hand
    # the Forest to an opponent who replaces it immediately. The Crustle deck does
    # not play a stadium (or runs one or two loose copies), so that risk does not
    # exist: the Forest stays on the field. And Lillie's Determination SHUFFLES THE
    # WHOLE HAND into the deck, so keeping the stadium "for later"
    # with a Lillie's in the same hand means LOSING IT. Going SECOND (turn 2)
    # with a stadium + Lillie's and the Supporter still unplayed, the stadium is
    # played first -- the `_TIER_STADIUM` order tier (50) already puts it ahead of
    # the Supporter (tier 0) -- and then the hand is refilled.
    # Only vs Crustle: against the other matchups the veto still rules. What is
    # looked at is the LINE on the board (`_op_juega_crustle`) and not the flag
    # `op_is_crustle_deck`, which also switches on with Sylveon/Eevee: those
    # share the ex immunity, but not the absence of a stadium, which is the
    # only thing that justifies playing ours early.
    _FixedRule("t1_second_crustle_stadium_before_lillie",
               lambda c: ((not c.we_go_first) and c.state.turn == 2
                          and _op_juega_crustle(c.op_state)
                          and c.stadium_id == 0
                          and not c.state.supporterPlayed
                          and c.hand_counts.get(Lillie_Determination, 0) >= 1),
               lambda c: 12000),
    _FixedRule("t1_second_no_opponent_stadium",
               lambda c: ((not c.we_go_first) and c.state.turn == 2
                          and c.stadium_id == 0),
               lambda c: SCORE_VETO),
    _FixedRule("t1_second_replaces_the_stadium",
               lambda c: ((not c.we_go_first) and c.state.turn == 2
                          and c.stadium_id != 0
                          and c.stadium_id != Forest_of_Vitality),
               lambda c: 15000),
    _FixedRule("forest_already_in_play",
               lambda c: c.stadium_id == Forest_of_Vitality,
               lambda c: SCORE_VETO),
    # FIRST THE GRAND TREE ABILITY, THEN THE REPLACEMENT (user's rule).
    # With Grand Tree on the field and a Forest of Vitality in hand, playing the
    # Forest NOW throws away a FREE evolution chain (Basic ->
    # Stage 1 -> Stage 2 pulled from the deck). The opponent's stadium is not going
    # anywhere: the ability is used and in the SAME turn, with the ABILITY option
    # no longer in the menu, this rule stops firing and the Forest is played with its
    # normal score (`replace_the_opponent_stadium`, 15000).
    #
    # The same mechanism as "Teal Dance precedes the manual attachment": veto the
    # play while the ability is still OFFERED in the menu, instead of trying
    # to order two actions inside a single call to `agent()`.
    # `grand_tree_ability_pending` already requires an executable plan, so
    # a useless Grand Tree (no evolvable Basic, or with the chain
    # exhausted in the deck) does NOT hold the Forest back.
    _FixedRule("wait_for_the_grand_tree_ability",
               lambda c: c.grand_tree_ability_pending,
               lambda c: SCORE_VETO),
    # The Neutralization Zone cancels the DAMAGE of our ex to 1-prize
    # Pokemon: removing it is the most urgent thing (29000 with a grass line on the field).
    _FixedRule("cancel_neutralization_zone",
               lambda c: c.neutralization_zone_active,
               _v_fv_neutralization),
    # Team Rocket's Watchtower SWITCHES OFF the Meowth engine (it cancels Last-Ditch).
    # With the engine ALIVE, replacing it is a priority: 27000, below the
    # Neutralization Zone and above the evolution chain (21900-22000).
    # (July 2026 audit, suggestion 3)
    _FixedRule("revive_the_meowth_engine_vs_watchtower",
               lambda c: (c.watchtower_in_play
                          and c.field_counts.get(Meowth_ex, 0) < 2
                          and (c.hand_counts.get(Meowth_ex, 0) >= 1
                               or c.cards_in_deck.get(
                                   Meowth_ex, {}).get(ZONE_DECK, 0) > 0)),
               lambda c: 27000),
    # Festival Grounds SWITCHES ON Festival Lead: their Dipplin repeats the attack as
    # soon as it knocks out our active, which is how games against that deck are
    # closed (log 88971843). Replacing it switches the double attack off at the root,
    # so it goes ahead of the evolution chain (21900-22000): the chain pays off next
    # turn, the double attack kills us this one. It stays below the Meowth engine
    # (27000), which is also irreversible.
    # NOT MEASURED in self-play: the generic OpponentBot cannot pilot the Festival Lead
    # deck (98.9% in both arms), so the gate has no signal.
    #
    # ... AND NOT ON THE TURN THE STADIUM IS PAYING US (user, registro_006 steps
    # 81-86). The card is SHARED: with a Dipplin of ours able to attack and its
    # Do the Wave already knocking their Active out, Festival Grounds is worth a
    # prize TODAY -- twice over, since the same Dipplin throws the attack again
    # (`_festival_double_wave`). Replacing it that turn spends the prize to buy a
    # defence, and the Forest is still there to be played the turn the wave stops
    # cashing. It is the narrowest possible guard on purpose: `festival_lead_hostil`
    # keeps deciding whether the counter-stadium is worth FETCHING, and this only
    # holds back the turn it would cost a knockout.
    _FixedRule("switch_off_festival_lead",
               lambda c: (c.festival_lead_hostil
                          and not c.festival_lead_pays_us_now),
               lambda c: 26000),
    _FixedRule("enables_the_evolution_chain",
               _fv_evolution_chain,
               _v_fv_chain),
    _FixedRule("replace_the_opponent_stadium",
               lambda c: c.stadium_id != 0,
               lambda c: 15000),
    _FixedRule("early_development",
               lambda c: c.state.turn <= 4,
               _v_fv_temprano),
]

def _score_forest_of_vitality_play(ctx: DecisionContext) -> int:
    """Scores playing Forest of Vitality (the stadium that allows evolving
    the same turn). Body migrated to the RULES ENGINE (phase 4)."""
    return _resolve_with_trace("forest->play", _RULES_FOREST_PLAY, [],
                               ctx, default=8000)






































def _ub_meowth_for_tomorrow(ctx) -> bool:
    """Digging TODAY for the Meowth ex that will be played TOMORROW, because
    tomorrow there are no Items.

    The ONLY exception to "the Ultra Ball is only played for a Pokemon we are
    going to PLAY this turn" (`_ub_dig_meowth_gets_played`), and the mirror image
    of the one the sterile-turn rescue net already had: with the Item lock
    hanging over us (`_bloqueo_de_items_inminente`) the Ultra Ball is not a
    resource to keep, it is a resource that EXPIRES.

    The scenario that motivates it (user, registro_002 step 17 vs Dragapult,
    LOST -- episode 89079426, turn 2 going second):

        US                                        OPPONENT
        active Chikorita 70, 1 energy             active **Budew 30**
        bench  Fezandipiti ex 210, 0 energies     bench  Dreepy x2, Munkidori 1 en.
        hand   Grass x3, Boss's x2, **Ultra Ball**, Meganium, Forest
        (Lillie's Determination ALREADY played this turn)

    The agent **attacked with the Chikorita** and closed the turn with the Ultra
    Ball in hand. On the following turn the Budew's *Itchy Pollen* killed it: the
    only card that could rebuild the game sat there as decoration until the end.

    The board was the worst possible one -- a Fezandipiti ex 3 energies away from
    attacking (one per turn) and a Meganium in hand with no Bayleef under it:
    `_no_attacker_for_tomorrow`. The correct line is to dig out the Meowth ex NOW
    and put it down next turn (Pokemon and abilities are NOT blocked by
    Itchy Pollen), where its *Last-Ditch Catch* brings a Lillie's Determination
    -- a Supporter, also playable under the lock.

    Why the Meowth ex is not put down today (the user's reason): the turn's
    Supporter is already spent, so its ability would produce nothing and the body
    would only GIVE AWAY two prizes on the opponent's turn. In hand it costs
    nothing.

    Guards: no Lillie's/Meowth already in hand (there is nothing to search for),
    no Meowth in play (the engine is already assembled; a second body is 2 prizes
    for zero), with both pieces alive in the deck, a bench slot for tomorrow and
    the ability not switched off (Watchtower / Iron Thorns)."""
    if not ctx.item_lock_incoming or ctx.itchy_pollen_active:
        return False
    if ctx.meowth_ability_lock or ctx.bench_count >= 5:
        return False
    _h, _f, _cards = ctx.hand_counts, ctx.field_counts, ctx.cards_in_deck
    if (_h.get(Meowth_ex, 0) >= 1 or _h.get(Lillie_Determination, 0) >= 1
            or _f.get(Meowth_ex, 0) >= 1):
        return False
    if (_cards.get(Meowth_ex, {}).get(ZONE_DECK, 0) <= 0
            or _cards.get(Lillie_Determination, {}).get(ZONE_DECK, 0) <= 0):
        return False
    return _no_attacker_for_tomorrow(ctx.my_state, _h, _f)


def _ub_target_score(ctx, _ubf) -> int:
    """Phase D of Ultra Ball (a route that was NOT cancelled): it values the best
    search target and maps it to ub_score tiers, with penalties for discards and
    a possible Supporter deferral. Verbatim body (step 2 of the plan)."""
    state = ctx.state
    my_state = ctx.my_state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    my_prize = ctx.my_prize
    op_prize = ctx.op_prize
    we_go_first = ctx.we_go_first
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    has_hydrapple = ctx.has_hydrapple
    ko_last_turn = ctx.ko_last_turn
    watchtower_in_play = ctx.meowth_ability_lock
    itchy_pollen_active = ctx.itchy_pollen_active
    can_attack = ctx.can_attack
    _field_at_turn_start = ctx.field_at_turn_start
    ACTIVE_CARDS_IN_DECK = ctx.cards_in_deck
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_is_cornerstone_deck = ctx.op_is_cornerstone_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    budew_on_op_field = ctx.budew_on_op_field
    budew_op_index = ctx.budew_op_index
    _mega_line_active = ctx.mega_line_active
    _evolve_possible_in_play = ctx.evolve_possible_in_play
    _best_supp_in_hand_val = ctx.best_supp_in_hand_val
    _best_supp_in_deck_val = ctx.best_supp_in_deck_val
    _win_via_boss_gust = ctx.win_via_boss_gust
    _gust_2prize_via_boss = ctx.gust_2prize_via_boss
    _boss_deny_alakazam_line = ctx.boss_deny_alakazam_line
    _ub_evolve_needs_search = _ubf.evolve_needs_search
    _ub_evolve_now_search = _ubf.evolve_now_search
    _ub_developed_attacker_board = _ubf.developed_attacker_board
    hand_size = _ubf.hand_size
    ub_score = 10000

    _ub_hand_play_options, _ub_supporters_in_hand = _count_hand_play_options(
        hand_counts, field_counts, bench_count, state.energyAttached)
    _ub_hand_is_weak = (_ub_hand_play_options <= 1 and hand_size <= 4)
    _ub_has_energy_for_teal = hand_counts.get(Basic_Grass_Energy, 0) >= 1

    # ONE question, asked ONCE for the whole Ultra Ball: does the Supporter we
    # already hold win the turn's only Supporter slot? If it does, every branch
    # here that values the Ultra Ball as "a searcher for the Meowth ex that
    # searches for a Supporter" is buying a card that cannot be played today.
    _ub_supp_in_hand_turn = _supp_in_hand_takes_the_turn(ctx)

    ub_best_target = _eval_ub_best_target(
        field_counts, hand_counts, meganium_in_play, has_hydrapple,
        forest_in_play, op_has_ex_immune_active, op_has_ex_immune_bench,
        op_prize, bench_count, state, ko_last_turn,
        _best_supp_in_deck_val, _ub_supporters_in_hand, _ub_hand_is_weak,
        _ub_has_energy_for_teal, we_go_first,
        _best_supp_in_hand_val,
        op_is_crustle_deck, op_is_cornerstone_deck,
        budew_on_op_field and budew_op_index == 0,
        watchtower_in_play,
        op_hand_count=ctx.op_hand_count,
        op_state=ctx.op_state, cards_in_deck=ACTIVE_CARDS_IN_DECK,
        supp_in_hand_takes_the_turn=_ub_supp_in_hand_turn,
        bench_max=getattr(my_state, 'benchMax', 5) or 5,
        our_cap_already_spent=AGENT_STATE._xerosic_played_this_turn)

    # Chain UB -> Meowth ex -> Last-Ditch Catch -> Supporter. `field_counts < 2`
    # was NOT enough: with ONE Meowth ex already in play the PLAY branch vetoes the
    # second body, so the Ultra Ball dug out a card that was then not played
    # (registro_004 step 35). See `_ub_dig_meowth_gets_played`.
    if (not _stamp_pendiente(ctx) and
            hand_counts.get(Meowth_ex, 0) == 0 and
            hand_counts.get(Lillie_Determination, 0) == 0 and
            not _ub_supp_in_hand_turn and
            not state.supporterPlayed and
            _ub_dig_meowth_gets_played(ctx) and
            bench_count < 5 and
            ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0 and
            ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0):

        if _ub_hand_is_weak or _mega_line_active:
            ub_best_target = max(ub_best_target, 950)
        elif _best_supp_in_deck_val >= 600:
            ub_best_target = max(ub_best_target, 850)

    # The SAME chain, shifted by one turn: with the Item lock hanging over us the
    # Meowth ex is dug out TODAY even though it can only be put down TOMORROW (see
    # `_ub_meowth_for_tomorrow`). It is the only branch that does not require the
    # target to be used this turn, because it is the only one where keeping the
    # Ultra Ball is the same as throwing it away.
    #
    # ...but not under a PENDING STAMP: "tomorrow" never arrives for a card that
    # this turn's Unfair Stamp shuffles back into the deck TODAY. Without this
    # gate the score would keep buying the Ultra Ball for a Meowth ex that the
    # fetch now refuses (`the_stamp_shuffles_the_last_ditch_supporter`), and the
    # Item would be spent on whatever came second.
    if _ub_meowth_for_tomorrow(ctx) and not _stamp_pendiente(ctx):
        ub_best_target = max(ub_best_target, 1100)

    if ub_best_target == 0:
        # NO target worth having in the deck: the Ultra Ball contributes
        # nothing. SCORE_CANCEL (not SCORE_VETO) for the same reason as the branches
        # below: with the rest of the turn also vetoed, the menu INDEX tie-break
        # played it anyway instead of attacking.
        ub_score = SCORE_CANCEL
    else:

        _ub_ns_in_hand = (hand_counts.get(Night_Stretcher, 0) >= 1)

        _ub_meowth_chain = (
            ub_best_target >= 850 and
            not state.supporterPlayed and
            ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0 and
            ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0)
        safe_discards = 0
        for cid, cnt in hand_counts.items():
            if cid == Ultra_Ball:
                continue
            for _ in range(cnt):

                if cid == Basic_Grass_Energy:
                    safe_discards += 1

                elif cid in (Chikorita, Applin, Tapu_Bulu):
                    if field_counts.get(cid, 0) >= 1:
                        safe_discards += 1
                    elif ACTIVE_CARDS_IN_DECK.get(cid, {}).get(ZONE_DECK, 0) >= 1:
                        safe_discards += 1
                    elif _ub_ns_in_hand:
                        safe_discards += 1

                elif cid == Forest_of_Vitality and (forest_in_play or cnt > 1):
                    safe_discards += 1
                elif cid == Meganium and meganium_in_play:
                    safe_discards += 1
                elif cid == Bayleef and meganium_in_play:
                    safe_discards += 1
                elif cid == Hydrapple_ex and has_hydrapple and cnt > 1:
                    safe_discards += 1
                elif cid == Meowth_ex and field_counts.get(Meowth_ex, 0) >= 1:
                    safe_discards += 1
                elif cid == Fezandipiti_ex and (field_counts.get(Fezandipiti_ex, 0) >= 1 or not ko_last_turn):
                    safe_discards += 1
                elif cid == Night_Stretcher and cnt > 1:
                    safe_discards += 1
                elif cid == Lanas_Aid and cnt > 1:
                    safe_discards += 1
                elif cid == Lillie_Determination and cnt > 1:
                    safe_discards += 1

                elif cid == Lanas_Aid and cnt == 1 and _ub_meowth_chain:
                    safe_discards += 1

                elif cid == Dipplin:
                    if cnt > 1:
                        safe_discards += 1
                    elif field_counts.get(Applin, 0) == 0:
                        safe_discards += 1

        if (_ub_developed_attacker_board and
                ub_best_target < 800 and
                not _ub_evolve_needs_search):
            # A board that is already developed with a ready attacker:
            # do not spend an Ultra Ball + discards on a
            # low-value development target.
            #
            # SCORE_CANCEL, not SCORE_VETO (user, registro_006 step 101 vs Mega
            # Lucario ex, LOST): with ALL the turn's plays vetoed
            # (attack = -1 by default) the argmax tie-break is by menu
            # INDEX, and the Ultra Ball -- which appears before the attack -- was
            # played despite being vetoed right here. -100 leaves it below
            # the veto floor so the turn is closed by the ATTACK. It is the
            # same reason the full-bench safeguard of
            # `_ub_terminal_overrides` already used SCORE_CANCEL.
            ub_score = SCORE_CANCEL
        elif ub_best_target < 300 and safe_discards < 2:
            ub_score = SCORE_CANCEL
        elif ub_best_target < 250:
            ub_score = SCORE_CANCEL
        elif bench_count >= 5 and not _evolve_possible_in_play:
            # FULL bench + NO Pokemon in play to
            # evolve: the Ultra Ball would only carry the
            # card to HAND (nothing can be benched)
            # and it enables no evolution, so it contributes
            # nothing this turn. It is cancelled to
            # KEEP the resource for when a
            # Pokemon is knocked out (a bench slot) or there is something to
            # evolve.
            ub_score = SCORE_VETO
        else:

            if ub_best_target >= 900:
                ub_score = 12500
            elif ub_best_target >= 700:
                ub_score = 12000
            elif ub_best_target >= 500:
                ub_score = 11200
            elif ub_best_target >= 300:
                ub_score = 10500
            else:
                ub_score = 10000

            if safe_discards < 2:
                ub_score -= 600
            elif safe_discards < 3:
                ub_score -= 250

            if _ub_hand_is_weak and ub_best_target >= 650:
                ub_score += 500

            if hand_counts.get(Lillie_Determination, 0) >= 1 and not state.supporterPlayed:
                _ub_enables_evo = (ub_best_target >= 800)
                # With exactly 6 prizes left
                # Lillie's Determination draws 8 cards:
                # that massive reinforcement takes priority,
                # so the Ultra Ball is postponed even if it
                # enables an evolution, in order to play
                # Lillie's first.
                # EXCEPTION: if the Ultra Ball enables an
                # evolution that can be COMPLETED this
                # turn (`_ub_evolve_now_search`: a pre-evolution on
                # the board already evolvable through Forest or because it
                # has been there since the start of the turn, and the
                # piece in the deck), it is NOT degraded: first
                # the evolution line is developed and
                # Lillie's is played afterwards, so as not to shuffle
                # back into the deck Ultra Balls that this turn
                # enabled evolutions.
                #
                # ...AND THE EXEMPTION HAS TO BE BACKED BY THE VALUE IT CLAIMS
                # (user, registro_004 step 50 vs Alakazam, LOST).
                # `_ub_evolve_now_search` only says a pre-evolution on the board
                # is evolvable and its piece is in the deck; it does NOT say the
                # Ultra Ball is going to fetch THAT piece. In that step it was
                # true (an Applin from the start of the turn, a Dipplin in the
                # deck) while the valuation had priced the search at 280 -- its
                # "preparation" band, the one that means "adds nothing this
                # turn" -- because a Dipplin from the OTHER Applin was already
                # in play. So the Ultra Ball skipped the refill on the strength
                # of an evolution nobody was buying, and the Lillie's it
                # postponed shuffled the fetched card back into the deck four
                # actions later.
                #
                # `_ub_enables_evo` is the value's own answer to the same
                # question, and it was already computed right here. Requiring
                # both leaves the exemption exactly where it was designed to
                # work (an evolution that completes TODAY prices at 800-1000)
                # and closes it where the value itself says the target waits
                # for tomorrow. See
                # [[el-hueco-de-supporter-muere-con-el-ataque-que-cierra-el-turno]]
                # and [[lo-que-la-mano-paga-va-antes-de-que-la-mano-se-baraje]].
                _lillie_draws_8 = (my_prize == 6)
                if ((hand_size < 4 or not _ub_enables_evo
                        or _lillie_draws_8)
                        and not (_ub_evolve_now_search and _ub_enables_evo)):
                    ub_score = 4500

            # Do not burn Lillie's Determination as the cost
            # of an Ultra Ball when that would leave us with no hand.
            # If after paying the cost (discarding 2 cards) at
            # least 2 cards other than the
            # Lillie's do not remain, playing Ultra Ball forces us to discard
            # the Lillie's and we are left practically with no
            # hand. In that case it is cancelled, unless the
            # search serves to close the game (taking
            # the prizes we are missing, that is, very few
            # prizes left).
            if hand_counts.get(Lillie_Determination, 0) >= 1:
                _ub_non_lillie_discardable = 0
                for _ub_lid, _ub_lcnt in hand_counts.items():
                    if _ub_lid in (Ultra_Ball, Lillie_Determination):
                        continue
                    _ub_non_lillie_discardable += _ub_lcnt
                _ub_lillie_forced_discard = (
                    _ub_non_lillie_discardable < 2)
                _ub_winning_search = (
                    my_prize <= 2 or
                    _win_via_boss_gust or
                    _gust_2prize_via_boss)
                if (_ub_lillie_forced_discard
                        and not _ub_winning_search):
                    ub_score = SCORE_VETO

    return ub_score


def _ub_score_before_overrides(ctx, _ubf) -> int:
    """Phases B+C+D of _score_ultra_ball_play: early hard cut-offs, vetoes by
    discard cost and target valuation. It returns ub_score BEFORE the
    terminal overrides (phase E). Verbatim body (step 2 of the plan)."""
    state = ctx.state
    my_state = ctx.my_state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    my_prize = ctx.my_prize
    op_prize = ctx.op_prize
    we_go_first = ctx.we_go_first
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    has_hydrapple = ctx.has_hydrapple
    ko_last_turn = ctx.ko_last_turn
    watchtower_in_play = ctx.meowth_ability_lock
    itchy_pollen_active = ctx.itchy_pollen_active
    can_attack = ctx.can_attack
    _field_at_turn_start = ctx.field_at_turn_start
    ACTIVE_CARDS_IN_DECK = ctx.cards_in_deck
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_is_cornerstone_deck = ctx.op_is_cornerstone_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    budew_on_op_field = ctx.budew_on_op_field
    budew_op_index = ctx.budew_op_index
    _mega_line_active = ctx.mega_line_active
    _evolve_possible_in_play = ctx.evolve_possible_in_play
    _best_supp_in_hand_val = ctx.best_supp_in_hand_val
    _best_supp_in_deck_val = ctx.best_supp_in_deck_val
    _win_via_boss_gust = ctx.win_via_boss_gust
    _gust_2prize_via_boss = ctx.gust_2prize_via_boss
    _boss_deny_alakazam_line = ctx.boss_deny_alakazam_line
    _ub_evolve_needs_search = _ubf.evolve_needs_search
    _ub_evolve_now_search = _ubf.evolve_now_search
    _ub_developed_attacker_board = _ubf.developed_attacker_board
    hand_size = _ubf.hand_size
    ub_score = 10000

    if hand_size < 3:
        ub_score = SCORE_VETO
    elif bench_count >= 5 and not _ub_evolve_needs_search:
        # Early SAFEGUARD (a hard cut-off): with a FULL bench
        # and NO Pokemon in play that can be evolved WITH A
        # SEARCH (the evolution piece is missing from hand and is in the
        # deck), the Ultra Ball cannot bench anything new and would only
        # carry a REDUNDANT card to hand (e.g. a 2nd
        # Meganium when there is already one in play), while also paying the
        # cost of discarding 2 useful cards. It does not count either if the
        # evolution is ALREADY in hand (that line evolves without an
        # Ultra Ball). It contributes NOTHING this turn, so it is cancelled
        # ALWAYS to keep the resource until a Pokemon is knocked out
        # (a bench slot) or there is an evolution to search for.
        # Independent of how ub_best_target ends up.
        # A value CLEARLY below the veto floor (-1) is used so that,
        # on a turn where the rest of the plays are also vetoed (attack /
        # retreat = -1 and END very negative), the argmax does NOT fall by
        # default into playing this useless Ultra Ball (index 0). That way
        # attacking / passing is preferred over wasting the Ultra Ball + 2
        # discards (user, registro 006 step 72 vs Hops, LOST: a full bench,
        # it searched for a Hydrapple ex that was not left in the deck).
        ub_score = SCORE_CANCEL
    else:

        _ub_cancel_for_stamp = _ub_cancel_stamp(ctx)
        _ub_cancel_for_fez = _ub_cancel_fez(ctx)
        _ub_cancel_for_lillie = _ub_cancel_lillie(ctx)
        _ub_cancel_for_meowth = _ub_cancel_meowth(ctx)
        _ub_cancel_for_xerosic = _ub_cancel_xerosic(ctx)
        # The Supporter that carries the NEXT turn: the four vetoes above all
        # require an unplayed Supporter, so with the turn's Supporter already
        # spent the cost was free to eat the whole Supporter hand. See
        # `_ub_cancel_tomorrow_supporter`.
        _ub_cancel_for_tomorrow = _ub_cancel_tomorrow_supporter(ctx)
        # THE ENGINE ITSELF: the cap (Xerosic) and the refill (Lillie's) are
        # never paid as a cost, at any hand size and whether or not the turn's
        # Supporter is spent, unless the search wins the game. It protects them
        # as a SET, which is what the one-card-at-a-time vetoes above could not
        # do. See `_ub_cancel_engine_supporters` (registro_006 step 81).
        _ub_cancel_for_engine = _ub_cancel_engine_supporters(ctx)
        # NO SURPLUS AT ALL: the two cards that would pay are protected for
        # DIFFERENT reasons, so no single-card veto above speaks for them. See
        # `_ub_cancel_no_surplus` (registro_004 step 49).
        _ub_cancel_for_surplus = _ub_cancel_no_surplus(ctx)
        if (_ub_cancel_for_stamp or _ub_cancel_for_fez
                or _ub_cancel_for_lillie or _ub_cancel_for_meowth
                or _ub_cancel_for_xerosic or _ub_cancel_for_tomorrow
                or _ub_cancel_for_engine
                or _ub_cancel_for_surplus):
            ub_score = SCORE_VETO

        if not _ub_cancel_for_meowth and not _ub_cancel_for_stamp and not _ub_cancel_for_fez and not _ub_cancel_for_lillie and not _ub_cancel_for_xerosic and not _ub_cancel_for_tomorrow and not _ub_cancel_for_engine and not _ub_cancel_for_surplus:
            ub_score = _ub_target_score(ctx, _ubf)
    return ub_score




def _score_ultra_ball_play(ctx) -> int:
    """Scores playing Ultra Ball. The orchestrator (step 2 of the plan): it composes
    the 3 already isolated phases. Phase A `_ub_derive_flags` (derived context) ->
    phases B+C+D `_ub_score_before_overrides` (hard cut-offs, cost vetoes,
    target valuation) -> phase E `_ub_terminal_overrides` (terminal overrides,
    ALWAYS last). See docs/project-history.md."""
    # Strategy vs Comfey (user, registro_005): the Ultra Ball is ONLY good for
    # searching for Teal Mask Ogerpon ex, and the maximum is 2 in play. If we already
    # have 2, the Ultra Ball is useless -> CANCEL (below the veto floor of -1 so the
    # agent ATTACKS/PASSES instead of wasting the card and its 2 discards).
    if (ctx.op_is_comfey_deck
            and ctx.field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2):
        return SCORE_CANCEL
    # UB->Meowth->Lillie's engine on the energy tier (see the helper): 31450
    # beats the manual attachment (~31410) and Ripening Charge without a pivot (30000),
    # and stays BELOW the ability pivots with a KO/retreat (31500-31600).
    # It arms `_ub_engine_pivot_turn` so the FETCH of this UB chooses Meowth.
    if _ub_engine_refresh_pivot(ctx):
        AGENT_STATE._ub_engine_pivot_turn = True
        return 31450
    # vs Alakazam with a fat opposing hand (Powerful Hand): assembling the Xerosic
    # cap via Ultra Ball -> Meowth ex -> Last-Ditch -> Xerosic (user,
    # registro_008 step 75, WON suboptimally: the agent played Lillie's
    # -- a redundant refill with a charged Hydrapple ex + 3 benched attackers -- in
    # stead of digging for the disruption). Disruption priority in the Xerosic band
    # (5950): above the attack (which would close the turn without capping Powerful
    # Hand) and above Lillie's (which also spends the turn's Supporter), below the
    # winning finishers and the 2-prize gust. Only when Meowth has to be DUG for (not
    # in hand). It arms `_ub_engine_pivot_turn` so the FETCH chooses Meowth ex and
    # continues the chain (its Last-Ditch searches for Xerosic through `xerosic_alakazam`).
    if (_alakazam_dig_xerosic_engine(ctx)
            and ctx.hand_counts.get(Meowth_ex, 0) == 0):
        AGENT_STATE._ub_engine_pivot_turn = True
        return 5950
    _ubf = _ub_derive_flags(ctx)
    ub_score = _ub_score_before_overrides(ctx, _ubf)
    ub_score = _ub_terminal_overrides(
        ctx, ub_score, _ubf.survival_mode, _ubf.hand_size, _ubf.first_action_turn)
    return ub_score


class _CtxLillie:
    """DecisionContext wrapper for the Lillie's Determination rules:
    it precomputes the derived values the original block computed at the start
    (ready ex attackers, pending/evolvable evolution lines,
    a charged active Hydrapple, the Boss's guard vs Hop's) and delegates the rest
    of the fields to the ctx via __getattr__."""

    def __init__(self, ctx):
        self.c = ctx
        my_state = ctx.my_state
        hand_counts = ctx.hand_counts
        field_counts = ctx.field_counts
        meganium_in_play = ctx.meganium_in_play
        has_hydrapple = ctx.has_hydrapple
        forest_in_play = ctx.forest_in_play
        _field_at_turn_start = ctx.field_at_turn_start

        self.hand_len = len(my_state.hand or [])

        _ready_ex_attackers = 0
        _lillie_my_pkmn = (
            [my_state.active[0]] if (my_state.active and my_state.active[0] is not None) else [])
        _lillie_my_pkmn += [bp for bp in my_state.bench if bp is not None]
        for _exp in _lillie_my_pkmn:
            _exp_eff = len(_exp.energies) * _grass_mult()
            if _exp.id == Hydrapple_ex and _exp_eff >= 2:
                _ready_ex_attackers += 1
            elif _exp.id == Teal_Mask_Ogerpon_ex and _exp_eff >= 3:
                _ready_ex_attackers += 1
            elif _exp.id == Fezandipiti_ex and _exp_eff >= 3:
                _ready_ex_attackers += 1
        self.ready_ex_attackers = _ready_ex_attackers

        # Evolution pieces in hand whose pre-evolution is ALREADY in play
        # (active or bench): if we shuffle the hand with Lillie's Determination
        # we would return them to the deck and lose the evolution line.
        # We detect that situation so as NOT to play Lillie's until the available
        # evolutions are completed.
        _lillie_pending_evo = False
        if not meganium_in_play:
            if (hand_counts.get(Bayleef, 0) >= 1 and
                    field_counts.get(Chikorita, 0) >= 1):
                _lillie_pending_evo = True
            if (hand_counts.get(Meganium, 0) >= 1 and
                    field_counts.get(Bayleef, 0) >= 1):
                _lillie_pending_evo = True
            if (forest_in_play and
                    hand_counts.get(Meganium, 0) >= 1 and
                    field_counts.get(Chikorita, 0) >= 1 and
                    hand_counts.get(Bayleef, 0) >= 1):
                _lillie_pending_evo = True
        if not has_hydrapple:
            if (hand_counts.get(Dipplin, 0) >= 1 and
                    field_counts.get(Applin, 0) >= 1):
                _lillie_pending_evo = True
            if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                    field_counts.get(Dipplin, 0) >= 1):
                _lillie_pending_evo = True
            if (forest_in_play and
                    hand_counts.get(Hydrapple_ex, 0) >= 1 and
                    field_counts.get(Applin, 0) >= 1 and
                    hand_counts.get(Dipplin, 0) >= 1):
                _lillie_pending_evo = True
        self.pending_evo = _lillie_pending_evo

        # An evolution line "with a GAP" that Ultra Ball can complete (user,
        # registro_004 step 47 vs Alakazam, LOST): we have the BASIC in
        # play and the STAGE 2 in HAND, but the intermediate STAGE 1 is missing
        # (Bayleef / Dipplin), which is in the DECK and can be SEARCHED for with an Ultra
        # Ball. Lillie's Determination SHUFFLES the whole hand into the deck, losing the
        # Stage 2 (Meganium / Hydrapple ex) and the Ultra Ball itself: the right play
        # is to play the Ultra Ball FIRST to bring the intermediate piece and assemble
        # the line (Chikorita->Bayleef->Meganium), and only then refill. Unlike
        # `pending_evo` (a DIRECT evolution already in hand), here the
        # intermediate piece is missing but searchable. Deck-agnostic.
        _lillie_ub_gapped_line = False
        if hand_counts.get(Ultra_Ball, 0) >= 1:
            if (not meganium_in_play
                    and hand_counts.get(Meganium, 0) >= 1
                    and field_counts.get(Chikorita, 0) >= 1
                    and hand_counts.get(Bayleef, 0) == 0
                    and field_counts.get(Bayleef, 0) == 0
                    and ctx.cards_in_deck.get(
                        Bayleef, {}).get(ZONE_DECK, 0) >= 1):
                _lillie_ub_gapped_line = True
            if (not has_hydrapple
                    and hand_counts.get(Hydrapple_ex, 0) >= 1
                    and field_counts.get(Applin, 0) >= 1
                    and hand_counts.get(Dipplin, 0) == 0
                    and field_counts.get(Dipplin, 0) == 0
                    and ctx.cards_in_deck.get(
                        Dipplin, {}).get(ZONE_DECK, 0) >= 1):
                _lillie_ub_gapped_line = True
        # BREAKING THE MUTUAL BLOCK Lillie's <-> Ultra Ball (user, registro_010
        # step 116 vs Dragapult, LOST). The two cards can be
        # yielding to each other at the same time:
        #   * this rule says "do not play Lillie's, it would shuffle away the Ultra Ball
        #     I am going to assemble the line with";
        #   * and `_ub_cancel_lillie` says "do not play the Ultra Ball, its cost
        #     of discarding 2 would take the Lillie's".
        # When both fire at once NEITHER is played and the
        # turn's Supporter dies in hand: on that step the hand was
        # {Ultra Ball x3, Hydrapple ex, Lillie's} and the turn closed by attacking.
        # The deference only makes sense if the Ultra Ball can be played for
        # something OTHER than this very Lillie's, so the way is given except in
        # that circular case. It is the same failure -- and the same way of breaking it
        # -- as in the Stamp<->Supporter pair (`_stamp_worth_playing`: "the way was
        # given to a card that was no longer going to be played").
        #
        # The Ultra Ball's full score is deliberately NOT consulted: the
        # other COST vetoes are about THIS INSTANT and lift themselves within
        # the turn. In registro_004 step 47 (the case that created this rule) the
        # Ultra Ball is at -1 through `_ub_cancel_meowth` -- its cost would take
        # the Meowth ex -- but the agent puts the Meowth down FIRST and afterwards
        # the Ultra Ball is playable: there keeping the Lillie's is correct and a
        # score-based gate would have thrown it away.
        #
        # And it is only broken if this Lillie's is the ONLY Supporter in hand, which
        # is when the block costs something: with ANOTHER Supporter in hand the turn's
        # slot is used anyway, so vetoing the Lillie's wastes nothing
        # and also preserves the line. That is the difference between the two scenarios:
        # on step 116 the hand was {Ultra Ball x3, Hydrapple ex, Lillie's} --
        # with no spare Supporter -- and on step 49 vs Marnie there is a Boss's
        # Orders alongside, which is the one that gets played.
        _other_supporter_in_hand = any(
            hand_counts.get(_sid, 0) >= 1
            for _sid in _SUPP_PLAY_IDS if _sid != Lillie_Determination)
        if (_lillie_ub_gapped_line and _ub_cancel_lillie(ctx)
                and not _other_supporter_in_hand
                and not ctx.state.supporterPlayed):
            _lillie_ub_gapped_line = False
        self.ub_gapped_line = _lillie_ub_gapped_line

        # Can we really EVOLVE one of those lines THIS turn? It only
        # counts if the pre-evolution is in play NOW (field_counts) and
        # can also evolve already: either it was in play at the start of the turn
        # (_field_at_turn_start, it did not come down this turn) or there is a Forest of
        # Vitality (which allows evolving the same turn). It avoids the false
        # positive of counting as evolvable a Pokemon that ALREADY evolved
        # this turn.
        _lillie_evolve_now = False
        if not meganium_in_play:
            if (hand_counts.get(Bayleef, 0) >= 1 and
                    field_counts.get(Chikorita, 0) >= 1 and
                    (forest_in_play or
                     _field_at_turn_start.get(Chikorita, 0) >= 1)):
                _lillie_evolve_now = True
            if (hand_counts.get(Meganium, 0) >= 1 and
                    field_counts.get(Bayleef, 0) >= 1 and
                    (forest_in_play or
                     _field_at_turn_start.get(Bayleef, 0) >= 1)):
                _lillie_evolve_now = True
        if not has_hydrapple:
            if (hand_counts.get(Dipplin, 0) >= 1 and
                    field_counts.get(Applin, 0) >= 1 and
                    (forest_in_play or
                     _field_at_turn_start.get(Applin, 0) >= 1)):
                _lillie_evolve_now = True
            if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                    field_counts.get(Dipplin, 0) >= 1 and
                    (forest_in_play or
                     _field_at_turn_start.get(Dipplin, 0) >= 1)):
                _lillie_evolve_now = True
        self.evolve_now = _lillie_evolve_now

        # A CHARGED Hydrapple ex in the active spot (>=2 effective Grass, ready
        # for Syrup Storm): playing Lillie's Determination takes priority
        # over Boss's Orders. Shuffling the hand and drawing 6-8 looks for more Pokemon
        # and energy to boost Syrup Storm (which scales with the Grass
        # energy in play); Hydrapple keeps its energy (Lillie's only
        # shuffles the HAND) and attacks afterwards anyway.
        self.hydra_active_charged = (
            my_state.active and my_state.active[0] is not None
            and my_state.active[0].id == Hydrapple_ex
            and len(my_state.active[0].energies) * _grass_mult() >= 2)

        # Rule (user, registro 008 step 84 vs Hops): Boss's Orders is a
        # KEY card vs Hops (it allows gusting and knocking out a Hops Phantump /
        # Trevenant that flips HEADS and knocks out our active). Lillie's
        # Determination shuffles the WHOLE hand into the deck (the Boss's included), so
        # vs Hops, with a Boss's in hand, Lillie's is only played if the
        # ACTIVE is the ONLY available attacker (we need to dig for more
        # resources). With >= 2 READY attackers (active + bench) Lillie's is NOT played:
        # the Boss's is kept in hand for the answer. If there is
        # no Boss's in hand, Lillie's can be played normally.
        # Generalisation (user, registro_007 p78 vs Archaludon, WON):
        # besides vs Hops, KEEP the Boss's (veto Lillie's) when the
        # opponent has on the bench a THREAT PRE-EVOLUTION that we can
        # gust and KNOCK OUT (Duraludon -> Archaludon ex: the deck's real
        # attacker) and we have >= 2 ready attackers. Lillie's would shuffle the Boss's
        # into the deck; with attackers to spare there is no need to dig, and the
        # priority is removing the attacker with Boss's. `_boss_ko_threat_preevo` is NOT
        # cancelled by `_active_attack_sufficient`, so it applies even if the
        # active could attack the opposing active (e.g. a not very dangerous Cinderace).
        # A DOOMED ACTIVE WITH NO RELIEF (user, registro_004 t4 vs Mega Lucario,
        # LOST): keeping the Boss's presupposes there will be a next turn
        # with a board. If the active dies for certain next turn
        # (`active_ko_likely`, the heuristic, or `active_doomed_real`, the opponent's
        # finisher read from attack_table) and there is NO ready benched attacker, there
        # is nobody to hand over to: reserving the Boss's condemns the turn.
        # There what rules is DIGGING with Lillie's (draw 6, or 8 with 6 prizes) to
        # find an attacker/energy. The same criterion as `_boss_yields_to_dig`.
        _lillie_doomed_without_relief = (
            (ctx.active_ko_likely or ctx.active_doomed_real)
            and not ctx.has_ready_bench_attacker)
        _hop_keep_boss = False
        if ((ctx.op_is_hop_deck or ctx.boss_ko_threat_preevo)
                and hand_counts.get(Boss_Orders, 0) >= 1
                and not ctx.boss_win_via_bench
                and not _lillie_doomed_without_relief):
            _lillie_ready_attackers = 0
            for _lra in _lillie_my_pkmn:
                # REAL ATTACKERS only (MAIN_ATTACKERS). Counting by
                # ATTACK_ENERGY_REQ alone counted as a "ready attacker" a
                # Chikorita with 1 energy (Growl: 0 damage) or an Applin, and
                # with that the veto fired with a single real attacker
                # (user, registro_004 t4 vs Mega Lucario, LOST: an Ogerpon ex
                # + a freshly benched Chikorita = "2 attackers" -> the
                # Boss's was kept and the refill was lost). It is the same criterion as
                # `has_ready_bench_attacker`.
                if _lra.id not in MAIN_ATTACKERS:
                    continue
                if _can_attack_eff(_lra.id, len(_lra.energies) * _grass_mult()):
                    _lillie_ready_attackers += 1
            if _lillie_ready_attackers >= 2:
                _hop_keep_boss = True
        self.hop_keep_boss = _hop_keep_boss

        # Final branch (hand > 6): the BROAD version of the pending /
        # evolvable lines of the original block (conditions transcribed faithfully;
        # they differ subtly from the pending_evo/evolve_now above).
        _has_pending_evolutions = False
        if (hand_counts.get(Bayleef, 0) >= 1 and
                field_counts.get(Chikorita, 0) >= 1 and
                not meganium_in_play):
            _has_pending_evolutions = True
        if (hand_counts.get(Meganium, 0) >= 1 and
                field_counts.get(Bayleef, 0) >= 1 and
                not meganium_in_play):
            _has_pending_evolutions = True
        if (hand_counts.get(Dipplin, 0) >= 1 and
                field_counts.get(Applin, 0) >= 1 and
                not has_hydrapple):
            _has_pending_evolutions = True
        if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                field_counts.get(Dipplin, 0) >= 1 and
                not has_hydrapple):
            _has_pending_evolutions = True
        if (hand_counts.get(Meganium, 0) >= 1 and
                field_counts.get(Chikorita, 0) >= 1 and
                forest_in_play and not meganium_in_play and
                hand_counts.get(Bayleef, 0) >= 1):
            _has_pending_evolutions = True
        if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                field_counts.get(Applin, 0) >= 1 and
                forest_in_play and not has_hydrapple and
                hand_counts.get(Dipplin, 0) >= 1):
            _has_pending_evolutions = True
        self.pending_evo_amplia = _has_pending_evolutions

        # It does NOT use `_evolvable_counts`: MEASURED AND REVERTED (scope note there).
        _evolvable_now = _field_at_turn_start if (not forest_in_play and _field_at_turn_start) else field_counts
        _can_evolve_now = False
        if (hand_counts.get(Bayleef, 0) >= 1 and
                _evolvable_now.get(Chikorita, 0) >= 1 and
                not meganium_in_play):
            _can_evolve_now = True
        if (hand_counts.get(Meganium, 0) >= 1 and
                _evolvable_now.get(Bayleef, 0) >= 1 and
                not meganium_in_play):
            _can_evolve_now = True
        if (hand_counts.get(Dipplin, 0) >= 1 and
                _evolvable_now.get(Applin, 0) >= 1 and
                not has_hydrapple):
            _can_evolve_now = True
        if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                _evolvable_now.get(Dipplin, 0) >= 1 and
                not has_hydrapple):
            _can_evolve_now = True
        if forest_in_play:
            if (hand_counts.get(Meganium, 0) >= 1 and
                    field_counts.get(Chikorita, 0) >= 1 and
                    not meganium_in_play and
                    hand_counts.get(Bayleef, 0) >= 1):
                _can_evolve_now = True
            if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                    field_counts.get(Applin, 0) >= 1 and
                    not has_hydrapple and
                    hand_counts.get(Dipplin, 0) >= 1):
                _can_evolve_now = True
        self.evolve_now_amplia = _can_evolve_now

    def __getattr__(self, name):
        return getattr(self.c, name)


_RULES_LILLIE_PLAY = [
    # Strategy vs Comfey (user, registro_005): Lillie's Determination is ONLY
    # played if we have 10 or MORE cards in hand. It shuffles the hand into the deck,
    # which RETURNS cards to the deck (it avoids decking ourselves out through Flower
    # Shower and dodges the Xerosic's Machinations discard). With fewer than 10
    # cards it is NOT played. With >=10 it falls through to the normal scoring (positive).
    _FixedRule("comfey_short_hand",
               lambda c: c.op_is_comfey_deck and c.hand_len < 10,
               lambda c: SCORE_VETO),
    # Keeping the Boss's vs Hops / a threat pre-evolution (comment in _CtxLillie).
    _FixedRule("hop_keeps_the_boss",
               lambda c: c.hop_keep_boss,
               lambda c: SCORE_VETO),
    _FixedRule("big_hand_turns_1_2",
               lambda c: (not c.op_is_comfey_deck
                          and c.state.turn <= 2 and c.hand_len >= 10
                          and not c.our_first_turn),
               lambda c: SCORE_VETO),
    # DECK-OUT BRAKE (crustle_kangaskhan autopsy jul 2026): in long games
    # vs wall+healing the draw engine burns 8-15 cards per turn and
    # there were REAL deck-outs (deck at 0 on t20-22). Lillie's shuffles the hand into
    # the deck and draws 6: its deck delta is (hand - 6). With a CRITICAL deck
    # (<=10) it is vetoed only in the band where it is also a luxury refill:
    # hand 4-6 (net negative/zero and there are still plays). With a hand of <=3 (a real
    # jam) it is still the way out; with a hand of >=7 it RETURNS cards to the deck
    # (anti-deck-out) and passes as well. Vs Comfey its own rule governs.
    _FixedRule("deckout_brake_critical_deck",
               lambda c: (not c.op_is_comfey_deck
                          and getattr(c.my_state, 'deckCount', 60) <= 10
                          and 4 <= c.hand_len < 7),
               lambda c: SCORE_VETO),
    # The third of the twins: never fires, kept on purpose. See the note on
    # `_RULES_BOSS_PLAY[0]` -- the engine enforces one Supporter per turn.
    _FixedRule("supporter_already_played",
               lambda c: c.state.supporterPlayed,
               lambda c: SCORE_VETO),
    # EXCEPTION (user): with an Unfair Stamp in hand we normally prefer
    # playing the Stamp (draw 5 + disruption) over Lillie's; BUT if the opponent
    # has 3 or fewer cards in hand the disruption contributes little and Lillie's is
    # preferred, so this veto only applies with an opposing hand > 3.
    _FixedRule("yields_to_unfair_stamp",
               lambda c: (_stamp_pendiente(c)
                          and c.op_hand_count > 3),
               lambda c: SCORE_VETO),
    # Guard (anti-Alakazam suggestion 3): Lillie's would SHUFFLE AWAY the Xerosic we
    # have in hand and there is NO longer any way to re-search for it (no Meowth in hand
    # or in the deck, or with both Meowth already in play and their Last-Ditch spent).
    # With the opposing hand >= 4 and growing, losing the only access to the Powerful
    # Hand cap right before its peak is unrecoverable. With an opposing hand
    # >= 6 the ladder already guarantees Xerosic (6000+) > Lillie's (5800); this
    # veto covers the 4-5 gap. If the Xerosic is still re-searchable, Lillie's
    # carries on normally (a previous design decision: Meowth re-searches for it).
    # With the 2nd copy in the deck (July 2026) the veto does not apply either:
    # shuffling the one in hand does not lose the access (there are drawable copies left).
    # The condition lives in `_xr_last_copy_locked_in_hand` (disruption.py):
    # Xerosic's `first_turn_yields_to_lillie` reads the SAME predicate so it does
    # not step aside for a Lillie's that this veto is about to silence.
    _FixedRule("do_not_shuffle_the_last_xerosic",
               _xr_last_copy_locked_in_hand,
               lambda c: SCORE_VETO),
    _FixedRule("alakazam_stamp_two_ex_ready",
               lambda c: (c.op_is_alakazam_deck and
                          c.hand_counts.get(Unfair_Stamp, 0) >= 1 and
                          _stamp_worth_playing_ctx(c) and
                          c.ready_ex_attackers >= 2 and
                          c.op_hand_count > 3),
               lambda c: SCORE_VETO),
    # vs Alakazam with a large opposing hand (Powerful Hand): if we can ASSEMBLE the
    # Xerosic cap THIS turn -- Ultra Ball -> Meowth ex -> Last-Ditch searches for
    # Xerosic -> play Xerosic -- and we already have a READY attacker, do NOT spend
    # the turn's Supporter on Lillie's (a redundant refill that also shuffles away the
    # Ultra Ball and the Boss's). Save it for Xerosic, which caps the damage of
    # Powerful Hand (20 x card in their hand). The ready-attacker guard
    # (a charged Hydrapple ex or a ready benched ex) avoids sacrificing the refill
    # when the board is poor and digging is really needed. It goes AFTER
    # `do_not_shuffle_the_last_xerosic` (Xerosic already in hand) and BEFORE
    # `charged_hydra_over_boss` (5800), which was what played Lillie's here.
    # See `_alakazam_dig_xerosic_engine`.
    _FixedRule("alakazam_reserves_supporter_for_xerosic",
               lambda c: (_alakazam_dig_xerosic_engine(c)
                          and (c.hydra_active_charged
                               or c.ready_ex_attackers >= 1)),
               lambda c: SCORE_VETO),
    # Rule (user, log 86025936 step 11): on OUR first turn Lillie's Determination is
    # ALWAYS played if it is in hand, above Boss's
    # Orders. The hand >= 10 veto and the Boss's priority veto are
    # ignored. The play-order layer keeps Lillie's (tier 0, score
    # 5000) AFTER the higher-scoring development/items, so the
    # hand is shuffled at the end of the turn.
    _FixedRule("first_turn_always",
               lambda c: c.our_first_turn,
               lambda c: 5000),
    # THE DECK IS A CLOCK AND IT HAS RUN OUT (user, episode 90321662 step 132 vs
    # Crustle / Great Tusk, LOST). Turn 30: an active Tapu Bulu at 4 energies
    # ready to knock out their Great Tusk, FOUR prizes still to take -- and TWO
    # cards left in our deck. Taking the prize needs at least four more turns of
    # ours and the deck pays for two: the game was already lost on time, and the
    # agent attacked. It attacked again on turn 32 and on turn 34, and lost by
    # deck-out with two prizes still on the table.
    #
    # In hand, unplayed, was this Lillie's Determination and ten cards. It
    # shuffles nine of them back and draws six: the deck goes 2 -> 5, which is
    # the three turns the win was missing. And it costs NOTHING -- a Supporter
    # does not end the turn, so the Tapu still attacks afterwards.
    #
    # What silenced it was `line_pending` further down ("evolve first, then
    # refill"), a veto about VALUE that assumes there is a later turn to refill
    # in. When `_deck_clock_runs_out` there may not be one, so this rule sits
    # above every ordering and value veto that merely POSTPONES the refill, and
    # below the hard ones that make it illegal or duplicated (a spent Supporter,
    # a pending Stamp -- which shuffles the hand back too and nets even more --,
    # the Xerosic guards).
    #
    # `_refill_deck_delta > 0` is what keeps it honest: with a short hand
    # Lillie's BURNS deck, and firing there would bring the end closer instead of
    # pushing it away. It is the same arithmetic the deck-out brake above already
    # uses, read from the other side.
    #
    # Deliberately NOT paired with a brake on the cards the engine burns (Teal
    # Dance, Ultra Ball, Bug Catching Set) when the clock is short: that was
    # built and measured in the July 2026 crustle autopsy and it converted
    # deck-out losses into prize losses one for one, -0.9 points at n=1000. The
    # deck-out there was a symptom. Here it is the whole cause: the board was
    # winning and the clock was not.
    _FixedRule("the_deck_clock_runs_out",
               _lillie_beats_the_deck_clock,
               lambda c: LILLIE_SCORE_DECK_CLOCK + c.supporter_boost),
    # FINISHER FISHING (user, registro_004 step 49 vs Marnie, LOST): the turn
    # has NO attack possible -- an active Teal Mask Ogerpon ex with 1 of the
    # 3 energies of Myriad, an uncharged bench and ZERO Grass in hand -- but
    # Lillie's draw (EIGHT cards with all 6 prizes untouched) can bring the
    # 2 that are missing: 10 live Grass in 42 cards = 63%. With them Myriad hits
    # 360 on the Marnie's Grimmsnarl ex (Grass weakness) and takes TWO prizes.
    # Here the refill is NOT "digging just in case": it is the only line that attacks
    # this turn, so it OVERRIDES the ordering vetoes further down (the Ultra Ball
    # that completes a line, the yield to an executable gust). It goes AFTER all
    # the hard vetoes above (Supporter spent, a pending Stamp, the deck-out brake,
    # the Xerosic guards): those still rule.
    #
    # The gust it yields to is also ACTIVELY bad here: Myriad Leaf
    # Shower scales with the energy on BOTH actives, so swapping a
    # Grimmsnarl ex with 2 energies and a Grass weakness for a bare Snorunt
    # DEGRADES the finisher on the very turn it is being fished for.
    _FixedRule("fish_energy_for_the_finisher",
               _finisher_fishing_valid,
               lambda c: LILLIE_SCORE_FISHING + c.supporter_boost),
    # Lillie's > Boss's priority with a charged Hydrapple ex in the active spot.
    # It scores ABOVE the maximum Boss's that does not win the game (~5600);
    # `_boss_win_via_bench` (a lethal gust to the bench) is exempted so as not
    # to lose a finisher. EXCEPTION (user, log 86343257 step 99, LOST vs
    # Hop): if the opposing active is IMMUNE by dodging (Splashing Dodge on
    # heads -> `_boss_dodge_redirect`) the active canNOT be attacked this
    # turn, so boosting Syrup Storm with Lillie's is useless; priority is yielded
    # to Boss's Orders (5500) to gust and knock out a bench target.
    _FixedRule("charged_hydra_over_boss",
               lambda c: (c.hydra_active_charged and not c.pending_evo
                          and not c.boss_win_via_bench
                          and not (c.boss_dodge_redirect
                                   and c.hand_counts.get(Boss_Orders, 0) >= 1)),
               lambda c: 5800 + c.supporter_boost),
    # Do not veto Lillie's when the `_boss_prize_rank` gust is NOT
    # executable this turn (the active cannot attack and there is no ready benched
    # attacker). The executable finishers (win_via_bench / dodge) do still
    # veto Lillie's. ALSO (user, registro_005 vs Dragapult): a DEVELOPMENT
    # gust (prize_rank, cutting the opposing line) does NOT veto Lillie's if
    # besides the active we do NOT have a REAL ready benched attacker
    # (`has_ready_bench_attacker`, which never counts an Applin); without a second
    # attacker it is better to DIG with Lillie's. The THREAT pre-evolution is
    # exempted (`boss_ko_threat_preevo`, e.g. Duraludon), which still has
    # gust priority.
    _FixedRule("yields_to_executable_boss",
               lambda c: (not c.boss_low_value_gust and
                          c.hand_counts.get(Boss_Orders, 0) >= 1 and
                          ((c.boss_prize_rank >= 1
                            and not c.active_cant_attack
                            and (c.has_ready_bench_attacker
                                 or (c.boss_ko_threat_preevo
                                     # a DOOMED active with no relief: the prize
                                     # KO does not veto the refill (esp. the
                                     # symmetry with _boss_yields_to_dig).
                                     #
                                     # A KNOWN, MEASURED AND KEPT ASYMMETRY
                                     # (user, registro_006 step 78 vs Archaludon
                                     # ex): `_boss_yields_to_dig` consults
                                     # `active_ko_likely OR active_doomed_real`
                                     # -- the second was added because the
                                     # first is BLIND (`_op_best_damage_vs`
                                     # always returns 0) -- and this rule looks
                                     # ONLY at `active_ko_likely`. In the exact
                                     # window (no ready benched attacker, a
                                     # gustable THREAT pre-evolution, an active
                                     # doomed only according to attack_table) the two
                                     # rules yield the turn to each other
                                     # -- Lillie's at -1 for "Boss's is
                                     # executable" and Boss's at 20 for "it yields to
                                     # Lillie's" -- and the Supporter slot is
                                     # lost entirely.
                                     #
                                     # Closing the asymmetry (adding
                                     # `or c.active_doomed_real` here) WAS MEASURED:
                                     # -0.39 points with n=7000 per branch across 4
                                     # matchups (archaludon -0.5, crustle -0.7,
                                     # alakazam -0.5, dragapult +0.3; p=0.40).
                                     # Probable mechanism of the sign: Lillie's
                                     # SHUFFLES the hand into the deck, so on
                                     # step 78 it traded a live Boss's Orders (and
                                     # the Bayleef of the Meganium line) for 8
                                     # random cards with the active dying
                                     # anyway. It is reverted and documented; the
                                     # lost turn is now rescued by the deferrable
                                     # ORDERING veto of Flip the Script, which
                                     # with no playable blocker cashes in the
                                     # 3-card draw instead of closing by attacking.
                                     and not c.active_ko_likely)))
                           or c.boss_win_via_bench or c.boss_dodge_redirect)),
               lambda c: SCORE_VETO),
    _FixedRule("ogerpon_playable_first",
               lambda c: (c.hand_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1 and
                          c.hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                          c.bench_count < 5),
               lambda c: 4500),
    # The Ultra Ball completes the evolution line before refilling (user,
    # registro_004 step 47 vs Alakazam, LOST): with the basic in play + the
    # Stage 2 in hand but the intermediate Stage 1 searchable in the deck
    # (`ub_gapped_line`), Lillie's is NOT played -- it would shuffle away the Stage 2
    # and the Ultra Ball. The hand is kept so the Ultra Ball can be played (bringing
    # a Bayleef / Dipplin) and the line assembled; once the intermediate piece is in
    # play, the `line_pending` veto (a direct evolution) takes over. Gate hand_len
    # > 4 (with a minimal hand the value of drawing 6-8 wins) and turn > 2.
    _FixedRule("ultra_ball_completes_the_line",
               lambda c: (c.ub_gapped_line and c.state.turn > 2
                          and c.hand_len > 4),
               lambda c: SCORE_VETO),
    # We have in hand the evolution (Bayleef/Meganium/Dipplin/Hydrapple ex) of
    # a Pokemon that is already in play. Those evolutions are completed first
    # (they score ~31000-35000) and the items are played; Lillie's
    # Determination is postponed until there is nothing left to evolve.
    # If the pre-evolution is in the active spot and cannot be evolved yet
    # this turn (it is deferred until it is benched), it is kept anyway so as
    # NOT to discard the pieces when shuffling the hand. It fixes the case where
    # Lillie's was played with a Bayleef+Meganium in hand and the line was lost.
    # EXCEPTION 1: with 4 or fewer cards in hand in total, the value of drawing
    # (Lillie's draws 6-8) beats keeping the line, so it is NOT vetoed
    # and Lillie's is played.
    # EXCEPTION 2: if we canNOT evolve the line THIS turn
    # (`_lillie_evolve_now` False, e.g. a Bayleef just evolved without
    # Forest) AND we are going to ATTACK this turn, it is NOT vetoed: attacking would
    # leave the Lillie's stranded in hand; better to play it now (draw 6-8) before
    # the attack. "Attacking this turn" covers both the current active
    # (`can_attack`) and knocking out the opposing active by RETREATING and promoting
    # a ready benched attacker (`_bdg_retreat_ko`). The line is only kept
    # if we really can evolve it already (evolve first) or if we are NOT
    # going to close the turn by attacking (it is saved for the next turn).
    # (user, log 86345042 step 44, vs Mega Lucario, WON): with a Hydrapple ex
    # in hand + a Dipplin on the bench and a benched attacker that already knocks out
    # the active Riolu (retreat+promote), the game played Boss's Orders in a
    # gust with no prize instead of refilling; now `_bdg_retreat_ko`
    # unlocks Lillie's to look for more resources (e.g. the Stadium) before
    # attacking.
    # EXCEPTION 3 (user, registro 003 step 36 vs Archaludon ex, WON): if
    # we canNOT evolve the line THIS turn (`_lillie_evolve_now` False)
    # we have entered this branch through the `not (can_attack or
    # _bdg_retreat_ko)` disjunct, that is, the turn would be DEAD (we do not evolve,
    # we do not attack, we do not retreat-to-knock-out). In that case keeping some
    # pieces we will not put down today anyway is worse than refilling: Lillie's
    # draws 6 (or 8 with 6 prizes) and opens new energy/attacker options.
    # The veto (keeping the line) is only kept when we CAN
    # evolve already (`_lillie_evolve_now`): there we evolve first and
    # defer Lillie's so as not to shuffle the remaining pieces away.
    _FixedRule("line_pending",
               lambda c: (c.pending_evo and c.state.turn > 2
                          and c.hand_len > 4
                          and (c.evolve_now
                               or not (c.can_attack or c.bdg_retreat_ko))),
               lambda c: 5000 if not c.evolve_now else SCORE_VETO),
    _FixedRule("refresh_short_hand",
               lambda c: c.hand_len <= 6,
               lambda c: 5000),
    # The original's final branch (hand > 6): score 5000 unless there are pending
    # pieces with NO outlet this turn. Transcribed faithfully even though its veto
    # requires `hand_len < 7` and this branch is only reached with a hand > 6: it is
    # unreachable (a dead sub-branch of the original, kept for fidelity).
    _FixedRule("keep_pieces_with_no_way_out",
               lambda c: (c.pending_evo_amplia
                          and not c.evolve_now_amplia
                          and c.state.turn > 2
                          and not (c.hand_counts.get(Lanas_Aid, 0) >= 1
                                   and not c.state.supporterPlayed)
                          and c.hand_len < 7),
               lambda c: SCORE_VETO),
    _FixedRule("generic_refresh",
               lambda c: True,
               lambda c: 5000),
]


def _score_lillie_determination_play(ctx: DecisionContext) -> int:
    """Scores playing Lillie's Determination (shuffle the hand and draw 6/8).
    Body migrated to the RULES ENGINE (phase 4): the derived values live in
    _CtxLillie and the rules (with their strategic comments) in
    _RULES_LILLIE_PLAY; PTCG_DEBUG prints the trace."""
    return _resolve_with_trace("lillie->play", _RULES_LILLIE_PLAY, [],
                               _CtxLillie(ctx), default=0)


# Lillie's vetoes that say "first X, THEN the refill" -- an ORDER, not a value.
# They are only true while X can really be played in this menu, so they go
# through `_order_veto` instead of killing the Supporter on the spot.
_LILLIE_ORDER_VETOES = {"ultra_ball_completes_the_line": (Ultra_Ball,)}


def _best_other_supporter_val(ctx: DecisionContext) -> int:
    """Best PLAY score among the Supporters in HAND other than Lillie's.

    It answers, on the scale that really resolves the slot (`_supp_play_score`),
    the question "if Lillie's stays vetoed, WHO takes the turn's Supporter?".
    0 when nobody would take it. The same reading
    `_supp_in_hand_takes_the_turn` and `_meowth_fetch_loses_the_turn` already
    do; written once here so the third caller cannot disagree with them."""
    _bos_best = 0
    for _bos_sid in _SUPP_PLAY_IDS:
        if _bos_sid == Lillie_Determination:
            continue
        if ctx.hand_counts.get(_bos_sid, 0) < 1:
            continue
        _bos_best = max(_bos_best, _supp_play_score(ctx, _bos_sid))
    return _bos_best


def _lillie_play_order_veto(ctx: DecisionContext,
                            blocker_offered_in_menu: bool = False):
    """(real score, blockers) when what vetoed Lillie's is a DEFERRABLE ORDER
    veto, else None.

    `ultra_ball_completes_the_line` says: do not refill yet, the Ultra Ball has
    to bring the missing intermediate piece of the line first, and Lillie's
    would shuffle both the Stage 2 and the Ultra Ball into the deck. That is an
    ORDER, and it holds only while the Ultra Ball is really playable. Under ITEM
    LOCK it is not: the opponent's Budew or a Jellicent turns the veto into a
    dead loss -- the Ultra Ball cannot be played this turn, so there is no
    "afterwards", and the turn's Supporter dies in hand for an order that will
    never come. Measured over 200 games against `jellicent_lock.csv`: the rule
    fired 124 times, in ALL 124 with no Ultra Ball offered in the menu, and 26
    of those turns closed with the Supporter slot unused.

    The revoking is not done here -- this only publishes the score the chain
    would give WITHOUT the ordering rule, plus which card is being waited for.
    The "REVOKE ORDERING VETOES" block reads the real menu and lifts it when no
    blocker is offered and playable, or when the turn closes on this very
    action. Same mechanism, and for the same reason, as the ability vetoes of
    registro_006 step 78.

    A VALUE veto is never registered: the rest of the chain (keeping an
    evolution line we CAN evolve today, the deck-out brake, yielding to an
    executable gust) is about what Lillie's would cost, not about when.

    And ONLY when no OTHER Supporter in hand is really the Supporter of the
    turn. The bound itself is not new -- it is the one the `ub_gapped_line`
    mutual-block breaker already decided for this rule -- but it used to be read
    by COUNTING cards ("is there another Supporter in hand?") when the agent
    holds a far finer reading of the same question: `_supp_play_score`, the
    scale that actually resolves the slot. Its premise was "with ANOTHER
    Supporter in hand the turn's slot gets used anyway, so keeping Lillie's
    vetoed costs nothing", and that premise is FALSE for exactly one band of
    Supporters -- `SUPP_SCORE_LAST_RESORT_BAND`, the height at which every
    Supporter scorer says "I have no useful effect today: play me only because
    nothing else scores". A Supporter down there does not USE the slot, it
    WASTES it, and the order "first the Ultra Ball, THEN the refill" turns into
    "the gust eats my slot and the refill never comes".

    Measured case (user, registro_004 step 39 vs Marnie, episode 91861054,
    LOST). Turn 4, our Tapu Bulu active with ZERO energy -- it cannot attack --
    and a hand of {Boss's Orders, Hydrapple ex, Meowth ex, Ultra Ball, Meganium,
    Lillie's Determination}. Four cards blocked each other in a circle:

      Lillie's       -1  `ultra_ball_completes_the_line` -- "the Ultra Ball first"
      Ultra Ball     -1  `_ub_cancel_meowth` -- "the Meowth ex first" (and that
                         veto is itself gated on `not supporterPlayed`)
      Meowth ex      -1
      Boss's Orders  20  `empty_gust_yields_to_lillie` -- its OWN scorer saying
                         "the active cannot attack, this gust is empty, Lillie's
                         should take the slot"

    ...so the only positive card was the one that had just declared it did not
    want the slot, and Boss's Orders won by default and spent it. The gust took
    no prize; the Ultra Ball became playable one action later precisely BECAUSE
    the Supporter was gone, and the turn closed with Lillie's still in hand.
    Boss's yield was a promise the score could not keep: 20 still beats -1.

    This is deck-agnostic on purpose. It names no matchup and no gust: it asks
    the real scorers who takes the slot, and only refuses to defer to a Supporter
    that is genuinely taking it."""
    _lov_other = _best_other_supporter_val(ctx)
    if _lov_other > SUPP_SCORE_LAST_RESORT_BAND:
        return None
    # With the blocker OFFERED in the menu the order stands as it always has,
    # even at -1: its cost vetoes are about this instant and lift themselves
    # within the turn (registro_004 step 47: the Meowth ex goes down first and
    # the Ultra Ball is playable straight after). The single exception is the
    # circle above -- a last-resort Supporter waiting to eat the slot -- where
    # "afterwards" is exactly what does not arrive.
    if blocker_offered_in_menu and _lov_other <= 0:
        return None
    _lov_c = _CtxLillie(ctx)
    for _lov_r in _RULES_LILLIE_PLAY:
        if not _lov_r.when(_lov_c):
            continue
        _lov_blockers = _LILLIE_ORDER_VETOES.get(_lov_r.name)
        if _lov_blockers is None:
            return None
        _lov_rest = [_x for _x in _RULES_LILLIE_PLAY if _x.name != _lov_r.name]
        _lov_score, _ = _resolve_rules(_lov_rest, [], _lov_c, 0)
        return (_lov_score, _lov_blockers) if _lov_score > 0 else None
    return None











def _supp_play_score(ctx: DecisionContext, sid: int) -> int:
    """REAL score of PLAYING the Supporter `sid` with the board of `ctx`."""
    if sid == Boss_Orders:
        return _score_boss_orders_play(ctx)
    if sid == Xerosic_Machinations:
        return _score_xerosic_play(ctx)
    if sid == Lillie_Determination:
        return _score_lillie_determination_play(ctx)
    if sid == Dawn:
        return _score_dawn_play(ctx)
    if sid == Lanas_Aid:
        return _score_lanas_aid_play(ctx, 0)
    return 0


def _best_supporter_in_hand(ctx: DecisionContext, hand_counts=None):
    """(id, score) of the Supporter in HAND that would take the turn.

    `hand_counts` allows evaluating a HYPOTHETICAL hand (e.g. the one after
    resolving a search) without touching the turn's ctx. It returns (None, 0) if
    no Supporter in hand is playable."""
    _hc = ctx.hand_counts if hand_counts is None else hand_counts
    best_id, best = None, 0
    for _sid in _SUPP_PLAY_IDS:
        if _hc.get(_sid, 0) < 1:
            continue
        _val = _supp_play_score(ctx, _sid)
        if _val > best:
            best_id, best = _sid, _val
    return best_id, best


def _supp_in_hand_takes_the_turn(ctx: DecisionContext) -> bool:
    """True when the Supporter ALREADY IN HAND wins the turn's only Supporter
    slot against ANYTHING the Last-Ditch Catch could bring up from the deck.

    It is the same question `_meowth_fetch_loses_the_turn` asks, moved one step
    earlier in the chain: there the Meowth ex is already in hand and the fetch
    target is known, so the veto only has to stop a body going down; here the
    Meowth ex is still in the DECK and what is about to be paid is the whole
    Ultra Ball -- two cards off the hand -- to dig out a searcher whose only
    product, a Supporter, cannot be played today because the slot is already
    taken. That gap was the documented one (user, registro_004 step 36 vs
    Alakazam, episode 90106609, LOST): with a ready Ogerpon ex active, a second
    one one energy short on the bench and XEROSIC'S MACHINATIONS in hand against
    a 10-card Alakazam hand, the agent played the Ultra Ball, paid it with Tapu
    Bulu and the Night Stretcher, put a 2-prize Meowth ex on the bench, fetched
    Lillie's Determination -- and Lillie's, committed by the fetch, took the
    turn's Supporter and SHUFFLED the Xerosic back into the deck. The opponent
    kept its ten cards and Powerful Hand (20 per card) answered for 200+.

    Both sides are measured on the PLAY scale (`_supp_play_score`), which is the
    one that really resolves the slot: the fetch scale orders the same pair the
    other way round (it scored Lillie's 1200 over Xerosic <=150 while the play
    scorer scores Xerosic over Lillie's). The deck side is scored over the
    HYPOTHETICAL hand the card would arrive into, and it has to beat the hand
    STRICTLY: a tie is not worth the Ultra Ball plus a 2-prize body.

    Deck-agnostic on purpose -- it names no card, it only asks the real scorers
    which Supporter wins the slot. See
    [[supporter-del-turno-ya-en-mano-no-meowth]]."""
    if ctx.state.supporterPlayed:
        return False
    # OUR first turn is exempt, like `_meowth_fetch_loses_the_turn`: the
    # anti-donk line puts a body down even with the Supporter already in hand.
    if ctx.our_first_turn:
        return False
    _hand_id, _hand_val = _best_supporter_in_hand(ctx)
    # `SUPP_SCORE_LAST_RESORT_BAND` is the height at which every Supporter
    # scorer says "play me only because nothing else scores": a Supporter down
    # there is not "the Supporter of the turn" and cannot be a reason to give up
    # a refill from the deck. Same cut-off as `_meowth_fetch_loses_the_turn`.
    if _hand_id is None or _hand_val <= SUPP_SCORE_LAST_RESORT_BAND:
        return False
    for _sid in _SUPP_PLAY_IDS:
        if ctx.cards_in_deck.get(_sid, {}).get(ZONE_DECK, 0) < 1:
            continue
        # a defaultdict, not a dict: the scorers index it by brackets.
        _hand_post = defaultdict(int, ctx.hand_counts)
        _hand_post[_sid] = _hand_post.get(_sid, 0) + 1
        if _supp_play_score(_dc_replace(ctx, hand_counts=_hand_post),
                            _sid) > _hand_val:
            return False
    return True


# --- Rules of the Ultra Ball -> Hydrapple ex fetch --------------------------






# --- Rules of the Ultra Ball -> Meowth ex fetch -----------------------------







# --- Rules of the Ultra Ball fetch: remaining branches ----------------------
# A ctx SHARED by the Ogerpon/Meganium/Bayleef/Dipplin/Chikorita/
# Applin/Tapu/Pinsir/Fezandipiti branches. The per-turn globals (meganium_in_play,
# forest_in_play, op_is_crustle_deck, op_is_cornerstone_deck, ko_last_turn,
# ACTIVE_CARDS_IN_DECK) are read on the fly from the lambdas (agent() declares
# them `global`).


















# --- Rules of the Night Stretcher recovery ---------------------------------
# A single ctx for the 12 branches. `evolvable_ns` replicates the start-of-turn
# snapshot of the original block (_field_at_turn_start if there is no Forest). The
# cross-cutting post-adjustments (the bonus for exhausted/prized copies and the
# whitelist veto vs Crustle/Cornerstone) stay inline: they apply to all
# cards equally.




def _no_attacker_for_tomorrow(my_state, hand_counts, field_counts) -> bool:
    """True if NO body of ours will get to attack NEXT turn.

    It looks one turn FURTHER than `_no_attack_today`: for the bodies ALREADY in
    play it counts next turn's attachment (one more Grass, in EFFECTIVE units)
    and the evolutions the hand can complete on a pre-evolution on the board (the
    evolution inherits the body's energy). It does not count the Basics
    in hand: a freshly played Tapu Bulu needs 4 energies, not one.

    Only the `MAIN_ATTACKERS` count -- a Chikorita that hits for 10 is not
    "starting to attack", and confusing them is exactly what lost the turn of
    registro_002 step 17 vs Dragapult.

    CONSERVATIVE by design: when in doubt it returns False ("we do have an
    attacker"), because whoever consults it uses it to justify spending resources."""
    unit = _grass_attach_unit()
    for _body in ((my_state.active or []) + (my_state.bench or [])):
        if _body is None or _body.id not in MAIN_ATTACKERS:
            continue
        if _can_attack_eff(_body.id, len(_body.energies) + unit):
            return False
    for _pre, _evo in ((Applin, Dipplin), (Dipplin, Hydrapple_ex),
                       (Chikorita, Bayleef), (Bayleef, Meganium)):
        if (hand_counts.get(_evo, 0) >= 1
                and field_counts.get(_pre, 0) >= 1
                and _evo in MAIN_ATTACKERS):
            return False
    return True






# --- The DRAW engine on a dead turn ----------------------------------------
# (user, registro_008 step 67 vs Alakazam, LOST). With the turn DEAD for
# attacking (`dead_turn`) and the hand dry (`hand_exhausted`), the recovery has
# to bring the body that REBUILDS THE HAND, not development:
#   1st Meowth ex   -> when put down, Last-Ditch Catch searches for a Supporter
#                      from the deck (Lillie's Determination rebuilds the WHOLE hand).
#   2nd Fezandipiti ex -> Flip the Script draws 3, but ONLY if one of our
#                      Pokemon was knocked out on the previous turn; if not, its
#                      ability does not exist and the 2-prize body is a gift.
# In the record a Meganium was recovered (990 through `bayleef_evolvable`) over
# the Meowth ex they had just knocked out: the Meganium had no energy, it did not
# attack, and we were left with 0 cards in hand and no attacker. The scores go
# above ALL development (990 + 200 from the last-copy bonus = 1190)
# and below the energy that produces an attack TODAY (1300/1400), which never
# coexists with `dead_turn`. Deck-agnostic: the dead turn is measured over
# `ATTACK_ENERGY_REQ`, not over a list of matchups.



















# --- Rules of the Bug Catching Set TO_HAND fetch ---------------------------
# Dispatch by TABLE (the same pattern as the Night Stretcher fetch): it reuses
# _CtxNS (hand/field/bench/flags); the per-turn globals (meganium_in_play,
# forest_in_play, ko_last_turn, op_is_crustle_deck, op_is_cornerstone_deck) are
# read on the fly from the lambdas. The bonus for prized copies is kept
# inline at the call site (a cross-cutting post-adjustment).

_RULES_BCS_CHIKORITA = [
    # Starting the Meganium line from scratch; with Forest and the evolution in
    # hand, the evolution rush raises the priority.
    _FixedRule("line_from_scratch_rush",
               lambda c: (not AGENT_STATE.meganium_in_play
                          and c.field.get(Chikorita, 0)
                          + c.field.get(Bayleef, 0)
                          + c.field.get(Meganium, 0) == 0
                          and AGENT_STATE.forest_in_play
                          and (c.hand.get(Bayleef, 0) >= 1
                               or c.hand.get(Meganium, 0) >= 1)),
               lambda c: 950),
    _FixedRule("line_from_scratch",
               lambda c: (not AGENT_STATE.meganium_in_play
                          and c.field.get(Chikorita, 0)
                          + c.field.get(Bayleef, 0)
                          + c.field.get(Meganium, 0) == 0),
               lambda c: 800),
]

_RULES_BCS_BAYLEEF = [
    _FixedRule("immediate_evo_rush",
               lambda c: (not AGENT_STATE.meganium_in_play
                          and c.field.get(Chikorita, 0) >= 1
                          and AGENT_STATE.forest_in_play
                          and c.hand.get(Meganium, 0) >= 1),
               lambda c: 950),
    _FixedRule("immediate_evo",
               lambda c: (not AGENT_STATE.meganium_in_play
                          and c.field.get(Chikorita, 0) >= 1),
               lambda c: 850),
    _FixedRule("chikorita_in_hand",
               lambda c: (not AGENT_STATE.meganium_in_play
                          and c.hand.get(Chikorita, 0) >= 1),
               lambda c: 700),
    _FixedRule("no_line_in_play",
               lambda c: not AGENT_STATE.meganium_in_play,
               lambda c: 400),
]

_RULES_BCS_MEGANIUM = [
    _FixedRule("immediate_evo",
               lambda c: (not AGENT_STATE.meganium_in_play
                          and c.field.get(Bayleef, 0) >= 1),
               lambda c: 1000),
    _FixedRule("rush_from_chikorita",
               lambda c: (not AGENT_STATE.meganium_in_play
                          and c.field.get(Chikorita, 0) >= 1
                          and AGENT_STATE.forest_in_play),
               lambda c: 900),
    _FixedRule("no_line_in_play",
               lambda c: not AGENT_STATE.meganium_in_play,
               lambda c: 500),
]

_RULES_BCS_APPLIN = [
    _FixedRule("line_from_scratch_rush",
               lambda c: (not c.has_hydrapple
                          and c.field.get(Applin, 0)
                          + c.field.get(Dipplin, 0)
                          + c.field.get(Hydrapple_ex, 0) == 0
                          and AGENT_STATE.forest_in_play
                          and (c.hand.get(Dipplin, 0) >= 1
                               or c.hand.get(Hydrapple_ex, 0) >= 1)),
               lambda c: 850),
    _FixedRule("line_from_scratch",
               lambda c: (not c.has_hydrapple
                          and c.field.get(Applin, 0)
                          + c.field.get(Dipplin, 0)
                          + c.field.get(Hydrapple_ex, 0) == 0),
               lambda c: 700),
    _FixedRule("no_hydrapple",
               lambda c: not c.has_hydrapple,
               lambda c: 200),
]

_RULES_BCS_DIPPLIN = [
    _FixedRule("immediate_evo_rush",
               lambda c: (not c.has_hydrapple
                          and c.field.get(Applin, 0) >= 1
                          and AGENT_STATE.forest_in_play
                          and c.hand.get(Hydrapple_ex, 0) >= 1),
               lambda c: 900),
    _FixedRule("immediate_evo",
               lambda c: (not c.has_hydrapple
                          and c.field.get(Applin, 0) >= 1),
               lambda c: 800),
    _FixedRule("applin_in_hand",
               lambda c: (not c.has_hydrapple
                          and c.hand.get(Applin, 0) >= 1),
               lambda c: 650),
    # A non-ex attacker useful against the walls with ex protection.
    _FixedRule("vs_the_anti_ex_wall",
               lambda c: c.op_ex_immune_active or c.op_ex_immune_bench,
               lambda c: 600),
    _FixedRule("no_hydrapple",
               lambda c: not c.has_hydrapple,
               lambda c: 350),
]

_RULES_BCS_HYDRAPPLE = [
    _FixedRule("immediate_evo",
               lambda c: (not c.has_hydrapple
                          and c.field.get(Dipplin, 0) >= 1),
               lambda c: 950),
    _FixedRule("rush_from_applin",
               lambda c: (not c.has_hydrapple
                          and c.field.get(Applin, 0) >= 1
                          and AGENT_STATE.forest_in_play),
               lambda c: 850),
    _FixedRule("no_hydrapple",
               lambda c: not c.has_hydrapple,
               lambda c: 400),
]

_RULES_BCS_OGERPON = [
    # Up to 2 Ogerpon in play; with a short bench, +100 (an early body).
    _FixedRule("fewer_than_two",
               lambda c: c.field.get(Teal_Mask_Ogerpon_ex, 0) < 2,
               lambda c: 700 if c.bench_count <= 2 else 600),
    # A 3rd Ogerpon as a Syrup Storm accelerator (Teal Dance adds Grass).
    _FixedRule("syrup_accelerator",
               lambda c: (c.bench_count < 5 and
                          c.hand.get(Basic_Grass_Energy, 0) >= 1 and
                          c.field.get(Hydrapple_ex, 0) >= 1),
               lambda c: 550),
]

_RULES_BCS_TAPU = [
    # vs Dragapult with the board already built it cannot be PUT DOWN: not searched for.
    _FixedRule("dragapult_does_not_play_it",
               lambda c: c.dragapult_no_tapu,
               lambda c: SCORE_VETO),
    _FixedRule("anti_wall_with_meganium_and_hydra",
               lambda c: (c.field.get(Tapu_Bulu, 0) == 0
                          and AGENT_STATE.meganium_in_play
                          and (c.op_ex_immune_active or c.op_ex_immune_bench)
                          and c.has_hydrapple),
               lambda c: 700),
    _FixedRule("anti_wall_with_meganium",
               lambda c: (c.field.get(Tapu_Bulu, 0) == 0
                          and AGENT_STATE.meganium_in_play
                          and (c.op_ex_immune_active or c.op_ex_immune_bench)),
               lambda c: 600),
    _FixedRule("first_tapu",
               lambda c: c.field.get(Tapu_Bulu, 0) == 0,
               lambda c: 50),
]

_RULES_BCS_PINSIR = [
    _FixedRule("anti_wall",
               lambda c: (c.field.get(Pinsir, 0) == 0 and
                          (AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck)),
               lambda c: 750),
]

_RULES_BCS_MEOWTH = [
    # Supporter engine: only if Last-Ditch is going to pay off (no Watchtower,
    # a free Supporter, a weak hand and a valuable Supporter in the deck).
    _FixedRule("supporter_engine",
               lambda c: (not c.watchtower and
                          c.field.get(Meowth_ex, 0) == 0
                          and not c.supporter_played and
                          c.best_supp_hand_val < 500
                          and c.best_supp_deck_val >= 400),
               lambda c: min(500, c.best_supp_deck_val - 100)),
]

_RULES_BCS_FEZ = [
    _FixedRule("lucario_answers",
               lambda c: (c.op_is_lucario
                          and c.field.get(Fezandipiti_ex, 0) == 0 and
                          (AGENT_STATE.ko_last_turn or c.bench_count == 0)),
               lambda c: 650),
    # vs Mega Lucario, outside the opening/answer it is KEPT (weak to Fighting).
    _FixedRule("lucario_reservation",
               lambda c: c.op_is_lucario,
               lambda c: SCORE_VETO),
    _FixedRule("after_a_ko",
               lambda c: (c.field.get(Fezandipiti_ex, 0) == 0
                          and AGENT_STATE.ko_last_turn),
               lambda c: 650),
]

_RULES_BCS_GRASS = [
    # The Grass that TAKES A PRIZE TODAY comes before any development: put on the
    # ACTIVE it turns an attack that does not knock out -- or that cannot even be
    # paid for -- into a KO. Same rule as `grass_makes_the_active_ko` in
    # _RULES_NS_GRASS (user, registro_008 step 85).
    _FixedRule("grass_makes_the_active_ko",
               lambda c: c.grass_makes_the_active_ko,
               lambda c: 1400),
    _FixedRule("grass_to_spare",
               lambda c: c.hand.get(Basic_Grass_Energy, 0) >= 3,
               lambda c: 150),
    _FixedRule("no_grass_and_no_attachment",
               lambda c: (c.hand.get(Basic_Grass_Energy, 0) == 0
                          and not c.energy_attached),
               lambda c: 650),
    _FixedRule("no_grass",
               lambda c: c.hand.get(Basic_Grass_Energy, 0) == 0,
               lambda c: 550),
    _FixedRule("with_hydrapple",
               lambda c: c.has_hydrapple,
               lambda c: 400),
]

_BCS_FETCH_TABLE = {
    Chikorita: ("bcs->chikorita", _RULES_BCS_CHIKORITA, 50),
    Bayleef: ("bcs->bayleef", _RULES_BCS_BAYLEEF, 30),
    Meganium: ("bcs->meganium", _RULES_BCS_MEGANIUM, 20),
    Applin: ("bcs->applin", _RULES_BCS_APPLIN, 40),
    Dipplin: ("bcs->dipplin", _RULES_BCS_DIPPLIN, 30),
    Hydrapple_ex: ("bcs->hydrapple", _RULES_BCS_HYDRAPPLE, 25),
    Teal_Mask_Ogerpon_ex: ("bcs->ogerpon", _RULES_BCS_OGERPON, 20),
    Tapu_Bulu: ("bcs->tapu", _RULES_BCS_TAPU, 20),
    Pinsir: ("bcs->pinsir", _RULES_BCS_PINSIR, 20),
    Meowth_ex: ("bcs->meowth", _RULES_BCS_MEOWTH, 15),
    Fezandipiti_ex: ("bcs->fez", _RULES_BCS_FEZ, 10),
    Basic_Grass_Energy: ("bcs->grass", _RULES_BCS_GRASS, 350),
}

# --- Rules of the Poke Pad TO_HAND fetch -----------------------------------
# Poke Pad searches for a NON Rule-Box Pokemon (a basic or an evolution) into HAND.
# Three modes from the original block, flattened into a single chain (the first
# rule that applies wins, like the nested if/elif): (1) FIRST TURN: secure
# the basics of both lines; (2) DIRECT EVO (`has_evo`): bring the
# NEXT evolution of a Pokemon that is ALREADY on the CURRENT board --
# deliberately NOT the start-of-turn snapshot (_field_at_turn_start): that
# snapshot ignores a freshly evolved Bayleef and would make us search for a
# redundant 2nd Bayleef instead of the Meganium that DOES complete the line;
# (3) FALLBACK: complete lines from hand even if the pre-evolution is not in play.




# --- Rules of the Meowth ex Supporter fetch (Last-Ditch Catch) --------------
# It only scores Supporters (_MEOWTH_FETCH_SUPPS); the other candidates
# keep the base 50 from the call site. The two adjustments of the original else
# (the Boss's bonus vs Crustle, the Dawn cap without Forest) live in the value of
# the catch-all (_v_meowth_fetch_value), faithful to the sequential reassignment.








def _meowth_fetch_prediction(hand_counts, supp_values, hand_size,
                             strong_attacker, op_hand_count,
                             active_cant_attack, win_via_boss, gust2_via_boss,
                             deny_evo_via_boss, devel_lillie, alakazam,
                             cards_in_deck, first_turn=False,
                             gust_over_immune_active=False,
                             recovery_ko=False):
    """(id, value) of the Supporter Last-Ditch Catch would bring RIGHT NOW.

    It reproduces the REAL fetch (`_RULES_MEOWTH_FETCH`, the same board) over
    the Supporters still in the DECK, so it can be decided BEFORE spending the
    Meowth ex whether the search contributes anything. `hand_size` must be the one
    AFTER putting the Meowth down (one card fewer), which is when the fetch is
    resolved. It returns (None, 0) if no Supporter is left in the deck.
    """
    best_id, best_val = None, 0
    _lillie_alcanzable = (cards_in_deck.get(
        Lillie_Determination, {}).get(ZONE_DECK, 0) > 0)
    # The price of the turn's Supporter slot, on the fetch's own scale: what the
    # hand ALREADY holds. See `the_slot_is_taken_so_bring_what_survives`.
    _hand_supp_val = max(
        (supp_values.get(_hsv_id, 0) for _hsv_id in _MEOWTH_FETCH_SUPPS
         if hand_counts.get(_hsv_id, 0) >= 1), default=0)
    for _sid in _MEOWTH_FETCH_SUPPS:
        if cards_in_deck.get(_sid, {}).get(ZONE_DECK, 0) <= 0:
            continue
        _ctx = _CtxMeowthFetch(
            _sid, supp_values.get(_sid, 0), hand_counts, supp_values,
            hand_size, strong_attacker, op_hand_count, active_cant_attack,
            win_via_boss, gust2_via_boss, deny_evo_via_boss, devel_lillie,
            alakazam, first_turn, _lillie_alcanzable,
            gust_over_immune_active, recovery_ko, _hand_supp_val)
        _val, _ = _resolve_rules(_RULES_MEOWTH_FETCH, [], _ctx, 50)
        if _val > best_val:
            best_id, best_val = _sid, _val
    return best_id, best_val


# --- Rules of the Dawn TO_HAND fetch ---------------------------------------
# Dawn searches for a Basic + a Stage 1 + a Stage 2: each candidate is scored
# by table (the same pattern as NS/BCS, reusing _CtxNS). The axis of the block is
# `_dawn_forest_avail`: with Forest of Vitality IN PLAY or IN HAND the lines
# can be evolved the same turn (a rush), so the Stage 1/2 pieces
# rise in value even if their pre-evolution is not on the board yet.


_RULES_DAWN_MEGANIUM = [
    _FixedRule("already_in_play",
               lambda c: AGENT_STATE.meganium_in_play, lambda c: 10),
    _FixedRule("immediate_evo",
               lambda c: c.field.get(Bayleef, 0) >= 1, lambda c: 1000),
    _FixedRule("rush_from_field_with_bayleef",
               lambda c: (c.field.get(Chikorita, 0) >= 1
                          and _dawn_forest_avail(c)
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 980),
    _FixedRule("rush_from_field",
               lambda c: (c.field.get(Chikorita, 0) >= 1
                          and _dawn_forest_avail(c)),
               lambda c: 950),
    _FixedRule("rush_from_hand_with_bayleef",
               lambda c: (c.hand.get(Chikorita, 0) >= 1
                          and _dawn_forest_avail(c)
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 960),
    _FixedRule("rush_from_hand",
               lambda c: (c.hand.get(Chikorita, 0) >= 1
                          and _dawn_forest_avail(c)),
               lambda c: 920),
]

_RULES_DAWN_BAYLEEF = [
    _FixedRule("meganium_already_in_play",
               lambda c: AGENT_STATE.meganium_in_play, lambda c: 10),
    # The immediate evolution rises if the Meganium that completes the line is
    # reachable (in hand or still in the deck).
    _FixedRule("immediate_evo_rush",
               lambda c: (c.field.get(Chikorita, 0) >= 1
                          and _dawn_forest_avail(c)
                          and (c.hand.get(Meganium, 0) >= 1 or
                               AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                                   Meganium, {}).get(ZONE_DECK, 0) > 0)),
               lambda c: 970),
    _FixedRule("immediate_evo",
               lambda c: c.field.get(Chikorita, 0) >= 1, lambda c: 900),
    _FixedRule("rush_from_hand",
               lambda c: (c.hand.get(Chikorita, 0) >= 1
                          and _dawn_forest_avail(c)),
               lambda c: 880),
    _FixedRule("with_chikorita_in_hand",
               lambda c: (c.bench_count < 5
                          and c.hand.get(Chikorita, 0) >= 1),
               lambda c: 500),
]

_RULES_DAWN_CHIKORITA = [
    _FixedRule("meganium_already_in_play",
               lambda c: AGENT_STATE.meganium_in_play, lambda c: 10),
    _FixedRule("line_in_play",
               lambda c: (c.field.get(Chikorita, 0)
                          + c.field.get(Bayleef, 0)
                          + c.field.get(Meganium, 0) >= 1),
               lambda c: 50),
    _FixedRule("full_bench",
               lambda c: c.bench_count >= 5, lambda c: 30),
    _FixedRule("rush_with_bayleef",
               lambda c: (_dawn_forest_avail(c)
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 850),
    _FixedRule("rush",
               lambda c: _dawn_forest_avail(c), lambda c: 800),
    _FixedRule("with_bayleef_in_hand",
               lambda c: c.hand.get(Bayleef, 0) >= 1, lambda c: 700),
]

_RULES_DAWN_HYDRAPPLE = [
    _FixedRule("already_in_play",
               lambda c: c.has_hydrapple, lambda c: 10),
    _FixedRule("immediate_evo",
               lambda c: c.field.get(Dipplin, 0) >= 1, lambda c: 980),
    _FixedRule("rush_from_field_with_dipplin",
               lambda c: (c.field.get(Applin, 0) >= 1
                          and _dawn_forest_avail(c)
                          and c.hand.get(Dipplin, 0) >= 1),
               lambda c: 960),
    _FixedRule("rush_from_field",
               lambda c: (c.field.get(Applin, 0) >= 1
                          and _dawn_forest_avail(c)),
               lambda c: 930),
    _FixedRule("rush_from_hand_with_dipplin",
               lambda c: (c.hand.get(Applin, 0) >= 1
                          and _dawn_forest_avail(c)
                          and c.hand.get(Dipplin, 0) >= 1),
               lambda c: 940),
    _FixedRule("rush_from_hand",
               lambda c: (c.hand.get(Applin, 0) >= 1
                          and _dawn_forest_avail(c)),
               lambda c: 900),
]

_RULES_DAWN_DIPPLIN = [
    _FixedRule("redundant_with_hydrapple",
               lambda c: (c.has_hydrapple
                          and c.field.get(Dipplin, 0) >= 1),
               lambda c: 10),
    _FixedRule("immediate_evo_rush",
               lambda c: (c.field.get(Applin, 0) >= 1
                          and _dawn_forest_avail(c)
                          and (c.hand.get(Hydrapple_ex, 0) >= 1 or
                               AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                                   Hydrapple_ex, {}).get(ZONE_DECK, 0) > 0)),
               lambda c: 950),
    _FixedRule("immediate_evo",
               lambda c: c.field.get(Applin, 0) >= 1, lambda c: 880),
    _FixedRule("rush_from_hand",
               lambda c: (c.hand.get(Applin, 0) >= 1
                          and _dawn_forest_avail(c)),
               lambda c: 860),
    _FixedRule("with_applin_in_hand",
               lambda c: (c.bench_count < 5
                          and c.hand.get(Applin, 0) >= 1),
               lambda c: 480),
]

_RULES_DAWN_APPLIN = [
    _FixedRule("full_line",
               lambda c: (c.has_hydrapple
                          and c.field.get(Applin, 0)
                          + c.field.get(Dipplin, 0) >= 1),
               lambda c: 10),
    _FixedRule("doubled_line",
               lambda c: (c.field.get(Applin, 0)
                          + c.field.get(Dipplin, 0)
                          + c.field.get(Hydrapple_ex, 0) >= 2),
               lambda c: 30),
    _FixedRule("full_bench",
               lambda c: c.bench_count >= 5, lambda c: 30),
    _FixedRule("rush_with_dipplin",
               lambda c: (_dawn_forest_avail(c)
                          and c.hand.get(Dipplin, 0) >= 1),
               lambda c: 830),
    _FixedRule("rush",
               lambda c: _dawn_forest_avail(c), lambda c: 780),
    _FixedRule("with_dipplin_in_hand",
               lambda c: c.hand.get(Dipplin, 0) >= 1, lambda c: 680),
]

_RULES_DAWN_OGERPON = [
    _FixedRule("two_in_play",
               lambda c: c.field.get(Teal_Mask_Ogerpon_ex, 0) >= 2,
               lambda c: 10),
    _FixedRule("full_bench",
               lambda c: c.bench_count >= 5, lambda c: 30),
    _FixedRule("first_ogerpon",
               lambda c: c.field.get(Teal_Mask_Ogerpon_ex, 0) == 0,
               lambda c: 500),
]

_RULES_DAWN_TAPU = [
    # vs Dragapult with the board already built it cannot be PUT DOWN: not searched for.
    _FixedRule("dragapult_does_not_play_it",
               lambda c: c.dragapult_no_tapu,
               lambda c: SCORE_VETO),
    _FixedRule("already_in_play",
               lambda c: c.field.get(Tapu_Bulu, 0) >= 1, lambda c: 10),
    _FixedRule("anti_wall_with_meganium",
               lambda c: ((AGENT_STATE.op_is_crustle_deck or c.op_ex_immune_active
                           or c.op_ex_immune_bench)
                          and AGENT_STATE.meganium_in_play),
               lambda c: 700),
    _FixedRule("anti_wall",
               lambda c: (AGENT_STATE.op_is_crustle_deck or c.op_ex_immune_active
                          or c.op_ex_immune_bench),
               lambda c: 600),
]

_RULES_DAWN_FEZ = [
    _FixedRule("already_in_play",
               lambda c: c.field.get(Fezandipiti_ex, 0) >= 1, lambda c: 10),
    _FixedRule("after_a_ko",
               lambda c: AGENT_STATE.ko_last_turn, lambda c: 500),
]

_RULES_DAWN_MEOWTH = [
    _FixedRule("already_in_play",
               lambda c: c.field.get(Meowth_ex, 0) >= 1, lambda c: 10),
    _FixedRule("supporter_engine",
               lambda c: (not c.watchtower and not c.supporter_played
                          and c.bench_count < 5),
               lambda c: 300),
]

_RULES_DAWN_GRASS = [
    # See `grass_makes_the_active_ko` in _RULES_NS_GRASS: today's prize beats
    # every development target of this table.
    _FixedRule("grass_makes_the_active_ko",
               lambda c: c.grass_makes_the_active_ko,
               lambda c: 1400),
    _FixedRule("no_grass_and_no_attachment",
               lambda c: (not c.energy_attached
                          and c.hand.get(Basic_Grass_Energy, 0) == 0),
               lambda c: 400),
    _FixedRule("no_grass",
               lambda c: c.hand.get(Basic_Grass_Energy, 0) == 0,
               lambda c: 250),
]

_RULES_DAWN_FOREST = [
    _FixedRule("forest_missing",
               lambda c: not AGENT_STATE.forest_in_play and not _dawn_forest_avail(c),
               lambda c: 600),
]

_DAWN_FETCH_TABLE = {
    Meganium: ("dawn->meganium", _RULES_DAWN_MEGANIUM, 200),
    Bayleef: ("dawn->bayleef", _RULES_DAWN_BAYLEEF, 150),
    Chikorita: ("dawn->chikorita", _RULES_DAWN_CHIKORITA, 500),
    Hydrapple_ex: ("dawn->hydrapple", _RULES_DAWN_HYDRAPPLE, 180),
    Dipplin: ("dawn->dipplin", _RULES_DAWN_DIPPLIN, 130),
    Applin: ("dawn->applin", _RULES_DAWN_APPLIN, 480),
    Teal_Mask_Ogerpon_ex: ("dawn->ogerpon", _RULES_DAWN_OGERPON, 400),
    Tapu_Bulu: ("dawn->tapu", _RULES_DAWN_TAPU, 100),
    Fezandipiti_ex: ("dawn->fez", _RULES_DAWN_FEZ, 80),
    Meowth_ex: ("dawn->meowth", _RULES_DAWN_MEOWTH, 50),
    Basic_Grass_Energy: ("dawn->grass", _RULES_DAWN_GRASS, 80),
    Forest_of_Vitality: ("dawn->forest", _RULES_DAWN_FOREST, 10),
}

# --- Rules of the Boss's Orders gust TARGET ---------------------------------
# Two modes, like the original block: NUISANCE (our active cannot attack:
# jam the opponent) and OFFENSIVE (gust to knock out or pin down). The entry
# score of the option loop is 0; the contributions are cumulative
# (_Adjustment). Dunsparce is discarded at the call site (user's rule: NEVER
# gust it, in any mode).





# GRADUATING THE ATTACK AXIS: MEASURED AND REVERTED (Aug 2026).
#
# `without_a_ko_prefer_the_dead_body` (+1500) is a BOOLEAN with a horizon of ONE
# energy (`_op_body_is_harmless` = deficit >= 2): it separates those who can
# attack next turn from those who cannot, but it leaves all the dead bodies
# TIED with each other. Since the RETREAT axis is graduated (`stall_diff` x
# 100), the same treatment was tried for the ATTACK one: +200 for each energy
# missing ABOVE the 2 that already earn the +1500, capped at 2 steps, with the
# same three guards (no KO / dead body / `GUST_TRAP_IDS` excluded).
#
# It was dropped for being INERT, not harmful. The bonus altered some score in 142 of
# 535 target decisions (1400 games, 7 matchups) and changed the chosen
# target in ZERO. The reason lies in the shape of the band: in 117 of the 144
# decisions with a bonusable candidate the gap to the chosen one was 0 -- the
# body with a deficit of 3 was ALREADY the argmax through other routes (a graduated
# `stuck_without_ko` + `_gust_opponent_line`), so the bonus only fattened an existing
# advantage. In the remaining 27 the gap was a KO tier (>= 3000) or the deliberate
# preference for cutting the evolution line: exactly what a tie-break must not
# overturn. The winrate was consistent with that -- neutral and below the gate's
# resolution (n=3000/branch x 5 matchups: aggregate -0.14 against the control, with
# a NULL control drift of -0.06; no individual delta leaves the null range).
#
# What DOES remain from the attempt is `_op_attack_deficit`: the graduated axis
# exists as a primitive and `_op_body_is_harmless` is explicitly its threshold, which
# is where the confusion was. If some day a tie-break inside the band is needed,
# the datum is already measured; what is not needed is the bonus.








def agent(obs_dict: dict) -> list[int]:
    """Answer ONE menu: read the board, score the options, return our choice.

    The competition's entry point. `obs_dict` is the raw observation; the
    return is a list of indices into `obs.select.option`.

    THE ONE SPECIAL CASE comes first: when there is no `select`, the engine is
    not asking us to choose -- it is asking for our DECK LIST at the start of
    the game, so we return that instead.

    Otherwise the phases run in the order documented at the top of this file,
    and the last of them (`finalizar`) returns the choice. Everything between
    is the reading of the board into the flags the rules consult.

    CALLED MANY TIMES PER TURN, including during the OPPONENT's turn for forced
    selections. Nothing may assume it is the first call of a turn; anything that
    must survive from one menu to the next lives on `AGENT_STATE`, and anything
    that must NOT is cleared here at the top -- the turn plan is the example
    right below.
    """
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return my_deck

    state = obs.current
    select = obs.select
    context = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]
    my_prize = len(my_state.prize)
    op_prize = len(op_state.prize)

    # The turn plan belongs to THIS observation and to no other: cleared here so
    # that no rule can ever read the plan of a previous decision (AGENT_STATE
    # survives between calls, and between two calls a Teal Dance or a gust may
    # have already changed which routes exist). It is filled in further down, once
    # the flags it consumes have been computed. See ptcg/turn/game_plan.py.
    AGENT_STATE.turn_plan = None

    # Nighttime Mine tax on our Tera. It goes HERE, before
    # any scoring, because ~50 places read ATTACK_ENERGY_REQ and all of them
    # have to see the already corrected cost.
    nighttime_mine_in_play = _aplicar_impuesto_tera(state.stadium)

    _update_cards_tracking(obs, my_index, my_state)


    if state.firstPlayer >= 0:
        AGENT_STATE.we_go_first = (state.firstPlayer == state.yourIndex)

    if AGENT_STATE.pre_turn != state.turn:
        AGENT_STATE.pre_turn = state.turn
        AGENT_STATE.plan = AttackPlan()

        # WHERE OUR PRIZE PILE STARTED THIS TURN. A prize cashed inside the turn
        # is invisible afterwards -- the observation only carries the pile as it
        # stands -- and Settle the Score (Okidogi) scales with the prizes of one
        # TURN, not of the game. Frozen here, on the only line that knows a turn
        # just changed.
        AGENT_STATE._prize_pile_at_turn_start = my_prize

        # Counter of Grass energies put on the field this turn (see
        # `_grass_ability_slots`): it is PER TURN.
        AGENT_STATE._grass_attaches_this_turn = 0

        # Our own Xerosic cap (see `_our_cap_already_spent`): PER TURN too. The
        # Stamp it holds back is held back for THIS turn only; on the next one
        # their hand has refilled and the card is worth playing again.
        AGENT_STATE._xerosic_played_this_turn = False

        # What OUR OWN searches have already bought into this hand: PER TURN.
        # A purchase is the reason a cost was paid TODAY; next turn the card is
        # just a card in hand and the ordinary ladders price it.
        AGENT_STATE._bought_this_turn = set()

        # Attacks each opposing body has declared this turn (see
        # `op_double_attack_pending`): PER TURN. Festival Lead grants a SECOND
        # wave inside one turn, never a third, and next turn the pair starts over.
        AGENT_STATE._op_attack_waves_this_turn = {}

        AGENT_STATE._field_at_turn_start = None

        # The OPENING sentence of the turn: the plan of its first menu, kept so
        # the trace can show what the turn was for before we started spending it.
        AGENT_STATE.turn_plan_open = None

        AGENT_STATE._ko_detected_this_turn = False

        AGENT_STATE._poke_pad_target_id = 0

        AGENT_STATE._ub_meowth_pending = False

        AGENT_STATE._ub_fez_pending = False

        AGENT_STATE._ub_engine_pivot_turn = False

        AGENT_STATE._ld_supp_comprometido = 0

        # The active's ability cache is PER TURN (see below).
        AGENT_STATE._td_ability_serial = None

    field_counts = defaultdict(int)
    hand_counts = defaultdict(int)
    discard_counts = defaultdict(int)

    AGENT_STATE.meganium_in_play = False
    AGENT_STATE.forest_in_play = False
    has_ogerpon = False
    has_hydrapple = False
    bench_count = 0
    # The state's bench cap; the synthetic states of the tests do not always
    # carry it, and the Supporter utility gates ("does what I bring fit?")
    # consult it every turn.
    bench_max = getattr(my_state, 'benchMax', None) or 5

    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id == Meganium:
            AGENT_STATE.meganium_in_play = True
        if card.id == Hydrapple_ex:
            has_hydrapple = True
        if card.id == Teal_Mask_Ogerpon_ex:
            has_ogerpon = True

    for pokemon in my_state.bench:
        if pokemon is not None:
            bench_count += 1

    if AGENT_STATE._field_at_turn_start is None:
        AGENT_STATE._field_at_turn_start = dict(field_counts)

    if AGENT_STATE._poke_pad_target_id > 0 and field_counts.get(AGENT_STATE._poke_pad_target_id, 0) > 0:
        AGENT_STATE._poke_pad_target_id = 0

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    # With a FULL bench, a search resource (Ultra Ball / Poke Pad) only
    # contributes value if it allows EVOLVING a Pokemon already in play (nothing new
    # can be benched). "There is something to evolve" = we have in play a
    # pre-evolution whose next stage is available (in hand or in the deck).
    _evolve_possible_in_play = (
        (field_counts.get(Chikorita, 0) >= 1 and
         (hand_counts.get(Bayleef, 0) >= 1 or
          AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Bayleef, {}).get(ZONE_DECK, 0) > 0)) or
        (field_counts.get(Bayleef, 0) >= 1 and
         (hand_counts.get(Meganium, 0) >= 1 or
          AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meganium, {}).get(ZONE_DECK, 0) > 0)) or
        (field_counts.get(Applin, 0) >= 1 and
         (hand_counts.get(Dipplin, 0) >= 1 or
          AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Dipplin, {}).get(ZONE_DECK, 0) > 0)) or
        (field_counts.get(Dipplin, 0) >= 1 and
         (hand_counts.get(Hydrapple_ex, 0) >= 1 or
          AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Hydrapple_ex, {}).get(ZONE_DECK, 0) > 0))
    )

    # The evolution link that really needs searching for / orphaned
    # evolutions (without their pre-evolution). See `_evo_link_state`.
    _evo_necesarios, _evo_huerfanos = _evo_link_state(hand_counts, field_counts)

    stadium_id = 0
    for card in state.stadium:
        stadium_id = card.id

    if stadium_id == Forest_of_Vitality:
        AGENT_STATE.forest_in_play = True

    # Grand Tree on the field: its ability is SHARED (once during EACH player's
    # turn), so we take advantage of it whether we played it
    # ourselves or the opponent did. See the `_gt_*` block for the concrete plan.
    grand_tree_in_play = (stadium_id == Grand_Tree)

    neutralization_zone_active = (stadium_id == Neutralization_Zone)

    # Full Metal Lab: -30 onto {M} bodies, after weakness and resistance. Only
    # THEIR Metal is reachable by it -- everything we play is Grass -- so this
    # flag only ever subtracts from our own projected damage.
    full_metal_lab_active = (stadium_id == Full_Metal_Lab)
    AGENT_STATE.full_metal_lab_in_play = full_metal_lab_active

    # Team Rocket's Watchtower: the {C} Pokemon in play (both players) do NOT
    # have Abilities. Meowth ex is {C}, so its Last-Ditch Catch (searching for a
    # Supporter when benched) is CANCELLED while this stadium is still in
    # play. It is not worth putting Meowth ex down or searching for it with an Ultra Ball
    # until the stadium can be replaced (e.g. with Forest of Vitality).
    watchtower_in_play = (stadium_id == Team_Rockets_Watchtower)

    # Iron Thorns ex ("Initialization") as the opposing ACTIVE (P1.4): it cancels the
    # abilities of ALL the Pokemon with a Rule Box on both sides. Teal
    # Dance / Ripening / Flip the Script disappear from the menu (the game engine
    # enforces it), but the agent must also NOT plan around
    # Last-Ditch Catch (putting down or searching for a Meowth ex "for the fetch"): the same
    # effect as Team Rocket's Watchtower on Meowth. Unlike the
    # stadium, Forest does NOT fix it (Iron Thorns has to be removed from the active spot:
    # a KO or a gust), which is why `watchtower_in_play` is kept pure for the
    # counter-stadium rules and this OR feeds the gates of the Meowth engine.
    op_iron_thorns_active = bool(
        op_state.active and op_state.active[0] is not None
        and op_state.active[0].id == Iron_Thorns_ex)
    meowth_ability_lock = watchtower_in_play or op_iron_thorns_active

    # Prize denial on the opponent's field (P0.2): it refreshes the flags that
    # `prize_count_op` consults (Pecharunt ex -> Munkidori ex yields 1 less;
    # Mega Gengar ex -> their {D} yield 1 less against our ex).
    _op_field_ids = {p.id for p in ((op_state.active or [])
                                    + (op_state.bench or [])) if p is not None}
    AGENT_STATE._op_prize_denial_pecharunt = Pecharunt_ex in _op_field_ids
    AGENT_STATE._op_prize_denial_gengar = Mega_Gengar_ex in _op_field_ids

    # The opposing board that the damage projections need: the BENCH scales Do
    # the Wave (20 x bench) and the stadium switches on Festival Lead. They are published as
    # module flags -- and not as parameters -- so that ALL the callers of
    # `_op_active_attack_damage_to` see them; see DO_THE_WAVE_ATTACK_ID.
    AGENT_STATE._op_bench_count = sum(1 for p in (op_state.bench or []) if p is not None)
    # ... and the damage their BENCH hands to their ATTACKER: an ability such as
    # Cheer On to Glory (Cynthia's Roserade) or Extra Helpings (Hop's Snorlax)
    # adds a flat 30 to every attack their team uses against our active, and it
    # lives on a body the projector never sees. Same block, same reason.
    AGENT_STATE._op_team_dmg_buff = _op_team_damage_buff(op_state)
    # ... and the FULL scale of the opposing attacks that do not do their printed
    # damage (see ptcg/cards/op_scaling.py). It goes in the same block and for
    # the same reason as the line above: the projector reads it from the state,
    # not from its signature.
    AGENT_STATE.op_scale = build_op_scale(
        my_state, op_state,
        prize_pile_at_turn_start=AGENT_STATE._prize_pile_at_turn_start)
    AGENT_STATE._festival_grounds_in_play = any(
        getattr(c, 'id', 0) == Festival_Grounds for c in (state.stadium or []))

    # A HOSTILE Festival Grounds: the stadium only damages us if the opponent really
    # has the line that exploits it. Having SEEN one of their Applin or
    # Dipplin (field or discard) is required because the stadium is double-edged --
    # our own Dipplin also gains Festival Lead with it on the field -- so
    # removing it "just in case" would switch off our copy too. We do not
    # play Festival Grounds (it is not in deck.csv): if it is on the field, it is theirs.
    _festival_lead_hostil = AGENT_STATE._festival_grounds_in_play and (
        any(p is not None and p.id in (Dipplin, Applin)
            for p in ((op_state.active or []) + (op_state.bench or [])))
        or any(getattr(c, 'id', 0) in (Dipplin, Applin)
               for c in (op_state.discard or [])))

    is_poisoned = my_state.poisoned
    is_burned = my_state.burned
    is_asleep = my_state.asleep
    is_paralyzed = my_state.paralyzed
    is_confused = my_state.confused
    has_condition = is_poisoned or is_burned or is_asleep or is_paralyzed or is_confused

    condition_blocks_action = is_paralyzed or is_asleep

    condition_risky_attack = is_confused

    condition_passive_damage = is_poisoned or is_burned

    condition_urgency = 0
    if is_paralyzed:
        condition_urgency += 5000
    if is_asleep:
        condition_urgency += 3000
    if is_confused:
        condition_urgency += 2000
    if is_poisoned:
        condition_urgency += 1500
    if is_burned:
        condition_urgency += 1200

    # Grass energies WE have put on the field during this turn. The logs arrive
    # in incremental batches, so they are accumulated call by call; if the batch
    # crosses the turn change only the ATTACH events after the last
    # TURN_START/TURN_END count. With this counter `_grass_ability_slots` knows whether
    # any charging ability (Teal Dance / Ripening Charge) is still alive
    # when the turn's MANUAL attachment has already been spent.
    _ga_from = 0
    for _ga_i, _ga_log in enumerate(obs.logs):
        if getattr(_ga_log, 'type', None) in (LogType.TURN_START,
                                              LogType.TURN_END):
            _ga_from = _ga_i + 1
    for _ga_log in obs.logs[_ga_from:]:
        if (getattr(_ga_log, 'type', None) == LogType.ATTACH
                and getattr(_ga_log, 'playerIndex', None) == my_index
                and getattr(_ga_log, 'cardId', None) == Basic_Grass_Energy):
            AGENT_STATE._grass_attaches_this_turn += 1
        # ...and, off the same batch and with the same turn boundary, whether OUR
        # OWN Xerosic's Machinations has already capped their hand this turn. It
        # cannot be read off the board: `supporterPlayed` does not say WHICH
        # Supporter went down, and a Xerosic in the discard may be one we played
        # three turns ago or one an Ultra Ball threw away. Only the PLAY log
        # dates it. See `_our_cap_already_spent` (disruption.py).
        elif (getattr(_ga_log, 'type', None) == LogType.PLAY
                and getattr(_ga_log, 'playerIndex', None) == my_index
                and getattr(_ga_log, 'cardId', None) == Xerosic_Machinations):
            AGENT_STATE._xerosic_played_this_turn = True
        # ...and, off the same batch and with the same turn boundary, WHICH
        # cards of this hand our own searches went and got today. A card that
        # arrives from the DECK or from the DISCARD PILE into our hand was
        # fetched by something we PLAYED (Ultra Ball, a Meowth ex ability, a
        # Bug Catching Set, a Night Stretcher...): we paid for it. A DRAW is a
        # different log and does not count -- nobody chose it, so it is not the
        # reason any cost was paid. See
        # `DISCARD_WHAT_THE_SEARCH_ALREADY_BOUGHT` in the DISCARD scorer.
        elif (getattr(_ga_log, 'type', None) == LogType.MOVE_CARD
                and getattr(_ga_log, 'playerIndex', None) == my_index
                and getattr(_ga_log, 'toArea', None) == AreaType.HAND
                and getattr(_ga_log, 'fromArea', None) in (AreaType.DECK,
                                                           AreaType.DISCARD)
                and getattr(_ga_log, 'serial', None) is not None):
            AGENT_STATE._bought_this_turn.add(_ga_log.serial)
        # ...and, off the same batch and with the same turn boundary, HOW MANY
        # times each opposing body has already attacked today. Festival Lead is
        # the only sentence in the format that lets one attack twice in a turn,
        # and the whole point of `op_double_attack_pending` is the wave STILL
        # OWED to us. The log dates it and nothing else can: the board at the
        # promotion looks identical whether the knockout came from their first
        # wave (a second one is coming) or from their second (the turn is over).
        elif (getattr(_ga_log, 'type', None) == LogType.ATTACK
                and getattr(_ga_log, 'playerIndex', None) != my_index
                and getattr(_ga_log, 'serial', None) is not None):
            AGENT_STATE._op_attack_waves_this_turn[_ga_log.serial] = (
                AGENT_STATE._op_attack_waves_this_turn.get(_ga_log.serial, 0)
                + 1)

    # The turn window of OUR KOs (see `_rastrear_ventana_de_ko`): it has to be
    # tracked in EVERY observation, including the forced selections
    # during the opponent's turn, because the TURN_END and the KO can arrive in
    # different log batches.
    _rastrear_ventana_de_ko(obs.logs, my_index, state.turn)

    AGENT_STATE.ko_last_turn = AGENT_STATE._ko_detected_this_turn

    if not AGENT_STATE.ko_last_turn:

        for log in obs.logs:
            if hasattr(log, 'type'):
                if (log.type == LogType.MOVE_CARD and hasattr(log, 'playerIndex') and
                        log.playerIndex != my_index and hasattr(log, 'fromArea') and
                        log.fromArea == AreaType.PRIZE):
                    AGENT_STATE.ko_last_turn = True
                    break

    if not AGENT_STATE.ko_last_turn:

        if op_prize < AGENT_STATE._prev_op_prize:
            AGENT_STATE.ko_last_turn = True

    if not AGENT_STATE.ko_last_turn:

        if context == SelectContext.TO_ACTIVE and not state.retreated:
            AGENT_STATE.ko_last_turn = True

    # --- THE KO WINDOW: the prize taken does not say WHEN the body died -------
    # The three tests above only see the EFFECT of a KO of ours (the opponent
    # takes a prize, we have to promote). Here the clause that Flip the Script and
    # Unfair Stamp really ask for is checked: that the KO fell WITHIN the
    # opponent's last turn. A KO BETWEEN TURNS (Froslass's Freezing Shroud) or
    # during our own turn (a recoil self-KO) does not enable them, and the engine
    # simply does not offer the Stamp or the ability.
    #
    # It only LOWERS, and only with positive evidence in the logs: if we did not see
    # the KO window, `ko_last_turn` stays as it was.
    _ko_fuera_de_ventana = (AGENT_STATE._own_ko_outside_op_turn >= state.turn - 1)
    _ko_dentro_de_ventana = (AGENT_STATE._own_ko_inside_op_turn >= state.turn - 1)
    if AGENT_STATE.ko_last_turn and _ko_fuera_de_ventana and not _ko_dentro_de_ventana:
        AGENT_STATE.ko_last_turn = False
        AGENT_STATE._ko_detected_this_turn = False

    # The engine's oracle: Unfair Stamp carries PRINTED on it the same clause as Flip
    # the Script ("you may play this card only if any of your Pokemon were Knocked
    # Out during your opponent's last turn"). If we have it in
    # hand and the MAIN menu does not offer it, the game itself is saying that
    # the clause is not met -- and then Fezandipiti's ability could not be used
    # either. It is the reference truth, above any
    # inference from logs, but it is only available with the Stamp in hand.
    if (AGENT_STATE.ko_last_turn and hand_counts.get(Unfair_Stamp, 0) >= 1
            and context == SelectContext.MAIN
            and my_state.hand is not None):
        _stamp_idx = {_i for _i, _c in enumerate(my_state.hand)
                      if _c is not None and _c.id == Unfair_Stamp}
        _jugables = {getattr(_o, 'index', None) for _o in select.option
                     if getattr(_o, 'type', None) == OptionType.PLAY}
        if not (_stamp_idx & _jugables):
            AGENT_STATE.ko_last_turn = False
            AGENT_STATE._ko_detected_this_turn = False

    if AGENT_STATE.ko_last_turn:
        AGENT_STATE._ko_detected_this_turn = True

    # Blocking the chain Unfair Stamp -> Fezandipiti's ability (Flip the
    # Script): while we have a playable Unfair Stamp this turn (we were knocked out
    # last turn and it is still in hand), the Stamp is played first and THEN
    # the ability. It is defined here (agent scope) because the block of
    # Fezandipiti's ability consults it in any context.
    # ...and only if the Stamp DESERVES to be played (a card rule, `_sello_merece_
    # jugarse`): with the opposing hand <= 2 and ours large the Stamp waits, so
    # it must block neither the ability nor the Supporter chain.
    # The three extra clauses travel with it: this scope runs BEFORE the matchup
    # flags are computed, but `_op_refill_engine` and `_stamp_buries_the_last_
    # xerosic` only read the board, the hand and the deck census, and the Xerosic
    # cap of the turn is already accumulated above -- all of them are here.
    # Without them this flag would go on blocking the chain for a Stamp that the
    # scoring is now going to veto -- the very paralysis `_stamp_pendiente`
    # documents.
    # THE SAME SENTENCE, UNDER THE NAME OF WHAT IT IS. "We were knocked out, the
    # Stamp is in hand and the card rule says it is worth playing" is the
    # ordering veto above AND a BOARD FACT about the turn that is coming: their
    # hand is about to be two cards. The projector needs the fact, not the veto
    # (see `_mp_reply_after_our_reset`), so the expression is written once and
    # wears both names.
    _stamp_reset_pending = (
        AGENT_STATE.ko_last_turn and hand_counts.get(Unfair_Stamp, 0) >= 1
        and _stamp_worth_playing(
            getattr(op_state, 'handCount', 0),
            len(my_state.hand or []),
            op_refill_engine=_op_refill_engine(op_state),
            buries_the_last_xerosic=_stamp_buries_the_last_xerosic(
                hand_counts, AGENT_STATE.ACTIVE_CARDS_IN_DECK,
                state.supporterPlayed, op_state),
            our_cap_already_spent=AGENT_STATE._xerosic_played_this_turn))
    _stamp_blocks_supp_chain = _stamp_reset_pending

    # Order Lillie's Determination -> Flip the Script (user's request): if
    # we have Lillie's Determination in hand and have not played a Supporter yet
    # this turn, Lillie's Determination is played first and THEN Fezandipiti's
    # ability. Lillie's Determination is a Supporter: once played it leaves the
    # hand and this flag becomes False, re-enabling the ability (30000).
    _lillie_blocks_fez_ability = (hand_counts.get(Lillie_Determination, 0) >= 1
                                  and not state.supporterPlayed)

    if context == SelectContext.MAIN:
        AGENT_STATE._prev_op_prize = op_prize

    def _op_best_damage_vs(my_pokemon, assume_attach=True):
        if my_pokemon is None:
            return 0
        _opa = _active_of(op_state)
        if _opa is None:
            return 0
        _opd = card_table.get(_opa.id)
        if not _opd or not getattr(_opd, 'attacks', None):
            return 0
        _avail = len(_opa.energies) + (1 if assume_attach else 0)
        _best = 0
        for _atk in _opd.attacks:
            _dmg = getattr(_atk, 'damage', None)
            if _dmg is None:
                continue
            _cost = getattr(_atk, 'cost', None)
            _need = 0
            if _cost is not None:
                try:
                    _need = len(_cost)
                except TypeError:
                    try:
                        _need = int(_cost)
                    except (TypeError, ValueError):
                        _need = 0
            if _need <= _avail:
                _best = max(_best, _dmg)
        _myd = card_table.get(my_pokemon.id)
        # Maximum Belt (1158, an Ace Spec) on the opposing active: +50 damage to
        # our ACTIVE ex Pokemon, before weakness (July 2026 audit:
        # the opponent's tools were invisible and the pivots believed the wall
        # survived a boosted hit).
        if (_best > 0 and my_pokemon.id in OUR_EX_IDS
                and any(getattr(_t, 'id', 0) == Maximum_Belt
                        for _t in (getattr(_opa, 'tools', None) or []))):
            _best += 50
        if (_myd and _opd and getattr(_myd, 'weakness', None) is not None and
                _myd.weakness == getattr(_opd, 'energyType', None)):
            _best *= 2
        return _best

    def _op_counter_threat_vs(my_pokemon):
        # Attacks that place damage COUNTERS according to the opponent's hand size
        # (e.g. Alakazam - Powerful Hand: 20 per card in their hand). These
        # attacks have 'damage' = None (n/a), so _op_best_damage_vs
        # ignores them and the agent is blind to the threat. Here we estimate them so
        # the lookahead penalises promoting a fragile Pokemon that would die.
        if my_pokemon is None:
            return 0
        _opa = _active_of(op_state)
        if _opa is None:
            return 0
        if _opa.id == Alakazam_ex:
            _h = _op_hand_size(op_state)
            if _h <= 0:
                _h = 4  # hidden opposing hand: a conservative estimate
            return 20 * _h
        # Do the Wave (Dipplin): 20 x THEIR bench, another printed damage of 0. This hook
        # is what the promotion lookahead consults (SCORE_LOOKAHEAD_PROMOTE_KO),
        # so without it bringing up a fragile body came for free. The Brave
        # Bangle is added just as in `_op_active_attack_damage_to`.
        if _opa.id == Dipplin:
            _dmg = 20 * AGENT_STATE._op_bench_count
            if (_dmg > 0 and my_pokemon.id in OUR_EX_IDS
                    and any(getattr(_t, 'id', 0) == Brave_Bangle
                            for _t in (getattr(_opa, 'tools', None) or []))
                    and not _tiene_rule_box(_opa.id)):
                _dmg += 30
            return _dmg
        return 0

    active_ko_likely = False
    active_hp_ratio = 1.0
    estimated_op_damage = 0
    _teal_wall_pivot = False
    # Deck-agnostic twin of the above; see the block that fills it in.
    _doomed_mute_pivot = False

    _mega_line_active = False
    if my_state.active and my_state.active[0] is not None:
        my_active = my_state.active[0]
        active_hp_ratio = my_active.hp / max(1, my_active.maxHp)
        if my_active.id in (Chikorita, Bayleef, Meganium):
            _mega_line_active = True

        op_active = _active_of(op_state)
        if op_active is not None:
            op_data = card_table.get(op_active.id)
            op_energy = len(op_active.energies)

            estimated_op_damage = _op_best_damage_vs(my_active)
            # Powerful Hand (Alakazam 743): real damage = 20 x card in the opponent's
            # hand, INVISIBLE to _op_best_damage_vs (printed damage 0). It is
            # projected as 20 x (hand + 2) via _op_active_attack_damage_to --
            # limited to an active Alakazam so as not to alter other matchups. This
            # switches on the whole "doomed active" machinery (defensive
            # pivots, retreat urgency, protections) in the matchup
            # where it is needed most (anti-Alakazam suggestion 1: before, the
            # model believed Alakazam hit for 0).
            # Do the Wave (Dipplin 93) is the same case -- printed damage 0, real
            # 20 x their bench -- and it arrives boosted with a Brave Bangle against
            # our ex. It is limited to an active Dipplin for the same reason as
            # Alakazam: not to alter the "doomed active" reading in the other
            # matchups (log 88971843: the agent believed Dipplin hit for 0).
            if op_active.id in (Alakazam_ex, Dipplin):
                estimated_op_damage = max(
                    estimated_op_damage,
                    _op_active_attack_damage_to(
                        op_active, my_active,
                        getattr(op_state, 'handCount', None)))

            # Opposing bench burst (P0.3): Dusknoir 133 ("Cursed Blast": 13
            # counters = 130) and Dusclops 132 (5 = 50) add EXTRA damage from
            # any position ON TOP OF the active's attack (they use the
            # ability, knock themselves out and THEN attack). Without adding it, the
            # defensive pivots believe the wall survives a hit that in
            # reality arrives with +130. The LARGEST available burst is added (one
            # single ability per projection: conservative without over-firing).
            # It applies even if the opposing active cannot attack: the ability does
            # not need an attack.
            _op_burst = 0
            for _ob_p in ((op_state.active or []) + (op_state.bench or [])):
                if _ob_p is not None and _ob_p.id in OP_BENCH_BURST:
                    _op_burst = max(_op_burst, OP_BENCH_BURST[_ob_p.id])
            estimated_op_damage += _op_burst

            if estimated_op_damage >= my_active.hp:
                active_ko_likely = True
            elif my_active.hp <= 60 and op_energy >= 2:
                active_ko_likely = True
            elif active_hp_ratio <= 0.3 and op_energy >= 1:
                active_ko_likely = True

            # Defensive pivot with Teal Dance (user): if the active is a Teal
            # Mask Ogerpon ex that is DOOMED and will NOT be able to attack this turn (it needs
            # 3 energy) and on the bench there is a Hydrapple ex at full HP
            # (a 330 wall), the correct line is to use Teal Dance on the active
            # (it attaches Grass + DRAWS 1) so as to also enable its retreat (cost
            # 1) and then RETREAT to bring up the stronger body (Hydrapple ex),
            # even if it cannot attack yet: the active is not given away for nothing.
            if (active_ko_likely
                    and my_active.id == Teal_Mask_Ogerpon_ex
                    and (len(my_active.energies) + _grass_attach_unit()) < 3
                    and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                for _twp_bp in (my_state.bench or []):
                    if (_twp_bp is not None and _twp_bp.id == Hydrapple_ex
                            and _twp_bp.hp >= (_twp_bp.maxHp or 0)):
                        _teal_wall_pivot = True
                        break

            # THE MUTE BODY DOES NOT PAY FOR THE FRONT SPOT (user,
            # `records/registro_004_pasos_050_hasta_063.json` step 62, episode
            # 90871654 vs Mega Lucario ex, LOST). The pivot above is the same
            # play written for two cards and one Grass: active Teal Mask
            # Ogerpon ex, benched Hydrapple ex at full HP, and a Grass in hand
            # because the story it was written from was "Teal Dance pays the
            # retreat and THEN we retreat".
            #
            # In the record the Ogerpon had already danced: it stood at 20 of
            # 210 with one Grass on it and a retreat cost of ONE, so the pivot
            # was fully paid for and needed nothing from the hand. The agent
            # spent the last Grass on it anyway, the `hand_counts >= 1` gate
            # went false, the pivot switched off, the retreat was vetoed and
            # the turn ENDED with a 2-prize body at 20 HP in front. Two prizes
            # handed over for a card that bought nothing.
            #
            # So the general rule, which the one above is a case of:
            #
            #   a doomed ACTIVE that cannot attack this turn, whose retreat is
            #   ALREADY payable, hands the front spot to a bench body that
            #   costs the opponent MORE than it does -- fewer prizes, or the
            #   same prizes and it SURVIVES their hit.
            #
            # Nothing here is card or matchup data: the sentence is read off
            # the two bodies and the opponent's REAL finisher
            # (`_op_active_attack_damage_to`, not the `active_ko_likely`
            # heuristic the narrow branch uses -- see
            # [[descuadre-generalizado-ex-condenado-sin-atacante]], where the
            # same generalisation was made with the same reading).
            #
            # It cannot concede more than staying does: the promoted body is
            # never worth more prizes than the one it replaces, and the ex we
            # tuck away is checked by the `_bench_cashable_after_retreat` guard
            # further down, which both walls share.
            #
            # IT GETS ITS OWN FLAG AND DOES NOT RIDE ON `_teal_wall_pivot`,
            # which was the first way this was written and measured -3.7 / -2.4
            # / -1.2 points vs the crustle, marnie and lucario bots (n=400 per
            # arm). That flag is read in three places, and only ONE of them is
            # the retreat: the other two are card-locked side effects written
            # for the board it was born on -- Teal Dance on the ACTIVE at 31600
            # (`ptcg/turn/options/ability.py`) and +4000 to promoting a
            # Hydrapple ex (`ptcg/turn/options/card.py`). Switching the flag on
            # across the whole generalised region dragged those two along, and
            # the +4000 is the expensive one: it puts a 2-prize ex in front of
            # the very ladder this rule exists to serve, over the 1-prize body
            # that `PROMO_PRIZE_PENALTY` had already chosen. The general rule
            # decides ONE thing, which body stands in front, and leaves the
            # promotion to the deck-agnostic chain that already ranks it
            # ([[promover-supervivencia-y-menos-premios]]).
            _doomed_mute_pivot = False
            if not _teal_wall_pivot:
                _dwp_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(my_active.id)
                _dwp_eff = len(my_active.energies)
                # MUTE = it cannot attack TODAY, and "today" is read with the
                # honest census (`_reachable_grass_for`: the Grass in hand, the
                # one a Night Stretcher gets back, and the routes -- the
                # turn's attachment if it is still there, plus the charging
                # abilities), not with a phantom attachment. The narrow branch
                # above assumes one Grass unconditionally, which reads a body
                # as ATTACKING on a turn whose attachment is already spent.
                _dwp_reach = _reachable_grass_for(
                    my_active, state, my_state, hand_counts, field_counts)
                _dwp_mute = (
                    my_active.id == Meowth_ex
                    or (_dwp_req is not None
                        and _dwp_eff < _dwp_req
                        and _dwp_eff + _dwp_reach * _grass_attach_unit()
                        < _dwp_req))
                _dwp_pays_retreat = (
                    _physical_energy(_dwp_eff)
                    >= RETREAT_COST.get(my_active.id, 1))
                _dwp_op_hand = getattr(op_state, 'handCount', None)
                _dwp_doomed = (
                    _op_active_attack_damage_to(op_active, my_active,
                                                _dwp_op_hand)
                    >= (my_active.hp or 0))
                # THE SNIPE GUARD, IN THE SAME NARROW READING THE OTHER
                # SACRIFICE PIVOT WAS MEASURED WITH
                # ([[repliegue-del-ex-condenado-vs-sniper]]): hiding the body
                # only denies prizes if it survives DOWN THERE, and an
                # attacker that also reaches the bench (Shadow Bullet: 180 to
                # the active and 30 to a benched one) cashes it anyway --
                # retreating then concedes 1 + 2 instead of 2. It is read off
                # the ATTACKER IN FRONT and not off the board flag, because
                # switching pivots off for a sniper sitting on their bench
                # measured -3.1 points vs crustle/Kangaskhan.
                #
                # It duplicates what `_bench_cashable_after_retreat` (the
                # shared cancellation further down) already asks, and on
                # purpose: that one honours the Tera of a benched Teal Mask
                # Ogerpon ex and answers "it survives", while the reading the
                # -3.1 was measured against does not. Widening a pivot into
                # the region a measurement told us to stay out of is not
                # something a generalisation gets to do for free.
                _dwp_snipe = OP_BENCH_SNIPE_DAMAGE.get(
                    getattr(op_active, 'id', 0), 0)
                if (_dwp_mute and _dwp_pays_retreat and _dwp_doomed
                        and _dwp_snipe < (my_active.hp or 0)):
                    _dwp_price = prize_count(my_active)
                    for _dwp_bp in (my_state.bench or []):
                        if _dwp_bp is None:
                            continue
                        _dwp_bp_price = prize_count(_dwp_bp)
                        if _dwp_bp_price > _dwp_price:
                            continue
                        _dwp_survives = (
                            (_dwp_bp.hp or 0) > _op_active_attack_damage_to(
                                op_active, _dwp_bp, _dwp_op_hand))
                        if _dwp_bp_price < _dwp_price or _dwp_survives:
                            _doomed_mute_pivot = True
                            break

    # The opponent's ITEM lock (P1.5). The flag keeps its historical name
    # (`itchy_pollen_active`, after Budew's Itchy Pollen) but since the jul 2026
    # plan it means "we canNOT play Items this turn" from ANY
    # source: (a) Budew's Itchy Pollen (an opposing attack last turn),
    # (b) Galvantula ex's Fulgurite (idem, attackId 210), (c) Jellicent ex's
    # "Oceanic Curse" or Tyranitar's "Daunting Gaze" WHILE they are the opposing
    # active. With 10+ items in the deck (UBx4/BCSx4/NSx2/Stamp/PokePad) all
    # the flag's consumers re-prioritise Supporters/abilities.
    itchy_pollen_active = False
    for log in obs.logs:
        if hasattr(log, 'type') and log.type == LogType.ATTACK:
            if log.cardId == Budew and log.playerIndex != my_index:
                itchy_pollen_active = True
            elif (log.cardId == Galvantula_ex
                    and getattr(log, 'attackId', None) == FULGURITE_ATTACK_ID
                    and log.playerIndex != my_index):
                itchy_pollen_active = True
    if (op_state.active and op_state.active[0] is not None
            and op_state.active[0].id in OP_ITEM_LOCK_ACTIVE_IDS):
        itchy_pollen_active = True

    # THE COIN OF THE PREVIOUS TURN DECIDES WHETHER THERE IS ANYTHING TO ATTACK
    # (user, episode 90325863, turn 8 vs a Dragapult / Azumarill deck). Their
    # Marill declared Hide, the coin came up HEADS, and our whole turn 8 went
    # into a Syrup Storm that the log itself scored at zero (`type:16,
    # value: 0`). The read is the OPPONENT'S LAST TURN, replayed here: the
    # ATTACK log gives the serial of the body that hid, the COIN_FLIP log right
    # after it gives the side, and only heads + that same serial still in the
    # active spot means "this body cannot be touched today".
    #
    # It is the ATTACK ID that carries the effect, never the card: `Hide`,
    # `Splashing Dodge`, `Dig`, `Fly`... are the same sentence on twelve
    # different bodies (`COIN_DODGE_ATTACK_IDS`). Reading a single card id --
    # which is what this loop did while it only knew about Hop's Phantump --
    # makes every other one of them invisible.
    op_active_dodge_immune = False
    _dodge_pending_serial = None
    for log in obs.logs:
        _lt = getattr(log, 'type', None)
        if _lt == LogType.ATTACK:
            if (getattr(log, 'attackId', None) in COIN_DODGE_ATTACK_IDS
                    and getattr(log, 'playerIndex', None) != my_index):
                _dodge_pending_serial = getattr(log, 'serial', None)
        elif _lt == COIN_FLIP_LOG_TYPE:

            if (_dodge_pending_serial is not None
                    and getattr(log, 'playerIndex', None) != my_index):
                if getattr(log, 'head', False):

                    if (op_state.active and op_state.active[0] is not None
                            and getattr(op_state.active[0], 'serial', None)
                            == _dodge_pending_serial):
                        op_active_dodge_immune = True

                        AGENT_STATE._dodge_immune_serial = _dodge_pending_serial
                        AGENT_STATE._dodge_immune_turn = state.turn
                _dodge_pending_serial = None

    if (not op_active_dodge_immune
            and AGENT_STATE._dodge_immune_serial is not None
            and AGENT_STATE._dodge_immune_turn == state.turn
            and op_state.active and op_state.active[0] is not None
            and getattr(op_state.active[0], 'serial', None) == AGENT_STATE._dodge_immune_serial):
        op_active_dodge_immune = True

    budew_on_op_field = False
    budew_op_index = -1
    if op_state.active and op_state.active[0] is not None and op_state.active[0].id == Budew:
        budew_on_op_field = True
        budew_op_index = 0
    else:
        for idx, pokemon in enumerate(op_state.bench):
            if pokemon is not None and pokemon.id == Budew:
                budew_on_op_field = True
                budew_op_index = idx + 1
                break

    op_has_ex_immune_active = False
    op_has_ex_immune_bench = False
    op_has_ability_immune_active = False
    op_has_sturdy_crustle = False
    op_has_dwebble_bench = False
    op_has_crustle_bench = False

    op_has_froslass = False
    op_has_snorunt_bench = False
    op_has_munkidori = False
    op_has_dragapult = False
    op_has_dreepy_line = False
    op_has_typhlosion = False
    op_has_ethan_preevo = False
    op_is_fire_deck = False
    op_is_mirror = False
    op_bench_snipe_threat = False
    op_has_latias_ex = False

    op_is_greninja_deck = False
    op_is_slowking_deck = False
    op_is_beedrill_deck = False
    op_is_drednaw_deck = False
    op_is_sylveon_deck = False
    op_has_eevee_bench = False
    op_has_non_immune_eevee_ex = False
    op_is_dragapult_dusknoir = False
    op_is_alakazam_deck = False
    op_is_gardevoir_deck = False
    op_is_zoroark_deck = False
    op_is_aggro_deck = False
    op_is_control_deck = False
    op_has_mega_starmie_active = False
    op_is_lucario_deck = False
    op_is_cubchoo_deck = False
    op_is_hop_deck = False
    op_is_comfey_deck = False
    op_is_raging_bolt_deck = False
    op_is_abomasnow_deck = False
    # The two archetypes that had no flag of their own until the opening
    # sacrifice needed to name them (`OPENING_SAC_SAFE_MATCHUPS`): Marnie's
    # Grimmsnarl ex and Cynthia's Garchomp ex. Detected exactly like the rest --
    # their line on the opposing ACTIVE, on their BENCH or in their DISCARD.
    op_is_marnie_deck = False
    op_is_cynthia_deck = False
    # Iron Thorns ex on the opposing FIELD (P1.4 plan B): even if it is not the active
    # yet, its presence announces the ability lock -> the plan pivots to
    # the attackers WITHOUT an ability with a Rule Box (Tapu Bulu, the Meganium line).
    op_is_iron_thorns_deck = False
    op_active_is_dunsparce = False
    if op_state.active and op_state.active[0] is not None:
        op_active_id = op_state.active[0].id
        if op_active_id in EX_IMMUNE_IDS:
            op_has_ex_immune_active = True
        if op_active_id in ABILITY_IMMUNE_IDS:
            op_has_ability_immune_active = True
        if op_active_id in (Cornerstone_Mask_Ogerpon_ex,
                            Cornerstone_Mask_Ogerpon):
            AGENT_STATE.op_is_cornerstone_deck = True
        if op_active_id == Crustle_Fighting:
            op_has_sturdy_crustle = True
        if op_active_id in (Crustle_Grass, Crustle_Fighting, Dwebble_Grass, Dwebble_Fighting):
            AGENT_STATE.op_is_crustle_deck = True
        if op_active_id == Mega_Kangaskhan_ex:
            AGENT_STATE.op_has_mega_kangaskhan = True
        if op_active_id == Froslass:
            op_has_froslass = True
        if op_active_id == Munkidori:
            op_has_munkidori = True
        if op_active_id == Dragapult_ex:
            op_has_dragapult = True
            op_bench_snipe_threat = True
        if op_active_id == Typhlosion:
            op_has_typhlosion = True
        if op_active_id in (Cyndaquil, Quilava):
            op_has_ethan_preevo = True
        if op_active_id == Grimmsnarl_ex:
            op_bench_snipe_threat = True
        if op_active_id == Mega_Starmie_ex and len(op_state.active[0].energies) >= 1:

            op_has_mega_starmie_active = True
            op_bench_snipe_threat = True
        if op_active_id in MEGA_STARMIE_LINE_IDS:
            AGENT_STATE.op_is_starmie_deck = True
        if op_active_id == Latias_ex:
            op_has_latias_ex = True
        if op_active_id in (Riolu, Mega_Lucario_ex):
            op_is_lucario_deck = True
        if op_active_id in (Cubchoo, Beartic):
            op_is_cubchoo_deck = True
        if op_active_id in (Hops_Phantump, Hops_Trevenant):
            op_is_hop_deck = True
        if op_active_id in (Comfey, Bramblin, Brambleghast):
            op_is_comfey_deck = True
        if op_active_id in DUNSPARCE_IDS:
            op_active_is_dunsparce = True

        op_active_data = card_table.get(op_active_id)
        if op_active_data and op_active_data.energyType == EnergyType.FIRE:
            op_is_fire_deck = True

        if op_active_id in (Teal_Mask_Ogerpon_ex, Hydrapple_ex, Dipplin, Applin, Meganium, Bayleef, Chikorita):
            op_is_mirror = True

        if op_active_id == Mega_Greninja_ex:
            op_is_greninja_deck = True
            op_bench_snipe_threat = True
        if op_active_id in (Slowpoke, Slowking):
            op_is_slowking_deck = True
            op_is_control_deck = True
        if op_active_id in (Weedle, Kakuna, Beedrill):
            op_is_beedrill_deck = True
            op_is_aggro_deck = True
        if op_active_id in (Chewtle, Drednaw):
            op_is_drednaw_deck = True
        if op_active_id == Sylveon or op_active_id in EEVEE_IDS:
            op_is_sylveon_deck = True
            AGENT_STATE.op_is_crustle_deck = True
        if op_active_id == Eevee_PRE_ex:
            op_has_non_immune_eevee_ex = True
        if op_active_id in (Abra, Kadabra, Alakazam_ex):
            op_is_alakazam_deck = True
        if op_active_id in (Ralts, Kirlia, Gardevoir_ex):
            op_is_gardevoir_deck = True
        if op_active_id in (Zorua_N, Zoroark_N):
            op_is_zoroark_deck = True
        if op_active_id in (Raging_Bolt_ex, Lugia_VSTAR):
            op_is_aggro_deck = True
        if op_active_id == Raging_Bolt_ex:
            op_is_raging_bolt_deck = True
        if op_active_id in (Snover, Mega_Abomasnow_ex):
            op_is_abomasnow_deck = True
        if op_active_id == Iron_Thorns_ex:
            op_is_iron_thorns_deck = True
        if op_active_id in MARNIE_LINE_IDS:
            op_is_marnie_deck = True
        if op_active_id in CYNTHIA_LINE_IDS:
            op_is_cynthia_deck = True
    for idx, pokemon in enumerate(op_state.bench):
        if pokemon is not None:
            if pokemon.id in EX_IMMUNE_IDS:
                op_has_ex_immune_bench = True
            if pokemon.id in (Cornerstone_Mask_Ogerpon_ex,
                              Cornerstone_Mask_Ogerpon):
                AGENT_STATE.op_is_cornerstone_deck = True
            if pokemon.id == Crustle_Fighting:
                op_has_sturdy_crustle = True
            if pokemon.id in (Dwebble_Grass, Dwebble_Fighting):
                op_has_dwebble_bench = True
                AGENT_STATE.op_is_crustle_deck = True
            if pokemon.id in (Crustle_Grass, Crustle_Fighting):
                AGENT_STATE.op_is_crustle_deck = True
                op_has_crustle_bench = True
            if pokemon.id == Mega_Kangaskhan_ex:
                AGENT_STATE.op_has_mega_kangaskhan = True
            if pokemon.id in (Comfey, Bramblin, Brambleghast):
                op_is_comfey_deck = True
            if pokemon.id == Froslass:
                op_has_froslass = True
            if pokemon.id == Snorunt:
                op_has_snorunt_bench = True
            if pokemon.id == Munkidori:
                op_has_munkidori = True
            if pokemon.id == Dragapult_ex:
                op_has_dragapult = True
                op_bench_snipe_threat = True
            if pokemon.id == Typhlosion:
                op_has_typhlosion = True
            if pokemon.id in (Cyndaquil, Quilava):
                op_has_ethan_preevo = True
            if pokemon.id == Grimmsnarl_ex:
                op_bench_snipe_threat = True
            if pokemon.id in (Dreepy, Drakloak):
                op_has_dreepy_line = True
            if pokemon.id == Latias_ex:
                op_has_latias_ex = True
            if pokemon.id in (Riolu, Mega_Lucario_ex):
                op_is_lucario_deck = True
            if pokemon.id in (Cubchoo, Beartic):
                op_is_cubchoo_deck = True
            if pokemon.id in (Hops_Phantump, Hops_Trevenant):
                op_is_hop_deck = True
            if pokemon.id in MEGA_STARMIE_LINE_IDS:
                AGENT_STATE.op_is_starmie_deck = True
            if pokemon.id == Iron_Thorns_ex:
                op_is_iron_thorns_deck = True

            bench_data = card_table.get(pokemon.id)
            if bench_data and bench_data.energyType == EnergyType.FIRE:
                op_is_fire_deck = True

            if pokemon.id in (Teal_Mask_Ogerpon_ex, Hydrapple_ex, Dipplin, Applin, Meganium, Bayleef, Chikorita):
                op_is_mirror = True

            if pokemon.id in (Mega_Greninja_ex,):
                op_is_greninja_deck = True
                op_bench_snipe_threat = True
            if pokemon.id in (Slowpoke, Slowking):
                op_is_slowking_deck = True
                op_is_control_deck = True
            if pokemon.id in (Weedle, Kakuna, Beedrill):
                op_is_beedrill_deck = True
                op_is_aggro_deck = True
            if pokemon.id in (Chewtle, Drednaw):
                op_is_drednaw_deck = True
            if pokemon.id == Sylveon or pokemon.id in EEVEE_IDS:
                op_is_sylveon_deck = True
                AGENT_STATE.op_is_crustle_deck = True
                if pokemon.id in EEVEE_IDS:
                    op_has_eevee_bench = True
                if pokemon.id == Eevee_PRE_ex:
                    op_has_non_immune_eevee_ex = True
            if pokemon.id in (Duskull, Dusclops, Dusknoir):
                op_is_dragapult_dusknoir = op_has_dragapult or op_has_dreepy_line
            if pokemon.id in (Abra, Kadabra, Alakazam_ex):
                op_is_alakazam_deck = True
            if pokemon.id in (Ralts, Kirlia, Gardevoir_ex):
                op_is_gardevoir_deck = True
            if pokemon.id in (Zorua_N, Zoroark_N):
                op_is_zoroark_deck = True
            if pokemon.id in (Raging_Bolt_ex, Lugia_VSTAR):
                op_is_aggro_deck = True
            if pokemon.id == Raging_Bolt_ex:
                op_is_raging_bolt_deck = True
            if pokemon.id in (Snover, Mega_Abomasnow_ex):
                op_is_abomasnow_deck = True
            if pokemon.id in MARNIE_LINE_IDS:
                op_is_marnie_deck = True
            if pokemon.id in CYNTHIA_LINE_IDS:
                op_is_cynthia_deck = True

    # Archetype inference from the opponent's DISCARD (July 2026 audit,
    # suggestion 7): detection by Pokemon IN PLAY arrives late against
    # hidden lines; one archetype Pokemon in the discard identifies the
    # deck 2-3 turns earlier and switches the preparations on in time (bench/Xerosic
    # reservation vs Alakazam, the Ogerpon-only plan vs Comfey, the whitelist vs
    # Cubchoo...). Only STRATEGIC deck flags are inferred; the "wall in play" flags
    # (Crustle/Sylveon/Cornerstone: they redirect the attack RIGHT NOW) and
    # the positional `op_has_*` ones stay as they are (they depend on the board).
    for _dc in (op_state.discard or []):
        _dcid = getattr(_dc, 'id', 0)
        if _dcid in (Abra, Kadabra, Alakazam_ex):
            op_is_alakazam_deck = True
        elif _dcid in (Comfey, Bramblin, Brambleghast):
            op_is_comfey_deck = True
        elif _dcid in (Riolu, Mega_Lucario_ex):
            op_is_lucario_deck = True
        elif _dcid in (Hops_Phantump, Hops_Trevenant):
            op_is_hop_deck = True
        elif _dcid in (Cubchoo, Beartic):
            op_is_cubchoo_deck = True
        elif _dcid in (Ralts, Kirlia, Gardevoir_ex):
            op_is_gardevoir_deck = True
        elif _dcid in (Zorua_N, Zoroark_N):
            op_is_zoroark_deck = True
        elif _dcid in (Slowpoke, Slowking):
            op_is_slowking_deck = True
            op_is_control_deck = True
        elif _dcid == Raging_Bolt_ex:
            op_is_aggro_deck = True
            op_is_raging_bolt_deck = True
        elif _dcid in (Snover, Mega_Abomasnow_ex):
            op_is_abomasnow_deck = True
        elif _dcid in MEGA_STARMIE_LINE_IDS:
            AGENT_STATE.op_is_starmie_deck = True
        elif _dcid in MARNIE_LINE_IDS:
            op_is_marnie_deck = True
        elif _dcid in CYNTHIA_LINE_IDS:
            op_is_cynthia_deck = True
        elif _dcid == Lugia_VSTAR:
            op_is_aggro_deck = True
        elif _dcid in (Cornerstone_Mask_Ogerpon_ex, Cornerstone_Mask_Ogerpon):
            # A matchup PLAN flag (the Meganium line as a priority, a whitelist
            # with Tapu Bulu): seeing it in the discard identifies the deck. The
            # POSITIONAL wall flag (op_has_ability_immune_active) still
            # depends only on the board.
            AGENT_STATE.op_is_cornerstone_deck = True

    # Eevee ex (id 249) is NOT the Sylveon wall: it is an attackable ex. If the opponent
    # follows the Eevee ex line and there is no real immune wall (Sylveon) in
    # play, we revoke the anti-wall strategy and go back to the ex strategy:
    # we attack that ex with our ex and evolve Dipplin -> Hydrapple ex.
    if op_has_non_immune_eevee_ex and not (op_has_ex_immune_active or op_has_ex_immune_bench):
        AGENT_STATE.op_is_crustle_deck = False
        op_is_sylveon_deck = False

    # Projected damage of the opposing snipe on ONE Pokemon of our bench per turn
    # (see OP_BENCH_SNIPE_DAMAGE). The MAXIMUM among the snipers the
    # opponent has IN PLAY is taken: it is the drip that has to be survived every turn.
    AGENT_STATE._op_bench_snipe_dmg = 0
    if op_bench_snipe_threat:
        for _bs_pk in ([_active_of(op_state)] + list(op_state.bench or [])):
            if _bs_pk is None:
                continue
            if _bs_pk.id in OP_BENCH_SNIPE_DAMAGE:
                AGENT_STATE._op_bench_snipe_dmg = max(
                    AGENT_STATE._op_bench_snipe_dmg, OP_BENCH_SNIPE_DAMAGE[_bs_pk.id])
        if AGENT_STATE._op_bench_snipe_dmg == 0:
            AGENT_STATE._op_bench_snipe_dmg = OP_BENCH_SNIPE_DEFAULT

    # --- The other two legs of THE GIFT WINDOW -----------------------------
    # They are armed by the PRESENCE of the pieces on the field (Froslass / Munkidori), not
    # by the complete matchup: any deck that plays them spreads the same
    # drip. See the constants block of the same name.
    _n_froslass = 0
    _n_munkidori_cargado = 0
    _has_dry_munkidori = False
    _op_counters_en_mesa = 0
    for _vr_pk in ([_active_of(op_state)] + list(op_state.bench or [])):
        if _vr_pk is None:
            continue
        _op_counters_en_mesa += max(0, (_vr_pk.maxHp or 0) - (_vr_pk.hp or 0))
        if _vr_pk.id == Froslass:
            _n_froslass += 1
        elif _vr_pk.id == Munkidori:
            if len(_vr_pk.energies or []) >= 1:
                _n_munkidori_cargado += 1
            else:
                _has_dry_munkidori = True

    AGENT_STATE._op_chip_per_round = (FREEZING_SHROUD_COUNTER * _n_froslass
                          * CHECKUPS_PER_ROUND)

    # A Munkidori WITHOUT energy that is already on the field is worth one more activation: the
    # opponent still has their attachment for the turn. Ignoring it underestimated exactly the turn
    # that decides (game 2 turn 10: the opponent put a Munkidori down, attached a
    # Darkness to it and with the two activations killed the benched Ogerpon at 80 HP).
    _n_activaciones = _n_munkidori_cargado + (1 if _has_dry_munkidori else 0)
    # Adrena-Brain only moves counters that ALREADY exist on their board, but before
    # the opponent plays there is one more checkup (the one at the end of OUR turn)
    # which reloads 10 per Froslass onto each Munkidori -- they all have an
    # ability. Without that term the ceiling is underestimated exactly on the turn in which
    # the opponent finishes us off.
    _op_counters_disponibles = (
        _op_counters_en_mesa
        + FREEZING_SHROUD_COUNTER * _n_froslass * _n_activaciones)
    AGENT_STATE._op_movable_cap = ADRENA_BRAIN_MOVE * _n_activaciones
    AGENT_STATE._op_movable_ammo = _op_counters_disponibles
    AGENT_STATE._op_movable_dmg = min(AGENT_STATE._op_movable_cap,
                          _op_counters_disponibles)

    # PRIZE MISMATCH (user): matchups whose attacker ONE-SHOTS any
    # of our ex -> Raging Bolt (Bellowing Thunder) and Mega Abomasnow ex. The
    # rule: whenever our active is an ex that canNOT knock out the opposing
    # active this turn, put a ONE-prize body in front (put a non-ex basic down
    # from hand and/or retreat the ex to promote it) -- if we are knocked out they concede 1
    # prize and not 2, and their deck (all 2-3 prize ex) needs big KOs to
    # win in time. EXCEPTION (user, registro_002 vs Mega Abomasnow ex): the rule
    # does NOT apply on OUR first turn going FIRST -- on that first turn we do not
    # attack and the opponent cannot knock us out on their next turn yet, so
    # sacrificing early development only slows us down. If we go SECOND (our
    # first turn is turn 2) or on any later turn, it DOES apply.
    _prize_mismatch_matchup = (
        (op_is_raging_bolt_deck or op_is_abomasnow_deck)
        and not (state.turn == 1 and AGENT_STATE.we_go_first))

    total_grass = count_total_grass_energy(my_state)

    # Wall pivot to Hydrapple ex WITHOUT a KO (user, log 85856881 step 127, vs Mega
    # Lucario ex, game WON). Unlike `_teal_wall_pivot` (an active that
    # canNOT attack), here the active Teal Mask Ogerpon ex CAN attack, but
    # its Myriad Leaf Shower does NOT knock the opponent out and the Mega Lucario ex finishes it
    # next turn (Mega Brave, 270 > 210 HP). If on the bench there is a Hydrapple
    # ex at full HP (a 330 HP wall) that SURVIVES the opponent's best hit and
    # can attack (>=2 effective), the correct line is to RETREAT the fragile
    # Ogerpon and bring up the wall: it takes the hit and keeps applying pressure (Syrup Storm
    # 330), instead of attacking with the Ogerpon, which would die giving away 2 prizes. The
    # only way to retreat in this engine is to choose PASS in the main menu
    # (it exposes the retreat prompt, ctx=30); that is why further down we point the plan
    # at the benched Hydrapple to SUPPRESS the option of attacking with the Ogerpon.
    # Limited to Mega Lucario (a fixed, high opposing finisher).
    _hydra_wall_pivot = False
    _hwp_active = my_state.active[0] if my_state.active else None
    _hwp_op_active = _active_of(op_state)
    if (op_is_lucario_deck and active_ko_likely
            and _hwp_active is not None
            and _hwp_active.id == Teal_Mask_Ogerpon_ex
            and len(_hwp_active.energies) >= 3
            and _hwp_op_active is not None):
        _hwp_op_hp = _hwp_op_active.hp or 0
        _hwp_oger_dmg = 30 + 30 * (
            len(_hwp_active.energies) + len(_hwp_op_active.energies))
        _hwp_oger_ko = (_hwp_op_hp > 0 and _hwp_oger_dmg >= _hwp_op_hp)
        _hwp_ret_phys = _physical_energy(len(_hwp_active.energies))
        _hwp_ret_cost = RETREAT_COST.get(_hwp_active.id, 1)
        if not _hwp_oger_ko and _hwp_ret_phys >= _hwp_ret_cost:
            _hwp_wall_hit = 30 + 30 * max(
                0, total_grass - _retreat_grass_units(_hwp_ret_cost))
            for _hwp_bp in (my_state.bench or []):
                if (_hwp_bp is not None and _hwp_bp.id == Hydrapple_ex
                        and _hwp_bp.hp >= (_hwp_bp.maxHp or 0)
                        and len(_hwp_bp.energies) * _grass_mult() >= 2
                        and (_hwp_bp.hp or 0) > _op_best_damage_vs(_hwp_bp)
                        and not _bench_cashable_after_retreat(
                            _hwp_active, _hwp_op_active, _hwp_wall_hit)):
                    _hydra_wall_pivot = True
                    break

    # Generalisation of the wall pivot (user, registro_006 step 84, vs Archaludon
    # ex, LOST): the same pattern applies against ANY opponent, not only Mega
    # Lucario. If the active Teal Mask Ogerpon ex CAN attack (>=3 energy)
    # but its Myriad Leaf Shower does NOT knock out the opposing active, and the ATTACK of the
    # opposing active KNOCKS OUT our Ogerpon next turn but a healthy benched
    # Hydrapple ex (a 330 wall) SURVIVES that hit and can attack (Syrup Storm > 0),
    # the correct line is to RETREAT the doomed Ogerpon and promote the wall (it survives
    # and keeps applying pressure) instead of attacking with the fragile Ogerpon, which would die
    # giving away 2 prizes. Unlike the Mega Lucario branch (limited by a deck
    # flag + the `active_ko_likely` heuristic, because it did not read the opposing damage), here
    # we require the REAL opposing finisher (`_op_active_attack_damage_to`, which resolves
    # the attack via attack_table) both to condemn the active and to validate
    # that the wall survives. If the opposing attack cannot be read (damage None),
    # the helper gives 0 and the pivot does NOT fire (conservative). Alakazam's Powerful Hand
    # IS modelled (20 x (opposing hand + 2), passing op_hand_count):
    # vs Alakazam this pivot can now fire; if at the same time there is a body
    # worth 1 prize that knocks out (_alakazam_pivot_1prize), the RETREAT fires
    # anyway and the PROMOTION is resolved by the `op_is_alakazam_deck` block of
    # _best_promote_card (1 prize > wall), which goes LAST in that chain.
    if (not _hydra_wall_pivot and _hwp_active is not None
            and _hwp_active.id == Teal_Mask_Ogerpon_ex
            and len(_hwp_active.energies) >= 3
            and _hwp_op_active is not None):
        _gwp_op_hp = _hwp_op_active.hp or 0
        _gwp_oger_dmg = _our_effective_damage(
            _hwp_active, _hwp_op_active,
            30 + 30 * (len(_hwp_active.energies) + len(_hwp_op_active.energies)),
            AGENT_STATE.meganium_in_play, neutralization_zone_active)
        _gwp_oger_ko = (_gwp_op_hp > 0 and _gwp_oger_dmg >= _gwp_op_hp)
        _gwp_ret_phys = _physical_energy(len(_hwp_active.energies))
        _gwp_ret_cost = RETREAT_COST.get(_hwp_active.id, 1)
        # Passing the opposing hand enables the Powerful Hand projection
        # (20 x (hand+2)) -- without it the helper gave 0 vs Alakazam and this
        # pivot never fired in that matchup (anti-Alakazam suggestion 1).
        _gwp_op_hand = getattr(op_state, 'handCount', None)
        _gwp_op_dmg_active = _op_active_attack_damage_to(
            _hwp_op_active, _hwp_active, _gwp_op_hand)
        if (not _gwp_oger_ko and _gwp_ret_phys >= _gwp_ret_cost
                and _gwp_op_dmg_active >= (_hwp_active.hp or 0)):
            for _gwp_bp in (my_state.bench or []):
                if (_gwp_bp is not None and _gwp_bp.id == Hydrapple_ex
                        and _gwp_bp.hp >= (_gwp_bp.maxHp or 0)
                        and len(_gwp_bp.energies) * _grass_mult() >= 2
                        and (_gwp_bp.hp or 0) > _op_active_attack_damage_to(
                            _hwp_op_active, _gwp_bp, _gwp_op_hand)):
                    _gwp_wall_dmg = _our_effective_damage(
                        _gwp_bp, _hwp_op_active,
                        30 + 30 * max(0, total_grass
                                      - _retreat_grass_units(_gwp_ret_cost)),
                        AGENT_STATE.meganium_in_play, neutralization_zone_active)
                    # THE HIDDEN EX HAS TO SURVIVE DOWN THERE (user, registro_012
                    # step 112 vs Marnie's Grimmsnarl ex). Putting up the wall
                    # only denies prizes if the ex we tuck away on the bench is
                    # out of reach; when they can cash it there, the retreat pays
                    # a Grass and 180 on the wall to concede the SAME two prizes
                    # they were going to take from the front. Staying at least
                    # spends their attack on a corpse and keeps the wall whole.
                    if (_gwp_wall_dmg > 0
                            and not _bench_cashable_after_retreat(
                                _hwp_active, _hwp_op_active, _gwp_wall_dmg)):
                        _hydra_wall_pivot = True
                        break

    # The same guard for the OTHER wall pivot, the one whose active canNOT
    # attack (`_teal_wall_pivot`, decided much further up, before the gift
    # window of this turn has been measured -- hence the cancellation here and
    # not a condition up there). Fixing one branch of a pair and leaving its
    # twin alone is how this very turn was lost, so both walls answer the same
    # question: does the ex survive on the bench?
    if _teal_wall_pivot:
        _twp_op_active = _active_of(op_state)
        _twp_active = my_state.active[0] if my_state.active else None
        _twp_grass_after = max(
            0, total_grass - _retreat_grass_units(
                RETREAT_COST.get(getattr(_twp_active, 'id', 0), 1)))
        _twp_wall_hit = 0
        for _twp_bp in (my_state.bench or []):
            if (_twp_bp is not None and _twp_bp.id == Hydrapple_ex
                    and len(_twp_bp.energies) * _grass_mult() >= 2):
                _twp_wall_hit = _our_effective_damage(
                    _twp_bp, _twp_op_active, 30 + 30 * _twp_grass_after,
                    AGENT_STATE.meganium_in_play, neutralization_zone_active)
                break
        if _bench_cashable_after_retreat(
                _twp_active, _twp_op_active, _twp_wall_hit):
            _teal_wall_pivot = False

    # And the same question of the deck-agnostic twin, plus the exclusion its
    # older brother `_doomed_ex_sac_pivot` already carries. Both live here and
    # not up in the flag because `op_has_ex_immune_active` is only known after
    # the opposing board has been read.
    #
    #   * does the body we hide survive down there? (the shared guard; the
    #     promotion has not been decided yet, so our damage is read as 0 --
    #     the conservative side of `_movable_dmg_after_our_hit`, which counts
    #     no counters we have not loaded onto their board);
    #
    #   * is the opposing active a wall that immunises our ex? There the
    #     retreat is not this rule's business: the matchup has its own logic
    #     (`_ex_stuck_promo_ready` / `_nonex_active_hits_wall`), which waits
    #     for the non-ex that DOES hit the wall to be READY before spending
    #     the retreat. Firing first at 6450 pre-empted it and paid the fee to
    #     promote a body that could not attack either -- measured -3.7 and
    #     -2.5 points vs the crustle bot (n=400 per arm, two runs) while the
    #     other matchups were flat.
    if _doomed_mute_pivot and (
            op_has_ex_immune_active
            or _bench_cashable_after_retreat(
                my_state.active[0] if my_state.active else None,
                _active_of(op_state))):
        _doomed_mute_pivot = False

    # Feza -> Hydrapple ex wall vs Mega Lucario (user, log 86342087 step 130,
    # WE LOST): if the ACTIVE is a Fezandipiti ex WEAK to Fighting that will be
    # KNOCKED OUT by Mega Lucario ex next turn (Mega Brave 270 x2 = 540,
    # 2 prizes) and on the bench there is a healthy Hydrapple ex (a 330 wall that SURVIVES
    # the opponent's hit, weak to {R} not {F}), the correct line is NOT to charge and
    # attack with the doomed Feza (it dies giving away 2 prizes) but to charge the
    # Hydrapple (see energy_score), RETREAT the Feza (cost 1) and promote the wall
    # to attack. `_feza_lucario_wall` enables that charge; here, once the
    # Hydrapple is ready (>=2 effective), we switch on the wall pivot to
    # suppress the Feza's attack and expose the retreat (the same mechanism as the
    # Ogerpon pivot above). The Feza has to be able to retreat already (physical
    # energy >= its retreat cost of 1).
    #
    # THE RULE READ THE FLAG THAT CANNOT SEE MEGA LUCARIO (user, registro_008
    # step 123, WE LOST). This branch was gated on `active_ko_likely`, which is
    # built on `_op_best_damage_vs` -- the helper that resolves `card.attacks`
    # entries as objects when they are ints, and therefore returns 0 for EVERY
    # opposing attack (see `_op_active_attack_damage_to`'s docstring). Against
    # the very card the rule names it read 0 damage on a body its own comment
    # prices at 540, so the whole line -- charge the wall, retreat, promote --
    # never fired once: with the Feza in front of a Mega Lucario ex and a bare
    # Hydrapple ex on the bench, the turn routed the Ripening Charge INTO the
    # doomed Feza and spent it on a Cruel Arrow. One prize for us (6->5), two for
    # them on the reply (3->1), and the 330 wall that eats Mega Brave whole
    # (270 < 330) still sitting on the bench.
    #
    # So the condemnation is asked of the projector that reads the attack table,
    # exactly as its Ogerpon twin twenty lines above already asks it -- the same
    # call, the same conservative 0 when the attack cannot be read, no `scaled`
    # (Mega Brave prints its real 270; the opt-in scale is a different argument
    # and belongs to the turn plan). `active_ko_likely` is kept as an OR so no
    # board that fired before stops firing.
    #
    # And the guard that was supposed to check the wall gets teeth in the same
    # motion: `(hp or 0) > _op_best_damage_vs(...)` was `330 > 0`, i.e. nothing.
    # It now also asks the real projection, which is what makes "the wall
    # SURVIVES" a fact instead of a hope.
    _feza_lucario_wall = False
    _flw_op_hand = getattr(op_state, 'handCount', None)
    if (op_is_lucario_deck
            and _hwp_active is not None
            and _hwp_active.id == Fezandipiti_ex
            and _hwp_op_active is not None
            and (active_ko_likely
                 or _op_active_attack_damage_to(
                     _hwp_op_active, _hwp_active, _flw_op_hand)
                 >= (_hwp_active.hp or 0))):
        _flw_ret_phys = _physical_energy(len(_hwp_active.energies))
        _flw_ret_cost = RETREAT_COST.get(_hwp_active.id, 1)
        if _flw_ret_phys >= _flw_ret_cost:
            for _flw_bp in (my_state.bench or []):
                if (_flw_bp is not None and _flw_bp.id == Hydrapple_ex
                        and _flw_bp.hp >= (_flw_bp.maxHp or 0)
                        and (_flw_bp.hp or 0) > max(
                            _op_best_damage_vs(_flw_bp),
                            _op_active_attack_damage_to(
                                _hwp_op_active, _flw_bp, _flw_op_hand))):
                    _feza_lucario_wall = True
                    if len(_flw_bp.energies) * _grass_mult() >= 2:
                        # Hydrapple already charged: switch on the wall pivot to
                        # retreat the Feza and promote the wall (it reuses the plan.attacker
                        # reassignment block further down).
                        #
                        # The shared guard of both walls: hiding the Feza only
                        # denies the two prizes if it SURVIVES on the bench. Its
                        # twin above already asks it, and "fixing one branch of a
                        # pair and leaving its twin alone is how this very turn
                        # was lost".
                        if not _bench_cashable_after_retreat(
                                _hwp_active, _hwp_op_active):
                            _hydra_wall_pivot = True

    # FRAGILE Hydrapple ex pivot: retreat the active with low HP and promote the
    # healthy one (user, log 86027506 step 81, vs Abomasnow, WON). If the ACTIVE is a
    # Hydrapple ex with low HP (at risk of a KO) and on the BENCH there is ANOTHER
    # Hydrapple ex at (almost) full HP, which SURVIVES the opponent's best hit and is
    # ready for a LETHAL Syrup Storm, the correct line is to RETREAT the fragile one to
    # protect it (if it stays active they knock it out next turn = 2 prizes) and
    # BRING UP the healthy one to finish (the same KO, but from the healthy body). The engine only
    # offers a retreat if the active has PHYSICAL energy >= its retreat cost
    # (3 for Hydrapple ex); that is why this turn's energy (the manual attachment
    # + Ripening Charge) has to be ROUTED to the fragile ACTIVE until that cost is reached
    # instead of leaving it on the benched Hydrapple (which is already charged). This flag
    # enables that charge in `energy_score`; the later retreat+promotion is covered by
    # `_hydra_lethal_promote` (a retreat with score 9000) once can_switch becomes
    # True.
    _hydra_fragile_pivot = False
    _hfp_active = my_state.active[0] if my_state.active else None
    _hfp_opa = _active_of(op_state)
    if (_hfp_active is not None and _hfp_active.id == Hydrapple_ex
            and _hfp_opa is not None and (_hfp_opa.hp or 0) > 0
            and (active_ko_likely
                 or (_hfp_active.hp or 0) <= (_hfp_active.maxHp or 1) * 0.5)):
        _hfp_rc = RETREAT_COST.get(Hydrapple_ex, 3)
        _hfp_phys = _physical_energy(len(_hfp_active.energies))
        if _hfp_phys < _hfp_rc:
            for _hfp_bp in (my_state.bench or []):
                if (_hfp_bp is not None and _hfp_bp.id == Hydrapple_ex
                        and (_hfp_bp.hp or 0) > (_hfp_active.hp or 0)
                        and (_hfp_bp.hp or 0) > _op_best_damage_vs(_hfp_bp)
                        and len(_hfp_bp.energies) * _grass_mult() >= 2):
                    _hfp_bdmg = _our_effective_damage(
                        _hfp_bp, _hfp_opa, 30 + 30 * total_grass,
                        AGENT_STATE.meganium_in_play, neutralization_zone_active)
                    if _hfp_bdmg > 0 and _hfp_bdmg >= (_hfp_opa.hp or 0):
                        _hydra_fragile_pivot = True
                        break

    _conf_active = my_state.active[0] if my_state.active else None
    # The wall that is immune to ex (Crustle/Sylveon) or to abilities (Cornerstone) only vetoes
    # promoting an ex WHEN IT IS THE OPPOSING ACTIVE: that is who the ex would attack
    # after the confusion pivot. With the wall on the opposing BENCH and an ATTACKABLE Pokemon
    # in the active spot (e.g. a Munkidori in a Crustle deck), our Ogerpon
    # ex DOES knock it out, so it has to count as a valid attacker for the pivot (user,
    # registro_006 step 64 vs Crustle: the active Dipplin at 10 HP and CONFUSED
    # attacked -- risking the self-KO if the coin fails -- instead of retreating
    # (Meganium makes its Grass pay the retreat cost of 2) and bringing up
    # the charged Ogerpon ex that knocks out the Munkidori). The DECK flags
    # (op_is_crustle_deck/op_is_cornerstone_deck) and the bench one
    # (op_has_ex_immune_bench) are too broad: they hold even if the active is
    # attackable, and they vetoed the winning pivot.
    _conf_ex_immune_match = (op_has_ex_immune_active or op_has_ability_immune_active)

    def _conf_can_attack_pkmn(_p):
        if _p is None:
            return False
        _e = len(_p.energies)
        _eff = _e * _grass_mult()
        if _p.id == Hydrapple_ex:
            return _eff >= 2
        if _p.id == Dipplin:
            return _e >= 1
        if _p.id == Teal_Mask_Ogerpon_ex:
            return _eff >= 3
        if _p.id == Tapu_Bulu:
            return _eff >= 4
        if _p.id == Pinsir:
            return _eff >= 2
        if _p.id == Fezandipiti_ex:
            return _eff >= 3
        return False

    def _conf_is_matchup_attacker(_pid):
        if _conf_ex_immune_match:
            return _pid in (Tapu_Bulu, Dipplin, Pinsir)
        return _pid in (Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex,
                        Tapu_Bulu, Pinsir, Fezandipiti_ex)

    _conf_bench_attacker_ready = any(
        bp is not None and _conf_is_matchup_attacker(bp.id) and _conf_can_attack_pkmn(bp)
        for bp in (my_state.bench or []))
    _conf_bench_attacker_body = any(
        bp is not None and _conf_is_matchup_attacker(bp.id)
        for bp in (my_state.bench or []))
    _conf_active_can_retreat = False
    if is_confused and _conf_active is not None:
        # Meganium's Wild Growth doubles every basic Grass energy, so
        # the effective energy can cover the retreat cost with fewer cards
        # (e.g. a Meganium with 1 energy = {G}{G} -> it pays its retreat cost of 2).
        _conf_ret_eff = len(_conf_active.energies) * _grass_mult()
        _conf_active_can_retreat = (
            _conf_ret_eff >= RETREAT_COST.get(_conf_active.id, 1))
    _conf_active_can_attack = bool(is_confused and _conf_can_attack_pkmn(_conf_active))
    _conf_should_retreat = bool(
        is_confused and _conf_active_can_retreat and _conf_bench_attacker_ready)
    _conf_should_attack = bool(
        is_confused and not _conf_bench_attacker_ready and _conf_active_can_attack)

    can_attack = False
    # The one-prize wall of our first turn. Its four flags are COMPUTED much
    # further down (they need the whole board read, `can_attack` included), but
    # `_energy_score_base` is a closure over this scope and can be called
    # before that point: bound here so an early call reads "off" instead of
    # tripping over an unbound name.
    _ft_wall_in_hand = None
    _ft_wall_body = None
    _ft_wall_pivot = False
    _ft_wall_promote = False
    _ft_wall_charge_active = False
    # Hiding the ex behind a one-prize body on our first turn. Same reason for
    # being bound here as the five above: they are computed once the whole
    # board is read, and anything that runs before that point has to see them
    # switched off.
    _opening_sac_wall_in_hand = None
    _opening_sac_pivot = False
    _opening_sac_promote = False
    _opening_sac_charge_active = False
    _opening_sac_needs_body = False
    _active_cant_attack_this_turn = False
    _hydra_pivot_active = False
    _tapu_sac_pivot = False
    _tapu_sac_enable_retreat = False
    _festival_sac_pivot = False
    _festival_lead_pays_us_now = False
    _prize_denial_pivot = False

    _bo_active_attack_sufficient = False

    can_switch = False
    can_op_switch = False
    has_switch_card = False
    if context == SelectContext.MAIN:
        can_switch = False
        can_op_switch = False
        for o in select.option:
            if o.type == OptionType.PLAY:
                card = get_card(obs, AreaType.HAND, o.index, my_index)
                if card is not None:
                    if card.id == Boss_Orders:
                        can_op_switch = True
            elif o.type == OptionType.RETREAT:
                can_switch = True
            elif o.type == OptionType.ATTACK:
                can_attack = True

        has_switch_card = False
        for o in select.option:
            if o.type == OptionType.PLAY:
                card = get_card(obs, AreaType.HAND, o.index, my_index)
                if card is not None and card.id == 1123:
                    can_switch = True
                    has_switch_card = True

        my_cards = [my_state.active[0]] if my_state.active else []
        for pokemon in my_state.bench:
            if pokemon is not None:
                my_cards.append(pokemon)
        op_cards = [op_state.active[0]] if op_state.active else []
        for pokemon in op_state.bench:
            if pokemon is not None:
                op_cards.append(pokemon)

        # Does the ACTIVE already knock out the opposing active with the energy it ALREADY has?
        # It is used as a guard for the "extra Grass via Night Stretcher" projection
        # below: if the active finishes, the recovered Grass unlocks
        # no new KO and the Night Stretcher will NOT be played
        # (`_ns_e_finisher_via_promotion` carries the same guard). Without this mirror
        # the plan would project a bench KO that depends on a card nobody
        # is going to play and would veto the active's attack.
        _plan_act_kos_now = False
        _pakn_act = my_cards[0] if my_cards else None
        _pakn_op = op_cards[0] if op_cards else None
        if _pakn_act is not None and _pakn_op is not None:
            _pakn_e = len(_pakn_act.energies)
            _pakn_base = _attacker_base_damage(
                _pakn_act.id, _pakn_op, _pakn_e * _grass_mult(),
                grass_scale=total_grass, teal_self_energy=_pakn_e,
                bench_count=bench_count)
            _plan_act_kos_now = (
                _pakn_base > 0
                and _our_effective_damage(
                    _pakn_act, _pakn_op, _pakn_base, AGENT_STATE.meganium_in_play,
                    neutralization_zone_active) >= (_pakn_op.hp or 0))

        # An opponent with NO Pokemon on the bench cannot promote a replacement if we
        # knock their active out: that KO WINS the game (a game rule), regardless
        # of the prize count. It is used to (a) recognise the winning
        # finisher with the active and (b) stop the mismatch pivots from
        # diverting us from it (user, registro_016 vs Crustle).
        _op_bench_empty = not any(
            b is not None for b in (op_state.bench or []))
        _active_win_plan = None

        if state.turn >= 2 and len(my_cards) > 0 and len(op_cards) > 0:
            best_score = SCORE_VETO
            # The KO the ACTIVE already achieves on each target `j`, noted as
            # (the active's CURRENT HP, the prizes it hands over). It is filled by
            # the i == 0 pass -- the active is always `my_cards[0]` and is walked first --
            # and consumed by `_bench_pivot_no_gain` further down, which is the one that
            # compares the benched candidate against the body ALREADY in front.
            _atk_act_ko = {}
            for i, my_pokemon in enumerate(my_cards):
                if my_pokemon is None:
                    continue
                if i != 0 and not can_switch:
                    break

                attack_options = []
                if my_pokemon.id == Hydrapple_ex:

                    _syrup_grass = total_grass
                    # A BENCHED Hydrapple ex (i >= 1) only attacks if we RETREAT
                    # the active, and that retreat DISCARDS the active's energy
                    # to pay its cost: Syrup Storm scales with the Grass on the
                    # field, so it has to be measured with the Grass that will remain
                    # AFTER the retreat (user, registro_011 step 138 vs
                    # Dragapult, LOST). There the active was a Tapu Bulu with
                    # 3 Grass (6 effective): with the previous Grass (10) the
                    # benched Hydrapple's Syrup Storm gave 330 and "knocked out"
                    # the 320 HP Dragapult ex, so the plan chose it as the
                    # attacker; retreating discarded those 3 Grass and the real
                    # attack came out at 150. The same pattern as
                    # `_bo_grass_after` in the gust selection.
                    if i >= 1 and not has_switch_card:
                        _sg_act = my_state.active[0] if my_state.active else None
                        if _sg_act is not None:
                            _syrup_grass = max(
                                0, _syrup_grass - _retreat_grass_units(
                                    RETREAT_COST.get(_sg_act.id, 1)))
                    # Grass we can STILL put on the field this turn.
                    # The route is not only the manual attachment: Teal Dance and Ripening
                    # Charge are ABILITIES and are still alive with `energyAttached`
                    # set. And if there is no Grass left in hand but there IS one in the
                    # discard, Night Stretcher recovers it: it counts as a source
                    # of energy when measuring the finisher (user, registro_006 step 78
                    # vs Archaludon ex, LOST -- see
                    # `_ns_e_finisher_via_promotion`, which is what then PAYS for
                    # playing it, so this projection is not a mirage).
                    _sg_route = _grass_attach_route_open(
                        state, field_counts, abilities_off=meowth_ability_lock)
                    # The Grass in hand is only counted with the MANUAL attachment
                    # available (the historical criterion): counting the ability route
                    # here too would widen the plan to many states without the user's
                    # case needing it, and the safe direction of this estimator is to fall
                    # SHORT (if it overestimates, it vetoes the active's
                    # attack because of a bench KO that does not exist).
                    #
                    # AND THE TURN'S ATTACHMENT HAS TO STILL EXIST, for BOTH
                    # routes (user, August 2026, found by the differential
                    # oracle on crustle_wall_9). The Grass-in-hand branch asked
                    # `not state.energyAttached` from the day it was written; the
                    # Night Stretcher branch below it never did, so with the
                    # attachment already spent it still added a Grass it could
                    # not attach. With Meganium in play `_grass_attach_unit()` is
                    # TWO, so the projection came out 60 damage high and the
                    # ATTACK block believed a knockout it did not have.
                    #
                    # Measured: 9 of 9 PHANTOM_KO in 1200 games against that deck
                    # had exactly this board -- no Grass in hand, a Night
                    # Stretcher in hand, Grass in the discard, `energyAttached`
                    # already True -- and every one of them predicted the target
                    # would fall and left it at 30 (or at 10 behind a Hero's
                    # Cape). The engine was right every single time.
                    #
                    # The shared precondition is hoisted rather than repeated:
                    # what both branches are really saying is "if I can still
                    # attach one this turn, from wherever I get it".
                    if not state.energyAttached:
                        if hand_counts.get(Basic_Grass_Energy, 0) >= 1:
                            _syrup_grass += _grass_attach_unit()
                        elif (hand_counts.get(Basic_Grass_Energy, 0) == 0
                              and hand_counts.get(Night_Stretcher, 0) >= 1
                              and discard_counts.get(Basic_Grass_Energy, 0) >= 1
                              and _sg_route and not _plan_act_kos_now):
                            _syrup_grass += _grass_attach_unit()
                    syrup_dmg = 30 + 30 * _syrup_grass
                    attack_options.append((2, syrup_dmg, 0, True))
                elif my_pokemon.id == Dipplin:

                    wave_dmg = 20 * bench_count
                    attack_options.append((1, wave_dmg, 0, False))
                elif my_pokemon.id == Teal_Mask_Ogerpon_ex:

                    if len(op_cards) > 0:
                        op_active_energy = len(op_cards[0].energies) if op_cards[0] is not None else 0
                        my_energy = len(my_pokemon.energies)
                        # Myriad Leaf Shower counts the energy of BOTH actives
                        # (a rule VERIFIED with 6 records, see
                        # _attacker_base_damage): the inline copy used only
                        # our energy and the ATTACK argmax underestimated real
                        # KOs (it chose another attacker or a chip).
                        leaf_dmg = 30 + 30 * (my_energy + op_active_energy)
                        attack_options.append((3, leaf_dmg, 0, False))
                elif my_pokemon.id == Tapu_Bulu:

                    attack_options.append((4, 220, 0, False))
                elif my_pokemon.id == Meganium:

                    attack_options.append((4, 140, 0, False))
                elif my_pokemon.id == Fezandipiti_ex:

                    attack_options.append((3, 100, 0, True))
                elif my_pokemon.id == Pinsir:

                    attack_options.append((2, 100, 1, False))

                for energy_req, base_damage, attack_idx, colorless_ok in attack_options:
                    base_score = 0

                    energy_count = len(my_pokemon.energies)
                    more_energy = False
                    _ns_energy_recovery = False

                    effective_energy = energy_count * _grass_mult()

                    if effective_energy < energy_req:
                        if hand_counts[Basic_Grass_Energy] >= 1 and not state.energyAttached:
                            effective_energy += _grass_attach_unit()
                            if effective_energy < energy_req:
                                continue
                            else:
                                more_energy = True

                        elif (i != 0 and
                              hand_counts.get(Night_Stretcher, 0) >= 1 and
                              discard_counts.get(Basic_Grass_Energy, 0) >= 1 and
                              not state.energyAttached):
                            _ns_eff = _grass_attach_unit()
                            if effective_energy + _ns_eff >= energy_req:
                                more_energy = True
                                _ns_energy_recovery = True
                            else:
                                continue
                        else:
                            continue

                    my_is_ex = my_pokemon.id in OUR_EX_IDS

                    _op_active_is_drednaw = (op_state.active and op_state.active[0] is not None
                                             and op_state.active[0].id == Drednaw)
                    if my_pokemon.id == Hydrapple_ex:
                        base_score += 200
                        if op_has_ability_immune_active:
                            base_score -= 2000

                        if _op_active_is_drednaw:
                            _syrup_dmg_est = 30 + 30 * total_grass
                            if _syrup_dmg_est >= 200:
                                base_score -= 3000

                        elif op_is_fire_deck:
                            base_score += 150
                        elif op_is_aggro_deck:
                            base_score += 100
                    elif my_pokemon.id == Dipplin:
                        base_score += 50

                        if op_has_ex_immune_active:
                            base_score += 1200
                        if op_has_ability_immune_active:
                            base_score += 1500

                        if _op_active_is_drednaw:
                            base_score += 2500
                    elif my_pokemon.id == Tapu_Bulu:
                        if op_has_ex_immune_active:
                            base_score += 2200

                            if (op_state.active and op_state.active[0] is not None
                                    and op_state.active[0].id == Sylveon):
                                base_score += 800
                        elif op_has_ability_immune_active:
                            base_score += 2500
                        elif _op_active_is_drednaw:
                            base_score -= 3000
                        elif op_is_fire_deck:
                            base_score += 800

                        elif op_is_control_deck or op_is_slowking_deck:
                            base_score += 500
                        else:
                            base_score += 100
                    elif my_pokemon.id == Pinsir:
                        base_score += 50

                        if op_has_ex_immune_active:
                            base_score += 1300
                        if op_has_ability_immune_active:
                            base_score += 1600

                        if _op_active_is_drednaw:
                            base_score += 2300
                    elif my_pokemon.id == Meganium:
                        if op_has_ex_immune_active:
                            base_score += 1500

                            if (op_state.active and op_state.active[0] is not None
                                    and op_state.active[0].id == Sylveon):
                                base_score += 2000
                        if op_has_ability_immune_active:
                            base_score -= 2000

                        if _op_active_is_drednaw:
                            base_score += 3500
                    elif my_pokemon.id == Teal_Mask_Ogerpon_ex:
                        base_score -= 100
                        if op_has_ability_immune_active:
                            base_score -= 2000
                    elif my_pokemon.id == Fezandipiti_ex:

                        if op_has_ex_immune_active:
                            base_score -= 2000
                        if op_has_ability_immune_active:
                            base_score -= 2000

                    if neutralization_zone_active:
                        if my_is_ex:
                            base_score -= 3000
                        else:

                            base_score += 2000

                    for j, op_pokemon in enumerate(op_cards):
                        if op_pokemon is None:
                            continue

                        if j != 0 and not can_op_switch and my_pokemon.id != Fezandipiti_ex:
                            break

                        damage = base_damage
                        data = card_table[op_pokemon.id]

                        if op_pokemon.id in EX_IMMUNE_IDS and my_is_ex:
                            damage = 0

                        _op_has_rule_box = (data.ex or data.megaEx)
                        if (neutralization_zone_active and my_is_ex and
                                not _op_has_rule_box and damage > 0):
                            damage = 0

                        my_has_ability = (my_pokemon.id in OUR_ABILITY_IDS)
                        if op_pokemon.id in ABILITY_IMMUNE_IDS and my_has_ability:
                            damage = 0

                        # Farigiraf ex "Armor Tail" (P1.6): immune to our
                        # BASIC ex; only Hydrapple ex and the non-ex damage it.
                        if (op_pokemon.id == Farigiraf_ex
                                and my_pokemon.id in OUR_BASIC_EX_IDS):
                            damage = 0

                        _drednaw_shell_active = (op_pokemon.id == Drednaw and damage > 0)

                        if damage > 0 and my_pokemon.id != Fezandipiti_ex:
                            if data.weakness == EnergyType.GRASS:
                                damage *= 2
                            elif data.resistance == EnergyType.GRASS:
                                damage -= 30

                        # Full Metal Lab, AFTER weakness/resistance as the card
                        # says. This is the line the differential oracle found:
                        # `plan.remain_hp` is written 15 lines below, and while
                        # that stadium was on the field it was 30 too generous on
                        # 51 of 51 measured attacks into their Metal.
                        if (full_metal_lab_active and damage > 0
                                and getattr(data, 'energyType', None) == EnergyType.METAL):
                            damage -= 30

                        if _drednaw_shell_active and damage >= 200:
                            damage = 0

                        effective_ko_hp = op_pokemon.hp
                        if op_pokemon.id == Crustle_Fighting and op_pokemon.hp == op_pokemon.maxHp:

                            if damage >= op_pokemon.hp:
                                damage = op_pokemon.hp - 10
                                effective_ko_hp = op_pokemon.hp + 1

                        prize = 0
                        score = pokemon_score(op_pokemon)
                        if damage <= 0 and op_pokemon.id in EX_IMMUNE_IDS:
                            score = SCORE_USELESS_ATTACK
                        elif damage <= 0 and op_pokemon.id in ABILITY_IMMUNE_IDS:
                            score = SCORE_USELESS_ATTACK
                        elif damage <= 0 and _drednaw_shell_active:
                            score = SCORE_USELESS_ATTACK
                        elif (damage <= 0 and op_pokemon.id == Farigiraf_ex
                                and my_pokemon.id in OUR_BASIC_EX_IDS):
                            score = SCORE_USELESS_ATTACK
                        elif damage <= 0 and neutralization_zone_active and my_is_ex:
                            score = SCORE_USELESS_ATTACK
                        elif op_pokemon.hp <= damage:
                            prize = prize_count_op(op_pokemon)
                        else:
                            score *= damage / max(1, op_pokemon.hp)
                        score += base_score

                        # The ACTIVE already finishes this target: WHICH
                        # body does it is noted (current HP and its own prizes) so it can be
                        # compared against afterwards. `prize_count`, not
                        # `prize_count_op`: it measures a Pokemon of OURS.
                        if i == 0 and damage > 0 and op_pokemon.hp <= damage:
                            _atk_act_ko[j] = ((my_pokemon.hp or 0),
                                              prize_count(my_pokemon))

                        if op_pokemon.id == Budew:
                            if op_pokemon.hp <= damage:
                                score += 8000
                            else:
                                score += 3000

                        elif op_pokemon.id == Froslass:
                            if op_pokemon.hp <= damage:
                                score += 9000
                            else:
                                score += 4000

                        elif op_pokemon.id == Munkidori:
                            if op_pokemon.hp <= damage:
                                score += 7500
                            else:
                                score += 2500

                        elif op_pokemon.id == Snorunt:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 2500

                        elif op_pokemon.id in (Dreepy, Drakloak):
                            if op_pokemon.hp <= damage:
                                # vs the Dragapult line, cutting off a Drakloak
                                # (a charged Stage 1 one step from Dragapult ex, a
                                # 2-prize attacker that spreads damage) with the
                                # free snipe of Cruel Arrow (Fezandipiti ex, a fixed
                                # 100) is MORE valuable than knocking out a Budew (a 30 hp
                                # support). Without this boost the Budew KO (8000 +
                                # 3500 basic + 300 active = 11800) beats the Drakloak one
                                # (6500 + 3000 Stage 1 = 9500) and the game
                                # shoots at the Budew. We raise Drakloak above
                                # Budew ONLY in the Dragapult matchup. Cruel Arrow
                                # never knocks out the Dragapult ex itself (320hp), so
                                # it does not interfere with higher-prize KOs.
                                if op_pokemon.id == Drakloak and op_has_dreepy_line:
                                    score += 9800
                                else:
                                    score += 6500
                            else:
                                score += 2000

                        elif op_pokemon.id in (Dwebble_Grass, Dwebble_Fighting):
                            if op_pokemon.hp <= damage:
                                score += 6000
                            else:
                                score += 2000

                        elif op_pokemon.id in EX_IMMUNE_IDS and not my_is_ex and damage > 0:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 4000

                        elif op_pokemon.id == Crustle_Fighting and op_pokemon.hp < op_pokemon.maxHp:
                            if op_pokemon.hp <= damage:
                                score += 5000

                        elif op_pokemon.id in (Ralts, Kirlia):
                            if op_pokemon.hp <= damage:
                                score += 6000
                            else:
                                score += 1500
                        elif op_pokemon.id == Gardevoir_ex:
                            if op_pokemon.hp <= damage:
                                score += 7500
                            else:
                                score += 3000

                        elif op_pokemon.id in (Abra, Kadabra):
                            if op_pokemon.hp <= damage:
                                score += 5500
                            else:
                                score += 1500
                        elif op_pokemon.id == Alakazam_ex:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 2500

                        elif op_pokemon.id == Slowking:
                            if op_pokemon.hp <= damage:
                                score += 7500
                            else:
                                score += 3000
                        elif op_pokemon.id == Slowpoke:
                            if op_pokemon.hp <= damage:
                                score += 5500
                            else:
                                score += 1500

                        elif op_pokemon.id in (Duskull, Dusclops):
                            if op_pokemon.hp <= damage:
                                score += 5500
                            else:
                                score += 1500
                        elif op_pokemon.id == Dusknoir:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 2500

                        elif op_pokemon.id == Zoroark_N:
                            if op_pokemon.hp <= damage:
                                score += 6500
                            else:
                                score += 2000
                        elif op_pokemon.id == Zorua_N:
                            if op_pokemon.hp <= damage:
                                score += 5000
                            else:
                                score += 1200

                        elif op_pokemon.id == Typhlosion:
                            if op_pokemon.hp <= damage:
                                score += 6500
                            else:
                                score += 2000
                        elif op_pokemon.id in (Cyndaquil, Quilava):
                            if op_pokemon.hp <= damage:
                                score += 5000
                            else:
                                score += 1200

                        elif op_pokemon.id == Chewtle:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 2500

                        elif op_pokemon.id == Drednaw and damage > 0:
                            if op_pokemon.hp <= damage:
                                score += 8000
                            else:
                                score += 3000

                        elif op_pokemon.id in EEVEE_IDS:
                            if op_pokemon.hp <= damage:
                                score += 7500
                            else:
                                score += 2500

                        elif op_pokemon.id == Sylveon and damage > 0:
                            if op_pokemon.hp <= damage:
                                score += 9000
                            else:
                                score += 4000

                        if my_pokemon.id == Fezandipiti_ex and damage > 0:
                            _op_data = card_table.get(op_pokemon.id)
                            _is_stage2 = (_op_data and getattr(_op_data, 'stage2', False))
                            _is_stage1 = (_op_data and getattr(_op_data, 'stage1', False))
                            _is_ex = (_op_data and getattr(_op_data, 'ex', False))
                            if op_pokemon.hp <= damage:

                                if _is_stage2:
                                    score += 5000
                                elif _is_ex:
                                    score += 4500
                                elif not _is_stage1:
                                    score += 3500
                                else:
                                    score += 3000
                            else:

                                if j == 0:
                                    score += 500

                        # Knocking out the opposing ACTIVE when the opponent has no other
                        # Pokemon in play (an empty bench) WINS the game: they cannot
                        # promote a replacement. It is won even if the KO does not complete
                        # the prizes (user, registro_016 p138 vs Crustle).
                        _ko_wins_no_bench = (
                            j == 0
                            and op_pokemon.hp <= damage
                            and not any(b is not None
                                        for b in (op_state.bench or [])))
                        # GUARANTEED KO (P0.1): vs Tenacious Body (a coin flip) or
                        # Survival Brace SCORE_WIN_GAME is not declared; the KO
                        # still scores through the normal route (prize/score).
                        if ((my_prize <= prize or _ko_wins_no_bench)
                                and not _ko_not_guaranteed(op_pokemon)):
                            score = SCORE_WIN_GAME
                        elif prize > 0:

                            remaining_after_ko = op_prize - prize
                            if remaining_after_ko == 1:

                                score += 4000

                        if i == 0:
                            score += 220
                        if j == 0:
                            score += 300
                        score += effective_energy

                        _la_return = _op_best_damage_vs(my_pokemon)
                        if _la_return > 0:
                            if _la_return >= my_pokemon.hp:
                                if my_pokemon.id in OUR_EX_IDS:

                                    _la_disrupt = _op_disruption_belief(op_state, False)
                                    score -= int(SCORE_LOOKAHEAD_EX_TRADE * (0.6 + 0.4 * _la_disrupt))
                                else:
                                    score -= SCORE_LOOKAHEAD_KO_TRADE
                            elif _la_return <= my_pokemon.hp * 0.4:
                                score += SCORE_LOOKAHEAD_SAFE

                        # A BENCHED attacker can only attack if we RETREAT
                        # the active to promote it, and then it is exposed to the
                        # opposing active. If that hit KNOCKS IT OUT, the pivot gives away
                        # its prizes (user, registro_011 step 138 vs Dragapult,
                        # LOST: the benched Hydrapple ex was at 70/330 and the
                        # opponent at 2 prizes, so promoting it handed them the
                        # game; the right play was to attack with the active Tapu Bulu,
                        # already charged). It is only allowed if the KO we achieve WINS
                        # the game (SCORE_WIN_GAME, already resolved above).
                        # It is measured with `_op_active_attack_damage_to` (which resolves
                        # the REAL attack of the opposing active via attack_table), not
                        # with `_op_best_damage_vs`, which here underestimated the
                        # Dragapult ex's hit and let the pivot through.
                        _pbs_opa = (op_state.active[0]
                                    if op_state.active and op_state.active[0] is not None
                                    else None)
                        _bench_pivot_suicidal = False
                        if i >= 1 and score != SCORE_WIN_GAME and _pbs_opa is not None:
                            _pbs_dmg = max(
                                _la_return,
                                _op_active_attack_damage_to(
                                    _pbs_opa, my_pokemon,
                                    getattr(op_state, 'handCount', None)))
                            _bench_pivot_suicidal = (
                                _pbs_dmg >= (my_pokemon.hp or 0))

                        # A bench pivot that IMPROVES NOTHING (user, registro_014
                        # step 166 vs Alakazam): if the ACTIVE already knocks out THAT
                        # SAME target, attacking from the bench forces a retreat
                        # -- energy is paid -- and leaves in front a body that
                        # endures the same or LESS for the same prizes. It is a
                        # change for the worse with a cost.
                        #
                        # It was chosen by `base_score`, which carries a SPECIES
                        # preference (+200 Hydrapple ex / -100 Teal Mask Ogerpon ex)
                        # inherited from PRINTED HP: Hydrapple is the 330 wall.
                        # But that is a CARD constant and it knows nothing about the damage
                        # already taken. In the record the "wall" was a Hydrapple
                        # ex at 90/330 and the active a healthy Teal Mask Ogerpon ex at
                        # 210/210; both knocked out the 140 HP Alakazam, and those
                        # 300 points of bias were enough to beat the +220 of
                        # "I am the active" and retreat the healthy one (78 points of
                        # difference) to put in front the one that dies.
                        #
                        # CURRENT HP is compared and the relief is also required not to
                        # DENY prizes: a benched non-ex can still relieve an active ex even if
                        # it endures less, because there the worse body is paid for with 1 prize
                        # instead of 2 (see `_alakazam_pivot_1prize`). The same criterion as
                        # `_pdx_act_margin`: the one that ENDURES goes in front.
                        _bench_pivot_no_gain = False
                        if i >= 1 and _atk_act_ko.get(j) is not None:
                            _pbsg_hp, _pbsg_prize = _atk_act_ko[j]
                            _bench_pivot_no_gain = (
                                (my_pokemon.hp or 0) <= _pbsg_hp
                                and prize_count(my_pokemon) >= _pbsg_prize)

                        if (best_score < score and not _bench_pivot_suicidal
                                and not _bench_pivot_no_gain):
                            best_score = score
                            AGENT_STATE.plan.attacker = i
                            AGENT_STATE.plan.target = j
                            AGENT_STATE.plan.attack_index = attack_idx
                            AGENT_STATE.plan.remain_hp = op_pokemon.hp - damage
                            AGENT_STATE.plan.energy = more_energy

            _op_act_main = op_state.active[0] if op_state.active else None
            _ret_active = my_cards[0] if my_cards else None

            # FINISHER with the ACTIVE: if the loop chose to attack with the active
            # (attacker 0) KNOCKING OUT the opposing active and the opponent has no bench,
            # that attack WINS the game. It is captured here, BEFORE the
            # mismatch/prize-sacrifice pivots, to restore it afterwards (those
            # pivots would retreat the lethal active to bring up a 1-prize body, throwing
            # away the immediate victory; user, registro_016 p138 vs Crustle).
            if (_op_bench_empty and AGENT_STATE.plan.attacker == 0
                    and AGENT_STATE.plan.remain_hp is not None and AGENT_STATE.plan.remain_hp <= 0):
                _active_win_plan = (
                    AGENT_STATE.plan.attacker, AGENT_STATE.plan.target, AGENT_STATE.plan.attack_index,
                    AGENT_STATE.plan.remain_hp, AGENT_STATE.plan.energy)

            if (_op_act_main is not None and can_switch and _ret_active is not None
                    and _ret_active.id != Hydrapple_ex):

                _hydra_mc_idx = -1
                _hydra_mc_pk = None

                _hydra_charge_idx = -1
                _hydra_charge_pk = None
                _grass_in_hand_promo = hand_counts.get(Basic_Grass_Energy, 0) >= 1
                # Tie-break by HP (user, log 86212499 step 151, vs Alakazam,
                # WON): with two or more IDENTICAL benched Hydrapple ex fit to
                # promote and attack (e.g. one at 70 hp and another at 330 hp), ALWAYS
                # promote the one with MORE HP. Before, the loop walked the bench in
                # order and took the FIRST fit Hydrapple (`break` / first
                # charging candidate), that is, the one with the lowest bench index (the
                # 70 hp one), which is fragile and dies easily. Now the whole
                # bench is walked and, at equal fitness (ready >= 2 effective, or
                # chargeable to >= 2), the one with the most hp is chosen. The
                # priority is kept: a Hydrapple that is ALREADY charged (`_hydra_mc_idx`) prevails
                # over one that needs charging (`_hydra_charge_idx`).
                for _mc_i, _mc_pk in enumerate(my_cards):
                    if _mc_i == 0 or _mc_pk is None:
                        continue
                    if _mc_pk.id == Hydrapple_ex:
                        _mc_eff = len(_mc_pk.energies) * _grass_mult()
                        if _mc_eff >= 2:
                            if (_hydra_mc_idx < 0
                                    or (_mc_pk.hp or 0) > (_hydra_mc_pk.hp or 0)):
                                _hydra_mc_idx = _mc_i
                                _hydra_mc_pk = _mc_pk
                        elif (_grass_in_hand_promo and
                                len(_mc_pk.energies) + _grass_attach_unit() >= 2):
                            if (_hydra_charge_idx < 0
                                    or (_mc_pk.hp or 0) > (_hydra_charge_pk.hp or 0)):
                                _hydra_charge_idx = _mc_i
                                _hydra_charge_pk = _mc_pk

                _hydra_promo_needs_charge = False
                if _hydra_mc_idx < 0 and _hydra_charge_idx >= 1:

                    _ret_req_now = None
                    if _ret_active.id == Hydrapple_ex:
                        _ret_req_now = 2
                    elif _ret_active.id == Dipplin:
                        _ret_req_now = 1
                    elif _ret_active.id == Teal_Mask_Ogerpon_ex:
                        _ret_req_now = 3
                    elif _ret_active.id == Tapu_Bulu:
                        _ret_req_now = 4
                    elif _ret_active.id == Pinsir:
                        _ret_req_now = 2
                    elif _ret_active.id == Fezandipiti_ex:
                        _ret_req_now = 3
                    elif _ret_active.id == Meganium:
                        _ret_req_now = 4
                    _ret_eff_now = len(_ret_active.energies) * _grass_mult()
                    _ret_act_ready_now = (_ret_req_now is not None and _ret_eff_now >= _ret_req_now)

                    if _ret_req_now is None or _ret_act_ready_now:
                        _hydra_mc_idx = _hydra_charge_idx
                        _hydra_mc_pk = _hydra_charge_pk
                        _hydra_promo_needs_charge = True
                if _hydra_mc_idx >= 1:
                    _op_main_hp = _op_act_main.hp or 0

                    _ret_cost = RETREAT_COST.get(_ret_active.id, 1)
                    if has_switch_card:
                        _ret_cost = 0
                    # Wild Growth: each Grass pays for two, so fewer Grass
                    # CARDS are discarded to cover the retreat -- but each
                    # discarded card erases TWO units from the count that
                    # Syrup Storm scales with (`_retreat_grass_units`), and the
                    # Grass attached for the charge also adds TWO
                    # (`_grass_attach_unit`). Counting cards instead of units
                    # inflated the damage by exactly that factor: user, registro_006
                    # step 78 vs Archaludon ex (LOST), where the pivot believed
                    # the benched Hydrapple ex knocked out (300 - 30 = 270 =
                    # the exact HP) and the real attack did 240.
                    _hydra_grass_after = max(
                        0, total_grass - _retreat_grass_units(_ret_cost))
                    if _hydra_promo_needs_charge:
                        _hydra_grass_after += _grass_attach_unit()
                    _hydra_base = 30 + 30 * _hydra_grass_after
                    _hydra_ko_dmg = _our_effective_damage(
                        _hydra_mc_pk, _op_act_main, _hydra_base,
                        AGENT_STATE.meganium_in_play, neutralization_zone_active)
                    _hydra_can_ko = (_hydra_ko_dmg > 0 and _hydra_ko_dmg >= _op_main_hp)

                    _act_can_ko = False
                    _act_prof = None
                    if _ret_active.id == Dipplin:
                        _act_prof = (1, 20 * bench_count)
                    elif _ret_active.id == Teal_Mask_Ogerpon_ex:
                        _oae = len(_op_act_main.energies)
                        _act_prof = (3, 30 + 30 * (len(_ret_active.energies) + _oae))
                    elif _ret_active.id == Tapu_Bulu:
                        _act_prof = (4, 220)
                    elif _ret_active.id == Meganium:
                        _act_prof = (4, 140)
                    elif _ret_active.id == Pinsir:
                        _act_prof = (2, 100)
                    elif _ret_active.id == Fezandipiti_ex:
                        _act_prof = (3, 100)
                    if _act_prof is not None:
                        _act_req, _act_base = _act_prof
                        _act_eff = len(_ret_active.energies) * _grass_mult()
                        if (_act_eff < _act_req and hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                and not state.energyAttached):
                            _act_eff += _grass_attach_unit()
                        if _act_eff >= _act_req:
                            _act_dmg = _our_effective_damage(
                                _ret_active, _op_act_main, _act_base,
                                AGENT_STATE.meganium_in_play, neutralization_zone_active)
                            _act_can_ko = (_act_dmg > 0 and _act_dmg >= _op_main_hp)

                    _promote_hydra = _hydra_can_ko or (not _act_can_ko)

                    if _hydra_ko_dmg <= 0:
                        _promote_hydra = False
                    # Rule (user, registro 010 step 82 vs Alakazam): a CHARGED Tapu Bulu
                    # in the active spot that can KNOCK OUT the opposing active attacks
                    # itself; it does not yield the attack to the Hydrapple ex pivot. Tapu
                    # Bulu is non-ex (1 prize if it is knocked out), so finishing with it
                    # is better than exposing/spending the Hydrapple ex (2 prizes).
                    if _ret_active.id == Tapu_Bulu and _act_can_ko:
                        _promote_hydra = False
                    # The same idea as the Tapu Bulu above, but for the
                    # body that ENDURES (user, registro_014 step 166 vs
                    # Alakazam): when the ACTIVE already knocks out, `_hydra_can_ko`
                    # promoted anyway out of the conviction that Hydrapple ex
                    # is the 330 HP wall. That is PRINTED HP. In the record
                    # the benched Hydrapple ex was at 90/330 and the active was an
                    # UNTOUCHED Teal Mask Ogerpon ex at 210/210: both knocked out
                    # the Alakazam, so retreating only served to pay an
                    # energy and leave in front the body that dies. A REAL
                    # HP improvement is required, and the relief must not deny prizes either
                    # (a non-ex relieving an ex is still worth it even if it endures
                    # less: 1 prize is paid instead of 2).
                    if (_act_can_ko and _hydra_mc_pk is not None
                            and (_hydra_mc_pk.hp or 0) <= (_ret_active.hp or 0)
                            and prize_count(_hydra_mc_pk)
                                >= prize_count(_ret_active)):
                        _promote_hydra = False
                    # The promoted Hydrapple ex is EXPOSED to the opposing active:
                    # if that hit KNOCKS IT OUT, the pivot gives away 2 prizes (user,
                    # registro_011 step 138 vs Dragapult, LOST: the benched Hydrapple
                    # was at 70/330 and the opponent at 2 prizes, so
                    # promoting it handed them the game; the right play was to attack
                    # with the active Tapu Bulu, already charged). `_promote_hydra` was
                    # switched on with just `not _act_can_ko` -- "if the active does not
                    # knock out, promote" -- without looking at whether the Hydrapple survives.
                    # The pivot is only allowed if it SURVIVES the projected hit
                    # or if its own KO already wins the game. It uses
                    # `_op_active_attack_damage_to` (which resolves the REAL attack via
                    # attack_table: here Phantom Dive, 200) because the generic estimator
                    # returned 0 for Dragapult ex.
                    if _promote_hydra and _hydra_mc_pk is not None:
                        _ph_gana = (_hydra_can_ko
                                    and my_prize <= prize_count_op(_op_act_main))
                        if not _ph_gana:
                            _ph_dmg_opponent = _op_active_attack_damage_to(
                                _op_act_main, _hydra_mc_pk,
                                getattr(op_state, 'handCount', None))
                            if _ph_dmg_opponent >= (_hydra_mc_pk.hp or 0):
                                _promote_hydra = False
                    if _promote_hydra and AGENT_STATE.plan.attacker != _hydra_mc_idx:
                        AGENT_STATE.plan.attacker = _hydra_mc_idx
                        AGENT_STATE.plan.target = 0
                        AGENT_STATE.plan.attack_index = 0
                        AGENT_STATE.plan.remain_hp = _op_main_hp - _hydra_ko_dmg
                        AGENT_STATE.plan.energy = False

            if (AGENT_STATE.plan.attacker >= 1
                    and _op_act_main is not None
                    and _ret_active is not None
                    and _ret_active.id in OUR_EX_IDS
                    and _op_act_main.id not in EX_IMMUNE_IDS):
                _rule_act_immune = False
                if _op_act_main.id in ABILITY_IMMUNE_IDS and _ret_active.id in OUR_ABILITY_IDS:
                    _rule_act_immune = True
                if neutralization_zone_active and _ret_active.id in OUR_EX_IDS:
                    _op_act_data_rule = card_table.get(_op_act_main.id)
                    if not (_op_act_data_rule and (_op_act_data_rule.ex or _op_act_data_rule.megaEx)):
                        _rule_act_immune = True
                if not _rule_act_immune:
                    _rule_act_prof = None
                    if _ret_active.id == Teal_Mask_Ogerpon_ex:
                        _oae_r = len(_op_act_main.energies)
                        _rule_act_prof = (3, 30 + 30 * (len(_ret_active.energies) + _oae_r))
                    elif _ret_active.id == Hydrapple_ex:
                        _rule_act_prof = (2, 30 + 30 * total_grass)
                    elif _ret_active.id == Fezandipiti_ex:
                        _rule_act_prof = (3, 100)
                    if _rule_act_prof is not None:
                        _rule_req, _rule_base = _rule_act_prof
                        _rule_eff = len(_ret_active.energies) * _grass_mult()
                        _rule_needs_attach = False
                        if (_rule_eff < _rule_req
                                and hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                and not state.energyAttached):
                            _rule_eff += _grass_attach_unit()
                            _rule_needs_attach = True
                        if _rule_eff >= _rule_req:
                            _rule_act_dmg = _our_effective_damage(
                                _ret_active, _op_act_main, _rule_base,
                                AGENT_STATE.meganium_in_play, neutralization_zone_active)
                            _rule_bench_kos = (AGENT_STATE.plan.target == 0
                                               and AGENT_STATE.plan.remain_hp is not None
                                               and AGENT_STATE.plan.remain_hp <= 0)
                            if _rule_act_dmg > 0 and not _rule_bench_kos:
                                AGENT_STATE.plan.attacker = 0
                                AGENT_STATE.plan.target = 0
                                AGENT_STATE.plan.attack_index = 0
                                AGENT_STATE.plan.remain_hp = (_op_act_main.hp or 0) - _rule_act_dmg
                                AGENT_STATE.plan.energy = _rule_needs_attach

            # --- Defensive pivot to Hydrapple ex ---
            # If our active is fragile (low HP / a likely KO next
            # turn) and on the bench there is a Hydrapple ex at full HP with
            # enough energy of its own (Meganium's Wild Growth counts) to
            # knock out the opposing active, it is better to RETREAT the fragile active and bring up
            # the Hydrapple ex: its very high HP is very hard to knock out,
            # it keeps up the pressure and it gives away no prizes. The fragile active is
            # sheltered on the bench; the KO is delivered all the same but with a body
            # far more resilient at the front. Meganium is key: it doubles
            # the Grass energy, so Hydrapple can attack with fewer cards.
            # Rule (user, registro 010 step 82 vs Alakazam): a CHARGED Tapu Bulu
            # in the active spot that can KNOCK OUT the opposing active NEVER retreats; it must
            # attack. Being non-ex, if it is knocked out it only hands over 1 prize, so
            # finishing with it is better than spending the pivot to Hydrapple ex (2
            # prizes). We veto the defensive pivot to Hydrapple when the active is
            # a Tapu Bulu with a KO available (even if it is "fragile"): not firing it also
            # stops `plan.attacker` from pointing at Hydrapple and suppressing the attack.
            _tapu_active_ko_here = False
            if (_ret_active is not None and _ret_active.id == Tapu_Bulu
                    and _op_act_main is not None
                    and len(_ret_active.energies) * _grass_mult() >= 4):
                _tapu_dmg_here = _our_effective_damage(
                    _ret_active, _op_act_main, 220, AGENT_STATE.meganium_in_play,
                    neutralization_zone_active)
                _tapu_active_ko_here = (_tapu_dmg_here > 0
                                        and _tapu_dmg_here >= (_op_act_main.hp or 0))

            # It includes the case where the ACTIVE is ALREADY a fragile Hydrapple ex
            # (user, registro_023 vs Archaludon): with two Hydrapple ex in play,
            # if the active has LOW HP and on the bench there is ANOTHER Hydrapple ex with
            # MORE HP that, after retreating, STILL knocks out the opposing active, the
            # tank is promoted: it knocks out all the same and survives the counterattack (the
            # fragile one would die and, being an ex, would concede 2 prizes). Hydrapple's attack
            # (Syrup Storm) scales with the TOTAL Grass on the field, which DROPS because of the
            # retreat cost, so the KO is checked against the field that will exist
            # AFTER the retreat -- WHICHEVER body is retreating.
            #
            # The discount used to be applied only when the active was another
            # Hydrapple, and the missing half cost a turn (user, registro_012
            # step 112 vs Marnie's Grimmsnarl ex): active Teal Mask Ogerpon ex at
            # 30 HP with 4 Grass, benched Hydrapple ex with 2, six Grass on the
            # field. The pivot read 30 + 30 x 6 = 210, doubled by weakness = 420
            # = exactly the 420 HP of the Grimmsnarl ex, so it promised a KO,
            # pointed `plan.attacker` at the bench and SUPPRESSED the attack of
            # the active. The retreat then burned one Grass and the real Syrup
            # Storm landed 360: the Grimmsnarl survived on 60, healed itself with
            # Adrena-Brain and moved those counters onto the 30 HP Ogerpon ex we
            # had just hidden on the bench -- two prizes for free. The attack
            # that was suppressed (Myriad Leaf Shower, 30 + 30 x (4 + 2) = 210
            # doubled = 420) WAS the exact KO. Same arithmetic as
            # `_retreat_grass_units` (registro_006 step 78 vs Archaludon ex),
            # which is the helper that already knew about this.
            _piv_active_is_hydra = (_ret_active is not None
                                    and _ret_active.id == Hydrapple_ex)
            if _ret_active is None or has_switch_card:
                _piv_ret_cost = 0
            else:
                _piv_ret_cost = RETREAT_COST.get(_ret_active.id, 1)
            _piv_grass_after = max(
                0, total_grass - _retreat_grass_units(_piv_ret_cost))
            if (can_switch and _op_act_main is not None and _ret_active is not None
                    and not _tapu_active_ko_here
                    and (active_ko_likely or active_hp_ratio <= 0.6)):
                _piv_op_hp = _op_act_main.hp or 0
                for _piv_i, _piv_pk in enumerate(my_cards):
                    if _piv_i == 0 or _piv_pk is None or _piv_pk.id != Hydrapple_ex:
                        continue
                    # Only if Hydrapple ex is at full HP (very hard to
                    # knock out); if it is already damaged it does not provide the wall advantage.
                    if _piv_pk.hp < (_piv_pk.maxHp or 0):
                        continue
                    # With an active Hydrapple, the benched one must have MORE HP than the
                    # active; otherwise pivoting adds nothing (the same field attack) and
                    # it also loses Grass because of the retreat.
                    if _piv_active_is_hydra and (_piv_pk.hp or 0) <= (_ret_active.hp or 0):
                        continue
                    # It needs its OWN energy to attack after coming up (Wild Growth
                    # included): the effective threshold for Hydrapple ex is 2.
                    if len(_piv_pk.energies) * _grass_mult() < 2:
                        continue
                    _piv_dmg = _our_effective_damage(
                        _piv_pk, _op_act_main, 30 + 30 * _piv_grass_after,
                        AGENT_STATE.meganium_in_play, neutralization_zone_active)
                    if _piv_dmg > 0 and _piv_dmg >= _piv_op_hp:
                        AGENT_STATE.plan.attacker = _piv_i
                        AGENT_STATE.plan.target = 0
                        AGENT_STATE.plan.attack_index = 0
                        AGENT_STATE.plan.remain_hp = _piv_op_hp - _piv_dmg
                        AGENT_STATE.plan.energy = False
                        _hydra_pivot_active = True
                        break

            # --- Wall pivot to Hydrapple ex WITHOUT a KO (user, log 85856881 p.127) ---
            # If `_hydra_wall_pivot` (a doomed active Ogerpon that CAN attack
            # but does NOT knock out, and a Hydrapple ex wall at full HP on the bench that
            # survives), we point the plan at the benched Hydrapple so that the
            # option of ATTACKING with the fragile Ogerpon is SUPPRESSED (plan.attacker
            # >= 1 with a retreat available -> see the ATTACK block), so that the
            # agent chooses PASS, the engine exposes the retreat (ctx=30) and the
            # wall is brought up. It does not require `can_switch` (in ctx=0 there is no RETREAT option; the
            # retreat is only exposed after PASS). Only if no KO pivot plan has been fixed yet.
            if (_hydra_wall_pivot and not _hydra_pivot_active
                    and AGENT_STATE.plan.attacker == 0 and _op_act_main is not None):
                for _hwpp_i, _hwpp_pk in enumerate(my_cards):
                    if (_hwpp_i >= 1 and _hwpp_pk is not None
                            and _hwpp_pk.id == Hydrapple_ex
                            and _hwpp_pk.hp >= (_hwpp_pk.maxHp or 0)
                            and len(_hwpp_pk.energies) * _grass_mult() >= 2):
                        _hwpp_dmg = _our_effective_damage(
                            _hwpp_pk, _op_act_main, 30 + 30 * total_grass,
                            AGENT_STATE.meganium_in_play, neutralization_zone_active)
                        AGENT_STATE.plan.attacker = _hwpp_i
                        AGENT_STATE.plan.target = 0
                        AGENT_STATE.plan.attack_index = 0
                        AGENT_STATE.plan.remain_hp = (_op_act_main.hp or 0) - _hwpp_dmg
                        AGENT_STATE.plan.energy = False
                        break

            # --- Prize sacrifice: pivot to a benched Tapu Bulu (user) ---
            # If our active is an ex (2 prizes) at risk of being knocked out
            # next turn and on the bench there is a Tapu Bulu (non-ex, 1 prize) READY
            # to attack that can knock out the opposing active, it is better to RETREAT the ex
            # and bring up Tapu Bulu to attack: we take the KO all the same, but we expose
            # at the front only a 1-prize body. If the opponent knocks it out we hand over
            # 1 prize instead of 2. It does not apply if we already pivoted to a benched
            # Hydrapple ex (a wall at full HP, a better body).
            #
            # Besides the DEFENSIVE case (an active at risk), we allow the PROACTIVE
            # pivot (user): with Meganium in play and a benched Tapu Bulu already
            # READY (>=4 effective) that knocks out the opposing active, bring up Tapu Bulu
            # (1 prize) to attack and NOT expose the active ex (2 prizes), even if
            # the ex is healthy. It does not apply in matchups with walls/immunities or with a
            # Neutralization Zone.
            _tapu_proactive_lead = (
                AGENT_STATE.meganium_in_play
                and not (AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck
                         or op_is_sylveon_deck)
                and not neutralization_zone_active)
            if (not _hydra_pivot_active
                    and _op_act_main is not None and _ret_active is not None
                    and _ret_active.id in OUR_EX_IDS
                    and (active_ko_likely or active_hp_ratio <= 0.5
                         or _tapu_proactive_lead)
                    and my_prize > prize_count_op(_op_act_main)):
                _tsac_op_hp = _op_act_main.hp or 0
                _tsac_bench_kos = False
                for _tsac_i, _tsac_pk in enumerate(my_cards):
                    if _tsac_i == 0 or _tsac_pk is None or _tsac_pk.id != Tapu_Bulu:
                        continue
                    # Tapu Bulu has to be READY (>=4 effective Grass).
                    if len(_tsac_pk.energies) * _grass_mult() < 4:
                        continue
                    _tsac_dmg = _our_effective_damage(
                        _tsac_pk, _op_act_main, 220,
                        AGENT_STATE.meganium_in_play, neutralization_zone_active)
                    if _tsac_dmg > 0 and _tsac_dmg >= _tsac_op_hp:
                        _tsac_bench_kos = True
                        if can_switch:
                            AGENT_STATE.plan.attacker = _tsac_i
                            AGENT_STATE.plan.target = 0
                            AGENT_STATE.plan.attack_index = 0
                            AGENT_STATE.plan.remain_hp = _tsac_op_hp - _tsac_dmg
                            AGENT_STATE.plan.energy = False
                            _tapu_sac_pivot = True
                        break
                # If Tapu can already finish from the bench but we canNOT retreat the
                # ex yet (it lacks energy for the retreat cost) and ONE more
                # energy is enough to enable it and we still have this turn's manual
                # attachment, it is better to attach that energy to the active ex so it can be
                # retreated and Tapu brought up. It only applies with Tapu ALREADY charged, so that
                # we never take energy away from Tapu.
                if (_tsac_bench_kos and not can_switch and not state.energyAttached
                        and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                    _tsac_rc = RETREAT_COST.get(_ret_active.id, 1)
                    _tsac_cur_e = len(_ret_active.energies)
                    if _tsac_cur_e < _tsac_rc and _tsac_cur_e + 1 >= _tsac_rc:
                        _tapu_sac_enable_retreat = True

            # =================================================================
            # THE STADIUM THEY BROUGHT ARMS OUR DIPPLIN TOO (user,
            # registro_006 steps 81-86, episode 91522323 vs *Festival Lead*,
            # LOST).
            #
            #     US (5 prizes)                       RIVAL (4 prizes)
            #     active Teal Mask Ogerpon ex         active Dipplin 80/80, 1 {G}
            #            **10**/210, 3 {G}            bench  Volbeat 70, Thwackey 100,
            #     bench  Tapu Bulu 140 (1 {G})               Grookey 70, Applin 40,
            #            Applin 40, Bayleef 110,             Applin 40
            #            Teal Mask Ogerpon ex 210    stadium **Festival Grounds** (theirs)
            #     hand   Dipplin, Ultra Ball, 1 {G}
            #
            # Their Dipplin had just thrown Do the Wave TWICE into our Ogerpon ex
            # (210 -> 110 -> 10) and the turn read the board correctly as far as
            # it went: evolve the benched Applin into Dipplin, and Myriad Leaf
            # Shower (30 + 30 x (3 + 1) = 150) knocks their Dipplin out. One
            # prize. Then the 10 HP ex stayed in the Active spot and the reply
            # took TWO -- `turn_plan.op_prizes_after_ko` said so out loud on that
            # very board, and nobody was listening.
            #
            # The whole turn was available at a better price. The Grass goes onto
            # the Dipplin we just evolved, the ex RETREATS (cost 1, it carries 3),
            # and Do the Wave = 20 x 4 benched = 80 knocks the same Dipplin out
            # -- and then, because **Festival Grounds is on the field**, it
            # attacks AGAIN (`_festival_double_wave`): three of the five bodies
            # they can promote die to a second 80. The prize is cashed by a
            # 1-PRIZE body that stays alive, and the wounded ex is not merely
            # hidden -- Teal Mask Ogerpon ex's Tera prevents ALL damage to it
            # while it is on our bench.
            #
            # WHY NO EXISTING PIVOT FIRED. `_doomed_ex_sac_pivot` stands aside
            # when the doomed ex can still knock out (`not _active_can_ko_now`):
            # cash the prize before it dies. `_prize_denial_pivot` needs the KO
            # to CLOSE their count (2 >= 4 is false here). `_tapu_sac_pivot` is
            # this same sentence -- retreat the doomed ex, hand a 1-prize body
            # the front spot, take the knockout anyway -- but it is written for a
            # Tapu Bulu that is ALREADY charged, and the body that was ready here
            # needed the one Grass in hand.
            #
            # So this is `_tapu_sac_pivot` with the other attacker: the ONE card
            # whose price the stadium changes. Outside Festival Grounds a Dipplin
            # taking the front spot is a chip and
            # [[el-relevo-que-no-toma-premio-no-gana-el-puesto-activo]] already
            # forbids it; under the stadium the same body throws its attack twice
            # and the swap is the whole turn. Requiring the KNOCKOUT on the first
            # wave is what keeps the two apart: the relay never gives up the prize
            # the doomed ex was going to cash, it only refuses to pay two for it.
            # See [[el-doble-ataque-del-estadio-tambien-es-nuestro]].
            # =================================================================
            # THE OTHER EDGE, read for the WHOLE board and not only for the
            # pivot: is the stadium paying US this turn? A Dipplin of ours --
            # active or benched -- that can attack today and whose Do the Wave
            # knocks their Active out is cashing a prize that only exists while
            # Festival Grounds is on the field. The counter-stadium rule reads it
            # so it does not buy next turn's safety with this turn's prize.
            if AGENT_STATE._festival_grounds_in_play and _op_act_main is not None:
                _flpn_op_hp = _op_act_main.hp or 0
                for _flpn_i, _flpn_pk in enumerate(my_cards):
                    if _flpn_pk is None or _flpn_pk.id != Dipplin:
                        continue
                    # The wave counts the bench the ATTACK sees: with the Dipplin
                    # already in front that is the bench as it stands, and from
                    # the bench it is the bench the retreat swaps it out of --
                    # the same count either way
                    # ([[la-retirada-intercambia-cuerpos-la-banca-no-encoge]]).
                    if _flpn_i >= 1 and not can_switch:
                        continue
                    _flpn_eff = len(_flpn_pk.energies) * _grass_mult()
                    if _flpn_eff < AGENT_STATE.ATTACK_ENERGY_REQ.get(Dipplin, 1):
                        if state.energyAttached or hand_counts.get(Basic_Grass_Energy, 0) < 1:
                            continue
                        if _flpn_eff + _grass_attach_unit() < AGENT_STATE.ATTACK_ENERGY_REQ.get(Dipplin, 1):
                            continue
                    _flpn_dmg = _our_effective_damage(
                        _flpn_pk, _op_act_main, 20 * bench_count,
                        AGENT_STATE.meganium_in_play, neutralization_zone_active)
                    if _flpn_dmg > 0 and _flpn_dmg >= _flpn_op_hp:
                        _festival_lead_pays_us_now = True
                        break

            if (not _hydra_pivot_active and not _tapu_sac_pivot
                    and can_switch
                    and AGENT_STATE._festival_grounds_in_play
                    and _op_act_main is not None and _ret_active is not None
                    and _ret_active.id in OUR_EX_IDS
                    and active_ko_likely
                    and my_prize > prize_count_op(_op_act_main)):
                _fsac_op_hp = _op_act_main.hp or 0
                # The bench the wave counts is the one the RETREAT leaves behind,
                # and a retreat SWAPS bodies -- the ex goes down as the Dipplin
                # comes up, so the count does not change
                # ([[la-retirada-intercambia-cuerpos-la-banca-no-encoge]]). The
                # promotion after a knockout is the other case and discounts one;
                # that is not this route.
                for _fsac_i, _fsac_pk in enumerate(my_cards):
                    if _fsac_i == 0 or _fsac_pk is None or _fsac_pk.id != Dipplin:
                        continue
                    _fsac_e = len(_fsac_pk.energies)
                    _fsac_eff = _fsac_e * _grass_mult()
                    # Do the Wave costs ONE Grass: the body is either already
                    # charged or this turn's attachment reaches it. The retreat
                    # fee is paid by the ACTIVE and cannot charge the relay.
                    _fsac_needs_energy = _fsac_eff < AGENT_STATE.ATTACK_ENERGY_REQ.get(Dipplin, 1)
                    if _fsac_needs_energy:
                        if state.energyAttached or hand_counts.get(Basic_Grass_Energy, 0) < 1:
                            continue
                        _fsac_eff += _grass_attach_unit()
                        if _fsac_eff < AGENT_STATE.ATTACK_ENERGY_REQ.get(Dipplin, 1):
                            continue
                    _fsac_dmg = _our_effective_damage(
                        _fsac_pk, _op_act_main, 20 * bench_count,
                        AGENT_STATE.meganium_in_play, neutralization_zone_active)
                    if _fsac_dmg <= 0 or _fsac_dmg < _fsac_op_hp:
                        continue
                    # The relay must not hand over MORE than the body it replaces
                    # ([[la-retirada-elige-quien-paga-el-premio]]).
                    if prize_count(_fsac_pk) >= prize_count(_ret_active):
                        continue
                    AGENT_STATE.plan.attacker = _fsac_i
                    AGENT_STATE.plan.target = 0
                    AGENT_STATE.plan.attack_index = 0
                    AGENT_STATE.plan.remain_hp = _fsac_op_hp - _fsac_dmg
                    AGENT_STATE.plan.energy = _fsac_needs_energy
                    _festival_sac_pivot = True
                    break

            # --- Prize denial: defensive pivot to a 1-prize body ---
            # An analysis BEFORE attacking (user, log 86211357 step 128, LOST vs
            # Mega Starmie). If our active is an ex (2 prizes) that will be
            # KNOCKED OUT next turn and with that KO the opponent REACHES the prizes
            # they need to WIN (prize_count(active) >= op_prize, with
            # op_prize >= 2), it is not worth attacking with the doomed active. Instead
            # we retreat it and bring up a benched Pokemon worth FEWER prizes
            # (non-ex = 1 prize) that can attack; that way, even if it is knocked out, the
            # opponent does NOT complete the prizes to win that turn. We prefer the
            # body that also SURVIVES the opponent's attack (it holds); if none
            # survives, the one with the MOST damage. Unlike `_tapu_sac_pivot`, this one
            # does NOT require the body to knock the opponent out: it is purely defensive
            # (buying time by denying the lethal prize). EXCEPTION: if the active
            # itself can finish and WIN this very turn, it does not retreat (it attacks).
            if (not _prize_denial_pivot
                    and not _hydra_pivot_active and not _tapu_sac_pivot
                    and not _festival_sac_pivot
                    and can_switch
                    and _op_act_main is not None and _ret_active is not None
                    and _ret_active.id in OUR_EX_IDS
                    and active_ko_likely
                    and op_prize >= 2
                    and prize_count(_ret_active) >= op_prize):

                # The ACTIVE's damage against the opposing active. TWO things consume it:
                # the winning finisher below (`_pdp_active_wins_now`: if the active's KO
                # already WINS the game, we attack and do not retreat) and the
                # guard of the EX FALLBACK (`_pdx_act_margin`), which compares the
                # benched candidate against the body that is ALREADY in front. Before,
                # it was computed only inside the "win now" gate, so the
                # fallback had no way of knowing whether the active did the same.
                _pdp_ae = len(_ret_active.energies)
                _pdp_aeff = _pdp_ae * _grass_mult()
                _pdp_abase = 0
                if _ret_active.id == Hydrapple_ex and _pdp_aeff >= 2:
                    _pdp_abase = 30 + 30 * total_grass
                elif _ret_active.id == Teal_Mask_Ogerpon_ex and _pdp_aeff >= 3:
                    # Myriad counts the energy of BOTH actives (verified).
                    _pdp_abase = 30 + 30 * (
                        _pdp_ae + len(getattr(_op_act_main, 'energies', []) or []))
                elif _ret_active.id == Fezandipiti_ex and _pdp_aeff >= 3:
                    _pdp_abase = 100
                _pdp_adm = 0
                if _pdp_abase > 0:
                    _pdp_adm = _our_effective_damage(
                        _ret_active, _op_act_main, _pdp_abase,
                        AGENT_STATE.meganium_in_play, neutralization_zone_active)
                _pdp_active_ko = (_pdp_adm > 0
                                  and _pdp_adm >= (_op_act_main.hp or 0))
                # If the active itself can take a KO that makes us WIN right now,
                # we attack (we do not retreat).
                _pdp_active_wins_now = (
                    _pdp_active_ko and my_prize <= prize_count_op(_op_act_main))

                if not _pdp_active_wins_now:
                    _pdp_best_i = -1
                    _pdp_best_key = None
                    for _pdp_i, _pdp_pk in enumerate(my_cards):
                        if _pdp_i == 0 or _pdp_pk is None:
                            continue
                        # Only bodies that hand over FEWER prizes than the
                        # opponent needs to win (non-ex): that way the KO does not close it.
                        if prize_count(_pdp_pk) >= op_prize:
                            continue
                        _pdp_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(_pdp_pk.id)
                        if _pdp_req is None:
                            continue
                        _pdp_e = len(_pdp_pk.energies)
                        _pdp_eff = _pdp_e * _grass_mult()
                        _pdp_can_attach = (
                            hand_counts.get(Basic_Grass_Energy, 0) >= 1
                            and not state.energyAttached)
                        _pdp_eff_after = _pdp_eff + (
                            _grass_attach_unit() if _pdp_can_attach else 0)
                        if _pdp_eff_after < _pdp_req:
                            continue  # it cannot attack this turn
                        # Estimated damage of the body against the opposing active.
                        _pdp_base = 0
                        if _pdp_pk.id == Tapu_Bulu:
                            _pdp_base = 220
                        elif _pdp_pk.id == Meganium:
                            _pdp_base = 140
                        elif _pdp_pk.id == Pinsir:
                            _pdp_base = 100
                        elif _pdp_pk.id == Dipplin:
                            _pdp_base = 20 * max(0, bench_count - 1)
                        _pdp_dmg = _our_effective_damage(
                            _pdp_pk, _op_act_main, _pdp_base,
                            AGENT_STATE.meganium_in_play, neutralization_zone_active
                        ) if _pdp_base > 0 else 0
                        # Preference: (survives the opposing attack, damage, HP).
                        _pdp_hp = _pdp_pk.hp or 0
                        _pdp_survives = 1 if (_pdp_hp > _op_best_damage_vs(_pdp_pk)) else 0
                        _pdp_key = (_pdp_survives, _pdp_dmg, _pdp_hp)
                        if _pdp_best_key is None or _pdp_key > _pdp_best_key:
                            _pdp_best_key = _pdp_key
                            _pdp_best_i = _pdp_i
                    if _pdp_best_i >= 1:
                        AGENT_STATE.plan.attacker = _pdp_best_i
                        AGENT_STATE.plan.target = 0
                        AGENT_STATE.plan.attack_index = 0
                        AGENT_STATE.plan.remain_hp = (_op_act_main.hp or 1)
                        AGENT_STATE.plan.energy = False
                        _prize_denial_pivot = True
                    else:
                        # EX FALLBACK (user, registro_013 step 139 vs
                        # Archaludon/Cinderace, LOST): with no 1-prize body
                        # able to attack, the 2nd option is to bring up an
                        # EX from the bench that (a) KNOCKS OUT the opposing active and (b)
                        # SURVIVES the best projected hit from the opposing
                        # BENCH (the opposing active dies with our KO; the
                        # threat that remains is their promoted bench). Before, the
                        # agent attacked with the 10 HP Hydrapple ex: a KO on
                        # the Duraludon, but the benched Cinderace (Turbo Flare
                        # 50 x2 weakness = 100) finished it and the opponent
                        # took their 2 LAST prizes = a LOSS. The
                        # right play: retreat and promote the charged Ogerpon ex
                        # (Myriad 300 - 30 resistance = 270 >= 130 KO; 210 HP
                        # > 100) -> the same KO without giving away the game. If the
                        # candidate does not knock out or also dies, it does not apply (the
                        # opponent would win anyway with their 2 prizes on the ex).
                        #
                        # GUARD "the one that endures goes IN FRONT" (user, registro_012
                        # step 174 vs Alakazam, LOST): the candidate has to
                        # IMPROVE on the body already in front, not merely meet
                        # the two requirements in the abstract. Here the active was a
                        # Teal Mask Ogerpon ex at 210/210 with 4 energies -- a KO on
                        # the Alakazam (Myriad 30+30*(4+1)=180 >= 140) and a margin of
                        # 210-30 = 180 against the best hit from their bench -- and the
                        # only candidate was the OTHER Ogerpon ex, at **50 HP** and
                        # a margin of 20. The fallback compared candidates with each other and
                        # never against the active, so it retreated the 210 one,
                        # paid an energy and left in front the 50 one: the same KO,
                        # the same 2 prizes at stake and a body that dies to
                        # anything. Both sides of the swap are ex (the loop
                        # only looks at `OUR_EX_IDS`), so the prizes tie and
                        # the only thing that decides is how much it ENDURES: a STRICTLY
                        # greater margin is required, because the swap also costs the
                        # retreat energy.
                        _pdx_act_margin = None
                        if _pdp_active_ko:
                            _pdx_act_threat = 0
                            for _pdx_ob in op_state.bench:
                                if _pdx_ob is None:
                                    continue
                                _pdx_act_threat = max(
                                    _pdx_act_threat,
                                    _op_active_attack_damage_to(
                                        _pdx_ob, _ret_active,
                                        getattr(op_state, 'handCount', None)))
                            if _pdx_act_threat < (_ret_active.hp or 0):
                                _pdx_act_margin = (
                                    (_ret_active.hp or 0) - _pdx_act_threat)
                        _pdx_best_i = -1
                        _pdx_best_margin = None
                        for _pdx_i, _pdx_pk in enumerate(my_cards):
                            if _pdx_i == 0 or _pdx_pk is None:
                                continue
                            if _pdx_pk.id not in OUR_EX_IDS:
                                continue
                            _pdx_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(_pdx_pk.id)
                            if _pdx_req is None:
                                continue
                            _pdx_eff = len(_pdx_pk.energies) * _grass_mult()
                            _pdx_can_attach = (
                                hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                and not state.energyAttached)
                            if _pdx_eff + (_grass_attach_unit()
                                           if _pdx_can_attach else 0) < _pdx_req:
                                continue  # it cannot attack this turn
                            _pdx_base = 0
                            if _pdx_pk.id == Hydrapple_ex:
                                _pdx_base = 30 + 30 * total_grass
                            elif _pdx_pk.id == Teal_Mask_Ogerpon_ex:
                                # Myriad counts the energy of BOTH actives.
                                _pdx_base = 30 + 30 * (
                                    len(_pdx_pk.energies)
                                    + len(getattr(_op_act_main, 'energies', [])
                                          or []))
                            elif _pdx_pk.id == Fezandipiti_ex:
                                _pdx_base = 100
                            if _pdx_base <= 0:
                                continue
                            _pdx_dmg = _our_effective_damage(
                                _pdx_pk, _op_act_main, _pdx_base,
                                AGENT_STATE.meganium_in_play, neutralization_zone_active)
                            if _pdx_dmg <= 0 or _pdx_dmg < (_op_act_main.hp or 0):
                                continue  # it must KNOCK OUT the opposing active
                            _pdx_hp = _pdx_pk.hp or 0
                            _pdx_threat = 0
                            for _pdx_ob in op_state.bench:
                                if _pdx_ob is None:
                                    continue
                                _pdx_threat = max(
                                    _pdx_threat,
                                    _op_active_attack_damage_to(
                                        _pdx_ob, _pdx_pk,
                                        getattr(op_state, 'handCount', None)))
                            if _pdx_threat >= _pdx_hp:
                                continue  # they knock it out too: it denies nothing
                            _pdx_margin = _pdx_hp - _pdx_threat
                            if (_pdx_act_margin is not None
                                    and _pdx_margin <= _pdx_act_margin):
                                # The active already knocks out and endures as much or more: the
                                # retreat would only swap one body for a worse one
                                # (see the guard above).
                                continue
                            if (_pdx_best_margin is None
                                    or _pdx_margin > _pdx_best_margin):
                                _pdx_best_margin = _pdx_margin
                                _pdx_best_i = _pdx_i
                        if _pdx_best_i >= 1:
                            AGENT_STATE.plan.attacker = _pdx_best_i
                            AGENT_STATE.plan.target = 0
                            AGENT_STATE.plan.attack_index = 0
                            AGENT_STATE.plan.remain_hp = 0
                            AGENT_STATE.plan.energy = False
                            _prize_denial_pivot = True

            # It restores the winning finisher with the active if some mismatch pivot
            # diverted it: no prize consideration matters
            # when the KO on the opposing active (with no bench) WINS the game.
            if _active_win_plan is not None and AGENT_STATE.plan.attacker != 0:
                (AGENT_STATE.plan.attacker, AGENT_STATE.plan.target, AGENT_STATE.plan.attack_index,
                 AGENT_STATE.plan.remain_hp, AGENT_STATE.plan.energy) = _active_win_plan

        _act_stall = my_state.active[0] if my_state.active else None
        if _act_stall is not None:
            # Single source of values: ATTACK_ENERGY_REQ (main attackers
            # only, the same set of keys as before).
            _ATK_REQS_STALL = {k: AGENT_STATE.ATTACK_ENERGY_REQ[k] for k in MAIN_ATTACKERS}
            _stall_req = _ATK_REQS_STALL.get(_act_stall.id, 999)
            _stall_eff = len(_act_stall.energies) * _grass_mult()
            _stall_can_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                 and not state.energyAttached)
            _stall_after = _stall_eff + (
                _grass_attach_unit() if _stall_can_attach else 0)

            if _stall_after < _stall_req:

                _nrg_deck = AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                    Basic_Grass_Energy, {}).get(ZONE_DECK, 0)
                _deck_total = max(1, sum(
                    v.get(ZONE_DECK, 0) for v in AGENT_STATE.ACTIVE_CARDS_IN_DECK.values()))

                _td_stall = sum(
                    1 for p in (list(my_state.active or []) + list(my_state.bench))
                    if p is not None and p.id == Teal_Mask_Ogerpon_ex
                    and len(p.energies) >= 1)

                # THE CHAIN NEEDS A SEED CARD (user, registro_004 step 48,
                # episode 89624233 vs a pure Teal Mask Ogerpon ex deck, LOST).
                # Teal Dance attaches a Grass FROM HAND and only then draws, so
                # with no Grass reachable there is no first dance, no card is
                # drawn, and the probability below is measuring a route that
                # does not exist. On that turn the active carried 1 energy of
                # the 3 its attack needs and the hand held no Grass at all --
                # but three Ogerpon with energy stood on the board and 9 Grass
                # were left in 41 cards, so the chain priced three draws at a 52%
                # chance of charging and the turn did not read as stalled: the
                # menu of that step offers PLAY, RETREAT and END and no ABILITY
                # option at all. Everything downstream followed from that wrong
                # reading: the Meowth -> Lillie's engine (21800) never fired,
                # the Meowth ex fell through to the generic ladder (which vetoes
                # it with a hand of 7) and the turn's Supporter went to a
                # Xerosic that discarded five of their cards and changed nothing
                # about a board that could not attack. They knocked the active
                # out on the reply.
                #
                # `_reachable_grass_for` is the same census the plan uses: the
                # Grass in hand PLUS the one a Night Stretcher pulls out of the
                # discard, which is a real seed -- the card lands in hand and
                # the dance can pay with it. The deck is deliberately not a
                # source here: it is exactly what the chain below is already
                # weighing.
                _td_seed = _reachable_grass_for(
                    _act_stall, state, my_state, hand_counts, field_counts) > 0
                if _td_stall <= 0 or _nrg_deck <= 0 or not _td_seed:
                    _active_cant_attack_this_turn = True
                else:

                    _p_no = 1.0
                    for _ in range(min(_td_stall, 4)):
                        _p_no *= max(0, _deck_total - _nrg_deck) / _deck_total
                    _active_cant_attack_this_turn = (_p_no > 0.5)

            if _active_cant_attack_this_turn and can_switch:
                for _bp_s in my_state.bench:
                    if (_bp_s is not None and _bp_s.id in _ATK_REQS_STALL
                            and _bp_s.id != Meowth_ex):
                        _bp_eff_s = len(_bp_s.energies) * _grass_mult()
                        if _bp_eff_s >= _ATK_REQS_STALL[_bp_s.id]:
                            _active_cant_attack_this_turn = False
                            break

    def evaluate_supporters():
        return _evaluate_supporters_impl(
            CtxEvaluateSupporters(
            _active_cant_attack_this_turn=_active_cant_attack_this_turn,
            _grass_plan=_grass_plan,
            bench_count=bench_count,
            bench_max=bench_max,
            budew_on_op_field=budew_on_op_field,
            budew_op_index=budew_op_index,
            can_switch=can_switch,
            estimated_op_damage=estimated_op_damage,
            field_counts=field_counts,
            hand_counts=hand_counts,
            has_hydrapple=has_hydrapple,
            has_switch_card=has_switch_card,
            meowth_ability_lock=meowth_ability_lock,
            my_prize=my_prize,
            my_state=my_state,
            neutralization_zone_active=neutralization_zone_active,
            op_active_dodge_immune=op_active_dodge_immune,
            op_has_ability_immune_active=op_has_ability_immune_active,
            op_has_crustle_bench=op_has_crustle_bench,
            op_has_dreepy_line=op_has_dreepy_line,
            op_has_dwebble_bench=op_has_dwebble_bench,
            op_has_eevee_bench=op_has_eevee_bench,
            op_has_ethan_preevo=op_has_ethan_preevo,
            op_has_ex_immune_active=op_has_ex_immune_active,
            op_has_ex_immune_bench=op_has_ex_immune_bench,
            op_has_froslass=op_has_froslass,
            op_has_latias_ex=op_has_latias_ex,
            op_has_munkidori=op_has_munkidori,
            op_has_snorunt_bench=op_has_snorunt_bench,
            op_has_typhlosion=op_has_typhlosion,
            op_is_alakazam_deck=op_is_alakazam_deck,
            op_is_dragapult_dusknoir=op_is_dragapult_dusknoir,
            op_is_drednaw_deck=op_is_drednaw_deck,
            op_is_gardevoir_deck=op_is_gardevoir_deck,
            op_is_slowking_deck=op_is_slowking_deck,
            op_is_sylveon_deck=op_is_sylveon_deck,
            op_is_zoroark_deck=op_is_zoroark_deck,
            op_prize=op_prize,
            op_state=op_state,
            state=state,
            total_grass=total_grass,
            ),
        )

    _supp_values = evaluate_supporters()

    _best_supp_in_hand_val = 0
    _best_supp_in_hand_id = None
    for sid in (Boss_Orders, Dawn, Lillie_Determination, Lanas_Aid):
        if hand_counts.get(sid, 0) >= 1 and _supp_values.get(sid, 0) > _best_supp_in_hand_val:
            _best_supp_in_hand_val = _supp_values[sid]
            _best_supp_in_hand_id = sid

    # =================================================================
    # MATCH POINT against the opposing ACTIVE: the finisher is on the BENCH
    # -----------------------------------------------------------------
    # (user, registro_010 step 144 vs Marnie's Grimmsnarl ex, LOST --
    # episode 89104831). At 2 prizes, with a Fezandipiti ex at 20 HP as the active
    # (2 effective: it does NOT reach its cost-3 attack) and a benched Teal Mask
    # Ogerpon ex already at 4 energies, the opposing ACTIVE was the **Marnie's
    # Grimmsnarl ex itself at 310/320 HP, with 3 energies and a Grass WEAKNESS**:
    # Myriad Leaf Shower = 30 + 30 x (4 of ours + 3 of THEIRS) = 240, x2 for
    # weakness = **480 >= 310** -> a KO on a **2-prize** ex = the 2 we
    # were missing = GAME WON. The chain (retreat -> promote -> attack)
    # was served up and payable: the Fezandipiti had energy to spare
    # for its retreat cost of 1. The agent played Boss's Orders and gusted a
    # 1-prize Froslass; the opponent finished on their turn.
    #
    # **Why:** every reading of "can I knock out the opposing ACTIVE?" is done
    # with the Pokemon that is in the active spot TODAY (`_boss_dmg_to` ->
    # `_bo_can_ko_active`, `_bpr_active_can_ko`). With our own active STUCK
    # that gives 0 -> `_bo_active_prize = 0` -> the opposing active becomes INVISIBLE
    # as a target and ANY bench prize (1) beats that "0". The
    # asymmetry is the bug: for BENCH targets the same block DOES look
    # through the retreat (`_bench_attacker_can_ko` in `_boss_prize_rank` and in
    # `_bo_win_via_bench`), but for the ACTIVE it never does. Here that
    # symmetry is closed in the one case that admits no discussion: when that KO WINS the
    # game. Winning is a VETO -- the same criterion as PROMO_MATCH_POINT_VETO: if the
    # turn closes the game by retreating, no lesser-prize gust can
    # divert it.
    #
    # It requires the finisher to be on the BENCH: if the CURRENT active already knocks out, the
    # route is to attack (`_active_attack_wins_now`, 99000) and not to retreat.
    #
    # It does NOT apply against IMMUNE WALLS in the active spot (ex-immune Crustle/Sylveon,
    # ability-immune Cornerstone). That case already has its own measured
    # machinery -- `_wall_ko_promote` does exactly this relief and YIELDS to the gust
    # on purpose ([[boss-el-chip-al-activo-no-es-un-premio]]: the same prize
    # comes cheaper without paying the retreat), and `rematar_muro_inmune_antes_de_
    # gustear` orders the rest. Without this guard the veto overrode that yield: measured
    # in self-play, the rule fired in **8%** of the
    # crustle/cornerstone games (120/1500, against 0.8% vs Marnie) and both matchups
    # lost ~0.6-0.75 pp. With the guard the firing is restricted to the
    # boards where nobody else looks at the opposing active through the retreat.
    #
    # `_promote_ko_active_prizes` answers the whole question in ONE place (see its
    # docstring): how many prizes the KO on the opposing ACTIVE is worth through
    # the retreat, 0 when that route does not exist. `_win_ko_active_via_promote`
    # is now the special case "and those prizes WIN the game", and
    # `_boss_active_prizes_via_promote` is the same number for the comparisons
    # that do NOT close the game (see `_boss_prize_rank` further down).
    _boss_active_prizes_via_promote = 0
    if (context == SelectContext.MAIN and can_switch
            and not op_has_ex_immune_active
            and not op_has_ability_immune_active
            and op_state.active and op_state.active[0] is not None
            and my_state.active and my_state.active[0] is not None):
        _boss_active_prizes_via_promote = _promote_ko_active_prizes(
            my_state, op_state.active[0], can_switch, has_switch_card,
            (hand_counts.get(Basic_Grass_Energy, 0) >= 1
             and not state.energyAttached),
            total_grass, bench_count, AGENT_STATE.meganium_in_play,
            neutralization_zone_active)
    _win_ko_active_via_promote = (_boss_active_prizes_via_promote >= my_prize
                                  and _boss_active_prizes_via_promote > 0)

    _boss_prize_rank = 0
    # `_boss_ko_threat_preevo`: there is a THREAT PRE-EVOLUTION on the opposing bench
    # (Duraludon->Archaludon, etc.: THREAT_PREEVO_IDS) that we can gust and
    # KNOCK OUT this turn. Unlike `_boss_prize_rank`, it is NOT cancelled when
    # the attack on the active is "enough": it serves to decide to KEEP the Boss's
    # (vetoing Lillie's) even if the active could attack (user, registro_007 p78).
    _boss_ko_threat_preevo = False
    # Best PRIZE among the gust targets this loop declares knockable: the term the
    # comparison against the opposing active was missing (see below).
    _bpr_best_prizes = 0
    if (context == SelectContext.MAIN
            and hand_counts.get(Boss_Orders, 0) >= 1
            and op_state.active and op_state.active[0] is not None):
        _bpr_active = my_state.active[0] if my_state.active else None
        _bpr_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                       and not state.energyAttached)

        _bpr_ret_cost = 0 if has_switch_card else (
            RETREAT_COST.get(_bpr_active.id, 1) if _bpr_active is not None else 1)
        # Wild Growth: each Grass pays for two, fewer cards discarded when retreating.
        _bpr_ret_cards = _retreat_grass_units(_bpr_ret_cost)
        _bpr_grass_after = max(0, total_grass - _bpr_ret_cards)

        def _bpr_active_can_ko(_tgt):
            if _bpr_active is None or _tgt is None:
                return False
            e = len(_bpr_active.energies)
            eff = e * _grass_mult()
            eff_a = eff + (_grass_attach_unit() if _bpr_attach else 0)
            e_a = e + (1 if _bpr_attach else 0)
            base = _attacker_base_damage(_bpr_active.id, _tgt, eff_a,
                                         grass_scale=total_grass,
                                         teal_self_energy=e_a, bench_count=bench_count)
            if base <= 0:
                return False
            _d = _our_effective_damage(_bpr_active, _tgt, base,
                                       AGENT_STATE.meganium_in_play, neutralization_zone_active)
            return _d >= (_tgt.hp or 0) and _d > 0

        for _bpr_tgt in (op_state.bench or []):
            if _bpr_tgt is None:
                continue
            _bpr_td = card_table.get(_bpr_tgt.id)
            if _bpr_td is None:
                continue
            # log 86339758 step 98: Dwebble is vetoed as a gust target
            # in a Crustle deck; it must not count in the Boss's prize ranking.
            if AGENT_STATE.op_is_crustle_deck and _bpr_tgt.id in (Dwebble_Grass, Dwebble_Fighting):
                continue

            if getattr(_bpr_td, 'megaEx', False):
                _bpr_base = 1
            elif getattr(_bpr_td, 'ex', False):
                _bpr_base = 3
            elif getattr(_bpr_td, 'stage2', False):
                _bpr_base = 5
            elif getattr(_bpr_td, 'stage1', False):
                _bpr_base = 7
            elif _bpr_tgt.id in THREAT_PREEVO_IDS:

                _bpr_base = 7
            else:
                continue

            _bpr_ko = _bpr_active_can_ko(_bpr_tgt)
            if not _bpr_ko and can_switch:
                _bpr_ko = _bench_attacker_can_ko(
                    my_state, _bpr_tgt, AGENT_STATE.meganium_in_play, total_grass,
                    bench_count, _bpr_grass_after, neutralization_zone_active)
            if not _bpr_ko:
                continue
            _bpr_rank = _bpr_base + (0 if len(_bpr_tgt.energies) >= 1 else 1)
            if _boss_prize_rank == 0 or _bpr_rank < _boss_prize_rank:
                _boss_prize_rank = _bpr_rank
            if prize_count_op(_bpr_tgt) > _bpr_best_prizes:
                _bpr_best_prizes = prize_count_op(_bpr_tgt)
            if _bpr_tgt.id in THREAT_PREEVO_IDS:
                _boss_ko_threat_preevo = True

    # THE PRIZE IN FRONT, DOWN THE SAME ROUTE (user, registro_006 step 97 vs
    # Marnie's Grimmsnarl ex, LOST -- deck-agnostic). Our active was a Teal Mask
    # Ogerpon ex at 2 energies (it does NOT reach Myriad Leaf Shower's 3, so
    # `_bpr_active_can_ko` read 0 against everything) and on the BENCH there was
    # another one already at 3. In front stood the **Marnie's Grimmsnarl ex at
    # 310/320 with 3 energies and a Grass weakness**: 30 + 30 x (3 ours + 3
    # theirs) = 210, x2 = 420 >= 310 -> a **2-prize** KO, served up by the very
    # retreat this loop already grants the BENCH targets (`_bench_attacker_can_ko`,
    # right above). The loop only measured their bench, found the charged
    # Marnie's Morgrem (rank 7) and played Boss's on it: the same turn cashed
    # **1 prize instead of 2** and left the Grimmsnarl ex alive to answer.
    #
    # The rule is the dominance, not the deck: a gust is a SWAP of the target we
    # knock out, so it can never be right to pay a Supporter to swap what is in
    # front for something worth STRICTLY FEWER prizes when the same retreat
    # already finishes what is in front. STRICT `>` on purpose -- on EQUAL prizes
    # the gust keeps ruling, which is what cutting the opposing line lives on
    # ([[boss-gust-mayor-evolucion-fase2]], `_bo_pe_outranks_active` and company).
    _bpr_active_prize_dominates = (_boss_active_prizes_via_promote > _bpr_best_prizes)

    if (_bo_active_attack_sufficient
            or _supp_values.get('_active_attack_sufficient')
            # The opposing active IS ALREADY the winning prize and the bench finishes it after
            # retreating: no lesser-prize gust can motivate the Supporter.
            or _win_ko_active_via_promote
            or _bpr_active_prize_dominates):
        _boss_prize_rank = 0

    # =================================================================
    # Req H (log 86023830, step 69): vs a Mega Lucario deck, if the opponent
    # has a Riolu (the pre-evolution of their main attacker Mega Lucario
    # ex) on the bench that we can gust and knock out, and we already have our own
    # bench established (>=2 Pokemon, enough charged attackers), the
    # priority is NOT to refill the hand or develop (Meowth ex,
    # Chikorita, Tapu...), but to play Boss's Orders on the Riolu to
    # cut the line of their main attacker. `_boss_deny_evo` already confirms
    # that there is a gustable and knockable ex pre-evolution on the opposing bench
    # (a harmless wall in the active spot); the specific target is chosen by
    # the tier_ko/jam adjustment, which prefers the Riolu through THREAT_PREEVO_IDS. This flag
    # VETOES the development plays (tier DEVELOP) further down so that Boss's
    # (a supporter, tier 0) is the play chosen over Meowth ex.
    # The veto EXEMPTS Fezandipiti ex with its ability alive (see there): putting it down
    # does not consume the turn's Supporter, so it does not compete with the Boss's.
    # =================================================================
    _lucario_riolu_gust = (
        op_is_lucario_deck
        and not state.supporterPlayed
        and hand_counts.get(Boss_Orders, 0) >= 1
        and bench_count >= 2
        and bool(_supp_values.get('_boss_deny_evo'))
        and any(bp is not None and bp.id == Riolu
                for bp in (op_state.bench or [])))

    _boss_win_via_bench = bool(_supp_values.get('_boss_win_via_bench'))

    _boss_dodge_redirect = bool(_supp_values.get('_boss_dodge_redirect'))

    _boss_deny_alakazam_line = bool(_supp_values.get('_boss_deny_alakazam_line'))

    # The trap gust of a dead turn. The value is read as well, because the
    # anti-Crustle guard at the end of `evaluate_supporters` can still zero the
    # Boss's after the flag has been raised.
    _boss_trap_gust = (bool(_supp_values.get('_boss_trap_gust'))
                       and _supp_values.get(Boss_Orders, 0) > 0)

    _best_supp_in_deck_val = 0
    _best_supp_in_deck_id = None
    for sid in (Boss_Orders, Dawn, Lillie_Determination, Lanas_Aid):
        if AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(sid, {}).get(ZONE_DECK, 0) > 0:
            val = _supp_values.get(sid, 0)
            if val > _best_supp_in_deck_val:
                _best_supp_in_deck_val = val
                _best_supp_in_deck_id = sid

    # TEAL DANCE AVAILABILITY, STABLE THROUGHOUT THE TURN (user).
    # Abilities only appear as options in the MAIN MENU; in the
    # chained prompts (search the deck, choose the target of an attachment,
    # discard...) the select does NOT list them. Reading `select.option` from those
    # prompts ALWAYS gave "Teal Dance not available", so the SAME turn
    # projected different damage depending on the prompt we were in: the engine
    # put Meowth ex down "to search for Boss's Orders" (a flag computed in the menu,
    # WITH Teal Dance) and two steps later the fetch valued that same Boss's at 0
    # (a flag WITHOUT Teal Dance) and took another card (registro_010 steps 118/120).
    # The SERIAL of the active whose ability was offered by the turn's last main
    # menu is cached: between one menu and the next the ability's state cannot
    # change, and requiring the serial avoids carrying the cache over if we retreat and
    # promote another Pokemon.
    if context == SelectContext.MAIN:
        AGENT_STATE._td_ability_serial = None
        _td_act = _active_of(my_state)
        if _td_act is not None and any(
                o.type == OptionType.ABILITY and o.area == AreaType.ACTIVE
                for o in select.option):
            AGENT_STATE._td_ability_serial = getattr(_td_act, 'serial', None)

    _gust_2prize_via_boss = False
    _win_via_boss_gust = False
    _deny_evo_via_boss = False
    # The EX-IMMUNE WALL (Crustle / Sylveon) is the opposing ACTIVE and our
    # active KNOCKS IT OUT TODAY -> killing it comes FIRST (see the
    # `finish_the_immune_wall_before_gusting` rule of _RULES_BOSS_PLAY).
    _ex_immune_wall_ko_ready = False
    if (not state.supporterPlayed
            and my_state.active and my_state.active[0] is not None
            and op_state.active and op_state.active[0] is not None
            and op_state.bench
            and (hand_counts.get(Boss_Orders, 0) >= 1
                 or AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Boss_Orders, {}).get(ZONE_DECK, 0) > 0)):
        _mbw_atk = my_state.active[0]
        # Teal Dance of the ACTIVE itself (user, pending from the Myriad combo): the
        # ability attaches ANOTHER Grass from hand and is INDEPENDENT of the
        # manual attachment, so the energy reachable this turn can be +2
        # (attachment + Teal Dance) and not +1. Without modelling it, the winning finisher via
        # Boss's was not detected as soon as the manual attachment was already spent
        # (energyAttached) even if the ability was still available.
        # `_pending_grass_extra_eff` is now the SINGLE SOURCE OF TRUTH for that
        # projection: the gust TARGET scorer (`_ctx_gust_target`) reads the very
        # same helper, so the body this detector promises the game on is the body
        # the target scorer aims at (registro_014 step 154).
        _mbw_extra_eff = _pending_grass_extra_eff(
            _mbw_atk, hand_counts.get(Basic_Grass_Energy, 0),
            state.energyAttached)

        def _mbw_dmg_to(_tgt):
            if _mbw_atk is None or _tgt is None:
                return 0
            _eff = len(_mbw_atk.energies) * _grass_mult()
            # EFFECTIVE energy after this turn's pending charges. Each
            # attached Grass adds `_grass_attach_unit()` (2 with Meganium), so
            # Myriad's own energy is the SAME effective magnitude
            # (before, `_atk_e` added +1 raw and with Meganium it fell short).
            _eff_after = _eff + _mbw_extra_eff
            _atk_e = _eff_after
            # Base damage via the single table _attacker_base_damage (the same formula
            # and thresholds as before; the weakness/resistance/immunity finish
            # is left inline below to preserve the exact behaviour of
            # this site, which does NOT apply the neutralization zone or the
            # Crustle cap at full HP).
            _d = _attacker_base_damage(_mbw_atk.id, _tgt, _eff_after,
                                       grass_scale=total_grass,
                                       teal_self_energy=_atk_e,
                                       bench_count=bench_count)
            if _d <= 0:
                return 0
            if _tgt.id in EX_IMMUNE_IDS and _mbw_atk.id in OUR_EX_IDS:
                return 0
            if _tgt.id in ABILITY_IMMUNE_IDS and _mbw_atk.id in OUR_ABILITY_IDS:
                return 0
            _td = card_table.get(_tgt.id)
            if _mbw_atk.id != Fezandipiti_ex and _td:
                if _td.weakness == EnergyType.GRASS:
                    _d *= 2
                elif _td.resistance == EnergyType.GRASS:
                    _d -= 30
            # Full Metal Lab, after weakness/resistance (wave 2, copy 1 of 4).
            if (full_metal_lab_active and _td
                    and getattr(_td, 'energyType', None) == EnergyType.METAL):
                _d -= 30
            if _tgt.id == Drednaw and _d >= 200:
                return 0
            return _d

        _mbw_act = op_state.active[0]
        _mbw_act_dmg = _mbw_dmg_to(_mbw_act)
        _mbw_act_ko = (_mbw_act_dmg >= (_mbw_act.hp or 0) and _mbw_act_dmg > 0)
        _mbw_act_wins = _mbw_act_ko and my_prize <= prize_count_op(_mbw_act)

        # AN EX-IMMUNE ACTIVE WALL THAT WE KNOCK OUT TODAY (user, registro_006
        # step 47 vs Crustle, LOST). Crustle/Sylveon cancel the damage of our WHOLE
        # engine (Ogerpon ex, Hydrapple ex, Meowth ex, Fezandipiti ex):
        # the window to kill them exists only when one of our NON-ex bodies
        # (Tapu Bulu, Meganium...) is charged and active, and that window
        # closes by itself (Wood Hammer's self-damage, the opponent's hit, the
        # retreat...). That is why the wall comes FIRST and the prizes afterwards: in the
        # record the agent gusted a benched Ogerpon ex to take 2
        # prizes with the same Tapu Bulu and left the Crustle alive, with the rest
        # of the board unable to touch it. It is computed with the central evaluator
        # `_our_effective_damage` (not with `_mbw_dmg_to`) because that one DOES apply
        # the Sturdy cap: the Crustle 533 at full HP survives at 10 HP,
        # so there is NO KO of the wall there and the rule must not fire.
        if _mbw_act.id in EX_IMMUNE_IDS:
            _wall_eff = (len(_mbw_atk.energies) * _grass_mult()
                         + _mbw_extra_eff)
            _wall_dmg = _our_effective_damage(
                _mbw_atk, _mbw_act,
                _attacker_base_damage(_mbw_atk.id, _mbw_act, _wall_eff,
                                      grass_scale=total_grass,
                                      teal_self_energy=_wall_eff,
                                      bench_count=bench_count),
                meganium_active=AGENT_STATE.meganium_in_play,
                neutralization_zone=neutralization_zone_active)
            _ex_immune_wall_ko_ready = (_wall_dmg > 0
                                        and _wall_dmg >= (_mbw_act.hp or 0))

        if not _mbw_act_wins:
            for _mbw_bp in op_state.bench:
                if _mbw_bp is None:
                    continue
                # log 86339758 step 98: Dwebble vetoed as a gust in a Crustle deck.
                if AGENT_STATE.op_is_crustle_deck and _mbw_bp.id in (Dwebble_Grass, Dwebble_Fighting):
                    continue
                _mbw_bp_dmg = _mbw_dmg_to(_mbw_bp)
                if (_mbw_bp_dmg >= (_mbw_bp.hp or 0) and _mbw_bp_dmg > 0
                        and my_prize <= prize_count_op(_mbw_bp)):
                    _win_via_boss_gust = True
                    break

            _mbw_act_prize = prize_count_op(_mbw_act) if _mbw_act_ko else 0
            _mbw_best_bench_prize = 0
            for _mbw_bp2 in op_state.bench:
                if _mbw_bp2 is None:
                    continue
                # log 86339758 step 98: Dwebble vetoed as a gust in a Crustle deck.
                if AGENT_STATE.op_is_crustle_deck and _mbw_bp2.id in (Dwebble_Grass, Dwebble_Fighting):
                    continue
                _mbw_bp2_dmg = _mbw_dmg_to(_mbw_bp2)
                if _mbw_bp2_dmg >= (_mbw_bp2.hp or 0) and _mbw_bp2_dmg > 0:
                    _mbw_bp2_pr = prize_count_op(_mbw_bp2)
                    if _mbw_bp2_pr > _mbw_best_bench_prize:
                        _mbw_best_bench_prize = _mbw_bp2_pr
            _mbw_trade_down = (not _mbw_act_ko and _mbw_act_dmg > 0
                               and prize_count_op(_mbw_act) > _mbw_best_bench_prize)
            # `_ex_immune_wall_ko_ready`: with the Crustle/Sylveon wall as the active
            # and knockable TODAY, the 2 prizes of the benched ex are NOT worth the
            # window (the flag also feeds the Meowth ex ->
            # Last-Ditch -> Boss's engine, which would take the turn searching for the card).
            if (_mbw_best_bench_prize >= 2
                    and _mbw_best_bench_prize > _mbw_act_prize
                    and not _mbw_trade_down
                    and not _ex_immune_wall_ko_ready):
                _gust_2prize_via_boss = True

            # VALUE gust (deny-evo) available via hand OR DECK (Meowth engine
            # plan, improvement A): a CHARGED pre-evolution of an ex line on the
            # opposing bench that we KNOCK OUT after gusting it. The in-hand machinery
            # (`_boss_deny_evo` in evaluate_supporters) requires a Boss's IN HAND;
            # this standalone flag replicates its conditions with the local helper
            # `_mbw_dmg_to` so that the Meowth ex -> Last-Ditch -> Boss's engine
            # has a path when the Boss's is in the DECK. The user's rule
            # (registro_006 step 82 vs Garchomp): ALWAYS favour beating
            # the evolution line of the opposing ex attacker. A conservative mirror:
            # damage from the ACTIVE only (no bench fallback after retreating).
            # The same yield to the knockable immune wall (`_ex_immune_wall_ko_ready`):
            # cutting an evolution line pays off in the future, killing the Crustle that
            # blocks all our ex pays off TODAY and only today.
            if (not _win_via_boss_gust and not _gust_2prize_via_boss
                    and not _ex_immune_wall_ko_ready):
                _dev_act_prize = prize_count_op(_mbw_act)
                for _dev_pe in op_state.bench:
                    if _dev_pe is None:
                        continue
                    # log 86339758 step 98: Dwebble vetoed as a gust vs Crustle.
                    if (AGENT_STATE.op_is_crustle_deck
                            and _dev_pe.id in (Dwebble_Grass, Dwebble_Fighting)):
                        continue
                    # A CHARGED pre-evolution of an ex line (2 prizes at the end);
                    # the Alakazam line (a non-ex final form, 1 prize) is excluded.
                    # The class comes from the CARD DATA (`_preevo_of_ex_line`),
                    # not from `EX_PREEVO_IDS`: the curated list covered the lines
                    # somebody hand-listed after losing a game, and
                    # left out any other one in the environment (e.g. Frillish ->
                    # Jellicent ex, which IS in the jellicent_lock deck). The
                    # helper is an exact superset of the list: all its
                    # members except Abra/Kadabra -- which is exactly what
                    # `NONEX_FINAL_PREEVO_IDS` excluded -- culminate in an ex.
                    if (not _preevo_of_ex_line(_dev_pe.id)
                            or len(_dev_pe.energies) < 1):
                        continue
                    _dev_dmg = _mbw_dmg_to(_dev_pe)
                    if not (_dev_dmg >= (_dev_pe.hp or 0) and _dev_dmg > 0):
                        continue
                    # Exception (registro_006 step 75 vs Archaludon): if the
                    # opposing ACTIVE is ALSO a THREAT pre-evolution equally or more
                    # developed, knocking it out already removes the same class of
                    # threat for the same prize -- do not spend the engine.
                    if (_mbw_act.id in THREAT_PREEVO_IDS
                            and len(_mbw_act.energies) >= len(_dev_pe.energies)):
                        continue
                    # Mirror of the STAGE VETO (registro_008 step 93): if the
                    # ACTIVE is a MORE EVOLVED link of the SAME line,
                    # knocking it out already cuts the chain higher up and it costs neither the
                    # search engine nor the Supporter.
                    if (_mbw_act_ko
                            and _is_more_evolved_than(_mbw_act, _dev_pe)
                            and _dev_act_prize >= prize_count_op(_dev_pe)):
                        continue
                    # Mirror of `_bo_pe_is_ex_preevo_energized` (EQUAL
                    # prizes: the same payout but it cuts the line) and of
                    # `_bo_pe_is_energized_preevo_vs_bare_wall` (a bare active wall
                    # worth <=1 prize: knocking it out cuts nothing).
                    if ((_mbw_act_ko
                         and _dev_act_prize == prize_count_op(_dev_pe))
                            or (len(_mbw_act.energies) == 0
                                and _dev_act_prize <= 1)):
                        _deny_evo_via_boss = True
                        break

    # Do not waste Boss's Orders on a defensive gust if we can ALREADY knock out the
    # opposing active this very turn by retreating to a ready attacker from the bench
    # (e.g. bringing up Tapu Bulu). can_attack only looks at the current active, not at the
    # retreat option, which is why it has to be checked separately.
    _bdg_retreat_ko = False
    if (can_switch and op_state.active and op_state.active[0] is not None
            and my_state.active and my_state.active[0] is not None):
        _bdg_cur_active = my_state.active[0]
        _bdg_ret_cost = (0 if has_switch_card
                         else RETREAT_COST.get(_bdg_cur_active.id, 1))
        _bdg_ret_cards = _retreat_grass_units(_bdg_ret_cost)
        _bdg_grass_after = max(0, total_grass - _bdg_ret_cards)
        _bdg_retreat_ko = _bench_attacker_can_ko(
            my_state, op_state.active[0], AGENT_STATE.meganium_in_play, total_grass,
            bench_count, _bdg_grass_after, neutralization_zone_active)

    # An attachment that ENABLES the retreat towards a LETHAL benched attacker (user,
    # registro_034 step 141 vs a Crustle/Terrakion deck, LOST): the active
    # (Fezandipiti ex, 0 energy) can neither attack NOR retreat, but on the bench
    # there is a ready attacker (a charged Dipplin: Do the Wave x2 for the Grass
    # weakness of the Terrakion = a KO) and ONE energy from hand pays the retreat
    # cost. The correct line: energy -> ACTIVE, retreat, promote and
    # knock out. It generalises `_tapu_sac_enable_retreat` (which requires a Tapu Bulu
    # >=4e) to ANY benched attacker via `_bench_attacker_can_ko` (the
    # same detector as `_bdg_retreat_ko`, which does not apply here because it requires
    # `can_switch`: the retreat is NOT legal yet). Without this, the energy
    # routing prefers Teal Dance / bench charges (~30000-31600) and the
    # KO line is lost entirely.
    # The shared core (`_grass_unlocks_active_retreat`): do the Grass energies that can
    # still land on the active pay its retreat and let a benched body
    # attack? Here it is consumed for the MANUAL attachment; further down, without the guard
    # of `state.energyAttached`, for the ABILITY route.
    #
    # The charging BUDGET towards the ACTIVE (the same computation as
    # `_charge_active_finishes`): the manual attachment if it is still free + the abilities that
    # can point at the active (`_grass_ability_slots_active`), bounded by the
    # Grass in hand. The floor of 1 preserves the historical behaviour for
    # the consumers that bring their own Grass from outside the hand (the Night
    # Stretcher recovers it from the DISCARD: there `hand_counts` is 0 and the single-Grass
    # line must stay alive).
    _grass_active_routes = (0 if state.energyAttached else 1)
    if not meowth_ability_lock:
        # With Watchtower / Iron Thorns ex the charging abilities are
        # switched off: counting them would leave the 1st Grass stranded on an active trapped
        # with nobody to complete the cost (the same guard as
        # `_grass_attach_route_open(abilities_off=...)`).
        _grass_active_routes += _grass_ability_slots_active(
            state, my_state, field_counts)
    _grass_active_budget = max(
        1, min(hand_counts.get(Basic_Grass_Energy, 0), _grass_active_routes))
    _grass_unlock_ko, _grass_unlock_chip = _grass_unlocks_active_retreat(
        my_state, op_state, AGENT_STATE.meganium_in_play, total_grass, bench_count,
        neutralization_zone_active, can_attack, budget=_grass_active_budget)

    _attach_enable_retreat_ko = (
        not _bdg_retreat_ko and not can_switch
        and not state.energyAttached
        and hand_counts.get(Basic_Grass_Energy, 0) >= 1
        and _grass_unlock_ko)

    # THE SAME LINE BUT WITHOUT A KO (user, log 88162794 turns 11 and 13 vs Archaludon ex,
    # LOST 6-1 without EVER attacking from turn 7 on). Our active (Meowth ex, 0
    # energy, retreat cost 1) can neither attack NOR retreat, and on the bench
    # a Meganium waits with energy to spare (e6/e8) that CAN attack. Solar
    # Beam does not knock out anything of the opponent's (an Archaludon ex at 300/400 HP; Duraludon
    # RESISTS Grass -30 and Full Metal Lab takes another -30), so
    # `_attach_enable_retreat_ko` -- and with it the WHOLE family of retreat
    # pivots, which require a KO -- never fired: the agent attached the Grass to the
    # benched Meganium (already fully charged, +0 damage: Solar Beam is flat) and
    # closed the turn. Four turns in a row given away.
    #
    # If the active canNOT attack in any way this turn, the chip damage of the
    # benched attacker is infinitely better than 0: the energy goes to the ACTIVE to
    # pay the retreat. The rest of the chain (RETREAT, promotion, attack) is already
    # resolved by the existing machinery as soon as the retreat is legal.
    #
    # Deck-agnostic and conservative:
    #  - it requires the benched attacker to be READY ALREADY WITHOUT this energy (if the
    #    energy is what makes it ready, its place is the bench: turn 9 of the same
    #    log, Meganium at e2 -> e4);
    #  - it always yields to the LETHAL version (`_attach_enable_retreat_ko`, 41000);
    #  - if the active is an ex, it replicates the "do not swap an ex for a worse body"
    #    guard of the retreat scorer (`_xx_vale`): the body coming up must
    #    endure at least what the ex has left. That way the attachment never enables
    #    a retreat that would then be vetoed, wasting the turn's energy.
    _attach_enable_retreat_attack = (
        not _bdg_retreat_ko and not _attach_enable_retreat_ko
        and not can_switch and not can_attack
        and not state.energyAttached
        and hand_counts.get(Basic_Grass_Energy, 0) >= 1
        and _grass_unlock_chip)

    # THE ABILITY ROUTE of the same line (user, registro_014 steps 137/141 vs
    # Alakazam, WON but with three wasted turns): the Hydrapple ex's Ripening Charge
    # "attaches a basic Grass from your hand to 1 of your Pokemon" and
    # does NOT consume the turn's manual attachment. With the active Fezandipiti ex at 0
    # energies (retreat cost 1) and a benched Hydrapple ex already ready, the
    # line "Grass to the active -> retreat -> Syrup Storm" was still available
    # AFTER the manual attachment had been spent, but the two flags
    # above switch off with `state.energyAttached` and nobody else saw it: the
    # ability was vetoed, the Grass was burned as the cost of an Ultra Ball
    # and the turn ended without attacking.
    #
    # These two do NOT look at `state.energyAttached` or at the hand: each consumer
    # adds its own condition (the ability requires Grass in hand; the Night
    # Stretcher requires Grass in the DISCARD and a live charging route).
    _ability_unlock_retreat_ko = (
        not _bdg_retreat_ko and not can_switch and _grass_unlock_ko)
    _ability_unlock_retreat_attack = (
        not _bdg_retreat_ko and not can_switch and not can_attack
        and _grass_unlock_chip)

    # Rule (user, log 85804848 step 49, vs Alakazam, WE LOST): if a benched
    # attacker can ALREADY knock out the opposing active this turn (retreat+promote,
    # `_bdg_retreat_ko`), Boss's Orders is redundant as a finisher: there is no need to
    # gust the bench to take a prize, knocking out the active is enough. In that
    # case, if we have Lillie's Determination in hand, refilling with Lillie's
    # pays more than spending the supporter on an unnecessary gust, so we cancel
    # `_boss_prize_rank` to yield priority to Lillie's. The gusts that are really
    # executable/valuable (lethal to the bench, 2 prizes) are respected, since they are
    # scored by their own branches before `_boss_prize_rank`.
    if (_bdg_retreat_ko
            and hand_counts.get(Lillie_Determination, 0) >= 1
            and not _win_via_boss_gust
            and not _gust_2prize_via_boss):
        _boss_prize_rank = 0

    _boss_defensive_gust = False
    if (AGENT_STATE.op_is_crustle_deck and not state.supporterPlayed and not can_attack
            and not _bdg_retreat_ko
            and not _conf_should_retreat
            and not _win_via_boss_gust and not _gust_2prize_via_boss
            and hand_counts.get(Boss_Orders, 0) >= 1
            and op_state.active and op_state.active[0] is not None
            and len(op_state.active[0].energies) >= 1
            and op_state.bench):
        _bdg_op_act_rc = RETREAT_COST.get(op_state.active[0].id, 0)
        _bdg_threshold = 1 if _bdg_op_act_rc == 0 else 2
        for _bdg_bp in op_state.bench:
            if _bdg_bp is None:
                continue
            _bdg_rc = RETREAT_COST.get(_bdg_bp.id, 0)
            _bdg_e = len(_bdg_bp.energies)
            if (_bdg_rc - _bdg_e) >= _bdg_threshold:
                _boss_defensive_gust = True
                break

    _meowth_devel_lillie = False
    if (not state.supporterPlayed
            and (hand_counts.get(Meowth_ex, 0) >= 1
                 or field_counts.get(Meowth_ex, 0) >= 1)
            and (AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0
                 or hand_counts.get(Lillie_Determination, 0) >= 1)):
        _mdl_in_play = 0
        for _mdl_p in (list(my_state.active or []) + list(my_state.bench or [])):
            if _mdl_p is not None and _mdl_p.id != Meowth_ex:
                _mdl_in_play += 1
        _mdl_hand_size = len(my_state.hand) if my_state.hand else 0
        _mdl_max_in_play = 4 if _mdl_hand_size <= 2 else 3
        if _mdl_in_play <= _mdl_max_in_play:
            _meowth_devel_lillie = True

    # Can we use Meowth ex's Last-Ditch Catch this turn? Its ability
    # triggers when it is PLAYED from hand, and "you can't use more than 1
    # Last-Ditch ability per turn". If some Meowth ex IN PLAY already appeared this turn
    # (appearThisTurn), its Last-Ditch is already spent -> playing ANOTHER Meowth ex would not
    # search for a Supporter. If the Meowth in play are from previous turns
    # (appearThisTurn False), the ability is available and playing a new one DOES
    # search for a Supporter. With no Meowth in play, it is also available.
    _meowth_ld_free = not any(
        _mlf_p is not None and _mlf_p.id == Meowth_ex
        and getattr(_mlf_p, 'appearThisTurn', False)
        for _mlf_p in (list(my_state.active or []) + list(my_state.bench or [])))

    # Is this turn's Last-Ditch engine still ALIVE? That is: is there a Meowth
    # ex left that can be PUT DOWN to search for a Supporter (Xerosic vs Alakazam)? It requires all
    # three things: an ability slot (< 2 copies on the field), the turn's Last-Ditch
    # unspent and a REACHABLE body (hand or deck). It is the same
    # criterion as `_alakazam_dig_xerosic_engine` and as the Meowth ex PLAY branch;
    # it lives up here because TWO places far apart from each other consult it: the
    # veto on the redundant ex body and the reservation of the last bench slot.
    _alk_ld_engine_alive = (
        field_counts.get(Meowth_ex, 0) < 2
        and _meowth_ld_free
        and (hand_counts.get(Meowth_ex, 0) >= 1
             or AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                 Meowth_ex, {}).get(ZONE_DECK, 0) > 0))

    # Is our ACTIVE already an attacker READY to attack this turn? (the active is in
    # MAIN_ATTACKERS with enough effective energy and we can attack). It is used
    # so as not to waste plays on utility bodies (e.g. Meowth ex, which only
    # searches for a Supporter) when we already have something to attack with.
    _active_ready_attacker = False
    _ara_act = my_state.active[0] if my_state.active else None
    # Can the active NOT DAMAGE the opposing active because of IMMUNITY? (Cornerstone Mask
    # Ogerpon ex cancels our Pokemon WITH an ability; Crustle/Sylveon cancel our
    # ex; the Neutralization Zone cancels ex vs a 1-prize body). A "charged"
    # attacker that does 0 to the opposing wall is NOT a useful attacker this turn: the
    # productive play is the Boss's engine (put Meowth ex down -> search for Boss's ->
    # gust an ATTACKABLE target from the opposing bench). Without this, the active looked
    # ready (`_active_ready_attacker`) and vetoed Meowth ex, and the ATTACK option
    # (0 damage) won (user: Hydrapple ex vs an active Cornerstone + a Mega Lucario on
    # the bench). `_active_immune_vs_op_active` is reused in the attack's score.
    _op_act_imm = _active_of(op_state)
    _op_act_imm_data = (card_table.get(_op_act_imm.id)
                        if _op_act_imm is not None else None)
    _op_act_is_exmega = bool(_op_act_imm_data and (
        getattr(_op_act_imm_data, 'ex', False)
        or getattr(_op_act_imm_data, 'megaEx', False)))
    _active_immune_vs_op_active = False
    if _ara_act is not None and _op_act_imm is not None:
        if op_active_dodge_immune:
            # THE COIN IS ANOTHER WALL, and the widest one: the dodge
            # (`COIN_DODGE_ATTACK_IDS` on heads) does not read our attacker's
            # id the way Cornerstone and Crustle do -- it blanks EVERY body we
            # own, ex and non-ex alike. So it is entered without asking who is
            # in front of it, and every consumer downstream of this flag treats
            # the turn the same way it treats an immune wall: the active is not
            # a "ready attacker" (attacking it resolves for zero, registro_009
            # step 99) and the productive line is the Boss's engine -- from
            # hand, or from the deck through Meowth ex's Last-Ditch Catch.
            _active_immune_vs_op_active = True
        elif op_has_ability_immune_active and _ara_act.id in OUR_ABILITY_IDS:
            _active_immune_vs_op_active = True
        elif op_has_ex_immune_active and _ara_act.id in OUR_EX_IDS:
            _active_immune_vs_op_active = True
        elif (neutralization_zone_active and _ara_act.id in OUR_EX_IDS
              and not _op_act_is_exmega):
            _active_immune_vs_op_active = True
    if (can_attack and _ara_act is not None and _ara_act.id in MAIN_ATTACKERS
            and _can_attack_eff(_ara_act.id, len(_ara_act.energies))
            and not _active_immune_vs_op_active):
        _active_ready_attacker = True

    # Is there an ATTACKABLE target on the opposing bench to gust with Boss's when
    # the opposing active is immune to our attacker? A benched Pokemon that does NOT
    # reproduce the same ability immunity (it is not another Cornerstone) can be brought up
    # to the active spot with Boss's Orders and attacked. It enables the Meowth ex
    # -> Last-Ditch -> Boss's -> gust+attack the bench engine (user: Hydrapple ex vs
    # an active Cornerstone with a Mega Lucario on the bench; attacking the Cornerstone = 0).
    _boss_gust_immune_active = False
    if _active_immune_vs_op_active:
        for _bt in (op_state.bench or []):
            if _bt is not None and _bt.id not in ABILITY_IMMUNE_IDS:
                _boss_gust_immune_active = True
                break
    # The complete engine Meowth ex -> Last-Ditch -> Boss's (in the DECK) -> gust an
    # attackable target from the bench when the opposing active is immune. It is used to
    # (a) EXEMPT Meowth ex from the `_block_4th_ex` veto (which vs Cornerstone/Crustle
    # blocks putting a 4th ex down) -- Meowth is UTILITY, not one more attacker -- and
    # (b) score its play in the PLAY chain.
    _meowth_immune_boss_engine = (
        _boss_gust_immune_active
        and hand_counts.get(Boss_Orders, 0) == 0
        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
            Boss_Orders, {}).get(ZONE_DECK, 0) > 0
        and not state.supporterPlayed
        and _meowth_ld_free
        and field_counts.get(Meowth_ex, 0) < 2
        and bench_count < 5)

    # The number of READY attackers (active + bench) with enough energy to
    # attack already. It serves to decide whether it is worth refilling the hand (putting
    # Meowth ex down -> Lillie's) or whether we already have attackers to spare.
    _ready_attacker_count = 0
    for _rac_p in (list(my_state.active or []) + list(my_state.bench or [])):
        if (_rac_p is not None and _rac_p.id in MAIN_ATTACKERS
                and _can_attack_eff(_rac_p.id, len(_rac_p.energies))):
            _ready_attacker_count += 1

    # Is there ANY path to a SECOND attacker (besides the active) without refilling
    # the hand? It is used for the Meowth->Lillie's engine when the bench has no
    # spare attacker (user, registro_006 step 78). There is a path if:
    #   * there is already an ATTACKING body on the bench (even with no energy: it gets charged), or
    #   * we can put an attacking basic on the bench from hand, or
    #   * there is a LEGAL evolution into an attacker (a pre-evolution in play + the evolution in hand).
    _BASIC_ATTACKER_IDS = (Teal_Mask_Ogerpon_ex, Tapu_Bulu, Fezandipiti_ex, Pinsir)
    _has_bench_attacker_body = any(
        _b is not None and _b.id in MAIN_ATTACKERS
        for _b in (my_state.bench or []))
    _can_bench_basic_attacker = (bench_count < 5 and any(
        hand_counts.get(_bid, 0) >= 1 for _bid in _BASIC_ATTACKER_IDS))
    _can_evolve_to_attacker = (
        (field_counts.get(Applin, 0) >= 1 and hand_counts.get(Dipplin, 0) >= 1)
        or (field_counts.get(Dipplin, 0) >= 1
            and hand_counts.get(Hydrapple_ex, 0) >= 1)
        or (field_counts.get(Chikorita, 0) >= 1
            and hand_counts.get(Bayleef, 0) >= 1)
        or (field_counts.get(Bayleef, 0) >= 1
            and hand_counts.get(Meganium, 0) >= 1))
    _no_second_attacker_path = not (
        _has_bench_attacker_body or _can_bench_basic_attacker
        or _can_evolve_to_attacker)

    # The REAL opposing finisher on our active (it resolves the attack via attack_table,
    # not the `active_ko_likely`/`_op_best_damage_vs` heuristic that underestimates Mega
    # Lucario and others). True if the opposing active KNOCKS OUT our active next
    # turn.
    #
    # `scaled=True` (ago 2026): the FIRST of the 42 call sites of
    # `_op_active_attack_damage_to` migrated to the corrected projection
    # (ptcg/cards/op_scaling.py). It is the one that admits least argument,
    # because reading the opponent's real finisher is this flag's ENTIRE job --
    # it exists precisely because the heuristic next to it was blind, and it was
    # still blind itself for thirteen of the fifteen attacks that scale with the
    # board. Its consumers are the "dig instead of reserving" rules
    # (`_boss_yields_to_dig`, `_lillie_doomed_without_relief`): they spend
    # resources when there is no next turn to spend them in, which is the
    # AGGRESSIVE side of the correction and not the passive one that measured
    # negative when the scale was switched on everywhere at once.
    #
    # MEASURED: the flag now changes value in 33.3% of board states, and in 23.2%
    # of the contexts where Boss's is scored it opens a "doomed active, no relief"
    # window that NEITHER the heuristic NOR the blind projector saw. And it flips
    # ZERO decisions -- 77.947 of them across seven matchups plus the mirror
    # (utils/shadow.py). The correction is real and inert at the same time, which
    # is a statement about its CONSUMERS, not about the number: what
    # `_boss_yields_to_dig` does with the window is yield the Supporter slot to a
    # Lillie's that, in that window, is usually not in hand. That is the next
    # thread to pull, and it is a rule-design problem, not a projection one.
    #
    # `team_buff=True` closes the OTHER half of the same blindness (user,
    # registro_004 step 30 vs Cynthia's Garchomp). `scaled` fixes the attacks
    # whose printed number is a placeholder; this fixes the attacks whose number
    # is right and gets a flat bonus from a body on THEIR BENCH. Their Gabite's
    # Dragonslice prints 40, their benched Roserade adds 30, and the engine took
    # exactly 70 off a Tapu Bulu that had 70 left -- while this flag said the
    # Tapu was fine. It belongs here and not in `active_ko_likely` for the reason
    # the whole projection is opt-in: this flag is the one written to be honest,
    # the heuristic next to it is the one calibrated against the blind number.
    _active_doomed_real = False
    _adr_act = my_state.active[0] if my_state.active else None
    _adr_opa = _active_of(op_state)
    if _adr_act is not None and _adr_opa is not None:
        _active_doomed_real = (
            _op_active_attack_damage_to(
                _adr_opa, _adr_act, getattr(op_state, 'handCount', None),
                scaled=True, team_buff=True)
            >= (_adr_act.hp or 0))

    _ctm_dipplin_low = False
    _ctm_tapu_high = False
    _ctm_tapu_ready = False
    if AGENT_STATE.op_is_crustle_deck:
        _ctm_op_act = op_state.active[0] if op_state.active else None
        _ctm_active_is_crustle = (_ctm_op_act is not None and
                                  _ctm_op_act.id in (Crustle_Grass, Crustle_Fighting))
        _ctm_all_in_play = (field_counts.get(Dipplin, 0) >= 1
                            and field_counts.get(Tapu_Bulu, 0) >= 1
                            and field_counts.get(Meganium, 0) >= 1)
        if _ctm_active_is_crustle and _ctm_all_in_play:
            # Tapu Bulu is our best attacker vs Crustle (non-ex, 220). If it is
            # charged (active OR bench), ALWAYS prioritise it: do not retreat a Tapu
            # that is active and already ready, and if it is on the bench make every effort to
            # bring it up to attack. We only chip with Dipplin when Tapu is NOT ready.
            for _ctm_tp in (([my_state.active[0]] if my_state.active else [])
                            + list(my_state.bench or [])):
                if (_ctm_tp is not None and _ctm_tp.id == Tapu_Bulu
                        and _can_attack_eff(Tapu_Bulu, len(_ctm_tp.energies))):
                    _ctm_tapu_ready = True
                    break
            if _ctm_tapu_ready:
                _ctm_tapu_high = True
            elif len(_ctm_op_act.energies) <= 2:
                _ctm_dipplin_low = True
            else:
                _ctm_tapu_high = True

    _ctm_chikorita_bench = False
    _ctm_applin_bench = False
    if AGENT_STATE.op_is_crustle_deck:
        _ctm_chikorita_bench = any(
            bp is not None and bp.id in (Chikorita, Bayleef, Meganium)
            for bp in (my_state.bench or []))
        _ctm_applin_bench = any(
            bp is not None and bp.id in (Applin, Dipplin, Hydrapple_ex)
            for bp in (my_state.bench or []))

    _ctm_charge_active_dipplin = False
    if AGENT_STATE.op_is_crustle_deck and not _ctm_tapu_ready:
        _ctm_cad_op_act = op_state.active[0] if op_state.active else None
        _ctm_cad_act_crustle = (_ctm_cad_op_act is not None and
                                _ctm_cad_op_act.id in (Crustle_Grass, Crustle_Fighting))
        _ctm_cad_dipplin_active = (my_state.active and my_state.active[0] is not None
                                   and my_state.active[0].id == Dipplin)
        if _ctm_cad_dipplin_active:
            if _ctm_cad_act_crustle:
                if len(_ctm_cad_op_act.energies) <= 2:
                    _ctm_charge_active_dipplin = True
            else:
                _ctm_charge_active_dipplin = True

    if context == SelectContext.MAIN and _ctm_dipplin_low:
        _my_cards_ctm = ([my_state.active[0]] if my_state.active else [])
        for _bp_ctm in my_state.bench:
            if _bp_ctm is not None:
                _my_cards_ctm.append(_bp_ctm)
        _dip_idx_ctm = -1
        for _idx_ctm, _mc_ctm in enumerate(_my_cards_ctm):
            if _mc_ctm is not None and _mc_ctm.id == Dipplin:
                if _dip_idx_ctm < 0:
                    _dip_idx_ctm = _idx_ctm
                if len(_mc_ctm.energies) >= 1:
                    _dip_idx_ctm = _idx_ctm
                    break
        if _dip_idx_ctm >= 0:
            AGENT_STATE.plan.attacker = _dip_idx_ctm
            AGENT_STATE.plan.target = 0
            AGENT_STATE.plan.attack_index = 0
            AGENT_STATE.plan.energy = (len(_my_cards_ctm[_dip_idx_ctm].energies) < 1)
            if op_state.active and op_state.active[0] is not None:
                AGENT_STATE.plan.remain_hp = (op_state.active[0].hp or 0)

    if context == SelectContext.MAIN and _ctm_tapu_ready:
        _my_cards_tpr = ([my_state.active[0]] if my_state.active else [])
        for _bp_tpr in my_state.bench:
            if _bp_tpr is not None:
                _my_cards_tpr.append(_bp_tpr)
        _tapu_idx_tpr = -1
        for _idx_tpr, _mc_tpr in enumerate(_my_cards_tpr):
            if (_mc_tpr is not None and _mc_tpr.id == Tapu_Bulu
                    and _can_attack_eff(Tapu_Bulu, len(_mc_tpr.energies))):
                _tapu_idx_tpr = _idx_tpr
                break
        if _tapu_idx_tpr >= 0:
            # Tapu Bulu already charged: if it is the active (idx 0) we attack without retreating;
            # if it is on the bench, force the promotion by retreating the active.
            AGENT_STATE.plan.attacker = _tapu_idx_tpr
            AGENT_STATE.plan.target = 0
            AGENT_STATE.plan.attack_index = 0
            AGENT_STATE.plan.energy = False
            if op_state.active and op_state.active[0] is not None:
                AGENT_STATE.plan.remain_hp = (op_state.active[0].hp or 0)

    _active_pokemon = my_state.active[0] if my_state.active else None
    _active_needs_energy = False
    if _active_pokemon is not None and not state.energyAttached:
        _act_energy = len(_active_pokemon.energies)
        _act_effective = _act_energy * _grass_mult()
        if _active_pokemon.id == Hydrapple_ex:
            _active_needs_energy = (_act_effective < 2)
        elif _active_pokemon.id == Dipplin:
            _active_needs_energy = (_act_energy < 1)
        elif _active_pokemon.id == Teal_Mask_Ogerpon_ex:
            _active_needs_energy = (_act_effective < 3)
        elif _active_pokemon.id == Tapu_Bulu:

            _active_needs_energy = (_act_effective < 4)
        elif _active_pokemon.id == Pinsir:

            _active_needs_energy = (_act_effective < 2)
        elif _active_pokemon.id == Meowth_ex:

            _active_needs_energy = (_act_energy == 0)
        elif _active_pokemon.id == Fezandipiti_ex:

            _fez_eff_after_att = _act_energy + _grass_attach_unit()
            if _act_effective >= 3:
                _active_needs_energy = False
            elif _fez_eff_after_att >= 3:
                _active_needs_energy = True
            else:

                _active_needs_energy = (_act_energy == 0)
        elif _active_pokemon.id in (Chikorita, Bayleef, Meganium):

            _retreat_needed = RETREAT_COST.get(_active_pokemon.id, 1)
            # With Wild Growth each basic Grass energy is worth two for
            # paying the retreat, so the effective energy is enough (e.g.
            # a Meganium with 1 energy can already retreat: 1*2 >= 2).
            _active_needs_energy = (_act_effective < _retreat_needed)

    _energy_in_hand = hand_counts.get(Basic_Grass_Energy, 0)
    _enough_for_both = (_energy_in_hand >= 2)

    _active_hydra_ready = (
        _active_pokemon is not None
        and _active_pokemon.id == Hydrapple_ex
        and len(_active_pokemon.energies) * _grass_mult() >= 2
    )

    _active_hydra_capped = (
        _active_pokemon is not None
        and _active_pokemon.id == Hydrapple_ex
        and len(_active_pokemon.energies) >= 2
    )

    _bench_has_chargeable = any(bp is not None for bp in (my_state.bench or []))

    _reserve_hydra_active_charge = False
    if (_active_pokemon is not None and _active_pokemon.id == Hydrapple_ex
            and _energy_in_hand == 1 and not op_has_ex_immune_active):
        _rhac_mult = _grass_mult()
        _rhac_cur = len(_active_pokemon.energies) * _rhac_mult
        _rhac_after = len(_active_pokemon.energies) + _grass_attach_unit()
        if _rhac_cur < 2 and _rhac_after >= 2:
            _reserve_hydra_active_charge = True

    _prob_energy_draw_soon = _prob_draw_any(Basic_Grass_Energy, draws=2)
    _energy_starved_low_draw = (
        _active_needs_energy and _energy_in_hand == 0 and
        not state.energyAttached and _prob_energy_draw_soon < 0.5
    )

    _hydrapple_bench_needs_energy = False
    if hand_counts.get(Basic_Grass_Energy, 0) >= 1:
        for _bp in (my_state.bench or []):
            if _bp is not None and _bp.id == Hydrapple_ex:
                _hydra_bench_e = len(_bp.energies)
                _hydra_bench_eff = _hydra_bench_e * _grass_mult()
                if _hydra_bench_eff < 2:
                    _hydrapple_bench_needs_energy = True
                    break

    _energy_demands_before_teal = 0
    if _active_needs_energy:
        _energy_demands_before_teal += 1
    if _hydrapple_bench_needs_energy:
        _energy_demands_before_teal += 1
    _enough_after_priorities = (_energy_in_hand > _energy_demands_before_teal)

    _reserve_energy_for_hydra_evolve = False
    if (_active_pokemon is not None and _active_pokemon.id == Dipplin
            and _energy_in_hand == 1 and not op_has_ex_immune_active):
        _hydra_reachable_this_turn = (
            hand_counts.get(Hydrapple_ex, 0) >= 1
            or hand_counts.get(Ultra_Ball, 0) >= 1)
        if _hydra_reachable_this_turn:
            if len(_active_pokemon.energies) + _grass_attach_unit() >= 2:
                _reserve_energy_for_hydra_evolve = True

    _bcs_playable_in_hand = False
    if hand_counts.get(Bug_Catching_Set, 0) >= 1:
        for _bcs_cid, _bcs_states in AGENT_STATE.ACTIVE_CARDS_IN_DECK.items():
            if _bcs_states[ZONE_DECK] <= 0:
                continue
            if _bcs_cid == Basic_Grass_Energy:
                _bcs_playable_in_hand = True
                break
            _bcs_cdata = card_table.get(_bcs_cid)
            if (_bcs_cdata is not None and _bcs_cdata.cardType == CardType.POKEMON
                    and _bcs_cdata.energyType == EnergyType.GRASS):
                _bcs_playable_in_hand = True
                break

    _pp_playable_in_hand = False
    if hand_counts.get(Poke_Pad, 0) >= 1:
        for _pp_cid in (Chikorita, Bayleef, Meganium, Applin, Dipplin, Tapu_Bulu):
            _pp_states = AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(_pp_cid)
            if _pp_states is not None and _pp_states[ZONE_DECK] > 0:
                _pp_playable_in_hand = True
                break

    # --- Rule (user): Meowth ex + Lillie's Determination on OUR first turn ---
    # On our first turn Meowth ex must NOT be played first: the rest of the hand
    # is deployed (basic Pokemon and artefacts) and Lillie's
    # Determination is played LAST. Reason: Lillie's shuffles the whole hand into the deck, so
    # any Supporter Meowth ex fetched would end up shuffled away (a wasted
    # fetch) and Meowth ex would be left over on the bench as a 2-prize
    # Pokemon.
    _our_first_turn = ((state.turn == 1 and AGENT_STATE.we_go_first)
                       or (state.turn == 2 and not AGENT_STATE.we_go_first))

    # A PROJECTED DONK ON OUR FIRST TURN (a board flag, it does not depend on
    # the card being scored): an EMPTY bench, only the active basic, and the
    # opposing ACTIVE already projects a KO with a single energy (via
    # `_op_active_attack_damage_to`, which assumes their attachment for the turn). With no bench,
    # that KO is an instant LOSS, so putting Meowth ex down as a BODY is the
    # survival play. It is the ONLY reason why on the first turn a
    # Meowth ex is put down while holding a Lillie's in hand; it is used by the anti-donk guard
    # (score 21900) and by the exception to the `no-meowth-para-lillie` veto.
    _meowth_antidonk_now = False
    if (state.turn == 1 and AGENT_STATE.we_go_first
            and bench_count == 0
            and field_counts.get(Meowth_ex, 0) == 0
            and _meowth_ld_free
            and my_state.active and my_state.active[0] is not None
            and op_state.active and op_state.active[0] is not None):
        _mdk_act0 = my_state.active[0]
        _mdk_hp0 = getattr(_mdk_act0, 'hp', 0) or 0
        _mdk_hit0 = _op_active_attack_damage_to(op_state.active[0], _mdk_act0)
        _meowth_antidonk_now = (
            _mdk_hit0 > 0 and _mdk_hp0 > 0 and _mdk_hit0 >= _mdk_hp0)

    # THE LONE MEOWTH EX STAYS IN HAND ON OUR FIRST TURN GOING FIRST (user,
    # registro_001 step 7, episode 89627609 vs Dragapult, WON with a mistake).
    # Board: active Fezandipiti ex (210 HP), empty bench, and in hand the only
    # BODY was a Meowth ex (the rest were a Hydrapple ex that cannot be played,
    # two Lillie's and a stadium). Every per-card veto did its job and left the
    # Meowth at <= 0, but the ANTI-EMPTY-BENCH SAFETY NET lifted it to 200 and
    # benched it anyway: it read "empty bench" as "we can be donked", which is
    # false behind a 210 HP body.
    #
    # What the net is really protecting against is losing on the spot on the
    # opponent's first turn. Going FIRST that only happens if their single
    # attachment reaches our active's HP, and against the tough openers of the
    # deck (`FIRST_TURN_TOUGH_OPENERS`: 210/210/170/140 HP) no first-turn attack
    # in the format gets there. So the bench costs nothing and holding the
    # Meowth is strictly better: it is a 2-prize body, and its Last-Ditch
    # fetch would be shuffled away by the very Lillie's we play on turn 2.
    #
    # THE ONE EXCEPTION the user named: a lone Meowth ex (170) in the active
    # spot against an opposing SOLROCK. Cosmic Beam (one {F}, 70) plus the four
    # Premium Power Pro (+30 each, Items) is the only opening that reaches 170
    # on their first turn, and with an empty bench that is an instant loss --
    # so there the second Meowth ex DOES go down as a body. It fires on SEEING
    # the Solrock, not on the arithmetic: the exact damage depends on how many
    # Power Pros they hold, which we cannot see (and the {F} weakness of the
    # Meowth ex does NOT double it -- see `Solrock` in ptcg/cards/ids.py for the
    # measurement). A projected donk seen by the damage model
    # (`_meowth_antidonk_now`) also lifts the hold, so the net keeps working
    # wherever it really applies.
    #
    # The rule is for going FIRST ONLY. Going second our first turn is turn 2:
    # the opponent has already attacked once and has a second attachment ready,
    # so the reasoning about a single energy does not hold.
    _ft_hold_lone_meowth = False
    if (state.turn == 1 and AGENT_STATE.we_go_first
            and bench_count == 0
            and not _meowth_antidonk_now
            and hand_counts.get(Meowth_ex, 0) >= 1
            and my_state.active and my_state.active[0] is not None):
        _fthm_act = my_state.active[0]
        _fthm_op = op_state.active[0] if op_state.active else None
        _fthm_solrock_donk = (_fthm_act.id == Meowth_ex
                              and _fthm_op is not None
                              and _fthm_op.id == Solrock)
        if (_fthm_act.id in FIRST_TURN_TOUGH_OPENERS
                and not _fthm_solrock_donk):
            # The hold only covers the case the user described: Meowth ex is
            # the ONLY body left to bench. With any other basic in hand that
            # one goes down (it is not a 2-prize card) and the net is right.
            _ft_hold_lone_meowth = True
            for _fthm_c in (my_state.hand or []):
                if _fthm_c.id == Meowth_ex:
                    continue
                _fthm_d = card_table.get(_fthm_c.id)
                if (_fthm_d is not None
                        and _fthm_d.cardType == CardType.POKEMON
                        and not getattr(_fthm_d, 'stage1', False)
                        and not getattr(_fthm_d, 'stage2', False)):
                    _ft_hold_lone_meowth = False
                    break

    _bench_attacker_ready = False
    for _bp in (my_state.bench or []):
        if _bp is None:
            continue
        _bp_e = len(_bp.energies)
        _bp_eff = _bp_e * _grass_mult()
        if _bp.id == Hydrapple_ex and _bp_eff >= 2:
            _bench_attacker_ready = True
            break
        if _bp.id == Teal_Mask_Ogerpon_ex and _bp_eff >= 3:
            _bench_attacker_ready = True
            break
        if _bp.id == Dipplin and _bp_e >= 1:
            _bench_attacker_ready = True
            break
        if _bp.id == Tapu_Bulu and _bp_eff >= 4:
            _bench_attacker_ready = True
            break
        if _bp.id == Pinsir and _bp_eff >= 2:
            _bench_attacker_ready = True
            break
        if _bp.id == Meganium and _bp_eff >= 4:
            _bench_attacker_ready = True
            break

    _bench_attacker_needs_energy = False
    for _bp in (my_state.bench or []):
        if _bp is None:
            continue
        _bp_e = len(_bp.energies)
        _bp_eff = _bp_e * _grass_mult()
        if _bp.id == Hydrapple_ex and _bp_eff < 2:
            _bench_attacker_needs_energy = True
            break
        if _bp.id == Teal_Mask_Ogerpon_ex and _bp_eff < 3:
            _bench_attacker_needs_energy = True
            break
        if _bp.id == Dipplin and _bp_e < 1:
            _bench_attacker_needs_energy = True
            break
        if _bp.id == Tapu_Bulu and _bp_eff < 4:
            _bench_attacker_needs_energy = True
            break

    _op_active_hp = 0
    _op_active_weakness_grass = False
    _op_active_resistance_grass = False
    _op_active_metal = False
    if op_state.active and op_state.active[0] is not None:
        _op_active_hp = op_state.active[0].hp
        _op_data = card_table.get(op_state.active[0].id)
        _op_active_metal = (getattr(_op_data, 'energyType', None) == EnergyType.METAL)
        if _op_data and _op_data.weakness == EnergyType.GRASS:
            _op_active_weakness_grass = True
        # Grass resistance (e.g. Archaludon ex): the engine subtracts 30 damage
        # (see _our_effective_damage). It has to be subtracted here so as not to overestimate
        # the Syrup Storm and believe we already knock out when we are 30 short.
        if _op_data and _op_data.resistance == EnergyType.GRASS:
            _op_active_resistance_grass = True

    _active_hydra_cannot_ko = False
    if _active_hydra_capped and _op_active_hp > 0:
        _syrup_dmg_now = 30 + 30 * total_grass
        if _op_active_weakness_grass:
            _syrup_dmg_now *= 2
        elif _op_active_resistance_grass:
            _syrup_dmg_now = max(0, _syrup_dmg_now - 30)
        # Full Metal Lab, after weakness/resistance (wave 2, copy 2 of 4). Their
        # Archaludon line is BOTH Grass-resisting and Metal, so both apply.
        if _op_active_metal and full_metal_lab_active:
            _syrup_dmg_now = max(0, _syrup_dmg_now - 30)
        _active_hydra_cannot_ko = (_syrup_dmg_now < _op_active_hp)

    def _extra_energy_enables_ko(pokemon_id: int, current_energy: int) -> bool:
        if _op_active_hp <= 0:
            return False
        if not (op_state.active and op_state.active[0] is not None):
            return False
        _mult = _grass_attach_unit()
        _op_act = op_state.active[0]

        # The CENTRAL evaluator (P0.1): the inline copy only applied weakness/
        # resistance; against Drednaw (which cancels >=200), Sturdy/Resolute Heart or
        # Crustle (immune to ex) it believed an extra energy "enabled" a
        # non-existent KO and wasted the charge.
        def _eff(_base):
            return _our_effective_damage(
                _ProjTarget(pokemon_id), _op_act, _base,
                AGENT_STATE.meganium_in_play, neutralization_zone_active)

        if pokemon_id == Hydrapple_ex:
            _dmg_now = _eff(30 + 30 * total_grass)
            _dmg_extra = _eff(30 + 30 * (total_grass + _mult))
            return _dmg_now < _op_active_hp <= _dmg_extra

        if pokemon_id == Teal_Mask_Ogerpon_ex:
            _op_e = len(_op_act.energies)
            _my_eff = current_energy
            _dmg_now = _eff(30 + 30 * (_my_eff + _op_e))
            _dmg_extra = _eff(30 + 30 * (_my_eff + _mult + _op_e))
            return _dmg_now < _op_active_hp <= _dmg_extra

        return False

    _active_already_kos = False
    # Hoisted out of the branch below: the DEFENDER's punish (see
    # `_active_self_ko_now`) has to know whether our swing damages them at all,
    # and "is damaged by an attack" is the condition those cards print.
    _ak_dmg = 0
    if _active_pokemon is not None and _op_active_hp > 0:

        _ak_eff = len(_active_pokemon.energies)
        if _active_pokemon.id == Teal_Mask_Ogerpon_ex and _ak_eff >= 3:
            _ak_op_e = (len(op_state.active[0].energies)
                        if (op_state.active and op_state.active[0] is not None) else 0)
            # Myriad counts the energy of BOTH actives (_ak_op_e was computed
            # and NOT used -- the same bug as the inline copy of the ATTACK).
            _ak_dmg = 30 + 30 * (_ak_eff + _ak_op_e)
        elif _active_pokemon.id == Hydrapple_ex and _ak_eff >= 2:
            _ak_dmg = 30 + 30 * total_grass
        elif _active_pokemon.id == Tapu_Bulu and _ak_eff >= 4:
            _ak_dmg = 220
        elif _active_pokemon.id == Meganium and _ak_eff >= 4:
            _ak_dmg = 140
        elif _active_pokemon.id == Fezandipiti_ex and _ak_eff >= 3:
            # Cruel Arrow: a FIXED 100 damage (Darkness type, not Grass) to
            # any Pokemon. It counts as a KO of the opposing active in order to enable
            # charging the future attacker (Tapu Bulu). It does not apply Grass weakness /
            # resistance because it is not Grass damage
            # (_our_effective_damage knows this through `is_fez`).
            _ak_dmg = 100
        # The CENTRAL evaluator (P0.1): the inline copy only applied weakness/
        # resistance, so `_active_already_kos` could declare a false KO
        # vs Crustle (immune to ex), Drednaw (which cancels >=200), Sturdy/Resolute
        # Heart (they survive at 10) or Cornerstone. `_our_effective_damage` already
        # skips weakness for Fezandipiti (fixed damage), covering
        # `_ak_is_grass`.
        if _ak_dmg > 0 and op_state.active and op_state.active[0] is not None:
            _ak_dmg = _our_effective_damage(
                _active_pokemon, op_state.active[0], _ak_dmg,
                AGENT_STATE.meganium_in_play, neutralization_zone_active)
        _active_already_kos = (_ak_dmg >= _op_active_hp)

    # --- THE ACTIVE'S SNIPE: the best target is not always the opposing active ----
    # (user, registro_004 step 54 vs Alakazam.) Fezandipiti ex's Cruel Arrow
    # hits ANY Pokemon of the opponent's for a fixed 100. `_active_already_kos`
    # and `_active_can_ko_now` (the retreat scorer) only look at the opposing ACTIVE, so
    # with the 140 HP Alakazam in front the turn looked sterile: the agent
    # retreated the Fezandipiti (paying its energy) to promote an Ogerpon that could not
    # even attack, and passed -- with an 80 HP Kadabra knockable on the opposing
    # bench. Here the best snipe target (active or bench) is resolved ONCE and
    # the result feeds the retreat/attack planner and the actual
    # target selection in the DAMAGE menu.
    _snipe_target, _snipe_dmg, _snipe_is_ko = (None, 0, False)
    if _active_pokemon is not None:
        _snipe_target, _snipe_dmg, _snipe_is_ko = _snipe_best_target(
            _active_pokemon, op_state,
            len(_active_pokemon.energies) * _grass_mult(),
            AGENT_STATE.meganium_in_play, neutralization_zone_active,
            bench_count=bench_count, grass_scale=total_grass)
    # The snipe KO only counts as a REAL play this turn if we can really
    # attack (and confusion does not turn it into a coin flip).
    #
    # `plan.attacker <= 0` (the active, or no plan) is MANDATORY and avoids a
    # mutual block: with `plan.attacker >= 1` the planner already preferred retreating
    # and attacking with a benched body, and the ATTACK scorer vetoes the active's attack
    # precisely for that. If on top of that we let the snipe veto the RETREAT
    # (via `_active_can_ko_now`) there would be no live play left and the turn would
    # close blank -- worse than the two alternatives. When the plan does
    # point at the active, both sides agree and the snipe rules.
    _active_snipe_ko_now = bool(_snipe_is_ko and can_attack and not is_confused
                                and AGENT_STATE.plan.attacker <= 0)
    _active_snipe_ko_prizes = (prize_count_op(_snipe_target)
                               if _active_snipe_ko_now else 0)

    # Does the ACTIVE's attack this turn WIN the game? (user, registro_009 step
    # 125 vs Archaludon ex, LOST): our Ogerpon ex with Meganium in play
    # (Wild Growth doubles every Grass) did Myriad 30+30x(8 effective + 3 of the
    # opponent's) = 360, minus 30 for Grass resistance = 330 >= 300 -> it KNOCKS OUT the
    # Archaludon ex (2 prizes) and with 2 prizes left it WINS. The agent, instead
    # of ATTACKING, charged energy onto Tapu Bulu (`_tapu_future_charge`, 40000) and
    # then retreated the Ogerpon to attack with Tapu -- throwing away the finisher. When
    # the active's KO WINS the game (my remaining prizes <= the prizes the
    # KO gives), ATTACKING is the TOP priority play: nothing else matters. The
    # damage computation (with Meganium, the opponent's energy and resistance) is already correct
    # via `_active_already_kos`; what was missing was prioritising the finisher.
    # The KO on the opposing active WINS the game in TWO cases: (a) it gives us the prizes
    # we are missing (my_prize <= the target's prizes), or (b) the opponent has no other
    # Pokemon in play -- an EMPTY bench -- and therefore cannot promote a new
    # active after the KO (a game rule: with no Pokemon to replace the knocked-out
    # active, they LOSE). Case (b) was missing (user, registro_016 step 138 vs
    # Crustle, WON with a suboptimal play): with a LETHAL active Ogerpon (Myriad 150
    # >= 110) and the opponent with ONLY their active Munkidori (1 prize, an empty bench),
    # knocking it out WINS even though my_prize (2) > the target's prizes (1). The agent,
    # not detecting the finisher, RETREATED the Ogerpon to attack with a 1-prize body
    # (Dipplin) -- throwing away the immediate victory. ATTACKING is the top priority.
    # `_op_bench_empty` was computed earlier (alongside op_cards).
    #
    # --- THE SUICIDAL FINISHER: the KO that DRAWS (or GIVES AWAY) instead of winning ---
    # (user, registro_016 step 184 vs Marnie's Grimmsnarl, a DRAW.) Our ACTIVE Tapu
    # Bulu, at 20/140 HP and charged, finished the opposing Impidimp (Wood Hammer
    # 220 >= 70) with ONE prize left on each side, so the agent set
    # `_active_attack_wins_now` and attacked with absolute priority (99000). But Wood
    # Hammer "also does 30 damage to itself": the attack itself KNOCKED OUT Tapu Bulu,
    # the opponent took THEIR last prize at the same instant and the game ended 0-0,
    # a DRAW. On the bench a Teal Mask Ogerpon ex waited with 6 energies: retreating
    # (cost 3) and finishing with Myriad Leaf Shower (30+30x6 = 210 >= 70) WON
    # cleanly -- verified against the real simulator (result 0 = a win) against
    # the result 2 (a draw) of the line the agent played.
    #
    # The agent was missing TWO data points, neither deducible from the damage dealt:
    #   1. the attack's SELF-DAMAGE (now `_attack_self_damage`, read from the card's
    #      text), and
    #   2. that the KO of OUR OWN body also PAYS PRIZES: with the opponent at
    #      `op_prize` prizes, leaving them a corpse worth `prize_count` >= op_prize
    #      closes their count TOO.
    # Hence the three states of the suicidal finisher:
    #   * `_suicide_hands_op_win`: the opponent reaches 0 with our corpse.
    #   * `_suicide_only_draws`  : and OUR KO also wins -> a DRAW, not a victory.
    #   * `_suicide_loses`       : the opponent reaches 0 and we do NOT -> a LOSS.
    # The self-damage is measured with the worst case (`incierto=True`): a finisher that
    # CAN kill us and close the opponent's count does not deserve absolute priority.
    # THE PRICE THE DEFENDER CHARGES FOR BEING ATTACKED (user, episode 92355371
    # vs Festival Lead, LOST; found as a class by `utils/card_text_census.py`).
    # Four cards print "...is damaged by an attack from your opponent's Pokemon
    # (even if this Pokemon is Knocked Out), put N damage counters on the
    # ATTACKING Pokemon": Spiky Energy 20, Punk Helmet 40, Deluxe Bomb 120. That
    # is recoil -- our body, our turn, the same instant as Wood Hammer's -- so it
    # belongs in the same brake and nowhere else yet.
    #
    # It is charged only when our swing DAMAGES them (`_ak_dmg > 0`), because
    # that is the condition the cards print: against a wall that reads our attack
    # as zero, nothing comes back.
    #
    # What this does NOT do, deliberately: it does not make the defensive half
    # fire more often. The body that took 120 in that episode did not die on our
    # turn, it died on the reply -- and pricing that means telling
    # `_opponent_reply` that our active's HP is lower than the board says, which
    # is a change to the machinery that has measured negative three separate
    # times when it was made to fire more often. That half is measured before it
    # is written.
    _defender_punish = (
        _defender_punish_damage(op_state.active[0])
        if (_active_pokemon is not None and can_attack and not is_confused
            and _ak_dmg > 0
            and op_state.active and op_state.active[0] is not None) else 0)
    _active_self_ko_now = (
        _active_pokemon is not None
        and can_attack
        and not is_confused
        and (_self_ko_by_own_attack(_active_pokemon, incierto=True)
             or (_defender_punish > 0
                 and (_self_damage_of_pokemon(_active_pokemon, incierto=True)
                      + _defender_punish) >= (_active_pokemon.hp or 0))))
    _active_self_ko_prizes = (prize_count(_active_pokemon)
                              if _active_self_ko_now else 0)
    _suicide_hands_op_win = (_active_self_ko_now
                             and op_prize <= _active_self_ko_prizes)

    _active_attack_wins_now = (
        _active_already_kos
        and can_attack
        and not is_confused
        and op_state.active and op_state.active[0] is not None
        # GUARANTEED KO (P0.1): vs Tenacious Body/Survival Brace the "finisher"
        # can fail the coin flip; it is not given absolute victory priority.
        and not _ko_not_guaranteed(op_state.active[0])
        # The finisher that KILLS US and closes the opponent's count does NOT win: it draws
        # (both KOs are simultaneous and each side takes its last prize).
        and not _suicide_hands_op_win
        and (my_prize <= prize_count_op(op_state.active[0])
             or _op_bench_empty))

    # The SNIPE can also close the game: if Cruel Arrow knocks out a body
    # on the opposing BENCH whose prizes are enough for us, attacking WINS just like the finisher
    # on the active, and it deserves the same absolute priority (score and tier). The
    # "empty opposing bench" case does not apply here: the opponent only loses for being unable
    # to replace their ACTIVE, and this KO does not touch it.
    _snipe_attack_wins_now = (
        _active_snipe_ko_now
        and _snipe_target is not None
        and not _ko_not_guaranteed(_snipe_target)
        and not _suicide_hands_op_win
        and my_prize <= _active_snipe_ko_prizes)
    if _snipe_attack_wins_now:
        _active_attack_wins_now = True

    # The suicidal finisher DRAWS if our KO also closed the count; if not,
    # it simply GIVES AWAY the game (we kill ourselves for nothing).
    _suicide_ko_would_win = (
        _suicide_hands_op_win
        and _active_already_kos
        and op_state.active and op_state.active[0] is not None
        and not _ko_not_guaranteed(op_state.active[0])
        and (my_prize <= prize_count_op(op_state.active[0])
             or _op_bench_empty))
    _suicide_only_draws = _suicide_hands_op_win and _suicide_ko_would_win
    _suicide_loses = _suicide_hands_op_win and not _suicide_ko_would_win

    # RELIEF OF THE SUICIDAL FINISHER: a BENCHED attacker that, promoted after retreating, wins
    # the game CLEANLY (it knocks out, takes the prizes we are missing and does NOT kill itself).
    # It measures the damage with the Grass that will remain AFTER paying the retreat (the
    # cost discards whole cards from the active: the same care as
    # `_hlp_grass_after`), because Syrup Storm scales with the Grass on the FIELD.
    _suicide_swap_winner = None
    if (_suicide_hands_op_win and can_switch and _active_pokemon is not None
            and op_state.active and op_state.active[0] is not None
            and not _ko_not_guaranteed(op_state.active[0])):
        _ssw_opa = op_state.active[0]
        _ssw_opa_hp = _ssw_opa.hp or 0
        _ssw_wins_prizes = (my_prize <= prize_count_op(_ssw_opa)
                             or _op_bench_empty)
        _ssw_grass_after = max(
            0, total_grass - (0 if has_switch_card else _retreat_grass_units(
                RETREAT_COST.get(_active_pokemon.id, 1))))
        if _ssw_wins_prizes and _ssw_opa_hp > 0:
            for _ssw_bp in (my_state.bench or []):
                if _ssw_bp is None or not isinstance(_ssw_bp, Pokemon):
                    continue
                _ssw_e = len(_ssw_bp.energies)
                if not _can_attack_eff(_ssw_bp.id, _ssw_e):
                    continue  # it does not attack today with the energy it already has
                # The relief cannot repeat the problem: if it, when attacking,
                # also kills itself and with that the opponent reaches 0, it is no use.
                if (_self_ko_by_own_attack(_ssw_bp, incierto=True)
                        and op_prize <= prize_count(_ssw_bp)):
                    continue
                _ssw_base = _attacker_base_damage(
                    _ssw_bp.id, _ssw_opa, _ssw_e * _grass_mult(),
                    grass_scale=_ssw_grass_after, teal_self_energy=_ssw_e,
                    bench_count=bench_count)
                if _ssw_base <= 0:
                    continue
                if _our_effective_damage(
                        _ssw_bp, _ssw_opa, _ssw_base, AGENT_STATE.meganium_in_play,
                        neutralization_zone_active) >= _ssw_opa_hp:
                    _suicide_swap_winner = _ssw_bp
                    break

    # Retreating to make way for the relief: it is the play that turns the draw (or the
    # loss) into a win, so it rules above everything else.
    _suicide_swap_win_promote = (_suicide_swap_winner is not None)

    # Syrup Storm counts the Grass on ALL our Pokemon, not just the attacker's:
    # with the ACTIVE Hydrapple ex already ready to attack, ONE more Grass
    # ANYWHERE (Teal Dance on a benched Ogerpon, Ripening Charge on
    # whoever) can turn a short attack into the KO. User, registro_006
    # step 68 vs Mega Abomasnow ex (LOST): 30+30x10 = 330 against 350 HP, and
    # with one more Grass 390 -> a 3-prize KO. `_extra_energy_enables_ko` already
    # does the arithmetic (the Hydrapple_ex branch, with weakness/resistance and
    # immunities); what was missing was for the charging ABILITIES to
    # consult it even when their own bearer gains nothing from the energy.
    _grass_anywhere_enables_syrup_ko = False
    if (_active_pokemon is not None
            and _active_pokemon.id == Hydrapple_ex
            and not _active_already_kos
            and can_attack and not is_confused
            and len(_active_pokemon.energies) * _grass_mult() >= 2
            and _extra_energy_enables_ko(Hydrapple_ex,
                                         len(_active_pokemon.energies))):
        _grass_anywhere_enables_syrup_ko = True

    # --- ATTACKING WITH THE ACTIVE COMES FIRST ---------------------------
    # (user, episode 88433181 registro_006 step 67 vs Marnie's Grimmsnarl,
    # WON with a mistake): turn 6 with the ACTIVE Hydrapple ex freshly evolved
    # at 0 energies, THREE Grass in hand, the manual attachment unspent and TWO
    # live charging abilities -- and the opposing active (Munkidori) at 10 HP. The
    # correct line was trivial: attach 1 Grass to the ACTIVE + Ripening Charge
    # on the ACTIVE = 2 effective = Syrup Storm (180) = a KO. Instead the
    # agent charged the BENCHED Hydrapple and sent both abilities to a
    # benched Ogerpon: a STERILE turn, without attacking, with the KO served up.
    #
    # Root cause (deck-agnostic): there was a whole family of rules for
    # charging a BENCHED attacker and promoting it (41000), but NONE that
    # asked the first question of all -- "can the active ATTACK this turn if
    # I take it the energy I can still move?" --. The charges to the active lived
    # in the development band (~31200), below any bench plan.
    # What is more, that bench plan was IMPOSSIBLE: promoting it required retreating the
    # active Hydrapple (cost 3) with 0 energies on it.
    #
    # What is measured here is the REAL BUDGET of energy that can still
    # land ON THE ACTIVE this turn: the manual attachment (if it was not spent) plus the
    # charging abilities that can point at it (`_grass_ability_slots_active`),
    # limited by the Grass in hand. If with that budget the active
    # reaches its attack cost and the attack does damage, the charge goes to the ACTIVE.
    # None of this depends on the opponent or on our own deck: the cost comes from
    # ATTACK_ENERGY_REQ (with `_min_attack_cost` as a fallback derived from the
    # card data) and the damage from the central evaluators.
    _charge_active_missing = 0        # charging units still missing
    _charge_active_finishes = False   # ...and the resulting attack KNOCKS OUT
    _charge_active_enables_attack = False  # ...it only chips, but today there is no other attack
    _cav_op_act = _active_of(op_state)
    # CAREFUL: `can_attack` is NOT used as a guard -- that flag only says whether the game
    # ALREADY offers the ATTACK option, and by definition here the active does not yet
    # reach its cost (that is what we came to fix). The correct guard is that
    # nothing PREVENTS attacking: asleep/paralysed (`condition_blocks_action`) or
    # confused (the coin flip makes the finisher unreliable; the confusion machinery
    # covers it).
    if (_active_pokemon is not None and _cav_op_act is not None
            and not condition_blocks_action and not is_confused
            and not _active_already_kos
            and _op_active_hp > 0
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _cav_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(_active_pokemon.id)
        if _cav_req is None:
            _cav_req = _min_attack_cost(_active_pokemon.id)
        _cav_e = len(_active_pokemon.energies)
        # THE CHARGE THAT DOES NOT UNLOCK THE ATTACK BUT DOES CREATE THE KNOCKOUT
        # (user, registro_010 turn 10 vs Archaludon ex, LOST). Everything below
        # used to hang off `_cav_e < _cav_req` alone: the charge was worth the
        # ACTIVE only while the active could not yet PAY for its attack. That
        # reads the cost, and the cost is not what the turn is about when the
        # attack SCALES with energy -- Myriad Leaf Shower is 30 + 30 for every
        # energy on both actives, so past the cost each Grass is 60 more damage,
        # not waste.
        #
        # On that turn our Ogerpon carried 6 effective energy against a 300 HP
        # Archaludon ex with 3: 30 + 30x9 = 300, minus 30 for its Grass
        # resistance and 30 for their Full Metal Lab = 240. One more physical
        # Grass (Meganium doubles it) makes it 30 + 30x11 = 360 - 60 = 300, their
        # ex, our last two prizes, the game. The active reached its cost of 3
        # eight times over, so this flag never even looked, and the energy scorer
        # fell through to a development rule that sends the Grass to a benched
        # pre-evolution instead ("the active does not need energy and there is a
        # Dipplin waiting to become a Hydrapple").
        #
        # It is the POSITIVE half of a question the anti-overcharge caps already
        # ask: `_extra_energy_enables_ko` is their one exception, so the codebase
        # has already decided that a cap yields to the energy that creates the
        # knockout. What was missing was anything that PREFERS the active for the
        # same reason.
        #
        # IT IS NO LONGER CONFINED TO THE TURN WITH NO TOMORROW (user,
        # `records/registro_014_pasos_156_hasta_169.json`, episode 92354161,
        # step 165, turn 14 vs Dragapult ex, LOST). It shipped gated on
        # `do_or_die` -- 0.50% of the boards -- because the score it hands out
        # (`SCORE_CHARGE_ACTIVE_FINISHER`) walks over every energy cap in the
        # file and those caps were each measured. The gate is what LOST this
        # game: active Teal Mask Ogerpon ex at 6 effective energy, a Basic {G}
        # in hand, the manual attachment unspent, and a 320 HP Dragapult ex with
        # 2 energies in front. Myriad Leaf Shower reads BOTH actives, so today
        # it is 30 + 30x(6+2) = 270 and with that one Grass on the ACTIVE it is
        # 30 + 30x(8+2) = 330 -- their ex, and we were on our last prize: the
        # game. The turn opened in mode RACE, the gate stayed shut, the Ogerpon
        # was past its cost of 3 so the `_cav_e < _cav_req` half never looked
        # either, and the Grass fell through to the development band: onto a
        # benched Applin, 23500 against the active's 8250.
        #
        # DECK-AGNOSTIC BY CONSTRUCTION: nothing below names a card. The cost
        # comes from ATTACK_ENERGY_REQ, the damage from the central evaluators
        # (`_attacker_base_damage` + `_our_effective_damage`, which is what makes
        # it work for an attack that SCALES -- Myriad with both actives, Syrup
        # Storm with the Grass on the field -- and for one that does not), and
        # the branch only speaks when the arithmetic reaches the HP in front.
        # The narrow guards it already carried are what keep the caps safe: a
        # knockout that is not guaranteed (`_ko_not_guaranteed`) sets nothing,
        # and a CHEAPER knockout that already exists through the retreat wins
        # the flag back below.
        if _cav_req is not None:
            _cav_unit = _grass_attach_unit()
            # Charges that can still land on the ACTIVE, limited by the hand.
            _dig_routes = ((0 if state.energyAttached else 1)
                          + _grass_ability_slots_active(state, my_state, field_counts))
            _cav_disp = min(hand_counts.get(Basic_Grass_Energy, 0), _dig_routes)
            if _cav_e < _cav_req:
                # Grass needed to reach the cost (rounded up).
                _cav_need = -(-(_cav_req - _cav_e) // _cav_unit)
            else:
                # Already at its cost: the number that matters is the one that
                # reaches the opposing HP, and the CHEAPEST one -- a second Grass
                # asked for by a body that dies to the first is energy the turn
                # still needs elsewhere. Zero when no reachable amount knocks
                # out, and the guard below (`1 <= _cav_need`) then leaves this
                # whole block exactly as it was.
                #
                # STRICTLY THE KNOCKOUT. The cost branch above may leave
                # `_cav_need` set on a charge that only CHIPS -- that is what the
                # `elif` below (`_charge_active_enables_attack`) is for, and it
                # is the right answer for an active that cannot attack at all.
                # This branch has no such consolation prize: the active already
                # attacks, so a charge that does not reach the HP buys nothing
                # and must leave the scorer untouched. `_ko_not_guaranteed` is
                # asked here for the same reason -- a body the KO is not
                # guaranteed against never sets the number.
                #
                # ...AND ONLY WHEN THE DESTINATION IS WHAT MAKES IT. Two kinds
                # of attack scale with energy and they do not ask the same
                # question. Myriad Leaf Shower counts the energy ON THE
                # ATTACKER (plus the opposing active's), so the Grass has to
                # land on the active or the knockout does not exist. Syrup
                # Storm counts the Grass on our WHOLE field, so it knocks out
                # from wherever the card lands -- and there this rule has
                # nothing to say: claiming the destination with a 41900 would
                # walk over the hygiene that decides it (not feeding a body
                # inside their reach, `_doomed_body`) to buy a prize that was
                # already bought. `_grass_anywhere_enables_syrup_ko` is the flag
                # written for that half. So the same charge is priced twice, on
                # the attacker and off it, and the rule only speaks when the
                # difference is the knockout.
                _cav_need = 0
                for _cav_n in (() if _ko_not_guaranteed(_cav_op_act)
                               else range(1, max(0, _cav_disp) + 1)):
                    _cav_try = _cav_e + _cav_n * _cav_unit
                    _cav_try_dmg = _our_effective_damage(
                        _active_pokemon, _cav_op_act,
                        _attacker_base_damage(
                            _active_pokemon.id, _cav_op_act, _cav_try,
                            grass_scale=total_grass + _cav_n * _cav_unit,
                            teal_self_energy=_cav_try, bench_count=bench_count),
                        AGENT_STATE.meganium_in_play, neutralization_zone_active)
                    if _cav_try_dmg >= _op_active_hp:
                        # The same cards, anywhere else of ours: the attacker
                        # keeps the energy it has today and only the field
                        # count goes up.
                        _cav_off_dmg = _our_effective_damage(
                            _active_pokemon, _cav_op_act,
                            _attacker_base_damage(
                                _active_pokemon.id, _cav_op_act, _cav_e,
                                grass_scale=total_grass + _cav_n * _cav_unit,
                                teal_self_energy=_cav_e,
                                bench_count=bench_count),
                            AGENT_STATE.meganium_in_play,
                            neutralization_zone_active)
                        if _cav_off_dmg < _op_active_hp:
                            _cav_need = _cav_n
                        break
            if 1 <= _cav_need <= _cav_disp:
                _cav_e_after = _cav_e + _cav_need * _cav_unit
                _cav_base = _attacker_base_damage(
                    _active_pokemon.id, _cav_op_act, _cav_e_after,
                    grass_scale=total_grass + _cav_need * _cav_unit,
                    teal_self_energy=_cav_e_after, bench_count=bench_count)
                _cav_dmg = _our_effective_damage(
                    _active_pokemon, _cav_op_act, _cav_base,
                    AGENT_STATE.meganium_in_play, neutralization_zone_active)
                if _cav_dmg > 0:
                    _charge_active_missing = _cav_need
                    if (_cav_dmg >= _op_active_hp
                            and not _ko_not_guaranteed(_cav_op_act)
                            # ...unless a CHEAPER KO ALREADY exists: a
                            # benched attacker that is already charged and only needs
                            # us to pay the active's retreat
                            # (`_attach_enable_retreat_ko` /
                            # `_ability_unlock_retreat_ko`). That line takes the
                            # same prize spending ONE Grass -- and it also puts the
                            # active out of harm's way -- whereas charging the active
                            # up to its cost can cost two or three. The cheaper
                            # KO rules (user, registro_014 step 136 vs
                            # Alakazam: an active Fezandipiti ex at 0 energies with the
                            # benched Hydrapple ex ALREADY ready).
                            and not _attach_enable_retreat_ko
                            and not _ability_unlock_retreat_ko):
                        _charge_active_finishes = True
                    elif (not (_bench_attacker_ready and can_switch)
                            and not op_is_cubchoo_deck):
                        # THIS CONSOLATION PRIZE IS FOR AN ACTIVE THAT CANNOT
                        # ATTACK AT ALL, and now that the block above is no
                        # longer confined to the do-or-die turn it is worth
                        # saying why it needs no guard keeping it there. The
                        # branch that measures the HP sets `_cav_need` ONLY when
                        # the charge knocks out, so the single way to fall
                        # through to here from it is with a cheaper knockout
                        # already on the table (`_attach_enable_retreat_ko` /
                        # `_ability_unlock_retreat_ko`) -- and those two lines
                        # put the Grass ON THE ACTIVE as well, to pay a retreat
                        # that is not payable yet. Same destination, so where it
                        # can still fire it agrees with what it would displace.
                        # Without a KO the charge is only prioritised when there is NO other
                        # body that is going to attack today (an already ready and
                        # promotable benched attacker rules: that line is resolved by the
                        # retreat machinery). The active's chip damage is worth
                        # infinitely more than closing the turn without attacking.
                        # The Cubchoo matchup is excluded: there the opponent BLOCKS our
                        # active's attack every turn (Snotted Up), so
                        # the energy is kept in hand to pay retreats
                        # (the user's rule, [[anti-cubchoo-...]]). The finisher
                        # (above) IS allowed: a prize is worth the bet.
                        _charge_active_enables_attack = True

    # A variant with the finisher still on the BENCH: retreating the active promotes it
    # and the retreat cost LOWERS the Grass count, so the extra Grass
    # can be exactly the one that gives the KO back (user, registro_006 step 78 vs
    # Archaludon ex). It serves so the Night Stretcher FETCH chooses the
    # ENERGY (and not a development piece) when that is the finisher's line.
    _grass_enables_promote_ko = False
    _gep_op = _active_of(op_state)
    if (_active_pokemon is not None and _gep_op is not None
            and (_gep_op.hp or 0) > 0 and can_switch):
        _gep_rc = RETREAT_COST.get(_active_pokemon.id, 1)
        if len(_active_pokemon.energies) >= _gep_rc:
            _gep_after = max(0, total_grass - _retreat_grass_units(_gep_rc))

            def _gep_ko(_g):
                return _bench_attacker_can_ko(
                    my_state, _gep_op, AGENT_STATE.meganium_in_play, total_grass,
                    bench_count, _g, neutralization_zone_active)
            _grass_enables_promote_ko = (
                _gep_ko(_gep_after + _grass_attach_unit())
                and not _gep_ko(_gep_after))

    # A LETHAL Ogerpon KO through a DOUBLE charge in one turn (user, log 85803267 turn
    # 4): Myriad Leaf Shower ({G}{G}{G}) does 30 + 30 for each energy on BOTH
    # actives. If the active is a Teal Mask Ogerpon ex and this turn we can add
    # TWO energies to it (the MANUAL attachment + Teal Dance, which attaches 1 Grass and also
    # draws), it can reach the 3 required energies and LETHAL damage (x2 if the
    # opponent is weak to Grass, e.g. Marnie's Grimmsnarl ex 320 HP -> with 3
    # energies and 2 of the opponent's: (30+30*5)*2 = 360 >= 320). The greedy scorer only
    # looks at +1 energy per option, so neither `_active_already_kos` nor
    # `_extra_energy_enables_ko` (which only count +1) detect this +2 lethal;
    # this flag stops charging the ACTIVE from being penalised/deprioritised.
    _ogerpon_td_manual_lethal = False
    if (_active_pokemon is not None
            and _active_pokemon.id == Teal_Mask_Ogerpon_ex
            and not state.energyAttached
            and _op_active_hp > 0
            and not _active_already_kos
            and hand_counts.get(Basic_Grass_Energy, 0) >= 2):
        _td_avail_lethal = any(
            o.type == OptionType.ABILITY and o.area == AreaType.ACTIVE
            for o in select.option)
        if _td_avail_lethal:
            _otml_unit = _grass_attach_unit()
            _otml_op_e = (len(op_state.active[0].energies)
                          if (op_state.active and op_state.active[0] is not None)
                          else 0)
            _otml_e_after = len(_active_pokemon.energies) + 2 * _otml_unit
            # Myriad counts the energy of BOTH actives (_otml_op_e existed
            # unused).
            _otml_dmg = 30 + 30 * (_otml_e_after + _otml_op_e)
            # The CENTRAL evaluator (P0.1): besides weakness/resistance it applies
            # Drednaw, Sturdy/Resolute Heart and ex immunities.
            if op_state.active and op_state.active[0] is not None:
                _otml_dmg = _our_effective_damage(
                    _active_pokemon, op_state.active[0], _otml_dmg,
                    AGENT_STATE.meganium_in_play, neutralization_zone_active)
            if _otml_e_after >= 3 and _otml_dmg >= _op_active_hp:
                _ogerpon_td_manual_lethal = True

    op_active_is_kangaskhan = bool(
        op_state.active and op_state.active[0] is not None
        and op_state.active[0].id == Mega_Kangaskhan_ex)

    op_kang_ko_target = False
    if op_active_is_kangaskhan and _op_active_hp > 0:
        _mult_kk = _grass_attach_unit()

        _kk_grass_max = total_grass
        if not state.energyAttached and hand_counts.get(Basic_Grass_Energy, 0) >= 1:
            _kk_grass_max += _mult_kk
        _syrup_max_kk = 30 + 30 * _kk_grass_max

        _hydra_in_play = field_counts.get(Hydrapple_ex, 0) >= 1
        _dipplin_evolvable = (field_counts.get(Dipplin, 0) >= 1
                              or hand_counts.get(Dipplin, 0) >= 1)
        _hydra_reachable = (
            hand_counts.get(Hydrapple_ex, 0) >= 1
            or (hand_counts.get(Night_Stretcher, 0) >= 1
                and discard_counts.get(Hydrapple_ex, 0) >= 1))

        _hydra_line_available = (
            _hydra_in_play
            or (_dipplin_evolvable and _hydra_reachable))

        if _hydra_line_available and _syrup_max_kk >= _op_active_hp:
            op_kang_ko_target = True

    # NEW RULE (preparing a future attacker): if Meganium and Tapu Bulu are in
    # play and the active ALREADY secures the KO on the opposing active, we charge energy onto
    # Tapu Bulu (bench) to leave it ready as next turn's attacker. With
    # Meganium each basic energy counts as {G}{G}, so 2 physical
    # energies = 4 effective = Tapu Bulu ready to attack (220). Besides the
    # manual attachment, we use Hydrapple ex's Ripening Charge ability
    # (which attaches to ANY Pokemon) to place the 2nd energy. It only applies
    # outside the special matchups, which already have their own logic.
    _tapu_bench_future = None
    for _bp_tf in (my_state.bench or []):
        if _bp_tf is not None and _bp_tf.id == Tapu_Bulu:
            _tapu_bench_future = _bp_tf
            break
    _tapu_future_charge = (
        AGENT_STATE.meganium_in_play
        and _active_already_kos
        and not _active_attack_wins_now
        and _tapu_bench_future is not None
        and len(_tapu_bench_future.energies) * _grass_mult() < 4
        and not AGENT_STATE.op_is_crustle_deck
        and not AGENT_STATE.op_is_cornerstone_deck
        and not neutralization_zone_active)

    # A SECOND ATTACKER through an ability (user, registro_014 step 137 vs Alakazam):
    # does ONE more Grass leave a REAL benched attacker READY that currently does not reach
    # its cost? Only `MAIN_ATTACKERS` (never an Applin/Chikorita, which "attack"
    # for 0-10) and only if it really crosses the threshold: it is the useful destination
    # Ripening Charge was missing when the Hydrapple already reaches its own attack.
    # Only when the MANUAL attachment has already been spent (`state.energyAttached`): there the
    # ability is the ONLY route left and vetoing it leaves the Grass dead in the
    # hand (it ends up as fodder for the cost of an Ultra Ball). While the manual
    # attachment is still free, the normal energy routing already places the Grass and there is
    # no need to touch that decision (pinned by the future-Meganium and
    # Ripening/healing tests).
    _ripen_bench_ready_pivot = False
    if (state.energyAttached
            and not AGENT_STATE.op_is_crustle_deck and not AGENT_STATE.op_is_cornerstone_deck
            and not neutralization_zone_active):
        for _rbr_bp in (my_state.bench or []):
            if _rbr_bp is None or _rbr_bp.id not in MAIN_ATTACKERS:
                continue
            _rbr_eff = len(_rbr_bp.energies) * _grass_mult()
            if (not _can_attack_eff(_rbr_bp.id, _rbr_eff)
                    and _can_attack_eff(_rbr_bp.id,
                                        _rbr_eff + _grass_attach_unit())):
                _ripen_bench_ready_pivot = True
                break

    # NEW RULE (user, registro_008 step 108 vs Alakazam, WON with a suboptimal
    # play): vs Alakazam, Meganium is an EXCELLENT ONE-prize attacker
    # (140 damage beats Alakazam 743 and its Kadabra/Abra line). When the
    # active ALREADY secures its KO this turn (we are not stealing energy from a necessary
    # attack) and on the bench there is a PARTIALLY charged Meganium (0 <
    # effective < 4, one Grass card short of its cost-4 Wood Hammer,
    # which with Wild Growth = 2 physical), we charge that Meganium to leave it READY
    # as a 1-prize attacker for the next turn -- instead of wasting the
    # energy (the manual attachment) or yielding the attack without charging it. The priority
    # is still the main attackers (Ogerpon/Applin/Dipplin/Hydrapple/
    # Tapu Bulu): Meganium's score (25000) stays BELOW their charges
    # (26000-40000), so it only wins when they no longer need the energy.
    # Reused by the manual attachment (OptionType.ATTACH) and by the target of
    # Ripening Charge (SelectContext.ATTACH_FROM), both via energy_score. A
    # Meganium at 0 energies is already covered by the bench-at-0 branch (27000).
    _meganium_bench_future = None
    for _bp_mf in (my_state.bench or []):
        if _bp_mf is not None and _bp_mf.id == Meganium:
            _meganium_bench_future = _bp_mf
            break
    _meganium_alk_future_charge = (
        op_is_alakazam_deck
        and _active_already_kos
        and not _active_attack_wins_now
        and _meganium_bench_future is not None
        and 0 < len(_meganium_bench_future.energies) * _grass_mult() < 4
        and not AGENT_STATE.op_is_crustle_deck
        and not AGENT_STATE.op_is_cornerstone_deck
        and not neutralization_zone_active)

    # NEW RULE (an ex stuck against an immune wall): when our ACTIVE is an ex
    # that the opposing active BLOCKS (Crustle makes our ex useless; Cornerstone
    # our Pokemon with abilities) it does no damage, so it is better to retreat it
    # and promote an attacker that DOES hit the wall (the one that hits hardest is
    # chosen when promoting via `_best_promote_card`). To be able to retreat, the ex
    # first has to be charged up to its retreat cost. `_ex_stuck_promo_ready` =
    # our active is blocked by the wall AND on the bench there is an attacker that is NOT
    # blocked and is READY to hit the wall this turn.
    _op_wall_active = None
    if op_has_ex_immune_active or op_has_ability_immune_active:
        _op_wall_active = _active_of(op_state)

    def _dmg_vs_wall(_p):
        # Effective damage of _p against the immune opposing active; 0 if it is blocked
        # by the immunity or if it cannot attack this turn.
        if _p is None or _op_wall_active is None:
            return 0
        if op_has_ex_immune_active and _p.id in OUR_EX_IDS:
            return 0
        if op_has_ability_immune_active and _p.id in OUR_ABILITY_IDS:
            return 0
        _e = len(_p.energies)
        _eff = _e * _grass_mult()
        # Raw base damage (without weakness/resistance: it is the direct hit against
        # the wall) via the single table _attacker_base_damage.
        return _attacker_base_damage(_p.id, _op_wall_active, _eff,
                                     grass_scale=total_grass,
                                     teal_self_energy=_e,
                                     bench_count=bench_count)

    _my_active_pk = (my_state.active[0]
                     if (my_state.active and my_state.active[0] is not None)
                     else None)
    _active_blocked_by_wall = (
        _op_wall_active is not None and _my_active_pk is not None
        and ((op_has_ex_immune_active and _my_active_pk.id in OUR_EX_IDS)
             or (op_has_ability_immune_active and _my_active_pk.id in OUR_ABILITY_IDS)))
    _wall_bench_attacker_ready = any(
        _dmg_vs_wall(_bp) > 0 for _bp in (my_state.bench or []))

    # A 1-PRIZE ATTACKER vs Alakazam THIS TURN (user, registro_008 step ~112
    # vs Alakazam, LOST): vs Alakazam we must ALWAYS knock out with a
    # 1-PRIZE body when we can. If the ACTIVE is an ex of OURS (2 prizes) and on the
    # bench there is a Meganium ONE Grass short of its attack cost (Wood Hammer 4 eff;
    # Wild Growth doubles every physical Grass) whose damage (140) KNOCKS OUT the opposing
    # active, the charge (the manual attachment) must go to the MEGANIUM -- not to the active ex --
    # to leave it READY and attack THIS turn with the 1-prize body: the ex retreats and
    # Meganium is promoted (the retreat logic already does this when Meganium is
    # READY; it was verified that with Meganium at 4 eff the agent retreats the ex and promotes
    # the 1-prize body). We concede 1 prize instead of 2 and the ex tank is sheltered.
    # Unlike `_meganium_alk_future_charge` (25000, which prepares Meganium for
    # the NEXT turn while keeping the ex as THIS turn's attacker), here Meganium
    # ATTACKS this turn, so it dominates the charge of the active ex. Only when 1
    # Grass is enough (2 <= eff < 4) and Meganium KNOCKS OUT; if attacking with the ex already WINS the
    # game it does not apply (there is no future turn to protect). Deck-gated (Alakazam),
    # with no leakage into other matchups.
    # GUARD (user, registro_014 step 136 vs Alakazam): the whole rule leans on
    # "the ex retreats and Meganium is promoted", so it only holds if the RETREAT
    # is legal this turn (`can_switch`). With the active Fezandipiti ex at 0
    # energies (cost 1) the charged Meganium stayed on the bench without attacking and
    # this 43000 overrode the attachment that DID enable the play: the Grass to the
    # ACTIVE to pay the retreat and bring up the ready Hydrapple ex
    # (`_attach_enable_retreat_ko`, 41000). If the retreat is not legal, Meganium
    # does not attack today: its charge falls back to the FUTURE tier (25000) and the energy is routed
    # to unblocking the turn.
    _meganium_alk_1prize_attacker = False
    if (op_is_alakazam_deck
            and can_switch
            and not _active_attack_wins_now
            and not _win_via_boss_gust
            and _my_active_pk is not None and _my_active_pk.id in OUR_EX_IDS
            and _meganium_bench_future is not None
            and op_state.active and op_state.active[0] is not None
            and not AGENT_STATE.op_is_crustle_deck and not AGENT_STATE.op_is_cornerstone_deck
            and not neutralization_zone_active):
        _malk_eff = len(_meganium_bench_future.energies) * _grass_mult()
        _malk_unit = _grass_attach_unit()
        if _malk_eff < 4 and _malk_eff + _malk_unit >= 4:
            _malk_opa = op_state.active[0]
            _malk_base = _attacker_base_damage(
                Meganium, _malk_opa, 4, grass_scale=total_grass,
                teal_self_energy=4, bench_count=bench_count)
            _malk_dmg = _our_effective_damage(
                _meganium_bench_future, _malk_opa, _malk_base,
                AGENT_STATE.meganium_in_play, neutralization_zone_active)
            if _malk_dmg > 0 and _malk_dmg >= (_malk_opa.hp or 0):
                _meganium_alk_1prize_attacker = True

    # Rule (user, log 86174943 turn 22, vs Crustle, LOST): if our
    # active is a Teal Mask Ogerpon ex READY to attack (>=3 effective) and this
    # turn we can play Boss's Orders to BRING UP a Mega Kangaskhan ex from the
    # opposing bench, we do NOT retreat the Ogerpon to promote a Dipplin. The Kangaskhan
    # is NOT the immune line (Crustle), so Ogerpon CAN attack it and is its
    # BEST attacker; Dipplin is KEPT to break the Crustle wall (our ex
    # do 0 to it). Before, `_ex_stuck_promo_ready` saw the active Ogerpon blocked
    # by the Crustle wall + a ready Dipplin on the bench and retreated it (6000), even though the
    # real plan of the turn was Boss's on the Kangaskhan and attacking it with Ogerpon.
    _keep_ogerpon_for_kang = False
    if (AGENT_STATE.op_is_crustle_deck
            and _my_active_pk is not None
            and _my_active_pk.id == Teal_Mask_Ogerpon_ex
            and len(_my_active_pk.energies) * _grass_mult() >= 3
            and hand_counts.get(Boss_Orders, 0) >= 1
            and not state.supporterPlayed):
        for _kbp in (op_state.bench or []):
            if _kbp is not None and _kbp.id == Mega_Kangaskhan_ex:
                _keep_ogerpon_for_kang = True
                break

    _ex_stuck_promo_ready = (_active_blocked_by_wall and _wall_bench_attacker_ready
                             and not _keep_ogerpon_for_kang)

    # Rule (user, log 86406907 step 87, WON vs Crustle): if our ACTIVE
    # is a NON-ex attacker that DOES hit the ex-immune wall (the opposing active IS
    # the Crustle/Sylveon, op_has_ex_immune_active True) and it can attack this
    # turn, it NEVER retreats: it MUST attack. Retreating it would promote a benched ex
    # Pokemon that does 0 damage to the wall (our ex do not hit it). The ONLY reason
    # to retreat vs Crustle is that the opposing active is NOT the wall (e.g. a
    # Mega Kangaskhan ex), in which case op_has_ex_immune_active is False and this
    # flag does not apply. `_dmg_vs_wall` already returns 0 for our blocked ex and
    # >0 only for a non-ex attacker with enough energy against that wall.
    #
    # LETHAL RELIEF AGAINST THE WALL (user, registro_018 step 113 vs Crustle,
    # LOST): the premise "retreating it would only promote an ex that does 0" is FALSE
    # when on the bench there waits ANOTHER unblocked body that also FINISHES the
    # wall. There the active was a Meganium at 4 effective -- Solar Beam 140 against
    # a Crustle with **170** HP (it carries a Grass Energy, which gives +20 HP to Grass
    # Pokemon) --: attacking left the wall alive at 30 and gave the turn away,
    # while on the bench a Tapu Bulu waited already at 4 effective whose Wood Hammer
    # (220) knocked it out. The missing rule, in general: **if the active does NOT finish
    # and a benched body DOES, retreat and finish**. Note: the retreat DISCARDS
    # energy (whole cards), so the Grass that will remain on the field is measured
    # AFTER the retreat -- the same criterion as `_hlp_grass_after`.
    _wall_ko_promote = None
    if (_op_wall_active is not None and _my_active_pk is not None
            and can_switch and (_op_wall_active.hp or 0) > 0):
        _wkp_hp = _op_wall_active.hp or 0
        _wkp_active_dmg = _our_effective_damage(
            _my_active_pk, _op_wall_active, _dmg_vs_wall(_my_active_pk),
            AGENT_STATE.meganium_in_play, neutralization_zone_active)
        if _wkp_active_dmg < _wkp_hp:
            _wkp_cost = RETREAT_COST.get(_my_active_pk.id, 1)
            _wkp_grass_after = max(
                0, total_grass - (0 if has_switch_card
                                  else _retreat_grass_units(_wkp_cost)))
            for _wkp_bp in (my_state.bench or []):
                if _wkp_bp is None:
                    continue
                if op_has_ex_immune_active and _wkp_bp.id in OUR_EX_IDS:
                    continue  # the wall makes it immune: 0 damage
                if op_has_ability_immune_active and _wkp_bp.id in OUR_ABILITY_IDS:
                    continue
                _wkp_e = len(_wkp_bp.energies)
                _wkp_base = _attacker_base_damage(
                    _wkp_bp.id, _op_wall_active, _wkp_e * _grass_mult(),
                    grass_scale=_wkp_grass_after, teal_self_energy=_wkp_e,
                    bench_count=bench_count)
                if _wkp_base <= 0:
                    continue  # it does not reach its energy requirement
                _wkp_dmg = _our_effective_damage(
                    _wkp_bp, _op_wall_active, _wkp_base,
                    AGENT_STATE.meganium_in_play, neutralization_zone_active)
                if _wkp_dmg >= _wkp_hp:
                    _wall_ko_promote = _wkp_bp
                    break
    # ...but the relief YIELDS to the gust (user, registro_020 step 122): if with
    # Boss's Orders we can bring up a body from the opposing bench that OUR ACTIVE
    # knocks out, that prize comes WITHOUT paying the retreat (no energy is discarded and
    # the relief is not exposed to the counterattack) and it also removes from the board a body that is already
    # wounded. The same prize, cheaper: the gust first.
    if (_wall_ko_promote is not None and can_attack
            and hand_counts.get(Boss_Orders, 0) >= 1
            and not state.supporterPlayed):
        for _wkp_gt in (op_state.bench or []):
            if _wkp_gt is None:
                continue
            _wkp_gt_e = len(_my_active_pk.energies)
            _wkp_gt_base = _attacker_base_damage(
                _my_active_pk.id, _wkp_gt, _wkp_gt_e * _grass_mult(),
                grass_scale=total_grass, teal_self_energy=_wkp_gt_e,
                bench_count=bench_count)
            if _wkp_gt_base <= 0:
                continue
            _wkp_gt_dmg = _our_effective_damage(
                _my_active_pk, _wkp_gt, _wkp_gt_base,
                AGENT_STATE.meganium_in_play, neutralization_zone_active)
            if _wkp_gt_dmg > 0 and _wkp_gt_dmg >= (_wkp_gt.hp or 0):
                _wall_ko_promote = None
                break

    _nonex_active_hits_wall = (
        can_attack
        and op_has_ex_immune_active
        and _my_active_pk is not None
        and _my_active_pk.id not in OUR_EX_IDS
        and _dmg_vs_wall(_my_active_pk) > 0
        # ...unless the bench relief FINISHES and the active does not (see above).
        and _wall_ko_promote is None)

    # Teal Dance -> retreat -> promote a lethal attacker pivot (user, log
    # 85802744 turn 16): if the active is a Teal Mask Ogerpon ex BLOCKED by
    # the opposing wall (Crustle/Sylveon makes our ex useless) that canNOT yet
    # retreat (effective energy < the retreat cost) but there is a non-ex attacker
    # READY on the bench that DOES hit the wall, and we have a basic Grass Energy
    # in hand, the correct line is to use TEAL DANCE on the active (it attaches
    # the Grass to the active itself + DRAWS 1 card) to enable its retreat, and
    # NOT waste the Grass charging bench developers (e.g. Dipplin).
    # After Teal Dance the active will have energy to retreat on the next step and
    # bring up the attacker that knocks out the wall. `_grass_attach_unit()` = the EFFECTIVE
    # energy 1 Grass provides (2 with Meganium in play, 1 without).
    _teal_dance_ko_pivot = False
    if (_ex_stuck_promo_ready
            and _my_active_pk is not None
            and _my_active_pk.id == Teal_Mask_Ogerpon_ex
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _tdkp_rc = RETREAT_COST.get(Teal_Mask_Ogerpon_ex, 1)
        _tdkp_eff_now = len(_my_active_pk.energies) * _grass_mult()
        _tdkp_eff_after = _tdkp_eff_now + _grass_attach_unit()
        if _tdkp_eff_now < _tdkp_rc and _tdkp_eff_after >= _tdkp_rc:
            _teal_dance_ko_pivot = True

    # A 1-prize SACRIFICE pivot (user, registro_008 step 110 vs Mega
    # Lucario, LOST): if the ACTIVE is a FRAGILE ex of OURS (2 prizes) that
    # will be KNOCKED OUT next turn, and on the bench there is a READY NON-ex attacker (1
    # prize) that KNOCKS OUT the opposing active, the correct line is to RETREAT the
    # ex and promote the non-ex to attack: the SAME KO is made, but if the opponent
    # knocks us out next turn they concede 1 prize (not 2) and the ex tank is
    # sheltered on the bench. The user's rule: whenever we see that our ex
    # may fall next turn and a 1-prize body on the bench can defeat
    # the active, we retreat the ex and use the non-ex to reduce the prizes
    # the opponent can win. It does NOT apply if attacking with the ex ALREADY wins the game (there is
    # no future turn to protect). For an active Hydrapple ex, the retreat is
    # enabled with Ripening Charge (see _ripen_retreat_ko_pivot). The benched attacker's
    # damage is measured with the single table and applies weakness/zone.
    _fragile_ex_sac_pivot = False
    _fragile_ex_sac_attacker = None
    if (_my_active_pk is not None and _my_active_pk.id in OUR_EX_IDS
            and op_state.active and op_state.active[0] is not None
            and (active_ko_likely
                 or (estimated_op_damage > 0
                     and estimated_op_damage >= (_my_active_pk.hp or 0)))
            and not (my_prize <= prize_count_op(op_state.active[0]))):
        _fesp_opa = op_state.active[0]
        _fesp_opa_hp = _fesp_opa.hp or 0
        for _fesp_bp in (my_state.bench or []):
            if (_fesp_bp is None or _fesp_bp.id in OUR_EX_IDS
                    or _fesp_bp.id not in MAIN_ATTACKERS):
                continue
            _fesp_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(_fesp_bp.id)
            if _fesp_req is None:
                continue
            _fesp_e = len(_fesp_bp.energies)
            _fesp_eff = _fesp_e * _grass_mult()
            if _fesp_eff < _fesp_req:
                continue
            _fesp_base = _attacker_base_damage(
                _fesp_bp.id, _fesp_opa, _fesp_eff,
                grass_scale=total_grass, teal_self_energy=_fesp_e,
                bench_count=bench_count)
            _fesp_dmg = _our_effective_damage(
                _fesp_bp, _fesp_opa, _fesp_base, AGENT_STATE.meganium_in_play,
                neutralization_zone_active)
            if _fesp_dmg > 0 and _fesp_dmg >= _fesp_opa_hp:
                _fragile_ex_sac_pivot = True
                _fragile_ex_sac_attacker = _fesp_bp
                break

    # Ripening Charge -> retreat -> promote a lethal attacker pivot (user, log
    # 86028607 turn 22, WON): analogous to _teal_dance_ko_pivot but with the
    # ACTIVE = a Hydrapple ex BLOCKED by the opposing wall (Crustle makes our ex
    # useless, Hydrapple ex does 0). Hydrapple ex cannot attack but it has
    # the Ripening Charge ability: it is used to attach a Grass TO THE ACTIVE
    # Hydrapple itself and reach its (EFFECTIVE) retreat cost, retreat it and
    # bring up a READY non-ex attacker from the bench (Tapu Bulu, 220) that knocks out
    # the wall. The retreat is measured in EFFECTIVE energy (Meganium's Wild Growth
    # doubles every physical Grass), which is why 1 Grass (=2 eff with Meganium) is enough
    # to go from 2 to 4 eff >= the cost of 3. It requires _ex_stuck_promo_ready (a blocked
    # active + a benched attacker already READY); that is why it only switches on AFTER
    # charging Tapu with the manual attachment (which leaves it ready this very turn),
    # at which point the greedy tie-break re-evaluates and this flag becomes True.
    # Anti-Cubchoo pivot: an active Hydrapple ex BLOCKED (Snotted Up) -> Ripening
    # Charge -> retreat -> promote a READY benched attacker (user, registro_008
    # step 82 vs cornerstone_cubchoo, LOST). The active Hydrapple ex canNOT
    # attack (the Cubchoo lock), but on the bench there is an Ogerpon ex ALREADY charged that
    # knocks out the Cubchoo. The correct line: use Ripening Charge on the Hydrapple
    # ITSELF to reach its (effective) retreat cost, retreat it and bring up
    # the Ogerpon to attack. The user's rule against this deck: if the active canNOT
    # attack, prioritise the retreat in order to attack. Unlike
    # [[anti-cubchoo-no-retirada-pivote-conservar-energia]] (a CHARGED active Ogerpon
    # whose energy would be wasted -> keep it/PASS), here the active is
    # a Hydrapple ex whose extra energy is dead weight (Syrup Storm scales with
    # the Grass on the FIELD, not with its own energy) and is UNDER-charged (it cannot pay
    # the retreat): charging it with the ability and retreating it does NOT waste attack
    # potential and it ENABLES a KO. Limited to Hydrapple ex (a body with Ripening and
    # dead-weight energy) so as not to clash with the conservation veto, which
    # covers the charged Ogerpon. It does not depend on the active's current energy, so
    # it stays True on the retreat step (can_switch already True).
    _cubchoo_lock_stuck = False
    if (op_is_cubchoo_deck and not can_attack
            and _my_active_pk is not None
            and _my_active_pk.id == Hydrapple_ex
            and op_state.active and op_state.active[0] is not None):
        _cls_rc = RETREAT_COST.get(Hydrapple_ex, 3)
        _cls_grass_after = max(
            0, total_grass - _retreat_grass_units(_cls_rc))
        _cubchoo_lock_stuck = _bench_attacker_can_ko(
            my_state, op_state.active[0], AGENT_STATE.meganium_in_play, total_grass,
            bench_count, _cls_grass_after, neutralization_zone_active)

    # A MUTED BODY WHOSE ENERGY WAS NEVER INVESTMENT CASHES THE PRIZE (user,
    # registro_007 turn 7 vs crustle_cubchoo_spheal, LOST). Same shape as
    # `_cubchoo_lock_stuck` and it exempts from the SAME conservation veto, but it
    # is a separate flag because it must NOT reach that flag's other two consumers
    # (the 6000 tier of the RETREAT branch and the 24000 charge-to-pay-the-retreat
    # of energy_score). Widening those as well TRIPLES the blast radius --
    # `utils/shadow.py` over 300 games vs crustle_cubchoo_spheal: 13 flips
    # (0.031%) against 4 (0.010%) for this flag alone -- and every extra flip is
    # an attachment, a decision this board never asked about. Neither variant can
    # be arbitrated by winrate at that frequency
    # ([[matchpoint-el-gate-no-arbitra-mide-la-frecuencia]]), so the tie-break is
    # the smallest blast radius that fixes the decision.
    #
    # The board: our active is a **Meowth ex** muted by Snotted Up with 3 Grass on
    # it, on the bench a Teal Mask Ogerpon ex charged to 3, and in front a Cubchoo
    # at 70 HP that Myriad Leaf Shower (which counts the energy on BOTH actives)
    # knocks out. There is no ATTACK option in the menu; the retreat costs 1 and
    # cashes a prize. The turn closed with END instead -- and, in the golden
    # corpus, so did turns 9, 11, 13, 15, 17, 19, 21 and 23 of that same game: the
    # same frozen board, nine turns in a row, zero prizes.
    #
    # What exempts a body is that its energy is NOT attack investment, so
    # retreating destroys nothing that would ever become damage. That is true of
    # the bodies in `NON_ATTACKER_ENERGY_WASTE_IDS` -- Meowth ex, Fezandipiti ex --
    # which are hand engines and do not attack at all: every energy on them is dead
    # the moment it lands. The charged Teal Mask Ogerpon ex of
    # [[anti-cubchoo-no-retirada-pivote-conservar-energia]] (registro_004 p47) stays
    # OUT on purpose: its Myriad Leaf Shower scales with its OWN energy, those Grass
    # ARE investment, and the PASS still stands.
    _cubchoo_mute_cashes_prize = False
    if (op_is_cubchoo_deck and not can_attack
            and _my_active_pk is not None
            and _my_active_pk.id in NON_ATTACKER_ENERGY_WASTE_IDS
            and op_state.active and op_state.active[0] is not None):
        _cmcp_rc = RETREAT_COST.get(_my_active_pk.id, 1)
        _cmcp_grass_after = max(
            0, total_grass - _retreat_grass_units(_cmcp_rc))
        _cubchoo_mute_cashes_prize = _bench_attacker_can_ko(
            my_state, op_state.active[0], AGENT_STATE.meganium_in_play, total_grass,
            bench_count, _cmcp_grass_after, neutralization_zone_active)

    _ripen_retreat_ko_pivot = False
    if ((_ex_stuck_promo_ready or _fragile_ex_sac_pivot or _cubchoo_lock_stuck)
            and _my_active_pk is not None
            and _my_active_pk.id == Hydrapple_ex
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _rrkp_rc = RETREAT_COST.get(Hydrapple_ex, 3)
        _rrkp_eff_now = len(_my_active_pk.energies) * _grass_mult()
        _rrkp_eff_after = _rrkp_eff_now + _grass_attach_unit()
        if _rrkp_eff_now < _rrkp_rc and _rrkp_eff_after >= _rrkp_rc:
            _ripen_retreat_ko_pivot = True

    # Ripening Charge -> charge the benched Tapu to LETHAL -> retreat the Hydrapple
    # -> promote Tapu -> knock out the wall (user, log 86182112 step 82, WON vs
    # Crustle). A variant of _ripen_retreat_ko_pivot for when the active
    # Hydrapple ex blocked by the Crustle wall CAN already retreat (effective
    # energy >= the retreat cost) but the benched Tapu Bulu is NOT ready yet
    # (it needs a 2nd Grass to reach 4 effective = Wood Hammer 220). Without
    # this flag, Teal Dance (Ogerpon, the Crustle cap) and Ripening Charge were BOTH
    # at -1 and the greedy tie-break chose Teal Dance, overcharging
    # Ogerpon (physical > the cap) and leaving Tapu at 2 effective, unable to finish
    # the wall. Ripening Charge (which attaches a Grass to ANY Pokemon) must WIN
    # so as to put the 2nd Grass on Tapu; the Tapu target is fixed in energy_score
    # (ATTACH_FROM, +20000 because _tapu_eff_ct < 4). It only switches on AFTER the
    # manual attachment that leaves Tapu at 2 effective (the greedy tie-break re-evaluates step by step).
    # _grass_attach_unit() = the EFFECTIVE energy of 1 Grass (2 with Meganium).
    _ripen_bench_tapu_ko_pivot = False
    if (AGENT_STATE.op_is_crustle_deck
            and _active_blocked_by_wall
            and _my_active_pk is not None
            and _my_active_pk.id == Hydrapple_ex
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _rbtk_rc = RETREAT_COST.get(Hydrapple_ex, 3)
        _rbtk_act_eff = len(_my_active_pk.energies) * _grass_mult()
        if _rbtk_act_eff >= _rbtk_rc:
            _rbtk_unit = _grass_attach_unit()
            _rbtk_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(Tapu_Bulu, 4)
            for _rbtk_bp in (my_state.bench or []):
                if _rbtk_bp is None or _rbtk_bp.id != Tapu_Bulu:
                    continue
                _rbtk_eff_now = len(_rbtk_bp.energies) * _grass_mult()
                _rbtk_eff_after = _rbtk_eff_now + _rbtk_unit
                if _rbtk_eff_now >= _rbtk_req or _rbtk_eff_after < _rbtk_req:
                    continue
                _rbtk_base = _attacker_base_damage(
                    Tapu_Bulu, _op_wall_active, _rbtk_eff_after,
                    grass_scale=total_grass, teal_self_energy=0,
                    bench_count=bench_count)
                if _our_effective_damage(
                        _rbtk_bp, _op_wall_active, _rbtk_base,
                        AGENT_STATE.meganium_in_play) >= (_op_wall_active.hp or 0):
                    _ripen_bench_tapu_ko_pivot = True
                    break

    # --- Charging focus on ONE Ogerpon that can become LETHAL this turn ---
    # (user, registro_006 step 62 vs Marnie's Grimmsnarl ex, a KO not finished):
    # with TWO Teal Mask Ogerpon ex in play, the charge (Teal Dance + the manual
    # attachment) was split between both and NEITHER reached the 3 lethal energies,
    # so the weakness KO (Myriad 180 x2 = 360 >= 320) was never assembled.
    # Here ONE single Ogerpon is identified that, by concentrating its 2 charging sources
    # of this turn (Teal Dance attaches 1 Grass from hand + the manual attachment),
    # reaches 3 EFFECTIVE energies and KNOCKS OUT the opposing active -- ALWAYS considering
    # the opponent's weakness via `_our_effective_damage`. The MOST charged
    # Ogerpon is preferred (less extra energy needed) to maximise the probability
    # of completing the finisher. energy_score concentrates the manual
    # attachment on that body and VETOES charging ANOTHER Ogerpon (no splitting); the
    # promotion+attack is resolved by `_ogerpon_lethal_promote` once it is charged.
    # The focus ONLY applies when the ACTIVE is STUCK: it is a body that does NOT
    # reach its own attack this turn even by charging (the manual attachment + its charging
    # ability: the Hydrapple's Ripening / the Ogerpon's Teal Dance). If the
    # active CAN attack by charging itself (e.g. an active Hydrapple ex with Ripening
    # Charge -> Syrup Storm, registro_009/lucario), the energy must go to the ACTIVE
    # and NOT be diverted to a benched Ogerpon: in that case the focus does not switch on.
    _olf_active = my_state.active[0] if my_state.active else None
    _olf_active_viable = False
    if _olf_active is not None and _olf_active.id in MAIN_ATTACKERS:
        _olf_a_eff = len(_olf_active.energies) * _grass_mult()
        _olf_a_grass = (hand_counts.get(Basic_Grass_Energy, 0) >= 1)
        _olf_a_extra = 0
        if not state.energyAttached and _olf_a_grass:
            _olf_a_extra += _grass_attach_unit()
        if (_olf_active.id in (Hydrapple_ex, Teal_Mask_Ogerpon_ex)
                and _olf_a_grass):
            _olf_a_extra += _grass_attach_unit()
        if _olf_a_eff + _olf_a_extra >= AGENT_STATE.ATTACK_ENERGY_REQ.get(_olf_active.id, 99):
            _olf_active_viable = True

    # The focus does NOT switch on when this turn's Grass has a more
    # urgent destination: paying the ACTIVE's RETREAT so a benched body that is ALREADY
    # ready can attack (`_ability_unlock_retreat_*`). That is the failure of registro_006 step
    # 101 vs Alakazam (LOST): with a benched Ogerpon at 6 effective (lethal
    # on the Alakazam) trapped behind an active Applin at 0 energies, the
    # focus sent the Grass to the OTHER Ogerpon "to make it lethal" -- a second
    # finisher just as trapped -- and the turn died without attacking. While the
    # retreat is not paid for, charging the bench promotes nobody.
    _ogerpon_lethal_focus_serial = None
    _olf_opa = _active_of(op_state)
    if (_olf_opa is not None and (_olf_opa.hp or 0) > 0
            and not _olf_active_viable
            and not _ability_unlock_retreat_ko
            and not _ability_unlock_retreat_attack
            and not op_has_ex_immune_active
            and not neutralization_zone_active):
        _olf_unit = _grass_attach_unit()
        _olf_grass = hand_counts.get(Basic_Grass_Energy, 0)
        if (hand_counts.get(Night_Stretcher, 0) >= 1
                and discard_counts.get(Basic_Grass_Energy, 0) >= 1):
            _olf_grass += 1
        _olf_opp_e = len(getattr(_olf_opa, 'energies', []) or [])
        _olf_best = None
        _olf_best_cur = -1
        for _olf_pk in (list(my_state.active or []) + list(my_state.bench or [])):
            if _olf_pk is None or _olf_pk.id != Teal_Mask_Ogerpon_ex:
                continue
            _olf_cur = len(_olf_pk.energies)
            if _olf_cur >= 3:
                continue  # already ready: it does not need the charging focus
            # REACHABLE energy by concentrating Teal Dance (+1 if there is Grass) and the
            # manual attachment (+1 if it has not been attached yet and a 2nd Grass is left).
            _olf_reach = _olf_cur
            if _olf_grass >= 1:
                _olf_reach += _olf_unit
            if not state.energyAttached and _olf_grass >= 2:
                _olf_reach += _olf_unit
            if _olf_reach < 3:
                continue
            _olf_dmg = _our_effective_damage(
                _olf_pk, _olf_opa, 30 + 30 * (_olf_reach + _olf_opp_e),
                AGENT_STATE.meganium_in_play, neutralization_zone_active)
            if _olf_dmg <= 0 or _olf_dmg < (_olf_opa.hp or 0):
                continue
            if _olf_cur > _olf_best_cur:
                _olf_best_cur = _olf_cur
                _olf_best = _olf_pk
        if _olf_best is not None:
            _ogerpon_lethal_focus_serial = getattr(_olf_best, 'serial', None)

    def _energy_score_base(pokemon, active):
        return _energy_score_base_impl(
            CtxEnergyScoreBase(
            _ability_unlock_retreat_attack=_ability_unlock_retreat_attack,
            _ability_unlock_retreat_ko=_ability_unlock_retreat_ko,
            _active_already_kos=_active_already_kos,
            _active_doomed_real=_active_doomed_real,
            _active_hydra_capped=_active_hydra_capped,
            _active_needs_energy=_active_needs_energy,
            _active_pokemon=_active_pokemon,
            _attach_enable_retreat_attack=_attach_enable_retreat_attack,
            _attach_enable_retreat_ko=_attach_enable_retreat_ko,
            _bench_attacker_needs_energy=_bench_attacker_needs_energy,
            _bench_attacker_ready=_bench_attacker_ready,
            _bench_has_chargeable=_bench_has_chargeable,
            _charge_active_enables_attack=_charge_active_enables_attack,
            _charge_active_finishes=_charge_active_finishes,
            _conf_active=_conf_active,
            _conf_active_can_attack=_conf_active_can_attack,
            _conf_active_can_retreat=_conf_active_can_retreat,
            _conf_bench_attacker_body=_conf_bench_attacker_body,
            _conf_bench_attacker_ready=_conf_bench_attacker_ready,
            _conf_can_attack_pkmn=_conf_can_attack_pkmn,
            _conf_is_matchup_attacker=_conf_is_matchup_attacker,
            _ctm_applin_bench=_ctm_applin_bench,
            _ctm_charge_active_dipplin=_ctm_charge_active_dipplin,
            _ctm_chikorita_bench=_ctm_chikorita_bench,
            _ctm_tapu_high=_ctm_tapu_high,
            _cubchoo_lock_stuck=_cubchoo_lock_stuck,
            _ex_stuck_promo_ready=_ex_stuck_promo_ready,
            _extra_energy_enables_ko=_extra_energy_enables_ko,
            _feza_lucario_wall=_feza_lucario_wall,
            _ft_wall_charge_active=_ft_wall_charge_active,
            _opening_sac_charge_active=_opening_sac_charge_active,
            _gust_2prize_via_boss=_gust_2prize_via_boss,
            _hydra_fragile_pivot=_hydra_fragile_pivot,
            _meganium_alk_1prize_attacker=_meganium_alk_1prize_attacker,
            _meganium_alk_future_charge=_meganium_alk_future_charge,
            _ogerpon_lethal_focus_serial=_ogerpon_lethal_focus_serial,
            _ogerpon_td_manual_lethal=_ogerpon_td_manual_lethal,
            _ripen_retreat_ko_pivot=_ripen_retreat_ko_pivot,
            _tapu_future_charge=_tapu_future_charge,
            _win_via_boss_gust=_win_via_boss_gust,
            active_ko_likely=active_ko_likely,
            bench_count=bench_count,
            field_counts=field_counts,
            hand_counts=hand_counts,
            has_hydrapple=has_hydrapple,
            is_confused=is_confused,
            my_state=my_state,
            neutralization_zone_active=neutralization_zone_active,
            op_has_ex_immune_active=op_has_ex_immune_active,
            op_has_ex_immune_bench=op_has_ex_immune_bench,
            op_has_froslass=op_has_froslass,
            op_is_aggro_deck=op_is_aggro_deck,
            op_is_alakazam_deck=op_is_alakazam_deck,
            op_is_beedrill_deck=op_is_beedrill_deck,
            op_is_cubchoo_deck=op_is_cubchoo_deck,
            op_is_drednaw_deck=op_is_drednaw_deck,
            op_is_fire_deck=op_is_fire_deck,
            op_is_hop_deck=op_is_hop_deck,
            op_is_lucario_deck=op_is_lucario_deck,
            op_is_sylveon_deck=op_is_sylveon_deck,
            op_kang_ko_target=op_kang_ko_target,
            op_state=op_state,
            state=state,
            total_grass=total_grass,
            ),
            pokemon, active,
        )

    def _doomed_body(pokemon, active) -> bool:
        """PHASE C (Marnie plan, D3): can the opponent CASH IN this body before
        our next turn, without the body taking anything first?

        Game 2 turn 10: Teal Dance on the BENCHED Ogerpon at 80/210, which
        died that same turn with 5 Grass on it. Of the 13 Grass in the deck,
        8 went to the discard inside knocked-out bodies.

        While the body LIVES the energy is NOT wasted -- Syrup Storm
        scales with the Grass on our WHOLE board and Myriad Leaf Shower with the
        Ogerpon's own (which is why the "attack cost + 1" cap the plan asked for is
        NOT implemented: overcharging is not the defect). The waste
        happens at the KO, so the condition is not "it already has enough" but
        "the opponent can cash it in".

        It is measured with the COMPLETE window -- the one that includes the AIMABLE
        damage of Adrena-Brain --, the opposite of Ripening Charge's healing, which uses the
        GUARANTEED one. The asymmetry is deliberate: there a false positive spends the
        whole ability on a body that was dying anyway; here it only diverts the
        Grass to another body of OURS, and for Syrup Storm it makes no difference where
        it lands. A nearly free false positive, a false negative = a prize.

        Without Froslass or Munkidori on the field both terms of the window are 0 and
        this does not switch on in any other matchup.
        """
        if AGENT_STATE._op_chip_per_round <= 0 and AGENT_STATE._op_movable_dmg <= 0:
            return False
        _cc_hp = pokemon.hp or 0
        if _cc_hp <= 0:
            return False
        # The ACTIVE that attacks TODAY is not doomed for these purposes: the energy
        # is cashed in before the opponent plays. The Grass we are
        # about to attach is counted (one card = _grass_mult() effective).
        if active and _can_attack_eff(pokemon.id,
                                      len(pokemon.energies) + _grass_mult()):
            return False
        _cc_golpe = estimated_op_damage if active else AGENT_STATE._op_bench_snipe_dmg
        return _cc_hp <= _ventana_de_regalo(pokemon, active, _cc_golpe)

    def energy_score(pokemon: Pokemon, active: bool) -> float:
        """`_energy_score_base` + the PHASE C ceiling.

        The ceiling goes in the WRAPPER and not at the end of the body because
        `_energy_score_base` has ~60 `return` statements scattered around (per-matchup caps,
        bench-at-0 bands, pivots...): a ceiling at the end would only reach the
        generic tail. Here it passes through the ONLY point all of them exit by.

        CAP, do not veto, and only BELOW the lethal floor (41000): everything that
        reaches that band is energy that takes or denies a prize TODAY --
        `_charge_active_finishes`, the retreat pivots, `_win_via_boss_gust` --
        and there the body does not die without having paid. What is below is
        development, and developing a body the opponent cashes in tonight is
        handing them the Grass. The relative ORDER between doomed bodies is preserved
        (a tiny fraction) so that, if the WHOLE board is inside the window, the same
        body that used to win still wins.

        The SECOND ceiling answers the mirror question and rides here for the
        same reason. While the turn's only attack hangs on the ACTIVE receiving
        the Grass that pays its retreat, no BENCH charge may outrank it: the
        active's band (31200/31250) was calibrated on "above any bench charge
        (<= 31150)", and the per-matchup branches of `_energy_score_base` --
        which answer "which body do I develop", a question that only arises when
        the energy is not doing anything better -- break that invariant with
        scores of up to 44000. See `SCORE_BENCH_YIELDS_TO_RETREAT_UNLOCK`."""
        score = _energy_score_base(pokemon, active)
        if (not active
                and (_attach_enable_retreat_attack
                     or _ability_unlock_retreat_attack)
                and SCORE_BENCH_YIELDS_TO_RETREAT_UNLOCK < score
                < SCORE_CHARGE_LETHAL_FLOOR):
            score = SCORE_BENCH_YIELDS_TO_RETREAT_UNLOCK + score / 1000000.0
        if 0 < score < SCORE_CHARGE_LETHAL_FLOOR and _doomed_body(pokemon, active):
            return SCORE_CHARGE_DOOMED + score / 1000000.0
        return score

    # --- Ripening Charge as HEALING: saving a body doomed by the snipe ---
    # (user, registro_006/008 steps 96-122 vs Marnie's Grimmsnarl ex, LOST.)
    # Ripening Charge does not only ATTACH a Grass: it HEALS 30 on the Pokemon that
    # receives it. When the benched Dipplin is at 20/80 and Shadow Bullet puts 30
    # automatic damage in every turn, that body dies by itself and gives away a prize;
    # healing it (20 -> 50) makes it SURVIVE. The agent attached that same Grass by hand
    # (the manual attachment, with no healing) or vetoed the ability for "not overcharging",
    # losing 30 HP FOR FREE: the energy ends up on the same field, so
    # Syrup Storm (which scales with the TOTAL Grass) does exactly the same damage.
    #
    # The threshold is NOT the snipe (user, records/marnie games 1-3, LOST):
    # with `_rh_thr = _op_bench_snipe_dmg = 30` no body above 30 HP
    # ever entered the detector, and we used the healing ONCE in three games
    # while taking 410/620/60 damage from counters. The correct threshold
    # is `_ventana_de_regalo`: the projected hit + the Froslass drip + Munkidori's
    # aimable damage. Without those pieces on the field the window is the usual hit,
    # so the other matchups do not change.
    #
    # `_ripen_heal_serial` = the serial of the body to aim the Grass at. It is only
    # armed when the healing CHANGES the outcome (the body is INSIDE the
    # window and with +30 it LEAVES), never as cosmetic healing. It is computed AFTER
    # `energy_score` so its priorities can be consulted: if some charge
    # is worth >= 41000 there is a pending FINISHER/lethal pivot and the Grass is not diverted
    # to healing. Among several candidates the one worth MORE PRIZES wins (denying two is worth more
    # than denying one -- in game 2 the benched Ogerpon ex at 80 HP competed
    # with a Meganium at 90), then the one with the LEAST HP and, on a tie, the benched one
    # (the active also has the retreat).
    _ripen_heal_serial = None
    _ripen_heal_ex = False
    if (field_counts.get(Hydrapple_ex, 0) >= 1
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1
            and not neutralization_zone_active):
        _rh_cands = ([(True, _p) for _p in (my_state.active or []) if _p is not None]
                     + [(False, _p) for _p in (my_state.bench or []) if _p is not None])
        _rh_lethal_pending = any(
            energy_score(_p, _act) >= 41000 for _act, _p in _rh_cands)
        if not _rh_lethal_pending:
            _rh_og_cap = None
            if op_is_cubchoo_deck:
                _rh_og_cap = 2 if AGENT_STATE.meganium_in_play else 4
            elif op_is_alakazam_deck or op_is_hop_deck:
                _rh_og_cap = _ogerpon_base_phys_cap(
                    AGENT_STATE.meganium_in_play, op_is_hop_deck)
            _rh_best = None
            _rh_best_key = None
            for _rh_act, _rh_pk in _rh_cands:
                _rh_hp = _rh_pk.hp or 0
                _rh_max = _rh_pk.maxHp or 0
                if _rh_hp <= 0 or _rh_hp >= _rh_max:
                    continue  # no damage: the healing yields nothing
                if _ripen_energy_capped(_rh_pk, _rh_og_cap):
                    continue  # a hard energy cap: do not aim the Grass there
                # The projected hit: to the active, the opponent's best attack; to the bench,
                # the automatic snipe. The WINDOW adds the drip and the aimable
                # damage; healing SAVES if it is inside now and outside afterwards.
                _rh_golpe = (estimated_op_damage if _rh_act
                             else AGENT_STATE._op_bench_snipe_dmg)
                _rh_vent = _ventana_de_regalo(_rh_pk, _rh_act, _rh_golpe)
                _rh_gar = _ventana_de_regalo(_rh_pk, _rh_act, _rh_golpe,
                                             include_movable=False)
                if _rh_vent <= 0 or _rh_hp > _rh_vent:
                    continue  # outside the window: there is no prize to deny
                _rh_nuevo = min(_rh_max, _rh_hp + RIPENING_HEAL)
                if _rh_nuevo <= _rh_gar:
                    continue  # it dies anyway without the opponent spending anything
                # Two degrees of salvation, and the first rules: leaving the
                # COMPLETE window puts the body out of their reach this
                # turn; leaving only the GUARANTEED one forces them to spend the
                # Adrena-Brain, which only reaches one body. Without Froslass or
                # Munkidori both windows coincide and this is the usual
                # rule. After that, PRIZES (denying two is worth more than denying one),
                # less HP, and on a tie the benched one.
                _rh_key = (0 if _rh_nuevo > _rh_vent else 1,
                           -prize_count(_rh_pk), _rh_hp, 1 if _rh_act else 0)
                if _rh_best_key is None or _rh_key < _rh_best_key:
                    _rh_best_key = _rh_key
                    _rh_best = _rh_pk
            if _rh_best is not None:
                _ripen_heal_serial = getattr(_rh_best, 'serial', None)
                _ripen_heal_ex = prize_count(_rh_best) >= 2

    _sel_active_cant_attack = False
    _sel_active_pkmn = my_state.active[0] if my_state.active else None
    if _sel_active_pkmn is not None:
        # Single source of requirements: ATTACK_ENERGY_REQ.
        _sel_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(_sel_active_pkmn.id)
        if _sel_req is not None:
            _sel_mult = _grass_mult()
            _sel_eff_now = len(_sel_active_pkmn.energies) * _sel_mult
            _sel_can_now = (_sel_eff_now >= _sel_req)
            _sel_can_attach = False
            if (not _sel_can_now and not state.energyAttached
                    and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                _sel_eff_after = len(_sel_active_pkmn.energies) + _grass_attach_unit()
                _sel_can_attach = (_sel_eff_after >= _sel_req)
            _sel_active_cant_attack = not (_sel_can_now or _sel_can_attach)
        elif _sel_active_pkmn.id == Meowth_ex:
            _sel_active_cant_attack = True

    _sel_ctx_card = getattr(select, 'contextCard', None)

    # OUR FIRST turn of play (the same criterion as the Ultra
    # Ball block): the anti-donk line puts Meowth ex down even if the Supporter is already in
    # hand, so the "redundant copy" rules do not apply yet.
    _our_first_action_turn = (
        (state.turn == 1 and AGENT_STATE.we_go_first) or
        (state.turn == 2 and not AGENT_STATE.we_go_first))

    # Is there a Lillie's Determination among the cards THIS Last-Ditch Catch
    # prompt offers? The REAL offer is looked at (not the deck belief,
    # which counts prized or already seen copies): the first-turn rule can only
    # degrade the other Supporters if there really is a Lillie's to
    # choose. Outside the fetch prompt it stays False and affects nothing.
    _ld_lillie_ofrecida = False
    if select.effect is not None and select.effect.id == Meowth_ex:
        for _ld_opt in select.option:
            if _ld_opt.type != OptionType.CARD:
                continue
            _ld_card = get_card(obs, _ld_opt.area, _ld_opt.index,
                                _ld_opt.playerIndex)
            if _ld_card is not None and _ld_card.id == Lillie_Determination:
                _ld_lillie_ofrecida = True
                break

    # A REDUNDANT MEOWTH EX SEARCH (user, registro_010 step 118 vs
    # Alakazam, WON with a mistake): putting Meowth ex down is only worth its Last-Ditch
    # Catch, so BEFORE spending it we have to look at WHICH Supporter it would really
    # bring; if THAT SAME Supporter is already in hand, the search contributes
    # nothing and it also exposes a 2-prize body on the bench. The right play is to
    # cancel the Meowth and carry on the turn playing that Supporter.
    #
    # The prediction uses the SAME engine as the real fetch
    # (`_RULES_MEOWTH_FETCH`), not a list of cases: that is why it holds for
    # ANY deck and for any Supporter. The existing guards looked at
    # `_best_supp_in_hand_val`, which only weighs Boss's/Dawn/Lillie's/Lana's --
    # with a Xerosic's Machinations in hand it was worth 0 and the veto never fired,
    # which is exactly what happened here: Meowth ex was put down while already holding the Xerosic
    # the fetch ended up bringing (a useless 2nd copy).
    #
    # `hand_size - 1` because the fetch is resolved AFTER benching the Meowth.
    # THE ENERGY WE ARE MISSING IS ALREADY OURS, IT IS JUST IN THE DISCARD
    # (user, episode 90591443 step 84 vs Marnie's Grimmsnarl ex, LOST). On a turn
    # that cannot attack at all, the Last-Ditch Catch is asked which Supporter
    # gets us out of it, and the answer is not always the refill: when the discard
    # holds the Grass that completes our active's attack cost, LANA'S AID is what
    # turns the turn into a knockout. See the `recovery_creates_the_ko` rule of
    # `_RULES_MEOWTH_FETCH` for the record and the arithmetic.
    #
    # It is the SAME sum the winning route uses (`_recovery_creates_the_ko`, in
    # ptcg/turn/game_plan.py), with the two guards that route cannot lift moved
    # here where they belong: the card is in the DECK and not in hand -- if it
    # were in hand there would be no fetch to decide -- and the knockout does not
    # have to END the game, because this is a choice between two Supporters and
    # not a route that commits the whole turn.
    #
    # `_bench_attacker_ready` is the other half of "the turn cannot attack": an
    # active that cannot attack while a charged body waits on the bench is a
    # retreat away from attacking, and that turn does not need rescuing.
    _meowth_recovery_ko = (
        not state.supporterPlayed
        and (_active_cant_attack_this_turn or _sel_active_cant_attack)
        and not _bench_attacker_ready
        and hand_counts.get(Lanas_Aid, 0) == 0
        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
            Lanas_Aid, {}).get(ZONE_DECK, 0) > 0
        and _recovery_creates_the_ko(
            my_state, op_state, state, hand_counts, field_counts, total_grass,
            bench_count, AGENT_STATE.meganium_in_play,
            neutralization_zone_active, meowth_ability_lock))

    _meowth_fetch_id, _meowth_fetch_val = _meowth_fetch_prediction(
        hand_counts, _supp_values,
        max(0, (len(my_state.hand) if my_state.hand else 0) - 1),
        (field_counts.get(Hydrapple_ex, 0) >= 1
         or field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1),
        getattr(op_state, 'handCount', 0),
        (_active_cant_attack_this_turn or _sel_active_cant_attack),
        _win_via_boss_gust, _gust_2prize_via_boss, _deny_evo_via_boss,
        _meowth_devel_lillie, op_is_alakazam_deck,
        AGENT_STATE.ACTIVE_CARDS_IN_DECK, _our_first_action_turn,
        _boss_gust_immune_active, _meowth_recovery_ko)
    _meowth_fetch_redundante = (
        _meowth_fetch_id is not None
        and hand_counts.get(_meowth_fetch_id, 0) >= 1)

    # THE LAST-DITCH FETCH CONTRIBUTES NOTHING: the Supporter we want to play is already
    # in HAND and only ONE is played per turn. A BOARD predicate -- without
    # the select's context -- so that the decision to PUT the Meowth ex DOWN and the
    # decision to USE its ability cannot contradict each other. It used to live embedded in
    # `_meowth_skip_fetch` (the ACTIVATE context only) and that opened the hole of
    # log 88162677 step 16 vs Alakazam (LOST): the engine put the Meowth ex down
    # and immediately afterwards the ability's prompt REJECTED the fetch, so
    # a 2-prize body was given away on the bench for nothing.
    #
    # ...AND THE REDUNDANCY IS DECIDED BY THE PREDICTION, NOT BY THE SPECIES
    # (user, registro_004 step 59, episode 91839511, turn 4 vs Alakazam, WON in
    # spite of this). "A Lillie's Determination in hand" is a PROXY for "the
    # fetch would bring a copy of what I am already holding", and vs Alakazam
    # with a fat opposing hand the proxy is false: the Last-Ditch points at the
    # XEROSIC'S MACHINATIONS in the deck, which is a different card AND the one
    # that wins the turn's only Supporter slot. On that turn the proxy deadlocked
    # the whole board: the Ultra Ball had already been paid for by
    # `_alakazam_dig_xerosic_engine` (5950, `_ub_engine_pivot_turn` armed), its
    # fetch had spent two discards bringing the Meowth ex (1300,
    # `engine_pivot_turn`, `_ub_meowth_pending` armed) and then the PLAY was
    # vetoed here while the Lillie's was vetoed by
    # `alakazam_reserves_supporter_for_xerosic` -- both plays at -1, so the
    # sterile-turn rescue of `finalize.py` lifted the Lillie's to 1500 and
    # shuffled the just-bought Meowth ex straight back into the deck.
    #
    # `_meowth_fetch_redundante` is the GENERAL, deck-agnostic form of this very
    # veto: it replays `_RULES_MEOWTH_FETCH` over the Supporters left in the deck
    # and asks whether THAT card is already in hand. The special case is
    # subordinated to the general rule, not the other way round: that
    # keeps every board where the fetch really would bring a second Lillie's --
    # log 88162677 step 16 among them, where the first-turn rule ranks Lillie's
    # above Xerosic -- and only lifts the veto when the prediction names another
    # card. The two decisions still read the SAME predicate, so the invariant
    # `test_alakazam_step16_the_meowth_engine_and_the_ability_do_not_contradict`
    # holds by construction.
    _meowth_fetch_already_in_hand = (
        _meowth_devel_lillie
        and hand_counts.get(Lillie_Determination, 0) >= 1
        and not _win_via_boss_gust and not _gust_2prize_via_boss
        and _meowth_fetch_redundante
    )
    _meowth_skip_fetch = (
        context == SelectContext.ACTIVATE
        and _sel_ctx_card is not None and _sel_ctx_card.id == Meowth_ex
        and _meowth_fetch_already_in_hand
    )

    # When we are behind on prizes and the only Boss's Orders gust is
    # a low-value target (a 1-prize basic/pre-evolution, a high rank) that neither
    # wins the game nor takes 2 prizes, it is better to develop with Lillie's than to
    # burn the Boss's Orders for a lesser prize.
    _boss_low_value_gust = (
        _boss_prize_rank >= 7
        and not _win_via_boss_gust
        and not _gust_2prize_via_boss
        and not _boss_win_via_bench
        and not _boss_dodge_redirect
        and my_prize > op_prize
        and hand_counts.get(Lillie_Determination, 0) >= 1
    )

    # Priority between COPIES of the same threat (user, registro_007 step 80 vs
    # Archaludon, WON with a mistake): the opposing active is a THREAT pre-evolution
    # (a Duraludon with 3 energies + a Hero's Cape) and on the bench there are only copies of the
    # SAME species that are less developed (fewer energies and no life
    # tool). The user's rule: between two identical Pokemon the priority goes to the
    # one carrying a tool that gives it more HP and, in 2nd place, the one with more
    # energies -- that is, ATTACK the big active and do NOT burn the Boss's on
    # gusting the weak copy. The previous fix
    # (`_bo_active_prize_dominates`) required being able to KNOCK OUT the active
    # (`_bo_can_ko_active`) and the Hero's Cape (230 > Syrup 210) disabled it;
    # besides, the low-value/prize-rank branch of the scorer (1500/5200) still
    # beat the ATTACK (~1100). This flag cuts ALL the low/medium value branches
    # of the Boss's PLAY (the winning and 2-prize finishers return earlier and are not affected).
    _bo_act_threat_dom = False
    if (op_state.active and op_state.active[0] is not None
            and my_state.active and my_state.active[0] is not None
            and op_state.bench):
        _atd_act = op_state.active[0]
        if _atd_act.id in THREAT_PREEVO_IDS and can_attack:
            _atd_act_tool = len(getattr(_atd_act, 'tools', None) or []) > 0
            _atd_all_dominated = True
            _atd_any_copy = False
            for _atd_bp in op_state.bench:
                if _atd_bp is None:
                    continue
                if _atd_bp.id != _atd_act.id:
                    _atd_all_dominated = False
                    break
                _atd_any_copy = True
                _atd_bp_tool = len(getattr(_atd_bp, 'tools', None) or []) > 0
                # 1st priority: a life tool; 2nd: energies.
                if _atd_bp_tool and not _atd_act_tool:
                    _atd_all_dominated = False
                    break
                if (_atd_bp_tool == _atd_act_tool
                        and len(_atd_bp.energies) > len(_atd_act.energies)):
                    _atd_all_dominated = False
                    break
            _bo_act_threat_dom = _atd_all_dominated and _atd_any_copy

    # --- Anti-2-prize rule vs Mega Lucario (an active opposing Riolu) ---
    # If on our first turn (going second) the opponent has an active Riolu
    # with energy, next turn it will evolve into Mega Lucario ex and knock out
    # our Ogerpon ex (2 prizes). To avoid that, we retreat the Ogerpon ex and
    # promote a 1-prize basic as a sacrifice (priority Tapu Bulu >
    # Applin > Chikorita), handing over only 1 prize from a Pokemon that is not
    # needed.
    _lucario_sac_context = (
        state.turn == 2 and not AGENT_STATE.we_go_first
        and op_state.active and op_state.active[0] is not None
        and op_state.active[0].id == Riolu
        and len(op_state.active[0].energies) >= 1
        and field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
    )
    _lucario_sac_pivot = (
        _lucario_sac_context
        and my_state.active and my_state.active[0] is not None
        and my_state.active[0].id == Teal_Mask_Ogerpon_ex
    )
    _lucario_sac_available = (
        field_counts.get(Tapu_Bulu, 0) >= 1
        or field_counts.get(Applin, 0) >= 1
        or field_counts.get(Chikorita, 0) >= 1
        or (hand_counts.get(Tapu_Bulu, 0) >= 1 and bench_count < 5)
    )
    # Within the anti-Lucario scenario, Tapu Bulu is ONLY the priority
    # sacrifice/target when it really contributes:
    #   * an opponent with ex protection (Crustle / Cornerstone Ogerpon / Sylveon),
    #     where our ex do 0 damage, or
    #   * a charged Hydrapple ex engine + Meganium in play, which allows putting Tapu
    #     Bulu down and charging it instantly (with Meganium 2 energies count as 4 and
    #     it can attack immediately).
    # Otherwise we prefer to spend Applin > Chikorita and keep Tapu Bulu.
    _lucario_hydra_engine = False
    if AGENT_STATE.meganium_in_play and has_hydrapple:
        for _lhp in (my_state.active + my_state.bench):
            if (_lhp is not None and _lhp.id == Hydrapple_ex
                    and len(_lhp.energies) * _grass_mult() >= 2):
                _lucario_hydra_engine = True
                break
    _tapu_sac_priority = _lucario_sac_pivot and (
        AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck or op_is_sylveon_deck
        or op_has_ex_immune_active or op_has_ex_immune_bench
        or op_has_ability_immune_active or _lucario_hydra_engine)
    _lucario_other_sac_available = (
        field_counts.get(Applin, 0) >= 1 or field_counts.get(Chikorita, 0) >= 1
        or hand_counts.get(Applin, 0) >= 1 or hand_counts.get(Chikorita, 0) >= 1)

    # vs DRAGAPULT: Tapu Bulu is only put down with the board UNDEVELOPED
    # (user, registro_003 step 43, episode 88912610, LOST).
    #
    # There we had FIVE Pokemon in play (an active Meganium + a Dipplin + three
    # Teal Mask Ogerpon ex) and the agent put Tapu Bulu down, filling the bench. Tapu
    # Bulu is the deck's MANUAL attacker: its only role is to hit when the
    # opponent switches off our abilities or makes our ex useless. Dragapult does
    # neither -- Ogerpon ex and Hydrapple ex attack
    # normally -- so there Tapu Bulu is a filler body with no energy
    # and every extra body PAYS the opponent:
    #   * Phantom Dive spreads 6 counters across the bench; with a full bench
    #     the spread always finds somewhere to hurt (`op_bench_snipe_threat`
    #     is already switched on in this matchup), and
    #   * one more body is one more prize to give away, and it blocks the slot
    #     the lines that DO attack need (Applin/Dipplin/Hydrapple ex and
    #     Chikorita/Bayleef/Meganium).
    # The only case where it comes down is survival: with <=2 Pokemon in
    # play any body is worth more than the slot (a KO would leave us with no
    # bench -> [[nunca-terminar-turno-banca-vacia]]).
    #
    # EXCEPTION through MATCHUP COLLISION ([[tech-rival-no-activa-matchup-completo]],
    # [[colision-cubchoo-muro-inmune-pivote]]): if there is also a wall that cancels
    # abilities or makes our ex useless on the opposing board, Tapu Bulu becomes
    # the ONLY attacker again and the veto is lifted (it is decided by `_op_is_crustle_like`
    # in the PLAY branch, which is the one that knows that complete list).
    _op_is_dragapult_deck = op_has_dragapult or op_has_dreepy_line
    _tapu_in_play_total = (
        (1 if (my_state.active and my_state.active[0] is not None) else 0)
        + bench_count)
    _dragapult_no_tapu = (_op_is_dragapult_deck and _tapu_in_play_total > 2)

    # ITEM LOCK THREAT (Budew's Itchy Pollen). It is computed a single
    # time and consumed by both faces of the same decision: the sterile-turn
    # rescue net (finalisation) and the UB->Meowth->Lillie's chain via
    # `_ub_meowth_for_tomorrow`. See `_bloqueo_de_items_inminente`.
    _item_lock_incoming = _bloqueo_de_items_inminente(
        budew_on_op_field, op_has_dragapult, op_has_dreepy_line)

    # When valuing discards, always keep at least one Lillie's: the first
    # copy evaluated gets a protective score and only the spare copies are
    # freely discardable.
    _lillie_protected_once = False

    # The same latch for the counter-stadium: while an OPPOSING stadium is
    # switching off part of our engine, the first copy evaluated is the OUT and
    # is protected; the rest are spare copies. Gating that protection on
    # "only one copy in hand" switched it off precisely when we held two --
    # and the forced discard took both (see the DISCARD branch).
    _counter_stadium_kept_once = False

    # And the same latch one level up, for the CARD-AGNOSTIC Supporter block of
    # the forced discard (`DISCARD_SUPPORTER_LIVE_KEEP`). That block keeps the
    # Supporter the value layer prices highest, which is a claim on a JOB -- one
    # Supporter per turn -- and a job cannot be held twice. Without the latch
    # the block handed the same floor to every copy in hand and undid the
    # ladder's own latch sixty lines above it: `_lillie_protected_once` released
    # the spare at 72 and the `min()` pulled it straight back down to 2. This
    # set holds the ids the current DISCARD menu has already kept for that
    # reason; the copies after them keep whatever price the ladder gave.
    _supp_live_keep_once = set()

    # And the same latch for the POWERFUL HAND CAP of the Alakazam matchup
    # (`DISCARD_XEROSIC_CAP_IS_THE_ANSWER`). Being the last access to the cap is
    # a claim about the DECK -- no copy left in it -- so every copy in hand
    # answers it identically, and a floor below the best live Supporter said of
    # two cards sacrifices two Supporters to keep one answer. The first copy
    # evaluated is the answer; the rest keep the branch's ordinary price.
    _cap_kept_once = set()

    # And the same latch for the HAND RECYCLER of the mill matchup
    # (`DISCARD_CF_HAND_RECYCLER`). The Comfey ladder replaces the ordinary
    # scores, so `_lillie_protected_once` -- which the ladder above has already
    # set by the time that block runs -- cannot tell the first copy from the
    # spares there. This set holds the ids the current DISCARD menu has already
    # kept as the recycler; the copies after them fall as generic fodder,
    # because the first one shuffles them back into the deck anyway.
    _cf_refill_kept_once = set()

    # The same idea for the EVOLUTION pieces, but counting seats instead of
    # copies: the line-protection branches keep as many copies as the board can
    # actually wear (`_evo_copies_usable`) and the rest fall as fodder. This
    # dict tallies, per card id, how many copies the current DISCARD menu has
    # already protected.
    _evo_spare_seen = {}

    # The same latch again, for the copies OUR OWN searches bought this turn
    # (`DISCARD_WHAT_THE_SEARCH_ALREADY_BOUGHT`). Copies of one card are
    # interchangeable, so the purchase is not a SERIAL, it is a COUNT: the first
    # copies the menu offers keep their ordinary price -- there are that many
    # more of them in hand than the search brought -- and the rest are the
    # purchase. This dict tallies, per card id, how many spares the current
    # DISCARD menu has already let through.
    _bought_spare_seen = {}

    # ------------------------------------------------------------------
    # Promotion after a KO: ALWAYS choose the best benched attacker according to the
    # opposing ACTIVE Pokemon (not according to what cards it has in its deck). For each
    # candidate that can attack this turn its EFFECTIVE damage against
    # the opposing active is estimated, respecting:
    #   * The active's ex immunity (Crustle / Sylveon): our ex do 0.
    #   * The active's ability immunity (Cornerstone Ogerpon ex): our
    #     attackers that depend on an ability do 0.
    #   * The opposing active's weakness to our type (x2).
    # The one that does the most damage is marked to be promoted decisively:
    #   - A normal / Mega active (e.g. Mega Kangaskhan ex): the one that hits
    #     hardest comes up (with a charged bench it is usually Hydrapple ex).
    #   - An active Crustle: it discards our ex and brings up the best non-ex.
    #   - An active Cornerstone: it brings up an attacker that does not depend on an ability.
    _best_promote_card = None
    # The pre-evolution that `_evk_*` (further down) promotes BECAUSE the
    # evolution in hand knocks out. The scorer needs it by name: the doomed
    # penalty measures a hit this body never takes as it is.
    _promo_evo_koer = None
    _forced_ko_promote = (
        (context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE)
        and not (my_state.active and my_state.active[0] is not None)
        and not _lucario_sac_context)

    # --- FESTIVAL LEAD: the opponent attacks again AS SOON AS we promote --------
    # (user, log 88971843 step 117 vs Festival Lead, LOST.) With Festival
    # Grounds on the field -- whoever's, it is a SHARED stadium -- and a Dipplin as
    # their Active, Festival Lead lets them repeat the attack right after we
    # choose the replacement. That inverts the premise this WHOLE branch is written
    # on ("the promotion happens on the OPPONENT's turn, where nobody attacks
    # any more"): the body we bring up eats a WHOLE hit before we play,
    # so "it can attack this turn" is worth nothing if it does not reach our
    # turn alive. There an 80 HP Dipplin was brought up against a Do the Wave of 100 with
    # the opponent at 1 prize -- an immediate loss -- while a 140 HP Tapu Bulu that
    # endured waited behind it.
    #
    # `_ko_dentro_de_ventana` is required (our body fell INSIDE the opponent's
    # turn) because the second attack only exists if the first one knocked out: a
    # promotion after a self-KO on OUR turn (Wood Hammer) does not trigger it.
    #
    # And the wave has to be one they still OWE us. Festival Lead reads "may use
    # an attack it has TWICE": two is the ceiling of the turn, not a standing
    # threat. (user, registro_003 step 62, episode 92355371 vs *Festival Lead*,
    # LOST.) There their Dipplin threw both Do the Wave at the same Tapu Bulu --
    # 140 -> 40 -> knocked out -- and only THEN did we promote: nothing was
    # pending, and the flag fired anyway. It cost the turn twice over. It struck
    # off the bodies that do not survive a hit that was never coming (Applin 40,
    # Chikorita 70), and above all it switched off `_promo_evo_koer`, the branch
    # that would have brought up that same Applin: with the Dipplin in hand and
    # one Grass it evolves and its own Do the Wave, 20 x 4 benched = 80, buries
    # their 80 HP Dipplin. Instead a Teal Mask Ogerpon ex left the bench --
    # where its Tera prevents ALL damage -- to stand in front as a 2-prize body.
    #
    # The board at the promotion cannot tell the two cases apart: only the log
    # dates the waves (`_op_attack_waves_this_turn`, ATTACK entries of THIS turn
    # by that serial). The read is asked SECOND and only ever LOWERS the flag --
    # with no evidence in the log the count is 0 and the guard behaves exactly
    # as it did before.
    _op_prom_act_dbl = (op_state.active[0]
                        if op_state.active and op_state.active[0] is not None
                        else None)
    _op_dbl_waves_spent = (
        AGENT_STATE._op_attack_waves_this_turn.get(
            getattr(_op_prom_act_dbl, 'serial', None), 0)
        if _op_prom_act_dbl is not None else 0)
    op_double_attack_pending = (
        _forced_ko_promote
        and AGENT_STATE._festival_grounds_in_play
        and _ko_dentro_de_ventana
        and _op_prom_act_dbl is not None
        and _op_prom_act_dbl.id in FESTIVAL_LEAD_IDS
        and _op_dbl_waves_spent < FESTIVAL_LEAD_MAX_WAVES)

    if _forced_ko_promote:
        _op_prom_active = (op_state.active[0]
                           if op_state.active and op_state.active[0] is not None
                           else None)
        _op_prom_data = (card_table.get(_op_prom_active.id)
                         if _op_prom_active is not None else None)
        _op_prom_weak = getattr(_op_prom_data, 'weakness', None) if _op_prom_data else None
        _op_prom_en = len(_op_prom_active.energies) if _op_prom_active is not None else 0
        _op_prom_remain = (getattr(_op_prom_active, 'hp', 0)
                           if _op_prom_active is not None else 0)
        _prom_bench_after = max(0, bench_count - 1)
        _prom_can_attach = (
            hand_counts.get(Basic_Grass_Energy, 0) >= 1
            or (hand_counts.get(Night_Stretcher, 0) >= 1
                and discard_counts.get(Basic_Grass_Energy, 0) >= 1))
        _best_promote_dmg = -1
        _best_promote_key = None
        # Under Festival Lead the candidate has to SURVIVE the second hit
        # in order to get to attack. The doomed ones are only discarded if some
        # body that endures is left (the same criterion as `_promo_survivors`): if
        # nobody endures, the choice goes back to the usual one and it is governed by
        # the prize rules further down.
        _dbl_has_survivor = False
        if op_double_attack_pending:
            for _db in my_state.bench:
                if _db is None or not isinstance(_db, Pokemon):
                    continue
                _db_hit = _op_active_attack_damage_to(
                    _op_prom_active, _db, getattr(op_state, 'handCount', None))
                if _db_hit < (getattr(_db, 'hp', 0) or 0):
                    _dbl_has_survivor = True
                    break
        for _pb in my_state.bench:
            if _pb is None or not isinstance(_pb, Pokemon):
                continue
            if op_double_attack_pending and _dbl_has_survivor:
                _pb_hit_now = _op_active_attack_damage_to(
                    _op_prom_active, _pb, getattr(op_state, 'handCount', None))
                if _pb_hit_now >= (getattr(_pb, 'hp', 0) or 0):
                    continue  # it dies before it can attack: not a candidate
            _pb_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(_pb.id)
            if _pb_req is None:
                continue
            _pb_en_eff = len(_pb.energies)
            if _pb_en_eff < _pb_req and _prom_can_attach:
                _pb_en_eff += _grass_attach_unit()
            if _pb_en_eff < _pb_req:
                continue  # it cannot attack this turn
            if _pb.id == Hydrapple_ex:
                _pb_dmg = 30 + 30 * total_grass
            elif _pb.id == Teal_Mask_Ogerpon_ex:
                # Myriad counts the energy of BOTH actives: the promoted body
                # will attack the CURRENT opposing active, whose energy is known.
                _pb_dmg = 30 + 30 * (
                    len(_pb.energies)
                    + len(getattr(_active_of(op_state), 'energies', []) or []))
            elif _pb.id == Dipplin:
                _pb_dmg = 20 * _prom_bench_after
            elif _pb.id == Tapu_Bulu:
                _pb_dmg = 220
            elif _pb.id == Meganium:
                _pb_dmg = 140
            elif _pb.id == Fezandipiti_ex:
                _pb_dmg = 100
            else:
                _pb_dmg = 10
            # The opposing active's ex immunity (Crustle / Sylveon): ex -> 0.
            if op_has_ex_immune_active and _pb.id in OUR_EX_IDS:
                _pb_dmg = 0
            # Neutralization Zone (id 1247, user): when promoting after a KO we must
            # evaluate whether the zone is in play. Under the zone, our ex (with a rule
            # box) do NOT damage an opposing active WITHOUT a rule box (1 prize): their damage
            # is 0. That is why the ONLY useful attacker to promote is a NON-ex one (Meganium/
            # Tapu Bulu/Pinsir/Dipplin), unless the opposing active is an ex
            # (a rule box), against which our ex do damage. Without this, an ex that
            # does 0 was promoted and the turn was left with no attack.
            if (neutralization_zone_active and _pb.id in OUR_EX_IDS
                    and not (_op_prom_data
                             and (_op_prom_data.ex or _op_prom_data.megaEx))):
                _pb_dmg = 0
            # The opposing active's ability immunity (Cornerstone): the
            # attackers that depend on an ability are blocked -> 0.
            if op_has_ability_immune_active and _pb.id in OUR_ABILITY_IDS:
                _pb_dmg = 0
            # The opposing active's weakness to our type -> x2.
            _pb_data = card_table.get(_pb.id)
            if (_pb_data is not None and _op_prom_weak is not None
                    and getattr(_pb_data, 'energyType', None) == _op_prom_weak):
                _pb_dmg *= 2
            if _pb_dmg <= 0:
                continue  # immune / no useful attack: it cannot defeat the opponent
            # Rule: ALWAYS bring up the one with the MOST HP that can defeat the opponent.
            # Lexicographic priority: (can knock out, prize prudence,
            # remaining HP, damage). GENERAL PRUDENCE (July 2026 audit,
            # suggestion 6 -- it generalises the per-matchup pattern of Alakazam/
            # Tapu): if the PROJECTED opposing hit knocks the candidate out, a
            # 1-prize body that also knocks out is a better trade than
            # an equally doomed 2-prize ex. With unreadable opposing damage
            # (a projection of 0, e.g. counter attacks that are not modelled) everybody
            # "survives" and the key stays EXACTLY as before
            # (conservative: it only changes behaviour with evidence).
            _pb_can_ko = 1 if (_op_prom_remain > 0 and _pb_dmg >= _op_prom_remain) else 0
            _pb_hp = getattr(_pb, 'hp', 0) or 0
            # The prudence ONLY discriminates between candidates that KNOCK OUT
            # (the user's rule: "any non-ex that knocks out EQUALLY"); if nobody
            # knocks out, the key stays as before (the biggest tank/strongest).
            _pb_pref = 1
            if _pb_can_ko:
                _pb_op_hit = _op_active_attack_damage_to(
                    _active_of(op_state), _pb,
                    getattr(op_state, 'handCount', None))
                _pb_pref = 1 if (_pb_op_hit < _pb_hp
                                 or prize_count(_pb) == 1) else 0
            _pb_key = (_pb_can_ko, _pb_pref, _pb_hp, _pb_dmg)
            if _best_promote_key is None or _pb_key > _best_promote_key:
                _best_promote_key = _pb_key
                _best_promote_dmg = _pb_dmg
                _best_promote_card = _pb
        if _best_promote_card is None or _best_promote_dmg <= 0:
            _best_promote_card = None

        # A RECHARGEABLE tank over a DOOMED ex attacker (user, registro_009
        # step 130 vs Archaludon, WON): when promoting after a KO, if the best
        # candidate is an ex that does NOT knock out and the projected opposing hit KILLS it
        # (Ogerpon 210 vs Ion Beam 220 -> it gives away 2 prizes), and on the bench there is
        # a Hydrapple ex that SURVIVES the hit (330) and is RECHARGEABLE next
        # turn (the manual attachment + Ripening Charge = 2 attachments; energies
        # accessible in hand or recoverable from the discard with Lana's Aid),
        # promote the tank. The "can attack this turn" filter excluded the
        # Hydrapple with no energies even though this promotion happens on the OPPONENT's
        # turn, where nobody attacks any more; with Lana's + 3 Grass in the discard
        # the Hydrapple is at 2 effective and attacks next turn (Syrup
        # Storm), while the promoted Ogerpon only dies. The overrides
        # BELOW (a Tapu that knocks out / a 1-prize body vs Alakazam) still win
        # because they are applied afterwards and require a real KO.
        if (_best_promote_card is not None
                and _best_promote_key is not None
                and _best_promote_key[0] == 0
                and prize_count(_best_promote_card) >= 2
                and _op_prom_remain > 0):
            _rt_op_act = _active_of(op_state)
            _rt_hit = _op_active_attack_damage_to(
                _rt_op_act, _best_promote_card,
                getattr(op_state, 'handCount', None))
            if (_rt_hit > 0
                    and _rt_hit >= (getattr(_best_promote_card, 'hp', 0) or 0)):
                _rt_unit = _grass_attach_unit()
                _rt_grass_discard = sum(
                    1 for _rc in (my_state.discard or [])
                    if getattr(_rc, 'id', 0) == Basic_Grass_Energy)
                _rt_avail = hand_counts.get(Basic_Grass_Energy, 0)
                if hand_counts.get(Lanas_Aid, 0) >= 1:
                    _rt_avail += min(3, _rt_grass_discard)
                for _rt_pb in my_state.bench:
                    if (_rt_pb is None or not isinstance(_rt_pb, Pokemon)
                            or _rt_pb.id != Hydrapple_ex):
                        continue
                    _rt_hp = getattr(_rt_pb, 'hp', 0) or 0
                    if _rt_hit >= _rt_hp:
                        continue  # it does not survive either: it is no tank
                    _rt_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(Hydrapple_ex, 2)
                    _rt_deficit = _rt_req - len(_rt_pb.energies)
                    if _rt_deficit <= 0:
                        continue  # it would attack already: the normal loop evaluated it
                    # physical cards needed, a maximum of 2 attachments next turn
                    _rt_need = -(-_rt_deficit // max(1, _rt_unit))
                    if _rt_need > 2 or _rt_avail < _rt_need:
                        continue
                    _best_promote_card = _rt_pb
                    break

        # Rule (user, registro 007 step 90 vs Alakazam, WON): when promoting after
        # a KO, if on the bench there is a Tapu Bulu that can ATTACK this turn (>=4
        # effective energy, or it is short and we have it in hand / recoverable with Night
        # Stretcher) and with its 220 attack it KNOCKS OUT the opposing active, bring it up ALWAYS
        # -- even if a benched ex (Ogerpon/Hydrapple ex) has more HP or hits somewhat
        # harder. Tapu Bulu is non-ex (only 1 prize if it is knocked out) and it finishes
        # just like a 2-prize ex: exposing the cheap body is the right thing to do.
        # It complements [[tapu-bulu-activo-que-noquea-ataca-no-retira]] (which decides not to
        # retreat a Tapu Bulu that knocks out); this one decides WHO to promote.
        if _op_prom_remain > 0:
            _tapu_prom = None
            for _tb in my_state.bench:
                if _tb is None or not isinstance(_tb, Pokemon) or _tb.id != Tapu_Bulu:
                    continue
                _tb_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(Tapu_Bulu, 4)
                _tb_eff = len(_tb.energies)
                if _tb_eff < _tb_req and _prom_can_attach:
                    _tb_eff += _grass_attach_unit()
                if _tb_eff < _tb_req:
                    continue
                _tb_dmg = 220
                _tb_data = card_table.get(Tapu_Bulu)
                if (_tb_data is not None and _op_prom_weak is not None
                        and getattr(_tb_data, 'energyType', None) == _op_prom_weak):
                    _tb_dmg *= 2
                if _tb_dmg >= _op_prom_remain:
                    _tapu_prom = _tb
                    break
            if _tapu_prom is not None:
                _best_promote_card = _tapu_prom

        # Rule (user, registro_010 step 127, vs Alakazam, LOST): when PROMOTING
        # (a voluntary retreat or a KO) against an Alakazam deck, ALWAYS prefer a
        # ONE-prize body (Meganium or Tapu Bulu) that KNOCKS OUT the opposing active
        # over a 2-prize ex, even if the ex has MORE HP. It extends the
        # universal Tapu Bulu rule (above) to include Meganium in this matchup:
        # if the attacker is knocked out we only concede 1 prize instead of 2. Among
        # several 1-prize candidates the one with the MOST HP comes up.
        if op_is_alakazam_deck and _op_prom_remain > 0:
            _ak_1prize_prom = None
            _ak_1prize_hp = -1
            for _mb in my_state.bench:
                if _mb is None or not isinstance(_mb, Pokemon):
                    continue
                # Dipplin and Pinsir included (user, registro_005 step 56 vs
                # Alakazam): any 1-prize body with a modelled attack
                # that knocks out will do; consistent with the generalised detection
                # of `_alakazam_pivot_1prize`.
                if _mb.id not in (Meganium, Tapu_Bulu, Dipplin, Pinsir):
                    continue
                _mb_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(_mb.id)
                if _mb_req is None:
                    continue
                _mb_eff = len(_mb.energies)
                if _mb_eff < _mb_req and _prom_can_attach:
                    _mb_eff += _grass_attach_unit()
                if _mb_eff < _mb_req:
                    continue
                if _mb.id == Tapu_Bulu:
                    _mb_dmg = 220
                elif _mb.id == Meganium:
                    _mb_dmg = 140
                elif _mb.id == Pinsir:
                    _mb_dmg = 100
                else:
                    # Dipplin's Do the Wave = 20 x our bench; when it is promoted
                    # it leaves the bench (conservative: bench_count - 1).
                    _mb_dmg = 20 * max(0, bench_count - 1)
                _mb_data = card_table.get(_mb.id)
                if (_mb_data is not None and _op_prom_weak is not None
                        and getattr(_mb_data, 'energyType', None) == _op_prom_weak):
                    _mb_dmg *= 2
                if _mb_dmg < _op_prom_remain:
                    continue
                _mb_hp = getattr(_mb, 'hp', 0) or 0
                if _mb_hp > _ak_1prize_hp:
                    _ak_1prize_hp = _mb_hp
                    _ak_1prize_prom = _mb
            if _ak_1prize_prom is not None:
                _best_promote_card = _ak_1prize_prom

        # A tank via EVOLUTION over a DOOMED attacker (user, registro_013 step
        # 99 vs Mega Lucario ex, LOST): when promoting after a KO, if NOBODY on the
        # bench KNOCKS OUT the opposing active (`_best_promote_key[0] == 0`) and the normal
        # candidate is a 2+ prize ex that DIES to the projected hit (an Ogerpon ex
        # 210 vs the Mega Lucario's 270 -> it gives away 2 prizes), but a benched
        # PRE-EVOLUTION (Dipplin) can EVOLVE next turn into a body that
        # SURVIVES (Hydrapple ex 330 > 270), promote that pre-evolution: it concedes 0 prizes
        # and takes the hit to stay in play. It generalises the "rechargeable
        # tank" above (which requires the tank ALREADY on the bench) to the
        # EVOLUTION route (the evolution is in HAND). The 1-prize attacker that
        # KNOCKS OUT (Tapu/Meganium, the branches above) keeps priority: this only
        # acts when no KO is possible. The user's priority is: (1) a 1-prize body
        # that knocks out; (2) the one that best ENDURES a future hit -- here --; (3) sacrificing
        # the least needed 1-prize body (the basic-prefer branches below). Deck-agnostic.
        # It fires when there is NO attacker that knocks out the opposing active: either the best
        # candidate is a doomed 2+ prize ex (`_best_promote_key[0]==0`),
        # or there is simply no body that can attack this turn
        # (`_best_promote_card is None`, e.g. with no energy to attach). In both
        # cases the user's priority (2) -- "the one that best ENDURES a future
        # hit" -- rules: if NO benched body survives the projected hit
        # as it is, but a PRE-EVOLUTION can EVOLVE next turn into a body
        # that SURVIVES, promote that pre-evolution.
        _ev_no_koer = (_best_promote_card is None
                       or (_best_promote_key is not None
                           and _best_promote_key[0] == 0
                           and prize_count(_best_promote_card) >= 2))
        if _forced_ko_promote and _ev_no_koer and _op_prom_remain > 0:
            _ev_op_act = _active_of(op_state)
            _ev_hand = getattr(op_state, 'handCount', None)
            # Does any body survive AS IT IS (without evolving) the projected
            # hit? If so, we do not force the evolution route (the normal logic
            # decides; we avoid collateral effects). We only act when NOTHING endures.
            _ev_survivor_asis = False
            for _sb in my_state.bench:
                if _sb is None or not isinstance(_sb, Pokemon):
                    continue
                _sb_hit = _op_active_attack_damage_to(_ev_op_act, _sb, _ev_hand)
                if _sb_hit > 0 and _sb_hit < (getattr(_sb, 'hp', 0) or 0):
                    _ev_survivor_asis = True
                    break
            if not _ev_survivor_asis:
                _ev_best = None
                _ev_best_hp = -1
                for _ev_pb in my_state.bench:
                    if _ev_pb is None or not isinstance(_ev_pb, Pokemon):
                        continue
                    if getattr(_ev_pb, 'appearThisTurn', False):
                        continue  # it just came down: it does not evolve next turn
                    _ev_pb_data = card_table.get(_ev_pb.id)
                    _ev_pb_name = getattr(_ev_pb_data, 'name', None)
                    if _ev_pb_name is None:
                        continue
                    # A DIRECT evolution in hand whose pre-evolution is this body.
                    _ev_to_id = None
                    for _hid, _hn in hand_counts.items():
                        if _hn <= 0:
                            continue
                        _hd = card_table.get(_hid)
                        if (_hd is not None
                                and getattr(_hd, 'evolvesFrom', None) == _ev_pb_name):
                            _ev_to_id = _hid
                            break
                    if _ev_to_id is None:
                        continue
                    _ev_to_data = card_table.get(_ev_to_id)
                    # CardData exposes the base HP as `.hp` (not `.maxHp`); the
                    # Pokemon on the BOARD do have `.maxHp`/`.hp` (current).
                    _ev_max = getattr(_ev_to_data, 'hp', 0) or 0
                    # The damage already taken by the pre-evolution is kept when evolving.
                    _ev_dmg_taken = ((getattr(_ev_pb, 'maxHp', 0) or 0)
                                     - (getattr(_ev_pb, 'hp', 0) or 0))
                    _ev_survive_hp = _ev_max - max(0, _ev_dmg_taken)
                    _ev_op_hit = _op_active_attack_damage_to(
                        _ev_op_act, _ProjTarget(_ev_to_id), _ev_hand)
                    if _ev_op_hit <= 0 or _ev_op_hit >= _ev_survive_hp:
                        continue  # the evolution does not survive either
                    if _ev_survive_hp > _ev_best_hp:
                        _ev_best_hp = _ev_survive_hp
                        _ev_best = _ev_pb
                if _ev_best is not None:
                    _best_promote_card = _ev_best

        # --- AN EVOLUTION IN HAND THAT KNOCKS OUT -----------------------------
        # (user, registro_009 step 120 vs Mega Lopunny ex, WON in spite of this.)
        # The candidate loop above reads every benched body as THE CARD IT IS
        # NOW: the hand only enters it as energy (`_prom_can_attach`). So a
        # pre-evolution is scored with its own little attack and loses on HP to
        # any ex, even when the hand holds the evolution that turns it into the
        # finisher. There: bench = 2 Teal Mask Ogerpon ex (210 HP, 6 energy),
        # Meowth ex, Meganium and a Dipplin; hand = Hydrapple ex + 2 Grass +
        # Night Stretcher; opposing active = Mega Lopunny ex at 330/330 and we
        # were at 2 prizes. The Ogerpon came up and hit for 240 -- no knockout.
        # The Dipplin evolves into Hydrapple ex and Syrup Storm (30 + 30 per
        # Grass on our field, 12 of them) does 390: it knocks out a THREE-prize
        # Mega ex and closes the game on the spot.
        #
        # The rechargeable-tank and the evolution-survivor overrides above cover
        # priority (2) of the user's order ("the body that best ENDURES"); this
        # one covers priority (1) ("a body that KNOCKS OUT"), which is why it is
        # applied last and wins over them. It only acts when NOBODY on the bench
        # knocks out as it is (`_best_promote_key[0] == 0`): a knockout already
        # available is a bird in the hand and does not spend the evolution.
        #
        # It shares the premise the whole branch is written on -- the promotion
        # resolves on the OPPONENT's turn, so our turn (evolve, attach, attack)
        # comes before their next attack. The one modelled exception, Festival
        # Lead attacking again as soon as we promote, switches it off.
        _evk_no_koer = (_best_promote_card is None
                        or (_best_promote_key is not None
                            and _best_promote_key[0] == 0))
        if (_evk_no_koer and _op_prom_remain > 0
                and not op_double_attack_pending):
            _evk_op_act = _active_of(op_state)
            # PHYSICAL Grass we can still put on the field next turn (the same
            # sources `_prom_can_attach` accepts, counted instead of tested).
            _evk_grass = hand_counts.get(Basic_Grass_Energy, 0)
            if (_evk_grass == 0
                    and hand_counts.get(Night_Stretcher, 0) >= 1
                    and discard_counts.get(Basic_Grass_Energy, 0) >= 1):
                _evk_grass = 1
            _evk_unit = _grass_attach_unit()
            _evk_best = None
            _evk_best_key = None
            for _evk_pb in my_state.bench:
                if _evk_pb is None or not isinstance(_evk_pb, Pokemon):
                    continue
                if getattr(_evk_pb, 'appearThisTurn', False):
                    continue  # it just came down: it does not evolve next turn
                _evk_pre_data = card_table.get(_evk_pb.id)
                _evk_pre_name = getattr(_evk_pre_data, 'name', None)
                if _evk_pre_name is None:
                    continue
                # A DIRECT evolution in hand whose pre-evolution is this body.
                _evk_to_id = None
                for _hid, _hn in hand_counts.items():
                    if _hn <= 0:
                        continue
                    _hd = card_table.get(_hid)
                    if (_hd is not None
                            and getattr(_hd, 'evolvesFrom', None) == _evk_pre_name):
                        _evk_to_id = _hid
                        break
                if _evk_to_id is None:
                    continue
                _evk_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(_evk_to_id)
                if _evk_req is None:
                    continue  # not an attacker we can price: we invent nothing
                # Energy the evolution reaches: what the pre-evolution already
                # carries (evolving keeps it) plus what we can attach next turn.
                # Attachment slots: the manual one, plus a Ripening Charge for
                # each bearer that will be in play (it charges ANY of our
                # Pokemon); Teal Dance only charges its own body, so it counts
                # only when the promoted body IS that Ogerpon.
                _evk_slots = 1
                if not meowth_ability_lock:
                    _evk_slots += field_counts.get(Hydrapple_ex, 0)
                    if _evk_to_id in (Hydrapple_ex, Teal_Mask_Ogerpon_ex):
                        _evk_slots += 1
                _evk_eff = (len(_evk_pb.energies)
                            + min(_evk_grass, _evk_slots) * _evk_unit)
                if _evk_eff < _evk_req:
                    continue  # we cannot pay for its attack
                # Damage through the single source. `total_grass` is NOT topped
                # up with the energy we are about to attach: falling short here
                # only refuses knockouts, it never invents one.
                _evk_dmg = _our_effective_damage(
                    _ProjTarget(_evk_to_id), _evk_op_act,
                    _attacker_base_damage(_evk_to_id, _evk_op_act, _evk_eff,
                                          grass_scale=total_grass,
                                          teal_self_energy=_evk_eff,
                                          bench_count=_prom_bench_after),
                    meganium_active=AGENT_STATE.meganium_in_play,
                    neutralization_zone=neutralization_zone_active)
                if _evk_dmg < _op_prom_remain:
                    continue  # it does not knock out: this branch says nothing
                _evk_to_data = card_table.get(_evk_to_id)
                _evk_prizes = (3 if getattr(_evk_to_data, 'megaEx', False)
                               else 2 if getattr(_evk_to_data, 'ex', False)
                               else 1)
                _evk_key = (-_evk_prizes, getattr(_evk_to_data, 'hp', 0) or 0,
                            _evk_dmg)
                if _evk_best_key is None or _evk_key > _evk_best_key:
                    _evk_best_key = _evk_key
                    _evk_best = _evk_pb
            if _evk_best is not None:
                _best_promote_card = _evk_best
                _promo_evo_koer = _evk_best

    # --- OUR OWN MATCH POINT AT THE PROMOTION (user, registro_013 step 116 vs
    # Mega Lucario, LOST -- episode 91191469, deck-agnostic) ------------------
    #
    # Their Mega Lucario ex stood at 40 of its 340 and we needed ONE prize.
    # Knocking that body out next turn does not "trade well": it ENDS THE GAME.
    # On our bench the Meganium carried one physical Grass -- two effective
    # under Wild Growth -- so a single attachment reached Solar Beam's four and
    # its 140 buries a 40 HP active. Every other candidate sat at zero energy,
    # two attachments away from anything. The agent promoted a Meowth ex,
    # spent the turn playing bodies, never attacked, and handed the game over
    # on the reply.
    #
    # Every rule that chose that Meowth ex is an argument about SURVIVING TO A
    # LATER TURN: hand over one prize instead of two, put up a cheap wall, keep
    # the engine safe on the bench. At our own match point there is no later
    # turn to buy -- our knockout resolves first, on our turn, and closes the
    # game before their reply exists. So the only question that survives is the
    # one the user states: WHICH BODY IS CLOSEST TO LANDING THAT KNOCKOUT,
    # measured in attachments still owed (energy required vs energy carried).
    #
    # This flag is what lets the deck-agnostic "almost-ready finisher" selector
    # (`_promote_setup_ko_attacker`, below) speak over the wall rules on those
    # boards. It is written from the prize piles and the opposing active's own
    # price, so it holds for any deck: `my_prize <= prize_count_op(active)`
    # means their body IS the rest of our pile.
    _promo_op_act_now = (op_state.active[0]
                         if op_state.active and op_state.active[0] is not None
                         else None)
    _promo_ko_wins_the_game = (
        _forced_ko_promote
        and _promo_op_act_now is not None
        and (getattr(_promo_op_act_now, 'hp', 0) or 0) > 0
        and my_prize <= prize_count_op(_promo_op_act_now))

    # Rule (user) vs Mega Lucario: when the opponent KNOCKS OUT one of our Pokemon and on
    # the bench there is NO attacker able to attack this turn
    # (`_best_promote_card is None`), we ALWAYS prefer to promote a
    # BASIC Pokemon first (Applin is the priority among the basics), or Dipplin if we
    # have no basic. That way we hand over a cheap body (1 prize) instead of
    # an ex (2 prizes) that cannot counterattack anyway. If there is neither a basic nor
    # a Dipplin on the bench, the current promotion logic is kept.
    _lucario_ko_prefer_basic = (
        _forced_ko_promote
        and op_is_lucario_deck
        and _best_promote_card is None)

    # A deck-agnostic generalisation of the previous rule (user, registro_004
    # step 37): when PROMOTING (after a retreat or a KO) with NO ready benched attacker
    # (`_best_promote_card is None`), if the opposing active's attack KNOCKS OUT even
    # the biggest tank we would promote, whatever body we put in front
    # falls -> expose a 1-prize BASIC (not a 2-prize ex). It is the promotion side
    # of the `_doomed_ex_sac_pivot` pivot: it is detected with the REAL opposing finisher, not with
    # a list of matchups, so it applies to any deck (Mega Lucario included).
    # It excludes ex/ability-immune walls (there the promotion brings up its own wall).
    #
    # THE CHEAP BODY HAS TO BE CHEAPER THAN THEIR PILE (user, registro_011 step
    # 130 vs Alakazam, LOST -- episode 91532527, deck-agnostic). The whole rule
    # is one sentence -- "hand over a cheap body (1 prize) instead of an ex (2
    # prizes)" -- and that sentence is only worth something while the cheap body
    # buys us a turn. With their pile at ONE it buys nothing: the 1-prize basic
    # closes their count exactly as fast as the ex, so the discount it is priced
    # on does not exist. It is the same correction the other two members of this
    # family already carry (the +3000 prize denial and `_alakazam_pivot_1prize`,
    # registro_014 step 130): `prize_count(body) < op_prize`.
    #
    # There, on a bench of five bodies with no energy anywhere, the rule handed
    # 8500 + hp/10 to a 140 HP Tapu Bulu against a Powerful Hand of 20 x (15+2);
    # the 330 HP Hydrapple ex it beat is the only body that their real blow --
    # every card they play takes 20 off it -- can fall short of. See
    # `_mp_last_stand` below, which is the criterion that replaces this one when
    # their pile makes every price the same price.
    _ko_prefer_basic_general = False
    if (_forced_ko_promote and _best_promote_card is None
            and not _lucario_ko_prefer_basic
            and my_prize >= 3
            and not op_has_ex_immune_active
            and not op_has_ability_immune_active
            and op_state.active and op_state.active[0] is not None):
        _kpb_opa = op_state.active[0]
        _kpb_has_basic = False
        _kpb_tank = None
        _kpb_tank_hp = -1
        for _kbp in my_state.bench:
            if _kbp is None or not isinstance(_kbp, Pokemon):
                continue
            _kbp_d = card_table.get(_kbp.id)
            if (_kbp_d is not None
                    and not getattr(_kbp_d, 'stage1', False)
                    and not getattr(_kbp_d, 'stage2', False)
                    and _kbp.id not in OUR_EX_IDS
                    and prize_count(_kbp) < op_prize):
                _kpb_has_basic = True
            if (_kbp.hp or 0) > _kpb_tank_hp:
                _kpb_tank_hp = _kbp.hp or 0
                _kpb_tank = _kbp
        if _kpb_has_basic and _kpb_tank is not None:
            _kpb_hit = _op_active_attack_damage_to(
                _kpb_opa, _kpb_tank, getattr(op_state, 'handCount', None))
            if _kpb_hit >= (_kpb_tank.hp or 0):
                _ko_prefer_basic_general = True
    # ------------------------------------------------------------------

    # Promote the best FUTURE attacker after a KO (user, registro_009 step 111 vs
    # Alakazam, LOST): when NO body can attack THIS turn
    # (`_best_promote_card is None`) but a benched attacker is ONE single
    # energy away from its requirement and, once completed, KNOCKS OUT the opposing active, and we also
    # have a way to refill/search for that energy (Lillie's/Dawn in hand + Grass
    # in the deck or in hand), promote THAT attacker instead of a cheap basic
    # wall. The promotion happens on the OPPONENT's turn; next turn we attach
    # 1 Grass (x2 with Meganium in play) and attack. Example: an Ogerpon ex at 2/3
    # effective -> with 1 attachment it reaches Myriad ({G}{G}{G}) and finishes (30+30*(4+
    # the opposing active's energy)); a Tapu Bulu (0/4) would take several turns and does not
    # counterattack. It does not apply in a pure sacrifice (the opponent one-shots even the
    # tank -> `_ko_prefer_basic_general`), vs Lucario, or with ex/ability
    # immunities or a Neutralization Zone. Deck-agnostic.
    # Note: this FUTURE finisher OVERRIDES `_ko_prefer_basic_general` (sacrificing
    # a basic because the opponent one-shots the tank): if the promoted ex KNOCKS OUT
    # the opposing active NEXT turn -- which is OUR turn, we attack first --,
    # the opponent does not even get to hit it, so the premise of the sacrifice does not apply.
    #
    # ... AND IT OVERRIDES THE LUCARIO WALL AT OUR MATCH POINT (user,
    # registro_013 step 116, LOST). The `vs Lucario` exclusion above is the one
    # per-matchup clause in this rule, and it is written on the same premise as
    # the sacrifice it defers to: the promoted body is a wall we hand over so
    # that a LATER turn exists. `_promo_ko_wins_the_game` is exactly the board
    # where that premise is false -- the knockout this selector is looking for
    # takes the last prize we need -- so there the general rule goes first
    # ([[la-regla-general-va-antes-que-su-caso-especial]]). It only LIFTS the
    # veto; if no candidate is one attachment from a lethal hit, this stays
    # None and the basic wall keeps the slot exactly as before.
    _promote_setup_ko_attacker = None
    if (_forced_ko_promote and _best_promote_card is None
            and (not _lucario_ko_prefer_basic or _promo_ko_wins_the_game)
            and not op_has_ex_immune_active
            and not op_has_ability_immune_active
            and not neutralization_zone_active
            and op_state.active and op_state.active[0] is not None):
        _ps_opa = op_state.active[0]
        _ps_opa_data = card_table.get(_ps_opa.id)
        _ps_weak = getattr(_ps_opa_data, 'weakness', None) if _ps_opa_data else None
        _ps_opa_en = len(_ps_opa.energies or [])
        _ps_remain = getattr(_ps_opa, 'hp', 0) or 0
        _ps_unit = _grass_attach_unit()
        # HIDDEN Grass (in the deck or prizes) = the deck's total - the VISIBLE Grass
        # (hand + discard + attached to our Pokemon). It is computed from the
        # observation so as NOT to depend on the per-zone counter
        # `ACTIVE_CARDS_IN_DECK[MAZO]`, which goes out of sync in records that do not
        # start on turn 1 (this one starts on turn 9). The deck total
        # (the sum of all zones) IS reliable (it is preserved).
        _ps_grass_total = sum(
            AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Basic_Grass_Energy, {}).values())
        _ps_grass_visible = (
            hand_counts.get(Basic_Grass_Energy, 0)
            + discard_counts.get(Basic_Grass_Energy, 0))
        for _pp in ([_active_of(my_state)] + list(my_state.bench or [])):
            if _pp is not None:
                _ps_grass_visible += sum(
                    1 for _e in (getattr(_pp, 'energyCards', None) or [])
                    if getattr(_e, 'id', 0) == Basic_Grass_Energy)
        _ps_grass_hidden = _ps_grass_total - _ps_grass_visible
        # How to get the missing energy next turn. The original version
        # only accepted a draw Supporter ALREADY in hand
        # (Lillie's/Dawn) + accessible Grass; with that, a hand that only has
        # the ENGINE that gets that Supporter was left out and a useless
        # wall was promoted (user, registro_007 step 126 vs Marnie's Grimmsnarl ex,
        # LOST: hand = Meowth ex + Meganium, bench = 2 Ogerpon ex at 2/3
        # energies -- which with 1 attachment finish through the Grass weakness -- and a Tapu
        # Bulu at 1/4; the Tapu Bulu was brought up, which can neither attack nor retreat
        # -- cost 3 -- and gave the turn away). Now ALL the real routes are enumerated,
        # deck-agnostically:
        #   a) a draw Supporter in hand (Lillie's/Dawn) + accessible Grass
        #      (in hand or still hidden in the deck/prizes).
        #   b) recovery from the DISCARD with a Lana's Aid in hand (Night Stretcher
        #      is already covered by `_prom_can_attach`, which attacks the SAME turn).
        #   c) the Meowth ex engine: benching it triggers Last-Ditch Catch and
        #      brings from the deck the missing Supporter -- Lana's Aid (which picks Grass
        #      out of the discard) or Lillie's/Dawn (which rebuild the hand). It
        #      requires a bench slot after the promotion and the ability alive (no Watchtower /
        #      Iron Thorns).
        #   d) the Fezandipiti ex -> Flip the Script engine: it draws 3. It is the route that
        #      was missing and the ONLY one whose trigger is guaranteed in this branch
        #      -- we are promoting BECAUSE we have just been knocked out, which is
        #      exactly what switches Flip the Script on -- (user, registro_008
        #      step 122 vs Dragapult, LOST: a hand with a Fezandipiti ex + an Ultra
        #      Ball, three Ogerpon ex at 2/3 effective that with ONE attachment finish
        #      the Dragapult ex at 50 HP... and the Tapu Bulu at 0/4 with a
        #      retreat cost of 3 was brought up, which neither attacks nor can switch out). Watchtower does NOT
        #      switch it off: it only cancels the abilities of {C} Pokemon and Fezandipiti ex is
        #      {D}; what does kill it is Iron Thorns (which cancels EVERY ability with a
        #      Rule Box). It holds both with the Fezandipiti ALREADY in play and with one
        #      in hand and a bench slot after the promotion.
        # The "hidden" copies (deck or prizes) are measured as the deck total
        # minus the VISIBLE ones (hand + discard), the same observational criterion as
        # `_ps_grass_hidden` so as not to depend on the per-zone counter.
        def _ps_hidden_copies(_cid):
            _tot = sum(AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(_cid, {}).values())
            return _tot - (hand_counts.get(_cid, 0)
                           + discard_counts.get(_cid, 0))

        _ps_grass_reachable = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                               or _ps_grass_hidden >= 1)
        _ps_grass_in_discard = discard_counts.get(Basic_Grass_Energy, 0) >= 1
        _ps_draw_supp_hand = (hand_counts.get(Lillie_Determination, 0) >= 1
                              or hand_counts.get(Dawn, 0) >= 1)
        _ps_meowth_engine = (
            hand_counts.get(Meowth_ex, 0) >= 1
            and not meowth_ability_lock
            and _prom_bench_after < 5
            and ((_ps_hidden_copies(Lanas_Aid) >= 1 and _ps_grass_in_discard)
                 or ((_ps_hidden_copies(Lillie_Determination) >= 1
                      or _ps_hidden_copies(Dawn) >= 1)
                     and _ps_grass_reachable)))
        _ps_can_find_energy = (
            (_ps_draw_supp_hand and _ps_grass_reachable)
            or (hand_counts.get(Lanas_Aid, 0) >= 1 and _ps_grass_in_discard)
            or _ps_meowth_engine)
        # Route (d): the 3-card draw of Flip the Script. It is kept apart from
        # `_ps_can_find_energy` because it is the weakest of the four -- it draws
        # blind, it does not search -- and that is why it carries TWO guards of its own: below, the
        # promoted body is required to keep its EXIT
        # (`_ps_keeps_its_way_out`), and here, that the KO it buys is really worth it.
        #
        # A WALL MATCHUP (MEASURED): the bet is not made against a deck that
        # structurally neutralises our ex -- ex immunity (Crustle /
        # Sylveon), ability immunity (Cornerstone) or a lock (Iron Thorns). There the
        # prize the finisher buys pays little (as soon as the wall goes back to the
        # active spot, the promoted ex does nothing to it) and what is risked -- a
        # 2-prize body -- is paid for anyway. The outer guard of
        # `_promote_setup_ko_attacker` only looks at the opposing ACTIVE; this one also looks
        # at the BENCH, which is where the wall waits its turn. A self-play gate
        # vs deck/opponents/crustle_kangaskhan.csv, 18000 games per
        # branch: 70.2% with the route open against 70.9% without it (-0.68, z
        # -1.4, and the sign repeated in 5 of 6 paired arms). It is not
        # significant, but the route fires in 5.8% of those games and does not
        # have to be there: it is limited to the matchup where the plan DOES pay off.
        _ps_wall_matchup = (
            AGENT_STATE.op_is_crustle_deck or op_is_sylveon_deck or AGENT_STATE.op_is_cornerstone_deck
            or op_is_iron_thorns_deck
            or op_has_ex_immune_active or op_has_ex_immune_bench
            or op_has_ability_immune_active)
        _ps_fez_draw_engine = (
            not op_iron_thorns_active
            and not _ps_wall_matchup
            and _ps_grass_reachable
            and (field_counts.get(Fezandipiti_ex, 0) >= 1
                 or (hand_counts.get(Fezandipiti_ex, 0) >= 1
                     and _prom_bench_after < 5)))

        def _ps_keeps_its_way_out(_pk):
            """The candidate can PAY ITS RETREAT with the energy it already carries.

            It is the half that makes route (d) safe (user, registro_008 step
            122): bringing up the almost-attacker is NOT a blind bet as long as
            it stays reversible. If the draw fails and the Grass does not appear,
            next turn we retreat it and bring up the 1-prize wall THEN --
            the sacrifice is a DEFERRABLE decision; being nailed down is
            not. A body at 0 energies with a retreat cost of 3 (Tapu Bulu) gives away
            the whole turn: it neither attacks nor can switch out.
            """
            return len(_pk.energies) >= RETREAT_COST.get(_pk.id, 1)

        # ROUTE (e), OUR MATCH POINT ONLY: THE TURN'S OWN DRAW. Routes (a)-(d)
        # all ask the board to GUARANTEE the missing Grass, because on an
        # ordinary turn a failed bet costs a body and buys nothing. At our match
        # point the arithmetic inverts: the alternative to betting is promoting
        # a wall whose chance of winning the game is exactly zero, so the top
        # card of the deck -- one draw, with Grass still hidden in there -- is
        # not a weak route, it is the ONLY route. Same guard as its neighbours:
        # `_ps_grass_reachable` (a copy is still unseen); with every Grass in
        # the discard and no recovery, nothing fires and the wall keeps the slot.
        #
        # The exit test goes with it. `_ps_keeps_its_way_out` protects a NEXT
        # turn -- "if the draw fails we retreat and put the wall up then" -- and
        # at match point the turn after this one only exists if we lose, where
        # a nailed-down body costs nothing extra.
        _ps_last_prize_bet = (_promo_ko_wins_the_game and _ps_grass_reachable)

        if _ps_remain > 0 and (_ps_can_find_energy or _ps_fez_draw_engine
                               or _ps_last_prize_bet):
            _ps_best_key = None
            for _psb in my_state.bench:
                if _psb is None or not isinstance(_psb, Pokemon):
                    continue
                _ps_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(_psb.id)
                if _ps_req is None:
                    continue
                # With ONLY route (d) alive -- the blind draw of Flip the
                # Script --, the candidate has to keep its exit: if the
                # Grass does not appear, it retreats and the wall comes up the
                # following turn. With any of the SEARCH routes (a/b/c) the
                # energy is practically assured and it is not needed, and at our
                # match point (route (e)) there is no following turn to keep the
                # exit for.
                if (not _ps_can_find_energy and not _promo_ko_wins_the_game
                        and not _ps_keeps_its_way_out(_psb)):
                    continue
                _ps_cur = len(_psb.energies)
                _ps_deficit = _ps_req - _ps_cur
                # ONE single attachment away from its requirement (the normal loop already covers
                # the ones that attack right now). Further away = it is not "almost ready".
                if _ps_deficit <= 0 or _ps_deficit > _ps_unit:
                    continue
                _ps_after = _ps_cur + _ps_unit
                if _psb.id == Hydrapple_ex:
                    _ps_dmg = 30 + 30 * total_grass
                elif _psb.id == Teal_Mask_Ogerpon_ex:
                    _ps_dmg = 30 + 30 * (_ps_after + _ps_opa_en)
                elif _psb.id == Dipplin:
                    _ps_dmg = 20 * max(0, bench_count - 1)
                elif _psb.id == Tapu_Bulu:
                    _ps_dmg = 220
                elif _psb.id == Meganium:
                    _ps_dmg = 140
                elif _psb.id == Fezandipiti_ex:
                    _ps_dmg = 100
                else:
                    _ps_dmg = 10
                _ps_bd = card_table.get(_psb.id)
                if (_ps_bd is not None and _ps_weak is not None
                        and getattr(_ps_bd, 'energyType', None) == _ps_weak):
                    _ps_dmg *= 2
                if _ps_dmg < _ps_remain:
                    continue  # even completed it does not finish the opposing active
                _ps_hp = getattr(_psb, 'hp', 0) or 0
                # PRIZES BEFORE HP (user): between two bodies that are the SAME
                # distance from finishing next turn, the one that concedes
                # FEWER prizes if it is knocked out comes up. Since the finisher is ours and
                # goes first, HP is a secondary tie-break; what is really
                # risked is the prize. Consistent with
                # [[alakazam-atacar-con-1-premio-no-ex]] and
                # [[promover-supervivencia-y-menos-premios]].
                _ps_key = (-_ps_deficit, -prize_count(_psb), _ps_hp, _ps_dmg)
                if _ps_best_key is None or _ps_key > _ps_best_key:
                    _ps_best_key = _ps_key
                    _promote_setup_ko_attacker = _psb
    # ------------------------------------------------------------------

    # --- SURVIVAL WHEN PROMOTING (user, registro_005 step 64 vs Archaludon,
    # LOST) --------------------------------------------------------------------
    # When choosing which body comes up to the active spot, the FIRST thing is whether it takes the
    # opposing active's attack. On that turn Archaludon ex hit for 220: only the
    # Hydrapple ex (330 HP) survived, and the agent brought up a Teal Mask Ogerpon ex
    # of 210 HP with SIX energies (4557 against 259) -- it died without having knocked out
    # (Myriad projected 300 against 400 HP) and gave away 2 prizes and the whole charge.
    #
    # Two criteria, in this order, deck-agnostic:
    #   1) if SOME candidate survives, the ones that die are penalised;
    #   2) if NONE survives, the one that hands over the FEWEST prizes wins.
    #
    # Exception: a candidate that KNOCKS OUT the opposing active keeps its score. There
    # the trade (taking a prize even if it dies) is correct and is already governed by
    # the rules above; this rule only orders those that take nothing.
    _promo_op_act = _active_of(op_state)
    _promo_survivors = 0
    _promo_min_prize = None

    def _promo_survives(_pk):
        """The candidate takes the projected attack of the opposing active."""
        if _promo_op_act is None or _pk is None:
            return True
        return _op_active_attack_damage_to(_promo_op_act, _pk) < (_pk.hp or 0)

    # HOW MANY BODIES OUR BENCH HAS AFTER THE PROMOTION -- the number that
    # scales the attack that reads it (Dipplin's Do the Wave). The two contexts
    # that promote do NOT agree on it:
    #
    #   TO_ACTIVE: the active was knocked out and is gone. The candidate leaves
    #   the bench and nothing takes its slot -> one body FEWER. With a raw
    #   `bench_count` the Dipplin of log 88971843 step 117 projected 20x4 = 80
    #   and "knocked out" the opposing 80 HP Dipplin: that handed it the
    #   PROMO_KO_BONUS of 20000 and also skipped the doomed-body penalty,
    #   bringing up an 80 HP body against a hit of 100. The real value is 20x3.
    #
    #   SWITCH: our voluntary retreat SWAPS the two bodies -- the candidate
    #   leaves the bench and the retreating active takes its slot, so the count
    #   does NOT drop. Subtracting there is the mirror error, and it hides
    #   damage instead of inventing it: the Dipplin of registro_008 step 78 was
    #   projected at 20x4 = 80 when it hits the Crustle for 20x5 = 100. It did
    #   not change that decision (80 > 0 was already enough for
    #   `_promo_wall_relief`), but `_promo_kos_op` is a THRESHOLD with 20000
    #   behind it, so under-counting can silence a finisher that is really there.
    #
    # The other two places that project onto a promoted body
    # (`_prom_bench_after` and `_promote_setup_ko_attacker`) keep their plain
    # subtraction: both hang off `_forced_ko_promote`, which demands an EMPTY
    # active spot, so they only ever run on the knockout path even though their
    # context test admits SWITCH.
    _promo_bench_after = (bench_count if context == SelectContext.SWITCH
                          else max(0, bench_count - 1))

    # THE ATTACHMENT THAT LOADS THE PROMOTED BODY IS **NEXT TURN'S** (user,
    # registro_007 step 135 vs Marnie's Grimmsnarl ex, LOST -- episode
    # 90898627, deck-agnostic).
    #
    # Turn 7, both piles at TWO. Their Grimmsnarl ex knocked out our Hydrapple ex
    # and, with the splash, the Meganium behind it: Wild Growth died with it, so
    # every Grass on our board went back to providing one. The menu offered a
    # Fezandipiti ex at 0 energy, TWO Teal Mask Ogerpon ex at 2/3 and a Tapu Bulu
    # at 1/4, with one Grass and a Boss's Orders in hand. Promoting an Ogerpon,
    # attaching that Grass and swinging Myriad Leaf Shower is 30+30x(3+3) = 210
    # doubled by the Darkness weakness = 420 on a 320 HP body: the last two
    # prizes, on OUR turn, before they can reply. The agent brought up the Tapu
    # Bulu -- which needs four energy and had one -- and lost.
    #
    # Every rule that could have promoted the Ogerpon was overruled by the same
    # -30000, `PROMO_MATCH_POINT_VETO`: at their match point a 2-prize body that
    # their blow removes (180 through a wounded 170 HP Ogerpon) is the game. Both
    # veto sites carry the one exemption that fits this board -- the body that
    # KNOCKS OUT and with that closes OUR count first -- and both ask
    # `_promo_kos_op` for it. It answered NO, and the reason was arithmetic, not
    # strategic: the projection refused to count the manual attachment because
    # `state.energyAttached` was True. That flag belongs to the turn IN PROGRESS,
    # and the turn in progress is THEIRS -- they attached and attacked with it.
    # The body we are choosing does not attack today; it attacks on our next
    # turn, which arrives with its attachment intact. Read at 2 energy the
    # Ogerpon does not reach Myriad's cost, `_attacker_base_damage` returns 0 and
    # a 420-damage finisher was priced at zero.
    #
    # So the flag is only believed while there IS an active in the spot -- the
    # voluntary retreat (SWITCH), which really does spend TODAY's attachment on
    # the body we bring up. With the spot EMPTY the promotion is forced and what
    # is being projected is next turn: the attachment counts. It is the same
    # reading `_ref_can_attach` already uses further down
    # (`not state.energyAttached or _ref_forced_promote`) and the one
    # `_prom_can_attach` uses inside `_best_promote_card` -- which is why that
    # selector DID see the Ogerpon and marked it: the two halves of the same
    # question disagreed, and the half with the veto behind it was the blind one.
    _promo_attach_open = (
        hand_counts.get(Basic_Grass_Energy, 0) >= 1
        and (not state.energyAttached
             or not (my_state.active and my_state.active[0] is not None)))

    def _promo_kos_op(_pk):
        """The candidate TAKES A PRIZE once promoted (with its current energy
        plus the manual attachment if it is still available).

        ASKED TWICE. First against the body in FRONT, which is what every
        consumer of this predicate was written around. Only if that says no, and
        only for a candidate whose attack picks its OWN target
        (`SNIPE_ANY_TARGET_IDS`), against the WHOLE opposing field: Cruel Arrow
        needs no Boss's Orders to reach their bench, so for a Fezandipiti ex "it
        knocks nothing out" and "it does not reach the wall in front" are two
        different sentences.

        The consumers all mean the wider one -- `PROMO_KO_BONUS` ("bring up the
        attacker that takes the prize"), the match-point exemptions ("the body
        that knocks out and closes OUR count first"), `_mp_last_stand` ("never
        surrender a knockout"), `_ko_front_outranked` ("among knockers"). Read
        only against the active, a sniper that closes the game reads as a mute
        body: user, registro_014 step 129, where promoting it WON on the spot
        and the agent brought up a Teal Mask Ogerpon ex to hit a Cornerstone
        wall for zero (see `_bench_snipe_best`).
        """
        if _pk is None:
            return False
        _pe = len(_pk.energies) * _grass_mult()
        if _promo_attach_open:
            _pe += _grass_attach_unit()
        if _promo_op_act is not None:
            _pbase = _attacker_base_damage(
                _pk.id, _promo_op_act, _pe, grass_scale=total_grass,
                teal_self_energy=_pe, bench_count=_promo_bench_after)
            if _pbase > 0:
                _peff = _our_effective_damage(
                    _pk, _promo_op_act, _pbase, AGENT_STATE.meganium_in_play,
                    neutralization_zone_active)
                if _peff >= (_promo_op_act.hp or 0):
                    return True
        return _snipe_best_target(
            _pk, op_state, _pe, AGENT_STATE.meganium_in_play,
            neutralization_zone_active, bench_count=_promo_bench_after,
            grass_scale=total_grass)[2]

    def _promo_damage_to_op(_pk):
        """Effective damage the candidate deals to the opposing active once promoted.

        The SAME projection as `_promo_kos_op` -- current energy, plus the manual
        attachment if it is still available (`_promo_attach_open`), and the bench
        as it stands after the promotion -- read as a QUANTITY instead of as a
        threshold. Against a wall the question is not whether the body finishes
        the wall off; it is whether it touches it AT ALL.
        """
        if _promo_op_act is None or _pk is None:
            return 0
        _pe = len(_pk.energies) * _grass_mult()
        if _promo_attach_open:
            _pe += _grass_attach_unit()
        _pbase = _attacker_base_damage(
            _pk.id, _promo_op_act, _pe, grass_scale=total_grass,
            teal_self_energy=_pe, bench_count=_promo_bench_after)
        if _pbase <= 0:
            return 0
        return _our_effective_damage(
            _pk, _promo_op_act, _pbase, AGENT_STATE.meganium_in_play,
            neutralization_zone_active)

    # SURVIVING IS WORTH NOTHING IF THE SURVIVOR IS MUTE (user, registro_008
    # step 78, turn 8, LOST vs Crustle -- episode 89679306).
    #
    # We retreat the Chikorita in front of a Crustle at 170/170 and the menu
    # offers a Dipplin (80 HP, 2 effective: Do the Wave does 100 to the wall) and
    # a Teal Mask Ogerpon ex (210 HP, 4 effective: Mysterious Rock Inn cancels it,
    # so it does 0). Crustle hits for 120: the Dipplin dies, the Ogerpon does not.
    #
    # The wall rule had already spoken -- the only unblocked attacker takes
    # +6000 -- and the survival band took the same 6000 straight back off it,
    # because the doomed-body penalty is EXACTLY the same size. The mute ex was
    # promoted with 3515 against the Dipplin's 715, dealt 0, and handed the
    # opponent a free turn and, two hits later, two prizes.
    #
    # The survival criterion was born against Archaludon (registro_005 step 64),
    # where EVERY candidate could hit back and the only question was who takes
    # the punch. Against a wall that premise breaks: the body that endures is
    # the one the wall has switched off. "One prize for 100 damage" is not a bad
    # trade there -- it is the only line that moves the game.
    #
    # So the exemption is deliberately narrow: only when NO survivor damages the
    # opposing active and some doomed candidate does. If any body both endures
    # AND hits, the penalty stands untouched and that body is still preferred.
    #
    # SWITCH only -- our voluntary retreat, on our turn, right before
    # attacking, so "it damages the wall" is a fact and not a forecast. The
    # FORCED promotion after a KO (TO_ACTIVE) is resolved on the OPPONENT's
    # turn: there the body that comes up attacks TOMORROW, today's damage says
    # nothing, and the criterion of `_best_promote_card` still rules (user,
    # registro_013 step 71).
    _promo_wall_relief = False
    if (context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE):
        for _pb in my_state.bench:
            if _pb is None:
                continue
            if _promo_survives(_pb):
                _promo_survivors += 1
            _pp = prize_count(_pb)
            if _promo_min_prize is None or _pp < _promo_min_prize:
                _promo_min_prize = _pp
        if (context == SelectContext.SWITCH and _promo_survivors > 0
                and (op_has_ex_immune_active or op_has_ability_immune_active)):
            _pw_hitters = [_pb for _pb in my_state.bench
                           if _pb is not None and _promo_damage_to_op(_pb) > 0]
            _promo_wall_relief = (
                bool(_pw_hitters)
                and not any(_promo_survives(_pb) for _pb in _pw_hitters))
    # ------------------------------------------------------------------

    # --- MATCH POINT ON THE ACTIVE SPOT (user, registro_014 step 130 vs
    # Alakazam, LOST -- episode 90350002, deck-agnostic) -----------------------
    #
    # Turn 14, four prizes to ONE. Our active Hydrapple ex stood at 170 of its
    # 330 and finished their Alakazam from the front; on the bench a Teal Mask
    # Ogerpon ex at 210/210 with four energies finished the same Alakazam just
    # as well, and a Tapu Bulu at 140 finished it too. The agent retreated and
    # promoted the TAPU BULU -- one prize instead of the ex's two -- it knocked
    # the Alakazam out, Wood Hammer left it at 110, and their next attacker
    # collected the last prize they needed.
    #
    # Every rule that chose it was arguing about a DISCOUNT THAT DOES NOT
    # EXIST. "Hand over one prize instead of two" and "so that an opposing KO
    # does not close the game" are worth something only while
    # `prize_count(body) < op_prize`. With their pile at ONE, the cheapest body
    # on our bench closes their count exactly as fast as the most expensive:
    # the price tag stops being information, and the only thing that still
    # separates the candidates is whether their reply can remove them at all.
    # 200 of Powerful Hand goes through a 140 HP Tapu Bulu and stops at a
    # 210 HP Ogerpon.
    #
    # WHY IT NEEDS ITS OWN SURVIVAL CENSUS. `_promo_survives` reads the
    # projector the ordinary way, and that is the seam where Powerful Hand
    # prints 0 (see `_op_active_attack_damage_to`): against the deck that
    # produced this record every candidate "survives" and the whole survival
    # band is asleep. This reading takes the maximum of the two -- the ordinary
    # one and the one that counts their hand -- exactly as
    # `_hand_revealed_lethal_reply` and `estimated_op_damage` already do.
    #
    # It only speaks with POSITIVE EVIDENCE: the candidate's own projection has
    # to be lethal and some other candidate has to outlast that same blow. With
    # an unreadable attack (a projection of 0) nobody is penalised, which is the
    # same guard `PROMO_MATCH_POINT_VETO` is written with.
    _mp_op_hand = getattr(op_state, 'handCount', None)

    def _mp_reply_to(_pk):
        """Their projected reply on `_pk`, reading their HAND where the card
        prints 0 damage. The maximum of both readings: never below what the
        rest of the model already sees."""
        if _promo_op_act is None or _pk is None:
            return 0
        return max(_op_active_attack_damage_to(_promo_op_act, _pk),
                   _op_active_attack_damage_to(_promo_op_act, _pk,
                                               op_hand_count=_mp_op_hand))

    def _mp_outlasts(_pk):
        """The candidate is still standing after that reply."""
        if _pk is None:
            return False
        return _mp_reply_to(_pk) < (_pk.hp or 0)

    _mp_front_survivors = 0
    if (context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE):
        for _pb in my_state.bench:
            if _pb is None:
                continue
            if _mp_reply_to(_pb) > 0 and _mp_outlasts(_pb):
                _mp_front_survivors += 1

    # THE SAME SEAM, ONE ROW FURTHER DOWN: THE SCALE (self-play mirror, game 90
    # turn 17; the census in docs/history/menu-order-ties.md). The reading above
    # was widened for Powerful Hand, which prints 0 damage. Syrup Storm has the
    # same problem with a different shape: it PRINTS 30 and counts the Grass
    # across their whole field, and the engine resolved it at 210 on that board.
    # Read without the scale all five candidates "survived", so nobody was
    # doomed, the prize fallback never ran, `PROMO_MATCH_POINT_VETO`'s own guard
    # was satisfied by phantom survivors, and a Teal Mask Ogerpon ex took the
    # front worth exactly the two prizes they still needed.
    #
    # `ptcg/cards/op_scaling.py` is opt-in on purpose -- switching the true
    # number on at all 42 call sites measured negative three times out of three,
    # because the thresholds downstream were fitted to the blind one. That
    # argument is about CALIBRATION, and this reading is not used to calibrate
    # anything: `_mp_price_ends_the_game` can only ever REMOVE from the menu a
    # body whose price IS their remaining pile. It can never promote a more
    # expensive one, which is what a blanket `scaled=True` did here -- measured
    # over 350 promotions against `crustle_wall_6`, it moved three, and two of
    # them from a 1-prize body to an ex.
    #
    # Positive evidence only, like its neighbours: their pile has to be at most
    # what this body pays AND their real blow has to remove it. With an
    # unreadable attack nothing is vetoed.
    def _mp_reply_scaled_to(_pk):
        """Their reply, now also reading the attack's real scale."""
        if _promo_op_act is None or _pk is None:
            return 0
        return max(_mp_reply_to(_pk),
                   _op_active_attack_damage_to(
                       _promo_op_act, _pk, op_hand_count=_mp_op_hand,
                       scaled=True, scale=AGENT_STATE.op_scale))

    _mp_cheaper_candidate = any(
        _pb is not None and prize_count(_pb) < op_prize
        for _pb in (my_state.bench or []))

    # THE BLOW IS PRICED ON A HAND WE ARE ABOUT TO TAKE AWAY (user,
    # registro_009 step 118 vs Alakazam, LOST -- episode 92106273,
    # deck-agnostic).
    #
    # Turn 9, three prizes to TWO. Their Alakazam knocked out our Meganium and
    # the promotion menu offered a Meowth ex 170, a Teal Mask Ogerpon ex 210
    # with two Grass, a Fezandipiti ex 210, a Tapu Bulu 140 and an Applin 40.
    # The Ogerpon FINISHES that Alakazam -- one Grass from hand puts Myriad Leaf
    # Shower at 30+30x(3+1) = 150 on a 140 HP body -- and `_promo_kos_op` said
    # so. It was vetoed anyway: their hand stood at SEVENTEEN cards, Powerful
    # Hand reads 20 x (17+2) = 380, that goes through every body on our bench,
    # and a 2-prize ex removed by their blow is their last two prizes. The Tapu
    # Bulu went up with no energy on it, could not attack, and the game was
    # over one turn later.
    #
    # The veto is right about the arithmetic and wrong about WHOSE number it is.
    # This promotion resolves at the END of their turn: OUR turn comes first,
    # and in that hand sat an Unfair Stamp, whose printed condition -- "only if
    # any of your Pokemon were Knocked Out during your opponent's last turn" --
    # is the very event that opened this menu. Playing it leaves them at
    # `STAMP_OP_HAND_AFTER` cards, and 20 x (2+2) = 80 does not remove a 210 HP
    # body. The blow the veto is priced on is not a fact about the board; it is
    # a quantity WE control, and we hold the card that collapses it.
    #
    # DECK-AGNOSTIC on their side: nothing here names Alakazam. It re-reads the
    # SAME three projections with the two hands the Stamp leaves behind, so it
    # speaks for every attack whose damage counts a hand -- theirs (Powerful
    # Hand) or ours (Resentful Refrain, Mind Ruler, which the reset makes
    # BIGGER, and then the veto simply stands).
    #
    # A SECOND QUESTION, NEVER A SUBSTITUTION. `_mp_op_hand` keeps feeding the
    # whole family untouched -- the survival census, `_mp_outlasts`, the doomed
    # penalty among the knockers -- because those consumers use the projection
    # as a FILTER and every one of them was calibrated on the blind reading;
    # swapping a shared projection for a truer one was measured at 47.8% against
    # 50.5% for asking it second. So this reading only speaks where the first
    # one already answered "lethal", and all it can do is REMOVE a veto: it can
    # never raise a score, never doom a body, and never promote anything on its
    # own.
    def _mp_reply_after_our_reset(_pk):
        """Their reply once our own hand reset has resolved.

        The same three readings as `_mp_reply_scaled_to`, with both hands set to
        what the Stamp prints. The plain reading stays in the `max()` because a
        blow that never counted a hand is not defused by emptying one.
        """
        if _promo_op_act is None or _pk is None:
            return 0
        _rs_scale = AGENT_STATE.op_scale
        if _rs_scale is not None:
            _rs_scale = _dc_replace(_rs_scale, my_hand=STAMP_OUR_HAND_AFTER)
        return max(
            _op_active_attack_damage_to(_promo_op_act, _pk),
            _op_active_attack_damage_to(_promo_op_act, _pk,
                                        op_hand_count=STAMP_OP_HAND_AFTER),
            _op_active_attack_damage_to(
                _promo_op_act, _pk, op_hand_count=STAMP_OP_HAND_AFTER,
                scaled=True, scale=_rs_scale))

    def _mp_our_reset_defuses(_pk):
        """We hold the reset, and after it their blow no longer removes `_pk`."""
        if not _stamp_reset_pending or _pk is None:
            return False
        return _mp_reply_after_our_reset(_pk) < (_pk.hp or 0)

    def _mp_price_ends_the_game(_pk):
        """This body hands them the last prize, and their blow takes it."""
        if _pk is None or _promo_op_act is None:
            return False
        if op_prize > prize_count(_pk):
            return False
        if _mp_reply_scaled_to(_pk) < (_pk.hp or 0):
            return False
        return not _mp_our_reset_defuses(_pk)

    # THE LAST STAND: WHEN EVERY PRICE IS THE SAME PRICE (user, registro_011
    # step 130 vs Alakazam, LOST -- episode 91532527, deck-agnostic).
    #
    # Turn 11, four prizes to ONE. Their Powerful Hand had just taken our
    # Teal Mask Ogerpon ex for 20 x 13 and the menu offered five bodies with no
    # energy on any of them: Meganium 160, Hydrapple ex 330, Fezandipiti ex 210,
    # Meowth ex 170 and a Tapu Bulu of 140. Nobody attacks next turn, nobody
    # knocks anything out; the only thing being chosen is who takes their next
    # blow. The agent promoted the TAPU BULU, the smallest body on the bench,
    # and the reply went through it with 200 to spare.
    #
    # Everything that pointed there was the prize discount again -- here
    # `_ko_prefer_basic_general`, "hand over a cheap body instead of an ex",
    # 8500 + hp/10 -- and at their match point that discount does not exist: a
    # 1-prize corpse closes their count exactly like a 2-prize one. The guard
    # above (`prize_count < op_prize`) takes that argument away; this is what
    # replaces it.
    #
    # WHEN THE PRICE STOPS BEING INFORMATION: `not _mp_cheaper_candidate`, i.e.
    # NO body on our bench pays less than their remaining pile. Whichever one
    # goes to the front, their next knockout ends the game, so the criterion is
    # the other one -- how much of their reply the body absorbs. It is read with
    # `_mp_reply_to` (the projector that counts their HAND, where this family of
    # attacks prints 0) and ordered by MARGIN: the bodies that outlast the blow
    # first, and among the doomed the one that comes CLOSEST to outlasting it.
    #
    # The margin is what matters and not just the raw HP because their number is
    # an UPPER bound -- `20 x (hand + 2)` -- that shrinks with every card they
    # play; the 330 HP Hydrapple ex is the only body on that bench their real
    # turn can fall short of, and it is the one line that keeps the game alive.
    #
    # AND THE BLOW HAS TO SEPARATE THEM. If their reply leaves EVERY candidate
    # standing, nobody is making a last stand and the ordinary criteria -- who
    # is closest to attacking, who protects the engine -- are the right ones;
    # this rule only speaks when their attack REMOVES at least one of the bodies
    # on the menu, which is when "who takes the blow" becomes the question.
    #
    # Positive evidence only, like its neighbours: a candidate whose reply is
    # unreadable (a projection of 0) is not ranked, and with the whole bench
    # unreadable nobody is chosen. It never surrenders a knockout: the bodies
    # that finish the opposing active are left out of the ranking altogether --
    # among knockers the base score decides, as `PROMO_KO_BONUS` documents --
    # and `PROMO_LAST_STAND` sits below the guaranteed finisher and far below
    # that bonus. It only decides who tanks when nothing else can be done.
    _mp_last_stand = None
    if ((context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE)
            and _promo_op_act is not None
            and not _mp_cheaper_candidate):
        _ls_best_key = None
        _ls_removes_one = False
        for _pb in my_state.bench:
            if _pb is None or not isinstance(_pb, Pokemon):
                continue
            _ls_reply = _mp_reply_to(_pb)
            if _ls_reply <= 0:
                continue
            if _ls_reply >= (_pb.hp or 0):
                _ls_removes_one = True
            if _promo_kos_op(_pb):
                continue
            _ls_key = ((_pb.hp or 0) - _ls_reply, _pb.hp or 0,
                       -prize_count(_pb))
            if _ls_best_key is None or _ls_key > _ls_best_key:
                _ls_best_key = _ls_key
                _mp_last_stand = _pb
        if not _ls_removes_one:
            _mp_last_stand = None
    # ------------------------------------------------------------------

    # --- THE FRONT SPOT AMONG THE ONES THAT KNOCK OUT (user, registro_012
    # step 172 vs Alakazam, LOST -- episode 91919734, deck-agnostic) ----------
    #
    # Turn 12, two prizes to TWO. We retreat the Dipplin and the menu offers
    # FIVE bodies, two of which finish the same 140 HP Alakazam from the front:
    # a Teal Mask Ogerpon ex at 210/210 with four Grass (Myriad Leaf Shower) and
    # a Hydrapple ex at 140 of its 330, already carved up, with two. The agent
    # promoted the HYDRAPPLE -- and it did take the prize -- but it left our
    # front seat at 140 HP and worth the exact two prizes they still needed,
    # with a 210 HP body that took the SAME prize sitting on the bench.
    #
    # NOTHING STRATEGIC DECIDED IT. `PROMO_KO_BONUS` says "among several
    # knockers the base score decides", and the base score of the two was 597
    # against 595: 500 for "it attacks now", `hp // 10` (21 for the Ogerpon, 14
    # for the Hydrapple), the energy count, +60 because a Hydrapple is a
    # Hydrapple and +21 for the size of Syrup Storm. HP IS in there -- it is
    # worth seven points, and the flavour bonuses on top of it are worth ninety.
    # The one criterion that separates the two bodies was outvoted by the ones
    # that do not.
    #
    # WHY THE MATCH-POINT RULE DID NOT CATCH IT. The sibling block below
    # (registro_014 step 130, the same matchup) penalises a knocker that their
    # reply removes when another knocker outlasts it. Their reply is projected
    # ONTO THE ACTIVE WE ARE ABOUT TO KNOCK OUT, and our own Xerosic had just
    # cut their hand to three: Powerful Hand read 20 x (3+2) = 100 and every
    # candidate on the bench "outlasted" it. The body that answers on their NEXT
    # turn is not on the board yet, so no survival reading can see it. Raw HP
    # can.
    #
    # THE ORDER, AND WHERE IT STOPS. The user's rung above this one -- "first a
    # one-prize body that beats them, a Meganium, a Tapu Bulu; only if we do not
    # have one, the ex with the most HP" -- is ALREADY decided, and decided by
    # rules that were measured one board at a time: prize denial (+3000 to a
    # 1-prize attacker while its price leaves them short), the basic-wall family
    # (8500 + hp/10), the Meganium designated against this very matchup (+400),
    # the Crustle/Kangaskhan split that keeps the Tapu Bulu on the bench ON
    # PURPOSE. This block does NOT re-decide it: reordering across prices was
    # tried first and moved two frozen-corpus decisions from a Teal Mask
    # Ogerpon ex to that same Tapu Bulu, which is a different question with an
    # answer somebody already measured.
    #
    # So the knockers are GROUPED by price (`ko_front_price_rung`, which clamps
    # every price that already reaches their pile onto one rung -- at their
    # match point the cheapest corpse closes their count exactly like the
    # dearest) and ordered ONLY INSIDE each group, by the most CURRENT HP:
    # `hp` and not the printed maximum, since the Hydrapple of this record is a
    # 330 HP body standing at 140.
    #
    # It only ever DEMOTES a knocker that an equally-priced knocker outlives, so
    # it can never promote a body that takes no prize, never change what the
    # front seat COSTS us, and never overturn a rule that scores in thousands
    # (the +3000 of prize denial, the +4000 of the best attacker, the +6000 of
    # the wall): see `PROMO_KO_FRONT` for where the size comes from.
    #
    # AND A BODY THAT CANNOT LEAVE THE FRONT DOES NOT SET THE BAR (user,
    # registro_036 step 146, the anti-Cubchoo rule thirty lines down in the
    # scorer). "The taller one takes the front" assumes both bodies are equally
    # usable there; against a deck that locks the active and discards its
    # energy, a candidate whose retreat cost it cannot pay is NAILED DOWN, and
    # that is a measured -300 on exactly this menu. Without this the 310 HP
    # Hydrapple ex (retreat 3, two energies) would demote the 210 HP Teal Mask
    # Ogerpon ex (retreat 1, four) that rule exists to promote. It is not
    # vetoed -- it stays a candidate and can still come up if it is the only
    # knocker -- it just does not get to demote a body that can pivot out.
    def _ko_front_nailed(_pk):
        if not op_is_cubchoo_deck or _pk is None:
            return False
        _kf_rc = RETREAT_COST.get(_pk.id, 1)
        return _kf_rc >= 3 and len(_pk.energies) < _kf_rc

    _ko_front_top_hp = {}
    if ((context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE)
            and _promo_op_act is not None):
        for _kf_b in (my_state.bench or []):
            if _kf_b is None or not isinstance(_kf_b, Pokemon):
                continue
            if not _promo_kos_op(_kf_b) or _ko_front_nailed(_kf_b):
                continue
            _kf_rung = ko_front_price_rung(_kf_b, op_prize)
            if (_kf_b.hp or 0) > _ko_front_top_hp.get(_kf_rung, 0):
                _ko_front_top_hp[_kf_rung] = (_kf_b.hp or 0)

    def _ko_front_outranked(_pk):
        """Another knocker of the SAME price stands taller than this one."""
        if not _ko_front_top_hp or _pk is None:
            return False
        if not _promo_kos_op(_pk):
            return False
        _kf_rung = ko_front_price_rung(_pk, op_prize)
        return _ko_front_top_hp.get(_kf_rung, 0) > (_pk.hp or 0)
    # ------------------------------------------------------------------

    # Rule (user, log 86345562 p55): when PROMOTING (a retreat or a KO) and NO
    # benched body can attack this turn and we have Lillie's Determination
    # in hand to refill, we prefer to bring up a 1-prize BASIC
    # (Applin is the priority) instead of a 2-prize ex (Meowth ex / Ogerpon
    # ex). That way we hand over only 1 prize as a wall while we rebuild the hand with
    # Lillie's and keep the ex -- and their already loaded energy -- safe on the bench
    # to attack later. It only applies if the opposing active is NOT immune to ex or
    # to abilities (those matchups already bring up an ex wall with their own logic).
    _ref_grass_attachable = (
        hand_counts.get(Basic_Grass_Energy, 0) >= 1
        or (hand_counts.get(Night_Stretcher, 0) >= 1
            and discard_counts.get(Basic_Grass_Energy, 0) >= 1))
    _ref_forced_promote = not (my_state.active and my_state.active[0] is not None)
    _ref_can_attach = _ref_grass_attachable and (
        not state.energyAttached or _ref_forced_promote)
    _refresh_no_attacker = True
    for _rbp in my_state.bench:
        if _rbp is None or not isinstance(_rbp, Pokemon):
            continue
        if _rbp.id not in MAIN_ATTACKERS:
            continue
        _rbp_e = len(_rbp.energies)
        if _can_attack_eff(_rbp.id, _rbp_e) or (
                _ref_can_attach
                and _can_attack_eff(_rbp.id, _rbp_e + _grass_attach_unit())):
            _refresh_no_attacker = False
            break
    _refresh_promote_prefer_basic = (
        (context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE)
        and not _lucario_sac_context
        and not _lucario_ko_prefer_basic
        and _promote_setup_ko_attacker is None
        and hand_counts.get(Lillie_Determination, 0) >= 1
        and not op_has_ex_immune_active
        and not op_has_ability_immune_active
        and _refresh_no_attacker)
    # ------------------------------------------------------------------

    # --- Crustle + Mega Kangaskhan ex matchup: splitting the attackers (user) ---
    # Against this deck the Mega Kangaskhan ex (or another target NOT immune to ex)
    # has to be attacked with OUR ex, and the non-ex -- above all Tapu Bulu,
    # which knocks Crustle out with a single attack -- have to be KEPT for when Crustle is active.
    # If the opposing active is Crustle (immune to ex) a non-ex comes up; if there is
    # no ex of ours able to attack, a basic is used all the same.
    _cm_matchup = AGENT_STATE.op_is_crustle_deck and AGENT_STATE.op_has_mega_kangaskhan
    _cm_have_ex_attacker = False
    _cm_vs_ex_target = (_cm_matchup and not op_has_ex_immune_active
                        and op_state.active and op_state.active[0] is not None)
    if _cm_vs_ex_target:
        for _cmp in my_state.bench:
            if _cmp is None or not isinstance(_cmp, Pokemon):
                continue
            if _cmp.id in (Teal_Mask_Ogerpon_ex, Hydrapple_ex):
                _cm_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(_cmp.id)
                if _cm_req is None:
                    continue
                _cm_e = len(_cmp.energies)
                if (_cm_e < _cm_req and not state.energyAttached
                        and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                    _cm_e += _grass_attach_unit()
                if _cm_e >= _cm_req:
                    _cm_have_ex_attacker = True
                    break
    # We only split (keeping Tapu Bulu / prioritising the ex) when the opposing active
    # is NOT immune to ex and we have an ex able to attack it this turn.
    _cm_use_ex = _cm_vs_ex_target and _cm_have_ex_attacker

    # =================================================================
    # GRAND TREE: the turn's plan (see the header of the `_gt_*` block).
    #
    # It is computed WHENEVER the stadium is on the field, not only when the menu
    # offers the ability: the plan is also consulted by (a) the retention of the
    # Forest of Vitality -- "first the ability, THEN the replacement" -- and
    # (b) the sub-selections the ability opens (which Basic evolves, which
    # card is brought from the deck), which arrive in later calls to `agent()`
    # with a different `context`.
    #
    # `_gt_ability_slot` = the position of the stadium's ABILITY option in THIS
    # menu. Its absence means the ability has already been used this turn (the
    # game engine stops offering it), so the Forest stops waiting.
    # It is identified by the CARD (id 1249), not by the area, so as not to depend on
    # how the simulator labels a stadium's ability.
    # =================================================================
    _gt_vetoes_ex_stage = (AGENT_STATE.op_is_crustle_deck or op_is_sylveon_deck
                         or op_has_ex_immune_active or op_has_ex_immune_bench)
    _gt_turn_plans = (
        _gt_planes(my_state, AGENT_STATE.ACTIVE_CARDS_IN_DECK, field_counts,
                   _our_first_turn, vetoes_ex_stage=_gt_vetoes_ex_stage,
                   doomed_active=(active_ko_likely or _active_doomed_real))
        if grand_tree_in_play else [])
    _gt_plan = _gt_turn_plans[0] if _gt_turn_plans else None

    _gt_ability_slot = None
    if grand_tree_in_play and context == SelectContext.MAIN:
        for _gt_o in select.option:
            if _gt_o.type != OptionType.ABILITY:
                continue
            _gt_c = get_card(obs, _gt_o.area, _gt_o.index, my_index)
            if _gt_c is not None and _gt_c.id == Grand_Tree:
                _gt_ability_slot = (_gt_o.area, _gt_o.index)
                break
    _gt_ability_pending = (_gt_ability_slot is not None and _gt_plan is not None)

    # Confirmations ("search?") emitted WHILE the ability is being resolved.
    _gt_prompt_si_no = (select.effect is not None
                        and select.effect.id == Grand_Tree)

    # Ranking of the Basics that open a chain (fetch + putting them down from hand). It only
    # makes sense with the stadium already on the field or with a copy in hand ready
    # to be played: without the stadium, the chain is not free and the normal
    # development rules govern.
    _gt_stadium_available = (grand_tree_in_play
                              or (hand_counts.get(Grand_Tree, 0) >= 1
                                  and not state.stadiumPlayed))
    _gt_basics_ranking = (
        _gt_wanted_basics(AGENT_STATE.ACTIVE_CARDS_IN_DECK, field_counts,
                             vetoes_ex_stage=_gt_vetoes_ex_stage)
        if _gt_stadium_available else {})
    # A Basic is only SEARCHED for if there is not already one in play that can serve as the root
    # next turn (here `appearThisTurn` is NOT filtered on: the one that comes down today
    # will be evolvable tomorrow) and if there is room on the bench.
    _gt_root_in_play = any(field_counts.get(b, 0) >= 1
                            for b in _gt_basics_ranking)
    _gt_quiere_basico = (bool(_gt_basics_ranking) and not _gt_root_in_play
                         and bench_count < 5)

    # FINISHER FISHING (see `_finisher_fishing`): with Lillie's Determination in
    # hand and the turn's Supporter free, is there an attack that TODAY only
    # depends on the draw bringing Grass? It is computed a single time, only in
    # MAIN (outside it there is no Supporter play to decide) and only with the
    # refill in hand, so the hypergeometric is not paid on every option.
    _finisher_fishing_plan = None
    if (context == SelectContext.MAIN
            and not state.supporterPlayed
            and hand_counts.get(Lillie_Determination, 0) >= 1):
        _finisher_fishing_plan = _finisher_fishing(
            my_state, op_state, state, hand_counts, field_counts,
            grass_in_deck=AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                Basic_Grass_Energy, {}).get(ZONE_DECK, 0),
            draws=_lillie_draw_count(my_prize),
            shuffles_hand=True,
            meganium_in_play=AGENT_STATE.meganium_in_play,
            neutralization_zone_active=neutralization_zone_active,
            total_grass=total_grass, bench_count=bench_count,
            can_switch=can_switch, has_switch_card=has_switch_card,
            abilities_off=meowth_ability_lock)

    # =================================================================
    # THE TURN PLAN (user, registro_013 steps 126-145, WON suboptimally). Every
    # "does this win?" flag has now been computed for this observation, so this is
    # the first point at which the question the whole turn hangs on can be
    # answered: with `my_prize` prizes left, is there a route that CLOSES the game
    # -- and if not, how many prizes do we take and how many do they take on the
    # reply? Until this block existed each of those flags was consulted by
    # whichever rule remembered it, and an ordering veto that knew nothing about
    # the prize count (`yields_to_unfair_stamp`) buried a winning Boss's Orders at
    # mutual match point. See ptcg/turn/game_plan.py for the record of that game.
    #
    # It is rebuilt on EVERY call, not frozen at the start of the turn: inside a
    # turn a Teal Dance adds energy and a gust changes the opposing active, so a
    # route that did not exist at action 1 may exist at action 4 -- and the other
    # way round.
    AGENT_STATE.turn_plan = build_turn_plan(
        my_prize=my_prize,
        op_prize=op_prize,
        my_state=my_state,
        op_state=op_state,
        state=state,
        hand_counts=hand_counts,
        total_grass=total_grass,
        bench_count=bench_count,
        meganium_in_play=AGENT_STATE.meganium_in_play,
        neutralization_zone=neutralization_zone_active,
        op_hand_count=getattr(op_state, 'handCount', 0),
        active_attack_wins_now=_active_attack_wins_now,
        win_via_boss_gust=_win_via_boss_gust,
        win_ko_active_via_promote=_win_ko_active_via_promote,
        # The PROMOTE route needs the same three things the retreat scorer reads:
        # which bodies are in play (which charging abilities are alive), whether
        # a retreat is possible at all, and whether abilities are locked.
        field_counts=field_counts,
        can_switch=can_switch,
        abilities_off=meowth_ability_lock,
    )
    if AGENT_STATE.turn_plan_open is None and context == SelectContext.MAIN:
        AGENT_STATE.turn_plan_open = AGENT_STATE.turn_plan

    # =================================================================
    # A READY ATTACK THAT TAKES NO PRIZE IS NOT WHAT THE TURN IS FOR
    # (user, registro_008 step 57, episode 90874130 vs Mega Lucario ex, LOST).
    #
    # `_active_ready_attacker` answers "is our active charged enough to attack",
    # and half a dozen rules read that answer as "the turn already has its
    # purpose, do not spend anything else on it". That reading is only true when
    # the attack is worth the turn. On the record's board it was not:
    #
    #     US (6 prizes)                       RIVAL (5 prizes)
    #     active Teal Mask Ogerpon ex         active Mega Lucario ex 340/340
    #            210/210, 3 Grass             bench  a 2nd Mega Lucario ex 340/340
    #     bench  Chikorita, Applin,                  + Solrock/Lunatone/Riolu
    #            2x Ogerpon ex (1 Grass each)
    #     hand   Meowth ex, Hydrapple ex, Meganium, Ogerpon ex,
    #            Xerosic's, Unfair Stamp, 2x Forest -- and NO Grass
    #
    # Myriad Leaf Shower with three on us and one on them is 30 + 30x4 = 150
    # against 340 at full health: no knockout, no prize, and the body that
    # throws it dies to Mega Brave (270) on the reply. The plan had already said
    # so -- `prizes_today=0`, `op_prizes_next=2`, mode DEVELOP -- and the turn
    # was still handed to the attack, ending with eight cards in hand, the
    # Supporter slot unspent and the Last-Ditch Catch of a Meowth ex in hand
    # never used. In the record the attack chipped the Lucario to 190, they
    # attacked with that same 190 body and won the game.
    #
    # The important half is that IT WAS NEVER A CHOICE. Benching a Basic lives
    # in `_TIER_DEVELOP` and the attack in tier 0, so the body goes down,
    # Last-Ditch Catch fetches the Supporter, the Supporter is played and the
    # attack STILL closes the turn ([[el-hueco-de-supporter-muere-con-el-ataque-
    # que-cierra-el-turno]]). The veto was paying for an attack it was not
    # competing with.
    #
    # The flag is the sentence "the attack is inert", read off the plan and
    # nothing else, so it is deck-agnostic in both directions -- ours and
    # theirs. It is the general case of a carve-out `_active_ready_attacker`
    # already carries: an attacker that does ZERO to an immune wall is not a
    # ready attacker. Zero damage is just the degenerate end of "takes no
    # prize"; what makes the turn sterile is the prize count, not the number on
    # the card. See [[gusteo-graduar-el-eje-del-ataque-inerte]] and
    # [[un-turno-esteril-es-un-turno-muerto-que-todavia-puede-mover]].
    #
    # `op_prizes_next >= 1` is what keeps a patient chip out of it: a body that
    # SURVIVES the reply attacks again next turn, so the 150 it puts on today is
    # an instalment and not a waste. Only when the attacker dies on the reply is
    # today's damage all the damage that body will ever do.
    # =================================================================
    _ready_attack_is_inert = (
        _active_ready_attacker
        and not AGENT_STATE.turn_plan.wins_this_turn
        and AGENT_STATE.turn_plan.prizes_today == 0
        and AGENT_STATE.turn_plan.op_prizes_next >= 1)

    # =================================================================
    # THE RELAY THAT TAKES NO PRIZE DOES NOT EARN THE FRONT SPOT (user,
    # registro_004 step 37, episode 90880936 vs Iono's Bellibolt ex, LOST).
    #
    #     US (6 prizes)                      RIVAL (6 prizes)
    #     active Chikorita 70/70, 1 Grass    active Iono's Bellibolt ex
    #            (Growl does 0; Seed Bomb           280/280, ZERO energy
    #             costs two)                 bench  3x Tadbulb, a 120 HP stage 1
    #     bench  Dipplin 80/80, 1 Grass             and a 70 HP body on TWO
    #     hand   Hydrapple ex, Boss's,              energies
    #            Xerosic's, 1 Grass
    #
    # `plan.attacker` pointed at the benched Dipplin, and TWO rules cash that
    # pointer without ever asking what the body it names would achieve: the
    # retreat scores 3500 for "the relay can attack" and the ATTACK of our own
    # active is vetoed for the same reason ("do not attack, retreat to the
    # relay"). The turn attached its Grass to the Chikorita, the retreat fee
    # discarded that same card, the Dipplin came up and threw Do the Wave -- 20
    # damage for each of our Benched Pokemon, and after the swap the bench holds
    # ONE. Twenty, into 280 at full health.
    #
    # What it bought is in the next record: the promoted Dipplin was knocked out
    # on the reply, Applin and Dipplin went to the discard together, the opponent
    # took a prize, and the Hydrapple ex stayed in hand with no body left to
    # evolve. The chip paid for the other side's prize.
    #
    # `_plan_relay_can_attack` measures whether the relay's attack is LEGAL. This
    # is the other half -- whether it is WORTH the swap -- and the front spot has
    # exactly THREE things to sell, so the flag is only true when the relay buys
    # none of them:
    #
    #   1. A PRIZE. `prizes_today` already answers it for BOTH routes a turn has
    #      -- `_prizes_via_promote` IS this retreat -- so a relay that knocks
    #      something out clears the flag by itself, with no card id involved.
    #   2. A KNOCKOUT WITHIN REACH. A chip is an instalment when one more of the
    #      same finishes the body it lands on, which is `remain_hp` <= the damage
    #      that produced it. Meganium leaving a Great Tusk at 40 is buying the
    #      next turn's prize; a Dipplin taking 20 off a 280 HP ex is buying a
    #      number. This is the user's sentence -- "it does not beat the active
    #      because it is an ex" -- with the ex read off its HP and not its type.
    #   3. A CHEAPER BODY IN FRONT. The retreat also chooses who pays the prize
    #      when the front spot falls ([[la-retirada-elige-quien-paga-el-premio]]),
    #      and a 2-prize body handing the spot to a 1-prize one is worth the fee
    #      with no damage at all ([[el-ex-mudo-no-es-un-muro]]).
    #
    # `op_prizes_next == 0` is the fourth escape, and the mirror image of the one
    # `_ready_attack_is_inert` uses one block above: when our active is knocked
    # out on the reply the swap is a RESCUE, and what pays for it is the body it
    # saves, not anything the relay does.
    #
    # See [[el-ataque-listo-que-no-toma-premio-no-es-el-turno]] -- the same
    # sentence for the attack our own active throws -- and
    # [[la-tasa-de-retirada-exige-relevo-que-pueda-actuar]], whose floor ("the
    # relay must be able to act") this raises to "the relay must achieve
    # something". And it is one flag for two menus on purpose:
    # [[una-bandera-de-dos-observaciones-no-puede-reevaluar-lo-ya-pagado]] --
    # a pointer that stops justifying the retreat must stop vetoing the attack
    # in the same breath, or the turn is left with no play at all.
    # =================================================================
    _pri_act = my_state.active[0] if my_state.active else None
    _pri_bench = [_b for _b in (my_state.bench or []) if _b is not None]
    _pri_i = AGENT_STATE.plan.attacker - 1
    _pri_relay = _pri_bench[_pri_i] if 0 <= _pri_i < len(_pri_bench) else None

    # The plan indexes the opposing bodies the way the loop that wrote it did:
    # 0 is their active, the rest is their bench with the empty slots removed.
    _pri_targets = ([op_state.active[0]] if op_state.active else [])
    _pri_targets += [_b for _b in (op_state.bench or []) if _b is not None]
    _pri_target = (_pri_targets[AGENT_STATE.plan.target]
                   if 0 <= AGENT_STATE.plan.target < len(_pri_targets) else None)
    _pri_remain = AGENT_STATE.plan.remain_hp

    _pri_ko_in_reach = (
        _pri_target is None or _pri_remain is None
        or _pri_remain <= (_pri_target.hp or 0) - _pri_remain)

    _pri_cheaper_body = (
        _pri_relay is not None and _pri_act is not None
        and prize_count(_pri_relay) < prize_count(_pri_act))

    _plan_relay_is_inert = (
        AGENT_STATE.plan.attacker >= 1
        and _pri_relay is not None
        and not AGENT_STATE.turn_plan.wins_this_turn
        and AGENT_STATE.turn_plan.prizes_today == 0
        and AGENT_STATE.turn_plan.op_prizes_next == 0
        and not _pri_ko_in_reach
        and not _pri_cheaper_body)

    # =================================================================
    # THE FINISHER THAT IS NOT ON THE BOARD YET (user, registro_002 step 25 vs
    # Mega Lucario ex, episode 89628162, LOST).
    #
    # Turn 2. Our active was a Meowth ex (170 HP, one energy, three short of
    # attacking) and in front of it a Riolu with one energy. Every defensive
    # reading agreed the board was quiet: Accelerating Stab projects 60 against
    # 170, so `_doomed_ex_sac_pivot` -- the pivot built for exactly this, retreat
    # the ex that is going to die and hand over a 1-prize body instead -- never
    # fired and the agent ENDED THE TURN. Their next turn the Riolu evolved into
    # Mega Lucario ex and took two prizes with the first attack of the game.
    #
    # `_op_evo_dmg_to_active` is that reading corrected: the same projection run
    # against what the opposing active can BECOME next turn (see
    # `_op_evolution_attack_damage_to`). Callers take `max()` of the two, because
    # against an active that is already a final stage it is 0.
    #
    # It corrects the reading that CONDEMNS our active, and only that one. The
    # pivot's snipe guard -- hiding the ex on the bench only denies prizes if it
    # survives there ([[repliegue-del-ex-condenado-vs-sniper]]) -- goes on being
    # measured with the body in front: broadening a guard that TURNS THE PIVOT
    # OFF is the change that was already measured at -3.1 points, and the
    # asymmetry is written down where the guard lives.
    _op_evo_dmg_to_active = 0
    _dsc_my_act = _active_of(my_state)
    _dsc_op_act = _active_of(op_state)
    if _dsc_my_act is not None and _dsc_op_act is not None:
        _op_evo_dmg_to_active = _op_evolution_attack_damage_to(
            _dsc_op_act, _dsc_my_act, getattr(op_state, 'handCount', None),
            op_discard=op_state.discard)

    # THE PROMOTION SIDE OF THE SAME SACRIFICE. The retreat is decided in the
    # MAIN menu (`ptcg/turn/options/retreat.py`); WHICH body goes up is decided
    # in the SWITCH menu of the next observation, where the board still reads the
    # same -- our doomed ex is still the active. This flag is what tells that
    # menu it is choosing a body to LOSE and not an attacker: the sacrifice
    # ordering lives in `ptcg/turn/options/card.py`.
    #
    # It is deliberately narrower than the retreat pivot. `_bench_attacker_ready`
    # and `prizes_today == 0` between them exclude every retreat that is looking
    # for a KO (the Tapu that knocks out, the Hydrapple wall, the lethal relief),
    # where the promotion has its own measured logic and a cheap body would be a
    # mistake.
    #
    # AND NOBODY MAY SURVIVE. The premise of a sacrifice is that whoever stands
    # in front is going to fall, so it may as well be the cheapest -- the same
    # arithmetic `_ko_prefer_basic_general` states as "the opponent one-shots
    # even our biggest tank". With a body that ENDURES the hit the premise is
    # false and the cheap one is a gift: the flip audit of this change caught it
    # promoting a 70 HP Chikorita over a healthy Hydrapple ex, a 330 HP wall that
    # takes the turn and keeps attacking. The projection is measured on each
    # benched body AS THE ACTIVE, which is where it is going.
    #
    # `_doomed_sac_armed` is the same reading MINUS the "a one-prize body is
    # already on the bench" clause, and it exists because the block below has
    # to be able to ARRANGE that body: asking for it first would switch the
    # arrangement off on exactly the boards that need it. Everything else --
    # the doomed active, nobody surviving, no attacker ready, no prize today --
    # is shared, so the two flags can never disagree about whether this is a
    # sacrifice board.
    _doomed_sac_context = False
    _doomed_sac_armed = False
    if (_dsc_my_act is not None and _dsc_my_act.id in OUR_EX_IDS
            and _dsc_op_act is not None
            and my_prize >= 3
            and not op_has_ex_immune_active
            and not _bench_attacker_ready
            and AGENT_STATE.turn_plan.prizes_today == 0):
        _dsc_hand = getattr(op_state, 'handCount', None)

        def _dsc_lethal_to(_dsc_body):
            return max(
                _op_active_attack_damage_to(_dsc_op_act, _dsc_body, _dsc_hand),
                _op_evolution_attack_damage_to(
                    _dsc_op_act, _dsc_body, _dsc_hand,
                    op_discard=op_state.discard)) >= (_dsc_body.hp or 0)

        if (_dsc_lethal_to(_dsc_my_act)
                and all(_dsc_bp is None or _dsc_lethal_to(_dsc_bp)
                        for _dsc_bp in (my_state.bench or []))):
            _doomed_sac_armed = True
            _doomed_sac_context = any(
                _dsc_bp is not None and prize_count(_dsc_bp) == 1
                for _dsc_bp in (my_state.bench or []))

    # THE BODY WE HAND OVER IS A BASIC, AND IF IT IS NOT ON THE BENCH WE PUT IT
    # THERE (user, episode 91522306 step 37 vs Archaludon ex, LOST).
    #
    #   US                                     RIVAL (Archaludon ex)
    #   active  Teal Mask Ogerpon ex 180 (3 G)  active  Duraludon 130 (1 M)
    #   bench   Dipplin 80, Bayleef 110,        bench   Duraludon 130
    #           Teal Mask Ogerpon ex 210 (1)
    #   hand    Chikorita, Hydrapple ex x2, ...
    #
    # Myriad Leaf Shower does not knock the Duraludon out (the whole line is
    # Metal and RESISTS Grass, -30), so attacking buys chip and leaves a
    # 2-prize ex in front of a body that evolves into Archaludon ex and hits
    # for 220. The projector above now sees that finisher, so the retreat
    # pivot fires -- but with the bench as it stands the body handed over is a
    # Dipplin or a Bayleef, halves of the two lines the deck attacks with, and
    # the CHIKORITA that is the actual spare body is sitting in hand.
    #
    # The user's ladder, in their words: put down a Basic from HAND first, or
    # one we can SEARCH for; only then hand over one already on the bench; and
    # with no Basic anywhere, attack. These are the same three pieces the
    # OPENING sacrifice already carries -- the body in hand, the PLAY envelope
    # that keeps it from being vetoed as development, the Poke Pad that buys
    # one -- asked of the board where the finisher is already visible.
    #
    # A ONE-PRIZE BODY ON THE BENCH DOES NOT SATISFY IT. It satisfies the
    # RETREAT (`_doomed_ex_sac_pivot` only ever needed one prize to go in front
    # instead of two), which is why nothing here gates that pivot: what this
    # arranges is a BETTER body to hand over, and if it never arrives the
    # retreat happens anyway with what the bench has. The order comes from the
    # promotion menu that will choose one observation later, which already
    # ranks a fresh Chikorita (6000) over a Bayleef or a Dipplin (4000).
    _doomed_sac_wall_in_hand = None
    _doomed_sac_needs_body = False
    if _doomed_sac_armed:
        _dsc_basic_benched = any(
            _dsb is not None
            and _dsb.id not in OUR_EX_IDS
            and not getattr(card_table.get(_dsb.id), 'stage1', False)
            and not getattr(card_table.get(_dsb.id), 'stage2', False)
            for _dsb in (my_state.bench or []))
        if not _dsc_basic_benched and bench_count < bench_max:
            for _dsc_hand_id in DOOMED_SAC_BENCH_ORDER:
                if hand_counts.get(_dsc_hand_id, 0) >= 1:
                    _doomed_sac_wall_in_hand = _dsc_hand_id
                    break
            # NO SPARE BASIC ANYWHERE: the search goes and gets one. The flag
            # says only "the sacrifice wants a cheap body and the board has
            # none"; WHICH body it brings is the fetch menu's question, and it
            # answers with this same order.
            _doomed_sac_needs_body = _doomed_sac_wall_in_hand is None

    # =================================================================
    # THE ONE-PRIZE WALL OF OUR FIRST TURN (user, registro_002 step 14 vs
    # Marnie, LOST). Our first turn, active Chikorita, Meowth ex on the bench
    # and a TAPU BULU in hand -- a 140 HP basic worth ONE prize. The agent
    # played Lillie's Determination, which shuffles the whole hand into the
    # deck, and the Tapu Bulu went with it: the one body of that hand that
    # drawing more cards cannot replace was spent to draw more cards.
    #
    # The turn we want instead has three parts, and they are three flags
    # because they are read in three different places:
    #
    #   * `_ft_wall_in_hand` -- the wall goes DOWN before the refill can
    #     shuffle it away (the PLAY branch);
    #   * `_ft_wall_charge_active` -- this turn's energy goes to the ACTIVE, up
    #     to its retreat cost, so the pivot below is payable at all (the
    #     DESTINATION of the energy is decided by `energy_score`, a different
    #     function from the one that scores the act of attaching -- a charge
    #     rule that only does one of the two halves does nothing);
    #   * `_ft_wall_pivot` -- if by the end of the turn we canNOT attack, the
    #     active retreats and the wall takes the front (the RETREAT branch and,
    #     one observation later, the promotion in the SWITCH menu).
    #
    # Attacking still comes first: the pivot asks for `not can_attack`, so a
    # turn that has an attack available takes it and the wall simply waits on
    # the bench. What the pivot buys when there is no attack is the shape of
    # the next two turns: they have to chew through a body that endures and
    # pays a single prize while our real attacker is assembled behind it.
    #
    # WHAT IT COSTS, stated plainly: the retreat DISCARDS the energy that pays
    # it. On our first turn that is at most the ONE Grass we attached this same
    # turn -- there is no earlier attachment to destroy -- and that bound is
    # why the rule is limited to the first turn instead of being a general
    # pivot. Deck-agnostic: `is_one_prize_wall` reads HP, prizes and stage off
    # the card, so the rule fires for whatever body a deck has in that role.
    # (The four names are pre-bound where `can_attack` is, see the note there.)
    #
    # THE ONE MATCHUP THAT DOES NOT WANT IT (user, ago 2026): an opponent whose
    # active makes the damage of our ex ZERO -- Crustle and Cornerstone Mask
    # Ogerpon ex. There the very body this rule spends as a shield is the only
    # thing on our side that can attack at all, and the ladder already treats it
    # that way (`_op_is_crustle_like` in ptcg/turn/options/play.py puts it down
    # at 22000/22500 as THE attacker of the matchup, and `_tapu_reserve` in
    # ptcg/turn/options/retreat.py refuses to retreat it away). Hiding an ex
    # behind it would be hiding an ex behind our own attacker: the wall goes in
    # front to take hits and the retreat burns the energy that should be
    # assembling it. It is stated as a property and not as a deck name -- what
    # excludes the matchup is that our ex cannot damage what is in front, so the
    # one-prize body stops being a wall and becomes the plan.
    _ftw_wall_is_our_attacker = (AGENT_STATE.op_is_crustle_deck
                                 or AGENT_STATE.op_is_cornerstone_deck)
    if _our_first_turn and not _ftw_wall_is_our_attacker:
        _ftw_act = _active_of(my_state)

        # (1) The copy in HAND. A second copy adds nothing (one wall is enough
        # in front) and the crowding vetoes of the PLAY branch already own that
        # decision, so we only claim the FIRST one.
        if bench_count < bench_max:
            for _ftw_c in (my_state.hand or []):
                if (is_one_prize_wall(_ftw_c.id)
                        and field_counts.get(_ftw_c.id, 0) == 0):
                    _ft_wall_in_hand = _ftw_c.id
                    break

        # (2) The copy already on the BENCH -- possibly the one we put down
        # earlier in this same turn. Undamaged: a wall that already took a hit
        # is not the body that buys turns.
        for _ftw_bp in (my_state.bench or []):
            if (_ftw_bp is not None and is_one_prize_wall(_ftw_bp.id)
                    and (_ftw_bp.hp or 0) >= (_ftw_bp.maxHp or 0)):
                _ft_wall_body = _ftw_bp
                break

        # (3) The pivot. It only makes sense if the swap is an IMPROVEMENT: an
        # active that hands over more prizes than the wall (an ex in front) or
        # one that endures less than it. An active that is itself a one-prize
        # wall is already the body we want and nothing is gained by shuffling
        # bodies around.
        #
        # AND THE WALL HAS TO SURVIVE. It is the premise of the whole idea: a
        # body the opponent one-shots buys no turns, hands over its prize just
        # the same, and the promotion is then a SACRIFICE -- a different
        # question, with its own measured answer (`_doomed_sac_context`:
        # nobody survives, so hand over the cheapest). Reading it with
        # `_op_evo_dmg_to_active` as well is what keeps a Riolu from being
        # priced as a Riolu when it is one card away from being a Mega Lucario.
        #
        # AND THERE HAS TO BE A REASON TO PAY THE FEE, of which there are two
        # (user, ago 2026, registro_002 step 25 vs Alakazam):
        #
        #   * THE THREAT. Their projection -- the attack of the active they
        #     have AND the one it becomes in one step -- takes the body in
        #     front down. This is the arm that was measured first.
        #   * THE PRIZE COUNT. Even with nothing threatening yet, an ex in
        #     front is a 2-prize body sitting where a 1-prize body could sit.
        #     Their bench is not built either: the KO does not come this turn
        #     or the next, and by the time it comes the swap is no longer free
        #     (an ex with its energy on it cannot be pulled back for one Grass).
        #     Paying the fee NOW -- on the only turn where the whole cost is the
        #     single Grass attached this same turn -- is what buys the three
        #     things the record asked for: an opponent who has to chew through
        #     a body that endures, ONE prize instead of two when it falls, and
        #     the turns in between to build the bench.
        #
        # The prize arm does NOT apply on turn 1 GOING FIRST -- the same seat
        # the prize mismatch already exempts (`_prize_mismatch_matchup`): there
        # the opponent has not played a card yet, so there is nothing to deny
        # and sacrificing early development only slows us down
        # (`test_abomasnow_first_turn_going_first_it_does_not_sacrifice`). The
        # threat arm is left alone: if something on that board really does
        # knock our body in front out, answering it was never the rule under
        # discussion.
        _ftw_op_act = _active_of(op_state)
        _ftw_op_hand = getattr(op_state, 'handCount', None)

        def _ftw_op_kos(_ftw_body):
            if _ftw_body is None or _ftw_op_act is None:
                return False
            return max(
                _op_active_attack_damage_to(_ftw_op_act, _ftw_body,
                                            _ftw_op_hand),
                _op_evolution_attack_damage_to(_ftw_op_act, _ftw_body,
                                               _ftw_op_hand,
                                               op_discard=op_state.discard)
            ) >= (_ftw_body.hp or 0)

        _ftw_threat = _ftw_op_kos(_ftw_act)
        _ftw_prize_denial = (
            _ftw_act is not None and _ft_wall_body is not None
            and prize_count(_ftw_act) > prize_count(_ft_wall_body)
            and not (state.turn == 1 and AGENT_STATE.we_go_first))

        if (_ft_wall_body is not None and _ftw_act is not None
                and not can_attack
                and not is_one_prize_wall(_ftw_act.id)
                and (prize_count(_ftw_act) > 1
                     or (_ftw_act.hp or 0) < (_ft_wall_body.hp or 0))
                and (_ftw_threat or _ftw_prize_denial)
                and not _ftw_op_kos(_ft_wall_body)):
            _ftw_rc = RETREAT_COST.get(_ftw_act.id, 1)
            _ftw_phys = _physical_energy(len(_ftw_act.energies))
            # The engine only OFFERS the retreat once the cost is already on
            # the body, so the two flags are exclusive: either it is paid and
            # we pivot, or this turn's attachment is what pays it.
            #
            # ONLY THE THREAT ARM BUYS THE FEE IN ADVANCE. Diverting the one
            # attachment of the turn to a body we are about to walk away from
            # is a real price -- it is an energy that does not go to the
            # attacker being assembled -- and a threat that lands next turn is
            # what pays for it. Denying a prize is worth the swap when the fee
            # is ALREADY on the active (the record's board: the Grass that Teal
            # Dance attached this same turn), not worth spending the turn's
            # energy on. With the arm off the wall simply waits on the bench,
            # which is where the rule found it.
            _ft_wall_pivot = _ftw_phys >= _ftw_rc
            # THE FEE IS PAID BEFORE THE PROMOTION IS ASKED (user,
            # registro_002 step 31/33 vs Marnie, WON -- episode 90361829).
            #
            # `_ft_wall_pivot` decides the RETREAT, and one observation later
            # the same flag was being asked again to decide WHO COMES UP. By
            # then the simulator has already discarded the retreat cost from
            # the active, so `_ftw_phys` is the energy that is LEFT, not the
            # energy that paid. In the canonical case of this rule -- the one
            # Grass of our first turn against a cost of one -- that leaves
            # `_ftw_phys` at 0, the flag comes out False exactly on the menu
            # where its second half had to act, and the generic ranking
            # (prizes x 1000 + HP) brings up the biggest body: the 2-prize ex
            # the pivot exists to hide. The record shows the whole cycle: an
            # active Teal Mask Ogerpon ex with one Grass retreats, the Grass
            # goes to the discard, and the promotion brings up ANOTHER Teal
            # Mask Ogerpon ex with one Grass. Same body in front, one energy
            # less.
            #
            # The affordability question belongs to the retreat and only to
            # it. Once `retreated` is set the fee is already spent: asking
            # again whether we can afford it is asking about money we have
            # already handed over. The rest of the pivot's conditions -- our
            # first turn, no attack, the wall alive on the bench, the active
            # worth more prizes or enduring less -- are still required, and
            # the promotion branch reads this flag only inside a SWITCH
            # context (ptcg/turn/options/card.py), the voluntary retreat we
            # just chose.
            _ft_wall_promote = _ft_wall_pivot or bool(state.retreated)
            _ft_wall_charge_active = (
                _ftw_threat
                and not _ft_wall_pivot
                and not state.energyAttached
                and hand_counts.get(Basic_Grass_Energy, 0) >= 1
                and _ftw_phys + 1 >= _ftw_rc)

    # =================================================================
    # THE EX DOES NOT WAIT IN FRONT ON OUR FIRST TURN (user, registro_002 step
    # 28, episode 90583594 vs Mega Starmie ex, LOST -- and generalised to the
    # whole field in ago 2026 at the user's request).
    #
    # The board of that step: our first turn, an active Teal Mask Ogerpon ex
    # with the one Grass of the turn on it -- not enough to attack -- and on
    # the bench an Applin with a Grass, a Meowth ex, a second Ogerpon ex with a
    # Grass and a bare Applin. In front of us, a Staryu with one Water.
    #
    # Every existing pivot looked at that Staryu and answered "no threat", each
    # for a reason that is correct in general:
    #
    #   * `_ft_wall_pivot` wants an undamaged one-prize WALL on the bench
    #     (`is_one_prize_wall`: a Basic, one prize, >= FIRST_TURN_WALL_MIN_HP
    #     and a real attacker). Two 40 HP Applin are not that, so the flag
    #     never even looked for a body.
    #   * `_doomed_sac_context` and `_doomed_ex_sac_pivot` ask the damage
    #     projector, evolution included. It answers 120 -- Jetting Blow, the
    #     only Mega Starmie attack whose cost a Staryu with one energy plus the
    #     projector's "+1 next turn" can pay -- and 120 does not knock out a
    #     210 HP ex, so nobody is doomed and nothing fires.
    #
    # What both readings miss is the SECOND attack on that card. Mega Starmie
    # ex prints Nebula Beam at 210 for three energies: the exact HP of our
    # Ogerpon ex, and the deck reaches three energies in one turn with the
    # Ignition Energy it runs.
    #
    # WHY THE RULE IS NOW STATED AS A DEFAULT AND NOT AS A DECK NAME. Mega
    # Starmie was the deck that got caught, not the only deck that does it: the
    # projector is right about what any of them can pay TODAY and blind to what
    # their line BECOMES in one card, and the list of lines that turn a
    # harmless opener into a 200+ damage body on their second turn is most of
    # the field -- Alakazam, Ogerpon Verde, Festival Lead, Mega Lopunny,
    # Dragapult, Mega Kangaskhan, Mega Lucario, Team Rocket's Mewtwo, Mega
    # Starmie, N's Zoroark ex, Archaludon, Mega Abomasnow, Hop's Phantump,
    # Slowpoke, Raging Bolt ex, Iron Thorns ex. Enumerating THEM would mean a
    # new unknown deck defaults to the wrong answer, and an unknown deck is
    # exactly the one whose evolution we cannot project. So the default is to
    # hide the ex, and what is enumerated is the SHORT list of openings where
    # hiding it is wrong (`_opening_sac_safe_matchup` below).
    #
    # So: with no attack available and a 2-prize ex in the active spot, retreat
    # it and put a one-prize body in front. `not can_attack` is the whole
    # gate on the offensive side -- a turn that can attack takes its attack --
    # and the promotion order the user gave lives in OPENING_SAC_PROMOTE_ORDER.
    #
    # IT IS AN OPENING RULE, AND THE GATE IS WHY (ago 2026, n=1000 per arm
    # against `deck/real_opponents/mega_starmie_1.csv` and `_2.csv`, two arms
    # that differ ONLY in `op_is_starmie_deck`, control `alakazam.csv` at -0.5
    # points / +0.01 prizes):
    #
    #     rule OFF                 88.3% / 88.6%   prizes +2.95 / +2.66
    #     every turn we cannot attack   84.0% / 81.3%   prizes +2.41 / +1.97
    #     OUR FIRST TURN only      88.5% / 85.7%   prizes +2.90 / +2.48
    #
    # Stated for any turn, the pivot fires 9.8-11.4 times PER GAME -- turns 2,
    # 4, 6, 8, 10, 12... -- because "we cannot attack" is the ordinary shape of
    # a turn spent developing. Every one of those firings discards an energy
    # and hands a 40 HP Applin to a deck that is happy to take it: three to six
    # points and half a prize per game, far outside the control's noise. What
    # the record asked for is the OPENING -- the user's own words are "to avoid
    # giving away two prizes at the START of the game" -- and there it is one
    # firing, it fixes step 28, and it costs nothing the gate can measure.
    #
    # `_our_first_turn` also subsumes the seat exemption that
    # `_prize_mismatch_matchup` carries: on turn 1 going FIRST the player
    # cannot attack by rule, so the pivot would burn the only Grass of the turn
    # before the opponent has played a card -- and their knockout does not come
    # next turn either, since a Staryu just placed cannot be a Mega Starmie
    # attacking for 210 on the following one. The user's own statement of the
    # rule names the same seat ("many of them, IF THEY GO FIRST, can already
    # knock one of our ex out on their second turn"): going second, our first
    # turn is turn 2 and the exemption does not apply.
    #
    # -----------------------------------------------------------------------
    # THE OPENINGS THAT DO NOT WANT IT (user's list, ago 2026). Seven
    # archetypes where leaving the ex in front costs nothing, so paying a
    # retreat fee out of the single attachment of the turn is pure loss:
    #
    #   Marnie's Grimmsnarl ex  -- their damage comes from a Stage 2 that is
    #   Cynthia's Garchomp ex      several turns away; nothing on the board
    #                              on their second turn takes 210 HP down.
    #   Crustle Wall            -- and Sylveon, which sets the same flag: a
    #   Sylveon                    wall deck whose whole plan is NOT to race.
    #   Cubchoo                 -- it locks our active instead of killing it.
    #   Comfey                  -- mill: it wins by decking us out, and every
    #                              turn we spend retreating helps it.
    #   Ralts (Gardevoir ex)    -- another Stage 2 ramp; the Ralts in front on
    #                              their first turn threatens nothing.
    #
    # ...plus Cornerstone Mask Ogerpon ex, which is NOT on the user's list but
    # is the same sentence as Crustle Wall and is already written down as such
    # elsewhere (`_ftw_wall_is_our_attacker`, twenty lines up): against an
    # active our ex cannot damage at all, the one-prize body is not a shield we
    # hide behind, it is the only attacker we have -- and the retreat burns the
    # energy that should be assembling it.
    #
    # Against all eight the ex STAYS in front and the second turn picks the
    # matchup plan back up with the board intact.
    #
    # WHAT THE GATE SAYS ABOUT THE GENERALISATION (ago 2026, candidate = this
    # tree vs base = the tree before it, both piloting deck.csv against the
    # bot; n=3000-4000 per arm, always from the SECOND seat, which is the seat
    # the rule fires in). Winrate delta, candidate minus base:
    #
    #   alakazam_1 +0.0   dragapult_1 -0.2   mega_lucario_1 -1.2
    #   mega_lopunny_1 +0.5   team_rocket_mewtwo_1 +0.1   ogerpon_verde_1 +1.1
    #   otro_ns_zoroark_ex_1 +0.0   mega_kangaskhan_1 -1.3   archaludon_1 -0.5
    #   mega_starmie_1 -0.8   festival_lead_1 +0.3
    #   marnie_grimmsnarl_1 -0.3   cynthia_garchomp_1 -0.6   crustle_wall_1 +0.1
    #
    # Mean -0.2 points. NOTHING here is outside the harness's own noise: two
    # base runs of archaludon_1 at n=4000 came out 93.4% and 94.3%, so the
    # floor is around a point per matchup and every number above sits inside
    # it. The rule is measured NEUTRAL and kept because it is the user's
    # strategy, stated for a reason the gate cannot see: the bot opponent does
    # not reliably assemble the second-turn knockout that the rule is insurance
    # against, so what it costs is measurable and what it buys is not.
    _opening_sac_safe_matchup = (AGENT_STATE.op_is_crustle_deck
                                 or AGENT_STATE.op_is_cornerstone_deck
                                 or op_is_sylveon_deck
                                 or op_is_cubchoo_deck
                                 or op_is_comfey_deck
                                 or op_is_gardevoir_deck
                                 or op_is_marnie_deck
                                 or op_is_cynthia_deck)
    _osac_act = _active_of(my_state)
    # ...AND THE PROJECTOR MUST NOT ALREADY SEE THE KNOCKOUT. The whole premise
    # of this rule is the knockout the opponent has NOT shown yet: the body in
    # front is healthy, their board says "no threat", and the rule fires anyway
    # because what kills us is the evolution still in their hand. A board where
    # the projection ALREADY takes our active down -- a wounded ex, an opposing
    # attacker that is simply big enough -- is a different board, and it
    # belongs to the pivots built on that projection (`_doomed_ex_sac_pivot`,
    # the prize-denial pivot, the survival ranking of the promotion), which are
    # better informed than an order that only knows about prizes: where a
    # benched body SURVIVES their reply, promoting it hands over ZERO prizes,
    # and no rung of this order beats zero.
    _osac_doomed_now = (
        _osac_act is not None
        and (_active_doomed_real
             or _op_evo_dmg_to_active >= (_osac_act.hp or 0)))
    if (not _opening_sac_safe_matchup
            and _our_first_turn
            and not can_attack
            and not _osac_doomed_now
            and _osac_act is not None
            and _osac_act.id in OUR_EX_IDS
            and not op_has_ex_immune_active
            and not (state.turn == 1 and AGENT_STATE.we_go_first)):
        # (1) THE BODY ALREADY ON THE BENCH. What the retreat needs is only
        # that ONE prize can go in front instead of two; WHICH of them goes up
        # is the promotion menu's question and is answered there, with the full
        # order. Asking the same ranking twice would let the two halves of one
        # rule disagree about who is available.
        _opening_sac_body = next(
            (_osac_bp for _osac_bp in (my_state.bench or [])
             if _osac_bp is not None and prize_count(_osac_bp) == 1), None)

        # (2) THE BODY IN HAND, walked in the user's order. These are the rungs
        # that can be missing from the board and still be arranged for: all
        # three are Basics, so they go down and come up in the same turn.
        #
        # TAPU BULU IS CLAIMED EVEN WITH A BODY ALREADY SEATED, the other two
        # only when the bench has nothing to promote. Tapu heads the order --
        # 140 HP and a real attacker afterwards -- so putting it down improves
        # a pivot that was going to happen anyway; an Applin or a Chikorita
        # benched on top of a bench that already holds a one-prize body would
        # be a second body given away for a swap the first one already pays
        # for. Only the first copy, and only with a free slot: the crowding
        # vetoes of the PLAY branch own everything else about benching them.
        if bench_count < bench_max:
            for _osac_hand_id in SETUP_ACTIVE_BASIC_ORDER:
                if hand_counts.get(_osac_hand_id, 0) < 1:
                    continue
                if (_osac_hand_id != Tapu_Bulu
                        and _opening_sac_body is not None):
                    break
                _opening_sac_wall_in_hand = _osac_hand_id
                break

        # (3) THE FEE. The retreat discards the cost off the active, and the
        # engine only offers the option once that cost is already on the body;
        # a Switch card pays it for free.
        _osac_rc = RETREAT_COST.get(_osac_act.id, 1)
        _osac_phys = _physical_energy(len(_osac_act.energies))
        # The one-prize body has to be ON THE BENCH, not in hand: a retreat
        # into a bench of nothing but ex spends the fee and changes which two
        # prizes we are offering. The copy in hand is a reason to PLAY it
        # (21600, above the refill that would shuffle it away) and the pivot
        # comes back one decision later, with the body already seated.
        _opening_sac_pivot = (
            _opening_sac_body is not None
            and (has_switch_card or _osac_phys >= _osac_rc))

        # (4) THE ENERGY OF THE TURN PAYS THE FEE (user, ago 2026): "if we
        # start with an ex in the active spot we attach ONE energy to it". Read
        # as arithmetic that is the same sentence as the pivot -- the engine
        # only OFFERS a retreat once the cost is on the body, so with an
        # unpaid fee the pivot cannot fire at all and the ex ends the turn in
        # front, which is the outcome the whole rule exists to avoid.
        #
        # It is the twin of `_ft_wall_charge_active` and it is deliberately
        # WIDER than that one. There the arm was gated on a projected THREAT,
        # because the wall it hides behind is a 140 HP body that could simply
        # wait on the bench one more turn; here the premise is that the threat
        # is exactly what the projector canNOT see (the evolution that is one
        # card away), so demanding it would switch the rule off on every board
        # it was written for -- the Staryu of the record included.
        #
        # The two flags are EXCLUSIVE, like there: either the fee is already
        # paid and we pivot, or this turn's attachment is what pays it. And it
        # only claims the attachment while it is still free and while ONE more
        # energy actually closes the cost: buying a retreat we still cannot
        # afford would throw the energy away for nothing.
        _opening_sac_charge_active = (
            not _opening_sac_pivot
            and (_opening_sac_body is not None
                 or _opening_sac_wall_in_hand is not None)
            and not state.energyAttached
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1
            and _osac_phys + 1 >= _osac_rc)

        # (5) NO ONE-PRIZE BODY ANYWHERE: the Poke Pad goes and gets one. The
        # flag says only "the pivot wants a body and the board has none"; WHICH
        # body the search brings is the fetch menu's question, answered with
        # the same order (`_RULES_PP_FETCH`, the `opening_sac_*` rungs).
        _opening_sac_needs_body = (_opening_sac_body is None
                                   and _opening_sac_wall_in_hand is None
                                   and bench_count < bench_max)

        # THE FEE IS ALREADY PAID BY THE TIME THE PROMOTION IS ASKED. The same
        # trap `_ft_wall_promote` documents at length: this menu arrives one
        # observation later, the simulator has already moved the retreat cost
        # to the discard, and re-asking the affordability question reads the
        # energy that is LEFT instead of the energy that paid. With `retreated`
        # set the question is already answered.
        _opening_sac_promote = _opening_sac_pivot or bool(state.retreated)

    # The decision context (Priority 1 refactor): invariant inputs that
    # the extracted `_score_*` scorers consume. It is built a single time.
    ctx = DecisionContext(
        state=state,
        my_state=my_state,
        op_state=op_state,
        hand_counts=hand_counts,
        field_counts=field_counts,
        supp_values=_supp_values,
        cards_in_deck=AGENT_STATE.ACTIVE_CARDS_IN_DECK,
        field_at_turn_start=AGENT_STATE._field_at_turn_start,
        bench_count=bench_count,
        my_hand_len=len(my_state.hand or []),
        my_prize=my_prize,
        op_prize=op_prize,
        op_hand_count=getattr(op_state, 'handCount', 0),
        meganium_in_play=AGENT_STATE.meganium_in_play,
        forest_in_play=AGENT_STATE.forest_in_play,
        itchy_pollen_active=itchy_pollen_active,
        has_hydrapple=has_hydrapple,
        watchtower_in_play=watchtower_in_play,
        festival_lead_hostil=_festival_lead_hostil,
        festival_lead_pays_us_now=_festival_lead_pays_us_now,
        meowth_ability_lock=meowth_ability_lock,
        neutralization_zone_active=neutralization_zone_active,
        mega_line_active=_mega_line_active,
        active_needs_energy=_active_needs_energy,
        evolve_possible_in_play=_evolve_possible_in_play,
        energy_starved_low_draw=_energy_starved_low_draw,
        pp_playable_in_hand=_pp_playable_in_hand,
        can_attack=can_attack,
        best_supp_in_hand_val=_best_supp_in_hand_val,
        best_supp_in_deck_val=_best_supp_in_deck_val,
        op_is_alakazam_deck=op_is_alakazam_deck,
        op_is_hop_deck=op_is_hop_deck,
        op_is_comfey_deck=op_is_comfey_deck,
        op_active_is_dunsparce=op_active_is_dunsparce,
        op_has_ability_immune_active=op_has_ability_immune_active,
        op_has_ex_immune_active=op_has_ex_immune_active,
        op_has_ex_immune_bench=op_has_ex_immune_bench,
        op_is_control_deck=op_is_control_deck,
        op_is_slowking_deck=op_is_slowking_deck,
        op_is_gardevoir_deck=op_is_gardevoir_deck,
        op_is_zoroark_deck=op_is_zoroark_deck,
        op_is_aggro_deck=op_is_aggro_deck,
        op_is_beedrill_deck=op_is_beedrill_deck,
        op_is_crustle_deck=AGENT_STATE.op_is_crustle_deck,
        op_is_cornerstone_deck=AGENT_STATE.op_is_cornerstone_deck,
        op_is_fire_deck=op_is_fire_deck,
        op_is_mirror=op_is_mirror,
        op_kang_ko_target=op_kang_ko_target,
        stadium_id=stadium_id,
        ko_last_turn=AGENT_STATE.ko_last_turn,
        our_first_turn=_our_first_turn,
        active_cant_attack=_active_cant_attack_this_turn,
        bdg_retreat_ko=_bdg_retreat_ko,
        supporter_boost=(500 if itchy_pollen_active else 0),
        we_go_first=AGENT_STATE.we_go_first,
        budew_op_index=budew_op_index,
        budew_on_op_field=budew_on_op_field,
        item_lock_incoming=_item_lock_incoming,
        opening_sac_needs_body=_opening_sac_needs_body,
        doomed_sac_needs_body=_doomed_sac_needs_body,
        our_xerosic_capped_this_turn=AGENT_STATE._xerosic_played_this_turn,
        lucario_sac_pivot=_lucario_sac_pivot,
        win_via_boss_gust=_win_via_boss_gust,
        gust_2prize_via_boss=_gust_2prize_via_boss,
        ex_immune_wall_ko_ready=_ex_immune_wall_ko_ready,
        boss_win_via_bench=_boss_win_via_bench,
        boss_dodge_redirect=_boss_dodge_redirect,
        boss_defensive_gust=_boss_defensive_gust,
        boss_deny_alakazam_line=_boss_deny_alakazam_line,
        boss_trap_gust=_boss_trap_gust,
        boss_low_value_gust=_boss_low_value_gust,
        boss_active_threat_dominates=_bo_act_threat_dom,
        boss_prize_rank=_boss_prize_rank,
        win_ko_active_via_promote=_win_ko_active_via_promote,
        boss_ko_threat_preevo=_boss_ko_threat_preevo,
        active_ko_likely=active_ko_likely,
        active_doomed_real=_active_doomed_real,
        ability_unlock_retreat_ko=_ability_unlock_retreat_ko,
        ability_unlock_retreat_attack=_ability_unlock_retreat_attack,
        has_ready_bench_attacker=_bench_attacker_ready,
        grand_tree_in_play=grand_tree_in_play,
        grand_tree_ability_pending=_gt_ability_pending,
        meowth_ld_free=_meowth_ld_free,
        finisher_fishing=_finisher_fishing_plan,
        turn_plan=AGENT_STATE.turn_plan,
    )

    # =================================================================
    # THE TURN'S SUPPORTER IS ALREADY IN HAND (user, registro_004 step 36 vs
    # Alakazam, WON with a mistake). Only ONE Supporter is played per turn, so
    # BEFORE putting the Meowth ex down we have to decide WHICH Supporter is going to be played:
    # if the winner is one we ALREADY have in hand, the one Last-Ditch
    # Catch brings canNOT be played today and the Meowth only gives away a 2-prize body
    # on the bench.
    #
    # On that turn: an active Ogerpon ex with 1 energy, and in hand a Boss's +
    # a Xerosic's Machinations + a Meowth ex. The agent put the Meowth ex down (the
    # `_meowth_devel_lillie` engine, 21800), its fetch brought Lillie's Determination...
    # and immediately afterwards it played the XEROSIC it already had in hand (7300 > the 5000 of
    # the Lillie's). The freshly fetched Lillie's stayed dead in hand and the
    # 2-prize body on the bench, free, for nothing.
    #
    # Why `_meowth_fetch_redundante` was not enough: that veto only looks at whether the
    # fetch would bring a card that is ALREADY in hand (a useless COPY). Here the
    # fetch brought something different and useful -- the problem is that it competes for the
    # ONLY Supporter slot of the turn and loses. They are two different failures
    # of the same resource.
    #
    # And why comparing on the fetch's scale was not enough: the two scales
    # ORDER THINGS THE OPPOSITE WAY. `_RULES_MEOWTH_FETCH` scored Lillie's 1200 vs Xerosic
    # <=150 (the `stuck_without_lillie_in_hand` branch), while the play scorer
    # scores Xerosic 7300 vs Lillie's 5000. The scale that DECIDES is the play
    # one, so the prediction has to be made there: both sides are measured
    # with `_supp_play_score`, over the HYPOTHETICAL hand after the fetch
    # (- the Meowth that goes down, + the Supporter that arrives), which is the exact
    # board on which the choice will be resolved. Deck-agnostic: it names no
    # cards, it only counts Supporters and their real scorers.
    #
    # It only vetoes PUTTING the Meowth ex DOWN. The ABILITY of a Meowth already in play still
    # searches: the Last-Ditch Catch is free and keeping the Supporter for the
    # next turn is a net gain (unlike the redundant copy of
    # `_meowth_skip_fetch`, which never contributes anything).
    # The same question one step earlier in the chain, for the Meowth ex that is
    # still in the DECK: it is read by the Ultra Ball (its value AND its fetch),
    # which is resolved in a deck-search prompt and not only in the MAIN menu,
    # so it is computed with no context gate. See `_supp_in_hand_takes_the_turn`.
    _ub_supp_in_hand_turn = _supp_in_hand_takes_the_turn(ctx)

    _meowth_supp_turn_id, _meowth_supp_turn_val = None, 0
    _meowth_fetch_play_val = 0
    _meowth_fetch_loses_the_turn = False
    if (context == SelectContext.MAIN
            and not state.supporterPlayed
            and not _our_first_action_turn
            and hand_counts.get(Meowth_ex, 0) >= 1
            and _meowth_fetch_id is not None
            and not _meowth_fetch_redundante):
        # a defaultdict, not a dict: the scorers access it by brackets (e.g.
        # hand_counts[Basic_Grass_Energy]) and a bare dict would blow up.
        _mw_hand_post = defaultdict(int, hand_counts)
        _mw_hand_post[Meowth_ex] = max(0, _mw_hand_post.get(Meowth_ex, 0) - 1)
        _mw_hand_post[_meowth_fetch_id] = (
            _mw_hand_post.get(_meowth_fetch_id, 0) + 1)
        # `my_hand_len` does not change: one card goes down (the Meowth) and another comes in
        # (the fetched Supporter).
        _ctx_post_fetch = _dc_replace(ctx, hand_counts=_mw_hand_post)
        _meowth_fetch_play_val = _supp_play_score(
            _ctx_post_fetch, _meowth_fetch_id)
        _meowth_supp_turn_id, _meowth_supp_turn_val = (
            _best_supporter_in_hand(_ctx_post_fetch, _mw_hand_post))
        # ...and the Supporter that wins the slot has to WIN IT FOR A REASON
        # (user, registro_004 step 46, episode 89624781 vs Dragapult ex -- WON in
        # spite of this). Turn 4, no Grass in hand at all: no attachment, no Teal
        # Dance, no attack -- the whole value of the turn was the refill. In hand
        # {Xerosic, Unfair Stamp, Meowth ex, Ultra Ball, Hydrapple ex}, three
        # Lillie's alive in the deck and the opponent on FOUR cards. The three
        # pieces blocked each other in a circle:
        #
        #   Lillie's (the fetched one)  -1  `ultra_ball_completes_the_line`
        #                                   -- an ORDER veto: play the Ultra Ball first
        #   Meowth ex                   -1  THIS predicate, reading that -1 as the
        #                                   real value of the fetch
        #   Xerosic                     20  its DEFAULT, `XEROSIC_SCORE_LAST_RESORT`
        #
        # ...so the turn's Supporter went to the card whose own scorer says it has
        # no useful effect: capping a Dragapult hand of 4 down to 3 takes ONE
        # random card and there is no Powerful Hand to cap. Right after, the Ultra
        # Ball paid its cost with the Meowth ex and the Hydrapple ex.
        #
        # `SUPP_SCORE_LAST_RESORT_BAND` is the height at which every Supporter
        # scorer says "play me only because nothing else scores"
        # (XEROSIC_SCORE_LAST_RESORT and BOSS_SCORE_EMPTY_GUST both sit there).
        # A Supporter at that height is not "the Supporter of the turn", so it
        # cannot be the reason to leave a Meowth ex dead in hand: if nothing we
        # hold does anything today, a fresh Supporter from the deck is worth the
        # 2-prize body. Above the band the comparison is unchanged -- a real
        # Boss's/Lillie's/Xerosic in hand still keeps the Meowth in hand.
        #
        # It is deliberately the MEOWTH side and not the Xerosic one: leaving
        # Xerosic at 20 keeps it as the net that takes the slot when the Meowth is
        # vetoed for some other reason, so the two never yield to each other and
        # lose the Supporter entirely (the measured Lillie's <-> Boss's failure).
        #
        # ONE EXEMPTION, AND IT IS ABOUT WHAT THE COMPARISON CANNOT SEE (user,
        # episode 90325863, turn 8 vs a Dragapult / Azumarill deck). The whole
        # Boss's projection -- `_bo_*` in the Supporter scorer, and with it
        # `_boss_dodge_redirect` and every gust value -- is computed inside
        # `if hand_counts.get(Boss_Orders, 0) >= 1`. With the Boss's still in
        # the DECK, which is the only situation in which a Meowth ex is worth
        # benching for it, `_supp_play_score` for the Boss's does not come back
        # low: it comes back -1, `no_value`, because nothing was projected at
        # all. Substituting the hypothetical hand does not undo that; the
        # projection is upstream of the hand.
        #
        # So on the record's board the comparison read a real Lillie's at 5800
        # (`charged_hydra_over_boss`: our Hydrapple ex was charged) against a
        # Boss's at -1, vetoed the Meowth, played the Lillie's -- and the
        # Lillie's DREW the Boss's Orders, one card too late, with the turn's
        # only Supporter already spent. Their Marill sat there untouchable and
        # our Syrup Storm resolved for zero.
        #
        # The exemption is as narrow as the blindness: only when the gust is
        # the turn's line because their active cannot be touched and their
        # bench can (`_boss_gust_immune_active`, the same flag that already
        # scores the Meowth play at 22000), and only when the fetch really
        # points at the Boss's. Everywhere else the comparison still rules --
        # this does not widen it, it stops it deciding a case it never measured.
        _meowth_fetch_loses_the_turn = (
            _meowth_supp_turn_id is not None
            and _meowth_supp_turn_id != _meowth_fetch_id
            and _meowth_supp_turn_val > SUPP_SCORE_LAST_RESORT_BAND
            and _meowth_supp_turn_val >= _meowth_fetch_play_val
            and not (_boss_gust_immune_active
                     and _meowth_fetch_id == Boss_Orders))

    # Teal Dance PRECEDES the manual attachment (user, registro_004 step 28, vs
    # Mega Starmie): if a Teal Mask Ogerpon ex STILL has its Teal
    # Dance ability available this turn (an ABILITY option appears for that same
    # Ogerpon), energy must not be charged onto it MANUALLY. Teal Dance
    # attaches a Grass AND ALSO DRAWS a card, so it takes priority: the
    # manual attachment is postponed until the ability has been used. Here
    # we collect the positions (area, index) of the Ogerpon that can still
    # use Teal Dance in order to veto, in the ATTACH branch, the manual attachment to that slot.
    _teal_dance_slots = set()
    if context == SelectContext.MAIN:
        for _tds_o in select.option:
            if _tds_o.type == OptionType.ABILITY:
                _tds_card = get_card(obs, _tds_o.area, _tds_o.index, my_index)
                if _tds_card is not None and _tds_card.id == Teal_Mask_Ogerpon_ex:
                    _teal_dance_slots.add((_tds_o.area, _tds_o.index))

    # Is the Ultra Ball OFFERED at all in this menu? It is the only honest test
    # of "can it still be played this turn", and it is not the same as its score.
    # `_ub_cancel_meowth` and the rest of the cost vetoes leave the Ultra Ball at
    # -1 for THIS INSTANT and lift themselves within the turn -- in registro_004
    # step 47 the Meowth ex goes down first and the Ultra Ball becomes playable
    # right after -- so a score gate would read "it will never be played" where
    # the order is simply not its turn yet. What the engine does NOT offer cannot
    # be played at all: under item lock (an opposing Budew, a Jellicent) the
    # Ultra Ball is absent from the menu, and only there is an ordering veto that
    # waits for it a dead loss. Read by `_lillie_play_order_veto`'s caller.
    _ub_offered_in_menu = False
    if context == SelectContext.MAIN:
        for _ubo_o in select.option:
            if _ubo_o.type != OptionType.PLAY:
                continue
            _ubo_card = get_card(obs, AreaType.HAND, _ubo_o.index, my_index)
            if _ubo_card is not None and _ubo_card.id == Ultra_Ball:
                _ub_offered_in_menu = True
                break

    # Pivot vs Alakazam (user, registro_010 step 127, LOST): against an Alakazam
    # deck we prefer to attack with ONE-prize bodies (Meganium, Tapu Bulu) instead
    # of with an ex (2 prizes). If the ACTIVE is an ex of OURS that is going to attack,
    # but on the bench there is a READY NON-ex 1-prize attacker (Meganium/Tapu Bulu)
    # that KNOCKS OUT the opposing active, and the active ex can pay its retreat cost,
    # we RETREAT the ex and promote the 1-prize body to attack: if it is then
    # knocked out we concede 1 prize instead of 2. It does NOT apply if attacking with the ex WINS
    # the game (then we attack, full stop). The later promotion chooses the
    # 1-prize body via `_best_promote_card` (the vs-Alakazam branch above).
    _alakazam_pivot_1prize = False
    if (context == SelectContext.MAIN and op_is_alakazam_deck
            and can_attack and my_state.active and my_state.active[0] is not None):
        _akp_act = my_state.active[0]
        _akp_op = op_state.active[0] if op_state.active else None
        if (_akp_act.id in OUR_EX_IDS and _akp_op is not None
                and not op_has_ex_immune_active):
            _akp_op_hp = _akp_op.hp or 0
            _akp_rc = RETREAT_COST.get(_akp_act.id, 1)
            _akp_can_retreat = len(_akp_act.energies) >= _akp_rc
            _akp_bench_ko_1prize = False
            for _akp_bp in (my_state.bench or []):
                # Any ONE-prize body (non-ex) that knocks out will do for the
                # pivot: Dipplin/Meganium/Tapu Bulu/... (user, registro_005
                # step 56 vs Alakazam, LOST: a charged Dipplin with Do the Wave
                # 20 x bench knocks out the active Abra -- before, the whitelist
                # (Meganium, Tapu_Bulu) excluded it and we attacked with the Ogerpon
                # ex, exposing 2 prizes to Powerful Hand). Bodies with no
                # modelled attack fall through `_akp_base <= 0`.
                if _akp_bp is None or prize_count(_akp_bp) != 1:
                    continue
                _akp_be = len(_akp_bp.energies)
                if not _can_attack_eff(_akp_bp.id, _akp_be):
                    continue
                _akp_base = _attacker_base_damage(
                    _akp_bp.id, _akp_op, _akp_be * _grass_mult(),
                    grass_scale=0, teal_self_energy=_akp_be, bench_count=bench_count)
                if _akp_base <= 0:
                    continue
                if _our_effective_damage(_akp_bp, _akp_op, _akp_base,
                                         AGENT_STATE.meganium_in_play,
                                         neutralization_zone_active) >= _akp_op_hp:
                    _akp_bench_ko_1prize = True
                    break
            _akp_prizes_from_ko = prize_count_op(_akp_op)
            _akp_my_left = len([p for p in (my_state.prize or []) if p is None])
            _akp_win_now = _akp_my_left <= _akp_prizes_from_ko
            # THE DISCOUNT HAS TO DISCOUNT (user, registro_014 step 127 vs
            # Alakazam, LOST -- episode 90350002). This whole pivot is one
            # sentence long: "if it is then knocked out we concede 1 prize
            # instead of 2". With their pile at ONE that sentence is false --
            # the one prize the cheap body hands over is the prize that ends the
            # game -- and paying a retreat for it burns the ex's energy to buy
            # nothing. At match point the front spot is decided by who OUTLASTS
            # their reply, which is `_mp_outlasts`'s business, not by the price
            # tag. See [[el-puesto-activo-lo-ocupa-el-cuerpo-que-paga-menos]].
            if (_akp_can_retreat and _akp_bench_ko_1prize and not _akp_win_now
                    and op_prize > 1):
                _alakazam_pivot_1prize = True

    # Indexes of manual attachments that YIELD to a pending Teal Dance
    # (see the rule in the OptionType.ATTACH branch): besides the score cap,
    # they are left at tier 0 of the play order so the score decides.
    _attach_yields_to_teal_dance = set()

    # DEFERRABLE ORDERING vetoes: {option index:
    # (real_score, (ids of the cards that must be played first, ...))}. They are filled by
    # the branches that veto a GOOD option only because another card in hand has
    # to be played FIRST -- the ABILITY branch (Flip the Script behind the Unfair
    # Stamp / Lillie's) and the PLAY branch (Lillie's behind the Ultra Ball that
    # completes the line). The "REVOKE ORDERING VETOES" block (further down)
    # lifts them if that "first" is not going to happen in this menu. Without this layer an
    # ordering veto ate free ONCE-PER-TURN abilities whose
    # blocker never got to be played (registro_006 step 78) and, under item
    # lock, the whole Supporter of the turn (see `_lillie_play_order_veto`).
    _order_veto = {}

    # LANA'S AID: the board reading for the RECOVERY (the TO_HAND context).
    # `_lana_plan` says how much Grass the field can use and whether any of it unlocks
    # an attack today; `_lana_grass_order` numbers the menu's Grass options
    # (0, 1, 2...) so that only the FIRST `demanda` ones get the high band: the
    # scores are computed per card, so without the ordinal the 4 copies of Grass
    # would tie and sweep the menu even if the board could only use one.
    _lana_plan = None
    _lana_grass_order = {}
    if (select.effect is not None and select.effect.id == Lanas_Aid
            and context == SelectContext.TO_HAND):
        _lana_plan = _grass_plan(my_state, state, field_counts, hand_counts,
                                     cap=select.maxCount or 1,
                                     can_switch=can_switch,
                                     abilities_off=meowth_ability_lock)
        _lana_n = 0
        for _lana_i, _lana_o in enumerate(select.option):
            if _lana_o.type != OptionType.CARD:
                continue
            _lana_c = get_card(obs, _lana_o.area, _lana_o.index,
                               getattr(_lana_o, 'playerIndex', my_index))
            if _lana_c is not None and _lana_c.id == Basic_Grass_Energy:
                _lana_grass_order[_lana_i] = _lana_n
                _lana_n += 1

    scores = []
    # The scoring context: it is built ONCE, not per option. It is populated
    # from locals() because some of these variables are only bound in certain
    # branches of the turn; and from globals() because some functions and tables the
    # chain consults are still defined at module level in main.py.
    _tcp = ScoringCtx()
    _loc = {**globals(), **locals()}
    for _field in ScoringCtx.__dataclass_fields__:
        if _field in _loc:
            setattr(_tcp, _field, _loc[_field])
    for o in select.option:
        score = 0

        score = score_option(_tcp, o, score)
        if score is _SALTAR:
            continue

        scores.append(score)

    # The context is populated from `locals()`, not with explicit kwargs: some
    # of these variables are only bound in certain branches (`_b`, `i`, ...). Passing them
    # by hand would force their evaluation and give a NameError precisely on the paths where
    # the original code does not even read them -- the split itself would invent a
    # failure that does not exist. Whatever is not bound stays as None, and the same
    # guard that stopped it being read before still stops it.
    _tc = TurnCtx()
    _locales = locals()
    for _field in TurnCtx.__dataclass_fields__:
        if _field in _locales:
            setattr(_tc, _field, _locales[_field])
    return finalizar(_tc)
