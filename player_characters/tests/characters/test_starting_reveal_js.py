"""Behaviour tests for static/js/starting_reveal.js.

Node runs the real script against a small fake DOM with a fake clock
(starting_reveal_harness.js). Each test plays one scenario and checks the
final state. Skipped when Node is not installed.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE.parent.parent.parent / "static"
HARNESS = HERE / "starting_reveal_harness.js"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

ANNOUNCEMENT = "You received: +1 Backpack, +2 Rations, +1 Rope. Starting coins: 15 gp."
ALL = [True, True, True]


def run(scenario, reduced=False):
    out = subprocess.run(
        [NODE, str(HARNESS), str(STATIC_DIR), scenario, "1" if reduced else "0"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(out.stdout)


def assert_finished(state):
    assert state["revealed"] == ALL
    assert state["armed"] is False
    assert state["coinsHidden"] is False
    assert state["coinsText"] == "15 gp"
    assert state["live"] == ANNOUNCEMENT
    assert state["replayHidden"] is False


def test_first_play_reveals_items_in_turn_then_coins_then_sheet():
    r = run("first-play")
    start = r["start"]
    assert start["revealed"] == [True, False, False]
    # Coins stay hidden until the coin step; nothing announced yet.
    assert start["coinsHidden"] is True
    assert start["live"] == ""
    assert start["replayHidden"] is True
    assert r["midCoins"]["revealed"] == ALL
    assert r["midCoins"]["live"] == ""
    assert r["end"]["coinsHidden"] is False
    assert_finished(r["after"])
    assert r["after"]["navigations"] == []
    assert r["later"]["navigations"] == ["/sheet/"]


def test_replay_completes_the_whole_reveal():
    r = run("replay")
    assert r["afterClick"]["revealed"] == [True, False, False]
    assert r["afterClick"]["coinsHidden"] is True
    assert r["afterClick"]["replayHidden"] is True
    assert_finished(r["end"])


def test_replay_during_coin_count_up_ignores_stale_run():
    r = run("replay-during-coins")
    # The first run's count-up would have ended here; it must not finish
    # the new run early.
    assert r["mid"]["live"] == ""
    assert r["mid"]["replayHidden"] is True
    assert r["mid"]["coinsHidden"] is True
    assert_finished(r["end"])


def test_click_during_play_finishes_reveal_and_stays_on_page():
    end = run("click-item-during-play")["end"]
    assert_finished(end)
    assert end["navigations"] == []


def test_hidden_tab_during_play_finishes_reveal_and_stays_on_page():
    end = run("tab-hidden-during-play")["end"]
    assert_finished(end)
    assert end["navigations"] == []


def test_click_after_finish_cancels_auto_advance():
    end = run("click-after-finish")["end"]
    assert_finished(end)
    assert end["navigations"] == []


def test_reduced_motion_turned_on_mid_play_shows_everything():
    end = run("reduced-motion-turned-on")["end"]
    assert_finished(end)
    assert end["navigations"] == []


def test_reduced_motion_shows_everything_at_once_without_auto_advance():
    r = run("first-play", reduced=True)
    assert_finished(r["start"])
    assert r["later"]["navigations"] == []
