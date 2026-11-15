# 📱 termux_reinstall

> Personal quick Termux config for my CS class.

> [!CAUTION]
> **Not ready to be used yet.** Expect rough edges.

Turns a fresh Termux install into a **C/C++ & Python dev environment** (with C/C++, Python, and Lua LSP support) and an opinionated **TUI setup**: zsh, Neovim, tmux, and a Nerd Font.

> [!NOTE]
> **`testing` branch:** Lightweight subset focused on fast installs while keeping the full editor, `xmake` plugins/templates, LSPs (`clangd`, `basedpyright`, `ruff`, `lua-language-server`), and terminal dev environment. Drops heavy/optional extras (`rust`, `dotnet-sdk-9.0` + `csharp-ls`, `conan`, `gdb`, `bear`, `glow`, `yazi`, `zip`, `man`, `manpages`).

---

## 🚀 Install (`testing` branch)

Paste this into a fresh Termux session:

```sh
pkg update && pkg upgrade -y && pkg install git jp2a python-pip wget -y && git clone -b testing https://github.com/daz-9/termux_reinstall && cd termux_reinstall && python3 main.py
```

Use <kbd>Space</kbd> to select items in the menus and <kbd>Enter</kbd> to confirm.

---

## 🧰 What it does

### Setup

Installs the packages:

| Category | Packages |
|----------|----------|
| C/C++ | `clang`, `lldb`, `make`, `xmake` (with custom `br`, `san`, `dbg` plugins & `clangd` templates) |
| Editor | `neovim`, `lua55`, `luarocks`, `lua-language-server`, `tree-sitter`, `nodejs` + `basedpyright`, `ruff`, `ripgrep`, `fd`, `fzf`, `lazygit` |
| Shell & CLI | `zsh`, `starship`, `git`, `eza`, `zoxide`, `bat`, `tmux`, `fastfetch`, `termux-api` |
| GitHub | `git`, `git-delta`, `openssh`, `gh` |

Then sets **zsh** as the default shell (only if zsh actually installed).

If a step fails, the script prints why, carries on, and lists every failed step at the end.

### Configure

| Option | What it does |
|--------|--------------|
| **Zsh** | Installs [Oh My Zsh](https://ohmyz.sh/), `zsh-autosuggestions` + `zsh-syntax-highlighting` (plus `git`, `colored-man-pages`), wires up `zoxide`/`fzf`/`bat`/`fastfetch` (skipped inside `tmux`/Neovim), configures [Starship](https://starship.rs/) (`starship.toml` with `xmake`, C, Python, etc.), and adds aliases |
| **Neovim** | Installs [AstroNvim](https://astronvim.com/) *(recommended)* or [LazyVim](https://www.lazyvim.org/). Existing configs are backed up to `*.bak`. Uses Termux's native `clangd`, `lua-language-server`, `basedpyright`, and `ruff` instead of Mason ([clangd#1944](https://github.com/clangd/clangd/issues/1944)), disables Mason auto-installs, fixes Termux italic comment clipping (`termux_cursor.lua`), and includes `tokyonight` + Snacks colorscheme preview |
| **Font** | Installs JetBrainsMono Nerd Font (`~/.termux/font.ttf`), Catppuccin Mocha colors (`~/.termux/colors.properties`), and Termux app tweaks (`~/.termux/termux.properties`: `bell-character = ignore`, `hide-soft-keyboard-on-startup`, `volume-keys = volume`, `disable-hardware-keyboard-shortcuts`, `back-key=escape`) |
| **Tmux** | Writes `~/.tmux.conf` (Catppuccin Mocha bar, mouse support, `Ctrl-a`/`Ctrl-b` prefix, `\|`/`-` splits, `Alt+Arrow` pane switching, `vi` copy mode with Android clipboard via `termux-clipboard-set`) |
| **Git** | Configures `git-delta` side-by-side diffs with line numbers, `zdiff3` merge conflicts, and `diff.colorMoved` in `~/.gitconfig`, plus `delta` + Nerd Font icons in `~/.config/lazygit/config.yml` |

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
python configure.py --zsh --font --tmux --git --astronvim     # recommended (or --lazyvim / --neovim)
```

---

## ⚠️ Warning

> [!WARNING]
> Disable the Android physical keyboard shortcuts.

---

## 🧪 Testing in a Fake `HOME`

To test `configure.py` safely without modifying your real dotfiles, point `HOME` to a temporary directory:

```sh
FAKE_HOME=$(mktemp -d)
HOME="$FAKE_HOME" python3 configure.py --zsh --tmux --font --git --astronvim

# Re-run to verify idempotency and check zsh syntax
HOME="$FAKE_HOME" python3 configure.py --zsh
HOME="$FAKE_HOME" zsh -n "$FAKE_HOME/.zshrc"

rm -rf "$FAKE_HOME"
```

**Notes from testing:**
* **Inherited `$ZSH` / `$ZSH_CUSTOM`:** If you run from an active Oh My Zsh session, `$ZSH` is already exported; `configure.py` overrides `ZSH` to `~/.oh-my-zsh` inside the active `HOME` so the installer doesn't abort.
* **`termux-reload-settings`:** Running `--font` still triggers Termux to reload your *real* `~/.termux/` settings, though all downloaded files (`font.ttf`, `colors.properties`) are written into `$FAKE_HOME/.termux/`.

---

## 🛠️ Troubleshooting

<details>
<summary><b>Install hangs at "Waiting for headers"</b></summary>

1. Press <kbd>Ctrl</kbd>+<kbd>C</kbd>
2. Run `termux-change-repo` and pick a mirror near you
3. Re-run the installer

</details>
