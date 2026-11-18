    Process {
        id: weatherProc
        command: ["python3", Quickshell.env("HOME") + "/.config/quickshell/scripts/weather.py"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const d = JSON.parse((this.text || "").trim() || "{}");
                    if (d.temp !== undefined) root.weatherTemp = String(d.temp);
                    if (d.detail !== undefined) root.weatherDetail = String(d.detail);
                    if (d.location !== undefined) root.weatherLocation = String(d.location);
                    if (d.icon !== undefined) root.weatherIcon = String(d.icon);
                    if (d.tone !== undefined) root.weatherTone = String(d.tone);
                    if (d.ok) root.lastWeatherMs = Date.now();
                } catch (e) {}
            }
        }
    }

    Timer {
        interval: 1400
        running: true
        repeat: false
        onTriggered: root.refreshWeather()
    }

    Timer {
        interval: 900000
        running: true
        repeat: true
        onTriggered: root.refreshWeather()
    }
