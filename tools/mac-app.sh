#!/bin/sh
# mac-app.sh [ORRERY ARGS...] -- install orrery on a Mac: the binary into
# PREFIX/bin (default ~/.local) and Orrery.app into APPDIR (default
# /Applications where it may be written, else ~/Applications), so the window opens from Finder, Launchpad, Spotlight and
# the Dock like any other application.
#
# The arguments are the ones the app starts orrery with; --gui is added if
# they leave it out. With none, the window opens on the fleet alone. The
# grove's console, for instance:
#
#   tools/mac-app.sh --operator paul --fleet grove \
#       --fleet-cmd "$HOME/.local/bin/copal fleet" \
#       --queue "$HOME/code/treadcore/build/queue/grove"
#
# Run it again with options to change them; with none (or `make install`)
# it keeps the last ones, from ~/.config/orrery/app-options.
# An app opened from Finder gets a bare PATH and no terminal, so orrery, started
# inside the bundle with no arguments, puts ~/.local/bin and Homebrew back on the
# PATH and writes what it says to ~/Library/Logs/orrery.log (src/bundle.rs). APPDIR=DIR puts it elsewhere.
# --uninstall removes both.
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PREFIX=${PREFIX:-$HOME/.local}
# The Applications folder Finder shows, where it may be written (an admin
# account); otherwise the user's own. APPDIR= chooses.
if [ -z "${APPDIR:-}" ]; then
    if [ -w /Applications ]; then APPDIR=/Applications; else APPDIR=$HOME/Applications; fi
fi
APP="$APPDIR/Orrery.app"
[ "$(uname -s)" = Darwin ] || { echo "mac-app.sh: this is for macOS" >&2; exit 2; }

if [ "${1:-}" = --uninstall ]; then
    rm -rf "$APP" "$PREFIX/bin/orrery"
    echo "removed $APP and $PREFIX/bin/orrery"
    exit 0
fi

# One argument, quoted for sh.
q() { printf "'%s'" "$(printf %s "$1" | sed "s/'/'\\\\''/g")"; }
# The options are remembered: given none (a plain `make install`), the app
# keeps the last ones it was made with.
OPTS="${XDG_CONFIG_HOME:-$HOME/.config}/orrery/app-options"
if [ $# -eq 0 ] && [ -s "$OPTS" ]; then
    ARGS=$(cat "$OPTS")
else
    ARGS=""
    gui=0
    for a in "$@"; do
        [ "$a" = --gui ] && gui=1
        ARGS="$ARGS $(q "$a")"
    done
    [ $gui = 1 ] || ARGS=" --gui$ARGS"
    mkdir -p "$(dirname "$OPTS")"
    printf '%s' "$ARGS" > "$OPTS"
fi

cd "$ROOT"
# Under the memory guard: a release build beside a full census once ran
# this Mac out of memory (tools/mem-guard.sh).
sh "$ROOT/tools/mem-guard.sh" cargo build --release
VERSION=$(sed -n 's/^version *= *"\(.*\)"/\1/p' Cargo.toml | head -1)

mkdir -p "$PREFIX/bin"
install -m 755 target/release/orrery "$PREFIX/bin/orrery"

# Build the bundle beside the old one and swap, so a failure leaves the old.
NEW="$APP.new"
rm -rf "$NEW"
mkdir -p "$NEW/Contents/MacOS" "$NEW/Contents/Resources"
install -m 755 target/release/orrery "$NEW/Contents/MacOS/orrery"

# The binary is the bundle's executable, and there is no launcher script. There was one until 18
# November 2026 (PATH, the log, the options, then exec), and macOS files an application's grant
# to reach the local network under the Mach-O UUID of the file CFBundleExecutable names: a script
# has none, so the bundle was on record with no code and the binary was a stranger at every build.
# The binary does the script's three jobs itself when it is started with no arguments inside a
# bundle (src/bundle.rs); its options are here, one a line.
( eval "set -- $ARGS"; for a in "$@"; do printf '%s\n' "$a"; done ) > "$NEW/Contents/Resources/arguments"

cat > "$NEW/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>Orrery</string>
    <key>CFBundleDisplayName</key><string>Orrery</string>
    <key>CFBundleIdentifier</key><string>org.copal.orrery</string>
    <key>CFBundleExecutable</key><string>orrery</string>
    <key>CFBundleIconFile</key><string>orrery</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleVersion</key><string>$VERSION</string>
    <key>CFBundleShortVersionString</key><string>$VERSION</string>
    <key>LSMinimumSystemVersion</key><string>11.0</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>NSLocalNetworkUsageDescription</key><string>Orrery reaches the fleet's machines on the local network.</string>
</dict>
</plist>
EOF

# The icon: one drawing at 1024, scaled by sips into the iconset's ten sizes.
SET=$(mktemp -d)/orrery.iconset
mkdir -p "$SET"
python3 "$ROOT/tools/mac-icon.py" "$SET/icon_512x512@2x.png"
for s in 16 32 128 256 512; do
    sips -z $s $s "$SET/icon_512x512@2x.png" --out "$SET/icon_${s}x${s}.png" >/dev/null
    d=$((s * 2))
    [ $s = 512 ] || sips -z $d $d "$SET/icon_512x512@2x.png" --out "$SET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$SET" -o "$NEW/Contents/Resources/orrery.icns"
rm -rf "$(dirname "$SET")"

# Signed by this Mac's own identity (tools/mac-sign.sh), the binary first and then the bundle
# around it (codesign will not seal a bundle whose code inside is unsigned). It was signed ad hoc
# until 18 November 2026, and an ad hoc signature's requirement is the build's own hash: macOS took
# every install for a new application and the grant to reach the local network went with the old
# one. The identity's requirement names the signer, so the grant is asked for once and kept.
# ORRERY_SIGN=adhoc is the old way, for a Mac where no key may be kept; it says what it costs.
if [ "${ORRERY_SIGN:-}" = adhoc ]; then
    codesign --force --sign - "$NEW/Contents/MacOS/orrery"
    codesign --force --sign - "$NEW"
    echo "signed ad hoc: macOS will take the next install for a new application and ask again"
else
    sh "$ROOT/tools/mac-sign.sh" sign "$NEW/Contents/MacOS/orrery" "$NEW"
    # The copy in PREFIX/bin is the same program started from a terminal: the same signer.
    sh "$ROOT/tools/mac-sign.sh" sign "$PREFIX/bin/orrery"
fi

mkdir -p "$APPDIR"
rm -rf "$APP"
mv "$NEW" "$APP"
# Tell Finder and Launchpad the icon changed.
touch "$APP"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP" 2>/dev/null || true

echo "installed $PREFIX/bin/orrery and $APP"
[ "${ORRERY_SIGN:-}" = adhoc ] || sh "$ROOT/tools/mac-sign.sh" check "$APP" | sed -n '2,3p;$p'
echo "it starts: orrery$ARGS"
