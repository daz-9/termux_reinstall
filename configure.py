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
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "start-desktop.sh")
    dst = os.path.expanduser("~/start-desktop.sh")
    if not os.path.exists(src):
        print("[-] start-desktop.sh not found")
        return
    shutil.copy(src, dst)          # copy, not move
    os.chmod(dst, 0o755)           # ensure executable

if __name__ == "__main__":
    main()