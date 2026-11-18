#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdlib.h>

#define DRM_FORMAT_XRGB8888 0x34325258u
#define DRM_FORMAT_ARGB8888 0x34325241u
#define DRM_FORMAT_ABGR8888 0x34324241u
#define WL_OUTPUT_TRANSFORM_NORMAL 0
#define WL_OUTPUT_TRANSFORM_FLIPPED_180 6

__attribute__((constructor))
static void _tgui_fix_init(void) {
    /* Prevent child processes (quickshell, foot, rofi) from inheriting LD_PRELOAD */
    unsetenv("LD_PRELOAD");
}

void wlr_output_state_set_render_format(void *state, uint32_t format) {
    static void (*real_fn)(void *, uint32_t) = NULL;
    if (!real_fn) {
        real_fn = dlsym(RTLD_NEXT, "wlr_output_state_set_render_format");
    }
    if (format == DRM_FORMAT_XRGB8888 || format == DRM_FORMAT_ARGB8888) {
        format = DRM_FORMAT_ABGR8888;
    }
    if (real_fn) {
        real_fn(state, format);
    }
}

void wlr_output_state_set_transform(void *state, int transform) {
    static void (*real_fn)(void *, int) = NULL;
    if (!real_fn) {
        real_fn = dlsym(RTLD_NEXT, "wlr_output_state_set_transform");
    }
    if (transform == WL_OUTPUT_TRANSFORM_NORMAL) {
        transform = WL_OUTPUT_TRANSFORM_FLIPPED_180;
    }
    if (real_fn) {
        real_fn(state, transform);
    }
}
