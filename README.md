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
| C toolchain | `clang`, `make` |
| Editor | `neovim`, `lua55`, `luarocks` |
| Shell & CLI | `zsh`, `git`, `zip`, `eza`, `yazi`, `neofetch` |

Then sets **zsh** as the default shell.

### Configure

| Option | What it does |
|--------|--------------|
| **Zsh** | Installs [Oh My Zsh](https://ohmyz.sh/) (the zsh config is taken from there) |
| **Neovim** | Installs [LazyVim](https://www.lazyvim.org/) or [AstroNvim](https://astronvim.com/). Existing configs are backed up to `*.bak` |
| **Font** | Installs JetBrainsMono Nerd Font as the Termux font |

---

## ⌨️ Command-line flags

Skip the menus by passing flags (case-insensitive, any number of them):

```sh
python main.py --setup --configure
python configure.py --zsh --font --lazyvim     # or --astronvim / --neovim (opens menu)
```

---

## 📝 TODO

- LazyVim's Mason breaks clangd on Termux ([clangd#1944](https://github.com/clangd/clangd/issues/1944)). Use the `clangd` that ships with `clang` instead.

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
