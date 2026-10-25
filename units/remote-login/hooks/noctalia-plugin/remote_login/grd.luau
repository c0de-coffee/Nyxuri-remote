--!nonstrict
-- gnome-remote-desktop's system daemon, through its configuration service on the system bus
-- (org.gnome.RemoteDesktop.Configuration, the one GNOME Settings uses). Reading properties is
-- open to everyone; methods ask polkit (org.gnome.remotedesktop.configure-system-daemon), so
-- Noctalia's polkit agent shows a password prompt. Every command is an argument array.

local M = {}

local DEST = "org.gnome.RemoteDesktop.Configuration"
local PATH = "/org/gnome/RemoteDesktop/Configuration"
local IFACE = "org.gnome.RemoteDesktop.Configuration.Rdp.Server"

-- runAsync gives up after 5 s by default; a call waiting on the polkit prompt needs the user's
-- time (the host caps it at 60 s).
local AUTH_TIMEOUT_MS = 60000

local function busctl(args)
  local argv = { "busctl", "--system", "--json=short" }
  for _, arg in args do
    table.insert(argv, arg)
  end
  return argv
end

local function decodeLines(stdout)
  local values = {}
  for line in string.gmatch(stdout or "", "[^\n]+") do
    local value = noctalia.json.decode(line)
    if type(value) == "table" then
      table.insert(values, value.data)
    end
  end
  return values
end

-- Turns a failed call into a short reason for the panel.
local function failure(result)
  if result.timedOut then
    return "timeout"
  end
  local err = result.stderr or ""
  if string.find(err, "Access denied", 1, true) or string.find(err, "Not authorized", 1, true) then
    return "denied"
  end
  return "failed"
end

-- cb(status): { setUp, enabled, port, fingerprint } or nil when grd isn't reachable.
-- setUp: remote-dm (the display manager for remote logins) is enabled, i.e. the Nyxuri
-- remote-login unit did its part.
function M.readStatus(cb)
  local status = { setUp = false }
  local pending = 2

  local function done()
    pending -= 1
    if pending == 0 then
      cb(status)
    end
  end

  noctalia.runAsync({ "systemctl", "is-enabled", "--quiet", "remote-dm.service" }, function(result)
    status.setUp = result.exitCode == 0
    done()
  end)

  noctalia.runAsync(busctl({ "get-property", DEST, PATH, IFACE, "Enabled", "Port", "TlsFingerprint" }), function(result)
    if result.exitCode == 0 then
      local values = decodeLines(result.stdout)
      status.reachable = #values == 3
      status.enabled = values[1] == true
      status.port = values[2]
      status.fingerprint = values[3]
    end
    done()
  end)
end

-- cb(ok, reason)
function M.setEnabled(enabled, cb)
  local method = if enabled then "Enable" else "Disable"
  noctalia.runAsync(busctl({ "call", DEST, PATH, IFACE, method }), function(result)
    cb(result.exitCode == 0, failure(result))
  end, AUTH_TIMEOUT_MS)
end

-- cb(username, password) on success, cb(nil, reason) otherwise.
function M.getCredentials(cb)
  noctalia.runAsync(busctl({ "call", DEST, PATH, IFACE, "GetCredentials" }), function(result)
    if result.exitCode ~= 0 then
      cb(nil, failure(result))
      return
    end
    local values = decodeLines(result.stdout)
    local dict = values[1] and values[1][1]
    if type(dict) ~= "table" then
      cb(nil, "failed")
      return
    end
    local function field(name)
      local entry = dict[name]
      return if type(entry) == "table" and type(entry.data) == "string" then entry.data else ""
    end
    cb(field("username"), field("password"))
  end, AUTH_TIMEOUT_MS)
end

-- An empty password keeps the current one. cb(ok, reason)
--
-- busctl takes the values as arguments, so the password is in its command line for the moment
-- the call takes; the configuration service offers no other way in.
function M.setCredentials(username, password, cb)
  local args = { "call", DEST, PATH, IFACE, "SetCredentials", "a{sv}" }
  if password == "" then
    for _, arg in { "1", "username", "s", username } do
      table.insert(args, arg)
    end
  else
    for _, arg in { "2", "username", "s", username, "password", "s", password } do
      table.insert(args, arg)
    end
  end
  noctalia.runAsync(busctl(args), function(result)
    cb(result.exitCode == 0, failure(result))
  end, AUTH_TIMEOUT_MS)
end

function M.hostname()
  local content = noctalia.readFile("/etc/hostname")
  local name = if content then noctalia.string.trim(content) else ""
  return if name ~= "" then name else "localhost"
end

return M
