# 📱 termux_reinstall

> Personal quick Termux config for my CS class.

> [!CAUTION]
> **Not ready to be used yet.** Expect rough edges.

Turns a fresh Termux install into a **C/C++ dev environment** (with Python, C#, and Lua LSP support) and an opinionated **TUI setup**: zsh, Neovim, tmux, and a Nerd Font.

---

## 🚀 Install

Paste this into a fresh Termux session:

```sh
pkg update && pkg upgrade -y && pkg install git jp2a python-pip wget -y && git clone https://github.com/daz-9/termux_reinstall && cd termux_reinstall && python3 main.py
```

Use <kbd>Space</kbd> to select items in the menus and <kbd>Enter</kbd> to confirm.

---

## 🧰 What it does

### Setup

Installs the packages:

| Category | Packages |
|----------|----------|
| C toolchain | `clang`, `lldb`, `gdb`, `make`, `bear`, `xmake` (with custom `br`, `san`, `dbg` plugins & `clangd` templates) |
| Editor | `neovim`, `lua55`, `luarocks`, `lua-language-server`, `dotnet-sdk-9.0` + `csharp-ls`, `nodejs` + `basedpyright`, `ruff`, `ripgrep`, `fd`, `fzf`, `lazygit` |
| Shell & CLI | `zsh`, `starship`, `git`, `zip`, `eza`, `yazi`, `zoxide`, `bat`, `tmux`, `man`, `manpages`, `fastfetch`, `termux-api` |
| GitHub | `openssh`, `gh` |

Then sets **zsh** as the default shell (only if zsh actually installed).

If a step fails, the script prints why, carries on, and lists every failed step at the end.

### Configure

| Option | What it does |
|--------|--------------|
| **Zsh** | Installs [Oh My Zsh](https://ohmyz.sh/), `zsh-autosuggestions` + `zsh-syntax-highlighting` (plus `git`, `colored-man-pages`), wires up `zoxide`/`fzf`/`bat`/`fastfetch` (skipped inside `tmux`/Neovim), sets `.NET` env (`~/.dotnet/tools`, `DOTNET_ROOT`, `DOTNET_ROLL_FORWARD=Major`), configures [Starship](https://starship.rs/) (`~/.config/starship.toml`, with `xmake` & C support), and adds aliases |
| **Neovim** | Installs [AstroNvim](https://astronvim.com/) *(recommended)* or [LazyVim](https://www.lazyvim.org/). Existing configs are backed up to `*.bak`. Uses Termux's native `clangd`, `lua-language-server`, `csharp-ls`, `basedpyright`, and `ruff` instead of Mason ([clangd#1944](https://github.com/clangd/clangd/issues/1944)) |
| **Font** | Installs JetBrainsMono Nerd Font (`~/.termux/font.ttf`) and Catppuccin Mocha terminal colors (`~/.termux/colors.properties`) |
| **Tmux** | Writes `~/.tmux.conf` (Catppuccin Mocha bar, mouse support, `Ctrl-a`/`Ctrl-b` prefix, `\|`/`-` splits, `Alt+Arrow` pane switching, `vi` copy mode with Android clipboard via `termux-clipboard-set`) |

> [!NOTE]
> **Neovim distro stability:** On Termux, **AstroNvim is stable** and recommended. **LazyVim tends to crash** on Termux, though the option is still available if you want to test it.

#### Custom `xmake` commands

Setup patches `xmake`'s default `c` and `c++` console templates to enable `-Wall -Wextra` and auto-update `compile_commands.json` (for `clangd`), and installs 3 global plugins in `~/.xmake/plugins/`:

| Command | What it does |
|---------|--------------|
| `xmake br [args...]` | Build and run in one step (like `cargo run`) |
| `xmake san [args...]` | Build and run with AddressSanitizer + UndefinedBehaviorSanitizer |
| `xmake dbg [args...]` | Build in debug mode and launch `lldb` |

#### Zsh aliases

| Alias | Runs |
|-------|------|
| `ls` / `ll` / `la` / `tree` | `eza` with icons (`ll`/`la` show git status) |
| `lg` | `lazygit` |
| `v` | `nvim` |
| `cc` | `clang -Wall -Wextra -g` |
| `ccsan` | `clang -Wall -Wextra -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer` |
| `xcc` | `xmake project -k compile_commands` |

Re-running the Zsh option is safe: nothing gets duplicated in `~/.zshrc`.

---

## ⌨️ Command-line flags

Skip the menus by passing flags (case-insensitive, any number of them):

```sh
python main.py --setup --configure
python configure.py --zsh --font --tmux --astronvim     # recommended (or --lazyvim / --neovim)
```

---

## ⚠️ Warning

> [!WARNING]
> Disable the Android physical keyboard shortcuts.

---

## 🛠️ Troubleshooting

<details>
<summary><b>Install hangs at "Waiting for headers"</b></summary>

1. Press <kbd>Ctrl</kbd>+<kbd>C</kbd>
2. Run `termux-change-repo` and pick a mirror near you
3. Re-run the installer

</details>
