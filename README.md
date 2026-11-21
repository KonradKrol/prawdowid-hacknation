# Prawdowid

Autorski projekt Konrada Króla na zadanie MSZ **Prawdowid** na HackNation 2026. Z wklejonej wiadomości wyodrębnia twierdzenia do sprawdzenia, wyszukuje lokalne dowody i wskazuje, co można rozstrzygnąć oraz jakiego dowodu brakuje. Oddziela pytanie o autorstwo wypowiedzi od oceny jej treści.

## Backend, WWW i adapter demonstracyjny

Wymagany Python 3.12 lub nowszy z SQLite FTS5. Uruchomienie odbywa się z katalogu repozytorium.

```powershell
python -m pip install -r requirements.txt
if (!(Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
python -m uvicorn app.main:app --port 8000
```

Jedna aplikacja obsługuje stronę WWW pod `/` i API pod `/docs`. Widok `/zrodla`, API `/api/v1/sources` i ocena zgłoszeń korzystają z korpusu wskazanego przez `PRAWDOWID_CORPUS`. Przykładowa konfiguracja wskazuje `Research/Prawdowid_Korpus_Probny.jsonl`. Po zmianie ustawienia uruchom aplikację ponownie. [Opis API i adaptera WhatsApp](docs/KONTRAKT_API.md) podaje żądania i format wyniku. Adapter nie wymaga konta Meta do demonstracji. Dane sesji i zdarzeń zapisują się w SQLite. [Instrukcja Fly.io](docs/WDROZENIE_FLY.md) opisuje trwały wolumen `/data` i kopię bazy.

Do rzeczywistej weryfikacji ustaw w pliku `.env` wartości `PRAWDOWID_API_KEY` i `PRAWDOWID_MODEL` dla swojego dostawcy oraz wybierz `PRAWDOWID_EVALUATOR=live`. Plik `.env` jest ignorowany przez Git. Ustawienie `PRAWDOWID_EVALUATOR=fake` służy do podglądu frontendu bez klucza. Produkcja wymaga trybu live.

**Dane.** Utwórz nową wersję przez `python scripts/import_sources.py Research/Prawdowid_Korpus_Start.jsonl nowe_materialy.csv --output Research/korpus_demo.jsonl` i ustaw `PRAWDOWID_CORPUS`. Oczekiwane odpowiedzi i próby trzymaj poza korpusem. Dodatkowy strażnik importu działa z `--llm-guard` i wymaga klucza.

**Pomiary.** `python eval/run.py --report wyniki` tworzy JSON, Markdown i CSV do ręcznej oceny cytatów. `python eval/run_guard.py --report guard.json` porównuje 20 syntetycznych prób z niezmienionym przypadkiem. Oba skrypty wymagają trybu live. Próby techniczne uruchom przez `python -m pip install -r requirements-dev.txt` i `python -m pytest tests`.


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
