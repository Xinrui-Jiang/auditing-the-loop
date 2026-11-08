"""M3 offline parts: WER normalisation and the dialogue status thresholds."""
from loopauditor.tools import dialogue_status, normalise_speech, word_error_rate


def test_wer_ignores_case_and_punctuation():
    assert word_error_rate("Grandma, they found me.", "grandma they found me") == 0.0
    assert word_error_rate("He won't help us.", "") == 1.0
    assert 0 < word_error_rate("Doctor! My mistress—she's breech!", "Doctor, my mistress is breech") < 1


def test_dialogue_status_thresholds():
    assert dialogue_status("en", 0.0, "en") == "pass"
    assert dialogue_status("en", 0.4, "en") == "uncertain"
    assert dialogue_status("en", 0.6, "en") == "fail"
    assert dialogue_status("zh", 0.0, "en") == "fail"  # right words in the wrong language still fail A1


def test_normalise_speech():
    assert normalise_speech("What… what is this?") == "what what is this"


def test_estimated_cost_from_price_table():
    from loopauditor.generate import estimated_cost
    assert estimated_cost("seedance-2.0", 8, "480p") == 0.538
