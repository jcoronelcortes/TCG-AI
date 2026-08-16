"""Scoring the CARD options: "pick a card" -- for a dozen different reasons.

The largest branch in the package, and its size is not one huge decision but
MANY unrelated ones sharing an option type. Whenever the engine asks us to
choose a card rather than to take an action, the option arrives here, and the
first thing the code does is ask WHY it is being asked. That question is
`select.context`, and it is the map of this file:

    SWITCH / TO_ACTIVE          who takes the front seat (after a knockout, or
                                as the target of a retreat). The biggest and
                                most-argued section -- see the promotion band
                                in `ptcg/cards/scoring.py`.
    SETUP_ACTIVE_POKEMON        the opening: which body starts in front
    SETUP_BENCH_POKEMON         the opening: what we bench behind it
    TO_HAND                     what a recovery brings back (Lana's Aid,
                                Night Stretcher)
    DISCARD                     what we throw away to pay a cost. The ladders
                                that price a card by what THIS hand needs.
    DAMAGE                      where damage counters go
    ATTACH_FROM                 which energy to move
    RECOVER/AFFECT_SPECIAL_CONDITION    the small ones

READ THE CONTEXT FIRST. The same card is worth completely different things
under two of these -- a Chikorita is a fine promotion and terrible fodder --
so a rule written without checking the context will fire in menus it was never
meant for. That is the recurring defect in this file.

SUB-SELECTIONS COME FIRST. A search or an ability can open its own card menu
that shares a context with unrelated selections (the Grand Tree chain is the
example handled at the top). Those are cut off before any generic handler
runs, because otherwise the generic scorer answers a question it does not
understand.

THE DISCARD LADDERS deserve their own note, since they are the subtlest part.
What a card costs is a PROPERTY OF THE HAND, not of the card: the right thing
to throw away is whatever this hand cannot use today. Hence the named rungs --
a spare copy of an evolution piece, a Supporter that is dead this turn, a body
with nowhere to sit -- and the guard that the cost must not eat what an earlier
search of the same turn just bought (`_purchase_of_this_turn`).

Extracted VERBATIM from the `agent()` chain: it unpacks from the context only
the fields it reads and returns only the ones it reassigns.
"""

from cg.api import AreaType, CardType, Pokemon, SelectContext
from ptcg.calc.card import get_card, prize_count, prize_count_op
from ptcg.calc.damage import _attacker_base_damage, _bench_attacker_can_ko, _festival_double_wave, _festival_second_wave_prizes, _ko_not_guaranteed, _our_effective_damage, _snipe_target_score
from ptcg.calc.energy import _can_attack_eff, _grass_attach_route_open, _grass_attach_unit, _grass_mult
from ptcg.calc.board import _active_of, _count_hand_play_options
from ptcg.cards.groups import EVO_LINES, GT_FETCH_BONUS
from ptcg.cards.ids import THE_COST_KEEPS_THE_SUPPORTER_THE_TURN_PLAYS
from ptcg.cards.ids import Applin, Basic_Grass_Energy, Bayleef, Boss_Orders, Bug_Catching_Set, Chikorita, DISCARD_SHIELD_KEEP_THE_GUST, DISCARD_SHIELD_KEEP_THE_NONEX, DISCARD_SHIELD_MUTES_THE_EX, DISCARD_SHIELD_SEARCH_FODDER, DISCARD_SHIELD_STADIUM_FODDER, OP_EX_SHIELD_MAX_PRIZES, DISCARD_XEROSIC_CAP_IS_THE_ANSWER, DISCARD_BODY_WITHOUT_SEAT, DISCARD_CF_HAND_RECYCLER, DISCARD_EVO_SPARE_COPY, DISCARD_LINK_LAST_BRIDGE, DISCARD_LINK_THE_SEARCH_BUYS, DISCARD_SUPPORTER_DEAD_DROP, DISCARD_SUPPORTER_LIVE_KEEP, DISCARD_WHAT_THE_SEARCH_ALREADY_BOUGHT, DUNSPARCE_IDS, Dawn, Dipplin, Drednaw, Fezandipiti_ex, Forest_of_Vitality, Grand_Tree, Hydrapple_ex, LANA_SEL_INJUGABLE, LANA_SEL_GRASS_DEMAND, LANA_SEL_GRASS_UNLOCKS, LANA_SEL_GRASS_SURPLUS, LANA_SEL_GRASS_WINS, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Night_Stretcher, OUR_ABILITY_IDS, OUR_EX_IDS, Pinsir, Poke_Pad, RETREAT_COST, RIPEN_HEAL_TARGET_SCORE, SCORE_FORBID, SCORE_LOOKAHEAD_PROMOTE_KO, SCORE_LOOKAHEAD_PROMOTE_SAFE, SCORE_NEVER, SCORE_VETO, Sylveon, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Unfair_Stamp, XEROSIC_BIG_HAND, DISCARD_XEROSIC_CAPS_A_FAT_HAND, Xerosic_Machinations
from ptcg.cards.lines import _evo_bridge_last_copies, _evo_copies_usable, _evo_top_unlocked_by_the_search, _line_base_benchable, _pokemon_injugable
from ptcg.cards.ids import OPENING_SAC_PROMOTE_ORDER, SETUP_ACTIVE_BASIC_ORDER, SETUP_ACTIVE_BASIC_TOP, SETUP_ACTIVE_EX_ORDER, SETUP_ACTIVE_EX_TOP, SETUP_ACTIVE_OTHER, SETUP_ACTIVE_OTHER_BASIC, SETUP_ACTIVE_STEP
from ptcg.cards.scoring import MAIN_ATTACKERS, PROMO_DEFERRED_ATTACKER, PROMO_DOOMED_PENALTY, PROMO_KO_BONUS, PROMO_KO_FRONT, PROMO_KO_ROTATION, PROMO_LAST_STAND, PROMO_MATCH_POINT_VETO, PROMO_PRIZE_PENALTY, OPENING_SAC_PROMOTE_STEP, OPENING_SAC_PROMOTE_TOP, _SUPP_PLAY_IDS, _purchase_of_this_turn, PROMOTE_TERA_PAYS_FOR_ITS_COVER, PROMO_TERA_COVER_PRICE
from ptcg.cards.tables import HAND_TO_DECK_PLAY_IDS, card_table
from ptcg.decision.boss_orders import _ADJUST_GUST_NUISANCE, _ADJUST_GUST_OFFENSIVE, _RULES_GUST_NUISANCE, _ctx_gust_target
from ptcg.decision.disruption import _stamp_pendiente, _xr_cap_lost_if_discarded
from ptcg.decision.meowth import _CtxMeowthFetch, _MEOWTH_FETCH_SUPPS, _RULES_MEOWTH_FETCH
from ptcg.decision.night_stretcher import _RULES_NS_APPLIN, _RULES_NS_BAYLEEF, _RULES_NS_CHIKORITA, _RULES_NS_DIPPLIN, _RULES_NS_FEZ, _RULES_NS_GRASS, _RULES_NS_HYDRAPPLE, _RULES_NS_MEGANIUM, _RULES_NS_MEOWTH, _RULES_NS_OGERPON, _RULES_NS_PINSIR, _RULES_NS_TAPU, _ctx_ns_fetch, _ns_fez_engine_alive, _ns_meowth_engine_alive
from ptcg.decision.poke_pad import _CtxPPFetch, _RULES_PP_FETCH
from ptcg.decision.supporters import DAWN_SEAT_TOMORROW_CAP, _dawn_seat_waits_a_turn
from ptcg.decision.ultra_ball import _AJUSTES_UB_HYDRAPPLE, _CtxUBFetch, _line_closed_by_its_top, _the_body_search_cannot_buy_the_energy, _ub_target_cannot_be_worn, _ub_wearable_bodies, _ub_target_covered_by_hand, _ub_target_has_no_seat, _RULES_UB_APPLIN, _RULES_UB_BAYLEEF, _RULES_UB_CHIKORITA, _RULES_UB_DIPPLIN, _RULES_UB_FEZ, _RULES_UB_HYDRAPPLE, _RULES_UB_MEGANIUM, _RULES_UB_MEOWTH, _RULES_UB_OGERPON, _RULES_UB_PINSIR, _RULES_UB_TAPU, _counter_stadium_urgent, _ctx_ub_fetch_hydrapple, _ctx_ub_fetch_meowth
from ptcg.state.agent_state import AGENT_STATE
from ptcg.state.zones import ZONE_BENCH, ZONE_DECK, ZONE_HAND, ZONE_PRIZE
from ptcg.engine.rules import _resolve_with_trace


