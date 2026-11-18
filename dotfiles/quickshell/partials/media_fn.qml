    function fmtMediaSec(sec) {
        const s = Math.max(0, Math.floor(sec));
        const m = Math.floor(s / 60);
        const rem = s % 60;
        return m + ":" + (rem < 10 ? "0" + rem : rem);
    }

    function refreshMedia() {
        if (!mediaStreamProc.running) {
            mediaStreamProc.running = true;
        } else {
            mediaStreamProc.write("status\n");
        }
    }

    function sendMediaAction(act) {
        const wasPlaying = root.mediaPlaying ? "1" : "0";
        if (act === "play-pause") {
            root.mediaPlaying = !root.mediaPlaying;
            root.mediaState = root.mediaPlaying ? "PLAYING" : "PAUSED";
        }
        if (!mediaStreamProc.running) {
            mediaStreamProc.running = true;
        }
        mediaStreamProc.write(act + "\t" + wasPlaying + "\t" + root.mediaTag + "\n");
    }

    function refreshFocus() {
        if (!mediaStreamProc.running) {
            mediaStreamProc.running = true;
        } else {
            mediaStreamProc.write("focus-status\n");
        }
    }

    function toggleFocusDnd() {
        root.focusDnd = !root.focusDnd;
        root.focusLabel = root.focusDnd ? "Priority Only" : "Off";
        if (!mediaStreamProc.running) {
            mediaStreamProc.running = true;
        }
        mediaStreamProc.write("focus-toggle\n");
    }

    function handleHubMessage(d) {
        const kind = d.kind || "media";
        if (kind === "media") {
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
        } else if (kind === "focus") {
            if (d.available !== undefined) root.focusAvailable = Boolean(d.available);
            if (d.zen !== undefined) root.focusZen = Number(d.zen) || 0;
            if (d.dnd !== undefined) root.focusDnd = Boolean(d.dnd);
            if (d.notif_count !== undefined) root.focusNotifCount = Number(d.notif_count) || 0;
            if (d.label !== undefined) root.focusLabel = String(d.label);
        } else if (kind === "calendar") {
            if (d.ok !== undefined) root.calendarOk = Boolean(d.ok);
            if (Array.isArray(d.events)) root.agendaEvents = d.events;
            root.rebuildCalendarGrid();
        }
    }
