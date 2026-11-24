# Instalacja klienta Windows

Wymagane: Assetto Corsa na PC, Content Manager i CSP 0.2.0 lub nowszy z włączonym Lua Apps.

1. Pobierz i rozpakuj paczkę klienta z sekcji **Releases** projektu na GitHubie.
2. Wygeneruj osobny token kierowcy u administratora i uzyskaj adres `wss://.../ws/client`.
3. Kliknij pasek adresu folderu z rozpakowaną paczką, wpisz `powershell` i naciśnij Enter.
4. Uruchom instalator:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-ACEndurance.ps1
   ```

5. Podaj katalog Assetto Corsa, adres WSS i token kierowcy. Typowa ścieżka Steam zostanie wykryta automatycznie.
6. W Content Manager włącz CSP i Lua Apps. Uruchom sesję i wybierz **Endurance Control** z paska aplikacji.

Jeśli aplikacja była wcześniej zainstalowana, instalator zachowuje kopię w katalogu `ac_endurance_client.backup-...`. Token jest zapisany lokalnie w pliku Lua, więc nie wysyłaj tego pliku innym osobom. Unieważnij token w razie jego ujawnienia.

Instalator nie konfiguruje backendu ani serwera Assetto Corsa. Instalacja CSP i połączenie WSS wymagają testu w grze.
