# Raport korpusu v6

## Stan

- Korpus v5: 513 rekordów; v6: 392 rekordy.
- Poprawiono fragmenty w 279 dokumentach nocnej partii; starszych 113 nie zmieniano.
- Wycofano 121 rekordów: 119 wskazanych w liście oraz dwa dodatkowe (duplikat artykułu i strona będąca listą zajawkowych materiałów). Zapisano je w Research/Wycofane_v5.jsonl.
- W 279 sprawdzonych rekordach kod potwierdził występowanie fragmentów w wyodrębnionej treści strony po normalizacji białych znaków, limit 400 znaków na fragment, niezmienione published_on i usage oraz brak duplikatów identyfikatorów i adresów w v6.
- Testy aplikacji: 57 przeszło.

## Pomiar jakości

- Wynik przed zmianą (11 tak, 14 częściowo, 5 nie) pochodzi z zadania użytkownika; nie został tu odtworzony.
- Niezależna ocena po zmianie dla wylosowanych 30 materiałów nie została ukończona. Nie można potwierdzić progu 80%. Lista próby: fc-we-wloszech-nie-zakazano-malzenstw-homoseksualnych, gov-narodowe-swieto-niepodleglosci-w-szczecinie, sam-betlejem-poznanskie-na-placu-wolnosci-i-starym-rynku, gov-ostrzezenie-publiczne-dotyczace-wyrobu-do-kontaktu-z-zywnosc-2, gov-centralny-osrodek-informatyki-przywrocil-dzialanie-najwaznie, sam-urzad-rozblysnie-blekitem, gov-ostrzezenie-publiczne-dotyczace-zywnosci-wykrycie-obecnosci, gov-obwodnica-sidziny-z-wnioskiem-o-pozwolenie-na-budowe, fc-zdjecie-europejskich-przywodcow-na-korytarzu-zostalo-wygener, fc-5d2f339668, fc-29fe080a25, gov-budynek-luw-przy-lubomelskiej-przejdzie-termomodernizacje, sam-muzyka-ktora-dopisuje-obrazom-nowe-znaczenia-rusza-7-festiwa, gov-zdrowe-i-bezpieczne-miejsce-pracy-rusza-kampania-zdrowa-prac, fc-zdjecia-mlodego-zohrana-mamdaniego-oraz-jego-matki-w-towarzy, fc-krople-na-borelioze-czy-olej-z-weza-jak-mit-przewleklej-chor, gov-komunikat-glownego-inspektora-sanitarnego-w-sprawie-potencja, fc-nagranie-nie-przedstawia-stoku-narciarskiego-w-kijowie, fc-611ee9f48e, gov-wodociag-publiczny-kotliny-gm-brojce---woda-nie-nadaje-sie-d, sam-11-mld-zl-z-unii-europejskiej-na-dolnoslaska-kolej, gov-ix-posiedzenie-polsko-litewskie, fc-skutecznosc-farm-wiatrowych-analiza, fc-pozar-w-los-angeles-jak-dotad-nie-zagrozil-napisowi-hollywoo, sam-debata-kandydatow-do-mlodziezowej-rady-miasta-torunia, gov-system-erekrutacje, gov-zmianie-ulegl-termin-przeprowadzenia-na-terenie-calego-wojew, gov-miejska-biblioteka-publiczna-im-w-reymonta-w-skierniewicach, gov-x-lecie-klauzuli-przeciwko-unikaniu-opodatkowania-gaar--dosw, fc-wyjasniamy-nieprawdziwe-tezy-z-wypowiedzi-donalda-trumpa-w-d.
- Ocena wybranych fragmentów nie zastępuje niezależnego przeglądu pełnej treści, dat obowiązywania i ewentualnych sprostowań.

## Dziesięć losowych porównań

Próba z generatora seed 20261122; pokazano pierwszy stary i pierwszy nowy fragment.

### 1. We Włoszech nie zakazano małżeństw homoseksualnych

- ID: `fc-we-wloszech-nie-zakazano-malzenstw-homoseksualnych`
- Przed: Od kilku tygodni na portalu X pojawia się ten sam wpis , według którego we Włoszech rzekomo zakazano małżeństw homoseksualnych. Post opatrzono wizerunkiem premier Giorgii Meloni, będącej jednocześnie szefową narodowo-konserwatywnej partii Bracia Włosi. Jak się jednak okazuje, żadne zmiany w tym zakresie nie mogły zostać wprowadzone, gdyż małżeństwa jednopłciowe nigdy w tym kraju nie zostały zalegalizowane.
- Po: Użytkownik @komentatorNaX trzykrotnie wrzucał identyczny post sugerujący, że we Włoszech rzekomo zakazano małżeństw jednopłciowych ( 4 , 14 , 25 marca). Posty wyświetlono kilkaset tysięcy razy. Uzyskały przy tym kilka tysięcy polubień i podań dalej. W rzeczywistości jednak Włochy nigdy nie wprowadziły równości małżeńskiej, dlatego też nie można było takich związków zakazać.

### 2. Narodowe Święto Niepodległości w Szczecinie

