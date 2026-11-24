# Replay Recorder / VAR

## Co działa

`replay_recorder/obs_agent.py` jest osobnym workerem do uruchomienia na komputerze obserwatora z OBS Studio. Loguje się kontem backendu, oczekuje na zgłoszenie VAR, odczekuje skonfigurowany czas po zdarzeniu, zapisuje OBS Replay Buffer, a potem przesyła klip do sprawy. Backend przechowuje plik w `ACEC_REPLAY_DIR` (domyślnie `var/replays`), pokazuje status w panelu VAR i udostępnia go sędziom z uwierzytelnieniem. Klipy starsze niż `ACEC_REPLAY_RETENTION_DAYS` (domyślnie 60) są usuwane przy okresowym przebiegu monitora.

Jest to zrzut obrazu z OBS na komputerze obserwatora, nie replay `.acreplay` generowany przez serwer headless. Serwer AC nie dostarcza gotowego wideo. Automatyczne skojarzenie wymaga, by obserwator miał aktywny właściwy widok wyścigu i działający bufor OBS w chwili incydentu. Współbieżne incydenty mogą otrzymać ten sam fragment bufora. Wideo należy oglądać jako dowód pomocniczy, nie automatyczną decyzję o winie.

## Instalacja obserwatora

1. W OBS włącz **Tools → WebSocket Server Settings**, ustaw silne hasło, pozostaw dostęp tylko dla hosta/LAN/VPN i nie publikuj portu 4455 w Internecie.
2. Włącz Replay Buffer, wybierz katalog zapisu i ustaw długość bufora obejmującą co najmniej czas przed i po incydencie. Zwykle 60–120 s. Zadbaj o miejsce i wydajność kodowania.
3. Utwórz konto `race_control` lub `steward` dla agenta (`tools/create_user.py`) i przygotuj środowisko Pythona na komputerze OBS.
4. Zainstaluj zależność `pip install -r replay_recorder/requirements.txt`, ustaw zmienne z `.env.example` w środowisku procesu i uruchom `python replay_recorder/obs_agent.py`.
5. Zapisuj OBS/WebSocket i backend tylko przez zaufaną sieć. Agent uwierzytelnia się HTTPS; ustaw `ACEC_API_URL` na publiczny adres TLS backendu.

`ACEC_REPLAY_POST_SECONDS` powinno być krótsze niż długość bufora OBS. Błąd OBS lub przekroczenie limitu klipu (250 MiB) oznacza sprawę `MISSED`. Panel VAR pozwala wtedy ręcznie dołączyć klip do sprawy. Rezerwacja zadania jest dzierżawiona na 10 minut, więc przerwany upload automatyczny może być ponowiony przez innego workera.

## API i granice

- Zgłoszenie incydentu tworzy wpis w kolejce nagrania. Oczekiwanie na `post_seconds` jest wykonywane przez worker.
- Claim zapobiega jednoczesnemu przejęciu przez dwóch obserwatorów. Backend weryfikuje, że upload wykonał użytkownik, który przejął zadanie.
- Upload przyjmuje MP4, MKV, MOV lub WebM do 250 MiB i używa pliku tymczasowego + atomowego rename.
- W przeglądarce klip jest strumieniowany z obsługą HTTP Range; kontrola dostępu wymaga roli sędziego/dyrekcji.
- Nie zrobiono automatycznego wykrywania kolizji na podstawie obrazu, synchronizacji wielokamerowej ani eksportu natywnego replay AC.

OBS WebSocket obsługuje `GetReplayBufferStatus`, `StartReplayBuffer`, `SaveReplayBuffer` oraz `GetLastReplayBufferReplay`; worker korzysta z tych poleceń przez `obsws-python`. Zob. [protokół obs-websocket](https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md?plain=1) oraz [obsws-python](https://pypi.org/project/obsws-python/).
