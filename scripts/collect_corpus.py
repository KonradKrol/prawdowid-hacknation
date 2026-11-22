"""Zbieranie rozszerzenia korpusu: komunikaty rządowe (gov.pl), samorządowe i fact-checki.

    python scripts/collect_corpus.py --cache <katalog> --out Research/Prawdoskop_Korpus_Rozszerzenie.jsonl

Dla każdej publikacji zapisuje wydawcę, adres, datę publikacji (i aktualizacji, gdy podana),
dosłowne akapity z treści (fragment związany z tezą) i warunki użycia. Fragmenty pochodzą
z pobranej strony; skrypt odrzuca stronę bez daty, bez tytułu albo bez akapitu treści.
Wymaga `beautifulsoup4` (requirements-dev.txt).
"""

import argparse
import concurrent.futures as cf
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; Prawdoskop-research/1.0; zbieranie korpusu HackNation)"
TODAY = date(2026, 11, 22).isoformat()
MONTHS = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
          "września", "października", "listopada", "grudnia")
GOV_USAGE = ("Treści tekstowe Gov.pl udostępniane na licencji CC BY-SA 4.0 "
             "(https://www.gov.pl/web/gov/warunki-korzystania, sprawdzono 22.11.2026). Cytat z podaniem wydawcy i linku.")
QUOTE_USAGE = ("Krótki cytat z podaniem wydawcy i linku (prawo cytatu, art. 29 ustawy o prawie autorskim). "
               "Pełna treść u wydawcy. Odrębnych warunków ponownego użycia nie sprawdzono.")
OFFICIAL_USAGE = ("Komunikat organu samorządu; krótki cytat z podaniem wydawcy i linku. Materiały urzędowe nie są "
                  "przedmiotem prawa autorskiego (art. 4 pkt 2 ustawy), warunki serwisu nie były osobno sprawdzane.")

# (grupa, sekcja gov.pl, wydawca, temat, limit)
GOV = [
    ("rcb/komunikaty", "Rządowe Centrum Bezpieczeństwa", "Alert RCB i ostrzeżenia kryzysowe", 40),
    ("gis/ostrzezenia", "Główny Inspektorat Sanitarny", "ostrzeżenia publiczne o produktach", 34),
    ("gis/wiadomosci", "Główny Inspektorat Sanitarny", "zdrowie publiczne", 6),
    ("cyfryzacja/wiadomosci", "Ministerstwo Cyfryzacji", "mObywatel i e-usługi", 22),
    ("mswia/aktualnosci", "Ministerstwo Spraw Wewnętrznych i Administracji", "dokumenty i bezpieczeństwo", 16),
    ("zdrowie/aktualnosci", "Ministerstwo Zdrowia", "ochrona zdrowia", 10),
    ("kgpsp/aktualnosci", "Państwowa Straż Pożarna", "pożary i ratownictwo", 16),
    ("wody-polskie/aktual", "Państwowe Gospodarstwo Wodne Wody Polskie", "powodzie i gospodarka wodna", 12),
    ("gddkia/aktualnosci-2026", "Generalna Dyrekcja Dróg Krajowych i Autostrad", "drogi krajowe", 10),
    ("kas/wiadomosci", "Krajowa Administracja Skarbowa", "podatki i podszywanie się", 12),
    ("dyplomacja/aktualnosci", "Ministerstwo Spraw Zagranicznych", "podróże i konsulaty", 6),
    ("edukacja/wiadomosci", "Ministerstwo Edukacji", "szkoły", 6),
    ("finanse/wiadomosci", "Ministerstwo Finansów", "finanse publiczne", 5),
    ("uw-pomorski/wiadomosci", "Pomorski Urząd Wojewódzki", "zarządzanie kryzysowe w województwie", 9),
    ("uw-lodzki/wiadomosci", "Łódzki Urząd Wojewódzki", "zarządzanie kryzysowe w województwie", 6),
    ("uw-lubelski/wiadomosci", "Lubelski Urząd Wojewódzki", "zarządzanie kryzysowe w województwie", 6),
    ("uw-podkarpacki/wiadomosci", "Podkarpacki Urząd Wojewódzki", "zarządzanie kryzysowe w województwie", 6),
    ("uw-zachodniopomorski/wiadomosci", "Zachodniopomorski Urząd Wojewódzki", "zarządzanie kryzysowe w województwie", 5),
    ("uw-podlaski/wiadomosci", "Podlaski Urząd Wojewódzki", "zarządzanie kryzysowe w województwie", 5),
    ("uw-lubuski/wiadomosci", "Lubuski Urząd Wojewódzki", "zarządzanie kryzysowe w województwie", 5),
    ("psse-chojnice/komunikaty", "Powiatowa Stacja Sanitarno-Epidemiologiczna w Chojnicach", "jakość wody i komunikaty lokalne", 8),
    ("psse-slupsk/komunikaty", "Powiatowa Stacja Sanitarno-Epidemiologiczna w Słupsku", "jakość wody i komunikaty lokalne", 5),
    ("psse-krakow/komunikaty", "Powiatowa Stacja Sanitarno-Epidemiologiczna w Krakowie", "komunikaty lokalne", 4),
    ("psse-lodz/komunikaty", "Powiatowa Stacja Sanitarno-Epidemiologiczna w Łodzi", "komunikaty lokalne", 8),
    ("psse-warszawa/komunikaty", "Powiatowa Stacja Sanitarno-Epidemiologiczna w m.st. Warszawie", "komunikaty lokalne", 4),
    ("wsse-gdansk/wiadomosci", "Wojewódzka Stacja Sanitarno-Epidemiologiczna w Gdańsku", "komunikaty sanitarne", 6),
]

