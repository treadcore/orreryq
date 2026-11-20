# The Same Application Tomorrow: a Signing Identity of Orrery's Own, the Binary as the Bundle's Executable, and Why macOS Called Every Machine Unreachable

*Paul Richeson · Lab Report — IEEE Format · 18 November 2026*

Copyright (c) 2026 Paul Richeson. MIT licensed, as orrery.

Companions: `tools/mac-sign.sh` (the identity: made, used, checked, proved, forgotten); `tools/mac-app.sh` (the install that uses it); `src/bundle.rs` (the binary doing what the launcher script did); `tools/mac-ssh-watch.py` (whose ssh this Mac is refusing, in one table); *The Orange Queue* (`docs/orange-queue-lab-report.md`), whose section VII left the cause of the dropped connections "not found".

## Abstract

On 18 November 2026 the queue called machines unreachable that answered a terminal at once. The Mac was refusing the connections itself. In the three minutes after the console opened at 13:47, the kernel dropped the first packet of 333 of 349 ssh connections "by policy" and returned *No route to host*; the 16 that connected came from a terminal. The policy is macOS's local network privacy, and it had lost track of which application Orrery was, for two reasons that this report separates by experiment. First, `Orrery.app` was signed ad hoc, so the only sentence macOS could keep about it was the hash of one build: 38 past builds were on the Mac's list as 38 applications. Second, the bundle named a shell script as its executable, and macOS files the grant under the Mach-O UUID of that file; a script has none, so the bundle was on record with no code. Both are changed. `make install` now signs with one self-signed identity kept in a keychain of its own, and the binary is the bundle's executable. After the change macOS for the first time asked the question under the application's own name: "prompting for Orrery (org.copal.orrery)". Paul answered Allow that afternoon, and both remaining measurements were made: the console's connections were allowed, and after the next install, a build with another hash and the same requirement, macOS asked nothing and allowed a fresh connection the new build opened (section X).

## I. The question

Paul, 18 November: "the mac keeps rejecting ssh. is there something wrong. Perhaps its after hours of stale connections." Then, after the diagnosis: "Please do the fix of make it stick. Explain the self signed process additions and concept overview with details in a lab report. and impliment."

Three questions follow from that. What refuses the connections? Why does a reboot, or an install, change whether it does? What must be true of the application for a grant, once given, to be kept?

## II. What the reader needs

### A. What a code signature is

A signed program carries four things that matter here.

| Part | What it is | Changes when |
|---|---|---|
| The code directory | a table of hashes, one for each page of the program and each sealed resource | any byte of the program changes |
| The `cdhash` | the hash of the code directory: one number that stands for this exact build | every build |
| The identifier | a name inside the signature, by convention the bundle identifier (`org.copal.orrery`) | only if the signer changes it |
| The signature proper | the code directory signed with a private key, and the certificate that holds the matching public key | the signer or the build changes |

`codesign -dvvv APP` prints all four. Apple's own account is in its three technical notes on code signing [1]-[3].

### B. Ad hoc: a signature with no signer

`codesign --sign -` makes the code directory and stops. There is no key and no certificate: the program is sealed, so the system can tell it has not been altered since, but nobody is named as having sealed it. Apple silicon will not run unsigned code, so the linker signs every program this way by itself, and `tools/mac-app.sh` did the same for the bundle.

### C. The designated requirement

When macOS grants an application something (the local network, a keychain item, an exception in the firewall) it must write down which application it meant, in a form that survives an update. That form is the *designated requirement*: a sentence in a small language that any later program either satisfies or does not [3]. `codesign -d -r- APP` prints it.

The requirement is derived from the signature, and this is where the two kinds part:

```text
signed by a certificate:  identifier "org.copal.orrery" and certificate root = H"6989d9e4..."
signed ad hoc:            cdhash H"b6c926740b64d2c082058f1ff93125e53d22c8eb"
```

The first names a signer. Every build that the same certificate signs under the same identifier satisfies it. The second can name nothing but the build itself, because an ad hoc signature has nothing else in it. **An ad hoc program's next build is, to every part of macOS that keeps a grant, a different application.**

### D. Local network privacy

Since macOS 15 a program that opens a connection to an address on the local network is checked against a per-application permission, the one listed under System Settings, Privacy & Security, Local Network [4]. Three properties of it matter here.

