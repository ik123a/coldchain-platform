# ColdChain Rescue — detailed film script

Target: ~4:30. Every claim below is the product's real output.

## Ch 0 — COLD OPEN (0:00–0:20)
A truck sits at three point nine degrees. Nothing is wrong. That is the problem:
nothing is wrong *yet*, and nobody knows how long it stays that way.

## Ch 1 — THE STAKE (0:20–0:45)
A pharmaceutical shipment leaves a facility in Delhi. Its entire value is
decided by one number in one box on the truck. If that box drifts four degrees,
the load is worth nothing, and nobody finds out until the customer opens it.
The cold chain is not a container. It is a countdown nobody was watching.

## Ch 2 — A COLD WORLD (0:45–1:20)
The system boots into nothing. No trucks, no simulation, no fake data.
You add a truck. You choose the product — frozen, pharma, dairy, produce.
You choose the destination warehouse. Nothing is assigned automatically,
because an operations team that cannot describe its own fleet cannot be
trusted to run one.

## Ch 3 — THE LIVE WORLD (1:20–2:00)
Three trucks become fourteen twins on the Delhi North Corridor. Every one is
moving, on a route, with a temperature, a speed and a load, streamed over a
WebSocket rather than polled. Traffic, weather and ambient heat are part of the
world, so a truck's reading is never just a number in isolation.

## Ch 4 — WHAT IT WATCHES (2:00–2:40)
Thirteen incident types are detectable, and every one is derived from a signal
that genuinely exists in the telemetry. Compressor failure. Door left open.
Power loss. Heatwave. Cooling degradation. Sensor fault.
And four more that it will not claim, because the sensors do not exist.
Refrigerant pressure. Door seal decay. Equipment age. Confirmed spoilage.
Those are declared as gaps rather than faked, and that list is the honest part
of the product.

## Ch 5 — PREDICTION (2:40–3:10)
Now the part that matters. A compressor dies at nine seconds.
The reading does not wait for the ceiling. It projects the crossing from the
trend and raises the incident while there is still margin — five seconds of
warning, before the number breaches, not after.
The model is a linear trend projection and it says so. It is not kinetics. It
does not pretend to be a validated shelf-life curve.

## Ch 6 — WHY (3:10–3:40)
And it is not a guess. Compressor failure at sixty two percent confidence,
with cooling degradation, door seal and ambient heat all considered, scored and
kept visible even though they lost. A system that only tells you what you
already suspected is not diagnosing anything.

## Ch 7 — WHERE TO GO (3:40–4:10)
Nearest is not best. Every cold store is scored on six axes — travel time,
cargo fit, traffic, distance, cost and energy — and the weights are published.
The winner here is eleven minutes away at three hundred rupees.
The *closest* warehouse scores a third of that.
Money is in the ranking because a rescue that bankrupts the operator is not a
rescue, it is just an expensive log entry.

## Ch 8 — THE GATE (4:10–4:40)
And then it stops. Every recommendation waits.
If nobody answers, the agent escalates on its own — because an unanswered
critical is itself a fault. But it never executes on its own. The authority to
move the load stays with a person, always.

## Ch 9 — WHAT IT LEARNED (4:40–5:10)
Every incident ends in a report: the truck, the fault, what was done, and a score
on how well it was handled. And when it failed — when the load was lost anyway
— it writes down what it would do differently next time.
That is the part most systems skip, and it is the part that compounds.

## Ch 10 — PROOF (5:10–5:30)
Nine test suites. Six deterministic scenarios that replay identically.
Thirteen incident types, four declared gaps, zero invented sensors.
ColdChain Rescue. Eight point seven seconds of margin.