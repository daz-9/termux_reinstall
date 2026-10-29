#!/usr/bin/env python3
"""Entry point: pick what to run. No imports from setup/configure."""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable  # the same python running this file



def run_script(name: str) -> int:
    """Run a sibling script by filename. Returns its exit code."""
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        print(f"[!] {name} not found next to main.py")
        return 1
    print(f"[*] Running {name} ...")
    return subprocess.run([PY, path]).returncode


def dispatch(choices: tuple[str, ...]) -> int:


    handlers = {
        "Setup":     lambda: run_script("setup.py"),
        "Configure": lambda: run_script("configure.py"),
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


def main() -> int:
    subprocess.run("python -m pip install simple-term-menu==1.6.6", shell=True, check=True)

    # Flags for non-interactive use
    args = sys.argv[1:]
    if args:
        return dispatch((args[0].lstrip("-"),))


    from simple_term_menu import TerminalMenu

    terminal_menu = TerminalMenu(
        ["Setup", "Configure"],
        multi_select=True,
        show_multi_select_hint=True,
        title="Select what to install (use space to select, enter to confirm):"
    )
    menu_entry_indices = terminal_menu.show()
    #print(menu_entry_indices)
    #print(terminal_menu.chosen_menu_entries)
    

    # If no menu entry was selected, exit with code 1
    if not menu_entry_indices:
        print("[!] No menu entry selected. Exiting.")
        return 1
    return dispatch(terminal_menu.chosen_menu_entries)


if __name__ == "__main__":
    raise SystemExit(main())