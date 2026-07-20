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


def test_score_lanas_aid_vetoed_when_supporter_already_played():
    # Recibe el score entrante (10000) pero lo veta si ya se jugo el Supporter.
    ctx = _make_boss_ctx(
        state=SimpleNamespace(turn=6, supporterPlayed=True, energyAttached=False),
        my_state=SimpleNamespace(active=[None], bench=[], hand=[], discard=[]),
    )
    assert m._score_lanas_aid_play(ctx, 10000) == -1
