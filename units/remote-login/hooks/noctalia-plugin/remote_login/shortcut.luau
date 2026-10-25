--!nonstrict
-- Control center tile: opens the remote login panel; lit while RDP is on.

local grd = require("./grd.luau")

local function render(enabled)
  shortcut.setLabel(noctalia.tr("title"))
  shortcut.setIcon("screen-share")
  shortcut.setActive(enabled == true)
end

render(false)
grd.readStatus(function(status)
  render(status.reachable and status.enabled)
end)

function onClick()
  noctalia.togglePanel("nyxuri/remote_login:panel")
end
