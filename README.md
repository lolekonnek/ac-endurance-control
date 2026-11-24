# AC Endurance Control

Samodzielny system backendu i moda dla klasycznej Assetto Corsa Dedicated Server. Nie wymaga ACSM ani RaceControl. Backend i serwer Linux są odseparowane od klienta gry: HUD działa jako CSP Lua App na komputerze gracza, a nagrywanie VAR jako osobny worker OBS na komputerze obserwatora.

## Status projektu

| Obszar | Stan |
| --- | --- |
| Backend SQLite, logowanie, role i audyt | Zaimplementowane; testy jednostkowe/API przechodzą |
| Adapter AC UDP, okrążenia, połączenia, kandydaci kolizji | Zaimplementowane według społecznościowego opisu ACSP; wymaga przechwycenia z tej konkretnej wersji serwera |
| Live timing, wyniki JSON i panel WWW | Zaimplementowane; import wyników wymaga przykładowego pliku z serwera do walidacji |
| CSP Lua HUD + WSS | Kod i instalator paczki istnieją; wymaga testu wewnątrz gry/CSP na Windows |
| Flagi/SC/VSC | Dostarczane jako komunikaty i wskazówki HUD; nie zmieniają fizyki/ograniczeń auta |
| Planowanie zmian kierowców | Plan, stinty i alerty są obsługiwane; faktyczny driver swap zachowujący stan auta nie jest dostępny i nie jest symulowany |
| Replay VAR przez OBS | Worker, kolejka, upload, playback, retencja zaimplementowane; wymaga konfiguracji i testu OBS na maszynie obserwatora |
| Praca przez 24 h, restart recovery | Projekt ma trwałe SQLite/WAL i proces systemd; nie wykonano jeszcze próby 24 h na serwerze gry |

„Zaimplementowane” nie oznacza zweryfikowane w rzeczywistym wyścigu. Granice API klasycznej AC i CSP są opisane w [analizie technicznej](docs/TECHNICAL_ANALYSIS.md), [architekturze klienta](docs/CLIENT_ARCHITECTURE.md) i [instrukcji VAR/OBS](docs/REPLAY.md).

## Uruchomienie backendu

Python 3.10+; backend używa standardowej biblioteki Pythona. Dla istniejącego serwera ustaw ścieżki instalacji, a sekret GUID trzymaj poza repozytorium:

```sh
cd /path/to/ac-endurance-control
export ACEC_SERVER_ROOT=/path/to/assetto/serverfiles
export ACEC_LGSM=/path/to/assetto/acserver
export ACEC_GUID_PEPPER='długi-losowy-sekret'
python3 -m ac_endurance
```

Domyślnie HTTP działa wyłącznie na `127.0.0.1:8088`, UDP na `0.0.0.0:12001`, a klient WebSocket na `127.0.0.1:8089`. Baza: `var/endurance.sqlite3`. Ustawienia: `ACEC_HTTP_HOST`, `ACEC_HTTP_PORT`, `ACEC_UDP_HOST`, `ACEC_UDP_PORT`, `ACEC_WS_HOST`, `ACEC_WS_PORT`, `ACEC_DB`. W produkcji użyj TLS reverse proxy dla HTTP i WSS. Dostęp produkcyjny wymaga silnych haseł i sekretów z pliku środowiska poza repozytorium.

Utwórz administratora interaktywnie przez `python3 tools/create_user.py var/endurance.sqlite3 admin admin`; następnie dodaj zespoły/kierowców z panelu. GUID kierowcy jest hashowany przy zapisie. Wydanie tokenu klienta: `python3 tools/mint_client_token.py var/endurance.sqlite3 <driver-id>`.

## Instalacja moda CSP

