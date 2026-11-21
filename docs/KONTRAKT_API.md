# Prawdowid — API v1

Ustalenia implementacyjne z sekcji 2 dokumentu podziału pracy. Modele Pydantic są w `app/contract.py`. Interaktywny opis HTTP jest dostępny pod `/docs`.

| Metoda | Wejście i odpowiedź |
|---|---|
| `POST /api/v1/checks` | `{"text":"…","lang":"pl"}`. Starsze `question` działa jako alias. Opcjonalne `clarifies` wskazuje poprzednie sprawdzenie z tej samej sesji, a `?nocache=1` pomija odczyt cache. Zwraca `CheckResult` z kodem 200. Wersja konkursowa przyjmuje zgłoszenia bez limitu częstotliwości. `PRAWDOWID_RATE_LIMIT_ENABLED=1` włącza 10 zgłoszeń na minutę i 100 na dobę na adres IP dla WWW/API oraz dla demo WhatsApp. Przekroczenie limitu skutkuje kodem 429. |
| `GET /api/v1/checks/{id}` | Wynik w bieżącej sesji albo 404. |
| `DELETE /api/v1/checks/{id}` | Usunięcie własnego sprawdzenia, 204 lub 404. |
| `DELETE /api/v1/session` | Usunięcie wyników tej sesji, odpowiedź `{"deleted":n}`. |
| `GET /api/v1/sources`, `GET /api/v1/sources.csv` | Katalog źródeł i statystyki lub eksport CSV. |
| `GET /health` | Stan SQLite, informacje o korpusie i flagi konfiguracji modelu. |

`CheckResult` ma `contract_version`, `id`, `created_at`, `channel`, `lang`, `status`, `parent_id`, `message`, `clarification_question`, `summary`, `input`, `items`, `notices` i `meta`. Przy statusie innym niż `ok`, `items` jest puste. Pozycja zawiera tezę, klasę lub odpowiedź, uzasadnienie, siłę i przesłanki, ewentualną różnicę kontekstu, brakujący dowód i listę dowodów z relacją `supports`, `refutes` albo `context`. Nagłówki, daty i adresy dowodów pochodzą z zatwierdzonych metadanych.

Cookie `pw_session` jest generowane przez backend. Frontend serwerowy wywołuje bezpośrednio `run_check`, `get_check`, `delete_check`, `delete_session` i `list_sources` z `app.core.service`. Ten sam router API pozostaje dostępny dla JavaScriptu. Wyniki są przypisane do sesji. Klient przekazuje `clarifies` w kolejnej wiadomości, maksymalnie dwukrotnie.

## Drugi kanał

- `POST /api/whatsapp/demo` przyjmuje `{"text":"…","lang":"pl"}`, buduje przykładowy webhook w formacie Meta, wywołuje ten sam backend i zwraca `{"simulated":true,"messages":[…]}`. Pozycja zawiera `check_id`, `status`, elementy wyniku i przykładowy rekord wychodzący. Treść odpowiedzi jest w `messages[0].message.text.body`.
- `GET /api/whatsapp/webhook` obsługuje `hub.challenge` po sprawdzeniu tokenu. `POST` przyjmuje oryginalne bajty podpisane `X-Hub-Signature-256` i obsługuje tekstowe wiadomości. Ten interfejs nadal używa symulowanego nadawcy. Nie wysyła wiadomości do Meta.
- `PRAWDOWID_EVALUATOR=fake` jest przeznaczony do pracy nad interfejsem i blokowany przy `PRAWDOWID_ENV=production`.
