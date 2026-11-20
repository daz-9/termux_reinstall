// Termux / Android 16 stability & phantom-process limit mitigations
user_pref("dom.ipc.processCount", 2);
user_pref("dom.ipc.processCount.webIsolated", 1);
user_pref("dom.ipc.processCount.extension", 1);
user_pref("dom.ipc.processCount.privilegedabout", 1);
user_pref("dom.ipc.processCount.privilegedmozilla", 1);
user_pref("dom.ipc.processCount.file", 1);
user_pref("dom.ipc.processCount.inference", 1);
user_pref("dom.ipc.processPrelaunch.enabled", false);
user_pref("fission.autostart", false);

// Use stable Software WebRender; avoid missing libgbm.so.1 DMABuf, broken Mesa Zink DRI2, and VirGL GL_RENDERER sanitizer crashes
user_pref("gfx.webrender.software", true);
user_pref("widget.dmabuf.force-enabled", false);
user_pref("media.ffmpeg.vaapi.enabled", false);
user_pref("media.hardware-video-decoding.enabled", false);
user_pref("layers.gpu-process.enabled", false);