1. **It is enforced in the kernel, before a packet leaves.** A refused `connect()` returns error 65, *No route to host*, at once. Nothing reaches the wire and the far machine logs nothing.
2. **A process is judged as the application that launched it.** `ssh` started by Python started by Orrery is, for this purpose, Orrery. Programs started from Terminal are judged as Terminal, which has the grant.
3. **The first refusal is meant to raise a question on screen**, and the answer is kept against the application's identity.

The fleet's machines are all on 192.168.8.x, so every connection Orrery makes is subject to it.

## III. Materials

| | |
|---|---|
| The Mac | macOS 26.7.2 (build 25G332) in the morning, 26.7.3 (25G342) from 14:08 |
| The application | `/Applications/Orrery.app`, bundle identifier `org.copal.orrery`, built by `tools/mac-app.sh` |
| The fleet | boburner, saskatchewan, columbia, whitewolf, macmini, calber on 192.168.8.x, reached by `ssh` |
| The kernel's record | `/usr/bin/log`, lines `tcp connect outgoing ... process: ssh:PID ... error: N` and `tcp drop outgoing ... reason: NECP` |
| The permission daemon's record | `nehelper`, subsystem `com.apple.networkextension`, at info level |
| A process catcher | `tools/mac-ssh-watch.py`: a loop over `libproc` that records each new `ssh` process, its command and its chain of parents, joined to the kernel's line for its connection |

The catcher was needed because a refused `ssh` lives a few milliseconds. `ps` in a loop caught none of 76 refused processes in 50 seconds; the `libproc` loop caught 223 of 223 in 90.

In `zsh`, `log` is a shell builtin: the system's is `/usr/bin/log`.

## IV. What was observed

Four states of the same application on the same day, each watched for 70 to 180 seconds. "Refused" is a `connect()` that returned error 65 with the kernel's reason NECP, the policy engine. "Launched by" is the root of the process's chain of parents.

| | When | Signature | Bundle executable | ssh launched by Orrery | What the permission daemon said |
|---|---|---|---|---|---|
| A | 13:47 to 13:50 | ad hoc | the script | refused: 333 of 349 never connected | (not read at the time) |
| B | 14:36 to 14:38, after the system update and a restart | ad hoc, the same build | the script | connected; the only failures were error 64, *Host is down*, to machines that were off | nothing |
| C | 14:42 to 14:44, after `make install` with the identity | the identity | the script | refused: 105 of 105 | "Local network allowed by preference for orrery (orrery-5555494461043453...), but received prompt"; "Received UUID 6F9328CD-... does not match cached UUIDs" |
| D | 14:48 to 14:51, after `make install` with the binary as the executable | the identity | the binary | refused: 85 of 85, a question pending | "UUID cache hit for org.copal.orrery"; "Local network preference not yet set, prompting for Orrery (org.copal.orrery)" |

In A the 16 connections that succeeded were opened from a terminal. In C and D the keeper, which the console had started at 14:08 while it was allowed, went on connecting: every machine answered and seven lanes ran throughout.

Two more facts were read from the Mac's own list of local network rules, `/Library/Preferences/com.apple.networkextension.plist`:

- It held 69 application rules. **Thirty-eight of them were Orrery**, each named `orrery-55554944` followed by a different 32 hexadecimal digits, each with the path of the binary inside the bundle.
- It held one rule named `org.copal.orrery`, for which the daemon reported "0 UUIDs" at every lookup.

The queue's record of the same morning, before any of this was understood:

| Hour | Jobs sent back as "host unreachable" |
|---|---|
| 00 | 23 |
| 01 | 15 |
| 08 | 10 |
| 09 | 6 |
| 11 | 15 |
| 12 | 14 |

macmini alone had 23 of its 260 jobs sent back.

## V. What it means

### A. The refusal is the Mac's

In A the far machines were up: a terminal reached four of them in the same minute. The kernel's lines show the first packet of each refused connection dropped on the Mac with the reason NECP, and zero bytes sent. Stale connections are not involved: a refused connection never existed.

That also explains two things that had no explanation. The queue only worked at all, in a bad spell, because its jobs ride a shared connection a machine, and a shared connection opened by a program in a terminal could be used by the keeper through a local socket, which the policy does not see. When that connection ended, the keeper could not open another. On the day, boburner and saskatchewan came "back" ten seconds after their shared connections were opened by hand from a terminal, and macmini stayed unreachable until its one was.

### B. The first fault: the name was the build

