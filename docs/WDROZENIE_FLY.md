# Uruchomienie backendu na Fly.io

Fly Machine ma ulotny system plików obrazu i osobny trwały Fly Volume. Plik SQLite musi trafić na wolumen. W `fly.toml` źródło `data` montuje się pod `/data` i ustawia `PRAWDOWID_DATA_DIR=/data`. Korpus z obrazu jest odczytywany i indeksowany przy starcie.

1. Zweryfikuj nazwę istniejącej aplikacji i region w swoim koncie Fly. W konfiguracji jest robocza nazwa `prawdowid-hacknation` i Frankfurt `fra`.
2. Utwórz wolumen `data` w tym samym regionie, np. `fly volumes create data --region fra --size 1 -a <app>`. Sprawdź, czy aplikacja ma jedną maszynę z podpiętym wolumenem. `fly deploy --ha=false -a <app>` ogranicza automatyczne tworzenie maszyn podczas pierwszego wdrożenia.
3. Ustaw `PRAWDOWID_API_KEY` przez Fly Secrets, opcjonalnie model, oraz sekrety webhooka tylko jeśli potrzebujesz testować podpis. Sekrety nie trafiają do Dockerfile ani konfiguracji Gita.
4. Wdróż obraz, sprawdź HTTPS i `/health`. Wykonaj sprawdzenie, zachowaj cookie sesji i sprawdź dostęp do wyniku po restarcie tej samej maszyny.
5. Kopię SQLite wykonaj okresowo za pomocą mechanizmu backup SQLite, np. `python scripts/backup_db.py /data/prawdowid.db /data/backup-YYYY-MM-DD.db`. Wybierz też zatwierdzone miejsce kopii poza tym samym wolumenem.

Pula publicznego dema obejmuje 400 prób wymagających wywołania modelu, wspólnych dla WWW i adaptera. Licznik jest zapisywany na wolumenie przed wywołaniem. Odpowiedzi z pamięci podręcznej i sprawdzenia bez źródeł są dostępne także po wyczerpaniu puli. Wartość można zmienić ustawieniem `PRAWDOWID_PAID_CHECK_LIMIT`.

Wolumen jest lokalny dla jednej maszyny i Fly nie replikuje go automatycznie. Produkcyjna konfiguracja używa jednego workera i cookies Secure. Plik SQLite na niezamontowanym dysku obrazu jest odpowiedni tylko dla krótkiego testu. [Fly Volumes](https://fly.io/docs/volumes/overview/)

## Konfiguracja na pierwszy prototyp

Zacznij od jednej maszyny z 1 współdzielonym vCPU i 256 MB RAM oraz pojedynczego wolumenu 1 GB. Uruchom jednego workera i sprawdź stan maszyny po pierwszej serii prób. Konfiguracja zatrzymuje maszynę przy bezczynności i uruchamia po kolejnym żądaniu. Pierwsza odpowiedź po przerwie może być wolniejsza, a wolumen pozostaje przy maszynie. Przed oceną zrób jedno sprawdzenie rozgrzewające. Koszt zależy od regionu i czasu pracy, a wolumen i zewnętrzne API mają osobne rozliczenia. [Cennik Fly.io](https://fly.io/docs/about/pricing/).