# (lista/RSS, wzorzec linku, wydawca, domena, temat, limit)
LOCAL = [
    ("https://www.wroclaw.pl/dla-mieszkanca/komunikaty-i-ostrzezenia-dla-wroclawia",
     r"https://www\.wroclaw\.pl/(?:dla-mieszkanca|komunikacja|srodowisko|zdrowie|bezpieczenstwo)/[a-z0-9-]{25,}",
     "Urząd Miejski Wrocławia", "wroclaw.pl", "komunikaty i ostrzeżenia dla Wrocławia", 26),
    ("https://www.wroclaw.pl/komunikacja",
     r"https://www\.wroclaw\.pl/komunikacja/[a-z0-9-]{25,}",
     "Urząd Miejski Wrocławia", "wroclaw.pl", "komunikacja miejska i utrudnienia", 10),
    ("https://um.warszawa.pl/aktualnosci", r"https://um\.warszawa\.pl/-/[a-z0-9-]{12,}",
     "Urząd m.st. Warszawy", "um.warszawa.pl", "usługi miejskie", 14),
    ("https://www.gdansk.pl/wiadomosci", r"https://www\.gdansk\.pl/wiadomosci/[^\"']+,a,\d+",
     "Urząd Miejski w Gdańsku", "gdansk.pl", "usługi miejskie", 14),
    ("https://uml.lodz.pl/aktualnosci/rss?type=9818", r"https://uml\.lodz\.pl/aktualnosci-lodzpl/artykul-lodzpl/\?[^<\"'\s]+",
     "Urząd Miasta Łodzi", "lodz.pl", "usługi miejskie", 14),
    ("https://www.rzeszow.pl/aktualnosci", r"/41-miasto-rzeszow/1713-aktualnosci/\d+-[a-z0-9-]+\.html",
     "Urząd Miasta Rzeszowa", "rzeszow.pl", "usługi miejskie", 10),
    ("https://www.bialystok.pl/pl/wiadomosci/aktualnosci/", r"/pl/aktualnosci/[a-z0-9-]{12,}\.html",
     "Urząd Miejski w Białymstoku", "bialystok.pl", "usługi miejskie", 10),
    ("https://www.torun.pl/pl/aktualnosci", r"/pl/aktualnosc/[a-z0-9-]{12,}",
     "Urząd Miasta Torunia", "torun.pl", "usługi miejskie", 10),
    ("https://www.poznan.pl/mim/info/news/", r"/mim/info/news/[a-z0-9-]{10,},\d+\.html",
     "Urząd Miasta Poznania", "poznan.pl", "usługi miejskie", 10),
]

