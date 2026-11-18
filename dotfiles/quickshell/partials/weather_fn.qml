    function weatherColor(tone) {
        if (tone === "blue") return root.colBlue;
        if (tone === "teal") return root.colTeal;
        if (tone === "mauve") return root.colMauve;
        if (tone === "red") return root.colRed;
        if (tone === "text") return root.colText;
        if (tone === "subtext") return root.colSubtext;
        return root.colPeach;
    }

    function refreshWeather() {
        if (!weatherProc.running) {
            weatherProc.running = true;
        }
    }

    function refreshWeatherIfStale() {
        const now = Date.now();
        if (root.lastWeatherMs === 0 || (now - root.lastWeatherMs) > 300000) {
            root.refreshWeather();
        }
    }
