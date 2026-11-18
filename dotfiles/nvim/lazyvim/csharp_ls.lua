-- Use Termux's csharp-ls (installed via `dotnet tool install --global csharp-ls --version 0.16.0`)
-- instead of Mason's, since Mason's prebuilt binaries target glibc Linux.
return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        csharp_ls = {
          mason = false,
          cmd = { vim.fn.expand("~/.dotnet/tools/csharp-ls") },
          cmd_env = {
            DOTNET_ROOT = (vim.env.PREFIX or "/data/data/com.termux/files/usr") .. "/lib/dotnet",
            DOTNET_ROLL_FORWARD = "Major",
          },
        },
      },
    },
  },
}
