-- Vaagdevi live preview for Neovim in iTerm2.
--
-- Write Sanskrit in Baraha in nvim (aqgnimI#LE puqrOhi#taM) and see it in
-- Vaagdevi in an iTerm2 pane beside you, updating as you type. The preview
-- runs outside nvim because nvim counts ि ा ी ो as zero-width while iTerm2
-- gives each a cell, so Devanagari drawn by nvim itself lands in the wrong
-- columns.
--
--   :Vaagdevi        open or close the preview pane      (<leader>vv)
--   :VaagdeviSvara   svara colours on or off in the pane  (<leader>vs)
--   :VaagdeviConvert turn the buffer (or the selected lines) from Baraha
--                    into Devanagari
--
-- Buffers that already contain Devanagari are shown as they are; anything
-- else is read as Baraha. Options (set before the plugin loads):
--   vim.g.vaagdevi_profile        = "Vaagdevi"         -- pane profile
--   vim.g.vaagdevi_svara_profile  = "Vaagdevi Svara"   -- profile with colours
--   vim.g.vaagdevi_no_mappings    = true               -- skip <leader>vv/vs

if vim.g.loaded_vaagdevi then
  return
end
vim.g.loaded_vaagdevi = true

local here = debug.getinfo(1, "S").source:sub(2)
local root = vim.fn.fnamemodify(here, ":p:h:h:h")   -- nvim/plugin/x.lua → root

local uv = vim.uv or vim.loop   -- vim.uv is Neovim 0.10+
local preview = nil   -- { tmp = path, pane = iTerm2 session id, svara = bool }
local timer = nil

local function skt_path()
  if vim.g.vaagdevi_skt then
    return vim.g.vaagdevi_skt
  end
  for _, p in ipairs({ root .. "/skt.py", root .. "/shell/skt.py" }) do
    if vim.fn.filereadable(p) == 1 then
      return p
    end
  end
end

local function applescript_str(s)
  return '"' .. s:gsub("\\", "\\\\"):gsub('"', '\\"') .. '"'
end

local function osascript(script)
  local out = vim.fn.system({ "osascript", "-e", script })
  if vim.v.shell_error ~= 0 then
    return nil, vim.trim(out)
  end
  return vim.trim(out)
end

-- The iTerm2 session running this nvim: ITERM_SESSION_ID is "w0t0p0:<uuid>".
local function own_session()
  local id = vim.env.ITERM_SESSION_ID
  return id and id:match(":(.+)$")
end

local function find_session(id)
  return ([[
    repeat with w in windows
      repeat with t in tabs of w
        repeat with s in sessions of t
          if id of s is %s then
            set found to s
          end if
        end repeat
      end repeat
    end repeat]]):format(applescript_str(id))
end

local function write_now()
  if not preview then
    return
  end
  local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  vim.fn.writefile(lines, preview.tmp)
  vim.fn.writefile({ vim.json.encode({
    cursor = vim.api.nvim_win_get_cursor(0)[1],
    svara = preview.svara,
    profile = vim.g.vaagdevi_profile or "Vaagdevi",
    svara_profile = vim.g.vaagdevi_svara_profile or "Vaagdevi Svara",
  }) }, preview.tmp .. ".state")
end

-- Writing on every keystroke is cheap, but batch bursts of typing anyway.
local function write_soon()
  if not preview then
    return
  end
  timer = timer or uv.new_timer()
  timer:stop()
  timer:start(60, 0, vim.schedule_wrap(write_now))
end

local function close()
  if not preview then
    return
  end
  local p = preview
  preview = nil
  if p.pane then
    osascript(([[tell application "iTerm2"
      set found to missing value
      %s
      if found is not missing value then close found
    end tell]]):format(find_session(p.pane)))
  end
  os.remove(p.tmp)            -- the preview also exits by itself once this is gone
  os.remove(p.tmp .. ".state")
  os.remove(p.tmp .. ".sh")
  pcall(vim.api.nvim_del_augroup_by_name, "Vaagdevi")
end

local function open()
  local skt, me = skt_path(), own_session()
  if not skt then
    return vim.notify("Vaagdevi: can't find skt.py (set vim.g.vaagdevi_skt)", vim.log.levels.ERROR)
  end
  if not me then
    return vim.notify("Vaagdevi: the preview needs nvim running in iTerm2", vim.log.levels.ERROR)
  end
  local tmp = vim.fn.tempname()
  preview = { tmp = tmp, svara = false }
  write_now()

  -- A launcher script keeps the AppleScript free of shell quoting.
  local launcher = tmp .. ".sh"
  vim.fn.writefile({
    "#!/bin/sh",
    ("exec python3 -I %s --watch %s"):format(vim.fn.shellescape(skt), vim.fn.shellescape(tmp)),
  }, launcher)
  vim.fn.setfperm(launcher, "rwx------")

  local pane, err = osascript(([[tell application "iTerm2"
    set found to missing value
    %s
    if found is missing value then error "this nvim's iTerm2 session wasn't found"
    tell found
      set p to (split vertically with profile %s command %s)
    end tell
    select found
    return id of p
  end tell]]):format(find_session(me), applescript_str(vim.g.vaagdevi_profile or "Vaagdevi"),
    applescript_str(launcher)))
  if not pane then
    preview = nil
    return vim.notify("Vaagdevi: couldn't open the preview pane: " .. (err or ""), vim.log.levels.ERROR)
  end
  preview.pane = pane

  local group = vim.api.nvim_create_augroup("Vaagdevi", { clear = true })
  vim.api.nvim_create_autocmd({ "TextChanged", "TextChangedI", "CursorMoved", "CursorMovedI", "BufEnter" },
    { group = group, callback = write_soon })
  vim.api.nvim_create_autocmd("VimLeavePre", { group = group, callback = close })
end

local function toggle()
  if preview then
    close()
  else
    open()
  end
end

local function toggle_svara()
  if not preview then
    return vim.notify("Vaagdevi: open the preview first (:Vaagdevi)", vim.log.levels.WARN)
  end
  preview.svara = not preview.svara
  write_now()
end

local function convert(opts)
  local skt = skt_path()
  if not skt then
    return vim.notify("Vaagdevi: can't find skt.py (set vim.g.vaagdevi_skt)", vim.log.levels.ERROR)
  end
  local lines = vim.api.nvim_buf_get_lines(0, opts.line1 - 1, opts.line2, false)
  local out = vim.fn.systemlist({ "python3", "-I", skt }, lines)
  if vim.v.shell_error ~= 0 then
    return vim.notify("Vaagdevi: " .. table.concat(out, "\n"), vim.log.levels.ERROR)
  end
  vim.api.nvim_buf_set_lines(0, opts.line1 - 1, opts.line2, false, out)
end

vim.api.nvim_create_user_command("Vaagdevi", toggle, { desc = "Toggle the Vaagdevi preview pane" })
vim.api.nvim_create_user_command("VaagdeviConvert", convert,
  { range = "%", desc = "Baraha to Devanagari for the buffer or the selected lines" })
vim.api.nvim_create_user_command("VaagdeviSvara", toggle_svara, { desc = "Toggle svara colours in the preview" })

if not vim.g.vaagdevi_no_mappings then
  for lhs, rhs in pairs({ ["<leader>vv"] = "<cmd>Vaagdevi<cr>", ["<leader>vs"] = "<cmd>VaagdeviSvara<cr>" }) do
    if vim.fn.maparg(lhs, "n") == "" then
      vim.keymap.set("n", lhs, rhs, { desc = "Vaagdevi" })
    end
  end
end
