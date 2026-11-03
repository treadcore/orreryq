# The transform: wider, deeper, or neither yet

The transform is the fourth part of the design: a learned stage after the rules that may move their answer when it is confident, and that is the brain as it was when all its numbers are zero. Paul asked whether it needs a larger matrix or more layers. The short answer from the week's one measurement is *not yet*; this chapter says what was measured, what the shapes on offer are, what each would touch, and the test that decides.

## What it is today

Two learned things share the word "net" here, and they must be kept apart:

- **The transform** (`patch.rs`): *k* steps, each a linear map of the 153 inputs (133 senses, the three waves, the rules' own answer, the base sense) and the output so far, through a tanh, added to the output: three outputs (move the point across, move it down, confidence). Two steps are 942 numbers. It has no hidden layer: its depth is its steps, and its width is its input. Trained by SPSA ([9]–[12]) over the census; one is in slot 1 and plays as the Overrider style, reading near zero so far (+0.28 ± 0.5 over few steps).
- **The learned tank's net** (`net.rs`): 133 senses into two hidden layers of 64 into the heads; trained by imitation on the card (`tools/bc`) and by evolution strategies. The *width test* of 1 November trained it at 32, 64 and 128: drive agreement 67.1, 67.7, 68.7 and gun 64.6, 65.7, 66.4; 128 beats 64 by 0.85, under the bar of 1.0 ([Waves](../2026-11-01-waves.html), section VI). The width watch repeats it every twenty generations.

## What "bigger" could mean

| Shape | What changes | Numbers | What it touches | Expected gain, and why |
| --- | --- | --- | --- | --- |
| A. more steps (deeper transform) | 2 → 4 steps | 942 → 1,884 | nothing but the file's step count; SPSA's step count | small: each step can correct the last, but a linear map through a tanh stays near-linear at these scales |
| B. a hidden layer per step (wider transform) | each step reads inputs → 16 hidden → 3 | about 2,500 a step | `Step`, the file format (TCP1 → TCP2), the planner's `PATCH_INPUTS`, the Training view's pictures | the first real nonlinearity: a step could gate on a sense (duck only when a gun is seen) rather than add to it |
| C. a wider net | hidden 64 → 128 | ×4 in the first layer | `HIDDEN`, every net file, the card's time | measured: +0.85, under the bar, on an older game |
| D. a deeper net | two hidden layers → three | +4,096 | as C | not measured; the universal-approximation results say width or depth both suffice, and the width-view results say depth buys more per parameter for some functions ([98]–[102]) |
| E. persona and leader inputs | the senses grow by a persona one-hot and the leader channel (chapter 11) | +12 inputs | the senses count, every net, the transform's inputs, `PATCH_INPUTS` | a new generation of nets regardless; the time to change shape is when the inputs change anyway |

## The recommendation

1. **Do not widen on today's evidence.** The one measurement is under its bar; the net is twenty points behind the rules for reasons that are not capacity (it cannot build or crew: it has no squad head trained and the game now pays for building).
2. **Change shape when the inputs change.** Chapter 11's leader channel and chapter 10's persona input force a new generation of nets. Make that the moment to train shapes A to D side by side, once, on the new game.
3. **Turn the width watch into a shape watch.** The watch already trains one width every twenty generations on 240 seeds and reads it against a bar. Give it a list of shapes rather than widths, the same seeds for all, 400 seeds (the 240 lean narrow), and the bar of 1.0 point as before. Report every shape's read on Settings → Long run, which is where the watch already reports.
4. **Prefer B over A for the transform.** A hidden layer per step is what lets a transform gate; four linear steps mostly re-add. B is the shape to try first, at 16 hidden, with SPSA's perturbation chosen as the trainer's own probe says (its step was measured well under its probe on 30 October).
5. **Keep the all-zeros rule.** Whatever the shape, zero numbers must be the rules unchanged, so training starts where the rules stand and a worse transform is one that moved something. That is residual policy learning's guarantee and the design's.

## The test, written before the run

For each shape: trained by the same method on the same recordings and seeds; read by agreement with the rules on held-out decisions (drive and gun heads), then by census at 400 seeds against today's defaults with the composition read; a shape wins only if it beats the current shape by 1.0 point a seat on the census or by 1.0 on both heads' agreement, and gives up nothing past the trade floors. A tie keeps the smaller shape.

## What was proved on 2 November

The trainer takes `DEPTH` beside `WIDTH`, and the shape watch's list is 32, 64, 128 and 64×3. The road was walked on this Mac the same evening, on the CPU backend (Burn's flex; the trainer's lock wants rustc 1.95, installed beside the Mac's 1.93): a recording of four seeds (36,743 samples, one seed held out); a net of 143 → 64 → 64 → 64 → 47 written, and a two-layer one beside it; Rust's own `Net::forward` on the held-out samples reading the trainer's agreement to the decimal on every head for both (drive 71.1 against 72.1, mortar 76.5 against 77.2, drone 96.6 against 96.5, lead 100 for both); and the gauntlet playing both from `nets/`. None of it is a read of the shape: 36,000 samples teach little, and the deeper net had not left the floor at three epochs where the shallower had (46.6% against 56.2%, the floor being the commonest label's 46.6%). It is the proof that the fleet's first shape-watch job will write a net the brain plays. The read of 64×3 against 64 is that job's, by the test above.

## Links

[Waves, Width and Waiting](../2026-11-01-waves.html) · [Algorhythm](../2026-10-30-algorhythm.html) · [The Net in Orrery](../2026-10-28-the-net-in-orrery.html) · `patch.rs`, `net.rs`, `tools/bc` · width and depth [98]–[104] · SPSA [9]–[16] · evolution strategies [1]–[8].
