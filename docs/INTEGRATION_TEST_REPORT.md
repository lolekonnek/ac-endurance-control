# Raport audytu i testów integracyjnych AC Endurance Control

**Data audytu:** 2026-11-24  
**Zakres:** kod i testy w repozytorium, lokalna diagnostyka serwera LinuxGSM, sprawdzenie instalatora w katalogu tymczasowym oraz przegląd dokumentacji CSP. Nie wykonywano zmian w konfiguracji serwera ani nie podłączano gry/OBS.

## Podsumowanie

- **Backend:** 13 testów jednostkowych/API przeszło, a kod Pythona kompiluje się. Pełny test uruchomionych endpointów, WebSocket i odbiornika UDP nie został wykonany: sandbox odmówił utworzenia lokalnego gniazda (`PermissionError`).
- **LinuxGSM:** odczyt konfiguracji wskazał `UDP_PLUGIN_ADDRESS=` oraz `UDP_PLUGIN_LOCAL_PORT=0`. Odbiór eventów UDP z obecnego serwera nie jest skonfigurowany. Żadna konfiguracja nie została zmieniona.
- **CSP:** pliki i manifest są zgodne ze strukturą aplikacji opisanej przez CSP. API `web.socket` i parametry JSON/reconnect/callback występują w SDK. Nie uruchomiono Lua ani Assetto Corsa, więc połączenie WSS, autoryzacja, HUD i reconnect pozostają do sprawdzenia na komputerze gracza.
- **VAR/OBS:** backendowe testy uploadu, przypisania, Range playback i retencji przeszły. OBS Replay Buffer, agent i rzeczywisty klip nie były dostępne do uruchomienia.

## 1. Backend

| Funkcja | Status | Sposób testowania i wynik | Ograniczenia | Kolejne działanie |
|---|---|---|---|---|
| Testy API, logowania i ról | **Zaliczone w testach automatycznych** | `PYTHONPATH=. python3 -m unittest discover -s tests -v` — 13/13 testów przeszło. `test_api` sprawdza brak dostępu bez logowania, logowanie, utworzenie wydarzenia, zmianę stanu i audyt. | Nie sprawdzono HTTP przez uruchomiony proces. Pokrycie ról nie jest pełną macierzą wszystkich endpointów. | Na lokalnej maszynie uruchomić backend i wykonać smoke test z kontami każdej używanej roli.
| Start backendu | **Niezweryfikowany w runtime** | Próba izolowanego uruchomienia wymagała lokalnych socketów; sandbox odmówił już przy próbie rezerwacji portu (`PermissionError: Operation not permitted`). | Nie wiadomo, czy porty są wolne, czy proces uruchomi się pod docelowym użytkownikiem ani czy usługa systemd ma kompletne środowisko. | Uruchomić w środowisku serwera z poprawnym plikiem środowiskowym i potwierdzić `/api/health`, logi systemd oraz działanie trzech listenerów.
| WebSocket klienta | **Częściowo pokryty testami; handshake runtime niezweryfikowany** | Testy sprawdzają format ramki serwera i mapowanie tokenu na kontekst kierowcy. Kod endpointu sprawdza ścieżkę, Bearer token, handshake, snapshot, ping, zgłoszenie incydentu i wejście/wyjście z pit lane. | Nie wykonano handshake'u z prawidłowym i błędnym tokenem ani ciągłej wymiany ramek z działającym serwerem. Test ramki nie testuje całego RFC 6455. | Z klienta testowego sprawdzić handshake, snapshot co sekundę, odrzucenie błędnego tokenu, raport incydentu, ping/close i ponowne łączenie.
| Zapis i odtworzenie po restarcie | **Częściowo potwierdzone; restart procesu niezweryfikowany** | `test_store` potwierdza zapis eventu/okrążenia i deduplikację. Testy używają trwałego pliku SQLite; backend tworzy schemat WAL. Proces nie został uruchomiony/zrestartowany w tej sesji. | Nie wykonano kill/restart procesu z otwartą bazą, crash recovery ani próby 24 h. | Wykonać test poniżej na osobnej bazie testowej; nie używać produkcyjnej bazy do prób zapisu.
| Parser i obsługa UDP | **Zaliczone testami parsera; odbiór UDP runtime niezweryfikowany** | `test_protocol` pokrywa przykładowe pakiety update/lap, ucięty pakiet i NaN. Dostępny `simulator/send_packets.py` wysyła dwa pakiety syntetyczne. | Nie uruchomiono listenera, więc generator nie został wysłany. Pakiety z helpera są syntetyczne i nie pochodzą z gry ani serwera AC. | Uruchomić listener na nieprodukcyjnym porcie, wysłać syntetyczne pakiety, potwierdzić wzrost `raw_events`/`laps`, potem zweryfikować eventy z prawdziwej instancji testowej AC.
| Wyniki / import JSON | **Zaliczone w teście jednostkowym** | Test store weryfikuje import, hashowanie GUID i idempotencję. | Nie porównano z plikiem wyników z Twojego serwera. | Po zakończonej sesji testowej zaimportować kopię pliku wyników i porównać klasyfikację ręcznie.

