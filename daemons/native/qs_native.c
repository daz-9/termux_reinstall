#define _GNU_SOURCE
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include <X11/Xlib.h>
#include <X11/extensions/XInput2.h>
#include <X11/extensions/Xfixes.h>

static volatile sig_atomic_t g_running = 1;

static void on_term_sig(int sig) {
    (void)sig;
    g_running = 0;
}

static void install_signals(void) {
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = on_term_sig;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    signal(SIGPIPE, SIG_IGN);
}

static int64_t mono_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000LL + (int64_t)(ts.tv_nsec / 1000000LL);
}

static void sleep_check_ms(int total_ms) {
    int rem = total_ms;
    while (g_running && rem > 0) {
        int step = rem > 100 ? 100 : rem;
        usleep((useconds_t)step * 1000U);
        rem -= step;
    }
}

static void json_write_str(FILE *f, const char *s) {
    fputc('"', f);
    if (s) {
        for (const unsigned char *p = (const unsigned char *)s; *p; p++) {
            unsigned char c = *p;
            if (c == '"') fputs("\\\"", f);
            else if (c == '\\') fputs("\\\\", f);
            else if (c == '\b') fputs("\\b", f);
            else if (c == '\f') fputs("\\f", f);
            else if (c == '\n') fputs("\\n", f);
            else if (c == '\r') fputs("\\r", f);
            else if (c == '\t') fputs("\\t", f);
            else if (c < 0x20) fprintf(f, "\\u%04x", (unsigned)c);
            else fputc((int)c, f);
        }
    }
    fputc('"', f);
}

/* --- /proc CPU & Memory Readers ------------------------------------------ */

static uint64_t read_total_jiffies(void) {
    DIR *d = opendir("/proc");
    if (!d) return 0;
    uint64_t total = 0;
    struct dirent *ent;
    char path[64];
    char buf[2048];
    while ((ent = readdir(d)) != NULL) {
        if (!isdigit((unsigned char)ent->d_name[0])) continue;
        bool all_digit = true;
        for (const char *c = ent->d_name; *c; c++) {
            if (!isdigit((unsigned char)*c)) {
                all_digit = false;
                break;
            }
        }
        if (!all_digit) continue;
        snprintf(path, sizeof(path), "/proc/%s/stat", ent->d_name);
        int fd = open(path, O_RDONLY);
        if (fd < 0) continue;
        ssize_t n = read(fd, buf, sizeof(buf) - 1);
        close(fd);
        if (n <= 0) continue;
        buf[n] = '\0';
        char *rp = strrchr(buf, ')');
        if (!rp || rp[1] == '\0') continue;
        char *p = rp + 2;
        int field = 0;
        uint64_t utime = 0, stime = 0;
        while (*p && field <= 12) {
            while (*p == ' ') p++;
            if (!*p) break;
            char *end = p;
            while (*end && *end != ' ') end++;
            if (field == 11) utime = strtoull(p, NULL, 10);
            else if (field == 12) {
                stime = strtoull(p, NULL, 10);
                total += utime + stime;
                break;
            }
            p = end;
            field++;
        }
    }
    closedir(d);
    return total;
}

static void read_mem_info(char *used_buf, size_t ucap, char *tot_buf, size_t tcap, int *pct_out) {
    FILE *f = fopen("/proc/meminfo", "r");
    long mem_tot = 0, mem_avail = -1, mem_free = 0;
    if (f) {
        char line[256];
        while (fgets(line, sizeof(line), f)) {
            long val = 0;
            if (sscanf(line, "MemTotal: %ld kB", &val) == 1) mem_tot = val;
            else if (sscanf(line, "MemAvailable: %ld kB", &val) == 1) mem_avail = val;
            else if (sscanf(line, "MemFree: %ld kB", &val) == 1) mem_free = val;
        }
        fclose(f);
    }
    if (mem_avail < 0) mem_avail = mem_free;
    if (mem_tot <= 0) {
        snprintf(used_buf, ucap, "0.0");
        snprintf(tot_buf, tcap, "0.0");
        *pct_out = 0;
        return;
    }
    long used_kb = mem_tot - mem_avail;
    if (used_kb < 0) used_kb = 0;
    int pct = (int)llround((double)used_kb * 100.0 / (double)mem_tot);
    if (pct < 0) pct = 0;
    if (pct > 100) pct = 100;
    snprintf(used_buf, ucap, "%.1f", (double)used_kb / 1048576.0);
    snprintf(tot_buf, tcap, "%.1f", (double)mem_tot / 1048576.0);
    *pct_out = pct;
}

/* --- Subprocess Capture + Minimal JSON Extractors ------------------------ */

static bool run_cmd_capture(const char *const argv[], char *out, size_t cap, int timeout_ms) {
    if (!out || cap == 0) return false;
    out[0] = '\0';
    int pfd[2];
    if (pipe2(pfd, O_CLOEXEC) != 0) return false;

    pid_t pid = fork();
    if (pid < 0) {
        close(pfd[0]);
        close(pfd[1]);
        return false;
    }
    if (pid == 0) {
        close(pfd[0]);
        dup2(pfd[1], STDOUT_FILENO);
        close(pfd[1]);
        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0) {
            dup2(devnull, STDIN_FILENO);
            dup2(devnull, STDERR_FILENO);
            if (devnull > 2) close(devnull);
        }
        execvp(argv[0], (char *const *)argv);
        _exit(127);
    }
    close(pfd[1]);

    int fl = fcntl(pfd[0], F_GETFL, 0);
    if (fl >= 0) fcntl(pfd[0], F_SETFL, fl | O_NONBLOCK);

    size_t len = 0;
    int64_t deadline = mono_ms() + timeout_ms;
    bool timed_out = false;
    for (;;) {
        int64_t left = deadline - mono_ms();
        if (left <= 0) {
            timed_out = true;
            break;
        }
        struct pollfd pf = { .fd = pfd[0], .events = POLLIN };
        int rc = poll(&pf, 1, (int)left);
        if (rc < 0) {
            if (errno == EINTR && g_running) continue;
            break;
        }
        if (rc == 0) {
            timed_out = true;
            break;
        }
        if (pf.revents & (POLLIN | POLLHUP)) {
            char tmp[2048];
            ssize_t r = read(pfd[0], tmp, sizeof(tmp));
            if (r > 0) {
                size_t copy = (size_t)r;
                if (len + copy >= cap) copy = cap - 1 - len;
                if (copy > 0) {
                    memcpy(out + len, tmp, copy);
                    len += copy;
                    out[len] = '\0';
                }
            } else if (r == 0) {
                break;
            } else if (errno != EAGAIN && errno != EWOULDBLOCK) {
                break;
            }
        }
    }
    close(pfd[0]);
    if (timed_out) kill(pid, SIGKILL);
    int st = 0;
    waitpid(pid, &st, 0);
    return !timed_out && WIFEXITED(st) && WEXITSTATUS(st) == 0 && len > 0;
}

static const char *json_find_val(const char *json, const char *key) {
    char pat[96];
    snprintf(pat, sizeof(pat), "\"%s\"", key);
    const char *p = json;
    size_t plen = strlen(pat);
    while ((p = strstr(p, pat)) != NULL) {
        const char *q = p + plen;
        while (*q == ' ' || *q == '\t' || *q == '\r' || *q == '\n') q++;
        if (*q == ':') {
            q++;
            while (*q == ' ' || *q == '\t' || *q == '\r' || *q == '\n') q++;
            return q;
        }
        p = q;
    }
    return NULL;
}

static bool json_get_double(const char *json, const char *key, double *out) {
    const char *v = json_find_val(json, key);
    if (!v || (*v != '-' && !isdigit((unsigned char)*v))) return false;
    char *end = NULL;
    double val = strtod(v, &end);
    if (end == v) return false;
    *out = val;
    return true;
}

