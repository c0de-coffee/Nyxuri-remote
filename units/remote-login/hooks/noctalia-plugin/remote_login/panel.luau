--!nonstrict
-- Remote login settings, like GNOME's: turn RDP on or off, how to connect (address,
-- certificate fingerprint), and the RDP sign-in that clients pass before the login screen.

local grd = require("./grd.luau")

local status = nil -- nil while loading
local busy = false
local message = ""
local messageIsError = false

local username = ""
local password = ""
local revealPassword = false
local fieldsKey = 0 -- bumped to reset the inputs to username/password

-- The polkit prompt is a panel too, and the shell shows one panel at a time: asking for a
-- password closes this one. When the answer comes back, reopen it with the result.
local isOpen = false
local reopening = false

local function setMessage(text, isError)
  message = text
  messageIsError = isError == true
end

local function reasonText(reason)
  if reason == "denied" then
    return noctalia.tr("error.denied")
  elseif reason == "timeout" then
    return noctalia.tr("error.timeout")
  end
  return noctalia.tr("error.failed")
end

local function polkitAgentOff()
  return noctalia.getSetting("shell.polkit_agent") == false
end

local function caption(text)
  return ui.label({ text = text, color = "on_surface_variant", fontSize = 12 })
end

local function infoRow(label, value, onCopy, small)
  return ui.row({ gap = 8, align = "center" }, {
    -- A fixed-width lane, so the values line up.
    ui.row({ width = 96 }, { ui.label({ text = label, color = "on_surface_variant" }) }),
    ui.label({ text = value, maxLines = 3, fontSize = if small then 12 else nil, flexGrow = 1 }),
    ui.button({ glyph = "copy", variant = "ghost", controlSize = "sm", tooltip = noctalia.tr("copy"), onClick = onCopy }),
  })
end

local function header()
  local canToggle = status ~= nil and status.setUp and status.reachable and not busy
  return ui.row({ gap = 12, align = "center" }, {
    ui.glyph({ name = "screen-share", size = 26, color = "primary" }),
    ui.column({ gap = 2, flexGrow = 1 }, {
      ui.label({ text = noctalia.tr("title"), fontSize = 16, fontWeight = "semibold" }),
      caption(noctalia.tr("subtitle")),
    }),
    ui.toggle({
      checked = status ~= nil and status.setUp and status.reachable and status.enabled == true,
      enabled = canToggle,
      onChange = "onToggle",
    }),
  })
end

local function notSetUp()
  return ui.column({ gap = 10, align = "stretch" }, {
    ui.label({ text = noctalia.tr("setup.text"), maxLines = 4 }),
    ui.row({ gap = 8 }, {
      ui.button({ text = noctalia.tr("setup.button"), glyph = "terminal-2", variant = "primary", onClick = "onSetUp" }),
      ui.button({ text = noctalia.tr("refresh"), glyph = "refresh", variant = "ghost", onClick = "onRefresh" }),
    }),
  })
end

local function settings()
  local address = grd.hostname() .. ":" .. tostring(status.port)
  local children = {}
  if polkitAgentOff() then
    table.insert(children, ui.row({ gap = 8, align = "center" }, {
      ui.glyph({ name = "alert-triangle", size = 16, color = "error" }),
      ui.label({ text = noctalia.tr("agent_off"), color = "error", fontSize = 12, maxLines = 3, flexGrow = 1 }),
    }))
  end
  for _, child in {
    ui.column({ gap = 8, align = "stretch" }, {
      ui.label({ text = noctalia.tr("connect.title"), fontWeight = "medium" }),
      infoRow(noctalia.tr("connect.address"), address, "onCopyAddress"),
      infoRow(noctalia.tr("connect.fingerprint"), status.fingerprint or "", "onCopyFingerprint", true),
      caption(noctalia.tr("connect.fingerprint_hint")),
    }),
    ui.separator({}),
    ui.column({ gap = 8, align = "stretch" }, {
      ui.label({ text = noctalia.tr("signin.title"), fontWeight = "medium" }),
      caption(noctalia.tr("signin.hint")),
      ui.input({
        key = "user_" .. tostring(fieldsKey),
        value = username,
        placeholder = noctalia.tr("signin.username"),
        enabled = not busy,
        onChange = "onUsernameChange",
      }),
      ui.row({ gap = 8, align = "center" }, {
        ui.input({
          key = "pass_" .. tostring(fieldsKey) .. (if revealPassword then "_shown" else ""),
          value = password,
          placeholder = noctalia.tr("signin.password_unchanged"),
          password = not revealPassword,
          enabled = not busy,
          flexGrow = 1,
          onChange = "onPasswordChange",
          submitOnEnter = true,
          onSubmit = "onSave",
        }),
        ui.button({
          glyph = if revealPassword then "eye-off" else "eye",
          variant = "ghost",
          controlSize = "sm",
          tooltip = noctalia.tr("signin.reveal"),
          onClick = "onReveal",
        }),
      }),
      ui.row({ gap = 8 }, {
        ui.button({ text = noctalia.tr("signin.load"), glyph = "key", variant = "ghost", enabled = not busy, onClick = "onLoad" }),
        ui.spacer({ flexGrow = 1 }),
        ui.button({ text = noctalia.tr("signin.save"), variant = "primary", enabled = not busy, onClick = "onSave" }),
      }),
    }),
  } do
    table.insert(children, child)
  end
  return ui.column({ gap = 14, align = "stretch" }, children)
