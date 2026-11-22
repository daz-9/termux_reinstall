#!/usr/bin/env python3
"""Install Termux packages, toolchains, xmake plugins, and native LSP servers."""

import os
import shutil
import subprocess
import sys
from time import sleep

# Everything that failed gets collected here and printed at the end
failures: list[str] = []


# --- Helpers -----------------------------------------------------------------

def run(cmd, desc: str) -> bool:
    """Run a command, report failure to the user and keep going. Returns True on success."""
    try:
        subprocess.run(cmd, shell=isinstance(cmd, str), check=True)
        return True
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"[-] {desc} failed: {e}")
        failures.append(desc)
        return False


def print_summary():
    """Print a final report of any steps that failed during setup."""
    if not failures:
        print("\n[+] Setup finished with no errors")
        return
    print(f"\n[!] Setup finished with {len(failures)} problem(s):")
    for f in failures:
        print(f"    - {f}")


# --- Package Installation ----------------------------------------------------

def welcome_message():
    """Display the startup ASCII banner."""
    from colorama import Fore, Style

    try:
        subprocess.run("jp2a https://assets.stickpng.com/images/613098fd48f1e30004910189.png --color", shell=True)
    except subprocess.CalledProcessError:
        pass
    print(Style.BRIGHT + Fore.BLUE + "[+] Created by: meow \n")
    sleep(2)
    print(Style.BRIGHT + Fore.BLUE + "\n[+] Installed")
    sleep(2)


def initialize_pkg():
    """Update Termux package lists and install bootstrap utilities."""
    run(["pkg", "update", "-y"], "pkg update")
    run(["pkg", "upgrade", "-y"], "pkg upgrade")
    run("pkg install curl wget jp2a ncurses-utils -y", "installing installation apps (curl, wget, jp2a, ncurses-utils)")


def _install_packages(packages: list[str]):
    """Bulk-install apt packages, falling back to per-package pkg installs on failure."""
    packages = list(dict.fromkeys(packages))  # dedupe, keep order
    packages_str = " ".join(packages)

    # pkg takes much longer than apt for bulk installs, so try apt first
    try:
        subprocess.run("apt install " + packages_str + " -y", check=True, shell=True)
        return
    except subprocess.CalledProcessError:
        print("[-] apt install failed, falling back to installing one by one with pkg...")

    # One bad package makes bulk install fail; install individually to isolate failures
    for pkg in packages:
        run(f"pkg install {pkg} -y", f"installing {pkg}")


def install_required_apps():
    """Install core CLI, C/C++ toolchain, Neovim, and GitHub packages."""
    run("pkg install tur-repo -y", "installing tur-repo")

    _install_packages([
        # Base / shell
        "fastfetch", "zip", "git", "zsh", "starship", "eza", "yazi", "zoxide",
        "bat", "glow", "tmux", "man", "manpages", "termux-api", "rish-shizuku",
        # C/C++ & Rust toolchains
        "clang", "lldb", "gdb", "make", "bear", "rust",
        # Neovim + pickers + native LSP runtimes
        "neovim", "lua55", "luarocks", "lua-language-server", "tree-sitter",
        "dotnet-sdk-9.0", "nodejs", "ruff", "ripgrep", "fd", "fzf", "lazygit",
        # GitHub / Git
        "git-delta", "openssh", "gh",
    ])


def install_x11() -> int:
    """Enable x11-repo/tur-repo and install Termux X11, quickshell, bspwm, polybar, rofi, and sxhkd."""
    run("pkg install x11-repo tur-repo -y", "installing x11-repo and tur-repo")
    run(["pkg", "update", "-y"], "pkg update")
    run(["pkg", "upgrade", "-y"], "pkg upgrade")
    _install_packages([
        "clang",
        "libx11",
        "libxi",
        "libxfixes",
        "dbus",
        "pulseaudio",
        "termux-api",
        "rish-shizuku",
        "termux-x11-nightly",
        "quickshell",
        "bspwm",
        "polybar",
        "rofi",
        "sxhkd",
        "fastcompmgr",
        "sway",
        "swaybg",
        "labwc",
        "foot",
        "feh",
        "xfce4-terminal",
        "alacritty",
        "virglrenderer-android",
        "xorg-xcursorgen",
        "xorg-xsetroot",
    ])
    return 0