static bool json_get_str(const char *json, const char *key, char *out, size_t cap) {
    const char *v = json_find_val(json, key);
    if (!v || *v != '"') return false;
    v++;
    size_t i = 0;
    while (*v && *v != '"' && i + 1 < cap) {
        if (*v == '\\' && v[1]) v++;
        out[i++] = *v++;
    }
    out[i] = '\0';
    return true;
}

/* --- Subcommand: cpu (Polybar) ------------------------------------------- */

static int cmd_cpu(void) {
    long clk = sysconf(_SC_CLK_TCK);
    if (clk <= 0) clk = 100;
    long ncpu = sysconf(_SC_NPROCESSORS_ONLN);
    if (ncpu <= 0) ncpu = 1;

    uint64_t j_prev = read_total_jiffies();
    int64_t t_prev = mono_ms();
    sleep_check_ms(350);

    while (g_running) {
        uint64_t j_now = read_total_jiffies();
        int64_t t_now = mono_ms();
        double dt = (double)(t_now - t_prev) / 1000.0;
        if (dt < 0.05) dt = 0.05;
        int pct = (int)llround((((double)(j_now - j_prev) / (double)clk) / (dt * (double)ncpu)) * 100.0);
        if (pct < 0) pct = 0;
        if (pct > 100) pct = 100;
        j_prev = j_now;
        t_prev = t_now;

        const char *col = pct >= 80 ? "#f38ba8" : (pct >= 50 ? "#fab387" : "#94e2d5");
        printf("%%{F%s}\xef\x92\xbc%%{F-} %d%%\n", col, pct);
        fflush(stdout);
        sleep_check_ms(3000);
    }
    return 0;
}

/* --- Subcommand: sys-diag (Quickshell Wayland topbar) -------------------- */

static int cmd_sys_diag(void) {
    long clk = sysconf(_SC_CLK_TCK);
    if (clk <= 0) clk = 100;
    long ncpu = sysconf(_SC_NPROCESSORS_ONLN);
    if (ncpu <= 0) ncpu = 1;

    uint64_t j_prev = read_total_jiffies();
    int64_t t_prev = mono_ms();

    int bat_pct = -1;
    char bat_status[32] = "UNKNOWN";
    bool has_temp = false;
    double temp_c = 0.0;
    char watts[24] = "";

    bool wifi_ok = false;
    int wifi_rate = 0;
    int wifi_rssi = 0;
    char wifi_ip[64] = "";

    sleep_check_ms(200);
    int tick = 0;
    char jbuf[8192];

    while (g_running) {
        uint64_t j_now = read_total_jiffies();
        int64_t t_now = mono_ms();
        double dt = (double)(t_now - t_prev) / 1000.0;
        if (dt < 0.05) dt = 0.05;
        int cpu_pct = (int)llround((((double)(j_now - j_prev) / (double)clk) / (dt * (double)ncpu)) * 100.0);
        if (cpu_pct < 0) cpu_pct = 0;
        if (cpu_pct > 100) cpu_pct = 100;
        j_prev = j_now;
        t_prev = t_now;

        char mem_used[16], mem_total[16];
        int mem_pct = 0;
        read_mem_info(mem_used, sizeof(mem_used), mem_total, sizeof(mem_total), &mem_pct);

        if (tick % 6 == 0) {
            const char *bat_argv[] = { "termux-battery-status", NULL };
            if (run_cmd_capture(bat_argv, jbuf, sizeof(jbuf), 2000)) {
                double dval = 0.0;
                if (json_get_double(jbuf, "percentage", &dval)) bat_pct = (int)dval;
                char sbuf[32];
                if (json_get_str(jbuf, "status", sbuf, sizeof(sbuf))) {
                    for (size_t i = 0; sbuf[i] && i + 1 < sizeof(bat_status); i++) {
                        bat_status[i] = (char)toupper((unsigned char)sbuf[i]);
                        bat_status[i + 1] = '\0';
                    }
                }
                if (json_get_double(jbuf, "temperature", &dval)) {
                    temp_c = floor(dval * 10.0 + 0.5) / 10.0;
                    has_temp = true;
                }
                double mv = 0.0, ua = 0.0;
                if (json_get_double(jbuf, "voltage", &mv) && json_get_double(jbuf, "current", &ua)) {
                    double w = (mv / 1000.0) * (ua / 1000000.0);
                    if (fabs(w) >= 0.1) snprintf(watts, sizeof(watts), "%+.1fW", w);
                    else watts[0] = '\0';
                } else {
                    watts[0] = '\0';
                }
            }

            const char *wifi_argv[] = { "termux-wifi-connectioninfo", NULL };
            if (run_cmd_capture(wifi_argv, jbuf, sizeof(jbuf), 2000)) {
                char st[32] = "";
                json_get_str(jbuf, "supplicant_state", st, sizeof(st));
                for (size_t i = 0; st[i]; i++) st[i] = (char)toupper((unsigned char)st[i]);
                wifi_ip[0] = '\0';
                json_get_str(jbuf, "ip", wifi_ip, sizeof(wifi_ip));
                wifi_ok = (strcmp(st, "COMPLETED") == 0 && wifi_ip[0] != '\0');
                double dval = 0.0;
                wifi_rate = json_get_double(jbuf, "link_speed_mbps", &dval) ? (int)dval : 0;
                wifi_rssi = json_get_double(jbuf, "rssi", &dval) ? (int)dval : 0;
            }
        }

        printf("{\"cpu\":%d,\"mem_used\":", cpu_pct);
        json_write_str(stdout, mem_used);
        fputs(",\"mem_total\":", stdout);
        json_write_str(stdout, mem_total);
        printf(",\"mem_pct\":%d,\"bat_pct\":%d,\"bat_status\":", mem_pct, bat_pct);
        json_write_str(stdout, bat_status);
        if (has_temp) printf(",\"temp_c\":%.1f", temp_c);
        else fputs(",\"temp_c\":null", stdout);
        fputs(",\"watts\":", stdout);
        json_write_str(stdout, watts);
        printf(",\"wifi_ok\":%s,\"wifi_rate\":%d,\"wifi_rssi\":%d,\"ip\":",
               wifi_ok ? "true" : "false", wifi_rate, wifi_rssi);
        json_write_str(stdout, wifi_ip);
        fputs("}\n", stdout);
        fflush(stdout);

        tick++;
        sleep_check_ms(2000);
    }
    return 0;
}

/* --- Subcommands: hide-cursor & submenu-watch (X11) ---------------------- */

typedef struct {
    int x, y, w, h;
} RectI;

static bool point_in(int px, int py, RectI r) {
    return r.w > 0 && r.h > 0 && px >= r.x && px < r.x + r.w && py >= r.y && py < r.y + r.h;
}

static bool matches_rect(const XWindowAttributes *a, RectI r, int tol) {
    return r.w > 0 && r.h > 0 &&
           abs(a->x - r.x) <= tol && abs(a->y - r.y) <= tol &&
           abs(a->width - r.w) <= tol && abs(a->height - r.h) <= tol;
}

static bool has_foreign_popup(Display *dpy, Window root, const RectI *own, int n_own) {
    Window r, p, *ch = NULL;
    unsigned int n = 0;
    if (!XQueryTree(dpy, root, &r, &p, &ch, &n)) return false;
    bool found = false;
    for (unsigned int i = 0; i < n; i++) {
        XWindowAttributes a;
        if (!XGetWindowAttributes(dpy, ch[i], &a) || a.map_state != IsViewable) continue;
        if (a.override_redirect == 1 && a.width >= 200 && a.height >= 150) {
            bool mine = false;
            for (int k = 0; k < n_own; k++) {
                if (matches_rect(&a, own[k], 16)) {
                    mine = true;
                    break;
                }
            }
            if (!mine) {
                found = true;
                break;
            }
        }
    }
    if (ch) XFree(ch);
    return found;
}

