import subprocess
import os
import shutil


def main() -> int:





    from simple_term_menu import TerminalMenu

    terminal_menu = TerminalMenu(
        ["Zsh", "Neovim", "start-desktop.sh"],
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
        show_multi_select_hint=True,
        title="Select Neovim config (use space to select, enter to confirm):"
    )
    menu_entry_indices = neovim_config_menu.show()
    if not menu_entry_indices:
        print("[!] No menu entry selected. Exiting.")
        return 1
    return dispatch_neovim_config(neovim_config_menu.chosen_menu_entries)


def dispatch(choices: tuple[str, ...]) -> int:


    handlers = {
        "Zsh":     lambda: configure_zsh(),
        "Neovim": lambda: neovim_config(),
        "start-desktop.sh": lambda: move_files(),
    }

    rc = 0
    for choice in choices:
        handler = handlers.get(choice)
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
        "LazyVim": lambda: configure_vim_lazyvim(),
        "AstroNvim": lambda: configure_vim_astrovim(),
    }

    rc = 0
    for choice in choices:
        handler = handlers.get(choice)
        if handler is None:
            print(f"[!] Invalid choice: {choice!r}")
            rc = 1
            continue
        result = handler()
        if result != 0:
            rc = result
    return rc


def configure_zsh():
    subprocess.run("sh -c \"$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)\"", shell=True, check=True)
    return 0

def configure_vim_lazyvim():

    for p in ["~/.config/nvim", "~/.local/share/nvim", "~/.local/state/nvim", "~/.cache/nvim"]:
        p = os.path.expanduser(p)
        if os.path.exists(p):
            shutil.move(p, p + ".bak") #backup config
    subprocess.run("git clone https://github.com/LazyVim/starter ~/.config/nvim", shell=True) #nvim config

def configure_vim_astrovim():
    for p in ["~/.config/nvim", "~/.local/share/nvim", "~/.local/state/nvim", "~/.cache/nvim"]:
        p = os.path.expanduser(p)
        if os.path.exists(p):
            shutil.move(p, p + ".bak") #backup config
    subprocess.run("git clone --depth 1 https://github.com/AstroNvim/template ~/.config/nvim", shell=True) #nvim config
    subprocess.run("rm -rf ~/.config/nvim/.git", shell=True) #remove git history



def move_files():
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "start-desktop.sh")
    dst = os.path.expanduser("~/start-desktop.sh")
    if not os.path.exists(src):
        print("[-] start-desktop.sh not found")
        return
    shutil.copy(src, dst)          # copy the file to home directory
    os.chmod(dst, 0o755)           # ensure executable

if __name__ == "__main__":
    main()