# Instrukcje dla Codex

## Projekt

AC Endurance Control to system do obsługi wyścigów endurance w klasycznym Assetto Corsa Dedicated Server. Backend w Pythonie, panel WWW oraz aplikacja Lua dla CSP są rozwijane razem, ale klient gry komunikuje się z backendem przez WebSocket.

## Układ kodu

- `ac_endurance/` — backend, baza SQLite, API HTTP/WebSocket, adapter UDP i logika wyścigu.
- `frontend/` — panel WWW, dostarczany przez backend.
- `client/` — klient CSP Lua i instalator Windows.
- `replay_recorder/` — worker Replay Buffer dla OBS.
- `tools/` — administracja użytkownikami, tokenami, serwerem i paczką klienta.
- `deployment/` — przykładowe pliki usług i konfiguracji wdrożenia.
- `tests/` — testy jednostkowe i API.
- `docs/` — architektura, ograniczenia i procedury integracyjne.

## Zasady pracy

- Zachowuj zgodność z Pythonem 3.10+ i unikaj zależności w backendzie, jeśli standardowa biblioteka wystarcza.
- Traktuj API Assetto Corsa i CSP jako ograniczone interfejsy. Nie deklaruj obsługi funkcji, których gra lub serwer nie udostępnia; opisz ograniczenia w dokumentacji.
- Nie zapisuj sekretów, haseł, tokenów, GUID-ów, danych serwera, baz runtime ani nagrań w repozytorium. Używaj plików `.env.example` wyłącznie z przykładowymi wartościami.
- Nie zmieniaj konfiguracji działającego serwera ani nie uruchamiaj poleceń restartu w ramach prac nad kodem.
- Przy zmianie protokołu klienta aktualizuj backend, klienta oraz odpowiednią dokumentację.
- Zachowuj istniejący styl kodu i utrzymuj dokumentację po polsku.

## Przydatne polecenia

```sh
PYTHONPATH=. python3 -m unittest discover -s tests -v
python3 -m compileall -q ac_endurance simulator tests tools replay_recorder
python3 tools/package_client.py
```

Testy i kompilację uruchamiaj, gdy użytkownik poprosi o weryfikację albo gdy zmiana tego wymaga i jest to objęte zakresem zadania.
