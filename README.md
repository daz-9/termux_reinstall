# 📱 termux_reinstall

> Personal quick Termux config for my CS class.

> [!CAUTION]
> **Not ready to be used yet.** Expect rough edges.

Turns a fresh Termux install into a **C/C++ dev environment** (with Python, C#, and Lua LSP support) and an opinionated **TUI + X11/Wayland GUI setup**: zsh, Neovim, tmux, Nerd Font, Sway/LabWC/bspwm, and Quickshell.

## 📁 Repository Layout

```text
termux_reinstall/
├── main.py            # Interactive Setup/Configure menu & CLI dispatcher
├── setup.py           # Core & X11/Wayland pkg / toolchain installer
├── configure.py       # Builds native binaries/cursors & deploys assets below
├── daemons/           # Native C daemons (qs_native.c, tgui_fix.c), Rust scaffold (qs-native-rs), wrappers & scripts
├── dotfiles/          # Zsh/Starship, Tmux, Termux, Lazygit, Neovim, Chromium, X11, Wayland, & Quickshell configs
└── .github/workflows/ # CI validation & aarch64-linux-android Rust cross-compilation
```

---

## 🚀 Install

Paste this into a fresh Termux session:

```sh
pkg update && pkg upgrade -y && pkg install git jp2a ncurses-utils python-pip wget -y && git clone https://github.com/daz-9/termux_reinstall && cd termux_reinstall && python3 main.py
```

Use <kbd>Space</kbd> to select items in the menus and <kbd>Enter</kbd> to confirm.

---

## 🧰 What it does

### Setup

Installs the packages:

| Category | Packages |
|----------|----------|
| C/C++ & Rust | `clang`, `lldb`, `gdb`, `make`, `bear`, `rust`, `xmake` (with custom `br`, `san`, `dbg` plugins & `clangd` templates), `conan` (pip) |
| Editor | `neovim`, `lua55`, `luarocks`, `lua-language-server`, `tree-sitter`, `dotnet-sdk-9.0` + `csharp-ls`, `nodejs` + `basedpyright`, `ruff`, `ripgrep`, `fd`, `fzf`, `lazygit` |
| Shell & CLI | `zsh`, `starship`, `git`, `zip`, `eza`, `yazi`, `zoxide`, `bat`, `glow`, `tmux`, `man`, `manpages`, `fastfetch`, `termux-api`, `rish-shizuku` |
| GitHub | `git`, `git-delta`, `openssh`, `gh` |
| **x11** *(optional in `setup.py`)* | `x11-repo`, `tur-repo`, `clang`, `libx11`, `libxi`, `libxfixes`, `dbus`, `pulseaudio`, `termux-api`, `rish-shizuku`, `termux-x11-nightly`, `quickshell`, `eww`, `bspwm`, `polybar`, `rofi`, `sxhkd`, `fastcompmgr`, `sway`, `swaybg`, `labwc`, `foot`, `feh`, `xfce4-terminal`, `alacritty`, `virglrenderer-android`, `xorg-xcursorgen`, `xorg-xsetroot` |

Then sets **zsh** as the default shell (only if zsh actually installed).

If a step fails, the script prints why, carries on, and lists every failed step at the end.

### Configure

| Option | What it does |
|--------|--------------|
| **Zsh** | Installs [Oh My Zsh](https://ohmyz.sh/), `zsh-autosuggestions` + `zsh-syntax-highlighting` (plus `git`, `colored-man-pages`), wires up `zoxide`/`fzf`/`bat`/`yazi` (`y` wrapper)/`fastfetch` (skipped inside `tmux`/Neovim), prepends `~/.local/bin` to `PATH`, sets `.NET` env (`~/.dotnet/tools`, `DOTNET_ROOT`, `DOTNET_ROLL_FORWARD=Major`), installs [`dotfiles/shell/starship.toml`](dotfiles/shell/starship.toml) (`xmake`, C, Python, etc.), installs `~/.local/bin/rish`, and adds aliases |
| **Neovim** | Installs [AstroNvim](https://astronvim.com/) *(recommended)* or [LazyVim](https://www.lazyvim.org/). Existing configs are backed up to `*.bak`. Uses Termux's native `clangd`, `lua-language-server`, `csharp-ls`, `basedpyright`, and `ruff` instead of Mason ([clangd#1944](https://github.com/clangd/clangd/issues/1944)), disables Mason auto-installs, fixes Termux italic comment clipping (`termux_cursor.lua`), and includes `tokyonight` + Snacks colorscheme preview |
| **Font** | Installs JetBrainsMono Nerd Font (`~/.termux/font.ttf`), Catppuccin Mocha colors (`~/.termux/colors.properties`), and Termux app tweaks (`~/.termux/termux.properties`: `bell-character = ignore`, `hide-soft-keyboard-on-startup`, `volume-keys = volume`, `extra-keys = []`, `disable-hardware-keyboard-shortcuts = false`, `back-key=escape`) |
| **Tmux** | Writes `~/.tmux.conf` (Catppuccin Mocha bar, mouse support, `Ctrl-a`/`Ctrl-b` prefix, `\|`/`-` splits, `Alt+Arrow` pane switching, `vi` copy mode with Android clipboard via `termux-clipboard-set`) |
| **Git** | Configures `git-delta` side-by-side diffs with line numbers, `zdiff3` merge conflicts, and `diff.colorMoved` in `~/.gitconfig`, plus `delta` + Nerd Font icons in `~/.config/lazygit/config.yml` |
| **x11** | Writes Catppuccin Mocha configs for X11 (`bspwm`, `sxhkd`, `polybar`, `quickshell` + QML `components/`, `eww`, `fastcompmgr`, `rofi`, `xfce4-terminal`, `picom`) and Wayland (`sway`, `labwc`, `foot`, `quickshell`), installs touch-scaled Chromium wrapper & flags (`~/.local/bin/chromium`, `~/.config/chromium-flags.conf`, `~/.local/share/applications/chromium.desktop`, override scale with `CHROMIUM_SCALE`), compiles `~/.local/bin/qs-native` (native C daemons & persistent `rish` media-control pipe) and `~/.local/lib/libtgui_fix.so` (`--tgui` orientation/color shim), installs `~/.local/bin/rish` + Quickshell helpers (`weather.py` — override location via `~/.config/quickshell/weather.json` or `WEATHER_*` env vars, `android_status.py`), builds `TouchDot-Mocha` cursor theme, and installs `~/start-x11.sh` (`desktop`) and `~/start-wayland.sh` (`desktop-wayland`) |

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
python setup.py --core --x11
python configure.py --zsh --font --tmux --git --astronvim     # recommended (also supports --lazyvim, --neovim, --termux, --rish, --x11)
desktop                                                        # start X11 (bspwm + Quickshell/Polybar)
desktop-wayland [sway|labwc] [--x11|--tgui] [--renderer=pixman|gles2|vulkan]
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
* **`csharp-ls` warning:** Because `.dotnet/tools` lives under `$HOME`, `configure.py` prints a harmless `[!] csharp-ls not found yet` notice in a clean fake `HOME` unless `csharp-ls` is on `PATH`.

---

## 🛠️ Troubleshooting

<details>
<summary><b>Install hangs at "Waiting for headers"</b></summary>

1. Press <kbd>Ctrl</kbd>+<kbd>C</kbd>
2. Run `termux-change-repo` and pick a mirror near you
3. Re-run the installer

</details>