FACT = [
    ("wp", "https://fakenews.pl/wp-json/wp/v2/posts?per_page=100&_fields=link,date,modified", None,
     "FakeNews.pl", "fakenews.pl", 55),
    ("sitemap", "https://demagog.org.pl/fake_news-sitemap4.xml", r"https://demagog\.org\.pl/fake_news/[^<\s]+",
     "Stowarzyszenie Demagog", "demagog.org.pl", 55),
    ("wp", "https://fakenews.pl/wp-json/wp/v2/posts?per_page=100&page=2&_fields=link,date,modified", None,
     "FakeNews.pl", "fakenews.pl", 20),
    ("rss", "https://pravda.org.pl/rss/", r"https://pravda\.org\.pl/[a-z0-9-]{12,}/",
     "Stowarzyszenie Pravda", "pravda.org.pl", 15),
]
VERDICT = re.compile(r"\b(fałsz|nieprawd|manipulac|zmanipulow|bez kontekstu|nie ma dowod|fake|prawda\b|"
                     r"nie jest prawd|wprowadza w błąd|nie potwierdz|zdementow|podszyw|oszust)", re.I)
SKIP = re.compile(r"(cookie|ciasteczk|newsletter|zapisz się|udostępnij|wesprzyj nas|przekaż 1,5|"
                  r"Zdjęcie:|Fot\.|fot\.|Źródło zdjęcia|Czytaj też|Przeczytaj także|Polub nas|Obalamy fałszywe informacje|"
                  r"Tworzenie treści kosztuje|podarujesz nam kawę|Weryfikujemy wypowiedzi|Wesprzyj|Dołącz do)", re.I)
JOBS = re.compile(r"(inspektor ds|specjalist[ay] ds|stanowisk|nabór|oferta pracy|konkurs na)", re.I)
RELEVANT = re.compile(r"(utrudnie|komunikat|ostrzeż|ostrzega|zamknię|objazd|wod[ayzęoą]|awari|kurs|autobus|tramwaj|"
                      r"komunikacj|bezpiecze|pożar|powod|powódź|alarm|ewakuac|szczepi|zdrow|urząd|urzęd|odpad|śmieci|"
                      r"podat|opłat|wniosek|wnioski|dowód|dowody|paszport|rejestr|zasił|świadcze|szkoł|przedszk|remont|"
                      r"drog|ulic|mróz|śnieg|zim[aęy]|ogrzew|smog|powietrz|prąd|gaz|oszu|podszyw|policj|straż|kryzys|"
                      r"mObywatel|e-usług|e-recept|pacjent|szpital|lekarz|sanepid|kontrol|wycof|produkt|cyber|SMS|alert)", re.I)


class Fetcher:
    def __init__(self, cache):
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.last = {}

    def get(self, url):
        path = self.cache / (hashlib.sha1(url.encode()).hexdigest() + ".html")
        if path.exists():
            return path.read_text(encoding="utf-8")
        host = urlsplit(url).hostname
        wait = 0.6 - (time.monotonic() - self.last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self.last[host] = time.monotonic()
        with urlopen(Request(url, headers={"User-Agent": UA}), timeout=30) as response:
            body = response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")
        path.write_text(body, encoding="utf-8")
        return body


def clean(text):
    return " ".join((text or "").replace("\xa0", " ").split())


def parse_date(text):
    text = clean(text)
    if m := re.search(r"(20\d\d)-(\d\d)-(\d\d)", text):
        return f"{m[1]}-{m[2]}-{m[3]}"
    if m := re.search(r"\b(\d{1,2})\.(\d{1,2})\.(20\d\d)\b", text):
        return f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}"
    if m := re.search(r"\b(\d{1,2}) (" + "|".join(MONTHS) + r") (20\d\d)", text, re.I):
        return f"{m[3]}-{MONTHS.index(m[2].lower()) + 1:02d}-{int(m[1]):02d}"
    return None


