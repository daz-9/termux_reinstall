-- Use Termux's clangd (from the `clang` package) instead of Mason's.
-- Mason has no Android build of clangd ("The current platform is unsupported").
return {
  {
    "neovim/nvim-lspconfig",
    opts = { servers = { clangd = { mason = false } } },
  },
}
