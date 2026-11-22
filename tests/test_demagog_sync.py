from app.core.service import get_service
from app.ingest.demagog import DemagogSync, URL


ARTICLE = "https://demagog.org.pl/fake_news/testowy-artykul/"
RSS = f"""<rss><channel><item><title>Weryfikacja zdjęcia</title><link>{ARTICLE}</link>
<pubDate>Fri, 20 Nov 2026 14:19:28 +0000</pubDate></item></channel></rss>""".encode()
PAGE = f'''<script type="application/ld+json">{{"@type":"ClaimReview","url":"{ARTICLE}",
"claimReviewed":"Zdjęcie pokazuje marsz w Krakowie.","reviewRating":{{"alternateName":"Fałsz"}}}}</script>'''.encode()


def test_demagog_import_persists_once_and_restores_for_search(monkeypatch, tmp_path):
    monkeypatch.setenv("PRAWDOWID_ENV", "development")
    monkeypatch.setenv("PRAWDOWID_DATA_DIR", str(tmp_path))
    get_service.cache_clear()
    service = get_service()
    fetch = {URL: RSS, ARTICLE: PAGE}.__getitem__
    try:
        sync = DemagogSync(service, fetcher=fetch)
        assert sync.sync() == 1
        assert sync.sync() == 0
        row, = service.corpus.search("Zdjęcie pokazuje marsz w Krakowie", url=ARTICLE)[:1]
        assert "Ocena Demagoga: Fałsz" in row["excerpt"]
        source_id = row["id"]
        service.corpus.remove(source_id)
        DemagogSync(service, fetcher=fetch).load_current()
        assert service.corpus.search("Zdjęcie pokazuje marsz w Krakowie", url=ARTICLE)[0]["id"] == source_id
    finally:
        service.corpus.close()
        get_service.cache_clear()
