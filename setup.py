from time import sleep
from os import system as sys
import subprocess
import importlib


def main() -> int:

    initialize_pkg()



    subprocess.run("pip install rich colorama==0.4.6 -y", shell=True)
    

    try:

        welcome_message()

    except ImportError: #this hopefully works in case colorama can't be installed
        print("{!} colorama could not be installed, skipping banner")
    
    install_font()
    install_required_apps()
    install_ui_packages()
    configure_ui_packages()
    clean_up()
    
    return 0


def welcome_message():
    from colorama import Fore, Back, Style, init

    subprocess.run("jp2a https://assets.stickpng.com/images/613098fd48f1e30004910189.png  --color ", shell=True)
    print(Style.BRIGHT + Fore.BLUE + "[+] Created by: meow \n")
    sleep(4)
    print(Style.BRIGHT + Fore.BLUE + "\n[+] Instaled")
    sleep(3)

def initialize_pkg():
    res = subprocess.run(["pkg", "update", "-y"], capture_output=True)
    print(res.stdout.decode())
    res = subprocess.run(["pkg", "upgrade", "-y"], capture_output=True)
    print(res.stdout.decode())

    subprocess.run(["pkg", "install", "curl", "wget", "jp2a","-y"]) #inconsistent but easier than spending more time on it


    return

def install_required_apps():
    res = subprocess.run(["pkg",
    "install",
    "x11-repo",
    "neofetch",
    "alacritty",
    "firefox",
    "zip",
    "git",
    "rofi",
    "zsh", #will be made default in the cleanup
    "neovim",
    "clang",
    "make",
    "lazygit",
    "lua",
    "luarocks"
    "-y"], capture_output=True)
    print(res.stdout.decode())
    return

def install_font():
    subprocess.run("mkdir -p ~/.termux/", shell=True)
    subprocess.run("curl -fsSL https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/patched-fonts/JetBrainsMono/Ligatures/Regular/JetBrainsMonoNerdFont-Regular.ttf -o ~/.termux/font.ttf", shell=True)
    #the font will be loaded at the end
    return

def clean_up():
    subprocess.run("termux-reload-settings", shell=True)
    subprocess.run("chsh -s zsh", shell=True)



def install_ui_packages():
    subprocess.run(["pkg",
    "install",
    "polybar",
    "i3",
    "picom",
    "-y"])
    return


def configure_ui_packages():
    #todo
    return






if __name__ == "__main__":
    raise SystemExit(main())
