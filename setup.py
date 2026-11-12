from time import sleep
import subprocess
import shutil
import os


def main() -> int:

    initialize_pkg()



    subprocess.run("python -m pip install rich colorama==0.4.6", shell=True, check=True)
    

    try:

        welcome_message()

    except ImportError: #this hopefully works in case colorama can't be installed
        print("[!] colorama could not be installed, skipping banner")   

    install_required_apps()

    clean_up()
    
    return 0



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
    subprocess.run(["pkg", "update", "-y"], check=True)
    subprocess.run(["pkg", "upgrade", "-y"], check=True)

    try:
        subprocess.run("pkg install curl wget jp2a -y", shell=True, check=True)
    except subprocess.CalledProcessError:
            print("failure in installing installation apps")

    return

def install_required_apps():
    try:
        subprocess.run("pkg install tur-repo -y", shell=True, check=True)
    except subprocess.CalledProcessError:
        print("[-] Failed to install tur-repo")

    apps_to_be_installed = ["neofetch", "zip", "git", "zsh", "neovim", "clang", "make", "lua55", "luarocks", "yazi", "eza"] #todo: change the lazyvim/astronvim to prevent mason from installing clangd since its downloaded with clang, and mason breaks clangd installation in termux
    apps_to_be_installed_str = " ".join(apps_to_be_installed)
    try:
        subprocess.run("apt install " + apps_to_be_installed_str + " -y", check=True, shell=True)
    except subprocess.CalledProcessError:
        print("[-] apt install failed, falling back to pkg...")
        try:
            subprocess.run("pkg install " + apps_to_be_installed_str + " -y", check=True, shell=True)#pkg takes way too long to install, so we use apt first
        except subprocess.CalledProcessError:
            print("[-] required apps installation failed, please check your internet connection and try again.")
    
        
    return



def clean_up():
    subprocess.run("termux-reload-settings", shell=True)
    subprocess.run("chsh -s zsh", shell=True) #taken from the official zsh page on termux docs










if __name__ == "__main__":
    raise SystemExit(main())
