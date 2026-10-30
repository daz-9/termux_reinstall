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

    from simple_term_menu import TerminalMenu #downloaded in main, so it should be available now

    terminal_menu = TerminalMenu(
        ["y", "n"],
        title="Install UI packages?"
    )
    menu_entry_indices = terminal_menu.show()


    install_font()
    install_required_apps()
    try:
        if "y" in terminal_menu.chosen_menu_entries:
            install_ui_packages()
    except TypeError as e:
        print(f"[!] An error occurred: {e}")

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
    res = subprocess.run(["pkg", "update", "-y"], capture_output=True, check=True)
    res = subprocess.run(["pkg", "upgrade", "-y"], capture_output=True, check=True)

    try:
        subprocess.run("pkg install curl wget jp2a -y", shell=True, check=True)
    except subprocess.CalledProcessError:
            print("failure in installing installation apps")

    return

def install_required_apps():
    try:
        subprocess.run("pkg install x11-repo -y", shell=True, check=True)
    except subprocess.CalledProcessError:
        print("[-] Failed to install x11-repo")
    
    try:
        subprocess.run("pkg install tur-repo -y", shell=True, check=True)
    except subprocess.CalledProcessError:
        print("[-] Failed to install tur-repo")

    apps_to_be_installed = ["neofetch", "zip", "git", "zsh", "neovim", "clang", "make", "lua55", "luarocks"] #todo: change the lazyvim/astronvim to prevent mason from installing clangd since its downloaded with clang, and mason breaks clangd installation in termux
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


def install_font():
    subprocess.run("mkdir -p ~/.termux/", shell=True)
    subprocess.run("curl -fsSL https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/patched-fonts/JetBrainsMono/Ligatures/Regular/JetBrainsMonoNerdFont-Regular.ttf -o ~/.termux/font.ttf", shell=True)
    #the font will be loaded at the end
    return



def install_ui_packages():

    apps_to_be_installed = ["polybar", "i3", "picom", "alacritty"] #todo: maybe remove?
    apps_to_be_installed_str = " ".join(apps_to_be_installed)
    try:
        subprocess.run("apt install " + apps_to_be_installed_str + " -y", shell=True, check=True)
    
    except subprocess.CalledProcessError:
        print("[-] apt install failed, falling back to pkg...")
        try: 
            subprocess.run("pkg install " + apps_to_be_installed_str + " -y", shell=True, check=True)
        except subprocess.CalledProcessError:
            print("[-] UI packages installation failed, please check your internet connection and try again.")
            

    return



def clean_up():
    subprocess.run("termux-reload-settings", shell=True)
    subprocess.run("chsh -s zsh", shell=True) #taken from the official zsh page on termux docs










if __name__ == "__main__":
    raise SystemExit(main())
