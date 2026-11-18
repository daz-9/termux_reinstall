    Process {
        id: mediaStreamProc
        command: [Quickshell.env("HOME") + "/.local/bin/qs-native", "media-stream"]
        running: true
        stdinEnabled: true
        stdout: SplitParser {
            onRead: line => {
                try {
                    const d = JSON.parse((line || "").trim() || "{}");
                    if (d.available !== undefined) root.mediaAvailable = Boolean(d.available);
                    if (d.playing !== undefined) root.mediaPlaying = Boolean(d.playing);
                    if (d.state !== undefined) root.mediaState = String(d.state);
                    if (d.package !== undefined) root.mediaPackage = String(d.package);
                    if (d.app !== undefined) root.mediaApp = String(d.app);
                    if (d.tag !== undefined) root.mediaTag = String(d.tag);
                    if (d.title !== undefined) root.mediaTitle = String(d.title);
                    if (d.artist !== undefined) root.mediaArtist = String(d.artist);
                    if (d.album !== undefined) root.mediaAlbum = String(d.album);
                    if (d.pos_sec !== undefined) root.mediaPosSec = Number(d.pos_sec) || 0;
                    if (d.pos_text !== undefined) root.mediaPosText = String(d.pos_text);
                } catch (e) {}
            }
        }
    }

    Timer {
        interval: 5000
        running: root.widgetsOpen
        repeat: true
        onTriggered: root.refreshMedia()
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
