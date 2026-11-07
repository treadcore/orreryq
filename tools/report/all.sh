#!/bin/sh
# Every lab report in docs/ as its page: REPORT SHORT-TITLE EYEBROW. An eyebrow names the project, Orreryq
# (Paul, 6 November: the pages carry the new name; the program, its command and Orrery.app stay orrery).
# Add a line for a new report, run it, and link the page from docs/index.html. Then every report of
# orrery and of treadcore is collected as HTML and listed in docs/reports.html (collect.py), so the
# collection keeps up with both repositories.
set -eu
cd "$(dirname "$0")/../../docs"
while IFS='|' read -r name short eyebrow; do
    [ -n "$name" ] || continue
    python3 ../tools/report/build.py "$name-lab-report.md" "$name-lab-report.html" "$short" "$eyebrow"
done <<'LIST'
appkit-gui|From Cargo to AppKit|Rust · AppKit · no crates
mac-app|Mac Applications|Orreryq · the app · bundles and signatures
cuda-node|A CUDA Node|Orreryq · the fleet · CUDA
pascal-versions|Held Back on Purpose|Orreryq · the fleet · CUDA versions
cuda-hybrid|One Source, Two CUDAs|Orreryq · crucible · CUDA 12 and 13
difficulty|Promotion Difficulty|Orreryq · the search · promotions
copal-machines|Copal Machines Join|Orreryq · the fleet · machines
storage|Fleet Storage|Orreryq · the fleet · storage
fleet-commanders|Fleet Commanders|Orreryq · the fleet · commanders
fleet-orchestration|Commanding the Fleet|Orreryq · the fleet · orchestration
brain-versions|Many Versions of One Brain|Orreryq · the brain · whole-number choices
algorhythm|Algorhythm|Orreryq · the brain · hybrid programming
analysis|Reading a Growing Brain|Orreryq · the brain · analysis
balance|Too Many Shots|Orreryq · the game · balance
jaguaribe-clock|A Dead Clock Battery|Orreryq · the fleet · machines
whole-line|The Whole Line|Orreryq · the fleet · the line, end to end
double|The Double Report|Orreryq · the fleet · the design and the guide
bot-styles|Eight Named Minds|Orreryq · the brain · styles and bridges
fortify|A Stale Dial|Orreryq · the brain · what we measured and changed
terrain|A Terrain for Each Dataset|Orreryq · the brain · maxima and what works on them
waves|Waves, Width and Waiting|Orreryq · the brain and the fleet · temperament, capacity, the queue
economy|The Zero-Sum Economy|treadcore · the game and the brain · ore, oil, workers, supply, trade
diff|The Day's Difference|Orreryq · treadcore · 2 November in exact code, flow and UML
nets|The Nets Explorer|Orreryq · the brain · every learned net, where it has been, kept by request
x8dt3|The X8DT3-LN4F, Warm Again|Orreryq · the fleet · a Supermicro server's jumpers and BIOS
storage-options|Storage, Reconsidered|Orreryq · the fleet · storage options, nothing decided
idle-fleet|Fifty-Four Idle Minutes|Orreryq · the fleet · the line replayed twice, and restarting
duty-cycle|The Duty Cycle|Orreryq · the fleet · utilization, waiting and the round table
line-film|Three Generations, Filmed|Orreryq · the montage · the line, the crowd and the wires
outgrowing|Outgrowing Yourself|Orreryq · the fleet · the GPU, the line, and what a generation keeps
one-rule|One Rule, Two Machines|Orreryq · crucible · the trees, the mazes, the CUDA gauntlet and the GPU's generations
round-corner|Round the Corner|Orreryq · crucible · maze navigation: the senses, the errand, the proving ground and the breach
full-card|Every Generation on Film|Orreryq · crucible · treadcore · the maze home, one wall, the camp, a full card, the footage and a page that reads itself
LIST
python3 ../tools/report/collect.py
