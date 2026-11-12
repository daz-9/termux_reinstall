import subprocess
import os
import shutil
import sys


# everything that failed gets collected here and printed at the end
failures: list[str] = []


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
    if not failures:
        print("\n[+] Configure finished with no errors")
        return
    print(f"\n[!] Configure finished with {len(failures)} problem(s):")
    for f in failures:
        print(f"    - {f}")


def main() -> int:
    # Flags for non-interactive use
    args = sys.argv[1:]
    if args:
        dispatch(tuple(arg.lstrip("-") for arg in args))
        print_summary()
        return 1 if failures else 0

    from simple_term_menu import TerminalMenu

    terminal_menu = TerminalMenu(
        ["Zsh", "Neovim", "Font", "Tmux"],
        multi_select=True,
        show_multi_select_hint=True,
        title="Select what to configure (use space to select, enter to confirm):"
    )
    menu_entry_indices = terminal_menu.show()
    #print(menu_entry_indices)
    #print(terminal_menu.chosen_menu_entries)
    

    # If no menu entry was selected, exit with code 1
    if not menu_entry_indices:
        print("[!] No menu entry selected. Exiting.")
        return 1
    dispatch(terminal_menu.chosen_menu_entries)
    print_summary()
    return 1 if failures else 0

def neovim_config():
    from simple_term_menu import TerminalMenu
    neovim_config_menu = TerminalMenu(
        ["LazyVim", "AstroNvim"],
        multi_select=False,
        title="Select Neovim config (press enter to confirm):"
    )
    menu_entry_index = neovim_config_menu.show()
    if menu_entry_index is None:
        print("[!] No menu entry selected. Exiting.")
        return 1
    return dispatch_neovim_config((neovim_config_menu.chosen_menu_entry,))


def dispatch(choices: tuple[str, ...]) -> int:


    # keys are lowercase so menu entries ("Zsh") and flags ("--zsh") both match
    handlers = {
        "zsh":     lambda: configure_zsh(),
        "neovim": lambda: neovim_config(),
        "lazyvim": lambda: configure_vim_lazyvim(),    # flag-only shortcut, skips the nvim menu
        "astronvim": lambda: configure_vim_astrovim(), # flag-only shortcut, skips the nvim menu
        "font": lambda: configure_font(),
        "tmux": lambda: configure_tmux(),
    }

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

def dispatch_neovim_config(choices: tuple[str, ...]) -> int:
    handlers = {
        "lazyvim": lambda: configure_vim_lazyvim(),
        "astronvim": lambda: configure_vim_astrovim(),
    }

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


def configure_zsh():
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
            env={"RUNZSH": "no", "CHSH": "no"},
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
    custom = os.environ.get("ZSH_CUSTOM", os.path.join(omz_dir, "custom"))
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
    import re
    with open(zshrc) as f:
        text = f.read()
    m = re.search(r"^plugins=\(([^)]*)\)", text, re.M)
    if not m:
        print("[-] no plugins=(...) line in ~/.zshrc, can't enable plugins")
        failures.append("enabling zsh plugins (no plugins= line)")
        return
    current = m.group(1).split()
    wanted = ["git", "z", "colored-man-pages"] + extra  # git/z/colored-man-pages ship with omz
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

STARSHIP_CONFIG = """# Starship configuration matching Catppuccin Mocha & Termux screen width

format = \"\"\"
$directory\\
$git_branch\\
$git_status\\
$c\\
$xmake\\
$fill\\
$cmd_duration\\
$line_break\\
$character\"\"\"

# Don't print empty line between prompts on mobile screen
add_newline = false

[directory]
style = "bold lavender"
truncation_length = 3
truncate_to_repo = true
read_only = " 󰌾"

[git_branch]
symbol = " "
style = "bold mauve"

[git_status]
style = "bold red"
format = '([$all_status$ahead_behind]($style) )'

[c]
symbol = " "
style = "bold sapphire"
format = "via [$symbol($version )]($style)"

[xmake]
symbol = " "
style = "bold sapphire"
format = "via [$symbol($version )]($style)"

[cmd_duration]
min_time = 2_000
style = "bold yellow"
format = "took [$duration]($style)"

[fill]
symbol = " "

[character]
success_symbol = "[❯](bold green)"
error_symbol = "[❯](bold red)"
vicmd_symbol = "[❮](bold peach)"
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
    path = os.path.expanduser("~/.config/starship.toml")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(STARSHIP_CONFIG)
        print("[+] wrote ~/.config/starship.toml")
    except OSError as e:
        print(f"[-] writing starship.toml failed: {e}")
        failures.append("writing starship.toml")
    if not shutil.which("starship"):
        print("[!] starship not found yet, install starship (run Setup) to enable prompt")


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

# Vi copy mode
setw -g mode-keys vi
bind -T copy-mode-vi v send-keys -X begin-selection
bind -T copy-mode-vi y send-keys -X copy-selection-and-cancel

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


def configure_tmux():
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

def configure_font():
    ok = run("mkdir -p ~/.termux/", "creating ~/.termux")
    # download to a temp file first so a failed download doesn't wipe the current font
    ok = ok and run("curl -fsSL https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/patched-fonts/JetBrainsMono/Ligatures/JetBrainsMonoNerdFont-Regular.ttf -o ~/.termux/font.ttf.tmp && mv ~/.termux/font.ttf.tmp ~/.termux/font.ttf", "downloading Nerd Font")
    if ok:
        run("termux-reload-settings", "termux-reload-settings")
    return 0 if ok else 1

def _backup_nvim_dirs():
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

def _write_clangd_spec(content: str):
    path = os.path.expanduser("~/.config/nvim/lua/plugins/clangd.lua")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        print("[+] Neovim set to use system clangd")
    except OSError as e:
        print(f"[-] writing clangd config failed: {e}")
        failures.append("writing clangd config")
    if not shutil.which("clangd"):
        print("[!] clangd not found yet, install clang (run Setup) for C completion/diagnostics")

def configure_vim_lazyvim():
    _backup_nvim_dirs()
    if not run("git clone https://github.com/LazyVim/starter ~/.config/nvim", "cloning LazyVim"): #nvim config
        _restore_nvim_dirs()
        return 1
    subprocess.run("rm -rf ~/.config/nvim/.git", shell=True) #remove git history
    _write_clangd_spec(CLANGD_LAZYVIM)
    return 0

def configure_vim_astrovim():
    _backup_nvim_dirs()
    if not run("git clone --depth 1 https://github.com/AstroNvim/template ~/.config/nvim", "cloning AstroNvim"): #nvim config
        _restore_nvim_dirs()
        return 1
    subprocess.run("rm -rf ~/.config/nvim/.git", shell=True) #remove git history
    _write_clangd_spec(CLANGD_ASTRONVIM)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())