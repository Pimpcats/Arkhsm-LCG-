"""The campaign is one connected story: no thread is written without a reader, every
pointer resolves, every act and resolution leads somewhere, and the finale's
endings depend on the choices made (tools/story_map.py does the work)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.story_map import Map  # noqa: E402

MAP = Map().run()


def _fails(check):
    return [f for f in MAP.fails if f.startswith(check + " ")]


def test_every_knowledge_entry_matters_beyond_its_district():
    assert not _fails("K"), "\n".join(_fails("K"))


def test_every_choice_option_changes_the_finale_and_echoes_elsewhere():
    assert not _fails("C"), "\n".join(_fails("C"))


def test_loop_marks_and_records_are_read():
    assert not _fails("M"), "\n".join(_fails("M"))


def test_every_pointer_resolves():
    assert not _fails("P"), "\n".join(_fails("P"))


def test_every_act_and_district_leads_somewhere():
    assert not _fails("A"), "\n".join(_fails("A"))


def test_the_agenda_is_complete():
    assert not _fails("H"), "\n".join(_fails("H"))


def test_the_finale_has_several_endings_that_depend_on_the_story():
    assert not _fails("E"), "\n".join(_fails("E"))
    e = MAP.rows["E endings"]
    assert len(e["defined"]) >= 7 and set(e["defined"]) == set(e["reachable"])
    assert e["distinct_open_sets"] >= 4
