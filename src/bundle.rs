//! The application bundle's own start -- what a shell script did until 18 November 2026.
//!
//! `Orrery.app` used to start through `Contents/MacOS/launch`, four lines of sh that put
//! `~/.local/bin` and Homebrew on the PATH, sent what orrery says to `~/Library/Logs/orrery.log`
//! and exec'd the binary with the options the app was installed with. It worked, and it cost the
//! application its name.
//!
//! macOS DECIDES WHO MAY REACH THE LOCAL NETWORK BY THE PROGRAM A BUNDLE DECLARES AS ITS OWN. It
//! reads `CFBundleExecutable`, takes that file's Mach-O UUID, and files the grant under the
//! bundle's identifier with that UUID beside it. A shell script has no UUID. So the bundle
//! `org.copal.orrery` was on record as an application with no code ("0 UUIDs for
//! org.copal.orrery"), and the process that actually asked -- this binary, exec'd by the script --
//! was a stranger found only by its path, filed under a name made from its own build
//! (`orrery-55554944...`). Thirty-eight such names were on this Mac's list on the day, one a
//! build, and the grant always belonged to an earlier one. The console's every connection, and
//! every connection of the keeper it starts, was refused before a packet left: "host unreachable"
//! for machines that were up. `docs/local-signing-lab-report.md` is the account.
//!
//! So the binary is the bundle's executable now, and does the script's three small jobs itself.
//! Finder starts an application with no arguments; the ones it was installed with are in
//! `Contents/Resources/arguments`, one a line. Started with arguments of its own -- from a
//! terminal, by the path inside the bundle -- it is an ordinary program and none of this happens.
//!
//! Rejected: `LSEnvironment` in Info.plist for the PATH (it cannot say `$HOME`, and it does
//! nothing for the arguments or the log); a compiled launcher that execs the binary (a second
//! program to sign, and exec replaces the image, so the UUID macOS sees is again not the
//! bundle's).

use std::path::{Path, PathBuf};

/// `Orrery.app/Contents/Resources`, if `exe` is `Orrery.app/Contents/MacOS/<something>`.
/// Anywhere else -- `~/.local/bin/orrery`, `target/release/orrery` -- there is no bundle.
pub fn resources(exe: &Path) -> Option<PathBuf> {
    let macos = exe.parent()?;
    let contents = macos.parent()?;
    let app = contents.parent()?;
    let named = |p: &Path, want: &str| p.file_name().map(|n| n == want).unwrap_or(false);
    if named(macos, "MacOS") && named(contents, "Contents") && app.extension().map(|e| e == "app").unwrap_or(false) {
        Some(contents.join("Resources"))
    } else {
        None
    }
}

/// One argument a line. A blank line is not an argument: nothing orrery takes is empty, and a
/// file that ends in a newline must not hand `main` a trailing "".
pub fn arguments(text: &str) -> Vec<String> {
    text.lines().filter(|l| !l.is_empty()).map(str::to_string).collect()
}

/// The PATH an application opened from Finder needs: Finder gives `/usr/bin:/bin:/usr/sbin:/sbin`,
/// and `copal`, `python3` and `ssh-keygen` from Homebrew are not on it.
pub fn path(home: &str, old: &str) -> String {
    format!("{home}/.local/bin:/opt/homebrew/bin:/usr/local/bin:{old}")
}

/// The arguments to run with. `given` wins when there are any; otherwise, inside a bundle, the
/// installed ones -- and then the PATH and the log are set as the launcher set them.
pub fn start(given: Vec<String>) -> Vec<String> {
    if !given.is_empty() {
        return given;
    }
    let Some(dir) = std::env::current_exe().ok().and_then(|e| resources(&e)) else {
        return given;
    };
    let Ok(text) = std::fs::read_to_string(dir.join("arguments")) else {
        return given;
    };
    let home = std::env::var("HOME").unwrap_or_default();
    std::env::set_var("PATH", path(&home, &std::env::var("PATH").unwrap_or_default()));
    log_to(&Path::new(&home).join("Library/Logs/orrery.log"));
    arguments(&text)
}

/// Standard output and error go to the log, appended, as `>>log 2>&1` did. If the log cannot be
/// opened the application starts anyway and says what it says to nobody: a window that does not
/// open because a log directory is missing would be the worse fault.
#[cfg(unix)]
fn log_to(log: &Path) {
    use std::os::fd::AsRawFd;
    extern "C" {
        fn dup2(from: std::ffi::c_int, to: std::ffi::c_int) -> std::ffi::c_int;
    }
    if let Some(dir) = log.parent() {
        let _ = std::fs::create_dir_all(dir);
    }
    if let Ok(f) = std::fs::OpenOptions::new().create(true).append(true).open(log) {
        // SAFETY: both descriptors are open and owned by this process; dup2 closes 1 and 2 and
        // points them at the file, which stays open through them after `f` is dropped.
        unsafe {
            dup2(f.as_raw_fd(), 1);
            dup2(f.as_raw_fd(), 2);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_binary_inside_an_application_finds_the_bundles_resources() {
        let r = resources(Path::new("/Applications/Orrery.app/Contents/MacOS/orrery"));
        assert_eq!(r, Some(PathBuf::from("/Applications/Orrery.app/Contents/Resources")));
    }

    #[test]
    fn a_binary_on_the_path_is_in_no_bundle() {
        assert_eq!(resources(Path::new("/Users/paul/.local/bin/orrery")), None);
        assert_eq!(resources(Path::new("/Users/paul/code/orrery/target/release/orrery")), None);
        // A folder that only looks like one: MacOS under Contents, and no .app above them.
        assert_eq!(resources(Path::new("/tmp/Contents/MacOS/orrery")), None);
    }

    #[test]
    fn arguments_are_one_a_line_and_keep_their_spaces() {
        let a = arguments("--gui\n--fleet-cmd\n/Users/paul/.local/bin/copal fleet\n--queue\n/q/grove\n");
        assert_eq!(a, ["--gui", "--fleet-cmd", "/Users/paul/.local/bin/copal fleet", "--queue", "/q/grove"]);
    }

    #[test]
    fn a_trailing_newline_is_not_an_empty_argument() {
        assert_eq!(arguments("--gui\n\n"), ["--gui"]);
        assert!(arguments("").is_empty());
    }

    #[test]
    fn the_path_puts_the_users_own_programs_before_the_systems() {
        assert_eq!(path("/Users/paul", "/usr/bin:/bin"), "/Users/paul/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin");
    }

    #[test]
    fn arguments_given_on_the_command_line_are_the_arguments() {
        // No file is read and nothing is redirected: the test's own output would vanish if it were.
        assert_eq!(start(vec!["--help".into()]), ["--help"]);
    }
}
