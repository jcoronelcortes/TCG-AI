"""Context of `_energy_score_base`: what it used to capture from the turn.

Generated when the closure was lifted out of `agent()` (wave 5). There are 61
fields: the ones the function read from `agent`'s scope without receiving them
as parameters.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class CtxEnergyScoreBase:
    """Captures of `_energy_score_base`."""

    _ability_unlock_retreat_attack: Any = None
    _ability_unlock_retreat_ko: Any = None
    _active_already_kos: Any = None
    _active_hydra_capped: Any = None
    _active_needs_energy: Any = None
    _active_pokemon: Any = None
    _attach_enable_retreat_attack: Any = None
    _attach_enable_retreat_ko: Any = None
    _bench_attacker_needs_energy: Any = None
    _bench_attacker_ready: Any = None
    _bench_has_chargeable: Any = None
    _charge_active_enables_attack: Any = None
    _charge_active_finishes: Any = None
    _conf_active: Any = None
    _conf_active_can_attack: Any = None
    _conf_active_can_retreat: Any = None
    _conf_bench_attacker_body: Any = None
    _conf_bench_attacker_ready: Any = None
    _conf_can_attack_pkmn: Any = None
    _conf_is_matchup_attacker: Any = None
    _ctm_applin_bench: Any = None
    _ctm_charge_active_dipplin: Any = None
    _ctm_chikorita_bench: Any = None
    _ctm_tapu_high: Any = None
    _cubchoo_lock_stuck: Any = None
    _ex_stuck_promo_ready: Any = None
    _extra_energy_enables_ko: Any = None
    _feza_lucario_wall: Any = None
    _ft_wall_charge_active: Any = None
    _gust_2prize_via_boss: Any = None
    _hydra_fragile_pivot: Any = None
    _meganium_alk_1prize_attacker: Any = None
    _meganium_alk_future_charge: Any = None
    _ogerpon_lethal_focus_serial: Any = None
    _ogerpon_td_manual_lethal: Any = None
    _ripen_retreat_ko_pivot: Any = None
    _tapu_future_charge: Any = None
    _win_via_boss_gust: Any = None
    active_ko_likely: Any = None
    bench_count: Any = None
    field_counts: Any = None
    hand_counts: Any = None
    has_hydrapple: Any = None
    is_confused: Any = None
    my_state: Any = None
    neutralization_zone_active: Any = None
    op_has_ex_immune_active: Any = None
    op_has_ex_immune_bench: Any = None
    op_has_froslass: Any = None
    op_is_aggro_deck: Any = None
    op_is_alakazam_deck: Any = None
    op_is_beedrill_deck: Any = None
    op_is_cubchoo_deck: Any = None
    op_is_drednaw_deck: Any = None
    op_is_fire_deck: Any = None
    op_is_hop_deck: Any = None
    op_is_lucario_deck: Any = None
    op_is_sylveon_deck: Any = None
    op_kang_ko_target: Any = None
    op_state: Any = None
    state: Any = None
    total_grass: Any = None


__all__ = ['CtxEnergyScoreBase']
