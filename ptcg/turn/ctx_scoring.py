"""`ScoringCtx`: everything the option-scoring chain reads from the turn.

Built ONCE before the loop over `select.option`, not once per option -- there
are 225 fields and a menu can hold dozens of options.

WHY IT IS A FLAT BAG OF `Any` FIELDS DEFAULTING TO None. This is not a designed
interface; it is the set of local variables the phases of `agent()` used to
share, given an explicit home so the function could be split. main.py fills it
from `locals()` rather than by keyword, because some of these names are only
bound on certain paths -- passing them explicitly would force their evaluation
and raise on exactly the paths where the original code never read them.
Anything unbound stays None, guarded by the same checks as before.

REASSIGNED VS MUTATED, the one rule to respect when editing a branch. A branch
that REASSIGNS a field must hand it back when it finishes, because later
iterations of the option loop read it. A branch that MUTATES an object in place
-- adding to a set, say -- needs to hand back nothing: it is the same object
every option sees. Getting this backwards produces a value that silently
reverts between two options of the same menu.

The per-branch docstrings in `ptcg/turn/options/` state how many fields each
one reads and reassigns.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ScoringCtx:
    """Snapshot of the turn used to score one option."""

    _SALTAR: Any = None
    _BCS_FETCH_TABLE: Any = None
    _DAWN_FETCH_TABLE: Any = None
    _order_veto: Any = None
    _ability_unlock_retreat_attack: Any = None
    _ability_unlock_retreat_ko: Any = None
    _active_already_kos: Any = None
    _ctm_wall_in_the_way: Any = None
    _active_attack_wins_now: Any = None
    _active_cant_attack_this_turn: Any = None
    _active_doomed_real: Any = None
    _active_hydra_cannot_ko: Any = None
    _active_hydra_ready: Any = None
    _active_needs_energy: Any = None
    _active_ready_attacker: Any = None
    _active_snipe_ko_now: Any = None
    _active_snipe_ko_prizes: Any = None
    _alakazam_pivot_1prize: Any = None
    _alk_ld_engine_alive: Any = None
    _ara_act: Any = None
    _atk: Any = None
    _attach_yields_to_teal_dance: Any = None
    _attach_enable_retreat_attack: Any = None
    _attach_enable_retreat_ko: Any = None
    _attach_reaches_no_cost: Any = None
    _b: Any = None
    _bcs_playable_in_hand: Any = None
    _bdg_retreat_ko: Any = None
    _bench_attacker_ready: Any = None
    _boss_gust_immune_active: Any = None
    _gust_finds_an_attacker: Any = None
    _bench_has_chargeable: Any = None
    _best_promote_card: Any = None
    _best_promote_key: Any = None
    _promo_evo_koer: Any = None
    _best_supp_in_hand_val: Any = None
    _best_supp_in_deck_id: Any = None
    _best_supp_in_deck_val: Any = None
    _bp: Any = None
    _bp_e: Any = None
    _bp_eff: Any = None
    _charge_active_missing: Any = None
    _charge_active_enables_attack: Any = None
    _charge_active_finishes: Any = None
    _cap_kept_once: Any = None
    _cf_refill_kept_once: Any = None
    _cm_use_ex: Any = None
    _conf_can_attack_pkmn: Any = None
    _conf_is_matchup_attacker: Any = None
    _conf_should_attack: Any = None
    _conf_should_retreat: Any = None
    _cubchoo_lock_stuck: Any = None
    _cubchoo_mute_cashes_prize: Any = None
    _cubchoo_mute_rotates: Any = None
    _cubchoo_ko_rotation_min: Any = None
    _doomed_body: Any = None
    _doomed_mute_pivot: Any = None
    _doomed_sac_context: Any = None
    _doomed_sac_wall_in_hand: Any = None
    _dc: Any = None
    _deny_evo_via_boss: Any = None
    _prize_mismatch_matchup: Any = None
    _dmg_vs_wall: Any = None
    _dragapult_no_tapu: Any = None
    _e: Any = None
    _eff: Any = None
    _energy_in_hand: Any = None
    _energy_score_base: Any = None
    _enough_after_priorities: Any = None
    _enough_for_both: Any = None
    _evo_huerfanos: Any = None
    _evo_necesarios: Any = None
    _counter_stadium_kept_once: Any = None
    _evo_spare_seen: Any = None
    _bridge_kept_once: Any = None
    _bought_spare_seen: Any = None
    _ex_stuck_promo_ready: Any = None
    _extra_energy_enables_ko: Any = None
    _festival_lead_hostil: Any = None
    _festival_lead_pays_us_now: Any = None
    _festival_refill_buys_the_wave: Any = None
    _festival_wave_outprizes_the_front: Any = None
    _festival_wave_needs_the_grass: Any = None
    _forced_ko_promote: Any = None
    _ft_hold_lone_meowth: Any = None
    _ft_wall_body: Any = None
    _ft_wall_charge_active: Any = None
    _ft_wall_in_hand: Any = None
    _ft_wall_pivot: Any = None
    _ft_wall_promote: Any = None
    _grass_anywhere_enables_syrup_ko: Any = None
    _grass_enables_promote_ko: Any = None
    _gt_plan: Any = None
    _gt_planes: Any = None
    _gt_turn_plans: Any = None
    _gt_prompt_si_no: Any = None
    _gt_quiere_basico: Any = None
    _gt_root_in_play: Any = None
    _gt_basics_ranking: Any = None
    _gt_score_selection: Any = None
    _gt_vetoes_ex_stage: Any = None
    _gust_2prize_via_boss: Any = None
    _has_bench_attacker: Any = None
    _hydra_fragile_pivot: Any = None
    _hydra_pivot_active: Any = None
    _hydra_wall_pivot: Any = None
    _hydrapple_bench_needs_energy: Any = None
    _ko_prefer_basic_general: Any = None
    _lana_grass_order: Any = None
    _lana_plan: Any = None
    _ld_lillie_ofrecida: Any = None
    _lillie_blocks_fez_ability: Any = None
    _lillie_protected_once: Any = None
    _lucario_ko_prefer_basic: Any = None
    _lucario_other_sac_available: Any = None
    _lucario_riolu_gust: Any = None
    _lucario_sac_available: Any = None
    _lucario_sac_context: Any = None
    _lucario_sac_pivot: Any = None
    _mega_line_active: Any = None
    _meowth_antidonk_now: Any = None
    _meowth_devel_lillie: Any = None
    _meowth_recovery_ko: Any = None
    _meowth_fetch_loses_the_turn: Any = None
    _meowth_fetch_redundante: Any = None
    _meowth_fetch_already_in_hand: Any = None
    _meowth_immune_boss_engine: Any = None
    _meowth_ld_free: Any = None
    _meowth_skip_fetch: Any = None
    _no_second_attacker_path: Any = None
    _plan_relay_is_inert: Any = None
    _ready_attack_is_inert: Any = None
    _nonex_active_hits_wall: Any = None
    _ogerpon_lethal_focus_serial: Any = None
    _op_act: Any = None
    _op_best_damage_vs: Any = None
    _op_evo_dmg_to_active: Any = None
    _op_counter_threat_vs: Any = None
    _our_first_action_turn: Any = None
    _our_first_turn: Any = None
    _p: Any = None
    _prize_denial_pivot: Any = None
    _promo_damage_to_op: Any = None
    _promo_kos_op: Any = None
    _promo_min_prize: Any = None
    _ko_front_outranked: Any = None
    _mp_cheaper_candidate: Any = None
    _mp_front_survivors: Any = None
    _mp_last_stand: Any = None
    _mp_outlasts: Any = None
    _mp_price_ends_the_game: Any = None
    _promo_bet_walks_back: Any = None
    _promo_ko_wins_the_game: Any = None
    _promo_op_act: Any = None
    _promo_survives: Any = None
    _promo_survivors: Any = None
    _promo_wall_relief: Any = None
    _promote_setup_ko_attacker: Any = None
    _ready_attacker_count: Any = None
    _refresh_promote_prefer_basic: Any = None
    _reserve_energy_for_hydra_evolve: Any = None
    _reserve_hydra_active_charge: Any = None
    _ripen_bench_ready_pivot: Any = None
    _ripen_bench_tapu_ko_pivot: Any = None
    _ripen_heal_ex: Any = None
    _ripen_heal_serial: Any = None
    _ripen_retreat_ko_pivot: Any = None
    _score_boss_orders_play: Any = None
    _score_forest_of_vitality_play: Any = None
    _lillie_play_order_veto: Any = None
    _score_lillie_determination_play: Any = None
    _score_night_stretcher_play: Any = None
    _score_ultra_ball_play: Any = None
    _sel_active_cant_attack: Any = None
    _self_ko_by_own_attack: Any = None
    _sid: Any = None
    _stamp_blocks_supp_chain: Any = None
    _opening_sac_charge_active: Any = None
    _opening_sac_needs_body: Any = None
    _doomed_sac_needs_body: Any = None
    _opening_sac_pivot: Any = None
    _opening_sac_promote: Any = None
    _opening_sac_wall_in_hand: Any = None
    _suicide_loses: Any = None
    _suicide_only_draws: Any = None
    _suicide_swap_win_promote: Any = None
    _supp_values: Any = None
    _supp_live_keep_once: Any = None
    _ub_offered_in_menu: Any = None
    _tapu_future_charge: Any = None
    _tapu_sac_enable_retreat: Any = None
    _tapu_sac_pivot: Any = None
    _festival_sac_pivot: Any = None
    _tapu_sac_priority: Any = None
    _tb_req: Any = None
    _teal_dance_ko_pivot: Any = None
    _teal_dance_slots: Any = None
    _teal_wall_pivot: Any = None
    _ub_meowth_for_tomorrow: Any = None
    _ub_supp_in_hand_turn: Any = None
    _supp_that_takes_the_turn: Any = None
    _wall_ko_promote: Any = None
    _win_ko_active_via_promote: Any = None
    _win_via_boss_gust: Any = None
    active_hp_ratio: Any = None
    active_ko_likely: Any = None
    b: Any = None
    bench_count: Any = None
    bp: Any = None
    budew_on_op_field: Any = None
    can_attack: Any = None
    can_switch: Any = None
    card: Any = None
    condition_blocks_action: Any = None
    condition_risky_attack: Any = None
    condition_urgency: Any = None
    context: Any = None
    ctx: Any = None
    data: Any = None
    discard_counts: Any = None
    energy_count: Any = None
    energy_score: Any = None
    estimated_op_damage: Any = None
    evaluate_supporters: Any = None
    field_counts: Any = None
    hand_counts: Any = None
    has_condition: Any = None
    has_hydrapple: Any = None
    has_ogerpon: Any = None
    has_switch_card: Any = None
    is_confused: Any = None
    itchy_pollen_active: Any = None
    meowth_ability_lock: Any = None
    my_index: Any = None
    my_prize: Any = None
    my_state: Any = None
    neutralization_zone_active: Any = None
    obs: Any = None
    op_active_dodge_immune: Any = None
    op_active_is_kangaskhan: Any = None
    op_bench_snipe_threat: Any = None
    op_double_attack_pending: Any = None
    op_has_ability_immune_active: Any = None
    op_has_dragapult: Any = None
    op_has_dreepy_line: Any = None
    op_has_dwebble_bench: Any = None
    op_has_ethan_preevo: Any = None
    op_has_ex_immune_active: Any = None
    op_has_ex_immune_bench: Any = None
    op_has_froslass: Any = None
    op_has_latias_ex: Any = None
    op_has_mega_starmie_active: Any = None
    op_has_typhlosion: Any = None
    op_is_aggro_deck: Any = None
    op_is_alakazam_deck: Any = None
    op_is_beedrill_deck: Any = None
    op_is_comfey_deck: Any = None
    op_is_control_deck: Any = None
    op_is_cubchoo_deck: Any = None
    op_is_dragapult_dusknoir: Any = None
    op_is_drednaw_deck: Any = None
    op_is_fire_deck: Any = None
    op_is_greninja_deck: Any = None
    op_is_hop_deck: Any = None
    op_is_iron_thorns_deck: Any = None
    op_is_lucario_deck: Any = None
    op_is_mirror: Any = None
    op_is_sylveon_deck: Any = None
    op_kang_ko_target: Any = None
    op_prize: Any = None
    op_state: Any = None
    pid: Any = None
    pokemon: Any = None
    scores: Any = None
    select: Any = None
    stadium_id: Any = None
    state: Any = None
    total_grass: Any = None
    watchtower_in_play: Any = None


REASIGNADAS = ['_atk', '_b', '_bench_attacker_ready', '_bought_spare_seen', '_bridge_kept_once', '_bp', '_bp_e', '_bp_eff', '_counter_stadium_kept_once', '_dc', '_e', '_eff', '_energy_in_hand', '_evo_spare_seen', '_has_bench_attacker', '_lillie_protected_once', '_op_act', '_our_first_turn', '_sid', '_tb_req', 'b', 'bp', 'card', 'data', 'energy_count', 'pid', 'pokemon']


__all__ = ['ScoringCtx', 'REASIGNADAS']
