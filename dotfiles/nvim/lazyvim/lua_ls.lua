-- Use Termux's lua-language-server instead of Mason's.
-- Mason's prebuilt binary is not built for Android/Termux.
return {
  {
    "neovim/nvim-lspconfig",
    opts = { servers = { lua_ls = { mason = false } } },
  },
}