static int cmd_hide_cursor(void) {
    const char *disp = getenv("DISPLAY");
    Display *dpy = XOpenDisplay(disp && *disp ? disp : ":0");
    if (!dpy) return 1;

    int ev = 0, er = 0, maj = 5, minv = 0;
    if (!XFixesQueryExtension(dpy, &ev, &er)) {
        XCloseDisplay(dpy);
        return 1;
    }
    XFixesQueryVersion(dpy, &maj, &minv);

    Window root = DefaultRootWindow(dpy);
    const char *tmp = getenv("TMPDIR");
    char pid_path[256] = "";
    snprintf(pid_path, sizeof(pid_path), "%s/hide-cursor.pid",
             (tmp && *tmp) ? tmp : "/data/data/com.termux/files/usr/tmp");
    FILE *pf = fopen(pid_path, "w");
    if (pf) {
        fprintf(pf, "%d", (int)getpid());
        fclose(pf);
    } else {
        pid_path[0] = '\0';
    }

    Window rw = 0, cw = 0;
    int rx = 0, ry = 0, wx = 0, wy = 0;
    unsigned int mask = 0;
    XQueryPointer(dpy, root, &rw, &cw, &rx, &ry, &wx, &wy, &mask);
    int last_x = rx, last_y = ry;
    bool was_pressed = (mask & 0x1F00U) != 0;
    bool hidden = true;
    XFixesHideCursor(dpy, root);
    XSync(dpy, False);
    int64_t hide_at = 0;

    while (g_running) {
        usleep(80000);
        if (!XQueryPointer(dpy, root, &rw, &cw, &rx, &ry, &wx, &wy, &mask)) break;
        int64_t now = mono_ms();
        bool moved = (rx != last_x) || (ry != last_y);
        bool pressed = (mask & 0x1F00U) != 0;
        last_x = rx;
        last_y = ry;

        if (pressed) {
            was_pressed = true;
            hide_at = now + 500;
        } else if (was_pressed && !pressed) {
            was_pressed = false;
            hide_at = now + 150;
            if (!hidden) {
                XFixesHideCursor(dpy, root);
                XSync(dpy, False);
                hidden = true;
            }
        } else if (moved) {
            if (hidden) {
                XFixesShowCursor(dpy, root);
                XSync(dpy, False);
                hidden = false;
            }
            hide_at = now + 600;
        } else if (!hidden && now >= hide_at) {
            XFixesHideCursor(dpy, root);
            XSync(dpy, False);
            hidden = true;
        }
    }

    if (hidden) {
        XFixesShowCursor(dpy, root);
        XSync(dpy, False);
    }
    if (pid_path[0]) unlink(pid_path);
    XCloseDisplay(dpy);
    return 0;
}

static int cmd_submenu_watch(int argc, char **argv) {
    int dock_w = 128, dock_h = 1508, sub_x = 140, sub_y = 80, sub_w = 844, sub_h = 1508;
    if (argc >= 8) {
        dock_w = (int)strtod(argv[2], NULL);
        dock_h = (int)strtod(argv[3], NULL);
        sub_x  = (int)strtod(argv[4], NULL);
        sub_y  = (int)strtod(argv[5], NULL);
        sub_w  = (int)strtod(argv[6], NULL);
        sub_h  = (int)strtod(argv[7], NULL);
    }
    RectI dock_rect = { 0, 80, dock_w, dock_h };
    RectI sub_rect  = { sub_x, sub_y, sub_w, sub_h };
    RectI own_rects[2] = { dock_rect, sub_rect };

    const char *disp = getenv("DISPLAY");
    Display *dpy = XOpenDisplay(disp && *disp ? disp : ":0");
    if (!dpy) return 1;
    Window root = DefaultRootWindow(dpy);
    int xfd = ConnectionNumber(dpy);

    int maj = 2, minv = 2;
    XIQueryVersion(dpy, &maj, &minv);

    unsigned char mask_bytes[4] = { 0, 0x80, 0, 0 }; /* XI_RawButtonPress (15) */
    XIEventMask em = { .deviceid = XIAllMasterDevices, .mask_len = 4, .mask = mask_bytes };
    XISelectEvents(dpy, root, &em, 1);
    XFlush(dpy);

    const char *tmp = getenv("TMPDIR");
    char pid_path[256] = "";
    snprintf(pid_path, sizeof(pid_path), "%s/qs-watch.pid",
             (tmp && *tmp) ? tmp : "/data/data/com.termux/files/usr/tmp");
    FILE *pf = fopen(pid_path, "w");
    if (pf) {
        fprintf(pf, "%d", (int)getpid());
        fclose(pf);
    } else {
        pid_path[0] = '\0';
    }

    Window focus_win = 0, initial_focus = 0;
    int revert_to = 0;
    XGetInputFocus(dpy, &initial_focus, &revert_to);

    int64_t start_t = mono_ms();
    XEvent ev_buf;

    while (g_running) {
        struct pollfd pf_x = { .fd = xfd, .events = POLLIN };
        int rc = poll(&pf_x, 1, 120);
        bool clicked = false;
        if (rc > 0 && (pf_x.revents & POLLIN)) {
            while (XPending(dpy) > 0) {
                XNextEvent(dpy, &ev_buf);
                clicked = true;
            }
        }

        XGetInputFocus(dpy, &focus_win, &revert_to);
        if ((focus_win != initial_focus && focus_win != None && focus_win != PointerRoot) ||
            has_foreign_popup(dpy, root, own_rects, 2)) {
            puts("CLOSE");
            fflush(stdout);
            break;
        }

        if (clicked && (mono_ms() - start_t) >= 80) {
            Window rw = 0, cw = 0;
            int rx = 0, ry = 0, wx = 0, wy = 0;
            unsigned int mask = 0;
            if (XQueryPointer(dpy, root, &rw, &cw, &rx, &ry, &wx, &wy, &mask)) {
                bool in_sub = point_in(rx, ry, sub_rect);
                bool in_dock = point_in(rx, ry, dock_rect);
                bool on_toggle = in_dock && (
                    (ry >= 80 + (int)(dock_h * 0.45) && ry <= 80 + (int)(dock_h * 0.70)) ||
                    (ry >= 80 + dock_h - 90)
                );
                if (!in_sub && !on_toggle) {
                    puts("CLOSE");
                    fflush(stdout);
                    break;
                }
            }
        }
    }

    if (pid_path[0]) unlink(pid_path);
    XCloseDisplay(dpy);
    return 0;
}

/* --- Subcommand: wl-workspaces (LabWC ext_workspace_manager_v1) ---------- */

#define MAX_WL_WS 32

typedef struct {
    uint32_t id;
    uint32_t state;
    char name[64];
    bool alive;
} WlWorkspace;

static uint32_t read_u32(const uint8_t *p, size_t off) {
    uint32_t v;
    memcpy(&v, p + off, 4);
    return v;
}

static size_t wl_pack_str(uint8_t *dst, size_t off, const char *s) {
    uint32_t slen = (uint32_t)strlen(s) + 1;
    memcpy(dst + off, &slen, 4);
    memcpy(dst + off + 4, s, slen);
    size_t step = 4 + ((slen + 3U) & ~3U);
    if (step > 4 + slen) {
        memset(dst + off + 4 + slen, 0, step - (4 + slen));
    }
    return off + step;
}

static size_t wl_unpack_str(const uint8_t *buf, size_t len, size_t off, char *out, size_t cap) {
    if (off + 4 > len) {
        out[0] = '\0';
        return len;
    }
    uint32_t slen = read_u32(buf, off);
    size_t avail = len - (off + 4);
    size_t copy = slen > 0 ? slen - 1 : 0;
    if (copy > avail) copy = avail;
    if (copy >= cap) copy = cap - 1;
    if (copy > 0) memcpy(out, buf + off + 4, copy);
    out[copy] = '\0';
    size_t step = 4 + ((slen + 3U) & ~3U);
    return (off + step <= len) ? (off + step) : len;
}

