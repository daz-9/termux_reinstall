# 📱 termux_reinstall

> Personal quick Termux config for my CS class.

> [!CAUTION]
> **Not ready to be used yet.** Expect rough edges.

Turns a fresh Termux install into a basic **C dev environment** with an opinionated **TUI setup**: zsh, Neovim and a Nerd Font.

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
| C toolchain | `clang`, `make`, `gdb`, `valgrind`, `xmake` (skipped if already installed) |
| Editor | `neovim`, `lua55`, `luarocks`, `ripgrep`, `fd`, `fzf`, `lazygit` |
| Shell & CLI | `zsh`, `starship`, `git`, `zip`, `eza`, `yazi`, `zoxide`, `bat`, `tmux`, `man`, `neofetch` |
| GitHub | `openssh`, `gh` |

Then sets **zsh** as the default shell (only if zsh actually installed).

If a step fails, the script prints why, carries on, and lists every failed step at the end.

### Configure

| Option | What it does |
|--------|--------------|
| **Zsh** | Installs [Oh My Zsh](https://ohmyz.sh/), `zsh-autosuggestions` + `zsh-syntax-highlighting` (plus `git`, `z`, `colored-man-pages`), wires up `zoxide`/`fzf`/`bat`, configures [Starship](https://starship.rs/) (`~/.config/starship.toml`, with `xmake` & C support), and adds aliases |
| **Neovim** | Installs [LazyVim](https://www.lazyvim.org/) or [AstroNvim](https://astronvim.com/). Existing configs are backed up to `*.bak`. Uses Termux's own `clangd` because Mason can't install it on Android ([clangd#1944](https://github.com/clangd/clangd/issues/1944)) |
| **Font** | Installs JetBrainsMono Nerd Font as the Termux font |
| **Tmux** | Writes `~/.tmux.conf` (Catppuccin Mocha bar, mouse support, `Ctrl-a`/`Ctrl-b` prefix, `\|`/`-` splits, `Alt+Arrow` pane switching, `vi` copy mode) |

#### Zsh aliases

| Alias | Runs |
|-------|------|
| `ls` / `ll` / `la` / `tree` | `eza` with icons (`ll`/`la` show git status) |
| `lg` | `lazygit` |
| `v` | `nvim` |
| `cc` | `clang -Wall -Wextra -g` |

Re-running the Zsh option is safe: nothing gets duplicated in `~/.zshrc`.

---

## ⌨️ Command-line flags

Skip the menus by passing flags (case-insensitive, any number of them):

```sh
python main.py --setup --configure
python configure.py --zsh --font --tmux --lazyvim     # or --astronvim / --neovim (opens menu)
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
