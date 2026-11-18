#!/usr/bin/env python3
"""Configure Zsh/Starship, Neovim (AstroNvim/LazyVim + native LSPs), Font/Colors, and Tmux."""

import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

# Everything that failed gets collected here and printed at the end
failures: list[str] = []
HERE = os.path.dirname(os.path.abspath(__file__))


# --- Helpers -----------------------------------------------------------------

def run(cmd: str, desc: str, env: dict | None = None) -> bool:
    """Run a shell command, report failure to the user and keep going. Returns True on success."""
    try:
        subprocess.run(cmd, shell=True, check=True, env={**os.environ, **(env or {})})
        return True
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"[-] {desc} failed: {e}")
        failures.append(desc)
        return False


def print_summary():
    """Print a final report of any steps that failed during configuration."""
    if not failures:
        print("\n[+] Configure finished with no errors")
        return
    print(f"\n[!] Configure finished with {len(failures)} problem(s):")
    for f in failures:
        print(f"    - {f}")


# --- CLI & Menus -------------------------------------------------------------

def main() -> int:
    """Parse CLI flags or show the interactive configuration menu."""
    args = sys.argv[1:]
    if args:
        dispatch(tuple(arg.lstrip("-") for arg in args))
        print_summary()
        return 1 if failures else 0

    if not shutil.which("tput"):
        run("pkg install ncurses-utils -y", "installing ncurses-utils")

    from simple_term_menu import TerminalMenu

    terminal_menu = TerminalMenu(
        ["Zsh", "Neovim", "Font", "Tmux", "Git", "x11"],
        multi_select=True,
        show_multi_select_hint=True,
        title="Select what to configure (use space to select, enter to confirm):",
    )
    menu_entry_indices = terminal_menu.show()

    if not menu_entry_indices:
        print("[!] No menu entry selected. Exiting.")
        return 1
    dispatch(terminal_menu.chosen_menu_entries)
    print_summary()
    return 1 if failures else 0


def neovim_config() -> int:
    """Show a sub-menu to choose between LazyVim and AstroNvim."""
    if not shutil.which("tput"):
        run("pkg install ncurses-utils -y", "installing ncurses-utils")

    from simple_term_menu import TerminalMenu

    neovim_config_menu = TerminalMenu(
        ["LazyVim", "AstroNvim"],
        multi_select=False,
        title="Select Neovim config (press enter to confirm):",
    )
    menu_entry_index = neovim_config_menu.show()
    if menu_entry_index is None:
        print("[!] No menu entry selected. Exiting.")
        return 1
    return dispatch_neovim_config((neovim_config_menu.chosen_menu_entry,))


def _run_handlers(choices: tuple[str, ...], handlers: dict) -> int:
    """Run each selected handler by name, isolating exceptions so remaining steps still run."""
    rc = 0
    for choice in choices:
        handler = handlers.get(choice.lower())
        if handler is None:
            print(f"[!] Invalid choice: {choice!r}")
            rc = 1
            continue
        try:
            result = handler()
        except Exception as e:  # never let one step kill the rest
            print(f"[-] {choice} failed: {e}")
            failures.append(choice)
            result = 1
        if result != 0:
            rc = result
    return rc


def dispatch(choices: tuple[str, ...]) -> int:
    """Dispatch top-level configuration choices (menu entries or CLI flags)."""
    # Keys are lowercase so menu entries ("Zsh") and flags ("--zsh") both match
    return _run_handlers(choices, {
        "zsh": lambda: configure_zsh(),
        "neovim": lambda: neovim_config(),
        "lazyvim": lambda: configure_vim_lazyvim(),    # flag-only shortcut, skips the nvim menu
        "astronvim": lambda: configure_vim_astrovim(), # flag-only shortcut, skips the nvim menu
        "font": lambda: configure_font(),
        "termux": lambda: configure_font(),            # flag alias for font/colors/properties
        "tmux": lambda: configure_tmux(),
        "git": lambda: configure_git(),
        "x11": lambda: configure_x11(),
        "rish": lambda: configure_rish(),
    })


def dispatch_neovim_config(choices: tuple[str, ...]) -> int:
    """Dispatch Neovim distro selection."""
    return _run_handlers(choices, {
        "lazyvim": lambda: configure_vim_lazyvim(),
        "astronvim": lambda: configure_vim_astrovim(),
    })


# --- Zsh & Starship ----------------------------------------------------------

def configure_zsh() -> int:
    """Install Oh My Zsh, plugins, aliases, CLI tool hooks, and Starship prompt."""
    # no zsh -> oh-my-zsh is pointless, and we must not try to launch/switch to it
    if not shutil.which("zsh"):
        print("[-] zsh is not installed (run Setup first), skipping Oh My Zsh")
        failures.append("Oh My Zsh skipped: zsh not installed")
        return 1
    omz_dir = os.path.expanduser("~/.oh-my-zsh")
    if os.path.isdir(omz_dir):
        # the installer refuses to run twice, so just skip to the polish
        print("[+] Oh My Zsh already installed, skipping install")
    else:
        # RUNZSH=no / CHSH=no: never start zsh or change the shell from here, even if the install half-fails
        ok = run(
            "sh -c \"$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)\" \"\" --unattended",
            "installing Oh My Zsh",
            env={"RUNZSH": "no", "CHSH": "no", "ZSH": omz_dir},
        )
        if not ok:
            return 1  # no omz -> plugins/zshrc edits would be pointless

    plugins = install_zsh_plugins(omz_dir)
    enable_zsh_plugins(plugins)
    _append_zshrc_block(ZSH_ALIASES_MARKER, ZSH_ALIASES, "aliases")
    _append_zshrc_block(ZSH_CLI_TOOLS_MARKER, ZSH_CLI_TOOLS, "CLI tools (zoxide, fzf, bat)")
    configure_starship()
    _append_zshrc_block(ZSH_STARSHIP_MARKER, ZSH_STARSHIP, "starship prompt")
    configure_rish()
    return 0


ZSH_PLUGIN_REPOS = {
    "zsh-autosuggestions": "https://github.com/zsh-users/zsh-autosuggestions",
    "zsh-syntax-highlighting": "https://github.com/zsh-users/zsh-syntax-highlighting",  # must stay last in plugins=()
}

def install_zsh_plugins(omz_dir: str) -> list[str]:
    """Clone the third-party plugins. Returns the ones that are actually present."""
    custom = os.path.join(omz_dir, "custom")
    present = []
    for name, url in ZSH_PLUGIN_REPOS.items():
        dest = os.path.join(custom, "plugins", name)
        if os.path.isdir(dest):
            print(f"[+] {name} already installed")
            present.append(name)
        elif run(f"git clone -q --depth 1 {url} '{dest}'", f"cloning {name}"):
            present.append(name)
    return present

def enable_zsh_plugins(extra: list[str]):
    """Add plugins to the plugins=(...) line in ~/.zshrc. Only plugins that exist are added,
    otherwise zsh complains on every start."""
    zshrc = os.path.expanduser("~/.zshrc")
    if not os.path.exists(zshrc):
        print("[-] ~/.zshrc not found, can't enable plugins")
        failures.append("enabling zsh plugins (~/.zshrc missing)")
        return
    with open(zshrc) as f:
        text = f.read()
    m = re.search(r"^plugins=\(([^)]*)\)", text, re.M)
    if not m:
        print("[-] no plugins=(...) line in ~/.zshrc, can't enable plugins")
        failures.append("enabling zsh plugins (no plugins= line)")
        return
    current = m.group(1).split()
    wanted = ["git", "colored-man-pages"] + extra  # git/colored-man-pages ship with omz (zoxide replaces omz's z)
    merged = current + [p for p in wanted if p not in current]
    # syntax-highlighting has to be loaded last
    if "zsh-syntax-highlighting" in merged:
        merged.remove("zsh-syntax-highlighting")
        merged.append("zsh-syntax-highlighting")
    text = text[:m.start()] + f"plugins=({' '.join(merged)})" + text[m.end():]
    with open(zshrc, "w") as f:
        f.write(text)
    print(f"[+] zsh plugins: {' '.join(merged)}")

ZSH_ALIASES_MARKER = "# >>> termux_reinstall aliases >>>"
ZSH_ALIASES = f"""
{ZSH_ALIASES_MARKER}
# eza instead of ls (only if it's installed)
if command -v eza >/dev/null; then
  alias ls='eza --icons --group-directories-first'
  alias ll='eza -l --icons --git --group-directories-first'
  alias la='eza -la --icons --git --group-directories-first'
  alias tree='eza --tree --icons'
fi
command -v lazygit >/dev/null && alias lg='lazygit'
alias v='nvim'
# compile C with warnings + debug info, e.g. `cc main.c -o main`
alias cc='clang -Wall -Wextra -g'
# compile C with AddressSanitizer + UndefinedBehaviorSanitizer (replaces valgrind on Android)
alias ccsan='clang -Wall -Wextra -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer'
# generate compile_commands.json for clangd in xmake projects
alias xcc='xmake project -k compile_commands'
# <<< termux_reinstall aliases <<<
"""

ZSH_CLI_TOOLS_MARKER = "# >>> CLI tools (zoxide, fzf, bat) >>>"
ZSH_CLI_TOOLS = f"""
{ZSH_CLI_TOOLS_MARKER}
if command -v zoxide >/dev/null 2>&1; then
  unalias z 2>/dev/null
  eval "$(zoxide init zsh)"
fi

if command -v fzf >/dev/null 2>&1; then
  source <(fzf --zsh)
fi

if command -v bat >/dev/null 2>&1; then
  export BAT_THEME="Catppuccin Mocha"
  alias cat='bat --paging=never'
  export MANPAGER="sh -c 'col -bx | bat -l man -p'"
fi

if command -v yazi >/dev/null 2>&1; then
  function y() {{
    local tmp cwd; tmp="$(mktemp -t "yazi-cwd.XXXXXX")"
    command yazi "$@" --cwd-file="$tmp"
    IFS= read -r -d '' cwd < "$tmp"
    [ "$cwd" != "$PWD" ] && [ -d "$cwd" ] && builtin cd -- "$cwd" || builtin true
    command rm -f -- "$tmp"
  }}
fi

if [ -d "$HOME/.dotnet/tools" ]; then
  export PATH="$HOME/.dotnet/tools:$PATH"
  export DOTNET_ROOT="${{PREFIX:-/data/data/com.termux/files/usr}}/lib/dotnet"
  export DOTNET_ROLL_FORWARD=Major
fi

# Run fastfetch only in top-level interactive shells (not inside tmux splits or Neovim)
[[ -z "$TMUX" && -z "$NVIM" ]] && command -v fastfetch >/dev/null 2>&1 && fastfetch
# <<< CLI tools (zoxide, fzf, bat) <<<
"""

ZSH_STARSHIP_MARKER = "# >>> starship prompt >>>"
ZSH_STARSHIP = f"""
{ZSH_STARSHIP_MARKER}
if command -v starship >/dev/null 2>&1; then
  eval "$(starship init zsh)"
fi
# <<< starship prompt <<<
"""


def _append_zshrc_block(marker: str, block: str, label: str):
    """Append a marked config block to ~/.zshrc once (re-running doesn't duplicate it)."""
    zshrc = os.path.expanduser("~/.zshrc")
    try:
        existing = open(zshrc).read() if os.path.exists(zshrc) else ""
        if marker in existing:
            print(f"[+] {label} already in ~/.zshrc")
            return
        with open(zshrc, "a") as f:
            f.write(block)
        print(f"[+] added {label} to ~/.zshrc")
    except OSError as e:
        print(f"[-] adding {label} failed: {e}")
        failures.append(f"adding zsh {label}")


def configure_starship():
    """Copy starship.toml from the repo into ~/.config/starship.toml."""
    src = os.path.join(HERE, "starship.toml")
    path = os.path.expanduser("~/.config/starship.toml")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copyfile(src, path)
        print("[+] wrote ~/.config/starship.toml")
    except OSError as e:
        print(f"[-] writing starship.toml failed: {e}")
        failures.append("writing starship.toml")
    if not shutil.which("starship"):
        print("[!] starship not found yet, install starship (run Setup) to enable prompt")


# --- Tmux --------------------------------------------------------------------

TMUX_CONF = """# True color & Neovim compatibility
set -g default-terminal "tmux-256color"
set -ag terminal-overrides ",xterm-256color:RGB"
set -sg escape-time 0
set -g focus-events on

# Prefix: Ctrl-b (default) + Ctrl-a (easier to reach)
set -g prefix2 C-a
bind C-a send-prefix -2

# Mouse & scrollback
set -g mouse on
set -g history-limit 10000

# 1-based indexing (matches keyboard layout)
set -g base-index 1
setw -g pane-base-index 1
set -g renumber-windows on

# Intuitive splits (keep current directory)
bind | split-window -h -c "#{pane_current_path}"
bind - split-window -v -c "#{pane_current_path}"
bind c new-window -c "#{pane_current_path}"

# Fast pane navigation with Alt+Arrow (no prefix needed)
bind -n M-Left select-pane -L
bind -n M-Right select-pane -R
bind -n M-Up select-pane -U
bind -n M-Down select-pane -D

# Vim-style pane navigation with prefix
bind h select-pane -L
bind j select-pane -D
bind k select-pane -U
bind l select-pane -R

# Reload config
bind r source-file ~/.tmux.conf \\; display-message "tmux.conf reloaded"

# Vi copy mode (y copies to Android clipboard via termux-api when available)
setw -g mode-keys vi
bind -T copy-mode-vi v send-keys -X begin-selection
bind -T copy-mode-vi y send-keys -X copy-pipe-and-cancel "termux-clipboard-set"

# Catppuccin Mocha status bar
set -g status-position bottom
set -g status-style "bg=#181825,fg=#cdd6f4"
set -g status-left "#[bg=#89b4fa,fg=#1e1e2e,bold] #S #[bg=#181825] "
set -g status-right "#[fg=#a6adc8]%H:%M "
setw -g window-status-format "#[fg=#6c7086] #I:#W "
setw -g window-status-current-format "#[bg=#313244,fg=#cba6f7,bold] #I:#W "
set -g pane-border-style "fg=#313244"
set -g pane-active-border-style "fg=#89b4fa"
"""


def configure_tmux() -> int:
    """Write ~/.tmux.conf (backing up any existing file) and reload hints."""
    path = os.path.expanduser("~/.tmux.conf")
    try:
        if os.path.exists(path):
            shutil.copy2(path, path + ".bak")
        with open(path, "w") as f:
            f.write(TMUX_CONF)
        print("[+] wrote ~/.tmux.conf")
        if not shutil.which("tmux"):
            print("[!] tmux not found yet, install tmux (run Setup) to use it")
        return 0
    except OSError as e:
        print(f"[-] writing ~/.tmux.conf failed: {e}")
        failures.append("writing ~/.tmux.conf")
        return 1

# --- Termux Font & Colors ----------------------------------------------------

TERMUX_COLORS = """# https://github.com/catppuccin/catppuccin (Catppuccin Mocha)
foreground=#cdd6f4
background=#1e1e2e
cursor=#f5e0dc

color0=#45475a
color1=#f38ba8
color2=#a6e3a1
color3=#f9e2af
color4=#89b4fa
color5=#f5c2e7
color6=#94e2d5
color7=#bac2de

color8=#585b70
color9=#f38ba8
color10=#a6e3a1
color11=#f9e2af
color12=#89b4fa
color13=#f5c2e7
color14=#94e2d5
color15=#a6adc8

color16=#fab387
color17=#f5e0dc
"""

TERMUX_PROPERTIES = {
    "hide-soft-keyboard-on-startup": "true",
    "volume-keys": "volume",
    "extra-keys": "[]",
    "disable-hardware-keyboard-shortcuts": "false",
    "bell-character": "ignore",
    "back-key": "escape",
}


def _configure_termux_properties(termux_dir: str) -> bool:
    """Enable recommended Termux app properties without clobbering existing comments."""
    props_path = os.path.join(termux_dir, "termux.properties")
    try:
        os.makedirs(termux_dir, exist_ok=True)
        lines = open(props_path).read().splitlines(True) if os.path.exists(props_path) else []
        remaining = dict(TERMUX_PROPERTIES)
        new_lines = []

        for line in lines:
            matched_key = None
            for key, val in remaining.items():
                # Match either an active `key = ...` or commented `# key = ...` / `#key=...`
                if re.match(rf"^\s*#?\s*{re.escape(key)}\s*=", line):
                    is_commented = line.lstrip().startswith("#")
                    # Multi-choice keys have several commented examples; only uncomment the matching value
                    if is_commented and key in ("bell-character", "back-key") and val not in line:
                        continue
                    matched_key = key
                    break
            if matched_key:
                val = remaining.pop(matched_key)
                sep = "=" if matched_key == "back-key" else " = "
                new_lines.append(f"{matched_key}{sep}{val}\n")
            else:
                new_lines.append(line)

        if remaining:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            for key, val in remaining.items():
                sep = "=" if key == "back-key" else " = "
                new_lines.append(f"{key}{sep}{val}\n")

        with open(props_path, "w") as f:
            f.writelines(new_lines)
        print("[+] updated ~/.termux/termux.properties")
        return True
    except OSError as e:
        print(f"[-] writing ~/.termux/termux.properties failed: {e}")
        failures.append("writing ~/.termux/termux.properties")
        return False


def configure_font() -> int:
    """Download JetBrainsMono Nerd Font, write Catppuccin colors, and set termux.properties."""
    termux_dir = os.path.expanduser("~/.termux")
    ok = run("mkdir -p ~/.termux/", "creating ~/.termux")
    # download to a temp file first so a failed download doesn't wipe the current font
    ok = ok and run("curl -fsSL https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/patched-fonts/JetBrainsMono/Ligatures/JetBrainsMonoNerdFont-Regular.ttf -o ~/.termux/font.ttf.tmp && mv ~/.termux/font.ttf.tmp ~/.termux/font.ttf", "downloading Nerd Font")
    try:
        os.makedirs(termux_dir, exist_ok=True)
        with open(os.path.join(termux_dir, "colors.properties"), "w") as f:
            f.write(TERMUX_COLORS)
        print("[+] wrote ~/.termux/colors.properties (Catppuccin Mocha)")
    except OSError as e:
        print(f"[-] writing ~/.termux/colors.properties failed: {e}")
        failures.append("writing ~/.termux/colors.properties")
        ok = False
    ok = _configure_termux_properties(termux_dir) and ok
    if ok:
        run("termux-reload-settings", "termux-reload-settings")
    return 0 if ok else 1

# --- Git & Lazygit (delta & diff/merge) --------------------------------------

LAZYGIT_CONFIG = """git:
  diffRenderers:
    - colorArg: always
      command: delta --dark --paging=never
gui:
  nerdFontsVersion: "3"
"""


def configure_git() -> int:
    """Configure git-delta side-by-side diffs, zdiff3 conflicts, and lazygit delta renderer."""
    settings = [
        ("core.pager", "delta"),
        ("interactive.diffFilter", "delta --color-only"),
        ("delta.navigate", "true"),
        ("delta.dark", "true"),
        ("delta.side-by-side", "true"),
        ("delta.line-numbers", "true"),
        ("merge.conflictstyle", "zdiff3"),
        ("diff.colorMoved", "default"),
    ]
    ok = True
    for key, val in settings:
        ok = run(f'git config --global "{key}" "{val}"', f"setting git {key}") and ok

    lg_path = os.path.expanduser("~/.config/lazygit/config.yml")
    try:
        os.makedirs(os.path.dirname(lg_path), exist_ok=True)
        if os.path.exists(lg_path):
            shutil.copy2(lg_path, lg_path + ".bak")
        with open(lg_path, "w") as f:
            f.write(LAZYGIT_CONFIG)
        print("[+] wrote ~/.config/lazygit/config.yml")
    except OSError as e:
        print(f"[-] writing ~/.config/lazygit/config.yml failed: {e}")
        failures.append("writing ~/.config/lazygit/config.yml")
        ok = False

    if not shutil.which("delta"):
        print("[!] delta not found yet, install git-delta (run Setup) to use it as git pager")
    return 0 if ok else 1


# --- Neovim & Native LSPs ----------------------------------------------------

def _backup_nvim_dirs():
    """Move existing Neovim config/data/state/cache directories to *.bak."""
    for p in ["~/.config/nvim", "~/.local/share/nvim", "~/.local/state/nvim", "~/.cache/nvim"]:
        p = os.path.expanduser(p)
        if os.path.exists(p):
            bak = p + ".bak"
            if os.path.exists(bak):
                if os.path.isdir(bak) and not os.path.islink(bak):
                    shutil.rmtree(bak)
                else:
                    os.remove(bak)
            shutil.move(p, bak) #backup config

def _restore_nvim_dirs():
    """Undo _backup_nvim_dirs() if the new config couldn't be cloned."""
    for p in ["~/.config/nvim", "~/.local/share/nvim", "~/.local/state/nvim", "~/.cache/nvim"]:
        p = os.path.expanduser(p)
        bak = p + ".bak"
        if os.path.exists(bak):
            if os.path.exists(p):
                shutil.rmtree(p, ignore_errors=True)
            shutil.move(bak, p)
    print("[*] Restored previous Neovim config")

# Mason has no Android build of clangd ("The current platform is unsupported"),
# so point both configs at the clangd that ships with Termux's `clang` package.
# see https://github.com/clangd/clangd/issues/1944
CLANGD_LAZYVIM = """-- Use Termux's clangd (from the `clang` package) instead of Mason's.
-- Mason has no Android build of clangd ("The current platform is unsupported").
return {
  {
    "neovim/nvim-lspconfig",
    opts = { servers = { clangd = { mason = false } } },
  },
}
"""

CLANGD_ASTRONVIM = """-- Use Termux's clangd (from the `clang` package) instead of Mason's.
-- Mason has no Android build of clangd ("The current platform is unsupported").
---@type LazySpec
return {
  "AstroNvim/astrolsp",
  ---@type AstroLSPOpts
  opts = { servers = { "clangd" } },
}
"""

LUA_LS_LAZYVIM = """-- Use Termux's lua-language-server instead of Mason's.
-- Mason's prebuilt binary is not built for Android/Termux.
return {
  {
    "neovim/nvim-lspconfig",
    opts = { servers = { lua_ls = { mason = false } } },
  },
}
"""

LUA_LS_ASTRONVIM = """-- Use Termux's lua-language-server instead of Mason's.
-- Mason's prebuilt binary is not built for Android/Termux.
---@type LazySpec
return {
  "AstroNvim/astrolsp",
  ---@type AstroLSPOpts
  opts = function(_, opts)
    opts.servers = vim.list_extend(opts.servers or {}, { "lua_ls" })
  end,
}
"""

CSHARP_LS_LAZYVIM = """-- Use Termux's csharp-ls (installed via `dotnet tool install --global csharp-ls --version 0.16.0`)
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
"""

CSHARP_LS_ASTRONVIM = """-- Use Termux's csharp-ls (installed via `dotnet tool install --global csharp-ls --version 0.16.0`)
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
"""

PYTHON_LSP_LAZYVIM = """-- Use Termux's native basedpyright + ruff instead of Mason.
return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        basedpyright = {
          mason = false,
          settings = {
            basedpyright = {
              analysis = {
                typeCheckingMode = "standard",
              },
            },
          },
        },
        ruff = { mason = false },
      },
    },
  },
}
"""

PYTHON_LSP_ASTRONVIM = """-- Use Termux's native basedpyright + ruff instead of Mason.
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
"""

MASON_DISABLE_ASTRONVIM = """-- Disable automatic Mason tool installation on Termux/Android,
-- since Mason's prebuilt glibc binaries are unsupported here.
---@type LazySpec
return {
  {
    "WhoIsSethDaniel/mason-tool-installer.nvim",
    opts = {
      run_on_start = false,
      auto_update = false,
    },
  },
}
"""

TERMUX_CURSOR_LAZYVIM = """-- Fix Termux italic glyph clipping (synthetic slant leans into the cursor cell)
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
"""

TERMUX_CURSOR_ASTRONVIM = """-- Fix Termux italic glyph clipping (synthetic slant leans into the cursor cell)
-- and keep Normal (block) vs Insert (vertical bar) clearly distinct.
local function strip_comment_italics()
  for _, group in ipairs({ "Comment", "@comment", "@comment.documentation", "SpecialComment" }) do
    local ok, hl = pcall(vim.api.nvim_get_hl, 0, { name = group, link = false })
    if ok and hl and (hl.italic or (hl.cterm and hl.cterm.italic)) then
      hl.italic = false
      if hl.cterm then hl.cterm.italic = false end
      vim.api.nvim_set_hl(0, group, hl)
    end
  end
end

---@type LazySpec
return {
  "AstroNvim/astrocore",
  ---@type AstroCoreOpts
  opts = {
    options = {
      opt = {
        guicursor = "n-v-c-sm:block-blinkwait300-blinkoff250-blinkon400,i-ci-ve:ver25,r-cr-o:hor20",
      },
    },
    autocmds = {
      termux_no_comment_italic = {
        {
          event = { "ColorScheme", "VimEnter" },
          desc = "Disable italic on comments so Termux doesn't clip glyphs at the cursor",
          callback = strip_comment_italics,
        },
      },
    },
  },
}
"""

COMMUNITY_ASTRONVIM = """-- AstroCommunity: import any community modules here
-- We import this file in `lazy_setup.lua` before the `plugins/` folder.
-- This guarantees that the specs are processed before any user plugins.

---@type LazySpec
return {
  "AstroNvim/astrocommunity",
  { import = "astrocommunity.pack.lua" },
  { import = "astrocommunity.colorscheme.tokyonight-nvim" },
}
"""

SNACKS_PREVIEW_ASTRONVIM = """---@type LazySpec
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
"""

def _write_lsp_spec(filename: str, content: str, bin_name: str, missing_hint: str):
    """Write a Neovim plugin spec to bypass Mason for a Termux-native LSP."""
    path = os.path.expanduser(f"~/.config/nvim/lua/plugins/{filename}")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        print(f"[+] Neovim set to use system {bin_name}")
    except OSError as e:
        print(f"[-] writing {filename} config failed: {e}")
        failures.append(f"writing {filename} config")
    if not (shutil.which(bin_name) or os.path.exists(os.path.expanduser(f"~/.dotnet/tools/{bin_name}"))):
        print(f"[!] {bin_name} not found yet, {missing_hint}")


def configure_vim_lazyvim() -> int:
    """Install LazyVim starter config and wire up Termux-native LSPs."""
    _backup_nvim_dirs()
    if not run("git clone https://github.com/LazyVim/starter ~/.config/nvim", "cloning LazyVim"):
        _restore_nvim_dirs()
        return 1
    subprocess.run("rm -rf ~/.config/nvim/.git", shell=True)
    _write_lsp_spec("clangd.lua", CLANGD_LAZYVIM, "clangd", "install clang (run Setup) for C completion/diagnostics")
    _write_lsp_spec("lua_ls.lua", LUA_LS_LAZYVIM, "lua-language-server", "install lua-language-server (run Setup) for Lua completion/diagnostics")
    _write_lsp_spec("csharp_ls.lua", CSHARP_LS_LAZYVIM, "csharp-ls", "install dotnet-sdk-9.0 + csharp-ls (run Setup) for C# completion/diagnostics")
    _write_lsp_spec("python_lsp.lua", PYTHON_LSP_LAZYVIM, "basedpyright-langserver", "install nodejs + basedpyright + ruff (run Setup) for Python completion/diagnostics")
    _write_lsp_spec("termux_cursor.lua", TERMUX_CURSOR_LAZYVIM, "nvim", "")
    return 0


def configure_vim_astrovim() -> int:
    """Install AstroNvim template config and wire up Termux-native LSPs."""
    _backup_nvim_dirs()
    if not run("git clone --depth 1 https://github.com/AstroNvim/template ~/.config/nvim", "cloning AstroNvim"):
        _restore_nvim_dirs()
        return 1
    subprocess.run("rm -rf ~/.config/nvim/.git", shell=True)
    _write_lsp_spec("clangd.lua", CLANGD_ASTRONVIM, "clangd", "install clang (run Setup) for C completion/diagnostics")
    _write_lsp_spec("lua_ls.lua", LUA_LS_ASTRONVIM, "lua-language-server", "install lua-language-server (run Setup) for Lua completion/diagnostics")
    _write_lsp_spec("csharp_ls.lua", CSHARP_LS_ASTRONVIM, "csharp-ls", "install dotnet-sdk-9.0 + csharp-ls (run Setup) for C# completion/diagnostics")
    _write_lsp_spec("python_lsp.lua", PYTHON_LSP_ASTRONVIM, "basedpyright-langserver", "install nodejs + basedpyright + ruff (run Setup) for Python completion/diagnostics")
    _write_lsp_spec("mason.lua", MASON_DISABLE_ASTRONVIM, "nvim", "")
    _write_lsp_spec("termux_cursor.lua", TERMUX_CURSOR_ASTRONVIM, "nvim", "")
    _write_lsp_spec("snacks.lua", SNACKS_PREVIEW_ASTRONVIM, "nvim", "")
    try:
        comm_path = os.path.expanduser("~/.config/nvim/lua/community.lua")
        with open(comm_path, "w") as f:
            f.write(COMMUNITY_ASTRONVIM)
        print("[+] wrote ~/.config/nvim/lua/community.lua")
    except OSError as e:
        print(f"[-] writing community.lua failed: {e}")
        failures.append("writing community.lua")
    return 0


# --- X11 (bspwm + sxhkd + polybar + rofi) ------------------------------------

BSPWMRC = """#!/data/data/com.termux/files/usr/bin/sh

export BSPWM_SOCKET="${BSPWM_SOCKET:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}/bspwm_0_0-socket}"
export XCURSOR_THEME="${XCURSOR_THEME:-TouchDot-Mocha}"
export XCURSOR_SIZE="${XCURSOR_SIZE:-32}"

[ -f "$HOME/.Xresources" ] && command -v xrdb >/dev/null 2>&1 && xrdb -merge "$HOME/.Xresources" >/dev/null 2>&1 || true
command -v xsetroot >/dev/null 2>&1 && xsetroot -cursor_name left_ptr >/dev/null 2>&1 || true

pgrep -x sxhkd >/dev/null || sxhkd &

bspc monitor -d 1 2 3 4 5 6

bspc config border_width          2
bspc config window_gap            12
bspc config split_ratio           0.52
bspc config borderless_monocle    true
bspc config gapless_monocle       true
bspc config focus_follows_pointer true
bspc config pointer_modifier      mod1

# Catppuccin Mocha borders
bspc config normal_border_color   "#313244"
bspc config active_border_color   "#45475a"
bspc config focused_border_color  "#89b4fa"
bspc config presel_feedback_color "#cba6f7"

if command -v fastcompmgr >/dev/null 2>&1; then
  pkill -x fastcompmgr 2>/dev/null || true
  pkill -x picom 2>/dev/null || true
  fastcompmgr >/dev/null 2>&1 &
elif command -v picom >/dev/null 2>&1; then
  pkill -x picom 2>/dev/null || true
  picom --config "${XDG_CONFIG_HOME:-$HOME/.config}/picom/picom.conf" >> "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/picom.log" 2>&1 &
fi

if command -v feh >/dev/null 2>&1 && [ -f "$HOME/.local/share/wallpapers/wallpaper.jpg" ]; then
  feh --no-fehbg --bg-fill "$HOME/.local/share/wallpapers/wallpaper.jpg" &
fi

if [ -f "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/hide-cursor.pid" ]; then
  kill "$(cat "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/hide-cursor.pid")" 2>/dev/null || true
  rm -f "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/hide-cursor.pid"
fi
if [ -x "$HOME/.local/bin/qs-native" ]; then
  "$HOME/.local/bin/qs-native" hide-cursor >/dev/null 2>&1 &
elif [ -x "${XDG_CONFIG_HOME:-$HOME/.config}/bspwm/hide-cursor.py" ]; then
  "${XDG_CONFIG_HOME:-$HOME/.config}/bspwm/hide-cursor.py" >/dev/null 2>&1 &
fi

"${XDG_CONFIG_HOME:-$HOME/.config}/polybar/launch.sh" &
if command -v quickshell >/dev/null 2>&1; then
  "${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/launch.sh" &
elif command -v eww >/dev/null 2>&1; then
  "${XDG_CONFIG_HOME:-$HOME/.config}/eww/launch.sh" &
fi
"""

SXHKDRC = """# i3-style keybinds for bspwm ($mod = Alt or Super/Command)

# Terminal (xfce4-terminal for fast 2D rendering on Mali; Shift+Return for VirGL Alacritty)
{alt,super} + Return
	if command -v xfce4-terminal >/dev/null 2>&1; then exec xfce4-terminal; else exec alacritty; fi

{alt,super} + shift + Return
	GALLIUM_DRIVER=virpipe alacritty

# App launcher (i3: $mod+d / $mod+Shift+d)
{alt,super} + d
	rofi -show drun

{alt,super} + shift + d
	rofi -show run

# Kill / force-kill focused window (i3: $mod+Shift+q)
{alt,super} + shift + q
	bspc node -c

{alt,super} + shift + ctrl + q
	bspc node -k

# Focus window (i3: $mod + h/j/k/l or arrows)
# NOTE: Separate alt/super blocks to work around sxhkd multi-brace pairing truncation.
alt + {h,j,k,l,Left,Down,Up,Right}
	bspc node -f {west,south,north,east,west,south,north,east}

super + {h,j,k,l,Left,Down,Up,Right}
	bspc node -f {west,south,north,east,west,south,north,east}

# Move/swap window (i3: $mod+Shift + h/j/k/l or arrows)
alt + shift + {h,j,k,l,Left,Down,Up,Right}
	bspc node -s {west,south,north,east,west,south,north,east}

super + shift + {h,j,k,l,Left,Down,Up,Right}
	bspc node -s {west,south,north,east,west,south,north,east}

# Split direction (i3-style: $mod+v vertical/below, $mod+b horizontal/right)
alt + {v,b}
	bspc node -p {south,east}

super + {v,b}
	bspc node -p {south,east}

{alt,super} + ctrl + space
	bspc node -p cancel

# Fullscreen toggle (i3: $mod+f)
{alt,super} + f
	bspc node -t ~fullscreen

# Floating toggle (i3: $mod+Shift+space)
{alt,super} + shift + space
	bspc node -t ~floating

# Layout toggle (i3: $mod+w monocle, $mod+e tiled)
{alt,super} + w
	bspc desktop -l next

{alt,super} + e
	bspc desktop -l tiled

# Resize focused window ($mod+Ctrl + h/j/k/l)
{alt,super} + ctrl + h
	bspc node -z right -20 0 || bspc node -z left 20 0

{alt,super} + ctrl + l
	bspc node -z right 20 0 || bspc node -z left -20 0

{alt,super} + ctrl + k
	bspc node -z bottom 0 -20 || bspc node -z top 0 20

{alt,super} + ctrl + j
	bspc node -z bottom 0 20 || bspc node -z top 0 -20

# Switch to workspace (i3: $mod+1..6)
alt + {1,2,3,4,5,6}
	bspc desktop -f '^{1,2,3,4,5,6}'

super + {1,2,3,4,5,6}
	bspc desktop -f '^{1,2,3,4,5,6}'

# Move window to workspace (i3: $mod+Shift+1..6)
alt + shift + {1,2,3,4,5,6}
	bspc node -d '^{1,2,3,4,5,6}'

super + shift + {1,2,3,4,5,6}
	bspc node -d '^{1,2,3,4,5,6}'

# Reload sxhkd (i3: $mod+Shift+c)
{alt,super} + shift + c
	pkill -USR1 -x sxhkd

# Restart bspwm (i3: $mod+Shift+r)
{alt,super} + shift + r
	bspc wm -r

# Exit bspwm session (i3: $mod+Shift+e)
{alt,super} + shift + e
	bspc quit
"""

POLYBAR_LAUNCH = """#!/data/data/com.termux/files/usr/bin/sh

export BSPWM_SOCKET="${BSPWM_SOCKET:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}/bspwm_0_0-socket}"
export XCURSOR_THEME="${XCURSOR_THEME:-TouchDot-Mocha}"
export XCURSOR_SIZE="${XCURSOR_SIZE:-32}"

pkill -x polybar 2>/dev/null || true
while pgrep -u "$(id -u)" -x polybar >/dev/null 2>&1; do
  sleep 0.2
done

MONITOR="$(polybar -m 2>/dev/null | head -n1 | cut -d: -f1)"
export MONITOR="${MONITOR:-builtin}"

LOG="${TMPDIR:-/data/data/com.termux/files/usr/tmp}/polybar.log"
polybar main >> "$LOG" 2>&1 &
"""

POLYBAR_CONFIG = """; Catppuccin Mocha Polybar config tuned for Termux/Android

[colors]
base = #1e1e2e
surface = #313244
surface1 = #45475a
text = #cdd6f4
subtext = #a6adc8
blue = #89b4fa
mauve = #cba6f7
green = #a6e3a1
teal = #94e2d5
red = #f38ba8

[bar/main]
monitor = ${env:MONITOR:builtin}
width = 100%
height = 40pt
radius = 16
border-size = 8pt
border-color = #00000000
background = ${colors.base}
foreground = ${colors.text}
line-size = 3pt
padding-left = 2
padding-right = 3
module-margin = 2
separator = |
separator-foreground = ${colors.surface1}

font-0 = "JetBrainsMono Nerd Font:size=14;3"
font-1 = "monospace:size=14;3"

cursor-click = pointer
cursor-scroll = ns-resize

modules-left = xwindow
modules-center =
modules-right = cpu memory battery date

wm-restack = bspwm
enable-ipc = true

[module/xwindow]
type = internal/xwindow
label = %title:0:60:...%
label-empty = Ready
label-foreground = ${colors.text}
label-empty-foreground = ${colors.subtext}

[module/cpu]
type = custom/script
exec = ~/.local/bin/qs-native cpu
tail = true

[module/memory]
type = internal/memory
interval = 3
format-prefix = "\U000f035b "
format-prefix-foreground = ${colors.mauve}
label = %gb_used% (%percentage_used%%)

[module/battery]
type = custom/script
exec = ~/.config/polybar/battery.sh
interval = 30

[module/date]
type = internal/date
interval = 1
date = %a %d %b
time = %H:%M
format-prefix = "\uf017 "
format-prefix-foreground = ${colors.blue}
label = %date%  %time%
label-foreground = ${colors.blue}
"""

