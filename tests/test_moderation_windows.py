from app.core.topics import GROWING_LAST_HOUR, RECURRING_LAST_DAY
from app.storage.db import Store


def test_moderation_prioritizes_bursts_and_topics_accumulating_over_a_day(tmp_path):
    store = Store(tmp_path / "topics.db")
    now = 1_000_000

    def topic(title, offsets):
        topic_id = store.topic_add(title, [], [], now - max(offsets))
        for offset in sorted(offsets, reverse=True):
            store.topic_report(topic_id, now - offset, None, "web", None, title, title, [])

    topic("Sprawa z poprzednich dni", [90_000] * 20)
    topic("Dużo przez dobę", [7200] * 14 + [1800])
    topic("Nagły wzrost", [120] * 5)
    topic("Poniżej progu", [7200] * 13 + [1800])

    rows = store.topics_board(now, now - 7 * 86400, hourly_threshold=GROWING_LAST_HOUR,
                              daily_threshold=RECURRING_LAST_DAY)
    assert [(row["title"], row["last_hour"], row["last_day"]) for row in rows] == [
        ("Nagły wzrost", 5, 5),
        ("Dużo przez dobę", 1, 15),
        ("Poniżej progu", 1, 14),
        ("Sprawa z poprzednich dni", 0, 0),
    ]