- ID: `gov-narodowe-swieto-niepodleglosci-w-szczecinie`
- Przed: Druga część uroczystości z udziałem premiera Dnalda Tuska oraz ministra infrastruktury Dariusza Klimczaka, wojewody i wicewojewodów, połączona z chrztem promu Bursztyn Unity odbyła się u podnóża Wałów Chrobrego w Szczecinie.
- Po: Druga część uroczystości z udziałem premiera Dnalda Tuska oraz ministra infrastruktury Dariusza Klimczaka, wojewody i wicewojewodów, połączona z chrztem promu Bursztyn Unity odbyła się u podnóża Wałów Chrobrego w Szczecinie.

### 3. Betlejem Poznańskie na Placu Wolności i Starym Rynku

- ID: `sam-betlejem-poznanskie-na-placu-wolnosci-i-starym-rynku`
- Przed: Młyńskie koło, lodowisko, wystawcy z różnych regionów kraju i świata oraz bogaty program kulturalny - to wszystko przez ponad 6 tygodni czeka na mieszkańców miasta i turystów. Uroczyste otwarcie Betlejem Poznańskiego na Placu Wolności zaplanowano na piątkowy wieczór. Dzień później wystartują atrakcje na Starym Rynku. Cały czas można odwiedzać także Jarmark Świąteczny na MTP, który ruszył w minioną sobotę.
- Po: Uroczyste otwarcie Betlejem Poznańskiego na Placu Wolności nastąpi w piątek (20 listopada) o godz. 18:00.

### 4. Ostrzeżenie publiczne dotyczące wyrobu do kontaktu z żywnością: migracja glinu z zestawu naczyń kuchennych

- ID: `gov-ostrzezenie-publiczne-dotyczace-wyrobu-do-kontaktu-z-zywnosc-2`
- Przed: Główny Inspektorat Sanitarny został poinformowany poprzez System Wczesnego Ostrzegania o Niebezpiecznej Żywności i Paszach o stwierdzeniu migracji glinu z zestawu naczyń kuchennych. Władze niemieckie stwierdziły w ocenie ryzyka, że wykryty poziom migracji glinu może mieć negatywny wpływ na zdrowie człowieka.
- Po: Główny Inspektorat Sanitarny został poinformowany poprzez System Wczesnego Ostrzegania o Niebezpiecznej Żywności i Paszach o stwierdzeniu migracji glinu z zestawu naczyń kuchennych.

### 5. Centralny Ośrodek Informatyki przywrócił działanie najważniejszych e-usług dla obywateli

- ID: `gov-centralny-osrodek-informatyki-przywrocil-dzialanie-najwaznie`
- Przed: Centralny Ośrodek Informatyki zakończył główny etap prac nad przywróceniem działania usług elektronicznych administracji publicznej. W pierwszej kolejności uruchomił te, z których korzysta największa liczba obywateli.
- Po: Centralny Ośrodek Informatyki zakończył główny etap prac nad przywróceniem działania usług elektronicznych administracji publicznej. W pierwszej kolejności uruchomił te, z których korzysta największa liczba obywateli.

### 6. Urząd rozbłyśnie błękitem

- ID: `sam-urzad-rozblysnie-blekitem`
- Przed: 20 listopada to rocznica uchwalenia Konwencji o prawach dziecka - jednego z najważniejszych międzynarodowych dokumentów określających uprawnienia najmłodszych. Z tej okazji budynek urzędu miasta zostanie podświetlony na niebiesko - by w symboliczny sposób przypomnieć o tej ważnej inicjatywie.
- Po: 20 listopada to rocznica uchwalenia Konwencji o prawach dziecka - jednego z najważniejszych międzynarodowych dokumentów określających uprawnienia najmłodszych. Z tej okazji budynek urzędu miasta zostanie podświetlony na niebiesko - by w symboliczny sposób przypomnieć o tej ważnej inicjatywie.

### 7. Ostrzeżenie publiczne dotyczące żywności: wykrycie obecności bakterii Listeria monocytogenes w jednej partii salami

- ID: `gov-ostrzezenie-publiczne-dotyczace-zywnosci-wykrycie-obecnosci`
- Przed: W wyniku działań urzędowych Inspekcji Weterynaryjnej wykryto obecność Listeria monocytogenes w 3 z 5 próbek w jednej partii produktu pn. Salami musli 250 g. Wycofaniem zostały objęte również Salami z pieprzem 250 g oraz Salami meksykańskie 250 g wyprodukowane w tym samym dniu co wskazany produkt. Spożycie żywności zanieczyszczonej Listeria monocytogenes może prowadzić do choroby zwanej listeriozą.
- Po: W wyniku działań urzędowych Inspekcji Weterynaryjnej wykryto obecność Listeria monocytogenes w 3 z 5 próbek w jednej partii produktu pn. Salami musli 250 g. Wycofaniem zostały objęte również Salami z pieprzem 250 g oraz Salami meksykańskie 250 g wyprodukowane w tym samym dniu co wskazany produkt. Spożycie żywności zanieczyszczonej Listeria monocytogenes może prowadzić do choroby zwanej listeriozą.

### 8. Obwodnica Sidziny z wnioskiem o pozwolenie na budowę

