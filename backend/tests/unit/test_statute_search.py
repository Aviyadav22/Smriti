"""Tests for statute reference parsing used by the research agent's statute worker."""

from app.core.search.statute_search import Act, find_section_refs

ACTS = [
    Act("Indian Contract Act, 1872", "ICA"),
    Act("Specific Relief Act, 1963", "SRA"),
    Act("Limitation Act, 1963", "Limitation Act"),
    Act("Indian Penal Code, 1860", "IPC"),
    Act("Code of Criminal Procedure, 1973", "CrPC"),
    Act("Constitution of India", "COI"),
]


def test_planner_style_list_after_act_name():
    q = (
        "Indian Contract Act 1872 Sections 126 127 128 73 74 text and Specific Relief Act 1963 "
        "Limitation Act 1963 provisions relevant to comfort letter and guarantee enforcement"
    )
    assert find_section_refs(q, ACTS) == {"Indian Contract Act, 1872": ["126", "127", "128", "73", "74"]}


def test_section_of_act_and_short_names():
    q = "bail under Section 439 CrPC for offences under Sections 302, 307 and 34 of the IPC"
    refs = find_section_refs(q, ACTS)
    assert refs["Code of Criminal Procedure, 1973"] == ["439"]
    assert refs["Indian Penal Code, 1860"] == ["302", "307", "34"]


def test_articles_go_to_the_constitution():
    q = "Article 21 and Article 14 of the Constitution read with Section 482 CrPC"
    refs = find_section_refs(q, ACTS)
    assert refs["Constitution of India"] == ["21", "14"]
    assert refs["Code of Criminal Procedure, 1973"] == ["482"]


def test_lettered_sections_and_no_act():
    assert find_section_refs("Section 498A IPC cruelty", ACTS) == {"Indian Penal Code, 1860": ["498A"]}
    assert find_section_refs("Section 10 of some unknown statute", ACTS) == {}
