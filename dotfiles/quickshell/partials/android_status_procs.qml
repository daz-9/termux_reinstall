    Process {
        id: androidStatusProc
        command: ["python3", Quickshell.env("HOME") + "/.config/quickshell/scripts/android_status.py"]
        running: false
        onRunningChanged: {
            if (!running) root.androidProbing = false;
        }
        stdout: StdioCollector {
            onStreamFinished: {
                root.androidProbing = false;
                try {
                    const d = JSON.parse((this.text || "").trim() || "{}");
                    if (d.api_ok !== undefined) root.termuxApiOk = Boolean(d.api_ok);
                    if (d.api_state !== undefined) root.termuxApiState = String(d.api_state);
                    if (d.api_ver !== undefined) root.termuxApiVer = String(d.api_ver);
                    if (d.api_detail !== undefined) root.termuxApiDetail = String(d.api_detail);
                    if (d.shizuku_ok !== undefined) root.shizukuOk = Boolean(d.shizuku_ok);
                    if (d.shizuku_state !== undefined) root.shizukuState = String(d.shizuku_state);
                    if (d.shizuku_ver !== undefined) root.shizukuVer = String(d.shizuku_ver);
                    if (d.shizuku_detail !== undefined) root.shizukuDetail = String(d.shizuku_detail);
                } catch (e) {}
            }
        }
    }

    Timer {
        interval: 1200
        running: true
        repeat: false
        onTriggered: root.refreshAndroidStatus()
    }

    Timer {
        interval: 15000
        running: root.widgetsOpen
        repeat: true
        onTriggered: root.refreshAndroidStatus()
    }

    Timer {
        id: androidDelayTimer
        interval: 700
        repeat: false
        onTriggered: root.refreshAndroidStatus()
    }
