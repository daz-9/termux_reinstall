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
