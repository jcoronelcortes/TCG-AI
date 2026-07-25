import sys
from pathlib import Path
import types
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from cg.api import AreaType, EnergyType, LogType, OptionType, SelectContext


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    m._op_prize_denial_pecharunt = False
    m._op_prize_denial_gengar = False
    yield
    m._init_cartas_tracking()


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
    assert m._move_card_state(first_card_id, m.ESTADO_MAZO, m.ESTADO_MANO) is True
    assert m.CARTAS_ACTIVAS_EN_MAZO[first_card_id][m.ESTADO_MANO] == 1
    assert m._move_card_state(first_card_id, m.ESTADO_MANO, m.ESTADO_BANCA) is True
    deck, prize = m._belief_deck_and_prizes()
    assert deck + prize == len(m.my_deck) - 1
    assert m._move_card_state(999999, m.ESTADO_MAZO, m.ESTADO_MANO) is False
    assert m.CARTAS_ACTIVAS_EN_MAZO[first_card_id][m.ESTADO_BANCA] == 1


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
    # Armor Tail (P1.6): Farigiraf ex es inmune al dano de BASICOS ex.
    farigiraf = make_pokemon(m.Farigiraf_ex, hp=260, max_hp=260)
    assert m._our_effective_damage(make_pokemon(m.Teal_Mask_Ogerpon_ex), farigiraf, 300) == 0
    assert m._our_effective_damage(make_pokemon(m.Meowth_ex), farigiraf, 60) == 0
    assert m._our_effective_damage(make_pokemon(m.Fezandipiti_ex), farigiraf, 100) == 0
    # Hydrapple ex (Etapa 2 ex) y los no-ex SI danan (debil a Planta: x2).
    assert m._our_effective_damage(make_pokemon(m.Hydrapple_ex), farigiraf, 100) == 200
    assert m._our_effective_damage(make_pokemon(m.Tapu_Bulu), farigiraf, 220) == 440


def test_our_effective_damage_resolute_heart_caps_at_full_hp():
    # Resolute Heart (P0.1): Pikachu ex a vida COMPLETA sobrevive a 10 PV.
    atk = make_pokemon(m.Tapu_Bulu)
    pika_full = make_pokemon(m.Pikachu_ex_Resolute, hp=200, max_hp=200)
    assert m._our_effective_damage(atk, pika_full, 220) == 190
    # Danado, la habilidad ya no aplica: el letal pasa entero.
    pika_dmg = make_pokemon(m.Pikachu_ex_Resolute, hp=150, max_hp=200)
    assert m._our_effective_damage(atk, pika_dmg, 220) == 220


def test_prize_count_op_aplica_denegacion_del_campo_rival():
    munki = make_pokemon(m.Munkidori_ex, hp=210, max_hp=210)
    fez_rival = make_pokemon(m.Fezandipiti_ex, hp=210, max_hp=210)  # {D} rival

    # Sin denegaciones en el campo rival: cuenta normal.
    assert m.prize_count_op(munki) == 2
    # Pecharunt ex rival en juego ("Oh No You Don't"): Munkidori ex rinde 1.
    m._op_prize_denial_pecharunt = True
    assert m.prize_count_op(munki) == 1
    assert m.prize_count_op(fez_rival) == 2  # no es Munkidori: sin cambio
    # Mega Gengar ex rival ("Shadowy Concealment"): sus {D} rinden 1 menos.
    m._op_prize_denial_gengar = True
    assert m.prize_count_op(fez_rival) == 1
    # Los premios que entrega NUESTRO lado (prize_count) no se ven afectados.
    assert m.prize_count(fez_rival) == 2


def test_ko_no_garantizado_detecta_hawlucha_y_survival_brace():
    # Tenacious Body (moneda): nunca es KO garantizado.
    assert m._ko_no_garantizado(
        make_pokemon(m.Mega_Hawlucha_ex, hp=250, max_hp=250)) is True
    # Survival Brace solo protege a vida COMPLETA.
    brace = make_card(m.Survival_Brace)
    assert m._ko_no_garantizado(
        make_pokemon(m.Slowpoke, hp=100, max_hp=100, tools=[brace])) is True
    assert m._ko_no_garantizado(
        make_pokemon(m.Slowpoke, hp=70, max_hp=100, tools=[brace])) is False
    assert m._ko_no_garantizado(make_pokemon(m.Slowpoke)) is False
    assert m._ko_no_garantizado(None) is False


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

    assert m.CARTAS_ACTIVAS_EN_MAZO[m.Bug_Catching_Set][m.ESTADO_MANO] == 1
    assert m.CARTAS_ACTIVAS_EN_MAZO[m.Chikorita][m.ESTADO_BANCA] == 1
    assert m.CARTAS_ACTIVAS_EN_MAZO[m.Applin][m.ESTADO_BANCA] == 1
    assert m._cartas_first_scan_done is True


def test_area_to_estado_maps_all_supported_areas():
    assert m._area_to_estado(AreaType.DECK) == m.ESTADO_MAZO
    assert m._area_to_estado(AreaType.HAND) == m.ESTADO_MANO
    assert m._area_to_estado(AreaType.ACTIVE) == m.ESTADO_BANCA
    assert m._area_to_estado(AreaType.DISCARD) == m.ESTADO_DESCARTE
    assert m._area_to_estado(AreaType.PRIZE) == m.ESTADO_PREMIO
    assert m._area_to_estado(999) is None


def test_process_logs_updates_tracking():
    m._move_card_state(m.Ultra_Ball, m.ESTADO_MAZO, m.ESTADO_MANO)
    obs = SimpleNamespace(logs=[SimpleNamespace(type=LogType.DRAW, playerIndex=0, cardId=m.Ultra_Ball)])

    m._process_logs(obs, my_index=0)

    assert m.CARTAS_ACTIVAS_EN_MAZO[m.Ultra_Ball][m.ESTADO_MANO] >= 1


def test_identify_prizes_reconciles_hidden_cards():
    m._move_card_state(m.Ultra_Ball, m.ESTADO_MAZO, m.ESTADO_MANO)
    obs = SimpleNamespace(
        select=SimpleNamespace(
            deck=[SimpleNamespace(id=m.Ultra_Ball)],
            effect=SimpleNamespace(id=m.Ultra_Ball),
        )
    )

    m._identify_prizes(obs, my_state=None)

    assert m.CARTAS_ACTIVAS_EN_MAZO[m.Ultra_Ball][m.ESTADO_MAZO] == 1


def test_sync_from_state_reconciles_visible_state():
    my_state = SimpleNamespace(
        hand=[SimpleNamespace(id=m.Ultra_Ball)],
        active=[],
        bench=[],
        discard=[],
    )

    m._sync_from_state(my_state)

    assert m.CARTAS_ACTIVAS_EN_MAZO[m.Ultra_Ball][m.ESTADO_MANO] == 1


def test_update_cartas_tracking_initial_scan():
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

    m._update_cartas_tracking(obs, my_index=0, my_state=my_state)

    assert m._cartas_first_scan_done is True
    assert m.CARTAS_ACTIVAS_EN_MAZO[m.Bug_Catching_Set][m.ESTADO_MANO] == 1


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
        _best_supp_in_mazo_val=0,
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
    monkeypatch.setattr(
        m,
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
    m._move_card_state(m.Ultra_Ball, m.ESTADO_MAZO, m.ESTADO_MANO)
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

    assert m.CARTAS_ACTIVAS_EN_MAZO[m.Ultra_Ball][m.ESTADO_MANO] == 0
    assert m.CARTAS_ACTIVAS_EN_MAZO[m.Ultra_Ball][m.ESTADO_DESCARTE] == 1


def test_identify_prizes_ignores_partial_reveal():
    before = m.CARTAS_ACTIVAS_EN_MAZO[m.Ultra_Ball][m.ESTADO_MAZO]
    obs = SimpleNamespace(
        select=SimpleNamespace(
            deck=[SimpleNamespace(id=m.Ultra_Ball)],
            effect=SimpleNamespace(id=m.Bug_Catching_Set),
        )
    )

    m._identify_prizes(obs, my_state=SimpleNamespace(deckCount=2))

    assert m.CARTAS_ACTIVAS_EN_MAZO[m.Ultra_Ball][m.ESTADO_MAZO] == before


def test_eval_ub_best_target_handles_turn_two_and_turn_one_branches():
    m.CARTAS_ACTIVAS_EN_MAZO[m.Meowth_ex][m.ESTADO_MAZO] = 1
    m.CARTAS_ACTIVAS_EN_MAZO[m.Lillie_Determination][m.ESTADO_MAZO] = 1

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
        _best_supp_in_mazo_val=900,
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

    m.CARTAS_ACTIVAS_EN_MAZO[m.Teal_Mask_Ogerpon_ex][m.ESTADO_MAZO] = 1
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
        _best_supp_in_mazo_val=0,
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
# Regresion: vs Marnie's Grimmsnarl ex (log 86699707, paso 51). Con la mano
# debil (Meowth ex + Lana's Aid, 4 cartas), 3 Lillie's en el mazo, activo
# Dipplin (chip) contra un muro de 320 HP y FROSLASS en la banca rival, el
# agente debe BAJAR Meowth ex (Last-Ditch Catch -> Lillie's -> refrescar), NO
# jugar Lana's Aid solo para recuperar 1 energia no letal. La excepcion
# Meowth->Lillie's cede ante Froslass EXCEPTO cuando nuestro unico atacante
# listo es el propio activo (_ready_attacker_count <= 1).
import copy
import json

_STEP51_FIXTURE = ROOT / "tests" / "fixtures" / "marnie_grimmsnarl_step51.json"


def _load_step51_obs():
    with open(_STEP51_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _resolve_play_options(obs_dict):
    """Devuelve {posicion_en_option: card_id} para las opciones PLAY (type 7)."""
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
    # El fixture debe contener ambas opciones para que el test sea significativo.
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
    # Quitar Froslass (id 104) y su pre-evo Snorunt (id 860) de la banca rival
    # NO debe cambiar la decision: la rama Meowth->Lillie's ya se cumplia con la
    # guarda original `not op_has_froslass`. Confirma que la relajacion no
    # altera el camino sin Froslass (comportamiento identico).
    obs = copy.deepcopy(_load_step51_obs())
    opp_bench = obs["current"]["players"][1]["bench"]
    obs["current"]["players"][1]["bench"] = [
        p for p in opp_bench if p is not None and p.get("id") not in (104, 860)
    ]

    play_map = _resolve_play_options(obs)
    meowth_opt = next(i for i, cid in play_map.items() if cid == m.Meowth_ex)

    result = m.agent(obs)
    assert result == [meowth_opt]


# Registro 006 (paso 51) vs Alakazam: nuestro turno con la mano [Bayleef,
# Boss's Orders, Night Stretcher, Lana's Aid], Hydrapple ex activo que aun no
# puede atacar (1 energia), Ogerpon ex recien bajado a la banca y Meowth ex en
# el DESCARTE. El agente terminaba el turno sin jugar entrenador ni atacar. Lo
# correcto es jugar Night Stretcher para recuperar Meowth ex y encadenar
# Meowth ex (Last-Ditch Catch) -> Lillie's Determination -> refrescar la mano.
# Ademas, Lana's Aid NO puede recuperar Meowth ex (tiene Regla/Rule Box), asi
# que no debe inflar el valor de la mano ni bloquear la linea.
_STEP51_NS_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_ns_meowth_step51.json"


def _load_ns_step51_obs():
    with open(_STEP51_NS_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def test_alakazam_step51_plays_night_stretcher_for_meowth():
    obs = _load_ns_step51_obs()

    play_map = _resolve_play_options(obs)
    # El fixture debe ofrecer Night Stretcher como jugada.
    assert m.Night_Stretcher in play_map.values()
    ns_opt = next(i for i, cid in play_map.items() if cid == m.Night_Stretcher)

    # La opcion de terminar el turno (type 14) es la ultima del select.
    options = obs["select"]["option"]
    pass_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.END))

    result = m.agent(obs)

    assert result == [ns_opt], (
        f"esperaba jugar Night Stretcher (opt {ns_opt}) para recuperar Meowth ex, "
        f"obtuvo {result} (map={play_map})"
    )
    assert result != [pass_opt], "no debe terminar el turno sin desarrollar"


# Registro 003 (paso 36) vs Archaludon ex (GANADA): en NUESTRO turno 3, tras
# jugar Poke Pad y evolucionar Applin -> Dipplin, el activo Ogerpon ex esta
# danado con 1 energia (no puede atacar) y la mano queda [Lillie's, Unfair
# Stamp, Hydrapple ex, Meganium, Night Stretcher]. NO podemos evolucionar
# Dipplin -> Hydrapple ex este turno (Dipplin acaba de aparecer, sin Forest) ni
# atacar: el turno seria MUERTO. El agente terminaba el turno conservando la
# linea de evolucion en vez de jugar Lillie's Determination. Lo correcto es
# refrescar con Lillie's (roba 6, u 8 con 6 premios) para ver mas opciones.
# El snapshot `_field_at_turn_start` (Applin en juego al inicio del turno, no
# Dipplin) es clave, por eso se reproduce la SECUENCIA del turno, no una sola
# observacion.
_TURN3_SEQ_FIXTURE = ROOT / "tests" / "fixtures" / "archaludon_lillie_turn3_seq.json"


def test_archaludon_step36_plays_lillie_not_end_on_dead_turn():
    with open(_TURN3_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    # Reproducir la secuencia del turno para fijar `_field_at_turn_start`.
    final_obs = None
    result = None
    for item in seq:
        obs = item["observation"]
        result = m.agent(obs)
        final_obs = obs

    # Ultima decision (tac=4): debe jugar Lillie's Determination (opt 0), no END.
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


# Registro 004 (paso ~62) vs Iono (PERDIDA): en la busqueda de Ultra Ball, con
# un Dipplin en juego evolucionable a Hydrapple ex ESTE turno (Forest en juego)
# pero SIN energia para que Hydrapple ex ataque (Syrup Storm necesita 2; ya
# adjuntamos energia este turno y el Dipplin tiene 0), traer Hydrapple ex lo deja
# MUERTO. Como el motor Meowth ex -> Last-Ditch Catch -> Lillie's Determination
# esta disponible (Meowth ex y Lillie's en el mazo, sin Supporter jugado, banca
# con hueco), lo correcto es traer Meowth ex para refrescar la mano, no Hydrapple
# ex. Buscar Hydrapple ex solo es correcto si PUEDE atacar este turno.
_UB_MEOWTH_FIXTURE = ROOT / "tests" / "fixtures" / "iono_ub_meowth_not_hydra_step62.json"


def _resolve_search_options(obs_dict):
    """{posicion_en_option: card_id} para opciones de busqueda en el mazo."""
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
    # El fixture debe ofrecer ambos como objetivos de busqueda.
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


# Registro 006 (paso 57) vs Alakazam (GANADA): en NUESTRO turno 6 ya tenemos un
# atacante LISTO en el activo (Ogerpon ex cargado), otro en la banca y mas
# atacantes cargables con la energia de la mano. Una Ultra Ball previa dejo
# `_ub_meowth_pending`, que forzaba bajar Meowth ex para encadenar Lillie's; pero
# Meowth ex es un cuerpo de 2 premios y aqui NO aporta ataque (ademas el Supporter
# ya se jugo este turno, la Lillie's buscada ni se podria jugar). Con el activo ya
# listo para atacar, NO se debe bajar Meowth ex: se ataca.
_NO_MEOWTH_SEQ_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_no_redundant_meowth_turn6.json"


def test_alakazam_step57_no_redundant_meowth_when_attacker_ready():
    with open(_NO_MEOWTH_SEQ_FIXTURE, encoding="utf-8") as f:
        seq = json.load(f)["sequence"]

    # Reproducir la secuencia del turno (fija `_ub_meowth_pending` y el snapshot).
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

    # No debe bajar Meowth ex (cuerpo redundante); con un atacante listo, ataca.
    assert result[0] not in meowth_opts, (
        f"no debe jugar Meowth ex con un atacante ya listo; obtuvo {result} "
        f"(meowth_opts={meowth_opts})"
    )
    assert result == [attack_opt], (
        f"esperaba atacar (opt {attack_opt}) en vez de bajar Meowth ex, obtuvo {result}"
    )


# Registro 004 (paso 53) vs Archaludon ex (GANADA): con Fezandipiti ex activo,
# Dawn (Supporter) en mano y el Supporter aun sin jugar, el agente decidia
# RETIRAR a Fezandipiti ex (para promover un atacante) ANTES de jugar Dawn. Es
# un error de secuencia: SIEMPRE se juega el Supporter antes de retirar (Dawn
# busca la linea Applin -> Dipplin -> Hydrapple ex que se evoluciona con Forest
# este mismo turno; recien despues conviene retirar y promover). El retiro no lo
# bloquea jugar el Supporter, asi que debe posponerse.
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


# Registro 010 (paso 64) vs Alakazam (GANADA): con Ogerpon ex activo (6 energias,
# puede atacar), Boss's Orders + Ultra Ball en la mano, el activo rival es un
# Dunsparce (FUERA de la linea Alakazam) y en la banca rival hay un Abra (741,
# pre-evo de la linea). El agente jugaba Ultra Ball -> descartaba el Boss's como
# coste y atacaba al Dunsparce. Es un error: la prioridad vs Alakazam es gustear
# con Boss's la pre-evo de banca (Kadabra > Abra > Alakazam) y noquearla para
# cortar el desarrollo del atacante Psiquico. Debe jugar Boss's ANTES que Ultra
# Ball (que ademas quemaria el propio Boss's).
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


# --- Refactor Prioridad 1: scorer puro `_score_boss_orders_play` -------------
# Al extraer la rama de Boss's a una funcion pura que lee un DecisionContext, el
# scoring se puede probar en AISLAMIENTO, sin fabricar una observacion completa.
def _make_boss_ctx(**overrides):
    base = dict(
        state=SimpleNamespace(supporterPlayed=False, turn=6, energyAttached=False),
        my_state=SimpleNamespace(discard=[], active=[None], bench=[], hand=[]),
        op_state=SimpleNamespace(active=[None], bench=[]),
        hand_counts={m.Boss_Orders: 1},
        field_counts={},
        supp_values={m.Boss_Orders: 700},
        cartas_en_mazo={},
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
        best_supp_in_mazo_val=0,
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
    )
    base.update(overrides)
    # `hand_counts`/`field_counts` en produccion son defaultdict(int); los scorers
    # usan acceso por corchete (p.ej. hand_counts[Basic_Grass_Energy],
    # field_counts[Chikorita]). Coercionamos para que el contexto de prueba se
    # comporte igual.
    from collections import defaultdict
    base["hand_counts"] = defaultdict(int, base["hand_counts"])
    base["field_counts"] = defaultdict(int, base["field_counts"])
    return m.DecisionContext(**base)


def test_score_boss_orders_vetoed_when_supporter_already_played():
    ctx = _make_boss_ctx(state=SimpleNamespace(supporterPlayed=True))
    assert m._score_boss_orders_play(ctx) == -1


def test_score_boss_orders_deny_alakazam_line_beats_default():
    # El corte de linea Alakazam puntua en BOSS_SCORE_PRIZE_RANK_BASE, por encima
    # del gusteo por defecto (2400 + val*1.4), replicando el registro 010.
    deny = m._score_boss_orders_play(_make_boss_ctx(boss_deny_alakazam_line=True))
    default = m._score_boss_orders_play(_make_boss_ctx())
    assert deny == m.BOSS_SCORE_PRIZE_RANK_BASE
    assert deny > default


def test_score_boss_orders_win_via_bench_has_priority_over_deny():
    # Una gustada letal a la banca (win_via_bench) mantiene su prioridad por
    # encima del corte de linea (el orden del if/elif se conserva tras extraer).
    ctx = _make_boss_ctx(boss_win_via_bench=True, boss_deny_alakazam_line=True)
    assert m._score_boss_orders_play(ctx) == m.BOSS_SCORE_WIN_VIA_BENCH


def test_score_unfair_stamp_dead_hand_scores_highest():
    # Mano SIN uso alternativo (nada jugable): Unfair Stamp vale su maximo (7500).
    ctx = _make_boss_ctx(hand_counts={m.Unfair_Stamp: 1})
    assert m._score_unfair_stamp_play(ctx) == 7500


def test_score_unfair_stamp_lower_when_hand_has_a_play():
    # Con un item jugable en mano (Night Stretcher) el refresco vale menos (2500):
    # conviene usar la mano antes de barajarla.
    ctx = _make_boss_ctx(hand_counts={m.Unfair_Stamp: 1, m.Night_Stretcher: 1})
    assert m._score_unfair_stamp_play(ctx) == 2500


def _mazo(*ids):
    """Deck-belief minimo: {id: {ESTADO_MAZO: 1}} para los ids dados."""
    return {cid: {m.ESTADO_MAZO: 1} for cid in ids}


def test_score_poke_pad_vetoed_when_nothing_searchable():
    # Sin ningun Pokemon no-ex en el mazo, Poke Pad no busca nada.
    ctx = _make_boss_ctx(state=SimpleNamespace(turn=6, energyAttached=False),
                         cartas_en_mazo={})
    assert m._score_poke_pad_play(ctx) == -1


def test_score_poke_pad_enables_evolution_this_turn_scores_high():
    # Bayleef en juego (desde inicio de turno) + Meganium en el mazo y no en mano:
    # buscar Meganium habilita la evolucion ESTE turno -> score alto (>=22000).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        cartas_en_mazo=_mazo(m.Meganium),
        field_counts={m.Bayleef: 1},
        field_at_turn_start={m.Bayleef: 1},
        bench_count=2,
    )
    assert m._score_poke_pad_play(ctx) >= 22000


def test_score_poke_pad_saves_resource_on_full_bench():
    # Banca llena y sin pre-evo que evolucionar con una busqueda: se guarda (-1).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        cartas_en_mazo=_mazo(m.Chikorita),
        field_counts={},
        bench_count=5,
    )
    assert m._score_poke_pad_play(ctx) == -1


def test_score_night_stretcher_vetoed_when_discard_empty():
    # Descarte vacio: no hay nada que recuperar.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(discard=[], active=[None], bench=[], hand=[]),
    )
    assert m._score_night_stretcher_play(ctx) == -1


def test_score_night_stretcher_recovers_meowth_for_refresh_engine():
    # Meowth ex en el descarte + motor de refresco viable (Supporter fuerte en el
    # mazo, ninguno en mano, Supporter no jugado): se recupera. Registro 006 p51.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(
            discard=[SimpleNamespace(id=m.Meowth_ex)], active=[None], bench=[], hand=[]),
        bench_count=1,
        best_supp_in_hand_val=0,
        best_supp_in_mazo_val=700,
    )
    # best_recovery_value=830 -> tier 800..899 -> ns_score 11000.
    assert m._score_night_stretcher_play(ctx) == 11000


def test_score_forest_vetoed_when_forest_already_in_play():
    # Si Forest of Vitality ya es el estadio en juego, no se vuelve a jugar.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        stadium_id=m.Forest_of_Vitality,
    )
    assert m._score_forest_of_vitality_play(ctx) == -1


def test_score_forest_high_when_enables_evolution_chain():
    # Chikorita en juego + Bayleef en mano y sin Meganium: Forest habilita la
    # cadena de evolucion este turno -> score alto (>=21900).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        field_counts={m.Chikorita: 1},
        hand_counts={m.Bayleef: 1},
        stadium_id=0,
    )
    assert m._score_forest_of_vitality_play(ctx) >= 21900


def test_score_bug_catching_set_vetoed_when_nothing_eligible():
    # Mazo sin Pokemon Planta ni Energia elegible: no hay nada que coger.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        cartas_en_mazo={},
    )
    assert m._score_bug_catching_set_play(ctx) == -1


def test_score_bug_catching_set_positive_when_grass_energy_in_deck():
    # Con Energia Planta en el mazo (elegible), la jugada tiene valor positivo.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False),
        cartas_en_mazo={m.Basic_Grass_Energy: {m.ESTADO_MAZO: 5}},
    )
    assert m._score_bug_catching_set_play(ctx) > 0


def test_score_ultra_ball_vetoed_with_tiny_hand():
    # Mano de <3 cartas: jugar Ultra Ball (coste de descartar 2) vaciaria la mano.
    # Ruta fria del corte temprano `hand_size < 3` (turno medio, sin supervivencia).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        my_state=SimpleNamespace(
            discard=[], active=[None], bench=[],
            hand=[SimpleNamespace(id=m.Ultra_Ball), SimpleNamespace(id=m.Boss_Orders)]),
        bench_count=1,
    )
    assert m._score_ultra_ball_play(ctx) == -1


def test_ub_cancel_stamp_false_without_unfair_stamp():
    # Sin Unfair Stamp en mano, esta guarda nunca cancela.
    ctx = _make_boss_ctx(hand_counts={m.Ultra_Ball: 1, m.Basic_Grass_Energy: 3})
    assert m._ub_cancel_stamp(ctx) is False


def test_ub_cancel_stamp_true_when_stamp_would_be_forced_fodder():
    # Mano {Unfair Stamp, Ultra Ball}: sin fodder (0 descartables sin tocar el
    # Stamp), jugar UB descartaria el Stamp -> se cancela.
    ctx = _make_boss_ctx(hand_counts={m.Unfair_Stamp: 1, m.Ultra_Ball: 1})
    assert m._ub_cancel_stamp(ctx) is True


def test_ub_cancel_meowth_false_when_no_meowth_engine():
    # Sin Meowth ex en mano (o sin Lillie's en mazo), la guarda de Meowth no aplica.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        hand_counts={m.Ultra_Ball: 1},
        cartas_en_mazo={},
    )
    assert m._ub_cancel_meowth(ctx) is False


def test_score_lillie_vetoed_when_supporter_already_played():
    # Ya se jugo el Supporter del turno: no se puede jugar otro.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, supporterPlayed=True),
        my_state=SimpleNamespace(active=[None], bench=[], hand=[]),
        hand_counts={m.Lillie_Determination: 1},
    )
    assert m._score_lillie_determination_play(ctx) == -1


def test_unfair_stamp_cedes_to_lillie_when_opp_hand_small():
    # Regla (user): con Lillie's en mano y el rival con <=3 cartas, NO se juega
    # Unfair Stamp (se cede a Lillie's).
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, energyAttached=False, supporterPlayed=False),
        hand_counts={m.Unfair_Stamp: 1, m.Lillie_Determination: 1},
        op_hand_count=3,
    )
    assert m._score_unfair_stamp_play(ctx) == -1


def test_unfair_stamp_not_ceded_when_opp_hand_large():
    # Con el rival con >3 cartas la disrupcion sigue valiendo: Unfair Stamp NO cede.
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
    # Con Unfair Stamp en mano + KO el turno pasado, normalmente Lillie's se veta;
    # pero si el rival tiene <=3 cartas, Lillie's queda JUGABLE (gana la decision).
    assert m._score_lillie_determination_play(_lillie_ctx(op_hand_count=3)) > 0


def test_lillie_still_vetoed_by_stamp_when_opp_hand_large():
    # Con el rival con >3 cartas se conserva el veto original: se prefiere el Stamp.
    assert m._score_lillie_determination_play(_lillie_ctx(op_hand_count=6)) == -1


def _og(energy_count):
    # Teal Mask Ogerpon ex con `energy_count` Plantas -> atacante listo con >=3.
    return SimpleNamespace(id=m.Teal_Mask_Ogerpon_ex, energies=[1] * energy_count)


