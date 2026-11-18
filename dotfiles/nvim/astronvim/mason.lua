-- Disable automatic Mason tool installation on Termux/Android,
-- since Mason's prebuilt glibc binaries are unsupported here.
---@type LazySpec
return {
  {
    "WhoIsSethDaniel/mason-tool-installer.nvim",
    opts = {
      run_on_start = false,
      auto_update = false,
    },
  },
}