POLYBAR_BATTERY_SH = """#!/data/data/com.termux/files/usr/bin/sh
if ! command -v termux-battery-status >/dev/null 2>&1; then
  printf "BAT --\\n"
  exit 0
fi

out="$(timeout 4 termux-battery-status 2>/dev/null)" || true
if [ -z "$out" ]; then
  printf "BAT --\\n"
  exit 0
fi

eval "$(printf '%s\\n' "$out" | awk -F: '
  /"percentage"/ { gsub(/[^0-9]/, "", $2); pct=$2 }
  /"status"/     { gsub(/[^A-Za-z]/, "", $2); st=$2 }
  END { printf "pct=%s\\nst=%s\\n", pct, st }
')"

if [ -z "$pct" ]; then
  printf "BAT --\\n"
  exit 0
fi

if [ "$st" = "CHARGING" ]; then
  icon="\uf0e7"
  color="#a6e3a1"
elif [ "$pct" -ge 85 ]; then
  icon="\uf240"
  color="#a6e3a1"
elif [ "$pct" -ge 60 ]; then
  icon="\uf241"
  color="#94e2d5"
elif [ "$pct" -ge 35 ]; then
  icon="\uf242"
  color="#cdd6f4"
elif [ "$pct" -ge 15 ]; then
  icon="\uf243"
  color="#fab387"
else
  icon="\uf244"
  color="#f38ba8"
fi

printf "%%{F%s}%s %s%%%%{F-}\\n" "$color" "$icon" "$pct"
"""

POLYBAR_CPU_PY = """#!/data/data/com.termux/files/usr/bin/python3
\"\"\"Stream Termux/X11 CPU utilization across visible processes for Polybar.\"\"\"

import os
import signal
import sys
import time


def _total_jiffies() -> int:
    total = 0
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat") as f:
                data = f.read()
            rp = data.rfind(")")
            if rp < 0:
                continue
            fields = data[rp + 2:].split()
            total += int(fields[11]) + int(fields[12])
        except (OSError, IndexError, ValueError):
            pass
    return total


def main() -> int:
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    clk = os.sysconf("SC_CLK_TCK")
    ncpu = os.cpu_count() or 1
    j_prev = _total_jiffies()
    t_prev = time.monotonic()

    # Emit initial quick sample right away, then poll every 3s
    time.sleep(0.35)
    while running:
        j_now = _total_jiffies()
        t_now = time.monotonic()
        dt = max(0.05, t_now - t_prev)
        pct = min(100, max(0, round(((j_now - j_prev) / clk) / (dt * ncpu) * 100.0)))
        j_prev, t_prev = j_now, t_now

        if pct >= 80:
            color = "#f38ba8"
        elif pct >= 50:
            color = "#fab387"
        else:
            color = "#94e2d5"

        print(f"%{{F{color}}}\uf4bc%{{F-}} {pct}%", flush=True)
        for _ in range(30):
            if not running:
                break
            time.sleep(0.1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

EWW_LAUNCH_SH = """#!/data/data/com.termux/files/usr/bin/sh

export BSPWM_SOCKET="${BSPWM_SOCKET:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}/bspwm_0_0-socket}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
export GDK_BACKEND=x11
export XCURSOR_THEME="${XCURSOR_THEME:-TouchDot-Mocha}"
export XCURSOR_SIZE="${XCURSOR_SIZE:-32}"

eww kill >/dev/null 2>&1 || true
[ -f "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/eww-watch.pid" ] && kill "$(cat "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/eww-watch.pid")" 2>/dev/null || true
rm -f "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/eww-watch.pid"
pkill -x eww 2>/dev/null || true
while pgrep -u "$(id -u)" -x eww >/dev/null 2>&1; do
  sleep 0.15
done

LOG="${TMPDIR:-/data/data/com.termux/files/usr/tmp}/eww.log"
# Give picom a moment on cold X11 boot so GTK3 sees compositor RGBA visual
if pgrep -x picom >/dev/null 2>&1; then
  sleep 0.2
fi
eww daemon >> "$LOG" 2>&1 &

i=0
while [ "$i" -lt 25 ]; do
  if eww ping >/dev/null 2>&1; then
    break
  fi
  i=$((i + 1))
  sleep 0.1
done

eww open dock >> "$LOG" 2>&1 || true
bspc config left_padding 128 >/dev/null 2>&1 || true
"""

EWW_BSPWM_STATE_PY = """#!/data/data/com.termux/files/usr/bin/python3
\"\"\"Stream bspwm desktop & layout state as JSON lines for eww deflisten.\"\"\"

import json
import os
import signal
import subprocess
import sys


def parse_report(line: str) -> dict | None:
    parts = line.strip().split(":")
    if len(parts) < 2:
        return None
    desktops = []
    layout = "T"
    for part in parts:
        if len(part) < 2:
            continue
        tag, name = part[0], part[1:]
        if tag in "FfOoUu":
            try:
                num = int(name)
            except ValueError:
                continue
            desktops.append({
                "num": num,
                "focused": tag in "FOU",
                "occupied": tag in "Oo",
                "urgent": tag in "Uu",
            })
        elif tag == "L":
            layout = name
    if not desktops:
        return None
    return {"layout": layout, "desktops": desktops}


def main() -> int:
    proc = subprocess.Popen(
        ["bspc", "subscribe", "report"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )

    def stop(_sig, _frame):
        proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    assert proc.stdout is not None
    for line in proc.stdout:
        state = parse_report(line)
        if state is not None:
            print(json.dumps(state), flush=True)
    return proc.wait()


if __name__ == "__main__":
    sys.exit(main())
"""

EWW_AUDIO_STATE_SH = """#!/data/data/com.termux/files/usr/bin/sh
vol=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | grep -oE '[0-9]+%' | head -n1 | tr -d '%')
mute=$(pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null)
case "$vol" in
  ''|*[!0-9]*) vol=50 ;;
esac
case "$mute" in
  *yes*) muted=true ;;
  *) muted=false ;;
esac
printf '{"pct":%s,"muted":%s}\\n' "$vol" "$muted"
"""

EWW_TOGGLE_WINDOW_SH = """#!/data/data/com.termux/files/usr/bin/sh
mode="toggle"
if [ "$1" = "close" ] || [ "$1" = "open" ]; then
  mode="$1"
  shift
fi
win="$1"
var="$2"

close_win() {
  eww close "$win" >/dev/null 2>&1 || true
  eww update "$var=false" >/dev/null 2>&1 || true
}

open_win() {
  eww update "$var=true" >/dev/null 2>&1 || true
  eww open "$win" >/dev/null 2>&1 || true
  watch_pid="${TMPDIR:-/data/data/com.termux/files/usr/tmp}/eww-watch.pid"
  if [ ! -f "$watch_pid" ] || ! kill -0 "$(cat "$watch_pid" 2>/dev/null)" 2>/dev/null; then
    if [ -x "${XDG_CONFIG_HOME:-$HOME/.config}/eww/scripts/submenu_watch.py" ]; then
      "${XDG_CONFIG_HOME:-$HOME/.config}/eww/scripts/submenu_watch.py" >/dev/null 2>&1 &
    fi
  fi
}

if [ "$mode" = "close" ]; then
  close_win
elif [ "$mode" = "open" ]; then
  open_win
elif eww active-windows 2>/dev/null | grep -q "$win"; then
  close_win
else
  open_win
fi
"""

EWW_SUBMENU_WATCH_PY = """#!/data/data/com.termux/files/usr/bin/python3
\"\"\"Auto-close open Eww submenus on focus loss, popup/launcher open, or outside click.\"\"\"

import os
import select
import signal
import subprocess
import sys
import time
from ctypes import CDLL, POINTER, Structure, byref, c_char, c_char_p, c_int, c_long, c_ubyte, c_uint, c_ulong, c_void_p, string_at


class XWA(Structure):
    _fields_ = [
        ("x", c_int), ("y", c_int), ("width", c_int), ("height", c_int),
        ("border_width", c_int), ("depth", c_int), ("visual", c_void_p),
        ("root", c_ulong), ("c_class", c_int), ("bit_gravity", c_int),
        ("win_gravity", c_int), ("backing_store", c_int),
        ("backing_planes", c_long), ("backing_pixel", c_long),
        ("save_under", c_int), ("colormap", c_ulong), ("map_installed", c_int),
        ("map_state", c_int), ("all_event_masks", c_long), ("your_event_mask", c_long),
        ("do_not_propagate_mask", c_long), ("override_redirect", c_int), ("screen", c_void_p),
    ]


class XIEventMask(Structure):
    _fields_ = [("deviceid", c_int), ("mask_len", c_int), ("mask", POINTER(c_ubyte))]


def _inspect_tree(x11, dpy, root):
    r, p, ch, n = c_ulong(), c_ulong(), POINTER(c_ulong)(), c_uint()
    rects = {}
    foreign_popup = False
    if not x11.XQueryTree(dpy, root, byref(r), byref(p), byref(ch), byref(n)):
        return rects, foreign_popup
    try:
        for i in range(n.value):
            a = XWA()
            if not x11.XGetWindowAttributes(dpy, ch[i], byref(a)) or a.map_state != 2:
                continue
            nm = c_void_p()
            name = b""
            if x11.XFetchName(dpy, ch[i], byref(nm)) and nm.value:
                name = string_at(nm.value)
                x11.XFree(nm)
            if name in (b"Eww - dock", b"Eww - widget_drawer", b"Eww - session_menu"):
                rects[name.decode()] = (a.x, a.y, a.width, a.height)
            elif a.override_redirect == 1 and a.width >= 200 and a.height >= 150 and not name.startswith(b"Eww"):
                foreign_popup = True
    finally:
        if ch:
            x11.XFree(ch)
    return rects, foreign_popup


def _point_in(px: int, py: int, rect) -> bool:
    if rect is None:
        return False
    x, y, w, h = rect
    return x <= px < x + w and y <= py < y + h


def _close_open(rects) -> None:
    toggle = os.path.expanduser("~/.config/eww/scripts/toggle_window.sh")
    targets = []
    if "Eww - widget_drawer" in rects:
        targets.append(("widget_drawer", "widgets_open"))
    if "Eww - session_menu" in rects:
        targets.append(("session_menu", "session_open"))
    procs = [subprocess.Popen([toggle, "close", win, var]) for win, var in targets]
    for proc in procs:
        proc.wait()


