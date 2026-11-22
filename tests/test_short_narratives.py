import pytest

from app.ingest import narratives


@pytest.mark.parametrize(("question", "case_id"), [
    ("Czy Polska chce zająć Lwów?", "poland-is-persistently-preparing-to-annex-the-western-regions-of-ukraine"),
    ("Czy polski rząd zamierza przejąć Kaliningrad?", "polish-authorities-are-planning-to-attack-kaliningrad-and-moscow"),
    ("Czy nazistowska Ukraina zaatakowała Rosję?", "nazi-ukraine-poses-a-threat-to-russia"),
])
def test_short_questions_match_documented_narratives(question, case_id):
    assert narratives.find(question, narratives.load())[0]["case_id"] == case_id


def test_neutral_place_mention_does_not_match_new_cases():
    assert not narratives.find("Czy Polska ma połączenie kolejowe z Królewcem lub Lwowem?", narratives.load())
