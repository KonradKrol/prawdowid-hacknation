# Ślad Dowodu

Prototyp dla zadania MSZ **Prawdowid** na HackNation 2026. Z wklejonej wiadomości wyodrębnia twierdzenia do sprawdzenia, wyszukuje lokalne dowody i wskazuje, co można rozstrzygnąć oraz jakiego dowodu brakuje. Oddziela pytanie o autorstwo wypowiedzi od oceny jej treści.

## Aktualny stan

Lokalne wyszukiwanie i konsolowy przebieg są zaimplementowane. Próby z symulowanymi odpowiedziami sprawdziły walidację cytatu, datę, brak trafień i pomiary. Do pierwszego uruchomienia z modelem potrzebny jest klucz API. WWW, drugi kanał, pełny korpus i ewaluacja konkursowa są kolejnymi blokami.

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
