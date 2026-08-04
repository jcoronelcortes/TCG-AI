"""Disrupting the opponent's hand: Xerosic's Machinations and Unfair Stamp.

They live TOGETHER on purpose: the ordering rule -- Xerosic BEFORE the Stamp,
because the Stamp leaves the opponent at 2 cards either way and the only thing
the order buys is the cards Xerosic sends to the discard FOREVER -- makes each
scorer consult the other. Separating them produces a circular import.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.calc.board import _active_of
from ptcg.cards.ids import Alakazam_ex, Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Bug_Catching_Set, Chikorita, Dipplin, Fezandipiti_ex, Forest_of_Vitality, Hydrapple_ex, Lillie_Determination, Meganium, Meowth_ex, Night_Stretcher, Poke_Pad, SCORE_VETO, STAMP_MAX_HAND_SACRIFICADA, STAMP_MIN_OP_HAND, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Unfair_Stamp, XEROSIC_SCORE_ALAKAZAM, XEROSIC_SCORE_GENERIC, XEROSIC_SCORE_LAST_RESORT, XEROSIC_SCORE_SOBRE_BOSS, XEROSIC_STAMP_ORDEN_MIN_OP_HAND, Xerosic_Machinations
from ptcg.state.zones import ZONE_DECK
from ptcg.engine.context import DecisionContext
from ptcg.engine.rules import _Adjustment, _FixedRule, _resolve_with_trace


def _stamp_worth_playing(op_hand_count, my_hand_len) -> bool:
    """Card rule for Unfair Stamp (user, August 2026): the Stamp is only played
    if it DISRUPTS the opponent (opposing hand >= `STAMP_MIN_OP_HAND`, because
    it leaves them at 2) or if the REFILL is cheap (we sacrifice <=
    `STAMP_MAX_HAND_SACRIFICADA` cards, which is the hand WITHOUT the Stamp
    itself). See the constants block for the full reasoning.

    It holds for ANY opposing deck: the card behaves the same in every matchup,
    so no whitelist enters here.

    With `None` (a caller without that datum at hand) it returns True: the rule
    only SUBTRACTS plays, it never invents one.
    """
    if op_hand_count is None or my_hand_len is None:
        return True
    return (op_hand_count >= STAMP_MIN_OP_HAND
            or max(0, my_hand_len - 1) <= STAMP_MAX_HAND_SACRIFICADA)


def _stamp_pendiente(c) -> bool:
    """The Stamp is PLAYABLE and also DESERVES to be played this turn.

    The SINGLE source of the ordering vetoes that step aside for it (Boss's,
    Lillie's, Lana's, Dawn, Xerosic, the Meowth -> Last-Ditch chain and the
    Fezandipiti ability). It used to be enough that "we got knocked out + the
    Stamp is still in hand", but ever since `_sello_merece_jugarse` can VETO the
    Stamp, that gate alone would have paralysed the turn: the way was given to a
    card that was no longer going to be played. By sharing the predicate, when
    the Stamp waits (opposing hand <= 2 and our own hand large) the Supporters
    carry on as normal -- and if our hand drops below 5 by playing items, the
    Stamp becomes available again in the same turn."""
    return (c.ko_last_turn
            and c.hand_counts.get(Unfair_Stamp, 0) >= 1
            and _stamp_worth_playing(c.op_hand_count, c.my_hand_len))


def _us_pokemon_jugable(c):
    if c.bench_count >= 5:
        return False
    h, f = c.hand_counts, c.field_counts
    if (h.get(Chikorita, 0) >= 1 and
            f.get(Chikorita, 0) + f.get(Bayleef, 0) + f.get(Meganium, 0) == 0):
        return True
    if (h.get(Applin, 0) >= 1 and
            f.get(Applin, 0) + f.get(Dipplin, 0) == 0):
        return True
    if (h.get(Teal_Mask_Ogerpon_ex, 0) >= 1 and
            f.get(Teal_Mask_Ogerpon_ex, 0) < 2):
        return True
    if h.get(Tapu_Bulu, 0) >= 1 and f.get(Tapu_Bulu, 0) == 0:
        return True
    if (h.get(Meowth_ex, 0) >= 1 and f.get(Meowth_ex, 0) == 0
            and not c.ko_last_turn):
        return True
    if h.get(Fezandipiti_ex, 0) >= 1 and f.get(Fezandipiti_ex, 0) == 0:
        return True
    return False


def _us_evo_jugable(c):
    h, f = c.hand_counts, c.field_counts
    if h.get(Meganium, 0) >= 1 and f.get(Bayleef, 0) >= 1 and not c.meganium_in_play:
        return True
    if h.get(Bayleef, 0) >= 1 and f.get(Chikorita, 0) >= 1:
        return True
    if h.get(Hydrapple_ex, 0) >= 1 and f.get(Dipplin, 0) >= 1:
        return True
    if h.get(Dipplin, 0) >= 1 and f.get(Applin, 0) >= 1:
        return True
    return False


def _us_item_jugable(c):
    if c.itchy_pollen_active:
        return False
    h = c.hand_counts
    return (h.get(Bug_Catching_Set, 0) >= 1
            or (h.get(Ultra_Ball, 0) >= 1 and c.my_hand_len >= 3)
            or h.get(Night_Stretcher, 0) >= 1
            or h.get(Poke_Pad, 0) >= 1)


def _us_bonus_matchup(c):
    if c.op_is_alakazam_deck:
        return 400
    if c.op_is_control_deck or c.op_is_slowking_deck:
        return 350
    if c.op_is_gardevoir_deck:
        return 300
    if c.op_is_zoroark_deck:
        return 250
    return 0


def _xr_before_the_stamp(c):
    """Is Xerosic's Machinations played BEFORE Unfair Stamp?

    Both fit in the SAME turn -- the Stamp is an ITEM (ACE SPEC) and Xerosic a
    Supporter -- so no card is being chosen here: the ORDER is. And the two do
    different things to the opponent's hand:

      * Unfair Stamp **SHUFFLES it back into their deck** and gives them 2 cards.
      * Xerosic **DISCARDS** it down to 3.

    Playing Xerosic FIRST, the opponent loses `op_hand - 3` cards forever and the
    Stamp still leaves them at 2: the same board at the end of the turn, with
    half the opposing deck in the discard. The other way around, those cards go
    back to the deck and the Stamp also shuffles away OUR Xerosic (registro_008
    step 90 vs Alakazam: the Stamp took Boss's and Xerosic, and only one was
    recovered by luck).

    The cost is real -- the Supporter slot is spent BEFORE the Stamp's refill, so
    the 5 new cards can no longer pay for another Supporter -- hence the
    `XEROSIC_STAMP_ORDEN_MIN_OP_HAND` threshold: only when what gets burned is
    worth more than a whole hand. It revokes itself: as soon as Xerosic is
    played, `supporterPlayed` becomes True and the Stamp recovers its normal
    score in the same turn.
    """
    return (c.ko_last_turn
            and c.hand_counts.get(Unfair_Stamp, 0) >= 1
            and c.hand_counts.get(Xerosic_Machinations, 0) >= 1
            and not c.state.supporterPlayed
            and c.op_hand_count >= XEROSIC_STAMP_ORDEN_MIN_OP_HAND)


_RULES_STAMP_PLAY = [
    # CARD RULE (user, August 2026): without disruption (opposing hand <= 2) or a
    # cheap refill (we sacrifice > 4 cards) the Stamp is NOT played. It is not an
    # ordering veto: no other card of the turn revokes it, it only changes if the
    # board changes (e.g. our own hand drops by playing items). See
    # `_sello_merece_jugarse`.
    _FixedRule("sin_disrupcion_ni_refresco",
               lambda c: not _stamp_worth_playing(c.op_hand_count,
                                                   c.my_hand_len),
               lambda c: SCORE_VETO),
    # ORDERING veto, not a value one (user, jul 2026): with a giant opposing hand,
    # Xerosic goes first and the Stamp waits for the same turn. The Xerosic is
    # required to be REALLY going to be played (a score above last resort): if any
    # of its guards knocks it down to `XEROSIC_SCORE_LAST_RESORT` -- e.g.
    # `alakazam_cede_a_gusteo_ganador`, where a Boss's decides the turn -- the
    # Stamp yields to nobody and is played normally. See `_xr_antes_del_sello`.
    _FixedRule("cede_el_orden_a_xerosic",
               lambda c: (_xr_before_the_stamp(c)
                          and _score_xerosic_play(c)
                          > XEROSIC_SCORE_LAST_RESORT),
               lambda c: SCORE_VETO),
    # Rule (user): with Lillie's in hand and the opponent at <= 3 cards, do NOT
    # play the Stamp: its disruption adds little and refilling OUR hand pays
    # more (the Stamp would shuffle the Lillie's away; mutually exclusive plays).
    _FixedRule("cede_a_lillie_mano_rival_corta",
               lambda c: (c.hand_counts.get(Lillie_Determination, 0) >= 1
                          and c.op_hand_count <= 3
                          and not c.state.supporterPlayed),
               lambda c: SCORE_VETO),
    # The base value rises the LESS alternative use the hand has this turn
    # (Pokemon/evo < item < energy/stadium < nothing = 7500).
    _FixedRule("mano_con_pokemon_o_evo",
               lambda c: _us_pokemon_jugable(c) or _us_evo_jugable(c),
               lambda c: 2000),
    _FixedRule("mano_con_item",
               _us_item_jugable,
               lambda c: 2500),
    _FixedRule("mano_con_energia_o_estadio",
               lambda c: ((c.hand_counts[Basic_Grass_Energy] >= 1
                           and not c.state.energyAttached)
                          or (c.hand_counts.get(Forest_of_Vitality, 0) >= 1
                              and not c.forest_in_play)),
               lambda c: 3000),
]


# Every adjustment requires `s > 0`: they are bonuses to the value of a play that
# IS GOING TO HAPPEN, they must not resurrect a veto. Without the guard, a vetoed
# Stamp (SCORE_VETO = -1) came out of the resolver at +399 just from
# `bonus_matchup` vs Alakazam -- which is exactly the matchup where the ordering
# veto `cede_el_orden_a_xerosic` lives.
_AJUSTES_STAMP_PLAY = [
    _Adjustment("turno_temprano",
            lambda c, s: s > 0 and c.state.turn <= 4,
            lambda c, s: s + 300),
    _Adjustment("vamos_perdiendo_premios",
            lambda c, s: s > 0 and c.my_prize > c.op_prize + 1,
            lambda c, s: s + 200),
    _Adjustment("bonus_matchup",
            lambda c, s: s > 0 and _us_bonus_matchup(c) != 0,
            lambda c, s: s + _us_bonus_matchup(c)),
    _Adjustment("aggro_y_perdiendo",
            lambda c, s: (s > 0
                          and (c.op_is_aggro_deck or c.op_is_beedrill_deck)
                          and c.my_prize > c.op_prize),
            lambda c, s: s + 350),
]


def _score_unfair_stamp_play(ctx: DecisionContext) -> int:
    """Scores playing Unfair Stamp (hand refill). Body migrated to the RULES
    ENGINE (phase 4): rules and comments in _REGLAS_STAMP_PLAY."""
    return _resolve_with_trace("stamp->play", _RULES_STAMP_PLAY,
                               _AJUSTES_STAMP_PLAY, ctx, default=7500)


def _xr_letal_proyectado(c):
    """EARLY anti-Alakazam trigger: with an opposing hand of 4-5, if the
    Alakazam is ALREADY active and its projected Powerful Hand (20 x (hand + 2))
    KNOCKS OUT our active, cap the hand NOW (waiting for hand >= 6 gives away
    the KO)."""
    if not (c.op_is_alakazam_deck and 4 <= c.op_hand_count < 6
            and c.my_state.active and c.my_state.active[0] is not None):
        return False
    op_act = _active_of(c.op_state)
    return (op_act is not None and op_act.id == Alakazam_ex
            and 20 * (c.op_hand_count + 2)
                >= (c.my_state.active[0].hp or 0))


def _xr_copia_respaldo(c):
    """A 2nd copy of Xerosic reachable (hand or deck): the 1st is played EARLY
    (opposing hand >= 4); the second late cap is destructive. Without a backup,
    conservative timing (user, july 2026: -1 Poke Pad +1 Xerosic)."""
    return (c.hand_counts.get(Xerosic_Machinations, 0) >= 2
            or c.cards_in_deck.get(
                Xerosic_Machinations, {}).get(ZONE_DECK, 0) >= 1)


def _xr_gate_alakazam(c):
    """vs Alakazam (the card's reason to exist): opposing hand >= 6 (Powerful
    Hand 120+), a projected KO on our active, or a backup copy with the opposing
    hand already growing (>= 4)."""
    return (c.op_is_alakazam_deck
            and (c.op_hand_count >= 6 or _xr_letal_proyectado(c)
                 or (_xr_copia_respaldo(c) and c.op_hand_count >= 4)))


_RULES_XEROSIC_PLAY = [
    _FixedRule("supporter_ya_jugado",
               lambda c: c.state.supporterPlayed,
               lambda c: SCORE_VETO),
    # No effect if the opposing hand is already <= 3 (e.g. after an Unfair Stamp
    # this same turn): do not burn the Supporter for nothing.
    _FixedRule("mano_rival_ya_corta",
               lambda c: c.op_hand_count <= 3,
               lambda c: SCORE_VETO),
    # With a KO last turn and the Stamp in hand, the Stamp goes FIRST (it is an
    # Item and re-shuffles OUR hand). Same gate as Boss's/Lana's/Dawn.
    # EXCEPTION (user, jul 2026): with a GIANT opposing hand the order is
    # reversed -- the Stamp only returns those cards to the deck, Xerosic
    # DISCARDS them, and both fit in the same turn. See `_xr_antes_del_sello`;
    # the other side of the change is `cede_el_orden_a_xerosic` in the Stamp.
    _FixedRule("cede_a_unfair_stamp",
               lambda c: (_stamp_pendiente(c)
                          and not _xr_before_the_stamp(c)),
               lambda c: SCORE_VETO),
    # Boss's Orders only takes priority when it WINS the game (user,
    # registro_006 step 85): there Xerosic yields and the Boss's (WIN_NOW 20000)
    # finishes. It used to yield to `boss_win_via_bench` too (a lethal gust that
    # only takes ONE prize), and with that the agent traded capping the opposing
    # hand for a single prize.
    _FixedRule("alakazam_cede_a_gusteo_ganador",
               lambda c: (_xr_gate_alakazam(c) and c.win_via_boss_gust
                          and c.hand_counts.get(Boss_Orders, 0) >= 1),
               lambda c: XEROSIC_SCORE_LAST_RESORT),
    # No attack and a short hand: development (Lillie's) is worth more than
    # disruption this turn.
    _FixedRule("alakazam_cede_a_lillie_mano_corta",
               lambda c: (_xr_gate_alakazam(c) and c.active_cant_attack
                          and sum(c.hand_counts.values()) <= 3
                          and c.hand_counts.get(Lillie_Determination, 0) >= 1),
               lambda c: XEROSIC_SCORE_LAST_RESORT),
    # With the opposing hand already MINIMAL (<= 4: capping only takes 1 card away)
    # Xerosic's disruption value is marginal (Powerful Hand drops by 20 damage); if
    # we have Lillie's Determination in hand (refill + development, especially when
    # we searched for it with Meowth ex and it is therefore the planned play), that
    # is worth more. It yields the turn's Supporter to Lillie's (user, registro_002
    # step 17 vs Alakazam, LOST: turn 2, opponent with 4 cards, the agent played
    # Xerosic instead of the Lillie's it had just fetched with Meowth ex). Different
    # from `alakazam_cede_a_lillie_mano_corta` (which gates on OUR hand <= 3 + an
    # active that cannot attack): here the gate is the minimal OPPOSING hand, with
    # no condition on ours. It goes BEFORE
    # `alakazam_prioridad_sobre_boss`/`_capar_mano` because those would fire
    # 7000/5900 even when only 1 card is taken away.
    _FixedRule("alakazam_cede_a_lillie_mano_rival_minima",
               lambda c: (_xr_gate_alakazam(c)
                          and c.op_hand_count <= 4
                          and c.hand_counts.get(Lillie_Determination, 0) >= 1),
               lambda c: XEROSIC_SCORE_LAST_RESORT),
    # PRIORITY OVER BOSS'S (user, registro_006 step 85 vs Alakazam, LOST): with
    # Boss's Orders in hand and the opponent at 16 cards, the agent played Boss's
    # (a 2-prize gust, 6800) instead of Xerosic (6200) and left the opposing hand
    # untouched: their Powerful Hand (20 x card in their hand) kept hitting for
    # 320 and swept the board. Capping the hand is worth more than any gust that
    # does NOT win the game; the WINNING gust already returned above (rule
    # `alakazam_cede_a_gusteo_ganador`). It is scored above
    # BOSS_SCORE_GUST_2PRIZE (6800), which was the band that used to win, and
    # below BOSS_SCORE_WIN_NOW (20000).
    _FixedRule("alakazam_prioridad_sobre_boss",
               lambda c: (_xr_gate_alakazam(c)
                          and c.hand_counts.get(Boss_Orders, 0) >= 1),
               lambda c: (XEROSIC_SCORE_SOBRE_BOSS
                          + min(300, 50 * (c.op_hand_count - 4))
                          + c.supporter_boost)),
    # Capping Powerful Hand: it scales with the opposing hand (5900-6200). It beats
    # a hydra-charged Lillie's (5800); below WIN_NOW/GUST_2PRIZE and the pivots.
    _FixedRule("alakazam_capar_mano",
               _xr_gate_alakazam,
               lambda c: (XEROSIC_SCORE_ALAKAZAM
                          + min(300, 50 * (c.op_hand_count - 4))
                          + c.supporter_boost)),
    # Generic: taking 4+ cards away is real value, but without Powerful Hand it goes
    # below a useful Lillie's/Lana's/Boss's. Only with an opposing hand >= 7.
    _FixedRule("generico_mano_muy_grande",
               lambda c: c.op_hand_count >= 7,
               lambda c: XEROSIC_SCORE_GENERIC + c.supporter_boost),
    # default: last resort (opposing hand 4-6 without the Alakazam matchup).
]


def _score_xerosic_play(ctx: DecisionContext) -> int:
    """Scores playing Xerosic's Machinations (id 1197): the opponent discards
    down to 3 cards. It is in the deck because of the Alakazam matchup (Powerful
    Hand does 20 per card in their hand). Body migrated to the RULES ENGINE
    (phase 4)."""
    return _resolve_with_trace("xerosic->play", _RULES_XEROSIC_PLAY, [],
                               ctx, default=XEROSIC_SCORE_LAST_RESORT)

__all__ = [
    '_xr_before_the_stamp',
    '_xr_letal_proyectado',
    '_xr_copia_respaldo',
    '_xr_gate_alakazam',
    '_score_xerosic_play',
    '_RULES_XEROSIC_PLAY',
    '_stamp_worth_playing',
    '_stamp_pendiente',
    '_us_pokemon_jugable',
    '_us_evo_jugable',
    '_us_item_jugable',
    '_us_bonus_matchup',
    '_score_unfair_stamp_play',
    '_RULES_STAMP_PLAY',
    '_AJUSTES_STAMP_PLAY',
]
