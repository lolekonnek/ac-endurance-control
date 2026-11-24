# Analiza techniczna Assetto Corsa Dedicated Server

## Zweryfikowane granice

Natywny interfejs UDP serwera jest konfigurowany przez `UDP_PLUGIN_LOCAL_PORT` (port lokalny, na którym serwer odbiera polecenia pluginu) i `UDP_PLUGIN_ADDRESS` (adres odbiorcy zdarzeń). Port odbiornika aplikacji (`ACEC_UDP_PORT`) jest niezależny; `UDP_PLUGIN_ADDRESS` musi wskazać właśnie jego. To binarny, little-endian protokół ACSP, nie HTTP/JSON. `AUTH_PLUGIN_ADDRESS` jest oddzielnym adresem dla pluginu autoryzacji; nie jest kanałem telemetrii ani API do sterowania wyścigiem. Format pakietów opiera się na publicznie dostępnej implementacji ACSP oraz Pythonowym przykładzie UDP powiązanym z przykładowym pluginem Kunos; trzeba zweryfikować na używanej wersji binarnej.

Rozpoznane identyfikatory komunikatów serwera: NEW_SESSION 50, NEW_CONNECTION 51, CONNECTION_CLOSED 52, CAR_UPDATE 53, CAR_INFO 54, END_SESSION 55, VERSION 56, CHAT 57, CLIENT_LOADED 58, SESSION_INFO 59, ERROR 60, LAP_COMPLETED 73, CLIENT_EVENT 130. Zdarzenia kolizji to CLIENT_EVENT z typem 10 (auto-auto) lub 11 (auto-otoczenie). Polecenia pluginu: REALTIMEPOS_INTERVAL 200, GET_CAR_INFO 201, SEND_CHAT 202, BROADCAST_CHAT 203, GET_SESSION_INFO 204, SET_SESSION_INFO 205 i KICK_USER 206. Komendy są binarne i nie są równoważne wszystkim komendom administracyjnym serwera.

Car update zawiera ID auta, wektor pozycji i prędkości, bieg, obroty i pozycję znormalizowaną na splajnie. Lap completed zawiera czas okrążenia, cuts, liczbę aut oraz leaderboard, grip. Car info i połączenia udostępniają nazwę kierowcy, GUID, auto i skin. Nie wolno wyciągać z tych komunikatów paliwa, mieszanki/zużycia opon, uszkodzeń, bieżącej kontroli samochodu ani statusu tankowania — tych pól tu nie ma.

Pliki `results/*.json` są końcowym źródłem klasyfikacji po zakończeniu sesji, a logi i pliki konfiguracyjne są źródłami pomocniczymi. Procesowe zatrzymanie/restart LinuxGSM nie może zamykać wydarzenia; stan wyścigu należy utrzymywać osobno, a wyniki scalać po identyfikatorach sesji i plików. Zapis replay jest funkcją klienta gry/obserwatora; dedykowany serwer nie tworzy gotowego wideo. OBS Replay Buffer na maszynie obserwatora to oddzielna integracja.

## Wykonalność wymagań

| Funkcja | Tylko natywny serwer/UDP | Bezpieczna implementacja |
| --- | --- | --- |
| timing, połączenia, pozycja, kolizje | Tak, z ograniczeniami/utraconymi pakietami | UDP + końcowy JSON jako uzgodnienie |
| wiadomość czatu | Tak | UDP chat; komunikaty w bazie i ponawianie osobno |
| kick | Tak | polecenie pluginu, uprawnienia/audyt w aplikacji |
| restart/proces | Nie przez UDP | LinuxGSM, wykrywanie PID i blokada drugiej instancji |
| drive swap z zachowaniem auta | Nie | Wymaga przetestowanego pluginu/procedury gry; bez tego niewspierane |
| pit lane, prędkość, paliwo, opony, damage | Nie wprost | klient telemetryczny/Real Penalty lub ręczna weryfikacja |
| SC/VSC/FCY i flagi | Nie jako pełna kontrola wyścigu | komunikaty + procedury organizacyjne / kompatybilna aplikacja |
| replay/wideo/VAR | Nie | klient obserwatora/replay lub OBS na zewnętrznej maszynie |
| AUTH_PLUGIN_ADDRESS | Tylko plugin auth | przyszły adapter auth; nie zakładamy prywatnego API |

## Plan etapów

1. Fundament: adapter UDP z trwałym raw logiem i deduplikacją, SQLite, role/audyt i roster. (częściowo rozpoczęte)
2. Zarządzanie serwerem: odczyt config, wykrywanie instalacji, LinuxGSM status/restart z blokadą duplikatu, kopie configu; żadnych zmian na produkcyjnej konfiguracji bez operatora.
3. Mechanika wydarzenia: sesje/okrążenia, wyniki końcowe, klasyfikacja, pitstop ręczny i harmonogram swap jako plan/alert, nie jako potwierdzenie swapu w grze.
4. Race control: kary i flagi jako audytowane decyzje/komunikaty; automatyczne wykrycia tylko jako kandydaci do weryfikacji.
5. Panel WWW/API i role, WebSocket/live timing, panel publiczny.
6. Replay recorder na kliencie obserwatora, powiązanie OBS/replay z incydentami.
7. Wdrożenie systemd, kopie bazy, monitoring i próba 24h.

## Źródła protokołu

- [ACSP – implementacja protokołu serwera AC](https://github.com/flamescape/acsp) (implementacja społecznościowa, nie formalna gwarancja Kunos).
- [ac-pserver – Pythonowy przykład UDP oparty na przykładzie Kunos](https://github.com/mathiasuk/ac-pserver).
- [ACServerPlugin – alternatywny plugin telemetryczny wykorzystujący API klienta/shared memory](https://github.com/SDavey149/ACServerPlugin), opcjonalny i nie wymagany przez ten projekt.

Dokumentacja protokołu jest niepełna i część wiedzy pochodzi z reverse engineeringu. Wersję AC należy traktować jako niezweryfikowaną, dopóki nie przejdzie przechwycenia i walidacji na tej konkretnej instalacji.
