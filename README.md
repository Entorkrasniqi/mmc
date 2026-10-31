# mini-mission-control

A pretend satellite and the ground software that talks to it. The **simulator** (Python) plays a small satellite that sends
**telemetry** (its health data) and obeys **telecommands** (instructions from the ground), using the real space-industry packet
format (CCSDS space packets) over the network. A **specification file** describes every packet once, and a generator turns it into
the database that **[Yamcs](https://yamcs.org)**, an open-source mission control system, needs to show the data on screen, raise
alarms and send commands.

```
$ minisat simulate &                      # the satellite
$ minisat listen                          # a tiny ground station that prints what it receives
Housekeeping #1  12:43:14Z  mode=NOMINAL  cmd_accepted=0  ...  battery_soc_pct=90.004  ...  in_eclipse=NO  heater=OFF
Housekeeping #2  12:43:15Z  mode=NOMINAL  cmd_accepted=0  ...  battery_soc_pct=90.008  ...  in_eclipse=NO  heater=OFF
...
Position     #1  12:43:18Z  latitude_deg=0.310  longitude_deg=9.938  altitude_km=560.000

$ minisat send-tc SetMode mode=PAYLOAD    # an instruction to the satellite
sent SetMode {'mode': 2} (9 bytes: 10 0a c0 00 00 02 00 02 02) to 127.0.0.1:10025
```

![Eleven simulated hours: a PAYLOAD command drains the battery through warning and critical levels until the on-board protection forces SAFE mode; a later command is refused; the satellite recovers](docs/scenario.png)

*Eleven simulated hours, produced in about a second by `minisat demo` (no network, no Yamcs needed). At 1 h the operator switches
the payload on; the battery drains through the 35 % warning and 20 % critical limits until the satellite protects itself by going to
SAFE mode (5.4 h). At 6.5 h the operator tries PAYLOAD again and the satellite **refuses** because the battery is too low. At 8 h the
operator returns to NOMINAL and the battery recovers. Grey bands are eclipses (the satellite is in the Earth's shadow, solar panels
produce nothing).*

> **Where the project is going.** The simulator, packet codec and XTCE generator described below are the foundation. On top of them
> the project is being extended into an ontology-based mission-control application: a PostgreSQL store with an audit trail, an action
> runner, a web dashboard and an AI assistant that may propose commands but never send them. The design is in
> [`ontology.md`](ontology.md), the plan and what is done in [`PLAN.md`](PLAN.md), and the engineering rules in
> [`protocols/`](protocols/README.md). So far the database, the action runner and the ground station that feeds it exist
> (sections 3.5 and 3.6); there is no web dashboard or AI assistant yet. Everything else in this README describes the simulator side.

---

## Table of contents

1. [Why this project exists](#1-why-this-project-exists)
2. [The ideas, explained from zero](#2-the-ideas-explained-from-zero)
3. [Quick start](#3-quick-start)
4. [How it works, step by step](#4-how-it-works-step-by-step)
5. [The demo scenario, and three exercises](#5-the-demo-scenario-and-three-exercises)
6. [Validation: how do we know the answers are right?](#6-validation-how-do-we-know-the-answers-are-right)
7. [Describing your own spacecraft](#7-describing-your-own-spacecraft)
8. [Project layout and tests](#8-project-layout-and-tests)
9. [Status and honest limits](#9-status-and-honest-limits)
10. [Roadmap](#10-roadmap)
11. [Questions you should be able to answer after this project](#11-questions-you-should-be-able-to-answer-after-this-project)
12. [References and licence](#12-references-and-licence)

---

## 1. Why this project exists

**The problem it models.** A satellite is a computer you cannot touch. Everything you know about it arrives as a stream of
numbers ("battery voltage is 7.4 V, temperature is 12 degrees, I am in safe mode"), and everything you tell it to do leaves as a short
message ("switch to payload mode"). The software on the ground that receives, decodes, displays, stores and alarms on those numbers,
and that sends and checks the commands, is called **mission control software**, and it is one part of the *ground segment*. Every
satellite operator needs one, including the Helsinki-area radar-satellite company ICEYE, which runs a whole constellation.

**What this repo is.** A small, open, from-scratch **learning version** of that chain, built so that every piece can be read in an
afternoon:

```
 specification (YAML)  ──generates──►  XTCE database (XML) ──read by──►  Yamcs  ◄──UDP packets──►  simulated satellite
        │                                                                                              ▲
        └──────────────────────── read by the Python code (packing, unpacking, validation) ─────────────┘
```

It is **not** ICEYE's, Nokia's or anybody's real system. The satellite is fictional, the numbers are invented, and I do not know what
real operators use internally. What the project does touch are the ideas that every ground segment is built from:

* **a binary packet format** defined by a standard (CCSDS space packets: bit fields, big-endian numbers, floats, length rules),
* **a machine-readable mission database** (XTCE, an XML standard) so the packet layout is written down once instead of being
  hard-coded in five places,
* **a real open-source mission control system** (Yamcs) configured only with built-in components,
* **a simulator** with believable physics (orbit, eclipse, power, temperature) and an on-board safety rule,
* **testing something that talks over a network**, and testing a generated file with an *independent* second reader.

**Skills it trains:** Python 3.10+ (dataclasses, `struct`, sockets, threads, `argparse`, packaging with `pyproject.toml`), bit-level
data formats, byte order and IEEE-754 floats, UDP networking, XML generation and schema validation (XSD), YAML pitfalls, state-machine
and physics modelling, pytest (including end-to-end tests over real sockets), reading a large open-source project's source to find out
how a configuration option behaves, and the Yamcs/XTCE vocabulary that appears in ground-segment job descriptions. The packet/bit skills
transfer directly to any protocol work: reading a specification and implementing it *bit-exactly* is the same craft whether the packets
come from a satellite or from a base station.

**Where it fits with the sibling projects.** [`leo-contact-planner`](https://github.com/Entorkrasniqi/leo-contact-planner) decides *when* a
satellite can be talked to (passes over ground stations); this project is *what is said* during such a pass.
[`ofdm-transceiver-cpp`](https://github.com/Entorkrasniqi/ofdm-transceiver-cpp) studies *how the bits become a radio signal*, and
[`sar-change-detection`](https://github.com/Entorkrasniqi/sar-change-detection) is about *what the satellite's data is used for*.

---

## 2. The ideas, explained from zero

### 2.1 Telemetry and telecommands

Two directions, two words:

* **Telemetry (TM)**, satellite → ground: measurements and status, sent over and over (here: every second and every five seconds).
* **Telecommand (TC)**, ground → satellite: instructions, sent only when an operator (or a schedule) decides to.

Everything in this project is about getting these two kinds of message **exactly right at the level of single bits**, because the
receiver has no way to "see what you meant": it just applies a rule to the bytes.

### 2.2 Bytes, integers, floats, byte order

A **byte** is 8 bits and holds a number 0 to 255. Bigger numbers use several bytes, and the question "which byte comes first?" is the
**byte order**. We use **big-endian** ("network byte order", the most significant byte first), which is what CCSDS uses: the number
1 000 as a 16-bit integer is `03 e8` (3 × 256 + 232 = 1000). A little-endian machine would write `e8 03`. If sender and receiver
disagree you do not get an error, you get the wrong number (`e8 03` read as big-endian is 59 395), which is why one of the tests in
this repo flips the byte order on purpose and checks that something screams.

A **float32** stores a decimal number in 32 bits as `sign | exponent | fraction` (IEEE 754). For example 8.1 is `41 01 99 9a`:
sign 0, exponent `10000010` = 130 → 2^(130−127) = 8, fraction ≈ 0.0125 → 8 × 1.0125 = 8.1. The nearest float32 to 8.1 is not exactly 8.1
(about 8.100000381), which is why the tests compare floats with a tolerance and integers exactly.

### 2.3 The CCSDS space packet

The **CCSDS** (Consultative Committee for Space Data Systems) is the standards body of the space agencies. Its *Space Packet Protocol*
puts every message into a **packet** that starts with a fixed 6-byte **primary header**:

```
 byte 0          byte 1          byte 2          byte 3          byte 4          byte 5
┌───┬─┬─┬───────────────────────┬─────┬─────────────────────────┬───────────────────────────────┐
│ver│T│S│        APID           │ seq │      sequence count     │        packet data length     │
│ 3 │1│1│         11 bits       │flags│         14 bits         │            16 bits            │
└───┴─┴─┴───────────────────────┴─────┴─────────────────────────┴───────────────────────────────┘
  bits 0-2: version, always 000        T: 0 = telemetry, 1 = telecommand
  S: 1 = a secondary header follows    APID: "application process identifier" - which source/kind of packet
  seq flags: 11 = this packet is not part of a split sequence ("standalone")
  sequence count: 0,1,2,... per APID, wraps at 16384 - a receiver spots lost packets by gaps
  data length: the number of bytes AFTER the primary header, MINUS ONE
```

That last rule ("minus one") is the classic trap: a packet with 41 data bytes carries the number **40** in its length field. A packet
cannot have zero data bytes because 0 would mean "one byte".

**Worked example**, the first six bytes of a Housekeeping packet: `08 64 c0 07 00 28`.

* `08 64` = `0000 1000 0110 0100`: version `000`, type `0` (telemetry), secondary-header flag `1`, APID = the remaining 11 bits `00001100100` = **100**.
* `c0 07` = `1100 0000 0000 0111`: sequence flags `11` (standalone), count = `00000000000111` = **7**.
* `00 28` = 40 → 40 + 1 = **41** data bytes follow.

### 2.4 Our telemetry packets

After the primary header, every MiniSat telemetry packet has a **secondary header**: an 8-byte **spacecraft time** (milliseconds since
1970-01-01 UTC as an unsigned 64-bit number), then the **fields** one after another with no padding. A real Housekeeping packet
(generated by this repo's code and printed byte by byte):

```
08 64 c0 07 00 28            primary header: telemetry, APID 100, count 7, 41 data bytes follow
00 00 01 a1 6b 35 08 00      spacecraft time 1 792 800 000 000 ms = 2026-10-24 00:00:00 UTC
01                           mode            = 1  (NOMINAL)
00 00                        cmd_accepted    = 0
00 00                        cmd_rejected    = 0
00 00                        last_cmd_id     = 0
00 00 00 05                  uptime_s        = 5
41 01 99 9a                  battery_voltage = 8.1 V     (float32)
42 b4 00 00                  battery_soc_pct = 90.0 %
41 40 00 00                  battery_temp_c  = 12.0 degC
3f 86 66 66                  solar_current_a = 1.05 A
3e e6 66 66                  load_current_a  = 0.45 A
00                           in_eclipse      = 0  (NO)
00                           heater          = 0  (OFF)
```

47 bytes in total (6 + 8 + 33). A second packet type, **Position** (APID 101, every 5 s), carries latitude, longitude and altitude as three
float32 values (26 bytes). `minisat info` prints the full layout with byte offsets (section 3).

### 2.5 Our telecommand packets

A telecommand also starts with a primary header (type bit = 1, no secondary header, APID 10), followed by a 16-bit **command id** and
the command's **arguments**:

```
10 0a c0 00 00 02 | 00 02 | 02
 └── primary ─────┘  └ id ┘  └ argument: mode = 2 (PAYLOAD)          = "SetMode PAYLOAD", 9 bytes
```

Decoding `10 0a`: `0001 0000 0000 1010` → version 000, type **1** (telecommand), no secondary header, APID **10**. The length field `00 02` says 3 more
bytes follow (command id 2 bytes + 1 argument byte).

Why a command id instead of one APID per command? Fewer APIDs to manage, and the ground can send *any* command through one pipe.

### 2.6 XTCE: writing the packet layout down once

Somebody has to tell the mission control software "bytes 19 to 22 of packet 100 are a float32 called `battery_voltage`, in volts, and
if it falls below 6.8 raise a warning". You could hard-code this in the software, but then every mission needs a software change. The
space industry solved this with a **mission database**, and the standard format for it is **XTCE** (XML Telemetric and Command
Exchange, maintained by the OMG and CCSDS). Yamcs reads XTCE directly.

The pieces of XTCE you meet here:

* **ParameterType**: what a value *is* (a 32-bit float with unit "V" and alarm ranges, an 8-bit enumeration `0 = SAFE, 1 = NOMINAL, 2 = PAYLOAD`).
* **Parameter**: a named value of some type (`battery_voltage`).
* **SequenceContainer**: a packet layout, i.e. a list of parameters in order. Containers can **inherit**: our `Housekeeping` container
  *extends* `TelemetryPacket`, which *extends* `CCSDSPacket` (the 6-byte header). The child says "I am the right one when the APID
  parameter equals 100", a **restriction criterion**. This is how Yamcs decides, packet by packet, which layout to apply.
* **Alarm ranges**: `<WarningRange minInclusive="35"/>` means "values below 35 are a warning". Note the meaning: the range is the
  *still-fine* region, and outside it the alarm fires.
* **MetaCommand**: a command definition: its arguments, how they are laid out in the bytes, and **argument assignments** that fix some
  arguments for the commands that inherit it (our `SetMode` fixes `Command_ID = 2` and the length field `= 2`).
* **Significance**: `Reboot` is marked *vital*, which makes Yamcs ask the operator for confirmation.

Writing 450 lines of XML by hand and keeping it in sync with the simulator would be miserable and error-prone. So this repo keeps one
short **YAML specification** and **generates** the XTCE from it (section 4.4), and tests that the two never drift apart.

### 2.7 Yamcs, in one page

**Yamcs** ("Yet Another Mission Control System") is open-source mission control software developed by Space Applications Services and
used by space organisations. It is a server (Java) with a web interface. For this project you need to know five of its ideas:

1. A **data link** is a pipe to the spacecraft. `UdpTmDataLink` listens on a UDP port for telemetry; `UdpTcDataLink` sends commands to a UDP address.
2. A **preprocessor** looks at each incoming packet and extracts the time it was generated (so the screen shows when it was *created*, not when it arrived).
3. The **mission database** (our XTCE file) tells Yamcs how to cut the packet into parameters and how to build commands.
4. The **processor** applies the database, checks **alarms**, and releases commands; the **archive** stores everything for later replay.
5. The **web interface** (http://localhost:8090) shows parameters, plots, alarms, link status, and a "send command" form.

Everything MiniSat-specific lives in **configuration files plus the generated database**. There is *no custom Java code* in this
repository, because Yamcs ships generic preprocessor/postprocessor classes that are enough for our packet format (section 4.7).

### 2.8 UDP in one paragraph

**UDP** sends independent *datagrams* (small messages) to an address and port with no connection and no guarantee of delivery. That is
ideal here: one UDP datagram carries exactly one space packet, the receiver always knows where a packet ends, and if a packet is lost the
sequence counter reveals the gap. (Real links use frames and error correction below the packet layer; we skip that.) Our simulator **sends
telemetry to port 10015** and **listens for telecommands on port 10025**; both numbers are written in the specification.

### 2.9 The pretend satellite

The simulator does not try to be a spacecraft design. It has just enough physics that numbers *move for reasons you can find in 20 lines*:

* **Orbit.** A circular orbit 560 km high, inclination 97.6° (a *sun-synchronous* orbit, typical for Earth observation). Kepler's third law
  gives the period T = 2π √(a³/μ) = **5751 s = 95.9 min**. The ground point under the satellite follows from the orbit angle and the Earth's rotation
  (about 24° of longitude westward per lap).
* **Eclipse.** The satellite is hidden when it is on the night side and within one Earth radius of the Earth-Sun axis. For a circular orbit this reduces to
  cos θ < −√(1 − (R/a)²) / cos β, with β the angle between orbit plane and Sun direction (20° here). Result: **36 % of each lap in shadow** (a unit test checks
  this, and checks that the eclipse vanishes for β above about 67°).
* **Power.** Panels deliver up to 1.3 A in sunlight (with a slow wobble), zero in eclipse. The satellite draws 0.25 A in SAFE, 0.45 A in NOMINAL, 1.10 A in PAYLOAD,
  plus 0.35 A for the heater. The 4 Ah battery (about 30 Wh) charges or drains with the difference; the voltage follows the charge (6.0 V empty, 8.4 V full).
* **Temperature.** The battery temperature drifts (time constant 25 min) toward a target that is warmer in sunlight, with more load, and with the heater on.
* **On-board protection ("FDIR": fault detection, isolation and recovery).** Below 15 % charge the satellite switches itself to SAFE mode.
  A PAYLOAD command is **refused** below 30 %. This is the kind of rule operators must understand, and the ground tools must *show* it.

All the constants are in `src/minisat/model.py` with comments; they are illustrative, not engineering data.

---

## 3. Quick start

You need **Python 3.10+** for everything. **Java 25+ and Maven** are only needed if you want to run the real Yamcs (section 3.4).

### 3.1 Install and test

```bash
git clone https://github.com/Entorkrasniqi/mini-mission-control.git
cd mini-mission-control
python3 -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"                                    # the package + pytest, lxml, matplotlib
minisat info                                               # the telemetry/telecommand interface, from the specification
pytest -q                                                  # 251 tests in about 20 seconds; 259 database tests skip themselves (section 3.5)
```

Run the commands from the repository root: the default specification path is `spec/minisat.yaml`. (Use `minisat --spec other.yaml <command>`
for another file; the option goes *before* the command.)

One test needs something extra and **skips itself** if it is missing: the check against the official XTCE schema (set `XTCE_ONLINE=1` to download the
schema from GitHub, or `XTCE_XSD=/path/to/SpaceSystemV1.2.xsd`; see section 6). The demo test also adapts to whether matplotlib is installed.

### 3.2 The offline demo (no network, no Yamcs)

```bash
minisat demo --out demo_out          # writes demo_out/scenario.csv and demo_out/scenario.png
```

```
wrote demo_out/scenario.csv (1321 rows)
  first_warning_h: 3.733
  first_critical_h: 4.283
  first_safe_after_payload_h: 5.433
  min_soc_pct: 12.189
  min_voltage_v: 6.198
  final_cmd_accepted: 2
  final_cmd_rejected: 1
wrote demo_out/scenario.png
```

This simulates 11 hours in about a second, runs a scripted "operator", and records what the telemetry says. The committed copies of
the output are [`docs/example/scenario.csv`](docs/example/scenario.csv) and [`docs/scenario.png`](docs/scenario.png). Section 5 explains the story in the picture.

### 3.3 A satellite and a ground station on your own computer

Open three terminals in the repository (with the virtual environment active):

```bash
# terminal 1: the satellite. Telemetry goes to UDP port 10015, it listens for commands on 10025
minisat simulate                      # add --speedup 60 to run a minute per second; Ctrl-C stops it

# terminal 2: a tiny ground station that decodes and prints telemetry
minisat listen

# terminal 3: send commands
minisat send-tc SetMode mode=PAYLOAD
minisat send-tc SetHeater state=ON
minisat send-tc SetTmRate period_s=500      # refused by the ground tool: the allowed range is 0.1 to 60 seconds
minisat send-tc Noop                        # a pure link test: it only increments the accepted-commands counter
```

What you see (a real recording of the first three commands; the numbers on your screen will differ in the details):

```
$ minisat send-tc SetMode mode=PAYLOAD
sent SetMode {'mode': 2} (9 bytes: 10 0a c0 00 00 02 00 02 02) to 127.0.0.1:10025
$ minisat send-tc SetTmRate period_s=500
period_s: 500.0 is outside the allowed range [0.1, 60]          (exit code 2, nothing was sent)

terminal 1 (the satellite's own log):
t=     2.7s  ACCEPT SetMode {'mode': 2}  (ok)
t=     3.3s  ACCEPT SetHeater {'state': 1}  (ok)

terminal 2 (what the ground station decodes):
Housekeeping #2  12:43:15Z  mode=NOMINAL  cmd_accepted=0  ...  load_current_a=0.449  in_eclipse=NO  heater=OFF
Housekeeping #3  12:43:16Z  mode=PAYLOAD  cmd_accepted=1  ...  last_cmd_id=2  ...  load_current_a=1.102  in_eclipse=NO  heater=OFF
Housekeeping #4  12:43:17Z  mode=PAYLOAD  cmd_accepted=2  ...  last_cmd_id=3  ...  load_current_a=1.445  in_eclipse=NO  heater=ON
```

Look at what changed between #2 and #4: the mode went to PAYLOAD, the load current jumped from 0.45 A to 1.10 A, the accepted-command counter
counted both commands, `last_cmd_id` shows the id of the most recent command (2 = SetMode, 3 = SetHeater), and the heater added another 0.35 A.
That is the satellite's way of **acknowledging** your commands: in a real mission you confirm a command worked by watching the telemetry, not by
trusting that it was sent.

Only one program can listen on a UDP port at a time, so run **either** `minisat listen` **or** Yamcs (next section), not both, on port 10015.

**All commands**

| Command | What it does |
|---|---|
| `minisat info` | prints the packets, field offsets, commands (from the specification) |
| `minisat gen-xtce [--out FILE] [--check]` | writes the XTCE database for Yamcs; `--check` writes nothing and fails (exit 1) if the file on disk is out of date |
| `minisat simulate [--speedup N] [--duration S] [--soc PERCENT] [--seed N] [--record FILE] [--tm-host/--tm-port/--tc-host/--tc-port]` | runs the satellite; `--soc` sets the initial battery charge (default 90); `--record` also saves every telemetry packet to a file |
| `minisat listen [--host H] [--port P] [--count N] [--timeout S]` | prints decoded telemetry arriving on a UDP port |
| `minisat send-tc COMMAND [name=value ...] [--host H] [--port P]` | validates and sends a command; enum arguments accept labels (`mode=PAYLOAD`) or numbers |
| `minisat decode FILE` | decodes a recording (`-` reads standard input) |
| `minisat demo [--hours H] [--out DIR]` | offline scenario, CSV and plot |
| `minisat db-seed [--demo] [--operator ID:NAME:ROLE ...]` | creates the spacecraft, the `automation` account and operators in the database (needs `.[db]`, section 3.5) |
| `minisat ground [--duration S]` | the ground station: stores telemetry, raises alarms, verifies and sends commands (section 3.6) |
| `minisat act OPERATOR "ACTION" '{json}' [--no-contact-check]` | runs one action as an operator; refusals exit with code 2 |
| `minisat actions` | lists the actions, who may run them and their parameters |
| `minisat status` | health, open alarms and anomalies, recent commands and events from the database |

Exit codes: 0 success, 1 a runtime problem (stale database, damaged recording, nothing received), 2 bad input (unknown command, bad value, bad or missing specification).

### 3.4 With the real Yamcs

> **Read this first:** the Yamcs part could **not be run** in the environment where this repository was written (no access to Maven Central). The
> configuration was written by reading the Yamcs 5.13.7 source code and checked in other ways (section 6), but **nobody has watched it run yet**. If it
> fails, the troubleshooting table below is the place to start, and a note about what you found would make a good README commit.

Prerequisites: **Java 25 or newer** (the latest LTS; Yamcs requires Java 21 or newer) and **Apache Maven 3.8 or newer**.

```bash
# terminal 1: Yamcs (the first start downloads Yamcs from Maven Central, so it takes a while)
cd yamcs
mvn yamcs:run

# terminal 2: the satellite (from the repository root)
minisat simulate                       # keep the default speed: with --speedup the spacecraft clock would race ahead of the real time Yamcs shows
```

Then open **http://localhost:8090**, choose the instance **minisat**, and look at:

* **Links**: `tm-in` and `tc-out` should be *enabled*, and `tm-in` should show a growing packet count.
* **Telemetry → Parameters → /MiniSat**: `battery_soc_pct`, `battery_voltage`, `mode`, ... updating once a second. Graphs are one click away.
* **Alarms**: restart the simulator with a nearly empty battery, `minisat simulate --soc 30` (or `--soc 18`), and `battery_soc_pct` shows a yellow *warning*
  (below 35 %) respectively a red *critical* alarm (below 20 %) until the panels have charged it back (about eight minutes from 18 %). Those limits come from the XTCE database, which comes from
  the `limits:` in the YAML. With `--soc 25`, a `SetMode PAYLOAD` is refused by the satellite and `cmd_rejected` becomes 1.
* **Commanding → Send a command**: choose `SetMode`, pick `PAYLOAD`, send. Watch `mode` change in telemetry. `Reboot` asks for confirmation (marked *vital*).
  A `SetTmRate` with `period_s` = 500 *should* be refused by Yamcs itself before it reaches the satellite (the allowed range is in the database; untested).
  Then look at the **command history** to see the stages of each command.

| Symptom | Likely cause and what to check |
|---|---|
| `mvn yamcs:run` fails with a Java error | The Yamcs quickstart asks for Java 21 or newer; use Java 25 or newer (`java -version`). |
| `Address already in use` | Something else listens on 10015 (a leftover `minisat listen`?) or on 8090. |
| Link `tm-in` shows no packets | Is the simulator running and printing "telemetry -> 127.0.0.1:10015"? Is it the same port as in `yamcs.minisat.yaml`? |
| Packets arrive but parameters stay empty | The container restriction did not match. Decode a recording with `minisat simulate --record rec.bin` then `minisat decode rec.bin` to confirm the bytes are as expected; then check the Yamcs log for "unknown packet" style messages and compare the APID and secondary-header flag with the XTCE file. |
| Times on screen are 1970 or far away | The preprocessor settings (`timestampOffset: 6`, UNIX epoch, 8 bytes, milliseconds) do not match the packet; compare with section 2.4. |
| A command is "sent" but nothing happens | Look at the simulator's log line: it prints `ACCEPT` or `REJECT` with a reason for every command it receives. |

To stop everything: Ctrl-C in each terminal. Yamcs's data (archive) lives in `yamcs/target/yamcs/yamcs-data`, which `mvn clean` removes.

### 3.5 The database (operations layer)

The first piece of the ontology layer ([`ontology.md`](ontology.md), [`PLAN.md`](PLAN.md) phase 1) is a PostgreSQL schema for what operators *do*:
command executions, alarms, anomalies, contact windows, an audit log, an outbox, plus a time series of telemetry samples. The *definitions* (parameters,
packet types, commands) are not stored there: they come from `spec/minisat.yaml` and are loaded read-only by `minisat.ontology.definitions`.

```bash
pip install -e ".[dev,db]"
cp .env.example .env                       # then change every password in it
docker compose up -d db                    # PostgreSQL 16; creates four roles, locked down (db/roles.sql, db/database.sql)
set -a; . ./.env; set +a
alembic upgrade head                       # applies migrations/ as the "migrator" role
```

Four roles with different rights: `migrator` owns the schema, `app_runner` is the only role that writes the operations tables (and never deletes),
`app_reader` can only read, `ingest` can only append samples and refresh a spacecraft's newest values. Nobody can change the audit log (a trigger refuses it,
even for the owner). Several rules of the ontology are also enforced by the database itself: a vital command is not approved by whoever proposed it,
only a person (not an agent) approves a command or acknowledges an alarm, a command cannot go beyond PROPOSED without an approver, one open alarm per parameter,
no overlapping contacts on one station.

The database tests run against a real server, with no mocks. **Use a throw-away server, never your development database**: the tests create and change the four
roles, which belong to the whole server, so they would reset the passwords of your development roles (the tests refuse to run on a server that has a database called `minisat`).

```bash
docker run --rm -d --name minisat-test-pg -e POSTGRES_PASSWORD=test -p 127.0.0.1:55432:5432 postgres:16
MINISAT_TEST_ADMIN_URL=postgresql://postgres:test@127.0.0.1:55432/postgres pytest -q tests/db
docker stop minisat-test-pg
```

They need a superuser URL and the `psql` program; each test works in a scratch database that is dropped afterwards. Without the variable they skip. Set `MINISAT_REQUIRE_DB=1` to make
a missing server a failure instead (the CI job does).

### 3.6 Running the ground station and the actions

The **ground station** receives the telemetry, stores it in the database and reacts to it (alarms, events, anomalies, command verification). People change things only through
**actions**, which check who is asking, validate, apply the change together with its audit row, and refuse what the rules forbid ([`protocols/action-runner-and-audit.md`](protocols/action-runner-and-audit.md)).
The commands below use the database from section 3.5 and read its settings from `.env`.

```bash
minisat db-seed --demo               # MINISAT-1, an "automation" account, operators alice bob sam tina vera and an AI helper, a station
minisat simulate --soc 30            # terminal 1: the satellite, with a battery that starts below the 35 % warning limit
minisat ground                       # terminal 2: stores telemetry, raises alarms, sends released commands
minisat status                       # terminal 3: what the database says now
```

Then change something, as a person would. Replace the id with the one printed by the first command:

```bash
minisat actions                                                   # every action, who may run it, its parameters
minisat act alice "Propose Command" '{"spacecraft_id":"MINISAT-1","command":"SetHeater","arguments":{"state":"ON"},"reason":"warm the battery"}'
minisat act bob   "Approve Command" '{"execution_id":"<id>"}'
minisat act bob   "Release Command" '{"execution_id":"<id>"}' --no-contact-check   # the simulator is always in contact
minisat status                                                    # SENT, then ACCEPTED, then VERIFIED, from the satellite's own telemetry
```

Things worth trying: approve a command as `vera` (a viewer) or `helper` (the AI agent) and read the refusal; propose `Reboot` as `sam` and approve it as `sam` (two-person rule),
then as `tina`; propose `SetMode` `PAYLOAD` while the battery is below 30 % and see the warning and why an operator cannot approve it; start `minisat simulate --soc 14` (below the 15 % at which the satellite protects itself) and watch it go to SAFE mode within a second, which the ground station
records as an FDIR event and an anomaly. Every attempt, successful or refused, is a row in `ops.audit_log`.

---

## 4. How it works, step by step

```
spec/minisat.yaml                      <- the only place where packets are defined
src/minisat/spec.py                    <- loads + validates it into typed objects
src/minisat/ccsds.py                   <- the 6-byte primary header
src/minisat/codec.py                   <- pack/unpack whole TM and TC packets from the spec
src/minisat/xtce.py                    <- spec -> XTCE XML
src/minisat/model.py                   <- orbit, eclipse, power, temperature, on-board rules
src/minisat/simulator.py               <- time stepping + UDP sockets
src/minisat/demo.py, cli.py            <- the offline scenario and the command-line tool
yamcs/                                 <- Maven project + Yamcs configuration + the generated database
```

### 4.1 `spec/minisat.yaml` and `spec.py`: one source of truth

The specification lists the enumerations, the telemetry packets (name, APID, period, fields) and the commands. A field looks like this:

```yaml
- {name: battery_soc_pct, type: float32, unit: "%", description: Battery state of charge,
   limits: {warning: [35, null], critical: [20, null]}}
```

`limits` are the *still-fine* ranges; `null` means "no limit on that side". Commands take `range: [min, max]` for arguments.

`spec.py` loads the YAML into frozen dataclasses (`Spec`, `TmPacketSpec`, `Field`, `CommandSpec` ...) and **refuses nonsense with a message that names the place**:
duplicate APIDs or names, reserved APIDs, an enum value that does not fit its field type, a float field with an enum, inverted or non-nested limits, a `range` on a
telemetry field, a command id of 0, and more (25 such cases are tested). Catching such mistakes in the specification is far cheaper than finding a garbled
packet later.

**The "Norway problem".** YAML 1.1, which the PyYAML library implements, reads an unquoted `NO` or `ON` as a *boolean*: the country code for Norway
becomes `False`. For us that would silently turn the enumeration labels `OFF/ON` and `NO/YES` into `False/True`. Hence the quotes in the file
(`OnOff: {"OFF": 0, "ON": 1}`), and a dedicated check in the loader so the mistake produces this message instead of a mysterious bug:

```
specification error: spec.yaml: enums.OnOff: a label was read as the boolean False: YAML turns unquoted ON/OFF/YES/NO/TRUE/FALSE into booleans - put the label in quotes
```

### 4.2 `ccsds.py`: the primary header

`PrimaryHeader` is a dataclass (version, packet type, secondary-header flag, APID, sequence flags, sequence count, data length). `pack_primary` and `unpack_primary` are about
ten lines each of shifts and masks, and they reject any value that does not fit its bit field (an APID of 2048 is an error, not a silently truncated 0).
`build_packet` computes the length field for you (`len(data) − 1`) and `parse_packet` checks it against the actual size; `iter_packets` splits a recording made of
back-to-back packets and reports truncation. Tests compare against bytes worked out by hand (section 2.3).

### 4.3 `codec.py`: whole packets from the specification

`encode_tm(spec, "Housekeeping", values, sc_time_ms, seq_count)` builds the primary header, the 8-byte time and every field in specification order using Python's `struct`
module (`">f"` = big-endian float32, `">H"` = big-endian unsigned 16-bit, ...). `decode_tm` does the reverse and **checks everything it can**: packet type, secondary-header
flag, APID known, exact length. `encode_tc` / `decode_tc` do the same for commands, and `encode_tc(..., validate=True)` also enforces each argument's allowed range like a careful ground
system would. `validate=False` exists on purpose, to **craft a bad command**, because the satellite must not trust its input (exercise 2 in section 5).

The codec contains no knowledge of batteries or modes: add a field to the YAML and the wire format changes without touching Python.

### 4.4 `xtce.py`: the generator

`generate_xtce(spec)` builds the XTCE document with Python's XML tools. The mapping is mechanical:

| In the specification | In the XTCE file |
|---|---|
| a field with `type: float32` and `limits` | a `FloatParameterType` (32-bit) with `DefaultAlarm/StaticAlarmRanges` |
| a field with `enum: Mode` | an `EnumeratedParameterType` with one `Enumeration` per label |
| `unit: V` | `UnitSet/Unit` |
| a telemetry packet | a `SequenceContainer` inheriting `TelemetryPacket`, restricted to `SecHdrFlag = Present` and `APID = 100` |
| the 6-byte header | the abstract `CCSDSPacket` container with an aggregate parameter `CCSDS_Packet_ID` (version, type, flag, APID) and `CCSDS_Packet_Sequence` |
| a command | a `MetaCommand` inheriting `MiniSat_TC`, with argument assignments for `Command_ID` and `CCSDS_Packet_Length` (= data bytes − 1) |
| `significance: vital` | `DefaultSignificance consequenceLevel="vital"` |

An excerpt of the result (the generated file is [`yamcs/src/main/yamcs/mdb/minisat.xml`](yamcs/src/main/yamcs/mdb/minisat.xml)):

```xml
<FloatParameterType name="battery_soc_pct_t">
  <UnitSet><Unit>%</Unit></UnitSet>
  <FloatDataEncoding sizeInBits="32" />
  <DefaultAlarm>
    <StaticAlarmRanges>
      <WarningRange minInclusive="35" />      <!-- below 35 %: yellow -->
      <CriticalRange minInclusive="20" />     <!-- below 20 %: red    -->
    </StaticAlarmRanges>
  </DefaultAlarm>
</FloatParameterType>

<SequenceContainer name="Housekeeping">
  <EntryList>  <ParameterRefEntry parameterRef="sc_time_ms" />  <ParameterRefEntry parameterRef="mode" /> ... </EntryList>
  <BaseContainer containerRef="TelemetryPacket">
    <RestrictionCriteria><ComparisonList>
      <Comparison value="Present" parameterRef="CCSDS_Packet_ID/SecHdrFlag" />
      <Comparison value="100"     parameterRef="CCSDS_Packet_ID/APID" />
    </ComparisonList></RestrictionCriteria>
  </BaseContainer>
</SequenceContainer>

<MetaCommand name="SetMode">
  <BaseMetaCommand metaCommandRef="MiniSat_TC">
    <ArgumentAssignmentList>
      <ArgumentAssignment argumentName="Command_ID" argumentValue="2" />
      <ArgumentAssignment argumentName="CCSDS_Packet_Length" argumentValue="2" />   <!-- 3 data bytes - 1 -->
    </ArgumentAssignmentList>
  </BaseMetaCommand>
  <ArgumentList><Argument argumentTypeRef="SetMode_mode_t" name="mode" /></ArgumentList>
  ...
</MetaCommand>
```

Because a generated file in a repository can go stale, `minisat gen-xtce --check` compares it with a fresh generation and fails if they differ; the test suite and the CI both run this check.

### 4.5 `model.py`: the physics

`Orbit` (altitude, inclination, beta angle) offers `period_s`, `ground_point(t)`, `in_eclipse(t)` and `eclipse_fraction()`. `Spacecraft` holds the state
(battery charge, temperature, mode, heater, counters) and `step(dt)` moves it forward: it computes the solar and load currents, integrates the battery charge
(clamped between 0 and 1; a full battery wastes the surplus), pulls the temperature toward its target, and applies the FDIR rule. `housekeeping()` returns the telemetry values
(with a little seeded random noise so graphs are not perfectly smooth; the same seed always gives the same numbers).
`handle_command` executes a decoded command and updates the **accepted/rejected counters and `last_cmd_id`**. Three details worth reading:

* `SetMode PAYLOAD` is refused when the charge is below 30 % (`"battery too low for PAYLOAD mode (25 % < 30 %)"`), and the refusal is *counted*.
* `SetTmRate` re-checks the range **on board** (also rejecting `NaN`, which fails every comparison), even though the ground tool already checked it.
* `Reboot` wipes the counters, restarts the uptime and goes to SAFE, like a real power-cycle that clears RAM.

### 4.6 `simulator.py`: time and sockets

Two layers, so that the logic can be tested without a network:

* `Simulator` (pure logic): `advance(seconds)` moves simulated time forward in slices of at most one second, sends every telemetry packet that falls due (first packets at t = 0, then each packet type at
  its own period, each APID with its own wrapping 14-bit sequence counter), and `handle_telecommand(bytes)` decodes and executes one command. Garbage never crashes it:
  a malformed command is logged and counted as rejected. Changing the Housekeeping period with `SetTmRate` takes effect immediately.
* `UdpSimulator` (real time): a TC listener thread receives datagrams, the main loop keeps simulated time equal to *wall-clock time × `speedup`*, and every packet is sent as a UDP datagram
  (and optionally appended to a recording file). `stop()` and `close()` shut it down cleanly.

A test checks that advancing 1200 s in one call or in 1200 one-second calls yields the same timestamps and (nearly) the same values.

### 4.7 The Yamcs configuration, line by line

All of it is in [`yamcs/src/main/yamcs/etc/`](yamcs/src/main/yamcs/etc). The important file is `yamcs.minisat.yaml`:

```yaml
dataLinks:
  - name: tm-in
    class: org.yamcs.tctm.UdpTmDataLink            # listen for UDP datagrams, one packet each
    stream: tm_realtime
    port: 10015
    packetPreprocessorClassName: org.yamcs.tctm.GenericPacketPreprocessor   # built in: no Java of our own
    packetPreprocessorArgs:
      timestampOffset: 6        # 8-byte spacecraft time starts right after the 6-byte primary header
      seqCountOffset: -1        # the generic reader wants a 4-byte counter; ours is 14 bits in the header: skip it
      timeEncoding: {epoch: UNIX, type: FIXED, size: 8, multiplier: 1}      # milliseconds since 1970

  - name: tc-out
    class: org.yamcs.tctm.UdpTcDataLink            # send each released command as one UDP datagram
    stream: tc_realtime
    host: 127.0.0.1
    port: 10025
    commandPostprocessorClassName: org.yamcs.tctm.GenericCommandPostprocessor   # sends the bytes unchanged

mdb:
  - type: xtce
    args: {file: mdb/minisat.xml}                  # the generated database
```

* **Why the preprocessor settings are what they are.** The built-in `GenericPacketPreprocessor` reads an 8-byte timestamp at `timestampOffset` and (optionally) a 4-byte sequence count. Our time is exactly
  that (8 bytes, offset 6, big-endian, milliseconds since the Unix epoch). Our sequence count is *not* a 4-byte field, so it is switched off; sequence-gap detection by Yamcs is one of the roadmap items.
* **`processor.yaml`** is the unchanged processor setup of Yamcs's own quickstart, with `alarm: parameterCheck: true` (which is what makes the alarm ranges of the database take effect).
* **`yamcs.yaml`** starts the web server on **127.0.0.1** only. There is no login configured, so do not expose it to a network.
* **`pom.xml`** has no Java code; it only pins the Yamcs version (5.13.7), adds the two Yamcs dependencies and the `yamcs-maven-plugin` that provides `mvn yamcs:run`.

A test file (`tests/test_yamcs_config.py`) checks that the ports match the specification, that the time offset is where the codec writes the time, and that no Java files sneaked in.

### 4.8 `demo.py`: the offline scenario

`run_scenario` starts a satellite at 55 % charge, advances the `Simulator` in 30-second slices, plays a scripted operator (sections below) and decodes the last Housekeeping packet of every slice
into a CSV row. The plot is drawn with matplotlib. `summarise` extracts the key moments. Because the demo goes through the full encode → decode path (not directly into the model), it exercises the codec as a side effect.

---

## 5. The demo scenario, and three exercises

### 5.1 What happens in the picture

| Simulated time | Event | Why |
|---|---|---|
| 0 h | start at 55 % charge, NOMINAL | the demo starts mid-story so the interesting part comes sooner |
| 1.0 h | `SetMode PAYLOAD` accepted | charge 57 % ≥ 30 % |
| 1.0 - 5.4 h | charge falls | PAYLOAD draws 1.10 A; in sunlight the panels give about 1.0-1.3 A, so the margin is tiny, and in every eclipse the battery drains |
| 3.73 h | `battery_soc_pct` < 35 %: **warning** | the XTCE alarm range |
| 4.28 h | < 20 %: **critical** | the XTCE alarm range |
| 5.43 h | < 15 %: the satellite goes to **SAFE** on its own | FDIR; load drops to 0.25 A, minimum charge reached is 12.2 % and minimum voltage 6.20 V |
| 6.5 h | `SetMode PAYLOAD` **rejected** (charge about 24 % < 30 %) | on-board rule; `cmd_rejected` becomes 1 |
| 8.0 h | `SetMode NOMINAL` accepted (charge about 39 %) | recovery |
| 11 h | about 54 % | the satellite has recovered |

The numbers come from `docs/example/demo_console.txt` and the CSV and are reproduced exactly by any run (the test suite checks the story: ordering of the events, final counters).

### 5.2 Exercise 1: add a telemetry parameter (about 10 minutes)

This shows the whole point of the design, a single source of truth.

1. In `spec/minisat.yaml`, add a field to `Housekeeping`, for example just before `solar_current_a`:
   ```yaml
   - {name: panel_temp_c, type: float32, unit: degC, description: Solar panel temperature,
      limits: {warning: [-60, 80], critical: [-80, 100]}}
   ```
2. In `src/minisat/model.py`, add a matching entry to `housekeeping()`, for example `"panel_temp_c": (60.0 if self._solar_a > 0 else -30.0) + noise(0.1),`. A test checks that the model provides exactly the specified fields.
3. Regenerate the database: `minisat gen-xtce`.
4. Run `pytest`. **Four tests fail**, and every one of them hard-codes the packet size: 41 data bytes became 45 and 47 bytes on the wire became 51. Also add `panel_temp_c=40.0` to `HK_VALUES` in
   `tests/test_codec.py` (the test helper has to supply every field). Fix the numbers, and the suite is green again, including the test that decodes your new packet with the **independent XTCE reader**.

(I ran exactly this exercise once to make sure it works as described.) If you forget step 3, `test_committed_database_is_up_to_date` and `minisat gen-xtce --check` tell you.

### 5.3 Exercise 2: send a bad command and watch the satellite defend itself

```python
from minisat.spec import load_spec
from minisat.codec import encode_tc, decode_tc
from minisat.model import Spacecraft

spec = load_spec("spec/minisat.yaml")
sat = Spacecraft()
packet = encode_tc(spec, "SetTmRate", {"period_s": 500.0}, validate=False)   # bypass the ground-side check
command, args, _ = decode_tc(spec, packet)
print(sat.handle_command(command, args), sat.cmd_rejected, sat.hk_period_s)
# (False, 'period 500.0 outside [0.1, 60]') 1 1.0
```

The ground tool refuses 500 s, but a command can also arrive from a different tool, a script, a bug or an attacker. The satellite repeats the check, rejects the command, counts it and keeps its old period.

### 5.4 Exercise 3: break things on purpose and see who notices

* **The Norway problem:** remove the quotes around `"OFF"` and `"ON"` in the YAML and run `minisat info`. Read the error message (section 4.1).
* **The "minus one":** in `src/minisat/xtce.py` change `cmd.data_size - 1` to `cmd.data_size` and run `minisat gen-xtce`, then `pytest -x`. The failing test is *the independent interpreter* telling you that the XML
  would make Yamcs send commands with a wrong length field, even though everything in Python still agrees with itself. This is the reason that second reader exists.
* **Byte order:** in `codec.py` change one `">"` into `"<"`. Several tests, including ones with hand-computed bytes, fail at once.

---

## 6. Validation: how do we know the answers are right?

A generated file that nobody has loaded into the real program is the kind of thing that "looks right" and is wrong. So the evidence comes in layers, each catching a different class of mistake:

1. **Hand-computed bytes.** Tests compare the encoder's output with packets worked out on paper (the header `08 64 c0 07 00 28`, a Position packet, `SetMode PAYLOAD`). These catch a wrong bit layout or byte order, which a round-trip test alone cannot (an encoder and decoder can share the same mistake).
2. **Round trips and property-style checks.** Random headers pack/unpack to themselves (500 cases); dozens of out-of-range or malformed inputs are each rejected with a specific error.
3. **The specification validator** rejects 25 kinds of invalid specification with messages naming the place.
4. **An independent XTCE interpreter** (`tests/xtce_interp.py`, 270 lines). It knows nothing about the specification or the codec; it reads *only the XML* the way Yamcs will: it walks the container inheritance, evaluates the
   restriction criteria, decodes bit fields, applies alarm ranges, resolves meta-command inheritance and argument assignments, and builds command bytes. The tests require that for every packet and command the interpreter and the Python codec agree. If they do, the XML describes the real wire format.
5. **The official schema.** The generated file is validated against the XTCE 1.2 XSD that Yamcs ships (`tools/validate_xtce.py`, using `lxml`). It also fails correctly on a deliberately damaged file.
6. **Mutation checks** (`python tools/mutation_check.py`, about 80 seconds; not part of the normal suite): the script injects 14 deliberate bugs into copies of the code (wrong byte order for the time field or for floats, an off-by-one in the length field written into the XTCE, a wrong sequence-flag value, a shifted
   sequence-count field, swapped warning/critical limits in the XTCE, wrong restriction values for the APID or the secondary-header flag, a command id off by one, inverted eclipse logic, a disabled on-board protection, a disabled range check, and two spec changes without regenerating the database). **Every one is caught by at least one test**; run the script yourself to see which test notices which bug. With `MINISAT_TEST_ADMIN_URL` set (section 3.5) it
   also injects 37 more: 14 in the SQL (an extra grant, a removed constraint, a disabled audit trigger, a lifted two-person rule ...) and 23 in the runner, the command lifecycle and the
   automations (an expired approval accepted, two commands in flight, an unplanned SAFE mode not reported, a command "verified" without checking its effect, a command re-sent ...);
   all 51 mutations were caught on the last run.
7. **Platforms.** The 197 tests passed on Python 3.11, 3.12 and 3.13, and a clean `pip install` into a fresh virtual environment gave a working `minisat` command. Python 3.10 (the minimum declared) has not been run locally; it is in the CI matrix.

**What this does not prove.** None of it proves that *Yamcs* accepts the configuration and interprets the database as intended: that needs a run (section 3.4). The interpreter encodes my understanding of XTCE and of Yamcs's behaviour,
which I took from the Yamcs 5.13.7 source code and the XSD; if I misunderstood something, interpreter and generator could be wrong in the same way. Treat the first real Yamcs run as the final test.

---

## 7. Describing your own spacecraft

You do not have to touch Python to change the packets. Copy `spec/minisat.yaml` to `spec/mysat.yaml` and edit:

* **A new telemetry packet:** add an entry under `telemetry.packets` with a unique `apid` (0 to 2039; CCSDS reserves 2040 to 2047, and 2047 is the idle packet), a `period_s` and `fields`. Field types: `uint8/16/32/64`, `int8/16/32/64`, `float32`, `float64`.
  Field names must be **unique across all packets** (Yamcs parameters share one namespace here).
* **A new command:** add under `telecommand.commands` a unique `id` (1 to 65535), a description and optional `args` (with `range` for numbers, `enum` for labels). Set `significance: vital` for dangerous ones.
* **Alarms:** add `limits: {warning: [lo, hi], critical: [lo, hi]}` to a telemetry field (`null` for an open side; critical must lie *outside* warning).

Then `minisat --spec spec/mysat.yaml gen-xtce --out yamcs/src/main/yamcs/mdb/minisat.xml`. Note that the **simulator only knows the MiniSat model**: new fields need values from `model.py` (exercise 1), and new commands need a branch in `Spacecraft._execute`.
The packet and database side works for any specification.

---

## 8. Project layout and tests

```
mini-mission-control/
├── spec/minisat.yaml                 the interface specification (the single source of truth)
├── src/minisat/                      the Python package: spec, ccsds, codec, xtce, model, simulator, demo, cli
│   └── ontology/                     definitions.py (read-only, from the spec), functions.py (preflight, effects, events, health),
│       │                             runner.py + actions/ (the action runner and every action), ingest.py, automation.py, worker.py,
│       │                             ground.py (the ground station), seed.py, cli.py, dbconfig.py (database roles and URLs)
├── db/                               roles.sql, database.sql and init/ : the database roles and lock-down (used by Docker and the tests)
├── migrations/                       Alembic migrations: 0001 operations schema, 0002 command context and more events
├── docker-compose.yml, .env.example  the PostgreSQL service and its settings (copy to .env)
├── ontology.md, PLAN.md              the domain model and the plan (what is done, what is next)
├── protocols/                        engineering protocols and architecture decision records (adr/)
├── yamcs/
│   ├── pom.xml                       Maven project (Yamcs 5.13.7, no Java code of our own)
│   └── src/main/yamcs/
│       ├── etc/                      yamcs.yaml, yamcs.minisat.yaml, processor.yaml
│       └── mdb/minisat.xml           the GENERATED XTCE database (do not edit by hand)
├── tests/                            252 tests + 259 database tests (table below), xtce_interp.py (the independent XTCE reader)
├── tools/validate_xtce.py            checks an XTCE file against the official XSD
├── tools/mutation_check.py           injects 14 known bugs (plus 37 database and logic bugs with a server) and checks that the tests notice every one
├── docs/                             scenario.png and docs/example/ (scenario.csv, demo_console.txt)
├── .github/workflows/ci.yml          GitHub Actions: Python 3.10-3.13, database up to date, tests, schema check, demo
├── LICENSE                           AGPL-3.0
└── pyproject.toml                    package metadata; installs the `minisat` command
```

| Test file | Tests | What it covers |
|---|---|---|
| `test_ccsds.py` | 15 | header bytes by hand, random round trips, range errors, length rule, truncated recordings |
| `test_spec.py` | 32 | real spec shape and derived sizes, lookups, limits, the Norway problem, 25 invalid-spec cases, error locations |
| `test_codec.py` | 27 | round trips, hand-computed bytes, enum helpers, bad arguments, range boundaries, damaged and foreign packets |
| `test_xtce.py` | 41 | database up to date, schema validity, the independent interpreter on telemetry and commands, alarm boundaries, vital significance |
| `test_model.py` | 27 | orbit period, ground track, eclipse, power balance, clamping, FDIR, every command's rules, counters |
| `test_simulator.py` | 16 | schedule, sequence counters and wrap, chunking invariance, command effects, garbage input, rate change, reboot |
| `test_udp.py` | 4 | **real UDP sockets**: telemetry out, a command in and its effect in telemetry, speed-up, garbage datagrams |
| `test_cli.py` | 24 | every sub-command, exit codes and error messages, a recorded session decoded again |
| `test_demo.py` | 4 | the scenario's story, reproducibility, CSV and plot |
| `test_yamcs_config.py` | 7 | ports, time offset and unit agree with the codec, built-in classes only, files exist |
| `test_ontology_definitions.py` | 16 | definitions agree with the YAML read independently, hand-counted packet sizes, alarm severity boundaries, read-only |
| `test_ontology_dbconfig.py` | 9 | database URLs per role, missing or odd settings |
| `test_ontology_functions.py` | 30 | preflight at the 30 % boundary, expected effects, what the counters say, derived events, health precedence, packet-loss counting |
| `tests/db/` (9 files) | 259 | **real PostgreSQL** (need `MINISAT_TEST_ADMIN_URL`): migrations up and down, an exact privilege matrix per role, constraints, the append-only audit log; the runner (exact role matrix over every action, audit, atomicity, idempotency); the command lifecycle incl. every illegal transition; alarms and anomalies; ingestion and automations; the CLI; and the whole chain over **real UDP sockets** |

Run subsets with `pytest tests/test_udp.py -q`, or one test with `pytest -k eclipse`. To include the schema check: `XTCE_ONLINE=1 pytest -q`.

---

## 9. Status and honest limits

**Done and checked when this repo was created:**

* 197 tests pass on Python 3.11, 3.12 and 3.13; code is lint-clean (`flake8`, 125 columns).
* The generated database is up to date and valid against the XTCE 1.2 schema; the independent interpreter agrees with the codec on all packets and commands.
* 14 injected bugs were each caught (section 6).
* A real end-to-end session over UDP (simulator, listener, three commands) works as shown in section 3.3.
* The database layer (section 3.5): its tests passed on PostgreSQL 14.18 (a local server) and on PostgreSQL 16.15 started by `docker compose up -d db`
  (where the init script, role logins and `alembic upgrade head` were also tried by hand), on Python 3.12.
* The action runner and the ground station (section 3.6): all 511 tests pass (510, the XTCE schema check skips) on PostgreSQL 16 from Docker, on Python 3.12; without a database
  251 pass in a Python 3.11 environment that has only the base dependencies. The whole chain was also run by hand with the real `minisat simulate`, `ground` and `act` commands:
  a low battery became an alarm, and a heater command went SENT, ACCEPTED, VERIFIED from the satellite's own telemetry.

**Not verified yet - do these first:**

* **Yamcs has never been started with this configuration.** The environment this was written in could not download from Maven Central. Everything about Yamcs (class names, option names, how the restriction criteria and the command assignments are interpreted)
  was checked against the Yamcs 5.13.7 source code and schema, not by running it. `mvn yamcs:run` may need small fixes. The `pom.xml` is modelled on the official quickstart and is well-formed, but dependency resolution is untested.
* **GitHub Actions** (`.github/workflows/ci.yml`, including the new `database` job) has not run yet, and Python 3.10 has not been run anywhere.
* **The Python-side package has only been run on Linux.**

**Limits of the model (say these out loud if you present the project):**

* The satellite is fictional and **all numbers are illustrative**: the power budget, thermal behaviour and thresholds demonstrate the mechanics, not any real design.
* Real missions put **PUS** (ECSS packet utilisation standard) services on top of CCSDS packets, use many more packet types, and protect the link with frames, CRCs and encryption/authentication. None of that is here.
  Commands here are **not authenticated**: anyone who can send a UDP datagram to the port can command the satellite. That is acceptable for a toy on `127.0.0.1` and unacceptable for anything else.
* Telemetry is not time-ordered or reassembled; UDP can lose or reorder packets (the sequence counter would reveal it, but nothing reads it yet).
* The Yamcs setup has no users, no roles and no TLS.
* Position is a spherical-Earth, circular-orbit approximation, good for plotting, not for navigation.
* The XTCE generator covers the subset needed here (fixed-size integers and floats, enumerations, static alarms, simple commands). It is not a general XTCE writer.
* **There is no login yet.** `minisat act alice ...` believes the operator name it is given, and anyone who has the database passwords can act as anyone. The roles, the two-person rule
  and the audit log are real, but they bind the *actions*, not the person at the keyboard; authentication comes with the API (PLAN.md phase 4).
* Command verification relies on counters and the id of the latest command, so only **one command can be in flight per spacecraft**; commands are delivered **at most once** and never retried.
* Alarms have no hysteresis: a value hovering around a limit raises and clears alarms repeatedly. Verification windows (5 s and 10 s) are wall-clock values, not tuned to anything.
* One ground station watches one spacecraft; notifications to supervisors are queued in the outbox but nothing delivers them beyond a log line.
* Not built yet: the web dashboard, the HTTP API, the AI assistant, `estimateTimeToSafe` and the staged proposal that would use it.

---

## 10. Roadmap

| # | Milestone | You will learn | Done when |
|---|---|---|---|
| M1 | **First real Yamcs run**: fix whatever breaks, add screenshots of the web UI | integration, reading logs | screenshots of parameters, alarms and a command in the README |
| M2 | **Docker Compose** for Yamcs + simulator | containers | `docker compose up` shows live data |
| M3 | **Sequence-gap detection**: count lost packets from the CCSDS sequence counter, show it in telemetry | link quality monitoring | a test with injected losses reports the right number |
| M4 | **Events**: the satellite sends event messages (mode changes, FDIR) shown in the Yamcs event list | event handling | an FDIR event appears in Yamcs |
| M5 | **CRC and time tags**: add a CRC to telecommands and verify it on board | error detection | corrupted commands are rejected and counted |
| M6 | **Command verification stages**: Yamcs "command verifiers" (sent, accepted, executed) using `cmd_accepted` and `last_cmd_id` | closed-loop commanding | a rejected command shows as FAILED in Yamcs's history |
| M7 | **Pass-based visibility**: connect to [`leo-contact-planner`](https://github.com/Entorkrasniqi/leo-contact-planner) so the link is only up during passes | system integration | telemetry flows only inside planned contact windows |
| M8 | **PUS services** (housekeeping, event reporting, function management) | the real packet standard | a PUS-3 housekeeping report decodes in Yamcs |
| M9 | **Python ground-side scripts** with the Yamcs client library: a test procedure that sends commands and checks telemetry automatically | test automation for operations | a script that runs the demo scenario against Yamcs and passes/fails |
| M10 | **Authentication** of commands (message authentication code) | link security basics | a tampered command is rejected |

---

## 11. Questions you should be able to answer after this project

1. What is the difference between telemetry and telecommands, and what is the APID for?
2. Decode `08 64 c0 07 00 28` by hand. Why does the length field contain 40 when 41 bytes follow?
3. What is big-endian, and what happens if sender and receiver disagree?
4. Why is a float32 `8.1` not exactly 8.1, and why do tests compare floats with a tolerance but integers exactly?
5. Why describe packets in XTCE instead of hard-coding them in the ground software? What problem does *generating* the XTCE from a YAML file solve, and which new problem does it create (staleness) and how is it handled?
6. In XTCE, what does a restriction criterion on a child container do? What does an alarm range such as `minInclusive="35"` mean?
7. Why does the satellite re-check a command's range even though the ground tool already did? What is the lesson for any system that accepts input over a network?
8. What is the "Norway problem" and where else in your own work could the same class of bug hide (implicit type conversion of config values)?
9. Why is the independent XTCE interpreter better evidence than a unit test of the generator, and what does it still *not* prove?
10. What is FDIR, and why must the ground software display refusals and mode changes clearly?
11. Which real-mission feature missing here would you add first, and why?

---

## 12. References and licence

* Yamcs - open-source mission control: <https://yamcs.org>; documentation and the quickstart project <https://github.com/yamcs/quickstart>; source <https://github.com/yamcs/yamcs>.
* CCSDS, *Space Packet Protocol* (CCSDS 133.0-B) and the CCSDS publications list: <https://public.ccsds.org>.
* XTCE (XML Telemetric and Command Exchange), OMG/CCSDS standard: <https://www.omg.org/spec/XTCE>; the XSD used for validation is the one shipped in the Yamcs repository.
* ECSS-E-ST-70-41C, *Telemetry and telecommand packet utilization* (PUS) - what real missions add on top of the space packet.
* IEEE 754 floating point; Python documentation of the `struct`, `socket` and `argparse` modules.
* The "Norway problem" of YAML 1.1 booleans: see the YAML 1.1 and 1.2 specifications (<https://yaml.org>); PyYAML implements 1.1.
* Wertz, Everett and Puschell (eds.), *Space Mission Engineering: The New SMAD* - orbits, eclipse geometry, power and thermal budgets in more depth than this toy needs.
* M. Okabe and K. Ito, *Color Universal Design* (the colour-blind-safe palette used in the figure).

**Licence: GNU Affero General Public License v3.0** - see [`LICENSE`](LICENSE). The sibling projects are MIT-licensed; this one is AGPL because the `yamcs/` folder is configuration for Yamcs (which is AGPL-3.0) and is modelled on Yamcs's own quickstart project, and
I chose to keep the whole repository under the same licence rather than split it. What that means in practice: you may use, study and modify it freely; if you run a modified version as a network service for other people you must offer them the source.
(The Python package does not contain or link to Yamcs code, so a different licence for that part alone would be possible; this is not legal advice.) The XTCE schema is *not* copied into the repository; it is downloaded when you ask for the schema check.
# mmc
