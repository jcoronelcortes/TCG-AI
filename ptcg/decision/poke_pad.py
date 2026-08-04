"""Poke Pad: which Pokemon is worth searching for.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.engine.rules import _FixedRule
from ptcg.state.agent_state import AGENT_STATE
from ptcg.cards.ids import Applin, Bayleef, Chikorita, Dipplin, Meganium
from ptcg.cards.ids import Applin, Bayleef, Chikorita, Dipplin, Hydrapple_ex, Meganium, SCORE_VETO, Tapu_Bulu
from ptcg.state.zones import ZONE_DECK
from ptcg.engine.context import DecisionContext
from ptcg.engine.rules import _Adjustment, _FixedRule, _resolve_with_trace


_PP_NON_RULEBOX_IDS = (Chikorita, Bayleef, Meganium, Applin, Dipplin,
                       Tapu_Bulu)


def _pp_buscables(c):
    """Pokemon WITHOUT a Rule Box that still have copies in the deck (the only
    thing Poke Pad can search for: it excludes the Hydrapple ex line and the
    other ex)."""
    cards = c.cards_in_deck
    return {cid: cards[cid][ZONE_DECK] for cid in _PP_NON_RULEBOX_IDS
            if cid in cards and cards[cid][ZONE_DECK] > 0}


def _pp_es_t1(c):
    return ((c.state.turn == 1 and c.we_go_first)
            or (c.state.turn == 2 and not c.we_go_first))


def _pp_budew_dump(c):
    """The opponent opens with Budew ACTIVE and we go second: its Itchy Pollen
    blocks items on our next turn; this first turn is the ONLY one for using
    items -> play ALL the Poke Pads now."""
    return (c.budew_op_index == 0
            and c.state.turn == 2 and not c.we_go_first)


def _v_pp_t1(c):
    s = _pp_buscables(c)
    tiene_applin = (c.field_counts.get(Applin, 0) >= 1
                    or c.hand_counts.get(Applin, 0) >= 1)
    tiene_chik = (c.field_counts.get(Chikorita, 0) >= 1
                  or c.hand_counts.get(Chikorita, 0) >= 1)
    if not tiene_applin and Applin in s and c.bench_count < 5:
        return 12800
    if not tiene_chik and Chikorita in s and c.bench_count < 5:
        return 12600
    if _pp_budew_dump(c):
        return 12400
    return SCORE_VETO


def _pp_evo_value(c):
    """Best evolution enabled THIS turn by a Poke Pad search (0 = none). The
    evolvable snapshot is the start-of-turn one when there is no Forest."""
    s = _pp_buscables(c)
    h, f = c.hand_counts, c.field_counts
    # It does NOT use `_evolvable_counts`: MEASURED AND REVERTED (see its scope note).
    evolvable = (c.field_at_turn_start
                 if (not c.forest_in_play and c.field_at_turn_start) else f)
    v = 0
    if (Meganium in s and not c.meganium_in_play
            and h.get(Meganium, 0) == 0):
        if evolvable.get(Bayleef, 0) >= 1:
            v = max(v, 1200)
        elif (c.forest_in_play and evolvable.get(Chikorita, 0) >= 1
                and h.get(Bayleef, 0) >= 1):
            v = max(v, 1100)
    if (Bayleef in s and not c.meganium_in_play
            and h.get(Bayleef, 0) == 0):
        if evolvable.get(Chikorita, 0) >= 1:
            v = max(v, 1000)
            if c.forest_in_play and h.get(Meganium, 0) >= 1:
                v = max(v, 1150)
    if Dipplin in s and h.get(Dipplin, 0) == 0:
        if evolvable.get(Applin, 0) >= 1:
            v = max(v, 950)
            if c.forest_in_play and h.get(Hydrapple_ex, 0) >= 1:
                v = max(v, 1100)
    return v


def _pp_evolution_pending_search(c):
    """Some pre-evolution in play whose evolution is NOT in hand but IS in the
    deck: a search enables it (do not cut off because the bench is full)."""
    h, f, cards = c.hand_counts, c.field_counts, c.cards_in_deck
    return ((f.get(Chikorita, 0) >= 1 and h.get(Bayleef, 0) == 0
             and cards.get(Bayleef, {}).get(ZONE_DECK, 0) > 0)
            or (f.get(Bayleef, 0) >= 1 and h.get(Meganium, 0) == 0
                and cards.get(Meganium, {}).get(ZONE_DECK, 0) > 0)
            or (f.get(Applin, 0) >= 1 and h.get(Dipplin, 0) == 0
                and cards.get(Dipplin, {}).get(ZONE_DECK, 0) > 0))


_RULES_PP_PLAY = [
    _FixedRule("nothing_to_search_for",
               lambda c: not _pp_buscables(c),
               lambda c: SCORE_VETO),
    _FixedRule("first_turn",
               _pp_es_t1,
               _v_pp_t1),
    _FixedRule("evolution_this_turn",
               lambda c: _pp_evo_value(c) > 0,
               lambda c: (23000 if _pp_evo_value(c) >= 1100
                          else (22000 if _pp_evo_value(c) >= 900
                                else 20000))),
    _FixedRule("secure_chikorita",
               lambda c: (Chikorita in _pp_buscables(c)
                          and not c.meganium_in_play
                          and (c.field_counts.get(Chikorita, 0)
                               + c.field_counts.get(Bayleef, 0)
                               + c.field_counts.get(Meganium, 0)) == 0
                          and c.hand_counts.get(Chikorita, 0) == 0
                          and c.bench_count < 5),
               lambda c: 12800),
    _FixedRule("secure_applin",
               lambda c: (Applin in _pp_buscables(c) and c.bench_count < 5),
               lambda c: 12600),
]


_AJUSTES_PP_PLAY = [
    # Search for Tapu Bulu as a 1-prize sacrifice (pivot vs Lucario).
    _Adjustment("lucario_tapu_sacrifice",
            lambda c, s: (c.lucario_sac_pivot
                          and Tapu_Bulu in _pp_buscables(c)
                          and c.field_counts.get(Tapu_Bulu, 0) == 0
                          and c.hand_counts.get(Tapu_Bulu, 0) == 0
                          and c.bench_count < 5),
            lambda c, s: 13000),
    # Bench full and no pre-evolution to evolve WITH A SEARCH: keep the
    # resource (Poke Pad excludes the Dipplin->Hydrapple ex line).
    _Adjustment("full_bench_keep_it",
            lambda c, s: (c.bench_count >= 5
                          and not _pp_evolution_pending_search(c)
                          and s > 0 and not _pp_budew_dump(c)),
            lambda c, s: SCORE_VETO),
]


def _score_poke_pad_play(ctx: DecisionContext) -> int:
    """Scores playing Poke Pad (searches for a Pokemon WITHOUT a Rule Box). It
    prioritises enabling an evolution THIS turn; failing that, securing basics;
    with a full bench and nothing to evolve, it keeps the resource. Body
    migrated to the RULES ENGINE (phase 4)."""
    return _resolve_with_trace("pokepad->play", _RULES_PP_PLAY,
                               _AJUSTES_PP_PLAY, ctx, default=SCORE_VETO)


class _CtxPPFetch:
    """Ctx of the Poke Pad fetch: candidate card + values derived from the mode."""

    def __init__(self, card_id, hand_counts, field_counts, bench_count,
                 state):
        self.card_id = card_id
        self.hand = hand_counts
        self.campo = field_counts
        self.bench_count = bench_count
        self.first_turn = ((state.turn == 1 and AGENT_STATE.we_go_first) or
                           (state.turn == 2 and not AGENT_STATE.we_go_first))
        self.have_chik = (field_counts.get(Chikorita, 0) >= 1 or
                          hand_counts.get(Chikorita, 0) >= 1)
        self.have_bay = (field_counts.get(Bayleef, 0) >= 1 or
                         hand_counts.get(Bayleef, 0) >= 1)
        self.have_applin = (field_counts.get(Applin, 0) >= 1 or
                            hand_counts.get(Applin, 0) >= 1)
        self.have_dipplin = (field_counts.get(Dipplin, 0) >= 1 or
                             hand_counts.get(Dipplin, 0) >= 1)
        has_evo = False
        if not AGENT_STATE.meganium_in_play and hand_counts.get(Meganium, 0) == 0:
            if field_counts.get(Bayleef, 0) >= 1:
                has_evo = True
            elif (AGENT_STATE.forest_in_play and field_counts.get(Chikorita, 0) >= 1 and
                  hand_counts.get(Bayleef, 0) >= 1):
                has_evo = True
        if (not AGENT_STATE.meganium_in_play and hand_counts.get(Bayleef, 0) == 0 and
                field_counts.get(Chikorita, 0) >= 1):
            has_evo = True
        if (hand_counts.get(Dipplin, 0) == 0 and
                field_counts.get(Applin, 0) >= 1):
            has_evo = True
        self.has_evo = has_evo


_RULES_PP_FETCH = [
    # (1) First turn: put down the basics of both lines before anything else.
    _FixedRule("t1_applin",
               lambda c: (c.first_turn and c.card_id == Applin
                          and not c.have_applin),
               lambda c: 2000),
    _FixedRule("t1_chikorita",
               lambda c: (c.first_turn and c.card_id == Chikorita
                          and not c.have_chik),
               lambda c: 1900),
    _FixedRule("t1_otro",
               lambda c: c.first_turn,
               lambda c: 10),
    # (2) Direct evolution of a Pokemon on the current board.
    _FixedRule("evo_meganium",
               lambda c: (c.has_evo and c.card_id == Meganium
                          and not AGENT_STATE.meganium_in_play
                          and c.hand.get(Meganium, 0) == 0
                          and c.campo.get(Bayleef, 0) >= 1),
               lambda c: 1000),
    _FixedRule("evo_meganium_rush",
               lambda c: (c.has_evo and c.card_id == Meganium
                          and not AGENT_STATE.meganium_in_play
                          and c.hand.get(Meganium, 0) == 0
                          and AGENT_STATE.forest_in_play
                          and c.campo.get(Chikorita, 0) >= 1
                          and c.hand.get(Bayleef, 0) >= 1),
               lambda c: 900),
    _FixedRule("evo_bayleef_rush",
               lambda c: (c.has_evo and c.card_id == Bayleef
                          and not AGENT_STATE.meganium_in_play
                          and c.hand.get(Bayleef, 0) == 0
                          and c.campo.get(Chikorita, 0) >= 1
                          and AGENT_STATE.forest_in_play
                          and c.hand.get(Meganium, 0) >= 1),
               lambda c: 950),
    _FixedRule("evo_bayleef",
               lambda c: (c.has_evo and c.card_id == Bayleef
                          and not AGENT_STATE.meganium_in_play
                          and c.hand.get(Bayleef, 0) == 0
                          and c.campo.get(Chikorita, 0) >= 1),
               lambda c: 850),
    _FixedRule("evo_dipplin_rush",
               lambda c: (c.has_evo and c.card_id == Dipplin
                          and c.hand.get(Dipplin, 0) == 0
                          and c.campo.get(Applin, 0) >= 1
                          and AGENT_STATE.forest_in_play
                          and c.hand.get(Hydrapple_ex, 0) >= 1),
               lambda c: 920),
    _FixedRule("evo_dipplin",
               lambda c: (c.has_evo and c.card_id == Dipplin
                          and c.hand.get(Dipplin, 0) == 0
                          and c.campo.get(Applin, 0) >= 1),
               lambda c: 800),
    _FixedRule("evo_otro",
               lambda c: c.has_evo,
               lambda c: 10),
    # (3) Fallback: complete lines from hand.
    _FixedRule("fb_bayleef",
               lambda c: (c.card_id == Bayleef and not AGENT_STATE.meganium_in_play
                          and c.have_chik and not c.have_bay),
               lambda c: 850),
    _FixedRule("fb_dipplin",
               lambda c: (c.card_id == Dipplin and c.have_applin
                          and not c.have_dipplin),
               lambda c: 800),
    _FixedRule("fb_meganium",
               lambda c: (c.card_id == Meganium and not AGENT_STATE.meganium_in_play
                          and c.hand.get(Meganium, 0) == 0 and c.have_bay),
               lambda c: 700),
    _FixedRule("fb_chikorita",
               lambda c: (c.card_id == Chikorita and not AGENT_STATE.meganium_in_play
                          and c.campo.get(Chikorita, 0)
                          + c.campo.get(Bayleef, 0)
                          + c.campo.get(Meganium, 0) < 1
                          and c.hand.get(Chikorita, 0) < 1
                          and c.bench_count < 5),
               lambda c: 800),
    _FixedRule("fb_applin",
               lambda c: c.card_id == Applin and c.bench_count < 5,
               lambda c: 650),
]

__all__ = [
    '_pp_buscables',
    '_pp_es_t1',
    '_pp_budew_dump',
    '_v_pp_t1',
    '_pp_evo_value',
    '_pp_evolution_pending_search',
    '_score_poke_pad_play',
    '_RULES_PP_PLAY',
    '_AJUSTES_PP_PLAY',
    '_PP_NON_RULEBOX_IDS',
    '_CtxPPFetch',
    '_RULES_PP_FETCH',
]
