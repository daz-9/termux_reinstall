-- Use Termux's csharp-ls (installed via `dotnet tool install --global csharp-ls --version 0.16.0`)
-- instead of Mason's, since Mason's prebuilt binaries target glibc Linux.
---@type LazySpec
return {
  "AstroNvim/astrolsp",
  ---@type AstroLSPOpts
  opts = function(_, opts)
    opts.servers = vim.list_extend(opts.servers or {}, { "csharp_ls" })
    opts.config = vim.tbl_deep_extend("force", opts.config or {}, {
      csharp_ls = {
        cmd = { vim.fn.expand("~/.dotnet/tools/csharp-ls") },
        cmd_env = {
          DOTNET_ROOT = (vim.env.PREFIX or "/data/data/com.termux/files/usr") .. "/lib/dotnet",
          DOTNET_ROLL_FORWARD = "Major",
        },
      },
    })
  end,
}