Na komputerze gracza Windows z Content Manager i CSP 0.2.0+. Najprościej pobrać paczkę klienta ZIP z **Releases** na GitHubie, rozpakować ją i uruchomić `Install-ACEndurance.ps1` w PowerShell. Instalator wykrywa typową instalację Steam, pyta o adres WSS i token kierowcy oraz zachowuje poprzednią wersję aplikacji jako kopię. Szczegóły: [instalacja Windows](client/windows/README.md).

Do przygotowania paczki ZIP dla GitHub Release:

```sh
python3 tools/package_client.py
```

Plik wyjściowy `dist/AC-Endurance-Control-Client-v0.1.0.zip` zawiera wyłącznie klienta i instalator; nie ma w nim tokenu. GitHub Actions buduje tę paczkę po ręcznym uruchomieniu workflow **Build Windows client package** albo po wypchnięciu taga `client-v*`. Instrukcja publikacji: [docs/GITHUB_RELEASE.md](docs/GITHUB_RELEASE.md).

Instalacja ręczna przez Pythona nadal jest dostępna:

```sh
python3 tools/install_client.py "C:/Program Files (x86)/Steam/steamapps/common/assettocorsa" --url wss://race.example.org/ws/client --token <token>
```

W Content Manager włącz CSP i Lua Apps, potem uruchom `Endurance Control` z listy aplikacji na ekranie jazdy. Klient nie jest wymagany dla samego backendu. Szczegóły i ograniczenia: [docs/CLIENT_ARCHITECTURE.md](docs/CLIENT_ARCHITECTURE.md).

## Replay VAR przez OBS

OBS i jego Replay Buffer muszą działać na komputerze obserwatora z widokiem wyścigu. Konfiguracja oraz komendy uruchomienia workera znajdują się w [docs/REPLAY.md](docs/REPLAY.md). Backend nie generuje obrazu z serwera headless.

## Assetto Corsa Dedicated Server

Adapter odbiera UDP plugin events na `ACEC_UDP_PORT`. `UDP_PLUGIN_ADDRESS` wskazuje adres/port odbiorczy tej aplikacji; `UDP_PLUGIN_LOCAL_PORT` jest osobnym portem lokalnym serwera do odbioru poleceń pluginu i nie należy utożsamiać go z portem odbiornika. Przed integracją sprawdź oba pola oraz czy inny plugin, np. RaceControl/Real Penalty, nie używa tej ścieżki. Nie modyfikuj istniejącego `server_cfg.ini` w ciemno. Klasyczny serwer zwykle ma pojedynczy adres odbiorcy pluginu; współdzielenie wymaga przetestowanego relay/łańcuchowania. `AUTH_PLUGIN_ADDRESS` to osobny interfejs autoryzacji, nie telemetryka.

`tools/server_manager.py` pokazuje status/config/catalog, robi kopię konfiguracji i oferuje kontrolowany restart LinuxGSM z kopią zapasową oraz kontrolą istniejącego procesu. Restart nie jest końcem wydarzenia. Najpierw sprawdź `status`, wykonaj backup i używaj `restart --confirm` tylko podczas zatwierdzonego okna serwisowego. Usługa systemd jest w `deployment/acec.service`; dzienny backup bazy skonfigurowano w `deployment/acec-backup.service` i `deployment/acec-backup.timer` (włącz timer przez `systemctl enable --now acec-backup.timer`). Konfiguracja proxy WSS w `deployment/nginx-client-ws.conf`.

## Testy

```sh
PYTHONPATH=. python3 -m unittest discover -s tests -v
python3 -m compileall -q ac_endurance simulator tests tools replay_recorder
```

Obecne testy sprawdzają parser/datagramy, API i role, GUID redaction, deduplikację, import JSON, server manager oraz upload/odtwarzanie/retencję VAR. Nie zastępują testu na produkcyjnym binarnym serwerze, CSP ani OBS.

## Audyt integracyjny

Wyniki audytu wraz ze statusami, ograniczeniami i instrukcjami dalszych prób znajdują się w [docs/INTEGRATION_TEST_REPORT.md](docs/INTEGRATION_TEST_REPORT.md).
