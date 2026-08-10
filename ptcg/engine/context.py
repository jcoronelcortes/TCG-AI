"""DecisionContext: the snapshot of the turn the scorers receive.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from dataclasses import dataclass


# =============================================================================
# DecisionContext + extracted scorers (Priority 1 refactor)
# -----------------------------------------------------------------------------
# `agent()` is a single ~11,800-line function whose scoring loop mixes dozens of
# rules into one giant if/elif. To shrink that monolith, the scoring branches are
# being extracted into PURE `_score_*(ctx)` functions that read a
# `DecisionContext` built once per decision. Each extraction is an IDENTICAL
# behaviour refactor, verified by the test suite.
#
# State of the refactor: PoC with the Boss's Orders branch
# (`_score_boss_orders_play`). As more branches are extracted, the fields they
# need are added here; the goal is for `agent()` to end up orchestrating (build
# ctx -> map option to its scorer -> argmax) instead of containing all the logic
# inline.
@dataclass
class DecisionContext:
    """Invariant inputs of a decision (built before the scoring loop). The
    `_score_*` scorers treat it as READ ONLY."""
    # Shared state objects
    state: object
    my_state: object
    op_state: object
    hand_counts: dict
    field_counts: dict
    supp_values: dict
    cards_in_deck: dict
    field_at_turn_start: dict
    # Board / prize counts
    bench_count: int
    my_hand_len: int
    my_prize: int
    op_prize: int
    op_hand_count: int
    meganium_in_play: bool
    forest_in_play: bool
    itchy_pollen_active: bool
    has_hydrapple: bool
    watchtower_in_play: bool
    meowth_ability_lock: bool   # watchtower OR Iron Thorns active (P1.4)
    neutralization_zone_active: bool
    mega_line_active: bool
    active_needs_energy: bool
    evolve_possible_in_play: bool
    energy_starved_low_draw: bool
    pp_playable_in_hand: bool
    can_attack: bool
    best_supp_in_hand_val: int
    best_supp_in_deck_val: int
    # Matchup / opposing wall flags
    op_is_alakazam_deck: bool
    op_is_hop_deck: bool
    op_is_comfey_deck: bool
    op_active_is_dunsparce: bool
    op_has_ability_immune_active: bool
    op_has_ex_immune_active: bool
    op_has_ex_immune_bench: bool
    op_is_control_deck: bool
    op_is_slowking_deck: bool
    op_is_gardevoir_deck: bool
    op_is_zoroark_deck: bool
    op_is_aggro_deck: bool
    op_is_beedrill_deck: bool
    op_is_crustle_deck: bool
    op_is_cornerstone_deck: bool
    op_is_fire_deck: bool
    op_is_mirror: bool
    op_kang_ko_target: bool
    stadium_id: int
    # Turn flags
    ko_last_turn: bool
    our_first_turn: bool
    active_cant_attack: bool
    bdg_retreat_ko: bool
    supporter_boost: int
    we_go_first: bool
    budew_op_index: int
    budew_on_op_field: bool
    lucario_sac_pivot: bool
    win_via_boss_gust: bool
    gust_2prize_via_boss: bool
    # Boss's Orders flags (computed in evaluate_supporters / further up)
    boss_win_via_bench: bool
    boss_dodge_redirect: bool
    boss_defensive_gust: bool
    boss_deny_alakazam_line: bool
    boss_low_value_gust: bool
    boss_prize_rank: int
    boss_ko_threat_preevo: bool
    has_ready_bench_attacker: bool
    # Our ACTIVE is DOOMED (active_ko_likely): the Boss's/Lillie's rules consult it
    # so the Supporter is not spent on a prize gust when there is no relief on the
    # bench (registro_004 vs Team Rocket).
    active_ko_likely: bool
    # The opposing ACTIVE is a THREAT pre-evolution (THREAT_PREEVO_IDS) that
    # DOMINATES all of its benched copies (a life tool such as Hero's Cape, or >=
    # energies) and our active can attack it: do NOT spend Boss's gusting the weak
    # copy (registro_007 step 80 vs Archaludon: still no KO because of the Cape).
    # Default False: unit tests build the ctx directly.
    boss_active_threat_dominates: bool = False
    # The gust TRAPS their turn: with no KO available and no attack of ours this
    # turn, there is a body on their bench that cannot answer from the active spot
    # even after an attachment and cannot pay its own retreat. Bringing it up costs
    # them either the turn or the energy they attach to get it out.
    # Default False: unit tests build the ctx directly.
    boss_trap_gust: bool = False
    # A REAL opposing finisher on our active, resolved via attack_table
    # (`_op_active_attack_damage_to` >= the active's HP). The `active_ko_likely`
    # heuristic leans on `_op_best_damage_vs`, which reads the damage of an attack
    # ID (an int) and ALWAYS gives 0: against a Mega Lucario ex with 2 energies
    # (Mega Brave 270) it believed our 210 HP Ogerpon ex was not in danger. The
    # "doomed active with no relief" rules of Boss's/Lillie's use BOTH flags
    # (registro_004 t4 vs Mega Lucario).
    # Default False: unit tests build the ctx directly.
    active_doomed_real: bool = False
    # ONE Grass on the ACTIVE pays its retreat cost and enables attacking with a
    # benched body (`_grass_unlocks_active_retreat`), through the CHARGING
    # ABILITIES route: they do NOT require the turn's manual attachment to still be
    # free. Night Stretcher consumes them to know that the energy in the discard has
    # a destination (registro_014 step 141 vs Alakazam).
    # Default False: unit tests build the ctx directly.
    ability_unlock_retreat_ko: bool = False
    ability_unlock_retreat_attack: bool = False
    # GRAND TREE (id 1249). `grand_tree_ability_pending` = the stadium is on the
    # field, it offers its ability in THIS menu and there is an executable evolution
    # plan. The Forest of Vitality rule consults it so as NOT to replace the stadium
    # before the free chain has been cashed in (user's request).
    # Default False: unit tests build the ctx directly.
    grand_tree_in_play: bool = False
    grand_tree_ability_pending: bool = False
    # The EX-IMMUNE WALL (Crustle / Sylveon) is the opposing ACTIVE and our active
    # KNOCKS IT OUT this turn (damage via `_our_effective_damage`, with the Sturdy
    # cap applied). The `finish_the_immune_wall_before_gusting` rule consults it:
    # gusting would move the wall to the bench and waste the only window in which
    # one of our NON-ex bodies can kill it (registro_006 step 47).
    # Default False: unit tests build the ctx directly.
    ex_immune_wall_ko_ready: bool = False
    # Is there a Last-Ditch Catch left this turn? False if any Meowth ex IN PLAY
    # appeared this turn (its ability is already spent and only one is allowed per
    # turn) -> benching or DIGGING for another Meowth ex would not fetch a Supporter.
    meowth_ld_free: bool = True
    # Festival Grounds on the field AND the opposing Applin/Dipplin line in sight:
    # that switches on their Festival Lead (a double attack after knocking out our
    # active). The stadium is DOUBLE-EDGED -- our Dipplin gains it too -- which is
    # why the flag arrives already filtered by the opposing line. See
    # `_festival_lead_hostil`.
    # Default False: unit tests build the ctx directly.
    festival_lead_hostil: bool = False
    # MATCH POINT against the opposing ACTIVE: knocking it out WINS the game (it is
    # worth at least the prizes we are missing) and the finisher is on the BENCH --
    # retreat -> promote -> attack, with the retreat payable. The
    # `winning_finisher_on_the_active_after_retreating` rule consults it: gusting would swap
    # the opposing active for a body worth FEWER prizes and throw away the winning
    # turn (registro_010 step 144). See the `_win_ko_active_via_promote` block.
    # Default False: unit tests build the ctx directly.
    win_ko_active_via_promote: bool = False
    # FINISHER FISHING (`_FinisherFishing` or None): the turn has no attack available,
    # but the refill DRAW may bring the energy that unlocks one -- with its
    # hypergeometric probability already computed over the deck belief. It is
    # consulted by Lillie's `fish_energy_for_the_finisher` rule and by Boss's
    # `yields_to_finisher_fishing` yield (registro_004 step 49 vs Marnie).
    # Default None: unit tests build the ctx directly.
    finisher_fishing: object = None
    # THE TURN PLAN (`ptcg.turn.game_plan.TurnPlan`): what the PRIZE COUNT says
    # this turn is for, decided once and before the first decision -- is there a
    # route that CLOSES the game, how many prizes do we take, how many do they
    # take on the reply. The ordering vetoes read it so as not to step aside for a
    # resource card on a turn that ends the game (registro_013 step 126: the
    # Unfair Stamp vetoed the winning Boss's at mutual match point). Read it
    # through `game_plan.plan_of(ctx)`, never directly: the contexts built by hand
    # in the unit tests do not carry one.
    # Default None: unit tests build the ctx directly.
    turn_plan: object = None
    # ITEM LOCK THREAT: the opponent can leave us without Items on OUR next turn
    # (Budew on their field, or a Dragapult deck, which runs it). See
    # `_bloqueo_de_items_inminente`: with that hanging over us an Item is not a
    # resource to keep, it is a resource that EXPIRES -- consulted by
    # `_ub_meowth_for_tomorrow`.
    # Default False: unit tests build the ctx directly.
    item_lock_incoming: bool = False
    # THE OPENING SACRIFICE HAS NOWHERE TO RETREAT TO: our first turn, a
    # 2-prize ex in the active spot, a matchup that is not on the safe list and
    # NO one-prize body on the bench or in hand. The Poke Pad rule reads it to
    # go and search for one (`_pp_opening_sac_target`). See
    # `_opening_sac_needs_body` in main.py.
    # Default False: unit tests build the ctx directly.
    opening_sac_needs_body: bool = False
    # ...and the same question asked on the board where the finisher is ALREADY
    # visible: a doomed 2-prize ex in front, nothing on the bench that survives
    # their reply, and no spare BASIC to hand over -- neither benched nor in
    # hand. The user's ladder for that turn is "a Basic from hand, or one we can
    # search for, and only then a body already on the bench"; this is the middle
    # rung. See `_doomed_sac_needs_body` in main.py.
    # Default False: unit tests build the ctx directly.
    doomed_sac_needs_body: bool = False

__all__ = [
    'DecisionContext',
]