The 38 rules are the proof. `orrery-55554944...` is not a name anybody chose. `55554944` is the four letters `UUID` in hexadecimal, and what follows is the build's own Mach-O UUID: it is the identifier the linker gives a bare program when nobody gives it one. Each install put a new program at the same path with a new identifier and a new hash, and macOS made a new rule for it. The grant Paul gave was to one of the 38.

State C shows what happens next. The daemon found the newest binary by its path, matched it to the rule of the build before, and read that rule as allowed. Then it compared UUIDs, found that the program in front of it was not the one the rule was made for, cleared its cache, looked the old name up again, found no such program anywhere, and stored nothing. It did this about every ten seconds for as long as it was watched. **It neither allowed the connection nor asked the question.** An application in this state cannot be fixed from System Settings, because no question is ever raised to answer.

### C. The second fault: the bundle had no code

Signing with the identity (state C) did not help by itself, and the daemon's lines say why: "0 UUIDs for org.copal.orrery". The bundle's `Info.plist` named `launch` as its executable, a four-line shell script that set the PATH, opened the log and ran the binary. macOS reads the UUID of the file the bundle names. A script has no UUID. So the rule for `org.copal.orrery` described an application with no code in it, and the binary the script ran was looked up as a stray program by its path.

State D is the same signature with the binary named as the executable. For the first time the daemon found the application by its bundle ("UUID cache hit for org.copal.orrery"), found no preference recorded for it, and did what the design intends: it raised the question, under the name Orrery.

### D. Why both changes are needed

| | Bundle names the script | Bundle names the binary |
|---|---|---|
| **Ad hoc** | a new stray program every build (states A, B: 38 rules) | found as the bundle, but its requirement is still one build's hash |
| **The identity** | still a stray program found by path (state C) | found as the bundle, and the requirement names the signer (state D) |

The lower right is the only cell in which macOS can both find the application and recognise the next build as the same one. The upper right was not tried: it would have meant installing a build known to be wrong.

### E. What is not explained

The same ad hoc build was refused at 13:47 and allowed at 14:36. Between them the system was updated and restarted. The daemon keeps a cache of UUIDs with a generation number, and the likeliest account is that the restart rebuilt it in a state where that one build matched its own rule. That is a guess: the daemon's lines for A were not captured. It matters less than it did, since the fix does not depend on it.

## VI. What was built

### A. The identity: `tools/mac-sign.sh`

```text
mac-sign.sh identity         make the identity if it is absent; print its fingerprint
mac-sign.sh sign PATH...     sign each path with it
mac-sign.sh check [APP]      what APP is signed with, its requirement, and whether it is this identity's
mac-sign.sh prove            sign two different programs and show one requirement, two hashes
mac-sign.sh forget           delete the identity
```

Making the identity is seven steps, each one command.

