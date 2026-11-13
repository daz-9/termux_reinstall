#!/usr/bin/env python3
"""Entry point: pick what to run. No imports from setup/configure."""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable  # the same python running this file



def run_script(name: str) -> int:
    """Run a sibling script by filename and return its exit code."""
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        print(f"[!] {name} not found next to main.py")
        return 1
    print(f"[*] Running {name} ...")
    return subprocess.run([PY, path]).returncode


def dispatch(choices: tuple[str, ...]) -> int:
    """Execute selected sub-scripts ('setup', 'configure') in order."""
    # Keys are lowercase so menu entries ("Setup") and flags ("--setup") both match
    handlers = {
        "setup": lambda: run_script("setup.py"),
        "configure": lambda: run_script("configure.py"),
    }

    rc = 0
    for choice in choices:
        handler = handlers.get(choice.lower())
        if handler is None:
            print(f"[!] Invalid choice: {choice!r}")
            rc = 1
            continue
        result = handler()
        if result != 0:
            rc = result
    return rc


def main() -> int:
    """Entry point: parse CLI flags or show the interactive Setup/Configure menu."""
    if subprocess.run("python -m pip install simple-term-menu==1.6.6", shell=True).returncode != 0:
        print("[-] Failed to install simple-term-menu, menus won't work (you can still use flags, e.g. --setup)")

    # Flags for non-interactive use
    args = sys.argv[1:]
    if args:
        return dispatch(tuple(arg.lstrip("-") for arg in args))

    try:
        from simple_term_menu import TerminalMenu
    except ImportError:
        print("[-] simple-term-menu is missing. Run with flags instead: python main.py --setup --configure")
        return 1

    terminal_menu = TerminalMenu(
        ["Setup", "Configure"],
        multi_select=True,
        show_multi_select_hint=True,
        title="Select what to install (use space to select, enter to confirm):",
    )
    menu_entry_indices = terminal_menu.show()

    if not menu_entry_indices:
        print("[!] No menu entry selected. Exiting.")
        return 1
    return dispatch(terminal_menu.chosen_menu_entries)


if __name__ == "__main__":
    raise SystemExit(main())