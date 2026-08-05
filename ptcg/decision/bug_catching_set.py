"""Bug Catching Set: searching for Bug Pokemon.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.engine.rules import _resolve_with_trace
from ptcg.engine.context import DecisionContext
from ptcg.state.zones import ZONE_DECK
from ptcg.cards.tables import card_table
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Chikorita, Dipplin, Hydrapple_ex, Meganium, Teal_Mask_Ogerpon_ex
from cg.api import CardType, EnergyType
from ptcg.cards.ids import Basic_Grass_Energy, SCORE_BELIEF_DIG_ENERGY, SCORE_VETO, Teal_Mask_Ogerpon_ex
from ptcg.engine.rules import _Adjustment, _FixedRule


def _v_bcs_base(w):
    v = 10500
    if (w.field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
            and w.hand_counts[Basic_Grass_Energy] >= 1):
        v -= 100
    return v


_RULES_BCS_PLAY = [
    _FixedRule("no_eligible_cards_in_deck",
               lambda w: w.elegibles == 0,
               lambda w: SCORE_VETO),
    # Deck-out brake (step 4 of the jul 2026 plan; autopsy v2 vs crustle: 4/19
    # losses BY DECKOUT and a tail of deckCount 0-5 at t20+, the item pending
    # from a7df1ce). With a critical deck -- same familiar threshold as the
    # Lillie's brake (<=10), here <=8 -- Bug Catching Set thins the deck by 1-2
    # cards: pure lost clock against a stall opponent. DRY ENERGY EXCEPTION
    # (the one that motivated the BCS of the anti-mill plan vs Comfey, b393426):
    # with no Grass in hand and the turn's attachment still pending, digging out
    # the energy enables attacking TODAY, and that is worth more than the clock.
    _FixedRule("deckout_brake_critical_deck",
               lambda w: (getattr(w.my_state, 'deckCount', 60) <= 8
                          and not (w.hand_counts[Basic_Grass_Energy] == 0
                                   and not w.state.energyAttached)),
               lambda w: SCORE_VETO),
    _FixedRule("base",
               lambda w: True,
               _v_bcs_base),
]


_AJUSTES_BCS_PLAY = [
    _Adjustment("probability_of_finding",
            lambda w, s: s > 0,
            lambda w, s: s + (800 if w.p_find >= 0.9
                              else (500 if w.p_find >= 0.7
                                    else (200 if w.p_find >= 0.5
                                          else -300)))),
    _Adjustment("high_value_pieces",
            lambda w, s: s > 0 and w.high_value >= 1,
            lambda w, s: s + (600 if w.high_value >= 3
                              else (400 if w.high_value >= 2 else 200))),
    _Adjustment("incomplete_lines",
            lambda w, s: s > 0 and (not w.meganium_in_play
                                    or not w.has_hydrapple),
            lambda w, s: s + (300 if (not w.meganium_in_play
                                      and not w.has_hydrapple) else 150)),
    _Adjustment("dry_energy",
            lambda w, s: (s > 0 and w.hand_counts[Basic_Grass_Energy] == 0
                          and not w.state.energyAttached),
            lambda w, s: s + 200),
    _Adjustment("dig_energy_by_belief",
            lambda w, s: (s > 0 and w.hand_counts[Basic_Grass_Energy] == 0
                          and not w.state.energyAttached
                          and w.energy_starved_low_draw
                          and w.energy_in_deck > 0),
            lambda w, s: s + SCORE_BELIEF_DIG_ENERGY),
    # With Poke Pad playable (and without Itchy Pollen), BCS yields: cap 9000.
    _Adjustment("cap_if_pokepad_playable",
            lambda w, s: (w.pp_playable_in_hand
                          and not w.itchy_pollen_active and s > 9000),
            lambda w, s: 9000),
]


class _CtxBCS:
    """DecisionContext wrapper for Bug Catching Set: it precomputes the deck
    statistics (eligible cards, high-value pieces, p_find over 7 looks) only
    once; everything else is delegated via __getattr__."""

    def __init__(self, ctx):
        self.c = ctx
        f = ctx.field_counts
        grass, energy, high_value = 0, 0, 0
        for cid, states in ctx.cards_in_deck.items():
            if states[ZONE_DECK] <= 0:
                continue
            copies = states[ZONE_DECK]
            cdata = card_table.get(cid)
            if cid == Basic_Grass_Energy:
                energy += copies
            elif cdata and cdata.cardType == CardType.POKEMON:
                if cdata.energyType == EnergyType.GRASS:
                    grass += copies
                    if (cid == Meganium and not ctx.meganium_in_play
                            and (f.get(Bayleef, 0) >= 1
                                 or f.get(Chikorita, 0) >= 1)):
                        high_value += copies
                    elif (cid == Hydrapple_ex and not ctx.has_hydrapple
                            and (f.get(Dipplin, 0) >= 1
                                 or f.get(Applin, 0) >= 1)):
                        high_value += copies
                    elif (cid == Bayleef and not ctx.meganium_in_play
                            and f.get(Chikorita, 0) >= 1):
                        high_value += copies
                    elif (cid == Dipplin and not ctx.has_hydrapple
                            and f.get(Applin, 0) >= 1):
                        high_value += copies
                    elif (cid == Chikorita and not ctx.meganium_in_play
                            and f.get(Chikorita, 0) + f.get(Bayleef, 0)
                                + f.get(Meganium, 0) == 0):
                        high_value += copies
                    elif (cid == Applin and not ctx.has_hydrapple
                            and f.get(Applin, 0) + f.get(Dipplin, 0)
                                + f.get(Hydrapple_ex, 0) == 0):
                        high_value += copies
                    elif (cid == Teal_Mask_Ogerpon_ex
                            and f.get(Teal_Mask_Ogerpon_ex, 0) < 2):
                        high_value += copies
        self.energy_in_deck = energy
        self.elegibles = grass + energy
        self.high_value = high_value
        total = sum(v[ZONE_DECK] for v in ctx.cards_in_deck.values())
        self.deck_total = total
        if self.elegibles == 0:
            self.p_find = 0.0
        elif total <= 7:
            self.p_find = 1.0
        else:
            p_miss, remaining = 1.0, total
            for _ in range(min(7, total)):
                if remaining <= 0:
                    break
                p_miss *= (remaining - self.elegibles) / remaining
                remaining -= 1
            self.p_find = 1.0 - p_miss

    def __getattr__(self, name):
        return getattr(self.c, name)


def _score_bug_catching_set_play(ctx: DecisionContext) -> int:
    """Scores playing Bug Catching Set (look at 7 and take Grass/Energy).
    Body migrated to the RULES ENGINE (phase 4): deck statistics precomputed in
    _CtxBCS, contributions expressed as named adjustments."""
    return _resolve_with_trace("bcs->play", _RULES_BCS_PLAY,
                               _AJUSTES_BCS_PLAY, _CtxBCS(ctx), default=0)

__all__ = [
    '_v_bcs_base',
    '_RULES_BCS_PLAY',
    '_AJUSTES_BCS_PLAY',
    '_CtxBCS',
    '_score_bug_catching_set_play',
]
