"""The guide's Campaign Rules no longer spell out the Control token's clicks: each button's hover text does.
These pin the instructions that moved there (2026-10-09), so a later edit cannot drop one silently."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTROL = open(os.path.join(ROOT, "src", "tts", "control.lua"), encoding="utf-8").read()
BOARD = open(os.path.join(ROOT, "src", "StillHour", "Board.ttslua"), encoding="utf-8").read()


def test_every_moved_instruction_is_on_a_button():
    for text, src in (
        ("move the Hours deck and click once per Hour", CONTROL),          # Hour
        ("Hour III's extra +1 at a Church location", CONTROL),
        ("After Hold Back, do not right-click", CONTROL),
        ("use Resolve on the token", CONTROL),                              # Dissonance
        ("Canceled Hour VIII: right-click twice", CONTROL),
        ("the Press removes it", CONTROL),                                  # [static]
        ("The Crossing, The Debt of Hours or the finale", CONTROL),        # Appointed
        ("to undo a canceled advance", CONTROL),
        ("The House Always Wins", CONTROL),                                 # banked Memory
        ("Anchor Point's token takes one", CONTROL),
        ("click it again", CONTROL),                                        # Reset Loop
        ("Unticking a mistake takes them back", CONTROL),                   # Knowledge
        ("none is automatic", CONTROL),                                     # Contest
        ("clicked before choosing, Age asks", CONTROL),                     # Age
        ("do not also \"\n          .. \"click Dissonance", CONTROL),       # Static token Resolve
        ("The Turning: one click here, two on Dissonance", BOARD),          # Dissonance raised
        ("for example Foreknowledge", BOARD),                               # Loop-power Memory
        ("Records \"\n            .. \"Office takes one back", BOARD),       # Years pending
        ("Disengage and exhaust the Appointed yourself", BOARD),            # Hold Back
        ("lands on a closed or unrevealed location", BOARD),                # Hunt
    ):
        assert text in src, "a button lost its instruction: %r" % text
