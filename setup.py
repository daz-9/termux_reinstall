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
        "fastfetch", "zip", "git", "zsh", "starship", "eza", "yazi", "zoxide", "bat", "tmux", "man", "manpages", "termux-api",
        # C toolchain
        "clang", "lldb", "gdb", "make", "bear",
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


XMAKE_PLUGINS = {
    "br": """task("br")
    set_category("plugin")
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        config.load()
        local cur_policies = config.get("policies") or ""
        if cur_policies:find("sanitizer") then
            os.exec("xmake f -q --policies=")
        end
        os.exec("xmake build")
        local args = {"run"}
        for _, a in ipairs(option.get("arguments") or {}) do
            table.insert(args, a)
        end
        os.execv("xmake", args)
    end)
    set_menu {
        usage = "xmake br [arguments...]",
        description = "Build and run the target in one step (like cargo run).",
        options = {
            {nil, "arguments", "vs", nil, "Arguments passed to the target binary."}
        }
    }
""",
    "san": """task("san")
    set_category("plugin")
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        config.load()
        local cur_policies = config.get("policies") or ""
        if config.get("mode") ~= "debug" or not cur_policies:find("sanitizer%.address") then
            os.exec("xmake f -q -m debug --policies=build.sanitizer.address,build.sanitizer.undefined")
        end
        os.exec("xmake build")
        local args = {"run"}
        for _, a in ipairs(option.get("arguments") or {}) do
            table.insert(args, a)
        end
        os.execv("xmake", args)
    end)
    set_menu {
        usage = "xmake san [arguments...]",
        description = "Build and run with AddressSanitizer + UndefinedBehaviorSanitizer.",
        options = {
            {nil, "arguments", "vs", nil, "Arguments passed to the target binary."}
        }
    }
""",
    "dbg": """task("dbg")
    set_category("plugin")
    on_run(function ()
        import("core.base.option")
        import("core.project.config")
        config.load()
        if config.get("mode") ~= "debug" or (config.get("policies") and config.get("policies") ~= "") then
            os.exec("xmake f -q -m debug --policies=")
        end
        os.exec("xmake build")
        local args = {"run", "-d"}
        for _, a in ipairs(option.get("arguments") or {}) do
            table.insert(args, a)
        end
        os.execv("xmake", args)
    end)
    set_menu {
        usage = "xmake dbg [arguments...]",
        description = "Build in debug mode and launch interactive debugger (lldb).",
        options = {
            {nil, "arguments", "vs", nil, "Arguments passed to the target binary."}
        }
    }
""",
}


def install_xmake():
    if shutil.which("xmake"):
        print("[+] xmake already installed, skipping")
    else:
        print("[*] xmake not found, installing...")
        run("pkg install xmake -y", "installing xmake")

    # Patch xmake's default C/C++ console templates so `xmake create` auto-updates compile_commands.json & enables warnings
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    rule = 'add_rules("plugin.compile_commands.autoupdate", {outputdir = "."})\nset_warnings("all", "extra")'
    for lang in ("c", "c++"):
        tpl = os.path.join(prefix, f"share/xmake/templates/{lang}/console/xmake.lua")
        if os.path.exists(tpl):
            try:
                text = open(tpl).read()
                if "plugin.compile_commands.autoupdate" not in text:
                    text = text.replace(
                        'add_rules("mode.debug", "mode.release")',
                        f'add_rules("mode.debug", "mode.release")\n{rule}',
                        1,
                    )
                    with open(tpl, "w") as f:
                        f.write(text)
                    print(f"[+] patched xmake {lang} template (compile_commands + warnings)")
            except OSError as e:
                print(f"[-] patching xmake {lang} template failed: {e}")

    # Install custom xmake plugins (xmake br, xmake san, xmake dbg)
    plugins_root = os.path.expanduser("~/.xmake/plugins")
    for name, code in XMAKE_PLUGINS.items():
        try:
            pdir = os.path.join(plugins_root, name)
            os.makedirs(pdir, exist_ok=True)
            with open(os.path.join(pdir, "xmake.lua"), "w") as f:
                f.write(code)
            print(f"[+] installed xmake plugin: xmake {name}")
        except OSError as e:
            print(f"[-] installing xmake plugin {name} failed: {e}")
            failures.append(f"installing xmake {name} plugin")


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
