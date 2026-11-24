-- AC Endurance Control HUD. Requires CSP Lua Apps (CSP 0.2.0+).
-- The token is a per-driver credential, never an administrator or server secret.
local SERVER_URL = 'wss://race.example.org/ws/client'
local CLIENT_TOKEN = 'SET_DRIVER_TOKEN'

local socket = nil
local connection = 'Rozłączono'
local sync = nil
local reconnectAt = 0
local reportNote = ''
local teamNote = ''
local lastLapCount = -1
local lastLapText = '—'
local wasInPitlane = nil
local notifiedSwap = nil
local pitSpeedWarned = false
local identityWarned = false
local PIT_SPEED_LIMIT_KMH = 80

local function connect()
  if CLIENT_TOKEN == 'SET_DRIVER_TOKEN' or CLIENT_TOKEN == '' then
    connection = 'Ustaw token kierowcy w pliku aplikacji'
    return
  end
  connection = 'Łączenie…'
  socket = web.socket(SERVER_URL, { Authorization = 'Bearer ' .. CLIENT_TOKEN }, function(data)
    if type(data) == 'table' and data.type == 'sync' then
      sync = data
      connection = 'Połączono'
    elseif type(data) == 'table' and data.type == 'incident_ack' then
      ui.toast(ui.Icons.Confirm, 'Zgłoszenie wysłane do dyrekcji')
    end
  end, { encoding = 'json', reconnect = true,
    onError = function(err) connection = 'Błąd połączenia: ' .. tostring(err) end,
    onClose = function() connection = 'Ponowne łączenie…' end })
end

function script.update(dt)
  if not socket and os.clock() >= reconnectAt then
    reconnectAt = os.clock() + 5
    connect()
  end
  local car = ac.getCar(0)
  if car and car.isInPitlane and car.speedKmh and car.speedKmh > PIT_SPEED_LIMIT_KMH and not pitSpeedWarned then
    pitSpeedWarned = true
    ui.toast(ui.Icons.Warning, string.format('Limit pit lane: %.0f km/h', PIT_SPEED_LIMIT_KMH))
  elseif not car or not car.isInPitlane or (car.speedKmh or 0) <= PIT_SPEED_LIMIT_KMH then
    pitSpeedWarned = false
  end
  if car and sync and sync.driver and sync.driver.nickname and car:driverName() and not identityWarned then
    local gameName = string.lower((car:driverName():gsub('^%s*(.-)%s*$', '%1')))
    local assignedName = string.lower((sync.driver.nickname:gsub('^%s*(.-)%s*$', '%1')))
    if gameName ~= assignedName then
      identityWarned = true
      ui.toast(ui.Icons.Warning, 'Nazwa w grze różni się od kierowcy przypisanego przez organizatora')
    end
  end
  if sync and sync.next_swap and sync.next_swap.scheduled_at then
    local seconds = sync.next_swap.scheduled_at - (sync.server_time or os.time())
    if seconds > 0 and seconds <= 900 and notifiedSwap ~= sync.next_swap.scheduled_at then
      notifiedSwap = sync.next_swap.scheduled_at
      ui.toast(ui.Icons.Warning, 'Zmiana kierowcy za około 15 minut')
    end
  end
  if car then
    if car.lapCount ~= lastLapCount then
      if lastLapCount >= 0 and car.lastLapTimeMs and car.lastLapTimeMs > 0 then
        lastLapText = string.format('%d:%06.3f', math.floor(car.lastLapTimeMs / 60000), (car.lastLapTimeMs % 60000) / 1000)
      end
      lastLapCount = car.lapCount
    end
    local inPit = car.isInPitlane == true
    if wasInPitlane ~= nil and inPit ~= wasInPitlane and socket then
      socket({type='pit_transition', entering=inPit, telemetry={lap=car.lapCount, speed_kmh=car.speedKmh, spline=car.splinePosition}})
    end
    wasInPitlane = inPit
  end
