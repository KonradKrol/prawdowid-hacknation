# Uruchomienie backendu na Fly.io

Fly Machine ma ulotny system plików obrazu i osobny trwały Fly Volume. Plik SQLite musi trafić na wolumen. W `fly.toml` źródło `data` montuje się pod `/data` i ustawia `PRAWDOWID_DATA_DIR=/data`. Korpus z obrazu jest odczytywany i indeksowany przy starcie.

1. Zweryfikuj nazwę istniejącej aplikacji i region w swoim koncie Fly. W konfiguracji jest robocza nazwa `prawdowid-hacknation` i Frankfurt `fra`.
2. Utwórz wolumen `data` w tym samym regionie, np. `fly volumes create data --region fra --size 1 -a <app>`. Sprawdź, czy aplikacja ma jedną maszynę z podpiętym wolumenem. `fly deploy --ha=false -a <app>` ogranicza automatyczne tworzenie maszyn podczas pierwszego wdrożenia.
3. Ustaw `PRAWDOWID_API_KEY` przez Fly Secrets, opcjonalnie model, oraz sekrety webhooka tylko jeśli potrzebujesz testować podpis. Sekrety nie trafiają do Dockerfile ani konfiguracji Gita.
4. Wdróż obraz, sprawdź HTTPS i `/health`. Wykonaj sprawdzenie, zachowaj cookie sesji i sprawdź dostęp do wyniku po restarcie tej samej maszyny.
5. Kopię SQLite wykonaj okresowo za pomocą mechanizmu backup SQLite, np. `python scripts/backup_db.py /data/prawdowid.db /data/backup-YYYY-MM-DD.db`. Wybierz też zatwierdzone miejsce kopii poza tym samym wolumenem.

Wolumen jest lokalny dla jednej maszyny i Fly nie replikuje go automatycznie. Produkcyjna konfiguracja używa jednego workera i cookies Secure. Plik SQLite na niezamontowanym dysku obrazu jest odpowiedni tylko dla krótkiego testu. [Fly Volumes](https://fly.io/docs/volumes/overview/)
