# IS NOT READY TO BE USED

## Personal quick termux config for my CS class

Will setup a basic C dev environment, UI sorely lacking, i have no idea what to put in a readme
Will set up lazyvim
The zsh config is stolen from ohmyzsh

# TODO

1. picom configuration
2. i3 configuration
3. rofi configuration
4. polybar configuration
5. alacritty setup in i3

# Warning

When nvim is enabled inside there is a big performance hit even though they are fine on their own, this might be fixed using `termux-x11-universal-sharedUid-debug.apk`, but I haven't tried it yet.

# Warning

Repeated launches of `start-desktop.sh` stack multiple polybars

# Warning

Disable the android physical keyboard shortcuts

# Warning

Alacritty font size is tiny, maybe i3 has a DPI setting?

## Troubleshooting

If install hangs at "Waiting for headers":

1. Ctrl+C
2. Run `termux-change-repo` and pick a mirror near you
3. Re-run the installer

`pkg update && pkg upgrade -y && pkg install git jp2a python-pip wget -y && git clone https://github.com/daz-9/termux_reinstall && cd termux_reinstall && python3 setup.py`
