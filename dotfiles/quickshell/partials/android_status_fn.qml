    function refreshAndroidStatus() {
        if (!androidStatusProc.running) {
            root.androidProbing = true;
            androidStatusProc.running = true;
        }
    }
