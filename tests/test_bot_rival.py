"""The reference opponent (`utils/bot_rival.py`) plays the ability engine.

Until 2026-08-02 the bot's docstring said *"Never RETREAT or ABILITY"*.
A non-obvious consequence: **the harness was BLIND to the decks whose engine IS an
ability**. Against Marnie's Grimmsnarl ex it never activated Munkidori's
*Adrena-Brain* — the ability that in `registros/marnie` took 5 of the 7 prizes the
opponent won WITHOUT ATTACKING — so any rule of ours against that engine
measured NEUTRAL by construction.

These tests pin the four pieces without which the engine does not come to exist:

1. it activates abilities (with anti-loop guards: one per Pokémon per turn);
2. when moving counters it takes the **MAXIMUM** amount (the generic fallback took
   `minCount`: 1 counter = 10 damage, the ability did almost nothing);
3. it places them where they **kill**, and on a tie where they give the most prizes;
4. it charges the energy onto the body whose ability REQUIRES it (without that Munkidori
   never switches on), and it **retreats** when the active cannot attack (without
   that a gusted body stays nailed in front forever).
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(ROOT / "utils"))

from bot_rival import BotRival
from cg.api import AreaType, OptionType, SelectContext

MUNKIDORI = 112
FROSLASS = 104
GRIMMSNARL = 648
MORGREM = 647
OGERPON = 96          # ex, 2 prizes
MEGANIUM = 710        # non-ex, 1 prize
TAPU = 920
HYDRAPPLE = 150       # ex, 2 prizes, 330 HP


def pk(cid, hp, max_hp, energies=0):
    return {"id": cid, "hp": hp, "maxHp": max_hp,
            "energies": [7] * energies, "energyCards": [], "tools": [],
            "preEvolution": [], "serial": cid * 10 + hp}


def obs(select, me_active, me_bench, op_active, op_bench, yidx=1, turn=6):
    jugadores = [None, None]
    jugadores[yidx] = {"active": [me_active] if me_active else [],
                       "bench": list(me_bench), "prize": [None] * 4,
                       "hand": [], "handCount": 0, "deckCount": 30,
                       "discard": []}
    jugadores[1 - yidx] = {"active": [op_active] if op_active else [],
                           "bench": list(op_bench), "prize": [None] * 4,
                           "hand": [], "handCount": 0, "deckCount": 30,
                           "discard": []}
    return {"current": {"players": jugadores, "yourIndex": yidx, "turn": turn,
                        "result": -1, "stadium": [], "retreated": False,
                        "energyAttached": False, "supporterPlayed": False},
            "select": select, "logs": []}


def sel(context, option, minCount=1, maxCount=1):
    return {"context": int(context), "option": option,
            "minCount": minCount, "maxCount": maxCount, "type": 1}


@pytest.fixture
def bot():
    return BotRival()


# --- 1. it activates abilities, with an anti-loop guard --------------------

def test_it_uses_the_ability_in_the_menu(bot):
    o = obs(sel(SelectContext.MAIN,
                [{"type": int(OptionType.ABILITY),
                  "area": int(AreaType.BENCH), "index": 0},
                 {"type": int(OptionType.END)}]),
            pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 100, 110, 1)],
            pk(OGERPON, 80, 210), [])
    assert bot.agent(o) == [0], "el bot vuelve a ignorar las habilidades"


def test_it_does_not_repeat_the_same_ability_in_a_turn(bot):
    def menu():
        return obs(sel(SelectContext.MAIN,
                       [{"type": int(OptionType.ABILITY),
                         "area": int(AreaType.BENCH), "index": 0},
                        {"type": int(OptionType.END)}]),
                   pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 100, 110, 1)],
                   pk(OGERPON, 80, 210), [])
    assert bot.agent(menu()) == [0]
    assert bot.agent(menu()) == [1], "segunda activación: bucle infinito"


def test_a_new_turn_frees_the_ability_again(bot):
    def menu(turn):
        o = obs(sel(SelectContext.MAIN,
                    [{"type": int(OptionType.ABILITY),
                      "area": int(AreaType.BENCH), "index": 0},
                     {"type": int(OptionType.END)}]),
                pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 100, 110, 1)],
                pk(OGERPON, 80, 210), [])
        o["current"]["turn"] = turn
        return o
    assert bot.agent(menu(6)) == [0]
    assert bot.agent(menu(6)) == [1]
    assert bot.agent(menu(8)) == [0]


# --- 2 and 3. Adrena-Brain: the maximum amount and a destination that KILLS -

def test_it_moves_the_maximum_number_of_counters(bot):
    o = obs(sel(SelectContext.REMOVE_DAMAGE_COUNTER_COUNT,
                [{"type": 0, "number": 1}, {"type": 0, "number": 2},
                 {"type": 0, "number": 3}]),
            pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 80, 110, 1)],
            pk(OGERPON, 80, 210), [])
    assert bot.agent(o) == [2], "coge el mínimo: la habilidad casi no hace daño"
    assert bot._contadores == 3


def _fijar_tres_contadores(bot):
    """It chains the AMOUNT select, as in a real game: that is the one that leaves
    `_contadores` ready for the DESTINATION select of the same turn."""
    bot.agent(obs(sel(SelectContext.REMOVE_DAMAGE_COUNTER_COUNT,
                      [{"type": 0, "number": 1}, {"type": 0, "number": 2},
                       {"type": 0, "number": 3}]),
                  pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 80, 110, 1)],
                  pk(OGERPON, 80, 210), []))
    assert bot._contadores == 3


def test_the_counters_go_to_the_body_they_kill(bot):
    """An Ogerpon ex at 80 does not die to 30; the Meganium at 20 does."""
    _fijar_tres_contadores(bot)
    o = obs(sel(SelectContext.DAMAGE_COUNTER,
                [{"type": 3, "area": int(AreaType.ACTIVE), "index": 0,
                  "playerIndex": 0},
                 {"type": 3, "area": int(AreaType.BENCH), "index": 0,
                  "playerIndex": 0}]),
            pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 80, 110, 1)],
            pk(OGERPON, 80, 210), [pk(MEGANIUM, 20, 160)])
    assert bot.agent(o) == [1]


def test_on_equal_kos_the_one_worth_more_prizes_wins(bot):
    """Both die to 30: the ex (2 prizes) wins over the Meganium (1)."""
    _fijar_tres_contadores(bot)
    o = obs(sel(SelectContext.DAMAGE_COUNTER,
                [{"type": 3, "area": int(AreaType.ACTIVE), "index": 0,
                  "playerIndex": 0},
                 {"type": 3, "area": int(AreaType.BENCH), "index": 0,
                  "playerIndex": 0}]),
            pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 80, 110, 1)],
            pk(OGERPON, 20, 210), [pk(MEGANIUM, 20, 160)])
    assert bot.agent(o) == [0], "el ex de 2 premios va primero"


def test_the_counters_come_off_the_most_damaged_body(bot):
    o = obs(sel(SelectContext.REMOVE_DAMAGE_COUNTER,
                [{"type": 3, "area": int(AreaType.BENCH), "index": 0,
                  "playerIndex": 1},
                 {"type": 3, "area": int(AreaType.BENCH), "index": 1,
                  "playerIndex": 1}]),
            pk(GRIMMSNARL, 320, 320, 2),
            [pk(MUNKIDORI, 100, 110, 1), pk(MUNKIDORI, 60, 110, 1)],
            pk(OGERPON, 80, 210), [])
    assert bot.agent(o) == [1], "el de 50 de daño da más munición que el de 10"


# --- 4. the energy that switches the engine on, and the retreat -----------

def test_it_charges_the_body_whose_ability_needs_energy(bot):
    """With the active already charged, the Darkness goes to the dry Munkidori."""
    o = obs(sel(SelectContext.MAIN,
                [{"type": int(OptionType.ATTACH), "area": int(AreaType.HAND),
                  "index": 0, "inPlayArea": int(AreaType.ACTIVE),
                  "inPlayIndex": 0},
                 {"type": int(OptionType.ATTACH), "area": int(AreaType.HAND),
                  "index": 0, "inPlayArea": int(AreaType.BENCH),
                  "inPlayIndex": 0}]),
            pk(GRIMMSNARL, 320, 320, 2), [pk(MUNKIDORI, 110, 110, 0)],
            pk(OGERPON, 210, 210), [])
    assert bot.agent(o) == [1], "sin esta energía Adrena-Brain no existe"


def test_with_a_dry_active_the_energy_goes_to_the_active(bot):
    o = obs(sel(SelectContext.MAIN,
                [{"type": int(OptionType.ATTACH), "area": int(AreaType.HAND),
                  "index": 0, "inPlayArea": int(AreaType.ACTIVE),
                  "inPlayIndex": 0},
                 {"type": int(OptionType.ATTACH), "area": int(AreaType.HAND),
                  "index": 0, "inPlayArea": int(AreaType.BENCH),
                  "inPlayIndex": 0}]),
            pk(GRIMMSNARL, 320, 320, 0), [pk(MUNKIDORI, 110, 110, 0)],
            pk(OGERPON, 210, 210), [])
    assert bot.agent(o) == [0]


def test_it_retreats_if_the_active_cannot_attack(bot):
    o = obs(sel(SelectContext.MAIN,
                [{"type": int(OptionType.RETREAT)},
                 {"type": int(OptionType.END)}]),
            pk(FROSLASS, 90, 90, 0), [pk(GRIMMSNARL, 320, 320, 2)],
            pk(OGERPON, 210, 210), [])
    assert bot.agent(o) == [0], (
        "el cuerpo gusteado se queda clavado delante y el gusteo gana solo")


def test_with_an_attack_available_it_does_not_retreat(bot):
    o = obs(sel(SelectContext.MAIN,
                [{"type": int(OptionType.RETREAT)},
                 {"type": int(OptionType.ATTACK), "attackId": 937},
                 {"type": int(OptionType.END)}]),
            pk(GRIMMSNARL, 320, 320, 2), [pk(MORGREM, 100, 100, 2)],
            pk(OGERPON, 210, 210), [])
    assert bot.agent(o) == [1]


def test_it_promotes_the_body_with_the_most_energy(bot):
    o = obs(sel(SelectContext.TO_ACTIVE,
                [{"type": 3, "area": int(AreaType.BENCH), "index": 0,
                  "playerIndex": 1},
                 {"type": 3, "area": int(AreaType.BENCH), "index": 1,
                  "playerIndex": 1}]),
            None, [pk(FROSLASS, 90, 90, 0), pk(GRIMMSNARL, 320, 320, 2)],
            pk(OGERPON, 210, 210), [])
    assert bot.agent(o) == [1]


def test_it_gusts_the_body_it_can_knock_out(bot):
    """A SWITCH over the OPPOSING bench: Shadow Bullet (180) kills the Meganium (160)
    but not the Hydrapple ex (330), which is also worth 2 prizes: the KO rules."""
    o = obs(sel(SelectContext.SWITCH,
                [{"type": 3, "area": int(AreaType.BENCH), "index": 0,
                  "playerIndex": 0},
                 {"type": 3, "area": int(AreaType.BENCH), "index": 1,
                  "playerIndex": 0}]),
            pk(GRIMMSNARL, 320, 320, 2), [],
            pk(OGERPON, 210, 210),
            [pk(HYDRAPPLE, 330, 330), pk(MEGANIUM, 160, 160)])
    assert bot.agent(o) == [1], (
        "gustea el ex de 2 premios que NO puede matar en vez del KO seguro")
