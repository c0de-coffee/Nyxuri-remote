--!nonstrict
-- Control center tile: opens the remote login panel; lit while RDP is on.

local grd = require("./grd.luau")

local function render(enabled)
  shortcut.setLabel(noctalia.tr("title"))
  shortcut.setIcon(if enabled then "device-desktop-share" else "device-desktop-off")
  shortcut.setActive(enabled == true)
end

render(false)
grd.readStatus(function(status)
  render(status.reachable and status.enabled)
end)

-- The panel publishes what it changes, so the tile follows a toggle right away.
noctalia.state.watch("enabled", function(value)
  if type(value) == "boolean" then
    render(value)
  end
end)

function onClick()
  noctalia.togglePanel("nyxuri/remote_login:panel")
end
