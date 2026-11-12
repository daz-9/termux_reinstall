from time import sleep
import subprocess
import shutil
import os


# everything that failed gets collected here and printed at the end
failures: list[str] = []


def run(cmd, desc: str) -> bool:
    """Run a command, report failure to the user and keep going. Returns True on success."""
    try:
        subprocess.run(cmd, shell=isinstance(cmd, str), check=True)
        return True
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"[-] {desc} failed: {e}")
        failures.append(desc)
        return False


def main() -> int:

    initialize_pkg()



    run("python -m pip install rich colorama==0.4.6", "pip install rich/colorama")
    

    try:

        welcome_message()

    except ImportError: #this hopefully works in case colorama can't be installed
        print("[!] colorama could not be installed, skipping banner")   

    install_required_apps()
    install_xmake()

    clean_up()

    print_summary()
    return 1 if failures else 0



def welcome_message():
    from colorama import Fore, Back, Style, init

    try :
        subprocess.run("jp2a https://assets.stickpng.com/images/613098fd48f1e30004910189.png  --color ", shell=True)
    except subprocess.CalledProcessError:
        pass
    print(Style.BRIGHT + Fore.BLUE + "[+] Created by: meow \n")
    sleep(2)
    print(Style.BRIGHT + Fore.BLUE + "\n[+] Installed")
    sleep(2)

def initialize_pkg():
    run(["pkg", "update", "-y"], "pkg update")
    run(["pkg", "upgrade", "-y"], "pkg upgrade")

    run("pkg install curl wget jp2a -y", "installing installation apps (curl, wget, jp2a)")

    return

def install_required_apps():
    run("pkg install tur-repo -y", "installing tur-repo")

    apps_to_be_installed = [
        # base / shell
        "neofetch", "zip", "git", "zsh", "eza", "yazi", "tmux", "man",
        # C toolchain
        "clang", "make", "gdb", "valgrind",
        # neovim + what LazyVim needs for search/pickers
        "neovim", "lua55", "luarocks", "ripgrep", "fd", "fzf", "lazygit",
        # github
        "git", "openssh", "gh",
    ]
    apps_to_be_installed = list(dict.fromkeys(apps_to_be_installed))  # dedupe, keep order
    apps_to_be_installed_str = " ".join(apps_to_be_installed)
    try:
        subprocess.run("apt install " + apps_to_be_installed_str + " -y", check=True, shell=True)
        return
    except subprocess.CalledProcessError:
        print("[-] apt install failed, falling back to installing one by one with pkg...")

    # one bad package makes the bulk install fail, so install individually and report which ones failed
    for app in apps_to_be_installed:
        run(f"pkg install {app} -y", f"installing {app}") #pkg takes way too long to install, so we use apt first

    return


def install_xmake():
    if shutil.which("xmake"):
        print("[+] xmake already installed, skipping")
        return
    print("[*] xmake not found, installing...")
    run("pkg install xmake -y", "installing xmake")


def clean_up():
    run("termux-reload-settings", "termux-reload-settings")
    # only switch shell if zsh actually got installed, otherwise the user gets locked into a missing shell
    if shutil.which("zsh"):
        run("chsh -s zsh", "setting zsh as default shell") #taken from the official zsh page on termux docs
    else:
        print("[-] zsh is not installed, not changing the default shell")
        failures.append("zsh missing, default shell not changed")


def print_summary():
    if not failures:
        print("\n[+] Setup finished with no errors")
        return
    print(f"\n[!] Setup finished with {len(failures)} problem(s):")
    for f in failures:
        print(f"    - {f}")











if __name__ == "__main__":
    raise SystemExit(main())