static bool wl_send(int fd, uint32_t obj_id, uint16_t op, const uint8_t *payload, size_t plen) {
    uint8_t pkt[256];
    uint32_t size = (uint32_t)(8 + plen);
    if (size > sizeof(pkt)) return false;
    uint32_t size_op = (size << 16) | (uint32_t)op;
    memcpy(pkt, &obj_id, 4);
    memcpy(pkt + 4, &size_op, 4);
    if (plen > 0 && payload) memcpy(pkt + 8, payload, plen);
    size_t sent = 0;
    while (sent < size) {
        ssize_t w = send(fd, pkt + sent, size - sent, 0);
        if (w <= 0) {
            if (w < 0 && errno == EINTR) continue;
            return false;
        }
        sent += (size_t)w;
    }
    return true;
}

static void wl_emit_state(const WlWorkspace *ws_list, int count) {
    const WlWorkspace *by_num[7] = { NULL };
    const WlWorkspace *ordered[6] = { NULL };
    int n_ord = 0;
    bool has_num = false;

    for (int i = 0; i < count; i++) {
        if (!ws_list[i].alive || (ws_list[i].state & 4U)) continue;
        if (n_ord < 6) ordered[n_ord++] = &ws_list[i];
        char *end = NULL;
        long n = strtol(ws_list[i].name, &end, 10);
        if (ws_list[i].name[0] && end && *end == '\0' && n >= 1 && n <= 6) {
            by_num[n] = &ws_list[i];
            has_num = true;
        }
    }
    if (!has_num && n_ord == 0) return;

    fputc('[', stdout);
    if (has_num) {
        for (int n = 1; n <= 6; n++) {
            bool foc = by_num[n] ? ((by_num[n]->state & 1U) != 0) : false;
            bool urg = by_num[n] ? ((by_num[n]->state & 2U) != 0) : false;
            printf("%s{\"num\":%d,\"focused\":%s,\"occupied\":false,\"urgent\":%s}",
                   n > 1 ? "," : "", n, foc ? "true" : "false", urg ? "true" : "false");
        }
    } else {
        for (int i = 0; i < n_ord; i++) {
            bool foc = (ordered[i]->state & 1U) != 0;
            bool urg = (ordered[i]->state & 2U) != 0;
            printf("%s{\"num\":%d,\"focused\":%s,\"occupied\":false,\"urgent\":%s}",
                   i > 0 ? "," : "", i + 1, foc ? "true" : "false", urg ? "true" : "false");
        }
    }
    fputs("]\n", stdout);
    fflush(stdout);
}

static int cmd_wl_workspaces(void) {
    const char *xdg = getenv("XDG_RUNTIME_DIR");
    if (!xdg || !*xdg) xdg = getenv("TMPDIR");
    if (!xdg || !*xdg) xdg = "/data/data/com.termux/files/usr/tmp";
    const char *wdisp = getenv("WAYLAND_DISPLAY");
    if (!wdisp || !*wdisp) wdisp = "wayland-0";

    struct sockaddr_un sa;
    memset(&sa, 0, sizeof(sa));
    sa.sun_family = AF_UNIX;
    if (wdisp[0] == '/') snprintf(sa.sun_path, sizeof(sa.sun_path), "%s", wdisp);
    else snprintf(sa.sun_path, sizeof(sa.sun_path), "%s/%s", xdg, wdisp);

    int sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock < 0) return 1;
    if (connect(sock, (struct sockaddr *)&sa, sizeof(sa)) != 0) {
        close(sock);
        return 1;
    }

    uint32_t reg_id = 2, sync_id = 3;
    wl_send(sock, 1, 1, (const uint8_t *)&reg_id, 4);
    wl_send(sock, 1, 0, (const uint8_t *)&sync_id, 4);

    uint32_t mgr_id = 0;
    WlWorkspace workspaces[MAX_WL_WS];
    memset(workspaces, 0, sizeof(workspaces));
    int ws_count = 0;

    uint8_t rx[32768];
    size_t rx_len = 0;
    char in_buf[512];
    size_t in_len = 0;

    while (g_running) {
        struct pollfd pfd[2] = {
            { .fd = sock, .events = POLLIN },
            { .fd = STDIN_FILENO, .events = POLLIN },
        };
        int prc = poll(pfd, 2, 500);
        if (prc < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (pfd[0].revents & (POLLIN | POLLHUP | POLLERR)) {
            if (rx_len < sizeof(rx)) {
                ssize_t r = recv(sock, rx + rx_len, sizeof(rx) - rx_len, 0);
                if (r <= 0) break;
                rx_len += (size_t)r;
            }
            size_t pos = 0;
            while (rx_len - pos >= 8) {
                uint32_t obj_id = read_u32(rx, pos);
                uint32_t size_op = read_u32(rx, pos + 4);
                uint32_t msize = size_op >> 16;
                uint16_t op = (uint16_t)(size_op & 0xFFFFU);
                if (msize < 8 || msize > rx_len - pos) break;
                const uint8_t *pl = rx + pos + 8;
                size_t plen = msize - 8;

                if (obj_id == 2 && op == 0 && plen >= 8) {
                    uint32_t gname = read_u32(pl, 0);
                    char iface[128];
                    size_t off = wl_unpack_str(pl, plen, 4, iface, sizeof(iface));
                    uint32_t gver = (off + 4 <= plen) ? read_u32(pl, off) : 1;
                    if (strcmp(iface, "ext_workspace_manager_v1") == 0 && mgr_id == 0) {
                        mgr_id = 4;
                        uint32_t ver = gver < 1 ? gver : 1;
                        uint8_t bind_pl[192];
                        memcpy(bind_pl, &gname, 4);
                        size_t boff = wl_pack_str(bind_pl, 4, iface);
                        memcpy(bind_pl + boff, &ver, 4);
                        memcpy(bind_pl + boff + 4, &mgr_id, 4);
                        wl_send(sock, 2, 0, bind_pl, boff + 8);
                    }
                } else if (mgr_id != 0 && obj_id == mgr_id) {
                    if (op == 1 && plen >= 4) {
                        uint32_t wid = read_u32(pl, 0);
                        int slot = -1;
                        for (int i = 0; i < ws_count; i++) {
                            if (!workspaces[i].alive || workspaces[i].id == wid) {
                                slot = i;
                                break;
                            }
                        }
                        if (slot < 0 && ws_count < MAX_WL_WS) slot = ws_count++;
                        if (slot >= 0) {
                            memset(&workspaces[slot], 0, sizeof(workspaces[slot]));
                            workspaces[slot].id = wid;
                            workspaces[slot].alive = true;
                        }
                    } else if (op == 2) {
                        wl_emit_state(workspaces, ws_count);
                    } else if (op == 3) {
                        g_running = 0;
                    }
                } else {
                    for (int i = 0; i < ws_count; i++) {
                        if (workspaces[i].alive && workspaces[i].id == obj_id) {
                            if (op == 1) {
                                wl_unpack_str(pl, plen, 0, workspaces[i].name, sizeof(workspaces[i].name));
                            } else if (op == 3 && plen >= 4) {
                                workspaces[i].state = read_u32(pl, 0);
                            } else if (op == 5) {
                                workspaces[i].alive = false;
                            }
                            break;
                        }
                    }
                }
                pos += msize;
            }
            if (pos > 0) {
                memmove(rx, rx + pos, rx_len - pos);
                rx_len -= pos;
            }
        }
        if (pfd[1].revents & (POLLIN | POLLHUP)) {
            ssize_t r = read(STDIN_FILENO, in_buf + in_len, sizeof(in_buf) - 1 - in_len);
            if (r <= 0) break;
            in_len += (size_t)r;
            in_buf[in_len] = '\0';
            char *nl;
            char *cursor = in_buf;
            while ((nl = strchr(cursor, '\n')) != NULL) {
                *nl = '\0';
                char *target = cursor;
                while (*target == ' ' || *target == '\r' || *target == '\t') target++;
                size_t tlen = strlen(target);
                while (tlen > 0 && (target[tlen - 1] == ' ' || target[tlen - 1] == '\r' || target[tlen - 1] == '\t')) {
                    target[--tlen] = '\0';
                }
                if (tlen > 0 && mgr_id != 0) {
                    for (int i = 0; i < ws_count; i++) {
                        if (workspaces[i].alive && strcmp(workspaces[i].name, target) == 0) {
                            wl_send(sock, workspaces[i].id, 1, NULL, 0);
                            wl_send(sock, mgr_id, 0, NULL, 0);
                            break;
                        }
                    }
                }
                cursor = nl + 1;
            }
            size_t rem = strlen(cursor);
            memmove(in_buf, cursor, rem);
            in_len = rem;
        }
    }

    close(sock);
    return 0;
}

