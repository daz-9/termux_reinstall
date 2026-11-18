    Process {
        id: mediaStreamProc
        command: [Quickshell.env("HOME") + "/.local/bin/qs-native", "media-stream"]
        running: true
        stdinEnabled: true
        stdout: SplitParser {
            onRead: line => {
                try {
                    const d = JSON.parse((line || "").trim() || "{}");
                    root.handleHubMessage(d);
                } catch (e) {}
            }
        }
    }

    Component.onCompleted: root.rebuildCalendarGrid()

    Timer {
        interval: 5000
        running: root.widgetsOpen
        repeat: true
        onTriggered: root.refreshMedia()
    }

    Timer {
        interval: 15000
        running: root.widgetsOpen
        repeat: true
        onTriggered: root.refreshFocus()
    }

    Timer {
        interval: 1000
        running: root.widgetsOpen && root.mediaPlaying
        repeat: true
        onTriggered: {
            root.mediaPosSec += 1;
            root.mediaPosText = root.fmtMediaSec(root.mediaPosSec);
        }
    }
