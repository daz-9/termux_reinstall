import subprocess
import os
import shutil


def main() -> int:
    configure_zsh()
    configure_vim()
    move_files()


    return 0



def configure_zsh():
    subprocess.run("sh -c \"$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)\"", shell=True)
    return

def configure_vim():

    for p in ["~/.config/nvim", "~/.local/share/nvim", "~/.local/state/nvim", "~/.cache/nvim"]:
        p = os.path.expanduser(p)
        if os.path.exists(p):
            shutil.move(p, p + ".bak") #backup config
    subprocess.run("git clone https://github.com/LazyVim/starter ~/.config/nvim", shell=True) #nvim config

def configure_ui_packages():
    #todo
    return

def move_files():
    subprocess.run("mv start-desktop.sh ~/start-desktop.sh", shell=True)

if __name__ == "__main__":
    main()