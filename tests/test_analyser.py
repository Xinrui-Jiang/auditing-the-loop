"""M1 rule layer, offline: a hand-made extraction for DB-38 and DB-35 becomes a checklist; bad spans are caught."""
import json

import pytest
from pydantic import ValidationError

from loopauditor.analyser import Extraction, assemble, bad_spans
from loopauditor.config import PROMPT_SET_30

ROWS = {json.loads(l)["shot_id"]: json.loads(l) for l in PROMPT_SET_30.open()}


def extraction(**overrides) -> Extraction:
    base = dict(
        actions=[{"span": "The call ends.", "check": "The phone call ends."},
                 {"span": "Haitong's portfolio slips.", "check": "The portfolio slips from her hands."}],
        elements=[{"span": "Pages scatter", "kind": "prop", "check": "Loose pages scatter."}],
        other_people=[], premise=[{"fact": "Grandma is addressed but not present.", "span": "Grandma, they found me."}],
        transition_scripted=False, physics_involved=False)
    return Extraction.model_validate({**base, **overrides})


def test_assemble_db38_ids_priorities_and_spans():
    cl = assemble(ROWS["DB-38"], extraction(), author="test")
    ids = [i.id for i in cl.items]
    assert ids[:3] == ["A1.1", "A2.1", "A2.2"]
    assert cl.item("A1.1").priority == "critical" and cl.item("A1.1").params.line == "Grandma, they found me."
    assert cl.item("A3.1").params.element == ROWS["DB-38"]["setting"]  # setting first, then the sound cue, then LLM props
    assert cl.item("A3.2").params.element == ROWS["DB-38"]["sfx_cue"]
    assert cl.item("C2.1").params.target_interval == (2, 3)
    assert cl.item("B1.1").priority == "minor" and cl.conflicts == []
    assert len(cl.family("B")) == 7 and cl.item("A4.1").text.endswith("cast: HAITONG. Nobody else appears.")


def test_cast_comes_from_the_script():
    cl = assemble(ROWS["DB-35"], extraction(other_people=["HUSBAND", "ZHAO WANRU"], physics_involved=True), author="test")
    assert "cast: HE XI, HUSBAND, ZHAO WANRU" in cl.item("A4.1").text and cl.item("A4.1").priority == "critical"
    assert cl.item("A4.2").text.startswith("Only HE XI speaks") and cl.conflicts == []
    assert cl.item("B1.1").priority == "major"


def test_spoken_line_is_not_an_action():
    cl = assemble(ROWS["DB-38"], extraction(actions=[{"span": "Grandma, they found me.", "check": "x"}]), author="test")
    assert cl.family("A")[1].id != "A2.1"


def test_bad_spans_are_reported_not_dropped():
    x = extraction(actions=[{"span": "She slams the door.", "check": "x"}])
    assert bad_spans(x, ROWS["DB-38"]["prompt_raw"]) == ["She slams the door."]


def test_extraction_shape_is_enforced():
    with pytest.raises(ValidationError):
        Extraction.model_validate({"actions": [], "elements": []})


def test_pronoun_of_other_gender_counts_as_second_person():
    # DB-37: the RED-ROBED WOMAN speaks while "He smashes the jade"; the LLM listed nobody
    cl = assemble(ROWS["DB-37"], extraction(actions=[], elements=[], premise=[]), author="test")
    assert "cast: RED-ROBED WOMAN, the man" in cl.item("A4.1").text and len(cl.conflicts) == 1


def test_delivery_cue_is_not_an_action():
    cl = assemble(ROWS["DB-38"], extraction(actions=[{"span": "(crying)", "check": "x"}, {"span": "The call ends.", "check": "y"}]), author="test")
    assert [i.id for i in cl.family("A") if i.check_id == "A2"] == ["A2.1"] and cl.item("A2.1").params.element == "The call ends."