def main() -> int:
    x11 = CDLL("libX11.so.6")
    xi = CDLL("libXi.so")

    x11.XOpenDisplay.restype = c_void_p
    x11.XOpenDisplay.argtypes = [c_char_p]
    x11.XDefaultRootWindow.restype = c_ulong
    x11.XDefaultRootWindow.argtypes = [c_void_p]
    x11.XConnectionNumber.restype = c_int
    x11.XConnectionNumber.argtypes = [c_void_p]
    x11.XPending.restype = c_int
    x11.XPending.argtypes = [c_void_p]
    x11.XNextEvent.argtypes = [c_void_p, c_void_p]
    x11.XFlush.argtypes = [c_void_p]
    x11.XQueryTree.restype = c_int
    x11.XQueryTree.argtypes = [c_void_p, c_ulong, POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_ulong)), POINTER(c_uint)]
    x11.XGetWindowAttributes.restype = c_int
    x11.XGetWindowAttributes.argtypes = [c_void_p, c_ulong, POINTER(XWA)]
    x11.XFetchName.restype = c_int
    x11.XFetchName.argtypes = [c_void_p, c_ulong, POINTER(c_void_p)]
    x11.XFree.argtypes = [c_void_p]
    x11.XGetInputFocus.argtypes = [c_void_p, POINTER(c_ulong), POINTER(c_int)]
    x11.XQueryPointer.restype = c_int
    x11.XQueryPointer.argtypes = [
        c_void_p, c_ulong, c_void_p, c_void_p,
        c_void_p, c_void_p, c_void_p, c_void_p, c_void_p,
    ]
    x11.XCloseDisplay.argtypes = [c_void_p]

    xi.XIQueryVersion.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
    xi.XISelectEvents.argtypes = [c_void_p, c_ulong, POINTER(XIEventMask), c_int]

    dpy = x11.XOpenDisplay(os.environ.get("DISPLAY", ":0").encode())
    if not dpy:
        return 1
    root = x11.XDefaultRootWindow(dpy)
    xfd = x11.XConnectionNumber(dpy)

    maj, minv = c_int(2), c_int(2)
    xi.XIQueryVersion(dpy, byref(maj), byref(minv))

    # XIAllMasterDevices = 1; XI_RawButtonPress = 15 (1 << 15 -> byte 1 bit 7 = 0x80)
    ev_mask = (c_ubyte * 4)(0, 0x80, 0, 0)
    em = XIEventMask(deviceid=1, mask_len=4, mask=ev_mask)
    xi.XISelectEvents(dpy, root, byref(em), 1)
    x11.XFlush(dpy)

    running = True

    def stop(_sig, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    pid_path = os.path.join(
        os.environ.get("TMPDIR", "/data/data/com.termux/files/usr/tmp"),
        "eww-watch.pid",
    )
    try:
        with open(pid_path, "w") as pf:
            pf.write(str(os.getpid()))
    except OSError:
        pid_path = ""

    focus_win, revert_to = c_ulong(), c_int()
    x11.XGetInputFocus(dpy, byref(focus_win), byref(revert_to))
    initial_focus = focus_win.value

    r_win, c_win = c_ulong(), c_ulong()
    rx, ry, wx, wy = c_int(), c_int(), c_int(), c_int()
    mask = c_uint()
    ev_buf = (c_char * 192)()
    start_t = time.monotonic()

    # Wait briefly for eww open before exiting on empty rects
    seen_submenu = False

    while running:
        readable, _, _ = select.select([xfd], [], [], 0.12)
        clicked = False
        if readable:
            while x11.XPending(dpy) > 0:
                x11.XNextEvent(dpy, ev_buf)
                clicked = True

        rects, foreign_popup = _inspect_tree(x11, dpy, root)
        has_sub = ("Eww - widget_drawer" in rects) or ("Eww - session_menu" in rects)
        if has_sub:
            seen_submenu = True
        elif seen_submenu or (time.monotonic() - start_t) > 1.0:
            break

        if not has_sub:
            continue

        x11.XGetInputFocus(dpy, byref(focus_win), byref(revert_to))
        if (focus_win.value != initial_focus and focus_win.value != 0) or foreign_popup:
            _close_open(rects)
            break

        if clicked and (time.monotonic() - start_t) >= 0.05:
            if x11.XQueryPointer(dpy, root, byref(r_win), byref(c_win), byref(rx), byref(ry), byref(wx), byref(wy), byref(mask)):
                px, py = rx.value, ry.value
                in_drawer = _point_in(px, py, rects.get("Eww - widget_drawer"))
                in_session = _point_in(px, py, rects.get("Eww - session_menu"))
                dock_r = rects.get("Eww - dock")
                on_toggle_btn = False
                if dock_r and _point_in(px, py, dock_r):
                    dx0, dy0, dw, dh = dock_r
                    on_spacer = (dy0 + 755 <= py <= dy0 + dh - 470)
                    on_power = (py >= dy0 + dh - 78)
                    on_toggle_btn = on_spacer or on_power
                if not in_drawer and not in_session and not on_toggle_btn:
                    _close_open(rects)
                    break

    if pid_path:
        try:
            os.remove(pid_path)
        except OSError:
            pass
    x11.XCloseDisplay(dpy)
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

EWW_YUCK = """(deflisten bspwm_state
  :initial '{"layout":"T","desktops":[{"num":1,"focused":true,"occupied":false,"urgent":false},{"num":2,"focused":false,"occupied":false,"urgent":false},{"num":3,"focused":false,"occupied":false,"urgent":false},{"num":4,"focused":false,"occupied":false,"urgent":false},{"num":5,"focused":false,"occupied":false,"urgent":false},{"num":6,"focused":false,"occupied":false,"urgent":false}]}'
  "~/.config/eww/scripts/bspwm_state.py")

(defpoll audio_state
  :interval "4s"
  :initial '{"pct":50,"muted":false}'
  "~/.config/eww/scripts/audio_state.sh")

(defvar session_open false)
(defvar widgets_open false)

(defwidget dock_content []
  (overlay
    (box :class "dock-bg" :hexpand true :vexpand true)
    (box :class "dock-fg"
         :orientation "v"
         :space-evenly false
         :vexpand true

    ;; Top: Touch Launchers
    (box :class "section"
         :orientation "v"
         :halign "center"
         :space-evenly false
      (button :class "hit-btn"
              :onclick "rofi -show drun &"
        (box :class "pill pill-tall" :orientation "v" :halign "center" :valign "center"
          (label :class "icon-launcher nf-apps c-blue" :halign "center" :text "\U000f003b")))
      (button :class "hit-btn"
              :onclick "if command -v xfce4-terminal >/dev/null 2>&1; then xfce4-terminal & else alacritty & fi"
        (box :class "pill pill-tall" :orientation "v" :halign "center" :valign "center"
          (label :class "icon-lg nf-term c-teal" :halign "center" :text "\uf120")))
      (button :class "hit-btn"
              :onclick "rofi -show window &"
        (box :class "pill pill-tall" :orientation "v" :halign "center" :valign "center"
          (label :class "icon-lg nf-win c-mauve" :halign "center" :text "\uf2d2"))))

    (box :class "divider" :halign "center")

    ;; Middle: Workspaces 1-6 + Layout Toggle
    (box :class "section"
         :orientation "v"
         :halign "center"
         :space-evenly false
      (box :orientation "v" :space-evenly false
        (for ws in {bspwm_state.desktops}
          (button :class "ws-hit"
                  :onclick "bspc desktop -f '^${ws.num}'"
            (box :class "ws-pill ${ws.focused ? 'focused' : (ws.urgent ? 'urgent' : (ws.occupied ? 'occupied' : 'empty'))}"
                 :orientation "h"
                 :halign "fill"
                 :valign "center"
                 :hexpand true
              (box :halign "center" :valign "center" :hexpand true :space-evenly false :spacing 6
                (label :class "ws-num" :text {ws.num})
                (box :visible {ws.occupied && !ws.focused} :class "ws-dot" :valign "center"))))))
      (button :class "hit-btn"
              :onclick "bspc desktop -l next"
        (box :class "pill pill-std" :orientation "v" :halign "center" :valign "center" :space-evenly false :spacing 2
          (label :class "icon-md nf-layout ${bspwm_state.layout == 'M' ? 'c-mauve' : 'c-subtext'}"
                 :halign "center"
                 :text {bspwm_state.layout == "M" ? "\U000f056e" : "\U000f0573"})
          (label :class "subtext" :halign "center" :text {bspwm_state.layout}))))

    (button :class "drawer-toggle-hit"
            :vexpand true
            :hexpand true
            :onclick "~/.config/eww/scripts/toggle_window.sh widget_drawer widgets_open &"
      (box :class "swipe-zone" :orientation "v" :vexpand true :halign "center" :valign "center" :space-evenly false :spacing 6
        (label :class "swipe-chev ${widgets_open ? 'c-blue' : 'c-subtext'}"
               :text {widgets_open ? "\U000f0141" : "\U000f0142"})
        (box :class "swipe-pill ${widgets_open ? 'swipe-pill-open' : ''}" :halign "center")))

    (box :class "divider" :halign "center")

    ;; Bottom: Window Controls + Audio + Session Power
    (box :class "section"
         :orientation "v"
         :halign "center"
         :space-evenly false
      (button :class "hit-btn"
              :onclick "bspc node -t ~floating"
        (box :class "pill pill-std" :orientation "v" :halign "center" :valign "center"
          (label :class "icon-win nf-float c-text" :halign "center" :text "\uf2d0")))
      (button :class "hit-btn"
              :onclick "bspc node -t ~fullscreen"
        (box :class "pill pill-std" :orientation "v" :halign "center" :valign "center"
          (label :class "icon-win nf-full c-text" :halign "center" :text "\uf065")))
      (button :class "hit-btn"
              :onclick "bspc node -c"
        (box :class "pill pill-std" :orientation "v" :halign "center" :valign "center"
          (label :class "icon-close c-red" :halign "center" :text "\uf00d")))

      (box :class "divider" :halign "center")

      (button :class "hit-btn"
              :onclick "pactl set-sink-volume @DEFAULT_SINK@ +5% && eww update audio_state=\\"$(~/.config/eww/scripts/audio_state.sh)\\""
        (box :class "pill pill-sm" :orientation "v" :halign "center" :valign "center"
          (label :class "icon-md nf-md c-text" :halign "center" :text "\U000f0415")))
      (button :class "hit-btn"
              :onclick "pactl set-sink-mute @DEFAULT_SINK@ toggle && eww update audio_state=\\"$(~/.config/eww/scripts/audio_state.sh)\\""
        (box :class "pill pill-std pill-vol" :orientation "v" :halign "center" :valign "center" :space-evenly false :spacing 0
          (label :class "icon-vol nf-md ${audio_state.muted ? 'c-red' : 'c-green'}"
                 :halign "center"
                 :text {audio_state.muted ? "\U000f075f" : "\U000f057e"})
          (label :class "subtext vol-pct" :halign "center" :text {audio_state.muted ? "MUTE" : "${audio_state.pct}%"})))
      (button :class "hit-btn"
              :onclick "pactl set-sink-volume @DEFAULT_SINK@ -5% && eww update audio_state=\\"$(~/.config/eww/scripts/audio_state.sh)\\""
        (box :class "pill pill-sm" :orientation "v" :halign "center" :valign "center"
          (label :class "icon-md nf-md c-text" :halign "center" :text "\U000f0374")))

      (button :class "hit-btn"
              :onclick "~/.config/eww/scripts/toggle_window.sh session_menu session_open &"
        (box :class "pill pill-pwr ${session_open ? 'pwr-open' : ''}" :orientation "v" :halign "center" :valign "center"
          (label :class "icon-close nf-pwr ${session_open ? 'c-dark' : 'c-red'}" :halign "center" :text "\uf011")))))))

(defwidget session_content []
  (box :class "popup-bg"
       :orientation "v"
       :space-evenly false
    (button :class "pop-hit"
            :onclick "~/.config/eww/scripts/toggle_window.sh close session_menu session_open; ~/.config/polybar/launch.sh & ~/.config/eww/launch.sh &"
      (box :class "pop-pill" :orientation "h" :halign "fill" :valign "center" :space-evenly false :spacing 16
        (label :class "pop-icon c-blue" :halign "center" :text "\uf021")
        (label :class "pop-label c-text" :text "Reload Bars")))
    (button :class "pop-hit"
            :onclick "~/.config/eww/scripts/toggle_window.sh close session_menu session_open; bspc wm -r"
      (box :class "pop-pill" :orientation "h" :halign "fill" :valign "center" :space-evenly false :spacing 16
        (label :class "pop-icon c-teal" :halign "center" :text "\uf021")
        (label :class "pop-label c-text" :text "Restart WM")))
    (button :class "pop-hit"
            :onclick "~/.config/eww/scripts/toggle_window.sh close session_menu session_open; bspc quit"
      (box :class "pop-pill" :orientation "h" :halign "fill" :valign "center" :space-evenly false :spacing 16
        (label :class "pop-icon nf-pwr c-red" :halign "center" :text "\uf011")
        (label :class "pop-label c-text" :text "Exit X11")))))

(defwidget cal_cell [day cls]
  (box :class "cal-cell ${cls}" :halign "center" :valign "center" :hexpand true
    (label :class "cal-num" :text day)))

(defwidget widgets_content []
  (box :class "drawer-bg"
       :orientation "v"
       :space-evenly false
       :vexpand true
       :spacing 20

    ;; Header
    (box :orientation "h" :halign "fill" :space-evenly false
      (box :orientation "h" :halign "start" :hexpand true :space-evenly false :spacing 14
        (label :class "drawer-title-icon c-blue" :text "\U000f003b")
        (label :class "drawer-title c-text" :text "Widgets"))
      (button :class "drawer-close"
              :onclick "~/.config/eww/scripts/toggle_window.sh close widget_drawer widgets_open &"
        (box :class "drawer-close-pill" :halign "center" :valign "center"
          (label :class "c-subtext" :text "\uf00d"))))

    ;; Quick Widget Spaces Row (Weather + Focus mockups)
    (box :orientation "h" :spacing 18 :halign "fill"
      (box :class "card card-sm" :orientation "v" :space-evenly false :spacing 8 :hexpand true
        (box :orientation "h" :space-evenly false :spacing 12
          (label :class "w-icon c-peach" :text "\U000f0599")
          (label :class "w-val c-text" :text "22°C"))
        (label :class "w-sub c-subtext" :halign "start" :text "Clear Sky · Feels 21°C"))
      (box :class "card card-sm" :orientation "v" :space-evenly false :spacing 8 :hexpand true
        (box :orientation "h" :space-evenly false :spacing 12
          (label :class "w-icon c-teal" :text "\U000f05a9")
          (label :class "w-val c-text" :text "Termux"))
        (label :class "w-sub c-subtext" :halign "start" :text "Do Not Disturb · On")))

    ;; Spotify Card Space (Mockup)
    (box :class "card" :orientation "v" :space-evenly false :spacing 18
      (box :orientation "h" :space-evenly false :spacing 20
        (box :class "sp-art" :halign "center" :valign "center"
          (label :class "sp-art-icon c-green" :halign "center" :text "\U000f04c7"))
        (box :orientation "v" :valign "center" :hexpand true :space-evenly false :spacing 6
          (label :class "sp-kicker c-green" :halign "start" :text "NOW PLAYING")
          (label :class "sp-title c-text" :halign "start" :text "Midnight City")
          (label :class "sp-artist c-subtext" :halign "start" :text "M83 · Hurry Up, We're Dreaming")))
      (box :orientation "v" :space-evenly false :spacing 8
        (box :class "sp-track" :orientation "h" :space-evenly false
          (box :class "sp-fill"))
        (box :orientation "h" :halign "fill"
          (label :class "sp-time c-subtext" :halign "start" :text "1:42")
          (label :class "sp-time c-subtext" :halign "end" :text "3:55")))
      (box :orientation "h" :halign "center" :spacing 40 :space-evenly false
        (label :class "sp-ctrl c-subtext" :text "\U000f04ae")
        (box :class "sp-play" :halign "center" :valign "center"
          (label :class "sp-play-icon c-dark" :halign "center" :text "\U000f03e4"))
        (label :class "sp-ctrl c-subtext" :text "\U000f04ad")))

    ;; Calendar Space (Mockup)
    (box :class "card" :orientation "v" :space-evenly false :spacing 14
      (box :orientation "h" :halign "fill" :space-evenly false
        (box :orientation "h" :halign "start" :hexpand true :space-evenly false :spacing 12
          (label :class "cal-icon c-blue" :text "\U000f00ed")
          (label :class "cal-month c-text" :text "November 2026"))
        (label :class "cal-chev c-subtext" :text "\U000f0141   \U000f0142"))
      (box :orientation "h" :halign "fill" :spacing 6
        (cal_cell :day "Mo" :cls "cal-hdr")
        (cal_cell :day "Tu" :cls "cal-hdr")
        (cal_cell :day "We" :cls "cal-hdr")
        (cal_cell :day "Th" :cls "cal-hdr")
        (cal_cell :day "Fr" :cls "cal-hdr")
        (cal_cell :day "Sa" :cls "cal-hdr")
        (cal_cell :day "Su" :cls "cal-hdr"))
      (box :orientation "h" :halign "fill" :spacing 6
        (cal_cell :day "2" :cls "")
        (cal_cell :day "3" :cls "")
        (cal_cell :day "4" :cls "")
        (cal_cell :day "5" :cls "")
        (cal_cell :day "6" :cls "")
        (cal_cell :day "7" :cls "cal-wknd")
        (cal_cell :day "8" :cls "cal-wknd"))
      (box :orientation "h" :halign "fill" :spacing 6
        (cal_cell :day "9" :cls "")
        (cal_cell :day "10" :cls "")
        (cal_cell :day "11" :cls "")
        (cal_cell :day "12" :cls "")
        (cal_cell :day "13" :cls "")
        (cal_cell :day "14" :cls "cal-wknd")
        (cal_cell :day "15" :cls "cal-wknd"))
      (box :orientation "h" :halign "fill" :spacing 6
        (cal_cell :day "16" :cls "")
        (cal_cell :day "17" :cls "cal-today")
        (cal_cell :day "18" :cls "")
        (cal_cell :day "19" :cls "")
        (cal_cell :day "20" :cls "")
        (cal_cell :day "21" :cls "cal-wknd")
        (cal_cell :day "22" :cls "cal-wknd"))
      (box :orientation "h" :halign "fill" :spacing 6
        (cal_cell :day "23" :cls "")
        (cal_cell :day "24" :cls "")
        (cal_cell :day "25" :cls "")
        (cal_cell :day "26" :cls "")
        (cal_cell :day "27" :cls "")
        (cal_cell :day "28" :cls "cal-wknd")
        (cal_cell :day "29" :cls "cal-wknd"))
      (box :orientation "h" :halign "fill" :spacing 6
        (cal_cell :day "30" :cls "")
        (cal_cell :day "1" :cls "cal-muted")
        (cal_cell :day "2" :cls "cal-muted")
        (cal_cell :day "3" :cls "cal-muted")
        (cal_cell :day "4" :cls "cal-muted")
        (cal_cell :day "5" :cls "cal-muted")
        (cal_cell :day "6" :cls "cal-muted")))

    ;; Agenda / Notes Space (Mockup)
    (box :class "card" :orientation "v" :vexpand true :space-evenly false :spacing 14
      (box :orientation "h" :space-evenly false :spacing 12
        (label :class "cal-icon c-mauve" :text "\U000f039a")
        (label :class "cal-month c-text" :text "Agenda"))
      (box :class "note-row" :orientation "h" :space-evenly false :spacing 16
        (label :class "note-time c-blue" :text "19:00")
        (label :class "note-item c-text" :halign "start" :text "Build Termux X11 Dock"))
      (box :class "note-row" :orientation "h" :space-evenly false :spacing 16
        (label :class "note-time c-mauve" :text "21:30")
        (label :class "note-item c-text" :halign "start" :text "Sync Dotfiles & GUI Rules"))
      (box :class "note-row" :orientation "h" :space-evenly false :spacing 16
        (label :class "note-time c-teal" :text "22:45")
        (label :class "note-item c-text" :halign "start" :text "Wrap Up Workspace Widgets")))))

(defwindow dock
  :monitor 0
  :geometry (geometry :x "0px"
                      :y "80px"
                      :width "128px"
                      :height "94%"
                      :anchor "top left")
  :stacking "fg"
  :windowtype "dock"
  :wm-ignore false
  :reserve (struts :distance "128px" :side "left")
  (dock_content))

(defwindow session_menu
  :monitor 0
  :geometry (geometry :x "140px"
                      :y "0px"
                      :width "330px"
                      :height "368px"
                      :anchor "bottom left")
  :stacking "overlay"
  :windowtype "dialog"
  :wm-ignore true
  :focusable false
  (session_content))

(defwindow widget_drawer
  :monitor 0
  :geometry (geometry :x "140px"
                      :y "80px"
                      :width "844px"
                      :height "94%"
                      :anchor "top left")
  :stacking "overlay"
  :windowtype "dialog"
  :wm-ignore true
  :focusable false
  (widgets_content))
"""

EWW_SCSS = """$base: rgba(30, 30, 46, 0.90);
$popup-base: rgba(30, 30, 46, 0.95);
$surface: #313244;
$surface1: #45475a;
$text: #cdd6f4;
$subtext: #a6adc8;
$blue: #89b4fa;
$mauve: #cba6f7;
$teal: #94e2d5;
$green: #a6e3a1;
$peach: #fab387;
$red: #f38ba8;
$dark: #1e1e2e;

* {
  all: unset;
  font-family: "JetBrainsMono Nerd Font";
}

window {
  background-color: transparent;
}

.dock-bg {
  margin-left: 12px;
  border-radius: 24px;
  background-color: $base;
  border: 2px solid $surface;
}

.popup-bg {
  margin-bottom: 36px;
  padding: 9px 0px;
  border-radius: 22px;
  background-color: $popup-base;
  border: 2px solid $surface1;
}

.dock-fg {
  padding-top: 6px;
  padding-bottom: 6px;
}

.divider {
  min-width: 60px;
  min-height: 2px;
  margin-left: 12px;
  margin-top: 4px;
  margin-bottom: 4px;
  border-radius: 1px;
  background-color: $surface1;
}

/* Transparent padded button containers for enlarged touch hitboxes */
.hit-btn {
  padding: 6px 12px 6px 24px;
  background-color: transparent;
}

.ws-hit {
  padding: 7px 12px 7px 24px;
  background-color: transparent;
}

.pop-hit {
  padding: 9px 18px;
  background-color: transparent;
}

.pill {
  min-width: 92px;
  border-radius: 18px;
  background-color: $surface;
  transition: background-color 100ms ease;
}

.pill-tall {
  min-height: 66px;
}

.pill-std {
  min-height: 56px;
}

.pill-sm {
  min-height: 50px;
}

.pill-pwr {
  min-height: 62px;
}

.pwr-open {
  background-color: $red;
}

.ws-pill {
  min-width: 92px;
  min-height: 58px;
  border-radius: 18px;
  border: 1px solid transparent;
  transition: background-color 100ms ease;
}

.ws-pill.focused {
  background-color: $blue;
}

.ws-pill.urgent {
  background-color: $red;
}

.ws-pill.occupied {
  background-color: $surface;
  border-color: $surface1;
}

.ws-pill.empty {
  background-color: transparent;
}

.ws-num {
  font-size: 24px;
  color: $subtext;
}

.ws-pill.occupied .ws-num {
  font-weight: bold;
  color: $text;
}

.ws-pill.focused .ws-num,
.ws-pill.urgent .ws-num {
  font-weight: bold;
  color: $dark;
}

.ws-dot {
  min-width: 8px;
  min-height: 8px;
  border-radius: 99px;
  background-color: $blue;
}

.pop-pill {
  min-height: 86px;
  padding-left: 20px;
  padding-right: 20px;
  border-radius: 16px;
  background-color: $surface;
  transition: background-color 100ms ease;
}

/* Active press feedback only (no sticky :hover state on touchscreens) */
.hit-btn:active .pill,
.ws-hit:active .ws-pill,
.pop-hit:active .pop-pill {
  background-color: $blue;
}

.hit-btn:active label,
.ws-hit:active label,
.pop-hit:active label {
  color: $dark;
}

.icon-launcher { font-size: 34px; }
.icon-lg { font-size: 30px; }
.icon-close { font-size: 28px; }
.icon-win { font-size: 26px; }
.icon-md { font-size: 24px; }
.icon-vol { font-size: 25px; margin-bottom: -5px; }
.pill-vol { padding-top: 3px; }
.vol-pct { font-size: 14px; font-weight: bold; color: $subtext; padding-bottom: 1px; }
.subtext { font-size: 13px; font-weight: bold; color: $subtext; }

/* Compensate Nerd Font double-width glyph overflow past Pango's 1-cell advance */
.nf-apps { padding-right: 4px; }
.nf-term { padding-right: 13px; }
.nf-win { padding-right: 10px; }
.nf-layout { padding-right: 4px; }
.nf-float { padding-right: 8px; }
.nf-full { padding-right: 5px; }
.nf-md { padding-right: 4px; }
.nf-pwr { padding-right: 6px; }

.pop-icon { min-width: 34px; font-size: 26px; }
.pop-label { font-size: 20px; font-weight: bold; }

.c-blue { color: $blue; }
.c-teal { color: $teal; }
.c-mauve { color: $mauve; }
.c-green { color: $green; }
.c-peach { color: $peach; }
.c-red { color: $red; }
.c-text { color: $text; }
.c-subtext { color: $subtext; }
.c-dark { color: $dark; }

/* Empty spacer drawer toggle handle */
.drawer-toggle-hit {
  background-color: transparent;
}

.swipe-zone {
  margin-left: 12px;
}

.swipe-chev {
  font-size: 16px;
}

.swipe-pill {
  min-width: 6px;
  min-height: 44px;
  border-radius: 99px;
  background-color: $surface1;
  transition: background-color 100ms ease;
}

.swipe-pill-open,
.drawer-toggle-hit:active .swipe-pill {
  background-color: $blue;
}

.drawer-toggle-hit:active .swipe-chev {
  color: $blue;
}

/* Exposed Widget Drawer & Mockup Cards */
.drawer-bg {
  min-width: 784px;
  padding: 22px 28px;
  border-radius: 24px;
  background-color: $popup-base;
  border: 2px solid $surface1;
}

.drawer-title-icon { font-size: 34px; }
.drawer-title { font-size: 28px; font-weight: bold; }

.drawer-close {
  background-color: transparent;
}

.drawer-close-pill {
  min-width: 54px;
  min-height: 54px;
  border-radius: 16px;
  background-color: $surface;
  font-size: 24px;
}

.drawer-close:active .drawer-close-pill {
  background-color: $blue;
}

.drawer-close:active label {
  color: $dark;
}

.card {
  padding: 22px 24px;
  border-radius: 20px;
  background-color: $surface;
  border: 1px solid $surface1;
}

.card-sm {
  padding: 20px 22px;
}

.w-icon { font-size: 38px; padding-right: 4px; }
.w-val { font-size: 32px; font-weight: bold; }
.w-sub { font-size: 21px; }

.sp-art {
  min-width: 112px;
  min-height: 112px;
  border-radius: 18px;
  background-color: $surface1;
}

.sp-art-icon {
  font-size: 54px;
  padding-right: 6px;
}

.sp-kicker { font-size: 16px; font-weight: bold; }
.sp-title { font-size: 27px; font-weight: bold; }
.sp-artist { font-size: 22px; }

.sp-track {
  min-height: 10px;
  border-radius: 99px;
  background-color: $surface1;
}

.sp-fill {
  min-width: 340px;
  min-height: 10px;
  border-radius: 99px;
  background-color: $green;
}

.sp-time { font-size: 19px; font-weight: bold; }
.sp-ctrl { font-size: 32px; }

.sp-play {
  min-width: 62px;
  min-height: 62px;
  border-radius: 99px;
  background-color: $green;
}

.sp-play-icon {
  font-size: 30px;
  padding-right: 2px;
}

.cal-icon { font-size: 28px; padding-right: 4px; }
.cal-month { font-size: 24px; font-weight: bold; }
.cal-chev { font-size: 24px; }

.cal-cell {
  min-width: 68px;
  min-height: 46px;
  border-radius: 14px;
}

.cal-num {
  font-size: 23px;
  color: $text;
}

.cal-hdr .cal-num {
  font-size: 21px;
  font-weight: bold;
  color: $subtext;
}

.cal-wknd .cal-num {
  color: $subtext;
}

.cal-muted .cal-num {
  color: $surface1;
}

.cal-today {
  background-color: $blue;
}

.cal-today .cal-num {
  font-weight: bold;
  color: $dark;
}

.note-row {
  padding: 12px 16px;
  border-radius: 14px;
  background-color: $popup-base;
  border: 1px solid $surface1;
}

.note-time { font-size: 21px; font-weight: bold; }
.note-item { font-size: 21px; }
"""

QUICKSHELL_LAUNCH = """#!/data/data/com.termux/files/usr/bin/sh

export BSPWM_SOCKET="${BSPWM_SOCKET:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}/bspwm_0_0-socket}"
export XCURSOR_THEME="${XCURSOR_THEME:-TouchDot-Mocha}"
export XCURSOR_SIZE="${XCURSOR_SIZE:-32}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}}"
export GALLIUM_DRIVER="${GALLIUM_DRIVER:-virpipe}"

# Wait briefly for VirGL socket on cold X11 startup, then use GPU OpenGL RHI (-> ANGLE -> Vulkan)
if pgrep -x virgl_test_serv >/dev/null 2>&1; then
  i=0
  while [ "$i" -lt 20 ] && [ ! -S "$XDG_RUNTIME_DIR/.virgl_test" ]; do
    i=$((i + 1))
    sleep 0.05
  done
fi

if [ -S "$XDG_RUNTIME_DIR/.virgl_test" ]; then
  unset QT_QUICK_BACKEND
  export QSG_RHI_BACKEND="${QSG_RHI_BACKEND:-opengl}"
  # Mesa virpipe is not thread-safe across concurrent Qt Quick render threads
  export QSG_RENDER_LOOP="${QSG_RENDER_LOOP:-basic}"
else
  export QT_QUICK_BACKEND="${QT_QUICK_BACKEND:-software}"
fi

[ -f "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/qs-watch.pid" ] && kill "$(cat "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/qs-watch.pid")" 2>/dev/null || true
rm -f "${TMPDIR:-/data/data/com.termux/files/usr/tmp}/qs-watch.pid"

pkill -x quickshell 2>/dev/null || true
while pgrep -u "$(id -u)" -x quickshell >/dev/null 2>&1; do
  sleep 0.2
done
pkill -f "qs-native (media-stream|submenu-watch|sys-diag|wl-workspaces)" 2>/dev/null || true

LOG="${TMPDIR:-/data/data/com.termux/files/usr/tmp}/quickshell.log"
quickshell >> "$LOG" 2>&1 &
bspc config left_padding 128 >/dev/null 2>&1 || true
"""

QUICKSHELL_WAYLAND_LAUNCH = """#!/data/data/com.termux/files/usr/bin/sh

export QT_QPA_PLATFORM=wayland
export QT_QUICK_BACKEND=software
export XCURSOR_THEME="${XCURSOR_THEME:-TouchDot-Mocha}"
export XCURSOR_SIZE="${XCURSOR_SIZE:-32}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/data/data/com.termux/files/usr/tmp}}"

# Match nested wlroots X11-1 window to the full outer Termux:X11 display size
if [ "${WLR_BACKENDS:-x11}" = "x11" ]; then
  python3 - <<'PY' >/dev/null 2>&1 || true
import os, subprocess
from ctypes import CDLL, POINTER, Structure, byref, c_int, c_long, c_uint, c_ulong, c_void_p

class XWA(Structure):
    _fields_ = [
        ("x", c_int), ("y", c_int), ("width", c_int), ("height", c_int),
        ("border_width", c_int), ("depth", c_int), ("visual", c_void_p),
        ("root", c_ulong), ("c_class", c_int), ("bit_gravity", c_int),
        ("win_gravity", c_int), ("backing_store", c_int),
        ("backing_planes", c_long), ("backing_pixel", c_long),
        ("save_under", c_int), ("colormap", c_ulong), ("map_installed", c_int),
        ("map_state", c_int), ("all_event_masks", c_long), ("your_event_mask", c_long),
        ("do_not_propagate_mask", c_long), ("override_redirect", c_int), ("screen", c_void_p),
    ]

disp = os.environ.get("TERMUX_X11_DISPLAY") or os.environ.get("DISPLAY") or ":0"
x11 = CDLL("libX11.so.6")
x11.XOpenDisplay.restype = c_void_p
dpy = x11.XOpenDisplay(disp.encode())
if dpy:
    x11.XDefaultRootWindow.restype = c_ulong
    x11.XDefaultRootWindow.argtypes = [c_void_p]
    x11.XGetWindowAttributes.argtypes = [c_void_p, c_ulong, POINTER(XWA)]
    x11.XQueryTree.argtypes = [c_void_p, c_ulong, POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_ulong)), POINTER(c_uint)]
    x11.XMoveResizeWindow.argtypes = [c_void_p, c_ulong, c_int, c_int, c_uint, c_uint]
    x11.XFree.argtypes = [c_void_p]
    x11.XFlush.argtypes = [c_void_p]
    x11.XCloseDisplay.argtypes = [c_void_p]
    root = x11.XDefaultRootWindow(dpy)
    ra = XWA()
    if x11.XGetWindowAttributes(dpy, root, byref(ra)) and ra.width > 0 and ra.height > 0:
        if os.environ.get("SWAYSOCK"):
            subprocess.run(["swaymsg", "output", "X11-1", "resolution", f"{ra.width}x{ra.height}"], check=False)
        else:
            r, p, ch, n = c_ulong(), c_ulong(), POINTER(c_ulong)(), c_uint()
            if x11.XQueryTree(dpy, root, byref(r), byref(p), byref(ch), byref(n)):
                try:
                    for i in range(n.value):
                        a = XWA()
                        if x11.XGetWindowAttributes(dpy, ch[i], byref(a)) and a.map_state == 2 and a.width == 1024 and a.height == 768:
                            x11.XMoveResizeWindow(dpy, ch[i], 0, 0, ra.width, ra.height)
                            x11.XFlush(dpy)
                finally:
                    if ch:
                        x11.XFree(ch)
    x11.XCloseDisplay(dpy)
PY
fi

pkill -x quickshell 2>/dev/null || true
while pgrep -u "$(id -u)" -x quickshell >/dev/null 2>&1; do
  sleep 0.2
done
pkill -f "qs-native (media-stream|submenu-watch|sys-diag|wl-workspaces)" 2>/dev/null || true

LOG="${TMPDIR:-/data/data/com.termux/files/usr/tmp}/quickshell-wayland.log"
quickshell -p "${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/wayland.qml" >> "$LOG" 2>&1 &
"""

QUICKSHELL_SUBMENU_WATCH_PY = """#!/data/data/com.termux/files/usr/bin/python3
\"\"\"Watch X11 clicks, focus changes, and foreign popups to auto-close Quickshell submenus.\"\"\"

import os
import select
import signal
import sys
import time
from ctypes import CDLL, POINTER, Structure, byref, c_char, c_int, c_long, c_ubyte, c_uint, c_ulong, c_void_p


class XWA(Structure):
    _fields_ = [
        ("x", c_int), ("y", c_int), ("width", c_int), ("height", c_int),
        ("border_width", c_int), ("depth", c_int), ("visual", c_void_p),
        ("root", c_ulong), ("c_class", c_int), ("bit_gravity", c_int),
        ("win_gravity", c_int), ("backing_store", c_int),
        ("backing_planes", c_long), ("backing_pixel", c_long),
        ("save_under", c_int), ("colormap", c_ulong), ("map_installed", c_int),
        ("map_state", c_int), ("all_event_masks", c_long), ("your_event_mask", c_long),
        ("do_not_propagate_mask", c_long), ("override_redirect", c_int), ("screen", c_void_p),
    ]


class XIEventMask(Structure):
    _fields_ = [("deviceid", c_int), ("mask_len", c_int), ("mask", POINTER(c_ubyte))]


def _point_in(px: int, py: int, rect) -> bool:
    x, y, w, h = rect
    return w > 0 and h > 0 and x <= px < x + w and y <= py < y + h


def _matches_rect(a, rect, tol: int = 16) -> bool:
    rx, ry, rw, rh = rect
    return rw > 0 and rh > 0 and abs(a.x - rx) <= tol and abs(a.y - ry) <= tol and abs(a.width - rw) <= tol and abs(a.height - rh) <= tol


def _has_foreign_popup(x11, dpy, root, own_rects) -> bool:
    r, p, ch, n = c_ulong(), c_ulong(), POINTER(c_ulong)(), c_uint()
    if not x11.XQueryTree(dpy, root, byref(r), byref(p), byref(ch), byref(n)):
        return False
    try:
        for i in range(n.value):
            a = XWA()
            if not x11.XGetWindowAttributes(dpy, ch[i], byref(a)) or a.map_state != 2:
                continue
            if a.override_redirect == 1 and a.width >= 200 and a.height >= 150:
                if not any(_matches_rect(a, rect) for rect in own_rects):
                    return True
    finally:
        if ch:
            x11.XFree(ch)
    return False


def main() -> int:
    # Args: dock_w dock_h sub_x sub_y sub_w sub_h
    args = [int(float(v)) for v in sys.argv[1:7]] if len(sys.argv) >= 7 else [128, 1508, 140, 80, 844, 1508]
    dock_w, dock_h, sub_x, sub_y, sub_w, sub_h = args
    dock_rect = (0, 80, dock_w, dock_h)
    sub_rect = (sub_x, sub_y, sub_w, sub_h)
    own_rects = [dock_rect, sub_rect]

    x11 = CDLL("libX11.so.6")
    xi = CDLL("libXi.so")

    x11.XOpenDisplay.restype = c_void_p
    x11.XOpenDisplay.argtypes = [c_void_p]
    x11.XDefaultRootWindow.restype = c_ulong
    x11.XDefaultRootWindow.argtypes = [c_void_p]
    x11.XConnectionNumber.restype = c_int
    x11.XConnectionNumber.argtypes = [c_void_p]
    x11.XPending.restype = c_int
    x11.XPending.argtypes = [c_void_p]
    x11.XNextEvent.argtypes = [c_void_p, c_void_p]
    x11.XFlush.argtypes = [c_void_p]
    x11.XQueryTree.restype = c_int
    x11.XQueryTree.argtypes = [c_void_p, c_ulong, POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_ulong)), POINTER(c_uint)]
    x11.XGetWindowAttributes.restype = c_int
    x11.XGetWindowAttributes.argtypes = [c_void_p, c_ulong, POINTER(XWA)]
    x11.XGetInputFocus.argtypes = [c_void_p, POINTER(c_ulong), POINTER(c_int)]
    x11.XQueryPointer.restype = c_int
    x11.XQueryPointer.argtypes = [
        c_void_p, c_ulong, c_void_p, c_void_p,
        c_void_p, c_void_p, c_void_p, c_void_p, c_void_p,
    ]
    x11.XFree.argtypes = [c_void_p]
    x11.XCloseDisplay.argtypes = [c_void_p]

    xi.XIQueryVersion.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
    xi.XISelectEvents.argtypes = [c_void_p, c_ulong, POINTER(XIEventMask), c_int]

    dpy = x11.XOpenDisplay(os.environ.get("DISPLAY", ":0").encode())
    if not dpy:
        return 1
    root = x11.XDefaultRootWindow(dpy)
    xfd = x11.XConnectionNumber(dpy)

    maj, minv = c_int(2), c_int(2)
    xi.XIQueryVersion(dpy, byref(maj), byref(minv))

    # XIAllMasterDevices = 1; XI_RawButtonPress = 15 (1 << 15 -> byte 1 bit 7 = 0x80)
    ev_mask = (c_ubyte * 4)(0, 0x80, 0, 0)
    em = XIEventMask(deviceid=1, mask_len=4, mask=ev_mask)
    xi.XISelectEvents(dpy, root, byref(em), 1)
    x11.XFlush(dpy)

    running = True

    def stop(_sig, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    pid_path = os.path.join(
        os.environ.get("TMPDIR", "/data/data/com.termux/files/usr/tmp"),
        "qs-watch.pid",
    )
    try:
        with open(pid_path, "w") as pf:
            pf.write(str(os.getpid()))
    except OSError:
        pid_path = ""

    focus_win, revert_to = c_ulong(), c_int()
    x11.XGetInputFocus(dpy, byref(focus_win), byref(revert_to))
    initial_focus = focus_win.value

    r_win, c_win = c_ulong(), c_ulong()
    rx, ry, wx, wy = c_int(), c_int(), c_int(), c_int()
    mask = c_uint()
    ev_buf = (c_char * 192)()
    start_t = time.monotonic()

    while running:
        readable, _, _ = select.select([xfd], [], [], 0.12)
        clicked = False
        if readable:
            while x11.XPending(dpy) > 0:
                x11.XNextEvent(dpy, ev_buf)
                clicked = True

        x11.XGetInputFocus(dpy, byref(focus_win), byref(revert_to))
        if (focus_win.value != initial_focus and focus_win.value not in (0, 1)) or _has_foreign_popup(x11, dpy, root, own_rects):
            print("CLOSE", flush=True)
            break

        if clicked and (time.monotonic() - start_t) >= 0.08:
            if x11.XQueryPointer(dpy, root, byref(r_win), byref(c_win), byref(rx), byref(ry), byref(wx), byref(wy), byref(mask)):
                px, py = rx.value, ry.value
                in_sub = _point_in(px, py, sub_rect)
                in_dock = _point_in(px, py, dock_rect)
                on_toggle = in_dock and (
                    (80 + int(dock_h * 0.45) <= py <= 80 + int(dock_h * 0.70))
                    or (py >= 80 + dock_h - 90)
                )
                if not in_sub and not on_toggle:
                    print("CLOSE", flush=True)
                    break

    if pid_path:
        try:
            os.remove(pid_path)
        except OSError:
            pass
    x11.XCloseDisplay(dpy)
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

QUICKSHELL_SYS_DIAG_PY = """#!/data/data/com.termux/files/usr/bin/python3
\"\"\"Stream CPU, RAM, battery/thermal, and Wi-Fi diagnostics as JSON lines for Quickshell.\"\"\"

import json
import os
import shutil
import signal
import subprocess
import sys
import time


def _total_jiffies() -> int:
    total = 0
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat") as f:
                data = f.read()
            rp = data.rfind(")")
            if rp < 0:
                continue
            fields = data[rp + 2 :].split()
            total += int(fields[11]) + int(fields[12])
        except (OSError, IndexError, ValueError):
            pass
    return total


def _mem_info() -> tuple[str, str, int]:
    vals = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, _, rest = line.partition(":")
                if k in ("MemTotal", "MemAvailable", "MemFree"):
                    parts = rest.strip().split()
                    if parts:
                        vals[k] = int(parts[0])
    except OSError:
        return "0.0", "0.0", 0
    tot_kb = vals.get("MemTotal", 0)
    avail_kb = vals.get("MemAvailable", vals.get("MemFree", 0))
    if tot_kb <= 0:
        return "0.0", "0.0", 0
    used_kb = max(0, tot_kb - avail_kb)
    pct = min(100, max(0, round(used_kb / tot_kb * 100)))
    return f"{used_kb / 1048576:.1f}", f"{tot_kb / 1048576:.1f}", pct


def _run_json(cmd: list[str], timeout_s: float = 2.0) -> dict | None:
    if not shutil.which(cmd[0]):
        return None
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return None


def main() -> int:
    running = True

    def stop(_sig, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    clk = os.sysconf("SC_CLK_TCK")
    ncpu = os.cpu_count() or 1
    j_prev = _total_jiffies()
    t_prev = time.monotonic()

    bat = {"bat_pct": -1, "bat_status": "UNKNOWN", "temp_c": None, "watts": ""}
    wifi = {"wifi_ok": False, "wifi_rate": 0, "wifi_rssi": 0, "ip": ""}

    time.sleep(0.25)
    tick = 0
    while running:
        j_now = _total_jiffies()
        t_now = time.monotonic()
        dt = max(0.05, t_now - t_prev)
        cpu_pct = min(100, max(0, round(((j_now - j_prev) / clk) / (dt * ncpu) * 100.0)))
        j_prev, t_prev = j_now, t_now

        mem_used, mem_total, mem_pct = _mem_info()

        # Refresh Termux:API battery & Wi-Fi every ~12s (and immediately on tick 0)
        if tick % 6 == 0:
            bdata = _run_json(["termux-battery-status"])
            if bdata:
                bat["bat_pct"] = int(bdata.get("percentage", -1))
                bat["bat_status"] = str(bdata.get("status", "UNKNOWN")).upper()
                if "temperature" in bdata:
                    try:
                        bat["temp_c"] = round(float(bdata["temperature"]), 1)
                    except (TypeError, ValueError):
                        pass
                try:
                    mv = float(bdata.get("voltage", 0))
                    ua = float(bdata.get("current", 0))
                    w = (mv / 1000.0) * (ua / 1_000_000.0)
                    bat["watts"] = f"{w:+.1f}W" if abs(w) >= 0.1 else ""
                except (TypeError, ValueError):
                    bat["watts"] = ""

            wdata = _run_json(["termux-wifi-connectioninfo"])
            if wdata:
                state = str(wdata.get("supplicant_state", "")).upper()
                wifi["wifi_ok"] = (state == "COMPLETED" and bool(wdata.get("ip")))
                wifi["wifi_rate"] = int(wdata.get("link_speed_mbps", 0) or 0)
                wifi["wifi_rssi"] = int(wdata.get("rssi", 0) or 0)
                wifi["ip"] = str(wdata.get("ip", "") or "")

        payload = {
            "cpu": cpu_pct,
            "mem_used": mem_used,
            "mem_total": mem_total,
            "mem_pct": mem_pct,
            **bat,
            **wifi,
        }
        print(json.dumps(payload), flush=True)

        tick += 1
        for _ in range(20):
            if not running:
                break
            time.sleep(0.1)

    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

QUICKSHELL_WL_WORKSPACES_PY = """#!/data/data/com.termux/files/usr/bin/python3
\"\"\"Stream and control ext_workspace_manager_v1 virtual desktops (LabWC) over Wayland wire protocol.\"\"\"

import json
import os
import select
import signal
import socket
import struct
import sys


def _pack_str(s: str) -> bytes:
    b = s.encode("utf-8") + b"\\x00"
    pad = (-len(b)) & 3
    return struct.pack("<I", len(b)) + b + (b"\\x00" * pad)


def _unpack_str(buf: bytes, off: int) -> tuple[str, int]:
    (slen,) = struct.unpack_from("<I", buf, off)
    raw = buf[off + 4 : off + 4 + max(0, slen - 1)]
    step = 4 + ((slen + 3) & ~3)
    return raw.decode("utf-8", errors="replace"), off + step


def _msg(obj_id: int, opcode: int, payload: bytes = b"") -> bytes:
    size = 8 + len(payload)
    return struct.pack("<II", obj_id, (size << 16) | opcode) + payload


def main() -> int:
    xdg = os.environ.get("XDG_RUNTIME_DIR", os.environ.get("TMPDIR", "/data/data/com.termux/files/usr/tmp"))
    wdisp = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
    sock_path = wdisp if os.path.isabs(wdisp) else os.path.join(xdg, wdisp)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(sock_path)

    # 1 = wl_display, 2 = wl_registry, 3 = initial sync callback
    sock.sendall(_msg(1, 1, struct.pack("<I", 2)) + _msg(1, 0, struct.pack("<I", 3)))

    mgr_id = 0
    mgr_ver = 1
    workspaces: dict[int, dict] = {}
    groups: set[int] = set()
    rx = bytearray()
    in_buf = ""
    running = True

    def stop(_sig, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def emit_state() -> None:
        by_num: dict[int, dict] = {}
        ordered = []
        for ws in workspaces.values():
            name = ws.get("name", "")
            st = ws.get("state", 0)
            if st & 4:  # hidden
                continue
            item = {
                "name": name,
                "focused": bool(st & 1),
                "urgent": bool(st & 2),
                "occupied": False,
            }
            ordered.append(item)
            if name.isdigit():
                by_num[int(name)] = item
        out = []
        if by_num:
            for n in range(1, 7):
                w = by_num.get(n)
                out.append({
                    "num": n,
                    "focused": w["focused"] if w else False,
                    "occupied": False,
                    "urgent": w["urgent"] if w else False,
                })
        else:
            for idx, w in enumerate(ordered[:6], 1):
                out.append({
                    "num": idx,
                    "focused": w["focused"],
                    "occupied": False,
                    "urgent": w["urgent"],
                })
        if out:
            print(json.dumps(out), flush=True)

    stdin_fd = sys.stdin.fileno()
    os.set_blocking(stdin_fd, False)

    while running:
        rlist, _, _ = select.select([sock, stdin_fd], [], [], 0.5)
        if sock in rlist:
            chunk = sock.recv(8192)
            if not chunk:
                break
            rx.extend(chunk)
            while len(rx) >= 8:
                obj_id, size_op = struct.unpack_from("<II", rx, 0)
                size = size_op >> 16
                op = size_op & 0xFFFF
                if size < 8 or len(rx) < size:
                    break
                payload = bytes(rx[8:size])
                del rx[:size]

                if obj_id == 2 and op == 0:  # wl_registry::global
                    (gname,) = struct.unpack_from("<I", payload, 0)
                    iface, off = _unpack_str(payload, 4)
                    (gver,) = struct.unpack_from("<I", payload, off)
                    if iface == "ext_workspace_manager_v1" and mgr_id == 0:
                        mgr_id = 4
                        mgr_ver = min(1, gver)
                        sock.sendall(_msg(2, 0, struct.pack("<I", gname) + _pack_str(iface) + struct.pack("<II", mgr_ver, mgr_id)))
                elif obj_id == mgr_id:
                    if op == 0:  # workspace_group(new_id)
                        (gid,) = struct.unpack_from("<I", payload, 0)
                        groups.add(gid)
                    elif op == 1:  # workspace(new_id)
                        (wid,) = struct.unpack_from("<I", payload, 0)
                        workspaces[wid] = {"name": "", "state": 0}
                    elif op == 2:  # done
                        emit_state()
                    elif op == 3:  # finished
                        running = False
                        break
                elif obj_id in workspaces:
                    if op == 1:  # name(string)
                        name, _ = _unpack_str(payload, 0)
                        workspaces[obj_id]["name"] = name
                    elif op == 3:  # state(uint)
                        (st,) = struct.unpack_from("<I", payload, 0)
                        workspaces[obj_id]["state"] = st
                    elif op == 5:  # removed
                        workspaces.pop(obj_id, None)

        if stdin_fd in rlist:
            try:
                data = os.read(stdin_fd, 1024)
            except BlockingIOError:
                data = b""
            if not data:
                break
            in_buf += data.decode("utf-8", errors="ignore")
            while "\\n" in in_buf:
                line, in_buf = in_buf.split("\\n", 1)
                target = line.strip()
                if not target or not mgr_id:
                    continue
                for wid, ws in workspaces.items():
                    if ws.get("name") == target:
                        # activate (opcode 1) + manager::commit (opcode 0)
                        sock.sendall(_msg(wid, 1) + _msg(mgr_id, 0))
                        break

    sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

QUICKSHELL_ANDROID_STATUS_PY = """#!/data/data/com.termux/files/usr/bin/python3
\"\"\"Probe Termux:API and Shizuku (rish / adbd) status and print one JSON object.\"\"\"

import concurrent.futures
import json
import os
import shutil
import socket
import subprocess
import sys
import time


def _getprop(name: str) -> str:
    try:
        res = subprocess.run(["getprop", name], capture_output=True, text=True, timeout=0.8)
        return res.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _tcp_open(host: str, port: int, timeout_s: float = 0.2) -> bool:
    sock = socket.socket()
    sock.settimeout(timeout_s)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _probe_termux_api() -> dict:
    bat_bin = shutil.which("termux-battery-status")
    ver = os.environ.get("TERMUX_API_VERSION", "")
    if not bat_bin:
        return {
            "api_ok": False,
            "api_state": "Missing",
            "api_ver": ver,
            "api_ms": 0,
            "api_detail": "Install termux-api pkg",
        }
    t0 = time.monotonic()
    try:
        res = subprocess.run([bat_bin], capture_output=True, text=True, timeout=2.5)
        ms = round((time.monotonic() - t0) * 1000)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            pct = data.get("percentage")
            temp = data.get("temperature")
            parts = []
            if pct is not None:
                parts.append(f"Bat {int(pct)}%")
            if temp is not None:
                parts.append(f"{float(temp):.1f}°C")
            parts.append(f"{ms}ms")
            return {
                "api_ok": True,
                "api_state": "Ready",
                "api_ver": ver,
                "api_ms": ms,
                "api_detail": " · ".join(parts),
            }
        return {
            "api_ok": False,
            "api_state": "Offline",
            "api_ver": ver,
            "api_ms": ms,
            "api_detail": "Open Termux:API app",
        }
    except subprocess.TimeoutExpired:
        return {
            "api_ok": False,
            "api_state": "Timeout",
            "api_ver": ver,
            "api_ms": 2500,
            "api_detail": "Bridge timed out (>2.5s)",
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {
            "api_ok": False,
            "api_state": "Offline",
            "api_ver": ver,
            "api_ms": 0,
            "api_detail": "Bridge error",
        }


def _probe_shizuku() -> dict:
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    dex_path = os.path.join(prefix, "share", "rish-shizuku.dex")
    adbd_svc = _getprop("init.svc.adbd") or "unknown"
    tcp_prop = _getprop("service.adb.tcp.port")
    adb_port = int(tcp_prop) if tcp_prop.isdigit() and int(tcp_prop) > 0 else 5555
    adb_tcp_open = _tcp_open("127.0.0.1", adb_port)

    if not os.path.exists(dex_path):
        detail = f"adbd {adbd_svc}" + (f" · :{adb_port} open" if adb_tcp_open else "")
        return {
            "shizuku_ok": False,
            "shizuku_state": "No rish",
            "shizuku_ver": "",
            "shizuku_uid": -1,
            "shizuku_pid": 0,
            "adb_tcp_open": adb_tcp_open,
            "adb_port": adb_port,
            "shizuku_detail": f"No rish · {detail}",
            "api_ver_pkg": "",
        }

    # Android 14+ aborts app_process if the dex file is writable by owner.
    try:
        mode = os.stat(dex_path).st_mode & 0o777
        if mode & 0o222:
            os.chmod(dex_path, 0o400)
    except OSError:
        pass

    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)
    env.pop("LD_PRELOAD", None)
    env["RISH_APPLICATION_ID"] = "com.termux"

    probe_cmd = (
        "echo UID:$(id -u); "
        "ps -A -o PID,NAME 2>/dev/null | grep -m1 shizuku_server | sed 's/^/SHZ_PS:/'; "
        "dumpsys package moe.shizuku.privileged.api 2>/dev/null | grep -m1 versionName= | sed 's/^/SHZ_VER:/'; "
        "dumpsys package com.termux.api 2>/dev/null | grep -m1 versionName= | sed 's/^/API_VER:/'"
    )
    app_proc = "/system/bin/app_process"
    if not os.path.exists(app_proc):
        app_proc = shutil.which("app_process") or "app_process"

    try:
        res = subprocess.run(
            [
                app_proc,
                f"-Djava.class.path={dex_path}",
                "/system/bin",
                "--nice-name=rish",
                "rikka.shizuku.shell.ShizukuShellLoader",
                "-c",
                probe_cmd,
            ],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=2.8,
        )
        out = (res.stdout or "") + "\\n" + (res.stderr or "")
    except subprocess.TimeoutExpired:
        detail = f"adbd {adbd_svc}" + (f" · :{adb_port}" if adb_tcp_open else "")
        return {
            "shizuku_ok": False,
            "shizuku_state": "Stopped",
            "shizuku_ver": "",
            "shizuku_uid": -1,
            "shizuku_pid": 0,
            "adb_tcp_open": adb_tcp_open,
            "adb_port": adb_port,
            "shizuku_detail": f"Timed out · {detail}",
            "api_ver_pkg": "",
        }
    except OSError as e:
        return {
            "shizuku_ok": False,
            "shizuku_state": "Error",
            "shizuku_ver": "",
            "shizuku_uid": -1,
            "shizuku_pid": 0,
            "adb_tcp_open": adb_tcp_open,
            "adb_port": adb_port,
            "shizuku_detail": str(e)[:42],
            "api_ver_pkg": "",
        }

    uid = -1
    pid = 0
    shizuku_ver = ""
    api_ver_pkg = ""
    for raw_line in out.splitlines():
        line = raw_line.strip()
        if line.startswith("UID:"):
            val = line[4:].strip()
            if val.isdigit():
                uid = int(val)
        elif line.startswith("SHZ_PS:") and "shizuku_server" in line:
            toks = line[7:].strip().split()
            if toks and toks[0].isdigit():
                pid = int(toks[0])
        elif line.startswith("SHZ_VER:") and "versionName=" in line:
            shizuku_ver = line.split("versionName=", 1)[1].strip()
        elif line.startswith("API_VER:") and "versionName=" in line:
            api_ver_pkg = line.split("versionName=", 1)[1].strip()

    if res.returncode == 0 and uid in (0, 2000):
        mode_lbl = "Root" if uid == 0 else "ADB"
        detail_parts = [f"UID {uid}"]
        if pid > 0:
            detail_parts.append(f"PID {pid}")
        if adb_tcp_open:
            detail_parts.append(f"TCP :{adb_port}")
        return {
            "shizuku_ok": True,
            "shizuku_state": f"Active · {mode_lbl}",
            "shizuku_ver": shizuku_ver,
            "shizuku_uid": uid,
            "shizuku_pid": pid,
            "adb_tcp_open": adb_tcp_open,
            "adb_port": adb_port,
            "shizuku_detail": " · ".join(detail_parts),
            "api_ver_pkg": api_ver_pkg,
        }

    low = out.lower()
    if "permission" in low or "denied" in low or "unauthorized" in low:
        state = "Denied"
        detail = "Grant Termux in Shizuku"
    else:
        state = "Stopped"
        detail = f"adbd {adbd_svc}" + (f" · :{adb_port} open" if adb_tcp_open else "")

    return {
        "shizuku_ok": False,
        "shizuku_state": state,
        "shizuku_ver": shizuku_ver,
        "shizuku_uid": uid,
        "shizuku_pid": pid,
        "adb_tcp_open": adb_tcp_open,
        "adb_port": adb_port,
        "shizuku_detail": detail,
        "api_ver_pkg": api_ver_pkg,
    }


def main() -> int:
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_api = pool.submit(_probe_termux_api)
        f_shz = pool.submit(_probe_shizuku)
        api = f_api.result()
        shz = f_shz.result()
    if shz.get("api_ver_pkg") and not api.get("api_ver"):
        api["api_ver"] = shz["api_ver_pkg"]
    shz.pop("api_ver_pkg", None)
    print(json.dumps({**api, **shz}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

_QS_ANDROID_STATUS_PROPS = """    property bool androidProbing: false
    property bool termuxApiOk: false
    property string termuxApiState: "Checking..."
    property string termuxApiVer: ""
    property string termuxApiDetail: "Probing Termux:API..."
    property bool shizukuOk: false
    property string shizukuState: "Checking..."
    property string shizukuVer: ""
    property string shizukuDetail: "Probing Shizuku..."
"""

_QS_ANDROID_STATUS_FN = """    function refreshAndroidStatus() {
        if (!androidStatusProc.running) {
            root.androidProbing = true;
            androidStatusProc.running = true;
        }
    }
"""

_QS_ANDROID_STATUS_PROCS = """    Process {
        id: androidStatusProc
        command: ["python3", Quickshell.env("HOME") + "/.config/quickshell/scripts/android_status.py"]
        running: false
        onRunningChanged: {
            if (!running) root.androidProbing = false;
        }
        stdout: StdioCollector {
            onStreamFinished: {
                root.androidProbing = false;
                try {
                    const d = JSON.parse((this.text || "").trim() || "{}");
                    if (d.api_ok !== undefined) root.termuxApiOk = Boolean(d.api_ok);
                    if (d.api_state !== undefined) root.termuxApiState = String(d.api_state);
                    if (d.api_ver !== undefined) root.termuxApiVer = String(d.api_ver);
                    if (d.api_detail !== undefined) root.termuxApiDetail = String(d.api_detail);
                    if (d.shizuku_ok !== undefined) root.shizukuOk = Boolean(d.shizuku_ok);
                    if (d.shizuku_state !== undefined) root.shizukuState = String(d.shizuku_state);
                    if (d.shizuku_ver !== undefined) root.shizukuVer = String(d.shizuku_ver);
                    if (d.shizuku_detail !== undefined) root.shizukuDetail = String(d.shizuku_detail);
                } catch (e) {}
            }
        }
    }

    Timer {
        interval: 1200
        running: true
        repeat: false
        onTriggered: root.refreshAndroidStatus()
    }

    Timer {
        interval: 15000
        running: root.widgetsOpen
        repeat: true
        onTriggered: root.refreshAndroidStatus()
    }

    Timer {
        id: androidDelayTimer
        interval: 700
        repeat: false
        onTriggered: root.refreshAndroidStatus()
    }
"""

_QS_ANDROID_STATUS_CARD = """                        // Termux:API & Shizuku Status Card
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: androidStatusCol.implicitHeight + 40
                            radius: 20
                            color: root.colSurface
                            border.color: root.colSurface1
                            border.width: 1

                            Column {
                                id: androidStatusCol
                                anchors.fill: parent
                                anchors.leftMargin: 24
                                anchors.rightMargin: 24
                                anchors.topMargin: 20
                                anchors.bottomMargin: 20
                                spacing: 14

                                RowLayout {
                                    width: parent.width
                                    Row {
                                        spacing: 12
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "\uf17b"
                                            color: (root.termuxApiOk && root.shizukuOk) ? root.colGreen : ((root.termuxApiOk || root.shizukuOk) ? root.colPeach : root.colRed)
                                            font.family: root.uiFont
                                            font.pixelSize: 28
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "Termux:API & Shizuku"
                                            color: root.colText
                                            font.family: root.uiFont
                                            font.pixelSize: 24
                                            font.bold: true
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Rectangle {
                                        implicitWidth: refreshRow.implicitWidth + 24
                                        height: 40
                                        radius: 12
                                        color: refreshBtnArea.pressed ? root.colBlue : root.colPopupBase
                                        border.color: root.colSurface1
                                        border.width: 1
                                        Row {
                                            id: refreshRow
                                            anchors.centerIn: parent
                                            spacing: 8
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: "\uf021"
                                                color: refreshBtnArea.pressed ? root.colDark : root.colBlue
                                                font.family: root.uiFont
                                                font.pixelSize: 18
                                            }
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: root.androidProbing ? "Checking" : "Refresh"
                                                color: refreshBtnArea.pressed ? root.colDark : root.colSubtext
                                                font.family: root.uiFont
                                                font.pixelSize: 18
                                                font.bold: true
                                            }
                                        }
                                        MouseArea {
                                            id: refreshBtnArea
                                            anchors.fill: parent
                                            onClicked: root.refreshAndroidStatus()
                                        }
                                    }
                                }

                                RowLayout {
                                    width: parent.width
                                    spacing: 14

                                    // Termux:API Tile
                                    Rectangle {
                                        Layout.fillWidth: true
                                        implicitHeight: apiTileCol.implicitHeight + 32
                                        radius: 16
                                        color: apiTileArea.pressed ? root.colSurface1 : root.colPopupBase
                                        border.color: root.termuxApiOk ? root.colGreen : root.colSurface1
                                        border.width: 1

                                        Column {
                                            id: apiTileCol
                                            anchors.fill: parent
                                            anchors.margins: 16
                                            spacing: 6

                                            RowLayout {
                                                width: parent.width
                                                Row {
                                                    spacing: 10
                                                    Rectangle {
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        width: 12
                                                        height: 12
                                                        radius: 6
                                                        color: root.termuxApiOk ? root.colGreen : (root.termuxApiState === "Missing" ? root.colRed : root.colPeach)
                                                    }
                                                    Text {
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        text: "Termux:API"
                                                        color: root.colText
                                                        font.family: root.uiFont
                                                        font.pixelSize: 21
                                                        font.bold: true
                                                    }
                                                }
                                                Item { Layout.fillWidth: true }
                                                Text {
                                                    visible: root.termuxApiVer.length > 0
                                                    text: "v" + root.termuxApiVer
                                                    color: root.colSubtext
                                                    font.family: root.uiFont
                                                    font.pixelSize: 17
                                                }
                                            }

                                            Text {
                                                width: parent.width
                                                elide: Text.ElideRight
                                                text: root.termuxApiState
                                                color: root.termuxApiOk ? root.colGreen : (root.termuxApiState === "Missing" ? root.colRed : root.colPeach)
                                                font.family: root.uiFont
                                                font.pixelSize: 23
                                                font.bold: true
                                            }

                                            Text {
                                                width: parent.width
                                                elide: Text.ElideRight
                                                text: root.termuxApiDetail
                                                color: root.colSubtext
                                                font.family: root.uiFont
                                                font.pixelSize: 18
                                            }
                                        }

                                        MouseArea {
                                            id: apiTileArea
                                            anchors.fill: parent
                                            onClicked: {
                                                root.runCmd(["sh", "-c", "termux-api-start >/dev/null 2>&1"]);
                                                androidDelayTimer.restart();
                                            }
                                        }
                                    }

                                    // Shizuku Tile
                                    Rectangle {
                                        Layout.fillWidth: true
                                        implicitHeight: shzTileCol.implicitHeight + 32
                                        radius: 16
                                        color: shzTileArea.pressed ? root.colSurface1 : root.colPopupBase
                                        border.color: root.shizukuOk ? root.colGreen : root.colSurface1
                                        border.width: 1

                                        Column {
                                            id: shzTileCol
                                            anchors.fill: parent
                                            anchors.margins: 16
                                            spacing: 6

                                            RowLayout {
                                                width: parent.width
                                                Row {
                                                    spacing: 10
                                                    Rectangle {
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        width: 12
                                                        height: 12
                                                        radius: 6
                                                        color: root.shizukuOk ? root.colGreen : (root.shizukuState === "No rish" ? root.colRed : root.colPeach)
                                                    }
                                                    Text {
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        text: "Shizuku"
                                                        color: root.colText
                                                        font.family: root.uiFont
                                                        font.pixelSize: 21
                                                        font.bold: true
                                                    }
                                                }
                                                Item { Layout.fillWidth: true }
                                                Text {
                                                    visible: root.shizukuVer.length > 0
                                                    text: "v" + root.shizukuVer
                                                    color: root.colSubtext
                                                    font.family: root.uiFont
                                                    font.pixelSize: 17
                                                }
                                            }

                                            Text {
                                                width: parent.width
                                                elide: Text.ElideRight
                                                text: root.shizukuState
                                                color: root.shizukuOk ? root.colGreen : (root.shizukuState === "No rish" ? root.colRed : root.colPeach)
                                                font.family: root.uiFont
                                                font.pixelSize: 23
                                                font.bold: true
                                            }

                                            Text {
                                                width: parent.width
                                                elide: Text.ElideRight
                                                text: root.shizukuDetail
                                                color: root.colSubtext
                                                font.family: root.uiFont
                                                font.pixelSize: 18
                                            }
                                        }

                                        MouseArea {
                                            id: shzTileArea
                                            anchors.fill: parent
                                            onClicked: root.refreshAndroidStatus()
                                        }
                                    }
                                }
                            }
                        }
"""

QUICKSHELL_MEDIA_CONTROL_PY = """#!/data/data/com.termux/files/usr/bin/python3
\"\"\"Query and control Android MediaSession playback via rish (Shizuku).\"\"\"

import json
import os
import re
import shutil
import subprocess
import sys


def _rish_cmd() -> tuple[list[str], dict[str, str]] | tuple[None, None]:
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    dex_path = os.path.join(prefix, "share", "rish-shizuku.dex")
    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)
    env.pop("LD_PRELOAD", None)
    env["RISH_APPLICATION_ID"] = "com.termux"

    if os.path.exists(dex_path):
        try:
            if (os.stat(dex_path).st_mode & 0o777) & 0o222:
                os.chmod(dex_path, 0o400)
        except OSError:
            pass
        app_proc = "/system/bin/app_process"
        if not os.path.exists(app_proc):
            app_proc = shutil.which("app_process") or "app_process"
        return [
            app_proc,
            f"-Djava.class.path={dex_path}",
            "/system/bin",
            "--nice-name=rish",
            "rikka.shizuku.shell.ShizukuShellLoader",
            "-c",
        ], env

    rish_bin = shutil.which("rish")
    if rish_bin:
        return [rish_bin, "-c"], env
    return None, None


def _run_rish(shell_cmd: str, stdin_text: str = "", timeout_s: float = 2.8) -> tuple[int, str]:
    base, env = _rish_cmd()
    if not base:
        return 127, ""
    try:
        res = subprocess.run(
            base + [shell_cmd],
            env=env,
            input=stdin_text if stdin_text else None,
            stdin=None if stdin_text else subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return res.returncode, (res.stdout or "") + "\\n" + (res.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def _uptime_ms() -> int:
    try:
        with open("/proc/uptime") as f:
            first = f.read().split()[0]
        return int(float(first) * 1000.0)
    except (OSError, IndexError, ValueError):
        return 0


def _app_label(pkg: str) -> str:
    known = {
        "com.spotify.music": "Spotify",
        "com.spotify.lite": "Spotify Lite",
        "com.google.android.apps.youtube.music": "YT Music",
        "app.morphe.android.apps.youtube.music": "YT Music",
        "com.google.android.youtube": "YouTube",
        "app.revanced.android.youtube": "YouTube",
        "org.videolan.vlc": "VLC",
        "com.apple.android.music": "Apple Music",
    }
    if pkg in known:
        return known[pkg]
    parts = [p for p in pkg.split(".") if p and p not in ("com", "org", "app", "android", "apps", "music")]
    return parts[-1].capitalize() if parts else (pkg or "Media")


def _fmt_time(sec: int) -> str:
    sec = max(0, sec)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _parse_description(desc: str) -> tuple[str, str, str]:
    if not desc or desc == "null":
        return "", "", ""
    parts = [p.strip() for p in desc.split(", ")]
    clean = [("" if p == "null" else p) for p in parts]
    if len(clean) == 1:
        return clean[0], "", ""
    if len(clean) == 2:
        return clean[0], clean[1], ""
    album = clean[-1]
    artist = clean[-2]
    title = ", ".join(clean[:-2]).strip()
    return title, artist, album


def get_status() -> dict:
    rc, out = _run_rish("echo UPTIME:$(cat /proc/uptime 2>/dev/null); dumpsys media_session 2>/dev/null")
    if rc != 0:
        return {
            "available": False,
            "playing": False,
            "state": "SHIZUKU OFF",
            "package": "",
            "app": "Media Control",
            "tag": "",
            "title": "Shizuku inactive",
            "artist": "Start Shizuku to control media",
            "album": "",
            "pos_sec": 0,
            "pos_text": "--:--",
        }

    uptime_ms = 0
    for raw in out.splitlines():
        if raw.startswith("UPTIME:"):
            toks = raw[7:].strip().split()
            if toks:
                try:
                    uptime_ms = int(float(toks[0]) * 1000.0)
                except ValueError:
                    uptime_ms = 0
            break
    if uptime_ms <= 0:
        uptime_ms = _uptime_ms()

    btn_tag = ""
    btn_pkg = ""
    m_btn = re.search(r"Media button session is\\s+([^/\\s]+)/([^/\\s]+)/", out)
    if m_btn:
        btn_pkg, btn_tag = m_btn.group(1), m_btn.group(2)

    sessions = []
    in_stack = False
    cur = None
    for raw in out.splitlines():
        line = raw.rstrip("\\r\\n")
        if "Sessions Stack - have" in line:
            in_stack = True
            continue
        if not in_stack:
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if not stripped:
            continue
        if indent <= 2:
            break
        if indent == 4:
            if cur:
                sessions.append(cur)
            # Example: spotify-media-session com.spotify.music/spotify-media-session/485 (userId=0)
            m_hdr = re.match(r"^(.+?)\\s+([^/\\s]+)/([^/\\s]+)/\\d+\\s+\\(userId=", stripped)
            cur = {
                "tag": m_hdr.group(3) if m_hdr else stripped.split()[0],
                "package": m_hdr.group(2) if m_hdr else "",
                "active": False,
                "state_name": "NONE",
                "state_code": 0,
                "pos_ms": 0,
                "speed": 0.0,
                "updated_ms": 0,
                "title": "",
                "artist": "",
                "album": "",
            }
        elif cur and indent >= 6:
            if stripped.startswith("package="):
                cur["package"] = stripped.split("=", 1)[1].strip()
            elif stripped.startswith("active="):
                cur["active"] = stripped.split("=", 1)[1].strip().lower() == "true"
            elif stripped.startswith("state=PlaybackState"):
                ms = re.search(r"state=([A-Z_]+)\\((\\d+)\\)", stripped)
                if ms:
                    cur["state_name"] = ms.group(1)
                    cur["state_code"] = int(ms.group(2))
                mp = re.search(r"position=(\\d+)", stripped)
                if mp:
                    cur["pos_ms"] = int(mp.group(1))
                mv = re.search(r"speed=([0-9.]+)", stripped)
                if mv:
                    try:
                        cur["speed"] = float(mv.group(1))
                    except ValueError:
                        cur["speed"] = 0.0
                mu = re.search(r"updated=(\\d+)", stripped)
                if mu:
                    cur["updated_ms"] = int(mu.group(1))
            elif stripped.startswith("metadata:") and "description=" in stripped:
                desc = stripped.split("description=", 1)[1].strip()
                cur["title"], cur["artist"], cur["album"] = _parse_description(desc)

    if cur:
        sessions.append(cur)

    # Ignore sessions with neither title nor active playback unless nothing else exists.
    usable = [s for s in sessions if s["title"] or s["state_code"] in (2, 3, 6)]
    if not usable:
        return {
            "available": True,
            "playing": False,
            "state": "IDLE",
            "package": "",
            "app": "Media Control",
            "tag": "",
            "title": "Nothing Playing",
            "artist": "Open Spotify or a media app",
            "album": "",
            "pos_sec": 0,
            "pos_text": "0:00",
        }

    def _score(s: dict) -> tuple[int, int, int, int]:
        return (
            1 if s["state_code"] == 3 else 0,
            1 if "spotify" in s["package"] else 0,
            1 if (s["package"] == btn_pkg and s["tag"] == btn_tag) else 0,
            1 if s["active"] else 0,
        )

    chosen = max(usable, key=_score)
    playing = chosen["state_code"] in (3, 6)
    pos_ms = chosen["pos_ms"]
    if chosen["state_code"] == 3 and chosen["updated_ms"] > 0 and chosen["speed"] > 0:
        if uptime_ms >= chosen["updated_ms"]:
            pos_ms = max(0, int(pos_ms + (uptime_ms - chosen["updated_ms"]) * chosen["speed"]))
    pos_sec = pos_ms // 1000

    return {
        "available": True,
        "playing": playing,
        "state": chosen["state_name"],
        "package": chosen["package"],
        "app": _app_label(chosen["package"]),
        "tag": chosen["tag"],
        "title": chosen["title"] or _app_label(chosen["package"]),
        "artist": chosen["artist"],
        "album": chosen["album"],
        "pos_sec": pos_sec,
        "pos_text": _fmt_time(pos_sec),
    }


def dispatch_action(action: str, tag: str = "", is_playing: str = "") -> int:
    allowed = {"play", "pause", "play-pause", "next", "previous", "stop"}
    if action not in allowed:
        return 2

    if tag and re.fullmatch(r"[A-Za-z0-9._ -]+", tag):
        mon_cmd = action
        if action == "play-pause":
            mon_cmd = "pause" if is_playing == "1" else "play"
        if mon_cmd in ("play", "pause", "next", "previous"):
            rc, _ = _run_rish(f"cmd media_session monitor '{tag}'", stdin_text=f"{mon_cmd}\\nq\\n", timeout_s=2.5)
            if rc == 0:
                return 0

    rc, _ = _run_rish(f"cmd media_session dispatch {action}", timeout_s=2.5)
    return 0 if rc == 0 else 1


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        print(json.dumps(get_status()), flush=True)
        return 0
    tag = sys.argv[2] if len(sys.argv) > 2 else ""
    is_playing = sys.argv[3] if len(sys.argv) > 3 else ""
    return dispatch_action(cmd, tag, is_playing)


if __name__ == "__main__":
    sys.exit(main())
"""

_QS_MEDIA_PROPS = """    property bool mediaAvailable: false
    property bool mediaPlaying: false
    property string mediaState: "IDLE"
    property string mediaPackage: ""
    property string mediaApp: "Media Control"
    property string mediaTag: ""
    property string mediaTitle: "Nothing Playing"
    property string mediaArtist: "Checking MediaSession..."
    property string mediaAlbum: ""
    property int mediaPosSec: 0
    property string mediaPosText: "0:00"
"""

_QS_MEDIA_FN = """    function fmtMediaSec(sec) {
        const s = Math.max(0, Math.floor(sec));
        const m = Math.floor(s / 60);
        const rem = s % 60;
        return m + ":" + (rem < 10 ? "0" + rem : rem);
    }

    function refreshMedia() {
        if (!mediaStreamProc.running) {
            mediaStreamProc.running = true;
        } else {
            mediaStreamProc.write("status\\n");
        }
    }

    function sendMediaAction(act) {
        const wasPlaying = root.mediaPlaying ? "1" : "0";
        if (act === "play-pause") {
            root.mediaPlaying = !root.mediaPlaying;
            root.mediaState = root.mediaPlaying ? "PLAYING" : "PAUSED";
        }
        if (!mediaStreamProc.running) {
            mediaStreamProc.running = true;
        }
        mediaStreamProc.write(act + "\\t" + wasPlaying + "\\t" + root.mediaTag + "\\n");
    }
"""

_QS_MEDIA_PROCS = """    Process {
        id: mediaStreamProc
        command: [Quickshell.env("HOME") + "/.local/bin/qs-native", "media-stream"]
        running: true
        stdinEnabled: true
        stdout: SplitParser {
            onRead: line => {
                try {
                    const d = JSON.parse((line || "").trim() || "{}");
                    if (d.available !== undefined) root.mediaAvailable = Boolean(d.available);
                    if (d.playing !== undefined) root.mediaPlaying = Boolean(d.playing);
                    if (d.state !== undefined) root.mediaState = String(d.state);
                    if (d.package !== undefined) root.mediaPackage = String(d.package);
                    if (d.app !== undefined) root.mediaApp = String(d.app);
                    if (d.tag !== undefined) root.mediaTag = String(d.tag);
                    if (d.title !== undefined) root.mediaTitle = String(d.title);
                    if (d.artist !== undefined) root.mediaArtist = String(d.artist);
                    if (d.album !== undefined) root.mediaAlbum = String(d.album);
                    if (d.pos_sec !== undefined) root.mediaPosSec = Number(d.pos_sec) || 0;
                    if (d.pos_text !== undefined) root.mediaPosText = String(d.pos_text);
                } catch (e) {}
            }
        }
    }

    Timer {
        interval: 5000
        running: root.widgetsOpen
        repeat: true
        onTriggered: root.refreshMedia()
    }

    Timer {
        interval: 1000
        running: root.widgetsOpen && root.mediaPlaying
        repeat: true
        onTriggered: {
            root.mediaPosSec += 1;
            root.mediaPosText = root.fmtMediaSec(root.mediaPosSec);
        }
    }
"""

_QS_MEDIA_CARD = """                        // Android MediaSession Control Card (via rish)
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: spotifyCol.implicitHeight + 44
                            radius: 20
                            color: root.colSurface
                            border.color: root.colSurface1
                            border.width: 1

                            Column {
                                id: spotifyCol
                                anchors.fill: parent
                                anchors.leftMargin: 24
                                anchors.rightMargin: 24
                                anchors.topMargin: 22
                                anchors.bottomMargin: 22
                                spacing: 18

                                Row {
                                    width: parent.width
                                    spacing: 20
                                    Rectangle {
                                        width: 112
                                        height: 112
                                        radius: 18
                                        color: root.colSurface1
                                        Text {
                                            anchors.centerIn: parent
                                            text: root.mediaPackage.indexOf("spotify") >= 0 ? "\U000f04c7" : "\U000f0384"
                                            color: root.mediaPackage.indexOf("spotify") >= 0 ? root.colGreen : (root.mediaPlaying ? root.colBlue : root.colSubtext)
                                            font.family: root.uiFont
                                            font.pixelSize: 54
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: root.refreshMedia()
                                        }
                                    }
                                    Column {
                                        width: parent.width - 132
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 6
                                        Text {
                                            width: parent.width
                                            elide: Text.ElideRight
                                            text: root.mediaApp.toUpperCase() + " · " + root.mediaState
                                            color: root.mediaPlaying ? root.colGreen : (root.mediaAvailable ? root.colBlue : root.colPeach)
                                            font.family: root.uiFont
                                            font.pixelSize: 16
                                            font.bold: true
                                        }
                                        Text {
                                            width: parent.width
                                            elide: Text.ElideRight
                                            text: root.mediaTitle
                                            color: root.colText
                                            font.family: root.uiFont
                                            font.pixelSize: 27
                                            font.bold: true
                                        }
                                        Text {
                                            width: parent.width
                                            elide: Text.ElideRight
                                            text: root.mediaArtist + (root.mediaAlbum.length > 0 ? " · " + root.mediaAlbum : "")
                                            color: root.colSubtext
                                            font.family: root.uiFont
                                            font.pixelSize: 22
                                        }
                                    }
                                }

                                Column {
                                    width: parent.width
                                    spacing: 8
                                    Rectangle {
                                        width: parent.width
                                        height: 10
                                        radius: 5
                                        color: root.colSurface1
                                        Rectangle {
                                            width: root.mediaPlaying
                                                ? parent.width * Math.min(1.0, Math.max(0.08, (root.mediaPosSec % 240) / 240.0))
                                                : (root.mediaPosSec > 0 ? parent.width * Math.min(1.0, Math.max(0.08, (root.mediaPosSec % 240) / 240.0)) : 0)
                                            height: parent.height
                                            radius: 5
                                            color: root.mediaPlaying ? root.colGreen : root.colBlue
                                            Behavior on width { NumberAnimation { duration: 250 } }
                                        }
                                    }
                                    RowLayout {
                                        width: parent.width
                                        Text {
                                            text: root.mediaPosText
                                            color: root.colSubtext
                                            font.family: root.uiFont
                                            font.pixelSize: 19
                                            font.bold: true
                                        }
                                        Item { Layout.fillWidth: true }
                                        Text {
                                            text: root.mediaPlaying ? "Playing" : (root.mediaState === "PAUSED" ? "Paused" : root.mediaApp)
                                            color: root.colSubtext
                                            font.family: root.uiFont
                                            font.pixelSize: 19
                                            font.bold: true
                                        }
                                    }
                                }

                                Row {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    spacing: 28
                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 56
                                        height: 56
                                        radius: 16
                                        color: prevArea.pressed ? root.colSurface1 : "transparent"
                                        Text {
                                            anchors.centerIn: parent
                                            text: "\U000f04ae"
                                            color: prevArea.pressed ? root.colText : root.colSubtext
                                            font.family: root.uiFont
                                            font.pixelSize: 32
                                        }
                                        MouseArea {
                                            id: prevArea
                                            anchors.fill: parent
                                            onClicked: root.sendMediaAction("previous")
                                        }
                                    }
                                    Rectangle {
                                        width: 62
                                        height: 62
                                        radius: 31
                                        color: playArea.pressed ? root.colBlue : (root.mediaPlaying ? root.colGreen : root.colBlue)
                                        scale: playArea.pressed ? 0.92 : 1.0
                                        Behavior on scale { NumberAnimation { duration: 80 } }
                                        Text {
                                            anchors.centerIn: parent
                                            text: root.mediaPlaying ? "\U000f03e4" : "\U000f040a"
                                            color: root.colDark
                                            font.family: root.uiFont
                                            font.pixelSize: 30
                                        }
                                        MouseArea {
                                            id: playArea
                                            anchors.fill: parent
                                            onClicked: root.sendMediaAction("play-pause")
                                        }
                                    }
                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 56
                                        height: 56
                                        radius: 16
                                        color: nextArea.pressed ? root.colSurface1 : "transparent"
                                        Text {
                                            anchors.centerIn: parent
                                            text: "\U000f04ad"
                                            color: nextArea.pressed ? root.colText : root.colSubtext
                                            font.family: root.uiFont
                                            font.pixelSize: 32
                                        }
                                        MouseArea {
                                            id: nextArea
                                            anchors.fill: parent
                                            onClicked: root.sendMediaAction("next")
                                        }
                                    }
                                }
                            }
                        }
"""

QUICKSHELL_WEATHER_PY = """#!/data/data/com.termux/files/usr/bin/python3
\"\"\"Fetch current weather exclusively for İzmir / Karşıyaka via Open-Meteo.\"\"\"

import json
import os
import sys
import time
import urllib.error
import urllib.request

# Locked coordinates for İzmir / Karşıyaka only
LATITUDE = 38.45772
LONGITUDE = 27.1142
LOCATION_LABEL = "İzmir/Karşıyaka"
API_URL = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={LATITUDE}&longitude={LONGITUDE}"
    "&current=temperature_2m,apparent_temperature,relative_humidity_2m,is_day,weather_code,wind_speed_10m"
    "&timezone=Europe%2FIstanbul"
)
CACHE_PATH = os.path.expanduser("~/.cache/quickshell/weather-karsiyaka.json")

WMO_MAP = {
    0: ("Clear Sky", "\\U000f0599", "\\U000f0594", "peach", "blue"),
    1: ("Mostly Clear", "\\U000f0595", "\\U000f0594", "peach", "blue"),
    2: ("Partly Cloudy", "\\U000f0595", "\\U000f0595", "peach", "subtext"),
    3: ("Overcast", "\\U000f0590", "\\U000f0590", "subtext", "subtext"),
    45: ("Foggy", "\\U000f0591", "\\U000f0591", "subtext", "subtext"),
    48: ("Rime Fog", "\\U000f0591", "\\U000f0591", "subtext", "subtext"),
    51: ("Light Drizzle", "\\U000f0597", "\\U000f0597", "blue", "blue"),
    53: ("Drizzle", "\\U000f0597", "\\U000f0597", "blue", "blue"),
    55: ("Dense Drizzle", "\\U000f0597", "\\U000f0597", "blue", "blue"),
    56: ("Freezing Drizzle", "\\U000f0597", "\\U000f0597", "teal", "teal"),
    57: ("Freezing Drizzle", "\\U000f0597", "\\U000f0597", "teal", "teal"),
    61: ("Light Rain", "\\U000f0597", "\\U000f0597", "blue", "blue"),
    63: ("Rain", "\\U000f0597", "\\U000f0597", "blue", "blue"),
    65: ("Heavy Rain", "\\U000f0596", "\\U000f0596", "blue", "blue"),
    66: ("Freezing Rain", "\\U000f0597", "\\U000f0597", "teal", "teal"),
    67: ("Heavy Freezing Rain", "\\U000f0596", "\\U000f0596", "teal", "teal"),
    71: ("Light Snow", "\\U000f0598", "\\U000f0598", "text", "text"),
    73: ("Snow", "\\U000f0598", "\\U000f0598", "text", "text"),
    75: ("Heavy Snow", "\\U000f0598", "\\U000f0598", "text", "text"),
    77: ("Snow Grains", "\\U000f0598", "\\U000f0598", "text", "text"),
    80: ("Light Showers", "\\U000f0597", "\\U000f0597", "blue", "blue"),
    81: ("Showers", "\\U000f0597", "\\U000f0597", "blue", "blue"),
    82: ("Heavy Showers", "\\U000f0596", "\\U000f0596", "blue", "blue"),
    85: ("Snow Showers", "\\U000f0598", "\\U000f0598", "text", "text"),
    86: ("Heavy Snow Showers", "\\U000f0598", "\\U000f0598", "text", "text"),
    95: ("Thunderstorm", "\\U000f0593", "\\U000f0593", "mauve", "mauve"),
    96: ("Thunderstorm + Hail", "\\U000f0593", "\\U000f0593", "mauve", "mauve"),
    99: ("Severe Thunderstorm", "\\U000f0593", "\\U000f0593", "red", "red"),
}


def _format_payload(cur: dict, stale: bool = False) -> dict:
    temp = cur.get("temperature_2m")
    feels = cur.get("apparent_temperature")
    code = int(cur.get("weather_code", 0) or 0)
    is_day = bool(cur.get("is_day", 1))
    hum = cur.get("relative_humidity_2m")
    wind = cur.get("wind_speed_10m")

    cond, icon_d, icon_n, tone_d, tone_n = WMO_MAP.get(
        code, ("Cloudy", "\\U000f0590", "\\U000f0590", "subtext", "subtext")
    )
    icon = icon_d if is_day else icon_n
    tone = tone_d if is_day else tone_n

    temp_str = f"{round(float(temp))}°C" if temp is not None else "--°C"
    feels_str = f"Feels {round(float(feels))}°C" if feels is not None else ""
    extra = []
    if feels_str:
        extra.append(feels_str)
    if wind is not None:
        extra.append(f"{round(float(wind))} km/h")
    if hum is not None and not extra:
        extra.append(f"{int(hum)}%")

    detail = cond if not extra else f"{cond} · {' · '.join(extra)}"
    if stale:
        detail = f"{detail} (cached)"

    return {
        "ok": True,
        "location": LOCATION_LABEL,
        "temp": temp_str,
        "cond": cond,
        "detail": detail,
        "icon": icon,
        "tone": tone,
        "ts": int(time.time()),
    }


def main() -> int:
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "quickshell-weather/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        cur = raw.get("current") or {}
        if not cur:
            raise ValueError("missing current weather")
        payload = _format_payload(cur, stale=False)
        try:
            os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
            with open(CACHE_PATH, "w") as f:
                json.dump({"current": cur, "fetched_at": int(time.time())}, f)
        except OSError:
            pass
        print(json.dumps(payload), flush=True)
        return 0
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH) as f:
                    cached = json.load(f)
                payload = _format_payload(cached.get("current") or {}, stale=True)
                print(json.dumps(payload), flush=True)
                return 0
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        print(json.dumps({
            "ok": False,
            "location": LOCATION_LABEL,
            "temp": "--°C",
            "cond": "Offline",
            "detail": "Tap to retry Open-Meteo",
            "icon": "\\U000f0590",
            "tone": "subtext",
            "ts": 0,
        }), flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
"""

_QS_WEATHER_PROPS = """    property string weatherTemp: "--°C"
    property string weatherDetail: "Loading İzmir/Karşıyaka..."
    property string weatherLocation: "İzmir/Karşıyaka"
    property string weatherIcon: "\\U000f0599"
    property string weatherTone: "peach"
    property real lastWeatherMs: 0
"""

_QS_WEATHER_FN = """    function weatherColor(tone) {
        if (tone === "blue") return root.colBlue;
        if (tone === "teal") return root.colTeal;
        if (tone === "mauve") return root.colMauve;
        if (tone === "red") return root.colRed;
        if (tone === "text") return root.colText;
        if (tone === "subtext") return root.colSubtext;
        return root.colPeach;
    }

    function refreshWeather() {
        if (!weatherProc.running) {
            weatherProc.running = true;
        }
    }

    function refreshWeatherIfStale() {
        const now = Date.now();
        if (root.lastWeatherMs === 0 || (now - root.lastWeatherMs) > 300000) {
            root.refreshWeather();
        }
    }
"""

_QS_WEATHER_PROCS = """    Process {
        id: weatherProc
        command: ["python3", Quickshell.env("HOME") + "/.config/quickshell/scripts/weather.py"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const d = JSON.parse((this.text || "").trim() || "{}");
                    if (d.temp !== undefined) root.weatherTemp = String(d.temp);
                    if (d.detail !== undefined) root.weatherDetail = String(d.detail);
                    if (d.location !== undefined) root.weatherLocation = String(d.location);
                    if (d.icon !== undefined) root.weatherIcon = String(d.icon);
                    if (d.tone !== undefined) root.weatherTone = String(d.tone);
                    if (d.ok) root.lastWeatherMs = Date.now();
                } catch (e) {}
            }
        }
    }

    Timer {
        interval: 1400
        running: true
        repeat: false
        onTriggered: root.refreshWeather()
    }

    Timer {
        interval: 900000
        running: true
        repeat: true
        onTriggered: root.refreshWeather()
    }
"""

_QS_WEATHER_CARD = """                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: weatherCol.implicitHeight + 40
                                radius: 20
                                color: weatherCardArea.pressed ? root.colSurface1 : root.colSurface
                                border.color: root.colSurface1
                                border.width: 1

                                Column {
                                    id: weatherCol
                                    anchors.fill: parent
                                    anchors.margins: 20
                                    spacing: 8
                                    RowLayout {
                                        width: parent.width
                                        Row {
                                            spacing: 12
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: root.weatherIcon
                                                color: root.weatherColor(root.weatherTone)
                                                font.family: root.uiFont
                                                font.pixelSize: 38
                                            }
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: root.weatherTemp
                                                color: root.colText
                                                font.family: root.uiFont
                                                font.pixelSize: 32
                                                font.bold: true
                                            }
                                        }
                                        Item { Layout.fillWidth: true }
                                        Text {
                                            text: root.weatherLocation
                                            color: root.colBlue
                                            font.family: root.uiFont
                                            font.pixelSize: 16
                                            font.bold: true
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        elide: Text.ElideRight
                                        text: root.weatherDetail
                                        color: root.colSubtext
                                        font.family: root.uiFont
                                        font.pixelSize: 20
                                    }
                                }

                                MouseArea {
                                    id: weatherCardArea
                                    anchors.fill: parent
                                    onClicked: root.refreshWeather()
                                }
                            }
"""

QUICKSHELL_QML = """import Quickshell
import Quickshell.Io
import QtQuick
import QtQuick.Layouts

ShellRoot {
    id: root

    property var desktopStates: [
        { num: 1, focused: true, occupied: false, urgent: false },
        { num: 2, focused: false, occupied: false, urgent: false },
        { num: 3, focused: false, occupied: false, urgent: false },
        { num: 4, focused: false, occupied: false, urgent: false },
        { num: 5, focused: false, occupied: false, urgent: false },
        { num: 6, focused: false, occupied: false, urgent: false }
    ]
    property string layoutMode: "T"
    property int volumePct: 50
    property bool muted: false

    property bool sessionOpen: false
    property bool sessionActive: false
    property bool widgetsOpen: false
    property bool widgetsActive: false
__ANDROID_STATUS_PROPS__
__MEDIA_PROPS__
__WEATHER_PROPS__
    readonly property color colBase: "#e61e1e2e"
    readonly property color colPopupBase: "#f21e1e2e"
    readonly property color colSurface: "#313244"
    readonly property color colSurface1: "#45475a"
    readonly property color colText: "#cdd6f4"
    readonly property color colSubtext: "#a6adc8"
    readonly property color colBlue: "#89b4fa"
    readonly property color colMauve: "#cba6f7"
    readonly property color colTeal: "#94e2d5"
    readonly property color colGreen: "#a6e3a1"
    readonly property color colPeach: "#fab387"
    readonly property color colRed: "#f38ba8"
    readonly property color colDark: "#1e1e2e"
    readonly property string uiFont: "JetBrainsMono Nerd Font"

    readonly property var calendarHeaders: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    readonly property var calendarDays: [
        { d: "2", cls: "" }, { d: "3", cls: "" }, { d: "4", cls: "" }, { d: "5", cls: "" }, { d: "6", cls: "" }, { d: "7", cls: "wknd" }, { d: "8", cls: "wknd" },
        { d: "9", cls: "" }, { d: "10", cls: "" }, { d: "11", cls: "" }, { d: "12", cls: "" }, { d: "13", cls: "" }, { d: "14", cls: "wknd" }, { d: "15", cls: "wknd" },
        { d: "16", cls: "" }, { d: "17", cls: "today" }, { d: "18", cls: "" }, { d: "19", cls: "" }, { d: "20", cls: "" }, { d: "21", cls: "wknd" }, { d: "22", cls: "wknd" },
        { d: "23", cls: "" }, { d: "24", cls: "" }, { d: "25", cls: "" }, { d: "26", cls: "" }, { d: "27", cls: "" }, { d: "28", cls: "wknd" }, { d: "29", cls: "wknd" },
        { d: "30", cls: "" }, { d: "1", cls: "muted" }, { d: "2", cls: "muted" }, { d: "3", cls: "muted" }, { d: "4", cls: "muted" }, { d: "5", cls: "muted" }, { d: "6", cls: "muted" }
    ]

    function runCmd(cmd) {
        Quickshell.execDetached(cmd);
    }

    function refreshAudio() {
        if (!audioPollProc.running) {
            audioPollProc.running = true;
        }
    }

__ANDROID_STATUS_FN__
__MEDIA_FN__
__WEATHER_FN__
    function toggleWidgets() {
        if (root.widgetsOpen) {
            closeWidgets();
        } else {
            closeSession();
            widgetsCloseTimer.stop();
            root.widgetsActive = true;
            root.widgetsOpen = true;
            root.refreshAndroidStatus();
            root.refreshMedia();
            root.refreshWeatherIfStale();
            syncWatcher();
        }
    }

    function closeWidgets() {
        if (!root.widgetsOpen && !root.widgetsActive) return;
        root.widgetsOpen = false;
        widgetsCloseTimer.restart();
        syncWatcher();
    }

    function toggleSession() {
        if (root.sessionOpen) {
            closeSession();
        } else {
            closeWidgets();
            sessionCloseTimer.stop();
            root.sessionActive = true;
            root.sessionOpen = true;
            syncWatcher();
        }
    }

    function closeSession() {
        if (!root.sessionOpen && !root.sessionActive) return;
        root.sessionOpen = false;
        sessionCloseTimer.restart();
        syncWatcher();
    }

    function closeAllMenus() {
        closeWidgets();
        closeSession();
    }

    function syncWatcher() {
        submenuWatcher.running = false;
        if (root.widgetsOpen || root.sessionOpen) {
            watcherRestartTimer.restart();
        } else {
            watcherRestartTimer.stop();
        }
    }

    function parseReport(line) {
        const parts = line.trim().split(":");
        if (parts.length < 2) return;
        const next = [];
        for (let i = 0; i < parts.length; i++) {
            const p = parts[i];
            if (!p || p.length < 2) continue;
            const tag = p[0];
            const name = p.slice(1);
            if ("FfOoUu".indexOf(tag) >= 0) {
                const n = parseInt(name, 10);
                if (!isNaN(n)) {
                    next.push({
                        num: n,
                        focused: ("FOU".indexOf(tag) >= 0),
                        occupied: ("Oo".indexOf(tag) >= 0),
                        urgent: ("Uu".indexOf(tag) >= 0)
                    });
                }
            } else if (tag === "L") {
                root.layoutMode = name;
            }
        }
        if (next.length > 0) {
            root.desktopStates = next;
        }
    }

    Timer {
        id: widgetsCloseTimer
        interval: 190
        repeat: false
        onTriggered: {
            if (!root.widgetsOpen) root.widgetsActive = false;
        }
    }

    Timer {
        id: sessionCloseTimer
        interval: 170
        repeat: false
        onTriggered: {
            if (!root.sessionOpen) root.sessionActive = false;
        }
    }

    Timer {
        id: watcherRestartTimer
        interval: 30
        repeat: false
        onTriggered: {
            if (root.widgetsOpen || root.sessionOpen) {
                submenuWatcher.running = true;
            }
        }
    }

    Process {
        id: submenuWatcher
        command: [
            Quickshell.env("HOME") + "/.local/bin/qs-native",
            "submenu-watch",
            String(dockWindow.width),
            String(dockWindow.height > 0 ? dockWindow.height : 1508),
            String(dockWindow.width + 12),
            String(root.widgetsOpen ? 80 : Math.max(80, 80 + (dockWindow.height > 0 ? dockWindow.height : 1508) - 368)),
            String(root.widgetsOpen ? widgetsPopup.implicitWidth : sessionPopup.implicitWidth),
            String(root.widgetsOpen ? widgetsPopup.implicitHeight : sessionPopup.implicitHeight)
        ]
        stdout: SplitParser {
            onRead: data => {
                if (data.trim() === "CLOSE") {
                    root.closeAllMenus();
                }
            }
        }
    }

    Process {
        id: bspwmSub
        command: ["bspc", "subscribe", "report"]
        running: true
        stdout: SplitParser {
            onRead: data => root.parseReport(data)
        }
    }

    Process {
        id: audioPollProc
        command: ["sh", "-c", "pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null; echo ---; pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                const sections = this.text.split("---");
                if (sections.length >= 1) {
                    const m = sections[0].match(/([0-9]+)%/);
                    if (m) root.volumePct = parseInt(m[1], 10);
                }
                if (sections.length >= 2) {
                    root.muted = (sections[1].indexOf("yes") >= 0);
                }
            }
        }
    }

__ANDROID_STATUS_PROCS__
__MEDIA_PROCS__
__WEATHER_PROCS__
    Timer {
        interval: 4000
        running: true
        repeat: true
        onTriggered: root.refreshAudio()
    }

    Timer {
        id: audioSyncDelay
        interval: 150
        repeat: false
        onTriggered: root.refreshAudio()
    }

    component DockButton: Rectangle {
        id: btn
        property string iconText: ""
        property string subText: ""
        property color iconColor: root.colText
        property color baseColor: root.colSurface
        property color activeColor: root.colSurface1
        property bool active: false
        property int iconSize: 28
        property int buttonHeight: 60
        signal clicked()

        implicitWidth: 92
        implicitHeight: btn.buttonHeight
        radius: 18
        color: area.pressed ? root.colBlue : (btn.active ? btn.activeColor : btn.baseColor)
        scale: area.pressed ? 0.92 : 1.0

        Behavior on scale { NumberAnimation { duration: 80 } }
        Behavior on color { ColorAnimation { duration: 100 } }

        Column {
            anchors.centerIn: parent
            spacing: 1
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: btn.iconText
                color: area.pressed ? root.colDark : btn.iconColor
                font.family: root.uiFont
                font.pixelSize: btn.iconSize
                lineHeight: 1.0
            }
            Text {
                visible: btn.subText.length > 0
                anchors.horizontalCenter: parent.horizontalCenter
                text: btn.subText
                color: area.pressed ? root.colDark : root.colSubtext
                font.family: root.uiFont
                font.pixelSize: 13
                font.bold: true
            }
        }

        MouseArea {
            id: area
            anchors.fill: parent
            anchors.leftMargin: -16
            anchors.rightMargin: -12
            anchors.topMargin: -4
            anchors.bottomMargin: -4
            onClicked: btn.clicked()
        }
    }

    PanelWindow {
        id: dockWindow
        anchors {
            left: true
            top: true
            bottom: true
        }
        margins {
            left: 0
            top: 80
            bottom: 12
        }
        implicitWidth: 128
        color: "transparent"

        readonly property bool compactDock: height > 0 && height < 1200

        Rectangle {
            id: barBg
            anchors.fill: parent
            anchors.leftMargin: 12
            radius: 24
            color: root.colBase
            border.color: root.colSurface
            border.width: 2

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: dockWindow.compactDock ? 8 : 14
                anchors.bottomMargin: dockWindow.compactDock ? 8 : 14
                spacing: dockWindow.compactDock ? 4 : 8

                // Top: Touch Launchers
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: dockWindow.compactDock ? 6 : 12

                    DockButton {
                        iconText: "\U000f003b"
                        iconColor: root.colBlue
                        iconSize: dockWindow.compactDock ? 26 : 34
                        buttonHeight: dockWindow.compactDock ? 44 : 66
                        onClicked: {
                            root.closeAllMenus();
                            root.runCmd(["rofi", "-show", "drun"]);
                        }
                    }
                    DockButton {
                        iconText: "\uf120"
                        iconColor: root.colTeal
                        iconSize: dockWindow.compactDock ? 24 : 30
                        buttonHeight: dockWindow.compactDock ? 44 : 66
                        onClicked: {
                            root.closeAllMenus();
                            root.runCmd(["sh", "-c", "if command -v xfce4-terminal >/dev/null 2>&1; then exec xfce4-terminal; else exec alacritty; fi"]);
                        }
                    }
                    DockButton {
                        iconText: "\uf2d2"
                        iconColor: root.colMauve
                        iconSize: dockWindow.compactDock ? 24 : 30
                        buttonHeight: dockWindow.compactDock ? 44 : 66
                        onClicked: {
                            root.closeAllMenus();
                            root.runCmd(["rofi", "-show", "window"]);
                        }
                    }
                }

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 60
                    height: 2
                    radius: 1
                    color: root.colSurface1
                }

                // Middle: Touch Workspaces (1-6) + Layout Toggle
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: dockWindow.compactDock ? 5 : 12

                    Repeater {
                        model: root.desktopStates
                        delegate: Rectangle {
                            required property var modelData
                            width: 92
                            height: dockWindow.compactDock ? 36 : 58
                            radius: 18
                            scale: wsArea.pressed ? 0.92 : 1.0
                            color: modelData.focused
                                ? root.colBlue
                                : (modelData.urgent
                                    ? root.colRed
                                    : (modelData.occupied ? root.colSurface : "transparent"))
                            border.color: (!modelData.focused && modelData.occupied) ? root.colSurface1 : "transparent"
                            border.width: 1

                            Behavior on scale { NumberAnimation { duration: 80 } }
                            Behavior on color { ColorAnimation { duration: 100 } }

                            Row {
                                anchors.centerIn: parent
                                spacing: 6
                                Text {
                                    text: String(modelData.num)
                                    color: (modelData.focused || modelData.urgent) ? root.colDark : (modelData.occupied ? root.colText : root.colSubtext)
                                    font.family: root.uiFont
                                    font.pixelSize: dockWindow.compactDock ? 18 : 24
                                    font.bold: modelData.focused || modelData.occupied
                                }
                                Rectangle {
                                    visible: modelData.occupied && !modelData.focused
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 8
                                    height: 8
                                    radius: 4
                                    color: root.colBlue
                                }
                            }

                            MouseArea {
                                id: wsArea
                                anchors.fill: parent
                                anchors.leftMargin: -16
                                anchors.rightMargin: -12
                                anchors.topMargin: -4
                                anchors.bottomMargin: -4
                                onClicked: root.runCmd(["bspc", "desktop", "-f", "^" + modelData.num])
                            }
                        }
                    }

                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 42 : 56
                        iconText: root.layoutMode === "M" ? "\U000f056e" : "\U000f0573"
                        subText: dockWindow.compactDock ? "" : root.layoutMode
                        iconColor: root.layoutMode === "M" ? root.colMauve : root.colSubtext
                        iconSize: dockWindow.compactDock ? 20 : 24
                        onClicked: root.runCmd(["bspc", "desktop", "-l", "next"])
                    }
                }

                // Empty Dock Spacer -> Click to Toggle Widget Drawer
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: dockWindow.compactDock ? 32 : 60

                    Column {
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: root.widgetsOpen ? "\U000f0141" : "\U000f0142"
                            color: root.widgetsOpen ? root.colBlue : root.colSubtext
                            font.family: root.uiFont
                            font.pixelSize: 22
                        }
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 6
                            height: dockWindow.compactDock ? 20 : 44
                            radius: 3
                            color: root.widgetsOpen ? root.colBlue : root.colSurface1
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                    }

                    MouseArea {
                        id: drawerToggleArea
                        anchors.fill: parent
                        onClicked: root.toggleWidgets()
                    }
                }

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 60
                    height: 2
                    radius: 1
                    color: root.colSurface1
                }

                // Bottom: Window Controls + Volume + Session Power
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: dockWindow.compactDock ? 5 : 10

                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: "\uf2d0"
                        iconColor: root.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: root.runCmd(["bspc", "node", "-t", "~floating"])
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: "\uf065"
                        iconColor: root.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: root.runCmd(["bspc", "node", "-t", "~fullscreen"])
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: "\uf00d"
                        iconColor: root.colRed
                        iconSize: dockWindow.compactDock ? 22 : 28
                        onClicked: root.runCmd(["bspc", "node", "-c"])
                    }

                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 60
                        height: 2
                        radius: 1
                        color: root.colSurface1
                    }

                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 34 : 50
                        iconText: "\U000f0415"
                        iconColor: root.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: {
                            root.runCmd(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"]);
                            audioSyncDelay.restart();
                        }
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 46 : 66
                        iconText: root.muted ? "\U000f075f" : "\U000f057e"
                        subText: root.muted ? "MUTE" : (root.volumePct + "%")
                        iconColor: root.muted ? root.colRed : root.colGreen
                        iconSize: dockWindow.compactDock ? 20 : 24
                        onClicked: {
                            root.runCmd(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"]);
                            audioSyncDelay.restart();
                        }
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 34 : 50
                        iconText: "\U000f0374"
                        iconColor: root.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: {
                            root.runCmd(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"]);
                            audioSyncDelay.restart();
                        }
                    }

                    DockButton {
                        id: sessionBtn
                        buttonHeight: dockWindow.compactDock ? 42 : 62
                        iconText: "\uf011"
                        iconColor: root.sessionOpen ? root.colDark : root.colRed
                        baseColor: root.sessionOpen ? root.colRed : root.colSurface
                        iconSize: dockWindow.compactDock ? 22 : 28
                        onClicked: root.toggleSession()
                    }
                }
            }
        }
    }

    // Large Readable Widget Drawer (1/3 screen width, full dock height)
    PopupWindow {
        id: widgetsPopup
        anchor.window: dockWindow
        anchor.rect.x: dockWindow.width + 12
        anchor.rect.y: 0
        implicitWidth: 844
        implicitHeight: dockWindow.height > 0 ? dockWindow.height : 1504
        visible: root.widgetsActive
        color: "transparent"

        Item {
            anchors.fill: parent
            clip: true

            Rectangle {
                id: drawerBg
                width: parent.width
                height: parent.height
                x: root.widgetsOpen ? 0 : -44
                opacity: root.widgetsOpen ? 1.0 : 0.0
                radius: 24
                color: root.colPopupBase
                border.color: root.colSurface1
                border.width: 2

                Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                Behavior on opacity { NumberAnimation { duration: 140 } }

                Flickable {
                    anchors.fill: parent
                    anchors.margins: 28
                    contentWidth: width
                    contentHeight: drawerCol.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    interactive: contentHeight > height

                    ColumnLayout {
                        id: drawerCol
                        width: parent.width
                        spacing: 20

                        // Header
                        RowLayout {
                            Layout.fillWidth: true
                            Row {
                                spacing: 14
                                Layout.fillWidth: true
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "\U000f003b"
                                    color: root.colBlue
                                    font.family: root.uiFont
                                    font.pixelSize: 34
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "Widgets"
                                    color: root.colText
                                    font.family: root.uiFont
                                    font.pixelSize: 30
                                    font.bold: true
                                }
                            }
                            Rectangle {
                                width: 48
                                height: 48
                                radius: 16
                                color: closeBtnArea.pressed ? root.colBlue : root.colSurface
                                border.color: root.colSurface1
                                border.width: 1
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uf00d"
                                    color: closeBtnArea.pressed ? root.colDark : root.colSubtext
                                    font.family: root.uiFont
                                    font.pixelSize: 22
                                }
                                MouseArea {
                                    id: closeBtnArea
                                    anchors.fill: parent
                                    onClicked: root.closeWidgets()
                                }
                            }
                        }

                        // Quick Widget Spaces Row
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 18

__WEATHER_CARD__

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: focusCol.implicitHeight + 40
                                radius: 20
                                color: root.colSurface
                                border.color: root.colSurface1
                                border.width: 1

                                Column {
                                    id: focusCol
                                    anchors.fill: parent
                                    anchors.margins: 20
                                    spacing: 8
                                    Row {
                                        spacing: 12
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "\U000f05a9"
                                            color: root.colTeal
                                            font.family: root.uiFont
                                            font.pixelSize: 38
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "Termux"
                                            color: root.colText
                                            font.family: root.uiFont
                                            font.pixelSize: 32
                                            font.bold: true
                                        }
                                    }
                                    Text {
                                        text: "Do Not Disturb · On"
                                        color: root.colSubtext
                                        font.family: root.uiFont
                                        font.pixelSize: 21
                                    }
                                }
                            }
                        }

__ANDROID_STATUS_CARD__
                        // Spotify Card Space (Mockup)
__MEDIA_CARD__

                        // Calendar Space (Mockup)
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: calCol.implicitHeight + 44
                            radius: 20
                            color: root.colSurface
                            border.color: root.colSurface1
                            border.width: 1

                            Column {
                                id: calCol
                                anchors.fill: parent
                                anchors.leftMargin: 24
                                anchors.rightMargin: 24
                                anchors.topMargin: 22
                                anchors.bottomMargin: 22
                                spacing: 14

                                RowLayout {
                                    width: parent.width
                                    Row {
                                        spacing: 12
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "\U000f00ed"
                                            color: root.colBlue
                                            font.family: root.uiFont
                                            font.pixelSize: 28
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "November 2026"
                                            color: root.colText
                                            font.family: root.uiFont
                                            font.pixelSize: 24
                                            font.bold: true
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        text: "\U000f0141   \U000f0142"
                                        color: root.colSubtext
                                        font.family: root.uiFont
                                        font.pixelSize: 24
                                    }
                                }

                                GridLayout {
                                    width: parent.width
                                    columns: 7
                                    columnSpacing: 6
                                    rowSpacing: 8

                                    Repeater {
                                        model: root.calendarHeaders
                                        delegate: Item {
                                            required property string modelData
                                            Layout.fillWidth: true
                                            implicitHeight: 42
                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData
                                                color: root.colSubtext
                                                font.family: root.uiFont
                                                font.pixelSize: 21
                                                font.bold: true
                                            }
                                        }
                                    }

                                    Repeater {
                                        model: root.calendarDays
                                        delegate: Rectangle {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            implicitHeight: 46
                                            radius: 14
                                            color: modelData.cls === "today" ? root.colBlue : "transparent"
                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData.d
                                                color: modelData.cls === "today"
                                                    ? root.colDark
                                                    : (modelData.cls === "muted"
                                                        ? root.colSurface1
                                                        : (modelData.cls === "wknd" ? root.colSubtext : root.colText))
                                                font.family: root.uiFont
                                                font.pixelSize: 23
                                                font.bold: modelData.cls === "today"
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Agenda / Notes Space (Mockup)
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            implicitHeight: agendaCol.implicitHeight + 44
                            radius: 20
                            color: root.colSurface
                            border.color: root.colSurface1
                            border.width: 1

                            Column {
                                id: agendaCol
                                anchors.fill: parent
                                anchors.leftMargin: 24
                                anchors.rightMargin: 24
                                anchors.topMargin: 22
                                anchors.bottomMargin: 22
                                spacing: 14

                                Row {
                                    spacing: 12
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "\U000f039a"
                                        color: root.colMauve
                                        font.family: root.uiFont
                                        font.pixelSize: 28
                                    }
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "Agenda"
                                        color: root.colText
                                        font.family: root.uiFont
                                        font.pixelSize: 24
                                        font.bold: true
                                    }
                                }

                                Repeater {
                                    model: [
                                        { t: "19:00", col: root.colBlue, txt: "Build Termux X11 Dock" },
                                        { t: "21:30", col: root.colMauve, txt: "Sync Dotfiles & GUI Rules" },
                                        { t: "22:45", col: root.colTeal, txt: "Wrap Up Workspace Widgets" }
                                    ]
                                    delegate: Rectangle {
                                        required property var modelData
                                        width: parent.width
                                        height: 54
                                        radius: 14
                                        color: root.colPopupBase
                                        border.color: root.colSurface1
                                        border.width: 1
                                        Row {
                                            anchors.verticalCenter: parent.verticalCenter
                                            anchors.left: parent.left
                                            anchors.leftMargin: 16
                                            spacing: 16
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: modelData.t
                                                color: modelData.col
                                                font.family: root.uiFont
                                                font.pixelSize: 21
                                                font.bold: true
                                            }
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: modelData.txt
                                                color: root.colText
                                                font.family: root.uiFont
                                                font.pixelSize: 21
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Raised Session Menu (Bottom-left submenu of Quit/Power button)
    PopupWindow {
        id: sessionPopup
        anchor.window: dockWindow
        anchor.rect.x: dockWindow.width + 12
        anchor.rect.y: Math.max(0, (dockWindow.height > 0 ? dockWindow.height : 1504) - 368)
        implicitWidth: 330
        implicitHeight: 368
        visible: root.sessionActive
        color: "transparent"

        Item {
            anchors.fill: parent
            clip: true

            Rectangle {
                width: parent.width
                height: 330
                y: root.sessionOpen ? 0 : 28
                opacity: root.sessionOpen ? 1.0 : 0.0
                radius: 22
                color: root.colPopupBase
                border.color: root.colSurface1
                border.width: 2

                Behavior on y { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                Behavior on opacity { NumberAnimation { duration: 130 } }

                Column {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 18

                    Repeater {
                        model: [
                            { label: "Reload Bars", icon: "\uf021", color: root.colBlue, cmd: ["sh", "-c", "$HOME/.config/polybar/launch.sh & $HOME/.config/quickshell/launch.sh &"] },
                            { label: "Restart WM", icon: "\uf021", color: root.colTeal, cmd: ["bspc", "wm", "-r"] },
                            { label: "Exit X11", icon: "\uf011", color: root.colRed, cmd: ["bspc", "quit"] }
                        ]
                        delegate: Rectangle {
                            required property var modelData
                            width: parent.width
                            height: 86
                            radius: 16
                            color: popArea.pressed ? root.colBlue : root.colSurface
                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: 20
                                spacing: 16
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.icon
                                    color: popArea.pressed ? root.colDark : modelData.color
                                    font.family: root.uiFont
                                    font.pixelSize: 26
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.label
                                    color: popArea.pressed ? root.colDark : root.colText
                                    font.family: root.uiFont
                                    font.pixelSize: 21
                                    font.bold: true
                                }
                            }
                            MouseArea {
                                id: popArea
                                anchors.fill: parent
                                anchors.leftMargin: -18
                                anchors.rightMargin: -18
                                anchors.topMargin: -9
                                anchors.bottomMargin: -9
                                onClicked: {
                                    root.closeSession();
                                    root.runCmd(modelData.cmd);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
"""

QUICKSHELL_WAYLAND_QML = """import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import QtQuick
import QtQuick.Layouts

ShellRoot {
    id: root

    readonly property bool isSway: (Quickshell.env("SWAYSOCK") || "").length > 0
    property var desktopStates: [
        { num: 1, focused: true, occupied: false, urgent: false },
        { num: 2, focused: false, occupied: false, urgent: false },
        { num: 3, focused: false, occupied: false, urgent: false },
        { num: 4, focused: false, occupied: false, urgent: false },
        { num: 5, focused: false, occupied: false, urgent: false },
        { num: 6, focused: false, occupied: false, urgent: false }
    ]
    property int volumePct: 50
    property bool muted: false
    property int cpuPct: 0
    property string memUsed: "0.0"
    property string memTotal: "0.0"
    property int memPct: 0
    property int batPct: -1
    property string batStatus: "UNKNOWN"
    property real tempC: -1
    property string batWatts: ""
    property bool wifiOk: false
    property int wifiRate: 0
    property string focusedTitle: {
        if (root.isSway) return swayFocusedTitle;
        const tl = ToplevelManager.activeToplevel;
        return (tl && tl.title && tl.title.length > 0) ? String(tl.title) : "Ready";
    }
    property string swayFocusedTitle: "Ready"
    property string clockText: Qt.formatDateTime(new Date(), "ddd d MMM  HH:mm")

    property bool sessionOpen: false
    property bool sessionActive: false
    property bool widgetsOpen: false
    property bool widgetsActive: false
__ANDROID_STATUS_PROPS__
__MEDIA_PROPS__
__WEATHER_PROPS__
    readonly property color colBase: "#e61e1e2e"
    readonly property color colPopupBase: "#f21e1e2e"
    readonly property color colSurface: "#313244"
    readonly property color colSurface1: "#45475a"
    readonly property color colText: "#cdd6f4"
    readonly property color colSubtext: "#a6adc8"
    readonly property color colBlue: "#89b4fa"
    readonly property color colMauve: "#cba6f7"
    readonly property color colTeal: "#94e2d5"
    readonly property color colGreen: "#a6e3a1"
    readonly property color colPeach: "#fab387"
    readonly property color colRed: "#f38ba8"
    readonly property color colDark: "#1e1e2e"
    readonly property string uiFont: "JetBrainsMono Nerd Font"

    readonly property var calendarHeaders: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    readonly property var calendarDays: [
        { d: "2", cls: "" }, { d: "3", cls: "" }, { d: "4", cls: "" }, { d: "5", cls: "" }, { d: "6", cls: "" }, { d: "7", cls: "wknd" }, { d: "8", cls: "wknd" },
        { d: "9", cls: "" }, { d: "10", cls: "" }, { d: "11", cls: "" }, { d: "12", cls: "" }, { d: "13", cls: "" }, { d: "14", cls: "wknd" }, { d: "15", cls: "wknd" },
        { d: "16", cls: "" }, { d: "17", cls: "today" }, { d: "18", cls: "" }, { d: "19", cls: "" }, { d: "20", cls: "" }, { d: "21", cls: "wknd" }, { d: "22", cls: "wknd" },
        { d: "23", cls: "" }, { d: "24", cls: "" }, { d: "25", cls: "" }, { d: "26", cls: "" }, { d: "27", cls: "" }, { d: "28", cls: "wknd" }, { d: "29", cls: "wknd" },
        { d: "30", cls: "" }, { d: "1", cls: "muted" }, { d: "2", cls: "muted" }, { d: "3", cls: "muted" }, { d: "4", cls: "muted" }, { d: "5", cls: "muted" }, { d: "6", cls: "muted" }
    ]

    function runCmd(cmd) {
        Quickshell.execDetached(cmd);
    }

    function refreshAudio() {
        if (!audioPollProc.running) {
            audioPollProc.running = true;
        }
    }

    function refreshSwayWorkspaces() {
        if (root.isSway && !swayWsPoll.running) {
            swayWsPoll.running = true;
        }
        if (root.isSway && !swayTreePoll.running) {
            swayTreePoll.running = true;
        }
    }

__ANDROID_STATUS_FN__
__MEDIA_FN__
__WEATHER_FN__
    function findFocusedTitle(node) {
        if (!node) return "";
        if (node.focused && node.name && node.type !== "workspace" && node.type !== "output" && node.type !== "root") {
            return String(node.name);
        }
        const kids = (node.nodes || []).concat(node.floating_nodes || []);
        for (let i = 0; i < kids.length; i++) {
            const t = findFocusedTitle(kids[i]);
            if (t.length > 0) return t;
        }
        return "";
    }

    function toggleWidgets() {
        if (root.widgetsOpen) {
            closeWidgets();
        } else {
            closeSession();
            widgetsCloseTimer.stop();
            root.widgetsActive = true;
            root.widgetsOpen = true;
            root.refreshAndroidStatus();
            root.refreshMedia();
            root.refreshWeatherIfStale();
        }
    }

    function closeWidgets() {
        if (!root.widgetsOpen && !root.widgetsActive) return;
        root.widgetsOpen = false;
        widgetsCloseTimer.restart();
    }

    function toggleSession() {
        if (root.sessionOpen) {
            closeSession();
        } else {
            closeWidgets();
            sessionCloseTimer.stop();
            root.sessionActive = true;
            root.sessionOpen = true;
        }
    }

    function closeSession() {
        if (!root.sessionOpen && !root.sessionActive) return;
        root.sessionOpen = false;
        sessionCloseTimer.restart();
    }

    function closeAllMenus() {
        closeWidgets();
        closeSession();
    }

    Timer {
        id: widgetsCloseTimer
        interval: 190
        repeat: false
        onTriggered: {
            if (!root.widgetsOpen) root.widgetsActive = false;
        }
    }

    Timer {
        id: sessionCloseTimer
        interval: 170
        repeat: false
        onTriggered: {
            if (!root.sessionOpen) root.sessionActive = false;
        }
    }

    // LabWC live ext_workspace_manager_v1 stream + activation
    Process {
        id: wlWsProc
        command: [Quickshell.env("HOME") + "/.local/bin/qs-native", "wl-workspaces"]
        running: !root.isSway
        stdinEnabled: true
        stdout: SplitParser {
            onRead: line => {
                try {
                    const list = JSON.parse(line);
                    if (Array.isArray(list) && list.length > 0) {
                        root.desktopStates = list;
                    }
                } catch (e) {}
            }
        }
    }

    // Sway live workspace & window events
    Process {
        id: swaySub
        command: ["swaymsg", "-t", "subscribe", "-m", "[\\"workspace\\",\\"window\\"]"]
        running: root.isSway
        stdout: SplitParser {
            onRead: _ => root.refreshSwayWorkspaces()
        }
    }

    Process {
        id: swayTreePoll
        command: ["swaymsg", "-t", "get_tree"]
        running: root.isSway
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const tree = JSON.parse(this.text || "{}");
                    const t = root.findFocusedTitle(tree);
                    root.swayFocusedTitle = t.length > 0 ? t : "Ready";
                } catch (e) {}
            }
        }
    }

    Process {
        id: swayWsPoll
        command: ["swaymsg", "-t", "get_workspaces"]
        running: root.isSway
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const list = JSON.parse(this.text || "[]");
                    const byNum = {};
                    for (let i = 0; i < list.length; i++) {
                        byNum[list[i].num] = list[i];
                    }
                    const next = [];
                    for (let n = 1; n <= 6; n++) {
                        const ws = byNum[n];
                        next.push({
                            num: n,
                            focused: ws ? Boolean(ws.focused) : false,
                            occupied: Boolean(ws),
                            urgent: ws ? Boolean(ws.urgent) : false
                        });
                    }
                    root.desktopStates = next;
                } catch (e) {}
            }
        }
    }

    Process {
        id: audioPollProc
        command: ["sh", "-c", "pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null; echo ---; pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                const sections = this.text.split("---");
                if (sections.length >= 1) {
                    const m = sections[0].match(/([0-9]+)%/);
                    if (m) root.volumePct = parseInt(m[1], 10);
                }
                if (sections.length >= 2) {
                    root.muted = (sections[1].indexOf("yes") >= 0);
                }
            }
        }
    }

    Process {
        id: sysDiagProc
        command: [Quickshell.env("HOME") + "/.local/bin/qs-native", "sys-diag"]
        running: true
        stdout: SplitParser {
            onRead: line => {
                try {
                    const d = JSON.parse(line);
                    if (d.cpu !== undefined) root.cpuPct = d.cpu;
                    if (d.mem_used !== undefined) root.memUsed = String(d.mem_used);
                    if (d.mem_total !== undefined) root.memTotal = String(d.mem_total);
                    if (d.mem_pct !== undefined) root.memPct = d.mem_pct;
                    if (d.bat_pct !== undefined) root.batPct = d.bat_pct;
                    if (d.bat_status !== undefined) root.batStatus = String(d.bat_status);
                    if (d.temp_c !== null && d.temp_c !== undefined) root.tempC = d.temp_c;
                    if (d.watts !== undefined) root.batWatts = String(d.watts);
                    if (d.wifi_ok !== undefined) root.wifiOk = Boolean(d.wifi_ok);
                    if (d.wifi_rate !== undefined) root.wifiRate = d.wifi_rate;
                } catch (e) {}
            }
        }
    }

__ANDROID_STATUS_PROCS__
__MEDIA_PROCS__
__WEATHER_PROCS__
    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: {
            root.clockText = Qt.formatDateTime(new Date(), "ddd d MMM  HH:mm");
        }
    }

    Timer {
        interval: 4000
        running: true
        repeat: true
        onTriggered: root.refreshAudio()
    }

    Timer {
        id: audioSyncDelay
        interval: 150
        repeat: false
        onTriggered: root.refreshAudio()
    }

    component DockButton: Rectangle {
        id: btn
        property string iconText: ""
        property string subText: ""
        property color iconColor: root.colText
        property color baseColor: root.colSurface
        property color activeColor: root.colSurface1
        property bool active: false
        property int iconSize: 28
        property int buttonHeight: 60
        signal clicked()

        implicitWidth: 92
        implicitHeight: btn.buttonHeight
        radius: 18
        color: area.pressed ? root.colBlue : (btn.active ? btn.activeColor : btn.baseColor)
        scale: area.pressed ? 0.92 : 1.0

        Behavior on scale { NumberAnimation { duration: 80 } }
        Behavior on color { ColorAnimation { duration: 100 } }

        Column {
            anchors.centerIn: parent
            spacing: 1
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: btn.iconText
                color: area.pressed ? root.colDark : btn.iconColor
                font.family: root.uiFont
                font.pixelSize: btn.iconSize
                lineHeight: 1.0
            }
            Text {
                visible: btn.subText.length > 0
                anchors.horizontalCenter: parent.horizontalCenter
                text: btn.subText
                color: area.pressed ? root.colDark : root.colSubtext
                font.family: root.uiFont
                font.pixelSize: 13
                font.bold: true
            }
        }

        MouseArea {
            id: area
            anchors.fill: parent
            anchors.leftMargin: -16
            anchors.rightMargin: -12
            anchors.topMargin: -4
            anchors.bottomMargin: -4
            onClicked: btn.clicked()
        }
    }

    // Top Status Bar (Wayland layer-shell replacement for Polybar)
    PanelWindow {
        id: topBarWindow
        anchors {
            left: true
            top: true
            right: true
        }
        margins {
            left: 12
            right: 12
            top: 10
        }
        implicitHeight: 54
        color: "transparent"
        WlrLayershell.layer: WlrLayer.Top

        Rectangle {
            id: topBarBg
            anchors.fill: parent
            radius: 18
            color: root.colBase
            border.color: root.colSurface
            border.width: 2

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 18
                anchors.rightMargin: 18
                spacing: 12

                Rectangle {
                    id: wmPill
                    radius: 12
                    color: root.colSurface
                    implicitHeight: 36
                    implicitWidth: wmRow.implicitWidth + 24
                    Row {
                        id: wmRow
                        anchors.centerIn: parent
                        spacing: 8
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "\U000f0359"
                            color: root.colBlue
                            font.family: root.uiFont
                            font.pixelSize: 18
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.isSway ? "SWAY" : "LABWC"
                            color: root.colText
                            font.family: root.uiFont
                            font.pixelSize: 15
                            font.bold: true
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    Layout.maximumWidth: Math.max(80, topBarBg.width / 2 - wmPill.width - clockPill.width / 2 - 48)
                    elide: Text.ElideRight
                    text: root.focusedTitle
                    color: root.focusedTitle === "Ready" ? root.colSubtext : root.colText
                    font.family: root.uiFont
                    font.pixelSize: 15
                }

                Item { Layout.fillWidth: true }

                Row {
                    spacing: 8

                    // CPU %
                    Rectangle {
                        radius: 12
                        color: root.colSurface
                        implicitHeight: 36
                        implicitWidth: cpuRow.implicitWidth + 22
                        Row {
                            id: cpuRow
                            anchors.centerIn: parent
                            spacing: 7
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "\uf4bc"
                                color: root.cpuPct >= 80 ? root.colRed : (root.cpuPct >= 50 ? root.colPeach : root.colTeal)
                                font.family: root.uiFont
                                font.pixelSize: 16
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.cpuPct + "%"
                                color: root.colText
                                font.family: root.uiFont
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }

                    // RAM
                    Rectangle {
                        radius: 12
                        color: root.colSurface
                        implicitHeight: 36
                        implicitWidth: memRow.implicitWidth + 22
                        Row {
                            id: memRow
                            anchors.centerIn: parent
                            spacing: 7
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "\U000f035b"
                                color: root.memPct >= 85 ? root.colRed : root.colMauve
                                font.family: root.uiFont
                                font.pixelSize: 16
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.memUsed + "/" + root.memTotal + "G (" + root.memPct + "%)"
                                color: root.colText
                                font.family: root.uiFont
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }

                    // Battery Temperature
                    Rectangle {
                        visible: root.tempC >= 0
                        radius: 12
                        color: root.colSurface
                        implicitHeight: 36
                        implicitWidth: tempRow.implicitWidth + 22
                        Row {
                            id: tempRow
                            anchors.centerIn: parent
                            spacing: 6
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "\U000f050f"
                                color: root.tempC >= 43 ? root.colRed : (root.tempC >= 38 ? root.colPeach : root.colTeal)
                                font.family: root.uiFont
                                font.pixelSize: 16
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.tempC.toFixed(1) + "°C"
                                color: root.colText
                                font.family: root.uiFont
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }

                    // Wi-Fi
                    Rectangle {
                        radius: 12
                        color: root.colSurface
                        implicitHeight: 36
                        implicitWidth: wifiRow.implicitWidth + 22
                        Row {
                            id: wifiRow
                            anchors.centerIn: parent
                            spacing: 7
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.wifiOk ? "\U000f05a9" : "\U000f05aa"
                                color: root.wifiOk ? root.colBlue : root.colSubtext
                                font.family: root.uiFont
                                font.pixelSize: 16
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.wifiOk ? (root.wifiRate > 0 ? root.wifiRate + "M" : "Wi-Fi") : "Off"
                                color: root.wifiOk ? root.colText : root.colSubtext
                                font.family: root.uiFont
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }

                    // Volume
                    Rectangle {
                        radius: 12
                        color: root.colSurface
                        implicitHeight: 36
                        implicitWidth: volRow.implicitWidth + 22
                        Row {
                            id: volRow
                            anchors.centerIn: parent
                            spacing: 7
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.muted ? "\U000f075f" : "\U000f057e"
                                color: root.muted ? root.colRed : root.colGreen
                                font.family: root.uiFont
                                font.pixelSize: 16
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.muted ? "MUTE" : (root.volumePct + "%")
                                color: root.colText
                                font.family: root.uiFont
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }

                    // Battery % + Power Draw
                    Rectangle {
                        radius: 12
                        color: root.colSurface
                        implicitHeight: 36
                        implicitWidth: batRow.implicitWidth + 22
                        Row {
                            id: batRow
                            anchors.centerIn: parent
                            spacing: 7
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.batStatus === "CHARGING" ? "\uf0e7" : (root.batPct >= 85 ? "\uf240" : (root.batPct >= 60 ? "\uf241" : (root.batPct >= 35 ? "\uf242" : (root.batPct >= 15 ? "\uf243" : "\uf244"))))
                                color: root.batStatus === "CHARGING" || root.batPct >= 85 ? root.colGreen : (root.batPct >= 35 ? root.colText : (root.batPct >= 15 ? root.colPeach : root.colRed))
                                font.family: root.uiFont
                                font.pixelSize: 16
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.batPct >= 0 ? (root.batPct + "%" + (root.batWatts.length > 0 ? " " + root.batWatts : "")) : "BAT --"
                                color: root.colText
                                font.family: root.uiFont
                                font.pixelSize: 15
                                font.bold: true
                            }
                        }
                    }
                }
            }

            Rectangle {
                id: clockPill
                anchors.centerIn: parent
                radius: 12
                color: root.colSurface
                height: 36
                width: clockRow.implicitWidth + 24
                Row {
                    id: clockRow
                    anchors.centerIn: parent
                    spacing: 8
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "\uf017"
                        color: root.colBlue
                        font.family: root.uiFont
                        font.pixelSize: 16
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.clockText
                        color: root.colBlue
                        font.family: root.uiFont
                        font.pixelSize: 16
                        font.bold: true
                    }
                }
            }
        }
    }

    // Left Touch Dock
    PanelWindow {
        id: dockWindow
        anchors {
            left: true
            top: true
            bottom: true
        }
        margins {
            left: 0
            top: 12
            bottom: 12
        }
        implicitWidth: 128
        color: "transparent"
        WlrLayershell.layer: WlrLayer.Top

        readonly property bool compactDock: height > 0 && height < 1200

        Rectangle {
            id: barBg
            anchors.fill: parent
            anchors.leftMargin: 12
            radius: 24
            color: root.colBase
            border.color: root.colSurface
            border.width: 2

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: dockWindow.compactDock ? 8 : 14
                anchors.bottomMargin: dockWindow.compactDock ? 8 : 14
                spacing: dockWindow.compactDock ? 4 : 8

                // Top: Touch Launchers
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: dockWindow.compactDock ? 6 : 12

                    DockButton {
                        iconText: "\U000f003b"
                        iconColor: root.colBlue
                        iconSize: dockWindow.compactDock ? 26 : 34
                        buttonHeight: dockWindow.compactDock ? 44 : 66
                        onClicked: {
                            root.closeAllMenus();
                            root.runCmd(["rofi", "-show", "drun"]);
                        }
                    }
                    DockButton {
                        iconText: "\uf120"
                        iconColor: root.colTeal
                        iconSize: dockWindow.compactDock ? 24 : 30
                        buttonHeight: dockWindow.compactDock ? 44 : 66
                        onClicked: {
                            root.closeAllMenus();
                            root.runCmd(["sh", "-c", "if command -v foot >/dev/null 2>&1; then exec foot; elif command -v xfce4-terminal >/dev/null 2>&1; then exec xfce4-terminal; else exec alacritty; fi"]);
                        }
                    }
                    DockButton {
                        iconText: "\uf2d2"
                        iconColor: root.colMauve
                        iconSize: dockWindow.compactDock ? 24 : 30
                        buttonHeight: dockWindow.compactDock ? 44 : 66
                        onClicked: {
                            root.closeAllMenus();
                            root.runCmd(["rofi", "-show", "window"]);
                        }
                    }
                }

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 60
                    height: 2
                    radius: 1
                    color: root.colSurface1
                }

                // Middle: Workspaces (1-6) + Layout/Window Toggle
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: dockWindow.compactDock ? 5 : 12

                    Repeater {
                        model: root.desktopStates
                        delegate: Rectangle {
                            required property var modelData
                            width: 92
                            height: dockWindow.compactDock ? 36 : 58
                            radius: 18
                            scale: wsArea.pressed ? 0.92 : 1.0
                            color: modelData.focused
                                ? root.colBlue
                                : (modelData.urgent
                                    ? root.colRed
                                    : (modelData.occupied ? root.colSurface : "transparent"))
                            border.color: (!modelData.focused && modelData.occupied) ? root.colSurface1 : "transparent"
                            border.width: 1

                            Behavior on scale { NumberAnimation { duration: 80 } }
                            Behavior on color { ColorAnimation { duration: 100 } }

                            Row {
                                anchors.centerIn: parent
                                spacing: 6
                                Text {
                                    text: String(modelData.num)
                                    color: (modelData.focused || modelData.urgent) ? root.colDark : (modelData.occupied ? root.colText : root.colSubtext)
                                    font.family: root.uiFont
                                    font.pixelSize: dockWindow.compactDock ? 18 : 24
                                    font.bold: modelData.focused || modelData.occupied
                                }
                                Rectangle {
                                    visible: modelData.occupied && !modelData.focused
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 8
                                    height: 8
                                    radius: 4
                                    color: root.colBlue
                                }
                            }

                            MouseArea {
                                id: wsArea
                                anchors.fill: parent
                                anchors.leftMargin: -16
                                anchors.rightMargin: -12
                                anchors.topMargin: -4
                                anchors.bottomMargin: -4
                                onClicked: {
                                    if (root.isSway) {
                                        root.runCmd(["swaymsg", "workspace", "number", String(modelData.num)]);
                                    } else {
                                        wlWsProc.write(String(modelData.num) + "\\n");
                                    }
                                }
                            }
                        }
                    }

                    DockButton {
                        visible: root.isSway
                        buttonHeight: dockWindow.compactDock ? 42 : 56
                        iconText: "\U000f0573"
                        subText: dockWindow.compactDock ? "" : "LAY"
                        iconColor: root.colSubtext
                        iconSize: dockWindow.compactDock ? 20 : 24
                        onClicked: root.runCmd(["swaymsg", "layout", "toggle", "tabbed", "split"])
                    }
                }

                // Empty Dock Spacer -> Click to Toggle Widget Drawer
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: dockWindow.compactDock ? 32 : 60

                    Column {
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: root.widgetsOpen ? "\U000f0141" : "\U000f0142"
                            color: root.widgetsOpen ? root.colBlue : root.colSubtext
                            font.family: root.uiFont
                            font.pixelSize: 22
                        }
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 6
                            height: dockWindow.compactDock ? 20 : 44
                            radius: 3
                            color: root.widgetsOpen ? root.colBlue : root.colSurface1
                            Behavior on color { ColorAnimation { duration: 120 } }
                        }
                    }

                    MouseArea {
                        id: drawerToggleArea
                        anchors.fill: parent
                        onClicked: root.toggleWidgets()
                    }
                }

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 60
                    height: 2
                    radius: 1
                    color: root.colSurface1
                }

                // Bottom: Window Controls + Volume + Session Power
                Column {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: dockWindow.compactDock ? 5 : 10

                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: "\uf2d0"
                        iconColor: root.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: {
                            if (root.isSway) {
                                root.runCmd(["swaymsg", "floating", "toggle"]);
                            } else if (ToplevelManager.activeToplevel) {
                                ToplevelManager.activeToplevel.maximized = !ToplevelManager.activeToplevel.maximized;
                            }
                        }
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: "\uf065"
                        iconColor: root.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: {
                            if (root.isSway) {
                                root.runCmd(["swaymsg", "fullscreen", "toggle"]);
                            } else if (ToplevelManager.activeToplevel) {
                                ToplevelManager.activeToplevel.fullscreen = !ToplevelManager.activeToplevel.fullscreen;
                            }
                        }
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 36 : 56
                        iconText: "\uf00d"
                        iconColor: root.colRed
                        iconSize: dockWindow.compactDock ? 22 : 28
                        onClicked: {
                            if (root.isSway) {
                                root.runCmd(["swaymsg", "kill"]);
                            } else if (ToplevelManager.activeToplevel) {
                                ToplevelManager.activeToplevel.close();
                            }
                        }
                    }

                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 60
                        height: 2
                        radius: 1
                        color: root.colSurface1
                    }

                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 34 : 50
                        iconText: "\U000f0415"
                        iconColor: root.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: {
                            root.runCmd(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"]);
                            audioSyncDelay.restart();
                        }
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 46 : 66
                        iconText: root.muted ? "\U000f075f" : "\U000f057e"
                        subText: root.muted ? "MUTE" : (root.volumePct + "%")
                        iconColor: root.muted ? root.colRed : root.colGreen
                        iconSize: dockWindow.compactDock ? 20 : 24
                        onClicked: {
                            root.runCmd(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"]);
                            audioSyncDelay.restart();
                        }
                    }
                    DockButton {
                        buttonHeight: dockWindow.compactDock ? 34 : 50
                        iconText: "\U000f0374"
                        iconColor: root.colText
                        iconSize: dockWindow.compactDock ? 20 : 26
                        onClicked: {
                            root.runCmd(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"]);
                            audioSyncDelay.restart();
                        }
                    }

                    DockButton {
                        id: sessionBtn
                        buttonHeight: dockWindow.compactDock ? 42 : 62
                        iconText: "\uf011"
                        iconColor: root.sessionOpen ? root.colDark : root.colRed
                        baseColor: root.sessionOpen ? root.colRed : root.colSurface
                        iconSize: dockWindow.compactDock ? 22 : 28
                        onClicked: root.toggleSession()
                    }
                }
            }
        }
    }

    // Native Wayland Outside-Click / Escape Dismiss Backdrop
    PanelWindow {
        id: dismissBackdrop
        anchors {
            left: true
            right: true
            top: true
            bottom: true
        }
        visible: root.widgetsActive || root.sessionActive
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand

        MouseArea {
            anchors.fill: parent
            onClicked: root.closeAllMenus()
        }
        Shortcut {
            sequence: "Escape"
            onActivated: root.closeAllMenus()
        }
    }

    // Large Readable Widget Drawer (Overlay layer matching dock height)
    PanelWindow {
        id: widgetsPopup
        anchors {
            left: true
            top: true
            bottom: true
        }
        margins {
            left: 140
            top: 76
            bottom: 12
        }
        implicitWidth: 844
        visible: root.widgetsActive
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay

        Item {
            anchors.fill: parent
            clip: true

            Rectangle {
                id: drawerBg
                width: parent.width
                height: parent.height
                x: root.widgetsOpen ? 0 : -44
                opacity: root.widgetsOpen ? 1.0 : 0.0
                radius: 24
                color: root.colPopupBase
                border.color: root.colSurface1
                border.width: 2

                Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                Behavior on opacity { NumberAnimation { duration: 140 } }

                Flickable {
                    anchors.fill: parent
                    anchors.margins: 28
                    contentWidth: width
                    contentHeight: drawerCol.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    interactive: contentHeight > height

                    ColumnLayout {
                        id: drawerCol
                        width: parent.width
                        spacing: 20

                        RowLayout {
                            Layout.fillWidth: true
                            Row {
                                spacing: 14
                                Layout.fillWidth: true
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "\U000f003b"
                                    color: root.colBlue
                                    font.family: root.uiFont
                                    font.pixelSize: 34
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "Widgets"
                                    color: root.colText
                                    font.family: root.uiFont
                                    font.pixelSize: 30
                                    font.bold: true
                                }
                            }
                            Rectangle {
                                width: 48
                                height: 48
                                radius: 16
                                color: closeBtnArea.pressed ? root.colBlue : root.colSurface
                                border.color: root.colSurface1
                                border.width: 1
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uf00d"
                                    color: closeBtnArea.pressed ? root.colDark : root.colSubtext
                                    font.family: root.uiFont
                                    font.pixelSize: 22
                                }
                                MouseArea {
                                    id: closeBtnArea
                                    anchors.fill: parent
                                    onClicked: root.closeWidgets()
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 18

__WEATHER_CARD__

                            Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: focusCol.implicitHeight + 40
                                radius: 20
                                color: root.colSurface
                                border.color: root.colSurface1
                                border.width: 1

                                Column {
                                    id: focusCol
                                    anchors.fill: parent
                                    anchors.margins: 20
                                    spacing: 8
                                    Row {
                                        spacing: 12
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "\U000f05a9"
                                            color: root.colTeal
                                            font.family: root.uiFont
                                            font.pixelSize: 38
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "Termux"
                                            color: root.colText
                                            font.family: root.uiFont
                                            font.pixelSize: 32
                                            font.bold: true
                                        }
                                    }
                                    Text {
                                        text: "Do Not Disturb · On"
                                        color: root.colSubtext
                                        font.family: root.uiFont
                                        font.pixelSize: 21
                                    }
                                }
                            }
                        }

__ANDROID_STATUS_CARD__
__MEDIA_CARD__

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: calCol.implicitHeight + 44
                            radius: 20
                            color: root.colSurface
                            border.color: root.colSurface1
                            border.width: 1

                            Column {
                                id: calCol
                                anchors.fill: parent
                                anchors.leftMargin: 24
                                anchors.rightMargin: 24
                                anchors.topMargin: 22
                                anchors.bottomMargin: 22
                                spacing: 14

                                RowLayout {
                                    width: parent.width
                                    Row {
                                        spacing: 12
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "\U000f00ed"
                                            color: root.colBlue
                                            font.family: root.uiFont
                                            font.pixelSize: 28
                                        }
                                        Text {
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: "November 2026"
                                            color: root.colText
                                            font.family: root.uiFont
                                            font.pixelSize: 24
                                            font.bold: true
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        text: "\U000f0141   \U000f0142"
                                        color: root.colSubtext
                                        font.family: root.uiFont
                                        font.pixelSize: 24
                                    }
                                }

                                GridLayout {
                                    width: parent.width
                                    columns: 7
                                    columnSpacing: 6
                                    rowSpacing: 8

                                    Repeater {
                                        model: root.calendarHeaders
                                        delegate: Item {
                                            required property string modelData
                                            Layout.fillWidth: true
                                            implicitHeight: 42
                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData
                                                color: root.colSubtext
                                                font.family: root.uiFont
                                                font.pixelSize: 21
                                                font.bold: true
                                            }
                                        }
                                    }

                                    Repeater {
                                        model: root.calendarDays
                                        delegate: Rectangle {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            implicitHeight: 46
                                            radius: 14
                                            color: modelData.cls === "today" ? root.colBlue : "transparent"
                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData.d
                                                color: modelData.cls === "today"
                                                    ? root.colDark
                                                    : (modelData.cls === "muted"
                                                        ? root.colSurface1
                                                        : (modelData.cls === "wknd" ? root.colSubtext : root.colText))
                                                font.family: root.uiFont
                                                font.pixelSize: 23
                                                font.bold: modelData.cls === "today"
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            implicitHeight: agendaCol.implicitHeight + 44
                            radius: 20
                            color: root.colSurface
                            border.color: root.colSurface1
                            border.width: 1

                            Column {
                                id: agendaCol
                                anchors.fill: parent
                                anchors.leftMargin: 24
                                anchors.rightMargin: 24
                                anchors.topMargin: 22
                                anchors.bottomMargin: 22
                                spacing: 14

                                Row {
                                    spacing: 12
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "\U000f039a"
                                        color: root.colMauve
                                        font.family: root.uiFont
                                        font.pixelSize: 28
                                    }
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "Agenda"
                                        color: root.colText
                                        font.family: root.uiFont
                                        font.pixelSize: 24
                                        font.bold: true
                                    }
                                }

                                Repeater {
                                    model: [
                                        { t: "19:00", col: root.colBlue, txt: "Build Termux X11 Dock" },
                                        { t: "21:30", col: root.colMauve, txt: "Sync Dotfiles & GUI Rules" },
                                        { t: "22:45", col: root.colTeal, txt: "Wrap Up Workspace Widgets" }
                                    ]
                                    delegate: Rectangle {
                                        required property var modelData
                                        width: parent.width
                                        height: 54
                                        radius: 14
                                        color: root.colPopupBase
                                        border.color: root.colSurface1
                                        border.width: 1
                                        Row {
                                            anchors.verticalCenter: parent.verticalCenter
                                            anchors.left: parent.left
                                            anchors.leftMargin: 16
                                            spacing: 16
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: modelData.t
                                                color: modelData.col
                                                font.family: root.uiFont
                                                font.pixelSize: 21
                                                font.bold: true
                                            }
                                            Text {
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: modelData.txt
                                                color: root.colText
                                                font.family: root.uiFont
                                                font.pixelSize: 21
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Raised Session Menu (Bottom-left overlay)
    PanelWindow {
        id: sessionPopup
        anchors {
            left: true
            bottom: true
        }
        margins {
            left: 140
            bottom: 12
        }
        implicitWidth: 330
        implicitHeight: 368
        visible: root.sessionActive
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay

        Item {
            anchors.fill: parent
            clip: true

            Rectangle {
                width: parent.width
                height: 330
                y: root.sessionOpen ? 0 : 28
                opacity: root.sessionOpen ? 1.0 : 0.0
                radius: 22
                color: root.colPopupBase
                border.color: root.colSurface1
                border.width: 2

                Behavior on y { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                Behavior on opacity { NumberAnimation { duration: 130 } }

                Column {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 18

                    Repeater {
                        model: [
                            { label: "Reload Shell", icon: "\uf021", color: root.colBlue, cmd: ["sh", "-c", "$HOME/.config/quickshell/launch-wayland.sh &"] },
                            { label: "Reload WM", icon: "\uf021", color: root.colTeal, cmd: root.isSway ? ["swaymsg", "reload"] : ["labwc", "--reconfigure"] },
                            { label: "Exit Wayland", icon: "\uf011", color: root.colRed, cmd: root.isSway ? ["swaymsg", "exit"] : ["labwc", "--exit"] }
                        ]
                        delegate: Rectangle {
                            required property var modelData
                            width: parent.width
                            height: 86
                            radius: 16
                            color: popArea.pressed ? root.colBlue : root.colSurface
                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: 20
                                spacing: 16
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.icon
                                    color: popArea.pressed ? root.colDark : modelData.color
                                    font.family: root.uiFont
                                    font.pixelSize: 26
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.label
                                    color: popArea.pressed ? root.colDark : root.colText
                                    font.family: root.uiFont
                                    font.pixelSize: 21
                                    font.bold: true
                                }
                            }
                            MouseArea {
                                id: popArea
                                anchors.fill: parent
                                anchors.leftMargin: -18
                                anchors.rightMargin: -18
                                anchors.topMargin: -9
                                anchors.bottomMargin: -9
                                onClicked: {
                                    root.closeSession();
                                    root.runCmd(modelData.cmd);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
"""

HIDE_CURSOR_PY = """#!/data/data/com.termux/files/usr/bin/python3
\"\"\"Auto-hide the X11 cursor when idle or right after simulated touch taps.\"\"\"

import os
import signal
import sys
import time
from ctypes import CDLL, byref, c_char_p, c_int, c_uint, c_ulong, c_void_p


def main() -> int:
    x11 = CDLL("libX11.so.6")
    xf = CDLL("libXfixes.so")

    x11.XOpenDisplay.restype = c_void_p
    x11.XOpenDisplay.argtypes = [c_char_p]
    x11.XDefaultRootWindow.restype = c_ulong
    x11.XDefaultRootWindow.argtypes = [c_void_p]
    x11.XSync.argtypes = [c_void_p, c_int]
    x11.XQueryPointer.restype = c_int
    x11.XQueryPointer.argtypes = [
        c_void_p, c_ulong, c_void_p, c_void_p,
        c_void_p, c_void_p, c_void_p, c_void_p, c_void_p,
    ]
    x11.XCloseDisplay.argtypes = [c_void_p]

    xf.XFixesQueryExtension.argtypes = [c_void_p, c_void_p, c_void_p]
    xf.XFixesQueryVersion.argtypes = [c_void_p, c_void_p, c_void_p]
    xf.XFixesHideCursor.argtypes = [c_void_p, c_ulong]
    xf.XFixesShowCursor.argtypes = [c_void_p, c_ulong]

    disp_name = os.environ.get("DISPLAY", ":0").encode()
    dpy = x11.XOpenDisplay(disp_name)
    if not dpy:
        return 1

    ev, er = c_int(), c_int()
    if not xf.XFixesQueryExtension(dpy, byref(ev), byref(er)):
        return 1
    maj, minv = c_int(5), c_int(0)
    xf.XFixesQueryVersion(dpy, byref(maj), byref(minv))

    root = x11.XDefaultRootWindow(dpy)
    r_win, c_win = c_ulong(), c_ulong()
    rx, ry, wx, wy = c_int(), c_int(), c_int(), c_int()
    mask = c_uint()

    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    pid_path = os.path.join(
        os.environ.get("TMPDIR", "/data/data/com.termux/files/usr/tmp"),
        "hide-cursor.pid",
    )
    try:
        with open(pid_path, "w") as pf:
            pf.write(str(os.getpid()))
    except OSError:
        pid_path = ""

    x11.XQueryPointer(dpy, root, byref(r_win), byref(c_win), byref(rx), byref(ry), byref(wx), byref(wy), byref(mask))
    last_x, last_y = rx.value, ry.value
    was_pressed = bool(mask.value & 0x1F00)
    hidden = True
    xf.XFixesHideCursor(dpy, root)
    x11.XSync(dpy, 0)
    hide_at = 0.0

    while running:
        time.sleep(0.08)
        if not x11.XQueryPointer(
            dpy, root, byref(r_win), byref(c_win), byref(rx), byref(ry), byref(wx), byref(wy), byref(mask)
        ):
            break

        now = time.monotonic()
        moved = (rx.value != last_x) or (ry.value != last_y)
        pressed = bool(mask.value & 0x1F00)
        last_x, last_y = rx.value, ry.value

        if pressed:
            was_pressed = True
            hide_at = now + 0.5
        elif was_pressed and not pressed:
            # Touch tap / click finished: hide quickly so no stray cursor lingers
            was_pressed = False
            hide_at = now + 0.15
            if not hidden:
                xf.XFixesHideCursor(dpy, root)
                x11.XSync(dpy, 0)
                hidden = True
        elif moved:
            if hidden:
                xf.XFixesShowCursor(dpy, root)
                x11.XSync(dpy, 0)
                hidden = False
            hide_at = now + 0.6
        elif not hidden and now >= hide_at:
            xf.XFixesHideCursor(dpy, root)
            x11.XSync(dpy, 0)
            hidden = True

    if hidden:
        xf.XFixesShowCursor(dpy, root)
        x11.XSync(dpy, 0)
    if pid_path:
        try:
            os.remove(pid_path)
        except OSError:
            pass
    x11.XCloseDisplay(dpy)
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

ROFI_CONFIG = """/* Catppuccin Mocha touch-coherent Rofi theme matching Eww & Polybar */
configuration {
    modi: "drun,run,window";
    font: "JetBrainsMono Nerd Font 17";
    show-icons: false;
    display-drun: "󰀻 Apps";
    display-run: " Run";
    display-window: " Win";
    drun-display-format: "{name}";
    click-to-exit: true;
    me-select-entry: "";
    me-accept-entry: "MousePrimary";
}

* {
    base: #1e1e2e;
    base-glass: rgba(30, 30, 46, 95 %);
    surface: #313244;
    surface1: #45475a;
    text: #cdd6f4;
    subtext: #a6adc8;
    blue: #89b4fa;
    red: #f38ba8;
    dark: #1e1e2e;
    transparent: rgba(0, 0, 0, 0 %);

    background-color: @transparent;
    text-color: @text;
}

window {
    width: 720px;
    background-color: @base-glass;
    border: 2px;
    border-color: @surface1;
    border-radius: 22px;
    padding: 18px;
}

mainbox {
    spacing: 14px;
    children: [ inputbar, listview, mode-switcher ];
}

inputbar {
    children: [ prompt, entry ];
    spacing: 12px;
    padding: 14px 18px;
    background-color: @surface;
    border: 1px;
    border-color: @surface1;
    border-radius: 16px;
}

prompt, entry {
    background-color: @transparent;
}

prompt {
    text-color: @blue;
}

entry {
    placeholder: "Search...";
    placeholder-color: @subtext;
    text-color: @text;
}

listview {
    lines: 6;
    columns: 1;
    fixed-height: false;
    scrollbar: false;
    spacing: 10px;
}

element {
    padding: 16px 18px;
    border-radius: 16px;
    background-color: @surface;
    border: 1px;
    border-color: @surface1;
    text-color: @text;
}

element normal.normal,
element alternate.normal {
    background-color: @surface;
    border: 1px;
    border-color: @surface1;
    text-color: @text;
}

element normal.active,
element alternate.active {
    background-color: @surface;
    border: 1px;
    border-color: @blue;
    text-color: @blue;
}

element normal.urgent,
element alternate.urgent {
    background-color: @surface;
    border: 1px;
    border-color: @red;
    text-color: @red;
}

element selected,
element selected.normal,
element selected.active {
    background-color: @blue;
    border: 1px;
    border-color: @blue;
    text-color: @dark;
}

element selected.urgent {
    background-color: @red;
    border: 1px;
    border-color: @red;
    text-color: @dark;
}

element-text {
    background-color: @transparent;
    text-color: inherit;
    vertical-align: 0.5;
}

mode-switcher {
    spacing: 10px;
}

button,
button normal {
    padding: 12px 16px;
    border-radius: 14px;
    background-color: @surface;
    border: 1px;
    border-color: @surface1;
    text-color: @subtext;
}

button selected {
    background-color: @blue;
    border: 1px;
    border-color: @blue;
    text-color: @dark;
}

textbox {
    padding: 12px 16px;
    border-radius: 14px;
    background-color: @surface;
    text-color: @text;
}
"""

PICOM_CONF = """# Lightweight picom v13 config for rounded corners on Termux:X11
# Uses xrender for low-overhead stability on Mali; try "glx" for smoother anti-aliased corners.
backend = "xrender";

corner-radius = 18;
shadow = false;
fading = false;
vsync = true;
use-damage = false;

rules: ({
  match = "window_type = 'dock'    || "
          "window_type = 'desktop' || "
          "fullscreen";
  corner-radius = 0;
})
"""

XFCE4_TERMINAL_RC = """[Configuration]
FontName=JetBrainsMono Nerd Font 19
FontUseSystem=FALSE
MiscMenubarDefault=FALSE
MiscConfirmClose=FALSE
MiscDefaultGeometry=110x34
ScrollingLines=10000
ColorForeground=#cdd6f4
ColorBackground=#1e1e2e
ColorCursor=#f5e0dc
ColorPalette=#45475a;#f38ba8;#a6e3a1;#f9e2af;#89b4fa;#f5c2e7;#94e2d5;#bac2de;#585b70;#f38ba8;#a6e3a1;#f9e2af;#89b4fa;#f5c2e7;#94e2d5;#a6adc8
"""

XFCE4_TERMINAL_XML = """<?xml version="1.1" encoding="UTF-8"?>

<channel name="xfce4-terminal" version="1.0">
  <property name="color-foreground" type="string" value="#cdd6f4"/>
  <property name="color-background" type="string" value="#1e1e2e"/>
  <property name="color-cursor" type="string" value="#f5e0dc"/>
  <property name="color-palette" type="string" value="#45475a;#f38ba8;#a6e3a1;#f9e2af;#89b4fa;#f5c2e7;#94e2d5;#bac2de;#585b70;#f38ba8;#a6e3a1;#f9e2af;#89b4fa;#f5c2e7;#94e2d5;#a6adc8"/>
  <property name="font-name" type="string" value="JetBrainsMono Nerd Font 19"/>
  <property name="font-use-system" type="bool" value="false"/>
  <property name="misc-default-geometry" type="string" value="110x34"/>
  <property name="misc-menubar-default" type="bool" value="false"/>
  <property name="misc-confirm-close" type="bool" value="false"/>
  <property name="scrolling-lines" type="uint" value="10000"/>
</channel>
"""

START_X11_SH = """#!/data/data/com.termux/files/usr/bin/bash
set -u

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
export DISPLAY=":0"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-$PREFIX/tmp}"
export TMPDIR="${TMPDIR:-$XDG_RUNTIME_DIR}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
export BSPWM_SOCKET="$XDG_RUNTIME_DIR/bspwm_0_0-socket"
export XCURSOR_THEME="TouchDot-Mocha"
export XCURSOR_SIZE="32"

VIRGL_PID=""
cleanup() {
  eww kill >/dev/null 2>&1 || true
  pkill -x eww quickshell qs-native polybar fastcompmgr picom sxhkd bspwm termux-x11 2>/dev/null || true
  [ -f "$TMPDIR/hide-cursor.pid" ] && kill "$(cat "$TMPDIR/hide-cursor.pid")" 2>/dev/null || true
  [ -f "$TMPDIR/eww-watch.pid" ] && kill "$(cat "$TMPDIR/eww-watch.pid")" 2>/dev/null || true
  [ -f "$TMPDIR/qs-watch.pid" ] && kill "$(cat "$TMPDIR/qs-watch.pid")" 2>/dev/null || true
  [ -n "$VIRGL_PID" ] && kill "$VIRGL_PID" 2>/dev/null || true
  rm -f "$XDG_RUNTIME_DIR/.virgl_test" "$BSPWM_SOCKET" "$XDG_RUNTIME_DIR/.X11-unix/X0" "$TMPDIR/hide-cursor.pid" "$TMPDIR/eww-watch.pid" "$TMPDIR/qs-watch.pid"
}
trap cleanup EXIT INT TERM

# Clean up stale X11 / WM / VirGL processes from an earlier session
eww kill >/dev/null 2>&1 || true
[ -f "$TMPDIR/eww-watch.pid" ] && kill "$(cat "$TMPDIR/eww-watch.pid")" 2>/dev/null || true
[ -f "$TMPDIR/qs-watch.pid" ] && kill "$(cat "$TMPDIR/qs-watch.pid")" 2>/dev/null || true
rm -f "$TMPDIR/eww-watch.pid" "$TMPDIR/qs-watch.pid"
pkill -x eww quickshell qs-native polybar fastcompmgr picom sxhkd bspwm termux-x11 virgl_test_serv 2>/dev/null || true
[ -f "$TMPDIR/hide-cursor.pid" ] && kill "$(cat "$TMPDIR/hide-cursor.pid")" 2>/dev/null || true
pkill -f '[v]irgl_test_server_android' 2>/dev/null || true
pkill -f "com.termux.x11" 2>/dev/null || true
rm -f "$XDG_RUNTIME_DIR/.virgl_test" "$BSPWM_SOCKET" "$XDG_RUNTIME_DIR/.X11-unix/X0"
sleep 0.5

# Hardware OpenGL ES -> Vulkan passthrough via ANGLE for Qt Quick / GL apps
if command -v virgl_test_server_android >/dev/null 2>&1; then
  virgl_test_server_android --multi-clients --angle-vulkan >/dev/null 2>&1 &
  VIRGL_PID=$!
  i=0
  while [ "$i" -lt 20 ] && [ ! -S "$XDG_RUNTIME_DIR/.virgl_test" ]; do
    i=$((i + 1))
    sleep 0.05
  done
  export GALLIUM_DRIVER=virpipe
fi

if command -v pulseaudio >/dev/null 2>&1; then
  pulseaudio --start --exit-idle-time=-1 2>/dev/null || true
fi

# Open the Termux:X11 Android activity
am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity >/dev/null 2>&1 || true

# Launch X11 and start bspwm once :0 is ready
if command -v dbus-launch >/dev/null 2>&1; then
  termux-x11 :0 -xstartup "dbus-launch --exit-with-session bspwm"
else
  termux-x11 :0 -xstartup "bspwm"
fi
"""

SWAY_CONFIG = """# Catppuccin Mocha Sway config for Termux Wayland (touch + 13" readable)
set $mod Mod1
xwayland enable

font pango:JetBrainsMono Nerd Font 14

gaps inner 12
gaps outer 8
default_border pixel 2
default_floating_border pixel 2
hide_edge_borders smart

# Catppuccin Mocha borders
client.focused          #89b4fa #1e1e2e #cdd6f4 #cba6f7 #89b4fa
client.focused_inactive #45475a #1e1e2e #a6adc8 #45475a #45475a
client.unfocused        #313244 #1e1e2e #a6adc8 #313244 #313244
client.urgent           #f38ba8 #1e1e2e #cdd6f4 #f38ba8 #f38ba8

# Terminal & Launchers
bindsym $mod+Return exec foot
bindsym Mod4+Return exec foot
bindsym $mod+Shift+Return exec xfce4-terminal
bindsym $mod+d exec rofi -show drun
bindsym Mod4+d exec rofi -show drun
bindsym $mod+Tab exec rofi -show window

# Window Controls
bindsym $mod+q kill
bindsym $mod+Shift+q kill
bindsym $mod+f fullscreen toggle
bindsym $mod+Shift+space floating toggle
bindsym $mod+space focus mode_toggle

# Focus & Move
bindsym $mod+h focus left
bindsym $mod+j focus down
bindsym $mod+k focus up
bindsym $mod+l focus right
bindsym $mod+Left focus left
bindsym $mod+Down focus down
bindsym $mod+Up focus up
bindsym $mod+Right focus right

bindsym $mod+Shift+h move left
bindsym $mod+Shift+j move down
bindsym $mod+Shift+k move up
bindsym $mod+Shift+l move right

# Layout
bindsym $mod+t layout tabbed
bindsym $mod+e layout toggle split
bindsym $mod+w layout stacking

# Workspaces 1-6
bindsym $mod+1 workspace number 1
bindsym $mod+2 workspace number 2
bindsym $mod+3 workspace number 3
bindsym $mod+4 workspace number 4
bindsym $mod+5 workspace number 5
bindsym $mod+6 workspace number 6

bindsym $mod+Shift+1 move container to workspace number 1
bindsym $mod+Shift+2 move container to workspace number 2
bindsym $mod+Shift+3 move container to workspace number 3
bindsym $mod+Shift+4 move container to workspace number 4
bindsym $mod+Shift+5 move container to workspace number 5
bindsym $mod+Shift+6 move container to workspace number 6

# Reload / Exit
bindsym $mod+Shift+r reload
bindsym $mod+Shift+e exit

# Wallpaper + Native Wayland Quickshell Dock/Topbar
exec_always sh -c '[ -f "$HOME/.local/share/wallpapers/wallpaper.jpg" ] && pkill -x swaybg 2>/dev/null; [ -f "$HOME/.local/share/wallpapers/wallpaper.jpg" ] && swaybg -i "$HOME/.local/share/wallpapers/wallpaper.jpg" -m fill &'
exec_always sh -c '"$HOME/.config/quickshell/launch-wayland.sh"'
"""

LABWC_RC_XML = """<?xml version="1.0"?>
<labwc_config>
  <core>
    <gap>12</gap>
  </core>
  <placement>
    <policy>center</policy>
  </placement>
  <desktops>
    <popupTime>800</popupTime>
    <names>
      <name>1</name>
      <name>2</name>
      <name>3</name>
      <name>4</name>
      <name>5</name>
      <name>6</name>
    </names>
  </desktops>
  <theme>
    <name>Catppuccin-Mocha</name>
    <cornerRadius>16</cornerRadius>
    <font name="JetBrainsMono Nerd Font" size="13" />
  </theme>
  <focus>
    <followMouse>yes</followMouse>
  </focus>
  <keyboard>
    <default />
    <keybind key="A-Return">
      <action name="Execute" command="foot" />
    </keybind>
    <keybind key="W-Return">
      <action name="Execute" command="foot" />
    </keybind>
    <keybind key="A-d">
      <action name="Execute" command="rofi -show drun" />
    </keybind>
    <keybind key="W-d">
      <action name="Execute" command="rofi -show drun" />
    </keybind>
    <keybind key="A-Tab">
      <action name="NextWindow" />
    </keybind>
    <keybind key="A-q">
      <action name="Close" />
    </keybind>
    <keybind key="A-S-q">
      <action name="Close" />
    </keybind>
    <keybind key="A-f">
      <action name="ToggleFullscreen" />
    </keybind>
    <keybind key="A-m">
      <action name="ToggleMaximize" />
    </keybind>
    <keybind key="A-1">
      <action name="GoToDesktop" to="1" />
    </keybind>
    <keybind key="A-2">
      <action name="GoToDesktop" to="2" />
    </keybind>
    <keybind key="A-3">
      <action name="GoToDesktop" to="3" />
    </keybind>
    <keybind key="A-4">
      <action name="GoToDesktop" to="4" />
    </keybind>
    <keybind key="A-5">
      <action name="GoToDesktop" to="5" />
    </keybind>
    <keybind key="A-6">
      <action name="GoToDesktop" to="6" />
    </keybind>
    <keybind key="A-S-1">
      <action name="SendToDesktop" to="1" />
    </keybind>
    <keybind key="A-S-2">
      <action name="SendToDesktop" to="2" />
    </keybind>
    <keybind key="A-S-3">
      <action name="SendToDesktop" to="3" />
    </keybind>
    <keybind key="A-S-4">
      <action name="SendToDesktop" to="4" />
    </keybind>
    <keybind key="A-S-5">
      <action name="SendToDesktop" to="5" />
    </keybind>
    <keybind key="A-S-6">
      <action name="SendToDesktop" to="6" />
    </keybind>
    <keybind key="A-S-r">
      <action name="Reconfigure" />
    </keybind>
    <keybind key="A-S-e">
      <action name="Exit" />
    </keybind>
  </keyboard>
</labwc_config>
"""

LABWC_THEMERC = """border.width: 2
padding.width: 6
padding.height: 6
window.active.title.bg.color: #1e1e2e
window.active.label.text.color: #cdd6f4
window.active.border.color: #89b4fa
window.inactive.title.bg.color: #181825
window.inactive.label.text.color: #a6adc8
window.inactive.border.color: #313244
window.active.button.unpressed.image.color: #cdd6f4
window.inactive.button.unpressed.image.color: #a6adc8
osd.bg.color: #1e1e2e
osd.border.color: #45475a
osd.border.width: 2
osd.label.text.color: #cdd6f4
"""

LABWC_AUTOSTART = """#!/data/data/com.termux/files/usr/bin/sh
if command -v swaybg >/dev/null 2>&1 && [ -f "$HOME/.local/share/wallpapers/wallpaper.jpg" ]; then
  swaybg -i "$HOME/.local/share/wallpapers/wallpaper.jpg" -m fill >/dev/null 2>&1 &
fi
"${XDG_CONFIG_HOME:-$HOME/.config}/quickshell/launch-wayland.sh" &
"""

FOOT_INI = """[main]
font=JetBrainsMono Nerd Font:size=19
initial-window-size-chars=110x34
pad=18x18 center-when-maximized-and-fullscreen
initial-color-theme=dark

[cursor]
style=block

[colors-dark]
alpha=0.94
foreground=cdd6f4
background=1e1e2e
cursor=1e1e2e f5e0dc
regular0=45475a
regular1=f38ba8
regular2=a6e3a1
regular3=f9e2af
regular4=89b4fa
regular5=f5c2e7
regular6=94e2d5
regular7=bac2de
bright0=585b70
bright1=f38ba8
bright2=a6e3a1
bright3=f9e2af
bright4=89b4fa
bright5=f5c2e7
bright6=94e2d5
bright7=a6adc8
16=fab387
17=f5e0dc
selection-foreground=cdd6f4
selection-background=45475a
search-box-no-match=1e1e2e f38ba8
search-box-match=cdd6f4 313244
jump-labels=1e1e2e fab387
urls=89b4fa

[csd]
preferred=server
size=28
color=1e1e2e
border-width=2
border-color=313244
button-color=313244
button-minimize-color=89b4fa
button-maximize-color=a6e3a1
button-close-color=f38ba8
"""

TGUI_FIX_C = """#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdlib.h>

#define DRM_FORMAT_XRGB8888 0x34325258u
#define DRM_FORMAT_ARGB8888 0x34325241u
#define DRM_FORMAT_ABGR8888 0x34324241u
#define WL_OUTPUT_TRANSFORM_NORMAL 0
#define WL_OUTPUT_TRANSFORM_FLIPPED_180 6

__attribute__((constructor))
static void _tgui_fix_init(void) {
    /* Prevent child processes (quickshell, foot, rofi) from inheriting LD_PRELOAD */
    unsetenv("LD_PRELOAD");
}

void wlr_output_state_set_render_format(void *state, uint32_t format) {
    static void (*real_fn)(void *, uint32_t) = NULL;
    if (!real_fn) {
        real_fn = dlsym(RTLD_NEXT, "wlr_output_state_set_render_format");
    }
    if (format == DRM_FORMAT_XRGB8888 || format == DRM_FORMAT_ARGB8888) {
        format = DRM_FORMAT_ABGR8888;
    }
    if (real_fn) {
        real_fn(state, format);
    }
}

void wlr_output_state_set_transform(void *state, int transform) {
    static void (*real_fn)(void *, int) = NULL;
    if (!real_fn) {
        real_fn = dlsym(RTLD_NEXT, "wlr_output_state_set_transform");
    }
    if (transform == WL_OUTPUT_TRANSFORM_NORMAL) {
        transform = WL_OUTPUT_TRANSFORM_FLIPPED_180;
    }
    if (real_fn) {
        real_fn(state, transform);
    }
}
"""

QS_NATIVE_C = r"""#define _GNU_SOURCE
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include <X11/Xlib.h>
#include <X11/extensions/XInput2.h>
#include <X11/extensions/Xfixes.h>

static volatile sig_atomic_t g_running = 1;

static void on_term_sig(int sig) {
    (void)sig;
    g_running = 0;
}

static void install_signals(void) {
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = on_term_sig;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    signal(SIGPIPE, SIG_IGN);
}

static int64_t mono_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000LL + (int64_t)(ts.tv_nsec / 1000000LL);
}

static void sleep_check_ms(int total_ms) {
    int rem = total_ms;
    while (g_running && rem > 0) {
        int step = rem > 100 ? 100 : rem;
        usleep((useconds_t)step * 1000U);
        rem -= step;
    }
}

static void json_write_str(FILE *f, const char *s) {
    fputc('"', f);
    if (s) {
        for (const unsigned char *p = (const unsigned char *)s; *p; p++) {
            unsigned char c = *p;
            if (c == '"') fputs("\\\"", f);
            else if (c == '\\') fputs("\\\\", f);
            else if (c == '\b') fputs("\\b", f);
            else if (c == '\f') fputs("\\f", f);
            else if (c == '\n') fputs("\\n", f);
            else if (c == '\r') fputs("\\r", f);
            else if (c == '\t') fputs("\\t", f);
            else if (c < 0x20) fprintf(f, "\\u%04x", (unsigned)c);
            else fputc((int)c, f);
        }
    }
    fputc('"', f);
}

/* --- /proc CPU & Memory Readers ------------------------------------------ */

static uint64_t read_total_jiffies(void) {
    DIR *d = opendir("/proc");
    if (!d) return 0;
    uint64_t total = 0;
    struct dirent *ent;
    char path[64];
    char buf[2048];
    while ((ent = readdir(d)) != NULL) {
        if (!isdigit((unsigned char)ent->d_name[0])) continue;
        bool all_digit = true;
        for (const char *c = ent->d_name; *c; c++) {
            if (!isdigit((unsigned char)*c)) {
                all_digit = false;
                break;
            }
        }
        if (!all_digit) continue;
        snprintf(path, sizeof(path), "/proc/%s/stat", ent->d_name);
        int fd = open(path, O_RDONLY);
        if (fd < 0) continue;
        ssize_t n = read(fd, buf, sizeof(buf) - 1);
        close(fd);
        if (n <= 0) continue;
        buf[n] = '\0';
        char *rp = strrchr(buf, ')');
        if (!rp || rp[1] == '\0') continue;
        char *p = rp + 2;
        int field = 0;
        uint64_t utime = 0, stime = 0;
        while (*p && field <= 12) {
            while (*p == ' ') p++;
            if (!*p) break;
            char *end = p;
            while (*end && *end != ' ') end++;
            if (field == 11) utime = strtoull(p, NULL, 10);
            else if (field == 12) {
                stime = strtoull(p, NULL, 10);
                total += utime + stime;
                break;
            }
            p = end;
            field++;
        }
    }
    closedir(d);
    return total;
}

static void read_mem_info(char *used_buf, size_t ucap, char *tot_buf, size_t tcap, int *pct_out) {
    FILE *f = fopen("/proc/meminfo", "r");
    long mem_tot = 0, mem_avail = -1, mem_free = 0;
    if (f) {
        char line[256];
        while (fgets(line, sizeof(line), f)) {
            long val = 0;
            if (sscanf(line, "MemTotal: %ld kB", &val) == 1) mem_tot = val;
            else if (sscanf(line, "MemAvailable: %ld kB", &val) == 1) mem_avail = val;
            else if (sscanf(line, "MemFree: %ld kB", &val) == 1) mem_free = val;
        }
        fclose(f);
    }
    if (mem_avail < 0) mem_avail = mem_free;
    if (mem_tot <= 0) {
        snprintf(used_buf, ucap, "0.0");
        snprintf(tot_buf, tcap, "0.0");
        *pct_out = 0;
        return;
    }
    long used_kb = mem_tot - mem_avail;
    if (used_kb < 0) used_kb = 0;
    int pct = (int)llround((double)used_kb * 100.0 / (double)mem_tot);
    if (pct < 0) pct = 0;
    if (pct > 100) pct = 100;
    snprintf(used_buf, ucap, "%.1f", (double)used_kb / 1048576.0);
    snprintf(tot_buf, tcap, "%.1f", (double)mem_tot / 1048576.0);
    *pct_out = pct;
}

/* --- Subprocess Capture + Minimal JSON Extractors ------------------------ */

static bool run_cmd_capture(const char *const argv[], char *out, size_t cap, int timeout_ms) {
    if (!out || cap == 0) return false;
    out[0] = '\0';
    int pfd[2];
    if (pipe2(pfd, O_CLOEXEC) != 0) return false;

    pid_t pid = fork();
    if (pid < 0) {
        close(pfd[0]);
        close(pfd[1]);
        return false;
    }
    if (pid == 0) {
        close(pfd[0]);
        dup2(pfd[1], STDOUT_FILENO);
        close(pfd[1]);
        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0) {
            dup2(devnull, STDIN_FILENO);
            dup2(devnull, STDERR_FILENO);
            if (devnull > 2) close(devnull);
        }
        execvp(argv[0], (char *const *)argv);
        _exit(127);
    }
    close(pfd[1]);

    int fl = fcntl(pfd[0], F_GETFL, 0);
    if (fl >= 0) fcntl(pfd[0], F_SETFL, fl | O_NONBLOCK);

    size_t len = 0;
    int64_t deadline = mono_ms() + timeout_ms;
    bool timed_out = false;
    for (;;) {
        int64_t left = deadline - mono_ms();
        if (left <= 0) {
            timed_out = true;
            break;
        }
        struct pollfd pf = { .fd = pfd[0], .events = POLLIN };
        int rc = poll(&pf, 1, (int)left);
        if (rc < 0) {
            if (errno == EINTR && g_running) continue;
            break;
        }
        if (rc == 0) {
            timed_out = true;
            break;
        }
        if (pf.revents & (POLLIN | POLLHUP)) {
            char tmp[2048];
            ssize_t r = read(pfd[0], tmp, sizeof(tmp));
            if (r > 0) {
                size_t copy = (size_t)r;
                if (len + copy >= cap) copy = cap - 1 - len;
                if (copy > 0) {
                    memcpy(out + len, tmp, copy);
                    len += copy;
                    out[len] = '\0';
                }
            } else if (r == 0) {
                break;
            } else if (errno != EAGAIN && errno != EWOULDBLOCK) {
                break;
            }
        }
    }
    close(pfd[0]);
    if (timed_out) kill(pid, SIGKILL);
    int st = 0;
    waitpid(pid, &st, 0);
    return !timed_out && WIFEXITED(st) && WEXITSTATUS(st) == 0 && len > 0;
}

static const char *json_find_val(const char *json, const char *key) {
    char pat[96];
    snprintf(pat, sizeof(pat), "\"%s\"", key);
    const char *p = json;
    size_t plen = strlen(pat);
    while ((p = strstr(p, pat)) != NULL) {
        const char *q = p + plen;
        while (*q == ' ' || *q == '\t' || *q == '\r' || *q == '\n') q++;
        if (*q == ':') {
            q++;
            while (*q == ' ' || *q == '\t' || *q == '\r' || *q == '\n') q++;
            return q;
        }
        p = q;
    }
    return NULL;
}

static bool json_get_double(const char *json, const char *key, double *out) {
    const char *v = json_find_val(json, key);
    if (!v || (*v != '-' && !isdigit((unsigned char)*v))) return false;
    char *end = NULL;
    double val = strtod(v, &end);
    if (end == v) return false;
    *out = val;
    return true;
}

static bool json_get_str(const char *json, const char *key, char *out, size_t cap) {
    const char *v = json_find_val(json, key);
    if (!v || *v != '"') return false;
    v++;
    size_t i = 0;
    while (*v && *v != '"' && i + 1 < cap) {
        if (*v == '\\' && v[1]) v++;
        out[i++] = *v++;
    }
    out[i] = '\0';
    return true;
}

/* --- Subcommand: cpu (Polybar) ------------------------------------------- */

static int cmd_cpu(void) {
    long clk = sysconf(_SC_CLK_TCK);
    if (clk <= 0) clk = 100;
    long ncpu = sysconf(_SC_NPROCESSORS_ONLN);
    if (ncpu <= 0) ncpu = 1;

    uint64_t j_prev = read_total_jiffies();
    int64_t t_prev = mono_ms();
    sleep_check_ms(350);

    while (g_running) {
        uint64_t j_now = read_total_jiffies();
        int64_t t_now = mono_ms();
        double dt = (double)(t_now - t_prev) / 1000.0;
        if (dt < 0.05) dt = 0.05;
        int pct = (int)llround((((double)(j_now - j_prev) / (double)clk) / (dt * (double)ncpu)) * 100.0);
        if (pct < 0) pct = 0;
        if (pct > 100) pct = 100;
        j_prev = j_now;
        t_prev = t_now;

        const char *col = pct >= 80 ? "#f38ba8" : (pct >= 50 ? "#fab387" : "#94e2d5");
        printf("%%{F%s}\xef\x92\xbc%%{F-} %d%%\n", col, pct);
        fflush(stdout);
        sleep_check_ms(3000);
    }
    return 0;
}

/* --- Subcommand: sys-diag (Quickshell Wayland topbar) -------------------- */

static int cmd_sys_diag(void) {
    long clk = sysconf(_SC_CLK_TCK);
    if (clk <= 0) clk = 100;
    long ncpu = sysconf(_SC_NPROCESSORS_ONLN);
    if (ncpu <= 0) ncpu = 1;

    uint64_t j_prev = read_total_jiffies();
    int64_t t_prev = mono_ms();

    int bat_pct = -1;
    char bat_status[32] = "UNKNOWN";
    bool has_temp = false;
    double temp_c = 0.0;
    char watts[24] = "";

    bool wifi_ok = false;
    int wifi_rate = 0;
    int wifi_rssi = 0;
    char wifi_ip[64] = "";

    sleep_check_ms(200);
    int tick = 0;
    char jbuf[8192];

    while (g_running) {
        uint64_t j_now = read_total_jiffies();
        int64_t t_now = mono_ms();
        double dt = (double)(t_now - t_prev) / 1000.0;
        if (dt < 0.05) dt = 0.05;
        int cpu_pct = (int)llround((((double)(j_now - j_prev) / (double)clk) / (dt * (double)ncpu)) * 100.0);
        if (cpu_pct < 0) cpu_pct = 0;
        if (cpu_pct > 100) cpu_pct = 100;
        j_prev = j_now;
        t_prev = t_now;

        char mem_used[16], mem_total[16];
        int mem_pct = 0;
        read_mem_info(mem_used, sizeof(mem_used), mem_total, sizeof(mem_total), &mem_pct);

        if (tick % 6 == 0) {
            const char *bat_argv[] = { "termux-battery-status", NULL };
            if (run_cmd_capture(bat_argv, jbuf, sizeof(jbuf), 2000)) {
                double dval = 0.0;
                if (json_get_double(jbuf, "percentage", &dval)) bat_pct = (int)dval;
                char sbuf[32];
                if (json_get_str(jbuf, "status", sbuf, sizeof(sbuf))) {
                    for (size_t i = 0; sbuf[i] && i + 1 < sizeof(bat_status); i++) {
                        bat_status[i] = (char)toupper((unsigned char)sbuf[i]);
                        bat_status[i + 1] = '\0';
                    }
                }
                if (json_get_double(jbuf, "temperature", &dval)) {
                    temp_c = floor(dval * 10.0 + 0.5) / 10.0;
                    has_temp = true;
                }
                double mv = 0.0, ua = 0.0;
                if (json_get_double(jbuf, "voltage", &mv) && json_get_double(jbuf, "current", &ua)) {
                    double w = (mv / 1000.0) * (ua / 1000000.0);
                    if (fabs(w) >= 0.1) snprintf(watts, sizeof(watts), "%+.1fW", w);
                    else watts[0] = '\0';
                } else {
                    watts[0] = '\0';
                }
            }

            const char *wifi_argv[] = { "termux-wifi-connectioninfo", NULL };
            if (run_cmd_capture(wifi_argv, jbuf, sizeof(jbuf), 2000)) {
                char st[32] = "";
                json_get_str(jbuf, "supplicant_state", st, sizeof(st));
                for (size_t i = 0; st[i]; i++) st[i] = (char)toupper((unsigned char)st[i]);
                wifi_ip[0] = '\0';
                json_get_str(jbuf, "ip", wifi_ip, sizeof(wifi_ip));
                wifi_ok = (strcmp(st, "COMPLETED") == 0 && wifi_ip[0] != '\0');
                double dval = 0.0;
                wifi_rate = json_get_double(jbuf, "link_speed_mbps", &dval) ? (int)dval : 0;
                wifi_rssi = json_get_double(jbuf, "rssi", &dval) ? (int)dval : 0;
            }
        }

        printf("{\"cpu\":%d,\"mem_used\":", cpu_pct);
        json_write_str(stdout, mem_used);
        fputs(",\"mem_total\":", stdout);
        json_write_str(stdout, mem_total);
        printf(",\"mem_pct\":%d,\"bat_pct\":%d,\"bat_status\":", mem_pct, bat_pct);
        json_write_str(stdout, bat_status);
        if (has_temp) printf(",\"temp_c\":%.1f", temp_c);
        else fputs(",\"temp_c\":null", stdout);
        fputs(",\"watts\":", stdout);
        json_write_str(stdout, watts);
        printf(",\"wifi_ok\":%s,\"wifi_rate\":%d,\"wifi_rssi\":%d,\"ip\":",
               wifi_ok ? "true" : "false", wifi_rate, wifi_rssi);
        json_write_str(stdout, wifi_ip);
        fputs("}\n", stdout);
        fflush(stdout);

        tick++;
        sleep_check_ms(2000);
    }
    return 0;
}

/* --- Subcommands: hide-cursor & submenu-watch (X11) ---------------------- */

typedef struct {
    int x, y, w, h;
} RectI;

static bool point_in(int px, int py, RectI r) {
    return r.w > 0 && r.h > 0 && px >= r.x && px < r.x + r.w && py >= r.y && py < r.y + r.h;
}

static bool matches_rect(const XWindowAttributes *a, RectI r, int tol) {
    return r.w > 0 && r.h > 0 &&
           abs(a->x - r.x) <= tol && abs(a->y - r.y) <= tol &&
           abs(a->width - r.w) <= tol && abs(a->height - r.h) <= tol;
}

static bool has_foreign_popup(Display *dpy, Window root, const RectI *own, int n_own) {
    Window r, p, *ch = NULL;
    unsigned int n = 0;
    if (!XQueryTree(dpy, root, &r, &p, &ch, &n)) return false;
    bool found = false;
    for (unsigned int i = 0; i < n; i++) {
        XWindowAttributes a;
        if (!XGetWindowAttributes(dpy, ch[i], &a) || a.map_state != IsViewable) continue;
        if (a.override_redirect == 1 && a.width >= 200 && a.height >= 150) {
            bool mine = false;
            for (int k = 0; k < n_own; k++) {
                if (matches_rect(&a, own[k], 16)) {
                    mine = true;
                    break;
                }
            }
            if (!mine) {
                found = true;
                break;
            }
        }
    }
    if (ch) XFree(ch);
    return found;
}

static int cmd_hide_cursor(void) {
    const char *disp = getenv("DISPLAY");
    Display *dpy = XOpenDisplay(disp && *disp ? disp : ":0");
    if (!dpy) return 1;

    int ev = 0, er = 0, maj = 5, minv = 0;
    if (!XFixesQueryExtension(dpy, &ev, &er)) {
        XCloseDisplay(dpy);
        return 1;
    }
    XFixesQueryVersion(dpy, &maj, &minv);

    Window root = DefaultRootWindow(dpy);
    const char *tmp = getenv("TMPDIR");
    char pid_path[256] = "";
    snprintf(pid_path, sizeof(pid_path), "%s/hide-cursor.pid",
             (tmp && *tmp) ? tmp : "/data/data/com.termux/files/usr/tmp");
    FILE *pf = fopen(pid_path, "w");
    if (pf) {
        fprintf(pf, "%d", (int)getpid());
        fclose(pf);
    } else {
        pid_path[0] = '\0';
    }

    Window rw = 0, cw = 0;
    int rx = 0, ry = 0, wx = 0, wy = 0;
    unsigned int mask = 0;
    XQueryPointer(dpy, root, &rw, &cw, &rx, &ry, &wx, &wy, &mask);
    int last_x = rx, last_y = ry;
    bool was_pressed = (mask & 0x1F00U) != 0;
    bool hidden = true;
    XFixesHideCursor(dpy, root);
    XSync(dpy, False);
    int64_t hide_at = 0;

    while (g_running) {
        usleep(80000);
        if (!XQueryPointer(dpy, root, &rw, &cw, &rx, &ry, &wx, &wy, &mask)) break;
        int64_t now = mono_ms();
        bool moved = (rx != last_x) || (ry != last_y);
        bool pressed = (mask & 0x1F00U) != 0;
        last_x = rx;
        last_y = ry;

        if (pressed) {
            was_pressed = true;
            hide_at = now + 500;
        } else if (was_pressed && !pressed) {
            was_pressed = false;
            hide_at = now + 150;
            if (!hidden) {
                XFixesHideCursor(dpy, root);
                XSync(dpy, False);
                hidden = true;
            }
        } else if (moved) {
            if (hidden) {
                XFixesShowCursor(dpy, root);
                XSync(dpy, False);
                hidden = false;
            }
            hide_at = now + 600;
        } else if (!hidden && now >= hide_at) {
            XFixesHideCursor(dpy, root);
            XSync(dpy, False);
            hidden = true;
        }
    }

    if (hidden) {
        XFixesShowCursor(dpy, root);
        XSync(dpy, False);
    }
    if (pid_path[0]) unlink(pid_path);
    XCloseDisplay(dpy);
    return 0;
}

static int cmd_submenu_watch(int argc, char **argv) {
    int dock_w = 128, dock_h = 1508, sub_x = 140, sub_y = 80, sub_w = 844, sub_h = 1508;
    if (argc >= 8) {
        dock_w = (int)strtod(argv[2], NULL);
        dock_h = (int)strtod(argv[3], NULL);
        sub_x  = (int)strtod(argv[4], NULL);
        sub_y  = (int)strtod(argv[5], NULL);
        sub_w  = (int)strtod(argv[6], NULL);
        sub_h  = (int)strtod(argv[7], NULL);
    }
    RectI dock_rect = { 0, 80, dock_w, dock_h };
    RectI sub_rect  = { sub_x, sub_y, sub_w, sub_h };
    RectI own_rects[2] = { dock_rect, sub_rect };

    const char *disp = getenv("DISPLAY");
    Display *dpy = XOpenDisplay(disp && *disp ? disp : ":0");
    if (!dpy) return 1;
    Window root = DefaultRootWindow(dpy);
    int xfd = ConnectionNumber(dpy);

    int maj = 2, minv = 2;
    XIQueryVersion(dpy, &maj, &minv);

    unsigned char mask_bytes[4] = { 0, 0x80, 0, 0 }; /* XI_RawButtonPress (15) */
    XIEventMask em = { .deviceid = XIAllMasterDevices, .mask_len = 4, .mask = mask_bytes };
    XISelectEvents(dpy, root, &em, 1);
    XFlush(dpy);

    const char *tmp = getenv("TMPDIR");
    char pid_path[256] = "";
    snprintf(pid_path, sizeof(pid_path), "%s/qs-watch.pid",
             (tmp && *tmp) ? tmp : "/data/data/com.termux/files/usr/tmp");
    FILE *pf = fopen(pid_path, "w");
    if (pf) {
        fprintf(pf, "%d", (int)getpid());
        fclose(pf);
    } else {
        pid_path[0] = '\0';
    }

    Window focus_win = 0, initial_focus = 0;
    int revert_to = 0;
    XGetInputFocus(dpy, &initial_focus, &revert_to);

    int64_t start_t = mono_ms();
    XEvent ev_buf;

    while (g_running) {
        struct pollfd pf_x = { .fd = xfd, .events = POLLIN };
        int rc = poll(&pf_x, 1, 120);
        bool clicked = false;
        if (rc > 0 && (pf_x.revents & POLLIN)) {
            while (XPending(dpy) > 0) {
                XNextEvent(dpy, &ev_buf);
                clicked = true;
            }
        }

        XGetInputFocus(dpy, &focus_win, &revert_to);
        if ((focus_win != initial_focus && focus_win != None && focus_win != PointerRoot) ||
            has_foreign_popup(dpy, root, own_rects, 2)) {
            puts("CLOSE");
            fflush(stdout);
            break;
        }

        if (clicked && (mono_ms() - start_t) >= 80) {
            Window rw = 0, cw = 0;
            int rx = 0, ry = 0, wx = 0, wy = 0;
            unsigned int mask = 0;
            if (XQueryPointer(dpy, root, &rw, &cw, &rx, &ry, &wx, &wy, &mask)) {
                bool in_sub = point_in(rx, ry, sub_rect);
                bool in_dock = point_in(rx, ry, dock_rect);
                bool on_toggle = in_dock && (
                    (ry >= 80 + (int)(dock_h * 0.45) && ry <= 80 + (int)(dock_h * 0.70)) ||
                    (ry >= 80 + dock_h - 90)
                );
                if (!in_sub && !on_toggle) {
                    puts("CLOSE");
                    fflush(stdout);
                    break;
                }
            }
        }
    }

    if (pid_path[0]) unlink(pid_path);
    XCloseDisplay(dpy);
    return 0;
}

/* --- Subcommand: wl-workspaces (LabWC ext_workspace_manager_v1) ---------- */

#define MAX_WL_WS 32

typedef struct {
    uint32_t id;
    uint32_t state;
    char name[64];
    bool alive;
} WlWorkspace;

static uint32_t read_u32(const uint8_t *p, size_t off) {
    uint32_t v;
    memcpy(&v, p + off, 4);
    return v;
}

static size_t wl_pack_str(uint8_t *dst, size_t off, const char *s) {
    uint32_t slen = (uint32_t)strlen(s) + 1;
    memcpy(dst + off, &slen, 4);
    memcpy(dst + off + 4, s, slen);
    size_t step = 4 + ((slen + 3U) & ~3U);
    if (step > 4 + slen) {
        memset(dst + off + 4 + slen, 0, step - (4 + slen));
    }
    return off + step;
}

static size_t wl_unpack_str(const uint8_t *buf, size_t len, size_t off, char *out, size_t cap) {
    if (off + 4 > len) {
        out[0] = '\0';
        return len;
    }
    uint32_t slen = read_u32(buf, off);
    size_t avail = len - (off + 4);
    size_t copy = slen > 0 ? slen - 1 : 0;
    if (copy > avail) copy = avail;
    if (copy >= cap) copy = cap - 1;
    if (copy > 0) memcpy(out, buf + off + 4, copy);
    out[copy] = '\0';
    size_t step = 4 + ((slen + 3U) & ~3U);
    return (off + step <= len) ? (off + step) : len;
}

static bool wl_send(int fd, uint32_t obj_id, uint16_t op, const uint8_t *payload, size_t plen) {
    uint8_t pkt[256];
    uint32_t size = (uint32_t)(8 + plen);
    if (size > sizeof(pkt)) return false;
    uint32_t size_op = (size << 16) | (uint32_t)op;
    memcpy(pkt, &obj_id, 4);
    memcpy(pkt + 4, &size_op, 4);
    if (plen > 0 && payload) memcpy(pkt + 8, payload, plen);
    size_t sent = 0;
    while (sent < size) {
        ssize_t w = send(fd, pkt + sent, size - sent, 0);
        if (w <= 0) {
            if (w < 0 && errno == EINTR) continue;
            return false;
        }
        sent += (size_t)w;
    }
    return true;
}

static void wl_emit_state(const WlWorkspace *ws_list, int count) {
    const WlWorkspace *by_num[7] = { NULL };
    const WlWorkspace *ordered[6] = { NULL };
    int n_ord = 0;
    bool has_num = false;

    for (int i = 0; i < count; i++) {
        if (!ws_list[i].alive || (ws_list[i].state & 4U)) continue;
        if (n_ord < 6) ordered[n_ord++] = &ws_list[i];
        char *end = NULL;
        long n = strtol(ws_list[i].name, &end, 10);
        if (ws_list[i].name[0] && end && *end == '\0' && n >= 1 && n <= 6) {
            by_num[n] = &ws_list[i];
            has_num = true;
        }
    }
    if (!has_num && n_ord == 0) return;

    fputc('[', stdout);
    if (has_num) {
        for (int n = 1; n <= 6; n++) {
            bool foc = by_num[n] ? ((by_num[n]->state & 1U) != 0) : false;
            bool urg = by_num[n] ? ((by_num[n]->state & 2U) != 0) : false;
            printf("%s{\"num\":%d,\"focused\":%s,\"occupied\":false,\"urgent\":%s}",
                   n > 1 ? "," : "", n, foc ? "true" : "false", urg ? "true" : "false");
        }
    } else {
        for (int i = 0; i < n_ord; i++) {
            bool foc = (ordered[i]->state & 1U) != 0;
            bool urg = (ordered[i]->state & 2U) != 0;
            printf("%s{\"num\":%d,\"focused\":%s,\"occupied\":false,\"urgent\":%s}",
                   i > 0 ? "," : "", i + 1, foc ? "true" : "false", urg ? "true" : "false");
        }
    }
    fputs("]\n", stdout);
    fflush(stdout);
}

static int cmd_wl_workspaces(void) {
    const char *xdg = getenv("XDG_RUNTIME_DIR");
    if (!xdg || !*xdg) xdg = getenv("TMPDIR");
    if (!xdg || !*xdg) xdg = "/data/data/com.termux/files/usr/tmp";
    const char *wdisp = getenv("WAYLAND_DISPLAY");
    if (!wdisp || !*wdisp) wdisp = "wayland-0";

    struct sockaddr_un sa;
    memset(&sa, 0, sizeof(sa));
    sa.sun_family = AF_UNIX;
    if (wdisp[0] == '/') snprintf(sa.sun_path, sizeof(sa.sun_path), "%s", wdisp);
    else snprintf(sa.sun_path, sizeof(sa.sun_path), "%s/%s", xdg, wdisp);

    int sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock < 0) return 1;
    if (connect(sock, (struct sockaddr *)&sa, sizeof(sa)) != 0) {
        close(sock);
        return 1;
    }

    uint32_t reg_id = 2, sync_id = 3;
    wl_send(sock, 1, 1, (const uint8_t *)&reg_id, 4);
    wl_send(sock, 1, 0, (const uint8_t *)&sync_id, 4);

    uint32_t mgr_id = 0;
    WlWorkspace workspaces[MAX_WL_WS];
    memset(workspaces, 0, sizeof(workspaces));
    int ws_count = 0;

    uint8_t rx[32768];
    size_t rx_len = 0;
    char in_buf[512];
    size_t in_len = 0;

    while (g_running) {
        struct pollfd pfd[2] = {
            { .fd = sock, .events = POLLIN },
            { .fd = STDIN_FILENO, .events = POLLIN },
        };
        int prc = poll(pfd, 2, 500);
        if (prc < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (pfd[0].revents & (POLLIN | POLLHUP | POLLERR)) {
            if (rx_len < sizeof(rx)) {
                ssize_t r = recv(sock, rx + rx_len, sizeof(rx) - rx_len, 0);
                if (r <= 0) break;
                rx_len += (size_t)r;
            }
            size_t pos = 0;
            while (rx_len - pos >= 8) {
                uint32_t obj_id = read_u32(rx, pos);
                uint32_t size_op = read_u32(rx, pos + 4);
                uint32_t msize = size_op >> 16;
                uint16_t op = (uint16_t)(size_op & 0xFFFFU);
                if (msize < 8 || msize > rx_len - pos) break;
                const uint8_t *pl = rx + pos + 8;
                size_t plen = msize - 8;

                if (obj_id == 2 && op == 0 && plen >= 8) {
                    uint32_t gname = read_u32(pl, 0);
                    char iface[128];
                    size_t off = wl_unpack_str(pl, plen, 4, iface, sizeof(iface));
                    uint32_t gver = (off + 4 <= plen) ? read_u32(pl, off) : 1;
                    if (strcmp(iface, "ext_workspace_manager_v1") == 0 && mgr_id == 0) {
                        mgr_id = 4;
                        uint32_t ver = gver < 1 ? gver : 1;
                        uint8_t bind_pl[192];
                        memcpy(bind_pl, &gname, 4);
                        size_t boff = wl_pack_str(bind_pl, 4, iface);
                        memcpy(bind_pl + boff, &ver, 4);
                        memcpy(bind_pl + boff + 4, &mgr_id, 4);
                        wl_send(sock, 2, 0, bind_pl, boff + 8);
                    }
                } else if (mgr_id != 0 && obj_id == mgr_id) {
                    if (op == 1 && plen >= 4) {
                        uint32_t wid = read_u32(pl, 0);
                        int slot = -1;
                        for (int i = 0; i < ws_count; i++) {
                            if (!workspaces[i].alive || workspaces[i].id == wid) {
                                slot = i;
                                break;
                            }
                        }
                        if (slot < 0 && ws_count < MAX_WL_WS) slot = ws_count++;
                        if (slot >= 0) {
                            memset(&workspaces[slot], 0, sizeof(workspaces[slot]));
                            workspaces[slot].id = wid;
                            workspaces[slot].alive = true;
                        }
                    } else if (op == 2) {
                        wl_emit_state(workspaces, ws_count);
                    } else if (op == 3) {
                        g_running = 0;
                    }
                } else {
                    for (int i = 0; i < ws_count; i++) {
                        if (workspaces[i].alive && workspaces[i].id == obj_id) {
                            if (op == 1) {
                                wl_unpack_str(pl, plen, 0, workspaces[i].name, sizeof(workspaces[i].name));
                            } else if (op == 3 && plen >= 4) {
                                workspaces[i].state = read_u32(pl, 0);
                            } else if (op == 5) {
                                workspaces[i].alive = false;
                            }
                            break;
                        }
                    }
                }
                pos += msize;
            }
            if (pos > 0) {
                memmove(rx, rx + pos, rx_len - pos);
                rx_len -= pos;
            }
        }
        if (pfd[1].revents & (POLLIN | POLLHUP)) {
            ssize_t r = read(STDIN_FILENO, in_buf + in_len, sizeof(in_buf) - 1 - in_len);
            if (r <= 0) break;
            in_len += (size_t)r;
            in_buf[in_len] = '\0';
            char *nl;
            char *cursor = in_buf;
            while ((nl = strchr(cursor, '\n')) != NULL) {
                *nl = '\0';
                char *target = cursor;
                while (*target == ' ' || *target == '\r' || *target == '\t') target++;
                size_t tlen = strlen(target);
                while (tlen > 0 && (target[tlen - 1] == ' ' || target[tlen - 1] == '\r' || target[tlen - 1] == '\t')) {
                    target[--tlen] = '\0';
                }
                if (tlen > 0 && mgr_id != 0) {
                    for (int i = 0; i < ws_count; i++) {
                        if (workspaces[i].alive && strcmp(workspaces[i].name, target) == 0) {
                            wl_send(sock, workspaces[i].id, 1, NULL, 0);
                            wl_send(sock, mgr_id, 0, NULL, 0);
                            break;
                        }
                    }
                }
                cursor = nl + 1;
            }
            size_t rem = strlen(cursor);
            memmove(in_buf, cursor, rem);
            in_len = rem;
        }
    }

    close(sock);
    return 0;
}

/* --- Subcommands: media-stream / media-status (Persistent rish pipe) ----- */

typedef struct {
    pid_t pid;
    int to_fd;
    int from_fd;
    unsigned seq;
} RishPipe;

static void rish_close(RishPipe *rp) {
    if (rp->to_fd >= 0) {
        (void)!write(rp->to_fd, "exit\n", 5);
        close(rp->to_fd);
        rp->to_fd = -1;
    }
    if (rp->from_fd >= 0) {
        close(rp->from_fd);
        rp->from_fd = -1;
    }
    if (rp->pid > 0) {
        int st = 0;
        if (waitpid(rp->pid, &st, WNOHANG) == 0) {
            usleep(30000);
            if (waitpid(rp->pid, &st, WNOHANG) == 0) {
                kill(rp->pid, SIGTERM);
                usleep(40000);
                if (waitpid(rp->pid, &st, WNOHANG) == 0) kill(rp->pid, SIGKILL);
                waitpid(rp->pid, &st, 0);
            }
        }
        rp->pid = -1;
    }
}

static bool rish_open(RishPipe *rp) {
    if (rp->pid > 0 && waitpid(rp->pid, NULL, WNOHANG) == 0) return true;
    rish_close(rp);

    const char *prefix = getenv("PREFIX");
    if (!prefix || !*prefix) prefix = "/data/data/com.termux/files/usr";
    char dex_path[512];
    snprintf(dex_path, sizeof(dex_path), "%s/share/rish-shizuku.dex", prefix);
    if (access(dex_path, F_OK) != 0) return false;

    struct stat st;
    if (stat(dex_path, &st) == 0 && (st.st_mode & 0222U)) {
        (void)!chmod(dex_path, 0400);
    }

    int in_p[2], out_p[2];
    if (pipe2(in_p, O_CLOEXEC) != 0) return false;
    if (pipe2(out_p, O_CLOEXEC) != 0) {
        close(in_p[0]);
        close(in_p[1]);
        return false;
    }

    pid_t pid = fork();
    if (pid < 0) {
        close(in_p[0]); close(in_p[1]);
        close(out_p[0]); close(out_p[1]);
        return false;
    }
    if (pid == 0) {
        dup2(in_p[0], STDIN_FILENO);
        dup2(out_p[1], STDOUT_FILENO);
        dup2(out_p[1], STDERR_FILENO);
        close(in_p[0]); close(in_p[1]);
        close(out_p[0]); close(out_p[1]);

        unsetenv("LD_LIBRARY_PATH");
        unsetenv("LD_PRELOAD");
        setenv("RISH_APPLICATION_ID", "com.termux", 1);

        char cp_arg[544];
        snprintf(cp_arg, sizeof(cp_arg), "-Djava.class.path=%s", dex_path);
        const char *argv[] = {
            "/system/bin/app_process",
            cp_arg,
            "/system/bin",
            "--nice-name=rish",
            "rikka.shizuku.shell.ShizukuShellLoader",
            NULL
        };
        execv("/system/bin/app_process", (char *const *)argv);
        _exit(127);
    }

    close(in_p[0]);
    close(out_p[1]);
    int fl = fcntl(out_p[0], F_GETFL, 0);
    if (fl >= 0) fcntl(out_p[0], F_SETFL, fl | O_NONBLOCK);

    rp->pid = pid;
    rp->to_fd = in_p[1];
    rp->from_fd = out_p[0];
    return true;
}

static bool rish_exec_framed(RishPipe *rp, const char *shell_body, char **out_buf, int timeout_ms) {
    *out_buf = NULL;
    if (!rish_open(rp)) return false;

    rp->seq++;
    char beg[48], endm[48];
    snprintf(beg, sizeof(beg), "__MKB_%u__", rp->seq);
    snprintf(endm, sizeof(endm), "__MKE_%u__", rp->seq);

    size_t cmd_cap = strlen(shell_body) + 128;
    char *cmd = malloc(cmd_cap);
    if (!cmd) return false;
    int clen = snprintf(cmd, cmd_cap, "printf '%s\\n'; %s; printf '\\n%s\\n'\n", beg, shell_body, endm);

    size_t sent = 0;
    while (sent < (size_t)clen) {
        ssize_t w = write(rp->to_fd, cmd + sent, (size_t)clen - sent);
        if (w <= 0) {
            if (w < 0 && errno == EINTR && g_running) continue;
            free(cmd);
            rish_close(rp);
            return false;
        }
        sent += (size_t)w;
    }
    free(cmd);

    size_t cap = 32768, len = 0;
    char *buf = malloc(cap);
    if (!buf) return false;
    buf[0] = '\0';

    int64_t deadline = mono_ms() + timeout_ms;
    bool done = false;
    while (g_running && !done) {
        int64_t left = deadline - mono_ms();
        if (left <= 0) break;
        struct pollfd pf = { .fd = rp->from_fd, .events = POLLIN };
        int rc = poll(&pf, 1, (int)left);
        if (rc < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (rc == 0) break;
        if (pf.revents & (POLLIN | POLLHUP)) {
            for (;;) {
                if (len + 4096 >= cap) {
                    if (cap >= 524288) break;
                    cap *= 2;
                    char *nb = realloc(buf, cap);
                    if (!nb) break;
                    buf = nb;
                }
                ssize_t r = read(rp->from_fd, buf + len, cap - 1 - len);
                if (r > 0) {
                    len += (size_t)r;
                    buf[len] = '\0';
                    char *end_pos = strstr(buf, endm);
                    if (end_pos) {
                        *end_pos = '\0';
                        done = true;
                        break;
                    }
                } else if (r == 0) {
                    rish_close(rp);
                    free(buf);
                    return false;
                } else {
                    if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                    rish_close(rp);
                    free(buf);
                    return false;
                }
            }
        }
    }

    if (!done) {
        rish_close(rp);
        free(buf);
        return false;
    }

    char *start = strstr(buf, beg);
    if (start) {
        start += strlen(beg);
        if (*start == '\r') start++;
        if (*start == '\n') start++;
        memmove(buf, start, strlen(start) + 1);
    }
    *out_buf = buf;
    return true;
}

typedef struct {
    char tag[128];
    char package[128];
    bool active;
    char state_name[32];
    int state_code;
    int64_t pos_ms;
    double speed;
    int64_t updated_ms;
    char title[256];
    char artist[256];
    char album[256];
} MediaSession;

static const char *app_label_for(const char *pkg, char *tmp, size_t cap) {
    if (strcmp(pkg, "com.spotify.music") == 0) return "Spotify";
    if (strcmp(pkg, "com.spotify.lite") == 0) return "Spotify Lite";
    if (strcmp(pkg, "com.google.android.apps.youtube.music") == 0 ||
        strcmp(pkg, "app.morphe.android.apps.youtube.music") == 0) return "YT Music";
    if (strcmp(pkg, "com.google.android.youtube") == 0 ||
        strcmp(pkg, "app.revanced.android.youtube") == 0) return "YouTube";
    if (strcmp(pkg, "org.videolan.vlc") == 0) return "VLC";
    if (strcmp(pkg, "com.apple.android.music") == 0) return "Apple Music";

    char copy[128];
    snprintf(copy, sizeof(copy), "%s", pkg ? pkg : "");
    const char *last = NULL;
    char *save = NULL;
    char *tok = strtok_r(copy, ".", &save);
    while (tok) {
        if (strcmp(tok, "com") != 0 && strcmp(tok, "org") != 0 &&
            strcmp(tok, "app") != 0 && strcmp(tok, "android") != 0 &&
            strcmp(tok, "apps") != 0 && strcmp(tok, "music") != 0) {
            last = tok;
        }
        tok = strtok_r(NULL, ".", &save);
    }
    if (last && *last) {
        snprintf(tmp, cap, "%s", last);
        tmp[0] = (char)toupper((unsigned char)tmp[0]);
        return tmp;
    }
    return (pkg && *pkg) ? pkg : "Media";
}

static void fmt_time(int64_t sec, char *out, size_t cap) {
    if (sec < 0) sec = 0;
    int64_t m = sec / 60;
    int64_t s = sec % 60;
    int64_t h = m / 60;
    m = m % 60;
    if (h > 0) snprintf(out, cap, "%lld:%02lld:%02lld", (long long)h, (long long)m, (long long)s);
    else snprintf(out, cap, "%lld:%02lld", (long long)m, (long long)s);
}

static void parse_description(const char *desc, char *title, size_t tcap,
                              char *artist, size_t acap, char *album, size_t lcap) {
    title[0] = artist[0] = album[0] = '\0';
    if (!desc || !*desc || strcmp(desc, "null") == 0) return;

    /* MediaDescription.toString() joins title, artist, album with ", ". */
    const char *sep2 = NULL, *sep1 = NULL;
    const char *p = desc;
    while ((p = strstr(p, ", ")) != NULL) {
        sep1 = sep2;
        sep2 = p;
        p += 2;
    }
    if (!sep2) {
        if (strcmp(desc, "null") != 0) snprintf(title, tcap, "%s", desc);
    } else if (!sep1) {
        size_t l1 = (size_t)(sep2 - desc);
        if (l1 >= tcap) l1 = tcap - 1;
        memcpy(title, desc, l1);
        title[l1] = '\0';
        if (strcmp(title, "null") == 0) title[0] = '\0';
        const char *a = sep2 + 2;
        if (strcmp(a, "null") != 0) snprintf(artist, acap, "%s", a);
    } else {
        size_t l1 = (size_t)(sep1 - desc);
        if (l1 >= tcap) l1 = tcap - 1;
        memcpy(title, desc, l1);
        title[l1] = '\0';
        if (strcmp(title, "null") == 0) title[0] = '\0';

        size_t l2 = (size_t)(sep2 - (sep1 + 2));
        if (l2 >= acap) l2 = acap - 1;
        memcpy(artist, sep1 + 2, l2);
        artist[l2] = '\0';
        if (strcmp(artist, "null") == 0) artist[0] = '\0';

        const char *al = sep2 + 2;
        if (strcmp(al, "null") != 0) snprintf(album, lcap, "%s", al);
    }
}

static void emit_media_json(bool available, bool playing, const char *state, const char *pkg,
                            const char *app, const char *tag, const char *title,
                            const char *artist, const char *album, int64_t pos_sec, const char *pos_text) {
    printf("{\"available\":%s,\"playing\":%s,\"state\":",
           available ? "true" : "false", playing ? "true" : "false");
    json_write_str(stdout, state);
    fputs(",\"package\":", stdout); json_write_str(stdout, pkg);
    fputs(",\"app\":", stdout); json_write_str(stdout, app);
    fputs(",\"tag\":", stdout); json_write_str(stdout, tag);
    fputs(",\"title\":", stdout); json_write_str(stdout, title);
    fputs(",\"artist\":", stdout); json_write_str(stdout, artist);
    fputs(",\"album\":", stdout); json_write_str(stdout, album);
    printf(",\"pos_sec\":%lld,\"pos_text\":", (long long)pos_sec);
    json_write_str(stdout, pos_text);
    fputs("}\n", stdout);
    fflush(stdout);
}

static void query_and_emit_media(RishPipe *rp) {
    char *raw = NULL;
    if (!rish_exec_framed(rp, "echo UPTIME:$(cat /proc/uptime 2>/dev/null); dumpsys media_session 2>/dev/null", &raw, 3000)) {
        emit_media_json(false, false, "SHIZUKU OFF", "", "Media Control", "",
                        "Shizuku inactive", "Start Shizuku to control media", "", 0, "--:--");
        return;
    }

    int64_t uptime_ms = 0;
    char btn_pkg[128] = "", btn_tag[128] = "";
    const char *mbtn = strstr(raw, "Media button session is ");
    if (mbtn) {
        mbtn += 24;
        const char *s1 = strchr(mbtn, '/');
        const char *eol = strpbrk(mbtn, "\r\n");
        if (s1 && (!eol || s1 < eol)) {
            size_t pl = (size_t)(s1 - mbtn);
            if (pl < sizeof(btn_pkg)) { memcpy(btn_pkg, mbtn, pl); btn_pkg[pl] = '\0'; }
            const char *s2 = strchr(s1 + 1, '/');
            if (s2 && (!eol || s2 < eol)) {
                size_t tl = (size_t)(s2 - (s1 + 1));
                if (tl < sizeof(btn_tag)) { memcpy(btn_tag, s1 + 1, tl); btn_tag[tl] = '\0'; }
            }
        }
    }

    MediaSession sessions[16];
    memset(sessions, 0, sizeof(sessions));
    int n_sess = 0;
    MediaSession *cur = NULL;
    bool in_stack = false;

    char *line = raw;
    while (line && *line) {
        char *nl = strchr(line, '\n');
        if (nl) *nl = '\0';
        size_t ll = strlen(line);
        while (ll > 0 && (line[ll - 1] == '\r' || line[ll - 1] == ' ')) line[--ll] = '\0';

        if (strncmp(line, "UPTIME:", 7) == 0 && uptime_ms == 0) {
            uptime_ms = (int64_t)(strtod(line + 7, NULL) * 1000.0);
        } else if (strstr(line, "Sessions Stack - have")) {
            in_stack = true;
        } else if (in_stack && line[0] != '\0') {
            int indent = 0;
            while (line[indent] == ' ') indent++;
            const char *s = line + indent;
            if (indent <= 2) {
                in_stack = false;
                cur = NULL;
            } else if (indent == 4) {
                if (n_sess < 16) {
                    cur = &sessions[n_sess++];
                    memset(cur, 0, sizeof(*cur));
                    snprintf(cur->state_name, sizeof(cur->state_name), "NONE");
                    const char *uid_p = strstr(s, " (userId=");
                    if (uid_p) {
                        const char *s2 = uid_p;
                        while (s2 > s && *s2 != '/') s2--;
                        const char *s1 = (s2 > s) ? s2 - 1 : s;
                        while (s1 > s && *s1 != '/') s1--;
                        if (*s1 == '/' && *s2 == '/' && s2 > s1) {
                            size_t tl = (size_t)(s2 - (s1 + 1));
                            if (tl >= sizeof(cur->tag)) tl = sizeof(cur->tag) - 1;
                            memcpy(cur->tag, s1 + 1, tl);
                            cur->tag[tl] = '\0';

                            const char *pstart = s1;
                            while (pstart > s && pstart[-1] != ' ') pstart--;
                            size_t pl = (size_t)(s1 - pstart);
                            if (pl >= sizeof(cur->package)) pl = sizeof(cur->package) - 1;
                            memcpy(cur->package, pstart, pl);
                            cur->package[pl] = '\0';
                        }
                    }
                } else {
                    cur = NULL;
                }
            } else if (cur && indent >= 6) {
                if (strncmp(s, "package=", 8) == 0) {
                    snprintf(cur->package, sizeof(cur->package), "%s", s + 8);
                } else if (strncmp(s, "active=", 7) == 0) {
                    cur->active = (strcasecmp(s + 7, "true") == 0);
                } else if (strncmp(s, "state=PlaybackState", 19) == 0) {
                    const char *sp = strstr(s, "state=");
                    sp = sp ? strstr(sp + 6, "state=") : NULL;
                    if (sp) {
                        sp += 6;
                        const char *op = strchr(sp, '(');
                        if (op && op > sp) {
                            size_t sl = (size_t)(op - sp);
                            if (sl >= sizeof(cur->state_name)) sl = sizeof(cur->state_name) - 1;
                            memcpy(cur->state_name, sp, sl);
                            cur->state_name[sl] = '\0';
                            cur->state_code = atoi(op + 1);
                        }
                    }
                    const char *pp = strstr(s, "position=");
                    if (pp) cur->pos_ms = strtoll(pp + 9, NULL, 10);
                    const char *vp = strstr(s, "speed=");
                    if (vp) cur->speed = strtod(vp + 6, NULL);
                    const char *up = strstr(s, "updated=");
                    if (up) cur->updated_ms = strtoll(up + 8, NULL, 10);
                } else if (strncmp(s, "metadata:", 9) == 0) {
                    const char *dp = strstr(s, "description=");
                    if (dp) {
                        parse_description(dp + 12,
                                          cur->title, sizeof(cur->title),
                                          cur->artist, sizeof(cur->artist),
                                          cur->album, sizeof(cur->album));
                    }
                }
            }
        }
        line = nl ? (nl + 1) : NULL;
    }

    int best_idx = -1, best_score = -1;
    for (int i = 0; i < n_sess; i++) {
        MediaSession *ms = &sessions[i];
        bool usable = ms->title[0] != '\0' || ms->state_code == 2 || ms->state_code == 3 || ms->state_code == 6;
        if (!usable) continue;
        int sc = (ms->state_code == 3 ? 1000 : 0)
               + (strstr(ms->package, "spotify") ? 100 : 0)
               + ((strcmp(ms->package, btn_pkg) == 0 && strcmp(ms->tag, btn_tag) == 0) ? 10 : 0)
               + (ms->active ? 1 : 0);
        if (sc > best_score) {
            best_score = sc;
            best_idx = i;
        }
    }

    if (best_idx < 0) {
        emit_media_json(true, false, "IDLE", "", "Media Control", "",
                        "Nothing Playing", "Open Spotify or a media app", "", 0, "0:00");
        free(raw);
        return;
    }

    MediaSession *ch = &sessions[best_idx];
    bool playing = (ch->state_code == 3 || ch->state_code == 6);
    int64_t pos_ms = ch->pos_ms;
    if (ch->state_code == 3 && ch->updated_ms > 0 && ch->speed > 0.0 && uptime_ms >= ch->updated_ms) {
        pos_ms = pos_ms + (int64_t)((double)(uptime_ms - ch->updated_ms) * ch->speed);
        if (pos_ms < 0) pos_ms = 0;
    }
    int64_t pos_sec = pos_ms / 1000;
    char pos_text[32], app_tmp[64];
    fmt_time(pos_sec, pos_text, sizeof(pos_text));
    const char *app = app_label_for(ch->package, app_tmp, sizeof(app_tmp));
    const char *title = ch->title[0] ? ch->title : app;

    emit_media_json(true, playing, ch->state_name, ch->package, app, ch->tag,
                    title, ch->artist, ch->album, pos_sec, pos_text);
    free(raw);
}

static bool valid_tag(const char *tag) {
    if (!tag || !*tag) return false;
    for (const char *p = tag; *p; p++) {
        if (!isalnum((unsigned char)*p) && *p != '.' && *p != '_' && *p != '-' && *p != ' ') {
            return false;
        }
    }
    return true;
}

static void dispatch_media_action(RishPipe *rp, const char *act, const char *was_playing, const char *tag) {
    if (strcmp(act, "play") != 0 && strcmp(act, "pause") != 0 &&
        strcmp(act, "play-pause") != 0 && strcmp(act, "next") != 0 &&
        strcmp(act, "previous") != 0 && strcmp(act, "stop") != 0) {
        return;
    }

    char cmd[512];
    if (valid_tag(tag)) {
        const char *mon_cmd = act;
        if (strcmp(act, "play-pause") == 0) {
            mon_cmd = (was_playing && strcmp(was_playing, "1") == 0) ? "pause" : "play";
        }
        if (strcmp(mon_cmd, "play") == 0 || strcmp(mon_cmd, "pause") == 0 ||
            strcmp(mon_cmd, "next") == 0 || strcmp(mon_cmd, "previous") == 0) {
            snprintf(cmd, sizeof(cmd),
                     "printf '%s\\nq\\n' | cmd media_session monitor '%s' >/dev/null 2>&1 || "
                     "cmd media_session dispatch %s >/dev/null 2>&1",
                     mon_cmd, tag, act);
        } else {
            snprintf(cmd, sizeof(cmd), "cmd media_session dispatch %s >/dev/null 2>&1", act);
        }
    } else {
        snprintf(cmd, sizeof(cmd), "cmd media_session dispatch %s >/dev/null 2>&1", act);
    }

    char *ignored = NULL;
    if (rish_exec_framed(rp, cmd, &ignored, 2500)) free(ignored);
    sleep_check_ms(220);
    query_and_emit_media(rp);
}

static int cmd_media_stream(void) {
    RishPipe rp = { .pid = -1, .to_fd = -1, .from_fd = -1, .seq = 0 };
    query_and_emit_media(&rp);

    char in_buf[1024];
    size_t in_len = 0;
    while (g_running) {
        struct pollfd pfd = { .fd = STDIN_FILENO, .events = POLLIN };
        int rc = poll(&pfd, 1, 500);
        if (rc < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (rc == 0) {
            if (rp.pid > 0 && waitpid(rp.pid, NULL, WNOHANG) != 0) {
                rish_close(&rp);
            }
            continue;
        }
        if (pfd.revents & (POLLIN | POLLHUP)) {
            ssize_t r = read(STDIN_FILENO, in_buf + in_len, sizeof(in_buf) - 1 - in_len);
            if (r <= 0) break;
            in_len += (size_t)r;
            in_buf[in_len] = '\0';

            char *nl;
            char *cur = in_buf;
            while ((nl = strchr(cur, '\n')) != NULL) {
                *nl = '\0';
                size_t l = strlen(cur);
                while (l > 0 && (cur[l - 1] == '\r' || cur[l - 1] == ' ')) cur[--l] = '\0';
                if (strcmp(cur, "status") == 0) {
                    query_and_emit_media(&rp);
                } else if (*cur) {
                    char *t1 = strchr(cur, '\t');
                    char *t2 = t1 ? strchr(t1 + 1, '\t') : NULL;
                    if (t1) *t1++ = '\0';
                    if (t2) *t2++ = '\0';
                    dispatch_media_action(&rp, cur, t1 ? t1 : "", t2 ? t2 : "");
                }
                cur = nl + 1;
            }
            size_t rem = strlen(cur);
            memmove(in_buf, cur, rem);
            in_len = rem;
        }
    }

    rish_close(&rp);
    return 0;
}

static int cmd_media_status(void) {
    RishPipe rp = { .pid = -1, .to_fd = -1, .from_fd = -1, .seq = 0 };
    query_and_emit_media(&rp);
    rish_close(&rp);
    return 0;
}

int main(int argc, char **argv) {
    install_signals();
    if (argc < 2) {
        fprintf(stderr, "usage: qs-native <cpu|sys-diag|hide-cursor|submenu-watch|wl-workspaces|media-stream|media-status>\n");
        return 2;
    }
    const char *sub = argv[1];
    if (strcmp(sub, "cpu") == 0) return cmd_cpu();
    if (strcmp(sub, "sys-diag") == 0) return cmd_sys_diag();
    if (strcmp(sub, "hide-cursor") == 0) return cmd_hide_cursor();
    if (strcmp(sub, "submenu-watch") == 0) return cmd_submenu_watch(argc, argv);
    if (strcmp(sub, "wl-workspaces") == 0) return cmd_wl_workspaces();
    if (strcmp(sub, "media-stream") == 0) return cmd_media_stream();
    if (strcmp(sub, "media-status") == 0) return cmd_media_status();

    fprintf(stderr, "qs-native: unknown subcommand '%s'\n", sub);
    return 2;
}
"""

START_WAYLAND_SH = """#!/data/data/com.termux/files/usr/bin/bash
set -u

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
export DISPLAY="${DISPLAY:-:0}"
export TERMUX_X11_DISPLAY="$DISPLAY"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-$PREFIX/tmp}"
export TMPDIR="${TMPDIR:-$XDG_RUNTIME_DIR}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
export XDG_SESSION_TYPE="wayland"
export XCURSOR_THEME="TouchDot-Mocha"
export XCURSOR_SIZE="32"
export WLR_NO_HARDWARE_CURSORS="1"

BACKEND="x11"
WM="sway"
USER_RENDERER="${WLR_RENDERER:-}"
for arg in "$@"; do
  case "$arg" in
    --tgui) BACKEND="tgui" ;;
    --x11)  BACKEND="x11" ;;
    --renderer=*) USER_RENDERER="${arg#--renderer=}" ;;
    sway|labwc) WM="$arg" ;;
    -h|--help)
      echo "Usage: $(basename "$0") [sway|labwc] [--x11|--tgui] [--renderer=pixman|gles2|vulkan]"
      exit 0
      ;;
  esac
