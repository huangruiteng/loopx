//! Install only the runtime snapshot carried by the signature-verified App.
use command_group::CommandGroup;
use flate2::read::GzDecoder;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::Path,
    process::{Command, Stdio},
    time::{Duration, Instant},
};
use tauri::{AppHandle, Manager};

pub fn identity(app: &AppHandle) -> Result<Value, String> {
    let path = app
        .path()
        .resource_dir()
        .map_err(|_| "runtime_bundle_missing")?
        .join("runtime/identity.json");
    let value: Value =
        serde_json::from_slice(&fs::read(path).map_err(|_| "runtime_bundle_missing")?)
            .map_err(|_| "runtime_bundle_invalid")?;
    if value["schema_version"] != "desktop_runtime_bundle_v1"
        || !value["source_revision"]
            .as_str()
            .is_some_and(|v| v.len() == 40 && v.bytes().all(|c| c.is_ascii_hexdigit()))
    {
        return Err("runtime_bundle_invalid".into());
    }
    Ok(value)
}

pub fn journal(app: &AppHandle) -> Result<std::path::PathBuf, String> {
    let dir = app
        .path()
        .app_local_data_dir()
        .map_err(|_| "update_state_unavailable")?;
    fs::create_dir_all(&dir).map_err(|_| "update_state_unavailable")?;
    Ok(dir.join("desktop-update.json"))
}

pub fn record_pending(app: &AppHandle, version: &str, channel: &str) -> Result<(), String> {
    let path = journal(app)?;
    let mut file = tempfile::NamedTempFile::new_in(path.parent().unwrap())
        .map_err(|_| "update_state_unavailable")?;
    use std::io::Write;
    file.write_all(
        json!({"version": version, "channel": channel})
            .to_string()
            .as_bytes(),
    )
    .map_err(|_| "update_state_unavailable")?;
    file.as_file()
        .sync_all()
        .map_err(|_| "update_state_unavailable")?;
    file.persist(path).map_err(|_| "update_state_unavailable")?;
    Ok(())
}

pub fn resume_pending(app: &AppHandle) -> Result<(), String> {
    let path = journal(app)?;
    if !path.exists() {
        return Ok(());
    }
    let state: Value =
        serde_json::from_slice(&fs::read(&path).map_err(|_| "update_state_unavailable")?)
            .map_err(|_| "update_state_invalid")?;
    // Never install runtime code from an App other than the approved target.
    if state["version"] != app.package_info().version.to_string() {
        return Err("app_update_incomplete".into());
    }
    install(app)?;
    fs::remove_file(path).map_err(|_| "update_state_unavailable")?;
    Ok(())
}

pub fn install(app: &AppHandle) -> Result<(), String> {
    let metadata = identity(app)?;
    let archive = app
        .path()
        .resource_dir()
        .map_err(|_| "runtime_bundle_missing")?
        .join("runtime/runtime-source.tar.gz");
    let bytes = fs::read(archive).map_err(|_| "runtime_bundle_missing")?;
    install_snapshot(&bytes, &metadata)
}

fn install_snapshot(bytes: &[u8], metadata: &Value) -> Result<(), String> {
    let digest: String = Sha256::digest(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect();
    if digest != metadata["sha256"].as_str().unwrap_or("") {
        return Err("runtime_bundle_invalid".into());
    }
    let source = tempfile::tempdir().map_err(|_| "runtime_staging_failed")?;
    extract(bytes, source.path())?;
    #[cfg(not(windows))]
    let mut command = {
        let mut c = Command::new("bash");
        c.arg(source.path().join("scripts/install-local.sh"));
        c
    };
    #[cfg(windows)]
    let mut command = {
        let mut c = Command::new("pwsh");
        c.args(["-NoProfile", "-File"])
            .arg(source.path().join("scripts/install-windows.ps1"));
        c
    };
    // Preserve the working interpreter of an existing managed snapshot.
    if let Ok(executable) = fs::canonicalize(crate::services::loopx_executable()) {
        if let Some(release) = executable.parent().and_then(Path::parent) {
            if let Ok(python) = fs::read_to_string(release.join(".loopx-python")) {
                command.env("LOOPX_PYTHON", python.trim());
            }
        }
    }
    command
        .current_dir(source.path())
        .env("LOOPX_PROMOTE_DEFAULT", "1")
        // The archive staging directory is temporary, never a canary checkout.
        .env("LOOPX_INSTALL_CANARY", "0")
        .env_remove("LOOPX_ARCHIVE_URL")
        .env_remove("LOOPX_ARCHIVE_SHA256")
        .env("LOOPX_REPO", "huangruiteng/loopx")
        .env("LOOPX_REF", metadata["source_revision"].as_str().unwrap())
        .env(
            "LOOPX_RESOLVED_SOURCE_GIT_COMMIT",
            metadata["source_revision"].as_str().unwrap(),
        )
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(test)]
    command.stderr(Stdio::inherit());
    let mut child = command
        .group_spawn()
        .map_err(|_| "runtime_installer_unavailable")?;
    let started = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => {
                return if status.success() {
                    let installed = crate::services::runtime_identity_for_executable(
                        &crate::services::loopx_executable(),
                    );
                    if installed.as_ref().map(|v| &v["source_revision"])
                        == Some(&metadata["source_revision"])
                    {
                        Ok(())
                    } else {
                        Err("runtime_identity_mismatch".into())
                    }
                } else {
                    Err(format!(
                        "runtime_install_exit_{}",
                        status
                            .code()
                            .map(|code| code.to_string())
                            .unwrap_or_else(|| "signal".into())
                    ))
                }
            }
            Ok(None) if started.elapsed() < Duration::from_secs(600) => {
                std::thread::sleep(Duration::from_millis(100))
            }
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                return Err("runtime_install_timeout".into());
            }
        }
    }
}