end

function render()
  local body
  if status == nil then
    body = caption(noctalia.tr("loading"))
  elseif not status.setUp or not status.reachable then
    body = notSetUp()
  else
    body = settings()
  end

  local children = { header(), ui.separator({}), body }
  if message ~= "" then
    table.insert(children, ui.label({
      text = message,
      color = if messageIsError then "error" else "on_surface_variant",
      maxLines = 3,
    }))
  end
  panel.render(ui.column({ gap = 14, align = "stretch" }, children))
end

local function refresh()
  grd.readStatus(function(result)
    status = result
    if isOpen then
      render()
    end
  end)
end

-- After an authorized call: show the outcome, reopening the panel the prompt closed.
local function finish()
  if isOpen then
    render()
    refresh()
  else
    reopening = true
    noctalia.togglePanel("nyxuri/remote_login:panel")
  end
end

function onOpen(_context)
  isOpen = true
  if reopening then
    reopening = false
    render()
    refresh()
    return
  end
  status = nil
  busy = false
  setMessage("")
  username = ""
  password = ""
  revealPassword = false
  fieldsKey += 1
  render()
  refresh()
end

function onClose()
  isOpen = false
  if busy then
    -- Closed by the polkit prompt; the call is still going.
    return
  end
  -- Don't keep what was typed or loaded around.
  username = ""
  password = ""
  revealPassword = false
  fieldsKey += 1
end

function onRefresh()
  status = nil
  render()
  refresh()
end

function onSetUp()
  noctalia.runInTerminal("nyxuri on remote-login")
  setMessage(noctalia.tr("setup.started"))
  render()
end

function onToggle(value)
  local enable = value == "true"
  busy = true
  setMessage(noctalia.tr("waiting"))
  render()
  grd.setEnabled(enable, function(ok, reason)
    busy = false
    setMessage(if ok then "" else reasonText(reason), not ok)
    finish()
  end)
end

function onCopyAddress()
  noctalia.copyToClipboard(grd.hostname() .. ":" .. tostring(status.port), "text/plain")
  setMessage(noctalia.tr("copied"))
  render()
end

function onCopyFingerprint()
  noctalia.copyToClipboard(status.fingerprint or "", "text/plain")
  setMessage(noctalia.tr("copied"))
  render()
end

function onUsernameChange(value)
  username = if type(value) == "string" then value else ""
end

function onPasswordChange(value)
  password = if type(value) == "string" then value else ""
end

function onReveal()
  revealPassword = not revealPassword
  render()
end

function onLoad()
  busy = true
  setMessage(noctalia.tr("waiting"))
  render()
  grd.getCredentials(function(user, pass)
    busy = false
    if user == nil then
      setMessage(reasonText(pass), true)
    else
      username = user
      password = pass
      fieldsKey += 1
      setMessage("")
    end
    finish()
  end)
end

function onSave()
  local user = noctalia.string.trim(username)
  if user == "" then
    setMessage(noctalia.tr("error.username_required"), true)
    render()
    return
  end
  busy = true
  setMessage(noctalia.tr("waiting"))
  render()
  grd.setCredentials(user, password, function(ok, reason)
    busy = false
    if ok then
      password = ""
      fieldsKey += 1
      setMessage(noctalia.tr("signin.saved"))
    else
      setMessage(reasonText(reason), true)
    end
    finish()
  end)
end
