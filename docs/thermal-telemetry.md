# Thermal telemetry: what is collected, how to read it, and what to change in each BIOS

Paul, 15 November 2026: "calculate a Tau, or a time constant ... determining the heat capacity and thermal emissions rates related to temperature changes until 5 time constants ... model how reactive in the time constant to the step function of turning a system on fully on and off ... Show all the temperatures on a graphs chart plots over time, many plots overlaid ... But first we need to collect the data. Make as part of the fleet script."

This is the guide to what was built that day. It is not a lab report: the data is hours old, and the model it is for is not yet argued.

## What runs where

| Piece | Where | Root | What it does |
|---|---|---|---|
| `tools/fleet-telemetry.sh` | each Linux machine, `~/.fleet-queue/` | no | one line of `key=value` every 5 seconds into `~/.fleet-queue/telemetry/YYYYMMDD.log` (UTC days, 14 kept) |
| `tools/telemetry.py QUEUE pull` | this Mac, by the keeper's housekeeping every 5 minutes | no | one connection a machine, of its own: puts the collector there if absent or old, starts it if it is not running (after a boot), brings the new lines to `QUEUE/telemetry/MACHINE/` |
| `tools/fleet-sensors.sh` | each Linux machine, once | **yes** | the thermometers only root reads: see below |
| `tools/telemetry.py QUEUE show` | this Mac | no | each machine's last sample, every channel |
| `tools/telemetry.py QUEUE chart [HOURS]` | this Mac | no | `QUEUE/plan/telemetry.html`: every channel of every machine over time |
| `tools/telemetry.py QUEUE fit [MACHINE] [HOURS]` | this Mac | no | time constants from the steps the queue made (`QUEUE/plan/telemetry-fits.json`) |

The keeper's own two-minute reading (`take_heat`, the hold at a limit, the rest after a drop) is separate and unchanged: it decides; this records.

## What each machine tells without root (15 November)

