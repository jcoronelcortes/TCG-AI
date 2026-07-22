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
        watchtower_in_play=False,
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
        watchtower_in_play=False,
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
        watchtower_in_play=False,
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

    result = m.agent(obs)

    assert result == [teal_active_opt], (
        f"debe hacer Teal Dance en el activo (opt {teal_active_opt}) para alcanzar el KO "
        f"considerando la resistencia de Duraludon; obtuvo {result}"
    )
    assert result[0] not in tapu_attach_opts, (
        "no cargar Tapu Bulu de banca cuando el activo aun no noquea (resistencia) y Teal Dance lo habilita"
    )


def test_ogerpon_damage_counts_own_energy_only_not_target():
    from types import SimpleNamespace as _NS
    tgt = _NS(id=169, hp=130, energies=[8, 8, 8], maxHp=130)  # 3 energia objetivo
    og = _NS(id=m.Teal_Mask_Ogerpon_ex, hp=180, energies=[1, 1, 1, 1])
    base = m._attacker_base_damage(m.Teal_Mask_Ogerpon_ex, tgt, 4,
                                   grass_scale=0, teal_self_energy=4, bench_count=5)
    assert base == 150, f"Ivy Bludgeon = 30+30*energia PROPIA (4) = 150, no cuenta la del objetivo; obtuvo {base}"


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