/* --- Subcommands: media-stream / media-status (Persistent rish pipe) ----- */

typedef struct {
    pid_t pid;
    int to_fd;
    int from_fd;
    unsigned seq;
} RishPipe;

static void rish_close(RishPipe *rp) {
    if (rp->to_fd >= 0) {
        (void)!write(rp->to_fd, "exit\n", 5);
        close(rp->to_fd);
        rp->to_fd = -1;
    }
    if (rp->from_fd >= 0) {
        close(rp->from_fd);
        rp->from_fd = -1;
    }
    if (rp->pid > 0) {
        int st = 0;
        if (waitpid(rp->pid, &st, WNOHANG) == 0) {
            usleep(30000);
            if (waitpid(rp->pid, &st, WNOHANG) == 0) {
                kill(rp->pid, SIGTERM);
                usleep(40000);
                if (waitpid(rp->pid, &st, WNOHANG) == 0) kill(rp->pid, SIGKILL);
                waitpid(rp->pid, &st, 0);
            }
        }
        rp->pid = -1;
    }
}

static bool rish_open(RishPipe *rp) {
    if (rp->pid > 0 && waitpid(rp->pid, NULL, WNOHANG) == 0) return true;
    rish_close(rp);

    const char *prefix = getenv("PREFIX");
    if (!prefix || !*prefix) prefix = "/data/data/com.termux/files/usr";
    char dex_path[512];
    snprintf(dex_path, sizeof(dex_path), "%s/share/rish-shizuku.dex", prefix);
    if (access(dex_path, F_OK) != 0) return false;

    struct stat st;
    if (stat(dex_path, &st) == 0 && (st.st_mode & 0222U)) {
        (void)!chmod(dex_path, 0400);
    }

    int in_p[2], out_p[2];
    if (pipe2(in_p, O_CLOEXEC) != 0) return false;
    if (pipe2(out_p, O_CLOEXEC) != 0) {
        close(in_p[0]);
        close(in_p[1]);
        return false;
    }

    pid_t pid = fork();
    if (pid < 0) {
        close(in_p[0]); close(in_p[1]);
        close(out_p[0]); close(out_p[1]);
        return false;
    }
    if (pid == 0) {
        dup2(in_p[0], STDIN_FILENO);
        dup2(out_p[1], STDOUT_FILENO);
        dup2(out_p[1], STDERR_FILENO);
        close(in_p[0]); close(in_p[1]);
        close(out_p[0]); close(out_p[1]);

        unsetenv("LD_LIBRARY_PATH");
        unsetenv("LD_PRELOAD");
        setenv("RISH_APPLICATION_ID", "com.termux", 1);

        char cp_arg[544];
        snprintf(cp_arg, sizeof(cp_arg), "-Djava.class.path=%s", dex_path);
        const char *argv[] = {
            "/system/bin/app_process",
            cp_arg,
            "/system/bin",
            "--nice-name=rish",
            "rikka.shizuku.shell.ShizukuShellLoader",
            NULL
        };
        execv("/system/bin/app_process", (char *const *)argv);
        _exit(127);
    }

    close(in_p[0]);
    close(out_p[1]);
    int fl = fcntl(out_p[0], F_GETFL, 0);
    if (fl >= 0) fcntl(out_p[0], F_SETFL, fl | O_NONBLOCK);

    rp->pid = pid;
    rp->to_fd = in_p[1];
    rp->from_fd = out_p[0];
    return true;
}