fn extract(bytes: &[u8], destination: &Path) -> Result<(), String> {
    let mut archive = tar::Archive::new(GzDecoder::new(bytes));
    for item in archive.entries().map_err(|_| "runtime_bundle_invalid")? {
        let mut entry = item.map_err(|_| "runtime_bundle_invalid")?;
        // Git archive includes a global PAX header with the commit comment.
        // It carries metadata only; never unpack it as a filesystem entry.
        if entry.header().entry_type().is_pax_global_extensions() {
            continue;
        }
        // Git snapshots need files and directories only. Never materialize links,
        // devices or a path escaping the dedicated staging directory.
        if !entry.header().entry_type().is_file() && !entry.header().entry_type().is_dir() {
            return Err("runtime_bundle_invalid".into());
        }
        if !entry
            .unpack_in(destination)
            .map_err(|_| "runtime_bundle_invalid")?
        {
            return Err("runtime_bundle_invalid".into());
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    #[ignore = "requires isolated installer paths and a built App runtime bundle"]
    fn real_bundled_installer_qualifies_selected_cli() {
        let root = std::env::var("LOOPX_TEST_BUNDLE").expect("isolated bundle path");
        for key in [
            "LOOPX_BIN",
            "LOOPX_BIN_DIR",
            "LOOPX_RELEASES_DIR",
            "LOOPX_REGISTRY",
            "LOOPX_RUNTIME_ROOT",
            "LOOPX_MAN_DIR",
            "LOOPX_SKILLS_DIR",
        ] {
            assert!(
                std::env::var(key).is_ok(),
                "explicit isolated {key} required"
            );
        }
        let root = Path::new(&root);
        let metadata: Value =
            serde_json::from_slice(&fs::read(root.join("identity.json")).unwrap()).unwrap();
        let bytes = fs::read(root.join("runtime-source.tar.gz")).unwrap();
        install_snapshot(&bytes, &metadata).unwrap();
    }
    #[test]
    fn corrupt_archive_cannot_reach_installer() {
        let dir = tempfile::tempdir().unwrap();
        assert!(extract(b"not a tar", dir.path()).is_err());
    }
    #[test]
    fn symlinks_cannot_escape_runtime_staging() {
        use flate2::{write::GzEncoder, Compression};
        let compressed = GzEncoder::new(Vec::new(), Compression::default());
        let mut archive = tar::Builder::new(compressed);
        let mut header = tar::Header::new_gnu();
        header.set_entry_type(tar::EntryType::Symlink);
        header.set_size(0);
        archive
            .append_link(&mut header, "escape", "../../outside")
            .unwrap();
        let bytes = archive.into_inner().unwrap().finish().unwrap();
        let dir = tempfile::tempdir().unwrap();
        assert!(extract(&bytes, dir.path()).is_err());
        assert!(!dir.path().join("escape").exists());
    }
    #[test]
    fn long_path_metadata_headers_install_as_plain_files() {
        // `git archive` emits a PAX local header ('x') for paths beyond ustar
        // capacity; GNU writers emit longname records ('L') instead. This
        // non-raw iterator folds both into the entry that follows, so such
        // snapshots are exactly what the App installs: this test is the
        // extractor half of the acceptance matrix the build-side gate in
        // scripts/desktop_runtime_bundle.py mirrors. An ustar header makes
        // the builder fall back to a PAX record; a GNU header to longname.
        use flate2::{write::GzEncoder, Compression};
        for new_header in [tar::Header::new_ustar, tar::Header::new_gnu] {
            let deep = format!("docs/{}long-path.md", "very/deep/".repeat(16));
            let compressed = GzEncoder::new(Vec::new(), Compression::default());
            let mut archive = tar::Builder::new(compressed);
            let mut header = new_header();
            header.set_size(6);
            header.set_mode(0o644);
            archive
                .append_data(&mut header, &deep, &b"hello!"[..])
                .unwrap();
            let bytes = archive.into_inner().unwrap().finish().unwrap();
            let dir = tempfile::tempdir().unwrap();
            assert!(extract(&bytes, dir.path()).is_ok(), "{deep}");
            assert_eq!(fs::read(dir.path().join(&deep)).unwrap(), b"hello!");
        }
    }
}
