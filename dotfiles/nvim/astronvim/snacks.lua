---@type LazySpec
return {
  "folke/snacks.nvim",
  opts = function(_, opts)
    local sample = {
      "-- Colorscheme Showcase: Lua Syntax & Highlights",
      "local M = {}",
      "",
      "---@class ThemeConfig",
      "---@field style string",
      "---@field transparent boolean",
      "local defaults = {",
      '  style = "night",',
      "  transparent = false,",
      "  styles = { comments = { italic = true }, keywords = { bold = true } },",
      "  max_items = 42,",
      "}",
      "",
      "---Compute a greeting and status summary",
      "---@param name string",
      "---@param count integer",
      "---@return string",
      "function M.greet(name, count)",
      "  if count <= 0 then",
      '    return string.format("Hello, %s! (no items)", name)',
      "  end",
      "  for i = 1, math.min(count, defaults.max_items) do",
      "    if i % 15 == 0 then",
      '      vim.notify("Milestone reached: " .. tostring(i), vim.log.levels.INFO)',
      "    end",
      "  end",
      '  return string.format("Welcome, %s (%d items)", name, count)',
      "end",
      "",
      "return M",
    }

    opts.picker = vim.tbl_deep_extend("force", opts.picker or {}, {
      sources = {
        colorschemes = {
          preview = function(ctx)
            if not ctx.preview.state.colorscheme then
              ctx.preview.state.colorscheme = vim.g.colors_name or "default"
              ctx.preview.state.background = vim.o.background
              ctx.preview.win:on("WinClosed", function()
                vim.schedule(function()
                  if not ctx.preview.state.colorscheme then return end
                  vim.cmd("colorscheme " .. ctx.preview.state.colorscheme)
                  vim.o.background = ctx.preview.state.background
                end)
              end, { win = true })
            end
            vim.schedule(function() vim.cmd("colorscheme " .. ctx.item.text) end)

            ctx.preview:reset()
            ctx.preview:set_title(ctx.item.text)
            ctx.preview:set_lines(sample)
            ctx.preview:highlight { ft = "lua" }
          end,
        },
      },
    })
  end,
}