done

export WLR_BACKENDS="$BACKEND"
if [ -n "$USER_RENDERER" ]; then
  export WLR_RENDERER="$USER_RENDERER"
else
  # pixman works across both termux-x11 and tgui (tgui R/B + Y-flip fixed via libtgui_fix.so)
  export WLR_RENDERER="pixman"
fi

cleanup() {
  pkill -x quickshell qs-native swaybg sway labwc polybar eww sxhkd bspwm termux-x11 2>/dev/null || true
  rm -f "$XDG_RUNTIME_DIR/.X11-unix/X0" "$XDG_RUNTIME_DIR/wayland-0" "$XDG_RUNTIME_DIR/wayland-0.lock"
}
trap cleanup EXIT INT TERM

# Clean stale sessions before launching
eww kill >/dev/null 2>&1 || true
pkill -x quickshell qs-native swaybg sway labwc polybar eww fastcompmgr picom sxhkd bspwm termux-x11 2>/dev/null || true
pkill -f "com.termux.x11" 2>/dev/null || true
rm -f "$XDG_RUNTIME_DIR/.X11-unix/X0" "$XDG_RUNTIME_DIR/wayland-0" "$XDG_RUNTIME_DIR/wayland-0.lock"
sleep 0.5

if ! command -v "$WM" >/dev/null 2>&1; then
  if [ "$WM" = "sway" ] && command -v labwc >/dev/null 2>&1; then
    WM="labwc"
  elif [ "$WM" = "labwc" ] && command -v sway >/dev/null 2>&1; then
    WM="sway"
  else
    echo "[-] Neither sway nor labwc is installed"
    exit 1
  fi
