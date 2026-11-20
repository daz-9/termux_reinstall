# `qs-native` (Rust Rewrite Scaffold)

Incremental Rust rewrite of [`daemons/native/qs_native.c`](../native/qs_native.c), cross-compiled for Termux (`aarch64-linux-android`) via GitHub Actions.

## Commands

```sh
# Run unit tests & lints locally (Windows, Linux, or Termux)
cargo test
cargo clippy --all-targets -- -D warnings

# Try the working `cpu` subcommand
cargo run -- cpu
```

## Porting Roadmap

1. **`cpu`** (`src/proc_stats.rs`) — Done. Reference implementation + unit tests.
2. **`sys-diag`** (`src/sys_diag.rs`) — Reuse `proc_stats` and spawn `termux-battery-status` + `termux-wifi-connectioninfo`.
3. **`media-status` / `focus-*` / `calendar` / `media-stream`** (`src/rish.rs`) — Parsers + unit tests are scaffolded; wire up persistent `rish` child process + stdin reader thread.
4. **`wl-workspaces`** (`src/wl_workspaces.rs`) — Connect to `$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY` over `UnixStream` and bind `ext_workspace_manager_v1`.
5. **`hide-cursor` & `submenu-watch`** (`src/x11.rs`) — Uncomment `x11rb` in `Cargo.toml` and connect via `termux_x11_socket_path()` (`$TMPDIR/.X11-unix/X<num>`).

## CI Cross-Compilation

`.github/workflows/build-qs-native.yml` runs `rustfmt`, `clippy`, and `cargo test`, then cross-compiles `qs-native-aarch64-android` using the runner's Android NDK (`aarch64-linux-android24-clang`).

- Every push/PR touching `daemons/qs-native-rs/` uploads `qs-native-aarch64-android` as a workflow artifact.
- Creating a GitHub Release automatically builds and attaches `qs-native-aarch64-android` to the release.
