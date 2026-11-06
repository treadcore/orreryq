#!/bin/sh
# Every lab report in docs/ as its page: REPORT SHORT-TITLE EYEBROW.
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
mac-app|Mac Applications|orrery · the app · bundles and signatures
cuda-node|A CUDA Node|orrery · the fleet · CUDA
pascal-versions|Held Back on Purpose|orrery · the fleet · CUDA versions
cuda-hybrid|One Source, Two CUDAs|orrery · crucible · CUDA 12 and 13
difficulty|Promotion Difficulty|orrery · the search · promotions
copal-machines|Copal Machines Join|orrery · the fleet · machines
storage|Fleet Storage|orrery · the fleet · storage
fleet-commanders|Fleet Commanders|orrery · the fleet · commanders
fleet-orchestration|Commanding the Fleet|orrery · the fleet · orchestration
brain-versions|Many Versions of One Brain|orrery · the brain · whole-number choices
algorhythm|Algorhythm|orrery · the brain · hybrid programming
analysis|Reading a Growing Brain|orrery · the brain · analysis
balance|Too Many Shots|orrery · the game · balance
jaguaribe-clock|A Dead Clock Battery|orrery · the fleet · machines
whole-line|The Whole Line|orrery · the fleet · the line, end to end
double|The Double Report|orrery · the fleet · the design and the guide
bot-styles|Eight Named Minds|orrery · the brain · styles and bridges
fortify|A Stale Dial|orrery · the brain · what we measured and changed
terrain|A Terrain for Each Dataset|orrery · the brain · maxima and what works on them
waves|Waves, Width and Waiting|orrery · the brain and the fleet · temperament, capacity, the queue
economy|The Zero-Sum Economy|treadcore · the game and the brain · ore, oil, workers, supply, trade
diff|The Day's Difference|orrery · treadcore · 2 November in exact code, flow and UML
nets|The Nets Explorer|orrery · the brain · every learned net, where it has been, kept by request
x8dt3|The X8DT3-LN4F, Warm Again|orrery · the fleet · a Supermicro server's jumpers and BIOS
storage-options|Storage, Reconsidered|orrery · the fleet · storage options, nothing decided
idle-fleet|Fifty-Four Idle Minutes|orrery · the fleet · the line replayed twice, and restarting
duty-cycle|The Duty Cycle|orrery · the fleet · utilization, waiting and the round table
line-film|Three Generations, Filmed|orrery · the montage · the line, the crowd and the wires
outgrowing|Outgrowing Yourself|orrery · the fleet · the GPU, the line, and what a generation keeps
one-rule|One Rule, Two Machines|orrery · crucible · the trees, the mazes, the CUDA gauntlet and the GPU's generations
round-corner|Round the Corner|orrery · crucible · maze navigation: the senses, the errand, the proving ground and the breach
LIST
python3 ../tools/report/collect.py