fi

if command -v pulseaudio >/dev/null 2>&1; then
  pulseaudio --start --exit-idle-time=-1 2>/dev/null || true
fi

if [ "$WM" = "labwc" ]; then
  THEME_DIR="$HOME/.themes/Catppuccin-Mocha/openbox-3"
  mkdir -p "$THEME_DIR"
  cp -f "$XDG_CONFIG_HOME/labwc/themerc" "$THEME_DIR/themerc" 2>/dev/null || true
  WM_CMD="$WM -C $XDG_CONFIG_HOME/labwc"
else
  WM_CMD="$WM -c $XDG_CONFIG_HOME/sway/config"
fi

if [ "$BACKEND" = "tgui" ]; then
  TGUI_SHIM="$HOME/.local/lib/libtgui_fix.so"
  am start --user 0 -n com.termux.gui/.GUIActivity >/dev/null 2>&1 || true
  if [ -f "$TGUI_SHIM" ]; then
    if command -v dbus-launch >/dev/null 2>&1; then
      exec dbus-launch --exit-with-session env LD_PRELOAD="$TGUI_SHIM" $WM_CMD
    else
      exec env LD_PRELOAD="$TGUI_SHIM" $WM_CMD
    fi
  else
    if command -v dbus-launch >/dev/null 2>&1; then
      exec dbus-launch --exit-with-session $WM_CMD
    else
      exec $WM_CMD
    fi
  fi
