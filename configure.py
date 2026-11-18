#!/data/data/com.termux/files/usr/bin/env python3
"""Configure Zsh/Starship, Neovim (AstroNvim/LazyVim + native LSPs), Font/Colors, Tmux, Rish, and X11/Wayland GUIs."""

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

WALLPAPER_URL = "https://raw.githubusercontent.com/Ahwxorg/Wallpapers/main/aenami/alena-aenami-eternity-1080px.jpg"


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


def _asset_path(*parts: str) -> str:
    """Return absolute path to an asset inside the repository."""
    return os.path.join(HERE, *parts)


def _read_asset(*parts: str) -> str:
    """Read a UTF-8 text asset from the repository."""
    with open(_asset_path(*parts), encoding="utf-8") as f:
        return f.read()


def _install_text(content: str, dest_raw: str, mode: int = 0o644) -> bool:
    """Write text content to dest_raw (expanding ~) with directory creation and chmod."""
    dest = os.path.expanduser(dest_raw)
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(dest, mode)
        print(f"[+] wrote {dest_raw}")
        return True
    except OSError as e:
        print(f"[-] writing {dest_raw} failed: {e}")
        failures.append(f"writing {dest_raw}")
        return False


def _install_asset(src_parts: tuple[str, ...], dest_raw: str, mode: int = 0o644, backup: bool = False) -> bool:
    """Install a file from the repo into dest_raw, optionally backing up an existing file."""
    dest = os.path.expanduser(dest_raw)
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if backup and os.path.exists(dest):
            shutil.copy2(dest, dest + ".bak")
        shutil.copyfile(_asset_path(*src_parts), dest)
        os.chmod(dest, mode)
        print(f"[+] wrote {dest_raw}")
        return True
    except OSError as e:
        print(f"[-] writing {dest_raw} failed: {e}")
        failures.append(f"writing {dest_raw}")
        return False