def extract(html, url):
    soup = BeautifulSoup(html, "html.parser")
    meta = {m.get("property") or m.get("name"): m.get("content") for m in soup.find_all("meta") if m.get("content")}
    title = clean(meta.get("og:title") or "")
    body = (soup.select_one("article#main-content .editor-content") or soup.select_one("article#main-content")
            or soup.select_one(".entry-content") or soup.select_one(".gh-content") or soup.select_one("article")
            or soup.select_one("main") or soup.body)
    if not title:
        heading = soup.select_one("article h1, article h2, h1")
        title = clean(heading.get_text(" ")) if heading else ""
    title = re.sub(r"\s*[-|–]\s*(Portal Gov\.pl|Demagog|FakeNews\.pl|Pravda|Wrocław\.pl|Gdańsk\.pl).*$", "", title)
    if (m := re.match(r"(.{20,}?)\s+[|–-]\s+([^|–-]{2,70})$", title)) and (
            re.search(r"(www\.|\.pl|\.eu|Ministerstwo|Urząd|Centrum|Inspektorat|Straż|Stacja|Gospodarstwo|"
                      r"Dyrekcja|Administracja|F$|Fake)", m[2])):
        title = m[1]
    published = parse_date(meta.get("article:published_time") or "")
    modified = parse_date(meta.get("article:modified_time") or "")
    if not published:
        for script in soup.find_all("script", type="application/ld+json"):
            if m := re.search(r'"datePublished"\s*:\s*"([^"]+)"', script.string or ""):
                published = parse_date(m[1])
                break
    if not published and (node := soup.select_one("p.event-date, .event-date, time[datetime]")):
        published = parse_date(node.get("datetime") or node.get_text(" "))
    if not published and body:
        published = parse_date(body.get_text(" ")[:600])
    if published and published > TODAY:
        published = None  # data wydarzenia z treści, nie data publikacji
    paragraphs = []
    for node in (body.find_all(["p", "li"]) if body else []):
        text = clean(node.get_text(" "))
        if 70 <= len(text) <= 650 and not SKIP.search(text) and "¶" not in text and text not in paragraphs:
            paragraphs.append(text)
    page_text = clean(soup.get_text(" "))
    return title, published, modified, paragraphs, page_text


def pick(paragraphs, fact_check):
    if not paragraphs:
        return []
    chosen = [paragraphs[0]]
    if fact_check:
        verdict = next((p for p in paragraphs[1:] if VERDICT.search(p)), None)
        if verdict:
            chosen.append(verdict)
    elif len(paragraphs) > 1:
        chosen.append(paragraphs[1])
    return chosen


def slug(url):
    if m := re.search(r"news%5D=(\d+)|news\]=(\d+)", url):
        return "news-" + (m[1] or m[2])
    tail = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    tail = re.sub(r"[^a-z0-9-]", "", tail.lower().split(",")[0])[:60].strip("-")
    return tail or hashlib.sha1(url.encode()).hexdigest()[:10]


def record(prefix, url, publisher, kind, rtype, domain, topic, usage, extracted, group):
    title, published, modified, paragraphs, page_text = extracted
    excerpts = pick(paragraphs, rtype == "fact-check")
    if not title or not published or not excerpts:
        return None, "brak tytułu, daty lub akapitu"
    if any(part not in page_text for part in excerpts):
        return None, "fragment niezgodny ze stroną"
    if group == "samorządowe" or "/uw-" in url:
        if not RELEVANT.search(title + " " + " ".join(excerpts)) or JOBS.search(title):
            return None, "poza tematem usług publicznych i ostrzeżeń"
    host = urlsplit(url).hostname
    for suffix in (f" - {publisher}", f" | {publisher}", " - Portal Gov.pl"):
        if suffix.casefold() in title.casefold():
            title = title[:title.casefold().index(suffix.casefold())].strip()
    return {
        "id": f"{prefix}-{slug(url)}", "title": title, "publisher": publisher, "type": rtype, "kind": kind,
        "domain": domain, "host": host, "url": url, "language": "pl", "published_on": published,
        "updated_on": modified if modified and modified != published else None, "checked_on": TODAY,
        "archival": published < "2024-11-22", "event_dates": [], "places": [], "topics": [topic],
        "source_section": "Pierwsze akapity treści" + (" i akapit z oceną" if rtype == "fact-check" else ""),
        "excerpts": excerpts,
        "scope": f"{publisher}: „{title}”. Opublikowano {published}. Fragmenty to akapity z treści strony; "
                 f"nie obejmują załączników ani grafik.",
        "usage": usage, "source_group": group,
    }, None


def gov_links(fetch, section, limit):
    links, page = [], 1
    while len(links) < limit * (3 if "/uw-" in "/" + section else 1) and page <= 9:
        html = fetch.get(f"https://www.gov.pl/web/{section}?page={page}&size=10")
        found = re.findall(r'<div class="title">\s*<a href="(/web/[^"]+)"', html)
        if not found:
            break
        links += [urljoin("https://www.gov.pl", link) for link in found if urljoin("https://www.gov.pl", link) not in links]
        page += 1
    return links[:limit]