fi

# Nested Wayland on Termux:X11
am start --user 0 -n com.termux.x11/com.termux.x11.MainActivity >/dev/null 2>&1 || true
if command -v dbus-launch >/dev/null 2>&1; then
  termux-x11 :0 -xstartup "dbus-launch --exit-with-session $WM_CMD"
else
  termux-x11 :0 -xstartup "$WM_CMD"
fi
"""


WALLPAPER_URL = "https://raw.githubusercontent.com/Ahwxorg/Wallpapers/main/aenami/alena-aenami-eternity-1080px.jpg"

XRESOURCES_CURSOR = """Xcursor.theme: TouchDot-Mocha
Xcursor.size: 32
"""

TOUCHDOT_INDEX = """[Icon Theme]
Name=TouchDot-Mocha
Comment=iPadOS-style translucent Catppuccin Mocha touch-dot cursor
Inherits=Adwaita
"""

DEFAULT_CURSOR_INDEX = """[Icon Theme]
Inherits=TouchDot-Mocha
"""


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    """Return a formatted PNG chunk with length and CRC32."""
    return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def _write_rgba_png(path: str, size: int, pixel_fn) -> None:
    """Write a square RGBA PNG generated by pixel_fn(x, y, size) -> (r, g, b, a)."""
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            r, g, b, a = pixel_fn(x, y, size)
            rows.extend((r, g, b, a))
    ihdr = struct.pack("!IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _png_chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    """Hermite smoothstep clamped to [0, 1]."""
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def _dot_pixel(fill_rgb: tuple[int, int, int], ring_rgb: tuple[int, int, int], fill_alpha: float):
    """Build an anti-aliased frosted touch-dot pixel shader."""
    fr, fg, fb = fill_rgb
    rr, rg, rb = ring_rgb

    def shade(x: int, y: int, size: int) -> tuple[int, int, int, int]:
        half = (size - 1) / 2.0
        dist = math.hypot(x - half, y - half)
        r_outer = size * 0.36
        ring_w = max(1.5, size * 0.05)
        r_inner = r_outer - ring_w

        halo = (1.0 - _smoothstep(r_outer - 0.5, r_outer + 2.2, dist)) * 0.35
        ring = (1.0 - _smoothstep(r_outer - 0.8, r_outer + 0.8, dist)) * _smoothstep(r_inner - 0.8, r_inner + 0.6, dist)
        fill = (1.0 - _smoothstep(r_inner - 0.6, r_inner + 0.6, dist)) * fill_alpha

        # Composite shadow halo -> translucent fill -> crisp ring (non-premultiplied RGBA)
        a_out = min(1.0, halo + fill * (1.0 - halo) + ring * (1.0 - halo) * (1.0 - fill))
        if a_out <= 0.002:
            return (0, 0, 0, 0)
        r_out = (17 * halo * (1.0 - ring) * (1.0 - fill) + fr * fill * (1.0 - ring) + rr * ring) / max(0.001, halo + fill + ring)
        g_out = (17 * halo * (1.0 - ring) * (1.0 - fill) + fg * fill * (1.0 - ring) + rg * ring) / max(0.001, halo + fill + ring)
        b_out = (27 * halo * (1.0 - ring) * (1.0 - fill) + fb * fill * (1.0 - ring) + rb * ring) / max(0.001, halo + fill + ring)
        return (
            max(0, min(255, int(r_out))),
            max(0, min(255, int(g_out))),
            max(0, min(255, int(b_out))),
            max(0, min(255, int(a_out * 255))),
        )

    return shade


def _ibeam_pixel(x: int, y: int, size: int) -> tuple[int, int, int, int]:
    """Rounded vertical pill I-beam for clean text selection on tablet."""
    cx = (size - 1) / 2.0
    dx = abs(x - cx)
    bar_h = size * 0.30
    dy = max(0.0, abs(y - cx) - bar_h)
    dist = math.hypot(dx, dy)
    half_w = max(1.2, size * 0.045)
    core = 1.0 - _smoothstep(half_w - 0.6, half_w + 0.6, dist)
    outline = (1.0 - _smoothstep(half_w + 0.6, half_w + 1.8, dist)) * 0.65
    a = max(core * 0.92, outline)
    if a <= 0.002:
        return (0, 0, 0, 0)
    mix = core / max(0.001, core + outline * (1.0 - core))
    r = int(17 + (205 - 17) * mix)
    g = int(17 + (214 - 17) * mix)
    b = int(27 + (244 - 27) * mix)
    return (r, g, b, max(0, min(255, int(a * 255))))


def _install_touch_cursor_theme() -> None:
    """Generate TouchDot-Mocha Xcursor theme in ~/.icons using xcursorgen."""
    if not shutil.which("xcursorgen"):
        print("[-] xcursorgen not found; skipping TouchDot-Mocha cursor build")
        failures.append("building TouchDot-Mocha cursor theme")
        return

    theme_dir = os.path.expanduser("~/.icons/TouchDot-Mocha")
    cursors_dir = os.path.join(theme_dir, "cursors")
    default_dir = os.path.expanduser("~/.icons/default")
    os.makedirs(cursors_dir, exist_ok=True)
    os.makedirs(default_dir, exist_ok=True)

    with open(os.path.join(theme_dir, "index.theme"), "w") as f:
        f.write(TOUCHDOT_INDEX)
    with open(os.path.join(default_dir, "index.theme"), "w") as f:
        f.write(DEFAULT_CURSOR_INDEX)

    shapes = {
        "dot": _dot_pixel((205, 214, 244), (205, 214, 244), 0.38),
        "hand": _dot_pixel((137, 180, 250), (137, 180, 250), 0.48),
        "busy": _dot_pixel((203, 166, 247), (203, 166, 247), 0.45),
        "ibeam": _ibeam_pixel,
    }
    aliases = {
        "dot": [
            "left_ptr", "default", "arrow", "top_left_arrow", "X_cursor",
            "move", "fleur", "all-scroll", "all-resize", "dnd-move", "dnd-ask",
            "copy", "alias", "context-menu", "cross", "crosshair", "cross_reverse",
            "tcross", "cell", "diamond_cross", "help", "question_arrow",
            "not-allowed", "no-drop", "zoom-in", "zoom-out",
            "n-resize", "s-resize", "e-resize", "w-resize",
            "ne-resize", "nw-resize", "se-resize", "sw-resize",
            "ns-resize", "ew-resize", "nesw-resize", "nwse-resize",
            "col-resize", "row-resize", "sb_h_double_arrow", "sb_v_double_arrow",
            "bd_double_arrow", "fd_double_arrow",
            "top_side", "bottom_side", "left_side", "right_side",
            "top_left_corner", "top_right_corner", "bottom_left_corner", "bottom_right_corner",
        ],
        "hand": ["pointer", "hand1", "hand2", "grab", "grabbing"],
        "ibeam": ["xterm", "text", "vertical-text"],
        "busy": ["watch", "wait", "progress"],
    }

    with tempfile.TemporaryDirectory() as tmp:
        for base, shader in shapes.items():
            cfg_lines = []
            for sz in (32, 48):
                png_path = os.path.join(tmp, f"{base}_{sz}.png")
                _write_rgba_png(png_path, sz, shader)
                hot = sz // 2
                cfg_lines.append(f"{sz} {hot} {hot} {png_path}\n")
            cfg_path = os.path.join(tmp, f"{base}.cfg")
            with open(cfg_path, "w") as f:
                f.writelines(cfg_lines)
            out_path = os.path.join(cursors_dir, base)
            subprocess.run(["xcursorgen", cfg_path, out_path], check=True)
            for name in aliases[base]:
                link_path = os.path.join(cursors_dir, name)
                if os.path.lexists(link_path):
                    os.unlink(link_path)
                os.symlink(base, link_path)

    print("[+] built ~/.icons/TouchDot-Mocha cursor theme")


def _build_tgui_fix_shim() -> None:
    """Compile LD_PRELOAD shim fixing Termux:GUI ABGR8888 pixel format and FLIPPED_180 transform."""
    if not shutil.which("clang"):
        print("[-] clang not found; skipping libtgui_fix.so build")
        failures.append("building libtgui_fix.so")
        return

    lib_dir = os.path.expanduser("~/.local/lib")
    os.makedirs(lib_dir, exist_ok=True)
    c_path = os.path.join(lib_dir, "tgui_fix.c")
    so_path = os.path.join(lib_dir, "libtgui_fix.so")
    try:
        with open(c_path, "w") as f:
            f.write(TGUI_FIX_C)
        subprocess.run(["clang", "-shared", "-fPIC", "-O2", c_path, "-ldl", "-o", so_path], check=True)
        print("[+] built ~/.local/lib/libtgui_fix.so")
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"[-] building ~/.local/lib/libtgui_fix.so failed: {e}")
        failures.append("building libtgui_fix.so")


def _build_native_daemons() -> None:
    """Compile ~/.local/bin/qs-native (C multi-call daemon for sys-diag, media-stream, X11, Wayland)."""
    if not shutil.which("clang"):
        print("[-] clang not found; skipping qs-native build")
        failures.append("building qs-native")
        return

    lib_dir = os.path.expanduser("~/.local/lib")
    bin_dir = os.path.expanduser("~/.local/bin")
    os.makedirs(lib_dir, exist_ok=True)
    os.makedirs(bin_dir, exist_ok=True)
    c_path = os.path.join(lib_dir, "qs_native.c")
    bin_path = os.path.join(bin_dir, "qs-native")
    try:
        with open(c_path, "w") as f:
            f.write(QS_NATIVE_C)
        subprocess.run(
            ["clang", "-O2", "-Wall", "-Wextra", "-Werror", c_path, "-lm", "-lX11", "-lXi", "-lXfixes", "-o", bin_path],
            check=True,
        )
        os.chmod(bin_path, 0o755)
        print("[+] built ~/.local/bin/qs-native")
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"[-] building ~/.local/bin/qs-native failed: {e}")
        failures.append("building qs-native")


RISH_WRAPPER_SH = """#!/data/data/com.termux/files/usr/bin/sh
# Shizuku rish wrapper hardened for Android 14+ (read-only dex + clean LD env)
PREFIX_DIR="${PREFIX:-/data/data/com.termux/files/usr}"
RISH_DEX="$PREFIX_DIR/share/rish-shizuku.dex"

