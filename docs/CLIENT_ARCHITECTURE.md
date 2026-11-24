# AC Endurance Client – architektura i weryfikacja możliwości

## Wybór moda

Klient to aplikacja CSP Lua (`client/csp/ac_endurance_client`). CSP Lua Apps są ładowane z `assettocorsa/apps/lua/<nazwa>/`, mają HUD przez `ui.*`, dane lokalnego/pozostałych aut przez `ac.getCar()` i asynchroniczne połączenia HTTP/WebSocket przez `web.request`/`web.socket`. Zastosowanie: CSP 0.2.0+ (wymóg wpisany w manifeście). Nie jest wymagany ACSM ani RaceControl. Klasyczne Python Apps korzystają ze starego środowiska Python 3.3 i pozostają nieużywane; nie są potrzebne do tego kanału.

Do zainstalowania CSP Lua Apps potrzebny jest klient Assetto Corsa na Windows z CSP. Sam Content Manager nie jest biblioteką runtime, ale jest zalecaną drogą włączania/instalacji CSP i Lua Apps. Bez CSP aplikacja nie ładuje się; backend i serwer działają niezależnie.

## Kanał klient–backend

- Klient łączy się przez WSS do `/ws/client`, z tokenem `Authorization: Bearer …`.
- Token jest losowy, przypisany do jednego kierowcy i przechowywany w bazie jako SHA-256. `tools/mint_client_token.py` wydaje go jednorazowo.
- Serwer wysyła odświeżany snapshot wyścigu oraz tożsamość kierowcy/drużyny przypisaną po stronie serwera. Klient nie może podać własnej drużyny ani modyfikować wyniku/kar/stanu wyścigu.
- Jedynym poleceniem zmieniającym dane klienta jest zgłoszenie incydentu; tworzy ono sprawę `NEW` dla weryfikacji sędziego.
- W produkcji TLS musi zapewnić reverse proxy (np. nginx/Caddy) przed lokalnym procesem. Nie wystawiaj surowego endpointu WebSocket na publiczny Internet. Hasło/token przypisany kierowcy pozostaje sekretem względem innych zawodników, ale nie można ukryć go przed właścicielem komputera, na którym działa mod.
- Przykładowy fragment nginx znajduje się w `deployment/nginx-client-ws.conf`; certyfikat TLS i przekierowanie HTTP→HTTPS należy skonfigurować dla własnej domeny.
- Adapter UDP serwera jest osobny; nie miesza się z WebSocket klienta. Utrata pakietów AC UDP nie przerywa kanału HUD.

## Rzeczywiste możliwości i ograniczenia

| Funkcja | Status w tej wersji |
| --- | --- |
| Własne okno HUD i lokalne pozycja/okrążenie/czas/auto | Zaimplementowane; wymaga testu w grze |
| Tożsamość kierowcy i zespół | Zaimplementowane przez przypisany token, w grze nie ufa się nazwie pokazanej przez klienta |
| Komunikaty i flaga na HUD | Snapshot backendu zaimplementowany; backend wymaga publikacji stanu przez narzędzie administratora |
| Zgłoszenie incydentu | Zaimplementowane jako skierowana do sędziego sprawa, bez automatycznej kary |
| Kary, plan swapu i następny kierowca | Snapshot HUD oraz panel kar/planu są zaimplementowane; kara jest decyzją stewarda, a swap pozostaje wyłącznie planem |
| Dane o pozycjach wszystkich aut | CSP może je lokalnie odczytać; backendowa wspólna klasyfikacja musi korelować z serwerowymi wynikami/UDP |
| Paliwo/opony/temperatury/pozycja | CSP może część odczytać z lokalnego klienta; to samo w sobie nie jest autorytatywnym źródłem serwerowym |
| Flagi, SC/VSC/FCY | HUD tylko komunikuje procedurę. Nie wymusza fizycznych ograniczeń aut w klasycznej grze |
| Detekcja incydentów i VAR | Lokalny CSP ma collision/track state APIs, ale brak wiarygodnego serwerowego osądu. Ten klient tylko przyjmuje zgłoszenie |
| Replay/OBS | Osobny worker obserwatora, kolejka incydentów, OBS Replay Buffer, upload, odtwarzanie i retencja są zaimplementowane; wymagają konfiguracji OBS i próby praktycznej |
| Driver swap z zachowaniem stanu auta | Nieobsługiwane. CSP Lua App nie przenosi kontrolera istniejącego auta między kontami sieciowymi. Nie wykonujemy resetu ani fikcyjnego swapu |

## Driver Swap

Standardowy serwer AC przypisuje samochód do połączenia/kierowcy. Inny klient nie może przejąć tej samej aktywnej sesji auta z zachowaniem tożsamości, przy zachowaniu wszystkich pól symulacji i bez rozłączenia/resetu. HUD może alarmować o zaplanowanej zmianie i prowadzić checklistę pit stopu, ale nie wykonuje driver swap. Rozwiązanie wymaga dedykowanego, kompatybilnego pluginu serwerowego/zmodyfikowanego klienta i rygorystycznych prób: stanowisko/pit, reconnect, stan auta, brak teleportu. Nie znaleziono podstaw, by uznać to za możliwe w Lua app CSP ani w natywnym UDP AC; obecnie status: wymaga osobnego komponentu eksperymentalnego.

## Instalacja

1. Administrator utworzy konto kierowcy i wyda token: `python3 tools/mint_client_token.py var/endurance.sqlite3 <driver-id>`.
2. Zainstaluje paczkę: `python3 tools/install_client.py "C:/Program Files (x86)/Steam/steamapps/common/assettocorsa" --url wss://race.example.org/ws/client --token <token>`.
3. W Content Manager włączy CSP 0.2.0+, Lua Apps i widoczność aplikacji. Gracz otworzy `Endurance Control` z paska aplikacji.

Zmiany CSP Lua API należy sprawdzać dla docelowej wersji patcha. Sam parser Lua poza grą nie dowodzi prawidłowego działania renderowania, certyfikatów ani sieci w CSP.

## Źródła

- [CSP Lua Apps – dokumentacja SDK](https://github.com/ac-custom-shaders-patch/acc-lua-sdk/wiki/Lua-apps)
- [CSP Lua SDK – WebSocket i HTTP API](https://github.com/ac-custom-shaders-patch/acc-lua-sdk/blob/main/lib_web.lua)
- [CSP Lua API – wprowadzenie i struktura app](https://lint069.github.io/csp-lua-api-docs/guides/getting-started/)
- [CSP Lua API – dane StateCar](https://github.com/ac-custom-shaders-patch/acc-lua-sdk/blob/main/common/ac_state.lua)