def listing_links(fetch, url, pattern, limit):
    html = fetch.get(url)
    base = f"{urlsplit(url).scheme}://{urlsplit(url).hostname}"
    links = []
    for link in re.findall(pattern, html):
        link = urljoin(base, link.replace("&amp;", "&").strip())
        if link not in links and link.rstrip("/") != url.rstrip("/"):
            links.append(link)
    return links[:limit]


def collect(fetch, known_urls, log):
    jobs = []
    for section, publisher, topic, limit in GOV:
        for url in gov_links(fetch, section, limit + 4 if not section.startswith("uw-") else limit * 3):
            jobs.append(("gov", url, publisher, "komunikat", "urzędowe", "gov.pl", topic, GOV_USAGE, "rządowe", limit, section))
    for listing, pattern, publisher, domain, topic, limit in LOCAL:
        try:
            for url in listing_links(fetch, listing, pattern, limit * 3):
                jobs.append(("sam", url, publisher, "komunikat", "samorządowe", domain, topic, OFFICIAL_USAGE, "samorządowe", limit, listing))
        except Exception as error:  # noqa: BLE001
            log.append({"listing": listing, "error": str(error)[:120]})
    for mode, listing, pattern, publisher, domain, limit in FACT:
        try:
            if mode == "wp":
                links = [row["link"] for row in json.loads(fetch.get(listing))
                         if "/blog/" not in row["link"]]
            else:
                links = listing_links(fetch, listing, pattern, 400)
                if mode == "sitemap":
                    links = links[::-1]  # najnowsze na końcu ostatniej mapy
            for url in links[:limit + 15]:
                jobs.append(("fc", url, publisher, "weryfikacja", "fact-check", domain, "weryfikacja informacji",
                             QUOTE_USAGE, "fact-check", limit, listing))
        except Exception as error:  # noqa: BLE001
            log.append({"listing": listing, "error": str(error)[:120]})

    def run(job):
        prefix, url, publisher, kind, rtype, domain, topic, usage, group, _, _ = job
        if url.rstrip("/") in known_urls:
            return job, None, "duplikat adresu z korpusu v4"
        try:
            extracted = extract(fetch.get(url), url)
        except Exception as error:  # noqa: BLE001
            return job, None, f"pobranie: {str(error)[:80]}"
        row, reason = record(prefix, url, publisher, kind, rtype, domain, topic, usage, extracted, group)
        return job, row, reason

    accepted, per_source, seen_ids, seen_titles = [], {}, set(), set()
    with cf.ThreadPoolExecutor(8) as pool:
        for job, row, reason in pool.map(run, jobs):
            source_key, limit = job[10], job[9]
            if row is None:
                log.append({"url": job[1], "reason": reason})
                continue
            if per_source.get(source_key, 0) >= limit:
                continue
            if row["title"].casefold() in seen_titles:
                log.append({"url": job[1], "reason": "duplikat tytułu"})
                continue
            base, n = row["id"], 2
            while row["id"] in seen_ids:
                row["id"] = f"{base}-{n}"
                n += 1
            seen_ids.add(row["id"])
            seen_titles.add(row["title"].casefold())
            per_source[source_key] = per_source.get(source_key, 0) + 1
            accepted.append(row)
    return accepted, per_source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--existing", type=Path, default=Path("Research/Prawdomir_Korpus_v4.jsonl"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    known = {json.loads(line)["url"].rstrip("/") for line in args.existing.read_text(encoding="utf-8-sig").splitlines() if line.strip()}
    log = []
    rows, per_source = collect(Fetcher(args.cache), known, log)
    known_ids = {json.loads(line)["id"] for line in args.existing.read_text(encoding="utf-8-sig").splitlines() if line.strip()}
    rows = [row for row in rows if row["id"] not in known_ids]
    with args.out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    if args.log:
        args.log.write_text(json.dumps({"per_source": per_source, "rejected": log}, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    groups = {}
    for row in rows:
        groups[row["source_group"]] = groups.get(row["source_group"], 0) + 1
    print(json.dumps({"accepted": len(rows), "groups": groups, "rejected": len(log)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