if [ ! -f "$RISH_DEX" ]; then
    echo "rish: $RISH_DEX not found (install with: pkg install rish-shizuku)" >&2
    exit 127
fi

# Android 14+ aborts app_process with SIGABRT if the dex file is writable by owner.
if [ -w "$RISH_DEX" ]; then
    chmod 0400 "$RISH_DEX" || exit $?
fi

unset LD_LIBRARY_PATH LD_PRELOAD
export RISH_APPLICATION_ID="${RISH_APPLICATION_ID:-com.termux}"
exec /system/bin/app_process \\
    -Djava.class.path="$RISH_DEX" \\
    /system/bin \\
    --nice-name=rish \\
    rikka.shizuku.shell.ShizukuShellLoader "${@}"
"""


def configure_rish() -> int:
    """Install/harden rish-shizuku and write ~/.local/bin/rish wrapper."""
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    rish_dex = os.path.join(prefix, "share", "rish-shizuku.dex")
    if not os.path.exists(rish_dex):
        run("pkg install rish-shizuku -y", "installing rish-shizuku")

    if os.path.exists(rish_dex):
        try:
            if (os.stat(rish_dex).st_mode & 0o777) & 0o222:
                os.chmod(rish_dex, 0o400)
                print("[+] set read-only 0400 on rish-shizuku.dex")
        except OSError as e:
            print(f"[-] chmod 0400 on rish-shizuku.dex failed: {e}")
            failures.append("hardening rish-shizuku.dex")

    wrapper_path = os.path.expanduser("~/.local/bin/rish")
    try:
        os.makedirs(os.path.dirname(wrapper_path), exist_ok=True)
        with open(wrapper_path, "w") as f:
            f.write(RISH_WRAPPER_SH)
        os.chmod(wrapper_path, 0o755)
        print("[+] wrote ~/.local/bin/rish")
    except OSError as e:
        print(f"[-] writing ~/.local/bin/rish failed: {e}")
        failures.append("writing ~/.local/bin/rish")
        return 1
    return 0


def configure_x11() -> int:
    """Write minimal bspwm, sxhkd, polybar, picom, rofi, xfce4-terminal configs and ~/start-x11.sh."""
    wall_dir = os.path.expanduser("~/.local/share/wallpapers")
    wall_path = os.path.join(wall_dir, "wallpaper.jpg")
    if not os.path.exists(wall_path):
        os.makedirs(wall_dir, exist_ok=True)
        run(
            f"curl -fsSL '{WALLPAPER_URL}' -o '{wall_path}.tmp' && mv '{wall_path}.tmp' '{wall_path}'",
            "downloading wallpaper",
        )

    _install_touch_cursor_theme()
    _build_tgui_fix_shim()
    _build_native_daemons()
    configure_rish()

    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    prefix_bin = os.path.join(prefix, "bin")

    def _render_qs(tpl: str) -> str:
        return (
            tpl.replace("__ANDROID_STATUS_PROPS__", _QS_ANDROID_STATUS_PROPS)
            .replace("__ANDROID_STATUS_FN__", _QS_ANDROID_STATUS_FN)
            .replace("__ANDROID_STATUS_PROCS__", _QS_ANDROID_STATUS_PROCS)
            .replace("__ANDROID_STATUS_CARD__", _QS_ANDROID_STATUS_CARD)
            .replace("__MEDIA_PROPS__", _QS_MEDIA_PROPS)
            .replace("__MEDIA_FN__", _QS_MEDIA_FN)
            .replace("__MEDIA_PROCS__", _QS_MEDIA_PROCS)
            .replace("__MEDIA_CARD__", _QS_MEDIA_CARD)
            .replace("__WEATHER_PROPS__", _QS_WEATHER_PROPS)
            .replace("__WEATHER_FN__", _QS_WEATHER_FN)
            .replace("__WEATHER_PROCS__", _QS_WEATHER_PROCS)
            .replace("__WEATHER_CARD__", _QS_WEATHER_CARD)
        )

    files = [
        ("~/.Xresources", XRESOURCES_CURSOR, 0o644),
        ("~/.config/bspwm/bspwmrc", BSPWMRC, 0o755),
        ("~/.config/bspwm/hide-cursor.py", HIDE_CURSOR_PY, 0o755),
        ("~/.config/sxhkd/sxhkdrc", SXHKDRC, 0o644),
        ("~/.config/polybar/config.ini", POLYBAR_CONFIG, 0o644),
        ("~/.config/polybar/battery.sh", POLYBAR_BATTERY_SH, 0o755),
        ("~/.config/polybar/cpu.py", POLYBAR_CPU_PY, 0o755),
        ("~/.config/polybar/launch.sh", POLYBAR_LAUNCH, 0o755),
        ("~/.config/eww/eww.yuck", EWW_YUCK, 0o644),
        ("~/.config/eww/eww.scss", EWW_SCSS, 0o644),
        ("~/.config/eww/launch.sh", EWW_LAUNCH_SH, 0o755),
        ("~/.config/eww/scripts/bspwm_state.py", EWW_BSPWM_STATE_PY, 0o755),
        ("~/.config/eww/scripts/audio_state.sh", EWW_AUDIO_STATE_SH, 0o755),
        ("~/.config/eww/scripts/toggle_window.sh", EWW_TOGGLE_WINDOW_SH, 0o755),
        ("~/.config/eww/scripts/submenu_watch.py", EWW_SUBMENU_WATCH_PY, 0o755),
        ("~/.config/quickshell/shell.qml", _render_qs(QUICKSHELL_QML), 0o644),
        ("~/.config/quickshell/wayland.qml", _render_qs(QUICKSHELL_WAYLAND_QML), 0o644),
        ("~/.config/quickshell/launch.sh", QUICKSHELL_LAUNCH, 0o755),
        ("~/.config/quickshell/launch-wayland.sh", QUICKSHELL_WAYLAND_LAUNCH, 0o755),
        ("~/.config/quickshell/scripts/submenu_watch.py", QUICKSHELL_SUBMENU_WATCH_PY, 0o755),
        ("~/.config/quickshell/scripts/sys_diag.py", QUICKSHELL_SYS_DIAG_PY, 0o755),
        ("~/.config/quickshell/scripts/wl_workspaces.py", QUICKSHELL_WL_WORKSPACES_PY, 0o755),
        ("~/.config/quickshell/scripts/android_status.py", QUICKSHELL_ANDROID_STATUS_PY, 0o755),
        ("~/.config/quickshell/scripts/media_control.py", QUICKSHELL_MEDIA_CONTROL_PY, 0o755),
        ("~/.config/quickshell/scripts/weather.py", QUICKSHELL_WEATHER_PY, 0o755),
        ("~/.config/sway/config", SWAY_CONFIG, 0o644),
        ("~/.config/labwc/rc.xml", LABWC_RC_XML, 0o644),
        ("~/.config/labwc/themerc", LABWC_THEMERC, 0o644),
        ("~/.config/labwc/autostart", LABWC_AUTOSTART, 0o755),
        ("~/.config/foot/foot.ini", FOOT_INI, 0o644),
        ("~/.config/picom/picom.conf", PICOM_CONF, 0o644),
        ("~/.config/rofi/config.rasi", ROFI_CONFIG, 0o644),
        ("~/.config/xfce4/terminal/terminalrc", XFCE4_TERMINAL_RC, 0o644),
        ("~/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-terminal.xml", XFCE4_TERMINAL_XML, 0o644),
        ("~/start-x11.sh", START_X11_SH, 0o755),
        ("~/start-wayland.sh", START_WAYLAND_SH, 0o755),
        (os.path.join(prefix_bin, "desktop"), START_X11_SH, 0o755),
        (os.path.join(prefix_bin, "desktop-wayland"), START_WAYLAND_SH, 0o755),
    ]
    for raw_path, content, mode in files:
        path = os.path.expanduser(raw_path)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            os.chmod(path, mode)
            print(f"[+] wrote {raw_path}")
        except OSError as e:
            print(f"[-] writing {raw_path} failed: {e}")
            failures.append(f"writing {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())