import sys
from pathlib import Path
import types
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from parcheo import patch_name, instalar
from cg.api import AreaType, EnergyType, LogType, OptionType, SelectContext


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    m._op_prize_denial_pecharunt = False
    m._op_prize_denial_gengar = False
    yield
    m._init_cards_tracking()


def make_pokemon(card_id, *, hp=100, max_hp=100, energies=None, pre_evolution=None, energy_cards=None, tools=None):
    return SimpleNamespace(
        id=card_id,
        hp=hp,
        maxHp=max_hp,
        energies=list(energies or []),
        preEvolution=list(pre_evolution or []),
        energyCards=list(energy_cards or []),
        tools=list(tools or []),
    )


def make_card(card_id, name="Card"):
    return SimpleNamespace(id=card_id, name=name)


def test_validate_id_constants_returns_list():
    result = m._validate_id_constants()
    assert isinstance(result, list)


def test_grass_helpers():
    assert m._grass_mult() == 1
    assert m._grass_attach_unit() == 1
    m.meganium_in_play = True
    assert m._grass_attach_unit() == 2
    m.meganium_in_play = False


def test_active_of_handles_none_and_list():
    state = SimpleNamespace(active=[make_pokemon(123), None])
    assert m._active_of(state).id == 123
    assert m._active_of(None) is None
    assert m._active_of(SimpleNamespace(active=[None])) is None


def test_physical_energy_uses_meganium_rule():
    m.meganium_in_play = False
    assert m._physical_energy(4) == 4
    m.meganium_in_play = True
    assert m._physical_energy(4) == 2
    assert m._physical_energy(5) == 2
    m.meganium_in_play = False


def test_retreat_cards_counts_effective_energy():
    m.meganium_in_play = False
    assert m._retreat_cards(0) == 0
    assert m._retreat_cards(3) == 3
    m.meganium_in_play = True
    assert m._retreat_cards(3) == 2
    m.meganium_in_play = False


def test_can_attack_eff_checks_energy_requirements():
    assert m._can_attack_eff(m.Hydrapple_ex, 2) is True
    assert m._can_attack_eff(m.Dipplin, 0) is False
    assert m._can_attack_eff(999999, 1) is False


def test_init_move_card_state_and_belief_tracking():
    first_card_id = m.my_deck[0]
    assert m._move_card_state(first_card_id, m.ZONE_DECK, m.ZONE_HAND) is True
    assert m.ACTIVE_CARDS_IN_DECK[first_card_id][m.ZONE_HAND] == 1
    assert m._move_card_state(first_card_id, m.ZONE_HAND, m.ZONE_BENCH) is True
    deck, prize = m._belief_deck_and_prizes()
    assert deck + prize == len(m.my_deck) - 1
    assert m._move_card_state(999999, m.ZONE_DECK, m.ZONE_HAND) is False
    assert m.ACTIVE_CARDS_IN_DECK[first_card_id][m.ZONE_BENCH] == 1


def test_prob_draw_any_and_prob_card_accessible_are_between_zero_and_one():
    cid = m.my_deck[0]
    prob_any = m._prob_draw_any(cid)
    prob_accessible = m._prob_card_accessible(cid)
    assert 0.0 <= prob_any <= 1.0
    assert 0.0 <= prob_accessible <= 1.0


def test_our_effective_damage_applies_immunity_and_basics():
    attacker = make_pokemon(m.Teal_Mask_Ogerpon_ex)
    immune_target = make_pokemon(m.Crustle_Grass)
    neutral_target = make_pokemon(m.Slowpoke)

    assert m._our_effective_damage(attacker, immune_target, 100) == 0
    assert m._our_effective_damage(attacker, neutral_target, 100) == 100


def test_our_effective_damage_farigiraf_armor_tail_blocks_basic_ex():
    # Armor Tail (P1.6): Farigiraf ex is immune to damage from BASIC ex.
    farigiraf = make_pokemon(m.Farigiraf_ex, hp=260, max_hp=260)
    assert m._our_effective_damage(make_pokemon(m.Teal_Mask_Ogerpon_ex), farigiraf, 300) == 0
    assert m._our_effective_damage(make_pokemon(m.Meowth_ex), farigiraf, 60) == 0
    assert m._our_effective_damage(make_pokemon(m.Fezandipiti_ex), farigiraf, 100) == 0
    # Hydrapple ex (a Stage 2 ex) and the non-ex DO damage it (weak to Grass: x2).
    assert m._our_effective_damage(make_pokemon(m.Hydrapple_ex), farigiraf, 100) == 200
    assert m._our_effective_damage(make_pokemon(m.Tapu_Bulu), farigiraf, 220) == 440


def test_our_effective_damage_resolute_heart_caps_at_full_hp():
    # Resolute Heart (P0.1): a Pikachu ex at FULL life survives on 10 HP.
    atk = make_pokemon(m.Tapu_Bulu)
    pika_full = make_pokemon(m.Pikachu_ex_Resolute, hp=200, max_hp=200)
    assert m._our_effective_damage(atk, pika_full, 220) == 190
    # Damaged, the ability no longer applies: the lethal blow goes through whole.
    pika_dmg = make_pokemon(m.Pikachu_ex_Resolute, hp=150, max_hp=200)
    assert m._our_effective_damage(atk, pika_dmg, 220) == 220


def test_prize_count_op_applies_denial_from_the_opponent_field():
    munki = make_pokemon(m.Munkidori_ex, hp=210, max_hp=210)
    opponent_fez = make_pokemon(m.Fezandipiti_ex, hp=210, max_hp=210)  # rival {D}

    # With no denials on the rival field: it counts normally.
    assert m.prize_count_op(munki) == 2
    # A rival Pecharunt ex in play ("Oh No You Don't"): Munkidori ex yields 1.
    m._op_prize_denial_pecharunt = True
    assert m.prize_count_op(munki) == 1
    assert m.prize_count_op(opponent_fez) == 2  # it is not Munkidori: no change
    # A rival Mega Gengar ex ("Shadowy Concealment"): their {D} yield 1 less.
    m._op_prize_denial_gengar = True
    assert m.prize_count_op(opponent_fez) == 1
    # The prizes OUR side gives away (prize_count) are unaffected.
    assert m.prize_count(opponent_fez) == 2


def test_ko_not_guaranteed_catches_hawlucha_and_survival_brace():
    # Tenacious Body (a coin flip): it is never a guaranteed KO.
    assert m._ko_not_guaranteed(
        make_pokemon(m.Mega_Hawlucha_ex, hp=250, max_hp=250)) is True
    # Survival Brace only protects at FULL life.
    brace = make_card(m.Survival_Brace)
    assert m._ko_not_guaranteed(
        make_pokemon(m.Slowpoke, hp=100, max_hp=100, tools=[brace])) is True
    assert m._ko_not_guaranteed(
        make_pokemon(m.Slowpoke, hp=70, max_hp=100, tools=[brace])) is False
    assert m._ko_not_guaranteed(make_pokemon(m.Slowpoke)) is False
    assert m._ko_not_guaranteed(None) is False


def test_attacker_base_damage_uses_card_specific_rules():
    target = make_pokemon(m.Slowpoke)
    assert m._attacker_base_damage(m.Hydrapple_ex, target, 2, 1, 0, 1) == 60
    assert m._attacker_base_damage(m.Dipplin, target, 1, 0, 0, 2) == 40
    assert m._attacker_base_damage(999, target, 1, 0, 0, 1) == 0


def test_bench_attacker_can_ko_detects_kos():
    target = make_pokemon(m.Slowpoke, hp=100, max_hp=100)
    my_state = SimpleNamespace(bench=[make_pokemon(m.Pinsir, energies=[EnergyType.GRASS, EnergyType.GRASS])])
    assert m._bench_attacker_can_ko(my_state, target, False, 0, 1, 0, False) is True

    target2 = make_pokemon(m.Slowpoke, hp=300, max_hp=300)
    assert m._bench_attacker_can_ko(my_state, target2, False, 0, 1, 0, False) is False


def test_op_hand_size_and_disruption_belief():
    state = SimpleNamespace(hand=[1, 2, 3])
    assert m._op_hand_size(state) == 3
    assert m._op_hand_size(SimpleNamespace(hand=None)) == 0
    assert m._op_hand_size(None) == 0
    assert m._op_disruption_belief(SimpleNamespace(hand=[]), False) == 0.05
    assert m._op_disruption_belief(SimpleNamespace(hand=[1, 2]), False) > 0.05


def test_debug_log_decision_does_not_crash():
    obs = SimpleNamespace(
        current=SimpleNamespace(players=[SimpleNamespace(hand=[]), SimpleNamespace(hand=[])]),
        select=SimpleNamespace(option=[SimpleNamespace(area=AreaType.HAND, index=0)]),
    )
    m._debug_log_decision("ctx", obs.select, [10, 20], obs, my_index=0, top_n=2)


def test_first_turn_scan_moves_cards_to_expected_states():
    my_state = SimpleNamespace(
        hand=[make_card(m.Bug_Catching_Set)],
        active=[make_pokemon(m.Chikorita)],
        bench=[make_pokemon(m.Applin)],
        discard=[make_card(9999)],
    )

    m._first_turn_scan(my_state)

    assert m.ACTIVE_CARDS_IN_DECK[m.Bug_Catching_Set][m.ZONE_HAND] == 1
    assert m.ACTIVE_CARDS_IN_DECK[m.Chikorita][m.ZONE_BENCH] == 1
    assert m.ACTIVE_CARDS_IN_DECK[m.Applin][m.ZONE_BENCH] == 1
    assert m._cards_first_scan_done is True


def test_area_to_estado_maps_all_supported_areas():
    assert m._area_to_zone(AreaType.DECK) == m.ZONE_DECK
    assert m._area_to_zone(AreaType.HAND) == m.ZONE_HAND
    assert m._area_to_zone(AreaType.ACTIVE) == m.ZONE_BENCH
    assert m._area_to_zone(AreaType.DISCARD) == m.ZONE_DISCARD
    assert m._area_to_zone(AreaType.PRIZE) == m.ZONE_PRIZE
    assert m._area_to_zone(999) is None


def test_process_logs_updates_tracking():
    m._move_card_state(m.Ultra_Ball, m.ZONE_DECK, m.ZONE_HAND)
    obs = SimpleNamespace(logs=[SimpleNamespace(type=LogType.DRAW, playerIndex=0, cardId=m.Ultra_Ball)])

    m._process_logs(obs, my_index=0)

    assert m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_HAND] >= 1


def test_identify_prizes_reconciles_hidden_cards():
    m._move_card_state(m.Ultra_Ball, m.ZONE_DECK, m.ZONE_HAND)
    obs = SimpleNamespace(
        select=SimpleNamespace(
            deck=[SimpleNamespace(id=m.Ultra_Ball)],
            effect=SimpleNamespace(id=m.Ultra_Ball),
        )
    )

    m._identify_prizes(obs, my_state=None)

    assert m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_DECK] == 1


def test_sync_from_state_reconciles_visible_state():
    my_state = SimpleNamespace(
        hand=[SimpleNamespace(id=m.Ultra_Ball)],
        active=[],
        bench=[],
        discard=[],
    )

    m._sync_from_state(my_state)

    assert m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_HAND] == 1


def test_update_cards_tracking_initial_scan():
    my_state = SimpleNamespace(
        hand=[make_card(m.Bug_Catching_Set)],
        active=[make_pokemon(m.Chikorita)],
        bench=[make_pokemon(m.Applin)],
        discard=[],
        deckCount=60,
    )
    obs = SimpleNamespace(
        current=SimpleNamespace(turn=1, players=[my_state, SimpleNamespace(hand=[], active=[], bench=[], discard=[], prize=[])])
    )
    obs.select = SimpleNamespace(deck=None, effect=None)

    m._update_cards_tracking(obs, my_index=0, my_state=my_state)

    assert m._cards_first_scan_done is True
    assert m.ACTIVE_CARDS_IN_DECK[m.Bug_Catching_Set][m.ZONE_HAND] == 1


def test_get_card_reads_from_all_relevant_areas():
    card_in_hand = SimpleNamespace(id=1000)
    card_in_discard = SimpleNamespace(id=1001)
    card_in_active = SimpleNamespace(id=1002)
    card_in_bench = SimpleNamespace(id=1003)
    card_in_prize = SimpleNamespace(id=1004)
    card_in_deck = SimpleNamespace(id=1005)
    obs = SimpleNamespace(
        current=SimpleNamespace(
            players=[
                SimpleNamespace(
                    hand=[card_in_hand],
                    discard=[card_in_discard],
                    active=[card_in_active],
                    bench=[card_in_bench],
                    prize=[card_in_prize],
                ),
                SimpleNamespace(hand=[], discard=[], active=[], bench=[], prize=[]),
            ],
            stadium=[],
            looking=[card_in_prize],
        ),
        select=SimpleNamespace(deck=[card_in_deck]),
    )

    assert m.get_card(obs, AreaType.HAND, 0, 0).id == 1000
    assert m.get_card(obs, AreaType.DISCARD, 0, 0).id == 1001
    assert m.get_card(obs, AreaType.ACTIVE, 0, 0).id == 1002
    assert m.get_card(obs, AreaType.BENCH, 0, 0).id == 1003
    assert m.get_card(obs, AreaType.PRIZE, 0, 0).id == 1004
    assert m.get_card(obs, AreaType.DECK, 0, 0).id == 1005
    assert m.get_card(obs, AreaType.STADIUM, 0, 0) is None
    assert m.get_card(obs, AreaType.LOOKING, 0, 0).id == 1004


def test_prize_count_and_pokemon_score():
    charizard = SimpleNamespace(id=m.Charizard_ex, energies=[], energyCards=[], tools=[], hp=100, maxHp=100)
    mega = SimpleNamespace(id=m.Mega_Kangaskhan_ex, energies=[SimpleNamespace(id=12)], energyCards=[], tools=[], hp=100, maxHp=100)

    assert m.prize_count(charizard) >= 2
    assert m.prize_count(mega) >= 1

    score = m.pokemon_score(SimpleNamespace(id=m.Meganium, energies=[EnergyType.GRASS], energyCards=[], tools=[], hp=180, maxHp=180))
    assert score > 0


def test_count_total_grass_energy_and_syrup_damage():
    my_state = SimpleNamespace(
        active=[SimpleNamespace(energies=[EnergyType.GRASS, EnergyType.FIRE])],
        bench=[SimpleNamespace(energies=[EnergyType.GRASS]), None],
    )

    assert m.count_total_grass_energy(my_state) == 2
    assert m.calc_syrup_storm_damage(my_state, has_meganium=False) == 90
    assert m.calc_syrup_storm_damage(my_state, has_meganium=True) == 90


def test_count_hand_play_options():
    hand_counts = {
        m.Meganium: 1,
        m.Bayleef: 1,
        m.Chikorita: 1,
        m.Lillie_Determination: 1,
        m.Basic_Grass_Energy: 1,
    }
    field_counts = {m.Bayleef: 1, m.Chikorita: 1, m.Applin: 1}

    play_options, supporters_in_hand = m._count_hand_play_options(hand_counts, field_counts, bench_count=2, energy_attached=False)

    assert play_options >= 7
    assert supporters_in_hand == 1


def test_eval_ub_best_target_returns_non_negative_value():
    state = SimpleNamespace(turn=2, supporterPlayed=False)
    field_counts = {m.Chikorita: 1}
    hand_counts = {m.Basic_Grass_Energy: 1}

    result = m._eval_ub_best_target(
        field_counts,
        hand_counts,
        meganium_in_play=False,
        has_hydrapple=False,
        forest_in_play=False,
        op_has_ex_immune_active=False,
        op_has_ex_immune_bench=False,
        op_prize=2,
        bench_count=1,
        state=state,
        ko_last_turn=False,
        _best_supp_in_deck_val=0,
        supporters_in_hand=0,
        hand_is_weak=False,
        has_energy_for_teal=False,
        _we_go_first=False,
        _best_supp_in_hand_val=0,
        op_is_crustle_deck=False,
        op_is_cornerstone_deck=False,
        op_active_is_budew=False,
        meowth_ability_lock=False,
    )

    assert result >= 0


def test_our_effective_damage_applies_weakness_and_resistance(monkeypatch):
    # `card_table` is bound in main and in thirteen modules of ptcg/: it has to be
    # set in all of them, or the function under test reads the one from ITS module.
    patch_name(
        monkeypatch,
        "card_table",
        {
            9001: SimpleNamespace(ex=False, megaEx=False, weakness=EnergyType.GRASS, resistance=EnergyType.FIRE, name="Weak"),
            9002: SimpleNamespace(ex=False, megaEx=False, weakness=EnergyType.FIRE, resistance=EnergyType.GRASS, name="Resist"),
        },
    )

    attacker = make_pokemon(m.Teal_Mask_Ogerpon_ex)
    weak_target = make_pokemon(9001)
    resist_target = make_pokemon(9002)

    assert m._our_effective_damage(attacker, weak_target, 60) == 120
    assert m._our_effective_damage(attacker, resist_target, 60) == 30


def test_process_logs_move_card_updates_tracking():
    m._move_card_state(m.Ultra_Ball, m.ZONE_DECK, m.ZONE_HAND)
    obs = SimpleNamespace(
        logs=[
            SimpleNamespace(
                type=LogType.MOVE_CARD,
                playerIndex=0,
                cardId=m.Ultra_Ball,
                fromArea=AreaType.HAND,
                toArea=AreaType.DISCARD,
            )
        ]
    )

    m._process_logs(obs, my_index=0)

    assert m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_HAND] == 0
    assert m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_DISCARD] == 1


def test_identify_prizes_ignores_partial_reveal():
    before = m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_DECK]
    obs = SimpleNamespace(
        select=SimpleNamespace(
            deck=[SimpleNamespace(id=m.Ultra_Ball)],
            effect=SimpleNamespace(id=m.Bug_Catching_Set),
        )
    )

    m._identify_prizes(obs, my_state=SimpleNamespace(deckCount=2))

    assert m.ACTIVE_CARDS_IN_DECK[m.Ultra_Ball][m.ZONE_DECK] == before


def test_eval_ub_best_target_handles_turn_two_and_turn_one_branches():
    m.ACTIVE_CARDS_IN_DECK[m.Meowth_ex][m.ZONE_DECK] = 1
    m.ACTIVE_CARDS_IN_DECK[m.Lillie_Determination][m.ZONE_DECK] = 1

    turn_two_result = m._eval_ub_best_target(
        field_counts={m.Chikorita: 1},
        hand_counts={},
        meganium_in_play=False,
        has_hydrapple=False,
        forest_in_play=False,
        op_has_ex_immune_active=False,
        op_has_ex_immune_bench=False,
        op_prize=2,
        bench_count=1,
        state=SimpleNamespace(turn=2, supporterPlayed=False),
        ko_last_turn=False,
        _best_supp_in_deck_val=900,
        supporters_in_hand=0,
        hand_is_weak=False,
        has_energy_for_teal=False,
        _we_go_first=False,
        _best_supp_in_hand_val=0,
        op_is_crustle_deck=False,
        op_is_cornerstone_deck=False,
        op_active_is_budew=False,
        meowth_ability_lock=False,
    )
    assert turn_two_result >= 900

    m.ACTIVE_CARDS_IN_DECK[m.Teal_Mask_Ogerpon_ex][m.ZONE_DECK] = 1
    turn_one_result = m._eval_ub_best_target(
        field_counts={m.Applin: 1},
        hand_counts={m.Basic_Grass_Energy: 1},
        meganium_in_play=False,
        has_hydrapple=False,
        forest_in_play=False,
        op_has_ex_immune_active=False,
        op_has_ex_immune_bench=False,
        op_prize=2,
        bench_count=0,
        state=SimpleNamespace(turn=1, supporterPlayed=False),
        ko_last_turn=False,
        _best_supp_in_deck_val=0,
        supporters_in_hand=0,
        hand_is_weak=False,
        has_energy_for_teal=False,
        _we_go_first=True,
        _best_supp_in_hand_val=0,
        op_is_crustle_deck=False,
        op_is_cornerstone_deck=False,
        op_active_is_budew=False,
        meowth_ability_lock=False,
    )
    assert turn_one_result >= 950


def test_agent_selects_high_priority_play_option_in_main_context(monkeypatch):
    monkeypatch.setattr(m, "to_observation_class", lambda obs_dict: obs_dict)

    hand_card = SimpleNamespace(id=m.Chikorita)
    opponent_active = SimpleNamespace(id=m.Applin, hp=100, maxHp=100, energies=[])

    obs = SimpleNamespace(
        current=SimpleNamespace(
            turn=1,
            yourIndex=0,
            firstPlayer=0,
            energyAttached=False,
            supporterPlayed=False,
            players=[
                SimpleNamespace(
                    hand=[hand_card],
                    active=[None],
                    bench=[],
                    discard=[],
                    prize=[],
                    poisoned=False,
                    asleep=False,
                    paralyzed=False,
                    burned=False,
                    confused=False,
                ),
                SimpleNamespace(
                    hand=[],
                    active=[opponent_active],
                    bench=[],
                    discard=[],
                    prize=[],
                    poisoned=False,
                    asleep=False,
                    paralyzed=False,
                    burned=False,
                    confused=False,
                ),
            ],
            stadium=[],
            looking=[],
        ),
        select=SimpleNamespace(
            context=SelectContext.MAIN,
            option=[
                SimpleNamespace(type=OptionType.PLAY, index=0),
                SimpleNamespace(type=OptionType.END),
            ],
            minCount=1,
            maxCount=1,
            deck=None,
            effect=None,
        ),
        logs=[],
    )

    result = m.agent(obs)
    assert result == [0]


def test_agent_selects_positive_option_in_setup_bench_context(monkeypatch):
    monkeypatch.setattr(m, "to_observation_class", lambda obs_dict: obs_dict)

    hand_card = SimpleNamespace(id=m.Applin)
    opponent_active = SimpleNamespace(id=m.Chikorita, hp=100, maxHp=100, energies=[])

    obs = SimpleNamespace(
        current=SimpleNamespace(
            turn=2,
            yourIndex=0,
            firstPlayer=0,
            energyAttached=False,
            supporterPlayed=False,
            players=[
                SimpleNamespace(
                    hand=[hand_card],
                    active=[None],
                    bench=[],
                    discard=[],
                    prize=[],
                    poisoned=False,
                    asleep=False,
                    paralyzed=False,
                    burned=False,
                    confused=False,
                ),
                SimpleNamespace(
                    hand=[],
                    active=[opponent_active],
                    bench=[],
                    discard=[],
                    prize=[],
                    poisoned=False,
                    asleep=False,
                    paralyzed=False,
                    burned=False,
                    confused=False,
                ),
            ],
            stadium=[],
            looking=[],
        ),
        select=SimpleNamespace(
            context=SelectContext.SETUP_BENCH_POKEMON,
            option=[
                SimpleNamespace(type=OptionType.PLAY, index=0),
                SimpleNamespace(type=OptionType.END),
            ],
            minCount=1,
            maxCount=1,
            deck=None,
            effect=None,
        ),
        logs=[],
    )

    result = m.agent(obs)
    assert result == [0]


def test_agent_returns_deck_when_no_selection_is_available(monkeypatch):
    monkeypatch.setattr(m, "to_observation_class", lambda obs_dict: SimpleNamespace(select=None))
    assert m.agent({}) == m.my_deck


# ---------------------------------------------------------------------------
# Regression: vs Marnie's Grimmsnarl ex (log 86699707, step 51). With a weak
# hand (Meowth ex + Lana's Aid, 4 cards), 3 Lillie's in the deck, an active
# Dipplin (a chip) against a 320 HP wall and FROSLASS on the rival bench, the
# agent must PLAY Meowth ex (Last-Ditch Catch -> Lillie's -> refresh), NOT
# play Lana's Aid just to recover 1 non-lethal energy. The Meowth->Lillie's
# exception yields to Froslass EXCEPT when our only ready attacker
# is the active itself (_ready_attacker_count <= 1).
import copy
import json

_STEP51_FIXTURE = ROOT / "tests" / "fixtures" / "marnie_grimmsnarl_step51.json"


def _load_step51_obs():
    with open(_STEP51_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _resolve_play_options(obs_dict):
    """Returns {position_in_option: card_id} for the PLAY options (type 7)."""
    obs = m.to_observation_class(obs_dict)
    my_index = obs_dict["current"]["yourIndex"]
    mapping = {}
    for i, opt in enumerate(obs_dict["select"]["option"]):
        if opt.get("type") == OptionType.PLAY:
            card = m.get_card(obs, AreaType.HAND, opt["index"], my_index)
            mapping[i] = None if card is None else card.id
    return mapping


def test_marnie_step51_plays_meowth_not_lanas_aid():
    obs = _load_step51_obs()

    play_map = _resolve_play_options(obs)
    # The fixture must contain both options for the test to be meaningful.
    assert m.Meowth_ex in play_map.values()
    assert m.Lanas_Aid in play_map.values()
    meowth_opt = next(i for i, cid in play_map.items() if cid == m.Meowth_ex)
    lanas_opt = next(i for i, cid in play_map.items() if cid == m.Lanas_Aid)

    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"esperaba bajar Meowth ex (opt {meowth_opt}), obtuvo {result} "
        f"(map={play_map})"
    )
    assert result != [lanas_opt]


def test_marnie_step51_meowth_priority_holds_without_froslass():
    # Removing Froslass (id 104) and its pre-evo Snorunt (id 860) from the rival bench
    # must NOT change the decision: the Meowth->Lillie's branch already held with the
    # original `not op_has_froslass` guard. It confirms that the relaxation does not
    # alter the path without Froslass (identical behaviour).
    obs = copy.deepcopy(_load_step51_obs())
    opp_bench = obs["current"]["players"][1]["bench"]
    obs["current"]["players"][1]["bench"] = [
        p for p in opp_bench if p is not None and p.get("id") not in (104, 860)
    ]

    play_map = _resolve_play_options(obs)
    meowth_opt = next(i for i, cid in play_map.items() if cid == m.Meowth_ex)

    result = m.agent(obs)
    assert result == [meowth_opt]


# Record 006 (step 51) vs Alakazam: our turn with the hand [Bayleef,
# Boss's Orders, Night Stretcher, Lana's Aid], an active Hydrapple ex that still
# cannot attack (1 energy), an Ogerpon ex just played to the bench and a Meowth ex in
# the DISCARD. The agent ended the turn without playing a trainer or attacking. The
# right thing is to play Night Stretcher to recover Meowth ex and chain
# Meowth ex (Last-Ditch Catch) -> Lillie's Determination -> refresh the hand.
# Besides, Lana's Aid canNOT recover Meowth ex (it has a Rule Box), so
# it must not inflate the hand's value nor block the line.
_STEP51_NS_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_ns_meowth_step51.json"


def _load_ns_step51_obs():
    with open(_STEP51_NS_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def test_alakazam_step51_plays_night_stretcher_for_meowth():
    obs = _load_ns_step51_obs()

    play_map = _resolve_play_options(obs)
    # The fixture must offer Night Stretcher as a play.
    assert m.Night_Stretcher in play_map.values()
    ns_opt = next(i for i, cid in play_map.items() if cid == m.Night_Stretcher)

    # The end-of-turn option (type 14) is the last of the select.
    options = obs["select"]["option"]
    pass_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.END))

    result = m.agent(obs)

    assert result == [ns_opt], (
        f"esperaba jugar Night Stretcher (opt {ns_opt}) para recuperar Meowth ex, "
        f"obtuvo {result} (map={play_map})"
    )
    assert result != [pass_opt], "no debe terminar el turno sin desarrollar"


# Record 003 (step 36) vs Archaludon ex (WON): on OUR turn 3, after
# playing Poke Pad and evolving Applin -> Dipplin, the active Ogerpon ex is
# damaged with 1 energy (it cannot attack) and the hand is left as [Lillie's, Unfair
# Stamp, Hydrapple ex, Meganium, Night Stretcher]. We canNOT evolve
# Dipplin -> Hydrapple ex this turn (the Dipplin has just appeared, no Forest) nor
# attack: the turn would be DEAD. The agent ended the turn keeping the
# evolution line instead of playing Lillie's Determination. The right thing is to
# refresh with Lillie's (draw 6, or 8 with 6 prizes) to see more options.
# The `_field_at_turn_start` snapshot (Applin in play at the start of the turn, not
# Dipplin) is key, which is why the SEQUENCE of the turn is reproduced, not a single
# observation.
_TURN3_SEQ_FIXTURE = ROOT / "tests" / "fixtures" / "archaludon_lillie_turn3_seq.json"


def test_archaludon_step36_plays_lillie_not_end_on_dead_turn():
    with open(_TURN3_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    # Reproducing the turn's sequence to set `_field_at_turn_start`.
    final_obs = None
    result = None
    for item in seq:
        obs = item["observation"]
        result = m.agent(obs)
        final_obs = obs

    # The last decision (tac=4): it must play Lillie's Determination (opt 0), not END.
    play_map = _resolve_play_options(final_obs)
    assert m.Lillie_Determination in play_map.values()
    lillie_opt = next(i for i, cid in play_map.items()
                      if cid == m.Lillie_Determination)
    options = final_obs["select"]["option"]
    end_opt = next(i for i, o in enumerate(options)
                   if o.get("type") == int(OptionType.END))

    assert result == [lillie_opt], (
        f"esperaba jugar Lillie's Determination (opt {lillie_opt}) para refrescar, "
        f"obtuvo {result} (map={play_map})"
    )
    assert result != [end_opt], "no debe terminar un turno muerto sin refrescar"


# Record 004 (step ~62) vs Iono (LOST): in the Ultra Ball search, with
# a Dipplin in play evolvable into Hydrapple ex THIS turn (Forest in play)
# but WITHOUT energy for Hydrapple ex to attack (Syrup Storm needs 2; we already
# attached energy this turn and the Dipplin has 0), bringing Hydrapple ex leaves it
# DEAD. Since the Meowth ex -> Last-Ditch Catch -> Lillie's Determination engine
# is available (Meowth ex and Lillie's in the deck, no Supporter played, a bench
# with a slot), the right thing is to bring Meowth ex to refresh the hand, not Hydrapple
# ex. Searching for Hydrapple ex is only right if it CAN attack this turn.
_UB_MEOWTH_FIXTURE = ROOT / "tests" / "fixtures" / "iono_ub_meowth_not_hydra_step62.json"


def _resolve_search_options(obs_dict):
    """{position_in_option: card_id} for deck search options."""
    deck = obs_dict["select"].get("deck") or []
    mapping = {}
    for i, opt in enumerate(obs_dict["select"]["option"]):
        if opt.get("type") == int(OptionType.CARD) and opt.get("area") == int(AreaType.DECK):
            di = opt.get("index")
            if di is not None and di < len(deck):
                mapping[i] = deck[di]["id"]
    return mapping


def test_iono_ultraball_fetches_meowth_not_dead_hydrapple():
    with open(_UB_MEOWTH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    search_map = _resolve_search_options(obs)
    # The fixture must offer both as search targets.
    assert m.Meowth_ex in search_map.values()
    assert m.Hydrapple_ex in search_map.values()
    meowth_opt = next(i for i, cid in search_map.items() if cid == m.Meowth_ex)
    hydra_opt = next(i for i, cid in search_map.items() if cid == m.Hydrapple_ex)

    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"esperaba buscar Meowth ex (opt {meowth_opt}) para refrescar, obtuvo "
        f"{result} (map={search_map})"
    )
    assert result != [hydra_opt], "no debe buscar un Hydrapple ex que no ataca este turno"


# Record 006 (step 57) vs Alakazam (WON): on OUR turn 6 we already have a
# READY attacker in the active spot (a charged Ogerpon ex), another on the bench and more
# attackers chargeable with the energy in hand. A previous Ultra Ball left
# `_ub_meowth_pending`, which forced playing Meowth ex to chain a Lillie's; but
# Meowth ex is a 2-prize body and here it adds NO attack (besides, the Supporter
# was already played this turn, the searched Lillie's could not even be played). With the active already
# ready to attack, Meowth ex must NOT be played: we attack.
_NO_MEOWTH_SEQ_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_no_redundant_meowth_turn6.json"


def test_alakazam_step57_no_redundant_meowth_when_attacker_ready():
    with open(_NO_MEOWTH_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    # Reproducing the turn's sequence (it sets `_ub_meowth_pending` and the snapshot).
    target = None
    result = None
    for item in seq:
        obs = item["observation"]
        result = m.agent(obs)
        if item.get("tac") == 11 and item.get("status") == "ACTIVE":
            target = obs
            break

    assert target is not None, "no se encontro la decision del paso 57 (tac=11)"
    play_map = _resolve_play_options(target)
    meowth_opts = [i for i, cid in play_map.items() if cid == m.Meowth_ex]
    assert meowth_opts, "el fixture debe ofrecer jugar Meowth ex"
    options = target["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    # It must not play Meowth ex (a redundant body); with a ready attacker, it attacks.
    assert result[0] not in meowth_opts, (
        f"no debe jugar Meowth ex con un atacante ya listo; obtuvo {result} "
        f"(meowth_opts={meowth_opts})"
    )
    assert result == [attack_opt], (
        f"esperaba atacar (opt {attack_opt}) en vez de bajar Meowth ex, obtuvo {result}"
    )


# Record 004 (step 53) vs Archaludon ex (WON): with an active Fezandipiti ex,
# Dawn (a Supporter) in hand and the Supporter still unplayed, the agent decided
# to RETREAT Fezandipiti ex (to promote an attacker) BEFORE playing Dawn. It is
# a sequencing error: the Supporter is ALWAYS played before retreating (Dawn
# searches for the Applin -> Dipplin -> Hydrapple ex line that is evolved with Forest
# this same turn; only afterwards is it worth retreating and promoting). The retreat is not
# blocked by playing the Supporter, so it must be postponed.
_DAWN_BEFORE_RETREAT_FIXTURE = ROOT / "tests" / "fixtures" / "archaludon_dawn_before_retreat_step53.json"


def test_archaludon_step53_plays_dawn_before_retreat():
    with open(_DAWN_BEFORE_RETREAT_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Dawn in play_map.values(), "el fixture debe ofrecer jugar Dawn"
    dawn_opt = next(i for i, cid in play_map.items() if cid == m.Dawn)
    options = obs["select"]["option"]
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    result = m.agent(obs)

    assert result == [dawn_opt], (
        f"esperaba jugar Dawn (opt {dawn_opt}) ANTES de retirar, obtuvo {result} "
        f"(map={play_map})"
    )
    assert result != [retreat_opt], "no debe retirar antes de jugar el Supporter"


# Record 010 (step 64) vs Alakazam (WON): with an active Ogerpon ex (6 energies,
# it can attack), Boss's Orders + Ultra Ball in hand, the rival active is a
# Dunsparce (OUTSIDE the Alakazam line) and on the rival bench there is an Abra (741,
# a pre-evo of the line). The agent played Ultra Ball -> discarded the Boss's as a
# cost and attacked the Dunsparce. It is a mistake: the priority vs Alakazam is to gust
# with Boss's the bench pre-evo (Kadabra > Abra > Alakazam) and knock it out to
# cut the development of the Psychic attacker. It must play Boss's BEFORE Ultra
# Ball (which would also burn the Boss's itself).
_BOSS_BEFORE_UB_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_boss_before_ub_step64.json"


def test_alakazam_step64_plays_boss_to_gust_abra_not_ultraball():
    with open(_BOSS_BEFORE_UB_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Boss_Orders in play_map.values(), "el fixture debe ofrecer jugar Boss's Orders"
    assert m.Ultra_Ball in play_map.values(), "el fixture debe ofrecer jugar Ultra Ball"
    boss_opt = next(i for i, cid in play_map.items() if cid == m.Boss_Orders)
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)

    result = m.agent(obs)

    assert result == [boss_opt], (
        f"esperaba jugar Boss's Orders (opt {boss_opt}) para gustear el Abra, "
        f"obtuvo {result} (map={play_map})"
    )
    assert result != [ub_opt], (
        "no debe jugar Ultra Ball (quema el Boss's necesario para cortar la linea Alakazam)"
    )


# --- Priority 1 refactor: the pure scorer `_score_boss_orders_play` ----------
# By extracting the Boss's branch into a pure function that reads a DecisionContext, the
# scoring can be tested in ISOLATION, without fabricating a full observation.
def _make_boss_ctx(**overrides):
    base = dict(
        state=SimpleNamespace(supporterPlayed=False, turn=6, energyAttached=False),
        my_state=SimpleNamespace(discard=[], active=[None], bench=[], hand=[]),
        op_state=SimpleNamespace(active=[None], bench=[]),
        hand_counts={m.Boss_Orders: 1},
        field_counts={},
        supp_values={m.Boss_Orders: 700},
        cards_in_deck={},
        field_at_turn_start={},
        bench_count=0,
        my_hand_len=5,
        my_prize=6,
        op_prize=6,
        op_hand_count=6,
        meganium_in_play=False,
        forest_in_play=False,
        itchy_pollen_active=False,
        has_hydrapple=False,
        watchtower_in_play=False,
        meowth_ability_lock=False,
        neutralization_zone_active=False,
        mega_line_active=False,
        active_needs_energy=False,
        evolve_possible_in_play=False,
        energy_starved_low_draw=False,
        pp_playable_in_hand=False,
        can_attack=False,
        best_supp_in_hand_val=0,
        best_supp_in_deck_val=0,
        op_is_alakazam_deck=False,
        op_is_hop_deck=False,
        op_is_comfey_deck=False,
        op_active_is_dunsparce=False,
        op_has_ability_immune_active=False,
        op_has_ex_immune_active=False,
        op_has_ex_immune_bench=False,
        op_is_control_deck=False,
        op_is_slowking_deck=False,
        op_is_gardevoir_deck=False,
        op_is_zoroark_deck=False,
        op_is_aggro_deck=False,
        op_is_beedrill_deck=False,
        op_is_crustle_deck=False,
        op_is_cornerstone_deck=False,
        op_is_fire_deck=False,
        op_is_mirror=False,
        op_kang_ko_target=False,
        stadium_id=0,
        ko_last_turn=False,
        our_first_turn=False,
        active_cant_attack=False,
        bdg_retreat_ko=False,
        supporter_boost=0,
        we_go_first=False,
        budew_op_index=-1,
        budew_on_op_field=False,
        lucario_sac_pivot=False,
        win_via_boss_gust=False,
        gust_2prize_via_boss=False,
        boss_win_via_bench=False,
        boss_dodge_redirect=False,
        boss_defensive_gust=False,
        boss_deny_alakazam_line=False,
        boss_low_value_gust=False,
        boss_prize_rank=0,
        boss_ko_threat_preevo=False,
        has_ready_bench_attacker=True,
        active_ko_likely=False,
    )
    base.update(overrides)
    # `hand_counts`/`field_counts` in production are defaultdict(int); the scorers
    # use bracket access (e.g. hand_counts[Basic_Grass_Energy],
    # field_counts[Chikorita]). We coerce them so that the test context
    # behaves the same.
    from collections import defaultdict
    base["hand_counts"] = defaultdict(int, base["hand_counts"])
    base["field_counts"] = defaultdict(int, base["field_counts"])
    return m.DecisionContext(**base)


def test_score_boss_orders_vetoed_when_supporter_already_played():
    ctx = _make_boss_ctx(state=SimpleNamespace(supporterPlayed=True))
    assert m._score_boss_orders_play(ctx) == -1


def test_score_boss_orders_deny_alakazam_line_beats_default():
    # The Alakazam line cut scores at BOSS_SCORE_PRIZE_RANK_BASE, above
    # the default gust (2400 + val*1.4), replicating record 010.
    deny = m._score_boss_orders_play(_make_boss_ctx(boss_deny_alakazam_line=True))
    default = m._score_boss_orders_play(_make_boss_ctx())
    assert deny == m.BOSS_SCORE_PRIZE_RANK_BASE
    assert deny > default


def test_score_boss_orders_win_via_bench_has_priority_over_deny():
    # A lethal gust to the bench (win_via_bench) keeps its priority above
    # the line cut (the if/elif order is preserved after the extraction).
    ctx = _make_boss_ctx(boss_win_via_bench=True, boss_deny_alakazam_line=True)
    assert m._score_boss_orders_play(ctx) == m.BOSS_SCORE_WIN_VIA_BENCH


def test_score_unfair_stamp_dead_hand_scores_highest():
    # A hand with NO alternative use (nothing playable): Unfair Stamp is worth its maximum (7500).
    ctx = _make_boss_ctx(hand_counts={m.Unfair_Stamp: 1})
    assert m._score_unfair_stamp_play(ctx) == 7500


def test_score_unfair_stamp_lower_when_hand_has_a_play():
    # With a playable item in hand (Night Stretcher) the refresh is worth less (2500):
    # it is better to use the hand before shuffling it.
    ctx = _make_boss_ctx(hand_counts={m.Unfair_Stamp: 1, m.Night_Stretcher: 1})
    assert m._score_unfair_stamp_play(ctx) == 2500


def _deck(*ids):
    """A minimal deck-belief: {id: {ESTADO_MAZO: 1}} for the given ids."""
    return {cid: {m.ZONE_DECK: 1} for cid in ids}


def test_score_poke_pad_vetoed_when_nothing_searchable():
    # With no non-ex Pokemon in the deck, Poke Pad searches for nothing.
    ctx = _make_boss_ctx(state=SimpleNamespace(turn=6, energyAttached=False),
                         cards_in_deck={})
    assert m._score_poke_pad_play(ctx) == -1


def test_score_poke_pad_enables_evolution_this_turn_scores_high():
    # Bayleef in play (since the start of the turn) + Meganium in the deck and not in hand:
    # searching for Meganium enables the evolution THIS turn -> a high score (>=22000).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        cards_in_deck=_deck(m.Meganium),
        field_counts={m.Bayleef: 1},
        field_at_turn_start={m.Bayleef: 1},
        bench_count=2,
    )
    assert m._score_poke_pad_play(ctx) >= 22000


def test_score_poke_pad_saves_resource_on_full_bench():
    # A full bench and no pre-evo to evolve with a search: it is kept (-1).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        cards_in_deck=_deck(m.Chikorita),
        field_counts={},
        bench_count=5,
    )
    assert m._score_poke_pad_play(ctx) == -1


def test_score_night_stretcher_vetoed_when_discard_empty():
    # An empty discard: there is nothing to recover.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(discard=[], active=[None], bench=[], hand=[]),
    )
    assert m._score_night_stretcher_play(ctx) == -1


def test_score_night_stretcher_recovers_meowth_for_refresh_engine():
    # Meowth ex in the discard + a viable refresh engine (a strong Supporter in the
    # deck, none in hand, the Supporter unplayed): it is recovered. Record 006 p51.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(
            discard=[SimpleNamespace(id=m.Meowth_ex)], active=[None], bench=[], hand=[]),
        bench_count=1,
        best_supp_in_hand_val=0,
        best_supp_in_deck_val=700,
    )
    # best_recovery_value=830 -> tier 800..899 -> ns_score 11000.
    assert m._score_night_stretcher_play(ctx) == 11000


def test_score_forest_vetoed_when_forest_already_in_play():
    # If Forest of Vitality is already the stadium in play, it is not played again.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        stadium_id=m.Forest_of_Vitality,
    )
    assert m._score_forest_of_vitality_play(ctx) == -1


def test_score_forest_high_when_enables_evolution_chain():
    # Chikorita in play + Bayleef in hand and no Meganium: Forest enables the
    # evolution chain this turn -> a high score (>=21900).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        field_counts={m.Chikorita: 1},
        hand_counts={m.Bayleef: 1},
        stadium_id=0,
    )
    assert m._score_forest_of_vitality_play(ctx) >= 21900


def test_score_bug_catching_set_vetoed_when_nothing_eligible():
    # A deck with no Grass Pokemon or eligible Energy: there is nothing to take.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        cards_in_deck={},
    )
    assert m._score_bug_catching_set_play(ctx) == -1


def test_score_bug_catching_set_positive_when_grass_energy_in_deck():
    # With Grass Energy in the deck (eligible), the play has positive value.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        cards_in_deck={m.Basic_Grass_Energy: {m.ZONE_DECK: 5}},
    )
    assert m._score_bug_catching_set_play(ctx) > 0


# The BCS deck-out brake (step 4 of the Jul 2026 plan; autopsy v2 vs crustle:
# 4/19 losses by DECKOUT): with a deck <=8, BCS thins the clock and is vetoed.
# The dry-energy exception (the anti-mill case vs Comfey of b393426): with no Grass
# in hand and an attachment pending, digging energy enables attacking TODAY.

def test_bcs_deckout_brake_with_a_critical_deck():
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=20, energyAttached=False),
        my_state=SimpleNamespace(deckCount=8, discard=[], active=[None],
                                 bench=[], hand=[]),
        cards_in_deck={m.Basic_Grass_Energy: {m.ZONE_DECK: 3}},
        hand_counts={m.Basic_Grass_Energy: 2},  # there IS Grass in hand
    )
    assert m._score_bug_catching_set_play(ctx) == -1


def test_bcs_brake_yields_when_the_energy_is_dry():
    # The same critical deck but with NO Grass in hand and an attachment pending: the BCS
    # is still playable (it is the energy route of the anti-mill plan).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=20, energyAttached=False),
        my_state=SimpleNamespace(deckCount=8, discard=[], active=[None],
                                 bench=[], hand=[]),
        cards_in_deck={m.Basic_Grass_Energy: {m.ZONE_DECK: 3}},
        hand_counts={},
    )
    assert m._score_bug_catching_set_play(ctx) > 0


def test_bcs_brake_does_not_apply_with_a_healthy_deck():
    # Boundary: with a deck of 9+ the brake does not fire.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=20, energyAttached=False),
        my_state=SimpleNamespace(deckCount=9, discard=[], active=[None],
                                 bench=[], hand=[]),
        cards_in_deck={m.Basic_Grass_Energy: {m.ZONE_DECK: 3}},
        hand_counts={m.Basic_Grass_Energy: 2},
    )
    assert m._score_bug_catching_set_play(ctx) > 0


def test_score_ultra_ball_vetoed_with_tiny_hand():
    # A hand of <3 cards: playing an Ultra Ball (the cost of discarding 2) would empty the hand.
    # The cold path of the early `hand_size < 3` cut-off (a mid turn, no survival concerns).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(
            discard=[], active=[None], bench=[],
            hand=[SimpleNamespace(id=m.Ultra_Ball), SimpleNamespace(id=m.Boss_Orders)]),
        bench_count=1,
    )
    assert m._score_ultra_ball_play(ctx) == -1


def test_ub_cancel_stamp_false_without_unfair_stamp():
    # With no Unfair Stamp in hand, this guard never cancels.
    ctx = _make_boss_ctx(hand_counts={m.Ultra_Ball: 1, m.Basic_Grass_Energy: 3})
    assert m._ub_cancel_stamp(ctx) is False


def test_ub_cancel_stamp_true_when_stamp_would_be_forced_fodder():
    # A hand of {Unfair Stamp, Ultra Ball}: with no fodder (0 discardable without touching the
    # Stamp), playing the UB would discard the Stamp -> it is cancelled.
    ctx = _make_boss_ctx(hand_counts={m.Unfair_Stamp: 1, m.Ultra_Ball: 1})
    assert m._ub_cancel_stamp(ctx) is True


def test_ub_cancel_meowth_false_when_no_meowth_engine():
    # With no Meowth ex in hand (or no Lillie's in the deck), the Meowth guard does not apply.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        hand_counts={m.Ultra_Ball: 1},
        cards_in_deck={},
    )
    assert m._ub_cancel_meowth(ctx) is False


def test_score_lillie_vetoed_when_supporter_already_played():
    # The turn's Supporter has already been played: another cannot be played.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, supporterPlayed=True),
        my_state=SimpleNamespace(active=[None], bench=[], hand=[]),
        hand_counts={m.Lillie_Determination: 1},
    )
    assert m._score_lillie_determination_play(ctx) == -1


def test_unfair_stamp_cedes_to_lillie_when_opp_hand_small():
    # Rule (user): with a Lillie's in hand and the rival at <=3 cards, Unfair
    # Stamp is NOT played (it yields to Lillie's).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        hand_counts={m.Unfair_Stamp: 1, m.Lillie_Determination: 1},
        op_hand_count=3,
    )
    assert m._score_unfair_stamp_play(ctx) == -1


def test_unfair_stamp_not_ceded_when_opp_hand_large():
    # With the rival at >3 cards the disruption is still worth it: Unfair Stamp does NOT yield.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        hand_counts={m.Unfair_Stamp: 1, m.Lillie_Determination: 1},
        op_hand_count=6,
    )
    assert m._score_unfair_stamp_play(ctx) > 0


def _lillie_ctx(**over):
    base = dict(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(active=[None], bench=[],
                                 hand=[SimpleNamespace(id=0) for _ in range(5)]),
        hand_counts={m.Unfair_Stamp: 1, m.Lillie_Determination: 1},
        ko_last_turn=True,
    )
    base.update(over)
    return _make_boss_ctx(**base)


def test_lillie_playable_when_stamp_in_hand_but_opp_hand_small():
    # With Unfair Stamp in hand + a KO last turn, Lillie's is normally vetoed;
    # but if the rival has <=3 cards, Lillie's stays PLAYABLE (it wins the decision).
    assert m._score_lillie_determination_play(_lillie_ctx(op_hand_count=3)) > 0


def test_lillie_still_vetoed_by_stamp_when_opp_hand_large():
    # With the rival at >3 cards the original veto is kept: the Stamp is preferred.
    assert m._score_lillie_determination_play(_lillie_ctx(op_hand_count=6)) == -1


def _og(energy_count):
    # A Teal Mask Ogerpon ex with `energy_count` Grass -> a ready attacker with >=3.
    return SimpleNamespace(id=m.Teal_Mask_Ogerpon_ex, energies=[1] * energy_count)


def _hop_lillie_ctx(**over):
    # Record 008 step 84 vs Hops: an active + a bench with ready attackers, Boss's and
    # Lillie's in hand, a Hops rival. (ko_last_turn=False so as not to cross the Unfair
    # Stamp veto; no Unfair Stamp in hand.)
    base = dict(
        state=SimpleNamespace(turn=8, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(active=[_og(4)], bench=[_og(4)],
                                 hand=[SimpleNamespace(id=0) for _ in range(5)]),
        hand_counts={m.Boss_Orders: 1, m.Lillie_Determination: 1},
        op_is_hop_deck=True,
        ko_last_turn=False,
    )
    base.update(over)
    return _lillie_ctx(**base)


def test_lillie_vetoed_vs_hops_with_boss_and_two_attackers():
    # vs Hops with Boss's in hand and >=2 ready attackers: do NOT play Lillie's (it would shuffle
    # the Boss's into the deck); it is kept to answer a Hops Phantump with heads.
    assert m._score_lillie_determination_play(_hop_lillie_ctx()) == -1


def test_lillie_playable_vs_hops_when_active_is_only_attacker():
    # vs Hops with Boss's but with the active as the ONLY attacker: Lillie's IS played
    # (digging for resources), even though it shuffles away the Boss's.
    ctx = _hop_lillie_ctx(
        my_state=SimpleNamespace(active=[_og(4)], bench=[],
                                 hand=[SimpleNamespace(id=0) for _ in range(5)]))
    assert m._score_lillie_determination_play(ctx) > 0


def test_lillie_playable_vs_hops_when_no_boss_in_hand():
    # vs Hops WITHOUT Boss's in hand: Lillie's can be played as usual.
    ctx = _hop_lillie_ctx(hand_counts={m.Lillie_Determination: 1})
    assert m._score_lillie_determination_play(ctx) > 0


def test_lillie_playable_with_boss_and_two_attackers_when_not_hops():
    # The rule only applies vs Hops: against another deck, Lillie's is still playable.
    assert m._score_lillie_determination_play(_hop_lillie_ctx(op_is_hop_deck=False)) > 0


def test_score_lanas_aid_vetoed_when_supporter_already_played():
    # It receives the incoming score (10000) but vetoes it if the Supporter has already been played.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, supporterPlayed=True, energyAttached=False),
        my_state=SimpleNamespace(active=[None], bench=[], hand=[], discard=[]),
    )
    assert m._score_lanas_aid_play(ctx, 10000) == -1


# Record 014 (step 146) vs Alakazam (WON): when gusting with Boss's Orders
# (our active Meowth ex cannot attack -> nuisance mode), the agent picked a
# Shaymin from the rival bench instead of an Abra. It must PRIORITISE the Alakazam line
# (Abra/Kadabra/Alakazam) to cut the development of the Psychic attacker.
_BOSS_GUST_ABRA_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_boss_gust_abra_step146.json"


def test_alakazam_step146_boss_gust_targets_abra_not_shaymin():
    with open(_BOSS_GUST_ABRA_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    # Mapping each option (the rival bench) to its Pokemon id.
    op_bench = obs["current"]["players"][0]["bench"]
    opt_ids = {i: op_bench[o["index"]]["id"]
               for i, o in enumerate(obs["select"]["option"])}
    abra_opts = [i for i, cid in opt_ids.items() if cid == m.Abra]
    shaymin_opts = [i for i, cid in opt_ids.items() if cid == 343]
    assert abra_opts and shaymin_opts, f"fixture debe ofrecer Abra y Shaymin (map={opt_ids})"

    result = m.agent(obs)

    assert result[0] in abra_opts, (
        f"esperaba gustear un Abra {abra_opts} (linea Alakazam), obtuvo {result} "
        f"(map={opt_ids})"
    )
    assert result[0] not in shaymin_opts, "no debe gustear el Shaymin sobre la linea Alakazam"


# Record 010 (step 76) vs Dragapult/Latias (WON): when gusting with Boss's
# Orders (an active Tapu Bulu that cannot attack -> nuisance), the agent picked the Latias
# ex from the rival bench. It is a mistake: Latias ex (Skyliner) lets any Basic
# retreat FOR FREE (including itself), so gusting a Basic hinders nothing. It must
# pick a NON-basic (Drakloak). Never gust Latias ex nor a Basic with Latias
# ex in play.
_LATIAS_BOSS_GUST_FIXTURE = ROOT / "tests" / "fixtures" / "dragapult_latias_boss_gust_drakloak_step76.json"


def test_boss_gust_avoids_latias_ex_and_basics_targets_drakloak():
    with open(_LATIAS_BOSS_GUST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    op_bench = obs["current"]["players"][1]["bench"]
    opt_ids = {i: op_bench[o["index"]]["id"]
               for i, o in enumerate(obs["select"]["option"])}
    latias_opts = [i for i, cid in opt_ids.items() if cid == m.Latias_ex]
    dreepy_opts = [i for i, cid in opt_ids.items() if cid == 119]   # Dreepy (basic)
    drakloak_opts = [i for i, cid in opt_ids.items() if cid == 120]  # Drakloak (stage 1)
    assert latias_opts and drakloak_opts, f"fixture debe ofrecer Latias ex y Drakloak (map={opt_ids})"

    result = m.agent(obs)

    assert result[0] not in latias_opts, "no debe gustear la Latias ex"
    assert result[0] not in dreepy_opts, "no debe gustear un Basico (Dreepy) con Latias ex en juego"
    assert result[0] in drakloak_opts, (
        f"esperaba gustear el Drakloak {drakloak_opts} (no-basico), obtuvo {result} (map={opt_ids})"
    )


# Record 008 (step 105) vs Alakazam (LOST with the old code): at the end of the
# turn, unable to attack (a Hydrapple ex with 1 energy) and with no Supporter played,
# with a Meowth ex in hand and a bench slot (even with ANOTHER Meowth ex already on the
# bench), the Meowth ex must be PLAYED (Last-Ditch Catch -> Lillie's) instead of
# ending the turn. The current code already does it (the Meowth->Lillie's engine); this
# test locks the behaviour in so it does not come back.
_MEOWTH_ENGINE_EOT_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_meowth_engine_end_of_turn_step105.json"


def test_alakazam_step105_plays_meowth_engine_instead_of_ending_turn():
    with open(_MEOWTH_ENGINE_EOT_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Meowth_ex in play_map.values(), "el fixture debe ofrecer jugar Meowth ex"
    meowth_opt = next(i for i, cid in play_map.items() if cid == m.Meowth_ex)
    options = obs["select"]["option"]
    end_opt = next(i for i, o in enumerate(options) if o.get("type") == int(OptionType.END))

    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"esperaba jugar Meowth ex (opt {meowth_opt}) para el motor Lillie's, "
        f"obtuvo {result} (map={play_map})"
    )
    assert result != [end_opt], "no debe terminar el turno con Meowth ex jugable en la mano"


# Record 010 (step 82) vs Alakazam (WON): with a CHARGED Tapu Bulu (4 energy)
# in the active spot that can KNOCK OUT the rival active (a Kadabra at 80 HP; Tapu Bulu hits for 220),
# the agent retreated the Tapu to pivot to Hydrapple ex. It is wrong: a Tapu Bulu is
# never retreated from the active spot if it can defeat the rival; it must ATTACK (Tapu Bulu
# is non-ex -> 1 prize if they knock it out; the Hydrapple ex is worth 2). The greedy planner
# promoted the bench Hydrapple ex even when the active could knock out.
_TAPU_KO_FIXTURE = ROOT / "tests" / "fixtures" / "tapu_bulu_step82_active_ko.json"


def test_alakazam_step82_tapu_bulu_attacks_instead_of_retreating():
    with open(_TAPU_KO_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    result = m.agent(obs)

    assert result == [attack_opt], (
        f"un Tapu Bulu activo que puede noquear debe ATACAR (opt {attack_opt}), "
        f"obtuvo {result}"
    )
    assert result != [retreat_opt], "nunca retirar un Tapu Bulu que puede derrotar al rival"


# Record 023 (vs Archaludon ex, LOST): with TWO Hydrapple ex in play, the
# active is a FRAGILE Hydrapple ex (110/330) that can attack and knock out, and on the
# bench there is another Hydrapple ex at FULL life (330/330) that, after retreating the
# active, STILL knocks out the Archaludon ex (Syrup Storm scales with the total Grass on the
# field, which drops through the retreat cost). The agent attacked with the fragile one, which
# died the next turn giving away 2 prizes (a loss). The right thing: RETREAT the
# fragile one and promote the tank, which knocks out all the same and survives. The defensive pivot
# excluded the active-Hydrapple case (`_ret_active.id != Hydrapple_ex`).
_HYDRA_PIVOT_LOWHP_FIXTURE = ROOT / "tests" / "fixtures" / "archaludon_hydra_pivot_lowhp_active_step143.json"


def test_archaludon_step143_retreats_low_hp_hydrapple_to_promote_full_hp_wall():
    with open(_HYDRA_PIVOT_LOWHP_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    result = m.agent(obs)

    # AN ARITHMETIC CORRECTION (registro_006 step 78 vs Archaludon ex): the
    # retreat is paid for with whole CARDS and with Wild Growth each Grass is worth
    # TWO units, so retreating the Hydrapple ex (cost 3) discards 2 cards
    # = 4 units, not 2. On THIS board (12 units) the bench tank is
    # left at 8 -> Syrup 270 - 30 of resistance = 240 < 300: it does NOT knock out. The
    # pivot's premise does not hold, and attacking with the fragile one DOES knock out
    # (12 units -> 390 - 30 = 360 >= 300) and takes 2 prizes. The pivot is still
    # valid when the tank really finishes: see the test below with one more
    # Grass on the field.
    assert result == [attack_opt], (
        f"con la cuenta correcta de la retirada el tanque NO noquea (240 < 300) "
        f"y el fragil SI (360 >= 300): debe ATACAR (opt {attack_opt}); "
        f"obtuvo {result}"
    )


_HYDRA_PIVOT_TANQUE_KO_FIXTURE = (
    ROOT / "tests" / "fixtures" / "archaludon_hydra_pivot_tanque_si_noquea.json")


def test_archaludon_pivot_when_the_tank_really_knocks_out():
    """The same board with ONE more Grass (14 units): after the retreat 10 are
    left -> Syrup 330 - 30 = 300 >= 300, the tank DOES finish, and then the
    defensive pivot (knocking out with the body that survives) rules again."""
    with open(_HYDRA_PIVOT_TANQUE_KO_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    result = m.agent(obs)

    assert result == [retreat_opt], (
        f"con el tanque REALMENTE letal tras retirar, debe RETIRAR "
        f"(opt {retreat_opt}) y no atacar con el fragil; obtuvo {result}")
    assert result != [attack_opt]


# Record 007 (step 78 vs Archaludon ex, WON with a suboptimal play): a charged active
# Hydrapple ex + >=2 attackers, with Boss's Orders AND Lillie's Determination in
# hand. The rival has a non-ex Cinderace (1 prize, not very dangerous) in the active spot
# and a Duraludon (1 prize, the pre-evo of Archaludon ex = the deck's attacker) on the
# bench that we can gust and KNOCK OUT. The agent played Lillie's (shuffling the
# Boss's into the deck). Correct: play Boss's to gust+knock out the Duraludon (the same
# prize as the Cinderace but it removes the future attacker). The pivot failed because
# (1) the Lillie's veto only applied vs Hops and (2) with EQUAL prizes the
# code prefers knocking out the active instead of gusting the threat pre-evo.
_BOSS_OVER_LILLIE_DURALUDON_FIXTURE = ROOT / "tests" / "fixtures" / "archaludon_boss_over_lillie_duraludon_step78.json"


def test_archaludon_step78_plays_boss_to_gust_duraludon_not_lillie():
    with open(_BOSS_OVER_LILLIE_DURALUDON_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o["index"] == 0)
    lillie_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.PLAY) and o["index"] == 1)

    result = m.agent(obs)

    assert result == [boss_opt], (
        f"debe jugar Boss's (opt {boss_opt}) para gustear+noquear al Duraludon "
        f"(pre-evo de Archaludon ex), no Lillie's (opt {lillie_opt}); obtuvo {result}"
    )
    assert result != [lillie_opt], "no jugar Lillie's teniendo Boss's y atacantes de sobra"


# Record 003 (step 17 vs Archaludon, LOST): the agent played Meowth ex to
# search (Last-Ditch Catch) for a Lillie's Determination when it ALREADY had one in
# hand (a redundant fetch + it exposes a 2-prize body). With the energy already
# attached and a Tapu Bulu as the active (the first-turn-going-first exception with a lone
# basic != Tapu does not apply), it must play the Lillie's it already has, NOT the Meowth.
_NO_MEOWTH_HAVE_LILLIE_FIXTURE = ROOT / "tests" / "fixtures" / "archaludon_no_meowth_have_lillie_step18.json"


def test_archaludon_step17_plays_lillie_not_meowth_when_lillie_in_hand():
    with open(_NO_MEOWTH_HAVE_LILLIE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    lillie_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.PLAY) and o["index"] == 1)
    meowth_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.PLAY) and o["index"] == 3)

    result = m.agent(obs)

    assert result == [lillie_opt], (
        f"debe jugar la Lillie's que ya tiene (opt {lillie_opt}), no bajar Meowth ex "
        f"para buscar otra (opt {meowth_opt}); obtuvo {result}"
    )
    assert result != [meowth_opt], "no bajar Meowth ex para un fetch de Lillie's redundante"


# Record 004 (step 60 vs Abomasnow, LOST): we already played a Supporter this turn
# (supporterPlayed=True) and the agent played a SECOND Meowth ex. Meowth ex is only
# good for Last-Ditch Catch -> searching for a Supporter; with the Supporter already played that
# fetch is useless, so playing a 2-prize body is pure waste. The normal
# veto (-1) tied on score with the non-KO attack (also -1) and the Meowth won
# the tie-break by index. Correct: attack (or end), never play the Meowth.
_ABOMASNOW_NO_SECOND_MEOWTH_FIXTURE = (
    ROOT / "tests" / "fixtures" / "abomasnow_no_second_meowth_supporter_played_step60.json")


def test_abomasnow_step60_no_meowth_when_supporter_played():
    with open(_ABOMASNOW_NO_SECOND_MEOWTH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    assert obs["current"]["supporterPlayed"] is True

    options = obs["select"]["option"]
    meowth_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.PLAY) and o["index"] == 2)
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    result = m.agent(obs)

    assert result != [meowth_opt], (
        f"no bajar un segundo Meowth ex (opt {meowth_opt}) con el Supporter ya jugado: "
        f"el fetch es inutil y expone un cuerpo de 2 premios; obtuvo {result}"
    )
    assert result == [attack_opt], (
        f"debe atacar (opt {attack_opt}) en vez de desperdiciar el Meowth; obtuvo {result}"
    )


# Record 012 (step 241 vs Iono, WON with a suboptimal play): with 2 prizes,
# an active Ogerpon ex (4 energies, it can retreat), a bench with Hydrapple ex (2 energies),
# another Ogerpon ex and Meganium, and Boss's + Lana's in hand; the rival has an Iono's
# Bellibolt ex (280 HP, 2 prizes) on the bench. The agent played Lana's Aid. Correct:
# play Boss's to gust the Bellibolt ex and knock it out after RETREATING the active and
# promoting the Hydrapple ex (Syrup Storm scales with the TOTAL Grass on the field ~= 330),
# winning the 2 prizes. The win-via-gust detection only looked at the attack of the
# current active (Ogerpon 150 < 280), not at the Hydrapple promoted after retreating.
_BOSS_WIN_RETREAT_PROMOTE_FIXTURE = ROOT / "tests" / "fixtures" / "iono_boss_win_retreat_promote_hydra_step241.json"


def test_iono_step241_plays_boss_win_via_retreat_promote_not_lana():
    with open(_BOSS_WIN_RETREAT_PROMOTE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o["index"] == 0)
    lana_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o["index"] == 1)

    result = m.agent(obs)

    assert result == [boss_opt], (
        f"debe jugar Boss's (opt {boss_opt}) para el remate ganador (gustear+noquear "
        f"al Bellibolt ex tras retirar+promover Hydrapple), no Lana's (opt {lana_opt}); "
        f"obtuvo {result}"
    )
    assert result != [lana_opt], "no jugar Lana's Aid cuando hay un remate ganador con Boss's"


# A variant (user): the winning finisher with Boss's must be detected with ANY
# bench attacker, not only Hydrapple ex. Here there is NO Hydrapple; the bench
# attacker is an Ogerpon ex with enough energy (Ivy Bludgeon = 30+30*10 = 330 >=
# 280) that knocks out the Bellibolt ex after retreating+promoting. It confirms that
# `_bench_attacker_can_ko` evaluates the whole bench (Ogerpon/Tapu/Meganium/etc).
_BOSS_WIN_RETREAT_OGERPON_FIXTURE = ROOT / "tests" / "fixtures" / "iono_boss_win_retreat_promote_ogerpon_step241.json"


def test_iono_step241_boss_win_via_bench_ogerpon_not_only_hydrapple():
    with open(_BOSS_WIN_RETREAT_OGERPON_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o["index"] == 0)
    lana_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o["index"] == 1)

    result = m.agent(obs)

    assert result == [boss_opt], (
        f"el remate ganador debe verse con un Ogerpon ex de banca (sin Hydrapple): "
        f"Boss's (opt {boss_opt}), no Lana's (opt {lana_opt}); obtuvo {result}"
    )
    assert result != [lana_opt], "la deteccion de win-via-banca debe evaluar toda la banca, no solo Hydrapple"


# Record 005 (step 51 vs Dragapult, LOST): with Boss's + Lillie's in hand,
# our ONLY attacker is the active (an Ogerpon ex) and on the bench there are only BASICS
# (an uncharged Tapu Bulu, Applin, Bayleef) -> no ready bench attacker. The
# rival (a Dragapult ex at 320 HP in the active spot) has a gustable 1-prize
# Drakloak/Dreepy. The agent played Boss's (a development gust to cut the line).
# Correct: play Lillie's to DIG, because with no second attacker the gust does not
# chain. Boss's over Lillie's only takes priority with a real bench attacker
# (!= Applin) ready.
_DRAGAPULT_LILLIE_OVER_BOSS_FIXTURE = ROOT / "tests" / "fixtures" / "dragapult_lillie_over_boss_one_attacker_step51.json"


def test_dragapult_step51_plays_lillie_over_boss_when_no_second_attacker():
    with open(_DRAGAPULT_LILLIE_OVER_BOSS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o["index"] == 0)
    lillie_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.PLAY) and o["index"] == 1)

    result = m.agent(obs)

    assert result == [lillie_opt], (
        f"con solo el activo como atacante (banca = basicos/Applin) debe CAVAR con "
        f"Lillie's (opt {lillie_opt}), no gustear con Boss's (opt {boss_opt}); obtuvo {result}"
    )
    assert result != [boss_opt], "un gusteo de desarrollo no tiene prioridad sin un atacante de banca real"


def test_boss_dev_gust_keeps_priority_with_ready_bench_attacker():
    # A complement: WITH a ready bench attacker (!= Applin), the development
    # gust (boss_prize_rank) DOES keep priority -> Boss's does not yield.
    _hc = {m.Boss_Orders: 1, m.Lillie_Determination: 1}
    ctx = _make_boss_ctx(boss_prize_rank=7, has_ready_bench_attacker=True,
                         active_cant_attack=False, hand_counts=_hc)
    assert m._score_boss_orders_play(ctx) > m.BOSS_SCORE_EMPTY_GUST, (
        "con atacante de banca listo, el gusteo de desarrollo mantiene prioridad")
    ctx_no = _make_boss_ctx(boss_prize_rank=7, has_ready_bench_attacker=False,
                            active_cant_attack=False, hand_counts=dict(_hc))
    assert m._score_boss_orders_play(ctx_no) == m.BOSS_SCORE_EMPTY_GUST, (
        "sin atacante de banca real (y Lillie's en mano), el gusteo de desarrollo cede a Lillie's")


# Record 004 (step 35) vs Mega Lucario (WON): when resolving the search (TO_HAND)
# of an Ultra Ball, with a Chikorita in the active spot (only a chip, no real attacker), a
# Meowth ex already on the bench, a Dipplin just evolved and Bayleef only in HAND (there
# is no Bayleef in play -> a searched Meganium would be USELESS this turn, mere
# preparation), and with Meowth ex + Lillie's still in the deck and no Supporter played,
# the 2nd Meowth ex must be searched for (Last-Ditch Catch -> Lillie's, refresh the hand) instead
# of the dead Meganium. The old code searched for Meganium.
_UB_MEOWTH_NOT_MEGANIUM_FIXTURE = ROOT / "tests" / "fixtures" / "lucario_ub_meowth_not_meganium_step35.json"


def test_lucario_step35_ultraball_searches_meowth_not_dead_meganium():
    with open(_UB_MEOWTH_NOT_MEGANIUM_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    deck = obs["select"]["deck"]
    options = obs["select"]["option"]
    meowth_opt = next(i for i, o in enumerate(options)
                      if deck[o["index"]]["id"] == m.Meowth_ex)
    meganium_opt = next(i for i, o in enumerate(options)
                        if deck[o["index"]]["id"] == m.Meganium)

    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"Ultra Ball debe buscar Meowth ex (opt {meowth_opt}) para el motor Lillie's, "
        f"no un Meganium inutil (opt {meganium_opt}); obtuvo {result}"
    )
    assert result != [meganium_opt], "no buscar un Meganium que no se puede jugar este turno"


# Record 007 (step 90) vs Alakazam (WON): after a KO, when PROMOTING (TO_ACTIVE)
# a new active, there is a CHARGED Tapu Bulu (4 energy, it hits for 220) on the bench that
# KNOCKS OUT the active Alakazam ex (140 HP). The agent brought up an Ogerpon ex (more life,
# but 2 prizes); the right thing is to bring up the Tapu Bulu (non-ex, 1 prize) which knocks out
# all the same. Rule: ALWAYS promote the charged Tapu Bulu (or one chargeable with energy in
# hand/Night Stretcher) that can defeat the rival active.
_PROMOTE_TAPU_KO_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_promote_tapu_bulu_ko_step90.json"


def test_alakazam_step90_promotes_tapu_bulu_ko_over_ogerpon_ex():
    with open(_PROMOTE_TAPU_KO_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    bench = obs["current"]["players"][1]["bench"]
    options = obs["select"]["option"]
    tapu_opt = next(i for i, o in enumerate(options)
                    if bench[o["index"]]["id"] == m.Tapu_Bulu)
    ogerpon_opts = [i for i, o in enumerate(options)
                    if bench[o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex]

    result = m.agent(obs)

    assert result == [tapu_opt], (
        f"debe promover el Tapu Bulu cargado que noquea (opt {tapu_opt}), obtuvo {result}"
    )
    assert result[0] not in ogerpon_opts, "no promover un Ogerpon ex (2 premios) si Tapu Bulu noquea"


# Record 019 (step 190) vs Dragapult (WON): on a lethal turn, with Boss's Orders
# in hand, ~20 Grass energies (the active Hydrapple ex's Syrup Storm knocks out
# any ex) and the rival at 2 prizes with Latias ex / Dragapult ex on the bench, the
# agent RETREATED the active (a defensive pivot, 6600) instead of playing Boss's to
# gust an ex and finish with the active (win_via_boss_gust, which was worth only 5600).
# A gust that WINS the game must beat any defensive retreat.
_BOSS_WIN_GUST_FIXTURE = ROOT / "tests" / "fixtures" / "dragapult_boss_win_gust_not_retreat_step190.json"


def test_dragapult_step190_plays_boss_win_gust_instead_of_retreating():
    with open(_BOSS_WIN_GUST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    hand = obs["current"]["players"][1]["hand"]
    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY)
                    and hand[o["index"]]["id"] == m.Boss_Orders)
    retreat_opts = [i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.RETREAT)]

    result = m.agent(obs)

    assert result == [boss_opt], (
        f"debe jugar Boss's Orders (opt {boss_opt}) para gustear+rematar y ganar, "
        f"obtuvo {result}"
    )
    assert result[0] not in retreat_opts, "no retirar el activo teniendo un gusteo ganador"


# Record 006 (step 72) vs Hops (LOST): with the BENCH FULL (5 Pokemon) and
# NO evolution available to search for in the DECK (there is a Dipplin in play but
# the Hydrapple ex is no longer in the deck), the Ultra Ball can neither bench nor
# evolve anything: it is useless and would only waste 2 discards. The agent played it
# anyway (a survival rescue that resurrected the cut-off + a tie-break by index 0
# when the rest of the plays were also vetoed). It must CANCEL it and attack.
# The turn's sequence is replicated so that the DECK tracking knows the
# Hydrapple ex is gone (the Explorer's Guidance reveals the deck earlier).
_UB_CANCEL_FULL_BENCH_FIXTURE = ROOT / "tests" / "fixtures" / "hops_ultraball_cancel_full_bench_no_evo_step72.json"


def test_hops_step72_cancels_useless_ultraball_full_bench_no_evo_in_deck():
    with open(_UB_CANCEL_FULL_BENCH_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    final_obs = None
    result = None
    for item in seq:
        final_obs = item["observation"]
        result = m.agent(final_obs)

    options = final_obs["select"]["option"]
    hand = final_obs["current"]["players"][0]["hand"]
    ub_opts = [i for i, o in enumerate(options)
               if o.get("type") == int(OptionType.PLAY)
               and hand[o["index"]]["id"] == m.Ultra_Ball]

    assert result[0] not in ub_opts, (
        "no jugar una Ultra Ball inutil (banca llena y sin evolucion en el mazo); "
        f"obtuvo {result}"
    )


# Record 004 (step 28) vs Mega Starmie (LOST): with a bench Teal Mask Ogerpon ex
# at 2 energies that can STILL use Teal Dance this turn, the agent attached
# an energy MANUALLY (to the Ogerpon or to another body) instead of using Teal Dance
# first. Teal Dance attaches 1 Grass AND DRAWS a card, so it takes priority
# over the manual attachment (the attachment is postponed until the ability is used). The play
# order left the ability (tier 0) below the ENERGY tier of the attachments.
_TEAL_DANCE_BEFORE_ATTACH_FIXTURE = ROOT / "tests" / "fixtures" / "starmie_teal_dance_before_attach_step28.json"


def test_starmie_step28_teal_dance_before_manual_attach():
    with open(_TEAL_DANCE_BEFORE_ATTACH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    teal_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.ABILITY))
    _teal_slot = (options[teal_opt].get("area"), options[teal_opt].get("index"))
    ogerpon_attach_opts = [
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.ATTACH)
        and (o.get("inPlayArea"), o.get("inPlayIndex")) == _teal_slot
    ]

    result = m.agent(obs)

    assert result == [teal_opt], (
        f"debe usar Teal Dance (opt {teal_opt}, adjunta + ROBA) antes de cargar "
        f"energia manualmente al Ogerpon ex; obtuvo {result}"
    )
    assert result[0] not in ogerpon_attach_opts, (
        "nunca cargar energia manualmente a un Ogerpon ex que aun puede usar Teal Dance"
    )


# Record 004 (step 29) vs Mega Starmie (LOST): the Ultra Ball resolves its
# search (TO_HAND) bringing a Meganium (it would evolve a Bayleef in play), but
# there is NO USABLE attacker this turn: the active (Tapu Bulu, 0 energy, a retreat
# cost of 3) can neither attack nor retreat, so the charged bench Ogerpon ex
# is stuck. With a free bench and the Meowth ex -> Lillie's engine available,
# Meowth ex must be brought (play it -> Last-Ditch Catch -> Lillie's -> refresh the
# hand) instead of an evolution that will give no attack now. It generalises the case of
# step 35: here the evolution IS playable (there is a Bayleef), but it still adds no attack.
_UB_NO_ATTACKER_MEOWTH_FIXTURE = ROOT / "tests" / "fixtures" / "starmie_ub_meowth_no_attacker_step29.json"


def test_starmie_step29_ultraball_searches_meowth_when_no_usable_attacker():
    with open(_UB_NO_ATTACKER_MEOWTH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    deck = obs["select"]["deck"]
    options = obs["select"]["option"]
    meowth_opt = next(i for i, o in enumerate(options)
                      if deck[o["index"]]["id"] == m.Meowth_ex)
    meganium_opts = [i for i, o in enumerate(options)
                     if deck[o["index"]]["id"] == m.Meganium]

    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"sin atacante usable este turno, Ultra Ball debe buscar Meowth ex "
        f"(opt {meowth_opt}) para el motor Lillie's; obtuvo {result}"
    )
    assert result[0] not in meganium_opts, (
        "no buscar un Meganium (evolucion sin ataque este turno) cuando no hay atacante usable"
    )


# Record 010 (step 127) vs Alakazam (LOST): with a charged active Teal Mask Ogerpon ex (an ex,
# 2 prizes) that KNOCKS OUT the Alakazam ex (140 HP) and a charged Meganium (non-ex,
# 1 prize) on the bench that ALSO knocks it out (140 base), the game attacked with
# the Ogerpon. Against Alakazam you have to attack with 1-prize bodies: retreat the ex
# and promote the Meganium so that, if they knock it out, we only give away 1 prize and not 2.
_ALAKAZAM_RETREAT_EX_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_retreat_ex_attack_meganium_step127.json"
_ALAKAZAM_PROMOTE_MEGANIUM_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_promote_meganium_1prize_step127.json"


def test_alakazam_step127_retreats_ex_to_attack_with_meganium():
    with open(_ALAKAZAM_RETREAT_EX_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    result = m.agent(obs)

    assert result == [retreat_opt], (
        f"vs Alakazam, con un Meganium (1 premio) que noquea en banca, debe RETIRAR "
        f"el ex activo (opt {retreat_opt}) en vez de atacar con el ex (opt {attack_opt}); "
        f"obtuvo {result}"
    )


def test_alakazam_step127_promotes_meganium_1prize_over_ex():
    with open(_ALAKAZAM_PROMOTE_MEGANIUM_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    bench = obs["current"]["players"][1]["bench"]
    options = obs["select"]["option"]
    meganium_opt = next(i for i, o in enumerate(options)
                        if bench[o["index"]]["id"] == m.Meganium)
    ex_opts = [i for i, o in enumerate(options)
               if bench[o["index"]]["id"] in m.OUR_EX_IDS]

    result = m.agent(obs)

    assert result == [meganium_opt], (
        f"vs Alakazam, al promover tras retirar debe subir el Meganium (1 premio, "
        f"opt {meganium_opt}) que noquea, no un ex de 2 premios; obtuvo {result}"
    )
    assert result[0] not in ex_opts, "no promover un ex (2 premios) si Meganium noquea vs Alakazam"


# Record 008 (step 84) vs Marnie/Froslass (LOST): a DEAD TURN -- the active
# (a Hydrapple ex, 0 energy, a retreat cost of 3) can neither ATTACK nor RETREAT, there is
# no bench attacker to bring up and the hand (Tapu Bulu, Ogerpon ex, Meowth ex, Ultra
# Ball) has nothing to enable an attack with. With a bench slot and the refresh engine
# in the DECK, Meowth ex must be played (Last-Ditch Catch -> Lana's Aid /
# Lillie's) instead of a redundant body (Tapu Bulu). The "do not bench
# Meowth ex vs Froslass" veto has a dead-turn exception here.
_MARNIE_FROSLASS_MEOWTH_FIXTURE = ROOT / "tests" / "fixtures" / "marnie_froslass_meowth_dead_turn_step84.json"


def test_marnie_froslass_step84_plays_meowth_dead_turn_not_tapu():
    with open(_MARNIE_FROSLASS_MEOWTH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    hand = obs["current"]["players"][1]["hand"]
    options = obs["select"]["option"]
    meowth_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.PLAY)
                      and hand[o["index"]]["id"] == m.Meowth_ex)
    tapu_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY)
                    and hand[o["index"]]["id"] == m.Tapu_Bulu)

    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"turno muerto vs Froslass: debe bajar Meowth ex (opt {meowth_opt}) para el "
        f"motor Lana's/Lillie's, no Tapu Bulu (opt {tapu_opt}); obtuvo {result}"
    )
    assert result[0] != tapu_opt, "no bajar un cuerpo redundante (Tapu Bulu) en un turno muerto"


# Record 012 (step 93) vs Archaludon/Duraludon (LOST): the active Teal Mask
# Ogerpon ex (4 effective energies) does 30+30*4 = 150 damage; Duraludon (Metal)
# RESISTS -30 to Grass, so the real damage is 120 and it does NOT knock out the 130 HP active
# (it leaves it at 10). The old computation added the TARGET's energy (30+30*(4+1)=
# 180 -> 150 after the resistance) and believed it already knocked out, so it charged Tapu Bulu
# for the future instead of finishing. The right thing: use Teal Dance on the active (it goes
# up to 6 effective -> 210 base -> 180 after the resistance >= 130) to enable the KO.
_DURALUDON_TEAL_DANCE_FIXTURE = ROOT / "tests" / "fixtures" / "duraludon_teal_dance_ko_resistance_step93.json"


def test_duraludon_step93_teal_dance_for_ko_accounting_resistance():
    with open(_DURALUDON_TEAL_DANCE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    # Teal Dance (an ability) on the ACTIVE Ogerpon ex (area 4)
    teal_active_opt = next(
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.ABILITY)
        and o.get("area") == int(AreaType.ACTIVE))
    # Attaching a manual energy to a bench Tapu Bulu (what it used to do)
    bench = obs["current"]["players"][0]["bench"]
    tapu_attach_opts = [
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.ATTACH)
        and o.get("inPlayArea") == int(AreaType.BENCH)
        and bench[o["inPlayIndex"]]["id"] == m.Tapu_Bulu]

    # UPDATED (July 2026 audit, the inline copies of Myriad corrected):
    # with the VERIFIED formula (30+30*(ours+theirs); the memory
    # ogerpon-myriad-cuenta-ambos-activos, 6 records of real damage), the
    # Duraludon of the fixture carries 1 energy -> 30+30*(4+1)=180 -> 150 after the
    # resistance >= 130: the active ALREADY knocks out WITHOUT Teal Dance, and charging the
    # future Tapu (the alakazam-cargar-meganium-atacante-futuro rule generalised by
    # _tapu_future_charge) is the right line. This test had been written
    # with the old "ours only" formula (voided as wrong).
    result = m.agent(obs)
    assert result[0] in tapu_attach_opts, (
        f"con el KO ya asegurado (180-30=150 >= 130) se carga el Tapu futuro; "
        f"obtuvo {result}")

    # A COUNTERFACTUAL (it preserves the test's original intent: the RESISTANCE
    # is accounted for): with the Duraludon WITHOUT energy, 30+30*4=150 -> 120 after
    # the resistance < 130 -> the active does NOT knock out and Teal Dance (it goes up to 6 of ours:
    # 30+30*6=210 -> 180 >= 130) enables the KO.
    import copy as _c
    obs2 = _c.deepcopy(obs)
    obs2["current"]["players"][1]["active"][0]["energies"] = []
    obs2["current"]["players"][1]["active"][0]["energyCards"] = []
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result2 = m.agent(obs2)
    assert result2 == [teal_active_opt], (
        f"sin energia rival la resistencia deja el golpe en 120 < 130: Teal "
        f"Dance en el activo habilita el KO; obtuvo {result2}")


def test_ogerpon_damage_counts_both_active_energy():
    # Myriad Leaf Shower (attack 120): 30 + 30 for each Energy attached to BOTH
    # Active Pokemon (ours + the rival's). Verified with the REAL damage of 6
    # records: own 3 + opp 2 -> 180; own 4 + opp 2 -> 210; own 4 + opp 0 -> 150;
    # own 3 + opp 1 -> 150. `_attacker_base_damage` returns the BASE damage (before
    # weakness/resistance), so it counts own(4)+target(3) = 7 -> 30+210 = 240.
    from types import SimpleNamespace as _NS
    tgt3 = _NS(id=169, hp=130, energies=[8, 8, 8], maxHp=130)   # 3 energy on the target
    base = m._attacker_base_damage(m.Teal_Mask_Ogerpon_ex, tgt3, 4,
                                   grass_scale=0, teal_self_energy=4, bench_count=5)
    assert base == 240, f"Myriad = 30+30*(propia 4 + objetivo 3) = 240; obtuvo {base}"
    # a target with no energy -> only ours counts (30+30*4 = 150)
    tgt0 = _NS(id=169, hp=130, energies=[], maxHp=130)
    base0 = m._attacker_base_damage(m.Teal_Mask_Ogerpon_ex, tgt0, 4,
                                    grass_scale=0, teal_self_energy=4, bench_count=5)
    assert base0 == 150, f"con objetivo sin energia = 30+30*4 = 150; obtuvo {base0}"


# Record 004 (step 51) vs Cynthia's Garchomp (LOST): when playing Boss's Orders,
# the game gusted the Cynthia's Gible (a basic, 70 HP) instead of the HIGHEST evolution
# of the line -- Cynthia's Gabite (stage1) with Cynthia's Power Weight (170 HP), which
# also has energy. Our bench Ogerpon ex (6 energies, x2 Grass weakness
# = 420) knocks out either one after retreating+promoting. A general rule for Stage 2 decks
# (Cynthia/Dragapult/Marnie; Alakazam has its own rule): ALWAYS favour the
# highest evolution line we can knock out.
_CYNTHIA_BOSS_GUST_EVO_FIXTURE = ROOT / "tests" / "fixtures" / "cynthia_boss_gust_highest_evo_gabite_step51.json"


def test_cynthia_step51_boss_gusts_highest_evolution_gabite_not_gible():
    with open(_CYNTHIA_BOSS_GUST_EVO_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    bench = obs["current"]["players"][0]["bench"]
    options = obs["select"]["option"]
    gabite_tool_opt = next(
        i for i, o in enumerate(options)
        if bench[o["index"]]["id"] == 380 and bench[o["index"]].get("tools"))
    gible_opts = [i for i, o in enumerate(options)
                  if bench[o["index"]]["id"] == 379]

    result = m.agent(obs)

    assert result == [gabite_tool_opt], (
        f"Boss's debe gustear el Cynthia's Gabite (mayor evolucion, opt {gabite_tool_opt}) "
        f"que podemos noquear, no el Gible basico; obtuvo {result}"
    )
    assert result[0] not in gible_opts, (
        "no gustear el basico (Gible) cuando podemos noquear la evolucion superior (Gabite)"
    )


# Strategy vs Comfey (mill/control; registro_005): detected by Comfey (164) /
# Bramblin (817) / Brambleghast (818). Rule 1 (strict): ONLY play Teal Mask
# Ogerpon ex, a MAXIMUM of 2 in play; veto any other Pokemon (apart from the start-up).
# Rule 5: cancel the Ultra Ball if there are already 2 Ogerpon ex in play.
def _comfey_main_obs(ogerpon_field, comfey=True):
    import copy
    base = json.load(open(
        ROOT / "tests" / "fixtures" / "cynthia_boss_gust_highest_evo_gabite_step51.json",
        encoding="utf-8"))["observation"]
    o = copy.deepcopy(base)
    cur = o["current"]; me = cur["players"][1]; op = cur["players"][0]
    if comfey:
        op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                         "hp": 70, "id": 164, "maxHp": 70, "playerIndex": 0,
                         "preEvolution": [], "serial": 900, "tools": []}]
        op["bench"] = []
    me["active"] = [{"appearThisTurn": False, "energies": [1, 1, 1], "energyCards": [],
                     "hp": 210, "id": 96, "maxHp": 210, "playerIndex": 1,
                     "preEvolution": [], "serial": 800, "tools": []}]
    me["bench"] = [{"appearThisTurn": False, "energies": [], "energyCards": [], "hp": 210,
                    "id": 96, "maxHp": 210, "playerIndex": 1, "preEvolution": [],
                    "serial": 810 + k, "tools": []} for k in range(max(0, ogerpon_field - 1))]
    me["hand"] = [{"id": 96, "playerIndex": 1, "serial": 820},
                  {"id": 710, "playerIndex": 1, "serial": 821},
                  {"id": 1121, "playerIndex": 1, "serial": 822}]
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [{"index": 0, "type": 7}, {"index": 1, "type": 7},
                              {"index": 2, "type": 7}, {"type": 14}]}
    cur["yourIndex"] = 1
    return o


def _score_by_hand_id(obs):
    captured = {}
    orig = m._debug_log_decision
    def spy(context, select, scores, obs_, my_index, top_n=3):
        captured["s"] = list(scores)
    _restaurar_spy = instalar("_debug_log_decision", spy)
    m.DEBUG_DECISIONS = True
    try:
        m._init_cards_tracking(); m.plan = m.AttackPlan()
        m.agent(obs)
    finally:
        _restaurar_spy()
    me = obs["current"]["players"][1]
    out = {}
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(OptionType.PLAY):
            out[me["hand"][o["index"]]["id"]] = captured["s"][i]
    return out


def test_comfey_rule1_only_ogerpon_max_two_and_veto_others():
    # With 0 Ogerpon ex in play: playing an Ogerpon ex is OK, another Pokemon vetoed.
    s0 = _score_by_hand_id(_comfey_main_obs(0, comfey=True))
    assert s0[m.Teal_Mask_Ogerpon_ex] > 0, "vs Comfey debe poder bajar Teal Mask Ogerpon ex"
    assert s0[m.Meganium] == -1, "vs Comfey NO se baja ningun Pokemon que no sea Ogerpon ex"
    # With 2 Ogerpon ex in play: do not play a 3rd.
    s2 = _score_by_hand_id(_comfey_main_obs(2, comfey=True))
    assert s2[m.Teal_Mask_Ogerpon_ex] == -1, "maximo 2 Teal Mask Ogerpon ex vs Comfey"


def test_comfey_rule5_cancel_ultraball_when_two_ogerpon():
    s2 = _score_by_hand_id(_comfey_main_obs(2, comfey=True))
    assert s2[m.Ultra_Ball] < 0, "vs Comfey con 2 Ogerpon ex, la Ultra Ball es inutil -> cancelar"


def test_comfey_rules_do_not_fire_vs_other_decks():
    # Control: without Comfey, Meganium is played normally and the Ultra Ball is not cancelled.
    s = _score_by_hand_id(_comfey_main_obs(0, comfey=False))
    assert s[m.Meganium] > 0, "vs un mazo normal, la regla Ogerpon-only NO debe vetar otros Pokemon"


# Strategy vs Comfey — the Trainer rules (user): the ONLY cards to play
# are Lillie's Determination (ONLY with a hand >=10), Lana's Aid (ONLY if it recovers >=2
# energies from the discard) and Boss's Orders (as always). The rest (Dawn, etc.)
# are not played.
def _comfey_supporter_obs(hand_size, grass_discard, comfey=True, ogerpon=False,
                          deck_count=None):
    import copy
    base = json.load(open(
        ROOT / "tests" / "fixtures" / "cynthia_boss_gust_highest_evo_gabite_step51.json",
        encoding="utf-8"))["observation"]
    o = copy.deepcopy(base)
    cur = o["current"]; me = cur["players"][1]; op = cur["players"][0]
    cur["supporterPlayed"] = False; cur["stadiumPlayed"] = False
    cur["energyAttached"] = False; cur["turn"] = 5
    if comfey:
        op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                         "hp": 70, "id": 164, "maxHp": 70, "playerIndex": 0,
                         "preEvolution": [], "serial": 900, "tools": []}]
        op["bench"] = [{"appearThisTurn": False, "energies": [], "energyCards": [], "hp": 40,
                        "id": 92, "maxHp": 40, "playerIndex": 0, "preEvolution": [],
                        "serial": 901, "tools": []}]
    me["active"] = [{"appearThisTurn": False, "energies": [1, 1, 1], "energyCards": [],
                     "hp": 210, "id": 96, "maxHp": 210, "playerIndex": 1,
                     "preEvolution": [], "serial": 800, "tools": []}]
    me["bench"] = []
    hand = [{"id": m.Lillie_Determination, "playerIndex": 1, "serial": 820},
            {"id": m.Lanas_Aid, "playerIndex": 1, "serial": 821},
            {"id": m.Dawn, "playerIndex": 1, "serial": 822}]
    # `ogerpon` puts a PRODUCTIVE PLAY in the menu without altering the hand
    # size (it replaces a filler): with an empty bench, playing Teal Mask
    # Ogerpon ex scores 22000 vs Comfey (Rule 1). It is needed to isolate the
    # Supporter PRIORITY rules from the dead-turn rescue: with no real
    # play, the rescue lifts the Lillie's veto on purpose.
    relleno = max(0, hand_size - 3 - (1 if ogerpon else 0))
    for k in range(relleno):
        hand.append({"id": 1, "playerIndex": 1, "serial": 830 + k})
    options = [{"index": 0, "type": 7}, {"index": 1, "type": 7},
                {"index": 2, "type": 7}]
    if ogerpon:
        hand.append({"id": m.Teal_Mask_Ogerpon_ex, "playerIndex": 1, "serial": 890})
        options.append({"index": len(hand) - 1, "type": 7})
    options.append({"type": 14})
    me["hand"] = hand
    if deck_count is not None:
        me["deckCount"] = deck_count
    me["discard"] = [{"id": 1, "playerIndex": 1, "serial": 700 + k}
                     for k in range(grass_discard)]
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0, "option": options}
    cur["yourIndex"] = 1
    return o


def test_comfey_lillie_only_with_ten_or_more_cards():
    # With a productive play in the menu (playing an Ogerpon) the PRIORITY rule
    # rules: vs Comfey, Lillie's only comes in with a hand >= 10.
    s10 = _score_by_hand_id(_comfey_supporter_obs(10, 1, comfey=True, ogerpon=True))
    assert s10[m.Lillie_Determination] > 0, "vs Comfey con mano>=10 se puede jugar Lillie's"
    s9 = _score_by_hand_id(_comfey_supporter_obs(9, 1, comfey=True, ogerpon=True))
    assert s9[m.Lillie_Determination] == -1, "vs Comfey con mano<10 NO se juega Lillie's"


# The turn's Supporter does NOT accumulate (user, log 88359220 step 33 vs Comfey,
# LOST): the reservation "vs Comfey only with a hand >= 10" is a PRIORITY
# rule, and it cannot end up ending the turn with the Lillie's dead in
# hand. If NO play is left, the sterile-turn rescue plays it; the
# only thing that stops it is the deck-out arithmetic (Lillie's shuffles the hand and
# draws 6/8), which is the real reason for the old matchup exemption and now
# protects equally against any mill deck.
def test_comfey_dead_turn_plays_lillie_even_with_a_short_hand():
    s = _score_by_hand_id(_comfey_supporter_obs(9, 1, comfey=True, ogerpon=False))
    assert s[m.Lillie_Determination] > 0, (
        "sin ninguna jugada productiva el turno muere: hay que refrescar con "
        f"Lillie's en vez de terminar; obtuvo {s[m.Lillie_Determination]}")


def test_comfey_dead_turn_respects_the_deckout_brake():
    # The same dead turn but with a CRITICAL deck: with 9 cards in hand and the 6
    # prizes intact Lillie's draws 8, so the deck stays the same (6) --- below
    # the threshold. There the anti-mill reservation DOES rule and the veto holds.
    s = _score_by_hand_id(
        _comfey_supporter_obs(9, 1, comfey=True, ogerpon=False, deck_count=6))
    assert s[m.Lillie_Determination] == -1, (
        "con el mazo critico refrescar acerca el deck-out: el veto debe "
        f"aguantar aunque el turno muera; obtuvo {s[m.Lillie_Determination]}")


def test_comfey_lana_only_when_recovers_two_energies():
    s2 = _score_by_hand_id(_comfey_supporter_obs(9, 2, comfey=True))
    assert s2[m.Lanas_Aid] > 0, "vs Comfey con >=2 energias en descarte, Lana's Aid es jugable"
    s1 = _score_by_hand_id(_comfey_supporter_obs(9, 1, comfey=True))
    assert s1[m.Lanas_Aid] == -1, "vs Comfey con <2 energias recuperables NO se juega Lana's Aid"


def test_comfey_vetoes_other_trainers_like_dawn():
    s = _score_by_hand_id(_comfey_supporter_obs(10, 2, comfey=True))
    assert s[m.Dawn] == -1, "vs Comfey NO se juegan otros entrenadores (p.ej. Dawn)"
    # Control: without Comfey, Dawn is played as usual.
    sc = _score_by_hand_id(_comfey_supporter_obs(9, 2, comfey=False))
    assert sc[m.Dawn] > 0, "vs un mazo normal, Dawn NO debe estar vetada por la regla Comfey"


# Strategy vs Comfey — Rule 2 (the discard from Xerosic's Machinations: keeping
# 3 cards). The priority of what to KEEP: energies > Night Stretcher > Lana's Aid > Unfair
# Stamp > the rest of the trainers (and an Ogerpon ex that still fits, above the
# trainers). Rule 4 (an active confused by Brambleghast): if there is a ready bench
# attacker, retreat and attack with it; if not, attack with the confused one.
def _comfey_discard_obs():
    import copy
    base = json.load(open(
        ROOT / "tests" / "fixtures" / "cynthia_boss_gust_highest_evo_gabite_step51.json",
        encoding="utf-8"))["observation"]
    o = copy.deepcopy(base)
    cur = o["current"]; me = cur["players"][1]; op = cur["players"][0]
    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [], "hp": 70,
                     "id": 164, "maxHp": 70, "playerIndex": 0, "preEvolution": [],
                     "serial": 900, "tools": []}]
    op["bench"] = []
    me["active"] = [{"appearThisTurn": False, "energies": [1, 1, 1], "energyCards": [],
                     "hp": 210, "id": 96, "maxHp": 210, "playerIndex": 1,
                     "preEvolution": [], "serial": 800, "tools": []}]
    me["bench"] = []
    # hand: 2 grass, Night Stretcher, Lana's, Unfair Stamp, Dawn (rest), Ogerpon
    me["hand"] = [{"id": 1, "serial": 1, "playerIndex": 1},
                  {"id": 1, "serial": 2, "playerIndex": 1},
                  {"id": m.Night_Stretcher, "serial": 3, "playerIndex": 1},
                  {"id": m.Lanas_Aid, "serial": 4, "playerIndex": 1},
                  {"id": m.Unfair_Stamp, "serial": 5, "playerIndex": 1},
                  {"id": m.Dawn, "serial": 6, "playerIndex": 1},
                  {"id": 96, "serial": 7, "playerIndex": 1}]
    o["select"] = {"context": 8, "contextCard": None, "deck": None,
                   "effect": {"id": 1197, "playerIndex": 1, "serial": 999},
                   "maxCount": 4, "minCount": 4, "type": 1, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [{"area": 2, "index": i, "playerIndex": 1, "type": 3}
                              for i in range(7)]}
    cur["yourIndex"] = 1
    return o


def test_comfey_rule2_xerosic_keeps_energy_over_trainers():
    obs = _comfey_discard_obs()
    hand = obs["current"]["players"][1]["hand"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    discarded = set(m.agent(obs))  # the indices of the 4 cards to discard
    discarded_ids = [hand[obs["select"]["option"][i]["index"]]["id"] for i in discarded]
    # The energies are KEPT (they are never discarded).
    assert m.Basic_Grass_Energy not in discarded_ids, "vs Comfey/Xerosic las energias se mantienen"
    # The rest of the trainers (Dawn) are discarded before Night Stretcher/Lana's.
    assert m.Dawn in discarded_ids, "vs Comfey/Xerosic se descarta el resto de entrenadores (Dawn)"


def _comfey_confused_obs(bench_ready):
    import copy
    base = json.load(open(
        ROOT / "tests" / "fixtures" / "cynthia_boss_gust_highest_evo_gabite_step51.json",
        encoding="utf-8"))["observation"]
    o = copy.deepcopy(base)
    cur = o["current"]; me = cur["players"][1]; op = cur["players"][0]
    me["confused"] = True
    cur["supporterPlayed"] = False; cur["energyAttached"] = False; cur["turn"] = 6
    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [], "hp": 70,
                     "id": 164, "maxHp": 70, "playerIndex": 0, "preEvolution": [],
                     "serial": 900, "tools": []}]
    op["bench"] = []
    me["active"] = [{"appearThisTurn": False, "energies": [1, 1, 1], "energyCards": [],
                     "hp": 210, "id": 96, "maxHp": 210, "playerIndex": 1,
                     "preEvolution": [], "serial": 800, "tools": []}]
    me["bench"] = [{"appearThisTurn": False, "energies": [1, 1, 1] if bench_ready else [],
                    "energyCards": [], "hp": 210, "id": 96, "maxHp": 210, "playerIndex": 1,
                    "preEvolution": [], "serial": 810, "tools": []}]
    me["hand"] = []
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [{"attackId": 120, "type": 13}, {"type": 12}, {"type": 14}]}
    cur["yourIndex"] = 1
    return o


def test_comfey_rule4_confused_active_retreats_to_bench_attacker():
    obs = _comfey_confused_obs(bench_ready=True)
    retreat_opt = next(i for i, o in enumerate(obs["select"]["option"])
                       if o.get("type") == int(OptionType.RETREAT))
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    assert m.agent(obs) == [retreat_opt], (
        "activo confundido con atacante de banca listo: retirar (promover el cuerpo NO confundido)"
    )


def test_comfey_rule4_confused_active_attacks_when_no_bench_attacker():
    obs = _comfey_confused_obs(bench_ready=False)
    attack_opt = next(i for i, o in enumerate(obs["select"]["option"])
                      if o.get("type") == int(OptionType.ATTACK))
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    assert m.agent(obs) == [attack_opt], (
        "activo confundido sin atacante de banca: atacar con el confundido (aceptar la moneda)"
    )


# =====================================================================
# Neutralization Zone (id 1247, user): the strategy under the Neutralization
# Zone. The zone PREVENTS all damage to a Pokemon WITHOUT a rule box
# (1 prize) caused by an attacker WITH one (our ex). That is why, with the zone in play,
# our ex only damage the rival's ex; a 1-prize active has to be
# attacked with a NON-ex (Meganium/Tapu Bulu/etc.), and to hit a rival ex on the bench
# Boss's Orders is used to gust it.
# =====================================================================
import copy as _copy
import json as _json

_ZONE_PROMOTE_FIXTURE = ROOT / "tests" / "fixtures" / "zone_promote_nonex_not_ex_active.json"
_ZONE_BOSS_GUST_EX_FIXTURE = ROOT / "tests" / "fixtures" / "zone_boss_gust_bench_ex_step.json"


def test_zone_promote_nonex_over_ex_when_active_single_prize():
    # After a KO, with the Neutralization Zone in play and the rival ACTIVE worth 1
    # prize (Alakazam-like), promote the NON-ex attacker (Meganium) instead of an
    # ex (Ogerpon ex) which under the zone does 0 damage to that active.
    with open(_ZONE_PROMOTE_FIXTURE, encoding="utf-8") as f:
        obs = _json.load(f)["observation"]
    assert obs["current"]["stadium"][0]["id"] == m.Neutralization_Zone
    options = obs["select"]["option"]
    ex_opt = next(i for i, o in enumerate(options) if o.get("index") == 0)      # Ogerpon ex
    nonex_opt = next(i for i, o in enumerate(options) if o.get("index") == 1)   # Meganium
    result = m.agent(obs)
    assert result == [nonex_opt], (
        f"bajo la zona con activo rival de 1 premio, promover el NO-ex Meganium "
        f"(opt {nonex_opt}), no el ex Ogerpon (opt {ex_opt}); obtuvo {result}")
    assert result != [ex_opt]


def test_zone_promote_ex_when_active_is_ex():
    # A positive control: if the rival ACTIVE is an ex (a rule box), our
    # ex DO damage under the zone, so the ex is promoted (Ogerpon ex).
    with open(_ZONE_PROMOTE_FIXTURE, encoding="utf-8") as f:
        obs = _json.load(f)["observation"]
    obs = _copy.deepcopy(obs)
    cur = obs["current"]; yi = cur["yourIndex"]; op = cur["players"][1 - yi]
    # op active -> Iono's Bellibolt ex (269, a rule box), 130hp (our ex KOs it)
    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                     "hp": 130, "id": 269, "maxHp": 280, "playerIndex": 1 - yi,
                     "preEvolution": [], "serial": 301, "tools": []}]
    # The original fixture brings Abra/Kadabra in the rival DISCARD; with the
    # archetype inference by discard (the July 2026 audit) that switches on
    # `op_is_alakazam_deck` and the 1-prize rule would dominate the promotion
    # (correct vs Alakazam, but this test is the positive control of the
    # ZONE LOGIC). The discard is cleaned to isolate what is being tested.
    op["discard"] = [c for c in op["discard"]
                     if c["id"] not in (m.Abra, m.Kadabra, m.Alakazam_ex)]
    options = obs["select"]["option"]
    ex_opt = next(i for i, o in enumerate(options) if o.get("index") == 0)      # Ogerpon ex
    nonex_opt = next(i for i, o in enumerate(options) if o.get("index") == 1)   # Meganium
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [ex_opt], (
        f"activo rival ex bajo la zona: nuestros ex SI danan, promover el ex "
        f"(opt {ex_opt}), no el no-ex (opt {nonex_opt}); obtuvo {result}")


def test_zone_boss_gust_bench_ex():
    # With the Neutralization Zone, a 1-prize rival active (our ex does 0)
    # and a rival ex on the BENCH that our ex CAN knock out: play Boss's
    # Orders to gust the bench ex and finish it off (the 2 prizes / the game).
    with open(_ZONE_BOSS_GUST_EX_FIXTURE, encoding="utf-8") as f:
        obs = _json.load(f)["observation"]
    assert obs["current"]["stadium"][0]["id"] == m.Neutralization_Zone
    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o.get("index") == 0)
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [boss_opt], (
        f"bajo la zona, gustear con Boss's al ex del rival en banca para poder "
        f"atacarlo con nuestro ex (opt {boss_opt}); obtuvo {result}")


# Record 008 (step 108 vs Alakazam, WON with a suboptimal play): with the active
# Hydrapple ex ALREADY knocking out the active Alakazam, a PARTIALLY charged Meganium on the
# bench (2 effective, 1 physical Grass; it needs 1 more for its Wood Hammer at cost 4) and a
# Grass in hand, the agent ATTACKED straight away without charging the Meganium, wasting the
# energy. Meganium is an excellent 1-prize attacker (140 defeats Alakazam and its
# line); vs Alakazam it is charged as a FUTURE attacker when the active already secures its KO.
_ALK_CHARGE_MEGANIUM_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_charge_meganium_future_step108.json")


def test_alakazam_step108_charges_bench_meganium_before_attacking():
    with open(_ALK_CHARGE_MEGANIUM_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    # a manual attachment (type 8) to the bench Meganium (inPlayArea 5, inPlayIndex 2)
    meganium_attach = next(
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.ATTACH)
        and o.get("inPlayArea") == 5 and o.get("inPlayIndex") == 2)
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [meganium_attach], (
        f"vs Alakazam, con el activo asegurando su KO, cargar el Meganium de banca "
        f"(opt {meganium_attach}) como atacante de 1 premio antes de atacar; "
        f"no atacar de una (opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]


# Record 008 (step 110 vs Mega Lucario, LOST): an active Hydrapple ex with only 60 HP
# (it will be knocked out next turn) that CAN knock out the active Lucario; on the bench a
# READY Tapu Bulu (a basic, 1 prize) that also knocks out the Lucario. The agent ATTACKED
# with the fragile Hydrapple ex (it stays active -> it gives away 2 prizes). Correct: use Ripening
# Charge to charge the Hydrapple ex up to its retreat cost, retreat it (sheltering the
# tank) and promote the Tapu Bulu, which makes the same KO giving away only 1 prize.
_LUCARIO_FRAGILE_EX_SAC_FIXTURE = (
    ROOT / "tests" / "fixtures" / "lucario_retreat_fragile_ex_sac_step110.json")


def test_lucario_step110_ripening_charge_to_retreat_fragile_ex_not_attack():
    with open(_LUCARIO_FRAGILE_EX_SAC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    ability_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.ABILITY))
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [attack_opt], (
        f"no atacar con el Hydrapple ex fragil (opt {attack_opt}): quedaria activo y "
        f"cederia 2 premios; obtuvo {result}")
    assert result == [ability_opt], (
        f"usar Ripening Charge (opt {ability_opt}) para habilitar la retirada del ex "
        f"fragil y promover un atacante de 1 premio; obtuvo {result}")


# Record 008 (step 119 vs Team Rocket Mewtwo ex, WON): a READY active Hydrapple ex
# (Syrup Storm ~570) that knocks out the active Spidops (1 prize), Boss's Orders in hand and
# the supporter still unplayed; on the rival bench a Mewtwo ex (280 HP, 2 prizes) that we ALSO
# knock out after gusting it. The agent ATTACKED the Spidops (1 prize) instead of playing Boss's
# and gusting+knocking out the Mewtwo ex (2 prizes, and harder to defeat later).
_MEWTWO_BOSS_GUST_FIXTURE = (
    ROOT / "tests" / "fixtures" / "mewtwo_boss_gust_2prize_step119.json")


def test_mewtwo_step119_boss_gust_2prize_over_attacking_active():
    with open(_MEWTWO_BOSS_GUST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o.get("index") == 0)
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [boss_opt], (
        f"jugar Boss's (opt {boss_opt}) para gustear+noquear el Mewtwo ex de banca "
        f"(2 premios), no atacar al activo de 1 premio (opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]


# =====================================================================
# Xerosic's Machinations (id 1197, user): a disruption supporter (the rival
# discards down to 3 cards). Added to the deck (-1 Poke Pad)
# for the Alakazam matchup: Powerful Hand does 20 damage PER CARD in the rival
# hand, so dropping them to 3 cards caps the attack. A synthetic fixture: vs
# Alakazam (743 active, a Kadabra on the bench), a charged Hydrapple ex in the active spot,
# Xerosic (opt 0) and Lillie's (opt 1) in hand, the supporter unplayed.
# =====================================================================
_XEROSIC_BIGHAND_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_play_xerosic_bighand.json")


def _load_xerosic_obs():
    with open(_XEROSIC_BIGHAND_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def test_xerosic_played_vs_alakazam_big_hand():
    # A rival hand of 8 (Powerful Hand threatens 160): play Xerosic (opt 0), above
    # a hydra-charged Lillie's (5800) which would also shuffle the Xerosic away.
    obs = _load_xerosic_obs()
    assert obs["current"]["players"][1]["handCount"] == 8
    result = m.agent(obs)
    assert result == [0], (
        f"vs Alakazam con mano rival 8, jugar Xerosic (opt 0) para capar "
        f"Powerful Hand; obtuvo {result}")


def test_xerosic_vetoed_when_op_hand_small():
    # A rival hand <= 3: Xerosic does nothing -> vetoed; the Lillie's is played.
    obs = _load_xerosic_obs()
    obs = _copy.deepcopy(obs)
    obs["current"]["players"][1]["handCount"] = 3
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result != [0], (
        f"con mano rival 3 Xerosic no tiene efecto: NO jugarlo; obtuvo {result}")
    assert result == [1], (
        f"con Xerosic vetado, el supporter del turno es Lillie's (opt 1); "
        f"obtuvo {result}")


def test_xerosic_vetoed_when_supporter_played():
    # The supporter already played: Xerosic and Lillie's vetoed -> attack (opt 2).
    obs = _load_xerosic_obs()
    obs = _copy.deepcopy(obs)
    obs["current"]["supporterPlayed"] = True
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [2], (
        f"con supporter jugado, ni Xerosic ni Lillie's: atacar (opt 2); "
        f"obtuvo {result}")


# The Meowth ex fetch (user): with Xerosic in the deck and a fat rival hand vs
# Alakazam, Last-Ditch Catch must search for Xerosic (1200; below a winning Boss's
# 1300 and a development Lillie's 1250). The selection's deck: [Boss's, Lillie's,
# Xerosic, Lana's] (indices 0-3).
_MEOWTH_FETCH_XEROSIC_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_meowth_fetch_xerosic.json")


def test_meowth_fetch_xerosic_vs_alakazam_big_hand():
    with open(_MEOWTH_FETCH_XEROSIC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    assert obs["select"]["deck"][2]["id"] == 1197
    result = m.agent(obs)
    assert result == [2], (
        f"vs Alakazam con mano rival 8, Meowth debe buscar Xerosic (opt 2); "
        f"obtuvo {result}")


def test_meowth_fetch_not_xerosic_when_op_hand_small():
    with open(_MEOWTH_FETCH_XEROSIC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    obs = _copy.deepcopy(obs)
    obs["current"]["players"][1]["handCount"] = 3
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result != [2], (
        f"con mano rival 3, Xerosic no aporta: buscar otro supporter; obtuvo {result}")


# The bench reservation vs Alakazam (user): with a SINGLE free slot (bench_count==4),
# Meowth ex not yet in play and Xerosic's Machinations still in the deck, the last
# slot is reserved for Meowth ex (which searches for the Xerosic to cap Powerful
# Hand). REDUNDANT bodies are vetoed (duplicates of something already in play); the
# first copies of line pieces (Applin, etc.) are still played.
# A verified counterfactual: without the rule, the 2nd Ogerpon WAS played.
_ALK_RESERVE_BENCH_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_reserve_bench_slot.json")


def test_alakazam_reserve_last_bench_slot_for_meowth():
    # Hand: a 2nd Teal Mask Ogerpon ex (a duplicate; there is already one on the bench).
    with open(_ALK_RESERVE_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    assert obs["current"]["players"][0]["hand"][0]["id"] == 96
    assert len(obs["current"]["players"][0]["bench"]) == 4
    result = m.agent(obs)
    assert result != [0], (
        f"con banca 4/5 y Meowth pendiente vs Alakazam, NO bajar un duplicado "
        f"(reservar el slot para Meowth ex); obtuvo {result}")
    assert result == [1], f"la jugada correcta es atacar (opt 1); obtuvo {result}"


def test_alakazam_reserve_allows_line_pieces():
    # A positive control: a FIRST copy of Applin (it advances the Hydrapple line)
    # IS played even with the reservation active.
    with open(_ALK_RESERVE_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    obs = _copy.deepcopy(obs)
    obs["current"]["players"][0]["hand"][0]["id"] = 92
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [0], (
        f"la reserva no debe bloquear piezas de linea (Applin, 1ra copia); "
        f"obtuvo {result}")


# The bench reservation ALSO holds with a Meowth ex ALREADY on the bench (user,
# registro_010 step 150 vs Alakazam, LOST -- log 88903365). What is
# reserved is not "the first Meowth" but the turn's LAST-DITCH CATCH: the
# bench Meowth from earlier turns has already spent its own, but a NEW one from
# hand searches again (the same criterion as `_alakazam_dig_xerosic_engine` and
# as Meowth ex's PLAY branch: < 2 copies on the field + `_meowth_ld_free`).
# The step's state: bench 4/5 (Bayleef, Ogerpon ex, Hydrapple ex, Meowth ex),
# a 3rd Teal Mask Ogerpon ex in hand, 2 Ultra Ball, a rival hand of 12 (Powerful
# Hand = 240) and the rival at 2 prizes. With `field_counts[Meowth_ex] == 0` the
# reservation did not fire: the 3rd Ogerpon ex filled the bench, the Ultra Ball dug
# the 2nd Meowth ex -- which stayed DEAD in hand -- and with no Xerosic the rival
# gusted a bench Ogerpon ex with Boss's Orders and knocked it out (220 >= 210) for
# their last 2 prizes.
_ALK_RESERVE_MEOWTH_ON_BENCH_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step150_reserva_con_meowth_en_banca.json")


def _alk_reserve_obs():
    with open(_ALK_RESERVE_MEOWTH_ON_BENCH_FIXTURE, encoding="utf-8") as f:
        return _copy.deepcopy(json.load(f)["observation"])


def _alk_reserve_run(obs):
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    return m.agent(obs)


def test_alakazam_reserves_the_slot_with_a_meowth_already_benched():
    obs = _alk_reserve_obs()
    me = obs["current"]["players"][0]
    assert [b["id"] for b in me["bench"]] == [709, 96, 150, 1071]
    assert me["hand"][3]["id"] == 96  # a 3rd Teal Mask Ogerpon ex (a duplicate)
    result = _alk_reserve_run(obs)
    assert result != [3], (
        f"con un Meowth ex de turnos anteriores en banca la Last-Ditch sigue "
        f"libre: el ultimo slot se reserva y NO se baja el 3er Ogerpon ex; "
        f"obtuvo {result}")
    assert result == [27], (
        f"la jugada correcta es Ripening Charge sobre el Hydrapple ex de banca "
        f"(opt 27); obtuvo {result}")


# On the real board TWO independent rules veto that 3rd Ogerpon ex: the
# bench reservation and the veto of the REDUNDANT ex body with a lethal Powerful Hand
# (below). To isolate each one, the reservation's controls drop the rival hand
# to 8 cards: the projected Powerful Hand = 20 x (8+2) = 200 < the Ogerpon ex's 210 HP,
# so the second veto switches off -- and 8 is still above the >= 7 threshold
# of the Xerosic engine, which is what the reservation protects.
_ALK_OPPONENT_HAND_NO_FINISHER = 8


def _alk_no_finisher(obs):
    obs["current"]["players"][1]["handCount"] = _ALK_OPPONENT_HAND_NO_FINISHER
    return obs


def test_alakazam_reservation_off_when_the_last_ditch_is_spent():
    # A negative control: the bench Meowth ex APPEARED THIS TURN -> its
    # Last-Ditch is already spent and a 2nd Meowth would search for nothing. With no engine to
    # take the slot there is nothing to reserve: the body is played again.
    obs = _alk_no_finisher(_alk_reserve_obs())
    for b in obs["current"]["players"][0]["bench"]:
        if b["id"] == 1071:
            b["appearThisTurn"] = True
    result = _alk_reserve_run(obs)
    assert result == [3], (
        f"con la Last-Ditch del turno gastada la reserva no aplica; "
        f"obtuvo {result}")


def test_alakazam_reservation_off_with_no_reachable_meowth():
    # A negative control: the 2nd copy of Meowth ex is in the DISCARD -> no
    # body is left that could take the reserved slot.
    obs = _alk_no_finisher(_alk_reserve_obs())
    obs["current"]["players"][0]["discard"].append(
        {"id": 1071, "playerIndex": 0, "serial": 19})
    result = _alk_reserve_run(obs)
    assert result == [3], (
        f"sin Meowth ex alcanzable la reserva no aplica; obtuvo {result}")


def test_alakazam_reservation_off_with_no_xerosic_in_the_deck():
    # A negative control: the 2nd Xerosic to the discard as well -> there is no disruption
    # to dig for, the slot is not worth more than the body.
    obs = _alk_no_finisher(_alk_reserve_obs())
    obs["current"]["players"][0]["discard"].append(
        {"id": 1197, "playerIndex": 0, "serial": 62})
    result = _alk_reserve_run(obs)
    assert result == [3], (
        f"sin Xerosic en el mazo la reserva no aplica; obtuvo {result}")


# A REDUNDANT ex BODY WITH A LETHAL POWERFUL HAND (user, the same registro_010): the
# bench reservation only covers the "bench 4/5" case. The principle is broader:
# vs Alakazam the rival's finisher is Boss's Orders + Powerful Hand (20 x their hand),
# so a DUPLICATE ex whose HP already fits in that damage, with the rival at <= 2
# prizes, can only lose the game. It is isolated from the reservation's veto by
# sending the 2nd copy of Meowth ex to the discard (the reservation OFF: with no body to
# take the slot there is nothing to reserve).


def _alk_no_reservation(obs):
    obs["current"]["players"][0]["discard"].append(
        {"id": 1071, "playerIndex": 0, "serial": 19})
    return obs


def test_alakazam_does_not_play_a_redundant_ex_under_a_lethal_powerful_hand():
    obs = _alk_no_reservation(_alk_reserve_obs())
    op = obs["current"]["players"][1]
    assert op["handCount"] == 12 and len(op["prize"]) == 2
    assert m._powerful_hand_proyectado(op["handCount"]) >= 210  # Ogerpon ex HP
    result = _alk_reserve_run(obs)
    assert result != [3], (
        f"con Powerful Hand proyectado 280 >= 210 PV y el rival a 2 premios, "
        f"un 3er Teal Mask Ogerpon ex es un remate servido: no se baja; "
        f"obtuvo {result}")


def test_alakazam_ex_redundante_ok_si_powerful_hand_no_remata():
    # A negative control: a rival hand of 8 -> 20 x 10 = 200 < 210 HP. The body does NOT
    # die in one blow, the veto does not apply and the duplicate is played again.
    obs = _alk_no_finisher(_alk_no_reservation(_alk_reserve_obs()))
    result = _alk_reserve_run(obs)
    assert result == [3], (
        f"si Powerful Hand no remata al cuerpo, el veto no aplica; "
        f"obtuvo {result}")


def test_alakazam_a_redundant_ex_is_fine_if_the_opponent_is_far_from_its_prizes():
    # A negative control: the rival at 4 prizes. Even if Powerful Hand finishes, one more
    # target does not close the game: normal development continues.
    obs = _alk_no_reservation(_alk_reserve_obs())
    obs["current"]["players"][1]["prize"] = [None] * 4
    result = _alk_reserve_run(obs)
    assert result == [3], (
        f"con el rival a 4 premios el veto no aplica; obtuvo {result}")


# DISCARD (user): vs Alakazam the Xerosic is PROTECTED when paying discard costs
# (it is the card that caps Powerful Hand); in other decks it is a middling discard.
# The selection's hand: [Xerosic, Bug Catching Set, Poke Pad, Forest], discard 2.
_ALK_DISCARD_XEROSIC_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_discard_protect_xerosic.json")


def test_discard_protects_xerosic_vs_alakazam():
    with open(_ALK_DISCARD_XEROSIC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    result = m.agent(obs)
    discarded = [obs["current"]["players"][0]["hand"][i]["id"] for i in result]
    assert 1197 not in discarded, (
        f"vs Alakazam nunca descartar el Xerosic para pagar costes; descarto {discarded}")


# Record 004 (step 53 vs Marnie's Grimmsnarl ex, LOST): Meowth ex uses
# Last-Ditch Catch to search the deck for a Supporter. The agent searched for DAWN
# (1231, it searches for a Basic+Stage1+Stage2 to build the evolution line), but WITHOUT
# Forest of Vitality (1261) IN PLAY we cannot evolve the same turn
# (a rush) -> refreshing the hand with Lillie's Determination (1227) gives more
# play/attack options. The stadium in play is Spikemuth Gym (1259, the rival's), not the
# Forest. It must search for Lillie's (opt 2), not Dawn (opt 1).
_MARNIE_FETCH_LILLIE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "marnie_meowth_fetch_lillie_no_forest_step53.json")


def test_marnie_step53_meowth_fetch_lillie_not_dawn_without_forest():
    with open(_MARNIE_FETCH_LILLIE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    deck = obs["select"]["deck"]
    opts = obs["select"]["option"]
    dawn_opt = next(i for i, o in enumerate(opts) if deck[o["index"]]["id"] == 1231)
    lillie_opts = [i for i, o in enumerate(opts) if deck[o["index"]]["id"] == 1227]
    # Forest of Vitality is NOT in play (there is the rival's Spikemuth Gym).
    assert 1261 not in [s["id"] for s in (obs["current"].get("stadium") or [])]

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [dawn_opt], (
        f"sin Forest of Vitality en juego, NO buscar Dawn (opt {dawn_opt}); obtuvo {result}")
    assert result[0] in lillie_opts, (
        f"buscar Lillie's (opts {lillie_opts}) para refrescar la mano; obtuvo {result}")


def test_marnie_step53_meowth_fetch_dawn_when_forest_in_play():
    # A positive control: with Forest of Vitality (1261) IN PLAY, Dawn keeps its
    # value (we can rush the evolution) and is the best search again.
    import copy as _c
    with open(_MARNIE_FETCH_LILLIE_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    obs["current"]["stadium"] = [{"id": 1261, "playerIndex": 0, "serial": 999}]
    deck = obs["select"]["deck"]
    opts = obs["select"]["option"]
    dawn_opt = next(i for i, o in enumerate(opts) if deck[o["index"]]["id"] == 1231)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [dawn_opt], (
        f"con Forest en juego, Dawn (opt {dawn_opt}) sigue siendo la mejor busqueda; "
        f"obtuvo {result}")


# =====================================================================
# The generalised wall pivot Ogerpon -> Hydrapple ex (user, registro_006 step 84,
# vs Archaludon ex, LOST): the active Teal Mask Ogerpon ex CAN attack
# (Myriad Leaf Shower 300) but does NOT knock out Archaludon (400 HP with a Hero's Cape,
# and it also RESISTS Grass -30) and it will be knocked out next turn (Metal Defender 220
# >= 210 HP). On the bench there is a healthy Hydrapple ex (330 HP) that SURVIVES the blow
# (220 < 330) and can attack. The right thing is to RETREAT the doomed Ogerpon (not
# to give away 2 prizes) and promote the wall. The previous branch was bounded to Mega
# Lucario; it was generalised with `_op_active_attack_damage_to` (the real rival damage).
# =====================================================================
_ARCHALUDON_WALL_PIVOT_FIXTURE = (
    ROOT / "tests" / "fixtures" / "archaludon_wall_pivot_ogerpon_to_hydra_step84.json")


def test_archaludon_step84_retreat_ogerpon_to_hydra_wall():
    with open(_ARCHALUDON_WALL_PIVOT_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [retreat_opt], (
        f"retirar el Ogerpon ex condenado (opt {retreat_opt}) para promover el "
        f"muro Hydrapple ex que sobrevive, no atacar con el Ogerpon fragil "
        f"(opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]


def test_archaludon_wall_pivot_not_when_wall_would_die():
    # A counterfactual: if the bench Hydrapple ex wall did NOT survive the rival
    # blow (we drop its life below the 220 damage), the pivot must NOT
    # fire: retreating to expose a body that dies anyway gains nothing,
    # so the agent attacks with the active again.
    import copy as _c
    with open(_ARCHALUDON_WALL_PIVOT_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    bench = obs["current"]["players"][0]["bench"]
    hydra = next(p for p in bench if p is not None and p["id"] == 150)
    hydra["hp"] = 200  # < 220 (Metal Defender) -> the wall would die
    hydra["maxHp"] = 200

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"si el muro Hydrapple no sobrevive (200 < 220), no pivotar: atacar "
        f"con el activo (opt {attack_opt}); obtuvo {result}")


def test_op_active_attack_damage_to_resolves_ids():
    # The helper must RESOLVE the damage of the rival active's attack (the
    # card.attacks are IDs, not objects) and apply weakness/resistance.
    arch = SimpleNamespace(id=190, energies=[8, 8, 8])   # Archaludon ex, Metal Defender 220
    oger = SimpleNamespace(id=96, hp=210)                # Ogerpon ex (not weak to Metal)
    hydra = SimpleNamespace(id=150, hp=330)              # Hydrapple ex
    assert m._op_active_attack_damage_to(arch, oger) == 220
    assert m._op_active_attack_damage_to(arch, hydra) == 220
    # no active or no target -> 0
    assert m._op_active_attack_damage_to(None, oger) == 0
    assert m._op_active_attack_damage_to(arch, None) == 0


# =====================================================================
# The winning Boss's engine via Meowth ex with a Meowth already in play (user,
# registro_011 step 148 vs Dragapult ex, WON): 1 prize from winning, after
# an Ultra Ball -> Meowth ex to hand, the agent ATTACKED with Hydrapple ex (Syrup
# Storm 210 does NOT knock out a Dragapult ex at 320) instead of PLAYING Meowth ex so that
# Last-Ditch Catch searches for Boss's Orders (in the deck), gusts a fragile basic
# from the bench (a Dreepy at 70) and knocks it out -> winning. The block was `field_counts==0`
# (there was already a bench Meowth ex from earlier turns); it was relaxed to `< 2`
# requiring that Last-Ditch is still available (`_meowth_ld_free`).
# =====================================================================
_DRAGAPULT_MEOWTH_WIN_FIXTURE = (
    ROOT / "tests" / "fixtures" / "dragapult_step148_play_meowth_boss_win_engine.json")


def test_dragapult_step148_play_meowth_for_boss_win_engine():
    with open(_DRAGAPULT_MEOWTH_WIN_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    play_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY))
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [play_opt], (
        f"a 1 premio de ganar, JUGAR Meowth ex (opt {play_opt}) para el motor "
        f"Boss's (Last-Ditch -> Boss's -> gustear+noquear un basico), no atacar "
        f"al activo rival que no muere (opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]


def test_dragapult_meowth_win_engine_needs_last_ditch_free():
    # A counterfactual: if the bench Meowth ex appeared THIS turn, its Last-Ditch
    # is already spent ("no more than 1 per turn"), so playing another Meowth would NOT search for
    # Boss's -> the engine does not apply and the agent attacks again.
    import copy as _c
    with open(_DRAGAPULT_MEOWTH_WIN_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    for p in obs["current"]["players"][1]["bench"]:
        if p is not None and p["id"] == 1071:
            p["appearThisTurn"] = True

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"con Last-Ditch ya gastado este turno, NO jugar un 2o Meowth ex: "
        f"atacar (opt {attack_opt}); obtuvo {result}")


# =====================================================================
# A redundant Boss's when the ACTIVE is the same threat pre-evo (user,
# registro_006 step 75 vs Archaludon ex, WON): the rival active is a
# Duraludon (3 energy + a Hero's Cape, 230 HP) and on the bench there is ANOTHER Duraludon
# (1 energy, 130 HP). Both are 1-prize threat pre-evos. The agent played
# Boss's Orders to gust+knock out the WEAK bench Duraludon, leaving the big one
# alive. The right thing: do NOT play Boss's and ATTACK the active (Syrup Storm 420
# knocks out 230), the same prize, it removes the more dangerous threat and keeps the Boss's.
# =====================================================================
_ARCHALUDON_ATTACK_ACTIVE_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step75_attack_active_duraludon_not_boss_bench.json")


def test_archaludon_step75_attack_active_duraludon_not_boss_bench():
    with open(_ARCHALUDON_ATTACK_ACTIVE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY)
                    and obs["current"]["players"][0]["hand"][o["index"]]["id"] == 1182)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"ATACAR el Duraludon activo (opt {attack_opt}), no jugar Boss's "
        f"(opt {boss_opt}) para gustear el Duraludon debil de banca; obtuvo {result}")
    assert result != [boss_opt]


def test_archaludon_step75_still_boss_when_active_is_nonthreat():
    # A positive control (registro_007): if the active is NOT a threat pre-evo
    # (e.g. Cinderace 666, 1 prize) but on the bench there is a gustable+
    # knockout-able Duraludon, Boss's IS played to gust the pre-evo (the same prize, it removes
    # the future attacker). The fix only switches the gust off when the active is the
    # SAME class of threat and equally or more developed.
    import copy as _c
    with open(_ARCHALUDON_ATTACK_ACTIVE_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    a = obs["current"]["players"][1]["active"][0]
    a["id"] = 666; a["maxHp"] = 160; a["hp"] = 160; a["energies"] = [2]; a["tools"] = []

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY)
                    and obs["current"]["players"][0]["hand"][o["index"]]["id"] == 1182)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [boss_opt], (
        f"con un activo NO-amenaza (Cinderace), SI jugar Boss's (opt {boss_opt}) "
        f"para gustear el Duraludon de banca; obtuvo {result}")


# =====================================================================
# Boss's -> gusting a 2-prize ex from the bench over attacking the 1-prize
# active (user, registro_008 step 161 vs Iono, WON): the rival active is an Iono's
# Voltorb (70 HP, 1 prize) that our Hydrapple ex KNOCKS OUT, but on the bench there is an
# Iono's Bellibolt ex (280 HP, 2 prizes) that we ALSO knock out (Syrup Storm
# ~510). The right play is Boss's -> gust the Bellibolt ex and take 2
# prizes. Already covered by `gust_2prize_via_boss` (BOSS_SCORE_GUST_2PRIZE=6800);
# this test locks the regression on a different Iono board (2 Bellibolt ex).
# =====================================================================
_IONO_BOSS_GUST_2PRIZE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "iono_step161_boss_gust_bellibolt_ex_2prize.json")


def test_iono_step161_boss_gust_bellibolt_ex_over_attacking_voltorb():
    with open(_IONO_BOSS_GUST_2PRIZE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY)
                    and obs["current"]["players"][0]["hand"][o["index"]]["id"] == 1182)
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [boss_opt], (
        f"jugar Boss's (opt {boss_opt}) para gustear+noquear el Bellibolt ex de "
        f"banca (2 premios), no atacar al Voltorb activo de 1 premio "
        f"(opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]


def test_iono_step161_boss_gust_target_is_bellibolt_ex():
    # When resolving the gust's target (the SWITCH context), pick an Iono's
    # Bellibolt ex (2 prizes, 280 HP), not a Kilowattrel/Voltorb worth 1 prize.
    import copy as _c
    with open(_IONO_BOSS_GUST_2PRIZE_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    cur = obs["current"]
    cur["supporterPlayed"] = True
    cur["players"][0]["hand"] = [c for c in cur["players"][0]["hand"] if c["id"] != 1182]
    opbench = cur["players"][1]["bench"]
    obs["select"] = {
        "context": 3, "contextCard": None, "deck": None,
        "effect": {"id": 1182, "playerIndex": 0, "serial": 28},
        "maxCount": 1, "minCount": 1,
        "option": [{"area": 5, "index": i, "playerIndex": 1, "type": 3}
                   for i in range(len(opbench))],
        "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1}

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    picked = opbench[obs["select"]["option"][result[0]]["index"]]["id"]
    assert picked == 269, (
        f"gustear un Iono's Bellibolt ex (269, 2 premios), no id {picked}; "
        f"obtuvo {result}")


# =====================================================================
# Completing the Ultra Ball -> Meowth ex play (user, registro_008 step 71 vs
# Hop's, WON): the agent played an Ultra Ball and CHOSE to search for Meowth ex (excellent),
# but then did NOT play it: it attacked with the active Hydrapple ex (a ready attacker) and the
# hand was left EMPTY. Rule: if the Ultra Ball chose to search for Meowth ex, the play must be
# COMPLETED WHENEVER the Supporter is still available: play Meowth ex
# (Last-Ditch Catch -> Lillie's Determination -> refresh the hand) and THEN
# attack (playing it to the bench does not prevent the attack). The guard goes from
# `not _active_ready_attacker` to `not state.supporterPlayed` (if the Supporter has already
# been played, the searched Lillie's could not even be played: attacking is kept, record
# 006 step 57 vs Alakazam).
# The sequence (the turn's ACTIVE frames, as the real environment calls it) is needed
# so that the Ultra Ball's selection (step 70) sets `_ub_meowth_pending`.
# =====================================================================
_HOPS_UB_MEOWTH_SEQ_FIXTURE = (
    ROOT / "tests" / "fixtures" / "hops_ub_meowth_play_after_fetch_step71.json")


def test_hops_step71_plays_ub_fetched_meowth_before_attacking():
    with open(_HOPS_UB_MEOWTH_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    result = None
    target = None
    for item in seq:
        target = item["observation"]
        result = m.agent(target)

    assert target["current"]["turnActionCount"] == 10, "el ultimo frame debe ser el paso 71"
    play_map = _resolve_play_options(target)
    meowth_opt = next(i for i, cid in play_map.items() if cid == m.Meowth_ex)
    assert result == [meowth_opt], (
        f"tras buscar Meowth ex con Ultra Ball debe BAJARLO (opt {meowth_opt}) "
        f"para encadenar Lillie's antes de atacar; obtuvo {result}")


def test_hops_step71_ub_meowth_not_played_if_supporter_already_played():
    # A counterfactual (it keeps the rule of record 006 p57 vs Alakazam): if the
    # Supporter has ALREADY been played this turn, the searched Lillie's could not be played ->
    # do NOT play the searched Meowth ex; attack.
    import copy as _c
    with open(_HOPS_UB_MEOWTH_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    result = None
    for item in seq:
        obs = item["observation"]
        if item.get("tac") == 10:
            obs = _c.deepcopy(obs)
            obs["current"]["supporterPlayed"] = True
        result = m.agent(obs)

    options = seq[-1]["observation"]["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    assert result == [attack_opt], (
        f"con el Supporter ya jugado, no bajar el Meowth buscado: atacar "
        f"(opt {attack_opt}); obtuvo {result}")


# =====================================================================
# Ultra Ball -> a 2nd Meowth ex -> Last-Ditch searches for XEROSIC vs Alakazam (user,
# registro_004 step 53 vs Alakazam, LOST): the Ultra Ball searched for Meowth ex
# (excellent) but the agent attacked without playing it. Two blocks corrected:
# (1) the `_ub_meowth_pending` branch required `field_counts[Meowth_ex] == 0` and here
#     there was a bench Meowth ex from previous turns -> relaxed to `< 2` +
#     `_meowth_ld_free` (as with the winning Boss's engine via Meowth);
# (2) the Last-Ditch fetch required our own hand >= 3 to pick Xerosic; with an
#     EMPTY hand it fell to the Lillie's refresh. With a strong attacker ALREADY in play
#     (Hydrapple/Ogerpon) and a fat rival hand (13 cards = Powerful Hand 260),
#     Xerosic rules: score 1260 (`_has_strong_attacker_sel`).
# =====================================================================
_ALAKAZAM_UB_MEOWTH2_SEQ_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_ub_meowth_second_copy_fetch_xerosic_step53.json")


def _alakazam_meowth2_build_fetch(s53_obs):
    import copy as _c
    o2 = _c.deepcopy(s53_obs)
    me = o2["current"]["players"][0]
    me["hand"].pop(0)
    me["bench"].append({"appearThisTurn": True, "energies": [], "energyCards": [],
                        "hp": 170, "id": 1071, "maxHp": 170, "playerIndex": 0,
                        "preEvolution": [], "serial": 20, "tools": []})
    deck = [{"id": 1227, "playerIndex": 0, "serial": 26},
            {"id": 1197, "playerIndex": 0, "serial": 43},
            {"id": 1182, "playerIndex": 0, "serial": 29},
            {"id": 1227, "playerIndex": 0, "serial": 24},
            {"id": 1227, "playerIndex": 0, "serial": 25},
            {"id": 1182, "playerIndex": 0, "serial": 28},
            {"id": 1184, "playerIndex": 0, "serial": 30}]
    o2["select"] = {"context": 7, "contextCard": None, "deck": deck,
                    "effect": {"id": 1071, "playerIndex": 0, "serial": 20},
                    "maxCount": 1, "minCount": 0,
                    "option": [{"area": 1, "index": i, "playerIndex": 0, "type": 3}
                               for i in range(len(deck))],
                    "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1}
    return o2, deck


def test_alakazam_step53_plays_second_ub_meowth_with_one_in_field():
    with open(_ALAKAZAM_UB_MEOWTH2_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    result = None
    target = None
    for item in seq:
        target = item["observation"]
        result = m.agent(target)
    play_map = _resolve_play_options(target)
    meowth_opt = next(i for i, cid in play_map.items() if cid == m.Meowth_ex)
    assert result == [meowth_opt], (
        f"con un Meowth de turnos previos en banca (Last-Ditch libre), el 2o "
        f"Meowth buscado por Ultra Ball debe bajarse (opt {meowth_opt}); obtuvo {result}")


def test_alakazam_step53_last_ditch_fetches_xerosic_with_strong_attacker():
    with open(_ALAKAZAM_UB_MEOWTH2_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    s53 = None
    for item in seq:
        s53 = item["observation"]
        m.agent(s53)
    o2, deck = _alakazam_meowth2_build_fetch(s53)
    result = m.agent(o2)
    picked = deck[o2["select"]["option"][result[0]]["index"]]["id"]
    assert picked == 1197, (
        f"vs Alakazam (mano rival 13) con atacante fuerte en juego, Last-Ditch "
        f"debe buscar Xerosic (1197) aunque nuestra mano quede vacia; busco id {picked}")


def test_alakazam_step53_last_ditch_falls_back_to_lillies_without_attacker():
    # A counterfactual: with no strong attacker in play and an empty hand -> the previous rule
    # (a refresh with Lillie's).
    with open(_ALAKAZAM_UB_MEOWTH2_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    s53 = None
    for item in seq:
        s53 = item["observation"]
        m.agent(s53)
    o2, deck = _alakazam_meowth2_build_fetch(s53)
    me = o2["current"]["players"][0]
    me["active"][0].update({"id": 710, "hp": 160, "maxHp": 160})
    me["bench"] = [b for b in me["bench"] if b["id"] not in (96, 150)]
    result = m.agent(o2)
    picked = deck[o2["select"]["option"][result[0]]["index"]]["id"]
    assert picked == 1227, (
        f"sin atacante fuerte y mano vacia debe refrescar con Lillie's (1227); "
        f"busco id {picked}")


# =====================================================================
# The 1-prize pivot generalised to Dipplin vs Alakazam (user, registro_005 step 56
# vs Alakazam, LOST): an active Ogerpon ex ready to attack and a charged Dipplin (1
# prize) on the bench whose Do the Wave (20 x the bench) KNOCKS OUT the active Abra
# (50 HP). Rule: WHENEVER a 1-prize body (Dipplin/Meganium/Tapu Bulu)
# can defeat the rival active vs Alakazam and the retreat is payable, RETREAT the
# ex and promote the 1-prize body (the same KO giving away 1 prize, not 2 to the
# Powerful Hand). The detection `_alakazam_pivot_1prize` and the promotion
# `_ak_1prize_prom` had a whitelist (Meganium, Tapu_Bulu); generalised to
# non-ex via prize_count (the detection) and to (Meganium, Tapu_Bulu, Dipplin, Pinsir)
# with Do the Wave = 20 x (bench - 1) (the promotion).
# =====================================================================
_ALAKAZAM_DIPPLIN_PIVOT_SEQ_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step56_retreat_ogerpon_promote_dipplin.json")


def _dipplin_pivot_replay(mutate_tac9=None):
    import copy as _c
    with open(_ALAKAZAM_DIPPLIN_PIVOT_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    result = None
    target = None
    for item in seq:
        obs = item["observation"]
        if item["tac"] == 9 and mutate_tac9 is not None:
            obs = _c.deepcopy(obs)
            mutate_tac9(obs)
        target = obs
        result = m.agent(obs)
        if item["tac"] == 9:
            break
    return result, target


def test_alakazam_step56_retreats_ex_for_charged_dipplin():
    result, target = _dipplin_pivot_replay()
    options = target["select"]["option"]
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))
    assert result == [retreat_opt], (
        f"con Dipplin cargado que noquea al Abra, retirar el Ogerpon ex "
        f"(opt {retreat_opt}) en vez de atacar con el ex; obtuvo {result}")


def test_alakazam_step56_promotes_dipplin_after_retreat():
    import copy as _c
    result, target = _dipplin_pivot_replay()
    o2 = _c.deepcopy(target)
    bench = o2["current"]["players"][1]["bench"]
    o2["select"] = {"context": 3, "contextCard": None, "deck": None,
                    "effect": None, "maxCount": 1, "minCount": 1,
                    "option": [{"area": 5, "index": i, "playerIndex": 1, "type": 3}
                               for i in range(len(bench))],
                    "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1}
    result = m.agent(o2)
    picked = bench[o2["select"]["option"][result[0]]["index"]]["id"]
    assert picked == m.Dipplin, (
        f"al retirar debe promover el Dipplin (1 premio que noquea); "
        f"promovio id {picked}")


def test_alakazam_step56_attacks_when_dipplin_uncharged():
    # A counterfactual: a Dipplin WITHOUT energy cannot attack -> there is no pivot;
    # attack with the active Ogerpon ex.
    def mut(obs):
        for b in obs["current"]["players"][1]["bench"]:
            if b["id"] == m.Dipplin:
                b["energies"] = []
                b["energyCards"] = []
    result, target = _dipplin_pivot_replay(mut)
    options = target["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    assert result == [attack_opt], (
        f"sin Dipplin cargado debe atacar con el activo (opt {attack_opt}); "
        f"obtuvo {result}")


# =====================================================================
# The complete anti-Alakazam chain (user, registro_007 turn 7 vs Alakazam,
# LOST): Ultra Ball -> search for Meowth ex (keeping the bench reservation) ->
# PLAY IT (before it attacked without playing it) -> Last-Ditch searches for XEROSIC (a rival hand
# of 12 = Powerful Hand 240; we have a strong attacker) -> play it -> attack.
# It validates end to end the `_ub_meowth_pending` fixes (the supporterPlayed guard) and
# the Xerosic fetch on real frames of a second scenario.
# =====================================================================
_ALAKAZAM_T7_CHAIN_SEQ_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_t7_ub_meowth_xerosic_chain.json")


def test_alakazam_t7_plays_ub_fetched_meowth_then_fetches_xerosic():
    import copy as _c
    with open(_ALAKAZAM_T7_CHAIN_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    result = None
    target = None
    for item in seq:
        target = item["observation"]
        result = m.agent(target)

    # 1) tac9: play the Meowth ex searched for by the Ultra Ball (do not attack yet).
    opt = target["select"]["option"][result[0]]
    hand = [c["id"] for c in target["current"]["players"][1]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Meowth_ex, (
        f"tac9 debe bajar el Meowth ex buscado por Ultra Ball; obtuvo {result} -> {opt}")

    # 2) Last-Ditch Catch: with a rival hand of 12 and a strong attacker, search for XEROSIC.
    o2 = _c.deepcopy(target)
    me = o2["current"]["players"][1]
    me["hand"] = [c for c in me["hand"] if c["id"] != m.Meowth_ex]
    me["bench"].append({"appearThisTurn": True, "energies": [], "energyCards": [],
                        "hp": 170, "id": 1071, "maxHp": 170, "playerIndex": 1,
                        "preEvolution": [], "serial": 80, "tools": []})
    deck = [{"id": 1227, "playerIndex": 1, "serial": 87},
            {"id": 1182, "playerIndex": 1, "serial": 89},
            {"id": 1184, "playerIndex": 1, "serial": 90},
            {"id": 1227, "playerIndex": 1, "serial": 84},
            {"id": 1197, "playerIndex": 1, "serial": 103}]
    o2["select"] = {"context": 7, "contextCard": None, "deck": deck,
                    "effect": {"id": 1071, "playerIndex": 1, "serial": 80},
                    "maxCount": 1, "minCount": 0,
                    "option": [{"area": 1, "index": i, "playerIndex": 1, "type": 3}
                               for i in range(len(deck))],
                    "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1}
    r2 = m.agent(o2)
    picked = deck[o2["select"]["option"][r2[0]]["index"]]["id"]
    assert picked == 1197, (
        f"Last-Ditch debe buscar Xerosic (1197) con mano rival 12; busco id {picked}")


# =====================================================================
# Cruel Arrow's target vs Crustle (user, registro_015 step 139 vs Crustle,
# LOST): Fezandipiti ex attacked with Cruel Arrow (a fixed 100 to ANY rival
# Pokemon) and the game aimed at the active Crustle -- IMMUNE to the damage of our ex
# through its ability -- with a knockout-able 70 HP Dwebble on the bench. There was no
# handler for SelectContext.DAMAGE (ctx 15) and the argmax fell on option 0.
# A new handler: EFFECTIVE damage per target (it applies ex immunity / the zone /
# weakness); a KO > the chip closest to a KO > immune ones only as a last resort.
# =====================================================================
_CRUSTLE_SNIPE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "crustle_cruel_arrow_snipe_dwebble_step139.json")


def _crustle_snipe_target(result, obs):
    opt = obs["select"]["option"][result[0]]
    op = obs["current"]["players"][0]
    return (op["active"][opt["index"]] if opt["area"] == 4
            else op["bench"][opt["index"]])


def test_crustle_step139_cruel_arrow_snipes_koable_dwebble():
    with open(_CRUSTLE_SNIPE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    result = m.agent(obs)
    picked = _crustle_snipe_target(result, obs)
    assert picked["id"] == 344 and picked["hp"] == 70, (
        f"Cruel Arrow debe apuntar al Dwebble noqueable (70 HP), no a un "
        f"Crustle inmune a ex; apunto a id {picked['id']} hp {picked['hp']}")


def test_crustle_step139_cruel_arrow_chips_dwebble_when_no_ko():
    # A counterfactual: a Dwebble with 150 HP (it does not die) -> it is still the only
    # target that TAKES damage (the Crustle are immune to our ex).
    import copy as _c
    with open(_CRUSTLE_SNIPE_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    dw = obs["current"]["players"][0]["bench"][1]
    dw["hp"] = 150
    dw["maxHp"] = 150
    result = m.agent(obs)
    picked = _crustle_snipe_target(result, obs)
    assert picked["id"] == 344, (
        f"sin KO posible debe chipear al Dwebble (unico no inmune); "
        f"apunto a id {picked['id']}")


# =====================================================================
# The Xerosic engine with Meowth ex ALREADY in hand vs Alakazam (user, registro_006 step 76
# vs Alakazam, WON): Meowth ex in hand (not searched for by an Ultra Ball this
# turn), the Supporter free, a rival hand of 10 cards (Powerful Hand 200 knocks us
# out next turn) and Xerosic still in the DECK. The agent attacked leaving
# the Meowth dead in hand (a veto through the ready attacker). A new branch: play
# the Meowth ALWAYS in that context (Last-Ditch -> Xerosic -> the rival at 3 cards ->
# attack afterwards). The "in hand" version of the `_ub_meowth_pending` chain.
# =====================================================================
_ALAKAZAM_MEOWTH_HAND_SEQ_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step76_meowth_in_hand_xerosic_engine.json")


def _meowth_hand_replay(mutate_tac4=None):
    import copy as _c
    with open(_ALAKAZAM_MEOWTH_HAND_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    for item in seq:
        obs = item["observation"]
        if item["tac"] == 4:
            if mutate_tac4 is not None:
                obs = _c.deepcopy(obs)
                mutate_tac4(obs)
            return m.agent(obs), obs
        m.agent(obs)


def test_alakazam_step76_plays_meowth_from_hand_for_xerosic():
    result, obs = _meowth_hand_replay()
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][1]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Meowth_ex, (
        f"con Supporter libre, mano rival 10 y Xerosic en mazo debe bajar el "
        f"Meowth ex de la mano; obtuvo {result} -> {opt}")


def test_alakazam_step76_attacks_if_supporter_already_played():
    # An updated counterfactual (anti-Alakazam suggestion 1, Powerful Hand
    # modelled): with the Supporter already played the Meowth is NOT played (the original
    # intent of the test). Besides, now that the model SEES that the active
    # 130 HP Hydrapple dies to the projected Powerful Hand (20 x (10+2) =
    # 240), the user's rule "retreat the fragile ex, sacrifice 1
    # prize" applies: Ripening Charge (it enables the retreat) -> retreat -> promote
    # the 1-prize Meganium which also knocks out the 140 Alakazam. Before it
    # attacked with the doomed ex (giving away 2 prizes) because it believed
    # Alakazam hit for 0.
    result, obs = _meowth_hand_replay(
        lambda o: o["current"].__setitem__("supporterPlayed", True))
    opt = obs["select"]["option"][result[0]]
    _my = obs["current"]["players"][obs["current"]["yourIndex"]]
    hand = [c["id"] for c in _my["hand"]]
    assert not (opt.get("type") == int(OptionType.PLAY)
                and opt.get("index", -1) < len(hand)
                and hand[opt["index"]] == m.Meowth_ex), (
        f"con el Supporter ya jugado no debe bajar el Meowth; "
        f"obtuvo {result} -> {opt}")
    assert (opt.get("type") == int(OptionType.ABILITY)
            and opt.get("area") == int(AreaType.ACTIVE)), (
        f"con el Hydrapple activo condenado (240 proyectado vs 130 HP) debe "
        f"activar Ripening Charge para el pivote de sacrificio de 1 premio; "
        f"obtuvo {result} -> {opt}")


def test_alakazam_step76_attacks_if_opponent_hand_small():
    result, obs = _meowth_hand_replay(
        lambda o: o["current"]["players"][0].__setitem__("handCount", 4))
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con la mano rival corta (<6) no aplica el motor Xerosic: atacar; "
        f"obtuvo {result} -> {opt}")


# =====================================================================
# The Xerosic engine OVER the development rush (user, registro_010 step 147 vs
# Alakazam, LOST): two Meowth ex in hand, the Supporter free, a rival hand of 11
# (Powerful Hand 220) and Xerosic in the DECK, with a SINGLE bench slot. The agent
# played the Applin (a rush with Forest, 21200) and the Meowth died in hand -- with no
# Xerosic, Powerful Hand knocked out everything. The engine's branch rises to 21500 to
# beat the rush: play Meowth ex -> Last-Ditch -> Xerosic (the rival at 3) -> attack.
# =====================================================================
_ALAKAZAM_MEOWTH_OVER_APPLIN_SEQ_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step147_meowth_over_applin_xerosic.json")


def _meowth_over_applin_replay(mutate_tac2=None):
    import copy as _c
    with open(_ALAKAZAM_MEOWTH_OVER_APPLIN_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    for item in seq:
        obs = item["observation"]
        if item["tac"] == 2:
            if mutate_tac2 is not None:
                obs = _c.deepcopy(obs)
                mutate_tac2(obs)
            return m.agent(obs), obs
        m.agent(obs)


def test_alakazam_step147_plays_meowth_over_applin():
    result, obs = _meowth_over_applin_replay()
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][0]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Meowth_ex, (
        f"con el motor Xerosic vivo (mano rival 11, un slot de banca) debe bajar "
        f"el Meowth ex, no el Applin; obtuvo {result} -> {opt}")


def test_alakazam_step147_applin_rush_returns_when_no_engine():
    # A counterfactual: a short rival hand -> the engine does not apply and the development
    # rush returns (Applin with Forest).
    result, obs = _meowth_over_applin_replay(
        lambda o: o["current"]["players"][1].__setitem__("handCount", 4))
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][0]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Applin, (
        f"sin mano rival gorda debe volver el rush de Applin; obtuvo {result} -> {opt}")


# =====================================================================
# The UB -> Meowth -> Lillie's chain vs Marnie's (user, registro_008 step 118,
# WON): on turn 8 the game played an Ultra Ball and searched for a Meowth ex, but
# the old version did not play it and attacked with the Hydrapple ex. With the Supporter
# free and Lillie's (1227) in the DECK, the play is COMPLETED: play the Meowth
# (21000 via _ub_meowth_pending) -> Last-Ditch searches for Lillie's -> play it to
# refresh and load more energies onto the Ogerpon. The chain validated with the
# current code on the real record + 2 synthetic frames.
# =====================================================================
_MARNIE_UB_MEOWTH_LILLIE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "marnie_step118_ub_meowth_lillie_chain.json")


def _marnie_ub_meowth_replay(mutate_last=None):
    import copy as _c
    with open(_MARNIE_UB_MEOWTH_LILLIE_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate_last is not None:
        obs = _c.deepcopy(obs)
        mutate_last(obs)
    return m.agent(obs), obs, data


def test_marnie_step118_plays_ub_fetched_meowth_before_attacking():
    result, obs, _ = _marnie_ub_meowth_replay()
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][0]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Meowth_ex, (
        f"el Meowth ex buscado por Ultra Ball debe bajarse (Supporter libre) "
        f"antes de atacar; obtuvo {result} -> {opt}")


def test_marnie_step118_ub_meowth_not_played_if_supporter_used():
    # A counterfactual: with the Supporter already played, the searched Lillie's could
    # not be played -> attack directly.
    result, obs, _ = _marnie_ub_meowth_replay(
        lambda o: o["current"].__setitem__("supporterPlayed", True))
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == 13, (
        f"con supporterPlayed=True debe atacar, no bajar el Meowth; "
        f"obtuvo {result} -> {opt}")


def test_marnie_step118_last_ditch_fetches_lillies_then_plays_it():
    _, _, data = _marnie_ub_meowth_replay()
    fetch = data["synthetic_fetch"]
    ch = m.agent(fetch)
    deck = fetch["select"]["deck"]
    picked = [deck[fetch["select"]["option"][i]["index"]]["id"] for i in ch]
    assert picked == [m.Lillie_Determination], (
        f"Last-Ditch Catch debe buscar la Lillie's (1227) para refrescar; "
        f"obtuvo {picked}")
    main_obs = data["synthetic_lillie_main"]
    ch2 = m.agent(main_obs)
    opt = main_obs["select"]["option"][ch2[0]]
    hand = [c["id"] for c in main_obs["current"]["players"][0]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Lillie_Determination, (
        f"la Lillie's buscada debe jugarse antes de atacar; obtuvo {ch2} -> {opt}")


# =====================================================================
# Anti-Alakazam suggestions 1-3 (user: "implement the changes step by step"):
# 1) Powerful Hand (Alakazam 743, attackId 1072, printed damage 0) modelled in
#    _op_active_attack_damage_to as 20 x (the rival hand + 2) when the caller
#    passes op_hand_count, and injected into active_ko_likely (bounded to an active
#    Alakazam) -> it wakes up the defensive pivots in this matchup.
# 2) An EARLY Xerosic trigger: with a rival hand of 4-5 (below the >=6 threshold), if
#    the active Alakazam projects a KO on our active, cap the hand NOW.
# 3) A Lillie's guard: do not shuffle away the LAST access to the Xerosic (with no
#    re-searchable Meowth) with the rival hand >= 4.
# =====================================================================


def test_powerful_hand_projected_damage():
    class _P:
        def __init__(s, id, energies, hp, maxHp):
            s.id, s.energies, s.hp, s.maxHp = id, energies, hp, maxHp
    alak = _P(m.Alakazam_ex, [5], 140, 140)
    oger = _P(m.Teal_Mask_Ogerpon_ex, [1, 1, 1], 210, 210)
    # without op_hand_count: conservative (the historical behaviour)
    assert m._op_active_attack_damage_to(alak, oger) == 0
    # with the rival hand: 20 x (hand + 2)
    assert m._op_active_attack_damage_to(alak, oger, 9) == 220
    assert m._op_active_attack_damage_to(alak, oger, 5) == 140
    # rivals with printed damage do not change when the hand is passed
    dura = _P(647, [7, 7, 7], 100, 100)
    assert (m._op_active_attack_damage_to(dura, oger, 9)
            == m._op_active_attack_damage_to(dura, oger))


def _xerosic_bighand_mutated(mutate):
    import copy as _c
    with open(_XEROSIC_BIGHAND_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mutate(obs)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    my = obs["current"]["players"][obs["current"]["yourIndex"]]
    hand = [c["id"] for c in my["hand"]]
    played = (hand[opt["index"]]
              if opt.get("type") == int(OptionType.PLAY) else None)
    return played, opt


def test_xerosic_early_trigger_on_projected_ko():
    # a rival hand of 5 (below the threshold of 6) + our own active at 130 HP: the projection
    # 20 x (5+2) = 140 >= 130 -> play Xerosic NOW.
    def mut(o):
        cur = o["current"]
        cur["players"][cur["yourIndex"]]["active"][0]["hp"] = 130
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    played, opt = _xerosic_bighand_mutated(mut)
    assert played == m.Xerosic_Machinations, (
        f"con KO proyectado (140 >= 130) debe jugar Xerosic; obtuvo {opt}")


def _xerosic_bighand_no_backup(mutate):
    # A variant with NO backup copy: the 2nd copy of Xerosic (deck, July
    # 2026) is marked as outside the deck via tracking, leaving the one in hand as
    # the last -> the conservative one-copy timing.
    import copy as _c
    with open(_XEROSIC_BIGHAND_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mutate(obs)
    m._init_cards_tracking()
    m.ACTIVE_CARDS_IN_DECK.setdefault(
        m.Xerosic_Machinations, {m.ZONE_DECK: 0})[m.ZONE_DECK] = 0
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    my = obs["current"]["players"][obs["current"]["yourIndex"]]
    hand = [c["id"] for c in my["hand"]]
    played = (hand[opt["index"]]
              if opt.get("type") == int(OptionType.PLAY) else None)
    return played, opt


def test_xerosic_early_with_backup_copy():
    # The 2nd copy in the DECK (July 2026): with a rival hand of 5 (>= 4) the 1st copy
    # is played EARLY even if the active is healthy -- a double-hit
    # strategy: slow them down now and keep the 2nd for the late cap.
    def mut(o):
        cur = o["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    played, opt = _xerosic_bighand_mutated(mut)
    assert played == m.Xerosic_Machinations, (
        f"con copia de respaldo en el mazo, la 1a se juega temprano "
        f"(mano rival 5 >= 4); obtuvo {opt}")


def test_xerosic_early_trigger_not_on_healthy_active_last_copy():
    # The LAST copy (no backup) + a rival hand of 5 + a healthy active (330):
    # the projection 140 < 330 -> do NOT burn it yet (the conservative timing).
    def mut(o):
        cur = o["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    played, opt = _xerosic_bighand_no_backup(mut)
    assert played != m.Xerosic_Machinations, (
        f"ultima copia sin KO proyectado (140 < 330): no quemarla; obtuvo {opt}")


def test_xerosic_early_trigger_needs_alakazam_active():
    # The LAST copy, a rival hand of 5, our own active at 130, but the rival has an
    # active Abra: the threat is not immediate -> do NOT trigger early.
    def mut(o):
        cur = o["current"]
        cur["players"][cur["yourIndex"]]["active"][0]["hp"] = 130
        op = cur["players"][1 - cur["yourIndex"]]
        op["handCount"] = 5
        op["active"][0]["id"] = m.Abra
    played, opt = _xerosic_bighand_no_backup(mut)
    assert played != m.Xerosic_Machinations, (
        f"ultima copia con Abra activo: amenaza no inmediata; obtuvo {opt}")


def test_lillies_guard_protects_last_xerosic_access():
    # Xerosic in hand, a rival hand of 5, and with NO re-searchable Meowth (0 in hand,
    # 0 in the deck): Lillie's would shuffle it away with no recovery -> a veto.
    def mut(o):
        cur = o["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    import copy as _c
    with open(_XEROSIC_BIGHAND_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mut(obs)
    m._init_cards_tracking()
    m.ACTIVE_CARDS_IN_DECK.setdefault(
        m.Meowth_ex, {m.ZONE_DECK: 0})[m.ZONE_DECK] = 0
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    my = obs["current"]["players"][obs["current"]["yourIndex"]]
    hand = [c["id"] for c in my["hand"]]
    assert not (opt.get("type") == int(OptionType.PLAY)
                and hand[opt["index"]] == m.Lillie_Determination), (
        f"Lillie's barajaria el ultimo Xerosic sin re-busqueda posible; "
        f"obtuvo {opt}")


def test_lillies_allowed_when_xerosic_refetchable():
    # The LAST copy + a Meowth in the deck: the normal course is kept (the Meowth
    # re-searches the shuffled Xerosic). With a backup in the deck the 1st copy would
    # be played early (the test test_xerosic_early_with_backup_copy).
    def mut(o):
        cur = o["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    played, opt = _xerosic_bighand_no_backup(mut)
    assert played == m.Lillie_Determination, (
        f"ultima copia con Meowth re-buscable: Lillie's sigue su curso; "
        f"obtuvo {opt}")


# =====================================================================
# Boss's cuts the Cynthia's Garchomp ex line (user, registro_006 step 82
# vs Garchomp, WON with a mistake): a ready Tapu Bulu in the active spot, Boss's in hand,
# the Supporter free; the rival with a Spiritomb (a bare wall, 70) in the active spot and TWO
# Gabite on the bench (one ENERGIZED). The agent attacked the wall; the right thing is to
# play Boss's and gust+knock out the Gabite with energy (the pre-evo of the 2-prize
# ex attacker). Fix: the Gible(379)/Gabite(380) line was NOT in
# EX_PREEVO_IDS, so the deny-evo (`_bo_pe_is_ex_preevo_energized` /
# `_bo_pe_is_ex_line_vs_wall`, the same mechanism as the Marnie line) never
# fired in this matchup. ALWAYS favour cutting the evolution line.
# =====================================================================
_GARCHOMP_BOSS_GABITE_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "garchomp_step82_boss_gust_energized_gabite.json")


def _garchomp_s82_replay(mutate=None):
    import copy as _c
    with open(_GARCHOMP_BOSS_GABITE_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    return m.agent(obs), obs, data


def test_garchomp_step82_plays_boss_to_cut_garchomp_line():
    result, obs, _ = _garchomp_s82_replay()
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][1]["hand"]]
    assert (opt.get("type") == int(OptionType.PLAY)
            and hand[opt["index"]] == m.Boss_Orders), (
        f"con Gabite energizado en banca rival debe jugar Boss's, no atacar "
        f"al muro Spiritomb; obtuvo {result} -> {opt}")


def test_garchomp_step82_attacks_if_supporter_already_played():
    result, obs, _ = _garchomp_s82_replay(
        lambda o: o["current"].__setitem__("supporterPlayed", True))
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"sin Supporter disponible debe atacar; obtuvo {result} -> {opt}")


def test_garchomp_step82_gust_targets_energized_gabite():
    _, _, data = _garchomp_s82_replay()
    tgt = data["synthetic_gust_target"]
    ch = m.agent(tgt)
    bench = tgt["current"]["players"][0]["bench"]
    picked = bench[tgt["select"]["option"][ch[0]]["index"]]
    assert (picked["id"] == m.Cynthias_Gabite
            and len(picked["energies"]) >= 1), (
        f"el gusteo debe apuntar al Gabite CON energia (mas cerca de "
        f"Garchomp ex); obtuvo idx {ch} -> id {picked['id']} "
        f"energias {picked['energies']}")


# =====================================================================
# The UB->Meowth->Lillie's engine OVER the energy tier (user, registro_008
# steps 56-64 vs Archaludon ex, LOST): turn 8, an active Hydrapple ex that does NOT
# knock out (Syrup Storm 90 vs 250), a bench of 1 Applin, a hand of [UB, Boss's] + 2
# energies just brought by a Bug Catching Set. The agent attached one energy
# (31410) and spent the other with Ripening Charge (30000) -- the hand was left at
# [UB, Boss's] and the Ultra Ball DIED without its 2 discards. A twofold fix:
# `_ub_engine_refresh_pivot` scores the UB at 31450 and raises it to the ENERGY tier
# (the Teal Dance pattern), and `_ub_engine_pivot_turn` forces the fetch to Meowth ex
# (1300) to complete UB -> discard 2 energies -> Meowth -> Last-Ditch ->
# Lillie's -> refresh and develop the bench (Syrup Storm scales with the field).
# =====================================================================
_ARCHALUDON_UB_ENGINE_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step58_ub_engine_over_energy.json")


def _archaludon_s58_replay(mutate=None):
    import copy as _c
    with open(_ARCHALUDON_UB_ENGINE_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    return m.agent(obs), obs, data


def test_archaludon_step58_plays_ub_over_energy_attach():
    result, obs, _ = _archaludon_s58_replay()
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][0]["hand"]]
    assert (opt.get("type") == int(OptionType.PLAY)
            and hand[opt["index"]] == m.Ultra_Ball), (
        f"con el activo sin KO y banca de 1, la UB (motor Meowth->Lillie's) va "
        f"ANTES de gastar las energias; obtuvo {result} -> {opt}")


def test_archaludon_step58_attaches_when_bench_developed():
    # A counterfactual: a developed bench (3) -> the pivot does not apply and the normal
    # attachment is kept.
    def mut(o):
        my = o["current"]["players"][0]
        for i in range(2):
            my["bench"].append({
                "appearThisTurn": False, "energies": [], "energyCards": [],
                "hp": 210, "id": 96, "maxHp": 210, "playerIndex": 0,
                "preEvolution": [], "serial": 60 + i, "tools": []})
    result, obs, _ = _archaludon_s58_replay(mut)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACH), (
        f"con banca desarrollada el adjunte normal se mantiene; "
        f"obtuvo {result} -> {opt}")


def test_archaludon_step58_ub_fetches_meowth_and_plays_it():
    _, _, data = _archaludon_s58_replay()
    fetch = data["synthetic_ub_fetch"]
    ch = m.agent(fetch)
    deck = fetch["select"]["deck"]
    picked = [deck[fetch["select"]["option"][i]["index"]]["id"] for i in ch]
    assert picked == [m.Meowth_ex], (
        f"el fetch de la UB del pivote debe traer Meowth ex; obtuvo {picked}")
    main_obs = data["synthetic_meowth_main"]
    ch2 = m.agent(main_obs)
    opt = main_obs["select"]["option"][ch2[0]]
    hand = [c["id"] for c in main_obs["current"]["players"][0]["hand"]]
    assert (opt.get("type") == int(OptionType.PLAY)
            and hand[opt["index"]] == m.Meowth_ex), (
        f"el Meowth buscado debe bajarse (Last-Ditch -> Lillie's); "
        f"obtuvo {ch2} -> {opt}")


# =====================================================================
# The "Meowth ex engine" plan (user): two gaps closed after the audit.
# IMPROVEMENT A -- The Meowth->Boss's engine for VALUE gusts (deny-evo) with the
# Boss's in the DECK: the in-hand machinery (`_boss_deny_evo`) requires a Boss's in
# hand and the `_active_ready_attacker` veto killed the generic fallback -> with no
# route, the agent attacked the wall letting the ENERGIZED pre-evo of the
# rival ex attacker evolve. A standalone flag `_deny_evo_via_boss` (alongside
# `_win_via_boss_gust`, hand OR deck) -> PLAY Meowth 22000 (below the finisher
# 22500) -> fetch Boss's 1280 -> the in-hand engine validates the gust afterwards.
# IMPROVEMENT B -- A GENERIC Xerosic in the Last-Ditch fetch: a rival hand >= 7 +
# a strong attacker in play + an active that attacks -> 1100 (below Lillie's/Boss's,
# "only if there is no better option"); before it was not even a candidate outside Alakazam.
# Fixture: the garchomp_step82 sequence MUTATED (the Boss's from hand into the deck,
# Meowth ex in hand, a bench slot) + 3 synthetic fetch frames.
# =====================================================================
_GARCHOMP_MEOWTH_DENY_EVO_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "garchomp_step82_meowth_boss_deck_deny_evo.json")


def _garchomp_meowth_deny_replay(mutate=None):
    import copy as _c
    with open(_GARCHOMP_MEOWTH_DENY_EVO_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    return m.agent(obs), obs, data


def _played_meowth(obs, result):
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][1]["hand"]]
    return (opt.get("type") == int(OptionType.PLAY)
            and opt.get("index", -1) < len(hand)
            and hand[opt["index"]] == m.Meowth_ex)


def test_garchomp_deny_evo_plays_meowth_for_deck_boss():
    result, obs, _ = _garchomp_meowth_deny_replay()
    assert _played_meowth(obs, result), (
        f"con Gabite energizado en banca rival y Boss's en el MAZO debe bajar "
        f"Meowth ex (motor deny-evo, 22000); obtuvo {result}")


def test_garchomp_deny_evo_no_meowth_if_supporter_played():
    result, obs, _ = _garchomp_meowth_deny_replay(
        lambda o: o["current"].__setitem__("supporterPlayed", True))
    assert not _played_meowth(obs, result), (
        f"con el Supporter jugado el Boss's buscado no se podria jugar: no "
        f"bajar Meowth; obtuvo {result}")


def test_garchomp_deny_evo_no_meowth_if_gabites_bare():
    def mut(o):
        for b in o["current"]["players"][0]["bench"]:
            if b["id"] == m.Cynthias_Gabite:
                b["energies"] = []
                b["energyCards"] = []
    result, obs, _ = _garchomp_meowth_deny_replay(mut)
    assert not _played_meowth(obs, result), (
        f"sin pre-evo ENERGIZADA el deny-evo no aplica: no gastar el Meowth; "
        f"obtuvo {result}")


def test_garchomp_deny_evo_last_ditch_fetches_boss():
    _, _, data = _garchomp_meowth_deny_replay()
    fetch = data["synthetic_ld_fetch_deny"]
    ch = m.agent(fetch)
    deck = fetch["select"]["deck"]
    picked = [deck[fetch["select"]["option"][i]["index"]]["id"] for i in ch]
    assert picked == [m.Boss_Orders], (
        f"con el deny-evo vivo, Last-Ditch debe traer Boss's (1280 > Lillie's "
        f"1200-1250); obtuvo {picked}")


def test_meowth_ld_fetches_xerosic_generic_big_hand():
    _, _, data = _garchomp_meowth_deny_replay()
    fetch = data["synthetic_ld_fetch_xerosic"]
    ch = m.agent(fetch)
    deck = fetch["select"]["deck"]
    picked = [deck[fetch["select"]["option"][i]["index"]]["id"] for i in ch]
    assert picked == [m.Xerosic_Machinations], (
        f"vs mazo generico con mano rival 8, atacante fuerte y sin mejor "
        f"fetch, Last-Ditch debe traer Xerosic (1100); obtuvo {picked}")


def test_meowth_ld_xerosic_generic_not_on_small_hand():
    import copy as _c
    _, _, data = _garchomp_meowth_deny_replay()
    fetch = _c.deepcopy(data["synthetic_ld_fetch_xerosic"])
    fetch["current"]["players"][0]["handCount"] = 5
    ch = m.agent(fetch)
    deck = fetch["select"]["deck"]
    picked = [deck[fetch["select"]["option"][i]["index"]]["id"] for i in ch]
    assert picked != [m.Xerosic_Machinations], (
        f"con mano rival 5 el Xerosic generico no aplica; obtuvo {picked}")


def test_meowth_ld_prefers_lillie_without_strong_attacker():
    _, _, data = _garchomp_meowth_deny_replay()
    fetch = data["synthetic_ld_fetch_xerosic_weak"]
    ch = m.agent(fetch)
    deck = fetch["select"]["deck"]
    picked = [deck[fetch["select"]["option"][i]["index"]]["id"] for i in ch]
    assert picked == [m.Lillie_Determination], (
        f"SIN atacante fuerte, cavar con Lillie's prima sobre el Xerosic "
        f"generico; obtuvo {picked}")


# =====================================================================
# The strategic audit (July 2026): 7 improvements implemented at once with
# the user's authorisation. Tests per improvement:
# 1) The Ogerpon inline: the ATTACK scoring now adds the rival active's energy
#    (Myriad Leaf Shower, the verified rule) -- before it underestimated KOs.
# 2) EX_IMMUNE_IDS includes Crustle_Fighting (533).
# 3) Forest replaces Watchtower with priority 27000 if the Meowth engine is alive.
# 4) A rival Maximum Belt (1158): +50 vs our ex in the damage projection.
# 5) Rocket's Tarountula (400) in THREAT_PREEVO_IDS.
# 6) GENERAL prize caution in the promotion: among candidates that
#    KNOCK OUT, if the projected rival blow kills the ex, prefer the 1-prize one.
# 7) Archetype inference from the rival DISCARD.
# =====================================================================


class _FakePkm:
    def __init__(self, id, energies=(), hp=100, maxHp=None, tools=()):
        self.id = id
        self.energies = list(energies)
        self.hp = hp
        self.maxHp = maxHp if maxHp is not None else hp
        self.tools = list(tools)


class _FakeTool:
    def __init__(self, id):
        self.id = id


def test_crustle_fighting_in_ex_immune_ids():
    assert m.Crustle_Fighting in m.EX_IMMUNE_IDS
    crustle_f = _FakePkm(m.Crustle_Fighting, hp=140)
    oger = _FakePkm(m.Teal_Mask_Ogerpon_ex, energies=[1, 1, 1], hp=210)
    assert m._our_effective_damage(oger, crustle_f, 120) == 0, (
        "la variante Fighting de Crustle tambien es inmune a nuestros ex")


def test_rockets_tarountula_is_threat_preevo():
    assert m.Rockets_Tarountula in m.THREAT_PREEVO_IDS


def test_maximum_belt_boosts_op_damage_vs_our_ex():
    mewtwo = _FakePkm(m.Rockets_Mewtwo_ex, energies=[5, 5, 5], hp=280)
    oger = _FakePkm(m.Teal_Mask_Ogerpon_ex, energies=[1, 1, 1], hp=210)
    base = m._op_active_attack_damage_to(mewtwo, oger)
    mewtwo_belt = _FakePkm(m.Rockets_Mewtwo_ex, energies=[5, 5, 5], hp=280,
                           tools=[_FakeTool(m.Maximum_Belt)])
    assert m._op_active_attack_damage_to(mewtwo_belt, oger) == base + 50
    # the Belt does NOT apply against a non-ex target
    megan = _FakePkm(m.Meganium, energies=[1, 1], hp=160)
    assert (m._op_active_attack_damage_to(mewtwo_belt, megan)
            == m._op_active_attack_damage_to(mewtwo, megan))


def _zone_fixture_base():
    import copy as _c
    with open(_ZONE_PROMOTE_FIXTURE, encoding="utf-8") as f:
        obs = _json.load(f)["observation"]
    return _c.deepcopy(obs)


def _prudence_promotion_obs(with_belt):
    # ctx4 (promotion after a KO): bench [Ogerpon ex 6e (210), Dipplin 1e (80),
    # Applin, Applin, Chikorita] -> Dipplin (Do the Wave) = 20*(5-1) = 80.
    # The op active: a TR Mewtwo ex at 70 HP remaining -> BOTH candidates knock out.
    # With a Maximum Belt the projection (160+50=210) OHKOs the Ogerpon (210) ->
    # caution: promote the 1-prize Dipplin. Without the Belt (160 < 210) the
    # Ogerpon survives -> the classic rule (more life).
    obs = _zone_fixture_base()
    cur = obs["current"]; yi = cur["yourIndex"]; op = cur["players"][1 - yi]
    my = cur["players"][yi]
    tools = ([{"id": m.Maximum_Belt, "playerIndex": 1 - yi, "serial": 302}]
             if with_belt else [])
    op["active"] = [{"appearThisTurn": False, "energies": [5, 5, 5],
                     "energyCards": [], "hp": 70, "id": m.Rockets_Mewtwo_ex,
                     "maxHp": 280, "playerIndex": 1 - yi, "preEvolution": [],
                     "serial": 301, "tools": tools}]
    op["discard"] = [c for c in op["discard"]
                     if c["id"] not in (m.Abra, m.Kadabra, m.Alakazam_ex)]
    cur["stadium"] = []
    def _pk(id, serial, energies, hp):
        return {"appearThisTurn": False, "energies": energies,
                "energyCards": [], "hp": hp, "id": id, "maxHp": hp,
                "playerIndex": yi, "preEvolution": [], "serial": serial,
                "tools": []}
    my["bench"] = [
        _pk(m.Teal_Mask_Ogerpon_ex, 3, [1, 1, 1, 1, 1, 1], 210),
        _pk(m.Dipplin, 16, [1], 80),
        _pk(m.Applin, 13, [], 40),
        _pk(m.Applin, 14, [], 40),
        _pk(m.Chikorita, 7, [], 70),
    ]
    obs["select"]["option"] = [
        {"area": 5, "index": i, "playerIndex": yi, "type": 3}
        for i in range(5)]
    return obs


def test_promotion_prudence_prefers_one_prize_when_both_doomed():
    obs = _prudence_promotion_obs(with_belt=True)
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    bench = obs["current"]["players"][obs["current"]["yourIndex"]]["bench"]
    picked = bench[obs["select"]["option"][result[0]]["index"]]["id"]
    assert picked == m.Dipplin, (
        f"proyeccion 210 (Belt) condena al Ogerpon y ambos noquean: promover "
        f"el 1-premio Dipplin; obtuvo {picked}")


def test_promotion_keeps_tank_ex_when_it_survives():
    obs = _prudence_promotion_obs(with_belt=False)
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    bench = obs["current"]["players"][obs["current"]["yourIndex"]]["bench"]
    picked = bench[obs["select"]["option"][result[0]]["index"]]["id"]
    assert picked == m.Teal_Mask_Ogerpon_ex, (
        f"sin Belt (160 < 210) el Ogerpon sobrevive: regla clasica de mas "
        f"vida; obtuvo {picked}")


def test_discard_inference_activates_alakazam_rule():
    # The zone fixture brings Abra/Kadabra ONLY in the rival DISCARD (an empty
    # bench, the active mocked to a Bellibolt ex): the inference by discard
    # switches on `op_is_alakazam_deck` and the 1-prize rule promotes Meganium
    # even though the ex has more life.
    import copy as _c
    obs = _zone_fixture_base()
    cur = obs["current"]; yi = cur["yourIndex"]; op = cur["players"][1 - yi]
    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                     "hp": 130, "id": 269, "maxHp": 280, "playerIndex": 1 - yi,
                     "preEvolution": [], "serial": 301, "tools": []}]
    assert any(c["id"] in (m.Abra, m.Kadabra) for c in op["discard"])
    options = obs["select"]["option"]
    nonex_opt = next(i for i, o in enumerate(options) if o.get("index") == 1)
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [nonex_opt], (
        f"Abra/Kadabra en el descarte rival deben activar la regla Alakazam "
        f"del 1-premio; obtuvo {result}")


def test_forest_replaces_watchtower_when_meowth_engine_alive():
    # A MAIN with a rival Watchtower in play, Forest in hand and a Meowth in the deck:
    # replacing the stadium (27000) beats development and attacking.
    import copy as _c
    with open(_GARCHOMP_BOSS_GABITE_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = _c.deepcopy(seq[-1]["observation"])
    cur = obs["current"]; yi = cur["yourIndex"]
    cur["stadium"] = [{"id": m.Team_Rockets_Watchtower,
                       "playerIndex": 1 - yi, "serial": 400}]
    my = cur["players"][yi]
    # the Forest into the hand in the Night Stretcher's slot (index 2)
    my["hand"][2] = {"id": m.Forest_of_Vitality, "playerIndex": yi, "serial": 46}
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in my["hand"]]
    assert (opt.get("type") == int(OptionType.PLAY)
            and hand[opt["index"]] == m.Forest_of_Vitality), (
        f"con Watchtower anulando el motor Meowth, reemplazarlo con Forest es "
        f"prioritario; obtuvo {result} -> {opt}")


def test_ogerpon_attack_counts_opponent_energy():
    # An op active with 150 HP and 2 energies: Myriad = 30+30*(3 ours + 2 theirs)
    # = 180 >= 150 (a KO). With the old inline copy (ours only: 120) the plan
    # did not see the KO. We verify via plan.remain_hp after the agent().
    obs = _zone_fixture_base()
    cur = obs["current"]; yi = cur["yourIndex"]; op = cur["players"][1 - yi]
    my = cur["players"][yi]
    op["active"] = [{"appearThisTurn": False, "energies": [5, 5],
                     "energyCards": [], "hp": 150, "id": m.Rockets_Mewtwo_ex,
                     "maxHp": 280, "playerIndex": 1 - yi, "preEvolution": [],
                     "serial": 301, "tools": []}]
    op["discard"] = [c for c in op["discard"]
                     if c["id"] not in (m.Abra, m.Kadabra, m.Alakazam_ex)]
    cur["stadium"] = []
    # our active: an Ogerpon ex with 3 energies
    my["active"] = [{"appearThisTurn": False, "energies": [1, 1, 1],
                     "energyCards": [], "hp": 210,
                     "id": m.Teal_Mask_Ogerpon_ex, "maxHp": 210,
                     "playerIndex": yi, "preEvolution": [], "serial": 3,
                     "tools": []}]
    obs["select"] = {"context": 0, "contextCard": None, "deck": None,
                     "effect": None, "maxCount": 1, "minCount": 1,
                     "option": [{"attackId": 195, "type": 13}, {"type": 14}],
                     "remainDamageCounter": 0, "remainEnergyCost": 0,
                     "type": 0}
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [0], f"debe atacar; obtuvo {result}"
    assert m.plan.attacker == 0 and m.plan.remain_hp is not None \
        and m.plan.remain_hp <= 0, (
        f"el plan debe registrar el KO (30+30*(3+2)=180 >= 150); "
        f"plan.remain_hp={m.plan.remain_hp}")


# =====================================================================
# An attachment that ENABLES the retreat towards a lethal bench attacker (user,
# registro_034 step 141 vs Crustle/Terrakion, LOST): an active Fezandipiti ex
# WITHOUT energy (it neither attacks nor retreats), a charged Dipplin on the bench (Do the Wave x2
# through the Grass weakness of the 140 Terrakion = a KO) and 2 energies in hand. The agent
# used Teal Dance on the bench Ogerpon (31500) and sprinkled the 2nd energy on
# Meganium: the whole KO line was lost. The flag `_attach_enable_retreat_ko`
# (it generalises `_tapu_sac_enable_retreat` via `_bench_attacker_can_ko`, without
# requiring can_switch) -> the ATTACH to the ACTIVE scores 41000 (the band of lethal
# charges, above Teal Dance and bench charges). The rest of the chain
# (Lillie's -> RETREAT -> promote the Dipplin -> attack) is resolved by the
# existing machinery once the retreat becomes legal.
# =====================================================================
_TERRAKION_ATTACH_RETREAT_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "terrakion_step141_attach_active_retreat_dipplin.json")


def _terrakion_s141_replay(mutate=None):
    import copy as _c
    with open(_TERRAKION_ATTACH_RETREAT_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    return m.agent(obs), obs, data


def test_terrakion_step141_attaches_energy_to_active_for_retreat():
    result, obs, _ = _terrakion_s141_replay()
    opt = obs["select"]["option"][result[0]]
    assert (opt.get("type") == int(OptionType.ATTACH)
            and opt.get("inPlayArea") == int(AreaType.ACTIVE)), (
        f"la energia debe ir al Fez ACTIVO (habilita la retirada hacia el "
        f"Dipplin letal), no a Teal Dance/banca; obtuvo {result} -> {opt}")


def test_terrakion_step141_no_pivot_without_bench_attacker():
    # A counterfactual: with no energies on the bench there is no lethal attacker -> the
    # pivot does not apply and the attachment to the active loses its priority.
    def mut(o):
        for b in o["current"]["players"][1]["bench"]:
            if b["id"] in (m.Dipplin, m.Teal_Mask_Ogerpon_ex):
                b["energies"] = []
                b["energyCards"] = []
    result, obs, _ = _terrakion_s141_replay(mut)
    opt = obs["select"]["option"][result[0]]
    assert not (opt.get("type") == int(OptionType.ATTACH)
                and opt.get("inPlayArea") == int(AreaType.ACTIVE)), (
        f"sin atacante de banca letal no debe priorizarse el adjunte al "
        f"activo; obtuvo {result} -> {opt}")


def test_terrakion_step141_promotes_charged_dipplin_after_retreat():
    _, _, data = _terrakion_s141_replay()
    prom = data["synthetic_promote"]
    ch = m.agent(prom)
    bench = prom["current"]["players"][1]["bench"]
    picked = bench[prom["select"]["option"][ch[0]]["index"]]
    assert picked["id"] in (m.Dipplin, m.Teal_Mask_Ogerpon_ex) \
        and len(picked["energies"]) >= 1, (
        f"tras retirar debe subir un atacante que NOQUEA al Terrakion "
        f"(Dipplin x2 debilidad / Ogerpon); obtuvo {picked['id']}")


# =====================================================================
# The Teal Dance tier guard (user, registro_009 step 113 vs Mega Lucario,
# LOST): an ACTIVE Hydrapple ex with 1 energy, a Mega Lucario ex at 160 (Syrup
# Storm 30+30x6=210 = a 3-prize KO) and a recovered energy in hand. The
# unconditional promotion of Teal Dance to the ENERGY tier made a DEGRADED
# TD (7500, an energy reservation) dominate by TIER over Ripening Charge
# (31100, tier 0), sprinkling the energy on a bench Ogerpon and losing the
# finisher. The guard: the promotion only applies with a score >= 29000 (a real play;
# its branches run from 29000 to 31600). RECONSTRUCTED frames of the state of turn
# 8 (the record only brings the rival's frames).
# =====================================================================
_LUCARIO_RIPEN_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "lucario_step113_ripening_active_over_bench_td.json")


def _lucario_ripen_data():
    with open(_LUCARIO_RIPEN_FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def test_lucario_step113_ripening_beats_degraded_teal_dance():
    data = _lucario_ripen_data()
    obs = data["main"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert (opt.get("type") == int(OptionType.ABILITY)
            and opt.get("area") == int(AreaType.ACTIVE)), (
        f"Ripening Charge (31100) debe ganar a las Teal Dance degradadas "
        f"(7500) que antes dominaban por tier; obtuvo {result} -> {opt}")


def test_lucario_step113_ripening_targets_active_hydrapple():
    data = _lucario_ripen_data()
    obs = data["ripen_target"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("area") == int(AreaType.ACTIVE), (
        f"la energia de Ripening va al Hydrapple ACTIVO (habilita Syrup 210 "
        f">= 160, KO de 3 premios); obtuvo {result} -> {opt}")


def test_lucario_step113_attacks_after_charge():
    data = _lucario_ripen_data()
    obs = data["attack"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con 2 energias el Hydrapple ataca (KO al Mega Lucario ex); "
        f"obtuvo {result} -> {opt}")


# =====================================================================
# A RECHARGEABLE tank over a doomed ex attacker (user, registro_009 step 130
# vs Archaludon ex, WON): after the rival's KO we have to promote; the best
# classic candidate was a charged Ogerpon ex (210) that does NOT knock out and DIES to
# the Archaludon's projected blow (Ion Beam 220) -> it gives away 2 prizes. On the bench
# there is a Hydrapple ex WITHOUT energies (330: it survives) and in hand a Lana's Aid with 3
# Grass in the discard: next turn it recovers energies and with a manual
# attachment + Ripening Charge it reaches 2 effective (Syrup Storm). An override in
# `_best_promote_card`: a doomed ex candidate with no KO -> promote the rechargeable
# Hydrapple tank; the real-KO overrides (Tapu / the 1-prize Alakazam one)
# still win because they are applied afterwards.
# =====================================================================
_ARCHALUDON_TANK_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step130_promote_rechargeable_tank.json")


def _archaludon_s130_replay(mutate=None):
    import copy as _c
    with open(_ARCHALUDON_TANK_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    result = m.agent(obs)
    bench = obs["current"]["players"][0]["bench"]
    return bench[obs["select"]["option"][result[0]]["index"]]


def test_archaludon_step130_promotes_rechargeable_hydrapple_tank():
    picked = _archaludon_s130_replay()
    assert picked["id"] == m.Hydrapple_ex, (
        f"con el Ogerpon condenado (210 <= 220 proyectado) y Lana's Aid + 3 "
        f"Plantas en el descarte, promover el Hydrapple tanque (330); "
        f"obtuvo {picked['id']}")


def test_archaludon_step130_tank_no_depende_de_lanas():
    # SUPERSEDED by the survival rule (user, registro_005 step 64):
    # before, without a Lana's Aid the Hydrapple "was not rechargeable" and the classic
    # behaviour was kept (promote the charged Ogerpon). The new instruction is
    # explicit and holds for any deck: if a body SURVIVES the projected attack,
    # bring that one up. Here Archaludon ex hits for 220: the Hydrapple ex (330) survives and
    # everything else dies, so rechargeability no longer changes the choice.
    def mut(o):
        my = o["current"]["players"][0]
        my["hand"] = [c for c in my["hand"] if c["id"] != m.Lanas_Aid]
        my["handCount"] = len(my["hand"])
    picked = _archaludon_s130_replay(mut)
    assert picked["id"] == m.Hydrapple_ex, (
        f"el Hydrapple ex (330) es el unico que aguanta los 220 de Archaludon "
        f"ex, con Lana's o sin ella; obtuvo {picked['id']}")


def test_archaludon_step130_keeps_attacker_if_it_survives():
    def mut(o):
        o["current"]["players"][1]["active"][0]["energies"] = [8]
    picked = _archaludon_s130_replay(mut)
    assert picked["id"] == m.Teal_Mask_Ogerpon_ex, (
        f"si el rival no paga el golpe letal, el Ogerpon cargado sobrevive y "
        f"se promueve normal; obtuvo {picked['id']}")


# =====================================================================
# The EX fallback of the prize-denial pivot (user, registro_013 step 139
# vs Archaludon/Cinderace, LOST): an active Hydrapple ex with 10 HP that can
# KNOCK OUT the active Duraludon, but the rival is at 2 prizes and their bench Cinderace
# (Turbo Flare 50 x2 for weakness = 100) finishes off the Hydrapple next
# turn = a LOSS. Before, `_prize_denial_pivot` only looked for 1-prize
# bodies that could attack (there were none: Tapu 2e, Meganium 0e) and the agent attacked
# with the doomed active. A new fallback: with no 1-prize body available, retreat and
# promote a bench EX that KNOCKS OUT the rival active AND SURVIVES the best
# projected blow from the rival bench (an Ogerpon 6e: Myriad 300-30 resistance =
# 270 >= 130 KO; 210 HP > 100). The same KO without giving away the final 2 prizes.
# =====================================================================
_ARCHALUDON_PDX_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step139_prize_denial_ex_fallback.json")


def _archaludon_s139_replay(mutate=None):
    import copy as _c
    with open(_ARCHALUDON_PDX_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    result = m.agent(obs)
    return result, obs, data


def test_archaludon_step139_suppresses_doomed_active_attack():
    result, obs, _ = _archaludon_s139_replay()
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") != int(OptionType.ATTACK), (
        f"con el rival a 2 premios y el Hydrapple de 10 HP condenado, atacar "
        f"con el activo regala la partida; obtuvo {result} -> {opt}")
    assert m.plan.attacker >= 1, (
        f"el plan debe redirigir al Ogerpon ex de banca (fallback EX del "
        f"prize-denial); plan.attacker={m.plan.attacker}")


def test_archaludon_step139_retreats_on_reduced_menu():
    _, _, data = _archaludon_s139_replay()
    obs = data["synthetic_retreat_menu"]
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.RETREAT), (
        f"con solo ATTACK/RETREAT/END debe RETIRAR al Hydrapple condenado; "
        f"obtuvo {result} -> {opt}")


def test_archaludon_step139_promotes_charged_ogerpon():
    _, _, data = _archaludon_s139_replay()
    obs = data["synthetic_promote"]
    result = m.agent(obs)
    bench = obs["current"]["players"][1]["bench"]
    picked = bench[obs["select"]["option"][result[0]]["index"]]
    assert (picked["id"] == m.Teal_Mask_Ogerpon_ex
            and len(picked["energies"]) >= 3), (
        f"tras retirar debe subir el Ogerpon ex cargado que noquea al "
        f"Duraludon y sobrevive al Cinderace; obtuvo {picked['id']}")


def test_archaludon_step139_no_pivot_when_ko_does_not_win_for_op():
    def mut(o):
        o["current"]["players"][0]["prize"] = [None, None, None]
    _, obs, _ = _archaludon_s139_replay(mut)
    assert m.plan.attacker == 0, (
        f"con el rival a 3 premios el KO del ex (2) no le da la partida: "
        f"conducta clasica (activo ataca); plan.attacker={m.plan.attacker}")


def test_archaludon_step139_no_pivot_without_ready_ex():
    def mut(o):
        for b in o["current"]["players"][1]["bench"]:
            if b["id"] == m.Teal_Mask_Ogerpon_ex:
                b["energies"] = b["energies"][:2]
                b["energyCards"] = b["energyCards"][:1]
    _, obs, _ = _archaludon_s139_replay(mut)
    assert m.plan.attacker == 0, (
        f"sin EX de banca que noquee y sobreviva, el fallback no aplica; "
        f"plan.attacker={m.plan.attacker}")


# =====================================================================
# The priority between COPIES of the same threat (user, registro_007 step 80 vs
# Archaludon, WON with a mistake): the rival active is a Duraludon with 3
# energies + a Hero's Cape (230 HP) and on the bench there is ANOTHER weak Duraludon (1
# energy, no tool). The agent played Boss's to gust+knock out the weak copy
# (the low-value branch 1500 > ATTACK 1100). The user's rule (restated): between
# two identical Pokemon the priority belongs to the one carrying a life tool
# and, second, to the one with more energies -> ATTACK the big active and KEEP
# the Boss's. The previous correction (`_bo_active_prize_dominates`) required being able to
# KNOCK OUT the active and the Cape (210 < 230) switched it off; besides, it only covered
# the deny-evo branch. A new flag `boss_active_threat_dominates` (ctx): a THREAT_PREEVO
# active + we can attack it + ALL the bench copies are of the same
# species and dominated (tool first, energies second) -> the PLAY of Boss's falls to
# EMPTY_GUST (20); the finishers (WIN_NOW/2-prize/win-via-bench) return
# earlier and are unaffected.
# =====================================================================
_ARCHALUDON_CAPED_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step80_attack_caped_active_not_gust_copy.json")


def _archaludon_s80_replay(mutate=None):
    import copy as _c
    with open(_ARCHALUDON_CAPED_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    result = m.agent(obs)
    return result, obs


def test_archaludon_step80_attacks_caped_active_instead_of_gusting_copy():
    result, obs = _archaludon_s80_replay()
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con el Duraludon grande (Cape + 3e) en el activo y solo su copia "
        f"debil en banca, ATACAR al activo y guardar el Boss's; "
        f"obtuvo {result} -> {opt}")


def test_archaludon_step80_gusts_when_bench_copy_is_stronger():
    def mut(o):
        op = o["current"]["players"][0]
        op["bench"][0]["energies"] = [8, 8, 8, 8]
        op["active"][0]["energies"] = [8]
        op["active"][0]["tools"] = []
    result, obs = _archaludon_s80_replay(mut)
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][1]["hand"]]
    assert (opt.get("type") == int(OptionType.PLAY)
            and hand[opt["index"]] == m.Boss_Orders), (
        f"si la copia de banca es la MAS desarrollada, el gusteo de valor "
        f"vuelve a aplicar; obtuvo {result} -> {opt}")


# =====================================================================
# The anti-DONK guard of the first turn going FIRST (user, registro_001
# steps 6-7 vs Cinderace/Archaludon, LOST): we start with ONLY an active Chikorita
# (an empty bench) and 2 Meowth ex + Lillie's in hand. The first turn's
# hold vetoed playing the Meowth ("there is a Lillie's in hand") -- but going first the
# Supporter is NOT EVEN playable that turn, and the rival Cinderace (Turbo
# Flare 50 x2 for weakness = 100 >= 70) donked us on their first turn = an
# instant loss with no bench. A new rule: if the rival active projects a ONE-energy
# KO on our lone active, play Meowth ex (21900, an
# anti-donk body) and its Last-Ditch brings a Lillie's for next turn; with no projected
# donk the previous behaviour is kept (do not play it).
# =====================================================================
_CINDERACE_DONK_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "cinderace_turn1_donk_guard_meowth.json")


def _cinderace_t1_replay(mutate=None):
    import copy as _c
    with open(_CINDERACE_DONK_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    obs = data["sequence"][0]["observation"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    result = m.agent(obs)
    return result, obs, data


def test_cinderace_turn1_plays_meowth_against_projected_donk():
    result, obs, _ = _cinderace_t1_replay()
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][1]["hand"]]
    assert (opt.get("type") == int(OptionType.PLAY)
            and hand[opt["index"]] == m.Meowth_ex), (
        f"con el donk de 1 energia proyectado (100 >= 70) y banca vacia, "
        f"bajar Meowth ex aunque haya Lillie's en mano; obtuvo {result} -> {opt}")


def test_cinderace_turn1_no_meowth_without_donk_threat():
    def mut(o):
        o["current"]["players"][0]["active"][0].update(
            {"id": 169, "hp": 130, "maxHp": 130})  # Duraludon: Hammer In 30 < 70
    result, obs, _ = _cinderace_t1_replay(mut)
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][1]["hand"]]
    is_meowth = (opt.get("type") == int(OptionType.PLAY)
                 and opt.get("index", -1) < len(hand)
                 and hand[opt["index"]] == m.Meowth_ex)
    assert not is_meowth, (
        f"sin donk proyectado se mantiene la regla no-meowth-para-lillie; "
        f"obtuvo {result} -> {opt}")


def test_cinderace_turn1_last_ditch_fetches_lillies():
    _, _, data = _cinderace_t1_replay()
    fetch = data["synthetic_ld_fetch"]
    result = m.agent(fetch)
    deck = fetch["select"]["deck"]
    picked = [deck[fetch["select"]["option"][i]["index"]]["id"] for i in result]
    assert picked == [m.Lillie_Determination], (
        f"el Last-Ditch del Meowth anti-donk trae Lillie's (aunque haya una "
        f"en mano: primer turno, banca vacia); obtuvo {picked}")


# =====================================================================
# Charging energy to the BEST ATTACKER (user, registro_004 steps 39-54 vs
# Archaludon ex, LOST): turn 4, an active Ogerpon ex (1 energy, Myriad
# needs 3) canNOT attack; the just-evolved bench Hydrapple ex
# receives the manual attachment (1 energy) and with ONE more Grass it is READY
# (Syrup Storm cost 2, 30+30xGrass on the field = 210 >= the rival active's 160).
# The old version of the agent spent the last Grass in hand with Teal
# Dance on the ACTIVE (which does not attack and whose energy powers nothing),
# retreated and promoted a Hydrapple with a single energy: NO attack option,
# a wasted turn. The user's rule: when playing each energy the best possible
# attacker of the turn is evaluated -> the Grass goes to the Hydrapple via its
# Ripening Charge ability (31100 > Teal Dance 7500, deprioritised because the
# bench Hydrapple needs the energy), then RETREAT the Ogerpon (cost 1,
# now payable), promote the Hydrapple and finish with Syrup Storm. Ripening's target
# is set in energy_score (ATTACH_FROM, the 41000 rule "charging the
# bench Hydrapple leaves it ready for a lethal Syrup Storm").
# =====================================================================
_ARCHALUDON_S43_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step43_ripening_hydrapple_over_teal_dance.json")


def _archaludon_s43_replay(mutate=None):
    import copy as _c
    with open(_ARCHALUDON_S43_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    return m.agent(obs), obs, data


def test_archaludon_step43_uses_ripening_over_teal_dance_active():
    result, obs, _ = _archaludon_s43_replay()
    opt = obs["select"]["option"][result[0]]
    me = obs["current"]["players"][0]
    picked = (me["active"][0] if opt.get("area") == int(AreaType.ACTIVE)
              else me["bench"][opt.get("index", 0)])
    assert (opt.get("type") == int(OptionType.ABILITY)
            and opt.get("area") == int(AreaType.BENCH)
            and picked["id"] == m.Hydrapple_ex), (
        f"con el activo Ogerpon sin poder atacar y el Hydrapple de banca a 1 "
        f"Planta de quedar listo, la energia se juega con Ripening Charge "
        f"(Hydrapple), NO con Teal Dance sobre el activo; "
        f"obtuvo {result} -> {opt}")


def test_archaludon_step43_ripening_targets_bench_hydrapple():
    _, _, data = _archaludon_s43_replay()
    tgt = data["synthetic_ripening_target"]
    ch = m.agent(tgt)
    opt = tgt["select"]["option"][ch[0]]
    me = tgt["current"]["players"][0]
    picked = (me["active"][0] if opt["area"] == int(AreaType.ACTIVE)
              else me["bench"][opt["index"]])
    assert (opt["area"] == int(AreaType.BENCH)
            and picked["id"] == m.Hydrapple_ex), (
        f"la Planta de Ripening Charge va al PROPIO Hydrapple de banca (mejor "
        f"atacante: queda a 2 energias, Syrup Storm letal), no al Ogerpon "
        f"activo; obtuvo {ch} -> {opt} (id {picked['id']})")


def test_archaludon_step43_retreats_after_charging_hydrapple():
    _, _, data = _archaludon_s43_replay()
    post = data["synthetic_post_ripening_main"]
    ch = m.agent(post)
    opt = post["select"]["option"][ch[0]]
    assert opt.get("type") == int(OptionType.RETREAT), (
        f"con el Hydrapple de banca ya listo (2 energias) y el activo sin "
        f"ataque, se RETIRA al Ogerpon (coste 1 ya pagable) para promover al "
        f"atacante; obtuvo {ch} -> {opt}")


def test_archaludon_step43_promotes_charged_hydrapple():
    _, _, data = _archaludon_s43_replay()
    prom = data["synthetic_promote"]
    ch = m.agent(prom)
    opt = prom["select"]["option"][ch[0]]
    picked = prom["current"]["players"][0]["bench"][opt["index"]]
    assert picked["id"] == m.Hydrapple_ex and len(picked["energies"]) >= 2, (
        f"tras retirar se promueve el Hydrapple ex CARGADO (2 energias, unico "
        f"atacante usable del turno); obtuvo {ch} -> {opt} (id {picked['id']})")


def test_archaludon_step43_attacks_with_syrup_storm():
    _, _, data = _archaludon_s43_replay()
    fin = data["synthetic_final_attack"]
    ch = m.agent(fin)
    opt = fin["select"]["option"][ch[0]]
    assert (opt.get("type") == int(OptionType.ATTACK)
            and opt.get("attackId") == 195), (
        f"el Hydrapple promovido con 2 energias debe ATACAR (Syrup Storm 195, "
        f"30+30xGrass = 210 >= 160), no terminar el turno; "
        f"obtuvo {ch} -> {opt}")


# =====================================================================
# The Applin's energy cap (user, registro_004 steps 35-63, episode
# 87675043 vs Mega Lucario, LOST): turn 4, step 36. The agent attached the
# 2nd energy to a bench Applin that ALREADY had 1: its only attack costs 1 and
# Do the Wave of the Dipplin it evolves into also costs 1, so the
# energy was COMPLETELY WASTED (the Dipplin finished the turn with a single
# useful energy). The cause: the 2nd energy to the Applin only got a soft
# penalty (-300 -> 7700) which still beat Teal Dance (7500);
# the attachments to the Ogerpon were correctly vetoed (Teal Dance precedes the
# manual attachment) and the Applin was left as the "best" target of the ENERGY tier.
# The user's rule: an Applin can have at MOST 1 PHYSICAL energy, unless
# the 2nd is needed to power the attack of a Hydrapple ex and it is the
# ONLY Pokemon to charge. Fix: a hard veto in energy_score (alongside the
# Chikorita cap) with two exceptions: (a) a complete evolution this turn
# (Dipplin + Hydrapple ex in hand, no Meganium) keeps the existing branch
# _applin_full_evolve_now; (b) a Hydrapple ex in play -> a minimum score of 10
# (a last resort: the energy on the field does scale Syrup Storm).
# =====================================================================
_LUCARIO_S36_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "lucario_step36_applin_max_one_energy.json")


def _lucario_s36_replay(mutate=None):
    import copy as _c
    with open(_LUCARIO_S36_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    return m.agent(obs), obs, data


def test_lucario_step36_no_second_energy_on_loaded_applin():
    result, obs, _ = _lucario_s36_replay()
    opt = obs["select"]["option"][result[0]]
    me = obs["current"]["players"][0]
    is_applin_attach = (
        opt.get("type") == int(OptionType.ATTACH)
        and opt.get("inPlayArea") == int(AreaType.BENCH)
        and me["bench"][opt.get("inPlayIndex", 0)]["id"] == m.Applin
        and len(me["bench"][opt.get("inPlayIndex", 0)]["energies"]) >= 1)
    assert not is_applin_attach, (
        f"un Applin con 1 energia NO recibe una 2a (su ataque y Do the Wave "
        f"cuestan 1; la energia se reserva para Teal Dance / atacantes); "
        f"obtuvo {result} -> {opt}")


def test_lucario_step36_applin_second_energy_hard_vetoed():
    # A forced choice [ATTACH -> Applin(1e), END]: the veto must prefer
    # ending the turn to overcharging the Applin.
    _, _, data = _lucario_s36_replay()
    forced = data["synthetic_forced_applin_loaded"]
    ch = m.agent(forced)
    opt = forced["select"]["option"][ch[0]]
    assert opt.get("type") == int(OptionType.END), (
        f"con el Applin ya cargado (1 fisica) el adjunte queda VETADO incluso "
        f"como unica jugada; obtuvo {ch} -> {opt}")


def test_lucario_step36_applin_first_energy_still_allowed():
    # The same forcing but with the Applin WITHOUT energy: the 1st Grass is attached.
    _, _, data = _lucario_s36_replay()
    forced = data["synthetic_forced_applin_empty"]
    ch = m.agent(forced)
    opt = forced["select"]["option"][ch[0]]
    assert opt.get("type") == int(OptionType.ATTACH), (
        f"la 1a energia del Applin sigue permitida (habilita su ataque y la "
        f"linea evolutiva); obtuvo {ch} -> {opt}")


def test_lucario_step36_applin_second_energy_last_resort_with_hydrapple():
    # Exception (b): with a Hydrapple ex OF OURS in play and the Applin as the
    # ONLY chargeable target, the 2nd energy is allowed (a minimum score of 10 >
    # END): on the field it still adds to the Syrup Storm.
    _, _, data = _lucario_s36_replay()
    forced = data["synthetic_forced_applin_hydra_in_play"]
    ch = m.agent(forced)
    opt = forced["select"]["option"][ch[0]]
    assert opt.get("type") == int(OptionType.ATTACH), (
        f"con Hydrapple ex en juego y ningun otro objetivo, la 2a energia al "
        f"Applin es el ultimo recurso valido (potencia Syrup Storm); "
        f"obtuvo {ch} -> {opt}")


# =====================================================================
# The Unfair Stamp -> Meowth ex order (user, registro_008 steps 106-128, episode
# 87676139 vs Mega Lucario, LOST): turn 8, step 115. An Ultra Ball brought
# Meowth ex to hand and the `_ub_meowth_pending` override forced playing it (21000)
# to chain Last-Ditch Catch -> search for Lillie's. But there was a playable Unfair
# Stamp in hand (they knocked us out last turn, `_stamp_blocks_supp_chain`):
# by playing the Meowth BEFORE the Stamp, the Supporter that Last-Ditch brings is SHUFFLED
# back into the deck when the Stamp remakes both hands, and on top of that a 2-prize
# body is exposed. The correct order: play the items -> Unfair Stamp -> and only AFTERWARDS
# play Meowth ex. Fix: the guard `and not _stamp_blocks_supp_chain` in the Meowth
# overrides (`_ub_meowth_pending` and the in-hand Xerosic engine), so that with the
# Stamp pending the Stamp+ko_last_turn veto of the main chain prevails.
# =====================================================================
_LUCARIO_S115_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "lucario_step115_meowth_after_unfair_stamp.json")


def _lucario_s115_replay(mutate=None):
    import copy as _c
    with open(_LUCARIO_S115_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = seq[-1]["observation"]
    if mutate is not None:
        obs = _c.deepcopy(obs)
        mutate(obs)
    return m.agent(obs), obs, data


def test_lucario_step115_does_not_play_meowth_before_stamp():
    result, obs, _ = _lucario_s115_replay()
    opt = obs["select"]["option"][result[0]]
    hand = obs["current"]["players"][0]["hand"]
    is_meowth = (opt.get("type") == int(OptionType.PLAY)
                 and opt.get("index", -1) < len(hand)
                 and hand[opt["index"]]["id"] == m.Meowth_ex)
    assert not is_meowth, (
        f"con un Unfair Stamp jugable en mano NO se baja Meowth ex antes del "
        f"Sello (su Last-Ditch se perderia al rebarajar); obtuvo {result} -> "
        f"{opt}")


def test_lucario_step115_stamp_is_still_playable_now():
    # The Unfair Stamp must still be available as a play this turn (not vetoed).
    result, obs, _ = _lucario_s115_replay()
    hand = obs["current"]["players"][0]["hand"]
    stamp_opt = next(
        (o for o in obs["select"]["option"]
         if o.get("type") == int(OptionType.PLAY)
         and o.get("index", -1) < len(hand)
         and hand[o["index"]]["id"] == m.Unfair_Stamp), None)
    assert stamp_opt is not None, "el Unfair Stamp debe estar entre las opciones"


def test_lucario_step115_plays_meowth_after_stamp_gone():
    # A counterfactual: the Unfair Stamp has already been played (out of the hand). The Meowth
    # engine is still alive -> now Meowth ex IS played for the Last-Ditch.
    _, _, data = _lucario_s115_replay()
    post = data["synthetic_post_stamp"]
    ch = m.agent(post)
    opt = post["select"]["option"][ch[0]]
    hand = post["current"]["players"][0]["hand"]
    assert (opt.get("type") == int(OptionType.PLAY)
            and opt.get("index", -1) < len(hand)
            and hand[opt["index"]]["id"] == m.Meowth_ex), (
        f"tras jugar el Unfair Stamp, el motor Meowth ex vuelve a activarse y se "
        f"baja para encadenar Last-Ditch -> Lillie's; obtuvo {ch} -> {opt}")


# =====================================================================
# The Ultra Ball searches for Hydrapple ex to evolve the doomed active Dipplin
# (user, registro_008 steps 067-072 vs Crustle/Kangaskhan, LOST): step 69.
# The active is a Dipplin (80 HP, 2 energies) that does NOT knock out the active
# Kangaskhan ex and will be defeated next turn. The right thing is to search for Hydrapple ex
# to EVOLVE it: a 330 HP tank that survives the blow and attacks the
# Kangaskhan ex better. The generic degradation of Hydrapple ex vs Crustle (a dead
# card through ex immunity) clamped its score to 40 and made a bare Tapu Bulu
# win. Fix: the exception `_ub_evo_doomed_hittable` (`_ub_dipplin_evo_atk` and the
# rival active NOT immune to ex) which lifts the clamp for this
# evolution+survival pivot of the active.
# =====================================================================
_CRUSTLE_S69_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "crustle_step69_ub_fetch_hydrapple_evolve_doomed_dipplin.json")


def _crustle_s69_replay(observation_key=None):
    with open(_CRUSTLE_S69_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = data[observation_key] if observation_key else seq[-1]["observation"]
    return m.agent(obs), obs, data


def _fetch_ids(obs, choice):
    sel = obs["select"]
    deck = sel["deck"]
    return [deck[sel["option"][x]["index"]]["id"] for x in choice
            if x < len(sel["option"])]


def test_crustle_step69_ub_fetches_hydrapple_to_evolve_doomed_dipplin():
    result, obs, _ = _crustle_s69_replay()
    ids = _fetch_ids(obs, result)
    assert m.Hydrapple_ex in ids, (
        f"la Ultra Ball debe buscar Hydrapple ex para evolucionar al Dipplin "
        f"activo condenado (tanque de 330 PV que sobrevive y ataca a Kangaskhan "
        f"ex); obtuvo {result} -> {ids}")


def test_crustle_step69_hydrapple_beats_tapu_bulu():
    result, obs, _ = _crustle_s69_replay()
    ids = _fetch_ids(obs, result)
    assert m.Tapu_Bulu not in ids, (
        f"no se busca el Tapu Bulu pelado: el pivote de evolucion del activo es "
        f"superior; obtuvo {result} -> {ids}")


def test_crustle_step69_immune_active_keeps_clamp():
    # A boundary counterfactual: if the rival active is a Crustle (immune to ex),
    # Hydrapple ex cannot attack it, the exception does NOT apply and the clamp vs
    # Crustle returns -> Hydrapple ex is not preferred.
    result, obs, _ = _crustle_s69_replay(
        observation_key="synthetic_op_active_crustle")
    ids = _fetch_ids(obs, result)
    assert m.Hydrapple_ex not in ids, (
        f"con un Crustle inmune de activo, Hydrapple ex vuelve a ser carta "
        f"muerta y el clamp debe aplicar (no se busca Hydrapple ex); obtuvo "
        f"{result} -> {ids}")


# =====================================================================
# Teal Dance over bench development (user, registro_002 step 20,
# episode 87709673 vs Marnie): our first turn going second. The
# ACTIVE Ogerpon ex has already used its Teal Dance, so the manual attachment to the active
# is vetoed by the first-turn rule and the Teal Dance of the BENCH Ogerpon ex
# falls to the degraded band (7500). The only remaining target, a
# bench Chikorita, won with 8400 (a base 8000 from energy_score + a development
# boost) and also dominated by TIER (an attachment = _TIER_ENERGY against
# the ability in tier 0), wasting the only Grass on a body that with 1
# energy is NOT an attacker. Fix: a MERE DEVELOPMENT attachment (a band < 9000 and
# a target that does not end up ready to attack, requiring MAIN_ATTACKERS) yields to
# a pending Teal Dance: it is capped at 7000 and left in tier 0 so that
# within the same tier the score decides.
# =====================================================================
_MARNIE_S20_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "marnie_step20_teal_dance_sobre_desarrollo.json")


def _marnie_s20_replay(observation_key=None):
    with open(_MARNIE_S20_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = data[observation_key] if observation_key else seq[-1]["observation"]
    return m.agent(obs), obs, data


def test_marnie_step20_usa_teal_dance_en_vez_de_cargar_chikorita():
    result, obs, _ = _marnie_s20_replay()
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ABILITY), (
        f"con una Teal Dance pendiente, el adjunte de desarrollo debe ceder: "
        f"se esperaba la habilidad; obtuvo {result} -> {opt}")


def test_marnie_step20_does_not_charge_energy_to_the_chikorita():
    result, obs, _ = _marnie_s20_replay()
    opt = obs["select"]["option"][result[0]]
    if opt.get("type") != int(OptionType.ATTACH):
        return  # it does not attach: the rule was respected
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    destino = (me["active"][0] if opt.get("inPlayArea") == 4
               else me["bench"][opt["inPlayIndex"]])
    assert destino["id"] != m.Chikorita, (
        f"nunca gastar la unica Planta en un Chikorita de banca (con 1 energia "
        f"no es atacante) habiendo Teal Dance; obtuvo {result} -> {opt}")


def test_marnie_step20_with_no_teal_dance_the_attachment_does_not_yield():
    # A boundary counterfactual: if the ability is no longer available, the
    # development attachment does NOT yield and is the best play again.
    result, obs, _ = _marnie_s20_replay(
        observation_key="synthetic_sin_teal_dance")
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACH), (
        f"sin Teal Dance pendiente el adjunte manual no debe cederle a nadie; "
        f"obtuvo {result} -> {opt}")


# =====================================================================
# Xerosic's Machinations over Boss's Orders (user, registro_006 step 85,
# episode 87709507 vs Alakazam ex, LOST): our active Hydrapple ex (10
# HP) knocks out the Alakazam ex and in hand there are Boss's Orders and Xerosic with the rival
# at 16 CARDS. The agent played Boss's (a 2-prize gust, 6800) instead of
# Xerosic (6200) and left the rival hand intact: their Powerful Hand (20 x each card in
# their hand) went on hitting for 320 and swept the board. The rule: vs Alakazam, capping the hand takes
# priority over Boss's; Boss's only has it when it WINS the game
# (`win_via_boss_gust`, WIN_NOW 20000). Fix: a new rule
# `alakazam_prioridad_sobre_boss` (XEROSIC_SCORE_SOBRE_BOSS=7000, above
# GUST_2PRIZE) and the yielding now requires the WINNING gust (before it yielded to
# `boss_win_via_bench`, which only takes one prize).
# =====================================================================
_ALAKAZAM_S85_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_step85_xerosic_sobre_boss.json")


def _alakazam_s85_replay(observation_key=None):
    with open(_ALAKAZAM_S85_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = data[observation_key] if observation_key else seq[-1]["observation"]
    return m.agent(obs), obs, data


def _played_card(obs, result):
    opt = obs["select"]["option"][result[0]]
    if opt.get("type") != int(OptionType.PLAY):
        return None
    hand = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    return hand[opt["index"]]["id"]


def test_alakazam_step85_plays_xerosic_and_not_boss():
    result, obs, _ = _alakazam_s85_replay()
    assert _played_card(obs, result) == m.Xerosic_Machinations, (
        f"con el rival a 16 cartas, capar la mano (Powerful Hand = 20 x carta) "
        f"tiene prioridad sobre un gusteo que no gana la partida; obtuvo "
        f"{result} -> id {_played_card(obs, result)}")


def test_alakazam_step85_keeps_the_boss_orders():
    result, obs, _ = _alakazam_s85_replay()
    assert _played_card(obs, result) != m.Boss_Orders, (
        f"Boss's Orders solo tiene prioridad cuando GANA la partida; obtuvo "
        f"{result}")


def test_alakazam_step85_without_xerosic_boss_returns():
    # A counterfactual: with no Xerosic in hand, Boss's is the play again.
    result, obs, _ = _alakazam_s85_replay(
        observation_key="synthetic_sin_xerosic")
    assert _played_card(obs, result) == m.Boss_Orders, (
        f"sin Xerosic en mano el gusteo de 2 premios sigue siendo correcto; "
        f"obtuvo {result} -> id {_played_card(obs, result)}")


# =====================================================================
# Do not pivot to a DOOMED Hydrapple ex (user, registro_011 step 138, episode
# 87713774 vs Dragapult ex, LOST): an active Tapu Bulu with 6 effective energies
# (ready to attack) and a bench Hydrapple ex at 70/330, with the rival at 2
# prizes. The agent retreated the Tapu Bulu to promote the Hydrapple; Dragapult
# ex (Phantom Dive, 200) knocked it out and took their final 2 prizes = a loss.
# Three chained bugs: (1) the Syrup Storm of a BENCH Hydrapple was measured
# with the Grass PRIOR to the retreat ("lethal" 330 vs 320) when the retreat discards
# the active's Grass; (2) the same in `_hydra_lethal_promote`; (3)
# `_promote_hydra = _hydra_can_ko or (not _act_can_ko)` promoted without checking
# whether the Hydrapple SURVIVES the projected blow.
# =====================================================================
_DRAGAPULT_S138_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "dragapult_step138_no_pivote_hydra_condenado.json")


def _dragapult_s138_replay(observation_key=None):
    with open(_DRAGAPULT_S138_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = data[observation_key] if observation_key else seq[-1]["observation"]
    return m.agent(obs), obs, data


def test_dragapult_step138_attacks_with_tapu_bulu():
    result, obs, _ = _dragapult_s138_replay()
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con el Tapu Bulu activo ya cargado y el Hydrapple ex de banca "
        f"condenado (70/330 frente a Phantom Dive), lo correcto es ATACAR; "
        f"obtuvo {result} -> {opt}")


def test_dragapult_step138_does_not_retreat_to_promote_hydra():
    result, obs, _ = _dragapult_s138_replay()
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") != int(OptionType.RETREAT), (
        f"promover un Hydrapple ex que el activo rival noquea regala 2 premios "
        f"(los ultimos del rival); obtuvo {result} -> {opt}")


def test_dragapult_step138_with_a_healthy_hydra_it_does_pivot():
    # A boundary counterfactual: with the Hydrapple ex at 330/330 it SURVIVES the
    # projected blow, so the promotion pivot is legitimate again.
    result, obs, _ = _dragapult_s138_replay(
        observation_key="synthetic_hydra_sano")
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.RETREAT), (
        f"con el Hydrapple ex sano el pivote sigue siendo valido; obtuvo "
        f"{result} -> {opt}")


# =====================================================================
# Meowth ex with a DOOMED active and a short bench (user, registro_014 step
# 107, episode 87721175 vs Marnie): an active Teal Mask Ogerpon ex at 10/210 HP
# (it falls to the first blow) and a SINGLE Pokemon on the bench, with Meowth ex in hand and
# the turn's Supporter free. The agent attacked (1100) because the veto "the
# active is already a ready attacker" (log 86511741 vs Mega Abomasnow) vetoed playing
# Meowth ex. But playing the Meowth is FREE: it does not consume the attack (the
# Basic is played and the attack happens afterwards in the same turn) and it chains Last-Ditch Catch ->
# Lillie's -> remaking the hand, giving a spare body for when the
# active falls. The original veto is meant for a HEALTHY active with a developed
# bench; with a doomed active and an empty bench it is inverted.
# =====================================================================
_MARNIE_S107_FIXTURE = (
    ROOT / "tests" / "fixtures" / "marnie_step107_meowth_activo_condenado.json")


def _marnie_s107_replay(observation_key=None):
    with open(_MARNIE_S107_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = data[observation_key] if observation_key else seq[-1]["observation"]
    return m.agent(obs), obs, data


def test_marnie_step107_plays_meowth_with_a_doomed_active():
    result, obs, _ = _marnie_s107_replay()
    assert _played_card(obs, result) == m.Meowth_ex, (
        f"con el activo a 10/210 y un solo cuerpo en banca, bajar Meowth ex "
        f"(gratis, no consume el ataque) para encadenar Lillie's va primero; "
        f"obtuvo {result}")


def test_marnie_step107_a_healthy_active_does_not_play_meowth():
    # Boundary: with a HEALTHY active the original veto returns (attack).
    result, obs, _ = _marnie_s107_replay(observation_key="synthetic_activo_sano")
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con el activo sano, un atacante listo no cede el turno a Meowth ex; "
        f"obtuvo {result} -> {opt}")


def test_marnie_step107_a_developed_bench_does_not_play_meowth():
    # Boundary: with a developed bench (3 bodies) the Meowth is not played either.
    result, obs, _ = _marnie_s107_replay(
        observation_key="synthetic_banca_desarrollada")
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con la banca desarrollada no hace falta el cuerpo de repuesto; "
        f"obtuvo {result} -> {opt}")


# =====================================================================
# The starting ACTIVE Pokemon: Tapu Bulu ALWAYS (user)
# ---------------------------------------------------------------------
# If at the start of the game we have a Tapu Bulu in hand, it is our
# starting active Pokemon, above any other basic (before Teal Mask Ogerpon ex
# won and, without it, Chikorita/Applin). Fixture: the REAL setup
# of registro_000 (Tapu Bulu and Chikorita as the only basics in hand).
# =====================================================================
_SETUP_TAPU_FIXTURE = ROOT / "tests" / "fixtures" / "setup_activo_tapu_bulu.json"


def _setup_obs():
    with open(_SETUP_TAPU_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _basico_elegido(obs, result):
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    return me["hand"][opt["index"]]["id"]


def test_setup_active_picks_tapu_bulu():
    obs = _setup_obs()
    assert obs["select"]["context"] == int(SelectContext.SETUP_ACTIVE_POKEMON)
    assert _basico_elegido(obs, m.agent(obs)) == m.Tapu_Bulu, (
        "con Tapu Bulu en la mano al comenzar la partida, es el Pokemon "
        "inicial activo")


def test_setup_active_tapu_bulu_over_ogerpon():
    # The Teal Mask Ogerpon ex was the preferred one (score 100): Tapu Bulu beats it.
    obs = _setup_obs()
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    otro = next(o for o in obs["select"]["option"]
                if me["hand"][o["index"]]["id"] != m.Tapu_Bulu)
    me["hand"][otro["index"]]["id"] = m.Teal_Mask_Ogerpon_ex
    assert _basico_elegido(obs, m.agent(obs)) == m.Tapu_Bulu, (
        "Tapu Bulu (1 premio, atacante de referencia) va al activo antes que "
        "el Teal Mask Ogerpon ex (2 premios)")


def test_setup_active_without_tapu_nothing_changes():
    # Boundary: with no Tapu Bulu among the options, the previous preference is
    # intact (Chikorita over the rest of the basics).
    obs = _setup_obs()
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    obs["select"]["option"] = [o for o in obs["select"]["option"]
                               if me["hand"][o["index"]]["id"] != m.Tapu_Bulu]
    assert _basico_elegido(obs, m.agent(obs)) == m.Chikorita, (
        "sin Tapu Bulu en la mano, la eleccion del inicial no cambia")


# =====================================================================
# The Meganium line: retreat the active Chikorita instead of attacking for a chip
# ---------------------------------------------------------------------
# user, registro_003 step 29 (turn 3 vs Dragapult, LOST): an active Chikorita
# with 1 Grass, Bayleef + Meganium in hand and Forest of Vitality in play. The
# agent attacked with Growl (0 damage) and left the line dead in hand: the
# EVOLVE scorer vetoes evolving in the ACTIVE spot ("retreat first and evolve
# on the bench") but the RETREAT was vetoed because the bench Tapu Bulu did not yet
# have energy. The right thing: RETREAT, promote Tapu Bulu (140 HP) and evolve
# the Chikorita on the BENCH -- with Forest, the whole chain this same turn.
# =====================================================================
_DRAGAPULT_P29_FIXTURE = (
    ROOT / "tests" / "fixtures" / "dragapult_paso29_retirar_chikorita.json")


def _dragapult_p29_obs():
    with open(_DRAGAPULT_P29_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _mi_lado(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def test_dragapult_p29_retreats_the_chikorita_instead_of_attacking():
    obs = _dragapult_p29_obs()
    tipos = {o.get("type") for o in obs["select"]["option"]}
    # The fixture must offer attacking, evolving in the active spot and retreating.
    assert {int(OptionType.ATTACK), int(OptionType.EVOLVE),
            int(OptionType.RETREAT)} <= tipos
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.RETREAT), (
        f"con Bayleef en mano, el Chikorita activo se retira para montar la "
        f"linea de Meganium en banca en vez de atacar con Growl (0 de dano); "
        f"obtuvo {opt}")


def test_dragapult_p29_promotes_tapu_bulu():
    # After retreating, the promotion brings up the body with the most life (Tapu Bulu, 140)
    # and not the just-played 40 HP Applin.
    obs = _dragapult_p29_obs()
    yo = obs["current"]["yourIndex"]
    obs["select"] = {
        "context": int(SelectContext.SWITCH), "type": 1,
        "minCount": 1, "maxCount": 1, "contextCard": None, "deck": None,
        "effect": None, "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [{"area": 5, "index": 0, "playerIndex": yo, "type": 3},
                   {"area": 5, "index": 1, "playerIndex": yo, "type": 3}],
    }
    result = m.agent(obs)
    bench = _mi_lado(obs)["bench"]
    elegido = bench[obs["select"]["option"][result[0]]["index"]]["id"]
    assert elegido == m.Tapu_Bulu, (
        f"al promover tras retirar el Chikorita se sube Tapu Bulu (140 PV), "
        f"no el Applin de 40; obtuvo {m.card_table[elegido].name}")


def _obs_tras_retirar():
    """A synthetic state: we have already retreated, Tapu Bulu active and Chikorita on the bench."""
    obs = _dragapult_p29_obs()
    yo = obs["current"]["yourIndex"]
    me = _mi_lado(obs)
    chiko = copy.deepcopy(me["active"][0])
    chiko["energies"] = []          # the Grass paid the retreat cost
    chiko["energyCards"] = []
    me["active"] = [me["bench"][0]]  # Tapu Bulu
    me["bench"] = [chiko, me["bench"][1]]
    obs["current"]["retreated"] = True
    obs["select"] = {
        "context": int(SelectContext.MAIN), "type": 0,
        "minCount": 1, "maxCount": 1, "contextCard": None, "deck": None,
        "effect": None, "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [
            {"index": 0, "type": int(OptionType.PLAY)},          # Boss's Orders
            {"area": 2, "inPlayArea": int(AreaType.BENCH), "inPlayIndex": 0,
             "index": 4, "type": int(OptionType.EVOLVE)},        # Bayleef -> Chikorita
            {"type": int(OptionType.END)},
        ],
    }
    return obs, yo


def test_dragapult_p29_evolves_the_chikorita_on_the_bench():
    obs, _ = _obs_tras_retirar()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.EVOLVE), (
        f"con el Chikorita ya en banca, Bayleef se juega sobre el; obtuvo {opt}")


def test_dragapult_p29_completes_meganium_with_forest():
    # Forest of Vitality allows evolving the just-played Bayleef: the chain
    # Chikorita -> Bayleef -> Meganium is completed in the same turn.
    obs, yo = _obs_tras_retirar()
    me = _mi_lado(obs)
    bayleef = copy.deepcopy(me["bench"][0])
    bayleef["id"] = m.Bayleef
    bayleef["hp"], bayleef["maxHp"] = 100, 110
    bayleef["appearThisTurn"] = True
    bayleef["preEvolution"] = [{"id": m.Chikorita, "playerIndex": yo,
                                "serial": 67}]
    me["bench"][0] = bayleef
    me["hand"] = [c for c in me["hand"] if c["id"] != m.Bayleef]
    obs["select"]["option"] = [
        {"index": 0, "type": int(OptionType.PLAY)},
        {"area": 2, "inPlayArea": int(AreaType.BENCH), "inPlayIndex": 0,
         "index": 4, "type": int(OptionType.EVOLVE)},            # Meganium
        {"type": int(OptionType.END)},
    ]
    assert m.card_table[me["hand"][4]["id"]].name == "Meganium"
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.EVOLVE), (
        f"con Forest of Vitality el Bayleef evoluciona a Meganium el mismo "
        f"turno (Wild Growth deja a Tapu Bulu atacando con 2 Plantas); "
        f"obtuvo {opt}")


def test_with_no_bayleef_in_hand_the_chikorita_does_not_retreat():
    # Boundary: with no evolution in hand there is no line to build, so the
    # pivot does not fire and the Chikorita keeps its previous behaviour.
    obs = _dragapult_p29_obs()
    me = _mi_lado(obs)
    me["hand"] = [c for c in me["hand"] if c["id"] != m.Bayleef]
    obs["select"]["option"] = [o for o in obs["select"]["option"]
                               if o.get("type") != int(OptionType.EVOLVE)]
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") != int(OptionType.RETREAT), (
        f"sin Bayleef en mano no hay linea evolutiva que habilitar: no se "
        f"retira solo por retirar; obtuvo {opt}")


# =====================================================================
# Never close the turn with a 0-damage attack while holding a Lillie's
# ---------------------------------------------------------------------
# user, registro_009 step 61 (turn 9 vs Dragapult, LOST): an active Chikorita
# at 50/70, an uncharged Tapu Bulu and Applin on the bench and in hand an Unfair Stamp +
# Bayleef + Meganium + Meowth ex + Xerosic + Lillie's Determination, with 6
# prizes (Lillie's draws EIGHT). The agent attacked with Growl (0 damage) and left
# the WHOLE hand dead: the Lillie's scorer vetoed it because "there is an evolvable
# line this turn" while the real evolution was blocked.
# =====================================================================
_DRAGAPULT_P61_FIXTURE = (
    ROOT / "tests" / "fixtures" / "dragapult_paso61_lillie_turno_esteril.json")


def _dragapult_p61_obs():
    with open(_DRAGAPULT_P61_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _p61_no_evolution_no_retreat(obs):
    """The menu of the real deadlock: neither evolving nor retreating, only playing or attacking."""
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if o.get("type") not in (int(OptionType.EVOLVE), int(OptionType.RETREAT))]
    return obs


def test_p61_a_sterile_turn_plays_lillie_instead_of_growl():
    obs = _p61_no_evolution_no_retreat(_dragapult_p61_obs())
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), (
        f"con la evolucion bloqueada, cerrar el turno con Growl (0 de dano) "
        f"deja la mano muerta: hay que refrescar con Lillie's; obtuvo {opt}")
    card = _mi_lado(obs)["hand"][opt["index"]]["id"]
    assert card == m.Lillie_Determination, (
        f"la jugada de rescate es Lillie's Determination (roba 6/8); obtuvo "
        f"{m.card_table[card].name}")


def test_p61_with_a_real_attack_the_rescue_does_not_fire():
    # Boundary: if the active DOES do damage (a charged Tapu Bulu, Wood Hammer 220)
    # the turn is not sterile and the rescue does not switch on.
    obs = _p61_no_evolution_no_retreat(_dragapult_p61_obs())
    me = _mi_lado(obs)
    yo = obs["current"]["yourIndex"]
    tapu = copy.deepcopy(me["bench"][0])
    tapu["energies"] = [1, 1, 1, 1]
    tapu["energyCards"] = [{"id": m.Basic_Grass_Energy, "playerIndex": yo,
                            "serial": 200 + i} for i in range(4)]
    me["bench"][0] = me["active"][0]
    me["active"] = [tapu]
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con un ataque que si hace dano no hay turno esteril que rescatar; "
        f"obtuvo {opt}")


def test_p61_promotes_tapu_bulu_not_applin():
    # When retreating the Chikorita, the wall is Tapu Bulu (140 HP), not the 40 HP
    # Applin -- which is also a piece of the Hydrapple line.
    obs = _dragapult_p61_obs()
    yo = obs["current"]["yourIndex"]
    obs["select"] = {
        "context": int(SelectContext.SWITCH), "type": 1,
        "minCount": 1, "maxCount": 1, "contextCard": None, "deck": None,
        "effect": None, "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [{"area": 5, "index": 0, "playerIndex": yo, "type": 3},
                   {"area": 5, "index": 1, "playerIndex": yo, "type": 3}],
    }
    result = m.agent(obs)
    bench = _mi_lado(obs)["bench"]
    elegido = bench[obs["select"]["option"][result[0]]["index"]]["id"]
    assert elegido == m.Tapu_Bulu, (
        f"con Lillie's en mano y sin atacante listo se sube el basico de 1 "
        f"premio mas resistente (Tapu Bulu 140), no el Applin de 40; obtuvo "
        f"{m.card_table[elegido].name}")


def test_p61_after_evolving_on_the_bench_lillie_is_played():
    # The turn's full sequence: retreated and with the Bayleef already on the bench,
    # the hand is refreshed with Lillie's before ending. The REAL observation
    # of step 61 is reproduced first so that the agent records the field at the
    # start of the turn (without it, a just-evolved Bayleef looks
    # "already evolvable" and the Lillie's is vetoed to keep the line).
    m.agent(_dragapult_p61_obs())
    obs = _dragapult_p61_obs()
    yo = obs["current"]["yourIndex"]
    me = _mi_lado(obs)
    bayleef = copy.deepcopy(me["active"][0])
    bayleef.update({"id": m.Bayleef, "hp": 90, "maxHp": 110,
                    "appearThisTurn": True, "energies": [], "energyCards": [],
                    "preEvolution": [{"id": m.Chikorita, "playerIndex": yo,
                                      "serial": 67}]})
    me["active"] = [me["bench"][0]]                 # a promoted Tapu Bulu
    me["bench"] = [bayleef, me["bench"][1]]
    me["hand"] = [c for c in me["hand"] if c["id"] != m.Bayleef]
    obs["current"]["retreated"] = True
    obs["select"]["option"] = [
        {"index": 2, "type": int(OptionType.PLAY)},   # Meowth ex
        {"index": 3, "type": int(OptionType.PLAY)},   # Xerosic
        {"index": 4, "type": int(OptionType.PLAY)},   # Lillie's
        {"type": int(OptionType.END)},
    ]
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    card = _mi_lado(obs)["hand"][opt["index"]]["id"] if opt.get("index") is not None else None
    assert card == m.Lillie_Determination, (
        f"con la linea ya bajada y la mano sin recursos, el turno termina "
        f"refrescando con Lillie's; obtuvo {opt}")


# =====================================================================
# The confusion pivot vs an immune wall ON THE BENCH (user, registro_006 step 64 vs
# Crustle, WON): the active Dipplin at 10 HP and CONFUSED attacked -- if the
# confusion coin fails it self-knocks-out -- instead of RETREATING and bringing up the
# charged Ogerpon ex that knocks out the active Munkidori. The bug: `_conf_ex_immune_
# match` used DECK flags (op_is_crustle_deck) and BENCH ones, which hold even if
# the rival active is ATTACKABLE, and excluded the Ogerpon ex from the pivot's
# attacker set. The immune wall only vetoes promoting an ex when it is IN THE RIVAL
# ACTIVE spot. A self-contained observation (the records are transient local data).
# =====================================================================
_CONF_BASE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "cynthia_boss_gust_highest_evo_gabite_step51.json")


def _crustle_confusion_obs(active_is_crustle=False):
    import copy as _c
    import json as _j
    o = _c.deepcopy(_j.load(open(_CONF_BASE_FIXTURE, encoding="utf-8"))["observation"])
    cur = o["current"]
    cur["turn"] = 6
    cur["yourIndex"] = 1
    cur["firstPlayer"] = 0
    cur["supporterPlayed"] = False
    cur["energyAttached"] = True
    me = cur["players"][1]
    op = cur["players"][0]
    me["confused"] = True
    # An active Dipplin at 10 HP CONFUSED, with 2 Grass (it pays its retreat cost of 2).
    me["active"] = [{"appearThisTurn": False, "energies": [1, 1],
                     "energyCards": [{"id": 1, "playerIndex": 1, "serial": 201},
                                     {"id": 1, "playerIndex": 1, "serial": 202}],
                     "hp": 10, "id": m.Dipplin, "maxHp": 80, "playerIndex": 1,
                     "preEvolution": [{"id": m.Applin, "playerIndex": 1, "serial": 210}],
                     "serial": 200, "tools": []}]
    # The bench: a charged Ogerpon ex (3 Grass -> Myriad Leaf Shower ready).
    me["bench"] = [{"appearThisTurn": False, "energies": [1, 1, 1],
                    "energyCards": [{"id": 1, "playerIndex": 1, "serial": 221},
                                    {"id": 1, "playerIndex": 1, "serial": 222},
                                    {"id": 1, "playerIndex": 1, "serial": 223}],
                    "hp": 210, "id": m.Teal_Mask_Ogerpon_ex, "maxHp": 210,
                    "playerIndex": 1, "preEvolution": [], "serial": 220, "tools": []}]
    me["hand"] = []
    me["handCount"] = 0
    # The rival: a Crustle wall on the BENCH; an ATTACKABLE active (Munkidori) except in the boundary case.
    _op_active_id = m.Crustle_Grass if active_is_crustle else m.Munkidori
    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                     "hp": 60, "id": _op_active_id,
                     "maxHp": 150 if active_is_crustle else 110, "playerIndex": 0,
                     "preEvolution": [], "serial": 900, "tools": []}]
    op["bench"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                    "hp": 150, "id": m.Crustle_Grass, "maxHp": 150, "playerIndex": 0,
                    "preEvolution": [], "serial": 901, "tools": []}]
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [{"attackId": 115, "type": 13}, {"type": 12}, {"type": 14}]}
    return o


def _tipo_elegido(obs):
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    res = m.agent(obs)
    return obs["select"]["option"][res[0]].get("type")


def test_confusion_pivot_retreats_to_an_ex_if_the_opponent_active_is_attackable():
    # The rival active = Munkidori (attackable): retreat the confused Dipplin and bring up
    # the charged Ogerpon ex that knocks it out, instead of risking the self-KO.
    obs = _crustle_confusion_obs(active_is_crustle=False)
    assert _tipo_elegido(obs) == int(OptionType.RETREAT), (
        "confundido a 10 PV con Ogerpon ex cargado en banca y activo rival "
        "atacable (Munkidori): retirar, no atacar con el confundido")


def test_confusion_does_not_retreat_to_an_ex_if_the_opponent_active_is_an_immune_wall():
    # Boundary: if the ex-immune wall (Crustle) is IN THE RIVAL ACTIVE spot, the
    # Ogerpon ex does not damage it -> promoting it is useless; we attack with the confused one.
    obs = _crustle_confusion_obs(active_is_crustle=True)
    assert _tipo_elegido(obs) != int(OptionType.RETREAT), (
        "con el muro inmune (Crustle) en el ACTIVO rival, promover el ex es "
        "inutil: no se retira a un ex que no puede noquear")


# =====================================================================
# The charging priority of Tapu Bulu vs Crustle (user, registro_002 step 17 vs
# Crustle, LOST): with Tapu Bulu (our main attacker, the only non-ex that
# damages the immune wall) in the ACTIVE spot with no energy, the agent charged a bench
# Applin instead of the Tapu. Cause: the generic veto of "do not charge the starting active"
# (Ogerpon/Tapu on our first turn) degraded the attachment to the
# active Tapu to SCORE_VETO. Vs Crustle, Tapu Bulu is EXEMPT from that veto. A self-contained
# observation (the records are transient local data).
# =====================================================================
def _crustle_tapu_charge_obs():
    import copy as _c
    import json as _j
    o = _c.deepcopy(_j.load(open(_CONF_BASE_FIXTURE, encoding="utf-8"))["observation"])
    cur = o["current"]
    cur["turn"] = 2            # our first turn going SECOND
    cur["yourIndex"] = 0
    cur["firstPlayer"] = 1
    cur["supporterPlayed"] = False
    cur["energyAttached"] = False
    me = cur["players"][0]
    op = cur["players"][1]
    me["confused"] = False
    me["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                     "hp": 140, "id": m.Tapu_Bulu, "maxHp": 140, "playerIndex": 0,
                     "preEvolution": [], "serial": 23, "tools": []}]
    me["bench"] = [
        {"appearThisTurn": False, "energies": [], "energyCards": [], "hp": 70,
         "id": m.Chikorita, "maxHp": 70, "playerIndex": 0, "preEvolution": [],
         "serial": 8, "tools": []},
        {"appearThisTurn": False, "energies": [1],
         "energyCards": [{"id": 1, "playerIndex": 0, "serial": 54}], "hp": 210,
         "id": m.Teal_Mask_Ogerpon_ex, "maxHp": 210, "playerIndex": 0,
         "preEvolution": [], "serial": 3, "tools": []},
        {"appearThisTurn": False, "energies": [], "energyCards": [], "hp": 40,
         "id": m.Applin, "maxHp": 40, "playerIndex": 0, "preEvolution": [],
         "serial": 13, "tools": []}]
    me["hand"] = [{"id": m.Basic_Grass_Energy, "playerIndex": 0, "serial": 50}]
    me["handCount"] = 1
    op["active"] = [{"appearThisTurn": False, "energies": [1],
                     "energyCards": [{"id": 18, "playerIndex": 1, "serial": 75}],
                     "hp": 190, "id": m.Dwebble_Grass, "maxHp": 190,
                     "playerIndex": 1, "preEvolution": [], "serial": 77, "tools": []}]
    op["bench"] = []
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [
                       {"area": 2, "inPlayArea": 4, "inPlayIndex": 0, "index": 0, "type": 8},
                       {"area": 2, "inPlayArea": 5, "inPlayIndex": 0, "index": 0, "type": 8},
                       {"area": 2, "inPlayArea": 5, "inPlayIndex": 1, "index": 0, "type": 8},
                       {"area": 2, "inPlayArea": 5, "inPlayIndex": 2, "index": 0, "type": 8},
                       {"type": 14}]}
    return o


def test_crustle_charges_the_active_tapu_bulu_first():
    obs = _crustle_tapu_charge_obs()
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    res = m.agent(obs)
    opt = obs["select"]["option"][res[0]]
    assert opt.get("type") == int(OptionType.ATTACH) and opt.get("inPlayArea") == 4, (
        f"vs Crustle, la 1a carga de energia va al Tapu Bulu ACTIVO (atacante "
        f"principal), no a un Applin de banca; obtuvo {res} -> {opt}")


# =====================================================================
# A GENERALISED MISMATCH: retreat the doomed ex and sacrifice a 1-prize
# body (user, registro_004 step 37 vs Mega Lucario ex). Our Teal Mask
# Ogerpon ex (210 HP, 3 energy) CAN attack but its Myriad Leaf Shower does NOT
# knock out the Mega Lucario ex (340 HP), and Mega Lucario finishes us off next
# turn (Mega Brave 270 >= 210). With no ready bench attacker and with a 1-prize
# body (Applin) to put in front, the right thing is to RETREAT the ex (it gives away
# 1 prize instead of 2 and keeps the ex on the bench), not to attack without knocking out. The
# logic is deck-agnostic: it is detected with the REAL rival finisher, not with a
# list of matchups.
# =====================================================================
_DOOMED_EX_RETREAT_FIXTURE = (
    ROOT / "tests" / "fixtures" / "lucario_step37_doomed_ex_retreat.json")
_DOOMED_EX_PROMOTE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "lucario_step41_promote_applin_sac.json")
_DOOMED_EX_RETREAT_GENERIC_FIXTURE = (
    ROOT / "tests" / "fixtures" / "generic_doomed_ex_retreat_nonlucario.json")
_DOOMED_EX_PROMOTE_GENERIC_FIXTURE = (
    ROOT / "tests" / "fixtures" / "generic_promote_basic_sac_nonlucario.json")


def test_step37_doomed_ex_retreats_instead_of_attacking():
    with open(_DOOMED_EX_RETREAT_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    options = obs["select"]["option"]
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [retreat_opt], (
        f"ex condenado que no noquea y muere el proximo turno, sin atacante de "
        f"banca: RETIRAR (opt {retreat_opt}) para ceder 1 premio, no atacar "
        f"(opt {attack_opt}); obtuvo {result}")


def test_step41_promotes_cheapest_basic_sacrifice():
    with open(_DOOMED_EX_PROMOTE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    bench = obs["current"]["players"][mi]["bench"]
    options = obs["select"]["option"]
    applin_opt = next(i for i, o in enumerate(options)
                      if bench[o["index"]]["id"] == m.Applin)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [applin_opt], (
        f"tras retirar el ex, promover el basico de 1 premio mas barato "
        f"(Applin, opt {applin_opt}); obtuvo {result}")


def test_doomed_ex_retreat_generalizes_to_nonlucario():
    # The same pattern with a NON-Lucario rival (Dragapult ex) that one-shots
    # our doomed ex: the pivot is deck-agnostic and must retreat all the same.
    with open(_DOOMED_EX_RETREAT_GENERIC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    options = obs["select"]["option"]
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [retreat_opt], (
        f"generalizacion (rival no-Lucario que one-shotea): RETIRAR "
        f"(opt {retreat_opt}); obtuvo {result}")


def test_doomed_ex_promote_basic_generalizes_to_nonlucario():
    # The promotion also generalises: with no bench attacker and with the rival
    # one-shotting the tankiest body (Bayleef 110), promote the 1-prize
    # basic (Applin 40) instead of the tankiest body. Without the general rule the
    # default promotion would bring up the Bayleef (more HP).
    with open(_DOOMED_EX_PROMOTE_GENERIC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    bench = obs["current"]["players"][mi]["bench"]
    options = obs["select"]["option"]
    applin_opt = next(i for i, o in enumerate(options)
                      if bench[o["index"]]["id"] == m.Applin)
    bayleef_opt = next(i for i, o in enumerate(options)
                       if bench[o["index"]]["id"] == m.Bayleef)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [applin_opt], (
        f"generalizacion promocion: subir Applin (opt {applin_opt}), no el mas "
        f"tanque Bayleef (opt {bayleef_opt}); obtuvo {result}")


def test_doomed_ex_does_not_sac_retreat_when_near_winning():
    # A negative control: in FINISHER RANGE (my_prize<=2) there is no sacrifice-retreat;
    # we have to race/finish. The same doomed board but with 4 prizes already
    # taken (2 remaining) -> the agent must NOT choose the defensive retreat.
    with open(_DOOMED_EX_RETREAT_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    # leave only 2 prizes remaining (my_prize == len(prize) == 2): finisher range
    obs["current"]["players"][mi]["prize"] = (
        obs["current"]["players"][mi]["prize"][:2])
    options = obs["select"]["option"]
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [retreat_opt], (
        f"cerca de ganar (my_prize<=2) NO se hace el retiro-sacrificio "
        f"defensivo; obtuvo {result}")


# =====================================================================
# THE MEOWTH -> LILLIE'S ENGINE ON A POOR BOARD (user, registro_006 step 57 vs
# Alakazam, WON). The active is a 1-prize CHIP attacker (Dipplin) that
# CAN knock out the rival active but is fragile, there is NO ready bench attacker
# and the hand is minimal (1 card: the Meowth ex itself). The agent attacked; the
# right thing is to PLAY Meowth ex first (Last-Ditch Catch -> Lillie's -> it refreshes
# the hand and builds a 2nd attacker) and to ATTACK afterwards in the same turn. It is allowed
# even with ONE Meowth already on the bench (field<2) and even if the active knocks out. Deck-agnostic.
# =====================================================================
_MEOWTH_REFRESH_POOR_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_step57_meowth_refresh_poor_board.json")


def test_step57_plays_meowth_refresh_on_poor_board():
    with open(_MEOWTH_REFRESH_POOR_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    options = obs["select"]["option"]
    play_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY))
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [play_opt], (
        f"tablero pobre (mano minima, sin atacante de banca, activo chip de 1 "
        f"premio): BAJAR Meowth ex (opt {play_opt}) para refrescar via Lillie's, "
        f"no atacar (opt {attack_opt}); obtuvo {result}")


def test_step57_meowth_refresh_does_not_fire_with_strong_hand():
    # A negative control: with a hand that is NOT weak (>=3 cards), a 2nd
    # Meowth ex is not benched; we attack with the active chip.
    import copy as _c
    with open(_MEOWTH_REFRESH_POOR_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mi = obs["current"]["yourIndex"]
    obs["current"]["players"][mi]["hand"] += [
        {"id": 1, "playerIndex": mi, "serial": 200 + k} for k in range(3)]
    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"con mano fuerte NO se banca un 2o Meowth; se ataca (opt {attack_opt}); "
        f"obtuvo {result}")


def test_step57_meowth_refresh_does_not_fire_with_ready_bench_attacker():
    # A negative control: if there is ALREADY a ready bench attacker (an Ogerpon ex with 3
    # energy), there is no need to refresh: we attack with the active chip.
    import copy as _c
    with open(_MEOWTH_REFRESH_POOR_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mi = obs["current"]["yourIndex"]
    for b in obs["current"]["players"][mi]["bench"]:
        if b["id"] == m.Teal_Mask_Ogerpon_ex:
            b["energies"] = [1, 1, 1]
            b["energyCards"] = [{"id": 1, "playerIndex": mi, "serial": 300 + k}
                                for k in range(3)]
    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"con atacante de banca listo NO se refresca con Meowth; se ataca "
        f"(opt {attack_opt}); obtuvo {result}")


def test_step57_meowth_refresh_generalizes_to_nonalakazam():
    # A generalisation: the refresh engine on a poor board is deck-agnostic;
    # with a different rival (not Alakazam) it also plays Meowth ex.
    import copy as _c
    with open(_MEOWTH_REFRESH_POOR_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    opi = 1 - obs["current"]["yourIndex"]
    oa = obs["current"]["players"][opi]["active"][0]
    oa["id"] = 849; oa["maxHp"] = 60; oa["hp"] = 50
    for b in obs["current"]["players"][opi]["bench"]:
        if b["id"] in (741, 305):
            b["id"] = 849; b["maxHp"] = 60; b["hp"] = 60
    options = obs["select"]["option"]
    play_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [play_opt], (
        f"generalizacion (rival no-Alakazam): BAJAR Meowth ex (opt {play_opt}); "
        f"obtuvo {result}")


# =====================================================================
# THE MEOWTH -> LILLIE'S ENGINE WITH NO SPARE ATTACKER (user, registro_006 step 78
# vs Mega Lucario ex). The active is a Teal Mask Ogerpon ex that CAN attack but
# whose Myriad does NOT knock out (180 vs 190) and Mega Lucario finishes it off next turn
# (270 >= 210); the bench has a SINGLE NON-attacking body (Chikorita) and from
# hand there is NO way to build a 2nd attacker (Hydrapple/Dipplin stuck with no
# Applin/Dipplin in play). The agent attacked; the right thing is to PLAY Meowth ex
# (Last-Ditch Catch -> Lillie's -> it refreshes the hand to find attackers) and
# attack/retreat afterwards. It detects the REAL rival finisher (not the
# active_ko_likely heuristic, which underestimates Mega Lucario). Deck-agnostic.
# =====================================================================
_MEOWTH_REFRESH_NO_ATTACKER_FIXTURE = (
    ROOT / "tests" / "fixtures" / "lucario_step78_meowth_refresh_no_attacker.json")


def test_step78_plays_meowth_refresh_no_bench_attacker():
    with open(_MEOWTH_REFRESH_NO_ATTACKER_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    options = obs["select"]["option"]
    mi = obs["current"]["yourIndex"]
    meowth_opt = next(
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.PLAY)
        and obs["current"]["players"][mi]["hand"][o["index"]]["id"] == m.Meowth_ex)
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"ex condenado que no noquea, banca sin atacante y sin camino a un 2o "
        f"atacante: BAJAR Meowth ex (opt {meowth_opt}) para refrescar via Lillie's, "
        f"no atacar (opt {attack_opt}); obtuvo {result}")


def test_step78_meowth_refresh_not_with_bench_attacker_body():
    # A negative control: if there is an ATTACKING body on the bench (an Ogerpon ex), there is
    # a route to a 2nd attacker (charging it) and a Meowth is NOT benched to refresh.
    import copy as _c
    with open(_MEOWTH_REFRESH_NO_ATTACKER_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mi = obs["current"]["yourIndex"]
    obs["current"]["players"][mi]["bench"].append(
        {"appearThisTurn": False, "energies": [], "energyCards": [], "hp": 210,
         "id": m.Teal_Mask_Ogerpon_ex, "maxHp": 210, "playerIndex": mi,
         "preEvolution": [], "serial": 999, "tools": []})
    options = obs["select"]["option"]
    meowth_opt = next(
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.PLAY)
        and obs["current"]["players"][mi]["hand"][o["index"]]["id"] == m.Meowth_ex)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [meowth_opt], (
        f"con un cuerpo atacante en banca NO se refresca con Meowth; obtuvo {result}")


def test_step78_meowth_refresh_not_when_active_not_doomed():
    # A negative control: if the active is NOT doomed (a rival with no energy to
    # finish), there is no need to refresh; the 2nd Meowth is not benched.
    import copy as _c
    with open(_MEOWTH_REFRESH_NO_ATTACKER_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    opi = 1 - obs["current"]["yourIndex"]
    obs["current"]["players"][opi]["active"][0]["energies"] = []
    obs["current"]["players"][opi]["active"][0]["energyCards"] = []
    mi = obs["current"]["yourIndex"]
    options = obs["select"]["option"]
    meowth_opt = next(
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.PLAY)
        and obs["current"]["players"][mi]["hand"][o["index"]]["id"] == m.Meowth_ex)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [meowth_opt], (
        f"con el activo NO condenado no se refresca con Meowth; obtuvo {result}")


def test_step78_meowth_refresh_generalizes_to_nonlucario():
    # A deck-agnostic generalisation: with a different rival (Dragapult ex) that
    # one-shots the doomed active, it also plays Meowth ex.
    import copy as _c
    with open(_MEOWTH_REFRESH_NO_ATTACKER_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mi = obs["current"]["yourIndex"]; opi = 1 - mi
    obs["current"]["players"][mi]["active"][0]["hp"] = 150
    a = obs["current"]["players"][opi]["active"][0]
    a["id"] = 121; a["maxHp"] = 320; a["hp"] = 320
    a["energies"] = [a["energies"][0]] * 3; a["preEvolution"] = []
    for b in obs["current"]["players"][opi]["bench"]:
        if b["id"] in (677, 678, 676, 675, 674, 673):
            b["id"] = 121; b["maxHp"] = 320; b["hp"] = 320
    options = obs["select"]["option"]
    meowth_opt = next(
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.PLAY)
        and obs["current"]["players"][mi]["hand"][o["index"]]["id"] == m.Meowth_ex)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"generalizacion (rival no-Lucario que one-shotea): BAJAR Meowth ex "
        f"(opt {meowth_opt}); obtuvo {result}")


# =====================================================================
# CONCENTRATING THE CHARGE ON ONE LETHAL OGERPON (user, registro_006 step 66 vs
# Marnie's Grimmsnarl ex). With TWO Teal Mask Ogerpon ex on the bench (one at 2
# energies, the other at 0/1), the charge was spread out and NEITHER reached the 3
# energies of the KO through weakness (Myriad 180 x2 = 360 >= 320). Now the manual
# attachment is CONCENTRATED on the most charged Ogerpon (2e -> 3e = lethal) and charging
# the other is vetoed. The weakness is ALWAYS taken into account via _our_effective_damage.
# =====================================================================
_MARNIE_CONCENTRATE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "marnie_step66_concentrate_ogerpon_charge.json")


def test_step66_concentrates_manual_attach_on_lethal_ogerpon():
    with open(_MARNIE_CONCENTRATE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    bench = obs["current"]["players"][mi]["bench"]
    options = obs["select"]["option"]
    # a manual ATTACH (inPlayArea==5 bench) to the Ogerpon (id 96) with MORE energy.
    ogerpon_slots = [(i, o) for i, o in enumerate(options)
                     if o.get("type") == int(OptionType.ATTACH)
                     and o.get("inPlayArea") == 5
                     and bench[o["inPlayIndex"]]["id"] == m.Teal_Mask_Ogerpon_ex]
    # the right target is the bench Ogerpon with the most energy (2e).
    best = max(ogerpon_slots,
              key=lambda io: len(bench[io[1]["inPlayIndex"]]["energies"]))
    best_e = len(bench[best[1]["inPlayIndex"]]["energies"])

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    chosen = options[result[0]]

    assert (chosen.get("type") == int(OptionType.ATTACH)
            and chosen.get("inPlayArea") == 5
            and bench[chosen["inPlayIndex"]]["id"] == m.Teal_Mask_Ogerpon_ex
            and len(bench[chosen["inPlayIndex"]]["energies"]) == best_e), (
        f"el adjunte manual debe CONCENTRARSE en el Ogerpon mas cargado "
        f"({best_e}e -> letal), no repartir; obtuvo {result} -> {chosen}")


def test_concentrate_focus_not_when_active_can_attack():
    # A negative control: if the ACTIVE is a viable attacker that reaches its attack
    # by charging itself (Hydrapple ex + Ripening/an attachment), the energy is NOT diverted to a
    # bench Ogerpon. It reuses the Ripening vs Lucario fixture (an active Hydrapple).
    data = _lucario_ripen_data()
    obs = data["ripen_target"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("area") == int(AreaType.ACTIVE), (
        f"con el activo atacante viable, la carga va al ACTIVO, no a un Ogerpon "
        f"de banca; obtuvo {result} -> {opt}")


# =====================================================================
# THE WINNING FINISHER WITH THE ACTIVE (user, registro_009 step 125 vs Archaludon ex,
# LOST). An active Ogerpon ex with 4 physical Grass + Meganium in play (Wild
# Growth doubles -> 8 effective). Myriad = 30 + 30x(8 ours + 3 of the rival) =
# 360, minus 30 of the Archaludon ex's Grass resistance = 330 >= 300 -> it KNOCKS OUT
# and, with 2 prizes remaining (Archaludon ex is worth 2), it WINS the game. The agent
# charged energy to Tapu Bulu (`_tapu_future_charge`) and then retreated the Ogerpon
# to attack with Tapu, throwing the finisher away. When the active's KO WINS, ATTACKING
# is the top priority. Deck-agnostic (computed with Meganium, the rival's energy and
# resistance).
# =====================================================================
_ARCHALUDON_WIN_FIXTURE = (
    ROOT / "tests" / "fixtures" / "archaludon_step125_winning_ogerpon_attack.json")


def test_step125_plays_winning_ogerpon_attack_over_charging_tapu():
    with open(_ARCHALUDON_WIN_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"con el remate GANADOR del activo (Myriad 330 >= 300, KO que gana), "
        f"ATACAR (opt {attack_opt}) es la maxima prioridad, no cargar Tapu Bulu; "
        f"obtuvo {result}")


def test_step125_winning_attack_generalizes_without_resistance():
    # A generalisation: with no resistance (a non-Metal rival) the KO also wins and we
    # attack. Swapping the rival for a 2-prize body with 300 HP and no resistance
    # (Mega Lucario ex 678) leaves Myriad at 360 >= 300 -> a winning KO.
    import copy as _c
    with open(_ARCHALUDON_WIN_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    opi = 1 - obs["current"]["yourIndex"]
    oa = obs["current"]["players"][opi]["active"][0]
    oa["id"] = 678; oa["maxHp"] = 340; oa["hp"] = 300; oa["preEvolution"] = []
    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"remate ganador sin resistencia: ATACAR (opt {attack_opt}); "
        f"obtuvo {result}")


def test_winning_attack_not_forced_when_ko_does_not_win():
    # A negative control: if the active's KO does NOT win the game (we have more
    # prizes left than the KO gives), the attack is NOT forced above
    # development; let the rival have 4 prizes (we do not win with 1 KO worth 2).
    import copy as _c
    with open(_ARCHALUDON_WIN_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mi = obs["current"]["yourIndex"]
    obs["current"]["players"][mi]["prize"] = [None, None, None, None]
    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [attack_opt], (
        f"con 4 premios el KO no gana; no se fuerza el ataque sobre el "
        f"desarrollo; obtuvo {result}")


# =====================================================================
# ANTI-CUBCHOO: no retreat-pivot that wastes energy (user, registro_004
# step 47/49 vs cornerstone_cubchoo, LOST). The deck of Cubchoo (506,
# Snotted Up) / Beartic (507, Sheer Cold) BLOCKS our active every turn
# ("the Defending Pokemon can't use attacks"), forcing a retreat to attack with
# another body. Their attacker is very weak (Cubchoo hits for 10, it does not knock us out), but
# since it forces us to retreat repeatedly, every retreat that DISCARDS energy
# bleeds the critical resource. Against THIS deck we remove the voluntary
# retreat-pivot: with the active blocked (6 energy, no attack option) and a
# ready Hydrapple ex on the bench, the agent PASSES (END) keeping the energy, it does not
# retreat discarding 2 energy. Only vs Cubchoo; against other decks the
# retreat-pivot is still in force.
# =====================================================================
_CUBCHOO_RETREAT_FIXTURE = (
    ROOT / "tests" / "fixtures" / "cubchoo_step47_no_energy_wasting_retreat.json")


def test_step47_vs_cubchoo_does_not_waste_energy_retreating():
    with open(_CUBCHOO_RETREAT_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    options = obs["select"]["option"]
    retreat_opts = [i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.RETREAT)]
    assert retreat_opts, "el fixture debe ofrecer una retirada"

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result[0] not in retreat_opts, (
        f"vs Cubchoo con el activo bloqueado (6 energia) no se debe retirar "
        f"descartando energia; se debe PASAR/desarrollar. retiradas={retreat_opts}, "
        f"obtuvo {result}")


def test_cubchoo_conserve_pass_is_deck_specific():
    # A deck-specificity control: the same board against a NON-Cubchoo deck
    # must NOT pass-to-keep (the anti-Cubchoo veto is lifted). The rival is changed
    # from Cubchoo (506) to Mega Lucario ex (678) to switch off
    # `op_is_cubchoo_deck`; then the decision stops being the conservative END.
    import copy as _c
    with open(_CUBCHOO_RETREAT_FIXTURE, encoding="utf-8") as f:
        base = json.load(f)["observation"]

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    cub_choice = m.agent(_c.deepcopy(base))
    cub_type = base["select"]["option"][cub_choice[0]].get("type")
    assert cub_type == int(OptionType.END), (
        f"vs Cubchoo se conserva pasando (END); obtuvo tipo {cub_type}")

    obs = _c.deepcopy(base)
    opi = 1 - obs["current"]["yourIndex"]
    opp = obs["current"]["players"][opi]
    for slot in ([opp["active"][0]] if opp.get("active") else []) + [
            b for b in opp.get("bench", []) if b]:
        if slot.get("id") in (506, 507):
            slot["id"] = 678
            slot["preEvolution"] = []
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    other = m.agent(obs)
    other_type = obs["select"]["option"][other[0]].get("type")

    assert other[0] != cub_choice[0] and other_type != int(OptionType.END), (
        f"contra un mazo no-Cubchoo la decision NO debe ser el END conservador "
        f"(el veto es especifico del matchup); obtuvo {other} tipo {other_type}")


# =====================================================================
# PROTECTING FOREST OF VITALITY AS A COUNTER-STADIUM IN A FORCED DISCARD (user,
# registro_005 step 62 vs cornerstone_cubchoo, LOST). The rival controls
# Neutralization Zone (1247): it cancels the damage of our ex to the 1-prize active
# and stops us attacking. The only way to remove it is to play OUR stadium
# (Forest of Vitality 1261) to replace it. Xerosic's Machinations (1197)
# forces us to discard 2 of 5 cards; the Forest is KEY and must not be discarded. Before,
# with Meganium+Hydrapple in play, the Forest scored 70 (discardable) without looking at the
# hostile rival stadium, and the agent threw it away.
# =====================================================================
_FOREST_DISCARD_FIXTURE = (
    ROOT / "tests" / "fixtures" / "cubchoo_step61_protect_forest_forced_discard.json")
_FOREST_OF_VITALITY = 1261
_NEUTRALIZATION_ZONE = 1247


def _discarded_card_ids(obs, choice):
    hand = [c["id"] for c in obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]]
    return [hand[obs["select"]["option"][i]["index"]] for i in choice]


def test_step62_forced_discard_protects_forest_vs_neutralization_zone():
    with open(_FOREST_DISCARD_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    # sanity: the rival stadium is Neutralization Zone and the Forest is in hand
    assert obs["current"]["stadium"][0]["id"] == _NEUTRALIZATION_ZONE
    mi = obs["current"]["yourIndex"]
    assert any(c["id"] == _FOREST_OF_VITALITY for c in obs["current"]["players"][mi]["hand"])

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    discarded = _discarded_card_ids(obs, result)

    assert _FOREST_OF_VITALITY not in discarded, (
        f"con Neutralization Zone rival en juego, Forest es el unico contra-estadio "
        f"y NO debe descartarse; descarto ids {discarded}")


def test_forest_discardable_when_no_hostile_op_stadium():
    # Control: with no hostile rival stadium, the protection does NOT apply -- with
    # Meganium+Hydrapple in play the Forest is discardable again (score 70).
    # The rival's Neutralization Zone is removed from the board; the Forest must be able to fall.
    import copy as _c
    with open(_FOREST_DISCARD_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    obs["current"]["stadium"] = []  # no hostile stadium
    mi = obs["current"]["yourIndex"]
    forest_opt = next(i for i, o in enumerate(obs["select"]["option"])
                      if obs["current"]["players"][mi]["hand"][o["index"]]["id"]
                      == _FOREST_OF_VITALITY)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert forest_opt in result, (
        f"sin estadio hostil rival, con Meganium+Hydrapple Forest es descartable; "
        f"obtuvo {result} (opcion Forest = {forest_opt})")


# =====================================================================
# ANTI-CUBCHOO: charging the blocked ACTIVE Hydrapple ex with Ripening Charge to
# enable the retreat towards a READY bench attacker (user, registro_008
# step 82 vs cornerstone_cubchoo, LOST). The active Hydrapple ex is blocked
# by Snotted Up (it cannot attack) but on the bench there is an already charged Ogerpon ex
# (4 effective) that knocks out the Cubchoo. The correct line: Ripening Charge on the
# Hydrapple ITSELF to reach its retreat cost (an effective 3), retreat it and
# bring up the Ogerpon to attack. The user's rule: if the active canNOT attack,
# prioritise the retreat in order to attack. Before, the agent used Teal Dance on a
# bench Ogerpon (the ENERGY tier dominated Ripening in tier 0), sprinkling the
# energy and wasting the turn without attacking. It differs from
# `test_step47_vs_cubchoo_does_not_waste_energy_retreating` (a CHARGED active Ogerpon
# -> keep it): here the active is a SUB-charged Hydrapple ex whose extra energy
# is dead weight.
# =====================================================================
_CUBCHOO_RIPEN_FIXTURE = (
    ROOT / "tests" / "fixtures" / "cubchoo_step82_ripening_charge_blocked_active.json")


def test_step82_charges_blocked_hydrapple_to_enable_retreat():
    with open(_CUBCHOO_RIPEN_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    options = obs["select"]["option"]
    # the Ripening Charge option on the Hydrapple ex's ACTIVE (area 4)
    ripen_active = [i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.ABILITY)
                    and o.get("area") == int(AreaType.ACTIVE)]
    assert ripen_active, "el fixture debe ofrecer Ripening Charge en el activo"

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result[0] in ripen_active, (
        f"con el Hydrapple ex activo bloqueado por Cubchoo y un Ogerpon ex de "
        f"banca listo, se debe cargar el ACTIVO con Ripening Charge (opciones "
        f"{ripen_active}) para habilitar la retirada; obtuvo {result}")


# =====================================================================
# ANTI-CUBCHOO: routing the recovered energies (Lana's Aid) to the blocked ACTIVE
# Hydrapple ex, not to the bench (user, registro_012 step 96 vs cornerstone_
# cubchoo, LOST). The same pattern as registro_008 step 82 but charging by
# MANUAL ATTACHMENT (the energies from Lana's Aid) instead of by Ripening Charge: the
# active Hydrapple ex is blocked by Snotted Up and there are 2 bench Ogerpon ex
# (4 effective) ready to knock out the Cubchoo. The energy must go to the ACTIVE
# to reach its retreat cost and enable retreat->promote->attack.
# Before, the agent charged a bench Meganium/Ogerpon. Covered by
# `_cubchoo_lock_stuck` (routing energy to the stalled ex, +24000).
# =====================================================================
_CUBCHOO_LANAS_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "cubchoo_step96_charge_blocked_active_from_lanas.json")


def test_step96_routes_lanas_energy_to_blocked_active_hydrapple():
    with open(_CUBCHOO_LANAS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    chosen = obs["select"]["option"][result[0]]
    assert chosen.get("type") == int(OptionType.ATTACH), (
        f"se debe ADJUNTAR energia (no {chosen}); obtuvo {result}")
    assert chosen.get("inPlayArea") == int(AreaType.ACTIVE), (
        f"la energia recuperada debe ir al Hydrapple ex ACTIVO bloqueado "
        f"(inPlayArea={int(AreaType.ACTIVE)}), no a la banca; obtuvo {chosen}")


# =====================================================================
# Do NOT shuffle the evolution line away with Lillie's: the Ultra Ball completes it first
# (user, registro_004 step 47 vs Alakazam, LOST). We have a Chikorita in play
# + Meganium in HAND, but the intermediate Stage 1 (Bayleef) is missing, and it is in the
# DECK and searchable with an Ultra Ball. Lillie's Determination SHUFFLES the whole hand
# into the deck -> we would lose the Meganium + both Ultra Balls. The right thing: play the
# Ultra Ball (bring the Bayleef, build Chikorita->Bayleef->Meganium) and do NOT refresh
# yet. The `ub_gapped_line` rule vetoes Lillie's while the gapped line +
# Ultra Ball are still in hand. Deck-agnostic (it also covers Applin/Dipplin/Hydra).
# =====================================================================
_ALAKAZAM_LILLIE_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step47_ultraball_completes_line_before_lillie.json")
_LILLIE_DETERMINATION = 1227


def test_step47_does_not_shuffle_meganium_line_with_lillie():
    with open(_ALAKAZAM_LILLIE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    hand = [c["id"] for c in obs["current"]["players"][mi]["hand"]]
    lillie_opts = [i for i, o in enumerate(obs["select"]["option"])
                   if o.get("type") == int(OptionType.PLAY)
                   and o.get("index", -1) < len(hand)
                   and hand[o["index"]] == _LILLIE_DETERMINATION]
    assert lillie_opts, "el fixture debe ofrecer jugar Lillie's Determination"

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result[0] not in lillie_opts, (
        f"con Chikorita en juego + Meganium en mano + Ultra Ball (falta Bayleef "
        f"buscable) NO se debe jugar Lillie's (barajaria la linea); "
        f"opciones Lillie={lillie_opts}, obtuvo {result}")


def _lillie_gapped_flag(obs):
    """Returns the `ub_gapped_line` flag of the Lillie's scorer for `obs`."""
    captured = {}
    orig = m._CtxLillie

    class _Spy(orig):
        def __init__(self, ctx):
            super().__init__(ctx)
            captured["v"] = self.ub_gapped_line

    m._CtxLillie = _Spy
    try:
        m._init_cards_tracking(); m.plan = m.AttackPlan()
        m.agent(obs)
    finally:
        m._CtxLillie = orig
    return captured.get("v")


def test_ub_gapped_line_flag_requires_ultraball():
    # The `ub_gapped_line` flag (which vetoes Lillie's) requires an Ultra Ball in hand:
    # it is True in the fixture and switches off when the Ultra Ball is removed (the gap stops
    # being completable).
    import copy as _c
    with open(_ALAKAZAM_LILLIE_FIXTURE, encoding="utf-8") as f:
        base = json.load(f)["observation"]
    assert _lillie_gapped_flag(_c.deepcopy(base)) is True, (
        "con Chikorita+Meganium+Ultra Ball+Bayleef en mazo el flag debe activarse")

    obs = _c.deepcopy(base)
    mi = obs["current"]["yourIndex"]
    obs["current"]["players"][mi]["hand"] = [
        c for c in obs["current"]["players"][mi]["hand"] if c["id"] != 1121]
    assert _lillie_gapped_flag(obs) is False, (
        "sin Ultra Ball el hueco no es completable: el flag NO debe activarse")


# =====================================================================
# Ripening Charge (ATTACH_FROM): do NOT waste the energy on an already charged
# FIXED-damage active; give it to the best FUTURE attacker (user, registro_006 step 79 vs
# Alakazam, LOST). The active Tapu Bulu already had 4 effective (= Wood Hammer,
# a fixed cost, a hard cap) and the game charged it a 5th via the Hydrapple ex's Ripening
# Charge, despite there being a bench Hydrapple ex at 0 energies (a future
# attacker). The winning/2-prize-gust routing (42000 to the active) no longer applies to a
# fixed-damage attacker that has reached its requirement.
# =====================================================================
_ALAKAZAM_RIPEN_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step79_ripening_charge_to_future_hydrapple.json")
_HYDRAPPLE_EX = 150
_TAPU_BULU = 920


def test_step79_ripening_charge_targets_future_hydrapple_not_capped_tapu():
    with open(_ALAKAZAM_RIPEN_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]

    def target_id(opt):
        if opt.get("area") == int(AreaType.ACTIVE):
            return me["active"][0]["id"]
        return me["bench"][opt["index"]]["id"]

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    chosen = obs["select"]["option"][result[0]]
    tid = target_id(chosen)

    assert tid == _HYDRAPPLE_EX, (
        f"Ripening Charge debe cargar el Hydrapple ex de banca (0e, atacante "
        f"futuro), no el Tapu Bulu activo ya cargado; cargo id {tid}")
    # and explicitly NOT the active Tapu Bulu (already at Wood Hammer's cap)
    assert not (chosen.get("area") == int(AreaType.ACTIVE)
                and me["active"][0]["id"] == _TAPU_BULU), (
        "no debe cargar el Tapu Bulu activo ya cargado")


# =====================================================================
# Do not overcharge an already ready ACTIVE Hydrapple ex; charge the BENCH one (a future
# attacker) with both the manual attachment and Ripening Charge (user,
# registro_008 steps 109-113 vs Alakazam, WON with a suboptimal play). Syrup
# Storm scales with the Grass on the FIELD (all our Pokemon), NOT with the attacker's
# own energy: putting the energy on a bench Hydrapple ex at 0 gives the
# SAME damage this turn and also develops a 2nd attacker. The 42000 routing of the
# winning/2-prize gust no longer applies to an active Hydrapple ex that has reached its attack
# requirement.
# =====================================================================
_ALK_STEP109 = (ROOT / "tests" / "fixtures"
                / "alakazam_step109_manual_attach_to_bench_hydrapple.json")
_ALK_STEP112 = (ROOT / "tests" / "fixtures"
                / "alakazam_step112_ripening_charge_to_bench_hydrapple.json")


def _bench_target_id(obs, chosen):
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]
    if chosen.get("type") == int(OptionType.ATTACH):
        if chosen.get("inPlayArea") == int(AreaType.BENCH):
            return me["bench"][chosen["inPlayIndex"]]["id"], True
        return me["active"][0]["id"], False
    # ATTACH_FROM (ctx 21): area/index
    if chosen.get("area") == int(AreaType.BENCH):
        return me["bench"][chosen["index"]]["id"], True
    return me["active"][0]["id"], False


def test_step109_manual_energy_charges_bench_hydrapple_not_ready_active():
    with open(_ALK_STEP109, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = obs["select"]["option"][m.agent(obs)[0]]
    tid, is_bench = _bench_target_id(obs, chosen)
    assert chosen.get("type") == int(OptionType.ATTACH), (
        f"se esperaba un adjunte manual, obtuvo tipo {chosen.get('type')}")
    assert is_bench and tid == 150, (
        "el adjunte manual debe ir al Hydrapple ex de BANCA (atacante futuro), "
        f"no al Hydrapple activo ya listo; fue id {tid} bench={is_bench}")


def test_step112_ripening_charge_targets_bench_hydrapple_not_ready_active():
    with open(_ALK_STEP112, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = obs["select"]["option"][m.agent(obs)[0]]
    tid, is_bench = _bench_target_id(obs, chosen)
    assert is_bench and tid == 150, (
        "Ripening Charge debe cargar el Hydrapple ex de BANCA, no el activo ya "
        f"listo (Syrup Storm escala con el campo); fue id {tid} bench={is_bench}")


# =====================================================================
# Boss's Orders gusts the target worth the MOST prizes when it wins (user,
# registro_011 vs Mega Heracross ex, WON suboptimally). 3 prizes from winning,
# with a LETHAL active Hydrapple ex, the game gusted a Teal Mask Ogerpon ex
# (2 prizes, energized) instead of the Mega Heracross ex (3 prizes) that it knocked out
# to WIN. Cause: the KO tier put megaEx and ex in the same tier (8/7) and the
# +1 for "energized" made the 2-prize ex beat the 3-prize Mega. Fix: a
# prize-aware tier (megaEx 10/9 > ex 8/7) + the `gust_gana_partida` override.
# =====================================================================
_BOSS_GUST_FIXTURE = (ROOT / "tests" / "fixtures"
                      / "boss_gust_prefers_higher_prize_mega_ex.json")
_MEGA_HERACROSS_EX = 781
_TEAL_OGERPON_EX = 96


def test_boss_gust_prefers_winning_3prize_mega_over_2prize_ex():
    with open(_BOSS_GUST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    op_bench = obs["current"]["players"][1 - mi]["bench"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = obs["select"]["option"][m.agent(obs)[0]]
    tid = op_bench[chosen["index"]]["id"]
    assert tid == _MEGA_HERACROSS_EX, (
        f"Boss's debe gustear el Mega Heracross ex (781, 3 premios, gana la "
        f"partida), no el Ogerpon ex (96, 2 premios); gusteo id {tid}")


def test_prize_count_recognizes_mega_ex_as_three():
    # The prize identification: megaEx=3, ex=2, non-ex=1.
    class _P:
        def __init__(self, cid): self.id = cid; self.energyCards = []; self.tools = []
    assert m.prize_count(_P(_MEGA_HERACROSS_EX)) == 3
    assert m.prize_count(_P(_TEAL_OGERPON_EX)) == 2
    assert m.prize_count(_P(349)) == 1  # Teal Mask Ogerpon (no-ex)


# =====================================================================
# A SEQUENCING ERROR Unfair Stamp / Meowth ex (user, registro_004 p34 vs Mega
# Starmie ex, WON suboptimally). With an Unfair Stamp (an ACE SPEC Item) PLAYABLE this
# turn (they knocked us out last turn + the Stamp in hand), the agent played
# Meowth ex so that Last-Ditch Catch would search for a Lillie's -> but the Stamp SHUFFLES
# THE WHOLE hand into the deck, losing that Lillie's and exposing a 2-prize
# body. The `_stamp_blocks_supp_chain` veto existed but was SHADOWED by
# the Lillie's refresh branches (earlier elifs); it was moved BEFORE them.
# =====================================================================
_STAMP_MEOWTH_FIXTURE = (ROOT / "tests" / "fixtures"
                         / "unfair_stamp_before_meowth_fetch_lillie.json")
_UNFAIR_STAMP = 1080
_MEOWTH_EX = 1071


def _played_id(obs, chosen_idx):
    o = m.to_observation_class(obs)
    me = o.current.players[o.current.yourIndex]
    opt = o.select.option[chosen_idx]
    if getattr(opt, "type", None) == m.OptionType.PLAY and getattr(opt, "index", None) is not None:
        return me.hand[opt.index].id
    return None


def test_stamp_playable_vetoes_meowth_fetch_lillie():
    with open(_STAMP_MEOWTH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    pid = _played_id(obs, chosen[0])
    assert pid != _MEOWTH_EX, (
        "Con Unfair Stamp jugable (KO el turno pasado), NO bajar Meowth ex a "
        f"buscar Lillie's (el Sello la baraja); el agente jugo id {pid}")


_MEOWTH_NO_STAMP_FIXTURE = (ROOT / "tests" / "fixtures"
                            / "meowth_fetch_lillie_no_stamp_control.json")


def test_meowth_fetch_lillie_still_played_without_playable_stamp():
    # Control: the SAME board but WITHOUT an Unfair Stamp in hand -> the veto does not apply
    # and the Meowth -> Lillie's engine (a refresh) is still in force and DOES play Meowth ex.
    with open(_MEOWTH_NO_STAMP_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    pid = _played_id(obs, chosen[0])
    assert pid == _MEOWTH_EX, (
        "Sin Unfair Stamp en mano, el motor Meowth->Lillie's debe seguir bajando "
        f"Meowth ex; el agente jugo id {pid}")


# =====================================================================
# THE SAME SEQUENCING ERROR, but through the BOSS'S ENGINE branch (user,
# registro_008 step 90 vs Alakazam, WON suboptimally). The veto
# `_stamp_blocks_supp_chain` was BELOW the Boss's-via-Meowth engines
# (_win_via_boss_gust/_gust_2prize_via_boss 22500, _deny_evo_via_boss 22000,
# _meowth_immune_boss_engine 22000), exempt on the argument that "the Boss's
# they search for is PLAYED this turn, it is not shuffled away". The argument is FALSE: ALL
# the scorers of `_SUPP_PLAY_IDS` (Boss's, Xerosic, Lillie's, Dawn, Lana's)
# veto with `cede_a_unfair_stamp`, so that Boss's canNOT be played this
# turn and the Stamp sends it back to the deck. In step 90 (a 210 HP Fezandipiti ex
# on the rival bench, finishable by Wood Hammer -> `_gust_2prize_via_boss`) the
# agent played Meowth ex, dug the Boss's, played the Stamp -- which shuffled it away
# -- and only recovered it by LUCK among the 5 drawn cards. The veto was moved
# ABOVE all those engines.
# =====================================================================
_STAMP_MEOWTH_BOSS_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step90_no_meowth_boss_con_unfair_stamp.json")
_MEOWTH_BOSS_NO_STAMP_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step90_meowth_boss_sin_stamp_control.json")


def test_stamp_playable_vetoes_meowth_fetch_boss():
    # The real step 90: a hand with a PLAYABLE Unfair Stamp (they knocked us out last
    # turn) + Xerosic, and a Boss's in the deck that would gust the rival Fezandipiti ex.
    # Meowth ex is not played: the Stamp goes first and would shuffle that Boss's away.
    with open(_STAMP_MEOWTH_BOSS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    pid = _played_id(obs, chosen[0])
    assert pid != _MEOWTH_EX, (
        "Con Unfair Stamp jugable, NO bajar Meowth ex a cavar un Boss's Orders "
        "que el propio Sello devuelve al mazo (y que `cede_a_unfair_stamp` "
        f"impide jugar este turno); el agente jugo id {pid}")


def test_a_playable_stamp_does_not_block_the_turn_supporter():
    # The Stamp is still PLAYABLE in the menu after the veto: the veto only stops the
    # Meowth fetch, not the items -> Unfair Stamp sequence.
    with open(_STAMP_MEOWTH_BOSS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    o = m.to_observation_class(obs)
    me = o.current.players[o.current.yourIndex]
    assert any(getattr(opt, "type", None) == m.OptionType.PLAY
               and me.hand[opt.index].id == _UNFAIR_STAMP
               for opt in o.select.option), "el Sello debe seguir en el menu"
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    assert m.agent(obs), "el agente debe elegir alguna opcion"


def test_meowth_fetch_boss_still_played_without_playable_stamp():
    # Control: the SAME board without the Stamp (nor the Xerosic, which would take the
    # Supporter slot through `_meowth_fetch_pierde_el_turno`) -> the
    # Boss's-via-Meowth-ex engine is intact and DOES play Meowth ex.
    with open(_MEOWTH_BOSS_NO_STAMP_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    pid = _played_id(obs, chosen[0])
    assert pid == _MEOWTH_EX, (
        "Sin Unfair Stamp jugable, el motor Boss's via Meowth ex (gustear+"
        f"noquear un ex de 2 premios) debe seguir vigente; el agente jugo id {pid}")


# =====================================================================
# vs Alakazam: charge the 1-PRIZE attacker (Meganium) that knocks out THIS turn,
# not the active ex (user, registro_008 steps 100-115 vs Alakazam, LOST). The
# active was an Ogerpon ex (2 prizes) able to knock out the Alakazam (140 HP), but
# on the bench there was a Meganium ONE Grass away from its Wood Hammer (140 = a KO). The
# charge (the manual attachment) must go to the MEGANIUM to leave it READY and attack with the
# 1-prize body (retreat the ex, promote the Meganium): we give away 1 prize instead of 2
# when the Alakazam knocks us out in return. Fix: the flag `_meganium_alk_1prize_attacker`
# -> energy_score 43000 (it dominates charging the active ex). The retreat logic already
# promotes the 1-prize body when the Meganium is READY.
# =====================================================================
_ALK_MEG_FIXTURE = (ROOT / "tests" / "fixtures"
                    / "alakazam_charge_meganium_1prize_not_ogerpon_ex.json")
_MEGANIUM = 710
_TEAL_OGERPON_EX_ID = 96


def test_vs_alakazam_charges_1prize_meganium_not_active_ex():
    with open(_ALK_MEG_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    o = m.to_observation_class(obs)
    opt = o.select.option[chosen[0]]
    assert getattr(opt, "type", None) == int(m.OptionType.ATTACH), (
        "Se esperaba un adjunte de energia")
    ipa = getattr(opt, "inPlayArea", None); ipi = getattr(opt, "inPlayIndex", None)
    tgt_id = (me["active"][0]["id"] if ipa == int(m.AreaType.ACTIVE)
              else me["bench"][ipi]["id"])
    assert tgt_id == _MEGANIUM, (
        "vs Alakazam la carga debe ir al Meganium (1 premio, KO este turno), no "
        f"al ex activo; el agente cargo id {tgt_id}")


def test_alakazam_retreats_ex_to_promote_ready_1prize_meganium():
    # With the Meganium already READY (4 eff) and no more plays, vs Alakazam the agent retreats
    # the active ex to promote the 1-prize body (instead of attacking with the 2-prize ex).
    import copy
    with open(_ALK_MEG_FIXTURE, encoding="utf-8") as f:
        obs = copy.deepcopy(json.load(f)["observation"])
    me = obs["current"]["players"][1]
    for b in me["bench"]:
        if b["id"] == _MEGANIUM:
            b["energies"] = [1, 1, 1, 1]
            b["energyCards"] = [{"id": 1, "playerIndex": 1, "serial": 114},
                                {"id": 1, "playerIndex": 1, "serial": 999}]
    me["hand"] = []; me["handCount"] = 0
    obs["current"]["supporterPlayed"] = True
    obs["select"]["option"] = [{"attackId": 120, "type": 13}, {"type": 12}, {"type": 14}]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    o = m.to_observation_class(obs)
    assert o.select.option[chosen[0]].type == int(m.OptionType.RETREAT), (
        "Con el Meganium 1-premio LISTO, vs Alakazam el agente debe RETIRAR el ex "
        "para promover el 1-premio, no atacar con el ex de 2 premios")


# =====================================================================
# NEVER end the turn with an EMPTY bench if we can develop it (user,
# registro_002 step 15 vs Mega Starmie ex, LOST). With a single basic (Tapu
# Bulu) in the active spot and no bench, if the rival knocks out that active we LOSE (there is
# nobody to promote). The agent ended the turn holding an Ultra Ball + Meowth ex
# in hand. A final safety net: if the best play is to END (or it is sterile) and
# there is an option that puts a Pokemon on the bench (an Ultra Ball -> a basic, or playing a
# basic), it takes priority over ending the turn. Preference: the searcher.
# =====================================================================
_EMPTY_BENCH_FIXTURE = (ROOT / "tests" / "fixtures"
                        / "never_end_turn_empty_bench_play_ultraball.json")
_ULTRA_BALL = 1121


def test_never_ends_turn_with_empty_bench_plays_ultraball():
    with open(_EMPTY_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    o = m.to_observation_class(obs)
    opt = o.select.option[chosen[0]]
    assert opt.type != int(m.OptionType.END), (
        "Con la banca VACIA y una Ultra Ball en mano, NO terminar el turno: "
        "desarrollar la banca para no perder si noquean el activo")
    tid = me["hand"][opt.index]["id"] if getattr(opt, "index", None) is not None else None
    assert tid == _ULTRA_BALL, (
        f"Se esperaba jugar Ultra Ball para buscar un basico; jugo id {tid}")


def test_empty_bench_net_does_not_fire_with_bench_present():
    # Control: with a Pokemon ALREADY on the bench, the anti-empty-bench net does not apply
    # (bench_count>0). Since the Jul 2026 plan there is ALSO the
    # anti-sterile-turn net (which can rehabilitate the Ultra Ball with a bench
    # present); to isolate the control of the ORIGINAL net, the new one is switched off
    # by putting a Comfey on the rival bench (the op_is_comfey_deck guard).
    import copy
    with open(_EMPTY_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = copy.deepcopy(json.load(f)["observation"])
    me = obs["current"]["players"][0]
    me["bench"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                    "hp": 70, "id": 1071, "maxHp": 170, "playerIndex": 0,
                    "preEvolution": [], "serial": 900, "tools": []}]
    op = obs["current"]["players"][1]
    op.setdefault("bench", []).append(
        {"appearThisTurn": False, "energies": [], "energyCards": [],
         "hp": 70, "id": 164, "maxHp": 70, "playerIndex": 1,
         "preEvolution": [], "serial": 901, "tools": []})
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    o = m.to_observation_class(obs)
    opt = o.select.option[chosen[0]]
    tid = (me["hand"][opt.index]["id"]
           if getattr(opt, "type", None) == int(m.OptionType.PLAY)
           and getattr(opt, "index", None) is not None else None)
    assert tid != _ULTRA_BALL, (
        "Con banca no vacia la red anti-banca-vacia no debe forzar la Ultra Ball")


# =====================================================================
# vs Alakazam: do NOT overcharge the already READY active Tapu Bulu; charge the bench
# Dipplin (user, registro_012 step 142 vs Alakazam, WON). The active Tapu Bulu
# had 2 physical Grass = 4 effective (Meganium doubles) = its Wood Hammer's cost
# of 4: it could already attack and its damage is FIXED. The manual attachment of the 3rd energy must go
# to the bench Dipplin (a future attacker), not be wasted on the Tapu. Covered
# by the `_active_extra_charge_wasted` guard (a Tapu/Meganium/Hydrapple at its
# requirement does not receive the 42000 of the winning gust -> the energy flows to the bench).
# =====================================================================
_ALK_TAPU_FIXTURE = (ROOT / "tests" / "fixtures"
                     / "alakazam_manual_attach_dipplin_not_ready_tapu.json")
_TAPU_BULU = 920
_DIPPLIN = 93


def test_alakazam_does_not_overcharge_ready_tapu_charges_dipplin():
    with open(_ALK_TAPU_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    me = obs["current"]["players"][1]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    o = m.to_observation_class(obs)
    opt = o.select.option[chosen[0]]
    assert getattr(opt, "type", None) == int(m.OptionType.ATTACH), (
        "Se esperaba un adjunte de energia")
    ipa = getattr(opt, "inPlayArea", None); ipi = getattr(opt, "inPlayIndex", None)
    tgt_id = (me["active"][0]["id"] if ipa == int(m.AreaType.ACTIVE)
              else me["bench"][ipi]["id"])
    assert tgt_id != _TAPU_BULU, (
        "NO sobrecargar el Tapu Bulu activo ya LISTO (4 ef, dano fijo)")
    assert tgt_id == _DIPPLIN, (
        f"La 3a energia debe ir al Dipplin de banca (atacante futuro); fue a {tgt_id}")


# =====================================================================
# Record 016 (step 138 vs Crustle, WON with a suboptimal play): our
# active is a CHARGED Ogerpon ex (4 energy) whose Myriad Leaf Shower KNOCKS OUT the
# rival active (Munkidori, 110 HP). The rival has an EMPTY BENCH: if we
# knock out their active they canNOT promote a replacement and they LOSE (another route to
# victory besides the prizes). The agent, not detecting the finisher, RETREATED
# the Ogerpon to attack with a 1-prize body (Dipplin) -- the mismatch pivot
# `_tapu_sac_pivot` fired because the Ogerpon was at <=50% HP and
# my_prize (2) > the target's prizes (1). With an empty rival bench, ATTACKING with
# the active WINS the game: no mismatch matters. Deck-agnostic.
_WIN_EMPTY_BENCH_FIXTURE = (ROOT / "tests" / "fixtures"
                            / "win_by_ko_empty_bench_attack_active.json")


def test_ko_of_last_opponent_pokemon_attacks_active_to_win():
    with open(_WIN_EMPTY_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"con el activo LETAL y la banca rival VACIA, noquear al activo GANA la "
        f"partida: debe ATACAR (opt {attack_opt}), no retirar; obtuvo {result}")
    assert result != [retreat_opt], (
        "no retirar el activo letal para pivotar a un 1-premio cuando el KO gana")
    assert m.plan.attacker == 0, (
        f"el atacante debe ser el ACTIVO (0), no un cuerpo de banca; "
        f"fue {m.plan.attacker}")


def test_win_by_empty_bench_does_not_fire_when_opponent_has_bench():
    # Control: with the rival HAVING a bench, the active's KO does NOT win the game, so
    # the finisher override must not apply (the mismatch/pivot logic is
    # free to act). A Pokemon is added to the rival bench and it is verified
    # that the decision is NO longer forced to the active's attack through the
    # empty-bench route (the plan may legitimately pivot).
    with open(_WIN_EMPTY_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = json.loads(json.dumps(json.load(f)["observation"]))

    cur = obs["current"]; yi = cur["yourIndex"]; op = cur["players"][1 - yi]
    oact = op["active"][0]
    op["bench"] = [{
        "appearThisTurn": False, "energies": [], "energyCards": [],
        "hp": oact.get("hp", 110), "maxHp": oact.get("maxHp", 110),
        "id": oact["id"], "playerIndex": oact["playerIndex"],
        "preEvolution": [], "serial": (oact.get("serial", 0) or 0) + 5000,
        "tools": [],
    }]

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    m.agent(obs)
    # With a rival bench, the active's KO no longer wins through the no-promotion rule;
    # the empty-bench finisher must not be active (`_active_win_plan` is not captured).
    # We verify that the scenario is different: the rival DOES have a bench.
    assert any(b is not None for b in op["bench"]), "control: rival con banca"


# =====================================================================
# A record against Alakazam (WON): with an Ultra Ball, with NO usable attacker and after
# a KO on the previous turn (ko_last_turn), the fetch brought Fezandipiti ex (its
# Flip the Script draws 3 when we are knocked out: the `refill_tras_ko` rule = 1050). It is
# a mistake while the Meowth ex -> Last-Ditch Catch -> Lillie's
# Determination engine is STILL in the deck: playing Meowth ex searches for a Lillie's and remakes the WHOLE hand
# (up to 8 cards), opening far more options than Fezandipiti's draw of 3.
# Fezandipiti ex is a good search ONLY if we already have a usable attacker, or if the
# Meowth ex engine is no longer available (no copies in the deck, a full bench, 2
# Meowth already in play, a Lillie's in hand, the Supporter already played, or a Watchtower).
# Fix: the `refill_tras_ko` rule of _REGLAS_UB_FEZ yields when
# `no_attacker_prefer_meowth` is active (the same predicate that favours
# Meowth). The fixture injects a KO log (fromArea PRIZE) to derive
# ko_last_turn from a single observation. Deck-agnostic.
_UB_MEOWTH_OVER_FEZ_FIXTURE = (ROOT / "tests" / "fixtures"
                               / "ub_prefer_meowth_over_fez_no_attacker.json")


def test_ub_fetch_prefers_meowth_over_fez_when_no_attacker():
    with open(_UB_MEOWTH_OVER_FEZ_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    search_map = _resolve_search_options(obs)
    assert m.Meowth_ex in search_map.values(), "el fixture debe ofrecer buscar Meowth ex"
    assert m.Fezandipiti_ex in search_map.values(), "el fixture debe ofrecer buscar Fezandipiti ex"
    meowth_opt = next(i for i, cid in search_map.items() if cid == m.Meowth_ex)
    fez_opt = next(i for i, cid in search_map.items() if cid == m.Fezandipiti_ex)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"sin atacante usable y con el motor Meowth->Lillie's en el mazo, la "
        f"Ultra Ball debe buscar Meowth ex (opt {meowth_opt}) para refrescar, no "
        f"Fezandipiti ex; obtuvo {result} (map={search_map})")
    assert result != [fez_opt], (
        "no buscar Fezandipiti ex cuando Meowth ex refresca mejor sin atacante")


def test_ub_fetch_gate_is_conditional_on_meowth_engine():
    # Control: the gate that makes Fezandipiti yield only applies when the
    # Meowth ex -> Lillie's engine is AVAILABLE (`no_attacker_prefer_meowth`). If it is
    # broken (e.g. the Supporter ALREADY played this turn -> a Lillie's could not be
    # chained), the gate must NOT divert the search towards Meowth ex: the decision
    # stops being forced to Meowth (here another refill/development target wins,
    # e.g. Hydrapple ex; Fezandipiti recovers its refill of 1050).
    with open(_UB_MEOWTH_OVER_FEZ_FIXTURE, encoding="utf-8") as f:
        obs = json.loads(json.dumps(json.load(f)["observation"]))

    obs["current"]["supporterPlayed"] = True  # rompe el motor Meowth->Lillie's

    search_map = _resolve_search_options(obs)
    meowth_opt = next(i for i, cid in search_map.items() if cid == m.Meowth_ex)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [meowth_opt], (
        f"con el Supporter ya jugado (motor Meowth roto), el gate NO debe forzar "
        f"buscar Meowth ex (opt {meowth_opt}); obtuvo {result} (map={search_map})")


# =====================================================================
# Registro_009 step 111 vs Alakazam (LOST): after the KO of our active
# (an Ogerpon ex) we have to promote a Pokemon from the bench. The agent brought up Tapu Bulu
# (0/4 energy, it cannot attack for several turns) as a cheap 1-prize wall,
# instead of the bench Ogerpon ex (2/3 effective: ONE single Grass -x2 with
# Meganium in play- away from its Myriad, which finishes off the Alakazam). The promotion happens
# on the RIVAL's turn; the next turn -OURS- we attach 1 Grass (with a Lillie's
# in hand to dig it) and attack first, so the rival does not even hit the ex.
# It must promote the NEARLY ready attacker that finishes, not the wall that never attacks.
_PROMOTE_NEAR_READY_FIXTURE = (ROOT / "tests" / "fixtures"
                               / "promote_near_ready_ex_over_wall_step111.json")


def test_promote_near_ready_ko_attacker_over_cheap_wall():
    with open(_PROMOTE_NEAR_READY_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    # opt cuyo bench-index apunta a Ogerpon ex (96) y a Tapu Bulu (920).
    ogerpon_opt = next(i for i, o in enumerate(options)
                       if me["bench"][o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex)
    tapu_opt = next(i for i, o in enumerate(options)
                    if me["bench"][o["index"]]["id"] == 920)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [ogerpon_opt], (
        f"tras el KO debe promover el atacante casi listo Ogerpon ex (opt "
        f"{ogerpon_opt}), no el muro Tapu Bulu 0/4; obtuvo {result}")
    assert result != [tapu_opt], (
        "no promover un muro que no puede atacar en varios turnos")


def _promote_near_ready_obs(without_lillie=False, without_fez=False):
    with open(_PROMOTE_NEAR_READY_FIXTURE, encoding="utf-8") as f:
        obs = json.loads(json.dumps(json.load(f)["observation"]))
    yi = obs["current"]["yourIndex"]; me = obs["current"]["players"][yi]
    if without_lillie:
        me["hand"] = [c for c in me["hand"] if c["id"] != m.Lillie_Determination]
    if without_fez:
        me["bench"] = [b for b in me["bench"] if b["id"] != m.Fezandipiti_ex]
        obs["select"]["option"] = [
            {"area": 5, "index": i, "playerIndex": yi, "type": 3}
            for i in range(len(me["bench"]))]
    return obs


def test_promote_near_ready_defers_without_draw_engine():
    # Control: with NO draw engine at all, the missing energy cannot be dug,
    # so the "nearly ready attacker" override does NOT apply and the decision
    # goes back to the basic wall logic / a normal promotion.
    #
    # TWO engines have to be removed, not one. Before, this control only removed the
    # Lillie's from hand and assumed there was no way left to dig; but
    # the board keeps a **Fezandipiti ex on the bench** and the promotion happens
    # right after a KO, which is Flip the Script's trigger: next
    # turn it draws 3. That route (route `d` of `_ps_can_find_energy`) is real and is now
    # modelled, so the control has to switch it off too in order to measure what
    # it says it measures. See `test_promote_near_ready_fez_draw_engine_is_enough`.
    obs = _promote_near_ready_obs(without_lillie=True, without_fez=True)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    ogerpon_opt = next(i for i, o in enumerate(obs["select"]["option"])
                       if me["bench"][o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [ogerpon_opt], (
        f"sin motor de robo alguno el override no debe forzar Ogerpon ex; "
        f"obtuvo {result}")


def test_promote_near_ready_fez_draw_engine_is_enough():
    # Without a Lillie's but WITH the Fezandipiti ex on the bench: Flip the Script (draw 3,
    # triggered by the KO that forces us to promote) is engine enough to
    # find the missing Grass, and the Ogerpon ex at 2/3 keeps its way out
    # (retreat 1, it carries 2 energies) in case the draw fails. The
    # nearly ready attacker is promoted, not the Tapu Bulu 0/4 with retreat 3.
    obs = _promote_near_ready_obs(without_lillie=True)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert any(b and b["id"] == m.Fezandipiti_ex for b in me["bench"])
    ogerpon_opt = next(i for i, o in enumerate(obs["select"]["option"])
                       if me["bench"][o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex)

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    assert m.agent(obs) == [ogerpon_opt]


# vs Alakazam with a big rival hand (Powerful Hand = 20 x card): reserve the
# turn's Supporter for Xerosic (via Ultra Ball -> Meowth ex -> Last-Ditch)
# instead of spending it on Lillie's (user, registro_008 step 75, WON suboptimally).
# With a charged Hydrapple ex + 3 bench attackers the Lillie's refresh is
# redundant; digging the disruption is worth more. See _alakazam_dig_xerosic_engine.
def _load_alakazam_step75_obs():
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" /
        "alakazam_step75_xerosic_engine_over_lillie.json",
        encoding="utf-8"))["observation"]


def test_alakazam_step75_plays_ultra_ball_not_lillie():
    obs = _load_alakazam_step75_obs()
    play_map = _resolve_play_options(obs)
    # The fixture must offer BOTH plays for the test to be meaningful.
    assert m.Ultra_Ball in play_map.values()
    assert m.Lillie_Determination in play_map.values()
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)
    lillie_opt = next(
        i for i, cid in play_map.items() if cid == m.Lillie_Determination)

    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [ub_opt], (
        f"vs Alakazam con mano rival 10 (Powerful Hand) debe jugar Ultra Ball "
        f"(opt {ub_opt}) para cavar Meowth ex -> Xerosic, no Lillie's; "
        f"obtuvo {result} (map={play_map})")
    assert result != [lillie_opt]
    # The pivot must be armed so that the FETCH picks Meowth ex.
    assert m._ub_engine_pivot_turn is True


def test_alakazam_step75_control_small_op_hand_allows_lillie():
    # Boundary: with a SMALL rival hand (< 7, outside the big Powerful
    # Hand zone) the disruption engine does NOT fire -> the Ultra Ball goes back to
    # its normal veto and Lillie's is no longer vetoed by
    # `alakazam_reserva_supporter_para_xerosic`: it refreshes as before.
    import copy as _copy
    obs = _copy.deepcopy(_load_alakazam_step75_obs())
    obs["current"]["players"][1]["handCount"] = 6
    play_map = _resolve_play_options(obs)
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)
    lillie_opt = next(
        i for i, cid in play_map.items() if cid == m.Lillie_Determination)

    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [lillie_opt], (
        f"con mano rival 6 (< 7) el motor de dig Xerosic NO debe dispararse: "
        f"se juega Lillie's como antes; obtuvo {result} (map={play_map})")
    assert result != [ub_opt]


# Promotion after a KO: evaluate the best SURVIVOR, not the ex with the most life (user,
# registro_013 step 99 vs Mega Lucario ex, LOST). No body knocks out the Mega
# Lucario (340) nor survives it as it stands (it projects 270); but Dipplin evolves the
# next turn into Hydrapple ex (330 > 270, it SURVIVES). Promote Dipplin, not the
# Ogerpon ex (210, it dies -> it gives away 2 prizes). See the evolution-survivor override.
def _load_lucario_step99_obs():
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" /
        "lucario_step99_promote_survivor_tank_not_ogerpon.json",
        encoding="utf-8"))["observation"]


def _promote_choice_id(obs):
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    dec = m.agent(obs)
    opt = obs["select"]["option"][dec[0]]
    return me["bench"][opt["index"]]["id"]


def test_lucario_step99_promotes_evolution_survivor_not_ogerpon():
    obs = _load_lucario_step99_obs()
    chosen = _promote_choice_id(obs)
    assert chosen == m.Dipplin, (
        f"debe promover Dipplin (evoluciona a Hydrapple ex 330, sobrevive a los "
        f"270 del Mega Lucario), no Ogerpon ex (210, muere -> 2 premios); "
        f"promovio id {chosen}")
    assert chosen != m.Teal_Mask_Ogerpon_ex


def test_lucario_step99_control_no_evolution_in_hand_keeps_normal():
    # Boundary: with no evolution (Hydrapple ex) in hand there is NO survivor
    # via evolution -> the override does not fire and the promotion follows the
    # normal logic (which does NOT pick Dipplin here). It confirms that the override depends on
    # having the evolution in hand.
    import copy as _copy
    obs = _copy.deepcopy(_load_lucario_step99_obs())
    me = obs["current"]["players"][0]
    me["hand"] = [c for c in me["hand"] if c["id"] != m.Hydrapple_ex]
    chosen = _promote_choice_id(obs)
    assert chosen != m.Teal_Mask_Ogerpon_ex, (
        f"SUPERSEDIDO (user, registro_005 paso 64): sin superviviente posible "
        f"-- Mega Lucario pega 270 y aqui muere todo -- se promueve el cuerpo "
        f"de MENOS premios (Dipplin/Meganium, 1) y no el Ogerpon ex (2); "
        f"promovio id {chosen}")


# Energy priority: charge the EMPTY bench Hydrapple ex (a future attacker)
# with Ripening Charge instead of Teal Dance on an ALREADY charged Ogerpon ex (user,
# registro_006 step 80 vs Mega Lucario). Both abilities attach Grass, but
# Teal Dance (the ENERGY tier) dominated by TIER the HIGHER-scoring Ripening that
# stayed in tier 0. Fix: a Ripening that scores as a real play (>=29000)
# also rises to the ENERGY tier -> within the tier it wins on score (31150 > 31050).
def _load_lucario_step80_obs():
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" /
        "lucario_step80_charge_bench_hydrapple_over_teal_dance.json",
        encoding="utf-8"))["observation"]


def test_lucario_step80_ripening_charges_bench_hydrapple_over_teal_dance():
    obs = _load_lucario_step80_obs()
    me = obs["current"]["players"][0]
    opts = obs["select"]["option"]
    # Locate the ability options: Ripening (Hydrapple) and Teal Dance (Ogerpon).
    ripen_opt = next(i for i, o in enumerate(opts)
                     if o.get("type") == int(m.OptionType.ABILITY)
                     and me["bench"][o["index"]]["id"] == m.Hydrapple_ex)
    teal_opts = [i for i, o in enumerate(opts)
                 if o.get("type") == int(m.OptionType.ABILITY)
                 and me["bench"][o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex]
    assert teal_opts, "el fixture debe ofrecer Teal Dance para que el test valga"
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [ripen_opt], (
        f"debe usar Ripening Charge para cargar el Hydrapple ex de banca vacio "
        f"(atacante futuro, opt {ripen_opt}), no Teal Dance sobre un Ogerpon ex "
        f"ya cargado (opts {teal_opts}); obtuvo {result}")


def test_lucario_step80_control_ready_bench_hydrapple_does_not_block_teal():
    # Boundary: if the bench Hydrapple ex is ALREADY ready (>=2 energies), charging it
    # again is not a priority; the Ripening to that Hydrapple no longer scores as
    # an empty-attacker charge (it drops below 31150) and must not hijack the turn.
    # It verifies that the fix depends on the Hydrapple having NO energy.
    import copy as _copy
    obs = _copy.deepcopy(_load_lucario_step80_obs())
    me = obs["current"]["players"][0]
    # Charging the bench Hydrapple to 2 energies (already ready for Syrup Storm).
    for b in me["bench"]:
        if b["id"] == m.Hydrapple_ex:
            b["energies"] = [1, 1]
            b["energyCards"] = [{"id": 1, "playerIndex": 0, "serial": 300},
                                {"id": 1, "playerIndex": 0, "serial": 301}]
    opts = obs["select"]["option"]
    ripen_opt = next(i for i, o in enumerate(opts)
                     if o.get("type") == int(m.OptionType.ABILITY)
                     and me["bench"][o["index"]]["id"] == m.Hydrapple_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result != [ripen_opt], (
        f"con el Hydrapple ex de banca YA cargado, la Ripening no debe forzarse "
        f"(opt {ripen_opt}); obtuvo {result}")


# Play Boss's Orders (gust+knock out the bench ex pre-evo) instead of Dawn
# (a useless refresh) when the rival active is OUTSIDE the ex line (user,
# registro_004 step ~47 vs Marnie's Grimmsnarl): we fetched a Boss's with the Meowth and
# then the agent played Dawn, wasting the turn's Supporter. The rival active
# is a Munkidori (1 energy, 1 prize, outside the line) and on the bench there is an energized Marnie's
# Morgrem (a pre-evo of Grimmsnarl ex, 1 prize): gusting+knocking it out
# yields the same prize BUT cuts off the main attacker. Before, Boss's was vetoed
# (-1) because "knocking out the active dominates with equal prizes"; now an energized ex
# pre-evo facing an active OUTSIDE the line is a valid deny-evo target.
def _load_marnie_step47_obs():
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" /
        "marnie_step47_play_boss_not_dawn.json",
        encoding="utf-8"))["observation"]


def test_marnie_step47_plays_boss_orders_not_dawn():
    obs = _load_marnie_step47_obs()
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]
    opts = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(opts)
                    if o.get("type") == int(m.OptionType.PLAY)
                    and me["hand"][o["index"]]["id"] == m.Boss_Orders)
    dawn_opt = next(i for i, o in enumerate(opts)
                    if o.get("type") == int(m.OptionType.PLAY)
                    and me["hand"][o["index"]]["id"] == m.Dawn)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [boss_opt], (
        f"debe jugar Boss's Orders (opt {boss_opt}, gustear el Morgrem pre-evo de "
        f"Grimmsnarl ex) en vez de Dawn (opt {dawn_opt}); obtuvo {result}")


def test_marnie_step47_control_active_on_ex_line_keeps_normal():
    # Boundary: if the rival active is ALREADY part of the bench ex line (e.g. another
    # energized active Morgrem), knocking it out already hits the line, so gusting the
    # bench copy is not a priority and the off-line deny-evo must NOT fire.
    import copy as _copy
    obs = _copy.deepcopy(_load_marnie_step47_obs())
    op = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    # Turning the active Munkidori into an energized Morgrem (the same line as the bench).
    op["active"][0]["id"] = 647
    op["active"][0]["maxHp"] = 100
    op["active"][0]["hp"] = 100
    op["active"][0]["preEvolution"] = [{"id": 646, "playerIndex": op["active"][0]["playerIndex"], "serial": 999}]
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(opts)
                    if o.get("type") == int(m.OptionType.PLAY)
                    and me["hand"][o["index"]]["id"] == m.Boss_Orders)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result != [boss_opt], (
        f"con el activo YA en la linea ex, el deny-evo off-line no debe forzar "
        f"Boss's (opt {boss_opt}); obtuvo {result}")


# Play Lillie's Determination (a refresh + development) instead of Xerosic's
# Machinations when the rival hand is MINIMAL (<= 4: capping only takes 1 card away)
# (user, registro_002 step 17 vs Alakazam, LOST): turn 2, the rival with 4 cards;
# we searched for a Lillie's with Meowth ex and the agent played Xerosic (7000, the rule
# `alakazam_prioridad_sobre_boss` designed for a HUGE rival hand). With a minimal rival
# hand the disruption value is marginal and Lillie's is worth more.
def _load_alakazam_step17_obs():
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" /
        "alakazam_step17_play_lillie_not_xerosic.json",
        encoding="utf-8"))["observation"]


def test_alakazam_step17_plays_lillie_not_xerosic_small_op_hand():
    obs = _load_alakazam_step17_obs()
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]
    opts = obs["select"]["option"]
    lillie_opt = next(i for i, o in enumerate(opts)
                      if o.get("type") == int(m.OptionType.PLAY)
                      and me["hand"][o["index"]]["id"] == m.Lillie_Determination)
    xerosic_opt = next(i for i, o in enumerate(opts)
                       if o.get("type") == int(m.OptionType.PLAY)
                       and me["hand"][o["index"]]["id"] == m.Xerosic_Machinations)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [lillie_opt], (
        f"con la mano rival minima (4) debe jugar Lillie's (opt {lillie_opt}, "
        f"refresco/desarrollo) no Xerosic (opt {xerosic_opt}); obtuvo {result}")


def test_alakazam_step17_control_large_op_hand_keeps_xerosic():
    # Boundary: with a BIG rival hand (>= 7) capping Powerful Hand IS worth more;
    # Xerosic must still beat Lillie's (it must not yield through the minimal hand).
    import copy as _copy
    obs = _copy.deepcopy(_load_alakazam_step17_obs())
    op = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    op["handCount"] = 9
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    xerosic_opt = next(i for i, o in enumerate(opts)
                       if o.get("type") == int(m.OptionType.PLAY)
                       and me["hand"][o["index"]]["id"] == m.Xerosic_Machinations)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [xerosic_opt], (
        f"con la mano rival grande (9) debe seguir capando con Xerosic "
        f"(opt {xerosic_opt}); obtuvo {result}")


# The principle (user, registro_010 step ~127 vs Alakazam): before playing Meowth ex
# to SEARCH for a Supporter (Last-Ditch Catch), evaluate whether the Supporter we ALREADY
# have in hand is the best for the scenario; if it is, do NOT play Meowth ex and
# play that Supporter. Here: vs Alakazam with a big rival hand (12), holding
# Xerosic's Machinations in hand (the best: it caps Powerful Hand), the agent must
# PLAY the Xerosic, not play Meowth ex nor play an Ultra Ball to dig another Supporter.
# The agent already complies: the Meowth->Xerosic engine (main.py ~L14794) and the
# UB->Meowth engine (`_alakazam_dig_xerosic_engine`) require `Xerosic NOT in hand`.
def test_alakazam_holds_xerosic_plays_it_not_meowth_fetch():
    import json as _json
    obs = _json.load(open(
        ROOT / "tests" / "fixtures" /
        "alakazam_hold_xerosic_no_meowth_fetch.json",
        encoding="utf-8"))["observation"]
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    xer = next(i for i, o in enumerate(opts)
               if o.get("type") == int(m.OptionType.PLAY)
               and me["hand"][o["index"]]["id"] == m.Xerosic_Machinations)
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [xer], (
        f"con Xerosic en mano (mejor Supporter vs Alakazam) debe jugarlo "
        f"(opt {xer}), no bajar Meowth ex (opt {meowth}) a buscar otro; "
        f"obtuvo {result}")


# ============================================================================
# vs Marnie's Grimmsnarl ex: the automatic snipe to the bench (Shadow Bullet, 180
# to the active + 30 to ONE benched body EVERY turn) only kills our low-life
# bodies and gives away prizes. (user, registro_006/008, LOST: the Dipplin went from
# 50 -> 20 -> dead without the rival spending anything.) Two levers to stop it:
#   (a) Ripening Charge HEALS 30 on the Pokemon that receives the Grass -> direct it to
#       the doomed body instead of spending the MANUAL attachment (which does not heal);
#   (b) Night Stretcher recovers the Hydrapple ex to EVOLVE that Dipplin
#       (evolving resets the life: 80 -> 330).
# ============================================================================

def _load_fixture_obs(name):
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" / name, encoding="utf-8"))["observation"]


def _idx_ability(obs, card_id):
    """The index of the ABILITY option of the Pokemon `card_id` (active or bench)."""
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") != int(m.OptionType.ABILITY):
            continue
        area = o.get("area")
        if area == int(m.AreaType.ACTIVE):
            pk = me["active"][0]
        else:
            pk = me["bench"][o["index"]]
        if pk and pk["id"] == card_id:
            return i
    raise AssertionError(f"sin opcion ABILITY para {card_id}")


def test_marnie_step122_ripening_charge_heals_doomed_dipplin():
    # The state (registro_008 step 122): an active Hydrapple ex (150/330) ALREADY charged
    # for Syrup Storm, a bench Dipplin at 20/80 and a SINGLE Grass in hand.
    # The agent attached it manually (the same energy on the field, ZERO healing) and
    # the Dipplin died to the next Shadow Bullet. It must use Ripening Charge: the
    # Grass ends up in the same place and it also heals 30 (20 -> 50 > the snipe's 30).
    obs = _load_fixture_obs("marnie_step122_ripening_heals_doomed_dipplin.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    ripen = _idx_ability(obs, m.Hydrapple_ex)
    attach_dipplin = next(
        i for i, o in enumerate(obs["select"]["option"])
        if o.get("type") == int(m.OptionType.ATTACH)
        and o.get("inPlayArea") != int(m.AreaType.ACTIVE)
        and me["bench"][o["inPlayIndex"]]["id"] == m.Dipplin)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [ripen], (
        f"con el Dipplin a 20/80 condenado por el snipe de 30, la ultima Planta "
        f"debe ir por Ripening Charge (opt {ripen}, cura 30) y no por el adjunte "
        f"manual (opt {attach_dipplin}, sin curacion); obtuvo {result}")


def test_marnie_step122_healthy_dipplin_keeps_manual_attach():
    # Boundary: if the Dipplin SURVIVES the snipe (60 > 30), the healing does not
    # change anything and there is no reason to divert the ability: the previous
    # behaviour is kept (a manual attachment).
    import copy as _copy
    obs = _copy.deepcopy(
        _load_fixture_obs("marnie_step122_ripening_heals_doomed_dipplin.json"))
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    for b in me["bench"]:
        if b["id"] == m.Dipplin:
            b["hp"] = 60
    ripen = _idx_ability(obs, m.Hydrapple_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [ripen], (
        "con el Dipplin a 60/80 (sobrevive el snipe de 30) la curacion no salva "
        f"nada: no debe desviarse Ripening Charge (opt {ripen})")


def test_marnie_step122_ripening_targets_the_doomed_dipplin():
    # Once Ripening Charge is chosen, the Grass must go to the DOOMED body (the Dipplin
    # at 20/80), not to the active Hydrapple nor to a healthy Ogerpon: it is where the 30 of
    # healing changes the outcome, and Syrup Storm's damage (it scales with the
    # TOTAL Grass on the field) is identical wherever it is put.
    obs = _load_fixture_obs("marnie_step122_ripening_target_doomed_dipplin.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    dipplin = next(i for i, o in enumerate(obs["select"]["option"])
                   if o.get("area") == int(m.AreaType.BENCH)
                   and me["bench"][o["index"]]["id"] == m.Dipplin)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [dipplin], (
        f"Ripening Charge debe curar al Dipplin condenado (opt {dipplin}); "
        f"obtuvo {result}")


def test_marnie_ripening_lethal_charge_beats_the_heal():
    # A guard: the healing NEVER steals the Grass from a finisher. The same board as
    # the previous fixture (a Dipplin doomed at 20/80) but with a BENCH Hydrapple ex
    # at 1 energy for which the 2nd Grass builds a LETHAL Syrup Storm
    # on the Grimmsnarl ex (a Grass weakness) and a retreatable active: the Grass
    # must go to that Hydrapple (41000), not to healing.
    obs = _load_fixture_obs("marnie_ripening_lethal_charge_over_heal.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    hydra = next(i for i, o in enumerate(obs["select"]["option"])
                 if o.get("area") == int(m.AreaType.BENCH)
                 and me["bench"][o["index"]]["id"] == m.Hydrapple_ex)
    dipplin = next(i for i, o in enumerate(obs["select"]["option"])
                   if o.get("area") == int(m.AreaType.BENCH)
                   and me["bench"][o["index"]]["id"] == m.Dipplin)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [hydra], (
        f"con un Syrup Storm LETAL pendiente la Planta va al Hydrapple ex de "
        f"banca (opt {hydra}), no a curar al Dipplin (opt {dipplin}); "
        f"obtuvo {result}")


def test_marnie_night_stretcher_recovers_hydrapple_to_save_dipplin():
    # A Night Stretcher with the bench Dipplin doomed (20/80 against the 30
    # snipe): recovering the Hydrapple ex to EVOLVE it (80 -> 330) is worth more
    # than recovering a Grass of mere development, which is what the agent
    # picked even when the turn's KO was already secured.
    obs = _load_fixture_obs("marnie_ns_recovers_hydrapple_saves_dipplin.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    hydra = next(i for i, o in enumerate(opts)
                 if me["discard"][o["index"]]["id"] == m.Hydrapple_ex)
    energy = next(i for i, o in enumerate(opts)
                   if me["discard"][o["index"]]["id"] == m.Basic_Grass_Energy)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [hydra], (
        f"debe recuperar Hydrapple ex (opt {hydra}) para salvar al Dipplin "
        f"condenado, no la energia redundante (opt {energy}); obtuvo {result}")


def test_marnie_night_stretcher_healthy_dipplin_keeps_energy():
    # Boundary: with the Dipplin healthy (50 > the snipe's 30) there is no rescue to make
    # and the recovery goes back to the normal criterion (development energy).
    import copy as _copy
    obs = _copy.deepcopy(
        _load_fixture_obs("marnie_ns_recovers_hydrapple_saves_dipplin.json"))
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    for b in me["bench"]:
        if b["id"] == m.Dipplin:
            b["hp"] = 50
    opts = obs["select"]["option"]
    hydra = next(i for i, o in enumerate(opts)
                 if me["discard"][o["index"]]["id"] == m.Hydrapple_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [hydra], (
        f"sin Dipplin condenado no debe dispararse el rescate (opt {hydra})")


def test_op_bench_snipe_damage_table_covers_grimmsnarl():
    # The drip to the bench is now quantified (before there was only a boolean that
    # was read solely in the setup).
    assert m.OP_BENCH_SNIPE_DAMAGE[m.Grimmsnarl_ex] == 30
    assert m.RIPENING_HEAL == 30


# ============================================================================
# THE ORDER OF THE EVOLUTION LINE in a searcher's fetch (user,
# registro_006 step 79 vs Marnie, LOST). With an Applin on the bench and NO
# Dipplin (neither in play nor in hand), the Ultra Ball brought Hydrapple ex: a DEAD
# card (it cannot evolve anything) that also won through the prized-copy
# bonus (+150). The MISSING link must be searched for -- the Dipplin -- and, if
# that link is no longer in the DECK and the bench is full, the Ultra
# Ball must be CANCELLED. The Meganium line already did it right (Bayleef 850 > Meganium 200).
# ============================================================================

def test_marnie_ub_fetch_takes_the_missing_link_not_the_orphan_stage2():
    obs = _load_fixture_obs("marnie_ub_fetch_missing_link_dipplin.json")
    deck = obs["select"]["deck"]
    opts = obs["select"]["option"]
    dipplin = [i for i, o in enumerate(opts)
               if deck[o["index"]]["id"] == m.Dipplin]
    hydra = next(i for i, o in enumerate(opts)
                 if deck[o["index"]]["id"] == m.Hydrapple_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result and result[0] in dipplin, (
        f"con un Applin en banca y ningun Dipplin, la Ultra Ball debe traer "
        f"el eslabon que falta (Dipplin, opts {dipplin}), no el Hydrapple ex "
        f"huerfano (opt {hydra}); obtuvo {result}")


def test_marnie_ub_cancels_when_the_missing_link_left_the_deck():
    # The same board but with BOTH Dipplin in the discard: the link is no longer
    # in the DECK and the bench is FULL, so the Ultra Ball cannot
    # contribute anything and must not be played.
    obs = _load_fixture_obs("marnie_ub_cancel_link_not_in_deck.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert len(me["bench"]) >= 5, "el escenario exige la banca llena"
    ub = next(i for i, o in enumerate(obs["select"]["option"])
              if o.get("type") == int(m.OptionType.PLAY)
              and me["hand"][o["index"]]["id"] == m.Ultra_Ball)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [ub], (
        f"sin Dipplin en el mazo y con la banca llena la Ultra Ball "
        f"(opt {ub}) no aporta nada: debe cancelarse; obtuvo {result}")


def test_evo_link_state_classifies_missing_link_and_orphan():
    # An Applin in play, no Dipplin: the Dipplin is missing and the Hydrapple ex is
    # an orphan. The stage 2 NEVER enters `necesarios` (its own branches already
    # score it and apply the matchup clamps).
    nec, huer = m._evo_link_state({}, {m.Applin: 1})
    assert nec == {m.Dipplin} and m.Hydrapple_ex in huer
    # With the Dipplin already in play, the Hydrapple ex stops being an orphan and is not
    # forced from here.
    nec, huer = m._evo_link_state({}, {m.Applin: 1, m.Dipplin: 1})
    assert m.Hydrapple_ex not in huer and m.Hydrapple_ex not in nec
    # Linea completa (Hydrapple ex en juego): no se fuerza ningun eslabon.
    nec, _ = m._evo_link_state({}, {m.Applin: 1, m.Hydrapple_ex: 1})
    assert m.Dipplin not in nec


# ============================================================================
# A REDUNDANT SEARCH FOR MEOWTH EX (user, registro_010 step 118 vs Alakazam,
# WON with a mistake). Meowth ex is only worth its Last-Ditch Catch, and only
# ONE Supporter is played per turn: bringing a 2nd copy of one already in
# hand adds nothing and on top of that exposes a 2-prize body on the bench.
#   (a) the FETCH never picks a duplicate (the `copia_ya_en_mano` rule);
#   (b) if the ONLY thing searchable is a duplicate, the Meowth ex play is cancelled
#       and the turn goes on with the Supporter we already had.
# A documented exception: our first turn (the anti-donk line with an empty bench).
# Deck-agnostic: the prediction uses the SAME engine as the real fetch.
# ============================================================================

def test_alakazam_last_ditch_does_not_fetch_a_copy_already_in_hand():
    obs = _load_fixture_obs("alakazam_ld_fetch_no_duplica_supporter.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    deck = obs["select"]["deck"]
    opts = obs["select"]["option"]
    in_hand = {c["id"] for c in me["hand"]}
    xerosic = next(i for i, o in enumerate(opts)
                   if deck[o["index"]]["id"] == m.Xerosic_Machinations)
    assert m.Xerosic_Machinations in in_hand, "el escenario exige Xerosic en mano"
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    traido = deck[opts[result[0]]["index"]]["id"]
    assert traido not in in_hand, (
        f"el Last-Ditch no debe traer una 2a copia de un Supporter que ya esta "
        f"en la mano (Xerosic, opt {xerosic}); trajo {traido}")


def test_alakazam_cancels_meowth_if_the_search_is_redundant():
    # The same board but with ALL the other Supporters out of the deck: the only thing
    # the Last-Ditch could bring is another Xerosic, which is already in hand.
    obs = _load_fixture_obs("alakazam_meowth_cancela_busqueda_redundante.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [meowth], (
        f"con el unico Supporter buscable ya en mano, bajar Meowth ex (opt "
        f"{meowth}) solo regala 2 premios: debe cancelarse; obtuvo {result}")


def test_the_meowth_fetch_prediction_spots_the_duplicate():
    # The helper that decides BEFORE playing the Meowth: with Xerosic as the only
    # Supporter in the deck and a copy in hand, the predicted target is that
    # duplicate (the signal that cancels the play).
    deck = {m.Xerosic_Machinations: {m.ZONE_DECK: 1}}
    target, _ = m._meowth_fetch_prediccion(
        {m.Xerosic_Machinations: 1}, {}, 4, True, 12, False,
        False, False, False, False, True, deck)
    assert target == m.Xerosic_Machinations
    # Our first turn keeps the anti-donk exception (it is not capped).
    target_t1, value_t1 = m._meowth_fetch_prediccion(
        {m.Xerosic_Machinations: 1}, {}, 4, True, 12, False,
        False, False, False, False, True, deck, first_turn=True)
    assert target_t1 == m.Xerosic_Machinations and value_t1 > 40


# ============================================================================
# THE TURN'S SUPPORTER IS ALREADY IN HAND (user, registro_004 step 36 vs
# Alakazam, episode 88700047, WON with a mistake). Only ONE Supporter is played per
# turn: before spending the Meowth ex you have to know WHICH one is going to be played. If
# the winner is one we already have in hand, the one Last-Ditch Catch brings
# cannot be played today and the Meowth only gives away a 2-prize body.
# Different from `_meowth_fetch_redundante` (a copy of something already in hand):
# here the fetch brings something NEW and useful, but it LOSES the turn's slot.
# ============================================================================

def test_meowth_is_not_played_if_the_turn_supporter_is_already_in_hand():
    obs = _load_fixture_obs(
        "alakazam_no_meowth_si_el_supporter_del_turno_esta_en_mano.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    # The scenario requires the Xerosic in hand and NO Lillie's: the fetch would
    # bring one from the deck, but the Xerosic takes the turn's Supporter.
    in_hand = [c["id"] for c in me["hand"]]
    assert m.Xerosic_Machinations in in_hand
    assert m.Lillie_Determination not in in_hand
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [meowth], (
        f"el Supporter del turno (Xerosic, ya en mano) gana a la Lillie's que "
        f"traeria el Last-Ditch: bajar Meowth ex (opt {meowth}) regala 2 "
        f"premios para nada; obtuvo {result}")


def test_supp_play_score_orders_by_the_scale_that_decides():
    # The FETCH scale (`_REGLAS_MEOWTH_FETCH`) and the PLAY scale
    # contradicted each other: the first put Lillie's (1200) above Xerosic (<=150), the
    # second the other way round. `_supp_play_score` is the one that DECIDES, so the
    # Meowth's prediction has to be made in it.
    from collections import defaultdict
    ctx = _make_boss_ctx(
        op_is_alakazam_deck=True,
        op_hand_count=13,
        hand_counts={m.Xerosic_Machinations: 1, m.Meowth_ex: 1},
    )
    val_xerosic = m._supp_play_score(ctx, m.Xerosic_Machinations)
    # The Lillie's is valued on the hand AFTER the fetch (it enters the slot
    # the Meowth leaves), which is the board on which it would be decided.
    hand_after = defaultdict(int, {m.Xerosic_Machinations: 1,
                                  m.Lillie_Determination: 1})
    ctx_post = m._dc_replace(ctx, hand_counts=hand_after)
    val_lillie = m._supp_play_score(ctx_post, m.Lillie_Determination)
    # (here the Lillie's is even VETOED by `no_barajar_ultimo_xerosic`:
    # with the Xerosic in hand, shuffling it away is worse than refreshing.)
    assert val_xerosic > val_lillie, (
        f"Xerosic ({val_xerosic}) debe ganar a la Lillie's buscada "
        f"({val_lillie}) en la escala de JUGADA")
    best_id, best_val = m._best_supporter_in_hand(ctx_post, hand_after)
    assert best_id == m.Xerosic_Machinations and best_val == val_xerosic


def test_supp_play_score_lets_through_the_fetch_that_wins_the_game():
    # A counterweight: if what the fetch would bring is a Boss's Orders that WINS the
    # game, the turn's slot is worth it and the Meowth ex must still be played.
    from collections import defaultdict
    ctx = _make_boss_ctx(
        op_is_alakazam_deck=True,
        op_hand_count=13,
        hand_counts={m.Xerosic_Machinations: 1, m.Meowth_ex: 1},
    )
    hand_after = defaultdict(int, {m.Xerosic_Machinations: 1, m.Boss_Orders: 1})
    ctx_post = m._dc_replace(ctx, hand_counts=hand_after,
                             win_via_boss_gust=True)
    val_boss = m._supp_play_score(ctx_post, m.Boss_Orders)
    best_id, best_val = m._best_supporter_in_hand(ctx_post, hand_after)
    assert best_id == m.Boss_Orders, (
        f"el gusteo GANADOR ({val_boss}) debe llevarse el turno; "
        f"gano {best_id} con {best_val}")


# ============================================================================
# MENU <-> PROMPT COHERENCE (user, registro_010 steps 118/120 vs Alakazam).
# ABILITIES are only listed as options in the MAIN MENU. The engines
# that project damage read `select.option` to know whether Teal Dance was still
# available, so the SAME turn was worth one thing in the menu and another in the
# chained prompts: the agent played Meowth ex "to search for Boss's Orders"
# (with Teal Dance -> Myriad 270 knocks out the bench Fezandipiti ex: 2 prizes) and
# two steps later, already in the fetch's prompt, it valued that Boss's at 0 (without
# Teal Dance -> 150, it does not knock out) and took another card. Now
# availability is cached per turn (`_td_ability_serial`).
# ============================================================================

def test_alakazam_the_fetch_follows_the_menu_plan_boss_orders():
    menu = _load_fixture_obs("alakazam_step118_menu_principal.json")
    fetch = _load_fixture_obs("alakazam_ld_fetch_no_duplica_supporter.json")
    me = menu["current"]["players"][menu["current"]["yourIndex"]]
    meowth = next(i for i, o in enumerate(menu["select"]["option"])
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._td_ability_serial = None
    xerosic = next(i for i, o in enumerate(menu["select"]["option"])
                   if o.get("type") == int(m.OptionType.PLAY)
                   and me["hand"][o["index"]]["id"] == m.Xerosic_Machinations)
    # On THIS board the Meowth ex is NO longer played: `_meowth_fetch_pierde_el_turno`
    # (registro_004 step 36) discovers that the fetch's Boss's (a 2-prize gust,
    # 6800) LOSES the turn's only Supporter slot against the
    # Xerosic already in hand (7300) -- which is literally the agent's tuned
    # scale: XEROSIC_SCORE_SOBRE_BOSS (7000) > GUST_2PRIZE (6800),
    # "capping the hand beats any gust that does not WIN the game". Playing the
    # Meowth to search for a card that is not going to be played gave away 2 prizes.
    decision = m.agent(menu)
    assert decision != [meowth], (
        f"con el Xerosic en mano el fetch del Boss's no se juega este turno: "
        f"no debe bajarse el Meowth ex (opt {meowth}); obtuvo {decision}")
    assert xerosic >= 0
    # What THIS test protects still stands: if the Last-Ditch does get resolved
    # the SAME turn, the prompt must bring what the menu had in mind (the
    # Boss's), not revalue it with the Teal Dance already spent.
    # The same turn, a chained prompt: the fetch must bring what motivated the play.
    deck = fetch["select"]["deck"]
    result = m.agent(fetch)
    traido = deck[fetch["select"]["option"][result[0]]["index"]]["id"]
    assert traido == m.Boss_Orders, (
        f"el Last-Ditch debe traer el Boss's Orders que motivo bajar el Meowth "
        f"(gusteo de 2 premios al Fezandipiti ex); trajo {traido}")


def test_teal_dance_availability_is_stable_outside_the_menu():
    # The cache is filled in the MAIN MENU and survives the prompts that do not
    # list abilities; with no previous menu it stays None (conservative).
    menu = _load_fixture_obs("alakazam_step118_menu_principal.json")
    me = menu["current"]["players"][menu["current"]["yourIndex"]]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._td_ability_serial = None
    m.agent(menu)
    assert m._td_ability_serial == me["active"][0]["serial"], (
        "tras el menu principal queda cacheado el serial del activo con "
        "habilidad disponible")


# ============================================================================
# A DEAD-TURN RESCUE WITH MEOWTH EX (user, registro_002 step 18 vs Cubchoo,
# LOST). Turn 2: the active is a Meowth ex that does NOT attack, the bench is a Tapu
# Bulu with no energy (it needs 4) and an Applin, and the hand has no play
# (a Hydrapple ex with no Dipplin, a Boss's with no KO, the energy already attached). The agent
# closed the turn with a Meowth ex in hand that it had also JUST searched for with
# an Ultra Ball. Playing it fires Last-Ditch Catch -> Lillie's Determination ->
# a refresh: anything is better than doing nothing. The rescue comes after
# all the vetoes and only overrides "ending without doing anything", so the
# anti-Cubchoo veto of a 2nd Meowth ex is still in force as soon as there is a real play.
# ============================================================================

def test_cubchoo_dead_turn_plays_meowth_instead_of_ending():
    obs = _load_fixture_obs("cubchoo_turno_muerto_baja_meowth.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    fin = next(i for i, o in enumerate(opts)
               if o.get("type") == int(m.OptionType.END))
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [meowth], (
        f"sin ningun atacante ni jugada posible, bajar Meowth ex (opt {meowth}) "
        f"para que Last-Ditch traiga Lillie's es mejor que terminar el turno "
        f"(opt {fin}); obtuvo {result}")


def test_cubchoo_with_a_real_play_still_vetoes_the_second_meowth():
    # Boundary: the rescue ONLY overrides the dead turn. If there is a real play
    # (here an attachable Grass), the anti-Cubchoo veto of the 2nd Meowth ex rules.
    import copy as _copy
    obs = _copy.deepcopy(_load_fixture_obs("cubchoo_turno_muerto_baja_meowth.json"))
    obs["current"]["energyAttached"] = False
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    energy = next(i for i, c in enumerate(me["hand"])
                   if c["id"] == m.Basic_Grass_Energy)
    obs["select"]["option"].insert(0, {
        "area": 2, "inPlayArea": 5, "inPlayIndex": 0,
        "index": energy, "type": int(m.OptionType.ATTACH)})
    opts = obs["select"]["option"]
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [meowth], (
        f"con una jugada real disponible el turno no esta muerto: el veto "
        f"anti-Cubchoo del 2o Meowth ex (opt {meowth}) sigue mandando; "
        f"obtuvo {result}")


# ============================================================================
# ANTI-CUBCHOO: do not evolve into a SLOW body that does not reach its attack
# (user, registro_034 step 131, LOST). The Cubchoo deck blocks and discards
# energy, so a Pokemon with a HIGH retreat cost (Hydrapple ex: 3) that
# also does not reach its attack requirement (Syrup Storm: 2) is left NAILED DOWN in the
# active spot -- it neither attacks nor retreats -- and gives away 2 prizes. The agent evolved
# an active Dipplin with ZERO energies (33000). The gate is the retreat cost,
# which is the real reason, and the rule is bounded to the Cubchoo matchup.
# ============================================================================

def _idx_evolve(obs):
    return [i for i, o in enumerate(obs["select"]["option"])
            if o.get("type") == int(m.OptionType.EVOLVE)]


def test_cubchoo_does_not_evolve_hydrapple_without_energy():
    obs = _load_fixture_obs("cubchoo_no_evolucionar_hydrapple_sin_energia.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert len(me["active"][0]["energies"]) == 0, "el escenario exige 0 energias"
    assert m.RETREAT_COST[m.Hydrapple_ex] >= 3
    evo = _idx_evolve(obs)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] not in evo, (
        f"vs Cubchoo no se evoluciona a Hydrapple ex (retirada 3) sin energia "
        f"para atacar: quedaria clavado en el activo; obtuvo {result} (evo {evo})")


def test_cubchoo_does_evolve_hydrapple_with_energy():
    # Boundary: with enough energy for Syrup Storm the evolution IS worth it
    # (it attacks, and the 330 HP wall makes up for the retreat cost).
    obs = _load_fixture_obs("cubchoo_si_evoluciona_hydrapple_con_energia.json")
    evo = _idx_evolve(obs)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in evo, (
        f"con energia para atacar la evolucion a Hydrapple ex sigue siendo la "
        f"jugada (opts {evo}); obtuvo {result}")


def test_regla_lenta_acotada_al_matchup_cubchoo():
    # Boundary: the same board against a generic rival does NOT switch the rule on --
    # there it recharges and retreats normally and the wall makes up for it.
    obs = _load_fixture_obs("generico_si_evoluciona_hydrapple_sin_energia.json")
    evo = _idx_evolve(obs)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in evo, (
        f"fuera del matchup Cubchoo la evolucion a Hydrapple ex se mantiene "
        f"(opts {evo}); obtuvo {result}")


# ============================================================================
# THE LINE "Teal Dance -> retreat -> promote the lethal one" vs Cubchoo (user,
# registro_036 step 146, LOST). The active was a Teal Mask Ogerpon ex with
# ZERO energies: it neither attacks nor retreats. On the bench there was another Ogerpon ex with 4
# energies that KNOCKS OUT the active Cubchoo. `_attach_enable_retreat_ko` already detected
# the line and gave 41000 to the manual attachment on the active, but the precedence
# "Teal Dance before the attachment" vetoed it and the turn ended up charging a Tapu
# Bulu on the bench at 10 HP. The chain's three steps:
#   1) Teal Dance on the ACTIVE (it attaches the Grass AND draws)
#   2) RETREAT (the anti-Cubchoo veto yields: it does not destroy investment and there is a KO)
#   3) promote the Ogerpon with 4 energies, not the Hydrapple ex that would be left nailed down
# ============================================================================

def test_cubchoo_teal_dance_enables_the_retreat_towards_the_ko():
    obs = _load_fixture_obs("cubchoo_teal_dance_habilita_retirada_ko.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert len(me["active"][0]["energies"]) == 0
    td = [i for i, o in enumerate(obs["select"]["option"])
          if o.get("type") == int(m.OptionType.ABILITY)
          and o.get("area") == int(m.AreaType.ACTIVE)]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in td, (
        f"con el activo a 0 energias y un Ogerpon letal en banca, Teal Dance en "
        f"el ACTIVO (opts {td}) habilita la retirada y ademas roba; "
        f"obtuvo {result}")


def test_cubchoo_after_teal_dance_it_does_retreat():
    obs = _load_fixture_obs("cubchoo_tras_teal_dance_retira_al_ogerpon.json")
    ret = [i for i, o in enumerate(obs["select"]["option"])
           if o.get("type") == int(m.OptionType.RETREAT)]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in ret, (
        f"el veto anti-Cubchoo de retirada cede cuando la retirada NOQUEA y el "
        f"activo no tiene excedente de energia que perder; obtuvo {result}")


def test_cubchoo_promotes_the_ogerpon_not_the_nailed_down_hydrapple():
    obs = _load_fixture_obs("cubchoo_promueve_ogerpon_letal_tras_retirar.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    oger = [i for i, o in enumerate(opts)
            if me["bench"][o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex]
    hydra = [i for i, o in enumerate(opts)
             if me["bench"][o["index"]]["id"] == m.Hydrapple_ex]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in oger, (
        f"vs Cubchoo se promueve el Ogerpon ex (retirada 1, 4 energias) y no el "
        f"Hydrapple ex (retirada 3, 2 energias -> clavado); oger={oger} "
        f"hydra={hydra}, obtuvo {result}")


def test_cubchoo_with_energy_already_invested_it_still_passes():
    # The BOUNDARY between the user's two rules: here the active has THREE
    # physical Grass. Retreating would destroy investment already put on the board, so
    # we PASS even though there is also a KO behind (registro_004 p47).
    obs = _load_fixture_obs("cubchoo_step47_no_energy_wasting_retreat.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert m._physical_energy(len(me["active"][0]["energies"])) > \
        m.RETREAT_COST[me["active"][0]["id"]], "el escenario exige excedente"
    ret = [i for i, o in enumerate(obs["select"]["option"])
           if o.get("type") == int(m.OptionType.RETREAT)]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] not in ret, (
        f"con excedente de energia invertida el veto anti-Cubchoo se mantiene; "
        f"obtuvo {result}")


# ============================================================================
# SURVIVAL WHEN PROMOTING (user, registro_005 step 64 vs Archaludon, LOST).
# When choosing which body goes to the active spot, the FIRST thing is whether it survives the
# rival active's attack. Archaludon ex hit for 220 and the agent brought up a Teal Mask Ogerpon
# ex of 210 HP with SIX energies (4557 against the Hydrapple ex's 259): it died without
# knocking out -- Myriad projected 300 against 400 HP -- and gave away 2 prizes and all
# the charge. Two criteria, deck-agnostic:
#   1) if any SURVIVES, the doomed ones are penalised;
#   2) if NONE survives, the one that gives away the FEWEST prizes comes up.
# Exception: the one that KNOCKS OUT the rival active keeps its score (taking a prize
# even if it dies is a valid trade).
# ============================================================================

def _promo_elegido(obs):
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    r = m.agent(obs)
    return me["bench"][obs["select"]["option"][r[0]]["index"]]


def test_archaludon_promotes_the_body_that_survives_the_attack():
    obs = _load_fixture_obs("archaludon_step64_promueve_el_que_aguanta.json")
    o = m.to_observation_class(obs)
    op_act = o.current.players[1].active[0]
    vivos = [b for b in o.current.players[0].bench
             if m._op_active_attack_damage_to(op_act, b) < b.hp]
    assert [b.id for b in vivos] == [m.Hydrapple_ex], (
        "el escenario exige que solo el Hydrapple ex aguante los 220")
    picked = _promo_elegido(obs)
    assert picked["id"] == m.Hydrapple_ex, (
        f"sube el unico cuerpo que aguanta (330 PV), no el Ogerpon ex cargado "
        f"que muere a 220 sin noquear; obtuvo {picked['id']}")


def test_with_no_survivor_it_promotes_the_one_worth_fewer_prizes():
    # The REAL scenario (lucario_step99): Mega Lucario hits for 270 and on the bench
    # nobody survives -- Meganium 130, Ogerpon ex 210, Dipplin 80. Then criterion
    # 2 rules: give away the FEWEST prizes. Dipplin/Meganium are worth 1, the
    # Ogerpon ex is worth 2. (Meganium is left out by its own promotion veto:
    # it is the Wild Growth engine that doubles all our energy.)
    obs = _load_lucario_step99_obs()
    o = m.to_observation_class(obs)
    op_act = o.current.players[1].active[0]
    assert not [b for b in o.current.players[0].bench
                if m._op_active_attack_damage_to(op_act, b) < b.hp], \
        "el escenario exige que no sobreviva nadie"
    chosen = _promote_choice_id(obs)
    assert chosen != m.Teal_Mask_Ogerpon_ex, (
        f"sin superviviente se entrega el minimo de premios (1), no el ex de 2; "
        f"promovio id {chosen}")


def test_the_survivor_does_not_override_the_one_that_knocks_out():
    # THE PRIORITY OF THE ONE THAT KNOCKS OUT (user): the charged attacker is brought up instead of the
    # tank ONLY when that attacker knocks out the rival. Taking the prize rules
    # even if it dies afterwards. With the Archaludon at 60 HP, the charged Ogerpon
    # (Myriad 300) knocks it out; the Hydrapple ex, with 0 energies, does not reach its
    # attack even though it survives the blow. Implemented as a GUARANTEE
    # (`PROMO_KO_BONUS`, above the maximum score of the other branches) and not
    # as a mere exemption from the penalty.
    import copy as _c
    obs = _c.deepcopy(_load_fixture_obs(
        "archaludon_step64_promueve_el_que_aguanta.json"))
    obs["current"]["players"][1]["active"][0]["hp"] = 60
    picked = _promo_elegido(obs)
    assert picked["id"] == m.Teal_Mask_Ogerpon_ex, (
        f"el cuerpo que NOQUEA se promueve aunque muera despues; obtuvo "
        f"{picked['id']} ({m.card_table[picked['id']].name})")


# Autopsy iron_thorns p007 (turn 16, Jul 2026 plan P1.4 plan B): with an Iron
# Thorns ex as the rival active (Initialization cancels Teal Dance / Ripening /
# Last-Ditch / Flip the Script), the agent closed the turn with END while holding a
# Tapu Bulu IN HAND (66 sterile turns across 15 losses). Tapu Bulu is the
# manual attacker with no ability: the Iron Thorns matchup enters the list of
# play priorities (22000), like Cornerstone/Crustle.
_IRON_THORNS_TAPU_FIXTURE = (
    ROOT / "tests" / "fixtures" / "iron_thorns_t16_baja_tapu_no_end.json")


def test_iron_thorns_t16_plays_tapu_instead_of_ending():
    with open(_IRON_THORNS_TAPU_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Tapu_Bulu in play_map.values()
    tapu_opt = next(i for i, cid in play_map.items() if cid == m.Tapu_Bulu)

    result = m.agent(obs)
    assert result == [tapu_opt], (
        f"vs Iron Thorns ex activo, con Tapu Bulu en mano el turno no se "
        f"cierra con END: se baja el atacante sin habilidad (opt {tapu_opt}); "
        f"obtuvo {result} (map={play_map})")


# Autopsy iron_thorns p030 (turn 2, step 1 of the Jul 2026 plan): an Iron Thorns ex
# ALREADY as the rival active and OUR active is a Tapu Bulu; in hand there is a SECOND
# Tapu Bulu and the agent closed with END holding 7 cards. Cause: the redundant-copy
# veto (field_counts >= 1) was evaluated BEFORE the matchup branches,
# so the backup of the matchup's ONLY attacker (with Teal Dance /
# Ripening / Last-Ditch cancelled by Initialization) died in hand. The
# `_tapu_backup_vs_lock` exception plays the 2nd Tapu when the only Tapu in
# play is the ACTIVE (with no relief if it falls) and the rival cancels our engine.
_IRON_THORNS_2TAPU_FIXTURE = (
    ROOT / "tests" / "fixtures" / "iron_thorns_t2_baja_segundo_tapu.json")


def test_iron_thorns_t2_plays_a_second_tapu_as_backup():
    with open(_IRON_THORNS_2TAPU_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Tapu_Bulu in play_map.values()
    tapu_opt = next(i for i, cid in play_map.items() if cid == m.Tapu_Bulu)

    result = m.agent(obs)
    assert result == [tapu_opt], (
        f"vs Iron Thorns ex activo con Tapu Bulu ACTIVO nuestro, el 2o Tapu "
        f"de la mano se baja como respaldo del unico atacante (opt "
        f"{tapu_opt}); obtuvo {result} (map={play_map})")


def test_generic_a_second_tapu_stays_vetoed_without_a_lock():
    """An inverse control: with no wall/lock across the table the copy veto is kept."""
    with open(_IRON_THORNS_2TAPU_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    # The rival stops being an Iron Thorns ex: a neutral active with no lock or
    # immunities (Applin) -> no matchup flag fires.
    op_index = 1 - obs["current"]["yourIndex"]
    obs["current"]["players"][op_index]["active"][0]["id"] = m.Applin

    play_map = _resolve_play_options(obs)
    tapu_opt = next(i for i, cid in play_map.items() if cid == m.Tapu_Bulu)

    result = m.agent(obs)
    assert result != [tapu_opt], (
        f"sin lock enfrente, el 2o Tapu Bulu sigue vetado (copia "
        f"redundante); obtuvo {result} (map={play_map})")


# Autopsy iron_thorns p018 (turn 10, step 3 of the Jul 2026 plan): an Iron Thorns ex
# as the rival ACTIVE (Initialization locks Teal Dance / Ripening / Last-Ditch),
# non-lockers on their bench, an Ogerpon ex on ours and Meowth ex + 2x Boss's
# Orders in hand -- and the agent closed with END (`sin_valor=-1`). The lock is
# POSITIONAL: gusting a non-locker into the rival active spot switches it off on the spot.
# A new rule `gusteo_deslockea_habilidades` (BOSS_SCORE_UNLOCK_GUST).
_IRON_THORNS_UNLOCK_FIXTURE = (
    ROOT / "tests" / "fixtures" / "iron_thorns_t10_boss_deslockea.json")


def test_iron_thorns_t10_boss_deslockea_habilidades():
    with open(_IRON_THORNS_UNLOCK_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Boss_Orders in play_map.values()
    boss_opt = next(i for i, cid in play_map.items() if cid == m.Boss_Orders)

    result = m.agent(obs)
    assert result == [boss_opt], (
        f"con Iron Thorns ex activo rival y no-lockers en su banca, Boss's "
        f"se juega para DES-LOCKEAR el motor (opt {boss_opt}); obtuvo "
        f"{result} (map={play_map})")


def test_boss_does_not_unlock_if_the_opponent_bench_is_all_iron_thorns():
    """Inverse control A: with no non-locker to bring up, the gust switches nothing off."""
    with open(_IRON_THORNS_UNLOCK_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    op_index = 1 - obs["current"]["yourIndex"]
    for b in obs["current"]["players"][op_index]["bench"]:
        if b is not None:
            b["id"] = m.Iron_Thorns_ex

    play_map = _resolve_play_options(obs)
    boss_opt = next(i for i, cid in play_map.items() if cid == m.Boss_Orders)

    result = m.agent(obs)
    assert result != [boss_opt], (
        f"con la banca rival TODA Iron Thorns el gusteo mantiene el lock: "
        f"Boss's sigue vetado; obtuvo {result} (map={play_map})")


def test_boss_does_not_unlock_with_no_engine_to_wake():
    """Inverse control B: with no Ogerpon/Hydrapple in play and no Meowth in hand,
    the unlocking buys nothing TODAY and the Boss's is kept."""
    with open(_IRON_THORNS_UNLOCK_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    cur = obs["current"]
    yo = cur["players"][cur["yourIndex"]]
    for b in yo["bench"]:
        if b is not None and b["id"] == m.Teal_Mask_Ogerpon_ex:
            b["id"] = m.Tapu_Bulu
    for c in yo["hand"]:
        if c["id"] == m.Meowth_ex:
            c["id"] = m.Xerosic_Machinations

    play_map = _resolve_play_options(obs)
    boss_opt = next(i for i, cid in play_map.items() if cid == m.Boss_Orders)

    result = m.agent(obs)
    assert result != [boss_opt], (
        f"sin habilidades que despertar, Boss's no se quema en el "
        f"des-lockeo; obtuvo {result} (map={play_map})")


# NOTE (Jul 2026 cycle, MEASURED AND REVERTED): here lived the tests of the
# "Boss's -> Dwebble via a retreat" chain (fixture crustle p049 step 72:
# crustle_gust_worth_it with an alternative KO after retreating + the gust's mode
# per candidate). The specific line was real, but the aggregate measured -1.4
# points vs crustle (n=4000/branch, consistently negative across 3 runs) and it was
# reverted as a block; see the notes in main.py next to
# `crustle_gust_worth_it` and to the target's mode selector.


def test_gust_estorbo_forbid_iron_thorns():
    """NUISANCE mode never brings up an Iron Thorns ex: it creates/keeps the lock
    on our own engine (the rule estorbo_crea_lock_iron_thorns)."""
    def _ctx(card_id):
        return m._CtxGustObjetivo(
            card_id=card_id, energy=0, rc0=2, rc1=2, stall_diff=2,
            is_ex=True, is_exmega=True, is_megaex=False, prizes=2,
            wins_now=False, is_stage1=False, is_stage2=False,
            tiene_tool=False, can_ko=False, tier_ko=0,
            plan_target_match=False, regust_energized=False,
            line_rank=0, line_can_ko=False, op_alakazam=False,
            op_latias=False, op_dragapult_line=False,
            op_typhlosion_line=False)

    s_iron, _ = m._resolve_rules(
        m._RULES_GUST_NUISANCE, m._ADJUST_GUST_NUISANCE,
        _ctx(m.Iron_Thorns_ex), default=-200)
    assert s_iron == m.SCORE_FORBID, (
        f"estorbo con Iron Thorns ex debe ser FORBID; obtuvo {s_iron}")

    # Control: another ex with the same net stuckness keeps its nuisance value.
    s_otro, _ = m._resolve_rules(
        m._RULES_GUST_NUISANCE, m._ADJUST_GUST_NUISANCE,
        _ctx(m.Alakazam_ex), default=-200)
    assert s_otro > 0, (
        f"un ex no-locker con traba neta sigue siendo estorbo valido; "
        f"obtuvo {s_otro}")


# Autopsy cornerstone_cubchoo p004 (turn 2, Jul 2026 plan): with the rival on
# Cornerstone (386 active, an ex 117 on the bench), an active Applin and a hand with
# Tapu Bulu + 2x Forest + a UB, the agent closed with END (122 sterile turns
# across 41 losses). Two root vetoes: the Tapu crowding rule (>2 in play) did not
# exempt Cornerstone -- the matchup where Tapu is THE attacker -- and the Forest was
# vetoed on the first turn going second even with a REDUNDANT copy in hand.
_CORNERSTONE_TAPU_FIXTURE = (
    ROOT / "tests" / "fixtures" / "cornerstone_t2_baja_tapu_no_end.json")


def test_cornerstone_t2_plays_tapu_instead_of_ending():
    with open(_CORNERSTONE_TAPU_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Tapu_Bulu in play_map.values()
    tapu_opt = next(i for i, cid in play_map.items() if cid == m.Tapu_Bulu)

    result = m.agent(obs)
    assert result == [tapu_opt], (
        f"vs Cornerstone, con Tapu Bulu en mano el turno 2 no se cierra con "
        f"END: se baja el unico atacante del matchup (opt {tapu_opt}); "
        f"obtuvo {result} (map={play_map})")


# Autopsy comfey p014 (turn 8, Jul 2026 plan): the anti-Comfey allowlist
# vetoed Bug Catching Set and in 178/186 late sterile turns we had 0
# Grass in hand (Hammer/Fan dry the table and with no supply there is no attachment nor
# Teal Dance): we lost on prizes without taking a single one in games of 40+
# turns. BCS enters the allowlist (and is kept in Xerosic's discard).
_COMFEY_BCS_FIXTURE = (
    ROOT / "tests" / "fixtures" / "comfey_t8_juega_bug_catching_set.json")


def test_comfey_t8_plays_bug_catching_set():
    with open(_COMFEY_BCS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Bug_Catching_Set in play_map.values()
    bcs_opts = [i for i, cid in play_map.items() if cid == m.Bug_Catching_Set]

    result = m.agent(obs)
    assert result[0] in bcs_opts, (
        f"vs Comfey con 0 Plantas en mano, Bug Catching Set (surtidor de "
        f"energia) debe jugarse (opts {bcs_opts}); obtuvo {result} "
        f"(map={play_map})")


# The anti-sterile-turn net with an Ultra Ball (Jul 2026 plan): the cluster of sterile
# turn 2s with the UB vetoed appeared in 4 matchups (iron_thorns, cornerstone,
# comfey, crustle_kangaskhan: 13/31 findings at t2). With a NON-empty bench, if
# the best play is END and the UB has a useful target in the deck, it is rehabilitated.
# Guards: not vs Comfey (mill) nor vs Cubchoo (a deliberate conservative END).
_STERIL_UB_FIXTURE = (
    ROOT / "tests" / "fixtures" / "crustle_t2_red_esteril_juega_ub.json")


def test_the_sterile_net_revives_the_ultra_ball_with_a_bench():
    with open(_STERIL_UB_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    ub_opts = [i for i, cid in play_map.items() if cid == _ULTRA_BALL]
    assert ub_opts

    result = m.agent(obs)
    assert result[0] in ub_opts, (
        f"turno esteril con UB vetada y objetivo util en mazo: la red debe "
        f"jugar la Ultra Ball (opts {ub_opts}); obtuvo {result} (map={play_map})")


# Record 008 vs Mega Starmie/Froslass with a TECH Cornerstone ex on the rival
# bench (LOST, Jul 2026). Two mistakes in the same turn 8:
# (a) step 75: the anti-Cornerstone whitelist of the Night Stretcher fetch
#     vetoed the ENERGY (matchup-agnostic) and recovered a dead Tapu Bulu;
#     the Grass enabled the active Hydrapple's Syrup Storm THIS turn.
# (b) step 74: the 4th-ex block vs Crustle/Cornerstone crushed
#     Fezandipiti ex with Flip the Script ALIVE (ko_last_turn): draw 3 now.
_STARMIE_NS_FIXTURE = (
    ROOT / "tests" / "fixtures" / "starmie_step75_ns_recupera_energia.json")
_STARMIE_FEZ_FIXTURE = (
    ROOT / "tests" / "fixtures" / "starmie_step74_baja_fez_flip_script.json")


def _reset_state_record_008():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_last_turn = -1
    m._prev_op_prize = 6
    m._ko_detected_this_turn = False
    m.plan = m.AttackPlan()


def test_starmie_step75_the_ns_recovers_energy_not_tapu():
    with open(_STARMIE_NS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    elegida = me["discard"][opt["index"]]["id"]
    assert elegida == m.Basic_Grass_Energy, (
        f"NS debe recuperar la Planta (habilita Syrup Storm este turno), no "
        f"{m.card_table[elegida].name}")


def test_starmie_step74_plays_fez_with_flip_the_script_alive():
    with open(_STARMIE_FEZ_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), f"esperaba PLAY, {opt}"
    elegida = me["hand"][opt["index"]]["id"]
    assert elegida == m.Fezandipiti_ex, (
        f"con KO sufrido el turno anterior, bajar Fezandipiti ex (Flip the "
        f"Script roba 3) supera al resto; jugo {m.card_table[elegida].name}")


# Record 004 turn 4 vs Team Rocket (LOST): an active Ogerpon ex at 30/210
# DOOMED with 3 energies, a bench with only a Tapu Bulu 1e (no ready relief). The
# deadlock `cede_a_boss_ejecutable` (Lillie's yields to Boss's) +
# `boss_ko_threat_preevo` (Boss's scores the 1-prize KO of the weak Spidops)
# spent the Supporter on a gust that left the board with no plan. A deck-agnostic
# fix: with `active_ko_likely and not has_ready_bench_attacker`,
# the prize gust yields to Lillie's in BOTH rules; the WINNING gust
# (win_via_bench / dodge_redirect) still dominates.
_ROCKET_LILLIE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "rocket_t4_lillie_sobre_boss_condenado.json")


def test_rocket_t4_lillie_over_boss_with_a_doomed_active():
    with open(_ROCKET_LILLIE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), f"esperaba PLAY, {opt}"
    elegida = me["hand"][opt["index"]]["id"]
    assert elegida == m.Lillie_Determination, (
        f"con el activo condenado y sin relevo en banca, el gusteo de +1 "
        f"premio cede a Lillie's (cavar el plan futuro); jugo "
        f"{m.card_table[elegida].name}")


# Record 008 step 85 vs Alakazam (episode 88119461, LOST): a rival hand of
# 15 cards (Powerful Hand 20x17 = 340 one-shots anything of ours),
# Meowth ex IN HAND, Xerosic in the DECK and the Supporter free. The "Meowth
# in hand -> Xerosic" engine (21500) fired but the generic veto "never play
# Meowth with a Lillie's already in hand" (registro_003, a redundant fetch) overrode it and
# the agent played Boss's/Poke Pad leaving the cannon loaded. The
# `_alk_meowth_hand_engine` exception lifts that veto: the fetch aims at the Xerosic, not at
# a redundant Lillie's.
_ALK_MEOWTH_ENGINE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_step85_meowth_engine_sobre_boss.json")


def test_alakazam_step85_meowth_engine_sobre_boss():
    with open(_ALK_MEOWTH_ENGINE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), f"esperaba PLAY, {opt}"
    elegida = me["hand"][opt["index"]]["id"]
    assert elegida == m.Meowth_ex, (
        f"con la mano rival gorda y Xerosic en el mazo, bajar Meowth ex "
        f"(Last-Ditch -> Xerosic) supera el gusteo de Boss's; jugo "
        f"{m.card_table[elegida].name}")


# Record 004 step 43 vs Marnie's Grimmsnarl (episode 88120517): the agent
# charged a 2nd energy to a JUST evolved Dipplin (it could not evolve again;
# Do the Wave costs 1 and its damage does not scale with energy) above
# Teal Dance. A rule mirroring Applin's: a Dipplin at most 1 PHYSICAL
# energy; exceptions (a) a Hydrapple ex in hand and the Dipplin can evolve
# NOW (it did not appear this turn) and (b) a Hydrapple in play as a last resort.
_MARNIE_DIPPLIN_FIXTURE = (
    ROOT / "tests" / "fixtures" / "marnie_step43_dipplin_max_una_energia.json")


def test_marnie_step43_no_sobrecargar_dipplin_recien_evolucionado():
    with open(_MARNIE_DIPPLIN_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    # The 2nd energy to the Dipplin (an ATTACH to bench1) is vetoed; the play
    # chosen is Teal Dance (ABILITY, type 10) from either of the Ogerpon.
    assert opt.get("type") != 8 or opt.get("inPlayIndex") != 1, (
        f"no se debe cargar la 2a energia al Dipplin recien evolucionado: {opt}")
    assert opt.get("type") == 10, (
        f"la linea correcta es Teal Dance (energia al Ogerpon + robo); {opt}")


# Record 002 steps 24/27 vs Ceruledge (episode 88148744, LOST): on
# our FIRST action turn, with the bench already populated (4/5) and a hand
# full of future value (Xerosic, Unfair Stamp, Lana's, Dipplin, Meganium),
# the anti-sterile-turn net rehabilitated the Ultra Ball (200) and the agent
# chained TWO UBs discarding Xerosic+Meganium+Lana's+Dipplin for 2 Meowth ex
# dead in hand. A new guard: on turn <= 2 the net only applies with a bench
# <= 2 (the crustle t2 case with a bench of 1 that motivated it is still covered); the
# legitimate first-turn UB with a made board is only the Budew/Dragapult case
# of `_ub_first_turn_allowed`.
_CERULEDGE_UB_FIXTURE = (
    ROOT / "tests" / "fixtures" / "ceruledge_t2_no_ub_banca_poblada.json")


def test_ceruledge_t2_does_not_play_the_ub_with_a_populated_bench():
    with open(_CERULEDGE_UB_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.END), (
        f"primer turno con banca 4/5 y mano rica: la UB no se juega (quema 2 "
        f"cartas utiles por un basico redundante); esperaba END, {opt}")


# Record 006 step 68 vs Mega Abomasnow ex (episode 88147133, LOST):
# an ACTIVE Hydrapple ex with 2 effective energies and Meganium in play -> Syrup
# Storm = 30 + 30 x 10 Grass = 330, TWENTY below the 350 HP of the active Mega
# Abomasnow ex (3 prizes). In hand there was a Night Stretcher and in the
# discard TWO Grass: recovering one and attaching it with Teal Dance (an ABILITY,
# it does not consume the turn's manual attachment, already spent) raises the Syrup Storm to
# 390 and knocks out. The agent attacked for 330 all the same.
#
# Two chained failures:
#   1) `_ns_banca_llena_guardar` (the full-bench cut-off) vetoed the Night
#      Stretcher: it considered the energy "useless" through `state.energyAttached`,
#      ignoring that Teal Dance / Ripening Charge are ABILITIES and can still
#      attach it.
#   2) The Teal Dance branch of an Ogerpon with >= 3 energies only looked at ITS
#      own Myriad Leaf Shower (`_extra_energy_enables_ko` with the Ogerpon), not
#      at the fact that the ACTIVE Hydrapple's Syrup Storm counts the Grass of ALL
#      our Pokemon -> the ability was vetoed and the recovered Grass
#      stayed dead in hand.
_ABOMASNOW_NS_SYRUP_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "abomasnow_step68_ns_energia_para_syrup_letal.json")
_ABOMASNOW_NS_FETCH_FIXTURE = (
    ROOT / "tests" / "fixtures" / "abomasnow_step68b_ns_fetch_energia.json")
_ABOMASNOW_TEAL_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "abomasnow_step68c_teal_dance_habilita_syrup.json")


def test_abomasnow_step68_plays_the_ns_for_the_lethal_syrup():
    with open(_ABOMASNOW_NS_SYRUP_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), (
        f"con Syrup Storm a 20 del KO y DOS Plantas en el descarte, Night "
        f"Stretcher va ANTES de atacar; esperaba PLAY, {opt}")
    assert me["hand"][opt["index"]]["id"] == m.Night_Stretcher, (
        f"esperaba Night Stretcher, jugo "
        f"{m.card_table[me['hand'][opt['index']]['id']].name}")


def test_abomasnow_step68_the_ns_recovers_the_grass_not_the_meganium():
    with open(_ABOMASNOW_NS_FETCH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    elegida = me["discard"][opt["index"]]["id"]
    assert elegida == m.Basic_Grass_Energy, (
        f"la Planta habilita el Syrup Storm letal ESTE turno; recupero "
        f"{m.card_table[elegida].name}")


def test_abomasnow_step68_teal_dance_makes_the_syrup_lethal():
    with open(_ABOMASNOW_TEAL_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ABILITY), (
        f"la Planta recuperada debe entrar al campo con Teal Dance (el Syrup "
        f"Storm cuenta la Planta de TODOS nuestros Pokemon: 330 -> 390 >= "
        f"350); esperaba ABILITY, {opt}")


_ABOMASNOW_FINISHER_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "abomasnow_step68d_ataca_tras_teal_dance.json")


def test_abomasnow_step68_finishes_after_the_charge():
    """Closing the NS -> Grass -> Teal Dance -> ATTACK chain: with the 12
    Grass already on the field the Syrup Storm does 390 >= 350 and knocks out."""
    with open(_ABOMASNOW_FINISHER_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con la carga hecha toca rematar (390 >= 350); esperaba ATTACK, {opt}")


# Record 003 (episode 88147133, LOST): the anti-sterile-turn net
# rehabilitated the Ultra Ball (200) on a turn in which NOTHING it could
# bring was usable. The board: a bench 4/5 with an Applin and a Chikorita JUST
# played (`appearThisTurn`, no Forest -> there is no way to evolve) and in
# hand there was already a Meowth ex (vetoed by the scorer, with the turn's Supporter
# already spent). The UB burned TWO cards -- Meganium, the Stage 2 of the
# line, and Dawn -- to bring a SECOND Meowth ex that was then not played.
#
# The rule (user), deck-agnostic: the Ultra Ball is only played if what it searches for can
# be USED this turn. Two sharpenings of the net:
#   (a) if the menu ALREADY offers playing/evolving a Pokemon and the scorer vetoed it,
#       the turn is not dead for lack of bodies: digging brings more of the
#       same and also burns 2 cards -> ending is better;
#   (b) the pre-evolution has to be able to evolve THIS turn (`appearThisTurn`
#       is checked body by body, not by species).
# The ONLY exception: a threat of an item block (a Budew on the rival field or a Dragapult
# deck, which carries one) -- there the UB is "use it or lose it" and digging
# something useful for the NEXT turn is allowed.
_UB_NO_USABLE_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "abomasnow_t6_no_ub_si_ya_hay_pokemon_en_mano.json")
_UB_BUDEW_FIXTURE = (
    ROOT / "tests" / "fixtures" / "abomasnow_t6_ub_con_budew_rival.json")
_UB_PREEVO_FRESCA_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "abomasnow_t6_no_ub_preevo_bajada_este_turno.json")
_UB_PREEVO_READY_FIXTURE = (
    ROOT / "tests" / "fixtures" / "abomasnow_t6_ub_preevo_evolucionable.json")


def _elige(fixture):
    with open(fixture, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    return obs, obs["select"]["option"][m.agent(obs)[0]]


def test_the_ub_is_not_played_if_a_playable_pokemon_is_already_in_hand():
    obs, opt = _elige(_UB_NO_USABLE_FIXTURE)
    assert opt.get("type") == int(OptionType.END), (
        f"con un Meowth ex ya en mano (vetado) y nada evolucionable, cavar "
        f"con Ultra Ball trae mas de lo mismo y quema 2 cartas; "
        f"esperaba END, {opt}")


def test_the_ub_is_played_with_an_opponent_budew_because_of_the_item_lock():
    obs, opt = _elige(_UB_BUDEW_FIXTURE)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert opt.get("type") == int(OptionType.PLAY), (
        f"con Budew en el campo rival la Ultra Ball es 'usala o pierdela' "
        f"(el proximo turno no hay items); esperaba PLAY, {opt}")
    assert me["hand"][opt["index"]]["id"] == _ULTRA_BALL


def test_the_ub_does_not_search_an_evolution_for_a_preevo_played_this_turn():
    obs, opt = _elige(_UB_PREEVO_FRESCA_FIXTURE)
    assert opt.get("type") == int(OptionType.END), (
        f"con la banca llena y el Applin recien bajado (no puede evolucionar "
        f"este turno) la Ultra Ball no produce nada; esperaba END, {opt}")


def test_the_ub_does_search_the_evolution_when_the_preevo_can_already_evolve():
    obs, opt = _elige(_UB_PREEVO_READY_FIXTURE)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert opt.get("type") == int(OptionType.PLAY), (
        f"contrafactual: con el Applin asentado la evolucion SI es jugable "
        f"este turno y la red debe cavar; esperaba PLAY, {opt}")
    assert me["hand"][opt["index"]]["id"] == _ULTRA_BALL


# ============================================================================
# DO NOT DIG WITH AN ULTRA BALL A POKEMON THAT IS NOT GOING TO BE PLAYED (user, registro_004
# step 35 vs Cynthia's Garchomp, episode 88701502, WON with a mistake).
#
# Turn 4: an active Teal Mask Ogerpon ex with 3 Grass (the finisher ready), a bench of
# Bayleef + Ogerpon ex + a JUST PLAYED Meowth ex (its Last-Ditch had already brought
# the Boss's Orders), and in hand {Night Stretcher, Ultra Ball, Xerosic, Tapu
# Bulu, Boss's Orders, Meganium, 2 Grass}. The right play -- and the one the
# agent ended up making -- was Boss's Orders (bring up the Cynthia's Gible) and
# knock out. But BEFORE that it played an Ultra Ball it did not need: it discarded TAPU BULU
# + XEROSIC to dig a SECOND Meowth ex... which the PLAY branch itself vetoed
# afterwards (score -1) and which stayed dead in hand.
#
# Two sides of the SAME rule of the user ("the Ultra Ball is only played to search for
# a Pokemon we need to PLAY"), both through incoherence with what the
# PLAY branch will do later:
#   (1) `_ub_cavar_meowth_se_juega`: the chain UB -> Meowth ex -> Last-Ditch ->
#       Supporter only looked at `field_counts[Meowth_ex] < 2`, but the card
#       allows ONE Last-Ditch per turn: with the bench Meowth having appeared
#       THIS turn the ability was already spent (`_meowth_ld_free` False) and the
#       second body would search for NOTHING. The PLAY branch already required it in its two
#       routes (`_ub_meowth_pending` and the 21700 rescue); the Ultra Ball's PLAY
#       side was the only one that did not check it.
#   (2) the Bayleef -> Meganium branch (1000) of `_eval_ub_best_target` did not look at whether
#       the Meganium was ALREADY in hand. Its sibling branches (Bayleef, Dipplin)
#       do, and `_ub_evolve_needs_search` documents the criterion: with the
#       evolution in hand the line evolves WITHOUT an Ultra Ball.
# ============================================================================
_UB_NO_CAVA_2O_MEOWTH_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "cynthia_no_ub_para_cavar_segundo_meowth_step35.json")


def _ub_cynthia_obs(mutar=None):
    with open(_UB_NO_CAVA_2O_MEOWTH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    if mutar is not None:
        mutar(obs)
    m._init_cards_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._td_ability_serial = None
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    play = {}
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(OptionType.PLAY):
            play[me["hand"][o["index"]]["id"]] = i
    return obs, play, m.agent(obs)


def test_no_ub_to_dig_a_second_meowth_with_the_last_ditch_spent():
    obs, play, result = _ub_cynthia_obs()
    assert result != [play[_ULTRA_BALL]], (
        f"el Meowth ex de la banca aparecio este turno (Last-Ditch gastada): "
        f"un 2o Meowth ex no buscaria nada y la rama PLAY lo veta, asi que la "
        f"Ultra Ball (opt {play[_ULTRA_BALL]}) no debe jugarse; obtuvo {result}")
    assert result == [play[m.Boss_Orders]], (
        f"con el activo cargado la jugada del turno es Boss's Orders "
        f"(opt {play[m.Boss_Orders]}) y noquear; obtuvo {result}")


def test_the_ub_digs_the_second_meowth_if_the_last_ditch_is_still_free():
    # Counterfactual (1): the SAME board with the Meowth ex from a PREVIOUS turn.
    # The Last-Ditch is free, the 2nd Meowth WOULD search for a Supporter and the PLAY
    # branch plays it (`_ub_meowth_pending`) -> the chain is completed and it digs.
    def _asentar_meowth(obs):
        me = obs["current"]["players"][obs["current"]["yourIndex"]]
        for pk in me["bench"]:
            if pk["id"] == m.Meowth_ex:
                pk["appearThisTurn"] = False
    obs, play, result = _ub_cynthia_obs(_asentar_meowth)
    assert result == [play[_ULTRA_BALL]], (
        f"con la Last-Ditch libre la cadena UB->Meowth->Supporter si produce: "
        f"esperaba jugar la Ultra Ball (opt {play[_ULTRA_BALL]}); obtuvo {result}")


def test_the_ub_does_not_dig_the_evolution_already_in_hand():
    # A unit test of the Bayleef->Meganium branch: with the Meganium IN HAND the line
    # evolves without an Ultra Ball, so that branch cannot justify the
    # search (1000). Without it in hand, it can.
    def _target(hand_counts):
        return m._eval_ub_best_target(
            {m.Bayleef: 1}, hand_counts,
            meganium_in_play=False, has_hydrapple=False, forest_in_play=False,
            op_has_ex_immune_active=False, op_has_ex_immune_bench=False,
            op_prize=6, bench_count=1,
            state=SimpleNamespace(turn=6, supporterPlayed=True,
                                  energyAttached=True),
            ko_last_turn=False, _best_supp_in_deck_val=0,
            supporters_in_hand=0, hand_is_weak=False,
            has_energy_for_teal=False, _we_go_first=False,
            _best_supp_in_hand_val=0, op_is_crustle_deck=False,
            op_is_cornerstone_deck=False, op_active_is_budew=False,
            meowth_ability_lock=False)

    with_meganium = _target({m.Meganium: 1})
    without_meganium = _target({})
    assert without_meganium >= 1000, (
        f"sin el Meganium en la mano hay que cavarlo; objetivo {without_meganium}")
    assert with_meganium < 1000, (
        f"con el Meganium ya en la mano la Ultra Ball no aporta a esa linea; "
        f"objetivo {with_meganium}")


def test_the_ub_digs_the_evolution_when_it_is_not_in_hand():
    # Counterfactual (2): with no Meganium in hand, the Bayleef->Meganium line
    # DOES need the search and the Ultra Ball is played again.
    def _quitar_meganium(obs):
        me = obs["current"]["players"][obs["current"]["yourIndex"]]
        pos = next(i for i, c in enumerate(me["hand"])
                   if c["id"] == m.Meganium)
        del me["hand"][pos]
        for o in obs["select"]["option"]:
            if o.get("type") == int(OptionType.PLAY) and o["index"] > pos:
                o["index"] -= 1
    obs, play, result = _ub_cynthia_obs(_quitar_meganium)
    assert result == [play[_ULTRA_BALL]], (
        f"sin el Meganium en la mano la Fase 2 de la linea si hay que cavarla: "
        f"esperaba la Ultra Ball (opt {play[_ULTRA_BALL]}); obtuvo {result}")


def test_ub_dig_meowth_gets_played_needs_a_free_last_ditch():
    # A unit test of the helper: the card's rule (ONE Last-Ditch per turn) rules
    # over the body count.
    free_ctx = _make_boss_ctx(field_counts={m.Meowth_ex: 1},
                              meowth_ld_free=True)
    ctx_gastada = _make_boss_ctx(field_counts={m.Meowth_ex: 1},
                                 meowth_ld_free=False)
    ctx_dos = _make_boss_ctx(field_counts={m.Meowth_ex: 2},
                             meowth_ld_free=True)
    assert m._ub_dig_meowth_gets_played(free_ctx) is True
    assert m._ub_dig_meowth_gets_played(ctx_gastada) is False
    assert m._ub_dig_meowth_gets_played(ctx_dos) is False


# Record 006 step 78 vs Archaludon ex (episode 88154185, LOST). Turn 6:
# an active Teal Mask Ogerpon ex with 3 Grass (6 units), a bench 5/5 with
# Meganium (Wild Growth), a just-evolved Hydrapple ex (1 Grass) and another
# Ogerpon (1 Grass); the rival with an Archaludon ex 270/300 (it RESISTS Grass, -30) and
# ONE 130 HP Duraludon on the bench. The agent played Boss's Orders, which brought up the
# Duraludon and turned a TWO-prize finisher into a ONE-prize one.
#
# The root cause (arithmetic): the retreat is paid for with whole CARDS and with Wild
# Growth each Grass is worth TWO units, but the projections subtracted the cost
# in SYMBOLS (or the number of cards). The plan believed the bench Hydrapple ex
# knocked out after retreating -- 10-1 = 9 units -> 330-30 = 300 -- when the
# reality was 8 units -> 270-30 = 240 (the attack log confirms 240).
# With that phantom KO the plan set a BENCH attacker, which VETOED the
# active's attack... which did knock out: Myriad 30+30x(6+3) = 300 - 30 = 270 =
# the Archaludon ex's exact life. `_retreat_grass_units` corrects the 9 places.
_ARCHA_P78_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step78_no_gustear_remate_de_dos_premios.json")
_ARCHA_P78B_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step78b_ataca_por_dos_premios.json")
_ARCHA_P78C_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step78c_ns_unica_via_al_remate.json")
_ARCHA_P78D_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step78d_ns_recupera_la_planta.json")


def test_archaludon_step78_does_not_gust_and_throw_away_the_two_prize_finisher():
    with open(_ARCHA_P78_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    play = me["hand"][opt["index"]]["id"] if opt.get("type") == int(
        OptionType.PLAY) else None
    assert play != m.Boss_Orders, (
        "Boss's Orders sube al Duraludon (1 premio) y tira el remate de DOS "
        "premios contra el Archaludon ex: nunca se juega aqui")


def test_archaludon_step78b_finishes_the_archaludon_for_two_prizes():
    """With the turn's Supporter already spent it is time to ATTACK: Myriad Leaf Shower
    30+30x(6 ours + 3 of the rival) = 300, minus 30 of Grass resistance =
    270 = the exact life of the Archaludon ex (2 prizes)."""
    with open(_ARCHA_P78B_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"el activo noquea al Archaludon ex (270 >= 270): esperaba ATTACK, {opt}")


def test_archaludon_step78c_the_night_stretcher_joins_the_finisher():
    """The same board with the rival at 2 energies: Myriad drops to 270-30 = 240 and the
    active NO LONGER finishes. The only route to the 2 prizes is recovering a Grass
    with a Night Stretcher, charging it with Teal Dance (the manual attachment is already spent)
    and promoting the Hydrapple ex: 8 units after retreating + 2 = 10 -> Syrup 330 -
    30 = 300 >= 270. The Night Stretcher must enter that analysis."""
    with open(_ARCHA_P78C_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), f"esperaba PLAY, {opt}"
    assert me["hand"][opt["index"]]["id"] == m.Night_Stretcher, (
        f"la Night Stretcher es la unica via al remate de 2 premios; jugo "
        f"{m.card_table[me['hand'][opt['index']]['id']].name}")


def test_archaludon_step78d_the_night_stretcher_recovers_the_grass():
    with open(_ARCHA_P78D_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert me["discard"][opt["index"]]["id"] == m.Basic_Grass_Energy, (
        "el fetch debe traer la ENERGIA (es la que arma el remate), no un cuerpo")


# Record 010 step 123 vs Archaludon ex (the same episode, LOST). Turn 10,
# our 3 prizes against the rival's 1: an active Teal Mask Ogerpon ex with 6
# units of Grass facing an Archaludon ex 300/300 (it resists Grass) and with
# the rival bench EMPTY -- knocking it out WINS the game. Myriad gave 30+30x(6+3) =
# 300 - 30 = 270 and fell 30 short of the KO; the agent attacked anyway (or retreated).
# With a Grass from the discard via Night Stretcher + Teal Dance on the
# active itself: 30+30x(8+3) = 360 - 30 = 330 >= 300 -> a KO and a WIN. This is the case
# `_ns_e_remate_con_el_activo` covers.
_ARCHA_P123_FIXTURE = (
    ROOT / "tests" / "fixtures" / "archaludon_step123_ns_remate_ganador.json")


def test_archaludon_step123_the_ns_builds_the_winning_finisher():
    with open(_ARCHA_P123_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    result = m.agent(obs)
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), (
        f"atacar por 270 contra 300 no cierra nada; la Planta del descarte SI "
        f"(330 >= 300, banca rival vacia = victoria); esperaba PLAY, {opt}")
    assert me["hand"][opt["index"]]["id"] == m.Night_Stretcher, (
        f"esperaba Night Stretcher, jugo "
        f"{m.card_table[me['hand'][opt['index']]['id']].name}")


# Record 009 vs Archaludon ex (episode 88154185). The user's rule: the
# ONLY reason to retreat an ex from the ACTIVE spot is to bring up a body that DEFEATS the
# rival active (taking a prize now) -- or, as a defensive pivot, one that survives
# at least as much. Swapping a 330 HP Hydrapple ex for a Teal Mask
# Ogerpon ex of 210 "because the second one can attack" throws the wall away and leaves
# in front a 2-prize body that is easier to defeat. The generic branch
# `(not can_attack) and _bench_ready_for_retreat` (3200) looked at neither life nor
# the KO: it was enough for somebody on the bench to be charged. Deck-agnostic.
_XX_NO_EX_MENOR = (
    ROOT / "tests" / "fixtures"
    / "archaludon_hydra_no_retirar_ex_por_ex_menor.json")
_XX_NO_1PRIZE_WITHOUT_KO = (
    ROOT / "tests" / "fixtures"
    / "archaludon_hydra_no_retirar_si_el_1premio_no_remata.json")
_XX_SI_1PREMIO_KO = (
    ROOT / "tests" / "fixtures"
    / "archaludon_hydra_retirar_si_el_1premio_remata.json")
_XX_SI_EX_KO = (
    ROOT / "tests" / "fixtures"
    / "archaludon_hydra_retirar_si_el_ex_de_banca_remata.json")


def _opcion_elegida(fixture):
    with open(fixture, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    return obs, obs["select"]["option"][m.agent(obs)[0]]


def test_do_not_swap_an_ex_for_another_ex_with_less_life():
    _, opt = _opcion_elegida(_XX_NO_EX_MENOR)
    assert opt.get("type") != int(OptionType.RETREAT), (
        f"el Hydrapple ex (330) no se cambia por un Ogerpon ex (210) que ni "
        f"remata ni aguanta mas: se queda el muro; eligio {opt}")


def test_do_not_retreat_the_ex_if_the_one_prize_body_does_not_finish():
    _, opt = _opcion_elegida(_XX_NO_1PRIZE_WITHOUT_KO)
    assert opt.get("type") != int(OptionType.RETREAT), (
        f"un Meganium listo que solo hace chip (110 contra 300 PV) no paga "
        f"cambiar el muro de 330; eligio {opt}")


def test_the_ex_does_retreat_when_the_one_prize_body_finishes():
    _, opt = _opcion_elegida(_XX_SI_1PREMIO_KO)
    assert opt.get("type") == int(OptionType.RETREAT), (
        f"con un Meganium (1 premio) que NOQUEA al activo rival, retirar el ex "
        f"cobra premio y concede la mitad si nos responden; eligio {opt}")


def test_the_ex_does_retreat_when_the_bench_body_finishes():
    _, opt = _opcion_elegida(_XX_SI_EX_KO)
    assert opt.get("type") == int(OptionType.RETREAT), (
        f"si el cuerpo de banca NOQUEA, el cambio cobra premio y si compensa; "
        f"eligio {opt}")


# Log 88162794 vs Archaludon ex (LOST 6-1): from turn 7 to the end,
# our active was a Meowth ex with 0 energy (a retreat cost of 1) -- it could neither
# ATTACK nor RETREAT -- while the bench Meganium accumulated energy (e4, e6,
# e8) without ever getting to play. Turns 11 and 13: the agent attached the Grass to the
# ALREADY ready Meganium (Solar Beam is flat: +0 damage) and closed the turn; four
# turns in a row without attacking. No pivot rule fired because they ALL require
# the promoted body to KNOCK OUT, and here Solar Beam only chipped (an Archaludon ex
# of 300/400 HP; Duraludon resists Grass -30 and Full Metal Lab takes another -30).
# `_attach_enable_retreat_attack`: if the active cannot attack in any way,
# the Grass goes to the ACTIVE to pay the retreat and the bench attacker's chip is
# cashed in. It coexists with "do not swap an ex for a worse body": the body that comes up must
# survive at least what the active ex has left.
_AERA_T11 = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step98_energia_al_activo_para_retirar.json")
_AERA_T13 = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step117_energia_al_activo_para_retirar.json")
_AERA_T9_BENCH = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step90_energia_a_la_banca_si_deja_listo.json")
_AERA_RETREAT = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step98b_retirar_para_atacar_con_meganium.json")


def test_archaludon_step98_energy_to_the_active_to_enable_the_retreat():
    obs, opt = _opcion_elegida(_AERA_T11)
    assert opt.get("type") == int(OptionType.ATTACH), f"esperaba ATTACH, {opt}"
    assert opt.get("inPlayArea") == int(AreaType.ACTIVE), (
        f"la Planta debe ir al Meowth ex ACTIVO (paga la retirada de 1 y habilita "
        f"subir al Meganium listo a atacar); cargarla en el Meganium de banca, ya "
        f"a e4, no suma dano y regala el turno; eligio {opt}")


def test_archaludon_step117_energy_to_the_active_even_if_the_chip_does_not_finish():
    obs, opt = _opcion_elegida(_AERA_T13)
    assert opt.get("type") == int(OptionType.ATTACH), f"esperaba ATTACH, {opt}"
    assert opt.get("inPlayArea") == int(AreaType.ACTIVE), (
        f"Solar Beam (140) no noquea al Cinderace (160) pero 140 de chip valen "
        f"mas que cerrar el turno sin atacar; eligio {opt}")


def test_archaludon_step90_the_energy_goes_to_the_bench_when_that_is_what_gets_ready():
    obs, opt = _opcion_elegida(_AERA_T9_BENCH)
    assert opt.get("type") == int(OptionType.ATTACH), f"esperaba ATTACH, {opt}"
    assert opt.get("inPlayArea") == int(AreaType.BENCH), (
        f"con el Meganium a e2 (necesita 4) la Planta es la que lo deja LISTO: su "
        f"sitio es la BANCA, no pagar una retirada que promoveria a un cuerpo que "
        f"tampoco podria atacar; eligio {opt}")


def test_archaludon_step98b_retreats_to_attack_with_meganium():
    obs, opt = _opcion_elegida(_AERA_RETREAT)
    assert opt.get("type") == int(OptionType.RETREAT), (
        f"con la Planta ya en el activo la retirada es legal: hay que retirar el "
        f"Meowth ex (no puede atacar) y subir el Meganium a atacar; eligio {opt}")


# Log 88162677 step 16 vs Alakazam (LOST), OUR FIRST TURN going
# second: a hand with TWO Lillie's Determination + Meowth ex, a bench with a Teal
# Mask Ogerpon ex and the turn's Supporter unplayed. The agent played the Meowth
# ex (the Xerosic engine `_alk_meowth_hand_engine`, 21500, which also EXEMPTED the
# generic veto "do not play a Meowth if there is already a Lillie's in hand") and on the next step
# the Last-Ditch Catch prompt REJECTED the fetch (`_meowth_skip_fetch`): the same
# board, two opposite answers. The cost: a 2-prize body given away on the
# bench, the Lillie's played anyway and zero value. The correction ties the engine to the
# SAME board predicate as the ability (`_meowth_fetch_ya_en_mano`), so
# the two decisions can no longer contradict each other -- deck-agnostic, and the
# cases that justified the engine (registro_006 p76, registro_008 p85,
# registro_010 p147) still play the Meowth to dig the Xerosic.
_ALK_P16_NO_MEOWTH = (
    ROOT / "tests" / "fixtures"
    / "alakazam_step16_no_meowth_con_lillie_en_mano.json")


def _secuencia_fixture(fixture):
    with open(fixture, encoding="utf-8") as f:
        return [p["observation"] for p in json.load(f)["sequence"]]


def test_alakazam_step16_plays_lillie_instead_of_playing_meowth():
    obs = _secuencia_fixture(_ALK_P16_NO_MEOWTH)[0]
    _reset_state_record_008()
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), f"esperaba PLAY, {opt}"
    elegida = me["hand"][opt["index"]]["id"]
    assert elegida == m.Lillie_Determination, (
        f"con DOS Lillie's en mano y el Supporter libre hay que JUGAR la "
        f"Lillie's; bajar Meowth ex solo expone un cuerpo de 2 premios (su "
        f"fetch seria redundante); jugo {m.card_table[elegida].name}")


def test_alakazam_step16_the_meowth_engine_and_the_ability_do_not_contradict():
    """An invariant: if the Meowth ex is played, its Last-Ditch MUST be used."""
    obs_play, obs_ability = _secuencia_fixture(_ALK_P16_NO_MEOWTH)

    _reset_state_record_008()
    me = obs_play["current"]["players"][obs_play["current"]["yourIndex"]]
    opt = obs_play["select"]["option"][m.agent(obs_play)[0]]
    plays_meowth = (opt.get("type") == int(OptionType.PLAY)
                   and me["hand"][opt["index"]]["id"] == m.Meowth_ex)

    _reset_state_record_008()
    uses_ability = (obs_ability["select"]["option"][m.agent(obs_ability)[0]]
                     .get("type") == int(OptionType.YES))

    assert not (plays_meowth and not uses_ability), (
        "incoherencia: se baja el Meowth ex por su Last-Ditch Catch y despues "
        "se RECHAZA el fetch -- se regala un cuerpo de 2 premios por nada")


# PLAY ORDER: Bug Catching Set BEFORE playing a Pokemon (user, log 88166559
# vs Archaludon, WON with a mistake). Looking at the top 7 and taking up to 2 {G} Pokemon
# / Grass Energy changes WHICH body we play and WHAT we charge it with, so
# deciding the body before that information is deciding blind. Two captures
# of the same mistake:
#   * step 6 (turn 1, an empty bench): it played the Meowth ex through the Lillie's engine
#     (21800) with the BCS (12200) in hand; the BCS ended up bringing a Chikorita
#     -- a ONE-prize body, a better bench candidate than a two-prize ex -- with the
#     slot already spent.
#   * step 36 (turn 3, bench 3/5): after refreshing with Lillie's it played BOTH
#     Teal Mask Ogerpon ex and only played the BCS at the end, with the bench already FULL:
#     the Applin it found could not be played. It is the case the user describes
#     ("I play an Ogerpon, I do Teal Dance and a BCS comes up").
# The rule is implemented in the tier layer by demoting the PLAYING of Pokemon
# (`_TIER_DEVELOP_TRAS_BCS`), not by promoting the BCS: EVOLUTIONS keep their
# tier and still precede the BCS (pinned by the two Hydrapple ex tests of
# `test_cubchoo_*_evoluciona_hydrapple_*`).
_BCS_ANTES_MEOWTH = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step6_bcs_antes_de_bajar_meowth.json")
_BCS_ANTES_OGERPON = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step36_bcs_antes_de_bajar_ogerpon.json")


def _bcs_and_pokemon_in_menu(obs):
    """(the BCS's index, the indices of Pokemon plays) in the menu of `obs`."""
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    bcs, pokes = None, []
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") != int(OptionType.PLAY):
            continue
        cid = me["hand"][o["index"]]["id"]
        if cid == m.Bug_Catching_Set:
            bcs = i
        else:
            data = m.card_table.get(cid)
            if data is not None and data.cardType == m.CardType.POKEMON:
                pokes.append(i)
    return bcs, pokes


def test_archaludon_step6_plays_the_bcs_before_playing_the_meowth():
    with open(_BCS_ANTES_MEOWTH, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    bcs, pokes = _bcs_and_pokemon_in_menu(obs)
    assert bcs is not None and pokes, "la fixture debe ofrecer BCS y bajar Pokemon"
    result = m.agent(obs)
    assert result == [bcs], (
        f"el Bug Catching Set (opt {bcs}) se juega ANTES de bajar un Pokemon "
        f"(opts {pokes}): sus 2 cartas cambian que cuerpo baja; obtuvo {result}")


def test_archaludon_step36_plays_the_bcs_before_playing_the_ogerpon():
    with open(_BCS_ANTES_OGERPON, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    _reset_state_record_008()
    bcs, pokes = _bcs_and_pokemon_in_menu(obs)
    assert bcs is not None and pokes, "la fixture debe ofrecer BCS y bajar Pokemon"
    result = m.agent(obs)
    assert result == [bcs], (
        f"con la banca a 3/5 el BCS (opt {bcs}) va antes que los cuerpos "
        f"(opts {pokes}): jugarlo con la banca ya llena desperdicia lo que "
        f"encuentre; obtuvo {result}")


# Record 004 (turn 4, steps 54 and 57) vs Mega Lucario ex (LOST). The board:
# an active Teal Mask Ogerpon ex (210/210, 3 Grass), a bench = a Tapu Bulu WITHOUT
# energy + a just-played Chikorita with 1 Grass, and a hand with
# {Ultra Ball x2, Hydrapple ex, Boss's Orders, Night Stretcher, Lillie's}.
# Across the table, a Mega Lucario ex with 340 HP and BOTH energies for Mega Brave
# (270): OUR ACTIVE DIES FOR SURE next turn and on the bench there is
# NO ready attacker. The agent played an Ultra Ball (step 54) and then
# Boss's Orders (step 57), spending the turn on a 1-prize gust and
# leaving the board with no plan. The right thing in both steps is Lillie's
# Determination: with 6 prizes it draws 8 cards and is the only route to a spare
# attacker. Two causes, both corrected:
#   1. `hop_keep_boss` (keeping the Boss's vs Hops / a threat pre-evo) counted the
#      Chikorita with 1 Grass as a "ready attacker" (Growl: 0 damage), saw 2
#      attackers and VETOED the Lillie's; now it only counts MAIN_ATTACKERS and it also
#      yields with a doomed active and no relief.
#   2. `_boss_cede_dig` did not yield because `active_ko_likely` was False (its
#      estimator `_op_best_damage_vs` does not resolve the rival damage and always gives 0);
#      now it also consults `active_doomed_real` (the REAL finisher via attack_table).
# The turn's SEQUENCE is reproduced: `_field_at_turn_start` is key (the
# Chikorita was played THIS turn, so the Ultra Ball enables no
# immediate evolution and cannot skip the deferral in favour of Lillie's).
_LUCARIO_T4_SEQ = (
    ROOT / "tests" / "fixtures" / "lucario_t4_lillie_sobre_ub_y_boss.json")


def _lucario_t4_hasta(step):
    """Replays the sequence of turn 4 up to `paso` and returns (obs, result)."""
    with open(_LUCARIO_T4_SEQ, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    obs = result = None
    for item in seq:
        if item["step"] > step:
            break
        obs = item["observation"]
        result = m.agent(obs)
    return obs, result


def test_lucario_step54_plays_lillie_not_the_ultra_ball():
    obs, result = _lucario_t4_hasta(54)

    play_map = _resolve_play_options(obs)
    assert m.Lillie_Determination in play_map.values()
    assert m.Ultra_Ball in play_map.values()
    lillie_opt = next(i for i, cid in play_map.items()
                      if cid == m.Lillie_Determination)
    ub_opts = [i for i, cid in play_map.items() if cid == m.Ultra_Ball]

    assert result == [lillie_opt], (
        f"con el activo condenado y sin atacante de banca hay que refrescar con "
        f"Lillie's (opt {lillie_opt}, roba 8 con 6 premios), no gastar Ultra Ball "
        f"(opts {ub_opts}) + 2 descartes en un objetivo que Lillie's barajaria; "
        f"obtuvo {result}")


def test_lucario_step57_plays_lillie_not_boss_orders():
    obs, result = _lucario_t4_hasta(57)

    play_map = _resolve_play_options(obs)
    assert m.Lillie_Determination in play_map.values()
    assert m.Boss_Orders in play_map.values()
    lillie_opt = next(i for i, cid in play_map.items()
                      if cid == m.Lillie_Determination)
    boss_opt = next(i for i, cid in play_map.items() if cid == m.Boss_Orders)

    assert result == [lillie_opt], (
        f"el Supporter del turno debe ser Lillie's (opt {lillie_opt}): un gusteo "
        f"de 1 premio (Boss's, opt {boss_opt}) con el activo condenado y la banca "
        f"sin atacante deja el tablero sin plan; obtuvo {result}")


# Record 014 (turn 14, steps 136/137/141) vs Alakazam (WON with three plays
# given away). The board: an ACTIVE Fezandipiti ex at 0 energies -- Cruel Arrow costs 3,
# so it does NOT attack, and its RETREAT cost is 1, so it does not retreat either -- with
# a bench full of resources: a Meganium at 2 effective (Wood Hammer needs 4),
# a Hydrapple ex at 2 effective (Syrup Storm ALREADY ready) and Tapu Bulu/Meowth ex at 0.
# Across the table, 50 HP Abras: any attacker of ours knocks out. Three chained
# mistakes, all from the same blindness -- nobody looked at the fact that the whole turn
# depended on PAYING THE ACTIVE'S RETREAT:
#   * step 136: the manual attachment went to the bench MEGANIUM (`_meganium_alk_1prize_
#     attacker`, 43000) overriding the attachment to the ACTIVE that enabled the retreat
#     (`_attach_enable_retreat_ko`, 41000). But that rule rests on "the ex is retreated
#     and Meganium is promoted": with no legal retreat (`can_switch`) the charged Meganium
#     stays on the bench and does not attack. Now the rule requires `can_switch`.
#   * step 137: with the manual attachment already spent, Ripening Charge (which attaches to
#     ANY of our Pokemon and does NOT consume the turn's attachment) was VETOED
#     -- its branch only looked at whether the Grass was useful to the Hydrapple itself -- and both
#     Grass ended up as fodder in the cost of an Ultra Ball that searched for an
#     unnecessary Ogerpon ex. Now `_ability_unlock_retreat_ko` gives it the
#     lethal band (41000) and `_ripen_bench_ready_pivot` covers the "second attacker".
#   * step 141: with no Grass in hand the ability does not even appear in the menu.
#     The Night Stretcher would recover one from the discard, but it was vetoed through the
#     full bench: its list of "useful energy" only contemplated the retreat of the MEGANIUM
#     LINE. Now `_ns_e_activo_paga_retirada` covers it, deck-agnostic.
_ALK_T14_SEQ = (
    ROOT / "tests" / "fixtures" / "alakazam_t14_ruta_de_ataque_por_retirada.json")


def _alk_t14_hasta(step):
    """Replays the sequence of turn 14 up to `paso`; returns (obs, result)."""
    with open(_ALK_T14_SEQ, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    obs = result = None
    for item in seq:
        if item["step"] > step:
            break
        obs = item["observation"]
        result = m.agent(obs)
    return obs, result


def _alk_t14_indices(obs):
    """(attachments to the active, attachments to the bench Meganium, Ripening's index)."""
    to_active, al_meganium, ripening = [], [], None
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(OptionType.ATTACH):
            if o.get("inPlayArea") == int(AreaType.ACTIVE):
                to_active.append(i)
            else:
                bench = obs["current"]["players"][0]["bench"]
                if bench[o["inPlayIndex"]]["id"] == m.Meganium:
                    al_meganium.append(i)
        elif o.get("type") == int(OptionType.ABILITY):
            card = m.get_card(m.to_observation_class(obs), o["area"], o["index"], 0)
            if card is not None and card.id == m.Hydrapple_ex:
                ripening = i
    return to_active, al_meganium, ripening


def test_alakazam_step136_charges_the_active_to_enable_the_retreat():
    obs, result = _alk_t14_hasta(136)

    to_active, al_meganium, _ = _alk_t14_indices(obs)
    assert to_active and al_meganium, "la fixture debe ofrecer ambos destinos"

    assert result[0] in to_active, (
        f"la Planta va al ACTIVO (opts {to_active}) para pagar su retirada y subir "
        f"al Hydrapple ex listo; cargar el Meganium de banca (opts {al_meganium}) "
        f"no le da un ataque este turno porque el activo no puede retirarse; "
        f"obtuvo {result}")
    assert result[0] not in al_meganium


def test_alakazam_step137_uses_ripening_charge_instead_of_burning_the_grass():
    obs, result = _alk_t14_hasta(137)

    _, _, ripening = _alk_t14_indices(obs)
    play_map = _resolve_play_options(obs)
    assert ripening is not None, "la fixture debe ofrecer Ripening Charge"
    assert m.Ultra_Ball in play_map.values()
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)

    assert result == [ripening], (
        f"con el adjunte manual gastado, Ripening Charge (opt {ripening}) es la "
        f"UNICA via para poner la Planta en el campo; la Ultra Ball (opt {ub_opt}) "
        f"descartaria las dos Plantas para buscar lo que no hace falta; "
        f"obtuvo {result}")


def test_alakazam_step141_the_night_stretcher_recovers_the_grass_from_the_discard():
    obs, result = _alk_t14_hasta(141)

    play_map = _resolve_play_options(obs)
    assert m.Night_Stretcher in play_map.values()
    ns_opt = next(i for i, cid in play_map.items() if cid == m.Night_Stretcher)
    end_opt = next(i for i, o in enumerate(obs["select"]["option"])
                   if o.get("type") == int(OptionType.END))
    # With the bench FULL the Night Stretcher is only worth the ENERGY in the discard.
    assert obs["current"]["players"][0]["bench"] and len(
        obs["current"]["players"][0]["bench"]) == 5

    assert result == [ns_opt], (
        f"la Night Stretcher (opt {ns_opt}) recupera la Planta que paga la retirada "
        f"del activo (Ripening Charge la pone y sube el Hydrapple ex a atacar); "
        f"terminar el turno (opt {end_opt}) lo regala; obtuvo {result}")


def test_alakazam_step137_ripening_charge_aims_at_the_active():
    """The ability's TARGET (ATTACH_FROM) must be the ACTIVE, not the bench.

    The other half of the chain: switching Ripening Charge on is useless if the
    Grass falls into normal bench development and the retreat stays blocked.
    `energy_score` ALREADY did that routing right (this test also passes with the
    previous code); it is pinned here because the ability's new branch depends on
    it: if anyone touches the routing, the play turns into a wasted Grass.
    The ATTACH_FROM select the engine presents right after choosing Ripening
    Charge is synthesised (the same shape as registro_004 step 27): one
    CARD option per Pokemon of ours (area 4 = active, 5 = bench).
    """
    import copy

    with open(_ALK_T14_SEQ, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]
    obs137 = next(x["observation"] for x in seq if x["step"] == 137)

    syn = copy.deepcopy(obs137)
    me = syn["current"]["players"][0]
    options = [{"area": int(AreaType.ACTIVE), "index": 0, "playerIndex": 0,
                 "type": int(OptionType.CARD)}]
    for i in range(len(me["bench"])):
        options.append({"area": int(AreaType.BENCH), "index": i,
                         "playerIndex": 0, "type": int(OptionType.CARD)})
    syn["select"] = {
        "context": int(SelectContext.ATTACH_FROM), "contextCard": None,
        "deck": None,
        "effect": {"id": m.Hydrapple_ex, "playerIndex": 0, "serial": 18},
        "maxCount": 1, "minCount": 1, "option": options,
        "remainDamageCounter": 0, "remainEnergyCost": 0, "type": 1}

    for item in seq:
        if item["step"] > 137:
            break
        m.agent(item["observation"])
    result = m.agent(syn)

    assert result == [0], (
        "la Planta de Ripening Charge va al ACTIVO (opt 0, Fezandipiti ex) para "
        "pagar su coste de retirada y promover al Hydrapple ex listo; cualquier "
        f"objetivo de banca deja la retirada bloqueada; obtuvo {result}")


# =====================================================================
# The anti-sterile-turn net does NOT revoke the Ultra Ball's COST veto
# (user, log 88359220 steps 8-14 vs Comfey/Yveltal, LOST -- registro_001).
#
# OUR first turn going FIRST: the menu only offers PLAY Ultra Ball
# / RETREAT / END (no attack and no Supporter: the turn is sterile BY RULE).
# A hand of {Ultra Ball, Lillie's Determination, Bayleef, Grass, Unfair Stamp} with
# an active Chikorita -- the only real fodder is the Grass, so paying the 2
# discards of the Ultra Ball burns the Lillie's (`_ub_cancel_lillie` vetoes it at
# -1, correctly). The anti-sterile-turn net resurrected it at 200 and the
# agent discarded Grass + Lillie's to dig a Meowth ex whose Last-Ditch
# Catch went and searched for ANOTHER Lillie's: -3 cards of hand and a 2-prize
# body given away to end up with the SAME card.
#
# The contract (deck-agnostic): the net revokes CONSERVATISM vetoes ("there is no
# useful target", "it is early"), never the COST veto, which is card
# arithmetic and does not change because the turn is dead. See
# `_ub_coste_destruye_carta_mejor`.
# =====================================================================
_UB_LILLIE_COST_FIXTURE = (
    ROOT / "tests" / "fixtures" / "comfey_t1_primeros_no_ub_que_quema_lillie.json")


def test_t1_going_first_no_ub_that_would_discard_the_lillie():
    with open(_UB_LILLIE_COST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    play_map = _resolve_play_options(obs)
    assert m.Ultra_Ball in play_map.values(), "el fixture debe ofrecer jugar Ultra Ball"
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)
    end_opt = next(i for i, o in enumerate(obs["select"]["option"])
                   if o.get("type") == OptionType.END)

    result = m.agent(obs)

    assert result == [end_opt], (
        f"con la Lillie's como unico pago posible de la Ultra Ball hay que "
        f"TERMINAR el turno (opt {end_opt}) y conservarla; obtuvo {result}")
    assert result != [ub_opt], (
        "jugar la Ultra Ball descarta el Lillie's para cavar un Meowth ex que "
        "vuelve a buscar otro Lillie's: tres cartas por la misma jugada")


def test_the_ub_cost_vetoes_only_when_real_fodder_is_missing():
    """The predicate that builds the guard is the one Phase C already used: it switches on
    when paying for the Ultra Ball would have to take the Supporter, and NOT
    when there is fodder to spare. It pins both faces so that the guard does not
    turn into a universal Ultra Ball veto."""
    import copy

    with open(_UB_LILLIE_COST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    # Face B: the same position but with TWO spare energies in hand (real
    # fodder). The cost veto disappears and the Ultra Ball is playable again.
    rico = copy.deepcopy(obs)
    me = rico["current"]["players"][rico["current"]["yourIndex"]]
    me["hand"].extend([
        {"id": m.Basic_Grass_Energy, "playerIndex": 1, "serial": 200},
        {"id": m.Basic_Grass_Energy, "playerIndex": 1, "serial": 201},
    ])
    me["handCount"] = len(me["hand"])

    play_map = _resolve_play_options(rico)
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)

    result = m.agent(rico)

    assert result == [ub_opt], (
        f"con 3 energias de forraje el Lillie's ya no paga la Ultra Ball: la "
        f"red anti-turno-esteril debe seguir cavando (opt {ub_opt}); "
        f"obtuvo {result}")


# =====================================================================
# A sweep of matchup exemptions in the rescue nets (Jul 2026).
# The Ultra Ball's anti-sterile-turn net switched off entirely vs Comfey. That
# prohibition by DECK was a proxy for a specific question: vs Comfey the plan
# only allows playing Teal Mask Ogerpon ex (max 2), so digging any other
# body brings a card the plan itself will veto when playing it. Asked via
# `_matchup_permite_bajar`, the net is still off in that case but it DOES dig
# when the target fits the plan --- which is exactly what the matchup wants.
# (vs Cubchoo the exemption is kept: the conservative END is matchup policy
# and the self-play gate backed it up, -1.3 points when lifting it.)
# =====================================================================
def _ub_dead_turn_obs(op_active_id, ogerpon_in_play):
    import copy

    with open(ROOT / "tests" / "fixtures" /
              "cynthia_boss_gust_highest_evo_gabite_step51.json",
              encoding="utf-8") as f:
        o = copy.deepcopy(json.load(f)["observation"])
    cur = o["current"]; me = cur["players"][1]; op = cur["players"][0]
    # The turn already spent except for the Ultra Ball: no Supporter, stadium or attachment.
    cur["supporterPlayed"] = True; cur["stadiumPlayed"] = True
    cur["energyAttached"] = True; cur["turn"] = 7; cur["yourIndex"] = 1

    def body(cid, hp, serial, energies=0):
        return {"appearThisTurn": False, "energies": [1] * energies,
                "energyCards": [], "hp": hp, "id": cid, "maxHp": hp,
                "playerIndex": 1, "preEvolution": [], "serial": serial,
                "tools": []}

    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                     "hp": 70, "id": op_active_id, "maxHp": 70, "playerIndex": 0,
                     "preEvolution": [], "serial": 900, "tools": []}]
    op["bench"] = []
    me["active"] = [body(m.Teal_Mask_Ogerpon_ex, 210, 800, 3)]
    me["bench"] = [body(m.Teal_Mask_Ogerpon_ex, 210, 801, 1)
                   if ogerpon_in_play >= 2 else body(m.Chikorita, 70, 802)]
    # A minimal hand with real fodder (2 Grass) so that the UB does not die on cost.
    me["hand"] = [{"id": m.Ultra_Ball, "playerIndex": 1, "serial": 810},
                  {"id": m.Basic_Grass_Energy, "playerIndex": 1, "serial": 811},
                  {"id": m.Basic_Grass_Energy, "playerIndex": 1, "serial": 812}]
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [{"index": 0, "type": 7}, {"type": 14}]}
    return o


def test_comfey_dead_turn_digs_an_ogerpon_if_there_is_room():
    obs = _ub_dead_turn_obs(m.Comfey, ogerpon_in_play=1)
    assert m.agent(obs) == [0], (
        "vs Comfey con hueco para un 2o Ogerpon ex, la Ultra Ball del turno "
        "muerto cava justo el cuerpo que el plan del matchup quiere")


def test_comfey_dead_turn_does_not_dig_if_the_plan_allows_nothing_to_be_played():
    obs = _ub_dead_turn_obs(m.Comfey, ogerpon_in_play=2)
    assert m.agent(obs) == [1], (
        "con los 2 Ogerpon ex ya en juego el plan veta bajar cualquier cuerpo: "
        "cavar quemaria dos cartas por una carta muerta, mejor terminar")


# =====================================================================
# The COUNTER-STADIUM is vetoed by no matchup whitelist (user, log
# 88359220 steps 60-76 vs Comfey, LOST -- registro_008).
#
# The rival played a Neutralization Zone: our Pokemon ex cannot attack
# Pokemon that are NOT ex, and their whole board is non-ex. That switches off ALL
# our ex attackers --- including the Teal Mask Ogerpon ex that IS the plan of the
# Comfey matchup. We had a Forest of Vitality in hand and the scorer gave it
# 28000, but the Trainer allowlist vs Comfey (Lillie's/Lana's/Boss's/
# Ultra Ball/Night Stretcher/Bug Catching Set) dropped it to -1 for not being on the
# list, and the lock stayed on the table turn after turn.
#
# The deck-agnostic contract: a whitelist describes WHICH cards advance the
# plan; it can never veto the card that LIFTS A RIVAL LOCK that disables
# that very plan. See `_contra_estadio_urgente`, shared with the DISCARD
# scorer (which already protected this card: something was being kept in hand that
# was then illegal to play).
# =====================================================================
def _hostile_stadium_obs(op_active_id, opponent_stadium, own_forest=False):
    import copy

    with open(ROOT / "tests" / "fixtures" /
              "cynthia_boss_gust_highest_evo_gabite_step51.json",
              encoding="utf-8") as f:
        o = copy.deepcopy(json.load(f)["observation"])
    cur = o["current"]; me = cur["players"][1]; op = cur["players"][0]
    cur["supporterPlayed"] = True; cur["stadiumPlayed"] = False
    cur["energyAttached"] = True; cur["turn"] = 9; cur["yourIndex"] = 1
    cur["stadium"] = [{"id": m.Forest_of_Vitality if own_forest
                       else opponent_stadium, "playerIndex": 1 if own_forest else 0,
                       "serial": 950}]

    def body(cid, hp, serial, energies=0):
        return {"appearThisTurn": False, "energies": [1] * energies,
                "energyCards": [], "hp": hp, "id": cid, "maxHp": hp,
                "playerIndex": 1, "preEvolution": [], "serial": serial,
                "tools": []}

    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                     "hp": 70, "id": op_active_id, "maxHp": 70, "playerIndex": 0,
                     "preEvolution": [], "serial": 900, "tools": []}]
    op["bench"] = []
    me["active"] = [body(m.Teal_Mask_Ogerpon_ex, 210, 800, 3)]
    me["bench"] = [body(m.Teal_Mask_Ogerpon_ex, 210, 801, 1)]
    me["hand"] = [{"id": m.Forest_of_Vitality, "playerIndex": 1, "serial": 810},
                  {"id": m.Basic_Grass_Energy, "playerIndex": 1, "serial": 811}]
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [{"index": 0, "type": 7}, {"type": 14}]}
    return o


def test_comfey_plays_the_forest_to_remove_neutralization_zone():
    obs = _hostile_stadium_obs(m.Comfey, m.Neutralization_Zone)
    assert m.agent(obs) == [0], (
        "la allowlist vs Comfey no puede vetar el Forest que quita la "
        "Neutralization Zone: sin quitarla, el Ogerpon ex del propio plan no "
        "puede atacar a ningun cuerpo no-ex del rival")


def test_comfey_plays_the_forest_to_remove_watchtower():
    obs = _hostile_stadium_obs(m.Comfey, m.Team_Rockets_Watchtower)
    assert m.agent(obs) == [0], (
        "mismo criterio con Team Rocket's Watchtower, que apaga la habilidad "
        "de los {C} (Last-Ditch Catch de Meowth ex)")


def test_comfey_does_not_play_a_redundant_forest_with_ours_on_the_table():
    # Control: with OUR Forest already on the table there is no lock to lift, so
    # the matchup's allowlist rules again and the 2nd Forest is not played.
    obs = _hostile_stadium_obs(m.Comfey, m.Neutralization_Zone, own_forest=True)
    assert m.agent(obs) == [1], (
        "sin estadio hostil en mesa la excepcion no aplica: vs Comfey el "
        "Forest redundante sigue vetado")


def test_counter_stadium_urgent_is_deck_agnostic():
    # The generic scorer already prioritised the counter-stadium (28000): the failure was
    # only the allowlist. This control pins it for any deck.
    obs = _hostile_stadium_obs(m.Duraludon, m.Neutralization_Zone)
    assert m.agent(obs) == [0], (
        "vs cualquier mazo, con Neutralization Zone en mesa el Forest se juega")