### Polecenia testowe odtworzenia stanu

Na maszynie testowej, z osobnym `ACEC_DB`, utwórz użytkownika i uruchom backend. Zmień stan przez panel/API, zatrzymaj proces normalnie, uruchom ponownie i potwierdź, że stan oraz rekordy nadal istnieją. Następnie powtórz z wymuszonym zakończeniem procesu tylko na kopii bazy. Nie kasuj produkcyjnego pliku SQLite ani plików WAL/SHM ręcznie.

## 2. Mod CSP

| Funkcja | Status | Sposób testowania i wynik | Ograniczenia | Kolejne działanie |
|---|---|---|---|---|
| Struktura Lua App | **Zgodność statyczna potwierdzona** | Katalog `client/csp/ac_endurance_client` zawiera `manifest.ini` oraz `ac_endurance_client.lua`; nazwa głównego pliku odpowiada katalogowi. Manifest deklaruje `WINDOW_MAIN`, `FUNCTION_MAIN=windowMain`, a kod zawiera `script.update` i `script.windowMain`. | Brak testu loadera CSP i runtime LuaJIT w grze. | Sprawdzić log Lua/CSP po pierwszym uruchomieniu oraz czy aplikacja widnieje na pasku aplikacji.
| Zgodność z dokumentacją CSP | **Przegląd statyczny zgodny w sprawdzonym zakresie** | Oficjalne repozytorium SDK opisuje katalogi `assettocorsa/apps/lua`, manifest `[ABOUT]`, `[CORE]`, `[WINDOW_*]`, `FUNCTION_MAIN`, callback `script.update`; kod korzysta z `web.socket(url, headers, callback, params)`, `encoding='json'`, `reconnect`, `onError`, `onClose`, zgodnie z API źródłowym. | Wpis `REQUIRED_VERSION=0.2.0` jest wymaganiem projektu; dokumentacja struktury podaje, że Lua Apps istnieją od CSP 0.1.76. Nie dowodzi to kompatybilności konkretnych wersji gry/CSP. | Zweryfikować na docelowej wersji CSP; zapisać numer wersji CSP użytej w teście. [Dokumentacja Lua Apps](https://github.com/ac-custom-shaders-patch/acc-lua-sdk/wiki/Lua-apps), [implementacja API web.socket](https://github.com/ac-custom-shaders-patch/acc-lua-sdk/blob/main/lib_web.lua).
| Instalator | **Zaliczone dla próby w katalogu tymczasowym** | `tools/install_client.py` uruchomiony na pustym katalogu tymczasowym ze ścieżką zawierającą spację. Powstały oba pliki; URL WSS i token zostały podstawione. | Nie zainstalowano do katalogu prawdziwej gry Windows. Próba nie sprawdza uprawnień UAC, wykrywania ścieżki ani zachowania przy aktualizacji istniejącej instalacji. | Uruchomić na Windows na kopii/instalacji testowej Assetto Corsa i potwierdzić docelową ścieżkę.
| WSS i autoryzacja kierowcy | **Niezweryfikowane w grze** | Statycznie: klient dodaje `Authorization: Bearer <token>`; backend mapuje hash tokenu do kierowcy/zespołu. Test tokenu sprawdza kontekst właściwego kierowcy i odrzucenie obcego hasha. | Nie wykonano rzeczywistego połączenia TLS/WSS, certyfikatu, tokenu z backendu ani testu tokenu odwołanego. | Wykonać kroki Windows poniżej z tokenem testowego kierowcy; powtórzyć z błędnym tokenem i potwierdzić odmowę.
| Dane HUD | **Niezweryfikowane w grze** | Kod rysuje stan wyścigu/flagę/wiadomość, tożsamość, pozycję, okrążenie, czasy, pit lane, kary i alert zmiany. | Nie potwierdzono nazw funkcji/fieldów CSP dla konkretnej wersji, widoczności w sesji ani jakości layoutu. Dane auta z CSP nie są autorytatywnym timingiem serwera. | Na torze testowym potwierdzić pola HUD oraz aktualizację flagi/wiadomości po zmianie z panelu.
| Utrata i ponowne połączenie | **Niezweryfikowane w runtime** | Kod ustawia `reconnect=true` i pokazuje `onError`/`onClose`; SDK udostępnia te opcje. | Nie wyłączano sieci, proxy ani backendu podczas jazdy. Reconnect jest realizowany przez CSP; kod nie ustawia `socket=nil` po zamknięciu. | Przerwać sieć/backend na 10–20 s, przywrócić i sprawdzić, czy status przechodzi z błędu do połączenia i snapshot wraca bez restartu gry.

### Instrukcja testu Windows + Assetto Corsa + Content Manager

1. Przygotuj serwer testowy z TLS działającym dla `wss://<domena>/ws/client`. Najpierw otwórz w przeglądarce `https://<domena>/api/health`; potwierdź zdrową odpowiedź. Użyj konta testowego i jednorazowego tokenu konkretnego kierowcy. Nie wklejaj tokenu administratora ani sekretu `ACEC_GUID_PEPPER` do klienta.
2. Zamknij Assetto Corsa. Odszukaj katalog główny gry (zwykle `steamapps\common\assettocorsa`). W PowerShell uruchom instalator z repozytorium, podstawiając prawdziwą ścieżkę, domenę i token:

   ```powershell
   py .\tools\install_client.py "C:\Program Files (x86)\Steam\steamapps\common\assettocorsa" --url "wss://race.example.org/ws/client" --token "TOKEN_KIEROWCY"
   ```

   Sprawdź, czy powstały `apps\lua\ac_endurance_client\manifest.ini` i `ac_endurance_client.lua`. Token jest zapisany jawnie w pliku Lua na komputerze kierowcy; traktuj go jak hasło i nie publikuj pliku.
3. W Content Manager wybierz wersję CSP co najmniej 0.2.0, włącz Custom Shaders Patch i Lua Apps. Uruchom Assetto Corsa w sesji testowej, włącz aplikację **Endurance Control** z paska aplikacji i sprawdź, czy nie pojawia się błąd aplikacji w logu CSP.
4. Zaloguj się do panelu jako race control i ustaw wyróżniającą się flagę oraz wiadomość. Potwierdź na HUD: nazwę kierowcy/zespołu z tokenu, flagę i wiadomość. Jedź przez linię startu i potwierdź zmianę okrążenia/czasów, pozycję, prędkość i tor; przejedź pit lane i sprawdź status. Porównaj wartości lokalne z timingiem serwera, pamiętając, że pola auta pochodzą z CSP.
5. Naciśnij **Zgłoś incydent**. W panelu sędziowskim sprawdź, że powstało zgłoszenie `NEW`; sprawdź też, że samo zgłoszenie nie nadało kary.
6. Zatrzymaj backend lub odłącz sieć na 10–20 s, obserwuj status rozłączenia, przywróć połączenie i potwierdź automatyczny powrót snapshotu. Potem wprowadź testowo błędny token: klient nie powinien otrzymać danych przypisanego kierowcy. Po próbie przywróć prawidłowy token.
7. Zanotuj wersje gry/CSP/Content Manager, wynik każdego kroku i kopię odpowiednich logów CSP. Po teście unieważnij testowy token, jeśli nie będzie dalej używany.

## 3. VAR i OBS

| Funkcja | Status | Sposób testowania i wynik | Ograniczenia | Kolejne działanie |
|---|---|---|---|---|
| Integracja OBS WebSocket | **Niezweryfikowana** | Kod workera używa `obsws_python.ReqClient` i żąda statusu Replay Buffer, startu bufora, zapisu oraz ostatniej ścieżki pliku. Zależność jest wskazana w `replay_recorder/requirements.txt`. | Nie było dostępnej sesji OBS ani aktywnego serwera WebSocket. Nie potwierdzono wersji OBS/protokołu ani prawdziwych nazw/odpowiedzi pól w użytej wersji. | Zainstalować OBS i worker na komputerze obserwatora, wykonać próbę z lokalnym OBS WebSocket i zapisać log agenta.
| Replay Buffer | **Niezweryfikowany** | Kod sprawdza `output_active` i uruchamia bufor, jeśli nie działa. | Nie sprawdzono długości bufora, miejsca na dysku, kodera ani zachowania po restarcie OBS. | Uruchomić bufor ręcznie, potwierdzić status aktywny i upewnić się, że obejmuje wymagane sekundy przed incydentem.
| Zapis klipu z incydentu | **Niezweryfikowany z OBS; przepływ backendu pokryty testem** | `test_replays` przechodzi claim/upload/range/retention. Agent czeka `ACEC_REPLAY_POST_SECONDS`, zapisuje bufor, czeka do 10 s na plik, limituje rozmiar do 250 MiB. | Nie utworzono pliku przez OBS. Zależność czasowa oznacza, że długość bufora musi obejmować przedział poprzedzający zgłoszenie. | Wywołać incydent testowy i potwierdzić utworzenie klipu oraz zmianę statusu sprawy na SAVED.
| Upload | **Backend zaliczony testem; agent runtime niezweryfikowany** | Test API obejmuje claim, upload i zapis. Worker przesyła plik jako binarne body z `X-Filename`, uwierzytelniając się HTTPS. | Brak próby z kontem agenta, TLS, dużym plikiem albo przerwanym uploadem. | Przesłać mały klip testowy przez agenta; potem sprawdzić błąd sieci i możliwość odzyskania lease.
| Powiązanie klipu z incydentem | **Zaliczone testem backendu** | Test sprawdza upload przypisany do identyfikatora zgłoszenia, ręczne dołączenie i odzyskanie nieaktualnego claimu. | Nie potwierdzono pełnego przepływu CSP → kolejka → worker OBS. Współbieżne incydenty mogą otrzymać fragment tego samego bufora. | Wykonać pełny test z jednym incydentem i sprawdzić właściwy identyfikator/status w panelu.
| Odtwarzanie w panelu | **Backendowy streaming pokryty testem; przeglądarka niezweryfikowana** | Test API sprawdza żądanie zakresu bajtów (HTTP Range). Endpoint wymaga roli sędziego/dyrekcji i statusu SAVED. | Nie odtwarzano pliku w docelowej przeglądarce ani na prawdziwym klipie z OBS. | Otworzyć SAVED wideo w panelu, przetestować seek, pełny odczyt oraz odmowę dostępu dla roli bez uprawnień.

### Test VAR na komputerze OBS

Użyj konta `race_control`/`steward` do workera i włącz OBS WebSocket z mocnym hasłem, dostępnym wyłącznie lokalnie lub przez zaufany LAN/VPN. Nie wystawiaj portu 4455 publicznie. Ustaw Replay Buffer dłuższy niż `ACEC_REPLAY_POST_SECONDS` oraz wystarczającą przestrzeń dyskową. Uruchom workera z `ACEC_API_URL` wskazującym HTTPS i wymaganymi zmiennymi środowiskowymi. Zgłoś incydent z panelu lub CSP, poczekaj na SAVED, otwórz klip w panelu i potwierdź seek. Przetestuj też brak bufora, nieosiągalne OBS i niedostępny backend: w logu ma być błąd, a incydent nie może udawać zapisanego klipu.

## 4. Bezpieczne podłączenie do istniejącego serwera AC zarządzanego przez LinuxGSM

### Stan odczytany podczas audytu

Polecenie `python3 tools/server_manager.py status` wykryło instalację skonfigurowaną przez `ACEC_SERVER_ROOT` i `ACEC_LGSM` oraz odczytało konfigurację. W wykrytym pliku `server_cfg.ini` są:

```ini
UDP_PLUGIN_LOCAL_PORT=0
UDP_PLUGIN_ADDRESS=
AUTH_PLUGIN_ADDRESS=
```

To oznacza, że obecna konfiguracja nie wysyła eventów serwera do adaptera. Raport nie zmieniał tych pól, nie uruchamiał restartu i nie włączał usługi. `AUTH_PLUGIN_ADDRESS` jest osobnym kanałem pluginu autoryzacji i nie należy wpisywać tam adresu adaptera telemetrycznego.

### Procedura bez zmian do czasu Twojej zgody

1. **Inwentaryzacja tylko do odczytu:** na serwerze zapisz `python3 tools/server_manager.py status`, sprawdź `pgrep -af acServer`, status LinuxGSM oraz aktualne `UDP_PLUGIN_*` i `AUTH_PLUGIN_ADDRESS`. Zapisz, czy inny plugin (np. Real Penalty/RaceControl) używa `UDP_PLUGIN_ADDRESS`. Nie wyświetlaj ani nie wysyłaj publicznie haseł, GUID-ów i tokenów.
2. **Uruchom adapter odizolowany:** najpierw użyj kopii bazy i listenera testowego. W docelowym systemie sprawdź, czy `ACEC_UDP_PORT` wolny i czy firewall dopuszcza UDP tylko z hosta serwera AC. Domyślny listener projektu wiąże `0.0.0.0:12001`; ograniczenie źródła w firewallu jest wskazane.
3. **Sprawdź kolizję pluginów:** klasyczny AC zwykle ma jedno `UDP_PLUGIN_ADDRESS`. Jeśli jest zajęty, nie nadpisuj go i nie zakładaj, że dwa odbiorniki mogą współdzielić eventy. Najpierw zaprojektuj i przetestuj świadomy UDP relay/forwarder.
4. **Przygotuj zmianę, ale jej nie stosuj:** jeżeli adapter działa na tym samym hoście i UDP port `12001` jest wolny, proponowana minimalna zmiana dla obecnego adaptera odbiorczego to `UDP_PLUGIN_ADDRESS=127.0.0.1:12001`; pozostaw `UDP_PLUGIN_LOCAL_PORT=0`, bo projekt nie wysyła poleceń pluginu do serwera. Nie zmieniaj `AUTH_PLUGIN_ADDRESS`. Społecznościowy przykład Kunos UDP wiąże IP/port odbiorcy z `UDP_PLUGIN_ADDRESS` i port odpowiedzi z `UDP_PLUGIN_LOCAL_PORT` ([ac-pserver](https://github.com/mathiasuk/ac-pserver)); potwierdź zachowanie na zainstalowanej wersji `acServer` przed zmianą.
5. **Przed wdrożeniem:** zaplanuj okno serwisowe i dopiero po osobnej zgodzie wykonaj kopię configu (`python3 tools/server_manager.py backup`), przygotuj rollback, wprowadź minimalną zmianę i restartuj przez LinuxGSM. Samo wykonanie backupu jest bezpieczne, ale zmiana pliku/restart wymaga Twojej zgody. Nie używaj `restart --confirm` bez zatwierdzonego okna.
6. **Weryfikacja po zgodzie:** sprawdź logi backendu pod kątem `UDP ... from ...`, obecność eventów, liczniki `/api/health`, zgodność kierowcy/auta i wyniki końcowe. Porównaj z logiem/stanem serwera. Jeśli pakiety nie docierają lub występują błędy, natychmiast przywróć kopię i restartuj przez LinuxGSM w uzgodnionym oknie.
7. **Dopiero po próbie:** rozważ usługę systemd i backup bazy. Pliki `deployment/acec.service` i backup timer wymagają sprawdzenia użytkownika, ścieżek, sekretów oraz uprawnień dla konkretnej instalacji. Nie instalowano ani nie włączano ich podczas tego audytu.

Nie podłączaj adaptera do trwającego wyścigu. Włączenie `UDP_PLUGIN_ADDRESS` wymaga zmiany konfiguracji i restartu serwera; tej zmiany nie wykonam bez Twojej zgody.

## 5. Dokładna lista rzeczy do wykonania na komputerze z uruchomioną grą

1. Zainstalować paczkę na Windows, włączyć CSP Lua Apps i zanotować wersję gry/CSP/Content Manager.
2. Połączyć właściwy token kierowcy przez WSS; potwierdzić odrzucenie nieprawidłowego tokenu.
3. W grze sprawdzić HUD: kierowca/zespół, flaga, komunikat, kara, pozycja, okrążenie, czasy, prędkość i pit lane. Zmienić flagę/wiadomość w panelu i potwierdzić synchronizację.
4. Zgłosić incydent i potwierdzić wpis `NEW` w panelu bez automatycznej kary.
5. Wyłączyć sieć lub backend na 10–20 sekund, potwierdzić komunikat utraty połączenia i automatyczne odzyskanie snapshotu.
6. Na komputerze obserwatora uruchomić OBS z Replay Buffer i agenta, wykonać testowy incydent, sprawdzić upload, przypisanie oraz odtworzenie/seek klipu w panelu.
7. Przekazać wynik kroków, log CSP, log workera OBS i (jeśli test integracji serwera jest zatwierdzony) log backendu. Usuń testowe tokeny po teście.

## Wykonane polecenia i granice audytu

- `PYTHONPATH=. python3 -m unittest discover -s tests -v` — **13/13 OK**.
- `python3 -m compileall -q ac_endurance simulator tests tools replay_recorder` — **OK**.
- `python3 tools/install_client.py ...` na tymczasowym katalogu — **OK**, oba pliki i podstawienia sprawdzone.
- `python3 tools/server_manager.py status` — tylko odczyt; `UDP_PLUGIN_ADDRESS` pusty.
- Próba uruchomienia backendu i lokalnego smoke testu socketów — **nie została wykonana**, bo środowisko sandbox odmówiło utworzenia gniazda. Nie traktować jako błąd backendu ani jako zaliczonego testu.
- Nie uruchomiono Assetto Corsa/CSP/Content Manager, OBS, LinuxGSM restartu ani testu 24-godzinnego.

## Gotowość publikacji klienta GitHub

| Element | Status | Wynik / ograniczenie | Kolejne działanie |
|---|---|---|---|
| Paczka ZIP klienta | **Zbudowana i sprawdzona statycznie** | `python3 tools/package_client.py` utworzył ZIP z manifestem, Lua App, instalatorem i README. Zawiera szablon `SET_DRIVER_TOKEN`, nie zawiera tokenu kierowcy. | Dołączyć ZIP do GitHub Release po Windows smoke test.
| Instalator Windows | **Przygotowany; nieuruchomiony na Windows** | Wykrywa dwie typowe ścieżki Steam, pyta o URL/token, waliduje dane i robi kopię istniejącej instalacji. | Uruchomić go na prawdziwym komputerze z grą i CSP.
| Workflow GitHub Actions | **Przygotowany; nieuruchomiony na GitHubie** | Ręczny workflow lub tag `client-v*` buduje i publikuje ZIP jako artifact workflow. Nie tworzy automatycznie GitHub Release. | Po dodaniu repozytorium uruchomić Actions; zweryfikować artifact, następnie dołączyć ręcznie do Release.
| Licencja projektu | **Decyzja właściciela wymagana przed publicznym repo** | Nie dodano `LICENSE`, ponieważ wybór licencji jest decyzją prawną/właścicielską. | Wybrać licencję i dodać właściwy plik przed publicznym udostępnieniem.
