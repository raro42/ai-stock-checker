"""Offline tests for param-grid autoresearch mutator."""

from scripts.autoresearch_param_worker import apply_param, _format_value


SAMPLE = '''
SHORT_SMA = 20
REQUIRE_REL_STRENGTH = False
MAX_RETURN_STDEV = 0.015
# idea: old idea
'''


def test_apply_param_int():
    out, err = apply_param(SAMPLE, "SHORT_SMA", 15)
    assert err is None
    assert "SHORT_SMA = 15" in out
    assert "# idea: param: SHORT_SMA=15" in out


def test_apply_param_bool():
    out, err = apply_param(SAMPLE, "REQUIRE_REL_STRENGTH", True)
    assert err is None
    assert "REQUIRE_REL_STRENGTH = True" in out


def test_apply_param_float():
    out, err = apply_param(SAMPLE, "MAX_RETURN_STDEV", 0.018)
    assert err is None
    assert "MAX_RETURN_STDEV = 0.018" in out


def test_format_bool():
    assert _format_value(True) == "True"
    assert _format_value(False) == "False"
