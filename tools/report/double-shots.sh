#!/bin/sh
# double-shots.sh QUEUE: every screen of Orrery from the live run, for docs/double-report.md, by the
# program's own --frame renderer. shot NAME VIEW DOC [ENV=VALUE ...]: a picture at 1400x860.
# SHOTS=list OUT=folder ORRERY_BIN=binary take another set: the feature guide's is
#   SHOTS=tools/report/feature-shots.list OUT=docs/features/live tools/report/double-shots.sh QUEUE
set -u
Q=$1; cd "$(dirname "$0")/../.."; D=${OUT:-docs/double}; T=$(mktemp -d); B=${ORRERY_BIN:-target/release/orrery}; mkdir -p $D
python3 -I tools/plans/treadcore-view.py --queue "$Q" > $T/status.json
python3 tools/machines.py "$Q" status > $T/machines.json 2>/dev/null
python3 tools/storage.py "$Q" status > $T/storage.json 2>/dev/null
python3 tools/orchestrate.py "$Q" status > $T/fleet.json 2>/dev/null
python3 tools/orchestrate.py "$Q" chat > $T/chat.json 2>/dev/null
P=$Q/plan/pipeline.json; J=$T/status.json
shot() { n=$1; v=$2; f=$3; shift 3; env ORRERY_FRAME_OPERATOR=1 "$@" $B --operator paul --fleet grove --frame $T/$n.ppm --frame-view $v ${f:+--frame-state $f} --frame-size 1400x860 >/dev/null 2>$T/err || { echo "FAILED $n: $(tail -1 $T/err)"; return; }
  python3 - "$T/$n.ppm" "$D/$n.png" <<'PY'
import sys
from PIL import Image
Image.open(sys.argv[1]).convert("RGB").quantize(colors=200,dither=Image.Dither.NONE).save(sys.argv[2],optimize=True)
PY
}
. "${SHOTS:-tools/report/double-shots.list}"
du -sh $D; ls $D/*.png | wc -l; rm -rf "$T"