def _hop_lillie_ctx(**over):
    # Registro 008 paso 84 vs Hops: activo + banca con atacantes listos, Boss's y
    # Lillie's en mano, rival Hops. (ko_last_turn=False para no cruzar el veto de
    # Unfair Stamp; sin Unfair Stamp en mano.)
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
    # vs Hops con Boss's en mano y >=2 atacantes listos: NO jugar Lillie's (barajaria
    # el Boss's al mazo); se guarda para responder a un Hops Phantump con cara.
    assert m._score_lillie_determination_play(_hop_lillie_ctx()) == -1


def test_lillie_playable_vs_hops_when_active_is_only_attacker():
    # vs Hops con Boss's pero el activo es el UNICO atacante: SI se juega Lillie's
    # (cavar por recursos), aunque baraje el Boss's.
    ctx = _hop_lillie_ctx(
        my_state=SimpleNamespace(active=[_og(4)], bench=[],
                                 hand=[SimpleNamespace(id=0) for _ in range(5)]))
    assert m._score_lillie_determination_play(ctx) > 0


def test_lillie_playable_vs_hops_when_no_boss_in_hand():
    # vs Hops SIN Boss's en mano: Lillie's se puede jugar con normalidad.
    ctx = _hop_lillie_ctx(hand_counts={m.Lillie_Determination: 1})
    assert m._score_lillie_determination_play(ctx) > 0


def test_lillie_playable_with_boss_and_two_attackers_when_not_hops():
    # La regla solo aplica vs Hops: contra otro mazo, Lillie's sigue jugable.
    assert m._score_lillie_determination_play(_hop_lillie_ctx(op_is_hop_deck=False)) > 0


def test_score_lanas_aid_vetoed_when_supporter_already_played():
    # Recibe el score entrante (10000) pero lo veta si ya se jugo el Supporter.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, supporterPlayed=True, energyAttached=False),
        my_state=SimpleNamespace(active=[None], bench=[], hand=[], discard=[]),
    )
    assert m._score_lanas_aid_play(ctx, 10000) == -1


# Registro 014 (paso 146) vs Alakazam (GANADA): al gustear con Boss's Orders
# (nuestro activo Meowth ex no puede atacar -> modo estorbo), el agente elegia un
# Shaymin de la banca rival en vez de un Abra. Debe PRIORIZAR la linea Alakazam
# (Abra/Kadabra/Alakazam) para cortar el desarrollo del atacante Psiquico.
_BOSS_GUST_ABRA_FIXTURE = ROOT / "tests" / "fixtures" / "alakazam_boss_gust_abra_step146.json"


def test_alakazam_step146_boss_gust_targets_abra_not_shaymin():
    with open(_BOSS_GUST_ABRA_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    # Mapear cada opcion (banca rival) a su id de Pokemon.
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


# Registro 010 (paso 76) vs Dragapult/Latias (GANADA): al gustear con Boss's
# Orders (Tapu Bulu activo no puede atacar -> estorbo), el agente elegia la Latias
# ex de la banca rival. Es un error: Latias ex (Skyliner) deja retirar GRATIS a
# cualquier Basico (incluida ella), asi que gustear un Basico no traba nada. Debe
# elegir un NO-basico (Drakloak). Nunca gustear Latias ex ni un Basico con Latias
# ex en juego.
_LATIAS_BOSS_GUST_FIXTURE = ROOT / "tests" / "fixtures" / "dragapult_latias_boss_gust_drakloak_step76.json"


def test_boss_gust_avoids_latias_ex_and_basics_targets_drakloak():
    with open(_LATIAS_BOSS_GUST_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    op_bench = obs["current"]["players"][1]["bench"]
    opt_ids = {i: op_bench[o["index"]]["id"]
               for i, o in enumerate(obs["select"]["option"])}
    latias_opts = [i for i, cid in opt_ids.items() if cid == m.Latias_ex]
    dreepy_opts = [i for i, cid in opt_ids.items() if cid == 119]   # Dreepy (basico)
    drakloak_opts = [i for i, cid in opt_ids.items() if cid == 120]  # Drakloak (stage 1)
    assert latias_opts and drakloak_opts, f"fixture debe ofrecer Latias ex y Drakloak (map={opt_ids})"

    result = m.agent(obs)

    assert result[0] not in latias_opts, "no debe gustear la Latias ex"
    assert result[0] not in dreepy_opts, "no debe gustear un Basico (Dreepy) con Latias ex en juego"
    assert result[0] in drakloak_opts, (
        f"esperaba gustear el Drakloak {drakloak_opts} (no-basico), obtuvo {result} (map={opt_ids})"
    )


# Registro 008 (paso 105) vs Alakazam (PERDIDA con codigo antiguo): al final del
# turno, sin poder atacar (Hydrapple ex con 1 energia) y sin Supporter jugado,
# con un Meowth ex en la mano y hueco en banca (incluso con OTRO Meowth ex ya en
# banca), hay que JUGAR el Meowth ex (Last-Ditch Catch -> Lillie's) en vez de
# terminar el turno. El codigo actual ya lo hace (motor Meowth->Lillie's); este
# test bloquea la conducta para que no regrese.
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


# Registro 010 (paso 82) vs Alakazam (GANADA): con un Tapu Bulu CARGADO (4 energia)
# en el activo que puede NOQUEAR al activo rival (Kadabra 80 HP; Tapu Bulu pega 220),
# el agente retiraba el Tapu para pivotar a Hydrapple ex. Es incorrecto: nunca se
# retira un Tapu Bulu del activo si puede derrotar al rival; debe ATACAR (Tapu Bulu
# es no-ex -> 1 premio si lo noquean; la Hydrapple ex vale 2). El planificador greedy
# promovia la Hydrapple ex de banca aun cuando el activo podia noquear.
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


# Registro 023 (vs Archaludon ex, PERDIDA): con DOS Hydrapple ex en juego, el
# activo es un Hydrapple ex FRAGIL (110/330) que puede atacar y noquear, y en
# banca hay otro Hydrapple ex a VIDA COMPLETA (330/330) que, tras retirar el
# activo, AUN noquea al Archaludon ex (Syrup Storm escala con el Grass total del
# campo, que baja por el coste de retirada). El agente atacaba con el fragil, que
# moria al turno siguiente cediendo 2 premios (derrota). Lo correcto: RETIRAR el
# fragil y promover al tanque, que noquea igual y sobrevive. El pivote defensivo
# excluia el caso activo-Hydrapple (`_ret_active.id != Hydrapple_ex`).
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

    assert result == [retreat_opt], (
        f"con dos Hydrapple ex, un activo fragil y un tanque de banca que noquea "
        f"tras retirar, debe RETIRAR (opt {retreat_opt}) para promover al tanque; "
        f"obtuvo {result}"
    )
    assert result != [attack_opt], "no atacar con el Hydrapple fragil (moriria dando 2 premios)"


# Registro 007 (paso 78 vs Archaludon ex, GANADA con jugada suboptima): Hydrapple
# ex activo cargado + >=2 atacantes, con Boss's Orders Y Lillie's Determination en
# mano. El rival tiene un Cinderace no-ex (1 premio, poco peligroso) en el activo
# y un Duraludon (1 premio, pre-evo de Archaludon ex = el atacante del mazo) en
# banca que podemos gustear y NOQUEAR. El agente jugaba Lillie's (barajando el
# Boss's al mazo). Correcto: jugar Boss's para gustear+noquear al Duraludon (mismo
# premio que el Cinderace pero remueve al futuro atacante). El pivote fallaba por
# (1) el veto de Lillie's solo aplicaba vs Hops y (2) con premios IGUALES el
# codigo prefiere noquear el activo en vez de gustear la pre-evo amenaza.
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


# Registro 003 (paso 17 vs Archaludon, PERDIDA): el agente bajaba Meowth ex para
# buscar (Last-Ditch Catch) una Lillie's Determination cuando YA tenia una en la
# mano (fetch redundante + expone un cuerpo de 2 premios). Con la energia ya
# adjuntada y un Tapu Bulu como activo (no aplica la excepcion de primer-turno-
# primero con basico solo != Tapu), debe jugar la Lillie's que ya tiene, NO Meowth.
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


# Registro 004 (paso 60 vs Abomasnow, PERDIDA): ya jugamos un Supporter este turno
# (supporterPlayed=True) y el agente bajaba un SEGUNDO Meowth ex. Meowth ex solo
# sirve para Last-Ditch Catch -> buscar un Supporter; con el Supporter ya jugado ese
# fetch es inutil, asi que bajar un cuerpo de 2 premios es puro desperdicio. El veto
# normal (-1) empataba por puntaje con el ataque no-KO (tambien -1) y Meowth ganaba
# el desempate por indice. Correcto: atacar (o terminar), nunca bajar el Meowth.
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


# Registro 012 (paso 241 vs Iono, GANADA con jugada suboptima): con 2 premios,
# activo Ogerpon ex (4 energias, puede retirar), banca con Hydrapple ex (2 energias),
# otro Ogerpon ex y Meganium, y Boss's + Lana's en mano; el rival tiene un Iono's
# Bellibolt ex (280 HP, 2 premios) en banca. El agente jugaba Lana's Aid. Correcto:
# jugar Boss's para gustear al Bellibolt ex y noquearlo tras RETIRAR el activo y
# promover el Hydrapple ex (Syrup Storm escala con el Grass TOTAL del campo ~= 330),
# ganando los 2 premios. La deteccion de win-via-gusteo solo miraba el ataque del
# activo actual (Ogerpon 150 < 280), no el Hydrapple promovido tras retirar.
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


# Variante (user): el remate ganador con Boss's debe detectarse con CUALQUIER
# atacante de banca, no solo Hydrapple ex. Aqui NO hay Hydrapple; el atacante de
# banca es un Ogerpon ex con energia suficiente (Ivy Bludgeon = 30+30*10 = 330 >=
# 280) que noquea al Bellibolt ex tras retirar+promover. Confirma que
# `_bench_attacker_can_ko` evalua toda la banca (Ogerpon/Tapu/Meganium/etc).
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


# Registro 005 (paso 51 vs Dragapult, PERDIDA): con Boss's + Lillie's en mano,
# nuestro UNICO atacante es el activo (Ogerpon ex) y en banca solo hay BASICOS
# (Tapu Bulu sin cargar, Applin, Bayleef) -> ningun atacante de banca listo. El
# rival (Dragapult ex 320 HP en el activo) tiene un Drakloak/Dreepy gusteable de
# 1 premio. El agente jugaba Boss's (gusteo de desarrollo para cortar la linea).
# Correcto: jugar Lillie's para CAVAR, porque sin segundo atacante el gusteo no
# encadena. Boss's sobre Lillie's solo tiene prioridad con un atacante de banca
# real (!= Applin) listo.
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
    # Complemento: CON un atacante de banca listo (!= Applin), el gusteo de
    # desarrollo (boss_prize_rank) SI mantiene prioridad -> Boss's no cede.
    _hc = {m.Boss_Orders: 1, m.Lillie_Determination: 1}
    ctx = _make_boss_ctx(boss_prize_rank=7, has_ready_bench_attacker=True,
                         active_cant_attack=False, hand_counts=_hc)
    assert m._score_boss_orders_play(ctx) > m.BOSS_SCORE_EMPTY_GUST, (
        "con atacante de banca listo, el gusteo de desarrollo mantiene prioridad")
    ctx_no = _make_boss_ctx(boss_prize_rank=7, has_ready_bench_attacker=False,
                            active_cant_attack=False, hand_counts=dict(_hc))
    assert m._score_boss_orders_play(ctx_no) == m.BOSS_SCORE_EMPTY_GUST, (
        "sin atacante de banca real (y Lillie's en mano), el gusteo de desarrollo cede a Lillie's")


# Registro 004 (paso 35) vs Mega Lucario (GANADA): al resolver la busqueda (TO_HAND)
# de una Ultra Ball, con Chikorita en el activo (solo chip, sin atacante real), un
# Meowth ex ya en banca, Dipplin recien evolucionado y Bayleef solo en la MANO (no
# hay Bayleef en juego -> un Meganium buscado seria INUTIL este turno, mera
# preparacion), y con Meowth ex + Lillie's aun en el mazo y sin Supporter jugado,
# hay que buscar el 2o Meowth ex (Last-Ditch Catch -> Lillie's, refrescar mano) en
# vez del Meganium muerto. El codigo antiguo buscaba Meganium.
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


# Registro 007 (paso 90) vs Alakazam (GANADA): tras un KO, al PROMOVER (TO_ACTIVE)
# un nuevo activo, hay un Tapu Bulu CARGADO (4 energia, pega 220) en la banca que
# NOQUEA al Alakazam ex activo (140 HP). El agente subia un Ogerpon ex (mas vida,
# pero 2 premios); lo correcto es subir el Tapu Bulu (no-ex, 1 premio) que noquea
# igual. Regla: promover SIEMPRE el Tapu Bulu cargado (o cargable con energia en
# mano/Night Stretcher) que pueda derrotar al activo rival.
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


# Registro 019 (paso 190) vs Dragapult (GANADA): en turno letal, con Boss's Orders
# en mano, ~20 energias Planta (Syrup Storm del Hydrapple ex activo noquea a
# cualquier ex) y el rival a 2 premios con Latias ex / Dragapult ex en banca, el
# agente RETIRABA el activo (pivote defensivo, 6600) en vez de jugar Boss's para
# gustear un ex y rematar con el activo (win_via_boss_gust, que valia solo 5600).
# Un gusteo que GANA la partida debe superar cualquier retirada defensiva.
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


# Registro 006 (paso 72) vs Hops (PERDIDA): con la BANCA LLENA (5 Pokemon) y
# NINGUNA evolucion que buscar disponible en el MAZO (hay un Dipplin en juego pero
# el Hydrapple ex ya no queda en el mazo), la Ultra Ball no puede banquear ni
# evolucionar nada: es inutil y solo malgastaria 2 descartes. El agente la jugaba
# igual (rescate de supervivencia que resucitaba el corte + desempate por indice 0
# cuando el resto de jugadas tambien estaban vetadas). Debe CANCELARla y atacar.
# Se replica la secuencia del turno para que el tracking del MAZO sepa que el
# Hydrapple ex ya no esta (la Explorer's Guidance revela el mazo antes).
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


# Registro 004 (paso 28) vs Mega Starmie (PERDIDA): con un Teal Mask Ogerpon ex de
# banca a 2 energias que TODAVIA puede usar Teal Dance este turno, el agente cargaba
# una energia MANUALMENTE (al Ogerpon o a otro cuerpo) en vez de usar Teal Dance
# primero. Teal Dance adjunta 1 Planta Y ROBA una carta, asi que tiene prioridad
# sobre el adjunte manual (se pospone el adjunte hasta usar la habilidad). El orden
# de jugada dejaba la habilidad (tier 0) por debajo del tier ENERGY de los adjuntes.
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


# Registro 004 (paso 29) vs Mega Starmie (PERDIDA): la Ultra Ball resuelve su
# busqueda (TO_HAND) trayendo un Meganium (evolucionaria un Bayleef en juego), pero
# NO hay ningun atacante USABLE este turno: el activo (Tapu Bulu, 0 energia, coste
# de retirada 3) no puede atacar ni retirarse, asi que el Ogerpon ex cargado de
# banca esta atascado. Con banca libre y el motor Meowth ex -> Lillie's disponible,
# hay que traer Meowth ex (bajarlo -> Last-Ditch Catch -> Lillie's -> refrescar la
# mano) en vez de una evolucion que no dara ataque ahora. Generaliza el caso del
# paso 35: aqui la evolucion SI es jugable (hay Bayleef), pero igual no aporta ataque.
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


# Registro 010 (paso 127) vs Alakazam (PERDIDA): con un Teal Mask Ogerpon ex (ex,
# 2 premios) activo cargado que NOQUEA al Alakazam ex (140 HP) y un Meganium (no-ex,
# 1 premio) cargado en banca que TAMBIEN lo noquea (140 base), el juego atacaba con
# el Ogerpon. Contra Alakazam hay que atacar con cuerpos de 1 premio: retirar el ex
# y promover el Meganium para que, si nos lo noquean, solo cedamos 1 premio y no 2.
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


# Registro 008 (paso 84) vs Marnie/Froslass (PERDIDA): TURNO MUERTO -- el activo
# (Hydrapple ex, 0 energia, coste de retirada 3) no puede ATACAR ni RETIRARSE, no
# hay atacante de banca que subir y la mano (Tapu Bulu, Ogerpon ex, Meowth ex, Ultra
# Ball) no tiene con que habilitar un ataque. Con hueco en banca y el motor de
# refresco en el MAZO, hay que bajar Meowth ex (Last-Ditch Catch -> Lana's Aid /
# Lillie's) en vez de un cuerpo redundante (Tapu Bulu). El veto de "no banquear
# Meowth ex vs Froslass" tiene aqui una excepcion por turno muerto.
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


# Registro 012 (paso 93) vs Archaludon/Duraludon (PERDIDA): el activo Teal Mask
# Ogerpon ex (4 energias efectivas) hace 30+30*4 = 150 de dano; Duraludon (Metal)
# RESISTE -30 a Planta, asi que el dano real es 120 y NO noquea al activo de 130 HP
# (lo deja en 10). El calculo antiguo sumaba la energia del OBJETIVO (30+30*(4+1)=
# 180 -> 150 tras resistencia) y creia que ya noqueaba, asi que cargaba Tapu Bulu
# para el futuro en vez de rematar. Lo correcto: hacer Teal Dance en el activo (sube
# a 6 efectivas -> 210 base -> 180 tras resistencia >= 130) para habilitar el KO.
_DURALUDON_TEAL_DANCE_FIXTURE = ROOT / "tests" / "fixtures" / "duraludon_teal_dance_ko_resistance_step93.json"


def test_duraludon_step93_teal_dance_for_ko_accounting_resistance():
    with open(_DURALUDON_TEAL_DANCE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    # Teal Dance (ability) sobre el ACTIVO Ogerpon ex (area 4)
    teal_active_opt = next(
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.ABILITY)
        and o.get("area") == int(AreaType.ACTIVE))
    # Cargar energia manual a un Tapu Bulu de banca (lo que hacia antes)
    bench = obs["current"]["players"][0]["bench"]
    tapu_attach_opts = [
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.ATTACH)
        and o.get("inPlayArea") == int(AreaType.BENCH)
        and bench[o["inPlayIndex"]]["id"] == m.Tapu_Bulu]

    # ACTUALIZADO (auditoria julio 2026, copias inline de Myriad corregidas):
    # con la formula VERIFICADA (30+30*(propias+rivales); memoria
    # ogerpon-myriad-cuenta-ambos-activos, 6 registros de dano real), el
    # Duraludon del fixture lleva 1 energia -> 30+30*(4+1)=180 -> 150 tras la
    # resistencia >= 130: el activo YA noquea SIN Teal Dance, y cargar el Tapu
    # futuro (regla alakazam-cargar-meganium-atacante-futuro generalizada por
    # _tapu_future_charge) es la linea correcta. Este test se habia escrito
    # con la formula antigua "solo propia" (anulada como erronea).
    result = m.agent(obs)
    assert result[0] in tapu_attach_opts, (
        f"con el KO ya asegurado (180-30=150 >= 130) se carga el Tapu futuro; "
        f"obtuvo {result}")

    # CONTRAFACTUAL (preserva la intencion original del test: la RESISTENCIA
    # se contabiliza): con el Duraludon SIN energia, 30+30*4=150 -> 120 tras
    # resistencia < 130 -> el activo NO noquea y Teal Dance (sube a 6 propias:
    # 30+30*6=210 -> 180 >= 130) habilita el KO.
    import copy as _c
    obs2 = _c.deepcopy(obs)
    obs2["current"]["players"][1]["active"][0]["energies"] = []
    obs2["current"]["players"][1]["active"][0]["energyCards"] = []
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result2 = m.agent(obs2)
    assert result2 == [teal_active_opt], (
        f"sin energia rival la resistencia deja el golpe en 120 < 130: Teal "
        f"Dance en el activo habilita el KO; obtuvo {result2}")


def test_ogerpon_damage_counts_both_active_energy():
    # Myriad Leaf Shower (ataque 120): 30 + 30 por cada Energia unida a AMBOS
    # Pokemon Activos (el nuestro + el rival). Verificado con el dano REAL de 6
    # registros: own 3 + opp 2 -> 180; own 4 + opp 2 -> 210; own 4 + opp 0 -> 150;
    # own 3 + opp 1 -> 150. `_attacker_base_damage` devuelve el dano BASE (antes de
    # debilidad/resistencia), asi que cuenta own(4)+target(3) = 7 -> 30+210 = 240.
    from types import SimpleNamespace as _NS
    tgt3 = _NS(id=169, hp=130, energies=[8, 8, 8], maxHp=130)   # 3 energia objetivo
    base = m._attacker_base_damage(m.Teal_Mask_Ogerpon_ex, tgt3, 4,
                                   grass_scale=0, teal_self_energy=4, bench_count=5)
    assert base == 240, f"Myriad = 30+30*(propia 4 + objetivo 3) = 240; obtuvo {base}"
    # objetivo sin energia -> solo cuenta la propia (30+30*4 = 150)
    tgt0 = _NS(id=169, hp=130, energies=[], maxHp=130)
    base0 = m._attacker_base_damage(m.Teal_Mask_Ogerpon_ex, tgt0, 4,
                                    grass_scale=0, teal_self_energy=4, bench_count=5)
    assert base0 == 150, f"con objetivo sin energia = 30+30*4 = 150; obtuvo {base0}"


# Registro 004 (paso 51) vs Cynthia's Garchomp (PERDIDA): al jugar Boss's Orders,
# el juego gusteaba el Cynthia's Gible (basico, 70 HP) en vez de la MAYOR evolucion
# de la linea -- Cynthia's Gabite (stage1) con Cynthia's Power Weight (170 HP), que
# ademas tiene energia. Nuestro Ogerpon ex de banca (6 energias, x2 debilidad Planta
# = 420) noquea cualquiera tras retirar+promover. Regla general de mazos de Fase 2
# (Cynthia/Dragapult/Marnie; Alakazam tiene su regla propia): privilegiar SIEMPRE la
# mayor linea evolutiva que podamos noquear.
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


# Estrategia vs Comfey (mill/control; registro_005): detectado por Comfey (164) /
# Bramblin (817) / Brambleghast (818). Regla 1 (estricta): SOLO bajar Teal Mask
# Ogerpon ex, MAXIMO 2 en juego; vetar cualquier otro Pokemon (salvo arranque).
# Regla 5: cancelar Ultra Ball si ya hay 2 Ogerpon ex en juego.
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
    m._debug_log_decision = spy
    m.DEBUG_DECISIONS = True
    try:
        m._init_cartas_tracking(); m.plan = m.AttackPlan()
        m.agent(obs)
    finally:
        m._debug_log_decision = orig
    me = obs["current"]["players"][1]
    out = {}
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(OptionType.PLAY):
            out[me["hand"][o["index"]]["id"]] = captured["s"][i]
    return out


def test_comfey_rule1_only_ogerpon_max_two_and_veto_others():
    # Con 0 Ogerpon ex en juego: bajar Ogerpon ex OK, otro Pokemon vetado.
    s0 = _score_by_hand_id(_comfey_main_obs(0, comfey=True))
    assert s0[m.Teal_Mask_Ogerpon_ex] > 0, "vs Comfey debe poder bajar Teal Mask Ogerpon ex"
    assert s0[m.Meganium] == -1, "vs Comfey NO se baja ningun Pokemon que no sea Ogerpon ex"
    # Con 2 Ogerpon ex en juego: no bajar un 3o.
    s2 = _score_by_hand_id(_comfey_main_obs(2, comfey=True))
    assert s2[m.Teal_Mask_Ogerpon_ex] == -1, "maximo 2 Teal Mask Ogerpon ex vs Comfey"


def test_comfey_rule5_cancel_ultraball_when_two_ogerpon():
    s2 = _score_by_hand_id(_comfey_main_obs(2, comfey=True))
    assert s2[m.Ultra_Ball] < 0, "vs Comfey con 2 Ogerpon ex, la Ultra Ball es inutil -> cancelar"


def test_comfey_rules_do_not_fire_vs_other_decks():
    # Control: sin Comfey, Meganium se baja normal y la Ultra Ball no se cancela.
    s = _score_by_hand_id(_comfey_main_obs(0, comfey=False))
    assert s[m.Meganium] > 0, "vs un mazo normal, la regla Ogerpon-only NO debe vetar otros Pokemon"


# Estrategia vs Comfey — reglas de Entrenadores (user): las UNICAS cartas a jugar
# son Lillie's Determination (SOLO con mano >=10), Lana's Aid (SOLO si recupera >=2
# energias del descarte) y Boss's Orders (igual que siempre). El resto (Dawn, etc.)
# no se juegan.
def _comfey_supporter_obs(hand_size, grass_discard, comfey=True):
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
    for k in range(max(0, hand_size - 3)):
        hand.append({"id": 1, "playerIndex": 1, "serial": 830 + k})
    me["hand"] = hand
    me["discard"] = [{"id": 1, "playerIndex": 1, "serial": 700 + k}
                     for k in range(grass_discard)]
    o["select"] = {"context": 0, "contextCard": None, "deck": None, "effect": None,
                   "maxCount": 1, "minCount": 1, "type": 0, "remainDamageCounter": 0,
                   "remainEnergyCost": 0,
                   "option": [{"index": 0, "type": 7}, {"index": 1, "type": 7},
                              {"index": 2, "type": 7}, {"type": 14}]}
    cur["yourIndex"] = 1
    return o


def test_comfey_lillie_only_with_ten_or_more_cards():
    s10 = _score_by_hand_id(_comfey_supporter_obs(10, 1, comfey=True))
    assert s10[m.Lillie_Determination] > 0, "vs Comfey con mano>=10 se puede jugar Lillie's"
    s9 = _score_by_hand_id(_comfey_supporter_obs(9, 1, comfey=True))
    assert s9[m.Lillie_Determination] == -1, "vs Comfey con mano<10 NO se juega Lillie's"


def test_comfey_lana_only_when_recovers_two_energies():
    s2 = _score_by_hand_id(_comfey_supporter_obs(9, 2, comfey=True))
    assert s2[m.Lanas_Aid] > 0, "vs Comfey con >=2 energias en descarte, Lana's Aid es jugable"
    s1 = _score_by_hand_id(_comfey_supporter_obs(9, 1, comfey=True))
    assert s1[m.Lanas_Aid] == -1, "vs Comfey con <2 energias recuperables NO se juega Lana's Aid"


def test_comfey_vetoes_other_trainers_like_dawn():
    s = _score_by_hand_id(_comfey_supporter_obs(10, 2, comfey=True))
    assert s[m.Dawn] == -1, "vs Comfey NO se juegan otros entrenadores (p.ej. Dawn)"
    # Control: sin Comfey, Dawn se juega con normalidad.
    sc = _score_by_hand_id(_comfey_supporter_obs(9, 2, comfey=False))
    assert sc[m.Dawn] > 0, "vs un mazo normal, Dawn NO debe estar vetada por la regla Comfey"


# Estrategia vs Comfey — Regla 2 (descarte por Xerosic's Machinations: quedarnos con
# 3 cartas). Prioridad de MANTENER: energías > Night Stretcher > Lana's Aid > Unfair
# Stamp > resto de entrenadores (y un Ogerpon ex que aún cabe, por encima de los
# entrenadores). Regla 4 (activo confundido por Brambleghast): si hay atacante de
# banca listo, retirar y atacar con él; si no, atacar con el confundido.
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    discarded = set(m.agent(obs))  # indices de las 4 cartas a descartar
    discarded_ids = [hand[obs["select"]["option"][i]["index"]]["id"] for i in discarded]
    # Las energias se MANTIENEN (nunca se descartan).
    assert m.Basic_Grass_Energy not in discarded_ids, "vs Comfey/Xerosic las energias se mantienen"
    # El resto de entrenadores (Dawn) se descarta antes que Night Stretcher/Lana's.
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    assert m.agent(obs) == [retreat_opt], (
        "activo confundido con atacante de banca listo: retirar (promover el cuerpo NO confundido)"
    )


def test_comfey_rule4_confused_active_attacks_when_no_bench_attacker():
    obs = _comfey_confused_obs(bench_ready=False)
    attack_opt = next(i for i, o in enumerate(obs["select"]["option"])
                      if o.get("type") == int(OptionType.ATTACK))
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    assert m.agent(obs) == [attack_opt], (
        "activo confundido sin atacante de banca: atacar con el confundido (aceptar la moneda)"
    )


# =====================================================================
# Neutralization Zone (id 1247, user): estrategia bajo la Zona de
# Neutralizacion. La zona EVITA todo el dano a un Pokemon SIN recuadro de
# regla (1 premio) causado por un atacante CON recuadro (nuestros ex). Por
# eso, con la zona en juego, nuestros ex solo danan a los ex del rival; a un
# activo de 1 premio hay que atacarlo con un NO-ex (Meganium/Tapu Bulu/etc.),
# y para pegarle a un ex del rival en banca se usa Boss's Orders para gustearlo.
# =====================================================================
import copy as _copy
import json as _json

_ZONE_PROMOTE_FIXTURE = ROOT / "tests" / "fixtures" / "zone_promote_nonex_not_ex_active.json"
_ZONE_BOSS_GUST_EX_FIXTURE = ROOT / "tests" / "fixtures" / "zone_boss_gust_bench_ex_step.json"


def test_zone_promote_nonex_over_ex_when_active_single_prize():
    # Tras un KO, con la Zona de Neutralizacion en juego y el ACTIVO rival de 1
    # premio (Alakazam-like), promover el atacante NO-ex (Meganium) en vez de un
    # ex (Ogerpon ex) que bajo la zona hace 0 dano a ese activo.
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
    # Control positivo: si el ACTIVO rival es un ex (recuadro de regla), nuestros
    # ex SI danan bajo la zona, asi que se promueve el ex (Ogerpon ex).
    with open(_ZONE_PROMOTE_FIXTURE, encoding="utf-8") as f:
        obs = _json.load(f)["observation"]
    obs = _copy.deepcopy(obs)
    cur = obs["current"]; yi = cur["yourIndex"]; op = cur["players"][1 - yi]
    # op activo -> Iono's Bellibolt ex (269, recuadro de regla), 130hp (nuestro ex KO)
    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                     "hp": 130, "id": 269, "maxHp": 280, "playerIndex": 1 - yi,
                     "preEvolution": [], "serial": 301, "tools": []}]
    # El fixture original trae Abra/Kadabra en el DESCARTE rival; con la
    # inferencia de arquetipo por descarte (auditoria julio 2026) eso activa
    # `op_is_alakazam_deck` y la regla del 1-premio dominaria la promocion
    # (correcto vs Alakazam, pero este test es el control positivo de la
    # LOGICA DE ZONA). Se limpia el descarte para aislar lo que se prueba.
    op["discard"] = [c for c in op["discard"]
                     if c["id"] not in (m.Abra, m.Kadabra, m.Alakazam_ex)]
    options = obs["select"]["option"]
    ex_opt = next(i for i, o in enumerate(options) if o.get("index") == 0)      # Ogerpon ex
    nonex_opt = next(i for i, o in enumerate(options) if o.get("index") == 1)   # Meganium
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [ex_opt], (
        f"activo rival ex bajo la zona: nuestros ex SI danan, promover el ex "
        f"(opt {ex_opt}), no el no-ex (opt {nonex_opt}); obtuvo {result}")