| Step | Command | What it is for |
|---|---|---|
| 1 | `openssl req -x509 -newkey rsa:2048 -nodes -days 7300` | a key pair, and a certificate for the public half that the private half signs itself |
| 2 | (the request's three extensions) | `CA:false`: it vouches for nobody else. `keyUsage = digitalSignature`: the key signs. `extendedKeyUsage = codeSigning`: what it signs is code. `codesign` will not use a certificate without the last. |
| 3 | `openssl pkcs12 -export` | key and certificate in one file, the only form `security import` takes them together |
| 4 | `security create-keychain` | a keychain of its own, `~/Library/Keychains/orrery-signing.keychain-db`, with a random password |
| 5 | `security import ... -T /usr/bin/codesign` | the pair goes in; `codesign` is named as a program that may use the key |
| 6 | `security set-key-partition-list -S apple-tool:,apple:` | without this the first signing opens a dialog asking whether `codesign` may use the key |
| 7 | `security lock-keychain` | locked until the next signing |

Signing then joins the keychain to the user's search list, unlocks it, runs `codesign --force --sign FINGERPRINT --identifier org.copal.orrery`, and puts the search list back and locks the keychain whatever happened.

### B. What "self-signed" gives and does not give

A certificate is ordinarily signed by an authority, and the authority's by another, up to a root the system trusts. This one is signed by its own key. The chain is one link long and ends at nothing the system trusts: `security find-identity` lists it as `CSSMERR_TP_NOT_TRUSTED`, and that is correct.

| It gives | It does not give |
|---|---|
| a requirement that names a signer, the same at every build | anything from Gatekeeper: a downloaded copy is still an unidentified developer's |
| grants that are kept from install to install | a way to give the application to another Mac; that wants a Developer ID and notarization |
| no cost, no account, no network | any assurance to a third party about who built it |

Nothing more is wanted. The requirement does not ask whether the certificate is trusted. It asks whether it is *the same certificate*, by its hash.

### C. Where the key lives, and what was rejected

**A keychain of its own, with its password in a file beside the application's options** (`~/.config/orrery/signing-keychain-password`, mode 600).

Rejected: the login keychain. `codesign` may not use a key newly put there until somebody types the login password, into a dialog or into `security set-key-partition-list`. An install that stops for a password is an install that does not get run, and the ad hoc signature would be back within the week.

What that costs: whoever can read this account's files can sign as this identity. Whoever can read this account's files can already replace the application. The key signs one identifier on one Mac and nothing trusts it.

Rejected: leaving the keychain on the search list. `codesign --keychain` alone answered "no identity found", so the keychain must be on the list while signing. Left there, other programs would meet a locked keychain they never asked for.

### D. The binary as the bundle's executable: `src/bundle.rs`

The launcher script did three jobs. The binary now does them itself, and only when it is started with no arguments from inside a bundle, which is how Finder starts an application:

| The script's job | Now |
|---|---|
| put `~/.local/bin` and Homebrew on the PATH | `bundle::path`, set before anything is run |
| send output to `~/Library/Logs/orrery.log` | the log opened for append and `dup2` onto standard output and error |
| pass the options the app was installed with | read from `Contents/Resources/arguments`, one a line |

Started with arguments of its own, from a terminal, it reads no file and redirects nothing. Six tests, named as sentences, cover the path test, the parsing and that last rule.

Rejected: `LSEnvironment` in `Info.plist`, which cannot say `$HOME` and does nothing for the options or the log. Rejected: a small compiled launcher that runs the binary, because `exec` replaces the program and the UUID macOS sees would again not be the bundle's.

### E. The install: `tools/mac-app.sh`

Three changes. The bundle's `CFBundleExecutable` is `orrery`. The options are written to `Contents/Resources/arguments`. The binary and then the bundle are signed by `mac-sign.sh sign`, and so is the copy in `~/.local/bin`. The install ends by printing who signed the application and its requirement.

`ORRERY_SIGN=adhoc make install` is the old signature, for a Mac where no key may be kept. It says what it costs when it is used.

## VII. How to use it

Nothing changes in the ordinary case: `make install`. The first run makes the identity and says so.

```text
$ make sign-check
signed by the identity:
  first   hash 1118b52b...   requirement identifier "org.copal.orrery" and certificate root = H"6989d9e4..."
  second  hash f4a94fb0...   requirement identifier "org.copal.orrery" and certificate root = H"6989d9e4..."
signed ad hoc:
  first   requirement cdhash H"8903a336..." or cdhash H"1031d385..."
  second  requirement cdhash H"ba9aa7a0..." or cdhash H"63b02a3d..."
PASSED: two builds, two hashes, ONE requirement by the identity; two requirements ad hoc
application   /Applications/Orrery.app
signed by     Orrery Local Signing
requirement   identifier "org.copal.orrery" and certificate root = H"6989d9e4c233c031dcb16b2481ffc9a1eaa13760"
ok: the requirement names this Mac's identity, and the next install will have the same one
```

The ad hoc lines show two hashes each because `/bin/ls` and `/bin/cat`, the two programs the proof signs, hold code for two processors.

To see whether the Mac is refusing connections now, and whose:

```text
$ python3 tools/mac-ssh-watch.py 30
99 ssh processes started in 30 s; the kernel recorded a connection for 53
count  result                           launched by  through                      to
    3  connected                        the keeper   git                          git@ssh.github.com
    7  refused, error 65, reason NECP   Orrery       tools/orchestrate.py         copal-fleet@saskatchewan
    7  refused, error 65, reason NECP   Orrery       tools/orchestrate.py         copal-fleet@columbia
    ...
REFUSED BY THIS MAC: 39 connections Orrery launched. Its grant: System Settings, Privacy & Security, Local Network.
```

That is state D, with the question unanswered. It needs no root, and it ends with a line that says "ok" when nothing Orrery launched was refused.

To see what the permission daemon thinks Orrery is:

```text
/usr/bin/log show --last 2m --info --predicate 'process == "nehelper" AND eventMessage CONTAINS[c] "local network"'
```

If the identity is ever lost (a new Mac, a deleted keychain), the next install makes another, macOS takes the application for a new one once, and asks once.

## VIII. Results

| Claim | How it was checked | Result |
|---|---|---|
| Two different programs signed by the identity have one requirement and two hashes | `mac-sign.sh prove` | passed |
| Two programs signed ad hoc have two requirements | the same | passed |
| The installed application's requirement names the identity | `mac-sign.sh check`, and `codesign --verify --deep --strict` | passed |
| Signing leaves the keychain search list as it found it | `security list-keychains` before and after | the login keychain alone, both times |
| No dialog and no password during an install | three installs run without a person | none appeared |
| The binary starts from Finder with its options, PATH and log | `open /Applications/Orrery.app`; the window opened in the operator posture and wrote to the log | passed |
| macOS finds the application by its bundle | the daemon's "UUID cache hit for org.copal.orrery" and its question by name | passed |
| The bundle's tests | `cargo test --release bundle` | 6 of 6 |
| Connections are allowed once the question is answered | `mac-ssh-watch.py` twice after Paul's Allow (section X) | passed: nothing Orrery launched was refused |
| They are still allowed after the next `make install` | a new build (another hash, the same requirement), reopened; a fresh connection forced from it (section X) | passed: no question asked, and a connection the new build's own process opened was allowed |

## IX. What Paul decides, and what is not done

1. **Answer the question.** Done that afternoon: Allow (section X).
2. **The two measurements** are made (section X).
3. **The keeper now running was started by the console of 14:08**, before the change, and is allowed. It was left alone, since restarting it runs the jobs in hand again. The next keeper will be started by the new application and will need the grant.
4. **The 38 old rules are still on the Mac's list.** They do not match the new application, which is found by its bundle. Removing them wants root and an edit to a system preference file; the Settings pane can switch a row off and cannot delete one. Not done.
5. **The film for this report was not attempted in this sitting.** The directive of 13 November asks for one after every report.
6. Nothing here is committed.

## X. Addendum, 16:00 to 16:50 the same day: allowed, and kept across an install

**Allowed.** Paul answered the question Allow and ran `python3 tools/mac-ssh-watch.py` himself, twice. The first run: 113 ssh processes in 40 seconds, and the only failures error 64, *Host is down*, to calber, which was off; "ok: nothing Orrery launched was refused by this Mac's policy". The second, with calber booted: every connection made.

**Kept across an install.** The same evening the console was changed (a full-tilt button on the Heat page, `docs/hearth-controller.md`) and installed by `make install`:

| | Before | After |
|---|---|---|
| CDHash | `413189877f4364291a2408c1dee02ca8ec0fe882` | `b0afdf76474542bacab2f993d968cdac1a648d42` |
| Mach-O UUID | `DE1ABC73-...` | `89A605B4-...` |
| Designated requirement | `identifier "org.copal.orrery" and certificate root = H"6989d9e4..."` | the same |

Under ad hoc signing this was a new application. The console was quit and opened again on it at 16:39:23, and the permission daemon was watched: it raised no question.

The first watches after the reopen proved less than they seemed. Every new connection in them was the keeper's, which the console of 14:08 had started, and the new console's own ssh calls all rode shared connections that were already open, which are local sockets and are not checked. A connection the new build itself opens had to be forced. The installed application was started through `open`, so that macOS counts it as the app that launched what follows, in its one-frame drawing mode on the Machines view. Immediately before, the housekeeping shared connections it reads the machines through were closed. In the minute that followed, `tools/disk-report.py`, launched by Orrery, opened a fresh connection, and it was allowed. **A grant given to one build was honoured for the next, with no question.**

That is the claim the report was written for, and it rests on one forced connection. Closing the jobs' own shared connections would have forced more, at the price of requeuing every job in hand, and was not done.

## References

[1] Apple Inc., "TN3125: Inside Code Signing: Provisioning Profiles," Apple Developer Technical Notes.

[2] Apple Inc., "TN3126: Inside Code Signing: Hashes," Apple Developer Technical Notes. The code directory and the `cdhash`.

[3] Apple Inc., "TN3127: Inside Code Signing: Requirements," Apple Developer Technical Notes. The designated requirement and its language.

[4] Apple Inc., "TN3179: Understanding local network privacy," Apple Developer Technical Notes.

[5] `codesign(1)`, `security(1)`, `csreq(1)`, macOS manual pages.

[6] P. Richeson, "The Orange Queue," orrery `docs/orange-queue-lab-report.md`, 15 November 2026. Section VII, "Where the drops come from", and its two addenda.
