"""Regression slice 4 of 8. Mega Lucario, the Archaludon retreat arithmetic and
the energy routing that enables it."""

from main_support import *  # noqa: F401,F403  (fixtures and helpers)

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

def test_crustle_fighting_is_STURDY_not_ex_immune():
    """It asserted the opposite until 11 August 2026, and the card says so.

    The two Crustle share a name and nothing else. 345 prints "Mysterious Rock
    Inn" -- prevent all damage from your opponent's Pokemon {ex} -- and 533
    prints "Sturdy": at full HP it survives a lethal hit at 10. The old
    assertion here ("la variante Fighting de Crustle tambien es inmune a
    nuestros ex") was a BELIEF, and the simulator's own card data contradicts
    it, which is the exact failure `utils/differential_oracle.py` was written
    for -- a test asserting the same wrong belief the code has, green forever.

    Found by `utils/op_immunity_census.py`, which diffs the three immunity
    tables against the printed text. Exposure was 0 of the 87 real lists, so
    nothing was bleeding; the entry is corrected because the meta rotates.
    """
    oger = _FakePkm(m.Teal_Mask_Ogerpon_ex, energies=[1, 1, 1], hp=210)
    assert m.Crustle_Fighting not in m.EX_IMMUNE_IDS
    assert m.Crustle_Fighting in m.FULL_HP_SURVIVE_IDS

    # Wounded: Sturdy does not apply and the body takes everything (Grass
    # weakness doubles it).
    herida = _FakePkm(m.Crustle_Fighting, hp=140, maxHp=150)
    assert m._our_effective_damage(oger, herida, 200) == 400

    # At FULL hp a lethal hit is capped at hp - 10, which is what Sturdy says
    # and all it says.
    entera = _FakePkm(m.Crustle_Fighting, hp=150)
    assert m._our_effective_damage(oger, entera, 200) == 140


def test_the_other_crustle_is_the_wall_and_stays_one():
    """The control: removing the wrong entry must not remove the real wall.
    345 is in 51 opposing decks and it is what this project routes around."""
    oger = _FakePkm(m.Teal_Mask_Ogerpon_ex, energies=[1, 1, 1], hp=210)
    muro = _FakePkm(m.Crustle_Grass, hp=150)
    assert m.Crustle_Grass in m.EX_IMMUNE_IDS
    assert m._our_effective_damage(oger, muro, 200) == 0

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
    #
    # `_ub_meowth_pending` is injected because the sequence no longer sets it on
    # its own: the Ultra Ball of that turn used to be spent on a Meowth ex WITH
    # THE STAMP PENDING, and that purchase is exactly what
    # `the_stamp_shuffles_the_last_ditch_supporter` now refuses (the fetch takes
    # Teal Mask Ogerpon ex instead -- see
    # tests/test_the_stamp_shuffles_what_the_ultra_ball_buys.py). What this test
    # guards is unchanged and is the other half of the same rule: the Stamp's
    # veto is one of ORDER, so once the Stamp leaves the hand a Meowth ex we
    # have already paid an Ultra Ball for is put down.
    #
    # El tablero lleva un Fezandipiti ex con Flip the Script viva (nos noquearon
    # el turno pasado: es la misma condicion que hacia jugable el Sello), y desde
    # `_TIER_FEZ_BEFORE_SEARCH` (agosto 2026) ese robo gratis va ANTES de bajar
    # el cuerpo de busqueda. La pregunta de este test -- si el Meowth se baja o
    # no una vez el Sello ya no esta -- se lee con la habilidad ya cobrada.
    from fez_menu import sin_flip_the_script
    _, _, data = _lucario_s115_replay()
    post = sin_flip_the_script(data["synthetic_post_stamp"])
    m.AGENT_STATE._ub_meowth_pending = True
    ch = m.agent(post)
    opt = post["select"]["option"][ch[0]]
    hand = post["current"]["players"][0]["hand"]
    assert (opt.get("type") == int(OptionType.PLAY)
            and opt.get("index", -1) < len(hand)
            and hand[opt["index"]]["id"] == m.Meowth_ex), (
        f"tras jugar el Unfair Stamp, el motor Meowth ex vuelve a activarse y se "
        f"baja para encadenar Last-Ditch -> Lillie's; obtuvo {ch} -> {opt}")

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

def test_marnie_step20_uses_teal_dance_instead_of_charging_the_chikorita():
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
    target_path = (me["active"][0] if opt.get("inPlayArea") == 4
               else me["bench"][opt["inPlayIndex"]])
    assert target_path["id"] != m.Chikorita, (
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
