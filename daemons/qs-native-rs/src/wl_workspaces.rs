/// Encode a Wayland wire protocol header (`object_id`, `(size << 16) | opcode`).
#[allow(dead_code)]
pub fn encode_wl_header(object_id: u32, opcode: u16, payload_len: usize) -> [u8; 8] {
    let total_size = (8 + payload_len) as u32;
    let size_op = (total_size << 16) | u32::from(opcode);
    let mut header = [0u8; 8];
    header[0..4].copy_from_slice(&object_id.to_ne_bytes());
    header[4..8].copy_from_slice(&size_op.to_ne_bytes());
    header
}

pub fn cmd_wl_workspaces() -> Result<(), String> {
    // TODO: Connect to `$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY` via `UnixStream`,
    // bind `ext_workspace_manager_v1`, emit workspace JSON on `done`, and activate on stdin lines.
    Err("wl-workspaces is not implemented in the Rust rewrite yet".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn encodes_wayland_header_bytes() {
        let hdr = encode_wl_header(1, 1, 4);
        let obj = u32::from_ne_bytes(hdr[0..4].try_into().unwrap());
        let size_op = u32::from_ne_bytes(hdr[4..8].try_into().unwrap());
        assert_eq!(obj, 1);
        assert_eq!(size_op >> 16, 12);
        assert_eq!(size_op & 0xffff, 1);
    }
}
