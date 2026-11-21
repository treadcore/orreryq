#!/bin/sh
# PHP with SQLite, for Parliament Chess lanes. Paul, 20 November: "add the
# orrery fleet installer script for php8.3, with the db. What you did to set
# it up, as a script." What was done by hand on calber, whitewolf and
# boburner that day, and what the Alpine machines lacked (their PHP had no
# SQLite).
#
# Run it ON THE MACHINE, as root (orrery's Machines view stages it and
# types this into the machine's Sessions tile, where the password is typed):
#
#   cd ~/orrery-recipes && sudo sh php-node.sh      (Ubuntu)
#   cd ~/orrery-recipes && doas sh php-node.sh      (Alpine, Copal)
#
# What it does, each step checked first, so running it again is safe:
#   Ubuntu 24.04  php8.3-cli, php8.3-sqlite3 (PDO's SQLite driver and
#                 sqlite3) and php8.3-opcache, from Ubuntu's own archive:
#                 8.3 is enough (Parliament Chess needs 8.2 or later) and
#                 no outside repository is added;
#   Alpine        the PHP already there (php85, else the newest of php85,
#                 php84, php83 in Alpine's repositories), with its pdo,
#                 pdo_sqlite, sqlite3 and ctype; PHP 8.5 has OPcache built in.
# Then the check, as the user: PHP 8.2 or later, PDO's SQLite driver, and a
# SQLite database written and read back in a temporary folder.
#
# Not here, and by design: the queue's side. A probe of the machine reads
# what this left, and `machines.py QUEUE php-lane NAME` gives the machine's
# CPU lane the "php" capability; the Parliament planner then sets up its
# lane itself (pc-prep: the code, the tests). Never on macmini (Paul, 20
# November), and that is macOS, where this does not run.
set -eu

U="${USER_NAME:-user}"
[ "$(id -u)" = 0 ] || { echo "run as root (sudo sh php-node.sh, or doas on Alpine)" >&2; exit 1; }
id "$U" >/dev/null 2>&1 || { echo "no user $U here" >&2; exit 1; }
. /etc/os-release
case "${ID:-}" in
ubuntu)
    want=""
    for p in php8.3-cli php8.3-sqlite3 php8.3-opcache; do
        dpkg-query -W -f '${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || want="$want $p"
    done
    if [ -n "$want" ]; then
        echo "installing:$want"
        apt-get update -qq
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends $want
    else
        echo "PHP 8.3 with SQLite is there"
    fi
    ;;
alpine)
    v=""
    for n in 85 84 83; do
        if apk info -e "php$n" >/dev/null 2>&1; then v=$n; break; fi
    done
    if [ -z "$v" ]; then
        for n in 85 84 83; do
            if apk search -x "php$n" 2>/dev/null | grep -q "^php$n-"; then v=$n; break; fi
        done
    fi
    [ -n "$v" ] || { echo "no PHP 8.3 or later in this machine's repositories" >&2; exit 1; }
    want=""
    for p in "php$v" "php$v-pdo" "php$v-pdo_sqlite" "php$v-sqlite3" "php$v-ctype"; do
        apk info -e "$p" >/dev/null 2>&1 || want="$want $p"
    done
    if [ "$v" != 85 ] && ! apk info -e "php$v-opcache" >/dev/null 2>&1; then
        want="$want php$v-opcache"
    fi
    if [ -n "$want" ]; then
        echo "installing:$want"
        apk add --no-progress $want
    else
        echo "PHP $v with SQLite is there"
    fi
    # Alpine names its binary php85; the fleet's jobs call php.
    if ! command -v php >/dev/null 2>&1 && [ -x "/usr/bin/php$v" ]; then
        ln -s "/usr/bin/php$v" /usr/bin/php
        echo "/usr/bin/php -> php$v"
    fi
    ;;
*)
    echo "for Ubuntu and Alpine; this is ${PRETTY_NAME:-unknown}" >&2
    exit 1
    ;;
esac

# The check, as the user, the way the jobs will run it: a database written
# and read back in a folder of its own, removed after.
chk=$(mktemp /tmp/php-node-check.XXXXXX)
cat > "$chk" <<'PHP'
<?php
if (PHP_VERSION_ID < 80200) { fwrite(STDERR, "PHP " . PHP_VERSION . " is older than 8.2\n"); exit(1); }
if (!class_exists(PDO::class) || !in_array('sqlite', PDO::getAvailableDrivers(), true)) { fwrite(STDERR, "no PDO SQLite driver\n"); exit(1); }
$dir = sys_get_temp_dir() . '/php-node-' . bin2hex(random_bytes(4));
mkdir($dir);
$db = new PDO('sqlite:' . $dir . '/check.sqlite', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
$db->exec('PRAGMA busy_timeout=5000');
$db->exec('PRAGMA journal_mode=WAL');
$db->exec('CREATE TABLE t (k INTEGER PRIMARY KEY, v TEXT)');
$db->prepare('INSERT INTO t (v) VALUES (?)')->execute(['parliament']);
$ok = $db->query('SELECT v FROM t')->fetchColumn() === 'parliament';
$sqlite = $db->query('SELECT sqlite_version()')->fetchColumn();
$db = null;
array_map('unlink', glob($dir . '/*'));
rmdir($dir);
echo ($ok ? 'ok' : 'FAILED') . ': PHP ' . PHP_VERSION . ', SQLite ' . $sqlite . ', ' . (extension_loaded('Zend OPcache') ? 'OPcache' : 'no OPcache') . "\n";
exit($ok ? 0 : 1);
PHP
chmod 644 "$chk"
rc=0
su -s /bin/sh "$U" -c "php $chk" || rc=$?
rm -f "$chk"
exit $rc
