#!/bin/sh
# mac-sign.sh -- one signing identity for Orrery.app on this Mac, kept from install to install, so
# that what macOS grants the application once it does not take back at the next build.
#
#   mac-sign.sh identity         make the identity if it is absent; print its fingerprint
#   mac-sign.sh sign PATH...     sign each path with it (the code inside a bundle first, then the bundle)
#   mac-sign.sh check [APP]      what APP is signed with, its requirement, and whether it is this identity's
#   mac-sign.sh prove            sign two different programs and show one requirement, two hashes
#   mac-sign.sh forget           delete the identity (the next install makes a new one, and macOS asks again)
#
# WHY. macOS keeps each grant it gives an application (the local network, the firewall, the
# keychain) against the application's DESIGNATED REQUIREMENT: a sentence that says which code counts
# as "the same application". A program signed ad hoc (codesign --sign -) has no signer, so its
# requirement can only be its own hash: `cdhash H"..."`. EVERY BUILD HAS A NEW HASH, SO EVERY
# `make install` WAS A NEW APPLICATION, and the grant to reach the fleet's machines belonged to the
# one before. On 18 November 2026 the Mac refused, by policy and before a packet left, 333 of the
# 349 ssh connections the console and its keeper opened in three minutes; the queue called every
# machine unreachable. docs/local-signing-lab-report.md is the account.
#
# Signed by a certificate, the requirement is `identifier "org.copal.orrery" and certificate root =
# H"<the certificate's hash>"`: it names the signer and not the build. The certificate here is
# self-signed: nobody vouches for it, Gatekeeper gives it nothing, and it is not for giving the
# application to anyone else. It only has to be THE SAME ONE next time.
#
# WHERE IT LIVES. A keychain of its own, ~/Library/Keychains/orrery-signing.keychain-db, with a
# random password beside the app's options (mode 600). Rejected: the login keychain, where codesign
# may not use a new key until somebody types the login password into a dialog or into
# `security set-key-partition-list`, and an install that stops for a password is an install that is
# not run. A keychain made here can be opened here. What that costs: whoever can read this
# account's files can sign as this identity -- and whoever can read this account's files can
# already replace the application. The key signs one bundle identifier on one Mac and is trusted
# by nothing.
#
# The keychain joins the user's search list only while signing (codesign finds an identity nowhere
# else; --keychain alone said "no identity found") and leaves it again, locked: no other program
# meets a locked keychain it never asked for.
set -eu
[ "$(uname -s)" = Darwin ] || { echo "mac-sign.sh: this is for macOS" >&2; exit 2; }

NAME="Orrery Local Signing"
BUNDLE_ID=org.copal.orrery
KC="${ORRERY_SIGN_KEYCHAIN:-$HOME/Library/Keychains/orrery-signing.keychain-db}"
PWFILE="${ORRERY_SIGN_PASSWORD:-${XDG_CONFIG_HOME:-$HOME/.config}/orrery/signing-keychain-password}"

# The certificate's SHA-1, as codesign and `security` name an identity; empty if there is none.
fingerprint() {
    [ -f "$KC" ] || return 0
    security find-certificate -c "$NAME" -Z "$KC" 2>/dev/null | sed -n 's/^SHA-1 hash: //p' | head -1
}

