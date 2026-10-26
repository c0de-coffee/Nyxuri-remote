--!nonstrict
-- Bar icon: slashed while RDP is off, with the number of open remote sessions next to it while
-- on; a click opens the remote login panel. The panel publishes changes it makes ("enabled" in
-- the plugin state), so the icon follows a toggle right away instead of at the next poll.

local grd = require("./grd.luau")

local POLL_MS = 15000

local enabled = nil -- nil until the first read
local sessions = 0

local function tooltip()
  local state = if enabled == nil
    then noctalia.tr("loading")
    elseif enabled then noctalia.tr("widget.on")
    else noctalia.tr("widget.off")
  local text = noctalia.tr("title") .. " · " .. state
  if enabled and sessions > 0 then
    text ..= "\n" .. noctalia.trp("widget.sessions", sessions, { count = sessions })
  end
  return text
end

-- Like the shell's own Bluetooth and night light widgets: the plain glyph while on (with the
-- number of remote sessions when there are any), the slashed one while off, both in the bar's
-- usual color.
local function render()
  barWidget.setGlyph(if enabled == false then "device-desktop-off" else "device-desktop-share")
  barWidget.setText(if enabled and sessions > 0 then tostring(sessions) else "")
  barWidget.setTooltip(tooltip())
end

local function poll()
  grd.readStatus(function(status)
    enabled = status.setUp and status.reachable and status.enabled == true
    render()
  end)
  grd.remoteSessions(function(count)
    sessions = count
    render()
  end)
end

function update()
  poll()
end

function onClick()
  noctalia.togglePanel("nyxuri/remote_login:panel")
end

noctalia.state.watch("enabled", function(value)
  if type(value) == "boolean" then
    enabled = value
    render()
  end
end)

render()
noctalia.setUpdateInterval(POLL_MS)
poll()