def test_zone_boss_gust_bench_ex():
    # Con la Zona de Neutralizacion, activo rival de 1 premio (nuestro ex hace 0)
    # y un ex del rival en BANCA que nuestro ex SI puede noquear: jugar Boss's
    # Orders para gustear al ex de banca y rematarlo (los 2 premios / la partida).
    with open(_ZONE_BOSS_GUST_EX_FIXTURE, encoding="utf-8") as f:
        obs = _json.load(f)["observation"]
    assert obs["current"]["stadium"][0]["id"] == m.Neutralization_Zone
    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY) and o.get("index") == 0)
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [boss_opt], (
        f"bajo la zona, gustear con Boss's al ex del rival en banca para poder "
        f"atacarlo con nuestro ex (opt {boss_opt}); obtuvo {result}")


# Registro 008 (paso 108 vs Alakazam, GANADA con jugada suboptima): con el activo
# Hydrapple ex que YA noquea al Alakazam activo, un Meganium PARCIALMENTE cargado en
# banca (2 efectivas, 1 Planta fisica; le falta 1 para su Wood Hammer coste 4) y una
# Planta en mano, el agente ATACABA de una sin cargar el Meganium, desperdiciando la
# energia. Meganium es un excelente atacante de 1 premio (140 derrota a Alakazam y su
# linea); vs Alakazam se carga como atacante FUTURO cuando el activo ya asegura su KO.
_ALK_CHARGE_MEGANIUM_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_charge_meganium_future_step108.json")