end

local function fmt(ms)
  if not ms or ms <= 0 then return '—' end
  return string.format('%d:%06.3f', math.floor(ms / 60000), (ms % 60000) / 1000)
end

function script.windowMain()
  local car = ac.getCar(0)
  local race = sync and sync.race or {}
  local driver = sync and sync.driver or {}
  ui.text('AC ENDURANCE CONTROL')
  ui.sameLine()
  ui.text(connection)
  ui.separator()
  ui.text('WYŚCIG')
  ui.text(tostring(race.name or race.status or 'Oczekiwanie na synchronizację'))
  ui.text('Flaga: ' .. tostring(race.flag or '—'))
  if race.message and race.message ~= '' then ui.textWrapped(tostring(race.message)) end
  ui.separator()
  ui.text('ZESPÓŁ  ' .. tostring(driver.team or 'Nieprzypisany'))
  ui.text('KIEROWCA  ' .. tostring(driver.nickname or (car and car:driverName()) or '—'))
  if car and car.isInPitlane then ui.text(string.format('Limit pit lane: %.0f km/h%s', PIT_SPEED_LIMIT_KMH, (car.speedKmh or 0)>PIT_SPEED_LIMIT_KMH and ' · PRZEKROCZONY' or '')) end
  if driver.car_number then ui.text('AUTO  #' .. tostring(driver.car_number) .. '  ' .. tostring(driver.car_model or '')) end
  ui.separator()
  if car then
    ui.text(string.format('Pozycja  P%d     Okrążenie  %d', car.racePosition or 0, car.lapCount or 0))
    ui.text(string.format('Prędkość  %.0f km/h     Tor  %.1f%%', car.speedKmh or 0, (car.splinePosition or 0) * 100))
    ui.text('Ostatnie okrążenie  ' .. lastLapText .. '     Najlepsze  ' .. fmt(car.bestLapTimeMs))
    if car.isInPitlane then ui.text('W PIT LANE') end
  else
    ui.text('Dane auta będą dostępne po dołączeniu do sesji.')
  end
  if sync and sync.next_swap then
    ui.text('NASTĘPNA ZMIANA  ' .. tostring(sync.next_swap.nickname))
    ui.text('Plan  ' .. os.date('%H:%M:%S', sync.next_swap.scheduled_at))
  end
  if sync and sync.stint then
    local elapsed = math.max(0, (sync.server_time or os.time()) - sync.stint.started_at)
    ui.text(string.format('Czas jazdy w stincie  %02d:%02d', math.floor(elapsed / 3600), math.floor(elapsed / 60) % 60))
  end
  if sync and sync.penalties and #sync.penalties > 0 then
    for _, p in ipairs(sync.penalties) do ui.textWrapped('KARA ' .. tostring(p.kind) .. ': ' .. tostring(p.reason)) end
  end
  if sync and sync.messages and sync.messages[1] then ui.textWrapped('DYREKCJA  ' .. tostring(sync.messages[1].body)) end
  if sync and sync.messages and #sync.messages > 1 then
    ui.textWrapped(tostring(sync.messages[2].author or 'Zespół') .. ': ' .. tostring(sync.messages[2].body))
  end
  ui.separator()
  teamNote = ui.inputText('Wiadomość do zespołu', teamNote)
  if ui.button('Wyślij do zespołu') and socket and teamNote ~= '' then
    socket({type='team_message', body=teamNote})
    teamNote = ''
  end
  ui.sameLine()
  if ui.button('Zgłoś incydent') and socket and car then
    socket({ type='incident_report', category='driver_report', note=reportNote,
      telemetry={ lap=car.lapCount, spline=car.splinePosition, speed_kmh=car.speedKmh,
        race_position=car.racePosition, in_pitlane=car.isInPitlane, game_time=ac.getSim().gameTime } })
  end
  ui.sameLine()
  ui.text('Zgłoszenie trafia do sędziów, nie nakłada kary.')
end
