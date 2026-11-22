# Prawdowid

Autorski projekt Konrada Króla na zadanie MSZ **Prawdowid** na HackNation 2026. Z wklejonej wiadomości wyodrębnia twierdzenia do sprawdzenia, wyszukuje lokalne dowody i wskazuje, co można rozstrzygnąć oraz jakiego dowodu brakuje. Oddziela pytanie o autorstwo wypowiedzi od oceny jej treści.

## Uruchomienie aplikacji

Publiczna wersja działa na [Fly.io](https://prawdowid-hacknation.fly.dev/). Możesz też uruchomić ją lokalnie. Potrzebujesz Git i Pythona 3.12 lub nowszego z SQLite FTS5.

### 1. Pobierz repozytorium i zainstaluj zależności

**Windows (PowerShell)**

```powershell
git clone https://github.com/KonradKrol/prawdowid-hacknation.git
cd prawdowid-hacknation
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

**macOS / Linux**

```bash
git clone https://github.com/KonradKrol/prawdowid-hacknation.git
cd prawdowid-hacknation
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Polecenie kopiowania konfiguracji wykonaj tylko przy pierwszym uruchomieniu. Uruchamiaj kolejne polecenia z katalogu repozytorium.

### 2. Wybierz tryb w pliku .env

- **Pełna weryfikacja:** zostaw `PRAWDOWID_EVALUATOR=live` i wpisz własny klucz OpenAI API w `PRAWDOWID_API_KEY`. Przykładowe ustawienia modelu to `PRAWDOWID_MODEL=gpt-6-luna` oraz `PRAWDOWID_GUARD_MODEL=gpt-6-luna`. Zapytania w tym trybie mogą naliczać koszt API.
- **Podgląd bez klucza:** ustaw `PRAWDOWID_EVALUATOR=fake`. To tryb demonstracyjny z wynikami testowymi.

Plik `.env` jest ignorowany przez Git. Konfiguracja startowa ładuje z repozytorium `Research/Prawdoskop_Korpus_v6.jsonl` i zapisuje dane lokalnie w `data/`. Jeśli chcesz włączyć cykliczny import IMGW i Demagoga, ustaw `PRAWDOWID_OFFICIAL_POLL_S=600` i uruchom aplikację ponownie.

### 3. Uruchom serwer

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**macOS / Linux**

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Otwórz [localhost:8000](http://localhost:8000/). W trybie live możesz wpisać **„Czy we Włoszech 20 listopada 2026 odbył się strajk generalny?”**. [Stan aplikacji](http://localhost:8000/health) pokazuje m.in. tryb i liczbę dokumentów, a [dokumentacja API](http://localhost:8000/docs) pozwala wysyłać zapytania. Serwer zatrzymasz przez Ctrl+C. Jeśli port jest zajęty, zmień `--port 8000` na np. `--port 8001` i otwórz odpowiedni adres.

Szczegóły dotyczące testowego adaptera WhatsApp są w [opisie API](docs/KONTRAKT_API.md), a konfiguracja produkcyjna w [instrukcji Fly.io](docs/WDROZENIE_FLY.md).

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

## Korpus v6 i pomiary

`Research/Prawdoskop_Korpus_v6.jsonl` ma 394 dokumenty statyczne po przeglądzie i wycofaniu 121 rekordów z v5. Importy IMGW i Demagoga zwiększają bieżący licznik. Porównanie odpowiedzi przed i po rozszerzeniu oraz wariantów BM25, E5 i hybrydy: `python eval/compare_corpus.py --e5 <katalog modelu> --report eval/wyniki`. Znane narracje EUvsDisinfo: `Research/EUvsDisinfo_Przypadki.jsonl`, klient MCP w `app/ingest/narratives.py` (token `PRAWDOWID_EUVS_TOKEN`).

[Raport z 22.11.2026](docs/RAPORT_2026-11-22.md) · [Prezentacja](docs/pitch/index.html)

## Aktualny stan

Backend obsługuje API v1, sesje, SQLite i adapter demonstracyjny. Testy z próbkami sprawdzają kontrakt, walidację dowodów i HTTP. Do ewaluacji jakości potrzebny jest klucz modelu i docelowy korpus. Wdrożenie na Fly.io wymaga wskazania aplikacji, wolumenu i ustawienia sekretów.

## Narzędzia wiersza poleceń

W katalogu repozytorium, po aktywacji środowiska Python:

```powershell
python -B prawdowid_core.py
python -B prawdowid_core.py "Czy RCB wysłało SMS wzywający do urzędów gmin w listopadzie 2018?"
```

Pierwsze polecenie pokazuje stan zbioru. Drugie wyszukuje kandydatów i działa lokalnie. Po ustawieniu `PRAWDOWID_API_KEY` lub `OPENAI_API_KEY` w środowisku uruchom pełną próbę:

```powershell
python -B prawdowid_verify.py "Czy RCB wysłało SMS wzywający do urzędów gmin w listopadzie 2018?" --metrics pomiary.jsonl
```

`--model` pozwala zmienić model obsługiwany przez usługę. Moduł sprawdzania przekazuje tylko wybrane fragmenty zatwierdzonego korpusu. Pierwszy zestaw w `Research/Prawdowid_Korpus_Start.jsonl` składa się z krótkich fragmentów i linków do materiałów. `Research/Prawdowid_Proby_Start.jsonl` zawiera wejścia i oczekiwane wyniki, które pozostają poza wyszukiwaniem.
