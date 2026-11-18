-- Use Termux's lua-language-server instead of Mason's.
-- Mason's prebuilt binary is not built for Android/Termux.
---@type LazySpec
return {
  "AstroNvim/astrolsp",
  ---@type AstroLSPOpts
  opts = function(_, opts)
    opts.servers = vim.list_extend(opts.servers or {}, { "lua_ls" })
  end,
}
