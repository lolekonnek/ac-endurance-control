# Publikowanie paczki klienta na GitHubie

## Przed udostępnieniem repozytorium

1. Przejrzyj repozytorium pod kątem danych serwera, haseł, tokenów, GUID-ów, bazy SQLite, kopii zapasowych i nagrań. `.gitignore` wyklucza typowe dane lokalne, ale nie usuwa plików już śledzonych przez Git.
2. Ustal właściciela praw i wybierz licencję dla kodu. W repozytorium nie dodano pliku `LICENSE`, bo licencji nie należy wybierać bez decyzji właściciela projektu.
3. W README ustaw właściwy adres GitHub i domenę przykładową. Nie publikuj produkcyjnych ścieżek, sekretów z plików środowiskowych ani tokenu kierowcy.
4. Zmień wersję aplikacji w `client/csp/ac_endurance_client/manifest.ini` i wersję `VERSION` w `tools/package_client.py`, jeśli robisz nowe wydanie.

## Ręczne zbudowanie paczki

```sh
python3 tools/package_client.py
```

Domyślna paczka trafia do `dist/AC-Endurance-Control-Client-v0.1.0.zip`. Sprawdź zawartość przed publikacją:

```sh
python3 -m zipfile -l dist/AC-Endurance-Control-Client-v0.1.0.zip
```

ZIP powinien zawierać `Install-ACEndurance.ps1`, `README.md`, `manifest.ini` i szablon Lua z `SET_DRIVER_TOKEN`; nie powinien zawierać tokenu ani danych backendu.

## GitHub Actions i Release

Workflow **Build Windows client package** można uruchomić ręcznie w Actions. Dołącza ZIP jako artifact. Alternatywnie wypchnięcie taga `client-v0.1.0` uruchomi to samo budowanie. Pobierz artifact, sprawdź zawartość i dołącz go ręcznie do GitHub Release `client-v0.1.0`, wpisując link do instrukcji Windows. Workflow nie publikuje automatycznie Release.

Przed ogłoszeniem wydania wykonaj instalację na Windows, uruchom Assetto Corsa z CSP i zanotuj wersje gry/CSP. Sama kompilacja ZIP nie potwierdza działania aplikacji w grze.
