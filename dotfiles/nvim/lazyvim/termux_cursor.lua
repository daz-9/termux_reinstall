-- Fix Termux italic glyph clipping (synthetic slant leans into the cursor cell)
-- and keep Normal (blinking block) vs Insert (vertical bar) clearly distinct.
vim.opt.guicursor = "n-v-c-sm:block-blinkwait300-blinkoff250-blinkon400,i-ci-ve:ver25,r-cr-o:hor20"
vim.api.nvim_create_autocmd({ "ColorScheme", "VimEnter" }, {
  desc = "Disable italic on comments so Termux doesn't clip glyphs at the cursor",
  callback = function()
    for _, group in ipairs({ "Comment", "@comment", "@comment.documentation", "SpecialComment" }) do
      local ok, hl = pcall(vim.api.nvim_get_hl, 0, { name = group, link = false })
      if ok and hl and (hl.italic or (hl.cterm and hl.cterm.italic)) then
        hl.italic = false
        if hl.cterm then hl.cterm.italic = false end
        vim.api.nvim_set_hl(0, group, hl)
      end
    end
  end,
})
return {}
