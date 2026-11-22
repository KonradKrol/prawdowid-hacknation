# Prawdoskop — notatki do pitcha i dalszego rozwoju

- Dziś RSS Demagoga wykrywa publikacje, a indeks dostaje tezę i ocenę redakcji z metadanych ClaimReview. Liczbę aktywnych dokumentów pokazuje `/health`.
- Kolejny krok: model wybiera z pełnego artykułu kluczowe akapity z uzasadnieniem. Kod kopiuje je dosłownie, sprawdza zgodność ze stroną i zapisuje link oraz wersję publikacji. Wystarczy przetwarzać nowe lub zmienione wpisy i mierzyć koszt oraz czas importu.
- Aktualność kryzysowa: działający adapter IMGW. Kolejne kandydatury to RSO i publikacje RCB. Oficjalne RSS lub API sprawdzamy osobno dla każdego źródła. Publikacja na stronie RCB nie daje dostępu do listy odbiorców SMS.
- Prywatność i bezpieczeństwo: maskujemy rozpoznane dane, np. telefon i e-mail, przed zapisem i wysłaniem do modelu. Zamaskowane zgłoszenia i wyniki są przechowywane siedem dni, a panel jest chroniony dostępem moderatora. W przypadku braku dowodu aplikacja może wstrzymać werdykt.
- Moderacja: wspólna etykieta „Wiele zgłoszeń” przy 5 zgłoszeniach w ostatniej godzinie lub 15 w ostatnich 24 godzinach. To liczba zgłoszeń, nie unikalnych osób. W pokazie używamy danych testowych.
- Korpus, EUvsDisinfo, aktualność i testy jakości: zakres zamknięty na potrzeby zgłoszenia. Wyniki trudnych pytań opisywać jako wynik skończonej próby.