| Machine | Board | Cooling, as Paul describes it | Channels now |
|---|---|---|---|
| columbia | MINIX NEO Z300-0dB, i3-N300 | a passive heatsink, air across it | CPU package, one NVMe (3 sensors) |
| calber | Gigabyte Z370 AORUS Gaming WIFI, i7-9700F | liquid | CPU package, six board thermometers (`gigabyte_wmi`, unnamed by the driver; one reads 78), three ACPI zones, two NVMe, the card |
| saskatchewan | MSI PRO B760-VC WIFI, i7-13700F | air | CPU package, three NVMe (10 sensors) |
| whitewolf | Gigabyte Z170M-D3H, i7-6700K | air | CPU package, two ACPI zones, one NVMe, the card |
| boburner | Gigabyte AB350-Gaming 3, Ryzen 7 3700X | air | CPU (Tctl, Tccd1), three board thermometers and three fan drives (`it8792`; its fan speeds read 0: that chip is the board's second, and the first has no driver in the kernel), one NVMe (4 sensors), the card |
| bosporus | Supermicro, two Xeons | one of these two is liquid (Paul); which is not recorded here | six memory thermometers (`jc42`) only: the CPU's driver is not loaded |
| jaguaribe | Supermicro, two Xeons | | off when this was written |
| macmini, this Mac | Apple | | nothing without root: no collector |

Every machine also gives the CPUs' use, the load, and the cores' mean clock (a CPU holding itself back for heat shows there first); the three cards give watts, use and fan.

## What needs root, once a machine: `fleet-sensors.sh`

Not one of these is readable by the user, and none is installed yet: each needs the machine's password once.

- **Each SATA disk** (calber 6, whitewolf 6 spinning, saskatchewan 4): the kernel's `drivetemp` driver, loaded at boot.
- **The board's fans and chipset thermometer**: the kernel's `nct6775`, `nct6683`, `it87`, `w83627ehf`, each tried; a board whose chip the kernel has no driver for (the Gigabyte boards' IT8686/IT8628, by what is known here) stays without fan speeds.
- **The CPU's watts**: the energy counter (RAPL) on all five; the kernel keeps it for root since 2020. This is the input the thermal model wants most: watts in, degrees out.
- **The Mellanox 10 GbE cards** (whitewolf `enp8s0`, boburner `enp6s0`: MT26448, ConnectX-2 EN). The `mlx4` driver gives no thermometer. Two things are tried each 15 seconds: the plugged module's own (`ethtool -m`: an optic with diagnostics tells, a copper cable does not) and the card's chip (`mstflint`'s `mget_temp`). **Whether a ConnectX-2 answers either is not known here**; the script says at its end which port told nothing.
- **The Supermicro boards' own controller** (`ipmitool`, each minute): inlet air, each CPU, each fan.

Three ways to run it:

1. **Machines tab, a machine, "Read every thermometer"**: the recipe is staged and typed into the machine's Sessions tile, where the password is typed.
2. **One password a machine, in a terminal:** `sh tools/fleet-root-round.sh columbia saskatchewan calber whitewolf boburner bosporus jaguaribe` (it now ends with `fleet-sensors.sh`; the three scripts before it change nothing on a machine that has them).
3. **At a boot, with no password:** not built. It would mean root running, at boot, a file the user account can write, which is passwordless root for anything that can write as `user`. That is Paul's decision, not a default.

## The packages

Every machine updated itself last night (the daily job, `fleet-update.sh --auto`): columbia and saskatchewan at 02:00, calber 03:05, boburner 03:31, whitewolf 03:51. What waits is a boot: all five have a newer kernel installed than the one running, and each has been up 7 days. Restart on the Queue page reboots a machine after its job in hand where it has the restart rule (boburner has; calber and whitewolf have the power-off rule only: the root round gives them the other). On Ubuntu the NVIDIA driver and CUDA are held back by the nightly run on purpose; a by-hand `fleet-update.sh` takes them.

## The model, and how a step is made

A part that is heated at P watts and loses heat in proportion to how far it is above the air settles at T_air + P x R (R, degrees a watt, is the cooler) and gets there as 1 - exp(-t / tau), tau = R x C (C, joules a degree, is how much metal and water there is). After one tau it has made 63% of the change, after three 95%, after five 99%. A CPU is at least two of these in a row: the silicon and its lid (seconds), then the cooler or the loop (minutes); a liquid loop has the larger C and so the longer tau.

`fit` finds, in what was recorded, each time the CPUs' use changed by 40 points or the card's watts by 40 and then held four minutes, and fits each channel that moved 3 degrees: one exponential, or two where the second halves the error. It prints how many tau the hold lasted. **Under three tau the end temperature is a projection.**

A step is made with the queue's own buttons, and costs the machine's work for as long as it is held:

- **All off, then all on:** `fleet-queue.py QUEUE machine NAME pause`, wait for the job in hand, hold five tau, `resume`.
- **The card alone:** `machine NAME-cuda pause` and `resume`.
- **Levels between:** `machine NAME cpus 1|2|4|8`, each held five tau: the jobs started after it are told that many CPUs. This is the dial for "not queueing the full amount of threads"; the settled temperature at each level, against the watts at each, is R.

## BIOS: what to change for the fans

None of this can be set from Linux on these boards; each is a visit to the machine's setup screen. The names are the boards' own menus as known here, not read from these machines' screens.

| Machine | Where | What to set |
|---|---|---|
| calber (Z370 AORUS, F15) | M.I.T., Smart Fan 5 | CPU_FAN and the pump header (CPU_OPT or SYS_FAN_PUMP) at Full Speed: a pump is not slowed. The radiator's and the case's fans: Manual, the curve moved left so they are at full by 60 on the CPU; "Fan Stop" off; Temperature Interval 1. The 78 one board thermometer reads is most likely the VRM: point one case fan's curve at that sensor if the header offers it |
| whitewolf (Z170M-D3H, F22f) | M.I.T., PC Health Status, Smart Fan | CPU Fan Speed Control: Full Speed, or Manual with a steep slope; each System Fan the same. Six spinning disks sit in this case: one fan on the disk cage at a fixed speed |
| boburner (AB350-Gaming 3, F52h) | M.I.T., Smart Fan 5 | as calber. Its card runs 81 to 82 at 100 W under a CPU at 78: the case is not clearing the card's heat. An intake fan at full pointed at the card does more than any curve |
| saskatchewan (MSI PRO B760-VC, B.D3) | Hardware Monitor | CPU Fan and each System Fan: the four-point curve pulled so 100% is reached by 65; Smart Fan Mode off gives a fixed speed. PL1 and PL2 are under OC, CPU Cooler Tuning: "Boxed Cooler" holds the CPU to 65 W and is the BIOS's own throttle |
| columbia (MINIX Z300-0dB) | none | it has no fan and no fan header: the case is the heatsink. It settles near 45 at full work; air across it is all there is to add |
| bosporus, jaguaribe (Supermicro) | the board's controller (IPMI), Fan Mode | Full, or Heavy IO. From Linux, after the root round: `ipmitool raw 0x30 0x45 0x01 0x01` sets Full on most Supermicro boards; check the reading before trusting it |

## The energy balance, and the Heat page

`tools/telemetry.py QUEUE model` (`tools/thermal.py`, run after every pull) writes `QUEUE/plan/thermal.json`; Orrery's Queue tab has a page for it, **Heat**.

- **What goes in comes out.** A machine's watts at the wall are its heat into the room: `tools/plans/power.json`'s model at the CPUs' use measured, the card's watts measured. At 11:00 on 15 November seven machines made about 1,240 W (4,200 BTU/h); carrying that off at a ten-degree rise takes about 370 m3/h of air.
- **A part is R and C.** A step's watts and where the part settled give R = degrees moved / watts moved; C = tau / R. T_zero = T_settled - R x P is the air the part sits in, inside its case.
- **The fin.** Where a step needs two exponentials, the fast one is the silicon to its cooler and the slow one the cooler to the air; T_fin = T_die - R_fast x P. No CPU has given a two-part step yet.
- **The room.** C_room dT/dt = the fleet's watts - (T_room - T_out) / R_room. Nothing in the fleet reads T_room. The page shows the coldest reading any machine gives (30 that morning, a board thermometer on boburner) as what the room is no warmer than. The controller Paul names as the end, one that holds the room by setting the fleet's watts, needs a thermometer in the room before it can be more than this bound. Radbeeper's counters (GMC-320) are logged for radiation only; the GMC-320 line has a temperature command (`GETTEMP`) that radbeeper does not ask, and whether these two units answer it is not tested.

The first parts, from the queue's own Pause on 15 November (each held more than three tau):

| Part | Step | tau | R, C/W | C, J/C | Air at the part |
|---|---|---|---|---|---|
| calber's card | 21 to 141 W | 78 s | 0.08 | 960 | 54 |
| whitewolf's card | 13 to 91 W | 90 s | 0.19 | 490 | 50 |
| whitewolf's card, cooling | 95 to 14 W | 154 s | | | |
| boburner's card | 11 to 98 W | 58 s | 0.28 | 210 | 54 |
| boburner's card, cooling | 77 to 13 W | 82 s | | | |

A card cools more slowly than it heats on both machines where both were measured: its fan slows as it cools. Boburner's card has the least metal and the worst path to air of the three, and sits in 54-degree air: it settles at 82 at 98 W, three under the keeper's limit.

Columbia's CPU fell from 44 to 33 inside one 5-second sample when its job ended: the passive case, not the silicon, is its slow part (its NVMe, 3 degrees over a quarter hour). Bosporus's memory, switched on from cold and idle, climbs with a tau near a quarter hour; that hold was 1.4 tau, so its end is a projection. No CPU has had a held step under load yet: the CPU lanes have not been paused long enough, and the two servers' CPU channels began after they were already working.

## What is not built

- The dial in Orrery (a history and sliders that set a machine's target and throttle its part in the queue). The data it needs is what this collects; Paul: "There is not a single number, this will take some thinking and analysis of logs."
- The watts-to-degrees model itself (R and C a machine, a predicted settled temperature at each load): it wants the CPU's watts, which wait for root, and held steps at several levels.
- A disk's time constant: hours of data, as Paul says.
