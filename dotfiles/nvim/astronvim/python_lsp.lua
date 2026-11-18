-- Use Termux's native basedpyright + ruff instead of Mason.
---@type LazySpec
return {
  "AstroNvim/astrolsp",
  ---@type AstroLSPOpts
  opts = function(_, opts)
    opts.servers = vim.list_extend(opts.servers or {}, { "basedpyright", "ruff" })
    opts.config = vim.tbl_deep_extend("force", opts.config or {}, {
      basedpyright = {
        settings = {
          basedpyright = {
            analysis = {
              typeCheckingMode = "standard",
            },
          },
        },
      },
    })
  end,
}