- ID: `gov-obwodnica-sidziny-z-wnioskiem-o-pozwolenie-na-budowe`
- Przed: W styczniu 2026 roku podpisaliśmy umowę z firmą Mirbud na zaprojektowanie i budowę tej trasy. Wykonawca ma 45 miesięcy na realizację zadania, w tym 17 na prace projektowe wraz z uzyskaniem pozwolenia na budowę (decyzji ZRID). Podczas robót budowlanych do czasu realizacji nie będą wliczane okresy zimowe od 16 grudnia do 15 marca.
- Po: W styczniu 2026 roku podpisaliśmy umowę z firmą Mirbud na zaprojektowanie i budowę tej trasy. Wykonawca ma 45 miesięcy na realizację zadania, w tym 17 na prace projektowe wraz z uzyskaniem pozwolenia na budowę (decyzji ZRID). Podczas robót budowlanych do czasu realizacji nie będą wliczane okresy zimowe od 16 grudnia do 15 marca.

### 9. Zdjęcie europejskich przywódców na korytarzu zostało wygenerowane przez AI

- ID: `fc-zdjecie-europejskich-przywodcow-na-korytarzu-zostalo-wygener`
- Przed: 18 sierpnia w Białym Domu odbyło się spotkanie Donalda Trumpa z Wołodymyrem Zełenskim. Do Waszyngtonu na rozmowy pokojowe przybyli także przywódcy europejscy. Stało się to przyczynkiem do rozpowszechnienia propagandowej fotografii mającej na celu ich ośmieszenie. Widoczni na niej politycy rzekomo zostali upokorzeni poprzez zmuszenie ich do oczekiwania na korytarzu na spotkanie z Donaldem Trumpem. W rzeczywistości zdjęcie zostało wygenerowane przez AI.
- Po: Widoczni na niej politycy rzekomo zostali upokorzeni poprzez zmuszenie ich do oczekiwania na korytarzu na spotkanie z Donaldem Trumpem. W rzeczywistości zdjęcie zostało wygenerowane przez AI.

### 10. Poczet królów Lechii? Imperium Lechitów to pseudonaukowa teoria

- ID: `fc-5d2f339668`
- Przed: Czy Polska była kiedyś starożytnym imperium? Tak twierdzą zwolennicy teorii o Wielkiej Lechii. Dowodem na to ma być obraz przedstawiający „poczet królów Lechii”.
- Po: Wspomniane zdjęcie przedstawia obraz z drugiej połowy XVIII wieku wystawiony na Jasnej Górze. Jest to poczet władców Polski – zarówno tych historycznych, jak i legendarnych, takich jak Lech , Wanda czy Popiel . Nie jest to źródło historyczne, które poświadcza ich istnienie.

## Znane ograniczenia

- Kontrola dosłowności odnosi się do tekstu automatycznie wyodrębnionego z pobranej strony, a nie do niezależnej kontroli kompletności każdego artykułu, obrazów czy załączników.
- Część komunikatów ma charakter historyczny lub czasowy: sam cytat nie dowodzi, że komunikat nadal obowiązuje. Wymagane jest sprawdzanie dat i sprostowań.
- Wycofanie 119 rekordów opiera się na przekazanej liście, nie na ponownym niezależnym rozstrzygnięciu potrzeby wycofania każdego z nich.
- Wdrożenie wstrzymano z powodu opisanego niżej błędnego werdyktu w teście N04 oraz niedokończonej oceny jakości próby.

## Porównanie odpowiedzi v5 i v6

Przeprowadzono po jednym przebiegu 32 pytań `eval/pytania_rozszerzenie.jsonl` na każdym korpusie, z rzeczywistym modelem; wyniki mogą się różnić między uruchomieniami. Użyto funkcji `end_to_end` i `summarize` z `eval/compare_corpus.py` z BM25. Pełne odpowiedzi: `eval/wyniki_korpus_v6.json`.

- v5: zgodność werdyktów 25/29; cytowanie oczekiwanego źródła 18/21; fałszywy werdykt w przypadkach oznaczonych jako brak dowodu 0/8; błędy techniczne 0.
- v6: zgodność werdyktów 22/29; cytowanie oczekiwanego źródła 14/21; fałszywy werdykt w przypadkach oznaczonych jako brak dowodu 0/8; błędy techniczne 0.

**Istotna regresja N04:** prawidłowy komunikat dotyczący niezdatnej wody w Świeradowie-Zdroju był na liście wycofanych. Przy v6 system odnalazł inny komunikat RCB z tego samego dnia i błędnie uznał zapytanie za fałszywe. Miernik błędnych werdyktów przy braku dowodu tego nie wykrywa, ponieważ pytanie N04 jest oznaczone jako potwierdzone. Nie przywracano dokumentu, gdyż użytkownik polecił pozostawić rekordy z listy wycofane. Potrzebne jest bezpieczne rozróżnienie komunikatów lub uzgodnienie przywrócenia źródła.

Lokalny `/health` z v6: HTTP 200, 392 dokumenty. Konfiguracja `.env` i Fly nie zostały przełączone.
