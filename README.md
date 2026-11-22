# Prawdowid

Autorski projekt Konrada Króla na zadanie MSZ **Prawdowid** na HackNation 2026. Z wklejonej wiadomości wyodrębnia twierdzenia do sprawdzenia, wyszukuje lokalne dowody i wskazuje, co można rozstrzygnąć oraz jakiego dowodu brakuje. Oddziela pytanie o autorstwo wypowiedzi od oceny jej treści.

## Backend, WWW i adapter demonstracyjny

Wymagany Python 3.12 lub nowszy z SQLite FTS5. Uruchomienie odbywa się z katalogu repozytorium.

```powershell
python -m pip install -r requirements.txt
if (!(Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
python -m uvicorn app.main:app --port 8000
```

Jedna aplikacja obsługuje stronę WWW pod `/` i API pod `/docs`. Widok `/zrodla`, API `/api/v1/sources` i ocena zgłoszeń korzystają z korpusu wskazanego przez `PRAWDOWID_CORPUS`. Przykładowa konfiguracja wskazuje `Research/Prawdoskop_Korpus_v5.jsonl`. Po zmianie ustawienia uruchom aplikację ponownie. [Opis API i adaptera WhatsApp](docs/KONTRAKT_API.md) podaje żądania i format wyniku. Adapter nie wymaga konta Meta do demonstracji. Dane sesji i zdarzeń zapisują się w SQLite. [Instrukcja Fly.io](docs/WDROZENIE_FLY.md) opisuje trwały wolumen `/data` i kopię bazy.

Do rzeczywistej weryfikacji ustaw w pliku `.env` wartości `PRAWDOWID_API_KEY` i `PRAWDOWID_MODEL` dla swojego dostawcy oraz wybierz `PRAWDOWID_EVALUATOR=live`. Plik `.env` jest ignorowany przez Git. Ustawienie `PRAWDOWID_EVALUATOR=fake` służy do podglądu frontendu bez klucza. Produkcja wymaga trybu live.

**Dane.** Utwórz nową wersję przez `python scripts/import_sources.py Research/Prawdowid_Korpus_Start.jsonl nowe_materialy.csv --output Research/korpus_demo.jsonl` i ustaw `PRAWDOWID_CORPUS`. Oczekiwane odpowiedzi i próby trzymaj poza korpusem. Dodatkowy strażnik importu działa z `--llm-guard` i wymaga klucza.

**Pomiary.** `python eval/run.py --report wyniki` tworzy JSON, Markdown i CSV do ręcznej oceny cytatów. `python eval/run_guard.py --report guard.json` porównuje 20 syntetycznych prób z niezmienionym przypadkiem. Oba skrypty wymagają trybu live. Próby techniczne uruchom przez `python -m pip install -r requirements-dev.txt` i `python -m pytest tests`.


## Kanał urzędowy, sprawy i moderacja

Prawdoskop importuje przyrostowo ostrzeżenia meteorologiczne IMGW-PIB (`app/ingest/imgw.py`). Zapisuje datę publikacji, czas udanego pobrania i wersję wpisu. Zgłoszenia o tym samym zjawisku, powiecie (TERYT) i dniu tworzą jedną sprawę z licznikiem i opisem brakującego dowodu. Nowy lub zmieniony komunikat uruchamia ponowną ocenę pasujących otwartych spraw, a moderator w `/moderacja` widzi poprzedni wynik, proponowany wynik i cytat. Panel wymaga `PRAWDOWID_ADMIN_TOKEN` (nagłówek `X-Admin-Token` albo jednorazowo `/moderacja?klucz=...`). Odpytywanie włącza `PRAWDOWID_OFFICIAL_POLL_S`.

```powershell
python scripts/demo_moderacja.py
python scripts/demo_moderacja.py --live --data-dir data/demo
python -m pytest tests/test_official.py
```

Pierwsze polecenie odtwarza najważniejszy przebieg bez kosztów: dwie różne wiadomości o tym samym zdarzeniu tworzą jedną sprawę, inny powiat lub dzień tworzy osobną, import ostrzeżenia daje propozycję tylko w sprawie, której dotyczy, a powtórny import nie tworzy duplikatów.

## Korpus v5 i pomiary

`Research/Prawdoskop_Korpus_v5.jsonl` ma 513 dokumentów: korpus v4 i 400 nowych materiałów (226 rządowych, 62 samorządowe, 112 fact-checków) zebranych skryptem `scripts/collect_corpus.py`. Porównanie odpowiedzi przed i po rozszerzeniu oraz wariantów BM25, E5 i hybrydy: `python eval/compare_corpus.py --e5 <katalog modelu> --report eval/wyniki`. Znane narracje EUvsDisinfo: `Research/EUvsDisinfo_Przypadki.jsonl`, klient MCP w `app/ingest/narratives.py` (token `PRAWDOWID_EUVS_TOKEN`).

[Raport z 22.11.2026](docs/RAPORT_2026-11-22.md) · [Prezentacja](docs/pitch/index.html)

## Aktualny stan

Backend obsługuje API v1, sesje, SQLite i adapter demonstracyjny. Testy z próbkami sprawdzają kontrakt, walidację dowodów i HTTP. Do ewaluacji jakości potrzebny jest klucz modelu i docelowy korpus. Wdrożenie na Fly.io wymaga wskazania aplikacji, wolumenu i ustawienia sekretów.

## Uruchomienie

Wymagany Python ze SQLite FTS5. W katalogu repozytorium:

```powershell
python -B prawdowid_core.py
python -B prawdowid_core.py "Czy RCB wysłało SMS wzywający do urzędów gmin w listopadzie 2018?"
```

Pierwsze polecenie pokazuje stan zbioru. Drugie wyszukuje kandydatów i działa lokalnie. Po ustawieniu `PRAWDOWID_API_KEY` lub `OPENAI_API_KEY` w środowisku uruchom pełną próbę:

```powershell
python -B prawdowid_verify.py "Czy RCB wysłało SMS wzywający do urzędów gmin w listopadzie 2018?" --metrics pomiary.jsonl
```

`--model` pozwala zmienić model obsługiwany przez usługę. Moduł sprawdzania przekazuje tylko wybrane fragmenty zatwierdzonego korpusu. Pierwszy zestaw w `Research/Prawdowid_Korpus_Start.jsonl` składa się z krótkich fragmentów i linków do materiałów. `Research/Prawdowid_Proby_Start.jsonl` zawiera wejścia i oczekiwane wyniki, które pozostają poza wyszukiwaniem.