make_identity() {
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    # The three extensions are the whole of what makes a certificate a code-signing one: it is not
    # an authority, its key signs, and what it signs is code. Twenty years: a signature made with
    # an expired certificate still satisfies the requirement, but codesign will not make a new one.
    cat > "$tmp/req.cnf" <<EOF
[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = $NAME
O = Orrery
[ext]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,codeSigning
subjectKeyIdentifier = hash
EOF
    openssl req -x509 -newkey rsa:2048 -nodes -days 7300 -config "$tmp/req.cnf" \
        -keyout "$tmp/key.pem" -out "$tmp/cert.pem" 2>/dev/null
    # `security import` takes a key and its certificate together only as PKCS#12, and wants a
    # password on it; the file lives for this function.
    openssl pkcs12 -export -inkey "$tmp/key.pem" -in "$tmp/cert.pem" -name "$NAME" \
        -passout pass:orrery -out "$tmp/id.p12"

    mkdir -p "$(dirname "$PWFILE")" "$(dirname "$KC")"
    (umask 077; openssl rand -hex 24 > "$PWFILE")
    pw=$(cat "$PWFILE")
    rm -f "$KC"
    security create-keychain -p "$pw" "$KC"
    security set-keychain-settings "$KC"                    # no timed lock: it is locked by hand, below
    security unlock-keychain -p "$pw" "$KC"
    security import "$tmp/id.p12" -k "$KC" -P orrery -T /usr/bin/codesign >/dev/null
    # Without this the first codesign opens a dialog asking whether codesign may use the key.
    security set-key-partition-list -S apple-tool:,apple: -s -k "$pw" "$KC" >/dev/null 2>&1
    security lock-keychain "$KC"
    rm -rf "$tmp"
    trap - EXIT
}

ensure_identity() {
    fp=$(fingerprint)
    if [ -z "$fp" ] || [ ! -s "$PWFILE" ]; then
        make_identity
        fp=$(fingerprint)
        [ -n "$fp" ] || { echo "mac-sign.sh: the identity was not made" >&2; exit 1; }
        echo "mac-sign.sh: made the signing identity \"$NAME\" ($fp) in $KC" >&2
        echo "mac-sign.sh: macOS will ask once more for what it granted the old signature; after that it keeps" >&2
    fi
    printf '%s\n' "$fp"
}

# The user's keychain search list, one path a line, without the quotes `security` prints.
search_list() { security list-keychains -d user | sed 's/^ *"//; s/"$//'; }

with_keychain() {
    # Join the search list, unlock, run, and put both back whatever happens.
    old=$(search_list)
    restore() {
        printf '%s\n' "$old" | tr '\n' '\0' | xargs -0 security list-keychains -d user -s
        security lock-keychain "$KC" 2>/dev/null || true
    }
    trap restore EXIT
    printf '%s\n%s\n' "$old" "$KC" | tr '\n' '\0' | xargs -0 security list-keychains -d user -s
    security unlock-keychain -p "$(cat "$PWFILE")" "$KC"
    "$@"
    restore
    trap - EXIT
}

sign_paths() {
    fp=$1; shift
    for p in "$@"; do
        # The identifier is given, not left to codesign: a bare binary would be named after its
        # file and its hash ("orrery-5555494461..."), and the identifier is half of the requirement.
        codesign --force --sign "$fp" --identifier "$BUNDLE_ID" "$p"
    done
}

requirement() { codesign -d -r- "$1" 2>&1 | sed -n 's/^designated => //p; s/^# designated => //p' | head -1; }

case "${1:-}" in
identity)
    ensure_identity
    ;;
sign)
    shift
    [ $# -gt 0 ] || { echo "mac-sign.sh sign PATH..." >&2; exit 2; }
    fp=$(ensure_identity)
    with_keychain sign_paths "$fp" "$@"
    ;;
check)
    app=${2:-/Applications/Orrery.app}
    fp=$(fingerprint)
    req=$(requirement "$app")
    echo "application   $app"
    echo "signed by     $(codesign -dvv "$app" 2>&1 | sed -n 's/^Authority=//p; s/^Signature=adhoc/nobody (ad hoc)/p' | head -1)"
    echo "requirement   $req"
    echo "identity      ${fp:-none made yet}"
    want=$(printf '%s' "$fp" | tr 'A-F' 'a-f')
    if [ -n "$fp" ] && printf '%s' "$req" | grep -q "identifier \"$BUNDLE_ID\" and certificate root = H\"$want\""; then
        echo "ok: the requirement names this Mac's identity, and the next install will have the same one"
    else
        echo "NOT STABLE: the requirement does not name this Mac's identity; the next install is a new application to macOS"
        exit 1
    fi
    ;;
prove)
    # Two programs that differ, one identity: the hashes differ and the requirement does not.
    fp=$(ensure_identity)
    tmp=$(mktemp -d)
    cp /bin/ls "$tmp/a"; cp /bin/cat "$tmp/b"
    with_keychain sign_paths "$fp" "$tmp/a" "$tmp/b" 2>/dev/null
    ha=$(codesign -dvvv "$tmp/a" 2>&1 | sed -n 's/^CDHash=//p'); hb=$(codesign -dvvv "$tmp/b" 2>&1 | sed -n 's/^CDHash=//p')
    ra=$(requirement "$tmp/a"); rb=$(requirement "$tmp/b")
    cp /bin/ls "$tmp/c"; cp /bin/cat "$tmp/d"
    codesign --force --sign - "$tmp/c" 2>/dev/null; codesign --force --sign - "$tmp/d" 2>/dev/null
    rc=$(requirement "$tmp/c"); rd=$(requirement "$tmp/d")
    rm -rf "$tmp"
    echo "signed by the identity:"
    echo "  first   hash $ha   requirement $ra"
    echo "  second  hash $hb   requirement $rb"
    echo "signed ad hoc:"
    echo "  first   requirement $rc"
    echo "  second  requirement $rd"
    [ "$ha" != "$hb" ] && [ "$ra" = "$rb" ] && [ "$rc" != "$rd" ] || { echo "FAILED: the claim does not hold"; exit 1; }
    echo "PASSED: two builds, two hashes, ONE requirement by the identity; two requirements ad hoc"
    ;;
forget)
    security delete-keychain "$KC" 2>/dev/null || rm -f "$KC"
    rm -f "$PWFILE"
    echo "removed $KC and its password; the next install makes a new identity"
    ;;
*)
    sed -n '2,9p' "$0" >&2
    exit 2
    ;;
esac
