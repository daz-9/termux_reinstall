from time import sleep
import subprocess
import shutil
import os


def main() -> int:

    initialize_pkg()



    subprocess.run("pip install rich colorama==0.4.6", shell=True)
    

    try:

        welcome_message()

    except ImportError: #this hopefully works in case colorama can't be installed
        print("[!] colorama could not be installed, skipping banner")    
    install_font()
    install_required_apps()
    install_ui_packages()
    configure_ui_packages()
    configure_other_packages()
    clean_up()
    
    return 0


def welcome_message():
    from colorama import Fore, Back, Style, init

    try :
        subprocess.run("jp2a https://assets.stickpng.com/images/613098fd48f1e30004910189.png  --color ", shell=True)
    except subprocess.CalledProcessError:
        pass
    print(Style.BRIGHT + Fore.BLUE + "[+] Created by: meow \n")
    sleep(4)
    print(Style.BRIGHT + Fore.BLUE + "\n[+] Installed")
    sleep(3)

def initialize_pkg():
    res = subprocess.run(["pkg", "update", "-y"], capture_output=True)
    if res.returncode != 0:
        print(res.stderr.decode())
    res = subprocess.run(["pkg", "upgrade", "-y"], capture_output=True)
    if res.returncode != 0:
        print(res.stderr.decode())

    res = subprocess.run(["pkg", "upgrade", "-y"], capture_output=True)
    if res.returncode != 0:
        print(res.stderr.decode())
    res = subprocess.run(["apt", "upgrade", "-y"], capture_output=True)
    if res.returncode != 0:
        print(res.stderr.decode())
    

    try:
        subprocess.run(["pkg install curl wget jp2a -y"], shell=True, check=True)
    except subprocess.CalledProcessError:
            print("failure in installing installation apps")

    return

def install_required_apps():
    subprocess.run("pkg install x11-repo -y", shell=True)
    subprocess.run("pkg install tur-repo -y", shell=True)


    try:
        subprocess.run(["apt install neofetch zip git zsh neovim clang make lua luarocks -y"], check=True, shell=True)
    except subprocess.CalledProcessError:
        print("failure in installing required apps")
        
        
    return


def install_font():
    subprocess.run("mkdir -p ~/.termux/", shell=True)
    subprocess.run("curl -fsSL https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/patched-fonts/JetBrainsMono/Ligatures/Regular/JetBrainsMonoNerdFont-Regular.ttf -o ~/.termux/font.ttf", shell=True)
    #the font will be loaded at the end
    return



def install_ui_packages():
    try:
        subprocess.run(["pkg install polybar i3 picom -y"], shell=True, check=True)
    except subprocess.CalledProcessError:
        print("failure in installing UI packages")

    return


def configure_ui_packages():
    #todo
    return

def configure_other_packages():
    for p in ["~/.config/nvim", "~/.local/share/nvim", "~/.local/state/nvim", "~/.cache/nvim"]:
        p = os.path.expanduser(p)
        if os.path.exists(p):
            shutil.move(p, p + ".bak") #backup config
    subprocess.run("git clone https://github.com/LazyVim/starter ~/.config/nvim", shell=True) #nvim config


def clean_up():
    subprocess.run("chsh -s zsh", shell=True) #taken from the official zsh page on termux docs
    subprocess.run("termux-reload-settings", shell=True)









if __name__ == "__main__":
    raise SystemExit(main())