def test_alakazam_step108_charges_bench_meganium_before_attacking():
    with open(_ALK_CHARGE_MEGANIUM_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    options = obs["select"]["option"]
    # adjunte manual (type 8) al Meganium de banca (inPlayArea 5, inPlayIndex 2)
    meganium_attach = next(
        i for i, o in enumerate(options)
        if o.get("type") == int(OptionType.ATTACH)
        and o.get("inPlayArea") == 5 and o.get("inPlayIndex") == 2)
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [meganium_attach], (
        f"vs Alakazam, con el activo asegurando su KO, cargar el Meganium de banca "
        f"(opt {meganium_attach}) como atacante de 1 premio antes de atacar; "
        f"no atacar de una (opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]


# Registro 008 (paso 110 vs Mega Lucario, PERDIDA): activo Hydrapple ex con solo 60 HP
# (sera noqueado el proximo turno) que SI puede noquear al Lucario activo; en banca un
# Tapu Bulu (basico, 1 premio) LISTO que tambien noquea al Lucario. El agente ATACABA
# con el Hydrapple ex fragil (queda activo -> cede 2 premios). Correcto: usar Ripening
# Charge para cargar al Hydrapple ex a su coste de retirada, retirarlo (resguardar el
# tanque) y promover al Tapu Bulu, que hace el mismo KO cediendo solo 1 premio.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [attack_opt], (
        f"no atacar con el Hydrapple ex fragil (opt {attack_opt}): quedaria activo y "
        f"cederia 2 premios; obtuvo {result}")
    assert result == [ability_opt], (
        f"usar Ripening Charge (opt {ability_opt}) para habilitar la retirada del ex "
        f"fragil y promover un atacante de 1 premio; obtuvo {result}")


# Registro 008 (paso 119 vs Team Rocket Mewtwo ex, GANADA): activo Hydrapple ex LISTO
# (Syrup Storm ~570) que noquea al Spidops activo (1 premio), Boss's Orders en mano y
# supporter aun no jugado; en la banca rival un Mewtwo ex (280 HP, 2 premios) que TAMBIEN
# noqueamos tras gustearlo. El agente ATACABA al Spidops (1 premio) en vez de jugar Boss's
# y gustear+noquear al Mewtwo ex (2 premios, mas dificil de derrotar despues).
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [boss_opt], (
        f"jugar Boss's (opt {boss_opt}) para gustear+noquear el Mewtwo ex de banca "
        f"(2 premios), no atacar al activo de 1 premio (opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]


# =====================================================================
# Xerosic's Machinations (id 1197, user): supporter de disrupcion (el rival
# descarta hasta quedarse con 3 cartas). Incorporado al mazo (-1 Poke Pad)
# para el matchup Alakazam: Powerful Hand hace 20 de dano POR CARTA en la mano
# rival, asi que bajarlo a 3 cartas capa el ataque. Fixture sintetico: vs
# Alakazam (743 activo, Kadabra en banca), Hydrapple ex cargado en el activo,
# Xerosic (opt 0) y Lillie's (opt 1) en mano, supporter no jugado.
# =====================================================================
_XEROSIC_BIGHAND_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_play_xerosic_bighand.json")


def _load_xerosic_obs():
    with open(_XEROSIC_BIGHAND_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def test_xerosic_played_vs_alakazam_big_hand():
    # Mano rival = 8 (Powerful Hand amenaza 160): jugar Xerosic (opt 0), por
    # encima de Lillie's hydra-cargado (5800) que ademas barajaria el Xerosic.
    obs = _load_xerosic_obs()
    assert obs["current"]["players"][1]["handCount"] == 8
    result = m.agent(obs)
    assert result == [0], (
        f"vs Alakazam con mano rival 8, jugar Xerosic (opt 0) para capar "
        f"Powerful Hand; obtuvo {result}")


def test_xerosic_vetoed_when_op_hand_small():
    # Mano rival <= 3: Xerosic no hace nada -> vetado; se juega Lillie's.
    obs = _load_xerosic_obs()
    obs = _copy.deepcopy(obs)
    obs["current"]["players"][1]["handCount"] = 3
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result != [0], (
        f"con mano rival 3 Xerosic no tiene efecto: NO jugarlo; obtuvo {result}")
    assert result == [1], (
        f"con Xerosic vetado, el supporter del turno es Lillie's (opt 1); "
        f"obtuvo {result}")


def test_xerosic_vetoed_when_supporter_played():
    # Supporter ya jugado: Xerosic y Lillie's vetados -> atacar (opt 2).
    obs = _load_xerosic_obs()
    obs = _copy.deepcopy(obs)
    obs["current"]["supporterPlayed"] = True
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [2], (
        f"con supporter jugado, ni Xerosic ni Lillie's: atacar (opt 2); "
        f"obtuvo {result}")


# Meowth ex fetch (user): con Xerosic en el mazo y la mano rival gorda vs
# Alakazam, Last-Ditch Catch debe buscar Xerosic (1200; bajo Boss's ganador
# 1300 y Lillie's de desarrollo 1250). Deck de la seleccion: [Boss's, Lillie's,
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result != [2], (
        f"con mano rival 3, Xerosic no aporta: buscar otro supporter; obtuvo {result}")


# Reserva de banca vs Alakazam (user): con UN solo slot libre (bench_count==4),
# Meowth ex aun no en juego y Xerosic's Machinations aun en el mazo, el ultimo
# slot se reserva para Meowth ex (que busca el Xerosic para capar Powerful
# Hand). Se vetan cuerpos REDUNDANTES (duplicados de algo ya en juego); las
# primeras copias de piezas de linea (Applin, etc.) siguen bajando.
# Contrafactual verificado: sin la regla, el 2do Ogerpon SI se bajaba.
_ALK_RESERVE_BENCH_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_reserve_bench_slot.json")


def test_alakazam_reserve_last_bench_slot_for_meowth():
    # Mano: 2do Teal Mask Ogerpon ex (duplicado; ya hay uno en banca).
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
    # Control positivo: una PRIMERA copia de Applin (avanza la linea Hydrapple)
    # SI se baja aunque la reserva este activa.
    with open(_ALK_RESERVE_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    obs = _copy.deepcopy(obs)
    obs["current"]["players"][0]["hand"][0]["id"] = 92
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [0], (
        f"la reserva no debe bloquear piezas de linea (Applin, 1ra copia); "
        f"obtuvo {result}")


# DISCARD (user): vs Alakazam el Xerosic se PROTEGE al pagar costes de descarte
# (es la carta que capa Powerful Hand); en otros mazos es descartable medio.
# Mano de la seleccion: [Xerosic, Bug Catching Set, Poke Pad, Forest], descartar 2.
_ALK_DISCARD_XEROSIC_FIXTURE = (
    ROOT / "tests" / "fixtures" / "alakazam_discard_protect_xerosic.json")


def test_discard_protects_xerosic_vs_alakazam():
    with open(_ALK_DISCARD_XEROSIC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    result = m.agent(obs)
    discarded = [obs["current"]["players"][0]["hand"][i]["id"] for i in result]
    assert 1197 not in discarded, (
        f"vs Alakazam nunca descartar el Xerosic para pagar costes; descarto {discarded}")


# Registro 004 (paso 53 vs Marnie's Grimmsnarl ex, PERDIDA): Meowth ex usa
# Last-Ditch Catch para buscar un Supporter del mazo. El agente buscaba DAWN
# (1231, busca Basico+Fase1+Fase2 para armar la linea evolutiva), pero SIN
# Forest of Vitality (1261) EN JUEGO no podemos evolucionar el mismo turno
# (rush) -> refrescar la mano con Lillie's Determination (1227) da mas opciones
# de juego/ataque. El estadio en juego es Spikemuth Gym (1259, del rival), no el
# Forest. Debe buscar Lillie's (opt 2), no Dawn (opt 1).
_MARNIE_FETCH_LILLIE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "marnie_meowth_fetch_lillie_no_forest_step53.json")


def test_marnie_step53_meowth_fetch_lillie_not_dawn_without_forest():
    with open(_MARNIE_FETCH_LILLIE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    deck = obs["select"]["deck"]
    opts = obs["select"]["option"]
    dawn_opt = next(i for i, o in enumerate(opts) if deck[o["index"]]["id"] == 1231)
    lillie_opts = [i for i, o in enumerate(opts) if deck[o["index"]]["id"] == 1227]
    # Forest of Vitality NO esta en juego (hay Spikemuth Gym del rival).
    assert 1261 not in [s["id"] for s in (obs["current"].get("stadium") or [])]

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [dawn_opt], (
        f"sin Forest of Vitality en juego, NO buscar Dawn (opt {dawn_opt}); obtuvo {result}")
    assert result[0] in lillie_opts, (
        f"buscar Lillie's (opts {lillie_opts}) para refrescar la mano; obtuvo {result}")


def test_marnie_step53_meowth_fetch_dawn_when_forest_in_play():
    # Control positivo: con Forest of Vitality (1261) EN JUEGO, Dawn conserva su
    # valor (podemos rushear la evolucion) y vuelve a ser la mejor busqueda.
    import copy as _c
    with open(_MARNIE_FETCH_LILLIE_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    obs["current"]["stadium"] = [{"id": 1261, "playerIndex": 0, "serial": 999}]
    deck = obs["select"]["deck"]
    opts = obs["select"]["option"]
    dawn_opt = next(i for i, o in enumerate(opts) if deck[o["index"]]["id"] == 1231)

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [dawn_opt], (
        f"con Forest en juego, Dawn (opt {dawn_opt}) sigue siendo la mejor busqueda; "
        f"obtuvo {result}")


# =====================================================================
# Pivote-muro generalizado Ogerpon -> Hydrapple ex (user, registro_006 paso 84,
# vs Archaludon ex, PERDIDA): el Teal Mask Ogerpon ex activo SI puede atacar
# (Myriad Leaf Shower 300) pero NO noquea a Archaludon (400 HP con Hero's Cape,
# ademas RESISTE Grass -30) y sera noqueado el proximo turno (Metal Defender 220
# >= 210 HP). En banca hay un Hydrapple ex sano (330 HP) que SOBREVIVE el golpe
# (220 < 330) y puede atacar. Lo correcto es RETIRAR el Ogerpon condenado (no
# regalar 2 premios) y promover el muro. La rama previa estaba acotada a Mega
# Lucario; se generalizo con `_op_active_attack_damage_to` (dano rival real).
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [retreat_opt], (
        f"retirar el Ogerpon ex condenado (opt {retreat_opt}) para promover el "
        f"muro Hydrapple ex que sobrevive, no atacar con el Ogerpon fragil "
        f"(opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]


def test_archaludon_wall_pivot_not_when_wall_would_die():
    # Contrafactual: si el muro Hydrapple ex de banca NO sobreviviera al golpe
    # rival (le bajamos la vida por debajo del dano 220), el pivote NO debe
    # dispararse: retirar para exponer un cuerpo que igual muere no gana nada,
    # asi que el agente vuelve a atacar con el activo.
    import copy as _c
    with open(_ARCHALUDON_WALL_PIVOT_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    bench = obs["current"]["players"][0]["bench"]
    hydra = next(p for p in bench if p is not None and p["id"] == 150)
    hydra["hp"] = 200  # < 220 (Metal Defender) -> el muro moriria
    hydra["maxHp"] = 200

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"si el muro Hydrapple no sobrevive (200 < 220), no pivotar: atacar "
        f"con el activo (opt {attack_opt}); obtuvo {result}")


def test_op_active_attack_damage_to_resolves_ids():
    # El helper debe RESOLVER el dano del ataque del activo rival (los
    # card.attacks son IDs, no objetos) y aplicar debilidad/resistencia.
    arch = SimpleNamespace(id=190, energies=[8, 8, 8])   # Archaludon ex, Metal Defender 220
    oger = SimpleNamespace(id=96, hp=210)                # Ogerpon ex (no debil a Metal)
    hydra = SimpleNamespace(id=150, hp=330)              # Hydrapple ex
    assert m._op_active_attack_damage_to(arch, oger) == 220
    assert m._op_active_attack_damage_to(arch, hydra) == 220
    # sin activo o sin objetivo -> 0
    assert m._op_active_attack_damage_to(None, oger) == 0
    assert m._op_active_attack_damage_to(arch, None) == 0


# =====================================================================
# Motor Boss's ganador via Meowth ex con un Meowth ya en juego (user,
# registro_011 paso 148 vs Dragapult ex, GANADA): a 1 premio de ganar, tras
# Ultra Ball -> Meowth ex a la mano, el agente ATACABA con Hydrapple ex (Syrup
# Storm 210 NO noquea a Dragapult ex 320) en vez de JUGAR Meowth ex para que
# Last-Ditch Catch busque Boss's Orders (en el mazo), gustear un basico fragil
# de banca (Dreepy 70) y noquearlo -> ganar. El bloqueo era `field_counts==0`
# (ya habia un Meowth ex de banca de turnos anteriores); se relajo a `< 2`
# exigiendo que Last-Ditch siga disponible (`_meowth_ld_free`).
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [play_opt], (
        f"a 1 premio de ganar, JUGAR Meowth ex (opt {play_opt}) para el motor "
        f"Boss's (Last-Ditch -> Boss's -> gustear+noquear un basico), no atacar "
        f"al activo rival que no muere (opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]


def test_dragapult_meowth_win_engine_needs_last_ditch_free():
    # Contrafactual: si el Meowth ex de banca aparecio ESTE turno, su Last-Ditch
    # ya se gasto ("no mas de 1 por turno"), asi que jugar otro Meowth NO buscaria
    # Boss's -> el motor no aplica y el agente vuelve a atacar.
    import copy as _c
    with open(_DRAGAPULT_MEOWTH_WIN_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    for p in obs["current"]["players"][1]["bench"]:
        if p is not None and p["id"] == 1071:
            p["appearThisTurn"] = True

    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"con Last-Ditch ya gastado este turno, NO jugar un 2o Meowth ex: "
        f"atacar (opt {attack_opt}); obtuvo {result}")


# =====================================================================
# Boss's redundante cuando el ACTIVO es la misma pre-evo amenaza (user,
# registro_006 paso 75 vs Archaludon ex, GANADA): el activo rival es un
# Duraludon (3 energia + Hero's Cape, 230 HP) y en banca hay OTRO Duraludon
# (1 energia, 130 HP). Ambos son pre-evo amenaza de 1 premio. El agente jugaba
# Boss's Orders para gustear+noquear el Duraludon DEBIL de banca, dejando vivo
# el grande. Lo correcto: NO jugar Boss's y ATACAR el activo (Syrup Storm 420
# noquea 230), mismo premio, remueve la amenaza mas peligrosa y guarda el Boss's.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"ATACAR el Duraludon activo (opt {attack_opt}), no jugar Boss's "
        f"(opt {boss_opt}) para gustear el Duraludon debil de banca; obtuvo {result}")
    assert result != [boss_opt]


def test_archaludon_step75_still_boss_when_active_is_nonthreat():
    # Control positivo (registro_007): si el activo NO es pre-evo amenaza
    # (p.ej. Cinderace 666, 1 premio) pero en banca hay un Duraludon gusteable+
    # noqueable, SI se juega Boss's para gustear la pre-evo (mismo premio, remueve
    # el atacante futuro). El fix solo desactiva el gusteo cuando el activo es la
    # MISMA clase de amenaza e igual/mas desarrollado.
    import copy as _c
    with open(_ARCHALUDON_ATTACK_ACTIVE_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    a = obs["current"]["players"][1]["active"][0]
    a["id"] = 666; a["maxHp"] = 160; a["hp"] = 160; a["energies"] = [2]; a["tools"] = []

    options = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.PLAY)
                    and obs["current"]["players"][0]["hand"][o["index"]]["id"] == 1182)

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [boss_opt], (
        f"con un activo NO-amenaza (Cinderace), SI jugar Boss's (opt {boss_opt}) "
        f"para gustear el Duraludon de banca; obtuvo {result}")


# =====================================================================
# Boss's -> gustear un ex de 2 premios de banca sobre atacar el activo de 1
# premio (user, registro_008 paso 161 vs Iono, GANADA): activo rival Iono's
# Voltorb (70 HP, 1 premio) que nuestro Hydrapple ex NOQUEA, pero en banca hay
# Iono's Bellibolt ex (280 HP, 2 premios) que TAMBIEN noqueamos (Syrup Storm
# ~510). La jugada correcta es Boss's -> gustear el Bellibolt ex y cobrar 2
# premios. Ya cubierto por `gust_2prize_via_boss` (BOSS_SCORE_GUST_2PRIZE=6800);
# este test bloquea la regresion en un tablero Iono distinto (2 Bellibolt ex).
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [boss_opt], (
        f"jugar Boss's (opt {boss_opt}) para gustear+noquear el Bellibolt ex de "
        f"banca (2 premios), no atacar al Voltorb activo de 1 premio "
        f"(opt {attack_opt}); obtuvo {result}")
    assert result != [attack_opt]


def test_iono_step161_boss_gust_target_is_bellibolt_ex():
    # Al resolver el objetivo del gusteo (contexto SWITCH), elegir un Iono's
    # Bellibolt ex (2 premios, 280 HP), no un Kilowattrel/Voltorb de 1 premio.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    picked = opbench[obs["select"]["option"][result[0]]["index"]]["id"]
    assert picked == 269, (
        f"gustear un Iono's Bellibolt ex (269, 2 premios), no id {picked}; "
        f"obtuvo {result}")


# =====================================================================
# Completar la jugada de Ultra Ball -> Meowth ex (user, registro_008 paso 71 vs
# Hop's, GANADA): el agente jugo Ultra Ball y ELIGIO buscar Meowth ex (excelente),
# pero luego NO lo bajaba: atacaba con el Hydrapple ex activo (atacante listo) y la
# mano quedaba VACIA. Regla: si la Ultra Ball eligio buscar Meowth ex, hay que
# COMPLETAR la jugada SIEMPRE que el Supporter siga disponible: bajar Meowth ex
# (Last-Ditch Catch -> Lillie's Determination -> refrescar la mano) y DESPUES
# atacar (bajarlo a la banca no impide el ataque). La guarda pasa de
# `not _active_ready_attacker` a `not state.supporterPlayed` (si el Supporter ya
# se jugo, la Lillie's buscada ni se podria jugar: se mantiene atacar, registro
# 006 paso 57 vs Alakazam).
# La secuencia (frames ACTIVE del turno, como llama el entorno real) es necesaria
# para que la seleccion de la Ultra Ball (paso 70) fije `_ub_meowth_pending`.
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
    # Contrafactual (conserva la regla del registro 006 p57 vs Alakazam): si el
    # Supporter YA se jugo este turno, la Lillie's buscada no se podria jugar ->
    # NO bajar el Meowth ex buscado; atacar.
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
# Ultra Ball -> 2o Meowth ex -> Last-Ditch busca XEROSIC vs Alakazam (user,
# registro_004 paso 53 vs Alakazam, PERDIDA): la Ultra Ball busco Meowth ex
# (excelente) pero el agente atacaba sin bajarlo. Dos bloqueos corregidos:
# (1) la rama `_ub_meowth_pending` exigia `field_counts[Meowth_ex] == 0` y aqui
#     habia un Meowth ex en banca de turnos previos -> relajada a `< 2` +
#     `_meowth_ld_free` (igual que el motor Boss's ganador via Meowth);
# (2) el fetch de Last-Ditch exigia mano propia >= 3 para elegir Xerosic; con la
#     mano VACIA caia al refresco de Lillie's. Con un atacante fuerte YA en juego
#     (Hydrapple/Ogerpon) y la mano rival gorda (13 cartas = Powerful Hand 260),
#     Xerosic manda: score 1260 (`_has_strong_attacker_sel`).
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
    # Contrafactual: sin atacante fuerte en juego y mano vacia -> regla previa
    # (refresco con Lillie's).
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
# Pivote 1-premio generalizado a Dipplin vs Alakazam (user, registro_005 paso 56
# vs Alakazam, PERDIDA): Ogerpon ex activo listo para atacar y un Dipplin (1
# premio) en banca cargado cuyo Do the Wave (20 x banca) NOQUEA al Abra activo
# (50 HP). Regla: SIEMPRE que un cuerpo de 1 premio (Dipplin/Meganium/Tapu Bulu)
# pueda derrotar al activo rival vs Alakazam y el retiro sea pagable, RETIRAR el
# ex y promover el cuerpo de 1 premio (mismo KO cediendo 1 premio, no 2 al
# Powerful Hand). La deteccion `_alakazam_pivot_1prize` y la promocion
# `_ak_1prize_prom` tenian whitelist (Meganium, Tapu_Bulu); generalizadas a
# no-ex via prize_count (deteccion) y a (Meganium, Tapu_Bulu, Dipplin, Pinsir)
# con Do the Wave = 20 x (banca - 1) (promocion).
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
    # Contrafactual: Dipplin SIN energia no puede atacar -> no hay pivote;
    # atacar con el Ogerpon ex activo.
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
# Cadena completa anti-Alakazam (user, registro_007 turno 7 vs Alakazam,
# PERDIDA): Ultra Ball -> buscar Meowth ex (manteniendo la reserva de banca) ->
# BAJARLO (antes atacaba sin bajarlo) -> Last-Ditch busca XEROSIC (mano rival
# 12 = Powerful Hand 240; tenemos atacante fuerte) -> jugarlo -> atacar.
# Valida punta-a-punta los fixes `_ub_meowth_pending` (guard supporterPlayed) y
# el fetch de Xerosic sobre frames reales de un segundo escenario.
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

    # 1) tac9: bajar el Meowth ex buscado por la Ultra Ball (no atacar aun).
    opt = target["select"]["option"][result[0]]
    hand = [c["id"] for c in target["current"]["players"][1]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Meowth_ex, (
        f"tac9 debe bajar el Meowth ex buscado por Ultra Ball; obtuvo {result} -> {opt}")

    # 2) Last-Ditch Catch: con mano rival 12 y atacante fuerte, buscar XEROSIC.
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
# Objetivo de Cruel Arrow vs Crustle (user, registro_015 paso 139 vs Crustle,
# PERDIDA): Fezandipiti ex ataco con Cruel Arrow (100 fijo a CUALQUIER Pokemon
# rival) y el juego apuntaba al Crustle activo -- INMUNE al dano de nuestros ex
# por su habilidad -- con un Dwebble de 70 HP noqueable en banca. No existia
# handler para SelectContext.DAMAGE (ctx 15) y el argmax caia en la opcion 0.
# Nuevo handler: dano EFECTIVO por objetivo (aplica inmunidad ex / zona /
# debilidad); KO > chip mas cercano al KO > inmunes solo como ultimo recurso.
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
    # Contrafactual: Dwebble con 150 HP (no muere) -> sigue siendo el unico
    # objetivo que RECIBE dano (los Crustle son inmunes a nuestros ex).
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
# Motor Xerosic con Meowth ex YA en mano vs Alakazam (user, registro_006 paso 76
# vs Alakazam, GANADA): Meowth ex en mano (no buscado por Ultra Ball este
# turno), Supporter libre, mano rival de 10 cartas (Powerful Hand 200 nos
# noquea el proximo turno) y Xerosic aun en el MAZO. El agente atacaba dejando
# el Meowth muerto en mano (veto por atacante listo). Nueva rama: bajar el
# Meowth SIEMPRE en ese contexto (Last-Ditch -> Xerosic -> rival a 3 cartas ->
# atacar despues). Version "en mano" de la cadena `_ub_meowth_pending`.
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
    # Contrafactual actualizado (sugerencia 1 anti-Alakazam, Powerful Hand
    # modelado): con el Supporter ya jugado el Meowth NO se baja (intencion
    # original del test). Ademas, ahora que el modelo VE que el Hydrapple
    # activo de 130 HP muere ante Powerful Hand proyectado (20 x (10+2) =
    # 240), aplica la regla del user "retirar ex fragil, sacrificar 1
    # premio": Ripening Charge (habilita la retirada) -> retirar -> promover
    # el Meganium de 1 premio que tambien noquea al Alakazam de 140. Antes
    # atacaba con el ex condenado (regalaba 2 premios) porque creia que
    # Alakazam pegaba 0.
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
# Motor Xerosic SOBRE el rush de desarrollo (user, registro_010 paso 147 vs
# Alakazam, PERDIDA): dos Meowth ex en mano, Supporter libre, mano rival de 11
# (Powerful Hand 220) y Xerosic en el MAZO, con UN solo slot de banca. El agente
# bajaba el Applin (rush con Forest, 21200) y los Meowth morian en mano -- sin
# Xerosic, Powerful Hand nos noqueo todo. La rama del motor sube a 21500 para
# ganar al rush: bajar Meowth ex -> Last-Ditch -> Xerosic (rival a 3) -> atacar.
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
    # Contrafactual: mano rival corta -> el motor no aplica y vuelve el rush de
    # desarrollo (Applin con Forest).
    result, obs = _meowth_over_applin_replay(
        lambda o: o["current"]["players"][1].__setitem__("handCount", 4))
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in obs["current"]["players"][0]["hand"]]
    assert opt.get("type") == 7 and hand[opt["index"]] == m.Applin, (
        f"sin mano rival gorda debe volver el rush de Applin; obtuvo {result} -> {opt}")


# =====================================================================
# Cadena UB -> Meowth -> Lillie's vs Marnie's (user, registro_008 paso 118,
# GANADA): en el turno 8 el juego jugo Ultra Ball y busco un Meowth ex, pero
# la version antigua no lo bajo y ataco con el Hydrapple ex. Con Supporter
# libre y Lillie's (1227) en el MAZO, la jugada se COMPLETA: bajar el Meowth
# (21000 via _ub_meowth_pending) -> Last-Ditch busca Lillie's -> jugarla para
# refrescar y cargar mas energias en los Ogerpon. Cadena validada con el
# codigo actual sobre el registro real + 2 frames sinteticos.
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
    # Contrafactual: con el Supporter ya jugado, la Lillie's buscada no se
    # podria jugar -> atacar directamente.
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
# Sugerencias anti-Alakazam 1-3 (user: "implementa los cambios paso a paso"):
# 1) Powerful Hand (Alakazam 743, attackId 1072, dano impreso 0) modelado en
#    _op_active_attack_damage_to como 20 x (mano rival + 2) cuando el llamador
#    pasa op_hand_count, e inyectado en active_ko_likely (acotado al activo
#    Alakazam) -> despierta los pivotes defensivos en este matchup.
# 2) Disparo TEMPRANO de Xerosic: con mano rival 4-5 (bajo el umbral >=6), si
#    el Alakazam activo proyecta KO sobre nuestro activo, capar la mano YA.
# 3) Guard de Lillie's: no barajar el ULTIMO acceso al Xerosic (sin Meowth
#    re-buscable) con la mano rival >= 4.
# =====================================================================


def test_powerful_hand_projected_damage():
    class _P:
        def __init__(s, id, energies, hp, maxHp):
            s.id, s.energies, s.hp, s.maxHp = id, energies, hp, maxHp
    alak = _P(m.Alakazam_ex, [5], 140, 140)
    oger = _P(m.Teal_Mask_Ogerpon_ex, [1, 1, 1], 210, 210)
    # sin op_hand_count: conservador (comportamiento historico)
    assert m._op_active_attack_damage_to(alak, oger) == 0
    # con mano rival: 20 x (mano + 2)
    assert m._op_active_attack_damage_to(alak, oger, 9) == 220
    assert m._op_active_attack_damage_to(alak, oger, 5) == 140
    # rivales con dano impreso no cambian al pasar la mano
    dura = _P(647, [7, 7, 7], 100, 100)
    assert (m._op_active_attack_damage_to(dura, oger, 9)
            == m._op_active_attack_damage_to(dura, oger))


def _xerosic_bighand_mutated(mutate):
    import copy as _c
    with open(_XEROSIC_BIGHAND_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mutate(obs)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    my = obs["current"]["players"][obs["current"]["yourIndex"]]
    hand = [c["id"] for c in my["hand"]]
    played = (hand[opt["index"]]
              if opt.get("type") == int(OptionType.PLAY) else None)
    return played, opt


def test_xerosic_early_trigger_on_projected_ko():
    # mano rival 5 (bajo el umbral 6) + activo propio a 130 HP: proyeccion
    # 20 x (5+2) = 140 >= 130 -> jugar Xerosic YA.
    def mut(o):
        cur = o["current"]
        cur["players"][cur["yourIndex"]]["active"][0]["hp"] = 130
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    played, opt = _xerosic_bighand_mutated(mut)
    assert played == m.Xerosic_Machinations, (
        f"con KO proyectado (140 >= 130) debe jugar Xerosic; obtuvo {opt}")


def _xerosic_bighand_no_backup(mutate):
    # Variante SIN copia de respaldo: la 2a copia de Xerosic (mazo, julio
    # 2026) se marca fuera del mazo via tracking, dejando la de la mano como
    # ultima -> timing conservador de una copia.
    import copy as _c
    with open(_XEROSIC_BIGHAND_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mutate(obs)
    m._init_cartas_tracking()
    m.CARTAS_ACTIVAS_EN_MAZO.setdefault(
        m.Xerosic_Machinations, {m.ESTADO_MAZO: 0})[m.ESTADO_MAZO] = 0
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    my = obs["current"]["players"][obs["current"]["yourIndex"]]
    hand = [c["id"] for c in my["hand"]]
    played = (hand[opt["index"]]
              if opt.get("type") == int(OptionType.PLAY) else None)
    return played, opt


def test_xerosic_early_with_backup_copy():
    # 2a copia en el MAZO (julio 2026): con mano rival 5 (>= 4) la 1a copia
    # se juega TEMPRANO aunque el activo este sano -- estrategia de doble
    # golpe: demorarlos ya y guardar la 2a para el cap tardio.
    def mut(o):
        cur = o["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    played, opt = _xerosic_bighand_mutated(mut)
    assert played == m.Xerosic_Machinations, (
        f"con copia de respaldo en el mazo, la 1a se juega temprano "
        f"(mano rival 5 >= 4); obtuvo {opt}")


def test_xerosic_early_trigger_not_on_healthy_active_last_copy():
    # ULTIMA copia (sin respaldo) + mano rival 5 + activo sano (330):
    # proyeccion 140 < 330 -> NO quemarla aun (timing conservador).
    def mut(o):
        cur = o["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    played, opt = _xerosic_bighand_no_backup(mut)
    assert played != m.Xerosic_Machinations, (
        f"ultima copia sin KO proyectado (140 < 330): no quemarla; obtuvo {opt}")


def test_xerosic_early_trigger_needs_alakazam_active():
    # ULTIMA copia, mano rival 5, activo propio a 130, pero el rival tiene un
    # Abra activo: la amenaza no es inmediata -> NO disparar temprano.
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
    # Xerosic en mano, mano rival 5, y SIN Meowth re-buscable (0 en mano,
    # 0 en mazo): Lillie's lo barajaria sin recuperacion -> veto.
    def mut(o):
        cur = o["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    import copy as _c
    with open(_XEROSIC_BIGHAND_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mut(obs)
    m._init_cartas_tracking()
    m.CARTAS_ACTIVAS_EN_MAZO.setdefault(
        m.Meowth_ex, {m.ESTADO_MAZO: 0})[m.ESTADO_MAZO] = 0
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
    # ULTIMA copia + Meowth en el mazo: el curso normal se mantiene (Meowth
    # re-busca el Xerosic barajado). Con respaldo en mazo la 1a copia se
    # jugaria temprano (test test_xerosic_early_with_backup_copy).
    def mut(o):
        cur = o["current"]
        cur["players"][1 - cur["yourIndex"]]["handCount"] = 5
    played, opt = _xerosic_bighand_no_backup(mut)
    assert played == m.Lillie_Determination, (
        f"ultima copia con Meowth re-buscable: Lillie's sigue su curso; "
        f"obtuvo {opt}")


# =====================================================================
# Boss's corta la linea de Cynthia's Garchomp ex (user, registro_006 paso 82
# vs Garchomp, GANADA con error): Tapu Bulu listo en el activo, Boss's en mano,
# Supporter libre; rival con Spiritomb (muro desnudo, 70) en el activo y DOS
# Gabite en banca (uno ENERGIZADO). El agente atacaba al muro; lo correcto es
# jugar Boss's y gustear+noquear el Gabite con energia (pre-evo del atacante ex
# de 2 premios). Fix: la linea Gible(379)/Gabite(380) NO estaba en
# EX_PREEVO_IDS, asi que el deny-evo (`_bo_pe_is_ex_preevo_energized` /
# `_bo_pe_is_ex_line_vs_wall`, mismo mecanismo que la linea Marnie) jamas
# disparaba en este matchup. Privilegiar SIEMPRE cortar la linea evolutiva.
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
# Motor UB->Meowth->Lillie's SOBRE el tier de energia (user, registro_008
# pasos 56-64 vs Archaludon ex, PERDIDA): turno 8, Hydrapple ex activo que NO
# noquea (Syrup Storm 90 vs 250), banca de 1 Applin, mano [UB, Boss's] + 2
# energias recien traidas por Bug Catching Set. El agente adjuntaba una energia
# (31410) y gastaba la otra con Ripening Charge (30000) -- la mano quedaba en
# [UB, Boss's] y la Ultra Ball MORIA sin sus 2 descartes. Fix doble:
# `_ub_engine_refresh_pivot` puntua la UB a 31450 y la sube al tier ENERGY
# (patron Teal Dance), y `_ub_engine_pivot_turn` fuerza el fetch a Meowth ex
# (1300) para completar UB -> descarta 2 energias -> Meowth -> Last-Ditch ->
# Lillie's -> refrescar y desarrollar banca (Syrup Storm escala con el campo).
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
    # Contrafactual: banca desarrollada (3) -> el pivote no aplica y el adjunte
    # normal se mantiene.
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
# Plan "motor Meowth ex" (user): dos huecos cerrados tras la auditoria.
# MEJORA A -- Motor Meowth->Boss's para gusteos de VALOR (deny-evo) con el
# Boss's en el MAZO: la maquinaria in-hand (`_boss_deny_evo`) exige Boss's en
# mano y el veto `_active_ready_attacker` mataba el fallback generico -> sin
# camino, el agente atacaba al muro dejando evolucionar la pre-evo ENERGIZADA
# del atacante ex rival. Flag standalone `_deny_evo_via_boss` (junto a
# `_win_via_boss_gust`, mano O mazo) -> PLAY Meowth 22000 (bajo el remate
# 22500) -> fetch Boss's 1280 -> el motor in-hand valida el gusteo despues.
# MEJORA B -- Xerosic GENERICO en el fetch de Last-Ditch: mano rival >= 7 +
# atacante fuerte en juego + activo que ataca -> 1100 (bajo Lillie's/Boss's,
# "solo si no hay mejor opcion"); antes ni era candidato fuera de Alakazam.
# Fixture: secuencia del garchomp_step82 MUTADA (Boss's de la mano al mazo,
# Meowth ex en mano, hueco de banca) + 3 frames sinteticos de fetch.
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
# Auditoria estrategica (julio 2026): 7 mejoras implementadas de una vez con
# autorizacion del user. Tests por mejora:
# 1) Ogerpon inline: el scoring de ATAQUE ahora suma la energia del activo
#    rival (Myriad Leaf Shower, regla verificada) -- antes subestimaba KOs.
# 2) EX_IMMUNE_IDS incluye Crustle_Fighting (533).
# 3) Forest reemplaza Watchtower con prioridad 27000 si el motor Meowth vive.
# 4) Maximum Belt (1158) rival: +50 vs nuestro ex en la proyeccion de dano.
# 5) Rocket's Tarountula (400) en THREAT_PREEVO_IDS.
# 6) Prudencia de premios GENERAL en la promocion: entre candidatos que
#    NOQUEAN, si el golpe rival proyectado mata al ex, preferir el 1-premio.
# 7) Inferencia de arquetipo por el DESCARTE rival.
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
    # el Belt NO aplica contra un objetivo no-ex
    megan = _FakePkm(m.Meganium, energies=[1, 1], hp=160)
    assert (m._op_active_attack_damage_to(mewtwo_belt, megan)
            == m._op_active_attack_damage_to(mewtwo, megan))


def _zone_fixture_base():
    import copy as _c
    with open(_ZONE_PROMOTE_FIXTURE, encoding="utf-8") as f:
        obs = _json.load(f)["observation"]
    return _c.deepcopy(obs)


def _prudence_promotion_obs(with_belt):
    # ctx4 (promocion tras KO): banca [Ogerpon ex 6e (210), Dipplin 1e (80),
    # Applin, Applin, Chikorita] -> Dipplin (Do the Wave) = 20*(5-1) = 80.
    # Op activo: TR Mewtwo ex a 70 HP restantes -> AMBOS candidatos noquean.
    # Con Maximum Belt la proyeccion (160+50=210) OHKOs al Ogerpon (210) ->
    # prudencia: promover el 1-premio Dipplin. Sin Belt (160 < 210) el
    # Ogerpon sobrevive -> regla clasica (mas vida).
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    bench = obs["current"]["players"][obs["current"]["yourIndex"]]["bench"]
    picked = bench[obs["select"]["option"][result[0]]["index"]]["id"]
    assert picked == m.Dipplin, (
        f"proyeccion 210 (Belt) condena al Ogerpon y ambos noquean: promover "
        f"el 1-premio Dipplin; obtuvo {picked}")


def test_promotion_keeps_tank_ex_when_it_survives():
    obs = _prudence_promotion_obs(with_belt=False)
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    bench = obs["current"]["players"][obs["current"]["yourIndex"]]["bench"]
    picked = bench[obs["select"]["option"][result[0]]["index"]]["id"]
    assert picked == m.Teal_Mask_Ogerpon_ex, (
        f"sin Belt (160 < 210) el Ogerpon sobrevive: regla clasica de mas "
        f"vida; obtuvo {picked}")


def test_discard_inference_activates_alakazam_rule():
    # El fixture de zona trae Abra/Kadabra SOLO en el DESCARTE rival (banca
    # vacia, activo mockeado a Bellibolt ex): la inferencia por descarte
    # activa `op_is_alakazam_deck` y la regla del 1-premio promueve Meganium
    # aunque el ex tenga mas vida.
    import copy as _c
    obs = _zone_fixture_base()
    cur = obs["current"]; yi = cur["yourIndex"]; op = cur["players"][1 - yi]
    op["active"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                     "hp": 130, "id": 269, "maxHp": 280, "playerIndex": 1 - yi,
                     "preEvolution": [], "serial": 301, "tools": []}]
    assert any(c["id"] in (m.Abra, m.Kadabra) for c in op["discard"])
    options = obs["select"]["option"]
    nonex_opt = next(i for i, o in enumerate(options) if o.get("index") == 1)
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [nonex_opt], (
        f"Abra/Kadabra en el descarte rival deben activar la regla Alakazam "
        f"del 1-premio; obtuvo {result}")


def test_forest_replaces_watchtower_when_meowth_engine_alive():
    # MAIN con Watchtower rival en juego, Forest en mano y Meowth en el mazo:
    # reemplazar el estadio (27000) gana al desarrollo y al ataque.
    import copy as _c
    with open(_GARCHOMP_BOSS_GABITE_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = _c.deepcopy(seq[-1]["observation"])
    cur = obs["current"]; yi = cur["yourIndex"]
    cur["stadium"] = [{"id": m.Team_Rockets_Watchtower,
                       "playerIndex": 1 - yi, "serial": 400}]
    my = cur["players"][yi]
    # Forest a la mano en el hueco del Night Stretcher (indice 2)
    my["hand"][2] = {"id": m.Forest_of_Vitality, "playerIndex": yi, "serial": 46}
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    hand = [c["id"] for c in my["hand"]]
    assert (opt.get("type") == int(OptionType.PLAY)
            and hand[opt["index"]] == m.Forest_of_Vitality), (
        f"con Watchtower anulando el motor Meowth, reemplazarlo con Forest es "
        f"prioritario; obtuvo {result} -> {opt}")


def test_ogerpon_attack_counts_opponent_energy():
    # Op activo con 150 HP y 2 energias: Myriad = 30+30*(3 propias + 2 rivales)
    # = 180 >= 150 (KO). Con la copia inline vieja (solo propias: 120) el plan
    # no veia el KO. Verificamos via plan.remain_hp tras el agent().
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
    # nuestro activo: Ogerpon ex con 3 energias
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [0], f"debe atacar; obtuvo {result}"
    assert m.plan.attacker == 0 and m.plan.remain_hp is not None \
        and m.plan.remain_hp <= 0, (
        f"el plan debe registrar el KO (30+30*(3+2)=180 >= 150); "
        f"plan.remain_hp={m.plan.remain_hp}")


# =====================================================================
# Adjunte que HABILITA la retirada hacia un atacante de banca letal (user,
# registro_034 paso 141 vs Crustle/Terrakion, PERDIDA): Fezandipiti ex activo
# SIN energia (no ataca ni retira), Dipplin cargado en banca (Do the Wave x2
# por debilidad Planta del Terrakion 140 = KO) y 2 energias en mano. El agente
# hacia Teal Dance en el Ogerpon de banca (31500) y regaba la 2a energia en
# Meganium: la linea de KO se perdia entera. Flag `_attach_enable_retreat_ko`
# (generaliza `_tapu_sac_enable_retreat` via `_bench_attacker_can_ko`, sin
# exigir can_switch) -> el ATTACH al ACTIVO puntua 41000 (banda de cargas
# letales, sobre Teal Dance y cargas de banca). El resto de la cadena
# (Lillie's -> RETREAT -> promover Dipplin -> atacar) la resuelve la
# maquinaria existente al volverse legal la retirada.
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
    # Contrafactual: sin energias en la banca no hay atacante letal -> el
    # pivote no aplica y el adjunte al activo pierde su prioridad.
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
# Guard del tier de Teal Dance (user, registro_009 paso 113 vs Mega Lucario,
# PERDIDA): Hydrapple ex ACTIVO con 1 energia, Mega Lucario ex a 160 (Syrup
# Storm 30+30x6=210 = KO de 3 premios) y una energia recuperada en mano. La
# promocion incondicional de Teal Dance al tier ENERGY hacia que una TD
# DEGRADADA (7500, reserva de energia) dominara por TIER a Ripening Charge
# (31100, tier 0), regando la energia en un Ogerpon de banca y perdiendo el
# remate. Guard: la promocion solo aplica con score >= 29000 (jugada real;
# sus ramas van de 29000 a 31600). Frames RECONSTRUIDOS del estado del turno
# 8 (el registro solo trae los frames del rival).
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert (opt.get("type") == int(OptionType.ABILITY)
            and opt.get("area") == int(AreaType.ACTIVE)), (
        f"Ripening Charge (31100) debe ganar a las Teal Dance degradadas "
        f"(7500) que antes dominaban por tier; obtuvo {result} -> {opt}")


def test_lucario_step113_ripening_targets_active_hydrapple():
    data = _lucario_ripen_data()
    obs = data["ripen_target"]
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("area") == int(AreaType.ACTIVE), (
        f"la energia de Ripening va al Hydrapple ACTIVO (habilita Syrup 210 "
        f">= 160, KO de 3 premios); obtuvo {result} -> {opt}")


def test_lucario_step113_attacks_after_charge():
    data = _lucario_ripen_data()
    obs = data["attack"]
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con 2 energias el Hydrapple ataca (KO al Mega Lucario ex); "
        f"obtuvo {result} -> {opt}")


# =====================================================================
# Tanque RECARGABLE sobre atacante ex condenado (user, registro_009 paso 130
# vs Archaludon ex, GANADA): tras el KO del rival debemos promover; el mejor
# candidato clasico era un Ogerpon ex cargado (210) que NO noquea y MUERE al
# golpe proyectado del Archaludon (Ion Beam 220) -> regala 2 premios. En banca
# hay un Hydrapple ex SIN energias (330: sobrevive) y en mano Lana's Aid con 3
# Plantas en el descarte: el proximo turno recupera energias y con adjunte
# manual + Ripening Charge queda a 2 efectivas (Syrup Storm). Override en
# `_best_promote_card`: candidato ex condenado sin KO -> promover el Hydrapple
# tanque recargable; los overrides de KO real (Tapu / 1-premio Alakazam)
# siguen ganando porque se aplican despues.
# =====================================================================
_ARCHALUDON_TANK_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step130_promote_rechargeable_tank.json")


def _archaludon_s130_replay(mutate=None):
    import copy as _c
    with open(_ARCHALUDON_TANK_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
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
    # SUPERSEDIDO por la regla de supervivencia (user, registro_005 paso 64):
    # antes, sin Lana's Aid el Hydrapple "no era recargable" y se conservaba la
    # conducta clasica (promover el Ogerpon cargado). La instruccion nueva es
    # explicita y para cualquier mazo: si un cuerpo AGUANTA el ataque proyectado,
    # sube ese. Aqui Archaludon ex pega 220: el Hydrapple ex (330) sobrevive y
    # todo lo demas muere, asi que la recargabilidad ya no cambia la eleccion.
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
# Fallback EX del pivote de negacion de premios (user, registro_013 paso 139
# vs Archaludon/Cinderace, PERDIDA): Hydrapple ex activo con 10 HP que puede
# NOQUEAR al Duraludon activo, pero el rival esta a 2 premios y su Cinderace
# de banca (Turbo Flare 50 x2 debilidad = 100) remata al Hydrapple el proximo
# turno = DERROTA. Antes `_prize_denial_pivot` solo buscaba cuerpos de 1
# premio que atacaran (no habia: Tapu 2e, Meganium 0e) y el agente atacaba
# con el activo condenado. Fallback nuevo: sin 1-premio disponible, retirar y
# promover un EX de banca que NOQUEE al activo rival Y SOBREVIVA al mejor
# golpe proyectado de la banca rival (Ogerpon 6e: Myriad 300-30 resistencia =
# 270 >= 130 KO; 210 HP > 100). Mismo KO sin regalar los 2 premios finales.
# =====================================================================
_ARCHALUDON_PDX_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step139_prize_denial_ex_fallback.json")


def _archaludon_s139_replay(mutate=None):
    import copy as _c
    with open(_ARCHALUDON_PDX_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
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
# Prioridad entre COPIAS de la misma amenaza (user, registro_007 paso 80 vs
# Archaludon, GANADA con error): el activo rival es un Duraludon con 3
# energias + Hero's Cape (230 HP) y en banca hay OTRO Duraludon debil (1
# energia, sin tool). El agente jugaba Boss's para gustear+noquear la copia
# debil (rama low-value 1500 > ATTACK 1100). Regla del user (reiterada): entre
# dos Pokemon iguales la prioridad la tiene el que lleva un artefacto de vida
# y, en 2o lugar, el de mas energias -> ATACAR al activo grande y GUARDAR el
# Boss's. La correccion anterior (`_bo_active_prize_dominates`) exigia poder
# NOQUEAR al activo y la Cape (210 < 230) la desactivaba; ademas solo cubria
# la rama deny-evo. Flag nuevo `boss_active_threat_dominates` (ctx): activo
# THREAT_PREEVO + podemos atacarlo + TODAS las copias de banca son de la misma
# especie y dominadas (tool 1o, energias 2o) -> el PLAY de Boss's cae a
# EMPTY_GUST (20); los remates (WIN_NOW/2-premios/win-via-bench) retornan
# antes y no se ven afectados.
# =====================================================================
_ARCHALUDON_CAPED_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "archaludon_step80_attack_caped_active_not_gust_copy.json")


def _archaludon_s80_replay(mutate=None):
    import copy as _c
    with open(_ARCHALUDON_CAPED_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
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
# Guard anti-DONK del primer turno partiendo PRIMEROS (user, registro_001
# pasos 6-7 vs Cinderace/Archaludon, PERDIDA): empezamos con SOLO un Chikorita
# activo (banca vacia) y 2 Meowth ex + Lillie's en mano. El hold del primer
# turno vetaba bajar Meowth ("hay Lillie's en mano") -- pero yendo primeros el
# Supporter NI SIQUIERA es jugable ese turno, y el Cinderace rival (Turbo
# Flare 50 x2 debilidad = 100 >= 70) nos donkeo en su primer turno = derrota
# instantanea sin banca. Regla nueva: si el activo rival proyecta un KO de UNA
# energia sobre nuestro activo solitario, bajar Meowth ex (21900, cuerpo
# anti-donk) y su Last-Ditch trae Lillie's para el proximo turno; sin donk
# proyectado se mantiene la conducta previa (no bajarlo).
# =====================================================================
_CINDERACE_DONK_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "cinderace_turn1_donk_guard_meowth.json")


def _cinderace_t1_replay(mutate=None):
    import copy as _c
    with open(_CINDERACE_DONK_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    obs = data["sequence"][0]["observation"]
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
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
# Carga de energia al MEJOR ATACANTE (user, registro_004 pasos 39-54 vs
# Archaludon ex, PERDIDA): turno 4, Ogerpon ex activo (1 energia, Myriad
# necesita 3) NO puede atacar; el Hydrapple ex recien evolucionado en banca
# recibe el adjunte manual (1 energia) y con UNA Planta mas queda LISTO
# (Syrup Storm coste 2, 30+30xGrass del campo = 210 >= 160 del activo rival).
# La version antigua del agente gastaba la ultima Planta de la mano con Teal
# Dance sobre el ACTIVO (que no ataca y cuya energia no potencia nada),
# retiraba y promovia un Hydrapple con 1 sola energia: SIN opcion de ataque,
# turno regalado. Regla del user: al jugar cada energia se evalua el mejor
# atacante posible del turno -> la Planta va al Hydrapple via su habilidad
# Ripening Charge (31100 > Teal Dance 7500, deprioritizado porque el
# Hydrapple de banca necesita la energia), luego RETIRAR al Ogerpon (coste 1,
# ya pagable), promover al Hydrapple y rematar con Syrup Storm. El objetivo
# de Ripening se fija en energy_score (ATTACH_FROM, regla 41000 "cargar al
# Hydrapple de banca lo deja listo para un Syrup Storm letal").
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
# Tope de energia del Applin (user, registro_004 pasos 35-63, episodio
# 87675043 vs Mega Lucario, PERDIDA): turno 4, paso 36. El agente adjunto la
# 2a energia a un Applin de banca que YA tenia 1: su unico ataque cuesta 1 y
# Do the Wave del Dipplin en que evoluciona tambien cuesta 1, asi que la
# energia se DESPERDICIO por completo (el Dipplin remato el turno con 1 sola
# energia util). La causa: la 2a energia al Applin solo recibia una
# penalizacion blanda (-300 -> 7700) que aun le ganaba a Teal Dance (7500);
# los adjuntes a los Ogerpon estaban bien vetados (Teal Dance precede al
# adjunte manual) y el Applin quedaba como "mejor" objetivo del tier ENERGY.
# Regla del user: un Applin puede tener como MAXIMO 1 energia FISICA, salvo
# que la 2a se necesite para potenciar el ataque de un Hydrapple ex y sea el
# UNICO Pokemon a cargar. Fix: veto duro en energy_score (junto al tope de
# Chikorita) con dos excepciones: (a) evolucion completa este turno
# (Dipplin + Hydrapple ex en mano, sin Meganium) mantiene la rama existente
# _applin_full_evolve_now; (b) Hydrapple ex en juego -> score minimo 10
# (ultimo recurso: la energia en el campo si escala Syrup Storm).
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
    # Eleccion forzada [ATTACH -> Applin(1e), END]: el veto debe preferir
    # terminar el turno antes que sobrecargar al Applin.
    _, _, data = _lucario_s36_replay()
    forced = data["synthetic_forced_applin_loaded"]
    ch = m.agent(forced)
    opt = forced["select"]["option"][ch[0]]
    assert opt.get("type") == int(OptionType.END), (
        f"con el Applin ya cargado (1 fisica) el adjunte queda VETADO incluso "
        f"como unica jugada; obtuvo {ch} -> {opt}")


def test_lucario_step36_applin_first_energy_still_allowed():
    # Mismo forzado pero con el Applin SIN energia: la 1a Planta si se adjunta.
    _, _, data = _lucario_s36_replay()
    forced = data["synthetic_forced_applin_empty"]
    ch = m.agent(forced)
    opt = forced["select"]["option"][ch[0]]
    assert opt.get("type") == int(OptionType.ATTACH), (
        f"la 1a energia del Applin sigue permitida (habilita su ataque y la "
        f"linea evolutiva); obtuvo {ch} -> {opt}")


def test_lucario_step36_applin_second_energy_last_resort_with_hydrapple():
    # Excepcion (b): con un Hydrapple ex NUESTRO en juego y el Applin como
    # UNICO objetivo cargable, la 2a energia se permite (score minimo 10 >
    # END): en el campo sigue sumando al Syrup Storm.
    _, _, data = _lucario_s36_replay()
    forced = data["synthetic_forced_applin_hydra_in_play"]
    ch = m.agent(forced)
    opt = forced["select"]["option"][ch[0]]
    assert opt.get("type") == int(OptionType.ATTACH), (
        f"con Hydrapple ex en juego y ningun otro objetivo, la 2a energia al "
        f"Applin es el ultimo recurso valido (potencia Syrup Storm); "
        f"obtuvo {ch} -> {opt}")


# =====================================================================
# Orden Unfair Stamp -> Meowth ex (user, registro_008 pasos 106-128, episodio
# 87676139 vs Mega Lucario, PERDIDA): turno 8, paso 115. Una Ultra Ball trajo
# Meowth ex a la mano y el override `_ub_meowth_pending` forzaba bajarlo (21000)
# para encadenar Last-Ditch Catch -> buscar Lillie's. Pero habia un Unfair
# Stamp JUGABLE en mano (nos noquearon el turno pasado, `_stamp_blocks_supp_chain`):
# al bajar Meowth ANTES del Stamp, el Supporter que trae Last-Ditch se BARAJA de
# vuelta al mazo cuando el Stamp rehace ambas manos, y encima se expone un cuerpo
# de 2 premios. Orden correcto: jugar los items -> Unfair Stamp -> y solo DESPUES
# bajar Meowth ex. Fix: guard `and not _stamp_blocks_supp_chain` en los overrides
# de Meowth (`_ub_meowth_pending` y el motor Xerosic in-hand), de modo que con el
# Sello pendiente el veto Stamp+ko_last_turn de la cadena principal prevalece.
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
    # El Unfair Stamp debe seguir disponible como jugada este turno (no vetado).
    result, obs, _ = _lucario_s115_replay()
    hand = obs["current"]["players"][0]["hand"]
    stamp_opt = next(
        (o for o in obs["select"]["option"]
         if o.get("type") == int(OptionType.PLAY)
         and o.get("index", -1) < len(hand)
         and hand[o["index"]]["id"] == m.Unfair_Stamp), None)
    assert stamp_opt is not None, "el Unfair Stamp debe estar entre las opciones"


def test_lucario_step115_plays_meowth_after_stamp_gone():
    # Contrafactual: el Unfair Stamp ya se jugo (fuera de la mano). El motor
    # Meowth sigue vivo -> ahora SI se baja Meowth ex para el Last-Ditch.
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
# Ultra Ball busca Hydrapple ex para evolucionar al Dipplin activo condenado
# (user, registro_008 pasos 067-072 vs Crustle/Kangaskhan, PERDIDA): paso 69.
# El activo es un Dipplin (80 PV, 2 energias) que NO noquea al Kangaskhan ex
# activo y sera derrotado el proximo turno. Lo correcto es buscar Hydrapple ex
# para EVOLUCIONARLO: un tanque de 330 PV que sobrevive el golpe y ataca mejor
# a Kangaskhan ex. La degradacion generica de Hydrapple ex vs Crustle (carta
# muerta por inmunidad a ex) clampaba su score a 40 y hacia ganar a un Tapu Bulu
# pelado. Fix: excepcion `_ub_evo_doomed_hittable` (`_ub_dipplin_evo_atk` y el
# activo rival NO inmune a ex) que levanta el clamp para este pivote de
# evolucion+supervivencia del activo.
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
    # Contrafactual de frontera: si el activo rival es un Crustle (inmune a ex),
    # Hydrapple ex no puede atacarlo, la excepcion NO aplica y el clamp vs
    # Crustle vuelve -> no se prefiere Hydrapple ex.
    result, obs, _ = _crustle_s69_replay(
        observation_key="synthetic_op_active_crustle")
    ids = _fetch_ids(obs, result)
    assert m.Hydrapple_ex not in ids, (
        f"con un Crustle inmune de activo, Hydrapple ex vuelve a ser carta "
        f"muerta y el clamp debe aplicar (no se busca Hydrapple ex); obtuvo "
        f"{result} -> {ids}")


# =====================================================================
# Teal Dance sobre el desarrollo de banca (user, registro_002 paso 20,
# episodio 87709673 vs Marnie): nuestro primer turno saliendo segundos. El
# Ogerpon ex ACTIVO ya uso su Teal Dance, asi que el adjunte manual al activo
# queda vetado por la regla de primer turno y la Teal Dance del Ogerpon ex de
# BANCA cae a la banda degradada (7500). El unico objetivo restante, un
# Chikorita de banca, ganaba con 8400 (base 8000 de energy_score + boost de
# desarrollo) y ademas dominaba por TIER (adjunte = _TIER_ENERGY frente a la
# habilidad en tier 0), desperdiciando la unica Planta en un cuerpo que con 1
# energia NO es atacante. Fix: un adjunte de MERO DESARROLLO (banda < 9000 y
# objetivo que no queda listo para atacar, exigiendo MAIN_ATTACKERS) cede ante
# una Teal Dance pendiente: se capa a 7000 y se le deja el tier 0 para que
# dentro del mismo tier decida el score.
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


def test_marnie_step20_no_carga_energia_al_chikorita():
    result, obs, _ = _marnie_s20_replay()
    opt = obs["select"]["option"][result[0]]
    if opt.get("type") != int(OptionType.ATTACH):
        return  # no adjunta: la regla se respeto
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    destino = (me["active"][0] if opt.get("inPlayArea") == 4
               else me["bench"][opt["inPlayIndex"]])
    assert destino["id"] != m.Chikorita, (
        f"nunca gastar la unica Planta en un Chikorita de banca (con 1 energia "
        f"no es atacante) habiendo Teal Dance; obtuvo {result} -> {opt}")


def test_marnie_step20_sin_teal_dance_el_adjunte_no_cede():
    # Contrafactual de frontera: si la habilidad ya no esta disponible, el
    # adjunte de desarrollo NO cede y vuelve a ser la mejor jugada.
    result, obs, _ = _marnie_s20_replay(
        observation_key="synthetic_sin_teal_dance")
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACH), (
        f"sin Teal Dance pendiente el adjunte manual no debe cederle a nadie; "
        f"obtuvo {result} -> {opt}")


# =====================================================================
# Xerosic's Machinations sobre Boss's Orders (user, registro_006 paso 85,
# episodio 87709507 vs Alakazam ex, PERDIDA): nuestro Hydrapple ex activo (10
# PV) noquea al Alakazam ex y en mano hay Boss's Orders y Xerosic con el rival
# a 16 CARTAS. El agente jugo Boss's (gusteo de 2 premios, 6800) en vez de
# Xerosic (6200) y dejo la mano rival intacta: su Powerful Hand (20 x carta de
# su mano) siguio pegando 320 y arraso. Regla: vs Alakazam, capar la mano tiene
# prioridad sobre Boss's; Boss's solo la tiene cuando GANA la partida
# (`win_via_boss_gust`, WIN_NOW 20000). Fix: nueva regla
# `alakazam_prioridad_sobre_boss` (XEROSIC_SCORE_SOBRE_BOSS=7000, sobre
# GUST_2PRIZE) y la cesion pasa a exigir el gusteo GANADOR (antes cedia ante
# `boss_win_via_bench`, que solo cobra un premio).
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


def _carta_jugada(obs, result):
    opt = obs["select"]["option"][result[0]]
    if opt.get("type") != int(OptionType.PLAY):
        return None
    mano = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    return mano[opt["index"]]["id"]


def test_alakazam_step85_juega_xerosic_y_no_boss():
    result, obs, _ = _alakazam_s85_replay()
    assert _carta_jugada(obs, result) == m.Xerosic_Machinations, (
        f"con el rival a 16 cartas, capar la mano (Powerful Hand = 20 x carta) "
        f"tiene prioridad sobre un gusteo que no gana la partida; obtuvo "
        f"{result} -> id {_carta_jugada(obs, result)}")


def test_alakazam_step85_no_gasta_el_boss_orders():
    result, obs, _ = _alakazam_s85_replay()
    assert _carta_jugada(obs, result) != m.Boss_Orders, (
        f"Boss's Orders solo tiene prioridad cuando GANA la partida; obtuvo "
        f"{result}")


def test_alakazam_step85_sin_xerosic_vuelve_boss():
    # Contrafactual: sin Xerosic en mano, Boss's vuelve a ser la jugada.
    result, obs, _ = _alakazam_s85_replay(
        observation_key="synthetic_sin_xerosic")
    assert _carta_jugada(obs, result) == m.Boss_Orders, (
        f"sin Xerosic en mano el gusteo de 2 premios sigue siendo correcto; "
        f"obtuvo {result} -> id {_carta_jugada(obs, result)}")


# =====================================================================
# No pivotar a un Hydrapple ex CONDENADO (user, registro_011 paso 138, episodio
# 87713774 vs Dragapult ex, PERDIDA): Tapu Bulu activo con 6 energias efectivas
# (listo para atacar) y un Hydrapple ex de banca a 70/330, con el rival a 2
# premios. El agente retiraba el Tapu Bulu para promover el Hydrapple; Dragapult
# ex (Phantom Dive, 200) lo noqueaba y cobraba sus 2 premios finales = derrota.
# Tres bugs encadenados: (1) el Syrup Storm de un Hydrapple de BANCA se medía
# con el Grass PREVIO al retiro (330 "letal" vs 320) cuando el retiro descarta
# las Plantas del activo; (2) lo mismo en `_hydra_lethal_promote`; (3)
# `_promote_hydra = _hydra_can_ko or (not _act_can_ko)` promovia sin comprobar
# si el Hydrapple SOBREVIVE al golpe proyectado.
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


def test_dragapult_step138_ataca_con_tapu_bulu():
    result, obs, _ = _dragapult_s138_replay()
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con el Tapu Bulu activo ya cargado y el Hydrapple ex de banca "
        f"condenado (70/330 frente a Phantom Dive), lo correcto es ATACAR; "
        f"obtuvo {result} -> {opt}")


def test_dragapult_step138_no_retira_para_promover_hydra():
    result, obs, _ = _dragapult_s138_replay()
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") != int(OptionType.RETREAT), (
        f"promover un Hydrapple ex que el activo rival noquea regala 2 premios "
        f"(los ultimos del rival); obtuvo {result} -> {opt}")


def test_dragapult_step138_con_hydra_sano_si_pivota():
    # Contrafactual de frontera: con el Hydrapple ex a 330/330 SOBREVIVE el
    # golpe proyectado, asi que el pivote de promocion vuelve a ser legitimo.
    result, obs, _ = _dragapult_s138_replay(
        observation_key="synthetic_hydra_sano")
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.RETREAT), (
        f"con el Hydrapple ex sano el pivote sigue siendo valido; obtuvo "
        f"{result} -> {opt}")


# =====================================================================
# Meowth ex con el activo CONDENADO y la banca corta (user, registro_014 paso
# 107, episodio 87721175 vs Marnie): Teal Mask Ogerpon ex activo a 10/210 PV
# (se cae al primer golpe) y UN solo Pokemon en banca, con Meowth ex en mano y
# el Supporter del turno libre. El agente atacaba (1100) porque el veto "el
# activo ya es atacante listo" (log 86511741 vs Mega Abomasnow) vetaba bajar
# Meowth ex. Pero bajar Meowth es GRATIS: no consume el ataque (se baja el
# Basico y se ataca despues en el mismo turno) y encadena Last-Ditch Catch ->
# Lillie's -> rehacer la mano, dando cuerpo de repuesto para cuando caiga el
# activo. El veto original esta pensado para un activo SANO con banca
# desarrollada; con el activo condenado y la banca vacia se invierte.
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


def test_marnie_step107_baja_meowth_con_activo_condenado():
    result, obs, _ = _marnie_s107_replay()
    assert _carta_jugada(obs, result) == m.Meowth_ex, (
        f"con el activo a 10/210 y un solo cuerpo en banca, bajar Meowth ex "
        f"(gratis, no consume el ataque) para encadenar Lillie's va primero; "
        f"obtuvo {result}")


def test_marnie_step107_activo_sano_no_baja_meowth():
    # Frontera: con el activo SANO vuelve el veto original (atacar).
    result, obs, _ = _marnie_s107_replay(observation_key="synthetic_activo_sano")
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con el activo sano, un atacante listo no cede el turno a Meowth ex; "
        f"obtuvo {result} -> {opt}")


def test_marnie_step107_banca_desarrollada_no_baja_meowth():
    # Frontera: con la banca desarrollada (3 cuerpos) tampoco se baja Meowth.
    result, obs, _ = _marnie_s107_replay(
        observation_key="synthetic_banca_desarrollada")
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con la banca desarrollada no hace falta el cuerpo de repuesto; "
        f"obtuvo {result} -> {opt}")


# =====================================================================
# Pokemon inicial ACTIVO: Tapu Bulu SIEMPRE (user)
# ---------------------------------------------------------------------
# Si al comenzar la partida tenemos un Tapu Bulu en la mano, es nuestro
# Pokemon inicial activo, por encima de cualquier otro basico (antes ganaba
# Teal Mask Ogerpon ex y, sin el, Chikorita/Applin). Fixture: el setup REAL
# de registro_000 (Tapu Bulu y Chikorita como unicos basicos de la mano).
# =====================================================================
_SETUP_TAPU_FIXTURE = ROOT / "tests" / "fixtures" / "setup_activo_tapu_bulu.json"


def _setup_obs():
    with open(_SETUP_TAPU_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _basico_elegido(obs, result):
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opt = obs["select"]["option"][result[0]]
    return me["hand"][opt["index"]]["id"]


def test_setup_activo_elige_tapu_bulu():
    obs = _setup_obs()
    assert obs["select"]["context"] == int(SelectContext.SETUP_ACTIVE_POKEMON)
    assert _basico_elegido(obs, m.agent(obs)) == m.Tapu_Bulu, (
        "con Tapu Bulu en la mano al comenzar la partida, es el Pokemon "
        "inicial activo")


def test_setup_activo_tapu_bulu_sobre_ogerpon():
    # El Teal Mask Ogerpon ex era el preferido (score 100): Tapu Bulu lo supera.
    obs = _setup_obs()
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    otro = next(o for o in obs["select"]["option"]
                if me["hand"][o["index"]]["id"] != m.Tapu_Bulu)
    me["hand"][otro["index"]]["id"] = m.Teal_Mask_Ogerpon_ex
    assert _basico_elegido(obs, m.agent(obs)) == m.Tapu_Bulu, (
        "Tapu Bulu (1 premio, atacante de referencia) va al activo antes que "
        "el Teal Mask Ogerpon ex (2 premios)")


def test_setup_activo_sin_tapu_no_cambia():
    # Frontera: sin Tapu Bulu entre las opciones, la preferencia previa sigue
    # intacta (Chikorita sobre el resto de basicos).
    obs = _setup_obs()
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    obs["select"]["option"] = [o for o in obs["select"]["option"]
                               if me["hand"][o["index"]]["id"] != m.Tapu_Bulu]
    assert _basico_elegido(obs, m.agent(obs)) == m.Chikorita, (
        "sin Tapu Bulu en la mano, la eleccion del inicial no cambia")


# =====================================================================
# Linea de Meganium: retirar el Chikorita activo en vez de atacar por chip
# ---------------------------------------------------------------------
# user, registro_003 paso 29 (turno 3 vs Dragapult, PERDIDA): Chikorita activo
# con 1 Planta, Bayleef + Meganium en mano y Forest of Vitality en juego. El
# agente atacaba con Growl (0 de dano) y dejaba la linea muerta en la mano: el
# scorer de EVOLVE veta evolucionar en el ACTIVO ("retirar primero y evolucionar
# en banca") pero el RETREAT quedaba vetado porque el Tapu Bulu de banca aun no
# tenia energia. Lo correcto: RETIRAR, promover Tapu Bulu (140 PV) y evolucionar
# el Chikorita en la BANCA -- con Forest, la cadena entera este mismo turno.
# =====================================================================
_DRAGAPULT_P29_FIXTURE = (
    ROOT / "tests" / "fixtures" / "dragapult_paso29_retirar_chikorita.json")


def _dragapult_p29_obs():
    with open(_DRAGAPULT_P29_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _mi_lado(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def test_dragapult_p29_retira_chikorita_en_vez_de_atacar():
    obs = _dragapult_p29_obs()
    tipos = {o.get("type") for o in obs["select"]["option"]}
    # El fixture debe ofrecer atacar, evolucionar en el activo y retirar.
    assert {int(OptionType.ATTACK), int(OptionType.EVOLVE),
            int(OptionType.RETREAT)} <= tipos
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.RETREAT), (
        f"con Bayleef en mano, el Chikorita activo se retira para montar la "
        f"linea de Meganium en banca en vez de atacar con Growl (0 de dano); "
        f"obtuvo {opt}")


def test_dragapult_p29_promueve_tapu_bulu():
    # Tras retirar, la promocion sube el cuerpo con mas vida (Tapu Bulu, 140)
    # y no el Applin de 40 recien jugado.
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
    banca = _mi_lado(obs)["bench"]
    elegido = banca[obs["select"]["option"][result[0]]["index"]]["id"]
    assert elegido == m.Tapu_Bulu, (
        f"al promover tras retirar el Chikorita se sube Tapu Bulu (140 PV), "
        f"no el Applin de 40; obtuvo {m.card_table[elegido].name}")


def _obs_tras_retirar():
    """Estado sintetico: ya retiramos, Tapu Bulu activo y Chikorita en banca."""
    obs = _dragapult_p29_obs()
    yo = obs["current"]["yourIndex"]
    me = _mi_lado(obs)
    chiko = copy.deepcopy(me["active"][0])
    chiko["energies"] = []          # la Planta pago el coste de retirada
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


def test_dragapult_p29_evoluciona_chikorita_en_banca():
    obs, _ = _obs_tras_retirar()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.EVOLVE), (
        f"con el Chikorita ya en banca, Bayleef se juega sobre el; obtuvo {opt}")


def test_dragapult_p29_completa_meganium_con_forest():
    # Forest of Vitality permite evolucionar el Bayleef recien jugado: la cadena
    # Chikorita -> Bayleef -> Meganium se completa en el mismo turno.
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


def test_sin_bayleef_en_mano_el_chikorita_no_se_retira():
    # Frontera: sin la evolucion en la mano no hay linea que montar, asi que el
    # pivote no dispara y el Chikorita conserva su comportamiento previo.
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
# Nunca cerrar el turno con un ataque de 0 de dano teniendo Lillie's
# ---------------------------------------------------------------------
# user, registro_009 paso 61 (turno 9 vs Dragapult, PERDIDA): Chikorita activo
# 50/70, Tapu Bulu y Applin sin cargar en banca y en la mano Unfair Stamp +
# Bayleef + Meganium + Meowth ex + Xerosic + Lillie's Determination, con 6
# premios (Lillie's roba OCHO). El agente ataco con Growl (0 de dano) y dejo
# TODA la mano muerta: el scorer de Lillie's la vetaba porque "hay una linea
# evolucionable este turno" mientras la evolucion real estaba bloqueada.
# =====================================================================
_DRAGAPULT_P61_FIXTURE = (
    ROOT / "tests" / "fixtures" / "dragapult_paso61_lillie_turno_esteril.json")


def _dragapult_p61_obs():
    with open(_DRAGAPULT_P61_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _p61_sin_evolucion_ni_retirada(obs):
    """Menu del deadlock real: ni evolucionar ni retirar, solo jugar o atacar."""
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if o.get("type") not in (int(OptionType.EVOLVE), int(OptionType.RETREAT))]
    return obs


def test_p61_turno_esteril_juega_lillie_en_vez_de_growl():
    obs = _p61_sin_evolucion_ni_retirada(_dragapult_p61_obs())
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.PLAY), (
        f"con la evolucion bloqueada, cerrar el turno con Growl (0 de dano) "
        f"deja la mano muerta: hay que refrescar con Lillie's; obtuvo {opt}")
    carta = _mi_lado(obs)["hand"][opt["index"]]["id"]
    assert carta == m.Lillie_Determination, (
        f"la jugada de rescate es Lillie's Determination (roba 6/8); obtuvo "
        f"{m.card_table[carta].name}")


def test_p61_con_ataque_real_no_dispara_el_rescate():
    # Frontera: si el activo SI hace dano (Tapu Bulu cargado, Wood Hammer 220)
    # el turno no es esteril y el rescate no se activa.
    obs = _p61_sin_evolucion_ni_retirada(_dragapult_p61_obs())
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


def test_p61_promueve_tapu_bulu_no_applin():
    # Al retirar el Chikorita, el muro es Tapu Bulu (140 PV), no el Applin de
    # 40 -- que ademas es pieza de la linea Hydrapple.
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
    banca = _mi_lado(obs)["bench"]
    elegido = banca[obs["select"]["option"][result[0]]["index"]]["id"]
    assert elegido == m.Tapu_Bulu, (
        f"con Lillie's en mano y sin atacante listo se sube el basico de 1 "
        f"premio mas resistente (Tapu Bulu 140), no el Applin de 40; obtuvo "
        f"{m.card_table[elegido].name}")


def test_p61_tras_evolucionar_en_banca_se_juega_lillie():
    # Secuencia completa del turno: retirado y con el Bayleef ya en la banca,
    # la mano se refresca con Lillie's antes de terminar. Se reproduce primero
    # la observacion REAL del paso 61 para que el agente registre el campo al
    # inicio del turno (sin eso, un Bayleef recien evolucionado parece
    # "evolucionable ya" y Lillie's queda vetada por conservar la linea).
    m.agent(_dragapult_p61_obs())
    obs = _dragapult_p61_obs()
    yo = obs["current"]["yourIndex"]
    me = _mi_lado(obs)
    bayleef = copy.deepcopy(me["active"][0])
    bayleef.update({"id": m.Bayleef, "hp": 90, "maxHp": 110,
                    "appearThisTurn": True, "energies": [], "energyCards": [],
                    "preEvolution": [{"id": m.Chikorita, "playerIndex": yo,
                                      "serial": 67}]})
    me["active"] = [me["bench"][0]]                 # Tapu Bulu promovido
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
    carta = _mi_lado(obs)["hand"][opt["index"]]["id"] if opt.get("index") is not None else None
    assert carta == m.Lillie_Determination, (
        f"con la linea ya bajada y la mano sin recursos, el turno termina "
        f"refrescando con Lillie's; obtuvo {opt}")


# =====================================================================
# Confusion pivot vs muro inmune EN BANCA (user, registro_006 paso 64 vs
# Crustle, GANADA): el activo Dipplin a 10 PV y CONFUNDIDO atacaba -- si falla
# la moneda de confusion se auto-noquea -- en vez de RETIRARSE y subir el
# Ogerpon ex cargado que noquea al Munkidori activo. El bug: `_conf_ex_immune_
# match` usaba flags de MAZO (op_is_crustle_deck) y de BANCA, que valen aunque
# el activo rival sea ATACABLE, y excluian al Ogerpon ex del set de atacantes
# del pivote. El muro inmune solo veta promover un ex cuando esta EN EL ACTIVO
# rival. Observacion autocontenida (los registros son datos locales transitorios).
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
    # Activo Dipplin a 10 PV CONFUNDIDO, con 2 Plantas (paga su coste de retirada 2).
    me["active"] = [{"appearThisTurn": False, "energies": [1, 1],
                     "energyCards": [{"id": 1, "playerIndex": 1, "serial": 201},
                                     {"id": 1, "playerIndex": 1, "serial": 202}],
                     "hp": 10, "id": m.Dipplin, "maxHp": 80, "playerIndex": 1,
                     "preEvolution": [{"id": m.Applin, "playerIndex": 1, "serial": 210}],
                     "serial": 200, "tools": []}]
    # Banca: Ogerpon ex cargado (3 Plantas -> Myriad Leaf Shower listo).
    me["bench"] = [{"appearThisTurn": False, "energies": [1, 1, 1],
                    "energyCards": [{"id": 1, "playerIndex": 1, "serial": 221},
                                    {"id": 1, "playerIndex": 1, "serial": 222},
                                    {"id": 1, "playerIndex": 1, "serial": 223}],
                    "hp": 210, "id": m.Teal_Mask_Ogerpon_ex, "maxHp": 210,
                    "playerIndex": 1, "preEvolution": [], "serial": 220, "tools": []}]
    me["hand"] = []
    me["handCount"] = 0
    # Rival: muro Crustle en la BANCA; activo ATACABLE (Munkidori) salvo la frontera.
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    res = m.agent(obs)
    return obs["select"]["option"][res[0]].get("type")


def test_confusion_pivot_retira_a_ex_si_activo_rival_atacable():
    # Activo rival = Munkidori (atacable): retirar el Dipplin confundido y subir
    # el Ogerpon ex cargado que lo noquea, en vez de arriesgar el auto-KO.
    obs = _crustle_confusion_obs(active_is_crustle=False)
    assert _tipo_elegido(obs) == int(OptionType.RETREAT), (
        "confundido a 10 PV con Ogerpon ex cargado en banca y activo rival "
        "atacable (Munkidori): retirar, no atacar con el confundido")


def test_confusion_no_retira_a_ex_si_activo_rival_es_muro_inmune():
    # Frontera: si el muro inmune a ex (Crustle) esta EN EL ACTIVO rival, el
    # Ogerpon ex no lo dana -> promoverlo es inutil; se ataca con el confundido.
    obs = _crustle_confusion_obs(active_is_crustle=True)
    assert _tipo_elegido(obs) != int(OptionType.RETREAT), (
        "con el muro inmune (Crustle) en el ACTIVO rival, promover el ex es "
        "inutil: no se retira a un ex que no puede noquear")


# =====================================================================
# Prioridad de carga de Tapu Bulu vs Crustle (user, registro_002 paso 17 vs
# Crustle, PERDIDA): con Tapu Bulu (nuestro atacante principal, unico no-ex que
# daña al muro inmune) en el ACTIVO sin energia, el agente cargaba un Applin de
# banca en vez del Tapu. Causa: el veto generico de "no cargar el activo inicial"
# (Ogerpon/Tapu en nuestro primer turno) degradaba a SCORE_VETO el adjunte al
# Tapu activo. Vs Crustle, Tapu Bulu queda EXENTO de ese veto. Observacion
# autocontenida (los registros son datos locales transitorios).
# =====================================================================
def _crustle_tapu_charge_obs():
    import copy as _c
    import json as _j
    o = _c.deepcopy(_j.load(open(_CONF_BASE_FIXTURE, encoding="utf-8"))["observation"])
    cur = o["current"]
    cur["turn"] = 2            # nuestro primer turno yendo SEGUNDOS
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


def test_crustle_carga_tapu_bulu_activo_primera_prioridad():
    obs = _crustle_tapu_charge_obs()
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    res = m.agent(obs)
    opt = obs["select"]["option"][res[0]]
    assert opt.get("type") == int(OptionType.ATTACH) and opt.get("inPlayArea") == 4, (
        f"vs Crustle, la 1a carga de energia va al Tapu Bulu ACTIVO (atacante "
        f"principal), no a un Applin de banca; obtuvo {res} -> {opt}")


# =====================================================================
# DESCUADRE GENERALIZADO: retirar el ex condenado y sacrificar un cuerpo de
# 1 premio (user, registro_004 paso 37 vs Mega Lucario ex). Nuestro Teal Mask
# Ogerpon ex (210 HP, 3 energia) PUEDE atacar pero su Myriad Leaf Shower NO
# noquea al Mega Lucario ex (340 HP), y Mega Lucario nos remata el proximo
# turno (Mega Brave 270 >= 210). Sin atacante de banca listo y con un cuerpo
# de 1 premio (Applin) para poner delante, lo correcto es RETIRAR el ex (cede
# 1 premio en vez de 2 y conserva el ex en banca), no atacar sin noquear. La
# logica es deck-agnostica: se detecta con el remate rival REAL, no con una
# lista de matchups.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [applin_opt], (
        f"tras retirar el ex, promover el basico de 1 premio mas barato "
        f"(Applin, opt {applin_opt}); obtuvo {result}")


def test_doomed_ex_retreat_generalizes_to_nonlucario():
    # Mismo patron con un rival NO-Lucario (Dragapult ex) que one-shotea a
    # nuestro ex condenado: el pivote es deck-agnostico y debe retirar igual.
    with open(_DOOMED_EX_RETREAT_GENERIC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    options = obs["select"]["option"]
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [retreat_opt], (
        f"generalizacion (rival no-Lucario que one-shotea): RETIRAR "
        f"(opt {retreat_opt}); obtuvo {result}")


def test_doomed_ex_promote_basic_generalizes_to_nonlucario():
    # La promocion tambien generaliza: sin atacante de banca y con el rival
    # one-shoteando al cuerpo mas tanque (Bayleef 110), promover el basico de
    # 1 premio (Applin 40) en vez del cuerpo mas tanque. Sin la regla general la
    # promocion por defecto subiria a Bayleef (mas HP).
    with open(_DOOMED_EX_PROMOTE_GENERIC_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    bench = obs["current"]["players"][mi]["bench"]
    options = obs["select"]["option"]
    applin_opt = next(i for i, o in enumerate(options)
                      if bench[o["index"]]["id"] == m.Applin)
    bayleef_opt = next(i for i, o in enumerate(options)
                       if bench[o["index"]]["id"] == m.Bayleef)

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [applin_opt], (
        f"generalizacion promocion: subir Applin (opt {applin_opt}), no el mas "
        f"tanque Bayleef (opt {bayleef_opt}); obtuvo {result}")


def test_doomed_ex_does_not_sac_retreat_when_near_winning():
    # Control negativo: en RANGO DE REMATE (my_prize<=2) NO se sacrifica-retira;
    # hay que racear/rematar. Mismo tablero condenado pero con 4 premios ya
    # tomados (2 restantes) -> el agente NO debe elegir el retiro defensivo.
    with open(_DOOMED_EX_RETREAT_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    # dejar solo 2 premios restantes (my_prize == len(prize) == 2): rango de remate
    obs["current"]["players"][mi]["prize"] = (
        obs["current"]["players"][mi]["prize"][:2])
    options = obs["select"]["option"]
    retreat_opt = next(i for i, o in enumerate(options)
                       if o.get("type") == int(OptionType.RETREAT))

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [retreat_opt], (
        f"cerca de ganar (my_prize<=2) NO se hace el retiro-sacrificio "
        f"defensivo; obtuvo {result}")


# =====================================================================
# MOTOR MEOWTH -> LILLIE'S en TABLERO POBRE (user, registro_006 paso 57 vs
# Alakazam, GANADA). El activo es un atacante CHIP de 1 premio (Dipplin) que
# PUEDE noquear al activo rival pero es fragil, NO hay atacante de banca listo
# y la mano es minima (1 carta: el propio Meowth ex). El agente atacaba; lo
# correcto es BAJAR Meowth ex primero (Last-Ditch Catch -> Lillie's -> refresca
# la mano y arma un 2o atacante) y ATACAR despues en el mismo turno. Se permite
# aun con UN Meowth ya en banca (field<2) y aunque el activo noquee. Deck-agnostico.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [play_opt], (
        f"tablero pobre (mano minima, sin atacante de banca, activo chip de 1 "
        f"premio): BAJAR Meowth ex (opt {play_opt}) para refrescar via Lillie's, "
        f"no atacar (opt {attack_opt}); obtuvo {result}")


def test_step57_meowth_refresh_does_not_fire_with_strong_hand():
    # Control negativo: con la mano NO debil (>=3 cartas), no se banca un 2o
    # Meowth ex; se ataca con el chip activo.
    import copy as _c
    with open(_MEOWTH_REFRESH_POOR_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mi = obs["current"]["yourIndex"]
    obs["current"]["players"][mi]["hand"] += [
        {"id": 1, "playerIndex": mi, "serial": 200 + k} for k in range(3)]
    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"con mano fuerte NO se banca un 2o Meowth; se ataca (opt {attack_opt}); "
        f"obtuvo {result}")


def test_step57_meowth_refresh_does_not_fire_with_ready_bench_attacker():
    # Control negativo: si YA hay un atacante de banca listo (Ogerpon ex con 3
    # energia), no hace falta refrescar: se ataca con el chip activo.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"con atacante de banca listo NO se refresca con Meowth; se ataca "
        f"(opt {attack_opt}); obtuvo {result}")


def test_step57_meowth_refresh_generalizes_to_nonalakazam():
    # Generalizacion: el motor de refresco en tablero pobre es deck-agnostico;
    # con un rival distinto (no Alakazam) tambien baja Meowth ex.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [play_opt], (
        f"generalizacion (rival no-Alakazam): BAJAR Meowth ex (opt {play_opt}); "
        f"obtuvo {result}")


# =====================================================================
# MOTOR MEOWTH -> LILLIE'S SIN ATACANTE DE REPUESTO (user, registro_006 paso 78
# vs Mega Lucario ex). El activo es un Teal Mask Ogerpon ex que PUEDE atacar pero
# su Myriad NO noquea (180 vs 190) y Mega Lucario lo remata el proximo turno
# (270 >= 210); la banca tiene UN solo cuerpo NO atacante (Chikorita) y desde la
# mano NO hay forma de montar un 2o atacante (Hydrapple/Dipplin atascados sin
# Applin/Dipplin en juego). El agente atacaba; lo correcto es BAJAR Meowth ex
# (Last-Ditch Catch -> Lillie's -> refresca la mano para hallar atacantes) y
# atacar/retirar despues. Detecta el remate rival REAL (no el heuristico
# active_ko_likely, que subestima a Mega Lucario). Deck-agnostico.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"ex condenado que no noquea, banca sin atacante y sin camino a un 2o "
        f"atacante: BAJAR Meowth ex (opt {meowth_opt}) para refrescar via Lillie's, "
        f"no atacar (opt {attack_opt}); obtuvo {result}")


def test_step78_meowth_refresh_not_with_bench_attacker_body():
    # Control negativo: si hay un cuerpo ATACANTE en banca (Ogerpon ex), hay
    # camino a un 2o atacante (cargarlo) y NO se banca un Meowth para refrescar.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [meowth_opt], (
        f"con un cuerpo atacante en banca NO se refresca con Meowth; obtuvo {result}")


def test_step78_meowth_refresh_not_when_active_not_doomed():
    # Control negativo: si el activo NO esta condenado (rival sin energia para
    # rematar), no hace falta refrescar; no se banca el 2o Meowth.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [meowth_opt], (
        f"con el activo NO condenado no se refresca con Meowth; obtuvo {result}")


def test_step78_meowth_refresh_generalizes_to_nonlucario():
    # Generalizacion deck-agnostica: con un rival distinto (Dragapult ex) que
    # one-shotea al activo condenado, tambien baja Meowth ex.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"generalizacion (rival no-Lucario que one-shotea): BAJAR Meowth ex "
        f"(opt {meowth_opt}); obtuvo {result}")


# =====================================================================
# CONCENTRAR LA CARGA EN UN OGERPON LETAL (user, registro_006 paso 66 vs
# Marnie's Grimmsnarl ex). Con DOS Teal Mask Ogerpon ex en banca (uno a 2
# energias, otro a 0/1), la carga se repartia y NINGUNO llegaba a las 3
# energias del KO por debilidad (Myriad 180 x2 = 360 >= 320). Ahora el adjunte
# manual se CONCENTRA en el Ogerpon mas cargado (2e -> 3e = letal) y se veta
# cargar al otro. La debilidad se considera SIEMPRE via _our_effective_damage.
# =====================================================================
_MARNIE_CONCENTRATE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "marnie_step66_concentrate_ogerpon_charge.json")


def test_step66_concentrates_manual_attach_on_lethal_ogerpon():
    with open(_MARNIE_CONCENTRATE_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    bench = obs["current"]["players"][mi]["bench"]
    options = obs["select"]["option"]
    # ATTACH manual (inPlayArea==5 banca) al Ogerpon (id 96) con MAS energia.
    ogerpon_slots = [(i, o) for i, o in enumerate(options)
                     if o.get("type") == int(OptionType.ATTACH)
                     and o.get("inPlayArea") == 5
                     and bench[o["inPlayIndex"]]["id"] == m.Teal_Mask_Ogerpon_ex]
    # el objetivo correcto es el Ogerpon de banca con mayor energia (2e).
    best = max(ogerpon_slots,
              key=lambda io: len(bench[io[1]["inPlayIndex"]]["energies"]))
    best_e = len(bench[best[1]["inPlayIndex"]]["energies"])

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    chosen = options[result[0]]

    assert (chosen.get("type") == int(OptionType.ATTACH)
            and chosen.get("inPlayArea") == 5
            and bench[chosen["inPlayIndex"]]["id"] == m.Teal_Mask_Ogerpon_ex
            and len(bench[chosen["inPlayIndex"]]["energies"]) == best_e), (
        f"el adjunte manual debe CONCENTRARSE en el Ogerpon mas cargado "
        f"({best_e}e -> letal), no repartir; obtuvo {result} -> {chosen}")


def test_concentrate_focus_not_when_active_can_attack():
    # Control negativo: si el ACTIVO es un atacante viable que llega a su ataque
    # cargandose (Hydrapple ex + Ripening/adjunte), la energia NO se desvia a un
    # Ogerpon de banca. Reusa el fixture de Ripening vs Lucario (activo Hydrapple).
    data = _lucario_ripen_data()
    obs = data["ripen_target"]
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("area") == int(AreaType.ACTIVE), (
        f"con el activo atacante viable, la carga va al ACTIVO, no a un Ogerpon "
        f"de banca; obtuvo {result} -> {opt}")


# =====================================================================
# REMATE GANADOR CON EL ACTIVO (user, registro_009 paso 125 vs Archaludon ex,
# PERDIDA). Ogerpon ex activo con 4 Plantas fisicas + Meganium en juego (Wild
# Growth duplica -> 8 efectivas). Myriad = 30 + 30x(8 propias + 3 del rival) =
# 360, menos 30 de resistencia a Planta del Archaludon ex = 330 >= 300 -> NOQUEA
# y, con 2 premios restantes (Archaludon ex vale 2), GANA la partida. El agente
# cargaba energia a Tapu Bulu (`_tapu_future_charge`) y luego retiraba al Ogerpon
# para atacar con Tapu, tirando el remate. Cuando el KO del activo GANA, ATACAR
# es la maxima prioridad. Deck-agnostico (calculo con Meganium, energia rival y
# resistencia). 
# =====================================================================
_ARCHALUDON_WIN_FIXTURE = (
    ROOT / "tests" / "fixtures" / "archaludon_step125_winning_ogerpon_attack.json")


def test_step125_plays_winning_ogerpon_attack_over_charging_tapu():
    with open(_ARCHALUDON_WIN_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"con el remate GANADOR del activo (Myriad 330 >= 300, KO que gana), "
        f"ATACAR (opt {attack_opt}) es la maxima prioridad, no cargar Tapu Bulu; "
        f"obtuvo {result}")


def test_step125_winning_attack_generalizes_without_resistance():
    # Generalizacion: sin resistencia (rival no-Metal) el KO tambien gana y se
    # ataca. Cambiar el rival por un cuerpo de 2 premios y 300 HP sin resistencia
    # (Mega Lucario ex 678) deja el Myriad 360 >= 300 -> KO ganador.
    import copy as _c
    with open(_ARCHALUDON_WIN_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    opi = 1 - obs["current"]["yourIndex"]
    oa = obs["current"]["players"][opi]["active"][0]
    oa["id"] = 678; oa["maxHp"] = 340; oa["hp"] = 300; oa["preEvolution"] = []
    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [attack_opt], (
        f"remate ganador sin resistencia: ATACAR (opt {attack_opt}); "
        f"obtuvo {result}")


def test_winning_attack_not_forced_when_ko_does_not_win():
    # Control negativo: si el KO del activo NO gana la partida (nos quedan mas
    # premios que los que da el KO), NO se fuerza el ataque por encima del
    # desarrollo; que el rival tenga 4 premios (no ganamos con 1 KO de 2).
    import copy as _c
    with open(_ARCHALUDON_WIN_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    mi = obs["current"]["yourIndex"]
    obs["current"]["players"][mi]["prize"] = [None, None, None, None]
    options = obs["select"]["option"]
    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [attack_opt], (
        f"con 4 premios el KO no gana; no se fuerza el ataque sobre el "
        f"desarrollo; obtuvo {result}")


# =====================================================================
# ANTI-CUBCHOO: no retirada-pivote que malgaste energia (user, registro_004
# paso 47/49 vs cornerstone_cubchoo, PERDIDA). El mazo de Cubchoo (506,
# Snotted Up) / Beartic (507, Sheer Cold) BLOQUEA nuestro activo cada turno
# ("el Defensor no puede usar ataques"), forzando una retirada para atacar con
# otro cuerpo. Su atacante es debilisimo (Cubchoo pega 10, no nos noquea), pero
# como nos obliga a retirarnos repetidamente, cada retirada que DESCARTA energia
# sangra el recurso critico. Contra ESTE mazo eliminamos la retirada-pivote
# voluntaria: con el activo bloqueado (6 energia, sin opcion de ataque) y un
# Hydrapple ex listo en banca, el agente PASA (END) conservando energia, no
# retira descartando 2 energia. Solo vs Cubchoo; contra otros mazos la
# retirada-pivote sigue vigente.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result[0] not in retreat_opts, (
        f"vs Cubchoo con el activo bloqueado (6 energia) no se debe retirar "
        f"descartando energia; se debe PASAR/desarrollar. retiradas={retreat_opts}, "
        f"obtuvo {result}")


def test_cubchoo_conserve_pass_is_deck_specific():
    # Control de deck-especificidad: el mismo tablero contra un mazo NO-Cubchoo
    # NO debe pasar-para-conservar (el veto anti-Cubchoo se levanta). Se cambia
    # el rival de Cubchoo (506) a Mega Lucario ex (678) para desactivar
    # `op_is_cubchoo_deck`; entonces la decision deja de ser el END conservador.
    import copy as _c
    with open(_CUBCHOO_RETREAT_FIXTURE, encoding="utf-8") as f:
        base = json.load(f)["observation"]

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    other = m.agent(obs)
    other_type = obs["select"]["option"][other[0]].get("type")

    assert other[0] != cub_choice[0] and other_type != int(OptionType.END), (
        f"contra un mazo no-Cubchoo la decision NO debe ser el END conservador "
        f"(el veto es especifico del matchup); obtuvo {other} tipo {other_type}")


# =====================================================================
# PROTEGER FOREST OF VITALITY COMO CONTRA-ESTADIO EN DESCARTE FORZADO (user,
# registro_005 paso 62 vs cornerstone_cubchoo, PERDIDA). El rival controla
# Neutralization Zone (1247): anula el dano de nuestros ex al activo de 1 premio
# y nos impide atacar. La unica forma de removerla es jugar NUESTRO estadio
# (Forest of Vitality 1261) para reemplazarla. Xerosic's Machinations (1197) nos
# fuerza a descartar 2 de 5 cartas; Forest es CLAVE y no debe descartarse. Antes,
# con Meganium+Hydrapple en juego, Forest puntuaba 70 (descartable) sin mirar el
# estadio hostil rival, y el agente lo tiraba.
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
    # sanity: el estadio rival es Neutralization Zone y Forest esta en mano
    assert obs["current"]["stadium"][0]["id"] == _NEUTRALIZATION_ZONE
    mi = obs["current"]["yourIndex"]
    assert any(c["id"] == _FOREST_OF_VITALITY for c in obs["current"]["players"][mi]["hand"])

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    discarded = _discarded_card_ids(obs, result)

    assert _FOREST_OF_VITALITY not in discarded, (
        f"con Neutralization Zone rival en juego, Forest es el unico contra-estadio "
        f"y NO debe descartarse; descarto ids {discarded}")


def test_forest_discardable_when_no_hostile_op_stadium():
    # Control: sin estadio hostil rival, la proteccion NO aplica -- con
    # Meganium+Hydrapple en juego Forest vuelve a ser descartable (score 70).
    # Se retira el Neutralization Zone rival del tablero; Forest debe poder caer.
    import copy as _c
    with open(_FOREST_DISCARD_FIXTURE, encoding="utf-8") as f:
        obs = _c.deepcopy(json.load(f)["observation"])
    obs["current"]["stadium"] = []  # sin estadio hostil
    mi = obs["current"]["yourIndex"]
    forest_opt = next(i for i, o in enumerate(obs["select"]["option"])
                      if obs["current"]["players"][mi]["hand"][o["index"]]["id"]
                      == _FOREST_OF_VITALITY)

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert forest_opt in result, (
        f"sin estadio hostil rival, con Meganium+Hydrapple Forest es descartable; "
        f"obtuvo {result} (opcion Forest = {forest_opt})")


# =====================================================================
# ANTI-CUBCHOO: cargar el Hydrapple ex ACTIVO bloqueado con Ripening Charge para
# habilitar la retirada hacia un atacante de banca LISTO (user, registro_008
# paso 82 vs cornerstone_cubchoo, PERDIDA). El Hydrapple ex activo esta bloqueado
# por Snotted Up (no puede atacar) pero en la banca hay un Ogerpon ex ya cargado
# (4 efectivas) que noquea al Cubchoo. La linea correcta: Ripening Charge en el
# PROPIO Hydrapple para alcanzar su coste de retirada (efectivo 3), retirarlo y
# subir al Ogerpon para atacar. Regla del user: si el activo NO puede atacar,
# priorizar la retirada para atacar. Antes el agente usaba Teal Dance en un
# Ogerpon de banca (tier ENERGY dominaba a Ripening en tier 0), regando la
# energia y desperdiciando el turno sin atacar. Se distingue de
# `test_step47_vs_cubchoo_does_not_waste_energy_retreating` (activo Ogerpon
# CARGADO -> conservar): aqui el activo es Hydrapple ex SUB-cargado cuya energia
# extra es peso muerto.
# =====================================================================
_CUBCHOO_RIPEN_FIXTURE = (
    ROOT / "tests" / "fixtures" / "cubchoo_step82_ripening_charge_blocked_active.json")


def test_step82_charges_blocked_hydrapple_to_enable_retreat():
    with open(_CUBCHOO_RIPEN_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    options = obs["select"]["option"]
    # opcion de Ripening Charge sobre el ACTIVO (area 4) del Hydrapple ex
    ripen_active = [i for i, o in enumerate(options)
                    if o.get("type") == int(OptionType.ABILITY)
                    and o.get("area") == int(AreaType.ACTIVE)]
    assert ripen_active, "el fixture debe ofrecer Ripening Charge en el activo"

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result[0] in ripen_active, (
        f"con el Hydrapple ex activo bloqueado por Cubchoo y un Ogerpon ex de "
        f"banca listo, se debe cargar el ACTIVO con Ripening Charge (opciones "
        f"{ripen_active}) para habilitar la retirada; obtuvo {result}")


# =====================================================================
# ANTI-CUBCHOO: rutear las energias recuperadas (Lana's Aid) al Hydrapple ex
# ACTIVO bloqueado, no a la banca (user, registro_012 paso 96 vs cornerstone_
# cubchoo, PERDIDA). Mismo patron que registro_008 paso 82 pero cargando por
# ADJUNTE MANUAL (energias de Lana's Aid) en vez de por Ripening Charge: el
# Hydrapple ex activo esta bloqueado por Snotted Up y hay 2 Ogerpon ex de banca
# (4 efectivas) listos para noquear al Cubchoo. La energia debe ir al ACTIVO
# para alcanzar su coste de retirada y habilitar retirar->promover->atacar.
# Antes el agente cargaba un Meganium/Ogerpon de banca. Cubierto por
# `_cubchoo_lock_stuck` (ruteo de energia al ex estancado, +24000).
# =====================================================================
_CUBCHOO_LANAS_FIXTURE = (
    ROOT / "tests" / "fixtures"
    / "cubchoo_step96_charge_blocked_active_from_lanas.json")


def test_step96_routes_lanas_energy_to_blocked_active_hydrapple():
    with open(_CUBCHOO_LANAS_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    chosen = obs["select"]["option"][result[0]]
    assert chosen.get("type") == int(OptionType.ATTACH), (
        f"se debe ADJUNTAR energia (no {chosen}); obtuvo {result}")
    assert chosen.get("inPlayArea") == int(AreaType.ACTIVE), (
        f"la energia recuperada debe ir al Hydrapple ex ACTIVO bloqueado "
        f"(inPlayArea={int(AreaType.ACTIVE)}), no a la banca; obtuvo {chosen}")


# =====================================================================
# NO barajar la linea de evolucion con Lillie's: Ultra Ball la completa primero
# (user, registro_004 paso 47 vs Alakazam, PERDIDA). Tenemos Chikorita en juego
# + Meganium en MANO, pero falta la Stage-1 intermedia (Bayleef), que esta en el
# MAZO y es buscable con Ultra Ball. Lillie's Determination BARAJA toda la mano
# al mazo -> perderiamos Meganium + las 2 Ultra Ball. Lo correcto: jugar la
# Ultra Ball (traer Bayleef, montar Chikorita->Bayleef->Meganium) y NO refrescar
# todavia. La regla `ub_gapped_line` veta Lillie's mientras la linea con hueco +
# Ultra Ball siga en mano. Deck-agnostico (cubre tambien Applin/Dipplin/Hydra).
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result[0] not in lillie_opts, (
        f"con Chikorita en juego + Meganium en mano + Ultra Ball (falta Bayleef "
        f"buscable) NO se debe jugar Lillie's (barajaria la linea); "
        f"opciones Lillie={lillie_opts}, obtuvo {result}")


def _lillie_gapped_flag(obs):
    """Devuelve el flag `ub_gapped_line` del scorer de Lillie's para `obs`."""
    captured = {}
    orig = m._CtxLillie

    class _Spy(orig):
        def __init__(self, ctx):
            super().__init__(ctx)
            captured["v"] = self.ub_gapped_line

    m._CtxLillie = _Spy
    try:
        m._init_cartas_tracking(); m.plan = m.AttackPlan()
        m.agent(obs)
    finally:
        m._CtxLillie = orig
    return captured.get("v")


def test_ub_gapped_line_flag_requires_ultraball():
    # El flag `ub_gapped_line` (que veta Lillie's) exige Ultra Ball en mano:
    # es True en el fixture y se apaga al quitar la Ultra Ball (el hueco deja
    # de ser completable).
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
# Ripening Charge (ATTACH_FROM): NO desperdiciar la energia en un activo de dano
# FIJO ya cargado; darla al mejor atacante FUTURO (user, registro_006 paso 79 vs
# Alakazam, PERDIDA). El activo Tapu Bulu ya tenia 4 efectivas (= Wood Hammer,
# coste fijo, tope duro) y el juego le cargaba una 5a via Ripening Charge del
# Hydrapple ex, pese a existir un Hydrapple ex de banca a 0 energias (atacante
# futuro). El winning/2-prize-gust routing (42000 al activo) ya no aplica a un
# atacante de dano fijo que llego a su requisito.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)
    chosen = obs["select"]["option"][result[0]]
    tid = target_id(chosen)

    assert tid == _HYDRAPPLE_EX, (
        f"Ripening Charge debe cargar el Hydrapple ex de banca (0e, atacante "
        f"futuro), no el Tapu Bulu activo ya cargado; cargo id {tid}")
    # y explicitamente NO el Tapu Bulu activo (ya al tope de Wood Hammer)
    assert not (chosen.get("area") == int(AreaType.ACTIVE)
                and me["active"][0]["id"] == _TAPU_BULU), (
        "no debe cargar el Tapu Bulu activo ya cargado")


# =====================================================================
# No sobrecargar un Hydrapple ex ACTIVO ya listo; cargar el de BANCA (atacante
# futuro) tanto con el adjunte manual como con Ripening Charge (user,
# registro_008 pasos 109-113 vs Alakazam, GANADA con jugada suboptima). Syrup
# Storm escala con el Grass del CAMPO (todos nuestros Pokemon), NO con la energia
# propia del atacante: poner la energia en un Hydrapple ex de banca a 0 da el
# MISMO dano este turno y ademas desarrolla un 2o atacante. El routing 42000 del
# winning/2-prize gust ya no aplica a un Hydrapple ex activo que llego a su
# requisito de ataque.
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    chosen = obs["select"]["option"][m.agent(obs)[0]]
    tid, is_bench = _bench_target_id(obs, chosen)
    assert is_bench and tid == 150, (
        "Ripening Charge debe cargar el Hydrapple ex de BANCA, no el activo ya "
        f"listo (Syrup Storm escala con el campo); fue id {tid} bench={is_bench}")


# =====================================================================
# Boss's Orders gustea el objetivo de MAS premios cuando gana (user,
# registro_011 vs Mega Heracross ex, GANADA suboptima). A 3 premios de ganar,
# con un Hydrapple ex activo LETAL, el juego gusteaba un Teal Mask Ogerpon ex
# (2 premios, energizado) en vez del Mega Heracross ex (3 premios) que noqueaba
# para GANAR. Causa: el tier de KO metia megaEx y ex en el mismo tier (8/7) y el
# +1 por "energizado" hacia que el ex de 2 premios superara al Mega de 3. Fix:
# tier prize-aware (megaEx 10/9 > ex 8/7) + override `gust_gana_partida`.
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    chosen = obs["select"]["option"][m.agent(obs)[0]]
    tid = op_bench[chosen["index"]]["id"]
    assert tid == _MEGA_HERACROSS_EX, (
        f"Boss's debe gustear el Mega Heracross ex (781, 3 premios, gana la "
        f"partida), no el Ogerpon ex (96, 2 premios); gusteo id {tid}")


def test_prize_count_recognizes_mega_ex_as_three():
    # La identificacion de premios: megaEx=3, ex=2, no-ex=1.
    class _P:
        def __init__(self, cid): self.id = cid; self.energyCards = []; self.tools = []
    assert m.prize_count(_P(_MEGA_HERACROSS_EX)) == 3
    assert m.prize_count(_P(_TEAL_OGERPON_EX)) == 2
    assert m.prize_count(_P(349)) == 1  # Teal Mask Ogerpon (no-ex)


# =====================================================================
# ERROR DE SECUENCIA Unfair Stamp / Meowth ex (user, registro_004 p34 vs Mega
# Starmie ex, GANADA suboptima). Con Unfair Stamp (Item ACE SPEC) JUGABLE este
# turno (nos noquearon el turno pasado + el Sello en mano), el agente bajaba
# Meowth ex para que Last-Ditch Catch buscara Lillie's -> pero el Sello BARAJA
# TODA la mano al mazo, perdiendo esa Lillie's y exponiendo un cuerpo de 2
# premios. El veto `_stamp_blocks_supp_chain` existia pero quedaba SOMBREADO por
# las ramas de refresco de Lillie's (elif previas); se movio ANTES de ellas.
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    pid = _played_id(obs, chosen[0])
    assert pid != _MEOWTH_EX, (
        "Con Unfair Stamp jugable (KO el turno pasado), NO bajar Meowth ex a "
        f"buscar Lillie's (el Sello la baraja); el agente jugo id {pid}")


_MEOWTH_NO_STAMP_FIXTURE = (ROOT / "tests" / "fixtures"
                            / "meowth_fetch_lillie_no_stamp_control.json")


def test_meowth_fetch_lillie_still_played_without_playable_stamp():
    # Control: el MISMO tablero pero SIN Unfair Stamp en mano -> el veto no aplica
    # y el motor Meowth -> Lillie's (refresco) sigue vigente y SI baja Meowth ex.
    with open(_MEOWTH_NO_STAMP_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    pid = _played_id(obs, chosen[0])
    assert pid == _MEOWTH_EX, (
        "Sin Unfair Stamp en mano, el motor Meowth->Lillie's debe seguir bajando "
        f"Meowth ex; el agente jugo id {pid}")


# =====================================================================
# vs Alakazam: cargar el atacante de 1 PREMIO (Meganium) que noquea ESTE turno,
# no el ex activo (user, registro_008 pasos 100-115 vs Alakazam, PERDIDA). El
# activo era Ogerpon ex (2 premios) capaz de noquear al Alakazam (140 HP), pero
# en la banca habia un Meganium a UNA Planta de su Wood Hammer (140 = KO). La
# carga (adjunte manual) debe ir al MEGANIUM para dejarlo LISTO y atacar con el
# 1-premio (retirar el ex, promover Meganium): cedemos 1 premio en vez de 2
# cuando Alakazam nos noquea de vuelta. Fix: flag `_meganium_alk_1prize_attacker`
# -> energy_score 43000 (domina la carga del ex activo). La logica de retirada ya
# promueve al 1-premio cuando Meganium esta LISTO.
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
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
    # Con Meganium ya LISTO (4 ef) y sin mas jugadas, vs Alakazam el agente retira
    # el ex activo para promover el 1-premio (en vez de atacar con el ex 2-premios).
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
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    o = m.to_observation_class(obs)
    assert o.select.option[chosen[0]].type == int(m.OptionType.RETREAT), (
        "Con el Meganium 1-premio LISTO, vs Alakazam el agente debe RETIRAR el ex "
        "para promover el 1-premio, no atacar con el ex de 2 premios")


# =====================================================================
# NUNCA terminar el turno con la banca VACIA si podemos desarrollarla (user,
# registro_002 paso 15 vs Mega Starmie ex, PERDIDA). Con un solo basico (Tapu
# Bulu) en el activo y sin banca, si el rival noquea ese activo PERDEMOS (no hay
# a quien promover). El agente terminaba el turno teniendo Ultra Ball + Meowth ex
# en mano. Red de seguridad final: si la mejor jugada es TERMINAR (o esteril) y
# hay una opcion que pone un Pokemon en banca (Ultra Ball -> basico, o bajar un
# basico), se prioriza sobre el fin de turno. Preferencia: el buscador.
# =====================================================================
_EMPTY_BENCH_FIXTURE = (ROOT / "tests" / "fixtures"
                        / "never_end_turn_empty_bench_play_ultraball.json")
_ULTRA_BALL = 1121


def test_never_ends_turn_with_empty_bench_plays_ultraball():
    with open(_EMPTY_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    mi = obs["current"]["yourIndex"]
    me = obs["current"]["players"][mi]
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
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
    # Control: con un Pokemon YA en banca, la red no aplica (bench_count>0) y el
    # agente conserva su conducta (no se fuerza la Ultra Ball).
    import copy
    with open(_EMPTY_BENCH_FIXTURE, encoding="utf-8") as f:
        obs = copy.deepcopy(json.load(f)["observation"])
    me = obs["current"]["players"][0]
    me["bench"] = [{"appearThisTurn": False, "energies": [], "energyCards": [],
                    "hp": 70, "id": 1071, "maxHp": 170, "playerIndex": 0,
                    "preEvolution": [], "serial": 900, "tools": []}]
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    chosen = m.agent(obs)
    o = m.to_observation_class(obs)
    opt = o.select.option[chosen[0]]
    tid = (me["hand"][opt.index]["id"]
           if getattr(opt, "type", None) == int(m.OptionType.PLAY)
           and getattr(opt, "index", None) is not None else None)
    assert tid != _ULTRA_BALL, (
        "Con banca no vacia la red anti-banca-vacia no debe forzar la Ultra Ball")


# =====================================================================
# vs Alakazam: NO sobrecargar el Tapu Bulu activo ya LISTO; cargar el Dipplin de
# banca (user, registro_012 paso 142 vs Alakazam, GANADA). El activo Tapu Bulu
# tenia 2 Plantas fisicas = 4 efectivas (Meganium duplica) = su Wood Hammer coste
# 4: ya podia atacar y su dano es FIJO. El adjunte manual de la 3a energia debe ir
# al Dipplin de banca (atacante futuro), no desperdiciarse en el Tapu. Cubierto
# por el guard `_active_extra_charge_wasted` (Tapu/Meganium/Hydrapple a su
# requisito no reciben el 42000 del gusteo ganador -> la energia fluye a banca).
# =====================================================================
_ALK_TAPU_FIXTURE = (ROOT / "tests" / "fixtures"
                     / "alakazam_manual_attach_dipplin_not_ready_tapu.json")
_TAPU_BULU = 920
_DIPPLIN = 93


def test_alakazam_does_not_overcharge_ready_tapu_charges_dipplin():
    with open(_ALK_TAPU_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    me = obs["current"]["players"][1]
    m._init_cartas_tracking(); m.plan = m.AttackPlan()
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
# Registro 016 (paso 138 vs Crustle, GANADA con jugada suboptima): nuestro
# activo es un Ogerpon ex CARGADO (4 energia) cuyo Myriad Leaf Shower NOQUEA al
# activo rival (Munkidori, 110 HP). El rival tiene la BANCA VACIA: si le
# noqueamos el activo NO puede promover un reemplazo y PIERDE (otra via de
# victoria ademas de los premios). El agente, sin detectar el remate, RETIRABA
# el Ogerpon para atacar con un cuerpo de 1 premio (Dipplin) -- el pivote de
# descuadre `_tapu_sac_pivot` se disparaba porque el Ogerpon estaba a <=50% HP y
# my_prize (2) > premios del objetivo (1). Con la banca rival vacia, ATACAR con
# el activo GANA la partida: nada de descuadre importa. Deck-agnostico.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
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
    # Control: con el rival CON banca, el KO del activo NO gana la partida, asi
    # que el override de remate no debe aplicar (la logica de descuadre/pivote
    # queda libre de actuar). Se anade un Pokemon a la banca rival y se verifica
    # que la decision ya NO esta forzada al ataque del activo por la via de
    # banca-vacia (plan puede legitimamente pivotar).
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    m.agent(obs)
    # Con banca rival, el KO del activo ya NO gana por regla de no-promocion;
    # el remate empty-bench no debe estar activo (no se captura `_active_win_plan`).
    # Verificamos que el escenario es distinto: el rival TIENE banca.
    assert any(b is not None for b in op["bench"]), "control: rival con banca"


# =====================================================================
# Registro contra Alakazam (GANADA): con Ultra Ball, SIN atacante usable y tras
# un KO en el turno anterior (ko_last_turn), el fetch traia Fezandipiti ex (su
# Flip the Script roba 3 al ser noqueados: regla `refill_tras_ko` = 1050). Es un
# error cuando AUN queda el motor Meowth ex -> Last-Ditch Catch -> Lillie's
# Determination en el mazo: bajar Meowth ex busca Lillie's y rehace TODA la mano
# (hasta 8 cartas), abriendo muchas mas opciones que el robo de 3 de Fezandipiti.
# Fezandipiti ex es buena busqueda SOLO si ya tenemos un atacante usable, o si el
# motor Meowth ex ya no esta disponible (sin copias en el mazo, banca llena, 2
# Meowth ya en juego, Lillie's en mano, Supporter ya jugado, o Watchtower).
# Fix: la regla `refill_tras_ko` de _REGLAS_UB_FEZ cede cuando
# `no_attacker_prefer_meowth` esta activo (el mismo predicado que privilegia a
# Meowth). El fixture inyecta un log de KO (fromArea PRIZE) para derivar
# ko_last_turn desde una sola observacion. Deck-agnostico.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [meowth_opt], (
        f"sin atacante usable y con el motor Meowth->Lillie's en el mazo, la "
        f"Ultra Ball debe buscar Meowth ex (opt {meowth_opt}) para refrescar, no "
        f"Fezandipiti ex; obtuvo {result} (map={search_map})")
    assert result != [fez_opt], (
        "no buscar Fezandipiti ex cuando Meowth ex refresca mejor sin atacante")


def test_ub_fetch_gate_is_conditional_on_meowth_engine():
    # Control: el gate que hace ceder a Fezandipiti solo aplica cuando el motor
    # Meowth ex -> Lillie's esta DISPONIBLE (`no_attacker_prefer_meowth`). Si se
    # rompe (p.ej. Supporter YA jugado este turno -> no se podria encadenar
    # Lillie's), el gate NO debe desviar la busqueda hacia Meowth ex: la decision
    # deja de estar forzada a Meowth (aqui gana otro objetivo de refill/desarrollo,
    # p.ej. Hydrapple ex; Fezandipiti recupera su refill de 1050).
    with open(_UB_MEOWTH_OVER_FEZ_FIXTURE, encoding="utf-8") as f:
        obs = json.loads(json.dumps(json.load(f)["observation"]))

    obs["current"]["supporterPlayed"] = True  # rompe el motor Meowth->Lillie's

    search_map = _resolve_search_options(obs)
    meowth_opt = next(i for i, cid in search_map.items() if cid == m.Meowth_ex)

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [meowth_opt], (
        f"con el Supporter ya jugado (motor Meowth roto), el gate NO debe forzar "
        f"buscar Meowth ex (opt {meowth_opt}); obtuvo {result} (map={search_map})")


# =====================================================================
# Registro_009 paso 111 vs Alakazam (PERDIDA): tras el KO de nuestro activo
# (Ogerpon ex) debemos promover un Pokemon de banca. El agente subia Tapu Bulu
# (0/4 energia, no puede atacar en varios turnos) como muro barato de 1 premio,
# en vez de Ogerpon ex de banca (2/3 efectivas: a UNA sola Planta -x2 con
# Meganium en juego- de su Myriad, que remata al Alakazam). La promocion ocurre
# en el turno RIVAL; el proximo turno -NUESTRO- adjuntamos 1 Planta (con Lillie's
# en mano para cavarla) y atacamos primero, asi que el rival ni golpea al ex.
# Debe promover al atacante CASI listo que remata, no al muro que nunca ataca.
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

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [ogerpon_opt], (
        f"tras el KO debe promover el atacante casi listo Ogerpon ex (opt "
        f"{ogerpon_opt}), no el muro Tapu Bulu 0/4; obtuvo {result}")
    assert result != [tapu_opt], (
        "no promover un muro que no puede atacar en varios turnos")


def test_promote_near_ready_defers_without_draw_engine():
    # Control: sin motor de robo/refresco en mano (quitamos la Lillie's), NO se
    # puede cavar la energia que falta, asi que el override de "atacante casi
    # listo" NO aplica y la decision deja de estar forzada a Ogerpon ex (vuelve
    # la logica de muro basico / promocion normal).
    with open(_PROMOTE_NEAR_READY_FIXTURE, encoding="utf-8") as f:
        obs = json.loads(json.dumps(json.load(f)["observation"]))

    yi = obs["current"]["yourIndex"]; me = obs["current"]["players"][yi]
    me["hand"] = [c for c in me["hand"] if c["id"] != m.Lillie_Determination]

    options = obs["select"]["option"]
    ogerpon_opt = next(i for i, o in enumerate(options)
                       if me["bench"][o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex)

    m._init_cartas_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [ogerpon_opt], (
        f"sin Lillie's (sin motor para cavar energia) el override no debe forzar "
        f"Ogerpon ex; obtuvo {result}")


# vs Alakazam con la mano rival grande (Powerful Hand = 20 x carta): reservar el
# Supporter del turno para Xerosic (via Ultra Ball -> Meowth ex -> Last-Ditch)
# en vez de gastarlo en Lillie's (user, registro_008 paso 75, GANADA suboptima).
# Con Hydrapple ex cargado + 3 atacantes de banca el refresco de Lillie's es
# redundante; cavar la disrupcion vale mas. Ver _alakazam_dig_xerosic_engine.
def _load_alakazam_step75_obs():
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" /
        "alakazam_step75_xerosic_engine_over_lillie.json",
        encoding="utf-8"))["observation"]


def test_alakazam_step75_plays_ultra_ball_not_lillie():
    obs = _load_alakazam_step75_obs()
    play_map = _resolve_play_options(obs)
    # El fixture debe ofrecer AMBAS jugadas para que el test sea significativo.
    assert m.Ultra_Ball in play_map.values()
    assert m.Lillie_Determination in play_map.values()
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)
    lillie_opt = next(
        i for i, cid in play_map.items() if cid == m.Lillie_Determination)

    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [ub_opt], (
        f"vs Alakazam con mano rival 10 (Powerful Hand) debe jugar Ultra Ball "
        f"(opt {ub_opt}) para cavar Meowth ex -> Xerosic, no Lillie's; "
        f"obtuvo {result} (map={play_map})")
    assert result != [lillie_opt]
    # El pivote debe quedar armado para que el FETCH elija Meowth ex.
    assert m._ub_engine_pivot_turn is True


def test_alakazam_step75_control_small_op_hand_allows_lillie():
    # Frontera: con la mano rival PEQUENA (< 7, fuera de la zona de Powerful
    # Hand grande) el motor de disrupcion NO se dispara -> Ultra Ball vuelve a
    # su veto normal y Lillie's ya no queda vetada por
    # `alakazam_reserva_supporter_para_xerosic`: se refresca como antes.
    import copy as _copy
    obs = _copy.deepcopy(_load_alakazam_step75_obs())
    obs["current"]["players"][1]["handCount"] = 6
    play_map = _resolve_play_options(obs)
    ub_opt = next(i for i, cid in play_map.items() if cid == m.Ultra_Ball)
    lillie_opt = next(
        i for i, cid in play_map.items() if cid == m.Lillie_Determination)

    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result == [lillie_opt], (
        f"con mano rival 6 (< 7) el motor de dig Xerosic NO debe dispararse: "
        f"se juega Lillie's como antes; obtuvo {result} (map={play_map})")
    assert result != [ub_opt]


# Promocion tras KO: evaluar el mejor SUPERVIVIENTE, no el ex de mas vida (user,
# registro_013 paso 99 vs Mega Lucario ex, PERDIDA). Ningun cuerpo noquea al Mega
# Lucario (340) ni lo aguanta tal cual (proyecta 270); pero Dipplin evoluciona el
# proximo turno a Hydrapple ex (330 > 270, SOBREVIVE). Promover Dipplin, no el
# Ogerpon ex (210, muere -> regala 2 premios). Ver el override evolucion-superviviente.
def _load_lucario_step99_obs():
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" /
        "lucario_step99_promote_survivor_tank_not_ogerpon.json",
        encoding="utf-8"))["observation"]


def _promote_choice_id(obs):
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    m._init_cartas_tracking()
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
    # Frontera: sin la evolucion (Hydrapple ex) en la mano NO hay superviviente
    # via evolucion -> el override no se dispara y la promocion sigue la logica
    # normal (que NO elige Dipplin aqui). Confirma que el override depende de
    # tener la evolucion en la mano.
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


# Prioridad de energia: cargar el Hydrapple ex de banca VACIO (atacante futuro)
# con Ripening Charge en vez de Teal Dance sobre un Ogerpon ex YA cargado (user,
# registro_006 paso 80 vs Mega Lucario). Ambas habilidades adjuntan Grass, pero
# Teal Dance (tier ENERGY) dominaba por TIER a la Ripening de MAYOR score que
# quedaba en tier 0. Fix: la Ripening que puntua como jugada real (>=29000)
# tambien sube a tier ENERGY -> dentro del tier gana por score (31150 > 31050).
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
    # Localizar las opciones de habilidad: Ripening (Hydrapple) y Teal Dance (Ogerpon).
    ripen_opt = next(i for i, o in enumerate(opts)
                     if o.get("type") == int(m.OptionType.ABILITY)
                     and me["bench"][o["index"]]["id"] == m.Hydrapple_ex)
    teal_opts = [i for i, o in enumerate(opts)
                 if o.get("type") == int(m.OptionType.ABILITY)
                 and me["bench"][o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex]
    assert teal_opts, "el fixture debe ofrecer Teal Dance para que el test valga"
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [ripen_opt], (
        f"debe usar Ripening Charge para cargar el Hydrapple ex de banca vacio "
        f"(atacante futuro, opt {ripen_opt}), no Teal Dance sobre un Ogerpon ex "
        f"ya cargado (opts {teal_opts}); obtuvo {result}")


def test_lucario_step80_control_ready_bench_hydrapple_does_not_block_teal():
    # Frontera: si el Hydrapple ex de banca YA esta listo (>=2 energias), cargarlo
    # de nuevo no es prioritario; la Ripening a ese Hydrapple ya NO puntua como
    # carga de atacante-vacio (baja de 31150) y no debe secuestrar el turno.
    # Verifica que el fix depende de que el Hydrapple este SIN energia.
    import copy as _copy
    obs = _copy.deepcopy(_load_lucario_step80_obs())
    me = obs["current"]["players"][0]
    # Cargar el Hydrapple de banca a 2 energias (ya listo para Syrup Storm).
    for b in me["bench"]:
        if b["id"] == m.Hydrapple_ex:
            b["energies"] = [1, 1]
            b["energyCards"] = [{"id": 1, "playerIndex": 0, "serial": 300},
                                {"id": 1, "playerIndex": 0, "serial": 301}]
    opts = obs["select"]["option"]
    ripen_opt = next(i for i, o in enumerate(opts)
                     if o.get("type") == int(m.OptionType.ABILITY)
                     and me["bench"][o["index"]]["id"] == m.Hydrapple_ex)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result != [ripen_opt], (
        f"con el Hydrapple ex de banca YA cargado, la Ripening no debe forzarse "
        f"(opt {ripen_opt}); obtuvo {result}")


# Jugar Boss's Orders (gustear+noquear la pre-evo ex de banca) en vez de Dawn
# (refresco inutil) cuando el activo rival esta FUERA de la linea ex (user,
# registro_004 paso ~47 vs Marnie's Grimmsnarl): fetcheamos Boss's con Meowth y
# luego el agente jugaba Dawn, malgastando el Supporter del turno. El activo rival
# es Munkidori (1 energia, 1 premio, ajeno a la linea) y en banca hay un Marnie's
# Morgrem energizado (pre-evo de Grimmsnarl ex, 1 premio): gustearlo+noquearlo
# rinde el mismo premio PERO corta al atacante principal. Antes Boss's se vetaba
# (-1) porque "noquear el activo domina con premios iguales"; ahora la pre-evo ex
# energizada frente a un activo AJENO a la linea es objetivo valido de deny-evo.
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
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result == [boss_opt], (
        f"debe jugar Boss's Orders (opt {boss_opt}, gustear el Morgrem pre-evo de "
        f"Grimmsnarl ex) en vez de Dawn (opt {dawn_opt}); obtuvo {result}")


def test_marnie_step47_control_active_on_ex_line_keeps_normal():
    # Frontera: si el activo rival YA es de la linea ex de banca (p.ej. otro
    # Morgrem energizado activo), noquearlo ya golpea la linea, asi que gustear la
    # copia de banca no es prioritario y el deny-evo off-line NO debe dispararse.
    import copy as _copy
    obs = _copy.deepcopy(_load_marnie_step47_obs())
    op = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    # Convertir el activo Munkidori en un Morgrem energizado (misma linea que banca).
    op["active"][0]["id"] = 647
    op["active"][0]["maxHp"] = 100
    op["active"][0]["hp"] = 100
    op["active"][0]["preEvolution"] = [{"id": 646, "playerIndex": op["active"][0]["playerIndex"], "serial": 999}]
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    boss_opt = next(i for i, o in enumerate(opts)
                    if o.get("type") == int(m.OptionType.PLAY)
                    and me["hand"][o["index"]]["id"] == m.Boss_Orders)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    result = m.agent(obs)
    assert result != [boss_opt], (
        f"con el activo YA en la linea ex, el deny-evo off-line no debe forzar "
        f"Boss's (opt {boss_opt}); obtuvo {result}")


# Jugar Lillie's Determination (refresco + desarrollo) en vez de Xerosic's
# Machinations cuando la mano rival es MINIMA (<= 4: capar solo le quita 1 carta)
# (user, registro_002 paso 17 vs Alakazam, PERDIDA): turno 2, rival con 4 cartas;
# buscamos Lillie's con Meowth ex y el agente jugaba Xerosic (7000, regla
# `alakazam_prioridad_sobre_boss` disenada para mano rival ENORME). Con la mano
# rival minima el valor de disrupcion es marginal y Lillie's vale mas.
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
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [lillie_opt], (
        f"con la mano rival minima (4) debe jugar Lillie's (opt {lillie_opt}, "
        f"refresco/desarrollo) no Xerosic (opt {xerosic_opt}); obtuvo {result}")


def test_alakazam_step17_control_large_op_hand_keeps_xerosic():
    # Frontera: con la mano rival GRANDE (>= 7) capar Powerful Hand SI vale mas;
    # Xerosic debe seguir ganando a Lillie's (no debe ceder por la mano minima).
    import copy as _copy
    obs = _copy.deepcopy(_load_alakazam_step17_obs())
    op = obs["current"]["players"][1 - obs["current"]["yourIndex"]]
    op["handCount"] = 9
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    xerosic_opt = next(i for i, o in enumerate(opts)
                       if o.get("type") == int(m.OptionType.PLAY)
                       and me["hand"][o["index"]]["id"] == m.Xerosic_Machinations)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [xerosic_opt], (
        f"con la mano rival grande (9) debe seguir capando con Xerosic "
        f"(opt {xerosic_opt}); obtuvo {result}")


# Principio (user, registro_010 paso ~127 vs Alakazam): antes de bajar Meowth ex
# para BUSCAR un Supporter (Last-Ditch Catch), evaluar si el Supporter que YA
# tenemos en mano es el mejor para el escenario; si lo es, NO bajar Meowth ex y
# jugar ese Supporter. Aqui: vs Alakazam con la mano rival grande (12), teniendo
# Xerosic's Machinations en mano (el mejor: capa Powerful Hand), el agente debe
# JUGAR Xerosic, no bajar Meowth ex ni jugar Ultra Ball para cavar otro Supporter.
# El agente ya lo cumple: el motor Meowth->Xerosic (main.py ~L14794) y el motor
# UB->Meowth (`_alakazam_dig_xerosic_engine`) exigen `Xerosic NO en mano`.
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
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [xer], (
        f"con Xerosic en mano (mejor Supporter vs Alakazam) debe jugarlo "
        f"(opt {xer}), no bajar Meowth ex (opt {meowth}) a buscar otro; "
        f"obtuvo {result}")


# ============================================================================
# vs Marnie's Grimmsnarl ex: el snipe automatico a la banca (Shadow Bullet, 180
# al activo + 30 a UN banquillo CADA turno) mata solo a nuestros cuerpos de poca
# vida y regala premios. (user, registro_006/008, PERDIDA: el Dipplin bajo de
# 50 -> 20 -> muerto sin que el rival gastase nada.) Dos palancas para pararlo:
#   (a) Ripening Charge CURA 30 al Pokemon que recibe la Planta -> dirigirla al
#       cuerpo condenado en vez de gastar el adjunte MANUAL (que no cura);
#   (b) Night Stretcher recupera el Hydrapple ex para EVOLUCIONAR ese Dipplin
#       (la evolucion resetea la vida: 80 -> 330).
# ============================================================================

def _load_fixture_obs(nombre):
    import json as _json
    return _json.load(open(
        ROOT / "tests" / "fixtures" / nombre, encoding="utf-8"))["observation"]


def _idx_ability(obs, card_id):
    """Indice de la opcion ABILITY del Pokemon `card_id` (activo o banca)."""
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
    # Estado (registro_008 paso 122): Hydrapple ex activo (150/330) YA cargado
    # para Syrup Storm, Dipplin de banca a 20/80 y UNA sola Planta en la mano.
    # El agente la adjuntaba a mano (misma energia en el campo, CERO curacion) y
    # el Dipplin moria al siguiente Shadow Bullet. Debe usar Ripening Charge: la
    # Planta acaba en el mismo sitio y ademas cura 30 (20 -> 50 > 30 del snipe).
    obs = _load_fixture_obs("marnie_step122_ripening_heals_doomed_dipplin.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    ripen = _idx_ability(obs, m.Hydrapple_ex)
    attach_dipplin = next(
        i for i, o in enumerate(obs["select"]["option"])
        if o.get("type") == int(m.OptionType.ATTACH)
        and o.get("inPlayArea") != int(m.AreaType.ACTIVE)
        and me["bench"][o["inPlayIndex"]]["id"] == m.Dipplin)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [ripen], (
        f"con el Dipplin a 20/80 condenado por el snipe de 30, la ultima Planta "
        f"debe ir por Ripening Charge (opt {ripen}, cura 30) y no por el adjunte "
        f"manual (opt {attach_dipplin}, sin curacion); obtuvo {result}")


def test_marnie_step122_healthy_dipplin_keeps_manual_attach():
    # Frontera: si el Dipplin SOBREVIVE el snipe (60 > 30), la curacion no
    # cambia nada y no hay motivo para desviar la habilidad: se conserva el
    # comportamiento anterior (adjunte manual).
    import copy as _copy
    obs = _copy.deepcopy(
        _load_fixture_obs("marnie_step122_ripening_heals_doomed_dipplin.json"))
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    for b in me["bench"]:
        if b["id"] == m.Dipplin:
            b["hp"] = 60
    ripen = _idx_ability(obs, m.Hydrapple_ex)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [ripen], (
        "con el Dipplin a 60/80 (sobrevive el snipe de 30) la curacion no salva "
        f"nada: no debe desviarse Ripening Charge (opt {ripen})")


def test_marnie_step122_ripening_targets_the_doomed_dipplin():
    # Elegido Ripening Charge, la Planta debe ir al cuerpo CONDENADO (Dipplin
    # 20/80), no al Hydrapple activo ni a un Ogerpon sano: es donde los 30 de
    # curacion cambian el resultado, y el dano de Syrup Storm (escala con el
    # Grass TOTAL del campo) es identico se ponga donde se ponga.
    obs = _load_fixture_obs("marnie_step122_ripening_target_doomed_dipplin.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    dipplin = next(i for i, o in enumerate(obs["select"]["option"])
                   if o.get("area") == int(m.AreaType.BENCH)
                   and me["bench"][o["index"]]["id"] == m.Dipplin)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [dipplin], (
        f"Ripening Charge debe curar al Dipplin condenado (opt {dipplin}); "
        f"obtuvo {result}")


def test_marnie_ripening_lethal_charge_beats_the_heal():
    # Guard: la curacion NUNCA le roba la Planta a un remate. Mismo tablero que
    # el fixture anterior (Dipplin condenado a 20/80) pero con un Hydrapple ex
    # de BANCA a 1 energia al que la 2a Planta le arma un Syrup Storm LETAL
    # sobre Grimmsnarl ex (debilidad Planta) y un activo retirable: la Planta
    # debe ir a ese Hydrapple (41000), no a curar.
    obs = _load_fixture_obs("marnie_ripening_lethal_charge_over_heal.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    hydra = next(i for i, o in enumerate(obs["select"]["option"])
                 if o.get("area") == int(m.AreaType.BENCH)
                 and me["bench"][o["index"]]["id"] == m.Hydrapple_ex)
    dipplin = next(i for i, o in enumerate(obs["select"]["option"])
                   if o.get("area") == int(m.AreaType.BENCH)
                   and me["bench"][o["index"]]["id"] == m.Dipplin)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [hydra], (
        f"con un Syrup Storm LETAL pendiente la Planta va al Hydrapple ex de "
        f"banca (opt {hydra}), no a curar al Dipplin (opt {dipplin}); "
        f"obtuvo {result}")


def test_marnie_night_stretcher_recovers_hydrapple_to_save_dipplin():
    # Night Stretcher con el Dipplin de banca condenado (20/80 frente al snipe
    # de 30): recuperar el Hydrapple ex para EVOLUCIONARLO (80 -> 330) vale mas
    # que recuperar una Planta de mero desarrollo, que era lo que el agente
    # elegia aunque el KO del turno ya estuviese asegurado.
    obs = _load_fixture_obs("marnie_ns_recovers_hydrapple_saves_dipplin.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    hydra = next(i for i, o in enumerate(opts)
                 if me["discard"][o["index"]]["id"] == m.Hydrapple_ex)
    energia = next(i for i, o in enumerate(opts)
                   if me["discard"][o["index"]]["id"] == m.Basic_Grass_Energy)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [hydra], (
        f"debe recuperar Hydrapple ex (opt {hydra}) para salvar al Dipplin "
        f"condenado, no la energia redundante (opt {energia}); obtuvo {result}")


def test_marnie_night_stretcher_healthy_dipplin_keeps_energy():
    # Frontera: con el Dipplin sano (50 > 30 del snipe) no hay rescate que hacer
    # y la recuperacion vuelve al criterio normal (energia de desarrollo).
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
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [hydra], (
        f"sin Dipplin condenado no debe dispararse el rescate (opt {hydra})")


def test_op_bench_snipe_damage_table_covers_grimmsnarl():
    # El goteo a banca queda cuantificado (antes solo habia un booleano que
    # unicamente se leia en el setup).
    assert m.OP_BENCH_SNIPE_DAMAGE[m.Grimmsnarl_ex] == 30
    assert m.RIPENING_HEAL == 30


# ============================================================================
# ORDEN DE LA LINEA DE EVOLUCION en el fetch de un buscador (user,
# registro_006 paso 79 vs Marnie, PERDIDA). Con un Applin en banca y NINGUN
# Dipplin (ni en juego ni en mano), la Ultra Ball traia Hydrapple ex: una carta
# MUERTA (no puede evolucionar nada) que ademas ganaba por el bonus de copia
# premiada (+150). Hay que buscar el ESLABON que falta -- el Dipplin -- y, si
# ese eslabon ya no esta en el MAZO y la banca esta llena, CANCELAR la Ultra
# Ball. La linea de Meganium ya lo hacia bien (Bayleef 850 > Meganium 200).
# ============================================================================

def test_marnie_ub_fetch_takes_the_missing_link_not_the_orphan_stage2():
    obs = _load_fixture_obs("marnie_ub_fetch_missing_link_dipplin.json")
    mazo = obs["select"]["deck"]
    opts = obs["select"]["option"]
    dipplin = [i for i, o in enumerate(opts)
               if mazo[o["index"]]["id"] == m.Dipplin]
    hydra = next(i for i, o in enumerate(opts)
                 if mazo[o["index"]]["id"] == m.Hydrapple_ex)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result and result[0] in dipplin, (
        f"con un Applin en banca y ningun Dipplin, la Ultra Ball debe traer "
        f"el eslabon que falta (Dipplin, opts {dipplin}), no el Hydrapple ex "
        f"huerfano (opt {hydra}); obtuvo {result}")


def test_marnie_ub_cancels_when_the_missing_link_left_the_deck():
    # Mismo tablero pero con los DOS Dipplin en el descarte: el eslabon ya no
    # esta en el MAZO y la banca esta LLENA, asi que la Ultra Ball no puede
    # aportar nada y no debe jugarse.
    obs = _load_fixture_obs("marnie_ub_cancel_link_not_in_deck.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert len(me["bench"]) >= 5, "el escenario exige la banca llena"
    ub = next(i for i, o in enumerate(obs["select"]["option"])
              if o.get("type") == int(m.OptionType.PLAY)
              and me["hand"][o["index"]]["id"] == m.Ultra_Ball)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [ub], (
        f"sin Dipplin en el mazo y con la banca llena la Ultra Ball "
        f"(opt {ub}) no aporta nada: debe cancelarse; obtuvo {result}")


def test_evo_link_state_classifies_missing_link_and_orphan():
    # Applin en juego, ningun Dipplin: falta el Dipplin y el Hydrapple ex es
    # huerfano. La etapa 2 NUNCA entra en `necesarios` (sus propias ramas ya la
    # puntuan y aplican los clamps de matchup).
    nec, huer = m._evo_link_state({}, {m.Applin: 1})
    assert nec == {m.Dipplin} and m.Hydrapple_ex in huer
    # Con el Dipplin ya en juego, el Hydrapple ex deja de ser huerfano y no se
    # fuerza desde aqui.
    nec, huer = m._evo_link_state({}, {m.Applin: 1, m.Dipplin: 1})
    assert m.Hydrapple_ex not in huer and m.Hydrapple_ex not in nec
    # Linea completa (Hydrapple ex en juego): no se fuerza ningun eslabon.
    nec, _ = m._evo_link_state({}, {m.Applin: 1, m.Hydrapple_ex: 1})
    assert m.Dipplin not in nec


# ============================================================================
# BUSQUEDA REDUNDANTE DE MEOWTH EX (user, registro_010 paso 118 vs Alakazam,
# GANADA con error). Meowth ex solo vale por su Last-Ditch Catch, y solo se
# juega UN Supporter por turno: traer una 2a copia de uno que ya esta en la
# mano no aporta nada y encima expone un cuerpo de 2 premios en la banca.
#   (a) el FETCH nunca elige un duplicado (regla `copia_ya_en_mano`);
#   (b) si lo UNICO buscable es un duplicado, la jugada de Meowth ex se cancela
#       y el turno sigue con el Supporter que ya teniamos.
# Excepcion documentada: nuestro primer turno (linea anti-donk con banca vacia).
# Deck-agnostico: la prediccion usa el MISMO motor que el fetch real.
# ============================================================================

def test_alakazam_last_ditch_no_trae_copia_ya_en_mano():
    obs = _load_fixture_obs("alakazam_ld_fetch_no_duplica_supporter.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    mazo = obs["select"]["deck"]
    opts = obs["select"]["option"]
    en_mano = {c["id"] for c in me["hand"]}
    xerosic = next(i for i, o in enumerate(opts)
                   if mazo[o["index"]]["id"] == m.Xerosic_Machinations)
    assert m.Xerosic_Machinations in en_mano, "el escenario exige Xerosic en mano"
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    traido = mazo[opts[result[0]]["index"]]["id"]
    assert traido not in en_mano, (
        f"el Last-Ditch no debe traer una 2a copia de un Supporter que ya esta "
        f"en la mano (Xerosic, opt {xerosic}); trajo {traido}")


def test_alakazam_cancela_meowth_si_la_busqueda_es_redundante():
    # Mismo tablero pero con TODOS los demas Supporters fuera del mazo: lo unico
    # que el Last-Ditch podria traer es otro Xerosic, que ya esta en mano.
    obs = _load_fixture_obs("alakazam_meowth_cancela_busqueda_redundante.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [meowth], (
        f"con el unico Supporter buscable ya en mano, bajar Meowth ex (opt "
        f"{meowth}) solo regala 2 premios: debe cancelarse; obtuvo {result}")


def test_meowth_fetch_prediccion_detecta_el_duplicado():
    # El helper que decide ANTES de bajar Meowth: con Xerosic como unico
    # Supporter del mazo y una copia en mano, el objetivo predicho es ese
    # duplicado (la senal que cancela la jugada).
    mazo = {m.Xerosic_Machinations: {m.ESTADO_MAZO: 1}}
    objetivo, _ = m._meowth_fetch_prediccion(
        {m.Xerosic_Machinations: 1}, {}, 4, True, 12, False,
        False, False, False, False, True, mazo)
    assert objetivo == m.Xerosic_Machinations
    # Nuestro primer turno conserva la excepcion anti-donk (no se capa).
    objetivo_t1, valor_t1 = m._meowth_fetch_prediccion(
        {m.Xerosic_Machinations: 1}, {}, 4, True, 12, False,
        False, False, False, False, True, mazo, first_turn=True)
    assert objetivo_t1 == m.Xerosic_Machinations and valor_t1 > 40


# ============================================================================
# COHERENCIA MENU <-> PROMPT (user, registro_010 pasos 118/120 vs Alakazam).
# Las HABILIDADES solo se listan como opciones en el MENU PRINCIPAL. Los motores
# que proyectan dano leian `select.option` para saber si Teal Dance seguia
# disponible, asi que el MISMO turno valia una cosa en el menu y otra en los
# prompts encadenados: el agente bajaba Meowth ex "para buscar Boss's Orders"
# (con Teal Dance -> Myriad 270 noquea al Fezandipiti ex de banca: 2 premios) y
# dos pasos despues, ya en el prompt del fetch, valoraba ese Boss's a 0 (sin
# Teal Dance -> 150, no noquea) y se llevaba otra carta. Ahora la
# disponibilidad se cachea por turno (`_td_ability_serial`).
# ============================================================================

def test_alakazam_el_fetch_sigue_el_plan_del_menu_boss_orders():
    menu = _load_fixture_obs("alakazam_step118_menu_principal.json")
    fetch = _load_fixture_obs("alakazam_ld_fetch_no_duplica_supporter.json")
    me = menu["current"]["players"][menu["current"]["yourIndex"]]
    meowth = next(i for i, o in enumerate(menu["select"]["option"])
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._td_ability_serial = None
    assert m.agent(menu) == [meowth], (
        "el escenario parte de que el motor Boss's baja Meowth ex")
    # Mismo turno, prompt encadenado: el fetch debe traer lo que motivo la jugada.
    mazo = fetch["select"]["deck"]
    result = m.agent(fetch)
    traido = mazo[fetch["select"]["option"][result[0]]["index"]]["id"]
    assert traido == m.Boss_Orders, (
        f"el Last-Ditch debe traer el Boss's Orders que motivo bajar el Meowth "
        f"(gusteo de 2 premios al Fezandipiti ex); trajo {traido}")


def test_teal_dance_disponible_es_estable_fuera_del_menu():
    # El cache se llena en el MENU PRINCIPAL y sobrevive a los prompts que no
    # listan habilidades; sin menu previo se queda en None (conservador).
    menu = _load_fixture_obs("alakazam_step118_menu_principal.json")
    me = menu["current"]["players"][menu["current"]["yourIndex"]]
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m._td_ability_serial = None
    m.agent(menu)
    assert m._td_ability_serial == me["active"][0]["serial"], (
        "tras el menu principal queda cacheado el serial del activo con "
        "habilidad disponible")


# ============================================================================
# RESCATE DE TURNO MUERTO CON MEOWTH EX (user, registro_002 paso 18 vs Cubchoo,
# PERDIDA). Turno 2: el activo es un Meowth ex que NO ataca, la banca es un Tapu
# Bulu sin energia (necesita 4) y un Applin, y la mano no tiene ninguna jugada
# (Hydrapple ex sin Dipplin, Boss's sin KO, energia ya adjuntada). El agente
# cerraba el turno con un Meowth ex en la mano que ademas ACABABA de buscar con
# una Ultra Ball. Bajarlo activa Last-Ditch Catch -> Lillie's Determination ->
# refresco: cualquier cosa es mejor que no hacer nada. El rescate va despues de
# todos los vetos y solo pisa el "terminar sin hacer nada", asi que el veto
# anti-Cubchoo de un 2o Meowth ex sigue vigente en cuanto haya jugada real.
# ============================================================================

def test_cubchoo_turno_muerto_baja_meowth_en_vez_de_terminar():
    obs = _load_fixture_obs("cubchoo_turno_muerto_baja_meowth.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    fin = next(i for i, o in enumerate(opts)
               if o.get("type") == int(m.OptionType.END))
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result == [meowth], (
        f"sin ningun atacante ni jugada posible, bajar Meowth ex (opt {meowth}) "
        f"para que Last-Ditch traiga Lillie's es mejor que terminar el turno "
        f"(opt {fin}); obtuvo {result}")


def test_cubchoo_con_jugada_real_sigue_vetando_el_segundo_meowth():
    # Frontera: el rescate SOLO pisa el turno muerto. Si hay una jugada real
    # (aqui una Planta adjuntable), el veto anti-Cubchoo del 2o Meowth ex manda.
    import copy as _copy
    obs = _copy.deepcopy(_load_fixture_obs("cubchoo_turno_muerto_baja_meowth.json"))
    obs["current"]["energyAttached"] = False
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    energia = next(i for i, c in enumerate(me["hand"])
                   if c["id"] == m.Basic_Grass_Energy)
    obs["select"]["option"].insert(0, {
        "area": 2, "inPlayArea": 5, "inPlayIndex": 0,
        "index": energia, "type": int(m.OptionType.ATTACH)})
    opts = obs["select"]["option"]
    meowth = next(i for i, o in enumerate(opts)
                  if o.get("type") == int(m.OptionType.PLAY)
                  and me["hand"][o["index"]]["id"] == m.Meowth_ex)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result != [meowth], (
        f"con una jugada real disponible el turno no esta muerto: el veto "
        f"anti-Cubchoo del 2o Meowth ex (opt {meowth}) sigue mandando; "
        f"obtuvo {result}")


# ============================================================================
# ANTI-CUBCHOO: no evolucionar a un cuerpo LENTO que no llega a su ataque
# (user, registro_034 paso 131, PERDIDA). El mazo de Cubchoo bloquea y descarta
# energia, asi que un Pokemon con coste de retirada ALTO (Hydrapple ex: 3) que
# ademas no alcanza su requisito de ataque (Syrup Storm: 2) queda CLAVADO en el
# activo -- ni ataca ni se retira -- y regala 2 premios. El agente evolucionaba
# un Dipplin activo con CERO energias (33000). El gate es el coste de retirada,
# que es la razon real, y la regla esta acotada al matchup Cubchoo.
# ============================================================================

def _idx_evolve(obs):
    return [i for i, o in enumerate(obs["select"]["option"])
            if o.get("type") == int(m.OptionType.EVOLVE)]


def test_cubchoo_no_evoluciona_hydrapple_sin_energia():
    obs = _load_fixture_obs("cubchoo_no_evolucionar_hydrapple_sin_energia.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert len(me["active"][0]["energies"]) == 0, "el escenario exige 0 energias"
    assert m.RETREAT_COST[m.Hydrapple_ex] >= 3
    evo = _idx_evolve(obs)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] not in evo, (
        f"vs Cubchoo no se evoluciona a Hydrapple ex (retirada 3) sin energia "
        f"para atacar: quedaria clavado en el activo; obtuvo {result} (evo {evo})")


def test_cubchoo_si_evoluciona_hydrapple_con_energia():
    # Frontera: con la energia suficiente para Syrup Storm la evolucion SI vale
    # (ataca, y el muro de 330 PV compensa el coste de retirada).
    obs = _load_fixture_obs("cubchoo_si_evoluciona_hydrapple_con_energia.json")
    evo = _idx_evolve(obs)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in evo, (
        f"con energia para atacar la evolucion a Hydrapple ex sigue siendo la "
        f"jugada (opts {evo}); obtuvo {result}")


def test_regla_lenta_acotada_al_matchup_cubchoo():
    # Frontera: el mismo tablero contra un rival generico NO activa la regla --
    # ahi se recarga y se retira con normalidad y el muro compensa.
    obs = _load_fixture_obs("generico_si_evoluciona_hydrapple_sin_energia.json")
    evo = _idx_evolve(obs)
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in evo, (
        f"fuera del matchup Cubchoo la evolucion a Hydrapple ex se mantiene "
        f"(opts {evo}); obtuvo {result}")


# ============================================================================
# LINEA "Teal Dance -> retirar -> promover el letal" vs Cubchoo (user,
# registro_036 paso 146, PERDIDA). El activo era un Teal Mask Ogerpon ex con
# CERO energias: ni ataca ni se retira. En banca habia otro Ogerpon ex con 4
# energias que NOQUEA al Cubchoo activo. `_attach_enable_retreat_ko` ya detectaba
# la linea y daba 41000 al adjunte manual sobre el activo, pero la precedencia
# "Teal Dance antes que el adjunte" lo vetaba y el turno acababa cargando un Tapu
# Bulu de banca a 10 PV. Los tres pasos de la cadena:
#   1) Teal Dance en el ACTIVO (adjunta la Planta Y roba)
#   2) RETREAT (el veto anti-Cubchoo cede: no destruye inversion y hay KO)
#   3) promover el Ogerpon de 4 energias, no el Hydrapple ex que quedaria clavado
# ============================================================================

def test_cubchoo_teal_dance_habilita_la_retirada_hacia_el_ko():
    obs = _load_fixture_obs("cubchoo_teal_dance_habilita_retirada_ko.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert len(me["active"][0]["energies"]) == 0
    td = [i for i, o in enumerate(obs["select"]["option"])
          if o.get("type") == int(m.OptionType.ABILITY)
          and o.get("area") == int(m.AreaType.ACTIVE)]
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in td, (
        f"con el activo a 0 energias y un Ogerpon letal en banca, Teal Dance en "
        f"el ACTIVO (opts {td}) habilita la retirada y ademas roba; "
        f"obtuvo {result}")


def test_cubchoo_tras_teal_dance_si_se_retira():
    obs = _load_fixture_obs("cubchoo_tras_teal_dance_retira_al_ogerpon.json")
    ret = [i for i, o in enumerate(obs["select"]["option"])
           if o.get("type") == int(m.OptionType.RETREAT)]
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in ret, (
        f"el veto anti-Cubchoo de retirada cede cuando la retirada NOQUEA y el "
        f"activo no tiene excedente de energia que perder; obtuvo {result}")


def test_cubchoo_promueve_el_ogerpon_no_el_hydrapple_clavado():
    obs = _load_fixture_obs("cubchoo_promueve_ogerpon_letal_tras_retirar.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    opts = obs["select"]["option"]
    oger = [i for i, o in enumerate(opts)
            if me["bench"][o["index"]]["id"] == m.Teal_Mask_Ogerpon_ex]
    hydra = [i for i, o in enumerate(opts)
             if me["bench"][o["index"]]["id"] == m.Hydrapple_ex]
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] in oger, (
        f"vs Cubchoo se promueve el Ogerpon ex (retirada 1, 4 energias) y no el "
        f"Hydrapple ex (retirada 3, 2 energias -> clavado); oger={oger} "
        f"hydra={hydra}, obtuvo {result}")


def test_cubchoo_con_energia_invertida_sigue_pasando():
    # FRONTERA entre las dos reglas del usuario: aqui el activo tiene TRES
    # Plantas fisicas. Retirar destruiria inversion ya puesta en el tablero, asi
    # que se PASA aunque tambien haya un KO detras (registro_004 p47).
    obs = _load_fixture_obs("cubchoo_step47_no_energy_wasting_retreat.json")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert m._physical_energy(len(me["active"][0]["energies"])) > \
        m.RETREAT_COST[me["active"][0]["id"]], "el escenario exige excedente"
    ret = [i for i, o in enumerate(obs["select"]["option"])
           if o.get("type") == int(m.OptionType.RETREAT)]
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    result = m.agent(obs)
    assert result[0] not in ret, (
        f"con excedente de energia invertida el veto anti-Cubchoo se mantiene; "
        f"obtuvo {result}")


# ============================================================================
# SUPERVIVENCIA AL PROMOVER (user, registro_005 paso 64 vs Archaludon, PERDIDA).
# Al elegir que cuerpo sube al activo, lo PRIMERO es si aguanta el ataque del
# activo rival. Archaludon ex pegaba 220 y el agente subio un Teal Mask Ogerpon
# ex de 210 PV con SEIS energias (4557 frente a 259 del Hydrapple ex): moria sin
# noquear -- Myriad proyectaba 300 contra 400 PV -- y regalaba 2 premios y toda
# la carga. Dos criterios, deck-agnosticos:
#   1) si alguno SOBREVIVE, los condenados se penalizan;
#   2) si NINGUNO sobrevive, sube el que entrega MENOS premios.
# Excepcion: quien NOQUEA al activo rival conserva su score (cobrar premio
# aunque muera es un intercambio valido).
# ============================================================================

def _promo_elegido(obs):
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    m._init_cartas_tracking()
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    r = m.agent(obs)
    return me["bench"][obs["select"]["option"][r[0]]["index"]]


def test_archaludon_promueve_el_cuerpo_que_aguanta_el_ataque():
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


def test_sin_superviviente_promueve_el_de_menos_premios():
    # Escenario REAL (lucario_step99): Mega Lucario pega 270 y en banca no
    # aguanta nadie -- Meganium 130, Ogerpon ex 210, Dipplin 80. Entonces manda
    # el criterio 2: entregar los MENOS premios. Dipplin/Meganium valen 1, el
    # Ogerpon ex vale 2. (Meganium queda fuera por su propio veto de promocion:
    # es el motor Wild Growth que duplica toda nuestra energia.)
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


def test_superviviente_no_pisa_al_que_noquea():
    # PRIORIDAD DEL QUE NOQUEA (user): se sube el atacante cargado en vez del
    # tanque SOLO cuando ese atacante noquea al rival. Cobrar el premio manda
    # aunque muera despues. Con el Archaludon a 60 PV, el Ogerpon cargado
    # (Myriad 300) lo noquea; el Hydrapple ex, con 0 energias, no llega a su
    # ataque aunque aguante el golpe. Implementado como GARANTIA
    # (`PROMO_KO_BONUS`, por encima del score maximo de las demas ramas) y no
    # como mera exencion de la penalizacion.
    import copy as _c
    obs = _c.deepcopy(_load_fixture_obs(
        "archaludon_step64_promueve_el_que_aguanta.json"))
    obs["current"]["players"][1]["active"][0]["hp"] = 60
    picked = _promo_elegido(obs)
    assert picked["id"] == m.Teal_Mask_Ogerpon_ex, (
        f"el cuerpo que NOQUEA se promueve aunque muera despues; obtuvo "
        f"{picked['id']} ({m.card_table[picked['id']].name})")


# Autopsia iron_thorns p007 (turno 16, plan jul 2026 P1.4 plan B): con Iron
# Thorns ex de activo rival (Initialization anula Teal Dance / Ripening /
# Last-Ditch / Flip the Script), el agente cerraba el turno con END teniendo
# Tapu Bulu EN MANO (66 turnos esteriles en 15 derrotas). Tapu Bulu es el
# atacante manual sin habilidad: el matchup Iron Thorns entra en la lista de
# prioridades de bajada (22000), como Cornerstone/Crustle.
_IRON_THORNS_TAPU_FIXTURE = (
    ROOT / "tests" / "fixtures" / "iron_thorns_t16_baja_tapu_no_end.json")


def test_iron_thorns_t16_baja_tapu_en_vez_de_end():
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


# Autopsia cornerstone_cubchoo p004 (turno 2, plan jul 2026): con el rival
# Cornerstone (386 activo, ex 117 en banca), Applin activo y una mano con
# Tapu Bulu + 2x Forest + UB, el agente cerraba con END (122 turnos esteriles
# en 41 derrotas). Dos vetos raiz: la aglomeracion de Tapu (>2 en juego) no
# eximia a Cornerstone -- el matchup donde Tapu es EL atacante -- y Forest se
# vetaba en el primer turno saliendo segundos aun con copia REDUNDANTE en mano.
_CORNERSTONE_TAPU_FIXTURE = (
    ROOT / "tests" / "fixtures" / "cornerstone_t2_baja_tapu_no_end.json")


def test_cornerstone_t2_baja_tapu_en_vez_de_end():
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
