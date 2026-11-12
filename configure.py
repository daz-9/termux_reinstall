import subprocess
import os
import shutil
import sys


def main() -> int:
    # Flags for non-interactive use
    args = sys.argv[1:]
    if args:
        return dispatch(tuple(arg.lstrip("-") for arg in args))

    from simple_term_menu import TerminalMenu

    terminal_menu = TerminalMenu(
        ["Zsh", "Neovim", "Font"],
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
    return dispatch(terminal_menu.chosen_menu_entries)

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
    }

    rc = 0
    for choice in choices:
        handler = handlers.get(choice.lower())
        if handler is None:
            print(f"[!] Invalid choice: {choice!r}")
            rc = 1
            continue
        result = handler()
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
        result = handler()
        if result != 0:
            rc = result
    return rc


def configure_zsh():
    subprocess.run("sh -c \"$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)\" \"\" --unattended", shell=True, check=True)
    return 0

def configure_font():
    subprocess.run("mkdir -p ~/.termux/", shell=True, check=True)
    subprocess.run("curl -fsSL https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/patched-fonts/JetBrainsMono/Ligatures/JetBrainsMonoNerdFont-Regular.ttf -o ~/.termux/font.ttf", shell=True, check=True)
    subprocess.run("termux-reload-settings", shell=True)
    return 0

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

def configure_vim_lazyvim():
    _backup_nvim_dirs()
    subprocess.run("git clone https://github.com/LazyVim/starter ~/.config/nvim", shell=True, check=True) #nvim config
    subprocess.run("rm -rf ~/.config/nvim/.git", shell=True) #remove git history
    return 0

def configure_vim_astrovim():
    _backup_nvim_dirs()
    subprocess.run("git clone --depth 1 https://github.com/AstroNvim/template ~/.config/nvim", shell=True, check=True) #nvim config
    subprocess.run("rm -rf ~/.config/nvim/.git", shell=True) #remove git history
    return 0


if __name__ == "__main__":
    raise SystemExit(main())