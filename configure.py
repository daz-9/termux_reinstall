#!/usr/bin/env python3
"""Configure Zsh/Starship, Neovim (AstroNvim/LazyVim + native LSPs), Font/Colors, and Tmux."""

import os
import re
import shutil
import subprocess
import sys

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
        ["Zsh", "Neovim", "Font", "Tmux", "Git"],
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
    "disable-hardware-keyboard-shortcuts": "true",
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


if __name__ == "__main__":
    raise SystemExit(main())