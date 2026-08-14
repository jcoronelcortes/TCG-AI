"""Regression slice 5 of 8. Promotion after a KO, the doomed active, and the
refresh engines on a poor board."""

from main_support import *  # noqa: F401,F403  (fixtures and helpers)

def test_alakazam_step85_without_xerosic_boss_returns():
    # A counterfactual: with no Xerosic in hand, Boss's is the play again.
    result, obs, _ = _alakazam_s85_replay(
        observation_key="synthetic_sin_xerosic")
    assert _played_card(obs, result) == m.Boss_Orders, (
        f"sin Xerosic en mano el gusteo de 2 premios sigue siendo correcto; "
        f"obtuvo {result} -> id {_played_card(obs, result)}")

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
    # El hueco de Supporter de este turno esta LIBRE y en la mano hay un
    # Xerosic's Machinations con la mano rival en seis: la red de `finalizar`
    # lo juega ANTES del ataque que cierra el turno (OP_HAND_PRICED_PLAY_IDS),
    # asi que la afirmacion del registro -- con el Tapu Bulu cargado se ATACA --
    # se comprueba en el menu siguiente, con el hueco ya gastado.
    _, obs, _ = _dragapult_s138_replay()
    despues = spend_the_supporter_slot(obs, m.Xerosic_Machinations)
    result = m.agent(despues)
    opt = despues["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con el Tapu Bulu activo ya cargado y el Hydrapple ex de banca "
        f"condenado (70/330 frente a Phantom Dive), lo correcto es ATACAR; "
        f"obtuvo {result} -> {opt}")

def test_dragapult_step138_cashes_the_dying_supporter_slot_first():
    """La otra mitad del mismo turno: el hueco de Supporter muere con el ataque
    y la mano rival esta en seis, asi que el cap se cobra primero. No es un
    cambio de plan -- el ataque sale en el menu siguiente (test de arriba)."""
    result, obs, _ = _dragapult_s138_replay()
    assert _played_card(obs, result) == m.Xerosic_Machinations, (
        f"con el hueco libre y su mano en 6, el cap se juega antes del ataque; "
        f"obtuvo {result} -> {obs['select']['option'][result[0]]}")

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

_MARNIE_S82_FIXTURE = (
    ROOT / "tests" / "fixtures" / "marnie_step82_meowth_refill_con_ko.json")

def _marnie_s82_replay(observation_key=None):
    with open(_MARNIE_S82_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    seq = data["sequence"]
    for item in seq[:-1]:
        m.agent(item["observation"])
    obs = data[observation_key] if observation_key else seq[-1]["observation"]
    return m.agent(obs), obs, data

def test_marnie_step82_plays_meowth_even_though_the_active_knocks_out():
    # El KO de hoy no paga el relevo de manana: bajar el Basico NO consume el
    # ataque (PLAY vive en _TIER_DEVELOP=40 y el ataque en tier 0), asi que el
    # premio sigue intacto y ademas se cobra el hueco de Supporter del turno.
    result, obs, _ = _marnie_s82_replay()
    assert _played_card(obs, result) == m.Meowth_ex, (
        f"con el activo como UNICO atacante listo y los dos Supporters de la "
        f"mano vetados, bajar Meowth ex va antes del ataque que cierra el "
        f"turno; obtuvo {result}")

def test_marnie_step82_the_attack_is_still_on_the_menu():
    # El ataque no se pierde: sigue ofertado y puntuado por encima de terminar.
    _, obs, _ = _marnie_s82_replay()
    assert any(o.get("type") == int(OptionType.ATTACK)
               for o in obs["select"]["option"]), (
        "el escenario deja de medir lo que dice si el ataque no esta en el menu")

def test_marnie_step82_a_charged_relief_on_the_bench_attacks():
    # Frontera 1: con un segundo Ogerpon ex ya cargado en banca hay respuesta si
    # cae el activo, y un cuerpo de 2 premios no vale un refresco.
    result, obs, _ = _marnie_s82_replay(
        observation_key="synthetic_relevo_en_banca")
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"con relevo cargado en banca el refresco no justifica exponer 2 "
        f"premios; obtuvo {result} -> {opt}")