def score_play(tc, o, score):
    """Returns the score of `o`. It may return `_SALTAR`."""
    _SALTAR = tc._SALTAR
    _BCS_FETCH_TABLE = tc._BCS_FETCH_TABLE
    _DAWN_FETCH_TABLE = tc._DAWN_FETCH_TABLE
    _active_cant_attack_this_turn = tc._active_cant_attack_this_turn
    _active_needs_energy = tc._active_needs_energy
    _active_ready_attacker = tc._active_ready_attacker
    _best_promote_card = tc._best_promote_card
    _best_promote_key = tc._best_promote_key
    _best_supp_in_hand_val = tc._best_supp_in_hand_val
    _best_supp_in_deck_val = tc._best_supp_in_deck_val
    _boss_gust_immune_active = tc._boss_gust_immune_active
    _gust_finds_an_attacker = tc._gust_finds_an_attacker
    _ready_attacker_count = tc._ready_attacker_count
    _active_doomed_real = tc._active_doomed_real
    _bp = tc._bp
    _cap_kept_once = tc._cap_kept_once
    _cf_refill_kept_once = tc._cf_refill_kept_once
    _cm_use_ex = tc._cm_use_ex
    _conf_is_matchup_attacker = tc._conf_is_matchup_attacker
    _dc = tc._dc
    _deny_evo_via_boss = tc._deny_evo_via_boss
    _prize_mismatch_matchup = tc._prize_mismatch_matchup
    _dragapult_no_tapu = tc._dragapult_no_tapu
    _evo_huerfanos = tc._evo_huerfanos
    _counter_stadium_kept_once = tc._counter_stadium_kept_once
    _evo_spare_seen = tc._evo_spare_seen
    _bridge_kept_once = tc._bridge_kept_once
    _bought_spare_seen = tc._bought_spare_seen
    _evo_necesarios = tc._evo_necesarios
    _festival_lead_hostil = tc._festival_lead_hostil
    _forced_ko_promote = tc._forced_ko_promote
    _ft_wall_body = tc._ft_wall_body
    _ft_wall_promote = tc._ft_wall_promote
    _grass_anywhere_enables_syrup_ko = tc._grass_anywhere_enables_syrup_ko
    _grass_enables_promote_ko = tc._grass_enables_promote_ko
    _gt_plan = tc._gt_plan
    _gt_turn_plans = tc._gt_turn_plans
    _gt_quiere_basico = tc._gt_quiere_basico
    _gt_basics_ranking = tc._gt_basics_ranking
    _gt_score_selection = tc._gt_score_selection
    _doomed_sac_context = tc._doomed_sac_context
    _gust_2prize_via_boss = tc._gust_2prize_via_boss
    _has_bench_attacker = tc._has_bench_attacker
    _ko_prefer_basic_general = tc._ko_prefer_basic_general
    _lana_grass_order = tc._lana_grass_order
    _lana_plan = tc._lana_plan
    _ld_lillie_ofrecida = tc._ld_lillie_ofrecida
    _lillie_protected_once = tc._lillie_protected_once
    _lucario_ko_prefer_basic = tc._lucario_ko_prefer_basic
    _lucario_sac_context = tc._lucario_sac_context
    _opening_sac_needs_body = tc._opening_sac_needs_body
    _doomed_sac_needs_body = tc._doomed_sac_needs_body
    _opening_sac_promote = tc._opening_sac_promote
    _mega_line_active = tc._mega_line_active
    _meowth_devel_lillie = tc._meowth_devel_lillie
    _meowth_recovery_ko = tc._meowth_recovery_ko
    _meowth_ld_free = tc._meowth_ld_free
    _op_best_damage_vs = tc._op_best_damage_vs
    _op_counter_threat_vs = tc._op_counter_threat_vs
    _our_first_action_turn = tc._our_first_action_turn
    _ko_front_outranked = tc._ko_front_outranked
    _cubchoo_ko_rotation_min = tc._cubchoo_ko_rotation_min
    _mp_cheaper_candidate = tc._mp_cheaper_candidate
    _mp_front_survivors = tc._mp_front_survivors
    _mp_last_stand = tc._mp_last_stand
    _mp_outlasts = tc._mp_outlasts
    _mp_price_ends_the_game = tc._mp_price_ends_the_game
    _promo_damage_to_op = tc._promo_damage_to_op
    _promo_kos_op = tc._promo_kos_op
    _promo_ko_wins_the_game = tc._promo_ko_wins_the_game
    _promo_min_prize = tc._promo_min_prize
    _promo_op_act = tc._promo_op_act
    _promo_survives = tc._promo_survives
    _promo_evo_koer = tc._promo_evo_koer
    _promo_survivors = tc._promo_survivors
    _promo_wall_relief = tc._promo_wall_relief
    _promote_setup_ko_attacker = tc._promote_setup_ko_attacker
    _promo_bet_walks_back = tc._promo_bet_walks_back
    _promo_deferred_attacker = tc._promo_deferred_attacker
    _refresh_promote_prefer_basic = tc._refresh_promote_prefer_basic
    _ripen_heal_serial = tc._ripen_heal_serial
    _sel_active_cant_attack = tc._sel_active_cant_attack
    _self_ko_by_own_attack = tc._self_ko_by_own_attack
    _supp_values = tc._supp_values
    _supp_that_takes_the_turn = tc._supp_that_takes_the_turn
    # Mutated in place (`.add`), so it needs no write-back: it is the same set
    # every option of this menu sees. See `REASIGNADAS` in ctx_scoring.py.
    _supp_live_keep_once = tc._supp_live_keep_once
    _tapu_sac_priority = tc._tapu_sac_priority
    _tb_req = tc._tb_req
    _teal_wall_pivot = tc._teal_wall_pivot
    _ub_meowth_for_tomorrow = tc._ub_meowth_for_tomorrow
    _win_via_boss_gust = tc._win_via_boss_gust
    b = tc.b
    bench_count = tc.bench_count
    bp = tc.bp
    budew_on_op_field = tc.budew_on_op_field
    card = tc.card
    context = tc.context
    ctx = tc.ctx
    discard_counts = tc.discard_counts
    energy_count = tc.energy_count
    energy_score = tc.energy_score
    estimated_op_damage = tc.estimated_op_damage
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    has_condition = tc.has_condition
    has_hydrapple = tc.has_hydrapple
    is_confused = tc.is_confused
    itchy_pollen_active = tc.itchy_pollen_active
    meowth_ability_lock = tc.meowth_ability_lock
    my_index = tc.my_index
    my_prize = tc.my_prize
    my_state = tc.my_state
    neutralization_zone_active = tc.neutralization_zone_active
    obs = tc.obs
    op_bench_snipe_threat = tc.op_bench_snipe_threat
    op_double_attack_pending = tc.op_double_attack_pending
    op_has_ability_immune_active = tc.op_has_ability_immune_active
    op_has_dragapult = tc.op_has_dragapult
    op_has_dreepy_line = tc.op_has_dreepy_line
    op_has_dwebble_bench = tc.op_has_dwebble_bench
    op_has_ethan_preevo = tc.op_has_ethan_preevo
    op_has_ex_immune_active = tc.op_has_ex_immune_active
    op_has_ex_immune_bench = tc.op_has_ex_immune_bench
    op_has_froslass = tc.op_has_froslass
    op_has_latias_ex = tc.op_has_latias_ex
    op_has_typhlosion = tc.op_has_typhlosion
    op_is_aggro_deck = tc.op_is_aggro_deck
    op_is_alakazam_deck = tc.op_is_alakazam_deck
    op_is_comfey_deck = tc.op_is_comfey_deck
    op_is_control_deck = tc.op_is_control_deck
    op_is_cubchoo_deck = tc.op_is_cubchoo_deck
    op_is_dragapult_dusknoir = tc.op_is_dragapult_dusknoir
    op_is_fire_deck = tc.op_is_fire_deck
    op_is_lucario_deck = tc.op_is_lucario_deck
    op_is_sylveon_deck = tc.op_is_sylveon_deck
    op_prize = tc.op_prize
    op_state = tc.op_state
    pid = tc.pid
    scores = tc.scores
    select = tc.select
    state = tc.state
    total_grass = tc.total_grass
    watchtower_in_play = tc.watchtower_in_play

    try:
        card = get_card(obs, o.area, o.index, o.playerIndex)
        if card is not None:
            energy_count = 0
            if isinstance(card, Pokemon):
                energy_count = len(card.energies)
        
            if (select.effect is not None
                    and select.effect.id == Grand_Tree
                    and getattr(o, 'playerIndex', my_index) == my_index):
                # Sub-selections of the Grand Tree ability (which Basic
                # evolves / which Stage 1 and Stage 2 are brought from the
                # deck). They go BEFORE any other CARD handler: they share
                # a context (TO_FIELD / EVOLVES_FROM / TO_HAND...) with
                # selections of other cards and without this cut-off they
                # would fall into the wrong scorer.
                scores.append(_gt_score_selection(
                    o, card, _gt_plan, _gt_turn_plans, my_state,
                    field_counts))
                return _SALTAR   # it already did its own scores.append
        
            if (context == SelectContext.DAMAGE
                    and isinstance(card, Pokemon)
                    and getattr(o, 'playerIndex', my_index) != my_index):
                # Selection of the damage TARGET of an attack that hits any
                # opposing Pokemon (e.g. Fezandipiti ex's Cruel Arrow, a
                # fixed 100). There used to be NO handler for this context and
                # the argmax fell on option 0 (the active) (user,
                # registro_015 step 139 vs Crustle, LOST: it aimed at the
                # active Crustle, IMMUNE to the damage of our ex because of its
                # ability, with a knockable 70 HP Dwebble on the bench).
                # Rule: evaluate ALL the opposing Pokemon with the EFFECTIVE
                # damage (`_our_effective_damage` applies Crustle's ex
                # immunity, the Neutralization Zone, weakness/resistance...):
                # 1) a KNOCKED OUT target is better (more prizes > more charged >
                #    more HP = more developed); 2) if nothing dies, chip damage
                #    to the one left CLOSEST to a KO; 3) immune bodies (0 damage)
                #    only as a last resort (the selection is mandatory).
                # The ranking lives in `_snipe_target_score`, the SAME function
                # the planner uses to decide whether to attack instead of
                # retreating (`_snipe_best_target`): that way the target that
                # makes attacking worthwhile is exactly the one that ends up
                # being chosen here, with no way for the two scales to diverge.
                _dmg_att = (my_state.active[0]
                            if my_state.active and my_state.active[0] is not None
                            else None)
                _dmg_eff = 0
                if _dmg_att is not None:
                    _dmg_e = len(_dmg_att.energies) * _grass_mult()
                    _dmg_base = _attacker_base_damage(
                        _dmg_att.id, card, _dmg_e,
                        grass_scale=total_grass,
                        teal_self_energy=_dmg_e,
                        bench_count=bench_count)
                    _dmg_eff = _our_effective_damage(
                        _dmg_att, card, _dmg_base, AGENT_STATE.meganium_in_play,
                        neutralization_zone_active)
                score = _snipe_target_score(_dmg_eff, card)
                scores.append(score)
                return _SALTAR   # it already did its own scores.append
        
            if context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE:
                # THE OPENING SACRIFICE ONLY OWNS THE VOLUNTARY RETREAT (user,
                # registro_002 step 28). `SelectContext.SWITCH` is the
                # promotion of the retreat we just chose, on our own turn; the
                # FORCED promotion after a knockout (TO_ACTIVE) can fall inside
                # the OPPONENT's turn and is a different question, with its own
                # measured answer -- survival, match point, the body that
                # attacks first. A flag about hiding an ex does not get to
                # answer it.
                #
                # ...AND IT YIELDS TO THE DOOMED SACRIFICE, which is its
                # SPECIAL CASE and therefore asked first. Both orders come from
                # the user and they disagree about the same two bodies --
                # opening: Tapu Bulu, Applin, Chikorita; doomed: Chikorita,
                # then Applin, unless an evolution waits in hand -- because
                # they are answering different questions on boards that
                # overlap. The opening order is picking a body to STAND there:
                # Tapu Bulu heads it because 140 HP endures a turn and attacks
                # afterwards, and the Applin goes ahead of the Chikorita
                # because its line is the one worth developing. The doomed
                # order is picking a body to LOSE -- `_doomed_sac_context`
                # means the projection, evolution included, kills whoever we
                # promote -- and there enduring is worth nothing, so what
                # counts is which line we can spare and which body already has
                # its evolution in hand. Where nobody survives, the informed
                # order wins.
                _opening_sac_menu = (_opening_sac_promote
                                     and context == SelectContext.SWITCH
                                     and not _lucario_sac_context
                                     and not _doomed_sac_context)
                if (o.playerIndex == my_index
                        and (_lucario_sac_context or _doomed_sac_context
                             or _opening_sac_menu)):
                    # WHICH BODY WE HAND OVER (user, registro_002 step 25 vs
                    # Mega Lucario ex, LOST). We are retreating a doomed 2-prize
                    # ex to concede one prize instead of two, so this menu is not
                    # choosing an attacker: it is choosing what to LOSE. Both
                    # contexts that reach here mean the same board -- the
                    # anti-Lucario one (an opposing Riolu on turn 2) and the
                    # deck-agnostic `_doomed_sac_context`, which reads the real
                    # finisher, the evolution included.
                    #
                    # THE ORDER IS CHIKORITA, THEN APPLIN, and the reason is what
                    # the two lines are worth to us: the Applin is the first link
                    # of Dipplin -> Hydrapple ex, the attacker the deck is built
                    # around, while the Chikorita line (Bayleef -> Meganium) is
                    # support. The cheapest body is not the cheapest CARD.
                    #
                    # THE EXCEPTION the user named, and it overrules the order: a
                    # body whose evolution is ALREADY IN HAND is not spare, it is
                    # next turn's play. With a Bayleef in hand the Chikorita
                    # stays and the Applin goes; with a Dipplin in hand -- the
                    # case in the record -- the Applin stays and the Chikorita
                    # goes; holding BOTH evolutions nothing distinguishes them
                    # and the base order decides again. Read from the hand rather
                    # than from a table of ids, so it holds for any line.
                    _sac_evo_in_hand = any(
                        _sh_n > 0
                        and getattr(card_table.get(_sh_id), 'evolvesFrom', None)
                        == getattr(card_table.get(card.id), 'name', None)
                        for _sh_id, _sh_n in hand_counts.items())
                    # THE ORDER THE USER GAVE FOR THE MEGA STARMIE LINE
                    # (registro_002 step 28, episode 90583594, LOST). It
                    # REPLACES the Chikorita-first order above, and the reason
                    # it may is that the two are answering different questions:
                    # `_doomed_sac_context` is spending one of two evolution
                    # lines and asks which line we can spare, while this menu
                    # is buying the difference between one prize and two
                    # against a deck that one-shots any ex left in front. The
                    # rungs and what each is worth are in
                    # STARMIE_SAC_PROMOTE_ORDER (ptcg/cards/ids.py).
                    #
                    # THE APPLIN WITHOUT ENERGY GOES FIRST. Both copies hand
                    # over the same single prize, so what separates them is
                    # what stays behind: the charged one keeps a Grass we
                    # already paid for, and sending it to the front throws that
                    # attachment away with the body. The record's board had
                    # exactly the two -- an Applin with a Grass and a bare one.
                    #
                    # Anything the order does not name falls through to the
                    # rungs below, which is what "and finally any other option"
                    # means: an unnamed one-prize body still beats an ex, and
                    # among ex the sturdiest goes first.
                    if _opening_sac_menu and card.id in OPENING_SAC_PROMOTE_ORDER:
                        _osac_rank = OPENING_SAC_PROMOTE_ORDER.index(card.id)
                        if card.id == Applin and energy_count > 0:
                            # The charged copy sits one rung below the bare one;
                            # everything under it shifts down by that rung.
                            _osac_rank += 1
                        elif _osac_rank >= OPENING_SAC_PROMOTE_ORDER.index(Applin) + 1:
                            _osac_rank += 1
                        score = (OPENING_SAC_PROMOTE_TOP
                                 - _osac_rank * OPENING_SAC_PROMOTE_STEP)
                    elif _tapu_sac_priority and card.id == Tapu_Bulu:
                        # Tapu Bulu only goes first where it really contributes
                        # (an opponent with ex protection, or the Hydrapple ex +
                        # Meganium engine that can charge it on the spot).
                        score = 6000
                    elif card.id == Chikorita:
                        score = 5000 if _sac_evo_in_hand else 6000
                    elif card.id == Applin:
                        score = 4900 if _sac_evo_in_hand else 5900
                    elif card.id == Tapu_Bulu:
                        # The deck's MANUAL attacker: the one body we do not
                        # feed. Still above any ex -- one prize beats two.
                        score = 200
                    elif prize_count(card) == 1:
                        # Any other 1-prize body (a Bayleef, a Dipplin, a
                        # Pinsir): worse than the two the rule names, better
                        # than an ex. Without this rung the menu flattened every
                        # unnamed body to the same number as a 2-prize ex and the
                        # sacrifice could hand over TWO prizes -- the flip audit
                        # of this change caught it promoting a Hydrapple ex on a
                        # bench with no Chikorita and no Applin.
                        score = 4000
                    else:
                        # An ex, only if there is nothing cheaper: the sturdiest
                        # first, so the choice does not depend on the menu order.
                        score = 100 + (card.hp or 0) // 10
                elif o.playerIndex == my_index:
        
                    # Ready-to-attack via effective energy (single source:
                    # ATTACK_ENERGY_REQ). It now includes Pinsir (previously omitted).
                    _can_attack_now = (
                        card.id in MAIN_ATTACKERS
                        and _can_attack_eff(card.id, energy_count))
        
                    _ns_grass_recover_switch = (
                        hand_counts.get(Night_Stretcher, 0) >= 1 and
                        discard_counts.get(Basic_Grass_Energy, 0) >= 1)
                    _grass_attachable_switch = (
                        hand_counts.get(Basic_Grass_Energy, 0) >= 1 or
                        _ns_grass_recover_switch)
                    _forced_promote_switch = not my_state.active
                    _can_attack_with_attach = _can_attack_now
                    if (not _can_attack_now and _grass_attachable_switch
                            and (not state.energyAttached or _forced_promote_switch)):
                        _pkmn_eff_plus1 = energy_count + _grass_attach_unit()
                        if card.id == Hydrapple_ex:
                            _can_attack_with_attach = (_pkmn_eff_plus1 >= 2)
                        elif card.id == Dipplin:
                            _can_attack_with_attach = True
                        elif card.id == Teal_Mask_Ogerpon_ex:
                            _can_attack_with_attach = (_pkmn_eff_plus1 >= 3)
                        elif card.id == Tapu_Bulu:
                            _can_attack_with_attach = (_pkmn_eff_plus1 >= 4)
                        elif card.id == Fezandipiti_ex:
                            _can_attack_with_attach = (_pkmn_eff_plus1 >= 3)
                        elif card.id == Meganium:
                            _can_attack_with_attach = (_pkmn_eff_plus1 >= 4)
        
                    if _can_attack_now:
                        score = 500
                    elif _can_attack_with_attach:
                        score = 350
                    else:
                        score = 100
        
                    if card.hp is not None:
                        score += card.hp // 10
        
                    score += energy_count
        
                    # PROMOTE THE FINISHER THAT WINS THE GAME (user,
                    # registro_016 step 184 vs Marnie's Grimmsnarl, DRAW).
                    # When retreating, the promotion chose by "the biggest tank
                    # that can attack": it brought up the 290 HP Hydrapple ex (350 +
                    # 29 + 60 + 250 = 689) ahead of the already charged Teal Mask
                    # Ogerpon ex (500 + 10 + 6 = 516)... and the Hydrapple with no
                    # energy did not finish, while the Ogerpon at 6 energies
                    # closed the game with Myriad Leaf Shower. When the
                    # candidate KNOCKS OUT the opposing active and that KO gives us
                    # the prizes we are missing (or the opponent has no bench to
                    # replace it), promoting it is decisive: there is no next turn
                    # to protect.
                    #
                    # Only in `SelectContext.SWITCH`, which is the promotion of
                    # OUR voluntary retreat: it always happens on our turn and
                    # before attacking, so the finisher is really available. The
                    # FORCED promotion after a KO (TO_ACTIVE) can fall on the
                    # OPPONENT's turn, where nobody attacks and the wall is still
                    # the right answer; that is why it is not included.
                    # `_ko_not_guaranteed` and the candidate's own self-damage are
                    # checked just like in the other finisher evaluators: a
                    # finisher that kills itself and with that closes the
                    # opponent's count wins nothing.
                    if context == SelectContext.SWITCH:
                        _wp_opa = _active_of(op_state)
                        _wp_opa_hp = (_wp_opa.hp or 0) if _wp_opa is not None else 0
                        _wp_e = energy_count
                        # THE ROUTE PAID THE RETREAT; THIS MENU HAS TO CASH IT.
                        # The prize test below is the same sentence as
                        # `_promote_ko_active_prizes`, and under Festival Grounds
                        # it was wrong here for the same reason: our Dipplin
                        # throws Do the Wave TWICE, so the promotion cashes the
                        # body in front AND the one they put up to replace it.
                        # Without this the fix upstream is worse than no fix at
                        # all -- the turn plan reads ROUTE_PROMOTE, the retreat
                        # gets chosen, and then this menu brings up the biggest
                        # tank instead of the attacker the route was for: the
                        # fee is paid and never cashed (measured on
                        # registro_020 with `utils/search_oracle.py`, which is
                        # how the hole was found at all).
                        _wp_double = _festival_double_wave(card.id)
                        _wp_op_bench_empty = not any(
                            b is not None for b in (op_state.bench or []))
                        if (_wp_opa is not None and _wp_opa_hp > 0
                                and (_can_attack_now or _can_attack_with_attach)
                                and not _ko_not_guaranteed(_wp_opa)
                                and (my_prize <= prize_count_op(_wp_opa)
                                     or _wp_double
                                     or _wp_op_bench_empty)
                                and not (_self_ko_by_own_attack(card, incierto=True)
                                         and op_prize <= prize_count(card))):
                            if not _can_attack_now:
                                _wp_e = energy_count + _grass_attach_unit()
                            _wp_base = _attacker_base_damage(
                                card.id, _wp_opa, _wp_e * _grass_mult(),
                                grass_scale=total_grass, teal_self_energy=_wp_e,
                                bench_count=bench_count)
                            _wp_dmg = (_our_effective_damage(
                                card, _wp_opa, _wp_base,
                                AGENT_STATE.meganium_in_play,
                                neutralization_zone_active)
                                if _wp_base > 0 else 0)
                            _wp_prizes = (prize_count_op(_wp_opa)
                                          if _wp_dmg >= _wp_opa_hp else 0)
                            if _wp_prizes and _wp_double:
                                _wp_prizes += _festival_second_wave_prizes(
                                    op_state, _wp_dmg, _wp_opa)
                            # The recomputed test is the outer one verbatim for
                            # every body that is not throwing two waves, so
                            # nothing outside the stadium changes score here.
                            if (_wp_base > 0 and _wp_dmg >= _wp_opa_hp
                                    and (my_prize <= _wp_prizes
                                         or _wp_op_bench_empty)):
                                # With the energy ALREADY on it the finisher is certain;
                                # if it depends on a pending attachment, it is worth
                                # slightly less (but still above every wall/development
                                # bonus of this block).
                                score += 20000 if _can_attack_now else 18000
        
                    # Prize denial when promoting (user): if the opponent is <=2
                    # prizes away from winning, DECISIVELY prefer bringing up a
                    # 1-prize body that can ALREADY attack over an ex (2 prizes),
                    # so that an opposing KO does not close the game. It only
                    # GIVES A BONUS to non-ex attackers (it never penalises the
                    # ex): if the only body able to attack is an ex, it is still
                    # promoted normally.
                    #
                    # `prize_count(card) < op_prize` IS the rule's own sentence
                    # (user, registro_014 step 130 vs Alakazam, LOST -- episode
                    # 90350002). Denial only denies while the cheap body leaves
                    # them short: with their pile at ONE the 1-prize body hands
                    # over the prize that ends the game exactly like the ex, the
                    # bonus buys nothing, and the +3000 it pays steers the front
                    # spot to the FRAGILE body -- a 140 HP Tapu Bulu ahead of a
                    # 210 HP Ogerpon ex against 200 of Powerful Hand. There the
                    # criterion is survival, and it is applied by the MATCH
                    # POINT block at the end of this chain.
                    if (op_prize <= 2 and _can_attack_now
                            and prize_count(card) < op_prize):
                        score += 3000
        
                    # PRIZE MISMATCH when promoting (user, vs Raging Bolt and
                    # Mega Abomasnow ex). If NOBODY on the bench can knock out the
                    # opposing active this turn, whoever is promoted will fall to
                    # their one-shot: bring up the 1-prize body (a cheap wall), never
                    # an ex worth 2. With an attacker able to knock out, the normal
                    # promotion (which already prefers it) still rules.
                    if _prize_mismatch_matchup and prize_count(card) <= 1:
                        _rb_opa = _active_of(op_state)
                        _rb_alguien_ko = (
                            _rb_opa is not None
                            and _bench_attacker_can_ko(
                                my_state, _rb_opa, AGENT_STATE.meganium_in_play,
                                total_grass, bench_count, total_grass,
                                neutralization_zone_active))
                        if not _rb_alguien_ko:
                            score += 2500
        
                    # When retreating a CONFUSED active, prioritise bringing up an
                    # attacker of the matchup that can ALREADY attack (e.g. Dipplin
                    # vs Crustle) over a wall that does not attack this turn
                    # (e.g. an ex that Crustle is immune to). It avoids bringing
                    # up the wrong Pokemon after curing the confusion.
                    if (is_confused and _can_attack_now
                            and _conf_is_matchup_attacker(card.id)):
                        score += 2000
        
                    if not _can_attack_now and not _can_attack_with_attach:
                        if card.hp is not None:
        
                            score += card.hp // 5
        
                            if estimated_op_damage > 0 and card.hp > estimated_op_damage:
                                score += 80
                            elif estimated_op_damage > 0 and card.hp <= estimated_op_damage:
                                score -= 20
        
                    if _teal_wall_pivot and card.id == Hydrapple_ex:
                        # Defensive pivot with Teal Dance: bring up the strongest
                        # body (Hydrapple ex, a 330 wall) even if it cannot attack
                        # yet. A decisive bonus for choosing it when promoting.
                        score += 4000
        
                    if card.id == Hydrapple_ex:
                        score += 60
                        if _can_attack_now:
        
                            _syrup_dmg = 30 + 30 * total_grass
                            score += min(_syrup_dmg // 10, 30)
                        elif _can_attack_with_attach:
        
                            score += 250
                        if _cm_use_ex and (_can_attack_now or _can_attack_with_attach):
                            # Crustle + Mega Kangaskhan ex matchup: bring up
                            # OUR ex to attack the Mega and keep the non-ex
                            # for Crustle.
                            score += 500
                    elif card.id == Tapu_Bulu:
                        if _can_attack_now:
                            score += 50
                        if _cm_use_ex:
                            # Keep Tapu Bulu for Crustle (it knocks it out in one
                            # hit): do NOT bring it up against the Mega Kangaskhan ex,
                            # which we attack with our ex.
                            score -= 500
                        elif op_has_ex_immune_active or AGENT_STATE.op_is_crustle_deck:
                            score += 80
                        if AGENT_STATE.op_is_cornerstone_deck:
        
                            score += 120
                    elif card.id == Teal_Mask_Ogerpon_ex:
                        score += 30
                        if _cm_use_ex and (_can_attack_now or _can_attack_with_attach):
                            # Bring up OUR ex to attack the Mega Kangaskhan
                            # ex and keep the non-ex (Tapu Bulu) for Crustle.
                            score += 500
                    elif card.id == Dipplin:
                        score += 15
                        if op_has_ex_immune_active:
                            score += 40
        
                        if (AGENT_STATE.op_is_crustle_deck and state.retreated and
                                energy_count == 0 and
                                hand_counts.get(Night_Stretcher, 0) >= 1 and
                                hand_counts.get(Basic_Grass_Energy, 0) == 0 and
                                discard_counts.get(Basic_Grass_Energy, 0) >= 1):
                            score += 5000
                    elif card.id == Meganium:
                        if (op_has_ex_immune_active or AGENT_STATE.op_is_crustle_deck) and _can_attack_now:
        
                            score += 120
                        else:
                            score -= 80
                    elif card.id == Meowth_ex:
                        score -= 100
                    elif card.id == Fezandipiti_ex:
                        score -= 100
                    elif card.id == Chikorita:
                        score -= 60
                    elif card.id == Bayleef:
                        score -= 50
                    elif card.id == Applin:
                        score -= 70
        
                    # Rule (user, log 86607718 turn 2, vs Crustle): when
                    # PROMOTING (e.g. after retreating an active Chikorita) and
                    # NO body can attack the wall this turn, bring up a tank EX
                    # as a disposable wall -- first candidate Teal Mask
                    # Ogerpon ex (210 HP) -- and KEEP Tapu Bulu on the bench
                    # (our key attacker, which knocks Crustle out) to charge it
                    # safely. Only when NOBODY attacks: if Tapu can already
                    # attack, its +80 vs Crustle still rules. It does not apply to
                    # the Crustle + Mega Kangaskhan ex split (_cm_use_ex).
                    if (AGENT_STATE.op_is_crustle_deck and not _cm_use_ex
                            and not _can_attack_now
                            and not _can_attack_with_attach):
                        if card.id == Teal_Mask_Ogerpon_ex:
                            score += 300
                        elif card.id == Tapu_Bulu:
                            score -= 300
        
                    _op_act_wsel = op_state.active[0] if op_state.active else None
                    if _op_act_wsel is not None and isinstance(card, Pokemon):
                        _op_act_wsel_data = card_table.get(_op_act_wsel.id)
                        _card_wsel_data = card_table.get(card.id)
                        if (_card_wsel_data is not None and getattr(_card_wsel_data, 'weakness', None) is not None and
                                _op_act_wsel_data is not None and
                                getattr(_op_act_wsel_data, 'energyType', None) == _card_wsel_data.weakness):
                            score -= 250
        
                        _op_dmg_vs_card = max(_op_best_damage_vs(card),
                                              _op_counter_threat_vs(card))
                        if _op_dmg_vs_card > 0:
                            if _op_dmg_vs_card >= card.hp:
                                score -= SCORE_LOOKAHEAD_PROMOTE_KO
                            elif _op_dmg_vs_card <= card.hp * 0.4:
                                score += SCORE_LOOKAHEAD_PROMOTE_SAFE
        
                    _forest_available = (AGENT_STATE.forest_in_play or
                                         hand_counts.get(Forest_of_Vitality, 0) >= 1)
        
                    if card.id == Applin and _forest_available:
        
                        _has_dipplin_hand = (hand_counts.get(Dipplin, 0) >= 1)
                        _has_hydrapple_hand = (hand_counts.get(Hydrapple_ex, 0) >= 1)
                        _has_energy_hand = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                            not state.energyAttached)
                        if _has_dipplin_hand and _has_hydrapple_hand:
        
                            _evo_bonus = 600
                            if _has_energy_hand:
                                _evo_bonus += 150
        
                            _bench_grass_energy = 0
                            for _bp in my_state.bench:
                                if _bp is not None and _bp.id != card.id:
                                    _bench_grass_energy += len(_bp.energies)
                            if _bench_grass_energy >= 1:
                                _evo_bonus += 100
        
                            _mega_evolvable = (AGENT_STATE.meganium_in_play or
                                (hand_counts.get(Meganium, 0) >= 1 and
                                 (field_counts.get(Bayleef, 0) >= 1 or
                                  (field_counts.get(Chikorita, 0) >= 1 and
                                   hand_counts.get(Bayleef, 0) >= 1 and _forest_available))))
                            if _mega_evolvable:
                                _evo_bonus += 100
                            score += _evo_bonus
                        elif _has_dipplin_hand:
        
                            _evo_bonus = 300
                            if _has_energy_hand:
                                _evo_bonus += 100
                            if op_has_ex_immune_active:
                                _evo_bonus += 150
                            score += _evo_bonus
        
                    elif card.id == Chikorita and _forest_available:
        
                        _has_bayleef_hand = (hand_counts.get(Bayleef, 0) >= 1)
                        _has_meganium_hand = (hand_counts.get(Meganium, 0) >= 1)
                        if _has_bayleef_hand and _has_meganium_hand and not AGENT_STATE.meganium_in_play:
        
                            pass
                        elif _has_bayleef_hand and not AGENT_STATE.meganium_in_play:
        
                            pass
        
                    elif card.id == Dipplin and not has_hydrapple:
        
                        if hand_counts.get(Hydrapple_ex, 0) >= 1 and _forest_available:
                            _evo_bonus = 500
                            _has_energy_hand = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                                not state.energyAttached)
                            if _has_energy_hand:
                                _evo_bonus += 150
                            _bench_grass_energy = 0
                            for _bp in my_state.bench:
                                if _bp is not None and _bp.id != card.id:
                                    _bench_grass_energy += len(_bp.energies)
                            if _bench_grass_energy >= 1:
                                _evo_bonus += 100
                            score += _evo_bonus
                        elif hand_counts.get(Hydrapple_ex, 0) >= 1:
        
                            pass
        
                    elif card.id == Bayleef and not AGENT_STATE.meganium_in_play:
        
                        if hand_counts.get(Meganium, 0) >= 1 and _forest_available:
        
                            _has_bench_attacker = any(
                                bp is not None and bp.id in (Hydrapple_ex, Dipplin,
                                    Teal_Mask_Ogerpon_ex, Tapu_Bulu)
                                for bp in my_state.bench)
                            if _has_bench_attacker:
        
                                pass
        
                    if card.id in (Chikorita, Bayleef, Meganium):
                        _meg_designated_attacker = False
                        if (card.id == Meganium and len(card.energies) >= 4 and
                                (AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck)):
                            _meg_other_atk_p = any(
                                bp is not None and (
                                    (bp.id == Dipplin and len(bp.energies) >= 1) or
                                    (bp.id == Tapu_Bulu and len(bp.energies) >= 4) or
                                    (bp.id == Pinsir and len(bp.energies) >= 2))
                                for bp in my_state.bench)
                            if not _meg_other_atk_p:
                                _meg_designated_attacker = True
                        # vs Alakazam (user, registro_010 step 127): a
                        # Meganium (1 prize) READY to attack is a DESIGNATED
                        # attacker -- we prefer it as the active over a 2-prize
                        # ex, even if there are other benched attackers. Without
                        # this the "Meganium active" veto (-10000) prevented
                        # promoting it after retreating the ex (_alakazam_pivot_1prize).
                        elif (card.id == Meganium and op_is_alakazam_deck
                                and _can_attack_now):
                            _meg_designated_attacker = True
                        # Neutralization Zone (id 1247, user): under the zone,
                        # our ex (with a rule box) do NOT damage an opposing
                        # active WITHOUT a rule box (1 prize). If the opposing
                        # active is non-ex and Meganium (non-ex, 140) can attack,
                        # Meganium is the DESIGNATED attacker: it knocks out/damages
                        # the active while the ex do 0. Without this the "Meganium
                        # active" veto (SCORE_NEVER) sank it and a useless ex was
                        # promoted.
                        elif (card.id == Meganium and _can_attack_now
                                and neutralization_zone_active):
                            _nz_meg_op_act = (op_state.active[0]
                                              if op_state.active else None)
                            _nz_meg_data = (card_table.get(_nz_meg_op_act.id)
                                            if _nz_meg_op_act is not None else None)
                            if not (_nz_meg_data
                                    and (_nz_meg_data.ex or _nz_meg_data.megaEx)):
                                _meg_designated_attacker = True
                        # THEIR MATCH POINT OVERRULES THE ENGINE (self-play
                        # mirror, game 276 turn 8; the census in
                        # log/perm_ties_main/FINDINGS.md). We retreat with them
                        # TWO prizes from the game, so every ex on our bench IS
                        # the game: the agent's own projector reads
                        # op_wins_next=True for the Ogerpon ex and for both
                        # Meowth ex, and False for the Meganium at 4 Grass, the
                        # one body that answers and only pays one prize. It
                        # promoted the Ogerpon ex AT ZERO ENERGY -- because this
                        # veto had already removed the Meganium from the menu
                        # (-10000) and the ex was simply the biggest thing left.
                        #
                        # The rule that should have decided is thirty lines
                        # above and HAD fired: prize denial when promoting
                        # (+3000 to a body worth fewer prizes than they need).
                        # `score = SCORE_NEVER` is an assignment, so it
                        # overwrote it. This exemption is that same sentence,
                        # `op_prize <= 2 and prize_count(card) < op_prize`, so
                        # the two halves cannot disagree: at their match point
                        # the front seat is not where we protect Wild Growth.
                        #
                        # It stays as narrow as its neighbours. `_can_attack_now`
                        # -- a Meganium that cannot answer this turn is the
                        # engine and nothing else. And with their pile at ONE it
                        # does not fire (1 < 1 is false), because there the
                        # one-prize body hands over the game exactly like the ex
                        # and the denial buys nothing, which is the measured
                        # sentence the prize-denial rule already carries.
                        elif (card.id == Meganium and _can_attack_now
                                and op_prize <= 2
                                and prize_count(card) < op_prize):
                            _meg_designated_attacker = True
                        # FORCED PROMOTION AFTER A KO: the turn in which we bring
                        # the body up is the OPPONENT's turn -- nobody attacks
                        # any more -- so "ready to attack" is measured with NEXT
                        # turn's energy, not with the current one (user,
                        # registro_013 step 71 vs Crustle, LOST).
                        #
                        # There the KO left us with no active and the opposing
                        # Crustle at 70 HP. Meganium on the bench had 1 Grass = 2
                        # effective (Wild Growth) and another Grass in hand:
                        # bringing it up, next turn we attach and it reaches
                        # 4 -> Solar Beam 140 finishes the Crustle. And it is the
                        # ONLY one that finishes it: Mysterious Rock Inn cancels
                        # the damage of our ex, so Ogerpon/Fezandipiti hit for 0.
                        # `_best_promote_card` had already chosen it (it
                        # contemplates ex immunity, ability immunity, weakness and
                        # next turn's attachment), but this "the Meganium line
                        # does not go active" veto (-10000) sank its bonus
                        # (+4000) and an Ogerpon ex was promoted that neither
                        # attacks nor damages -> a turn given away.
                        # The veto protects the Wild Growth engine from the
                        # BENCH, and that protection is EXPENSIVE to lose: if the
                        # active body falls, every Grass is worth 1 again and
                        # the whole board is left half-built. That is why the
                        # exemption requires a FINISHER, not just "it is the best
                        # candidate": the veto only yields when the KO-aware
                        # selector points at this body AND its hit KNOCKS OUT the
                        # opposing active next turn (`_best_promote_key[0] == 1`).
                        # Measured: exempting without requiring a KO costs -3.6 pp
                        # vs Crustle/Kangaskhan (68.1% vs 71.7%, n=1000) -- it
                        # brought the Chikorita/Bayleef/Meganium line up for
                        # nothing.
                        elif (_forced_ko_promote
                                and _best_promote_card is not None
                                and card is _best_promote_card
                                and _best_promote_key is not None
                                and _best_promote_key[0] == 1):
                            _meg_designated_attacker = True
                        if _meg_designated_attacker:
                            score += 400
                        elif bench_count > 1:
                            score = SCORE_NEVER
        
                    if op_has_ex_immune_active and card.id not in OUR_EX_IDS:
                        score += 150
                    elif op_has_ex_immune_active and card.id in OUR_EX_IDS:
                        score -= 80
        
                    if op_has_ability_immune_active and card.id not in OUR_ABILITY_IDS:
                        score += 180
                    elif op_has_ability_immune_active and card.id in OUR_ABILITY_IDS:
                        score -= 100
        
                    if op_is_fire_deck and card.id == Hydrapple_ex and _can_attack_now:
                        score += 40
        
                    if op_is_control_deck and card.id == Tapu_Bulu and _can_attack_now:
                        score += 50
        
                    _op_is_drednaw_active = (op_state.active and op_state.active[0] is not None
                                             and op_state.active[0].id == Drednaw)
                    if _op_is_drednaw_active:
                        if card.id == Meganium and _can_attack_now:
                            score += 250
                        elif card.id == Meganium and _can_attack_with_attach:
                            score += 200
                        elif card.id == Dipplin and _can_attack_now:
                            score += 180
                        elif card.id == Dipplin and _can_attack_with_attach:
                            score += 150
                        elif card.id == Hydrapple_ex:
                            score -= 150
                        elif card.id == Tapu_Bulu:
                            score -= 150
        
                    _op_is_sylveon_active = (op_state.active and op_state.active[0] is not None
                                             and op_state.active[0].id == Sylveon)
                    if _op_is_sylveon_active:
                        if card.id == Tapu_Bulu and _can_attack_now:
                            score += 280
                        elif card.id == Meganium and _can_attack_now:
                            score += 260
                        elif card.id == Tapu_Bulu and _can_attack_with_attach:
                            score += 220
                        elif card.id == Meganium and _can_attack_with_attach:
                            score += 200
                        elif card.id == Dipplin and _can_attack_now:
                            score += 180
                        elif card.id == Dipplin and _can_attack_with_attach:
                            score += 150
                        elif card.id in OUR_EX_IDS:
                            score -= 200
        
                    if neutralization_zone_active:
        
                        _op_act_nz = op_state.active[0] if op_state.active else None
                        _op_act_nz_rb = False
                        if _op_act_nz is not None:
                            _op_act_nz_data = card_table[_op_act_nz.id]
                            _op_act_nz_rb = (_op_act_nz_data.ex or _op_act_nz_data.megaEx)
                        if not _op_act_nz_rb:
        
                            if card.id == Tapu_Bulu and _can_attack_now:
                                score += 250
                            elif card.id == Meganium and _can_attack_now:
                                score += 220
                            elif card.id == Tapu_Bulu and _can_attack_with_attach:
                                score += 200
                            elif card.id == Meganium and _can_attack_with_attach:
                                score += 180
                            elif card.id == Dipplin and _can_attack_now:
                                score += 160
                            elif card.id == Dipplin and _can_attack_with_attach:
                                score += 140
                            elif card.id in OUR_EX_IDS:
                                score -= 200
        
                    if o.index == AGENT_STATE.plan.attacker - 1:
                        score += 120
        
                    if card.id == Dipplin and hand_counts.get(Hydrapple_ex, 0) >= 1:
                        score += 80
                    elif card.id == Bayleef and hand_counts.get(Meganium, 0) >= 1:
                        score -= 30
                    elif card.id == Applin and hand_counts.get(Dipplin, 0) >= 1:
                        if AGENT_STATE.forest_in_play and hand_counts.get(Hydrapple_ex, 0) >= 1:
                            score += 60
                        else:
                            score += 20
                    elif card.id == Chikorita and hand_counts.get(Bayleef, 0) >= 1:
                        if AGENT_STATE.forest_in_play and hand_counts.get(Meganium, 0) >= 1:
                            score -= 30
                        else:
                            score += 5
        
                    if has_condition:
                        score += 50
        
                    # --- Promotion vs an active IMMUNE to ex (Crustle) ----
                    # Only when the immune Pokemon is ACTIVE (it is not enough
                    # for it to be on the bench): an active Crustle cancels the damage
                    # of OUR ex, so an ex does not attack but serves as a
                    # WALL. Rule: bring up a non-ex attacker that DOES damage
                    # Crustle if it can attack; if none can, bring up an ex
                    # as a wall (with energy first; if none has
                    # energy, Teal Mask Ogerpon ex first).
                    if op_has_ex_immune_active:
                        _crus_is_our_ex = card.id in OUR_EX_IDS
                        # In the FORCED promotion after a KO the body coming
                        # up does not attack this turn (it is the opponent's
                        # turn): the correct criterion is whether it attacks
                        # NEXT turn, counting the attachment from hand (x2 with Wild
                        # Growth). With the "attacks NOW" criterion a Meganium
                        # at 2/4 effective did not count as an attacker and the ex
                        # wall (+3000) took the slot even though it does 0 damage
                        # to the Crustle -- user, registro_013 step 71, LOST.
                        _crus_nonex_attacker = (
                            not _crus_is_our_ex
                            and (_can_attack_now
                                 or (_forced_ko_promote
                                     and _can_attack_with_attach)))
                        if _crus_nonex_attacker:
                            # A non-ex attacker that DOES damage Crustle: top priority.
                            score += 6000
                        elif _crus_is_our_ex:
                            # An ex wall: with energy first; otherwise Teal Mask first.
                            if energy_count >= 1:
                                score += 3000 + energy_count * 10
                            elif card.id == Teal_Mask_Ogerpon_ex:
                                score += 2500
                            else:
                                score += 2000
        
                    # A decisive bonus to the best attacker against the opposing
                    # ACTIVE (computed before the loop from effective damage). It
                    # holds for any active: Mega/normal -> the one that hits
                    # hardest (Hydrapple ex); Crustle/Cornerstone -> the best
                    # non-ex / non-ability body.
                    if (_best_promote_card is not None
                            and card is _best_promote_card
                            and not (_prize_mismatch_matchup
                                     and _best_promote_key is not None
                                     and _best_promote_key[0] == 0)):
                        # vs Raging Bolt / Mega Abomasnow, a "best candidate"
                        # that does NOT knock out is just a doomed ex: without the
                        # bonus, the +2500 of the 1-prize body decides the wall.
                        score += 4000
        
                    # Rule (user) vs Mega Lucario with no benched attacker:
                    # promote a BASIC first (Applin as the priority) or, if there
                    # is no basic, Dipplin. The other bodies (ex, Stages 1/2
                    # other than Dipplin) keep their current score, so
                    # if there is neither a basic nor a Dipplin the normal logic
                    # applies.
                    if _lucario_ko_prefer_basic:
                        _luc_prom_data = card_table.get(card.id)
                        _luc_is_basic = (
                            _luc_prom_data is not None
                            and not getattr(_luc_prom_data, 'stage1', False)
                            and not getattr(_luc_prom_data, 'stage2', False))
                        if card.id == Applin:
                            score = 9000
                        elif _luc_is_basic:
                            score = 8500
                        elif card.id == Dipplin:
                            score = 8000
        
                    # Rule (user, log 86345562 p55): prefer bringing up a
                    # 1-prize BASIC (Applin) instead of a 2-prize ex
                    # when no body can attack and we have a Lillie's to
                    # refill. It keeps the ex -- and their energy -- safe on the
                    # bench. No basic -> the normal promotion (an ex) applies.
                    if _refresh_promote_prefer_basic:
                        _ref_pb_data = card_table.get(card.id)
                        _ref_is_basic = (
                            _ref_pb_data is not None
                            and not getattr(_ref_pb_data, 'stage1', False)
                            and not getattr(_ref_pb_data, 'stage2', False))
                        if card.id not in OUR_EX_IDS and _ref_is_basic:
                            if card.id == Applin:
                                score = 6000
                            else:
                                score = 5500
                            # Tie-break by HP between 1-prize basics
                            # (user, registro_009 step 61 vs Dragapult): the
                            # rule above was born to prefer a basic
                            # over an ex, but between TWO basics it always
                            # brought up the 40 HP Applin -- a prize given away
                            # and also a piece of the Hydrapple line we
                            # want to evolve on the bench. With a really
                            # resilient 1-prize body available
                            # (Tapu Bulu, 140 HP) that is the wall: it takes
                            # the opponent's turn and it is the one we are charging.
                            if (card.hp or 0) >= 100:
                                score = 6100
        
                    # Generalised mismatch (user, registro_004 step 37):
                    # with no benched attacker and the opponent one-shotting even
                    # our biggest tank, promote a 1-prize BASIC
                    # (Applin as the priority) or Dipplin instead of a 2-prize ex.
                    # Same scores as `_lucario_ko_prefer_basic` for identical
                    # behaviour with any deck. Tie-break by HP between basics.
                    if _ko_prefer_basic_general:
                        _gpb_data = card_table.get(card.id)
                        _gpb_is_basic = (
                            _gpb_data is not None
                            and not getattr(_gpb_data, 'stage1', False)
                            and not getattr(_gpb_data, 'stage2', False))
                        if card.id == Applin:
                            score = 9000
                        elif _gpb_is_basic and card.id not in OUR_EX_IDS:
                            score = 8500 + (card.hp or 0) // 10
                        elif card.id == Dipplin:
                            score = 8000
        
                    # THE ATTACKER THAT CAN STILL WALK BACK (user, registro_008
                    # step 109 vs Archaludon ex, LOST -- episode 93497723,
                    # deck-agnostic). The front spot goes to the body that
                    # attacks -- today, or after this coming turn's attachment
                    # -- over the cheap wall the three rules above hand it to,
                    # because this promotion resolves at the END of their turn
                    # and a body that can pay its own retreat does not have to
                    # be standing there when their reply lands. See
                    # `_promo_deferred_attacker` in `agent()` for the board and
                    # the two guards that make the deferral real.
                    #
                    # `score > 0` for the same reason the last stand below
                    # carries it: it must not resurrect a body some veto has
                    # already removed -- "the Meganium line does not go active"
                    # (SCORE_NEVER) is protecting the Wild Growth multiplier,
                    # and an attacker bought with the engine that feeds it is
                    # not a bet, it is a trade.
                    if (_forced_ko_promote and isinstance(card, Pokemon)
                            and _promo_deferred_attacker is not None
                            and card is _promo_deferred_attacker
                            and score > 0):
                        score = PROMO_DEFERRED_ATTACKER

                    # THE LAST STAND (user, registro_011 step 130 vs Alakazam,
                    # LOST -- episode 91532527, deck-agnostic). At their match
                    # point every body on our bench pays at least their
                    # remaining pile: whichever one goes to the front, their
                    # next knockout ends the game. The price tag stops being
                    # information and the front spot goes to whoever absorbs
                    # their reply best -- see `_mp_last_stand` in `agent()` for
                    # the board and the reading.
                    #
                    # `score > 0` so that it cannot resurrect a vetoed body:
                    # "the Meganium line does not go active" (SCORE_NEVER) is
                    # protecting the Wild Growth engine, and a tank that costs
                    # us the engine is not a last stand. And it goes BEFORE the
                    # two branches about acting first, which keep the last word.
                    if (_mp_last_stand is not None and card is _mp_last_stand
                            and score > 0):
                        score = PROMO_LAST_STAND

                    # Promote the ALMOST ready attacker that finishes next
                    # turn (user, registro_009 p111): it dominates the basic wall
                    # and any other promotion branch. See
                    # `_promote_setup_ko_attacker`.
                    if (_promote_setup_ko_attacker is not None
                            and card is _promote_setup_ko_attacker):
                        score = 9500

                    # THE OTHER HALF OF THE FIRST-TURN WALL PIVOT (user,
                    # registro_002 step 14 vs Marnie, LOST). The retreat is
                    # decided in the MAIN menu; WHICH body goes up is decided
                    # here, one observation later, and by then nothing on the
                    # board says why we retreated. Without this the generic
                    # ranking (prizes x 1000 + HP) promotes the biggest body,
                    # which is precisely the 2-prize ex the pivot exists to
                    # hide.
                    #
                    # SelectContext.SWITCH only -- the VOLUNTARY retreat we
                    # just chose. The promotion after a knockout (TO_ACTIVE) is
                    # a different question, with its own measured logic, and it
                    # does not get to be answered by a flag about our own
                    # first turn. 9400 leaves the guaranteed finisher above it
                    # (9500) and keeps the terminal survival adjustments -- the
                    # one that knocks out, match point -- with the last word.
                    #
                    # It reads `_ft_wall_promote` and not `_ft_wall_pivot`
                    # (user, registro_002 step 33 vs Marnie): by the time this
                    # menu arrives the simulator has already discarded the
                    # retreat cost from the active, and the pivot's
                    # affordability test -- the energy that is LEFT on a body
                    # that just paid -- came out False on precisely the boards
                    # the rule was written for. See the note in main.py.
                    if (_ft_wall_promote and _ft_wall_body is not None
                            and card is _ft_wall_body
                            and context == SelectContext.SWITCH):
                        score = 9400

                    # ANTI-CUBCHOO: do not promote a body that would be left NAILED
                    # down (user, registro_036 step 146). Same principle as the
                    # evolution veto vs Cubchoo: against a deck that locks and
                    # discards energy, bringing up a Pokemon with a HIGH retreat
                    # cost that cannot pay it leaves it trapped there.
                    # When retreating after Teal Dance, Hydrapple ex (retreat 3, 2
                    # effective energies -> nailed down) beat the Teal Mask
                    # Ogerpon ex 623 to 555 (retreat 1, 4 energies), which also
                    # KNOCKS OUT and keeps its mobility for the next
                    # pivot. It is a PENALTY, not a veto: if the slow
                    # body is the only option, it is still the one promoted.
                    if (op_is_cubchoo_deck and score > 0
                            and isinstance(card, Pokemon)):
                        _cp_rc = RETREAT_COST.get(card.id, 1)
                        if _cp_rc >= 3 and len(card.energies) < _cp_rc:
                            score -= 300
        
                    # SURVIVAL (user, registro_005 step 64). A TERMINAL
                    # adjustment: it goes after all the promotion branches
                    # so it has the last word. See the block that computes
                    # `_promo_survivors` / `_promo_min_prize`.
                    #
                    # The TWO exemptions below (the one that knocks out and the
                    # guaranteed finisher) share a premise: the promoted body
                    # reaches OUR turn alive and attacks first. Under
                    # Festival Lead that premise is false -- the opponent repeats
                    # the attack as soon as we choose -- so a candidate that
                    # does NOT survive loses both and falls to the
                    # survival/prizes band. See `op_double_attack_pending`.
                    _promo_gets_to_attack = not (
                        op_double_attack_pending
                        and isinstance(card, Pokemon)
                        and not _promo_survives(card))
                    if (score > 0 and isinstance(card, Pokemon)
                            and _promo_op_act is not None
                            and _promo_gets_to_attack
                            and _promo_kos_op(card)):
                        # PRIORITY OF THE ONE THAT KNOCKS OUT (user): bring up the
                        # charged attacker instead of the tank ONLY when that
                        # attacker knocks the opponent out. Taking the prize
                        # rules even if it dies afterwards; if it does not knock
                        # out, survival and the prizes below govern.
                        score += PROMO_KO_BONUS
                    elif (_promote_setup_ko_attacker is not None
                            and card is _promote_setup_ko_attacker
                            and _promo_gets_to_attack):
                        # GUARANTEED FINISHER NEXT TURN (user,
                        # registro_007 step 126): the promotion after a KO is
                        # resolved at the END of the opponent's turn, so the
                        # next turn is OURS and this body attacks
                        # FIRST. Neither the doomed penalty nor the prize one
                        # applies: the opponent never gets to hit it.
                        # Without this exemption the -1500 for being a 2-prize
                        # ex sank the 9500 of
                        # `_promote_setup_ko_attacker` (8000) below the
                        # basic wall of `_ko_prefer_basic_general`
                        # (8500+hp/10), exactly what that rule's note said it
                        # prevented: a Tapu Bulu at 1/4 energies was brought up
                        # -- with no attack and a retreat cost of 3 -- instead of the
                        # Ogerpon ex at 2/3 that finished the Grimmsnarl ex through
                        # weakness.
                        pass
                    elif (_promo_deferred_attacker is not None
                            and card is _promo_deferred_attacker
                            and _promo_gets_to_attack):
                        # THE ATTACKER THAT CAN STILL WALK BACK (user,
                        # registro_008 step 109 vs Archaludon ex): the same
                        # exemption as the finisher above, reached by the other
                        # road. That one is spared because it knocks out first,
                        # so their blow never comes; this one is spared because
                        # it can RETREAT first, so their blow does not find it.
                        # Both price a reply that lands a whole turn of ours
                        # later, and both are sunk by the same arithmetic if the
                        # exemption is missing: -6000 doomed, or -1500 per extra
                        # prize, takes the 9200 of `PROMO_DEFERRED_ATTACKER`
                        # below the 8500 + hp/10 of the very basic wall the rung
                        # was written to outrank.
                        #
                        # Under Festival Lead `_promo_gets_to_attack` is already
                        # False for a body that does not survive, and rightly:
                        # there the opponent attacks again the instant we choose,
                        # so there is no turn of ours to defer anything to and
                        # the exit is worth nothing.
                        pass
                    elif (score > 0 and isinstance(card, Pokemon)
                            and _promo_op_act is not None):
                        if _promo_survivors > 0:
                            # 1) Somebody endures: the one that dies without taking
                            #    a prize stops being a candidate. A penalty
                            #    (not a veto) so the relative order among the
                            #    doomed is kept if there is no alternative.
                            #
                            #    UNLESS every survivor is MUTE against the
                            #    opposing active (a wall that cancels our ex or
                            #    our abilities) and this body is one of the few
                            #    that DOES touch it -- see `_promo_wall_relief`
                            #    in `agent()`, user, registro_008 step 78 vs
                            #    Crustle. There "it endures" means "the wall
                            #    already switched it off": the penalty is exactly
                            #    the size of the +6000 the wall rule gives the
                            #    unblocked attacker and cancelled it, promoting a
                            #    charged ex that dealt 0.
                            #
                            #    AND UNLESS this body is the pre-evolution that
                            #    `_promo_evo_koer` picked: the penalty measures a
                            #    hit it never takes AS IT IS. Our turn comes
                            #    first, the evolution goes on it from hand and
                            #    what the opponent finds in front of them is the
                            #    finisher, not the 80 HP pre-evolution (user,
                            #    registro_009 step 120 vs Mega Lopunny ex). It is
                            #    the same exemption the bodies that knock out
                            #    already have -- "we take a prize before dying" --
                            #    reaching the one that knocks out one evolution
                            #    later.
                            if (not _promo_survives(card)
                                    and card is not _promo_evo_koer
                                    and not (_promo_wall_relief
                                             and _promo_damage_to_op is not None
                                             and _promo_damage_to_op(card) > 0)):
                                score -= PROMO_DOOMED_PENALTY
                        elif _promo_min_prize is not None:
                            # 2) Nobody endures: hand over the FEWEST prizes
                            #    possible. It reinforces the mismatch rules
                            #    that already prefer a 1-prize body.
                            score -= (PROMO_PRIZE_PENALTY
                                      * (prize_count(card) - _promo_min_prize))
        
                    # THE COVER THE SEAT LEAVES BEHIND (user, pending written
                    # 12 August 2026 from episode 92355371 step 62 vs Festival
                    # Lead, LOST). While it sits on the BENCH the Tera of a Teal
                    # Mask Ogerpon ex prevents all damage from attacks, so the
                    # promotion is not free even when the body survives the blow
                    # it is being measured against: it hands over an untouchable
                    # seat and puts two prizes in front of an engine that spreads
                    # knockouts. In the record it came up, took 120, and the next
                    # wave took it with both prizes.
                    #
                    # It is charged where the cover is REAL and the choice is
                    # ours: the forced promotion after a knockout. On a voluntary
                    # retreat the body is being asked for something it can only do
                    # from the front, and the turn is paying a fee to ask.
                    #
                    # `PROMO_TERA_COVER_PRICE` is 500 and the size is the point:
                    # it cannot reach the knockout bonus (+20000), the doomed
                    # penalty (-6000) or the prize band (-1500 each), all three
                    # measured rules of their own. It reaches exactly the band
                    # where the only argument for the ex is that it is the
                    # biggest body left.
                    if (PROMOTE_TERA_PAYS_FOR_ITS_COVER
                            and _forced_ko_promote
                            and isinstance(card, Pokemon)
                            and card.id == Teal_Mask_Ogerpon_ex
                            and score > 0):
                        score -= PROMO_TERA_COVER_PRICE

                    # MATCH POINT (user, log 88971843 step 117). When the
                    # opponent only needs to knock THIS body out to take
                    # the last prize, bringing up a doomed body is not a bad
                    # trade: it is losing the game. As long as there is
                    # ANY candidate that endures, the doomed one stops being
                    # an option -- a VETO, not a penalty, so no bonus
                    # can buy it (the 20000 of the one that knocks out, the
                    # 9500 of the guaranteed finisher, the 8500+ of the basic
                    # wall). It goes AFTER the whole chain, with the last
                    # word.
                    #
                    # Two guards keep it narrow:
                    #   * `_promo_survivors > 0`: if NOBODY endures the
                    #     game is lost anyway and the prize rule above
                    #     governs (we do not veto the whole bench).
                    #   * the one that GETS to attack and KNOCKS OUT is exempt:
                    #     there we take a prize before dying and the play can
                    #     close the game in our favour. Under Festival
                    #     Lead `_promo_gets_to_attack` is already False for the
                    #     doomed ones, so the exemption does not open.
                    #   * the guaranteed finisher is exempt WHEN ITS KNOCKOUT
                    #     ENDS THE GAME (`_promo_ko_wins_the_game`, user,
                    #     registro_013 step 116). The exemption above reads
                    #     `_promo_kos_op`, which measures TODAY's energy, so the
                    #     body that is one attachment from lethal fails it and
                    #     the veto sank the very play that wins. It is the same
                    #     sentence the +9500 branch thirty lines up is written
                    #     with -- this promotion resolves at the END of their
                    #     turn, ours comes next and this body attacks FIRST --
                    #     and the guard makes it unambiguous: our prize is the
                    #     last one, so their reply never happens.
                    # AND NOT `_promo_bet_walks_back` HERE, ON PURPOSE. The
                    # sibling veto at the bottom of this chain lets the named
                    # finisher through when it can pay its own retreat (user,
                    # registro_006 step 77 vs Archaludon ex), and the same
                    # sentence reads true of this one -- their reply lands a
                    # whole turn of OURS later, and a body that can step aside
                    # is not there to receive it. It is not written here because
                    # this veto asks for something that one does not:
                    # `_promo_survivors > 0`, a body that ENDURES their blow.
                    # That is a different board -- the alternative to the bet is
                    # a tank that lives, not a mute wall that dies anyway -- and
                    # no record in either corpus produces it, so the trade has
                    # never been measured. The mutation gate says the same
                    # thing out loud: written here, the term is a line no test
                    # in the repository can kill.
                    #
                    # With the opposing damage unreadable (a projection of 0) EVERYBODY
                    # "survives" and this does not fire: with no evidence nothing is
                    # vetoed.
                    if (_forced_ko_promote and isinstance(card, Pokemon)
                            and _promo_op_act is not None
                            and _promo_survivors > 0
                            and op_prize <= prize_count(card)
                            and not _promo_survives(card)
                            and not (_promo_gets_to_attack
                                     and _promo_kos_op(card))
                            and not (_promo_ko_wins_the_game
                                     and _promote_setup_ko_attacker is not None
                                     and card is _promote_setup_ko_attacker)):
                        score = PROMO_MATCH_POINT_VETO

                    # MATCH POINT AMONG THE ONES THAT KNOCK OUT (user,
                    # registro_014 step 130 vs Alakazam, LOST -- episode
                    # 90350002, deck-agnostic).
                    #
                    # `PROMO_KO_BONUS` says it plainly: "among several knockers
                    # the base score decides". That base score orders by prizes
                    # first and HP second, and at match point the first half of
                    # it is a fiction -- their next knockout takes their last
                    # prize whichever of our bodies it lands on -- while the
                    # second half is the whole question. Three of our bodies
                    # finished the same Alakazam that turn; the one the base
                    # score picked was the 140 HP Tapu Bulu, and 200 of Powerful
                    # Hand went through it. The 210 HP Ogerpon ex it beat took
                    # the same prize and would still have been standing.
                    #
                    # So the doomed penalty, which the knockers are exempt from
                    # by design, comes back for them HERE and only here: their
                    # exemption is written on "the play can close the game in our
                    # favour", and at match point against us it cannot -- unless
                    # our own knockout closes it FIRST, which is the exemption
                    # kept below.
                    #
                    # A penalty and not a veto, and the same size as the ordinary
                    # doomed one: it reorders INSIDE the +20000 band -- the
                    # knocker that dies still outranks any body that takes no
                    # prize at all -- and never surrenders the knockout itself.
                    #
                    # `_mp_front_survivors` / `_mp_outlasts` read their attack
                    # counting their HAND, which is where this family of cards
                    # prints 0 damage; with an unreadable attack nobody is
                    # penalised. See the block in `agent()`.
                    if (isinstance(card, Pokemon) and score > 0
                            and _promo_op_act is not None
                            and op_prize <= prize_count(card)
                            and (_mp_front_survivors or 0) > 0
                            and callable(_mp_outlasts)
                            and not _mp_outlasts(card)
                            and not (_promo_kos_op(card)
                                     and my_prize <= prize_count_op(_promo_op_act))):
                        score -= PROMO_DOOMED_PENALTY

                    # THE FRONT SPOT AMONG THE ONES THAT KNOCK OUT (user,
                    # registro_012 step 172 vs Alakazam, LOST -- episode
                    # 91919734, deck-agnostic).
                    #
                    # The rule right above is this same sentence read through
                    # SURVIVAL, and survival is exactly what could not be read on
                    # that board: their reply is projected onto the active we are
                    # about to knock out, and our own Xerosic had just cut their
                    # hand to three, so Powerful Hand printed 100 and all five
                    # candidates "outlasted" it. Two of them finished the same
                    # Alakazam -- a Teal Mask Ogerpon ex at 210/210 and a
                    # Hydrapple ex at 140 of its 330 -- and the base score picked
                    # the wounded one by TWO points.
                    #
                    # So among the knockers, and only among them, the order is
                    # the user's: first the body that leaves them SHORT of their
                    # pile (a Meganium, a Tapu Bulu -- while that price is still
                    # information), then the one with the most CURRENT HP. See
                    # `ko_front_price_rung` and the block in `agent()`.
                    #
                    # A penalty on the dominated body and never a bonus on the
                    # chosen one: it reorders INSIDE the +20000 band, so it can
                    # never promote a body that takes no prize, and it is sized
                    # (`PROMO_KO_FRONT`) to beat the flavour bonuses of the base
                    # score and to yield to every rule that scores in thousands.
                    if (isinstance(card, Pokemon) and score > 0
                            and _promo_op_act is not None
                            and callable(_ko_front_outranked)
                            and _ko_front_outranked(card)):
                        score -= PROMO_KO_FRONT

                    # THE FRONT SPOT UNDER A LOCK THAT MUTES IT (user,
                    # registro_010 step 81, episode 93149196 vs a Cubchoo stall
                    # deck, WON). The rule right above orders the knockers by who
                    # OUTLIVES whom, and against this deck that question is
                    # empty: *Snotted Up* does 10, everybody outlives it, so the
                    # seat went to the body with the most HP. The seat's real
                    # price here is MOBILITY. The lock mutes whatever is in
                    # front, so the body promoted today is the body that has to
                    # buy its way out tomorrow, and it pays in whole Grass cards.
                    #
                    # On that board two of ours finished the same 70 HP Cubchoo
                    # -- a Hydrapple ex at 330/330, retreat 3, and a Teal Mask
                    # Ogerpon ex at 210/210, retreat 1 -- and the HP tie-break
                    # handed the seat to the Hydrapple by 1272 points: the same
                    # prize today, three times the fee tomorrow.
                    #
                    # It completes the -300 thirty lines up, which reads the same
                    # matchup one question short: that one demotes a body that
                    # CANNOT pay its retreat, and the Hydrapple could pay -- with
                    # two of the four Grass cards on our field.
                    #
                    # `_cubchoo_ko_rotation_min` is the cheapest retreat among
                    # the bench bodies that knock out, the SAME number the
                    # retreat that gets us here was priced with
                    # (`_cubchoo_mute_rotates` in agent()): the decision that
                    # pays for the pivot and the decision that spends it must not
                    # be able to disagree about which body it was for. A penalty
                    # on the dominated knocker and never a bonus, so it reorders
                    # inside the +20000 band and can never promote a body that
                    # takes no prize.
                    if (isinstance(card, Pokemon) and score > 0
                            and _promo_op_act is not None
                            and _cubchoo_ko_rotation_min is not None
                            and _promo_kos_op(card)
                            and RETREAT_COST.get(card.id, 1)
                            > _cubchoo_ko_rotation_min):
                        score -= PROMO_KO_ROTATION

                    # THEIR MATCH POINT, READ WITH THE ATTACK'S REAL SCALE
                    # (self-play mirror, game 90 turn 17; see
                    # `_mp_price_ends_the_game` in agent() for the whole story).
                    # The veto above asks whether the candidate survives through
                    # a projector that reads Syrup Storm as its printed 30, so on
                    # a board where their real blow is 210 every candidate looked
                    # safe and a Teal Mask Ogerpon ex went to the front worth
                    # exactly the two prizes they still needed.
                    #
                    # It is a VETO and it goes LAST, after the whole chain and
                    # after the doomed penalty, for the same reason the one above
                    # is: no bonus written for a board where the front body lives
                    # gets to buy a body whose death ends the game. And it is
                    # written so that it can only ever REMOVE a candidate that
                    # pays their last prize -- never raise a more expensive one --
                    # with `_mp_cheaper_candidate` guaranteeing the menu still
                    # has something to promote afterwards.
                    #
                    # The one exemption is the one its neighbours already carry:
                    # a body that knocks out and with that closes OUR count first
                    # wins the game before their reply exists. It reaches the
                    # guaranteed finisher for the same reason it does one veto
                    # up: `_promo_kos_op` measures TODAY's energy, and the body
                    # this branch of the chain is about is the one that is a
                    # single attachment from lethal ON OUR TURN, which comes
                    # first (see `_promo_ko_wins_the_game`).
                    #
                    # AND THE SAME FINISHER IS EXEMPT WHEN IT CAN WALK BACK
                    # (`_promo_bet_walks_back`, user, registro_006 step 77 vs
                    # Archaludon ex, episode 92848103, LOST). This is the veto
                    # that fired on that board: six prizes to TWO, so our
                    # knockout was nowhere near ending the game and the
                    # exemption above stayed shut, while the Ogerpon ex it
                    # removed was one attachment from finishing their
                    # Archaludon and carried the Grass that pays its own
                    # retreat. What this veto prices -- "their blow takes this
                    # body and with it their last prize" -- is a reply that
                    # arrives a whole turn of OURS later, and a body that can
                    # step aside is not there to receive it. See `agent()`.
                    #
                    # THE EXEMPTION REACHES FURTHER NOW, AND STILL ONLY TO A
                    # FINISHER (user, registro_008 step 109 vs Archaludon ex,
                    # episode 93497723, LOST). On that board the clause above
                    # stayed shut for a reason that had nothing to do with the
                    # trade it prices: our Teal Mask Ogerpon ex sat on four
                    # effective Grass, one attachment from burying their 300 HP
                    # Archaludon, and carried the Grass that pays its own
                    # retreat -- but because it could already swing for 240,
                    # `_promote_setup_ko_attacker` never even ran and could not
                    # name it. The veto removed it at -30000 and the slot went to
                    # a Tapu Bulu at 0/4 that could neither attack nor step
                    # aside. The fix is in that selector's guard, not here.
                    #
                    # AND IT IS DELIBERATELY NOT WIDENED TO EVERY ATTACKER THAT
                    # CAN WALK BACK. `_promo_deferred_attacker` names the best
                    # body we can put in front when nobody knocks out, and it
                    # outranks the cheap-wall family for exactly the reason
                    # written there -- but the exit only saves us if we USE it,
                    # and a body that can attack without knocking out will
                    # attack. At their match point that is not a deferred
                    # sacrifice, it is the game: we swing for less than lethal,
                    # their reply lands and takes their last prize. What earns
                    # the exemption here is the knockout that means their reply
                    # never comes.
                    if (isinstance(card, Pokemon)
                            and _promo_op_act is not None
                            and _mp_cheaper_candidate
                            and callable(_mp_price_ends_the_game)
                            and _mp_price_ends_the_game(card)
                            and not (_promo_kos_op(card)
                                     and my_prize <= prize_count_op(_promo_op_act))
                            and not ((_promo_ko_wins_the_game
                                      or _promo_bet_walks_back)
                                     and _promote_setup_ko_attacker is not None
                                     and card is _promote_setup_ko_attacker)):
                        score = PROMO_MATCH_POINT_VETO

                    # TIE-BREAK BETWEEN SURVIVORS (user, priorities 3 and
                    # 4). With survival already settled (1) and the Wild Growth
                    # multiplier protected (2, via the "the Meganium line
                    # does not go active" veto), between the bodies that
                    # ENDURE and where none knocks out, what rules is: first the one
                    # CLOSEST to being able to attack -- measured in ATTACHMENTS, not
                    # in energies, because with Meganium in play one Grass
                    # is worth two -- and on a tie the one that concedes FEWER prizes.
                    # A 160 HP tank that would not attack for three turns is worth
                    # less than a 140 HP one that attacks next turn.
                    #
                    # Bounded to 0..450: it rules over the BASE score of the
                    # promotion -- which is around 150-250 and orders by HP, which
                    # is exactly the criterion the user puts BELOW these
                    # two -- and stays far below any decisive rule
                    # (+4000 for the best attacker, 8000-9500 for the named
                    # branches, +20000 for the one that knocks out), which still
                    # have the last word. 60 points was not enough: measured
                    # in a real tie, a 210 HP Ogerpon ex THREE attachments away
                    # from attacking still beat a 140 HP Tapu
                    # Bulu that was TWO away (193 vs 144 of base score).
                    #
                    # The one that KNOCKS OUT is excluded: among knockers the
                    # base score decides, as PROMO_KO_BONUS documents. And note that
                    # priority (3)+(4) is ALREADY decisive -- and in this same
                    # order -- inside `_promote_setup_ko_attacker`
                    # (`_ps_key`); this covers the gap that rule leaves
                    # out: the candidates whose completed attack does NOT
                    # finish the opposing active.
                    if (_forced_ko_promote and isinstance(card, Pokemon)
                            and score > 0
                            and _promo_op_act is not None
                            and _promo_survivors > 0
                            and _promo_survives(card)
                            and not _promo_kos_op(card)):
                        _tb_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(card.id)
                        if _tb_req is None:
                            _tb_steps = 3      # it does not attack: the furthest away
                        else:
                            _tb_missing = max(0, _tb_req - len(card.energies))
                            _tb_unit = max(1, _grass_attach_unit())
                            _tb_steps = min(3, -(-_tb_missing // _tb_unit))
                        score += 300 - 100 * _tb_steps
                        if prize_count(card) <= 1:
                            score += 150
                else:
        
                    # Target of the Boss's Orders GUST: migrated to the RULES
                    # ENGINE (phase 4). Definitions and strategic comments in
                    # _RULES_GUST_NUISANCE / _AJUSTES_GUST_* (before agent()).
                    if card.id in DUNSPARCE_IDS:
                        # Rule (user): NEVER gust a Dunsparce (ids 65 and
                        # 305), neither in nuisance mode nor in offensive mode.
                        score = SCORE_FORBID
                    else:
                        _gt_ctx = _ctx_gust_target(
                            card, o, my_state, op_state, state, hand_counts,
                            total_grass, bench_count, neutralization_zone_active,
                            op_is_alakazam_deck, op_has_latias_ex,
                            (op_has_dragapult or op_has_dreepy_line),
                            (op_has_typhlosion or op_has_ethan_preevo),
                            my_prize=my_prize, op_prize=op_prize)
                        # NOTE (jul 2026 cycle, MEASURED AND REVERTED): an attempt
                        # was made to decide the mode PER CANDIDATE (with
                        # `not _gt_ctx.can_ko` in this condition) so that
                        # a target knockable after retreating --
                        # Dwebble 650 vs Kangaskhan-jam 800 -- would evaluate
                        # in offensive mode with the active stuck. See the twin note
                        # in `crustle_gust_worth_it`: -1.4 points
                        # vs crustle with n=4000/branch, reverted as a block.
                        if _active_cant_attack_this_turn or _sel_active_cant_attack:
                            score = _resolve_with_trace(
                                "boss->objetivo/estorbo", _RULES_GUST_NUISANCE,
                                _ADJUST_GUST_NUISANCE, _gt_ctx, default=-200)
                        else:
                            score = _resolve_with_trace(
                                "boss->objetivo", [], _ADJUST_GUST_OFFENSIVE,
                                _gt_ctx, default=0)
            elif context == SelectContext.SETUP_ACTIVE_POKEMON:
                # WHO STARTS IN FRONT (user, ago 2026). The order and the reason
                # for each rung are in SETUP_ACTIVE_BASIC_ORDER /
                # SETUP_ACTIVE_EX_ORDER (ptcg/cards/ids.py); the one sentence
                # that governs the whole branch is that NO ex outranks ANY
                # non-ex Basic, because what the active spot decides is whether
                # the opponent's first knockout pays one prize or two.
                #
                # Every body in this deck is a Basic, ex included, so the split
                # is read off the CARD TABLE and not off `prize_count`: at setup
                # the option points at a card in HAND, which has no
                # `energyCards` or `tools` for that helper to walk.
                #
                # THE OLD DUPLICATE TIE-BREAK IS GONE. The previous ladder gave
                # a Chikorita/Applin we held TWO of the same score (7), which on
                # a hand with two Chikorita and one Applin put the Chikorita in
                # front -- the user's order says Applin. Holding a second copy
                # is a reason to be relaxed about the one we seat, not a reason
                # to change WHICH line starts developing.
                _setup_data = card_table.get(card.id)
                _setup_is_ex = bool(
                    _setup_data is not None
                    and (getattr(_setup_data, 'ex', False)
                         or getattr(_setup_data, 'megaEx', False)))
                if not _setup_is_ex and card.id in SETUP_ACTIVE_BASIC_ORDER:
                    score = (SETUP_ACTIVE_BASIC_TOP
                             - SETUP_ACTIVE_STEP
                             * SETUP_ACTIVE_BASIC_ORDER.index(card.id))
                elif not _setup_is_ex:
                    # Any other one-prize Basic the opening hand happens to
                    # carry (a Pinsir): below the three the user names, above
                    # every ex. Without this rung an unnamed Basic tied with the
                    # "anything else" floor and a 210 HP ex took the front.
                    score = SETUP_ACTIVE_OTHER_BASIC
                elif card.id in SETUP_ACTIVE_EX_ORDER:
                    score = (SETUP_ACTIVE_EX_TOP
                             - SETUP_ACTIVE_STEP
                             * SETUP_ACTIVE_EX_ORDER.index(card.id))
                else:
                    score = SETUP_ACTIVE_OTHER

            elif context == SelectContext.SETUP_BENCH_POKEMON:
        
                if card.id == Chikorita:
                    score = 8
        
                    if op_is_fire_deck or op_is_aggro_deck:
                        score = 10
                elif card.id == Applin:
                    score = 7
        
                    if op_bench_snipe_threat:
                        score = 4
                    elif op_is_fire_deck or op_is_aggro_deck:
                        score = 8
                elif card.id == Teal_Mask_Ogerpon_ex:
                    # A MAXIMUM OF 2 Teal Mask Ogerpon ex IN PLAY, also at setup
                    # (user, log 89629887 vs Crustle/Cornerstone Mask Ogerpon ex,
                    # LOST): the opening hand had THREE Ogerpon ex and all three
                    # went to the bench, because this branch scored every copy
                    # the same (6) and the setup takes every option with a
                    # score >= 0. From turn 2 the opposing active was a
                    # Cornerstone Mask Ogerpon ex, whose Cornerstone Stance
                    # cancels the attacks of Pokemon WITH an ability: the three
                    # bodies did 0 for the rest of the game, they were 6 prizes
                    # parked on the bench, they left only one free slot for the
                    # attackers that DO damage in that matchup (Tapu Bulu, the
                    # Chikorita->Bayleef->Meganium line, Dipplin) and, with
                    # three ex on the field, the `_block_4th_ex` veto of the PLAY
                    # closed the door on any further ex -- Meowth ex included.
                    #
                    # The cap is DECK-AGNOSTIC because the setup is BLIND: the
                    # opponent has not revealed their active, so neither
                    # `op_is_crustle_deck` nor `op_is_cornerstone_deck` can be on
                    # yet. It costs nothing to hold the third copy in hand: the
                    # PLAY branch already treats it as marginal (20500 only with a
                    # Grass in hand, SCORE_VETO otherwise) and puts it down later
                    # if the matchup allows it, whereas a body already benched can
                    # never be taken back.
                    #
                    # `field_counts` does NOT serve here: at setup the bench is
                    # empty and the active is FACE DOWN, so it counts 0 for every
                    # option. What is counted is the ordinal of the copy inside
                    # the hand plus `setup_active_id`, which the SETUP_ACTIVE
                    # decision wrote down (see finalize.py).
                    _setup_og_in_play = (
                        1 if AGENT_STATE.setup_active_id == Teal_Mask_Ogerpon_ex
                        else 0)
                    for _sh in (my_state.hand or [])[:o.index]:
                        if _sh.id == Teal_Mask_Ogerpon_ex:
                            _setup_og_in_play += 1
                    if _setup_og_in_play >= 2:
                        score = SCORE_VETO
                    else:
                        score = 6

                        if op_is_fire_deck:
                            score = 7
                elif card.id == Meowth_ex:

                    score = SCORE_VETO
                elif card.id == Fezandipiti_ex:
                    # At the start of the game (setup) we do NOT put Fezandipiti
                    # ex on the bench unless it is the ONLY Pokemon in hand
                    # (forced to place a basic). Fezandipiti ex is weak to
                    # Fighting ({F}) and is worth 2 prizes, and its Flip the
                    # Script ability only works after being knocked out; putting it down
                    # at the start gives away an easy 2-prize KO (critical vs Mega Lucario,
                    # which is NOT yet detectable at setup: the opponent has not
                    # revealed their active). If there is another Pokemon in hand, we
                    # keep it (it can be put down later when convenient).
                    _setup_hand_poke = 0
                    for _shp in (my_state.hand or []):
                        _shp_data = card_table.get(_shp.id)
                        if _shp_data is not None and _shp_data.cardType == CardType.POKEMON:
                            _setup_hand_poke += 1
                    if _setup_hand_poke <= 1:
                        score = 2
                        if op_has_froslass:
                            score = 0
                        if op_bench_snipe_threat:
                            score = 1
                    else:
                        score = SCORE_VETO
                elif card.id == Tapu_Bulu:
        
                    if AGENT_STATE.meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                        score = 3
                    elif AGENT_STATE.op_is_crustle_deck:
                        score = 3
                    else:
                        score = SCORE_VETO
                elif card.id == Pinsir:
        
                    if AGENT_STATE.op_is_crustle_deck or op_is_sylveon_deck or AGENT_STATE.op_is_cornerstone_deck:
                        score = 3
                    elif op_has_ex_immune_active or op_has_ex_immune_bench:
                        score = 2
                    else:
                        score = SCORE_VETO
        
            elif context == SelectContext.TO_HAND:
                score = 200 - hand_counts[card.id] * 100
        
                is_bcs_selection = (select.effect is not None and select.effect.id == Bug_Catching_Set)
        
                if is_bcs_selection:
                    # Block migrated to the RULES ENGINE (phase 4):
                    # definitions and strategic comments in
                    # _TABLA_BCS_FETCH / _REGLAS_BCS_* (before agent()).
                    # The bonus for prized copies is kept inline.
                    score = 100
                    _bcs_ctx = _ctx_ns_fetch(
                        my_state, state, hand_counts, field_counts,
                        bench_count, total_grass, has_hydrapple,
                        _active_needs_energy, op_has_ex_immune_active,
                        op_has_ex_immune_bench, op_is_lucario_deck,
                        meowth_ability_lock, _best_supp_in_hand_val,
                        _best_supp_in_deck_val,
                        dragapult_no_tapu=_dragapult_no_tapu,
                        op_state=op_state,
                        neutralization_zone_active=neutralization_zone_active)
                    _bcs_entry = _BCS_FETCH_TABLE.get(card.id)
                    if _bcs_entry is not None:
                        _bcs_et, _bcs_rules, _bcs_defecto = _bcs_entry
                        score = _resolve_with_trace(
                            _bcs_et, _bcs_rules, [], _bcs_ctx,
                            default=_bcs_defecto)
        
                    if card.id in AGENT_STATE.ACTIVE_CARDS_IN_DECK:
                        prized_copies = AGENT_STATE.ACTIVE_CARDS_IN_DECK[card.id][ZONE_PRIZE]
                        total_copies = sum(AGENT_STATE.ACTIVE_CARDS_IN_DECK[card.id].values())
                        if prized_copies > 0 and total_copies - prized_copies <= 1:
                            score += 100
        
                elif select.effect is not None and select.effect.id == Poke_Pad:
        
                    # Block migrated to the RULES ENGINE (phase 4):
                    # definitions and strategic comments in
                    # _RULES_PP_FETCH (before agent()).
                    score = _resolve_with_trace(
                        "pp->fetch", _RULES_PP_FETCH, [],
                        _CtxPPFetch(card.id, hand_counts, field_counts,
                                    bench_count, state,
                                    _opening_sac_needs_body,
                                    _doomed_sac_needs_body),
                        default=10)
        
                elif select.effect is not None and select.effect.id == Night_Stretcher:
        
                    score = 50
        
                    # Block migrated to the RULES ENGINE (phase 4):
                    # definitions and strategic comments in
                    # _REGLAS_NS_* (before agent()). The cross-cutting
                    # post-adjustments below are kept inline.
                    _ns_ctx = _ctx_ns_fetch(
                        my_state, state, hand_counts, field_counts,
                        bench_count, total_grass, has_hydrapple,
                        _active_needs_energy, op_has_ex_immune_active,
                        op_has_ex_immune_bench, op_is_lucario_deck,
                        meowth_ability_lock, _best_supp_in_hand_val,
                        _best_supp_in_deck_val,
                        grass_enables_syrup_ko=(
                            (_grass_anywhere_enables_syrup_ko
                             or _grass_enables_promote_ko)
                            and _grass_attach_route_open(
                                state, field_counts,
                                abilities_off=meowth_ability_lock)),
                        ld_free=_meowth_ld_free,
                        dragapult_no_tapu=_dragapult_no_tapu,
                        op_state=op_state,
                        neutralization_zone_active=neutralization_zone_active,
                        gust_over_immune_active=bool(
                            _boss_gust_immune_active))
        
                    _ns_tables = {
                        Basic_Grass_Energy: ("ns->grass",
                                             _RULES_NS_GRASS, 300),
                        Fezandipiti_ex: ("ns->fez", _RULES_NS_FEZ, 10),
                        Chikorita: ("ns->chikorita",
                                    _RULES_NS_CHIKORITA, 40),
                        Applin: ("ns->applin", _RULES_NS_APPLIN, 80),
                        Teal_Mask_Ogerpon_ex: ("ns->ogerpon",
                                               _RULES_NS_OGERPON, 20),
                        Tapu_Bulu: ("ns->tapu", _RULES_NS_TAPU, 50),
                        Pinsir: ("ns->pinsir", _RULES_NS_PINSIR, 15),
                        Meowth_ex: ("ns->meowth",
                                    _RULES_NS_MEOWTH, 15),
                        Hydrapple_ex: ("ns->hydrapple",
                                       _RULES_NS_HYDRAPPLE, 30),
                        Meganium: ("ns->meganium",
                                   _RULES_NS_MEGANIUM, 30),
                        Dipplin: ("ns->dipplin", _RULES_NS_DIPPLIN, 30),
                        Bayleef: ("ns->bayleef", _RULES_NS_BAYLEEF, 30),
                    }
                    _ns_entry = _ns_tables.get(card.id)
                    if _ns_entry is not None:
                        _ns_et, _ns_rules, _ns_defecto = _ns_entry
                        score = _resolve_with_trace(
                            _ns_et, _ns_rules, [], _ns_ctx,
                            default=_ns_defecto)
        
                    if card.id in AGENT_STATE.ACTIVE_CARDS_IN_DECK and card.id != Basic_Grass_Energy:
                        entry = AGENT_STATE.ACTIVE_CARDS_IN_DECK[card.id]
                        if entry[ZONE_DECK] == 0 and entry[ZONE_PRIZE] >= 1:
                            score += 200
                        elif entry[ZONE_DECK] == 0 and entry[ZONE_PRIZE] == 0:
                            score += 150
        
                    if AGENT_STATE.op_is_crustle_deck or AGENT_STATE.op_is_cornerstone_deck:
                        # ENERGY is matchup-agnostic and is NEVER vetoed
                        # (registro_008 step 75 vs Mega Starmie with a
                        # TECH Cornerstone on the bench): the whitelist
                        # crushed the Grass (1300, which enabled the Syrup
                        # Storm of the active Hydrapple THIS turn via the
                        # pending manual attachment) and recovered a Tapu
                        # Bulu that was dead in hand (50). The Grass also charges
                        # the Tapu itself, the attacker of these matchups.
                        if AGENT_STATE.op_is_cornerstone_deck and not AGENT_STATE.op_is_crustle_deck:
                            # THE LIST WAS DRAWN FROM THE WRONG PROPERTY (user,
                            # ago 2026). The Cornerstone whitelist kept only the
                            # two bodies that hit the wall THEMSELVES and dropped
                            # Chikorita, Bayleef and Meganium -- and on both
                            # halves of that reading it is the Crustle list, not
                            # this one, that is right here.
                            #
                            # Chikorita and Bayleef carry NO Ability, so unlike
                            # every ex in this deck they are not blanked by
                            # Cornerstone Stance: through the {G} weakness a
                            # Bayleef's Push Down is 100 to the wall's face. And
                            # Meganium, which really does do zero to it, is the
                            # card the matchup is BUILT around: Wild Growth is
                            # what drops Wood Hammer from four physical Grass to
                            # two. Recovering the piece that halves the price of
                            # the win condition is not off-plan, it IS the plan --
                            # the same argument `mega_line_enables_tapu_vs_cornerstone`
                            # already makes on the Ultra Ball side of the deck.
                            # Applin and Dipplin stay out: both lead only to
                            # bodies the wall switches off.
                            _cc_sel_valid = (Tapu_Bulu, Pinsir, Chikorita,
                                             Bayleef, Meganium,
                                             Basic_Grass_Energy)
                        else:
                            _cc_sel_valid = (Tapu_Bulu, Pinsir, Applin, Chikorita,
                                             Dipplin, Bayleef, Meganium,
                                             Basic_Grass_Energy)
                        # The DRAW ENGINE is not vetoed by matchup either: with
                        # a dead turn and a dry hand, the anti-ex whitelist
                        # left as the only option a development body
                        # that is not played, and the next turn
                        # repeats with no cards. Same exception as the
                        # ENERGY above (see `_ns_motor_*_vivo`).
                        _cc_engine = (
                            _ns_ctx.dead_turn and _ns_ctx.hand_exhausted
                            and ((card.id == Meowth_ex
                                  and _ns_meowth_engine_alive(_ns_ctx))
                                 or (card.id == Fezandipiti_ex
                                     and _ns_fez_engine_alive(_ns_ctx))))
                        if card.id not in _cc_sel_valid and not _cc_engine:
                            score = SCORE_VETO
        
                elif select.effect is not None and select.effect.id == Ultra_Ball:
        
                    score = 100
        
                    hand_play_options, supporters_in_hand = _count_hand_play_options(
                        hand_counts, field_counts, bench_count, state.energyAttached)
                    hand_is_weak = (hand_play_options <= 1 and len(my_state.hand) <= 4)
                    has_energy_for_teal = hand_counts.get(Basic_Grass_Energy, 0) >= 1
        
                    # It does NOT use `_evolvable_counts`: MEASURED AND REVERTED.
                    _ub_evolvable = AGENT_STATE._field_at_turn_start if (not AGENT_STATE.forest_in_play and AGENT_STATE._field_at_turn_start) else field_counts
        
                    _t1_going_second_meowth = (
                        state.turn == 2 and not AGENT_STATE.we_go_first and
                        not state.supporterPlayed and
                        hand_counts.get(Lillie_Determination, 0) == 0 and
                        field_counts.get(Meowth_ex, 0) < 2 and
                        bench_count < 5 and
                        AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0 and
                        AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0)
        
                    _t1_going_second_need_ogerpon = (
                        state.turn == 2 and not AGENT_STATE.we_go_first and
                        bench_count == 0 and
                        any(field_counts.get(pid, 0) >= 1 for pid in (Applin, Chikorita)) and
                        not any(hand_counts.get(pid, 0) >= 1
                                for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                            Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir)))
        
                    _t1_going_first_need_basic = (
                        state.turn == 1 and AGENT_STATE.we_go_first and
                        bench_count == 0 and
                        not any(hand_counts.get(pid, 0) >= 1
                                for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                            Tapu_Bulu, Fezandipiti_ex, Pinsir)))
        
                    # Rule (user, log 85850698 step 5, WON vs Lucario):
                    # when we have only ONE Pokemon in play (empty bench) and
                    # NO playable Pokemon in hand, the Ultra Ball search
                    # must ALWAYS bring Meowth ex (a Basic that, when put
                    # down, also searches for a Supporter = Lillie's Determination to
                    # refill the hand next turn) instead of Ogerpon ex.
                    # EXCEPTION: if we ALREADY have a Lillie's Determination in
                    # hand, the Meowth ex fetch is not needed -> Ogerpon ex
                    # (an attacker) is preferred. It requires Meowth ex and Lillie's in the
                    # deck, no Watchtower (which cancels its ability) and < 2 Meowth
                    # ex already in play.
                    _ub_only_active_in_play = (bench_count == 0)
                    _ub_no_playable_basic_hand = not any(
                        hand_counts.get(pid, 0) >= 1
                        for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                    Tapu_Bulu, Fezandipiti_ex, Pinsir, Meowth_ex))
                    # THE REFILL ENGINE IS NOT AVAILABLE UNDER A PENDING STAMP
                    # (user, registro_008 step 70). The four `*_prefer_meowth`
                    # premises below all say the same thing -- "the Meowth ex ->
                    # Last-Ditch -> Lillie's engine refills better than the body
                    # this fetch would otherwise bring" -- and each of them
                    # SUPPRESSES a rival target (Ogerpon, Hydrapple, Meganium,
                    # Fezandipiti). With an Unfair Stamp that is going to be
                    # played this turn the engine cannot run at all: the whole
                    # hand goes back into the deck before any fetched Supporter
                    # can be played. Leaving the premises on made the Ultra Ball
                    # veto the target it had been BOUGHT for (the Fezandipiti
                    # refill) in favour of a Meowth ex that was shuffled away.
                    # One concept, one gate, and it reads the same against any
                    # opposing deck.
                    _ub_stamp_pending = _stamp_pendiente(ctx)

                    _ub_prefer_meowth_develop = (
                        not _ub_stamp_pending
                        and _ub_only_active_in_play
                        and _ub_no_playable_basic_hand
                        and hand_counts.get(Lillie_Determination, 0) == 0
                        and not meowth_ability_lock
                        and field_counts.get(Meowth_ex, 0) < 2
                        and bench_count < 5
                        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0
                        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0)
        
                    # -----------------------------------------------------
                    # Dipplin vs Meowth ex priority in the search (user):
                    # Searching for Dipplin is only FAVOURED in 3 cases:
                    #  1) A Lillie's Determination has already been played (it is in
                    #     the discard).
                    #  2) An anti-ex opponent (Crustle / Sylveon / Cornerstone ex) and
                    #     we can ATTACK this turn with Dipplin (the Applin to be
                    #     evolved already has energy for the cost-1 attack).
                    #  3) We have the stadium (Forest) + Hydrapple ex in hand and
                    #     we can evolve into Hydrapple ex and ALSO attack
                    #     (Syrup Storm requires 2 effective energy).
                    # If none of them holds, Meowth ex has priority to
                    # refill the hand, NO MATTER what is in hand.
                    # -----------------------------------------------------
                    # Fix (user, log 86585073 turn 4, vs Marnie, WON): the fact
                    # that a Lillie's Determination has already been played is NOT enough to
                    # favour Dipplin/Hydrapple over Meowth ex in the
                    # search if there are STILL Lillie's left in the DECK. Meowth ex (when
                    # put down, its Last-Ditch Catch ability searches for a Supporter)
                    # is still the best search for refilling the hand when
                    # the Hydrapple line adds no attack (Hydrapple ex is a 2-prize
                    # ex that cannot attack here). Dipplin is only favoured
                    # by "Lillie already played" when the Lillie's engine
                    # is EXHAUSTED (no copy left in the deck); if there are still
                    # copies, Meowth ex keeps priority (rule
                    # lillie_in_deck_refresh of _RULES_UB_MEOWTH).
                    _dp_lillie_played = (
                        discard_counts.get(Lillie_Determination, 0) >= 1
                        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                            Lillie_Determination, {}).get(ZONE_DECK, 0) == 0)
        
                    _dp_applin_energy = 0
                    for _dp_bp in (my_state.bench or []):
                        if _dp_bp is not None and _dp_bp.id == Applin:
                            _dp_applin_energy = max(_dp_applin_energy,
                                                    len(_dp_bp.energies))
        
                    _dp_anti_ex = (
                        (AGENT_STATE.op_is_crustle_deck or op_is_sylveon_deck or
                         AGENT_STATE.op_is_cornerstone_deck)
                        and _dp_applin_energy >= AGENT_STATE.ATTACK_ENERGY_REQ.get(Dipplin, 1))
        
                    _dp_can_grass_now = (not state.energyAttached and
                                         hand_counts.get(Basic_Grass_Energy, 0) >= 1)
                    _dp_hydra_req = AGENT_STATE.ATTACK_ENERGY_REQ.get(Hydrapple_ex, 2)
                    _dp_hydra_line = (
                        AGENT_STATE.forest_in_play and
                        hand_counts.get(Hydrapple_ex, 0) >= 1 and
                        _dp_applin_energy >= 1 and
                        (_dp_applin_energy >= _dp_hydra_req or
                         (_dp_can_grass_now and
                          _dp_applin_energy + _grass_attach_unit() >= _dp_hydra_req)))
        
                    # PHASE E4 of the Marnie plan ("search priority vs
                    # Marnie: Hydrapple line > Meowth ex"): TESTED AND NOT
                    # IMPLEMENTED, and the reason is useful for the next
                    # cycle. Adding a "Hydrapple anchor" disjunct here DOES
                    # have an effect -- it raises the Dipplin fetch from 150 to 800 --
                    # but it NEVER decides: it changed 0 decisions in the 929
                    # steps of the records and 0 as well in the synthetic
                    # scenario built on purpose for it. The reason is
                    # that `yields_to_priority_dipplin` (10) lives at the END of
                    # `_RULES_UB_MEOWTH`, behind the
                    # `dead_hydra_prefers_meowth` /
                    # `dead_meganium_prefers_meowth` /
                    # `no_attacker_prefers_meowth` family (1000-1250), which is
                    # exactly the one that fires on the boards of this matchup.
                    #
                    # That is: the real hook of E4 is not `_dipplin_priority`
                    # but that family, and turning it around is a TRADE,
                    # not a fix -- those rules say "if the evolution does not
                    # help today and there is no attacker, refill", each with its
                    # own record behind it, and E4 says the opposite leaning on
                    # ONE game (number 3). With the winrate saturated (~96% vs the
                    # bot piloting Marnie) the harness cannot arbitrate that
                    # trade, so nothing is changed blind.
                    _dipplin_priority = (_dp_lillie_played or _dp_anti_ex or
                                         _dp_hydra_line)
        
                    # Hydrapple ex brought to evolve a Dipplin ALREADY in play
                    # this turn (the score-980 branch), but which would be DEAD: without
                    # enough energy for Syrup Storm (2 effective). Searching for a
                    # Hydrapple ex that does not attack only makes sense if there is NO
                    # better play. When the Meowth ex ->
                    # Last-Ditch Catch -> Lillie's Determination refill engine is available,
                    # bringing Meowth ex (it rebuilds the hand and opens up energy /
                    # attacker options) beats an inert Hydrapple ex that a
                    # later Lillie's could also shuffle back into the deck
                    # (registro 004, step ~62 vs Iono, LOST). It only applies if
                    # Hydrapple ex canNOT attack this turn.
                    _ub_hydra_evolvable_now = (
                        not has_hydrapple and _ub_evolvable.get(Dipplin, 0) >= 1)
                    _ub_hydra_can_attack_now = False
                    if _ub_hydra_evolvable_now:
                        _ub_best_dip_e = -1
                        for _hp in (([my_state.active[0]] if my_state.active else [])
                                    + list(my_state.bench or [])):
                            if _hp is not None and _hp.id == Dipplin:
                                if len(_hp.energies) > _ub_best_dip_e:
                                    _ub_best_dip_e = len(_hp.energies)
                        if _ub_best_dip_e >= 0:
                            # THE BODY WE ARE FETCHING BRINGS ITS OWN
                            # ATTACHMENT WITH IT (user, episode 92595425, turn 4
                            # vs a Dragapult ex deck, LOST). This used to count
                            # the Dipplin's energy plus the turn's manual
                            # attachment and stop, which is one short of the
                            # truth and always in the same direction: Syrup
                            # Storm costs TWO and the Hydrapple ex prints
                            # Ripening Charge, so the copy coming out of the
                            # deck arrives carrying one of the two. It has not
                            # spent that ability -- it is not on the board yet
                            # -- and the record shows the engine offering it the
                            # same turn the body evolves (step 69 evolves, step
                            # 70 is the charge's own target select).
                            #
                            # It is the mirror of `OP_EVO_ENERGY_ON_PLAY`
                            # (ptcg/cards/ids.py), which exists because the same
                            # arithmetic under-read an Archaludon ex's Assemble
                            # Alloy by a whole attack cost. We modelled it for
                            # THEM and not for us.
                            #
                            # AND THE BUDGET IS THE HAND: two routes are two
                            # CARDS, so one Grass buys one attachment however
                            # many routes are open. Without the cap every gapped
                            # line would read as alive.
                            _ub_hdip_routes = 1
                            if not state.energyAttached:
                                _ub_hdip_routes += 1
                            _ub_hdip_attaches = min(
                                hand_counts.get(Basic_Grass_Energy, 0),
                                _ub_hdip_routes)
                            _ub_hdip_after = (
                                _ub_best_dip_e
                                + _ub_hdip_attaches * _grass_attach_unit())
                            if _ub_hdip_after >= AGENT_STATE.ATTACK_ENERGY_REQ.get(Hydrapple_ex, 2):
                                _ub_hydra_can_attack_now = True
                    _ub_hydra_dead_prefer_meowth = (
                        not _ub_stamp_pending
                        and _ub_hydra_evolvable_now
                        and not _ub_hydra_can_attack_now
                        and not meowth_ability_lock
                        and field_counts.get(Meowth_ex, 0) < 2
                        and bench_count < 5
                        and not state.supporterPlayed
                        and hand_counts.get(Lillie_Determination, 0) == 0
                        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0
                        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0)
        
                    # Analogous to _ub_hydra_dead_prefer_meowth, but for the
                    # Meganium line (Chikorita->Bayleef->Meganium). A Meganium brought
                    # with Ultra Ball is USELESS this turn if there is no Bayleef in
                    # play to evolve (nor Forest+Bayleef in hand to
                    # chain it): with only the lower line in play (e.g. a Chikorita)
                    # the Meganium is mere preparation (score 200) and adds no attack.
                    # If we also do NOT have a READY attacker, we prefer bringing
                    # Meowth ex to put it down, let its Last-Ditch Catch search for a
                    # Lillie's and refill the hand/options. It even covers the case
                    # of a 2nd Meowth ex with one already on the bench (the active Chikorita
                    # only chips, it is not a real attacker). (user, registro 004
                    # step 35 vs Mega Lucario, WON)
                    _ub_mega_evolvable_now = (
                        not AGENT_STATE.meganium_in_play and _ub_evolvable.get(Bayleef, 0) >= 1)
                    _ub_mega_chain_now = (
                        not AGENT_STATE.meganium_in_play
                        and _ub_evolvable.get(Chikorita, 0) >= 1
                        and (AGENT_STATE.forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1)
                        and hand_counts.get(Bayleef, 0) >= 1)
                    _ub_mega_dead_prefer_meowth = (
                        not _ub_stamp_pending
                        and not AGENT_STATE.meganium_in_play
                        and not _ub_mega_evolvable_now
                        and not _ub_mega_chain_now
                        and not _active_ready_attacker
                        and not meowth_ability_lock
                        and field_counts.get(Meowth_ex, 0) < 2
                        and bench_count < 5
                        and not state.supporterPlayed
                        and hand_counts.get(Lillie_Determination, 0) == 0
                        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0
                        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0)
        
                    # Rule (user, registro_004 step 29, vs Mega Starmie):
                    # it generalises _ub_mega_dead_prefer_meowth. Even if an
                    # evolution IS playable this turn (e.g. there is a Bayleef
                    # in play to bring up Meganium), if we have NO USABLE
                    # attacker this turn the Ultra Ball must bring
                    # Meowth ex (put it down -> Last-Ditch Catch searches for Lillie's ->
                    # refill the hand and open options) instead of an
                    # evolution that will add no attack now. An attacker is
                    # "usable" if: (a) the ACTIVE can already attack, or (b) there is a
                    # READY attacker on the bench AND the active can pay its retreat
                    # cost to BRING IT UP to the active spot. In this record the
                    # active (Tapu Bulu, 0 energy, cost 3) cannot
                    # retreat, so the charged benched Ogerpon ex is
                    # stuck -> there is no usable attacker.
                    _uba_act = my_state.active[0] if my_state.active else None
                    _ub_active_can_retreat = (
                        _uba_act is not None
                        and len(_uba_act.energies) >= RETREAT_COST.get(_uba_act.id, 1))
                    _ub_bench_ready_attacker = any(
                        _bp is not None and _bp.id in MAIN_ATTACKERS
                        and _can_attack_eff(_bp.id, len(_bp.energies))
                        for _bp in (my_state.bench or []))
                    # ON A DO-OR-DIE TURN AN ATTACK THAT DOES NOT CLOSE THE GAME
                    # IS NOT A USABLE ATTACKER (user, registro_010 step 140 vs
                    # Archaludon ex, LOST). The board is written out in
                    # `_TIER_SEARCH_KEEPS_THE_SEAT`: their reply takes their last
                    # prize, so the turn either manufactures the knockout or the
                    # game is over, and this fetch is the only place the missing
                    # Grass can come from. With the seat kept free the ladder
                    # still bought the wrong body -- `ub->fez` 1050
                    # (`refill_after_a_ko`, three cards off Flip the Script) over
                    # `ub->meowth` 1000 -- because the flag below asks whether an
                    # attack is LEGAL and our Ogerpon could indeed attack. For
                    # 240 into a 300 HP body, on the last turn we get.
                    #
                    # `do_or_die` is exactly the condition under which "we have
                    # an attacker, we do not need the search" stops being true:
                    # the mode is only DENY when NO route closes the game (a
                    # lethal attack would have made it WIN_NOW) and their reply
                    # does. What the turn has then is not an attacker, it is a
                    # body that throws a number. It is the same correction
                    # `_ready_attack_is_inert` (main.py) makes for the PLAY
                    # branch -- "a ready attack that takes no prize is not what
                    # the turn is for" -- extended to the one case that flag
                    # deliberately leaves out: `prizes_today >= 1`. On this board
                    # it was 1 (a Boss's Orders on a benched Relicanth), and a
                    # prize taken on a turn we do not survive is not a prize.
                    #
                    # The consequence is one flag and no new rule: with it true
                    # `no_attacker_prefers_meowth` (1250) wins `ub->meowth`, and
                    # `refill_after_a_ko` already yields to that same flag
                    # (`not c.no_attacker_prefer_meowth`), so the Fez arm falls
                    # back to its default. The deepest look at the deck wins the
                    # search: Last-Ditch Catch fetches the Supporter it wants and
                    # Lillie's Determination draws six, against three drawn blind.
                    _ub_do_or_die = bool(getattr(
                        AGENT_STATE.turn_plan, 'do_or_die', False))
                    _ub_usable_attacker = (
                        (_active_ready_attacker
                         or (_ub_active_can_retreat and _ub_bench_ready_attacker))
                        and not _ub_do_or_die)
                    _ub_no_attacker_prefer_meowth = (
                        not _ub_stamp_pending
                        and not _ub_usable_attacker
                        and not meowth_ability_lock
                        and field_counts.get(Meowth_ex, 0) < 2
                        and bench_count < 5
                        and not state.supporterPlayed
                        and hand_counts.get(Lillie_Determination, 0) == 0
                        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meowth_ex, {}).get(ZONE_DECK, 0) > 0
                        and AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Lillie_Determination, {}).get(ZONE_DECK, 0) > 0)
        
                    # Chain migrated to the RULES ENGINE (phase 4): the
                    # definitions and strategic comments live in
                    # _REGLAS_UB_* (before agent()). PTCG_DEBUG
                    # prints the trace of each resolution.
                    _ub_fetch_ctx = _CtxUBFetch(
                        hand=hand_counts, field=field_counts,
                        evolvable=_ub_evolvable, bench_count=bench_count,
                        prefer_meowth_develop=_ub_prefer_meowth_develop,
                        t1_going_second_need_ogerpon=_t1_going_second_need_ogerpon,
                        t1_going_first_need_basic=_t1_going_first_need_basic,
                        has_energy_for_teal=has_energy_for_teal,
                        dipplin_priority=_dipplin_priority,
                        has_hydrapple=has_hydrapple,
                        op_ex_immune_active=op_has_ex_immune_active,
                        op_ex_immune_bench=op_has_ex_immune_bench,
                        no_attacker_prefer_meowth=_ub_no_attacker_prefer_meowth,
                        supp_in_hand_takes_the_turn=bool(
                            tc._ub_supp_in_hand_turn))
        
                    if card.id == Meowth_ex:
                        _ub_meo_ctx = _ctx_ub_fetch_meowth(
                            hand_counts, field_counts, bench_count,
                            state.turn, meowth_ability_lock,
                            _supp_values, _ub_prefer_meowth_develop,
                            _ub_hydra_dead_prefer_meowth,
                            _ub_mega_dead_prefer_meowth,
                            _ub_no_attacker_prefer_meowth,
                            _t1_going_second_meowth, _dipplin_priority,
                            _active_cant_attack_this_turn,
                            _mega_line_active, op_is_dragapult_dusknoir,
                            supporter_played=state.supporterPlayed,
                            ld_free=_meowth_ld_free,
                            meowth_tomorrow=_ub_meowth_for_tomorrow(ctx),
                            supp_in_hand_takes_the_turn=bool(
                                tc._ub_supp_in_hand_turn),
                            stamp_pending=_ub_stamp_pending,
                            gust_over_immune_active=bool(
                                _boss_gust_immune_active))
                        score = _resolve_with_trace(
                            "ub->meowth", _RULES_UB_MEOWTH, [],
                            _ub_meo_ctx, default=10)
        
                    elif card.id == Teal_Mask_Ogerpon_ex:
                        score = _resolve_with_trace(
                            "ub->ogerpon", _RULES_UB_OGERPON, [],
                            _ub_fetch_ctx, default=100)
        
                    elif state.turn == 2 and not AGENT_STATE.we_go_first:
                        score = 10
        
                    elif card.id == Meganium:
                        score = _resolve_with_trace(
                            "ub->meganium", _RULES_UB_MEGANIUM, [],
                            _ub_fetch_ctx, default=100)
        
                    elif card.id == Hydrapple_ex:
                        # Branch migrated to the RULES ENGINE (phase 4
                        # pilot): definitions and strategic comments in
                        # _RULES_UB_HYDRAPPLE / _AJUSTES_UB_HYDRAPPLE
                        # (before agent()). PTCG_DEBUG prints the trace.
                        # The PLAY menu prices the second copy (see
                        # `TOP_IN_PLAY_DOES_NOT_CLOSE_THE_LINE`), so this menu
                        # has to be willing to spend the Item on it.
                        if not has_hydrapple or not _line_closed_by_its_top():
                            _ub_hyd_ctx = _ctx_ub_fetch_hydrapple(
                                my_state, state, hand_counts,
                                field_counts, _ub_evolvable,
                                op_has_ex_immune_active,
                                op_has_ex_immune_bench,
                                _ub_hydra_dead_prefer_meowth)
                            score = _resolve_with_trace(
                                "ub->hydrapple",
                                _RULES_UB_HYDRAPPLE,
                                _AJUSTES_UB_HYDRAPPLE,
                                _ub_hyd_ctx, default=100)
                        else:
                            score = 20
        
                    elif card.id == Bayleef:
                        score = _resolve_with_trace(
                            "ub->bayleef", _RULES_UB_BAYLEEF, [],
                            _ub_fetch_ctx, default=150)
        
                    elif card.id == Dipplin:
                        score = _resolve_with_trace(
                            "ub->dipplin", _RULES_UB_DIPPLIN, [],
                            _ub_fetch_ctx, default=150)
        
                    elif card.id == Chikorita:
                        score = _resolve_with_trace(
                            "ub->chikorita", _RULES_UB_CHIKORITA, [],
                            _ub_fetch_ctx, default=200)
        
                    elif card.id == Applin:
                        score = _resolve_with_trace(
                            "ub->applin", _RULES_UB_APPLIN, [],
                            _ub_fetch_ctx, default=180)
        
                    elif card.id == Tapu_Bulu:
                        score = _resolve_with_trace(
                            "ub->tapu", _RULES_UB_TAPU, [],
                            _ub_fetch_ctx, default=50)
        
                    elif card.id == Pinsir:
                        score = _resolve_with_trace(
                            "ub->pinsir", _RULES_UB_PINSIR, [],
                            _ub_fetch_ctx, default=15)
        
                    elif card.id == Fezandipiti_ex:
                        score = _resolve_with_trace(
                            "ub->fez", _RULES_UB_FEZ, [],
                            _ub_fetch_ctx, default=10)
        
                    if card.id in AGENT_STATE.ACTIVE_CARDS_IN_DECK:
                        entry = AGENT_STATE.ACTIVE_CARDS_IN_DECK[card.id]
                        prized = entry[ZONE_PRIZE]
                        total_copies = sum(entry.values())
                        accessible = total_copies - prized
        
                        if prized > 0 and accessible <= 1:
                            score += 150
        
                        if hand_counts.get(card.id, 0) >= 1:
                            score -= 150
        
                    # ORDER OF THE EVOLUTION LINE (user, registro_006
                    # step 79 vs Marnie, LOST). With an Applin on the bench and
                    # NO Dipplin (neither in play nor in hand), the Ultra Ball
                    # brought Hydrapple ex -- which cannot evolve anything and
                    # stays dead in hand -- because its
                    # `applin_evolvable` branch (180) plus the prized-copy
                    # bonus (+150 = 330) beat the Dipplin (150), which
                    # is the link that is REALLY missing. The Meganium
                    # line already got this right (Bayleef 850 > Meganium
                    # 200); this brings the Hydrapple one in line.
                    # It goes AFTER the scarcity bonus so it has the LAST
                    # word: that +150 is what resurrected the dead
                    # card. If the link is not in the deck it does not appear
                    # among the options, and with a full bench the Ultra Ball
                    # itself is CANCELLED before being played
                    # (`_evolve_possible_in_play`).
                    if card.id in _evo_huerfanos:
                        score = min(score, 30)
                    elif card.id in _evo_necesarios and score >= 50:
                        # `score >= 50` respects the "dead card" clamps
                        # (20/25/40) in case a future branch applies them
                        # to an intermediate link.
                        score = max(score, 900)

                    # THE ULTRA BALL DOES NOT BUY WHAT THE HAND ALREADY HOLDS
                    # (user, registro_010 step 112 vs Mega Lucario ex). The
                    # same rule that gates the Ultra Ball's VALUE
                    # (`_ub_target_covered_by_hand`) has to gate its FETCH, or
                    # the two menus disagree: the play branch buys the Item for
                    # target A and the prompt spends it on target B. There the
                    # ladder took a SECOND Meowth ex with one already in hand
                    # -- `lillie_in_deck_refresh` (1000) only asks whether a
                    # Supporter is alive in the deck -- discarding the Meganium
                    # and the Chikorita of our own line to buy a card the hand
                    # already had. It goes AFTER the scarcity bonus and the
                    # link clamps so it has the LAST word, and it lands on 10,
                    # the floor the "this fetch produces nothing" rules of
                    # `_RULES_UB_MEOWTH` already use -- below the `> 10` gate
                    # that arms `_ub_meowth_pending` / `_ub_fez_pending` in
                    # `finalizar`, so a body clamped here is not committed to
                    # the bench either. Deck-agnostic: it names no card.
                    _ub_free_seats = max(
                        0, (getattr(my_state, 'benchMax', 5) or 5)
                        - bench_count)
                    if _ub_target_covered_by_hand(
                            card.id, hand_counts, field_counts,
                            _ub_free_seats):
                        score = min(score, 10)

                    # ...AND IT DOES NOT BUY A BODY WITH NOWHERE TO SIT (user,
                    # registro_004 steps 50-57 vs Alakazam, LOST). The same
                    # sentence read from the other side: with the bench FULL a
                    # BASIC cannot enter play this turn at all, so the fetch
                    # brings a card that sleeps in hand while its two discards
                    # are paid today -- and there the Lillie's Determination
                    # that was sitting in that very hand shuffled both fetched
                    # Meowth ex straight back into the deck.
                    #
                    # Every branch of `_RULES_UB_MEOWTH` that asks for a seat
                    # (`full_bench`) sat BELOW the engine rules, and the engine
                    # flag `_ub_engine_pivot_turn` had been armed earlier in the
                    # turn with a seat still free: a promise that outlived its
                    # premise (see [[el-puntero-del-plan-es-una-promesa-y-caduca]]).
                    # Here the question is asked about the CARD, not about the
                    # plan, so no engine can talk over it -- and it is asked of
                    # every target, not only of the Meowth ex.
                    # `_ub_target_has_no_seat` reads the stage off the card
                    # data: deck-agnostic, it names no card.
                    if _ub_target_has_no_seat(card.id, _ub_free_seats):
                        score = min(score, 10)

                    # ...AND IT DOES NOT BUY AN EVOLUTION THAT HAS NOTHING TO
                    # EVOLVE TODAY (user, registro_004 steps 43-46 vs Marnie).
                    # The third door into play, and the same sentence: a body
                    # that came down THIS TURN cannot be evolved, so an
                    # evolution whose only seat is that fresh body is a card
                    # that sleeps in hand while its two discards are paid now.
                    # There the fresh Chikorita made `_evo_link_state` -- which
                    # reads the CURRENT field -- call the Bayleef the missing
                    # LINK and lift it to 900 over the Applin (650) that the
                    # free bench seat could have put down at once; the Unfair
                    # Stamp of that same turn shuffled it back into the deck.
                    #
                    # It is asked of `_ub_evolvable`, the start-of-turn
                    # snapshot, which is also what folds in the Forest of
                    # Vitality (with the stadium on the board it IS the current
                    # field, and the fresh body evolves at once -- the control
                    # in tests/test_the_ultra_ball_fetches_the_link_not_a_new_line.py).
                    # It goes LAST, after the link clamps, so no promotion can
                    # talk over it, and it lands on the same 10 as its two
                    # sisters. Deck-agnostic: it names no card.
                    if _ub_target_cannot_be_worn(
                            card.id,
                            _ub_wearable_bodies(
                                my_state, field_counts, _ub_evolvable,
                                (AGENT_STATE.forest_in_play
                                 or hand_counts.get(Forest_of_Vitality, 0) >= 1))):
                        score = min(score, 10)

                elif select.effect is not None and select.effect.id == Meowth_ex:
        
                    # Block migrated to the RULES ENGINE (phase 4):
                    # definitions and strategic comments in
                    # _RULES_MEOWTH_FETCH (before agent()). Only the
                    # Supporters enter the engine; the rest keep the 50.
                    score = 50
                    if card.id in _MEOWTH_FETCH_SUPPS:
                        _mf_ctx = _CtxMeowthFetch(
                            card.id, _supp_values.get(card.id, 0),
                            hand_counts, _supp_values,
                            len(my_state.hand) if my_state.hand else 0,
                            (field_counts.get(Hydrapple_ex, 0) >= 1 or
                             field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1),
                            getattr(op_state, 'handCount', 0),
                            (_active_cant_attack_this_turn
                             or _sel_active_cant_attack),
                            _win_via_boss_gust, _gust_2prize_via_boss,
                            _deny_evo_via_boss, _meowth_devel_lillie,
                            op_is_alakazam_deck, _our_first_action_turn,
                            _ld_lillie_ofrecida,
                            bool(_boss_gust_immune_active),
                            bool(_meowth_recovery_ko),
                            # The price of the turn's Supporter slot: the best
                            # Supporter ALREADY in hand, on this same scale. See
                            # `the_slot_is_taken_so_bring_what_survives`.
                            max((_supp_values.get(_hsv_id, 0)
                                 for _hsv_id in _MEOWTH_FETCH_SUPPS
                                 if hand_counts.get(_hsv_id, 0) >= 1),
                                default=0),
                            # Is there an attack behind the gust at all? See
                            # `boss_beats_the_untouchable_active`.
                            bool(_gust_finds_an_attacker),
                            # OUR prizes remaining: the fetch reads the SAME
                            # Xerosic floor the play side reads
                            # (`_xr_alakazam_floor`), so it cannot bring a cap
                            # that `alakazam_needs_the_hand_floor` then vetoes.
                            my_prize=my_prize,
                            # The two halves of the refill engine's own
                            # reading: the body in front dies next turn and it
                            # is the only charged one we own. See
                            # `the_gust_without_a_reason_yields_to_the_second_wave`.
                            lone_ready_attacker=(_ready_attacker_count <= 1),
                            active_doomed=bool(_active_doomed_real))
                        score = _resolve_with_trace(
                            "meowth->fetch", _RULES_MEOWTH_FETCH, [],
                            _mf_ctx, default=50)
        
                elif select.effect is not None and select.effect.id == Dawn:
        
                    # Block migrated to the RULES ENGINE (phase 4):
                    # definitions and strategic comments in
                    # _TABLA_DAWN_FETCH / _REGLAS_DAWN_* (before
                    # agent()).
                    _dawn_ctx = _ctx_ns_fetch(
                        my_state, state, hand_counts, field_counts,
                        bench_count, total_grass, has_hydrapple,
                        _active_needs_energy, op_has_ex_immune_active,
                        op_has_ex_immune_bench, op_is_lucario_deck,
                        meowth_ability_lock, _best_supp_in_hand_val,
                        _best_supp_in_deck_val,
                        dragapult_no_tapu=_dragapult_no_tapu,
                        op_state=op_state,
                        neutralization_zone_active=neutralization_zone_active)
                    _dawn_entry = _DAWN_FETCH_TABLE.get(card.id)
                    if _dawn_entry is not None:
                        _dawn_et, _dawn_rules, _dawn_defecto = _dawn_entry
                        score = _resolve_with_trace(
                            _dawn_et, _dawn_rules, [], _dawn_ctx,
                            default=_dawn_defecto)
                    else:
                        score = 50 - hand_counts.get(card.id, 0) * 30
                    # THE SEAT THAT IS NOT FREE UNTIL TOMORROW. The table's
                    # `immediate_evo` rungs read the field, which says the body
                    # is THERE and not that it can be evolved today; a body that
                    # came down this turn cannot wear anything. One ceiling
                    # here, over every candidate, instead of the same condition
                    # repeated in each per-card rung. See
                    # `_dawn_seat_waits_a_turn` (registro_005 step 74).
                    if _dawn_seat_waits_a_turn(card.id, _dawn_ctx):
                        score = min(score, DAWN_SEAT_TOMORROW_CAP)
        
                else:
        
                    if card.id == Chikorita:
                        if field_counts[Chikorita] + field_counts[Bayleef] + field_counts[Meganium] >= 1:
                            score -= 150
                        else:
                            score += 80
                    elif card.id == Bayleef:
                        if field_counts[Chikorita] >= 1 or field_counts[Bayleef] >= 1:
                            score += 60
                        else:
                            score -= 50
                    elif card.id == Meganium:
                        if (field_counts[Bayleef] >= 1 or field_counts[Chikorita] >= 1) and not AGENT_STATE.meganium_in_play:
                            score += 100
                        elif AGENT_STATE.meganium_in_play:
                            score -= 200
                        else:
                            score -= 50
                    elif card.id == Applin:
                        if field_counts[Applin] + field_counts[Dipplin] + field_counts[Hydrapple_ex] >= 2:
                            score -= 100
                        else:
                            score += 60
                    elif card.id == Dipplin:
                        if field_counts[Applin] >= 1:
                            score += 70
                        else:
                            score -= 30
        
                        if op_has_ex_immune_active or op_has_ex_immune_bench:
                            score += 80
                    elif card.id == Hydrapple_ex:
                        if field_counts[Dipplin] >= 1 or field_counts[Applin] >= 1:
                            score += 90
                        elif has_hydrapple:
                            score -= 150
                        else:
                            score -= 30
                    elif card.id == Teal_Mask_Ogerpon_ex:
                        if field_counts[card.id] < 2:
                            score += 50
                        else:
                            score -= 100
                    elif card.id == Meowth_ex:
                        if field_counts[card.id] >= 1:
                            score -= 150
                        else:
                            score += 20
                    elif card.id == Fezandipiti_ex:
                        if field_counts[card.id] >= 1:
                            score -= 200
                        else:
                            score += 15
                    elif card.id == Forest_of_Vitality:
                        if not AGENT_STATE.forest_in_play:
                            score += 70
                        else:
                            score -= 100
                    elif card.id == Basic_Grass_Energy:
                        if not state.energyAttached:
                            score += 40
                        else:
                            score -= 5
                    elif card.id == Tapu_Bulu:
                        if field_counts[card.id] >= 1:
                            score -= 100
                        elif AGENT_STATE.meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                            score += 60
                        else:
                            score -= 10
        
                # LANA'S AID: THE BOARD DECIDES WHAT IS PICKED UP (user,
                # registro_018 step 118 vs Crustle, LOST).
                #
                # Board: ACTIVE Tapu Bulu with 2 effective energies (Wood
                # Hammer asks for 4) and two Meganium in play, so ONE Grass
                # is worth {G}{G} and puts it in attack range instantly; FULL bench
                # (5/5); hand with a single Hydrapple ex; discard with 4
                # Grass, 2 Applin and 1 Dipplin. The agent played Lana's Aid
                # -- the right card -- and picked up 2 Applin + 1 Dipplin:
                # with a full bench and no Applin in play, THREE cards
                # that cannot be played. The turn died without attacking.
                #
                # The cause was structural: Lana's Aid had no branch of its own
                # and fell into the generic scorer above, which only knows how to read
                # evolution-line SHAPES ("am I missing this link?") and looks at
                # neither the energy nor the bench slot. Its numbers
                # (Applin 260 > Dipplin 250 > Grass 240) decided the menu.
                #
                # Here they are replaced by the board reading, in three bands:
                #   1. `unlocks_today`: the Grass that puts a body in attack range
                #      THIS turn. A prize today beats any
                #      development -- the same criterion as `ns->grass`.
                #   2. `demanda`: the ones an attacker IN PLAY is still
                #      asking for; they are still worth it even if they are not attached today,
                #      because they go to HAND and are played next turn.
                #   3. the remaining Grass falls below development.
                # And development loses its value if the card cannot be
                # put into play (`_pokemon_injugable`).
                #
                # The ordinal (`_lana_grass_order`) is what avoids the
                # symmetric failure: with a demand of 1 and 4 Grass in the discard, without
                # it all 4 would tie at the top and take all 3 choices.
                #
                # Above all three bands sits the RECOVERY THAT WINS THE GAME
                # (`ROUTE_RECOVER`): there the Grass is the finisher itself, and
                # the bands cannot see it. `unlocks_today` and `demanda` both
                # measure ATTACK RANGE, so an attacker that already reaches
                # `ATTACK_ENERGY_REQ` asks for nothing -- with a charged bench
                # the Grass that wins the game falls to SURPLUS (120) and loses
                # to a Pokemon for a bench that has no tomorrow.
                #
                # It reads `turn_plan_open` and not `turn_plan`: by the time this
                # menu is offered, Lana's Aid has ALREADY been played, so the
                # plan rebuilt for this observation sees the Supporter slot spent
                # and no longer reports the route. The opening plan is what the
                # turn was for before we started spending it, which is exactly
                # what that field is kept for.
                _lana_win_recovery = (
                    _lana_plan is not None
                    and getattr(AGENT_STATE.turn_plan_open,
                                'lethal_recovery', False))
                if _lana_win_recovery and card.id == Basic_Grass_Energy:
                    score = LANA_SEL_GRASS_WINS
                elif _lana_plan is not None:
                    if card.id == Basic_Grass_Energy:
                        _lana_orden = _lana_grass_order.get(len(scores), 0)
                        if (_lana_plan.unlocks_today
                                and _lana_orden < _lana_plan.cards_to_attack):
                            score = LANA_SEL_GRASS_UNLOCKS
                        elif _lana_orden < _lana_plan.demanda:
                            score = LANA_SEL_GRASS_DEMAND
                        else:
                            score = LANA_SEL_GRASS_SURPLUS
                    elif _pokemon_injugable(card.id, field_counts,
                                            bench_count,
                                            my_state.benchMax):
                        score = LANA_SEL_INJUGABLE
        
                # Cubchoo matchup: Lana's Aid and Night Stretcher ONLY
                # recover Basic Energies from the discard, never Pokemon.
                # Cubchoo's attack leaves our active unable to
                # attack next turn, so we use the turn
                # to recharge energy and do not spend these cards on
                # recovering Pokemon.
                if (op_is_cubchoo_deck and select.effect is not None and
                        select.effect.id in (Night_Stretcher, Lanas_Aid)):
                    if card.id == Basic_Grass_Energy:
                        score = max(score, 900)
                    else:
                        score = SCORE_VETO
        
                # GRAND TREE: BRINGING THE ROOT OF THE CHAIN (user's rule,
                # "if we do not have the basic Pokemon we can search for it in the
                # deck or recover it from the discard pile"). With the stadium
                # on the field (or a copy in hand ready to be played) and
                # NO Basic in play to serve as the root, the turn's search
                # has to bring that Basic: playing it today turns the
                # next turn into a free Stage 2. It holds for ANY
                # searcher (Ultra Ball, Bug Catching Set, Poke Pad) and for
                # recovery from the discard (Night Stretcher, Lana's
                # Aid), because the bonus is applied at the END of the
                # TO_HAND context, common to all of them.
                #
                # It is a TIE-BREAK, not an override: `GT_FETCH_BONUS` (600)
                # is added on top of the already resolved score and NEVER resurrects a
                # vetoed option -- the matchup whitelists and the cost
                # vetoes still rule.
                if (_gt_quiere_basico and score > SCORE_VETO
                        and card.id in _gt_basics_ranking):
                    score += GT_FETCH_BONUS
                    if card.id == max(_gt_basics_ranking,
                                      key=_gt_basics_ranking.get):
                        # The root that leads to the best body, ahead of
                        # the others (same criterion as `_gt_planes`).
                        score += 100
        
            elif context == SelectContext.DISCARD:

                score = 50

                # WHOSE TURN IS THIS DISCARD ON? (user, August 2026, measured on
                # `records/registro_006_pasos_077_hasta_100.json`, episode
                # 91519548, step 99.) This one menu serves two callers with
                # OPPOSITE time horizons:
                #
                #   * the COST of our own Ultra Ball -- our turn, and what the
                #     hand still has to spend TODAY is exactly the right reading;
                #   * a discard FORCED by their card (Xerosic's Machinations cuts
                #     us down to three) -- THEIR turn. The hand that survives is
                #     the hand we start OUR next turn with.
                #
                # The block below prices several cards off `state.supporterPlayed`
                # and `state.energyAttached`, and on a forced discard those two
                # flags describe what the OPPONENT spent, not us. Measured on that
                # step: `supporterPlayed=True`, `energyAttached=True` -- and
                # Xerosic's Machinations IS a Supporter, so `supporterPlayed` is
                # ALWAYS True by the time we are asked. `_protect_last_supporter`
                # is gated on `not state.supporterPlayed`, which means the
                # protection of our last playable Supporter was dead code on
                # every forced discard the agent has ever answered.
                #
                # So the two turn-scoped flags are read through the horizon: on a
                # forced discard the Supporter slot and the turn's attachment are
                # FREE, because the turn they belong to has not started yet. The
                # discriminator names no card -- it asks whose card is making us
                # discard -- so it holds for any opposing hand-cutter, and with no
                # effect at all it falls back to today's reading.
                #
                # THE SECOND CUTTER, AND WHY IT NEEDED NO SECOND RULE (user,
                # `registro_001_pasos_005_hasta_017.json`, episode 92489131, step
                # 16, turn 1 vs Mega Lopunny ex / Mega Froslass ex -- LOST). Their
                # HAND TRIMMER ("each player discards until they have 5 cards;
                # your opponent discards first") cut our hand of eight down to
                # five, and the ask was that we answer it exactly as we answer
                # their Xerosic's. We already do, and by construction: the whole
                # block below prices the CARDS IN OUR HAND and reads `select.effect`
                # once -- here, for the owner -- so both cutters walk the same
                # ladder. Measured on that record and on the Alakazam board of
                # `alakazam_t9_...step124.json`, the two menus come out identical
                # rung for rung, while the same menu as OUR OWN cost does not:
                # `tests/test_their_hand_trimmer_is_the_forced_discard_of_their_xerosic.py`.
                #
                # It is also what stops the R8 story hardening into a rule about
                # Supporters. Xerosic's is one, so `supporterPlayed` was True on
                # every forced discard we had ever seen; Hand Trimmer is an ITEM
                # and their Supporter slot may still be unspent when it fires.
                # Whose card it is survives that. Which card it is would not.
                _forced_discard = (
                    select.effect is not None
                    and getattr(select.effect, 'playerIndex', my_index) != my_index)
                _supporter_spent = state.supporterPlayed and not _forced_discard
                _energy_spent = state.energyAttached and not _forced_discard

                _has_recovery = (hand_counts.get(Night_Stretcher, 0) >= 1 or
                                hand_counts.get(Lanas_Aid, 0) >= 1 or
                                AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Night_Stretcher, {}).get(ZONE_DECK, 0) > 0 or
                                AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Lanas_Aid, {}).get(ZONE_DECK, 0) > 0)
        
                _ns_in_hand = (hand_counts.get(Night_Stretcher, 0) >= 1)
        
                _total_supps_in_hand = (hand_counts.get(Lillie_Determination, 0) +
                                       hand_counts.get(Boss_Orders, 0) +
                                       hand_counts.get(Dawn, 0) +
                                       hand_counts.get(Lanas_Aid, 0) +
                                       hand_counts.get(Xerosic_Machinations, 0))
                _protect_last_supporter = (not _supporter_spent and _total_supps_in_hand <= 1)
        
                _refresh_supps_in_hand = (hand_counts.get(Lillie_Determination, 0) +
                                          hand_counts.get(Dawn, 0))
                # A LONE REFILL SUPPORTER IS PROTECTED **BECAUSE** THE TURN'S
                # SUPPORTER IS SPENT, NOT DESPITE IT (user, registro_002 step 22
                # vs Marnie, episode 90088766, WON in spite of this). The gate
                # used to be `not state.supporterPlayed`, which inverted the
                # valuation exactly where it hurts: this block prices a card by
                # what it does NOW, so a Supporter that can no longer be played
                # dropped from 2 to 14 and became the cheapest thing in the hand
                # -- and the cost of an Ultra Ball ate it. With the slot already
                # spent that Supporter is GUARANTEED playable next turn (nothing
                # can compete for it) and it is the only card that replaces the
                # hand the cost is emptying: that is when it is worth most, not
                # least. `_protect_last_supporter` keeps its own gate: it is
                # about the Supporter we can still play THIS turn.
                _protect_refresh_supporter = (_refresh_supps_in_hand <= 1)
        
                _ogerpon_on_field = (field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1)
                _ogerpon_playable = (hand_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1 and bench_count < 5)
                _teal_dance_possible = ((_ogerpon_on_field or _ogerpon_playable) and
                                        hand_counts[Basic_Grass_Energy] >= 1)
        
                _has_teal_dance_target = (bench_count >= 1 or
                                         hand_counts.get(Applin, 0) >= 1 or
                                         hand_counts.get(Chikorita, 0) >= 1 or
                                         hand_counts.get(Tapu_Bulu, 0) >= 1 or
                                         _ogerpon_playable)
                _teal_dance_possible = _teal_dance_possible and _has_teal_dance_target
        
                if card.id == Basic_Grass_Energy:
                    energy_in_hand = hand_counts[Basic_Grass_Energy]
        
                    if _teal_dance_possible:
        
                        if energy_in_hand >= 4:
                            score = 85
                        elif energy_in_hand >= 3:
                            score = 75
                        elif energy_in_hand == 2:
        
                            score = 18
                        else:
        
                            score = 2
                    else:
        
                        if energy_in_hand >= 4:
                            score = 92
                        elif energy_in_hand >= 3:
                            score = 85
                        elif energy_in_hand >= 2:
                            score = 70
                        else:
                            score = 35
                            if _energy_spent:
                                score = 65
        
                    if _has_recovery:
                        score += 5
        
                    if _ns_in_hand:
                        score += 5
        
                    energy_in_deck = AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Basic_Grass_Energy, {}).get(ZONE_DECK, 0)
                    if energy_in_deck >= 5:
                        score += 5
        
                elif card.id == Forest_of_Vitality:
                    # CRITICAL counter-stadium (user, registro_005 step 62 vs
                    # cornerstone_cubchoo, LOST): the opponent controls a
                    # HOSTILE stadium -- Neutralization Zone (1247) cancels the
                    # damage of our ex to a 1-prize active (we cannot
                    # attack) and Team Rocket's Watchtower (1256) switches Abilities
                    # off. The ONLY way to remove it is to play
                    # OUR stadium (Forest) to replace it. When we are
                    # FORCED to discard (Xerosic's Machinations) and Forest is
                    # our only playable copy, it is a KEY card: it has to be
                    # kept and something else let go (Ultra Ball / Tapu Bulu).
                    # Before, with Meganium+Hydrapple in play, Forest scored
                    # 70 (discardable) WITHOUT looking at the opponent's hostile stadium, and the
                    # agent threw it away -- losing the only way to recover the
                    # attack. Our own stadium in the DISCARD does not count:
                    # it is only played from hand.
                    #
                    # THE COUNTER-STADIUM KEEPS ONE COPY, NOT ZERO (user,
                    # `records/registro_006_pasos_077_hasta_100.json`, episode
                    # 91519548, step 99, turn 6 vs Alakazam -- LOST). The
                    # protection used to be gated on
                    # `hand_counts[Forest_of_Vitality] <= 1`, so it switched OFF
                    # exactly when we held more than one out: with two copies in
                    # hand the branch fell through to the spare-copy score (88)
                    # -- which is the score of BOTH copies -- and their Xerosic's
                    # Machinations took the two of them. Under their
                    # Neutralization Zone, with no rule-box body anywhere on
                    # their board, our ex do 0 damage (`_our_effective_damage`),
                    # and those two Forests were the only cards in the deck that
                    # could lift it.
                    #
                    # The `<= 1` guard was reading "spare copies are cheap" --
                    # true -- and answering "so throw away the only out too" --
                    # not true. The surplus is what is cheap; the FIRST copy is
                    # the out. Same shape as `_lillie_protected_once` and
                    # `_evo_spare_seen`: protect one, let the rest be fodder.
                    _forest_counters_op_stadium = _counter_stadium_urgent(
                        neutralization_zone_active, watchtower_in_play,
                        AGENT_STATE.forest_in_play, _festival_lead_hostil)
                    if (_forest_counters_op_stadium
                            and not _counter_stadium_kept_once):
                        _counter_stadium_kept_once = True
                        score = 2
                    elif AGENT_STATE.forest_in_play:
                        score = 95
                    elif hand_counts[Forest_of_Vitality] > 1:
                        score = 88
                    elif AGENT_STATE.meganium_in_play and has_hydrapple:
                        score = 70
                    elif AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Forest_of_Vitality, {}).get(ZONE_DECK, 0) >= 2:
                        score = 55
                    else:
                        score = 15
        
                elif card.id == Meganium:
                    if AGENT_STATE.meganium_in_play:
                        score = 95
                    elif field_counts.get(Bayleef, 0) >= 1:
                        # It is only "almost untouchable" when the line is really
                        # ready: with a Bayleef in play, Meganium is a single
                        # evolution away. Having only a Chikorita does NOT count (two evolutions
                        # are missing), so in that case it falls to the branches
                        # below and ends up more discardable than an unplayed supporter.
                        score = 3
                    elif AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Meganium, {}).get(ZONE_DECK, 0) >= 1:
                        score = 40
                    else:
                        score = 20
        
                elif card.id == Bayleef:
                    if AGENT_STATE.meganium_in_play:
                        score = 88
                    elif field_counts.get(Chikorita, 0) >= 1:
                        score = 3
                    elif hand_counts.get(Bayleef, 0) > 1:
                        score = 75
                    elif AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(Bayleef, {}).get(ZONE_DECK, 0) >= 1:
                        score = 50
                    else:
                        score = 25
        
                elif card.id == Chikorita:
                    if AGENT_STATE.meganium_in_play:
                        score = 85
                    elif field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) >= 1:
                        score = 75
                    elif hand_counts.get(Chikorita, 0) > 1:
                        score = 72
                    elif _ns_in_hand:
                        score = 62
                    elif _has_recovery:
                        score = 55
                    else:
                        score = 18
        
                elif card.id == Applin:
                    if has_hydrapple:
                        score = 83
                    elif field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) >= 1:
                        score = 72
                    elif hand_counts.get(Applin, 0) > 1:
                        score = 70
                    elif _ns_in_hand:
                        score = 60
                    elif _has_recovery:
                        score = 52
                    else:
                        score = 18
        
                elif card.id == Tapu_Bulu:
                    if field_counts.get(Tapu_Bulu, 0) >= 1:
                        score = 95
                    elif AGENT_STATE.meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                        score = 5
                    elif op_has_ex_immune_active or op_has_ex_immune_bench:
                        score = 20
                    else:
                        score = 90
        
                elif card.id == Pinsir:
        
                    if field_counts.get(Pinsir, 0) >= 1:
                        score = 95
                    elif op_has_ex_immune_active or op_has_ex_immune_bench:
                        score = 15
                    else:
                        score = 90
        
                elif card.id == Hydrapple_ex:
                    if AGENT_STATE.op_is_crustle_deck or op_has_ex_immune_active or op_has_ex_immune_bench:
        
                        score = 96
                    elif has_hydrapple and hand_counts.get(Hydrapple_ex, 0) > 1:
                        score = 55
                    elif has_hydrapple:
                        score = 30
                    elif field_counts.get(Dipplin, 0) >= 1 or field_counts.get(Applin, 0) >= 1:
                        score = 3
                    # The other half of the line in hand AND the Basic that will
                    # wear it: with the Forest on the field the three pieces are
                    # one turn away from a Hydrapple ex, so this copy is not
                    # what the cost should eat. The Basic must be IN HAND -- one
                    # sitting in the DECK is not a seat and this branch used to
                    # count it (`_line_base_benchable`; it has to say exactly the
                    # same as `_ub_real_fodder`, which decides whether the Ultra
                    # Ball is played at all).
                    elif (hand_counts.get(Dipplin, 0) >= 1 and
                          (AGENT_STATE.forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                          _line_base_benchable(Hydrapple_ex, hand_counts,
                                               max(0, my_state.benchMax - bench_count))):
                        score = 3
                    else:
                        score = 12
        
                elif card.id == Teal_Mask_Ogerpon_ex:
                    if field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2:
                        score = 65
                    elif field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                        score = 25
                    else:
                        score = 8
        
                elif card.id == Dipplin:
                    if has_hydrapple and not (op_has_ex_immune_active or op_has_ex_immune_bench):
                        score = 55
                    elif field_counts.get(Applin, 0) >= 1:
                        score = 5
                    elif (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                          (AGENT_STATE.forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                          _line_base_benchable(Dipplin, hand_counts,
                                               max(0, my_state.benchMax - bench_count))):
                        score = 3
                    elif op_has_ex_immune_active or op_has_ex_immune_bench:
                        score = 8
                    else:
                        score = 18
        
                elif card.id == Meowth_ex:
                    # WHAT MAKES THIS COPY DEAD IS THE SEAT, NOT THE SUPPORTER
                    # SLOT (user, August 2026, `registro_032_cynthia_garchomp_3`
                    # turn 7, found by the frozen corpus). The gate used to read
                    # `bench_count >= 5 and state.supporterPlayed`, and the two
                    # halves are not the same claim:
                    #
                    #   * the spent Supporter slot only says the Last-Ditch chain
                    #     cannot cash out THIS turn -- and on a forced discard the
                    #     spent slot is the OPPONENT'S, so the half was simply
                    #     false (see the top of this block);
                    #   * the FULL BENCH says the card cannot enter play at all --
                    #     not this turn, not the next, not until they knock
                    #     something out. Nothing in our own turn opens a seat.
                    #
                    # That second half is the one that makes the copy fodder, and
                    # it is the same question `_ub_target_has_no_seat` asks before
                    # the Ultra Ball will spend two cards fetching a body. In that
                    # record the bench was 5/5 with no Meowth ex on it, we were
                    # ahead 3 prizes to 6, and dropping the `supporterPlayed` half
                    # alone would have kept an unplayable Meowth ex over the Ultra
                    # Ball that still had a turn to do something with.
                    if field_counts.get(Meowth_ex, 0) >= 1:
                        score = 82
                    elif bench_count >= 5:

                        score = 65
                    else:

                        score = 2
        
                elif card.id == Fezandipiti_ex:
                    if field_counts.get(Fezandipiti_ex, 0) >= 1:
                        score = 82
                    elif AGENT_STATE.ko_last_turn and bench_count < 5:
        
                        score = SCORE_NEVER
                    else:
        
                        score = 38
        
                elif card.id == Boss_Orders:
                    if (AGENT_STATE.op_is_crustle_deck or op_has_dwebble_bench) and hand_counts.get(Boss_Orders, 0) <= 1:
        
                        score = 2
                    elif hand_counts.get(Boss_Orders, 0) > 1:
                        score = 85
                    elif _protect_last_supporter:
                        score = 12
                    elif budew_on_op_field or op_has_dwebble_bench:
                        score = 10
                    elif op_prize <= 3:
                        score = 20
                    elif state.turn <= 5 and hand_counts.get(Dawn, 0) >= 1:
        
                        score = 30
                    else:
                        # A single copy of Boss's Orders: even if we have already played
                        # the turn's supporter, it keeps future value (a gust to the
                        # bench to finish/redirect), so it is NOT free to discard.
                        # It is protected, but LESS than Lillie's: if a supporter has to be
                        # let go to pay a cost, Boss's falls before Lillie's.
                        score = 22
        
                elif card.id == Lillie_Determination:
                    if _lillie_protected_once:
                        # A spare copy (we are already keeping one): discardable.
                        score = 72
                    else:
                        _lillie_protected_once = True
                        # THE STRONGEST PROTECTION FIRST (user, August 2026,
                        # `registro_021_crustle_wall_18` turn 5, found by the
                        # frozen corpus). These two gates are not exclusive and
                        # the ladder used to test the WEAKER one first: a card
                        # that is both "the last refill" (2) and "the last
                        # Supporter we can still play" (5) came out at 5 -- less
                        # protected for satisfying one more reason to keep it.
                        #
                        # It stayed invisible while `_protect_last_supporter` was
                        # dead code on forced discards. The moment the horizon
                        # read revived it, a Lillie's Determination that was the
                        # last refill against the Crustle wall started falling to
                        # a second Meowth ex scored at 2.
                        #
                        # ...AND NOT WHEN IT IS THE CARD THAT BURIES THE CAP
                        # (user, registro_009 step 124 vs Alakazam). Lillie's
                        # SHUFFLES OUR HAND INTO THE DECK
                        # (`HAND_TO_DECK_PLAY_IDS`), so while we are keeping the
                        # last Xerosic (`_xr_cap_lost_if_discarded`) the two
                        # cards are in conflict: playing the refill puts the
                        # matchup's only answer back among seventeen cards, in
                        # the matchup where their attack reads 20 per card in
                        # their hand and grows every turn.
                        #
                        # Both had the SAME floor of 2 on that board and only
                        # one could stay, so the tie was broken by menu order
                        # and the Boss's Orders fell -- the gust the value layer
                        # prices at 970, sacrificed to a refill it prices at
                        # 450. That is the static proxy ("the last refill")
                        # outranking a live reading, which is the very defect
                        # `DISCARD_SUPPORTER_LIVE_KEEP` was written to end.
                        #
                        # It does not name a score: the branch below prices the
                        # single copy it is (16 there), above every item and
                        # below anything the turn can still use. With a Xerosic
                        # still in the deck the predicate is false and the
                        # refill keeps its floor.
                        _lillie_buries_the_cap = (
                            card.id in HAND_TO_DECK_PLAY_IDS
                            and ctx is not None
                            and _xr_cap_lost_if_discarded(ctx))
                        if _protect_refresh_supporter and not _lillie_buries_the_cap:

                            score = 2
                        elif _protect_last_supporter:

                            score = 5
                        elif state.turn <= 5 and not _supporter_spent:

                            score = 8
                        elif hand_counts.get(Lillie_Determination, 0) > 1:
                            # There are duplicates and we have already played a supporter: we keep
                            # one copy (a low score) and the others will be the
                            # discardable ones through the branch above.
                            score = 20
                        elif len(my_state.hand) >= 6:
                            # A single copy: even with the supporter already played, Lillie's
                            # keeps future value (draw/new hand). It is protected
                            # BELOW Boss's (Lillie has keeping priority),
                            # so that Boss's falls first.
                            score = 16
                        else:
                            score = 14
        
                elif card.id == Dawn:
                    # Strongest protection first, same as the Lillie's ladder
                    # above: the two gates are not exclusive, and being the last
                    # refill (3) must not be overruled by the weaker "last
                    # Supporter we can still play" (12).
                    if AGENT_STATE.meganium_in_play and has_hydrapple:
                        score = 75
                    elif (ctx is not None
                          and select.effect is not None
                          and select.effect.id == Ultra_Ball
                          and _the_body_search_cannot_buy_the_energy(
                              ctx, ub_in_hand=True)):
                        # THE OTHER HALF OF THE SENTENCE `_ub_real_fodder` SAYS.
                        # That count released this Dawn as fodder because on a
                        # turn with no energy anywhere a search for BODIES
                        # refills nothing; if the ladder that actually pays the
                        # cost went on protecting it at 3, the two sides would
                        # disagree and the Ultra Ball this rule unlocked would
                        # eat the evolution piece beside it instead. Read only
                        # on the Ultra Ball's OWN discard (`select.effect`),
                        # because that is the cost the count was speaking about
                        # -- and the card is no longer in hand by then, which is
                        # why the route's first step is asserted here rather
                        # than looked up. See
                        # `_the_body_search_cannot_buy_the_energy`.
                        score = DISCARD_SUPPORTER_DEAD_DROP
                    elif _protect_refresh_supporter:
                        score = 3
                    elif _protect_last_supporter:
                        score = 12
                    elif state.turn <= 5 and (hand_counts.get(Lillie_Determination, 0) >= 1 or
                                              hand_counts.get(Boss_Orders, 0) >= 1):
        
                        score = 55
                    elif not AGENT_STATE.meganium_in_play or not has_hydrapple:
                        score = 15
                    else:
                        score = 50
        
                elif card.id == Lanas_Aid:
        
                    if hand_counts.get(Lanas_Aid, 0) > 1:
                        score = 80
                    elif _protect_last_supporter:
                        score = 12
                    elif len(my_state.discard) <= 2:
                        score = 75
                    else:
                        score = 35
        
                elif card.id == Xerosic_Machinations:
                    # Xerosic's Machinations (user): vs Alakazam it is the card
                    # that caps Powerful Hand (20 x card in the opponent's hand) --
                    # PROTECT IT the way the Meganium line is protected. In
                    # other decks it is moderately discardable (generic
                    # disruption, a single copy).
                    if op_is_alakazam_deck:
                        score = 5
                        # ...AND THE LAST COPY IS PROTECTED ABOVE EVERY OTHER
                        # SUPPORTER (user, registro_009 step 124 vs Alakazam --
                        # see `DISCARD_XEROSIC_CAP_IS_THE_ANSWER`). This 5 was
                        # written when it was the strongest number in the
                        # Supporter band; the keep floor of 2 arrived later and
                        # left the matchup's own answer ranked BELOW a Boss's
                        # Orders and a refill, so their Xerosic's Machinations
                        # forced ours into the discard pile.
                        #
                        # The gate is `_xr_cap_lost_if_discarded`: no copy left
                        # in the deck. It is the DISCARD half of the predicate
                        # that vetoes the Lillie's which would shuffle this card
                        # away, and it drops that veto's Meowth clauses on
                        # purpose -- Last-Ditch Catch searches the DECK, so it
                        # answers a shuffle and not a discard. From the pile the
                        # deck recovers no Supporter at all.
                        if (ctx is not None
                                and card.id not in _cap_kept_once
                                and _xr_cap_lost_if_discarded(ctx)):
                            _cap_kept_once.add(card.id)
                            score = DISCARD_XEROSIC_CAP_IS_THE_ANSWER
                    else:
                        score = 60
                        # THE FIXED 60 ASKED NOTHING (user, August 2026, found by
                        # `utils/rule_census.py` and measured on the frozen
                        # corpus: 34 of the 40 Xerosic options priced in 50
                        # records take this branch, in 25 different games).
                        #
                        # Outside the Alakazam matchup the cap was fodder of
                        # middling price WHATEVER the opposing hand held -- with
                        # their hand at twelve and with their hand at four. The
                        # PLAY scorer has never agreed with that: at or above
                        # XEROSIC_BIG_HAND it prices the same card
                        # XEROSIC_SCORE_GENERIC (3380) and below it drops to
                        # XEROSIC_SCORE_LAST_RESORT (20). This is the doctrine
                        # the Supporter block already applies to the other four:
                        # the card we KEEP and the card we would PLAY cannot
                        # disagree.
                        #
                        # It is the SECOND question and it only SUBTRACTS: the
                        # 60 above is asked first and is what still answers on a
                        # thin hand, the Alakazam branch is untouched, and the
                        # threshold is the play rule's own constant so the two
                        # scorers cannot drift apart.
                        #
                        # WHICH HAND. The count read is the one on the board.
                        # On a discard FORCED by their card that is their hand
                        # in the middle of THEIR turn -- already spent, their own
                        # Supporter just played -- so it is a LOWER bound on what
                        # they will hold when we could play the cap: the reading
                        # protects less often than it might, never more. On the
                        # cost of our own Ultra Ball it is their hand right now.
                        # Deliberately the same threshold in both: an
                        # observed number, not a projected one.
                        if getattr(op_state, 'handCount', 0) >= XEROSIC_BIG_HAND:
                            score = min(score, DISCARD_XEROSIC_CAPS_A_FAT_HAND)
        
                elif card.id == Night_Stretcher:
                    # A PLAY-CONTEXT SENTENCE THAT WAS PRICING A DISCARD (user,
                    # August 2026, measured; found while reading the forced
                    # discard). This branch used to open with a fourth case: if
                    # the ONLY recoverable target is basic Energy we cannot use
                    # this turn (`state.energyAttached`), then `SCORE_VETO`.
                    #
                    # That sentence belongs to the PLAY scorer, where SCORE_VETO
                    # means "do not play it" (see `_score_night_stretcher_play`,
                    # which asks the same question with thirty scenarios instead
                    # of three). In the DISCARD context the scale runs the other
                    # way: a NEGATIVE score means "keep this above everything",
                    # second only to the Unfair Stamp's SCORE_NEVER. So the branch
                    # handed its strongest protection to the card it had just
                    # judged useless. Measured on the step-99 board with the
                    # Pokemon stripped out of the discard pile, the Stretcher came
                    # out at -1: ranked above the last playable Supporter (5) and
                    # above the critical counter-stadium (2), the one card that
                    # lifts a Neutralization Zone. It has been there since the
                    # first commit and no test ever covered it.
                    #
                    # It is DELETED rather than re-signed, because the reading
                    # itself does not survive either caller of this menu:
                    #
                    #   * on a FORCED discard the spent attachment is the
                    #     OPPONENT'S (see the top of this block). Next turn ours
                    #     is free and the energy is not dead at all;
                    #   * on our own ULTRA BALL cost the pile it measures is the
                    #     pile BEFORE the cost -- and the cost is about to throw
                    #     two cards into it. In `registro_003_alakazam_3` turn 6
                    #     the very same discard sent a Tapu Bulu down, which is
                    #     exactly the Pokemon the branch had just certified the
                    #     Stretcher could not find.
                    #
                    # With it gone the Stretcher is priced by the ladder that is
                    # left, which asks what it always asked: is this a spare copy
                    # (78), is the pile too thin to be worth recovering from (70),
                    # or is it a live recovery card (30).
                    if hand_counts.get(Night_Stretcher, 0) > 1:
                        score = 78
                    elif len(my_state.discard) <= 1:
                        score = 70
                    else:
                        score = 30
        
                elif card.id == Bug_Catching_Set:
                    if hand_counts.get(Bug_Catching_Set, 0) > 1:
                        score = 76
                    elif itchy_pollen_active:
                        score = 85
                    else:
                        score = 45
        
                elif card.id == Ultra_Ball:
        
                    if hand_counts.get(Ultra_Ball, 0) > 1:
                        score = 95
                    else:
                        score = 38
        
                elif card.id == Poke_Pad:
                    if itchy_pollen_active:
                        score = 85
                    else:
                        score = 55
        
                elif card.id == Unfair_Stamp:
        
                    score = SCORE_NEVER
        
                # THE COST DOES NOT EAT THE CARD THAT MAKES ITS OWN PURCHASE
                # WORTH MAKING (user, `records/registro_004_pasos_029_hasta_042
                # .json`, episode 91601506, step 33, turn 4 vs Crustle -- WON in
                # spite of this). Hand of four -- Fezandipiti ex, Lillie's
                # Determination, **Meganium**, Boss's Orders -- two Chikorita on
                # a full bench, our Forest of Vitality on the field, and an
                # Ultra Ball just played TO FETCH THE BAYLEEF. The cost took the
                # Meganium (40) and the Fezandipiti (38) and kept the Boss's
                # Orders (36) that `_supp_values` had already priced as a gust
                # worth nothing on that board.
                #
                # Every branch was right about the board it was shown. The
                # Meganium ladder asks for a **Bayleef in play** and, failing
                # that, falls to "there is another copy in the deck" (40) --
                # the reading of an ORPHAN, and the comment says so out loud:
                # "having only a Chikorita does NOT count, two evolutions are
                # missing". But the second evolution was the card being BOUGHT:
                # `_RULES_UB_BAYLEEF` had scored that very fetch 950 instead of
                # 850 *because we were holding the Meganium in hand*, and the
                # cost then threw away the reason for its own price. The two
                # halves of one Ultra Ball contradicted each other, which is the
                # same doctrine the Supporter block below already applies: the
                # card we keep and the card we would play cannot disagree.
                #
                # The discard is paid BEFORE the fetch resolves, so the scorer
                # is pricing a hand against a board this very card is about to
                # change. `_evo_top_unlocked_by_the_search` puts the incoming
                # link on the board first, and only then asks the question: an
                # orphaned top whose missing link is `necesario` (its own
                # pre-evolution already in play) and still IN THE DECK is one
                # evolution away, not cardboard. It names no card -- the stages
                # come from `EVO_LINES`, so it holds for the Hydrapple ex line
                # exactly as it holds for the Meganium one.
                #
                # It only ever PROTECTS (`min`) and it stays gated on OUR OWN
                # Ultra Ball: on a discard forced by their card nothing is being
                # bought, and the orphan is an orphan again.
                if (not _forced_discard and select.effect is not None
                        and getattr(select.effect, 'id', None) == Ultra_Ball
                        and score > DISCARD_LINK_THE_SEARCH_BUYS
                        and _evo_top_unlocked_by_the_search(
                            card.id, hand_counts, field_counts,
                            {_lk: AGENT_STATE.ACTIVE_CARDS_IN_DECK.get(
                                _lk, {}).get(ZONE_DECK, 0)
                             for _line in EVO_LINES for _lk in _line[1:-1]})):
                    score = DISCARD_LINK_THE_SEARCH_BUYS

                # ...AND IT DOES NOT EAT WHAT AN EARLIER SEARCH OF THE SAME TURN
                # ALREADY BOUGHT (user, `records/registro_004_pasos_031_hasta
                # _045.json`, episode 91650234, turn 4 -- LOST). The turn spent
                # an Ultra Ball and two cards to bench a Meowth ex, activated
                # its Last-Ditch Catch and, of the whole deck, brought back a
                # **Lillie's Determination**. Four menus later the SECOND Ultra
                # Ball paid its cost with that same Lillie's -- with the
                # Supporter slot still free -- and the turn ended having paid
                # twice for a card that never touched the board.
                #
                # Nothing had "changed its mind": the two halves never spoke.
                # The fetch scorer reads the deck against the board and answers
                # "this is what this board needs"; the discard ladders read the
                # hand with static proxies (copies in hand, the last refill, the
                # size of the pile) and none of them can tell a card that was
                # drawn from a card WE WENT AND GOT ten seconds ago. So the
                # cheapest card in hand and the most valuable card in the deck
                # were allowed to be the same card.
                #
                # `_bought_this_turn` is that missing memory, taken off the
                # MOVE_CARD logs (deck/discard -> hand, ours, this turn), so the
                # rule names no card and no deck: whatever the search bought is
                # what the next cost stops pricing as fodder.
                #
                # TWO GUARDS, and the second is the one the corpus asked for:
                #   * OUR OWN cost only. On a discard forced by their card
                #     nothing of ours is being bought (`_forced_discard`).
                #   * THE PURCHASE IS A COUNT, NOT A SERIAL. Copies of one card
                #     are interchangeable, so what has to survive the cost is as
                #     many copies as the search brought, not the physical ones
                #     it brought. The spares -- the copies in hand BEYOND the
                #     purchase -- keep their ordinary price and are what the
                #     cost eats; only the rest are protected. Same reading as
                #     `_evo_copies_usable` ("a line protects the SEATS, not the
                #     copies"). It is what the frozen corpus asked for: its only
                #     event was a Basic Grass the Night Stretcher had recovered
                #     with two more sitting in the same hand, and protecting
                #     THAT copy would only have moved the cost onto its twin.
                #
                # It only ever PROTECTS (`min`) and it goes BEFORE the three
                # blocks below, which ask whether the card can be used at all
                # (no seat for the body, a surplus copy of a line, a Supporter
                # `_supp_values` prices at zero). Those keep the last word: what
                # the board cannot use today is not saved by having been bought.
                #
                # WHAT IS DELIBERATELY *NOT* DONE, for the same reason the block
                # above documents: it is NOT mirrored into `_ub_real_fodder`.
                # This is a RANKING among the cards the cost takes, not a claim
                # that the purchase is untouchable -- the menu still takes
                # `minCount` cards whatever the scores say. Fed to the veto
                # family it would cancel the very search the purchase was made
                # for.
                _bought_copies = (
                    0 if _forced_discard else _purchase_of_this_turn(
                        card.id, my_state.hand,
                        AGENT_STATE._bought_this_turn))
                if _bought_copies:
                    _bought_spares = max(
                        0, hand_counts.get(card.id, 0) - _bought_copies)
                    if _bought_spare_seen.get(card.id, 0) >= _bought_spares:
                        score = min(score,
                                    DISCARD_WHAT_THE_SEARCH_ALREADY_BOUGHT)
                    else:
                        _bought_spare_seen[card.id] = (
                            _bought_spare_seen.get(card.id, 0) + 1)

                # A LINE PROTECTS THE COPIES IT CAN WEAR, NOT EVERY COPY
                # (user, registro_002 step 26 vs Marnie, episode 90181011,
                # LOST). The branches above price an evolution by the body
                # waiting underneath it -- a Hydrapple ex with an Applin on the
                # bench scores 3, "do not throw this away" -- but they give that
                # same 3 to EVERY copy in hand. One Applin only ever wears one
                # Hydrapple ex: with two in hand the second is cardboard that
                # cannot reach the field, and it was still ranked as the most
                # protected card of the hand. So the Ultra Ball's cost had
                # nothing cheap to pay with (`_ub_cancel_no_surplus`) and the
                # turn fell back to a Dawn that, with no Forest of Vitality in
                # play, searches a line we cannot evolve yet -- instead of Ultra
                # Ball -> Meowth ex -> Last-Ditch -> Lillie's Determination.
                #
                # `_evo_copies_usable` counts the SEATS (bodies in play below
                # the card + basics of the line the bench still fits), the first
                # copies keep the branch's protective score and the surplus goes
                # to the spare-copy band -- the very band the Hydrapple branch
                # already uses when one is in play. It names no card: the stages
                # come from `EVO_LINES`.
                # ...AND THE ONE LINK THE SEARCH CAN NEVER BUY BACK IS THE LAST
                # BRIDGE (user, `records/registro_006_pasos_047_hasta_073.json`
                # step 47, episode 93159383 vs Marnie -- LOST). Turn 6, prizes
                # 6-6, hand {Bayleef, Bayleef, Ultra Ball}. Both Bayleef are the
                # deck's only bridge between the Chikorita and the Meganium, and
                # this ladder priced them at 75 -- `hand_counts[Bayleef] > 1`,
                # the surplus band -- which made them the two cheapest cards in
                # the hand and exactly what the cost of two took. They stayed in
                # the discard from step 49 to step 190, the last one of the
                # game; a Meganium reached hand on that same turn and sat there
                # for 127 of the game's 191 steps, with the Chikorita it needed
                # benched under our own Forest of Vitality and never evolved.
                #
                # The branch is the same defect the counter-stadium comment
                # above names in as many words: "spare copies are cheap" is true
                # and "so throw away the only out too" is not. Holding two
                # copies is not surplus when two is ALL THERE IS -- the branch
                # never even reached its own `ZONE_DECK` test, which is
                # unreachable while `hand_counts > 1`.
                #
                # It names no card (`EVO_LINES` supplies the stages, so the
                # Dipplin of the Applin line is covered on the same terms), it
                # only ever PROTECTS, and it protects ONE copy: a line wears one
                # bridge per body, and `_bridge_kept_once` lets every copy after
                # the first keep the ladder's price. Unlike
                # `DISCARD_LINK_THE_SEARCH_BUYS` it is NOT gated on our own
                # Ultra Ball -- a discard forced by their Xerosic's Machinations
                # buries the bridge just as permanently.
                if (score > DISCARD_LINK_LAST_BRIDGE
                        and card.id not in _bridge_kept_once
                        and _evo_bridge_last_copies(
                            card.id, hand_counts, field_counts,
                            # Every zone a draw or a search still reaches: the
                            # belief minus the discard. The BELIEF and not
                            # `field_counts`, because a link already spent
                            # UNDER a body -- the Dipplin beneath a Hydrapple ex
                            # -- is in play without being a body, so the field
                            # count reads 0 for it and the copy in hand would
                            # look like the last one on a board whose line is
                            # already finished.
                            {_bk: sum(AGENT_STATE.ACTIVE_CARDS_IN_DECK
                                      .get(_bk, {}).get(_bz, 0)
                                      for _bz in (ZONE_DECK, ZONE_HAND,
                                                  ZONE_BENCH, ZONE_PRIZE))
                             for _line in EVO_LINES for _bk in _line})):
                    _bridge_kept_once.add(card.id)
                    score = DISCARD_LINK_LAST_BRIDGE

                if score < DISCARD_EVO_SPARE_COPY:
                    _evo_seats = _evo_copies_usable(
                        card.id, hand_counts, field_counts,
                        free_bench=max(0, my_state.benchMax - bench_count))
                    if _evo_seats is not None:
                        # ALWAYS at least one copy: with no seat at all the piece
                        # is an ORPHAN, and how much an orphan is worth is a
                        # different question that the branches above already
                        # answer (Hydrapple ex 12, Meganium 18...). This block
                        # only prices the copies BEYOND the first, which is the
                        # only reading the board settles on its own.
                        _evo_seats = max(1, _evo_seats)
                        if _evo_spare_seen.get(card.id, 0) >= _evo_seats:
                            score = DISCARD_EVO_SPARE_COPY
                        else:
                            _evo_spare_seen[card.id] = (
                                _evo_spare_seen.get(card.id, 0) + 1)

                # A BODY WITH NOWHERE TO SIT IS NOT WHAT THE FORCED DISCARD
                # KEEPS (user, `records/registro_006_pasos_077_hasta_100.json`,
                # episode 91519548, step 99, turn 6 vs Alakazam -- LOST). Their
                # Xerosic's Machinations cut a hand of six down to three:
                # Meganium (one already in play), Night Stretcher, Lana's Aid,
                # Teal Mask Ogerpon ex and two Forest of Vitality, on a bench
                # that was FULL -- Meganium, Teal Mask Ogerpon ex, Meowth ex,
                # Fezandipiti ex, Tapu Bulu.
                #
                # The block above fixes the Forests. What is left is the second
                # half of the same mistake: the scorer kept the Teal Mask
                # Ogerpon ex (25, "only one in play") over the Night Stretcher
                # (30) and the Lana's Aid (35) -- a Basic that with 5/5 on the
                # bench could not be played that turn, the next one, or any turn
                # until the opponent knocked something out.
                #
                # The evolution branches already ask the seat question from the
                # other side (`_evo_copies_usable`, `_line_base_benchable`): an
                # evolution needs a BODY of its line in play, and the block above
                # caps the copies by those bodies. A Basic enters through the
                # other door and nobody was asking about it. `_ub_target_has_no
                # _seat` is the very predicate the Ultra Ball already uses to
                # refuse to FETCH such a body -- what we will not spend two cards
                # to buy is not what we should spend a keep-slot to hold.
                #
                # NO SEAT IS NOT ENOUGH -- THE BOARD MUST ALREADY BE DOING THE
                # BODY'S JOB. A full bench is a snapshot, not a sentence: a
                # knock-out opens a seat, and the piece that could not sit today
                # may be the only answer tomorrow. The corpus said so out loud
                # -- with the rule asking only for the seat, three frozen
                # decisions started throwing away a **Tapu Bulu** against
                # ex-immune walls, where it is the one body that can break
                # through and nothing on our bench does its job.
                #
                # So the rule asks for BOTH halves: the bench cannot fit it AND
                # a copy of that same card is ALREADY IN PLAY. Then the card in
                # hand is not the plan, it is a duplicate of the plan -- which
                # is the record exactly: a second Teal Mask Ogerpon ex with one
                # already on the bench. Same doctrine as `_evo_copies_usable`
                # ("a line protects the SEATS, not the copies"), asked of the
                # door a Basic actually walks through.
                #
                # `max` on purpose: it only ever makes such a body MORE
                # discardable. A card the branches already priced as fodder
                # (a Meganium with one in play at 95, a spare Forest at 88)
                # keeps its score, so this never rescues junk -- it only moves
                # the duplicate below the utility cards the turn can still use.
                _seatless_data = card_table.get(card.id)
                if (_seatless_data is not None
                        and _seatless_data.cardType == CardType.POKEMON
                        and field_counts.get(card.id, 0) >= 1
                        and _ub_target_has_no_seat(
                            card.id,
                            max(0, my_state.benchMax - bench_count))):
                    score = max(score, DISCARD_BODY_WITHOUT_SEAT)

                # THE FORCED DISCARD PRICES A SUPPORTER BY WHAT IT DOES ON
                # *THIS* BOARD (user, episode 90115646 step 132 vs Archaludon
                # ex, LOST). Every branch above prices a Supporter with static
                # proxies -- copies in hand, "the last refill", the size of the
                # discard pile -- and not one of them asks the board what the
                # card would actually do. In the record that inverted the whole
                # hand: Lana's Aid fell at 35 (`len(discard) > 2`) while Dawn
                # kept its 3 for being the last refill and Boss's Orders its 20
                # for `op_prize <= 3`. The value layer had already read that
                # exact board in that exact decision and said the opposite --
                # Lana's Aid 750, Dawn 0, Boss's Orders 0 -- because with a full
                # bench Dawn had nothing to search for and Boss's no gust worth
                # taking, while the discard held the Grass that on the next turn
                # takes Myriad Leaf Shower from 270 to 330 on a 300 HP ex.
                #
                # So the ordering AMONG the Supporters in hand follows
                # `_supp_values`, the same reading that decides which Supporter
                # gets played -- the card we keep and the card we would play
                # cannot disagree. It names no card, so it holds for any deck.
                #
                # Two guards keep it a strict no-op unless the board really has
                # a preference:
                #   * it needs ANOTHER Supporter in hand to trade against (with
                #     a single one there is nothing to permute);
                #   * KEEP asks for a STRICT maximum and DROP for a live value
                #     of zero facing a sibling above zero. With `_supp_values`
                #     silent (every entry 0, or the dict empty) neither fires.
                #
                # AND IT ONLY SPEAKS ABOUT THE SUPPORTERS THE VALUE LAYER
                # ACTUALLY PRICES (user, `records/registro_013_pasos_113_hasta
                # _124.json`, episode 91513072, step 114, turn 13 vs Alakazam --
                # LOST). Their Xerosic's Machinations cut a hand of seven down to
                # three and the agent paid with its OWN Xerosic's Machinations --
                # the one card the matchup is built around, the cap on a
                # Powerful Hand that was reading an 18-card hand at the time.
                #
                # The branch above had already answered that question the right
                # way (`op_is_alakazam_deck` -> 5, "protect it like the Meganium
                # line"), and this block overwrote it with 36. Not because it
                # judged the cap useless: because `evaluate_supporters` prices
                # FOUR ids -- Boss's, Lillie's, Dawn, Lana's -- and Xerosic's
                # Machinations is not one of them. Its play value lives on the
                # other scale (`_score_xerosic_play`, the disruption engine), so
                # `_supp_values.get(card.id, 0)` read a MISSING KEY as a live
                # value of zero and the block declared dead the only Supporter it
                # had never asked about. Structural, not situational: on that
                # scale the cap can never be anything but dead, in any deck, on
                # any board, and the same holds for any Supporter added to
                # `_SUPP_PLAY_IDS` without a branch in the value layer.
                #
                # So SILENCE IS NOT A ZERO. The block asks for MEMBERSHIP, not
                # for a default: a card the layer never priced is unmeasured, and
                # about the unmeasured this reading says nothing -- neither KEEP
                # nor DROP -- leaving the last word to the ladder branch above,
                # which is where the matchup knowledge already lives.
                #
                # The membership guard is on the SUBJECT of the sentence only.
                # The rivals list is left exactly as it was, and deliberately: it
                # answers a different question -- "is there another Supporter in
                # hand that could be sacrificed instead?" -- and an unpriced
                # sibling is still a Supporter one can trade against. Filtering
                # it out of there as well was measured against the frozen corpus
                # and it emptied the rivals list on a hand whose only two
                # Supporters were a priced one and the cap, cancelling a KEEP
                # that had nothing to do with this bug (registro_028, turn 7).
                #
                # And it stays inside the Supporter band on purpose (see the
                # constants): it changes WHICH Supporter is sacrificed, never
                # how many non-Supporters are.
                # ...AND THE SCALE IT RANKS THEM ON IS THE ONE THAT RESOLVES THE
                # SLOT (user, `records/registro_004_pasos_040_hasta_055.json`
                # step 44, episode 93428975 vs Mega Lucario ex -- LOST). The
                # board and the whole cascade are written out in
                # `THE_COST_KEEPS_THE_SUPPORTER_THE_TURN_PLAYS`.
                #
                # `_supp_values` is a FETCH scale: it prices the slot for the
                # searchers, which have to guess what a card still in the deck
                # would be worth. On that board it read Dawn 900 over Lillie's
                # Determination 750 -- correctly by its own lights, since with a
                # Forest of Vitality on the field a search for bodies assembles a
                # whole chain in one turn. The PLAY scorers, asked in the same
                # tick, said Lillie's 5000. So this block handed its keep floor to
                # the card the turn would not play, and the Ultra Ball's cost
                # took the one it would.
                #
                # `_supp_that_takes_the_turn` is `_best_supporter_in_hand` -- the
                # same PLAY scale `_supp_in_hand_takes_the_turn` already insists
                # on for exactly this reason ("the fetch scale orders the same
                # pair the other way round"). It answers the KEEP half only. The
                # DROP half below still reads `_supp_values`, and deliberately:
                # "this card is dead today" is a statement about the board, the
                # two scales do not disagree about it, and a card the play
                # scorers merely rank second is not dead.
                #
                # It is None while the slot is spent, and then this reads exactly
                # as it did before. Nothing else changes: the floor stays inside
                # the Supporter band, so it still decides WHICH Supporter is
                # sacrificed and never how many.
                if card.id in _SUPP_PLAY_IDS and card.id in _supp_values:
                    _dsv_live = _supp_values.get(card.id, 0) or 0
                    _dsv_rivals = [_supp_values.get(_sid, 0) or 0
                                   for _sid in _SUPP_PLAY_IDS
                                   if _sid != card.id
                                   and hand_counts.get(_sid, 0) >= 1]
                    if _dsv_rivals:
                        # The KEEP verdict, and ONLY it: the play scale names the
                        # card that holds the job, the value layer decides
                        # nothing about it. The `elif` below is left byte for
                        # byte as it was.
                        _dsv_takes_the_turn = (_dsv_live > 0
                                               and _dsv_live > max(_dsv_rivals))
                        if (THE_COST_KEEPS_THE_SUPPORTER_THE_TURN_PLAYS
                                and _supp_that_takes_the_turn is not None):
                            _dsv_takes_the_turn = (
                                card.id == _supp_that_takes_the_turn)
                        if _dsv_takes_the_turn:
                            # AND ONLY THE FIRST COPY GETS IT (user, August
                            # 2026, found by `utils/duplicate_protection_audit
                            # .py` over the 118 discard menus of the frozen
                            # corpus: four records where two Lillie's
                            # Determination came out of this block sharing a 2).
                            #
                            # The floor is a ROLE -- "the best Supporter I could
                            # still play" -- and only one card can play it: a
                            # turn plays ONE Supporter. Said of every copy in
                            # hand it protects the surplus, which is the one
                            # thing that can never be the reason. The ladder
                            # already knew (`_lillie_protected_once`: keep one
                            # at 2, release the spare at 72) and this `min()`
                            # pulled the spare back down to 2 sixty lines later
                            # -- the general rule undoing its own special case.
                            #
                            # The DROP branch below does NOT latch, and the
                            # asymmetry is the argument: "this Supporter is dead
                            # and another one is live" is equally true of every
                            # copy, and every copy really should go. Only a KEEP
                            # claims a job.
                            if card.id not in _supp_live_keep_once:
                                _supp_live_keep_once.add(card.id)
                                score = min(score, DISCARD_SUPPORTER_LIVE_KEEP)
                        elif _dsv_live <= 0 and max(_dsv_rivals) > 0:
                            score = max(score, DISCARD_SUPPORTER_DEAD_DROP)

                # Strategy vs Comfey (user, registro_005): a discard forced by
                # Xerosic's Machinations (it leaves us with ONLY 3 cards in hand). The
                # KEEPING priority is: the hand recycler > Energies > Night
                # Stretcher > Lana's
                # Aid > Unfair Stamp > the other trainers. The score here is a
                # DISCARD one (higher = discarded sooner), so the cards to
                # KEEP carry a LOW score. An EXTRA Ogerpon ex (there are already 2 in
                # play) is useless -> it is discarded; if more still fit (<2), it is kept
                # above the trainers because it is the matchup's plan.
                #
                # THE CARD THAT ANSWERS THE MILL WAS IN THE `else` (user,
                # `records/registro_009_pasos_072_hasta_078.json`, episode
                # 91837627, step 77, turn 9 vs Comfey/Brambleghast -- LOST while
                # AHEAD on prizes 4-6, which is what deck-out looks like).
                #
                # Their Xerosic's Machinations cut a hand of sixteen down to
                # three. Twelve of the thirteen discards were right -- the two
                # Xerosic of ours are dead against a deck with nothing to cap,
                # the line pieces had no seat -- and the thirteenth was Lillie's
                # Determination, the only card in hand that puts cards BACK into
                # the deck they are emptying.
                #
                # It did not lose on a judgement. This ladder names six cards and
                # sends EVERYTHING else to one number: Lillie's came out at 850,
                # tied with a spare Applin. The general ladder had already priced
                # that same copy at 2 (`_protect_refresh_supporter`, "the last
                # refill") sixty lines above, and this block overwrote it --
                # a matchup table speaking about a card it never measured. Same
                # shape as `el-silencio-de-una-capa-de-valor-no-es-un-cero`, one
                # layer down.
                #
                # The fix is a rung, not a hole in the table: the recycler is
                # read off the printed text (`HAND_TO_DECK_PLAY_IDS`) rather than
                # by name, and it takes the top of the ladder. See
                # `DISCARD_CF_HAND_RECYCLER` for why it outranks the energy and
                # why keeping it is not the same as playing it.
                if op_is_comfey_deck:
                    if (card.id in HAND_TO_DECK_PLAY_IDS
                            and card.id != Unfair_Stamp
                            and card.id not in _cf_refill_kept_once):
                        # The Unfair Stamp recycles the hand too, but it is
                        # playable only after they knock one of our Pokemon out
                        # -- against a mill deck that may never happen -- so it
                        # keeps the conditional rung it already had, below.
                        _cf_refill_kept_once.add(card.id)
                        score = DISCARD_CF_HAND_RECYCLER
                    elif card.id == Basic_Grass_Energy:
                        score = 80
                    elif card.id == Teal_Mask_Ogerpon_ex:
                        score = (850 if field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2
                                 else 120)
                    elif card.id == Night_Stretcher:
                        score = 300
                    elif card.id == Bug_Catching_Set:
                        # The matchup's Grass supplier (see the allowlist):
                        # it is kept alongside NS/Lana's, below the energy.
                        score = 350
                    elif card.id == Lanas_Aid:
                        score = 400
                    elif card.id == Unfair_Stamp:
                        score = 500
                    else:
                        score = 850

                # ...AND THE SAME DECK'S OTHER HALF, WHICH THIS LADDER COULD NOT
                # SEE. Their Acerola's Mischief silences our ex on the turn that
                # follows, so the hand their cap leaves us is judged by one
                # question -- what can still put damage on their board -- and the
                # answer reorders it from both ends. The rungs and the record are
                # on `DISCARD_SHIELD_MUTES_THE_EX`.
                #
                # It rides ON TOP of the Comfey ladder rather than replacing it:
                # the mill is still running (the recycler keeps its 60, the
                # energy its 80) and this only moves the cards whose value the
                # shield changes. It is also not gated on `op_is_comfey_deck` --
                # the shield is a card, not a deck, and any list that plays it
                # asks the same question of our hand.
                if (AGENT_STATE.op_has_ex_shield and _forced_discard
                        and my_prize <= OP_EX_SHIELD_MAX_PRIZES):
                    if card.id in OUR_EX_IDS:
                        score = DISCARD_SHIELD_MUTES_THE_EX
                    elif card.id == Forest_of_Vitality and not _counter_stadium_kept_once:
                        # ...unless the FIRST copy is still the only way to lift
                        # a hostile stadium, which the block above has already
                        # claimed by latching `_counter_stadium_kept_once`. Two
                        # walls at once is exactly the board where throwing the
                        # counter away loses the game twice.
                        score = DISCARD_SHIELD_STADIUM_FODDER
                    elif card.id == Ultra_Ball:
                        score = DISCARD_SHIELD_SEARCH_FODDER
                    elif card.id == Boss_Orders:
                        score = min(score, DISCARD_SHIELD_KEEP_THE_GUST)
                    elif card.id in (Applin, Dipplin):
                        score = min(score, DISCARD_SHIELD_KEEP_THE_NONEX)
        
            elif context == SelectContext.RECOVER_SPECIAL_CONDITION:
        
                if hasattr(card, 'id'):
                    score = 50
            elif context == SelectContext.AFFECT_SPECIAL_CONDITION:
        
                score = 50
            elif context == SelectContext.ATTACH_FROM:
                score = energy_score(card, o.area == AreaType.ACTIVE)
                # Target of Ripening Charge when the ability is played
                # FOR THE HEALING (see `_ripen_heal_serial`): the Grass goes to the
                # body that dies to the projected hit and that with +30 survives.
                # 39500 beats all normal development and stays BELOW the
                # future attacker (_tapu_future_charge, 40000) and below the
                # lethal charges (41000/42000), which also already veto the flag.
                if (_ripen_heal_serial is not None and score > 0
                        and getattr(card, 'serial', None) == _ripen_heal_serial):
                    score = max(score, RIPEN_HEAL_TARGET_SCORE)
        return score
    finally:
        tc._bp = _bp
        tc._dc = _dc
        tc._counter_stadium_kept_once = _counter_stadium_kept_once
        tc._evo_spare_seen = _evo_spare_seen
        tc._bridge_kept_once = _bridge_kept_once
        tc._bought_spare_seen = _bought_spare_seen
        tc._has_bench_attacker = _has_bench_attacker
        tc._lillie_protected_once = _lillie_protected_once
        tc._tb_req = _tb_req
        tc.b = b
        tc.bp = bp
        tc.card = card
        tc.energy_count = energy_count
        tc.pid = pid


__all__ = ['score_play']