def _build_c_artifact(src_rel: tuple[str, ...], lib_copy_name: str, out_raw: str, cflags: list[str], mode: int) -> None:
    """Copy a C source asset into ~/.local/lib and compile it with clang."""
    out_path = os.path.expanduser(out_raw)
    if not shutil.which("clang"):
        print(f"[-] clang not found; skipping {out_raw} build")
        failures.append(f"building {out_raw}")
        return

    lib_dir = os.path.expanduser("~/.local/lib")
    os.makedirs(lib_dir, exist_ok=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    c_path = os.path.join(lib_dir, lib_copy_name)
    try:
        shutil.copyfile(_asset_path(*src_rel), c_path)
        subprocess.run(["clang", *cflags, c_path, "-o", out_path], check=True)
        os.chmod(out_path, mode)
        print(f"[+] built {out_raw}")
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"[-] building {out_raw} failed: {e}")
        failures.append(f"building {out_raw}")


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
    return _run_handlers(choices, {
        "zsh": lambda: configure_zsh(),
        "neovim": lambda: neovim_config(),
        "lazyvim": lambda: configure_vim_lazyvim(),
        "astronvim": lambda: configure_vim_astrovim(),
        "font": lambda: configure_font(),
        "termux": lambda: configure_font(),
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

ZSH_PLUGIN_REPOS = {
    "zsh-autosuggestions": "https://github.com/zsh-users/zsh-autosuggestions",
    "zsh-syntax-highlighting": "https://github.com/zsh-users/zsh-syntax-highlighting",  # must stay last in plugins=()
}

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
    """Add plugins to the plugins=(...) line in ~/.zshrc."""
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
    wanted = ["git", "colored-man-pages"] + extra
    merged = current + [p for p in wanted if p not in current]
    if "zsh-syntax-highlighting" in merged:
        merged.remove("zsh-syntax-highlighting")
        merged.append("zsh-syntax-highlighting")
    text = text[:m.start()] + f"plugins=({' '.join(merged)})" + text[m.end():]
    with open(zshrc, "w") as f:
        f.write(text)
    print(f"[+] zsh plugins: {' '.join(merged)}")


def configure_starship():
    """Copy dotfiles/shell/starship.toml into ~/.config/starship.toml."""
    _install_asset(("dotfiles", "shell", "starship.toml"), "~/.config/starship.toml")
    if not shutil.which("starship"):
        print("[!] starship not found yet, install starship (run Setup) to enable prompt")


def configure_zsh() -> int:
    """Install Oh My Zsh, plugins, aliases, CLI tool hooks, Starship prompt, and rish."""
    if not shutil.which("zsh"):
        print("[-] zsh is not installed (run Setup first), skipping Oh My Zsh")
        failures.append("Oh My Zsh skipped: zsh not installed")
        return 1
    omz_dir = os.path.expanduser("~/.oh-my-zsh")
    if os.path.isdir(omz_dir):
        print("[+] Oh My Zsh already installed, skipping install")
    else:
        ok = run(
            "sh -c \"$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)\" \"\" --unattended",
            "installing Oh My Zsh",
            env={"RUNZSH": "no", "CHSH": "no", "ZSH": omz_dir},
        )
        if not ok:
            return 1

    plugins = install_zsh_plugins(omz_dir)
    enable_zsh_plugins(plugins)
    _append_zshrc_block(ZSH_ALIASES_MARKER, ZSH_ALIASES, "aliases")
    _append_zshrc_block(ZSH_CLI_TOOLS_MARKER, ZSH_CLI_TOOLS, "CLI tools (zoxide, fzf, bat)")
    configure_starship()
    _append_zshrc_block(ZSH_STARSHIP_MARKER, ZSH_STARSHIP, "starship prompt")
    configure_rish()
    return 0


# --- Tmux, Termux Font/Properties & Git -------------------------------------

TERMUX_PROPERTIES = {
    "hide-soft-keyboard-on-startup": "true",
    "volume-keys": "volume",
    "extra-keys": "[]",
    "disable-hardware-keyboard-shortcuts": "false",
    "bell-character": "ignore",
    "back-key": "escape",
}


def configure_tmux() -> int:
    """Install dotfiles/tmux/tmux.conf to ~/.tmux.conf (with .bak backup)."""
    if not _install_asset(("dotfiles", "tmux", "tmux.conf"), "~/.tmux.conf", backup=True):
        return 1
    if not shutil.which("tmux"):
        print("[!] tmux not found yet, install tmux (run Setup) to use it")
    return 0


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
                if re.match(rf"^\s*#?\s*{re.escape(key)}\s*=", line):
                    is_commented = line.lstrip().startswith("#")
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
    """Download JetBrainsMono Nerd Font, install Catppuccin colors, and set termux.properties."""
    termux_dir = os.path.expanduser("~/.termux")
    ok = run("mkdir -p ~/.termux/", "creating ~/.termux")
    ok = ok and run(
        "curl -fsSL https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/patched-fonts/JetBrainsMono/Ligatures/JetBrainsMonoNerdFont-Regular.ttf -o ~/.termux/font.ttf.tmp && mv ~/.termux/font.ttf.tmp ~/.termux/font.ttf",
        "downloading Nerd Font",
    )
    ok = _install_asset(("dotfiles", "termux", "colors.properties"), "~/.termux/colors.properties") and ok
    ok = _configure_termux_properties(termux_dir) and ok
    if ok:
        run("termux-reload-settings", "termux-reload-settings")
    return 0 if ok else 1


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

    ok = _install_asset(("dotfiles", "lazygit", "config.yml"), "~/.config/lazygit/config.yml", backup=True) and ok
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
            shutil.move(p, bak)


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


def _write_lsp_spec(distro: str, filename: str, bin_name: str, missing_hint: str):
    """Copy a Neovim plugin spec from dotfiles/nvim/<distro>/ to bypass Mason."""
    if _install_asset(("dotfiles", "nvim", distro, filename), f"~/.config/nvim/lua/plugins/{filename}"):
        print(f"[+] Neovim set to use system {bin_name}")
    if not (shutil.which(bin_name) or os.path.exists(os.path.expanduser(f"~/.dotnet/tools/{bin_name}"))):
        print(f"[!] {bin_name} not found yet, {missing_hint}")


def configure_vim_lazyvim() -> int:
    """Install LazyVim starter config and wire up Termux-native LSPs."""
    _backup_nvim_dirs()
    if not run("git clone https://github.com/LazyVim/starter ~/.config/nvim", "cloning LazyVim"):
        _restore_nvim_dirs()
        return 1
    subprocess.run("rm -rf ~/.config/nvim/.git", shell=True)
    _write_lsp_spec("lazyvim", "clangd.lua", "clangd", "install clang (run Setup) for C completion/diagnostics")
    _write_lsp_spec("lazyvim", "lua_ls.lua", "lua-language-server", "install lua-language-server (run Setup) for Lua completion/diagnostics")
    _write_lsp_spec("lazyvim", "csharp_ls.lua", "csharp-ls", "install dotnet-sdk-9.0 + csharp-ls (run Setup) for C# completion/diagnostics")
    _write_lsp_spec("lazyvim", "python_lsp.lua", "basedpyright-langserver", "install nodejs + basedpyright + ruff (run Setup) for Python completion/diagnostics")
    _write_lsp_spec("lazyvim", "termux_cursor.lua", "nvim", "")
    return 0


def configure_vim_astrovim() -> int:
    """Install AstroNvim template config and wire up Termux-native LSPs."""
    _backup_nvim_dirs()
    if not run("git clone --depth 1 https://github.com/AstroNvim/template ~/.config/nvim", "cloning AstroNvim"):
        _restore_nvim_dirs()
        return 1
    subprocess.run("rm -rf ~/.config/nvim/.git", shell=True)
    _write_lsp_spec("astronvim", "clangd.lua", "clangd", "install clang (run Setup) for C completion/diagnostics")
    _write_lsp_spec("astronvim", "lua_ls.lua", "lua-language-server", "install lua-language-server (run Setup) for Lua completion/diagnostics")
    _write_lsp_spec("astronvim", "csharp_ls.lua", "csharp-ls", "install dotnet-sdk-9.0 + csharp-ls (run Setup) for C# completion/diagnostics")
    _write_lsp_spec("astronvim", "python_lsp.lua", "basedpyright-langserver", "install nodejs + basedpyright + ruff (run Setup) for Python completion/diagnostics")
    _write_lsp_spec("astronvim", "mason.lua", "nvim", "")
    _write_lsp_spec("astronvim", "termux_cursor.lua", "nvim", "")
    _write_lsp_spec("astronvim", "snacks.lua", "nvim", "")
    _install_asset(("dotfiles", "nvim", "astronvim", "community.lua"), "~/.config/nvim/lua/community.lua")
    return 0


# --- Touch Cursor Generator & Native Daemons ---------------------------------

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

        a_out = min(1.0, halo + fill * (1.0 - halo) + ring * (1.0 - halo) * (1.0 - fill))
        if a_out <= 0.002:
            return (0, 0, 0, 0)
        denom = max(0.001, halo + fill + ring)
        r_out = (17 * halo * (1.0 - ring) * (1.0 - fill) + fr * fill * (1.0 - ring) + rr * ring) / denom
        g_out = (17 * halo * (1.0 - ring) * (1.0 - fill) + fg * fill * (1.0 - ring) + rg * ring) / denom
        b_out = (27 * halo * (1.0 - ring) * (1.0 - fill) + fb * fill * (1.0 - ring) + rb * ring) / denom
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

    shutil.copyfile(_asset_path("dotfiles", "x11", "cursors", "touchdot-index.theme"), os.path.join(theme_dir, "index.theme"))
    shutil.copyfile(_asset_path("dotfiles", "x11", "cursors", "default-index.theme"), os.path.join(default_dir, "index.theme"))

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

    return 0 if _install_asset(("daemons", "bin", "rish"), "~/.local/bin/rish", 0o755) else 1


def _render_quickshell(tpl_name: str) -> str:
    """Expand shared QML widget/partial templates into shell.qml or wayland.qml."""
    partials = {
        "__ANDROID_STATUS_PROPS__": ("dotfiles", "quickshell", "partials", "android_status_props.qml"),
        "__ANDROID_STATUS_FN__": ("dotfiles", "quickshell", "partials", "android_status_fn.qml"),
        "__ANDROID_STATUS_PROCS__": ("dotfiles", "quickshell", "partials", "android_status_procs.qml"),
        "__ANDROID_STATUS_CARD__": ("dotfiles", "quickshell", "partials", "android_status_card.qml"),
        "__MEDIA_PROPS__": ("dotfiles", "quickshell", "partials", "media_props.qml"),
        "__MEDIA_FN__": ("dotfiles", "quickshell", "partials", "media_fn.qml"),
        "__MEDIA_PROCS__": ("dotfiles", "quickshell", "partials", "media_procs.qml"),
        "__MEDIA_CARD__": ("dotfiles", "quickshell", "partials", "media_card.qml"),
        "__WEATHER_PROPS__": ("dotfiles", "quickshell", "partials", "weather_props.qml"),
        "__WEATHER_FN__": ("dotfiles", "quickshell", "partials", "weather_fn.qml"),
        "__WEATHER_PROCS__": ("dotfiles", "quickshell", "partials", "weather_procs.qml"),
        "__WEATHER_CARD__": ("dotfiles", "quickshell", "partials", "weather_card.qml"),
        "__FOCUS_PROPS__": ("dotfiles", "quickshell", "partials", "focus_props.qml"),
        "__FOCUS_CARD__": ("dotfiles", "quickshell", "partials", "focus_card.qml"),
        "__CALENDAR_PROPS__": ("dotfiles", "quickshell", "partials", "calendar_props.qml"),
        "__CALENDAR_FN__": ("dotfiles", "quickshell", "partials", "calendar_fn.qml"),
        "__CALENDAR_CARD__": ("dotfiles", "quickshell", "partials", "calendar_card.qml"),
        "__AGENDA_CARD__": ("dotfiles", "quickshell", "partials", "agenda_card.qml"),
    }
    text = _read_asset("dotfiles", "quickshell", tpl_name)
    for token, asset_parts in partials.items():
        text = text.replace(token, _read_asset(*asset_parts))
    return text


def configure_x11() -> int:
    """Build native daemons/cursors/shims and deploy X11, Wayland, and Quickshell configs."""
    wall_dir = os.path.expanduser("~/.local/share/wallpapers")
    wall_path = os.path.join(wall_dir, "wallpaper.jpg")
    if not os.path.exists(wall_path):
        os.makedirs(wall_dir, exist_ok=True)
        run(
            f"curl -fsSL '{WALLPAPER_URL}' -o '{wall_path}.tmp' && mv '{wall_path}.tmp' '{wall_path}'",
            "downloading wallpaper",
        )

    _install_touch_cursor_theme()
    _build_c_artifact(("daemons", "native", "tgui_fix.c"), "tgui_fix.c", "~/.local/lib/libtgui_fix.so", ["-shared", "-fPIC", "-O2", "-ldl"], 0o755)
    _build_c_artifact(("daemons", "native", "qs_native.c"), "qs_native.c", "~/.local/bin/qs-native", ["-O2", "-Wall", "-Wextra", "-Werror", "-lm", "-lX11", "-lXi", "-lXfixes"], 0o755)
    configure_rish()

    prefix_bin = os.path.join(os.environ.get("PREFIX", "/data/data/com.termux/files/usr"), "bin")
    assets = [
        (("dotfiles", "x11", "Xresources"), "~/.Xresources", 0o644),
        (("dotfiles", "x11", "bspwm", "bspwmrc"), "~/.config/bspwm/bspwmrc", 0o755),
        (("daemons", "scripts", "bspwm", "hide-cursor.py"), "~/.config/bspwm/hide-cursor.py", 0o755),
        (("dotfiles", "x11", "sxhkd", "sxhkdrc"), "~/.config/sxhkd/sxhkdrc", 0o644),
        (("dotfiles", "x11", "polybar", "config.ini"), "~/.config/polybar/config.ini", 0o644),
        (("dotfiles", "x11", "polybar", "battery.sh"), "~/.config/polybar/battery.sh", 0o755),
        (("daemons", "scripts", "polybar", "cpu.py"), "~/.config/polybar/cpu.py", 0o755),
        (("dotfiles", "x11", "polybar", "launch.sh"), "~/.config/polybar/launch.sh", 0o755),
        (("dotfiles", "x11", "eww", "eww.yuck"), "~/.config/eww/eww.yuck", 0o644),
        (("dotfiles", "x11", "eww", "eww.scss"), "~/.config/eww/eww.scss", 0o644),
        (("dotfiles", "x11", "eww", "launch.sh"), "~/.config/eww/launch.sh", 0o755),
        (("daemons", "scripts", "eww", "bspwm_state.py"), "~/.config/eww/scripts/bspwm_state.py", 0o755),
        (("dotfiles", "x11", "eww", "scripts", "audio_state.sh"), "~/.config/eww/scripts/audio_state.sh", 0o755),
        (("dotfiles", "x11", "eww", "scripts", "toggle_window.sh"), "~/.config/eww/scripts/toggle_window.sh", 0o755),
        (("daemons", "scripts", "eww", "submenu_watch.py"), "~/.config/eww/scripts/submenu_watch.py", 0o755),
        (("dotfiles", "quickshell", "launch.sh"), "~/.config/quickshell/launch.sh", 0o755),
        (("dotfiles", "quickshell", "launch-wayland.sh"), "~/.config/quickshell/launch-wayland.sh", 0o755),
        (("daemons", "scripts", "quickshell", "submenu_watch.py"), "~/.config/quickshell/scripts/submenu_watch.py", 0o755),
        (("daemons", "scripts", "quickshell", "sys_diag.py"), "~/.config/quickshell/scripts/sys_diag.py", 0o755),
        (("daemons", "scripts", "quickshell", "wl_workspaces.py"), "~/.config/quickshell/scripts/wl_workspaces.py", 0o755),
        (("daemons", "scripts", "quickshell", "android_status.py"), "~/.config/quickshell/scripts/android_status.py", 0o755),
        (("daemons", "scripts", "quickshell", "media_control.py"), "~/.config/quickshell/scripts/media_control.py", 0o755),
        (("daemons", "scripts", "quickshell", "weather.py"), "~/.config/quickshell/scripts/weather.py", 0o755),
        (("dotfiles", "wayland", "sway", "config"), "~/.config/sway/config", 0o644),
        (("dotfiles", "wayland", "labwc", "rc.xml"), "~/.config/labwc/rc.xml", 0o644),
        (("dotfiles", "wayland", "labwc", "themerc"), "~/.config/labwc/themerc", 0o644),
        (("dotfiles", "wayland", "labwc", "autostart"), "~/.config/labwc/autostart", 0o755),
        (("dotfiles", "wayland", "foot", "foot.ini"), "~/.config/foot/foot.ini", 0o644),
        (("dotfiles", "x11", "picom", "picom.conf"), "~/.config/picom/picom.conf", 0o644),
        (("dotfiles", "x11", "rofi", "config.rasi"), "~/.config/rofi/config.rasi", 0o644),
        (("dotfiles", "x11", "xfce4", "terminalrc"), "~/.config/xfce4/terminal/terminalrc", 0o644),
        (("dotfiles", "x11", "xfce4", "xfce4-terminal.xml"), "~/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-terminal.xml", 0o644),
        (("dotfiles", "x11", "start-x11.sh"), "~/start-x11.sh", 0o755),
        (("dotfiles", "wayland", "start-wayland.sh"), "~/start-wayland.sh", 0o755),
        (("dotfiles", "x11", "start-x11.sh"), os.path.join(prefix_bin, "desktop"), 0o755),
        (("dotfiles", "wayland", "start-wayland.sh"), os.path.join(prefix_bin, "desktop-wayland"), 0o755),
    ]

    _install_text(_render_quickshell("shell.qml"), "~/.config/quickshell/shell.qml", 0o644)
    _install_text(_render_quickshell("wayland.qml"), "~/.config/quickshell/wayland.qml", 0o644)
    for src_parts, dest_raw, mode in assets:
        _install_asset(src_parts, dest_raw, mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
