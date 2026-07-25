"""Tests for clean-code agent helpers."""

from scripts.clean_code_agent import ROOT_SLOP_SCRIPTS, STALE_DOC_REDIRECTS, Report


def test_root_slop_list_nonempty():
    assert "test_scanner.py" in ROOT_SLOP_SCRIPTS


def test_stale_doc_redirect_mentions_readme():
    body = STALE_DOC_REDIRECTS["ENHANCED_SYSTEM_README.md"]
    assert "README.md" in body
    assert body.strip().startswith("# Deprecated")


def test_report_collects():
    r = Report()
    r.add("a.py", "comment_slop", "x")
    assert len(r.findings) == 1