# --- Xmake & LSP Tooling -----------------------------------------------------

XMAKE_PLUGINS = {
    "br": """task("br")
    set_category("plugin")
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        config.load()
        local cur_policies = config.get("policies") or ""
        if cur_policies:find("sanitizer") then
            os.exec("xmake f -q --policies=")
        end
        os.exec("xmake build")
        local args = {"run"}
        for _, a in ipairs(option.get("arguments") or {}) do
            table.insert(args, a)
        end
        os.execv("xmake", args)
    end)
    set_menu {
        usage = "xmake br [arguments...]",
        description = "Build and run the target in one step (like cargo run).",
        options = {
            {nil, "arguments", "vs", nil, "Arguments passed to the target binary."}
        }
    }
""",
    "san": """task("san")
    set_category("plugin")
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        config.load()
        local cur_policies = config.get("policies") or ""
        if config.get("mode") ~= "debug" or not cur_policies:find("sanitizer%.address") then
            os.exec("xmake f -q -m debug --policies=build.sanitizer.address,build.sanitizer.undefined")
        end
        os.exec("xmake build")
        local args = {"run"}
        for _, a in ipairs(option.get("arguments") or {}) do
            table.insert(args, a)
        end
        os.execv("xmake", args)
    end)
    set_menu {
        usage = "xmake san [arguments...]",
        description = "Build and run with AddressSanitizer + UndefinedBehaviorSanitizer.",
        options = {
            {nil, "arguments", "vs", nil, "Arguments passed to the target binary."}
        }
    }
""",
    "dbg": """task("dbg")
    set_category("plugin")
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        config.load()
        if config.get("mode") ~= "debug" or (config.get("policies") and config.get("policies") ~= "") then
            os.exec("xmake f -q -m debug --policies=")
        end
        os.exec("xmake build")
        local args = {"run", "-d"}
        for _, a in ipairs(option.get("arguments") or {}) do
            table.insert(args, a)
        end
        os.execv("xmake", args)
    end)
    set_menu {
        usage = "xmake dbg [arguments...]",
        description = "Build in debug mode and launch interactive debugger (lldb).",
        options = {
            {nil, "arguments", "vs", nil, "Arguments passed to the target binary."}
        }
    }
""",
}


def install_xmake():
    """Install xmake, patch C/C++ console templates, and install custom plugins."""
    if shutil.which("xmake"):
        print("[+] xmake already installed, skipping")
    else:
        print("[*] xmake not found, installing...")
        run("pkg install xmake -y", "installing xmake")

    # Patch xmake's default C/C++ console templates so `xmake create` auto-updates compile_commands.json & enables warnings
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    rule = 'add_rules("plugin.compile_commands.autoupdate", {outputdir = "."})\nset_warnings("all", "extra")'
    for lang in ("c", "c++"):
        tpl = os.path.join(prefix, f"share/xmake/templates/{lang}/console/xmake.lua")
        if os.path.exists(tpl):
            try:
                text = open(tpl).read()
                if "plugin.compile_commands.autoupdate" not in text:
                    text = text.replace(
                        'add_rules("mode.debug", "mode.release")',
                        f'add_rules("mode.debug", "mode.release")\n{rule}',
                        1,
                    )
                    with open(tpl, "w") as f:
                        f.write(text)
                    print(f"[+] patched xmake {lang} template (compile_commands + warnings)")
            except OSError as e:
                print(f"[-] patching xmake {lang} template failed: {e}")

    # Install custom xmake plugins (xmake br, xmake san, xmake dbg)
    plugins_root = os.path.expanduser("~/.xmake/plugins")
    for name, code in XMAKE_PLUGINS.items():
        try:
            pdir = os.path.join(plugins_root, name)
            os.makedirs(pdir, exist_ok=True)
            with open(os.path.join(pdir, "xmake.lua"), "w") as f:
                f.write(code)
            print(f"[+] installed xmake plugin: xmake {name}")
        except OSError as e:
            print(f"[-] installing xmake plugin {name} failed: {e}")
            failures.append(f"installing xmake {name} plugin")


