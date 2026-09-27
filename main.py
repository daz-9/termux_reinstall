# main.py
import setup as setup_mod
import configure as configure_mod
import subprocess


MENU = """
[1] Full install  (packages + config)
[2] Setup only    (packages + font + repos)
[3] Configure only (zsh + nvim + start-desktop.sh)
[4] Quit
"""


def main() -> int:
    subprocess.run("pip install rich colorama==0.4.6", shell=True)
    from colorama import Fore, Style, init

    print(Fore.CYAN + Style.BRIGHT + MENU)

    choice = input("Choose [1-4]: ").strip()

    if choice == "1":
        setup_mod.main()
        configure_mod.main()
    elif choice == "2":
        setup_mod.main()
    elif choice == "3":
        configure_mod.main()
    elif choice == "4":
        print("Bye.")
        return 0
    else:
        print(Fore.RED + "[!] Invalid choice.")
        return 1

    print(Fore.GREEN + "[+] Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())