static bool rish_exec_framed(RishPipe *rp, const char *shell_body, char **out_buf, int timeout_ms) {
    *out_buf = NULL;
    if (!rish_open(rp)) return false;

    rp->seq++;
    char beg[48], endm[48];
    snprintf(beg, sizeof(beg), "__MKB_%u__", rp->seq);
    snprintf(endm, sizeof(endm), "__MKE_%u__", rp->seq);

    size_t cmd_cap = strlen(shell_body) + 128;
    char *cmd = malloc(cmd_cap);
    if (!cmd) return false;
    int clen = snprintf(cmd, cmd_cap, "printf '%s\\n'; %s; printf '\\n%s\\n'\n", beg, shell_body, endm);

    size_t sent = 0;
    while (sent < (size_t)clen) {
        ssize_t w = write(rp->to_fd, cmd + sent, (size_t)clen - sent);
        if (w <= 0) {
            if (w < 0 && errno == EINTR && g_running) continue;
            free(cmd);
            rish_close(rp);
            return false;
        }
        sent += (size_t)w;
    }
    free(cmd);

    size_t cap = 32768, len = 0;
    char *buf = malloc(cap);
    if (!buf) return false;
    buf[0] = '\0';

    int64_t deadline = mono_ms() + timeout_ms;
    bool done = false;
    while (g_running && !done) {
        int64_t left = deadline - mono_ms();
        if (left <= 0) break;
        struct pollfd pf = { .fd = rp->from_fd, .events = POLLIN };
        int rc = poll(&pf, 1, (int)left);
        if (rc < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (rc == 0) break;
        if (pf.revents & (POLLIN | POLLHUP)) {
            for (;;) {
                if (len + 4096 >= cap) {
                    if (cap >= 524288) break;
                    cap *= 2;
                    char *nb = realloc(buf, cap);
                    if (!nb) break;
                    buf = nb;
                }
                ssize_t r = read(rp->from_fd, buf + len, cap - 1 - len);
                if (r > 0) {
                    len += (size_t)r;
                    buf[len] = '\0';
                    char *end_pos = strstr(buf, endm);
                    if (end_pos) {
                        *end_pos = '\0';
                        done = true;
                        break;
                    }
                } else if (r == 0) {
                    rish_close(rp);
                    free(buf);
                    return false;
                } else {
                    if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                    rish_close(rp);
                    free(buf);
                    return false;
                }
            }
        }
    }

    if (!done) {
        rish_close(rp);
        free(buf);
        return false;
    }

    char *start = strstr(buf, beg);
    if (start) {
        start += strlen(beg);
        if (*start == '\r') start++;
        if (*start == '\n') start++;
        memmove(buf, start, strlen(start) + 1);
    }
    *out_buf = buf;
    return true;
}

typedef struct {
    char tag[128];
    char package[128];
    bool active;
    char state_name[32];
    int state_code;
    int64_t pos_ms;
    double speed;
    int64_t updated_ms;
    char title[256];
    char artist[256];
    char album[256];
} MediaSession;

static const char *app_label_for(const char *pkg, char *tmp, size_t cap) {
    if (strcmp(pkg, "com.spotify.music") == 0) return "Spotify";
    if (strcmp(pkg, "com.spotify.lite") == 0) return "Spotify Lite";
    if (strcmp(pkg, "com.google.android.apps.youtube.music") == 0 ||
        strcmp(pkg, "app.morphe.android.apps.youtube.music") == 0) return "YT Music";
    if (strcmp(pkg, "com.google.android.youtube") == 0 ||
        strcmp(pkg, "app.revanced.android.youtube") == 0) return "YouTube";
    if (strcmp(pkg, "org.videolan.vlc") == 0) return "VLC";
    if (strcmp(pkg, "com.apple.android.music") == 0) return "Apple Music";

    char copy[128];
    snprintf(copy, sizeof(copy), "%s", pkg ? pkg : "");
    const char *last = NULL;
    char *save = NULL;
    char *tok = strtok_r(copy, ".", &save);
    while (tok) {
        if (strcmp(tok, "com") != 0 && strcmp(tok, "org") != 0 &&
            strcmp(tok, "app") != 0 && strcmp(tok, "android") != 0 &&
            strcmp(tok, "apps") != 0 && strcmp(tok, "music") != 0) {
            last = tok;
        }
        tok = strtok_r(NULL, ".", &save);
    }
    if (last && *last) {
        snprintf(tmp, cap, "%s", last);
        tmp[0] = (char)toupper((unsigned char)tmp[0]);
        return tmp;
    }
    return (pkg && *pkg) ? pkg : "Media";
}

static void fmt_time(int64_t sec, char *out, size_t cap) {
    if (sec < 0) sec = 0;
    int64_t m = sec / 60;
    int64_t s = sec % 60;
    int64_t h = m / 60;
    m = m % 60;
    if (h > 0) snprintf(out, cap, "%lld:%02lld:%02lld", (long long)h, (long long)m, (long long)s);
    else snprintf(out, cap, "%lld:%02lld", (long long)m, (long long)s);
}

static void parse_description(const char *desc, char *title, size_t tcap,
                              char *artist, size_t acap, char *album, size_t lcap) {
    title[0] = artist[0] = album[0] = '\0';
    if (!desc || !*desc || strcmp(desc, "null") == 0) return;

    /* MediaDescription.toString() joins title, artist, album with ", ". */
    const char *sep2 = NULL, *sep1 = NULL;
    const char *p = desc;
    while ((p = strstr(p, ", ")) != NULL) {
        sep1 = sep2;
        sep2 = p;
        p += 2;
    }
    if (!sep2) {
        if (strcmp(desc, "null") != 0) snprintf(title, tcap, "%s", desc);
    } else if (!sep1) {
        size_t l1 = (size_t)(sep2 - desc);
        if (l1 >= tcap) l1 = tcap - 1;
        memcpy(title, desc, l1);
        title[l1] = '\0';
        if (strcmp(title, "null") == 0) title[0] = '\0';
        const char *a = sep2 + 2;
        if (strcmp(a, "null") != 0) snprintf(artist, acap, "%s", a);
    } else {
        size_t l1 = (size_t)(sep1 - desc);
        if (l1 >= tcap) l1 = tcap - 1;
        memcpy(title, desc, l1);
        title[l1] = '\0';
        if (strcmp(title, "null") == 0) title[0] = '\0';

        size_t l2 = (size_t)(sep2 - (sep1 + 2));
        if (l2 >= acap) l2 = acap - 1;
        memcpy(artist, sep1 + 2, l2);
        artist[l2] = '\0';
        if (strcmp(artist, "null") == 0) artist[0] = '\0';

        const char *al = sep2 + 2;
        if (strcmp(al, "null") != 0) snprintf(album, lcap, "%s", al);
    }
}

static void emit_media_json(bool available, bool playing, const char *state, const char *pkg,
                            const char *app, const char *tag, const char *title,
                            const char *artist, const char *album, int64_t pos_sec, const char *pos_text) {
    printf("{\"kind\":\"media\",\"available\":%s,\"playing\":%s,\"state\":",
           available ? "true" : "false", playing ? "true" : "false");
    json_write_str(stdout, state);
    fputs(",\"package\":", stdout); json_write_str(stdout, pkg);
    fputs(",\"app\":", stdout); json_write_str(stdout, app);
    fputs(",\"tag\":", stdout); json_write_str(stdout, tag);
    fputs(",\"title\":", stdout); json_write_str(stdout, title);
    fputs(",\"artist\":", stdout); json_write_str(stdout, artist);
    fputs(",\"album\":", stdout); json_write_str(stdout, album);
    printf(",\"pos_sec\":%lld,\"pos_text\":", (long long)pos_sec);
    json_write_str(stdout, pos_text);
    fputs("}\n", stdout);
    fflush(stdout);
}

static void query_and_emit_media(RishPipe *rp) {
    char *raw = NULL;
    if (!rish_exec_framed(rp, "echo UPTIME:$(cat /proc/uptime 2>/dev/null); dumpsys media_session 2>/dev/null", &raw, 3000)) {
        emit_media_json(false, false, "SHIZUKU OFF", "", "Media Control", "",
                        "Shizuku inactive", "Start Shizuku to control media", "", 0, "--:--");
        return;
    }

    int64_t uptime_ms = 0;
    char btn_pkg[128] = "", btn_tag[128] = "";
    const char *mbtn = strstr(raw, "Media button session is ");
    if (mbtn) {
        mbtn += 24;
        const char *s1 = strchr(mbtn, '/');
        const char *eol = strpbrk(mbtn, "\r\n");
        if (s1 && (!eol || s1 < eol)) {
            size_t pl = (size_t)(s1 - mbtn);
            if (pl < sizeof(btn_pkg)) { memcpy(btn_pkg, mbtn, pl); btn_pkg[pl] = '\0'; }
            const char *s2 = strchr(s1 + 1, '/');
            if (s2 && (!eol || s2 < eol)) {
                size_t tl = (size_t)(s2 - (s1 + 1));
                if (tl < sizeof(btn_tag)) { memcpy(btn_tag, s1 + 1, tl); btn_tag[tl] = '\0'; }
            }
        }
    }

    MediaSession sessions[16];
    memset(sessions, 0, sizeof(sessions));
    int n_sess = 0;
    MediaSession *cur = NULL;
    bool in_stack = false;

    char *line = raw;
    while (line && *line) {
        char *nl = strchr(line, '\n');
        if (nl) *nl = '\0';
        size_t ll = strlen(line);
        while (ll > 0 && (line[ll - 1] == '\r' || line[ll - 1] == ' ')) line[--ll] = '\0';

        if (strncmp(line, "UPTIME:", 7) == 0 && uptime_ms == 0) {
            uptime_ms = (int64_t)(strtod(line + 7, NULL) * 1000.0);
        } else if (strstr(line, "Sessions Stack - have")) {
            in_stack = true;
        } else if (in_stack && line[0] != '\0') {
            int indent = 0;
            while (line[indent] == ' ') indent++;
            const char *s = line + indent;
            if (indent <= 2) {
                in_stack = false;
                cur = NULL;
            } else if (indent == 4) {
                if (n_sess < 16) {
                    cur = &sessions[n_sess++];
                    memset(cur, 0, sizeof(*cur));
                    snprintf(cur->state_name, sizeof(cur->state_name), "NONE");
                    const char *uid_p = strstr(s, " (userId=");
                    if (uid_p) {
                        const char *s2 = uid_p;
                        while (s2 > s && *s2 != '/') s2--;
                        const char *s1 = (s2 > s) ? s2 - 1 : s;
                        while (s1 > s && *s1 != '/') s1--;
                        if (*s1 == '/' && *s2 == '/' && s2 > s1) {
                            size_t tl = (size_t)(s2 - (s1 + 1));
                            if (tl >= sizeof(cur->tag)) tl = sizeof(cur->tag) - 1;
                            memcpy(cur->tag, s1 + 1, tl);
                            cur->tag[tl] = '\0';

                            const char *pstart = s1;
                            while (pstart > s && pstart[-1] != ' ') pstart--;
                            size_t pl = (size_t)(s1 - pstart);
                            if (pl >= sizeof(cur->package)) pl = sizeof(cur->package) - 1;
                            memcpy(cur->package, pstart, pl);
                            cur->package[pl] = '\0';
                        }
                    }
                } else {
                    cur = NULL;
                }
            } else if (cur && indent >= 6) {
                if (strncmp(s, "package=", 8) == 0) {
                    snprintf(cur->package, sizeof(cur->package), "%s", s + 8);
                } else if (strncmp(s, "active=", 7) == 0) {
                    cur->active = (strcasecmp(s + 7, "true") == 0);
                } else if (strncmp(s, "state=PlaybackState", 19) == 0) {
                    const char *sp = strstr(s, "state=");
                    sp = sp ? strstr(sp + 6, "state=") : NULL;
                    if (sp) {
                        sp += 6;
                        const char *op = strchr(sp, '(');
                        if (op && op > sp) {
                            size_t sl = (size_t)(op - sp);
                            if (sl >= sizeof(cur->state_name)) sl = sizeof(cur->state_name) - 1;
                            memcpy(cur->state_name, sp, sl);
                            cur->state_name[sl] = '\0';
                            cur->state_code = atoi(op + 1);
                        }
                    }
                    const char *pp = strstr(s, "position=");
                    if (pp) cur->pos_ms = strtoll(pp + 9, NULL, 10);
                    const char *vp = strstr(s, "speed=");
                    if (vp) cur->speed = strtod(vp + 6, NULL);
                    const char *up = strstr(s, "updated=");
                    if (up) cur->updated_ms = strtoll(up + 8, NULL, 10);
                } else if (strncmp(s, "metadata:", 9) == 0) {
                    const char *dp = strstr(s, "description=");
                    if (dp) {
                        parse_description(dp + 12,
                                          cur->title, sizeof(cur->title),
                                          cur->artist, sizeof(cur->artist),
                                          cur->album, sizeof(cur->album));
                    }
                }
            }
        }
        line = nl ? (nl + 1) : NULL;
    }

    int best_idx = -1, best_score = -1;
    for (int i = 0; i < n_sess; i++) {
        MediaSession *ms = &sessions[i];
        bool usable = ms->title[0] != '\0' || ms->state_code == 2 || ms->state_code == 3 || ms->state_code == 6;
        if (!usable) continue;
        int sc = (ms->state_code == 3 ? 1000 : 0)
               + (strstr(ms->package, "spotify") ? 100 : 0)
               + ((strcmp(ms->package, btn_pkg) == 0 && strcmp(ms->tag, btn_tag) == 0) ? 10 : 0)
               + (ms->active ? 1 : 0);
        if (sc > best_score) {
            best_score = sc;
            best_idx = i;
        }
    }

    if (best_idx < 0) {
        emit_media_json(true, false, "IDLE", "", "Media Control", "",
                        "Nothing Playing", "Open Spotify or a media app", "", 0, "0:00");
        free(raw);
        return;
    }

    MediaSession *ch = &sessions[best_idx];
    bool playing = (ch->state_code == 3 || ch->state_code == 6);
    int64_t pos_ms = ch->pos_ms;
    if (ch->state_code == 3 && ch->updated_ms > 0 && ch->speed > 0.0 && uptime_ms >= ch->updated_ms) {
        pos_ms = pos_ms + (int64_t)((double)(uptime_ms - ch->updated_ms) * ch->speed);
        if (pos_ms < 0) pos_ms = 0;
    }
    int64_t pos_sec = pos_ms / 1000;
    char pos_text[32], app_tmp[64];
    fmt_time(pos_sec, pos_text, sizeof(pos_text));
    const char *app = app_label_for(ch->package, app_tmp, sizeof(app_tmp));
    const char *title = ch->title[0] ? ch->title : app;

    emit_media_json(true, playing, ch->state_name, ch->package, app, ch->tag,
                    title, ch->artist, ch->album, pos_sec, pos_text);
    free(raw);
}

static bool valid_tag(const char *tag) {
    if (!tag || !*tag) return false;
    for (const char *p = tag; *p; p++) {
        if (!isalnum((unsigned char)*p) && *p != '.' && *p != '_' && *p != '-' && *p != ' ') {
            return false;
        }
    }
    return true;
}

static void dispatch_media_action(RishPipe *rp, const char *act, const char *was_playing, const char *tag) {
    if (strcmp(act, "play") != 0 && strcmp(act, "pause") != 0 &&
        strcmp(act, "play-pause") != 0 && strcmp(act, "next") != 0 &&
        strcmp(act, "previous") != 0 && strcmp(act, "stop") != 0) {
        return;
    }

    char cmd[512];
    if (valid_tag(tag)) {
        const char *mon_cmd = act;
        if (strcmp(act, "play-pause") == 0) {
            mon_cmd = (was_playing && strcmp(was_playing, "1") == 0) ? "pause" : "play";
        }
        if (strcmp(mon_cmd, "play") == 0 || strcmp(mon_cmd, "pause") == 0 ||
            strcmp(mon_cmd, "next") == 0 || strcmp(mon_cmd, "previous") == 0) {
            snprintf(cmd, sizeof(cmd),
                     "printf '%s\\nq\\n' | cmd media_session monitor '%s' >/dev/null 2>&1 || "
                     "cmd media_session dispatch %s >/dev/null 2>&1",
                     mon_cmd, tag, act);
        } else {
            snprintf(cmd, sizeof(cmd), "cmd media_session dispatch %s >/dev/null 2>&1", act);
        }
    } else {
        snprintf(cmd, sizeof(cmd), "cmd media_session dispatch %s >/dev/null 2>&1", act);
    }

    char *ignored = NULL;
    if (rish_exec_framed(rp, cmd, &ignored, 2500)) free(ignored);
    sleep_check_ms(220);
    query_and_emit_media(rp);
}

static void emit_focus_json(bool available, int zen, int notif_count, const char *label) {
    printf("{\"kind\":\"focus\",\"available\":%s,\"zen\":%d,\"dnd\":%s,\"notif_count\":%d,\"label\":",
           available ? "true" : "false", zen, zen > 0 ? "true" : "false", notif_count);
    json_write_str(stdout, label);
    fputs("}\n", stdout);
    fflush(stdout);
}

static const char *zen_label_for(int zen) {
    if (zen == 1) return "Priority Only";
    if (zen == 2) return "Total Silence";
    if (zen == 3) return "Alarms Only";
    return "Off";
}

static int query_zen_raw(RishPipe *rp, int *zen_out, int *notif_out) {
    char *raw = NULL;
    if (!rish_exec_framed(rp, "echo ZEN:$(settings get global zen_mode 2>/dev/null); echo NOTIFS:$(cmd notification list 2>/dev/null | grep -c '|')", &raw, 2500)) {
        return -1;
    }
    int zen = 0, notifs = 0;
    char *line = raw;
    while (line && *line) {
        char *nl = strchr(line, '\n');
        if (nl) *nl = '\0';
        if (strncmp(line, "ZEN:", 4) == 0) {
            zen = atoi(line + 4);
        } else if (strncmp(line, "NOTIFS:", 7) == 0) {
            notifs = atoi(line + 7);
        }
        line = nl ? (nl + 1) : NULL;
    }
    free(raw);
    if (zen_out) *zen_out = zen;
    if (notif_out) *notif_out = notifs;
    return 0;
}

static void query_and_emit_focus(RishPipe *rp) {
    int zen = 0, notifs = 0;
    if (query_zen_raw(rp, &zen, &notifs) != 0) {
        emit_focus_json(false, 0, 0, "Shizuku Off");
        return;
    }
    emit_focus_json(true, zen, notifs, zen_label_for(zen));
}

static void toggle_focus(RishPipe *rp) {
    int zen = 0, notifs = 0;
    if (query_zen_raw(rp, &zen, &notifs) != 0) {
        emit_focus_json(false, 0, 0, "Shizuku Off");
        return;
    }
    const char *cmd = (zen == 0)
        ? "cmd notification set_dnd priority >/dev/null 2>&1"
        : "cmd notification set_dnd off >/dev/null 2>&1";
    char *ignored = NULL;
    if (rish_exec_framed(rp, cmd, &ignored, 2500)) free(ignored);
    sleep_check_ms(120);
    query_and_emit_focus(rp);
}

static void query_and_emit_calendar(RishPipe *rp, int64_t start_ms, int64_t end_ms) {
    if (start_ms <= 0 || end_ms <= start_ms) {
        int64_t now_s = (int64_t)time(NULL);
        start_ms = (now_s - 14LL * 86400LL) * 1000LL;
        end_ms = (now_s + 90LL * 86400LL) * 1000LL;
    }

    char cmd[320];
    snprintf(cmd, sizeof(cmd),
             "content query --uri \"content://com.android.calendar/instances/when/%lld/%lld\" "
             "--projection title:begin:end:allDay:calendar_id --sort \"begin ASC\" 2>/dev/null",
             (long long)start_ms, (long long)end_ms);

    char *raw = NULL;
    if (!rish_exec_framed(rp, cmd, &raw, 3000)) {
        printf("{\"kind\":\"calendar\",\"ok\":false,\"start_ms\":%lld,\"end_ms\":%lld,\"events\":[]}\n",
               (long long)start_ms, (long long)end_ms);
        fflush(stdout);
        return;
    }

    printf("{\"kind\":\"calendar\",\"ok\":true,\"start_ms\":%lld,\"end_ms\":%lld,\"events\":[",
           (long long)start_ms, (long long)end_ms);

    int count = 0;
    char *line = raw;
    while (line && *line && count < 96) {
        char *nl = strchr(line, '\n');
        if (nl) *nl = '\0';
        size_t ll = strlen(line);
        while (ll > 0 && (line[ll - 1] == '\r' || line[ll - 1] == ' ')) line[--ll] = '\0';

        char *tp = strstr(line, "title=");
        char *cp = strstr(line, ", calendar_id=");
        char *ap = cp ? strstr(line, ", allDay=") : NULL;
        char *ep = ap ? strstr(line, ", end=") : NULL;
        char *bp = ep ? strstr(line, ", begin=") : NULL;

        if (tp && bp && ep && ap && cp && tp < bp && bp < ep && ep < ap && ap < cp) {
            *bp = '\0';
            const char *title = tp + 6;
            int64_t begin_ms = strtoll(bp + 8, NULL, 10);
            int64_t ev_end_ms = strncmp(ep + 6, "NULL", 4) == 0 ? 0 : strtoll(ep + 6, NULL, 10);
            int all_day = atoi(ap + 9);
            int cal_id = atoi(cp + 14);

            printf("%s{\"title\":", count > 0 ? "," : "");
            json_write_str(stdout, title);
            printf(",\"begin_ms\":%lld,\"end_ms\":%lld,\"all_day\":%s,\"cal_id\":%d}",
                   (long long)begin_ms, (long long)ev_end_ms, all_day ? "true" : "false", cal_id);
            count++;
        }
        line = nl ? (nl + 1) : NULL;
    }
    fputs("]}\n", stdout);
    fflush(stdout);
    free(raw);
}

static int cmd_media_stream(void) {
    RishPipe rp = { .pid = -1, .to_fd = -1, .from_fd = -1, .seq = 0 };
    query_and_emit_media(&rp);
    query_and_emit_focus(&rp);
    query_and_emit_calendar(&rp, 0, 0);

    char in_buf[1024];
    size_t in_len = 0;
    while (g_running) {
        struct pollfd pfd = { .fd = STDIN_FILENO, .events = POLLIN };
        int rc = poll(&pfd, 1, 500);
        if (rc < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (rc == 0) {
            if (rp.pid > 0 && waitpid(rp.pid, NULL, WNOHANG) != 0) {
                rish_close(&rp);
            }
            continue;
        }
        if (pfd.revents & (POLLIN | POLLHUP)) {
            ssize_t r = read(STDIN_FILENO, in_buf + in_len, sizeof(in_buf) - 1 - in_len);
            if (r <= 0) break;
            in_len += (size_t)r;
            in_buf[in_len] = '\0';

            char *nl;
            char *cur = in_buf;
            while ((nl = strchr(cur, '\n')) != NULL) {
                *nl = '\0';
                size_t l = strlen(cur);
                while (l > 0 && (cur[l - 1] == '\r' || cur[l - 1] == ' ')) cur[--l] = '\0';
                if (strcmp(cur, "status") == 0) {
                    query_and_emit_media(&rp);
                } else if (strcmp(cur, "focus-status") == 0) {
                    query_and_emit_focus(&rp);
                } else if (strcmp(cur, "focus-toggle") == 0) {
                    toggle_focus(&rp);
                } else if (strcmp(cur, "calendar") == 0 || strncmp(cur, "calendar\t", 9) == 0) {
                    int64_t s_ms = 0, e_ms = 0;
                    if (cur[8] == '\t') {
                        char *t2 = strchr(cur + 9, '\t');
                        if (t2) {
                            *t2++ = '\0';
                            s_ms = strtoll(cur + 9, NULL, 10);
                            e_ms = strtoll(t2, NULL, 10);
                        }
                    }
                    query_and_emit_calendar(&rp, s_ms, e_ms);
                } else if (*cur) {
                    char *t1 = strchr(cur, '\t');
                    char *t2 = t1 ? strchr(t1 + 1, '\t') : NULL;
                    if (t1) *t1++ = '\0';
                    if (t2) *t2++ = '\0';
                    dispatch_media_action(&rp, cur, t1 ? t1 : "", t2 ? t2 : "");
                }
                cur = nl + 1;
            }
            size_t rem = strlen(cur);
            memmove(in_buf, cur, rem);
            in_len = rem;
        }
    }

    rish_close(&rp);
    return 0;
}

static int cmd_media_status(void) {
    RishPipe rp = { .pid = -1, .to_fd = -1, .from_fd = -1, .seq = 0 };
    query_and_emit_media(&rp);
    rish_close(&rp);
    return 0;
}

static int cmd_focus_status(void) {
    RishPipe rp = { .pid = -1, .to_fd = -1, .from_fd = -1, .seq = 0 };
    query_and_emit_focus(&rp);
    rish_close(&rp);
    return 0;
}

static int cmd_focus_toggle(void) {
    RishPipe rp = { .pid = -1, .to_fd = -1, .from_fd = -1, .seq = 0 };
    toggle_focus(&rp);
    rish_close(&rp);
    return 0;
}

static int cmd_calendar(int argc, char **argv) {
    int64_t s_ms = (argc >= 4) ? strtoll(argv[2], NULL, 10) : 0;
    int64_t e_ms = (argc >= 4) ? strtoll(argv[3], NULL, 10) : 0;
    RishPipe rp = { .pid = -1, .to_fd = -1, .from_fd = -1, .seq = 0 };
    query_and_emit_calendar(&rp, s_ms, e_ms);
    rish_close(&rp);
    return 0;
}

int main(int argc, char **argv) {
    install_signals();
    if (argc < 2) {
        fprintf(stderr, "usage: qs-native <cpu|sys-diag|hide-cursor|submenu-watch|wl-workspaces|media-stream|media-status|focus-status|focus-toggle|calendar>\n");
        return 2;
    }
    const char *sub = argv[1];
    if (strcmp(sub, "cpu") == 0) return cmd_cpu();
    if (strcmp(sub, "sys-diag") == 0) return cmd_sys_diag();
    if (strcmp(sub, "hide-cursor") == 0) return cmd_hide_cursor();
    if (strcmp(sub, "submenu-watch") == 0) return cmd_submenu_watch(argc, argv);
    if (strcmp(sub, "wl-workspaces") == 0) return cmd_wl_workspaces();
    if (strcmp(sub, "media-stream") == 0) return cmd_media_stream();
    if (strcmp(sub, "media-status") == 0) return cmd_media_status();
    if (strcmp(sub, "focus-status") == 0) return cmd_focus_status();
    if (strcmp(sub, "focus-toggle") == 0) return cmd_focus_toggle();
    if (strcmp(sub, "calendar") == 0) return cmd_calendar(argc, argv);

    fprintf(stderr, "qs-native: unknown subcommand '%s'\n", sub);
    return 2;
}
