# API Prawdowidu

## Start lokalny

W folderze repozytorium uruchom:

```powershell
python -m pip install -r requirements-backend.txt
python -m uvicorn prawdowid_api:app --host 127.0.0.1 --port 8000
```

Klucz dostawcy ustaw przez `PRAWDOWID_API_KEY` lub `OPENAI_API_KEY`. Model jest konfigurowalny przez `PRAWDOWID_MODEL`. Frontend z Vite może wywołać API z lokalnego portu 5173. Inny origin wpisz do `PRAWDOWID_CORS_ORIGINS` jako adres lub listę oddzieloną przecinkami. Przy wspólnym adresie aplikacji używaj względnej ścieżki API.

## Kontrakt WWW i adapterów

`POST /api/v1/checks` z `Content-Type: application/json` i treścią:

```json
{"question":"Czy RCB wysłało SMS wzywający do urzędów gmin w listopadzie 2018 roku?"}
```

Poprawny wynik to HTTP 200, także przy braku dowodów. Wynik zawiera `id`, `status`, `items`, `corpus_version`, `elapsed_ms`, `usage` i `estimated_cost_usd`. Każdy element `items` zawiera:

| Pole | Znaczenie |
|---|---|
| `claim`, `kind` | Treść ocenianej tezy lub pytania oraz `verdict` albo `answer`. |
| `label`, `answer` | Klasa werdyktu lub treść odpowiedzi otwartej. Jedno z pól może mieć wartość null. |
| `reason`, `missing_evidence` | Krótkie uzasadnienie i informacja, jakiego materiału potrzeba. |
| `citations` | Lista przypisanych dowodów. Cytat zawiera `source_id`, `title`, `publisher`, `url`, `published_on`, `quote` oraz `field`. Przy dacie publikacji `field` to `published_on`, a `quote` może być null. |

Renderuj osobno wszystkie elementy `items`. Pola `missing_evidence`, `answer`, datę i koszt pokazuj tylko jeśli są dostępne. Użytkownik może otrzymać kilka ocen naraz, np. osobno o autorstwie wypowiedzi i o jej treści. Przy HTTP 422 pokaż błąd wejścia, przy 429 komunikat o zajętości, przy 503 komunikat o problemie technicznym. Błędy sprawdzenia mają `message` i puste `items`. Walidacja formularza na poziomie HTTP 422 może zwrócić `detail`.

`GET /health` pokazuje stan korpusu, liczniki i informację, czy skonfigurowano klucz modelu. `GET /docs` pokazuje interaktywny opis API. Dla WWW renderowanego przez ten sam proces można włączyć własne trasy, importując `app` z `prawdowid_api`.

Pierwszy blok zapisuje lokalnie techniczne pomiary do ignorowanego przez Git pliku `pomiary_backend.jsonl`. Dziennik nie przechowuje treści zgłoszenia ani odpowiedzi. Wynik jest zwracany w tej samej odpowiedzi HTTP. Trwałe karty wyników, URL, SMS i panel są osobnymi blokami.
