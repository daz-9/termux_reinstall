import Quickshell
import Quickshell.Io
import QtQuick

Scope {
    id: hub

    property bool widgetsOpen: false

    // Android / Termux:API / Shizuku state
    property bool androidProbing: false
    property bool termuxApiOk: false
    property string termuxApiState: "Checking..."
    property string termuxApiVer: ""
    property string termuxApiDetail: "Probing Termux:API..."
    property bool shizukuOk: false
    property string shizukuState: "Checking..."
    property string shizukuVer: ""
    property string shizukuDetail: "Probing Shizuku..."

    // MediaSession state
    property bool mediaAvailable: false
    property bool mediaPlaying: false
    property string mediaState: "IDLE"
    property string mediaPackage: ""
    property string mediaApp: "Media Control"
    property string mediaTag: ""
    property string mediaTitle: "Nothing Playing"
    property string mediaArtist: "Checking MediaSession..."
    property string mediaAlbum: ""
    property int mediaPosSec: 0
    property string mediaPosText: "0:00"
    property var hubWriteQueue: []

    // Weather state
    property string weatherTemp: "--°C"
    property string weatherDetail: "Loading weather..."
    property string weatherLocation: "Weather"
    property string weatherIcon: "󰖙"
    property string weatherTone: "peach"
    property real lastWeatherMs: 0

    // Focus / DND state
    property bool focusAvailable: false
    property bool focusDnd: false
    property int focusZen: 0
    property int focusNotifCount: 0
    property string focusLabel: "Checking..."

    // Calendar & Agenda state
    readonly property var calendarHeaders: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    readonly property var monthNames: [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    readonly property var monthShort: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    property int calViewYear: (new Date()).getFullYear()
    property int calViewMonth: (new Date()).getMonth()
    property string calMonthTitle: monthNames[calViewMonth] + " " + calViewYear
    property string calSelectedDateKey: ""
    property var calGridCells: []
    property string _calGridSig: ""
    property real _lastAndroidMs: 0
    property bool calendarOk: false
    property var agendaEvents: []

    Timer {
        id: openRefreshTimer
        interval: 210
        repeat: false
        onTriggered: {
            if (!hub.widgetsOpen) return;
            hub.refreshAndroidStatusIfStale();
            hub.refreshMedia();
            hub.refreshFocus();
            hub.rebuildCalendarGrid(false);
            hub.queryCalendarMonth(hub.calViewYear, hub.calViewMonth);
            hub.refreshWeatherIfStale();
        }
    }

    function onWidgetsOpened() {
        openRefreshTimer.restart();
    }

    function refreshAndroidStatusIfStale() {
        const now = Date.now();
        if (hub._lastAndroidMs === 0 || (now - hub._lastAndroidMs) > 60000) {
            hub.refreshAndroidStatus();
        }
    }

    function refreshAndroidStatus() {
        if (!androidStatusProc.running) {
            hub._lastAndroidMs = Date.now();
            hub.androidProbing = true;
            androidStatusProc.running = true;
        }
    }

    function startTermuxApi() {
        Quickshell.execDetached(["sh", "-c", "termux-api-start >/dev/null 2>&1"]);
        androidDelayTimer.restart();
    }

    function fmtMediaSec(sec) {
        const s = Math.max(0, Math.floor(sec));
        const m = Math.floor(s / 60);
        const rem = s % 60;
        return m + ":" + (rem < 10 ? "0" + rem : rem);
    }

    function sendHubCmd(line) {
        if (mediaStreamProc.running) {
            mediaStreamProc.write(line);
        } else {
            const q = (hub.hubWriteQueue || []).slice();
            q.push(line);
            hub.hubWriteQueue = q;
            mediaStreamProc.running = true;
        }
    }

    function flushHubQueue() {
        if (!mediaStreamProc.running) return;
        const q = hub.hubWriteQueue || [];
        if (q.length === 0) return;
        hub.hubWriteQueue = [];
        for (let i = 0; i < q.length; i++) {
            mediaStreamProc.write(q[i]);
        }
    }

    function refreshMedia() {
        if (!mediaStreamProc.running) {
            mediaStreamProc.running = true;
        } else {
            mediaStreamProc.write("status\n");
        }
    }

    function sendMediaAction(act) {
        const wasPlaying = hub.mediaPlaying ? "1" : "0";
        if (act === "play-pause") {
            hub.mediaPlaying = !hub.mediaPlaying;
            hub.mediaState = hub.mediaPlaying ? "PLAYING" : "PAUSED";
        }
        hub.sendHubCmd(act + "\t" + wasPlaying + "\t" + hub.mediaTag + "\n");
    }

    function refreshFocus() {
        if (!mediaStreamProc.running) {
            mediaStreamProc.running = true;
        } else {
            mediaStreamProc.write("focus-status\n");
        }
    }

    function toggleFocusDnd() {
        hub.focusDnd = !hub.focusDnd;
        hub.focusLabel = hub.focusDnd ? "Priority Only" : "Off";
        hub.sendHubCmd("focus-toggle\n");
    }

    function handleHubMessage(d) {
        const kind = d.kind || "media";
        if (kind === "media") {
            if (d.available !== undefined) hub.mediaAvailable = Boolean(d.available);
            if (d.playing !== undefined) hub.mediaPlaying = Boolean(d.playing);
            if (d.state !== undefined) hub.mediaState = String(d.state);
            if (d.package !== undefined) hub.mediaPackage = String(d.package);
            if (d.app !== undefined) hub.mediaApp = String(d.app);
            if (d.tag !== undefined) hub.mediaTag = String(d.tag);
            if (d.title !== undefined) hub.mediaTitle = String(d.title);
            if (d.artist !== undefined) hub.mediaArtist = String(d.artist);
            if (d.album !== undefined) hub.mediaAlbum = String(d.album);
            if (d.pos_sec !== undefined) hub.mediaPosSec = Number(d.pos_sec) || 0;
            if (d.pos_text !== undefined) hub.mediaPosText = String(d.pos_text);
        } else if (kind === "focus") {
            if (d.available !== undefined) hub.focusAvailable = Boolean(d.available);
            if (d.zen !== undefined) hub.focusZen = Number(d.zen) || 0;
            if (d.dnd !== undefined) hub.focusDnd = Boolean(d.dnd);
            if (d.notif_count !== undefined) hub.focusNotifCount = Number(d.notif_count) || 0;
            if (d.label !== undefined) hub.focusLabel = String(d.label);
        } else if (kind === "calendar") {
            if (d.ok !== undefined) hub.calendarOk = Boolean(d.ok);
            if (Array.isArray(d.events)) hub.agendaEvents = d.events;
            hub.rebuildCalendarGrid(true);
        }
    }

    function weatherColor(tone) {
        if (tone === "blue") return Theme.colBlue;
        if (tone === "teal") return Theme.colTeal;
        if (tone === "mauve") return Theme.colMauve;
        if (tone === "red") return Theme.colRed;
        if (tone === "text") return Theme.colText;
        if (tone === "subtext") return Theme.colSubtext;
        return Theme.colPeach;
    }

    function refreshWeather() {
        if (!weatherProc.running) {
            weatherProc.running = true;
        }
    }

    function refreshWeatherIfStale() {
        const now = Date.now();
        if (hub.lastWeatherMs === 0 || (now - hub.lastWeatherMs) > 300000) {
            hub.refreshWeather();
        }
    }

    function dateKey(y, m, d) {
        return y + "-" + (m + 1) + "-" + d;
    }

    function eventDateParts(ev) {
        const dt = new Date(Number(ev.begin_ms) || 0);
        if (ev.all_day) {
            return { y: dt.getUTCFullYear(), m: dt.getUTCMonth(), d: dt.getUTCDate(), hh: 0, mm: 0 };
        }
        return { y: dt.getFullYear(), m: dt.getMonth(), d: dt.getDate(), hh: dt.getHours(), mm: dt.getMinutes() };
    }

    function eventDateKey(ev) {
        const p = eventDateParts(ev);
        return dateKey(p.y, p.m, p.d);
    }

    function rebuildCalendarGrid(force) {
        const y = hub.calViewYear;
        const m = hub.calViewMonth;
        const now = new Date();
        const todayKey = dateKey(now.getFullYear(), now.getMonth(), now.getDate());
        const evs = hub.agendaEvents || [];
        const sig = y + ":" + m + ":" + todayKey + ":" + evs.length;
        if (!force && hub._calGridSig === sig && hub.calGridCells.length > 0) {
            return;
        }
        hub._calGridSig = sig;
        hub.calMonthTitle = hub.monthNames[m] + " " + y;

        const eventMap = {};
        for (let i = 0; i < evs.length; i++) {
            eventMap[eventDateKey(evs[i])] = true;
        }

        const first = new Date(y, m, 1);
        const startOffset = (first.getDay() + 6) % 7; // Monday = 0
        const daysInMonth = new Date(y, m + 1, 0).getDate();
        const prevDays = new Date(y, m, 0).getDate();
        const totalCells = (startOffset + daysInMonth) > 35 ? 42 : 35;

        const cells = [];
        for (let idx = 0; idx < totalCells; idx++) {
            const col = idx % 7;
            const isWknd = (col === 5 || col === 6);
            if (idx < startOffset) {
                const d = prevDays - startOffset + 1 + idx;
                const pm = m === 0 ? 11 : m - 1;
                const py = m === 0 ? y - 1 : y;
                const k = dateKey(py, pm, d);
                cells.push({ d: String(d), key: k, cls: "muted", hasEvent: Boolean(eventMap[k]) });
            } else if (idx < startOffset + daysInMonth) {
                const d = idx - startOffset + 1;
                const k = dateKey(y, m, d);
                const cls = (k === todayKey) ? "today" : (isWknd ? "wknd" : "");
                cells.push({ d: String(d), key: k, cls: cls, hasEvent: Boolean(eventMap[k]) });
            } else {
                const d = idx - (startOffset + daysInMonth) + 1;
                const nm = m === 11 ? 0 : m + 1;
                const ny = m === 11 ? y + 1 : y;
                const k = dateKey(ny, nm, d);
                cells.push({ d: String(d), key: k, cls: "muted", hasEvent: Boolean(eventMap[k]) });
            }
        }
        hub.calGridCells = cells;
    }

    function queryCalendarMonth(y, m) {
        const startMs = new Date(y, m, -6).getTime();
        const endMs = new Date(y, m + 2, 15).getTime();
        hub.sendHubCmd("calendar\t" + startMs + "\t" + endMs + "\n");
    }

    function stepCalendarMonth(delta) {
        let m = hub.calViewMonth + delta;
        let y = hub.calViewYear;
        while (m < 0) { m += 12; y -= 1; }
        while (m > 11) { m -= 12; y += 1; }
        hub.calViewYear = y;
        hub.calViewMonth = m;
        hub.rebuildCalendarGrid();
        hub.queryCalendarMonth(y, m);
    }

    function resetCalendarToday() {
        const now = new Date();
        hub.calViewYear = now.getFullYear();
        hub.calViewMonth = now.getMonth();
        hub.calSelectedDateKey = "";
        hub.rebuildCalendarGrid();
        hub.queryCalendarMonth(hub.calViewYear, hub.calViewMonth);
    }

    function toggleCalendarDay(cell) {
        if (!cell || cell.cls === "muted") return;
        hub.calSelectedDateKey = (hub.calSelectedDateKey === cell.key) ? "" : cell.key;
    }

    function filteredAgendaEvents() {
        const evs = hub.agendaEvents || [];
        const sel = hub.calSelectedDateKey;
        const out = [];
        const now = new Date();
        const todayStartMs = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();

        for (let i = 0; i < evs.length; i++) {
            const ev = evs[i];
            if (sel.length > 0) {
                if (eventDateKey(ev) === sel) out.push(ev);
            } else {
                const cmpMs = (ev.end_ms && ev.end_ms > 0) ? ev.end_ms : ev.begin_ms;
                if (cmpMs >= todayStartMs) out.push(ev);
            }
        }
        return out.slice(0, 5);
    }

    function formatEventWhen(ev) {
        const p = eventDateParts(ev);
        const now = new Date();
        const isToday = (p.y === now.getFullYear() && p.m === now.getMonth() && p.d === now.getDate());
        const dStr = p.d + " " + hub.monthShort[p.m];
        if (ev.all_day) {
            return isToday ? "Today" : dStr;
        }
        const hh = p.hh < 10 ? "0" + p.hh : String(p.hh);
        const mm = p.mm < 10 ? "0" + p.mm : String(p.mm);
        return (isToday || hub.calSelectedDateKey.length > 0) ? (hh + ":" + mm) : (dStr + " " + hh + ":" + mm);
    }

    function eventColor(ev) {
        const cid = Number(ev.cal_id) || 0;
        if (cid % 4 === 1) return Theme.colBlue;
        if (cid % 4 === 2) return Theme.colMauve;
        if (cid % 4 === 3) return Theme.colTeal;
        return Theme.colPeach;
    }

    Component.onCompleted: hub.rebuildCalendarGrid(true)

    Process {
        id: androidStatusProc
        command: ["python3", Quickshell.env("HOME") + "/.config/quickshell/scripts/android_status.py"]
        running: false
        onRunningChanged: {
            if (!running) hub.androidProbing = false;
        }
        stdout: StdioCollector {
            onStreamFinished: {
                hub.androidProbing = false;
                try {
                    const d = JSON.parse((this.text || "").trim() || "{}");
                    if (d.api_ok !== undefined) hub.termuxApiOk = Boolean(d.api_ok);
                    if (d.api_state !== undefined) hub.termuxApiState = String(d.api_state);
                    if (d.api_ver !== undefined) hub.termuxApiVer = String(d.api_ver);
                    if (d.api_detail !== undefined) hub.termuxApiDetail = String(d.api_detail);
                    if (d.shizuku_ok !== undefined) hub.shizukuOk = Boolean(d.shizuku_ok);
                    if (d.shizuku_state !== undefined) hub.shizukuState = String(d.shizuku_state);
                    if (d.shizuku_ver !== undefined) hub.shizukuVer = String(d.shizuku_ver);
                    if (d.shizuku_detail !== undefined) hub.shizukuDetail = String(d.shizuku_detail);
                } catch (e) {}
            }
        }
    }

    Process {
        id: mediaStreamProc
        command: [Quickshell.env("HOME") + "/.local/bin/qs-native", "media-stream"]
        running: true
        stdinEnabled: true
        onRunningChanged: {
            if (running) hub.flushHubQueue();
        }
        stdout: SplitParser {
            onRead: line => {
                try {
                    const d = JSON.parse((line || "").trim() || "{}");
                    hub.handleHubMessage(d);
                } catch (e) {}
            }
        }
    }

    Process {
        id: weatherProc
        command: ["python3", Quickshell.env("HOME") + "/.config/quickshell/scripts/weather.py"]
        running: false
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const d = JSON.parse((this.text || "").trim() || "{}");
                    if (d.temp !== undefined) hub.weatherTemp = String(d.temp);
                    if (d.detail !== undefined) hub.weatherDetail = String(d.detail);
                    if (d.location !== undefined) hub.weatherLocation = String(d.location);
                    if (d.icon !== undefined) hub.weatherIcon = String(d.icon);
                    if (d.tone !== undefined) hub.weatherTone = String(d.tone);
                    if (d.ok) hub.lastWeatherMs = Date.now();
                } catch (e) {}
            }
        }
    }

    Timer {
        interval: 1200
        running: true
        repeat: false
        onTriggered: hub.refreshAndroidStatus()
    }

    Timer {
        interval: 15000
        running: hub.widgetsOpen
        repeat: true
        onTriggered: hub.refreshAndroidStatus()
    }

    Timer {
        id: androidDelayTimer
        interval: 700
        repeat: false
        onTriggered: hub.refreshAndroidStatus()
    }

    Timer {
        interval: 5000
        running: hub.widgetsOpen
        repeat: true
        onTriggered: hub.refreshMedia()
    }

    Timer {
        interval: 15000
        running: hub.widgetsOpen
        repeat: true
        onTriggered: hub.refreshFocus()
    }

    Timer {
        interval: 1000
        running: hub.widgetsOpen && hub.mediaPlaying
        repeat: true
        onTriggered: {
            hub.mediaPosSec += 1;
            hub.mediaPosText = hub.fmtMediaSec(hub.mediaPosSec);
        }
    }

    Timer {
        interval: 1400
        running: true
        repeat: false
        onTriggered: hub.refreshWeather()
    }

    Timer {
        interval: 900000
        running: true
        repeat: true
        onTriggered: hub.refreshWeather()
    }
}
