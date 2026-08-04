"""Context of `evaluate_supporters`: what it used to capture from the turn.

Generated when the closure was lifted out of `agent()` (wave 5). There are 41
fields: the ones the function read from `agent`'s scope without receiving them
as parameters.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class CtxEvaluateSupporters:
    """Captures of `evaluate_supporters`."""

    _active_cant_attack_this_turn: Any = None
    _grass_plan: Any = None
    bench_count: Any = None
    bench_max: Any = None
    budew_on_op_field: Any = None
    budew_op_index: Any = None
    can_switch: Any = None
    estimated_op_damage: Any = None
    field_counts: Any = None
    hand_counts: Any = None
    has_hydrapple: Any = None
    has_switch_card: Any = None
    meowth_ability_lock: Any = None
    my_prize: Any = None
    my_state: Any = None
    neutralization_zone_active: Any = None
    op_active_dodge_immune: Any = None
    op_has_ability_immune_active: Any = None
    op_has_crustle_bench: Any = None
    op_has_dreepy_line: Any = None
    op_has_dwebble_bench: Any = None
    op_has_eevee_bench: Any = None
    op_has_ethan_preevo: Any = None
    op_has_ex_immune_active: Any = None
    op_has_ex_immune_bench: Any = None
    op_has_froslass: Any = None
    op_has_latias_ex: Any = None
    op_has_munkidori: Any = None
    op_has_snorunt_bench: Any = None
    op_has_typhlosion: Any = None
    op_is_alakazam_deck: Any = None
    op_is_dragapult_dusknoir: Any = None
    op_is_drednaw_deck: Any = None
    op_is_gardevoir_deck: Any = None
    op_is_slowking_deck: Any = None
    op_is_sylveon_deck: Any = None
    op_is_zoroark_deck: Any = None
    op_prize: Any = None
    op_state: Any = None
    state: Any = None
    total_grass: Any = None


__all__ = ['CtxEvaluateSupporters']