def test_marnie_step82_at_their_match_point_it_attacks():
    # Frontera 2: aritmetica pura. Con el rival a 2 premios, el Meowth ex que
    # bajamos ES la partida; ningun refresco de mano compra eso de vuelta.
    result, obs, _ = _marnie_s82_replay(
        observation_key="synthetic_rival_a_dos_premios")
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.ATTACK), (
        f"a match point del rival no se regala un cuerpo de 2 premios por "
        f"robar cartas; obtuvo {result} -> {opt}")

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
    # Boundary: with no Tapu Bulu among the options the setup falls to the next
    # rung it HAS. In this fixture the only other Pokemon offered is the
    # Chikorita, so the full order (Tapu Bulu, Applin, Chikorita, and only then
    # the ex) is pinned in
    # tests/test_the_opening_puts_one_prize_in_front.py, not here.
    obs = _setup_obs()
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    obs["select"]["option"] = [o for o in obs["select"]["option"]
                               if me["hand"][o["index"]]["id"] != m.Tapu_Bulu]
    assert _basico_elegido(obs, m.agent(obs)) == m.Chikorita, (
        "sin Tapu Bulu en la mano, la eleccion del inicial no cambia")

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
    chosen = bench[obs["select"]["option"][result[0]]["index"]]["id"]
    assert chosen == m.Tapu_Bulu, (
        f"al promover tras retirar el Chikorita se sube Tapu Bulu (140 PV), "
        f"no el Applin de 40; obtuvo {m.card_table[chosen].name}")

def _obs_after_retreating():
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
    obs, _ = _obs_after_retreating()
    result = m.agent(obs)
    opt = obs["select"]["option"][result[0]]
    assert opt.get("type") == int(OptionType.EVOLVE), (
        f"con el Chikorita ya en banca, Bayleef se juega sobre el; obtuvo {opt}")

def test_dragapult_p29_completes_meganium_with_forest():
    # Forest of Vitality allows evolving the just-played Bayleef: the chain
    # Chikorita -> Bayleef -> Meganium is completed in the same turn.
    obs, yo = _obs_after_retreating()
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
    chosen = bench[obs["select"]["option"][result[0]]["index"]]["id"]
    assert chosen == m.Tapu_Bulu, (
        f"con Lillie's en mano y sin atacante listo se sube el basico de 1 "
        f"premio mas resistente (Tapu Bulu 140), no el Applin de 40; obtuvo "
        f"{m.card_table[chosen].name}")

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

    assert result != [attack_opt], (
        f"ex condenado que no noquea y muere el proximo turno, sin atacante de "
        f"banca: NO atacar (opt {attack_opt}); obtuvo {result}")
    # ...and once the free development of the turn is done, the retreat-
    # sacrifice is still the play. See `_retreat_survives_the_development`
    # below for why this test now measures the OUTCOME and not the first
    # action: the Meowth ex that goes down first does not consume the retreat.
    assert _after_benching_the_meowth(obs) == "RETREAT", (
        f"tras bajar el cuerpo, RETIRAR (opt {retreat_opt}) para ceder 1 premio")

def _after_benching_the_meowth(obs):
    """The same board with the Meowth ex already on the bench and off the menu.

    THE ORDER OF THE TURN CHANGED, NOT ITS OUTCOME (registro_008 step 57,
    episode 90874130). `_ready_attack_is_inert` stopped a ready-but-worthless
    attack from vetoing the hand engine, and on these two boards the Meowth ex
    play (21350, `_TIER_DEVELOP`) now precedes the retreat. It does not replace
    it: a Pokemon PLAY is tier 40 and the retreat is tier 0, so the body goes
    down, Last-Ditch Catch fetches the Supporter and the retreat-sacrifice --
    which is what these two tests were built to pin -- still happens in the
    same turn. This helper measures exactly that, so the assertion is about the
    turn and not about which of its actions comes first.
    """
    o = copy.deepcopy(obs)
    mine = o["current"]["players"][o["current"]["yourIndex"]]
    meowth = next(c for c in mine["hand"] if c["id"] == m.Meowth_ex)
    mine["hand"].remove(meowth)
    mine["handCount"] = len(mine["hand"])
    mine["bench"].append({
        "appearThisTurn": True, "energies": [], "energyCards": [], "hp": 170,
        "id": m.Meowth_ex, "maxHp": 170, "playerIndex": mine["active"][0]["playerIndex"],
        "preEvolution": [], "serial": 999, "tools": []})
    o["select"]["option"] = [x for x in o["select"]["option"]
                             if x.get("type") != int(OptionType.PLAY)]
    m._init_cards_tracking(); m.plan = m.AttackPlan()
    chosen = o["select"]["option"][m.agent(o)[0]]
    return {int(OptionType.RETREAT): "RETREAT",
            int(OptionType.ATTACK): "ATTACK",
            int(OptionType.END): "END"}.get(chosen.get("type"), str(chosen))

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

    attack_opt = next(i for i, o in enumerate(options)
                      if o.get("type") == int(OptionType.ATTACK))

    m._init_cards_tracking(); m.plan = m.AttackPlan()
    result = m.agent(obs)

    assert result != [attack_opt], (
        f"generalizacion (rival no-Lucario que one-shotea): NO atacar "
        f"(opt {attack_opt}); obtuvo {result}")
    assert _after_benching_the_meowth(obs) == "RETREAT", (
        f"generalizacion: tras el desarrollo, RETIRAR (opt {retreat_opt})")

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