def install_csharp_ls():
    """Install csharp-ls 0.16.0 as a .NET global tool (compatible with Termux .NET 9)."""
    tool_bin = os.path.expanduser("~/.dotnet/tools/csharp-ls")
    if shutil.which("csharp-ls") or os.path.exists(tool_bin):
        print("[+] csharp-ls already installed, skipping")
        return
    if not shutil.which("dotnet"):
        print("[-] dotnet not found, skipping csharp-ls install")
        failures.append("csharp-ls skipped: dotnet not installed")
        return
    print("[*] csharp-ls not found, installing via dotnet tool...")
    run("dotnet tool install --global csharp-ls --version 0.16.0", "installing csharp-ls")


def install_basedpyright():
    """Install basedpyright globally via npm for Python type checking in Neovim."""
    if shutil.which("basedpyright-langserver"):
        print("[+] basedpyright already installed, skipping")
        return
    if not shutil.which("npm"):
        print("[-] npm not found, skipping basedpyright install")
        failures.append("basedpyright skipped: npm not installed")
        return
    print("[*] basedpyright not found, installing via npm...")
    run("npm install -g basedpyright", "installing basedpyright")


def install_conan():
    """Install Conan C/C++ package manager via pip."""
    if shutil.which("conan"):
        print("[+] conan already installed, skipping")
        return
    print("[*] conan not found, installing via pip...")
    run("python -m pip install conan", "installing conan")


def clean_up():
    """Reload Termux settings and set zsh as the default login shell."""
    run("termux-reload-settings", "termux-reload-settings")
    # Only switch shell if zsh actually got installed, otherwise the user gets locked into a missing shell
    if shutil.which("zsh"):
        run("chsh -s zsh", "setting zsh as default shell")  # from official Termux zsh docs
    else:
        print("[-] zsh is not installed, not changing the default shell")
        failures.append("zsh missing, default shell not changed")


# --- Entry Point -------------------------------------------------------------

def setup_core() -> int:
    """Run core Termux package, toolchain, xmake, and LSP setup."""
    initialize_pkg()
    run("python -m pip install rich colorama==0.4.6", "pip install rich/colorama")

    try:
        welcome_message()
    except ImportError:  # in case colorama could not be installed
        print("[!] colorama could not be installed, skipping banner")

    install_required_apps()
    install_xmake()
    install_csharp_ls()
    install_basedpyright()
    install_conan()
    clean_up()
    return 0


def dispatch(choices: tuple[str, ...]) -> int:
    """Dispatch setup choices ('core', 'x11') from menu entries or CLI flags."""
    handlers = {
        "core": lambda: setup_core(),
        "x11": lambda: install_x11(),
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


def main() -> int:
    """Parse CLI flags or show the interactive setup menu."""
    args = sys.argv[1:]
    if args:
        rc = dispatch(tuple(arg.lstrip("-") for arg in args))
        print_summary()
        return 1 if (failures or rc != 0) else 0

    if not shutil.which("tput"):
        run("pkg install ncurses-utils -y", "installing ncurses-utils")

    try:
        from simple_term_menu import TerminalMenu
    except ImportError:
        run("python -m pip install simple-term-menu==1.6.6", "pip install simple-term-menu")
        try:
            from simple_term_menu import TerminalMenu
        except ImportError:
            print("[-] simple-term-menu is missing. Run with flags instead: python setup.py --core --x11")
            return 1

    terminal_menu = TerminalMenu(
        ["Core", "x11"],
        multi_select=True,
        show_multi_select_hint=True,
        title="Select what to set up (use space to select, enter to confirm):",
    )
    menu_entry_indices = terminal_menu.show()

    if not menu_entry_indices:
        print("[!] No menu entry selected. Exiting.")
        return 1
    rc = dispatch(terminal_menu.chosen_menu_entries)
    print_summary()
    return 1 if (failures or rc != 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
