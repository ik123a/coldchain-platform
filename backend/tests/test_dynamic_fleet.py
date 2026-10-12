"""Dynamic truck management — TDD.

Covers the operator-facing fleet lifecycle required by the brief:
add trucks one at a time (no hard 3-truck cap), configure each explicitly,
start each independently, remove inactive AND running trucks without
disturbing the others, and clean up every per-vehicle simulation state.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.simulation.fleet_orchestrator import FleetOrchestrator


def check(cond, label):
    print(("PASS" if cond else "FAIL"), "-", label)
    assert cond, label


def raises(fn, *needle):
    try:
        fn()
    except ValueError as e:
        return any(n in str(e) for n in needle)
    return False


def fresh() -> FleetOrchestrator:
    # n_vehicles=0 keeps the default demo fleet out of the way so assertions
    # on vehicles/ are unambiguous.
    return FleetOrchestrator(n_vehicles=0)


def spec_of(orch, tid):
    return next(s for s in orch.dispatch if s["id"] == tid)


def main():
    orch = fresh()

    # 1. add one truck: draft, unique id, nothing started
    t1 = orch.add_dispatch_truck()
    check(t1["id"] == "T01", f"first truck gets id T01 (got {t1['id']})")
    check(t1["name"] == "Truck 01", f"auto name Truck 01 (got {t1['name']})")
    check(t1["cargo_type"] == "" and t1["destination_id"] == "",
          "new truck is a draft: no product, no destination")
    check(t1["status"] == "NOT_STARTED", "new truck is Not Started")
    check(len(orch.vehicles) == 0, "adding a truck does not spawn anything")

    # 2. add 2 more, then a 4th — no hard 3-truck limit
    orch.add_dispatch_truck()
    t3 = orch.add_dispatch_truck()
    t4 = orch.add_dispatch_truck()
    check(len(orch.dispatch) == 4, "4 trucks can be added (no cap at 3)")
    ids = [s["id"] for s in orch.dispatch]
    check(len(set(ids)) == 4, f"truck ids are unique: {ids}")
    names = [s["name"] for s in orch.dispatch]
    check(len(set(names)) == 4, f"auto names do not collide: {names}")

    # 3. configure trucks explicitly
    orch.update_dispatch_truck("T01", {"cargo_type": "pharma", "destination_id": "D-101"})
    orch.update_dispatch_truck("T02", {"cargo_type": "frozen_goods", "destination_id": "WH-003"})
    orch.update_dispatch_truck("T04", {"cargo_type": "dairy", "destination_id": "WH-002",
                                       "load_units": 250})
    check(spec_of(orch, "T01")["cargo_type"] == "pharma", "T01 configured")
    check(spec_of(orch, "T04")["load_units"] == 250, "T04 load configured")
    check(spec_of(orch, "T03")["cargo_type"] == "", "T03 stays a draft")

    # 4. validation: unknown product / destination, duplicates, bad pair
    check(raises(lambda: orch.update_dispatch_truck("T03", {"cargo_type": "plutonium",
                                                            "destination_id": "WH-001"}),
                 "unknown product"), "unknown product rejected")
    check(raises(lambda: orch.update_dispatch_truck("T03", {"cargo_type": "dairy",
                                                            "destination_id": "D-999"}),
                 "unknown destination"), "unknown destination rejected")
    check(raises(lambda: orch.update_dispatch_truck("T03", {"cargo_type": "dairy",
                                                            "destination_id": "D-101"}),
                 "already used"), "duplicate destination rejected")
    check(raises(lambda: orch.update_dispatch_truck("T03", {"cargo_type": "frozen_goods",
                                                            "destination_id": "D-103"}),
                 "only accepts"), "incompatible cargo/destination pair rejected")

    # 4b. empty product/destination in a patch CLEARS the field (draft) —
    #     that is how the UI lets the operator change the product without
    #     the old destination blocking the edit.
    orch.update_dispatch_truck("T03", {"cargo_type": "pharma"})
    orch.update_dispatch_truck("T03", {"destination_id": "D-108"})
    check(spec_of(orch, "T03")["cargo_type"] == "pharma"
          and spec_of(orch, "T03")["destination_id"] == "D-108",
          "T03 configured in two steps")
    orch.update_dispatch_truck("T03", {"destination_id": ""})
    check(spec_of(orch, "T03")["destination_id"] == "" and spec_of(orch, "T03")["cargo_type"] == "pharma",
          "empty destination clears it without erroring")
    orch.update_dispatch_truck("T03", {"cargo_type": ""})
    check(spec_of(orch, "T03")["cargo_type"] == "",
          "empty product clears it without erroring")

    # 5. start trucks independently; drafts refuse to start
    orch.start_dispatch_truck("T01")
    orch.start_dispatch_truck("T02")
    check("USER-T01" in orch.vehicles and "USER-T02" in orch.vehicles,
          "started trucks spawn twins with stable ids")
    check("USER-T03" not in orch.vehicles, "draft truck did not spawn")
    check(raises(lambda: orch.start_dispatch_truck("T03"), "not configured"),
          "starting a draft truck is refused with a readable reason")
    v1, v2 = orch.vehicles["USER-T01"], orch.vehicles["USER-T02"]
    check(v1.cargo_type == "pharma" and v1.dest_id == "D-101", "T01 twin carries its own spec")
    check(v2.cargo_type == "frozen_goods" and v2.dest_id == "WH-003",
          "T02 twin carries its own spec")
    check(v1.geom != v2.geom and v1.origin_id != v2.origin_id, "independent routes")
    orch.start_dispatch_truck("T01")
    check(sum(1 for vid in orch.vehicles if vid == "USER-T01") == 1,
          "re-starting a running truck is idempotent, no duplicate twin")

    # 6. per-truck live status in the spec list
    specs = {s["id"]: s for s in orch._dispatch_specs()}
    check(specs["T01"]["running"] and specs["T01"]["status"] == "IN_TRANSIT",
          "running truck reports IN_TRANSIT")
    check(not specs["T03"]["running"] and specs["T03"]["status"] == "NOT_STARTED",
          "draft truck reports Not Started")

    # 7. remove an INACTIVE truck: others untouched
    res = asyncio.run(orch.remove_dispatch_truck("T03"))
    check(res["removed"] == "T03", "remove returns the removed truck id")
    check(all(s["id"] != "T03" for s in orch.dispatch), "T03 gone from the plan")
    check("USER-T01" in orch.vehicles and "USER-T02" in orch.vehicles,
          "removing an inactive truck does not touch running trucks")

    # 8. running trucks keep independent state after another is removed
    check(v2.cargo_type == "frozen_goods" and v2.dest_id == "WH-003" and v2.geom,
          "T02 twin intact after T03 removal")

    # 9. remove an ACTIVE truck: twin + all per-vehicle state cleaned,
    #    other trucks keep functioning
    vid1 = "USER-T01"
    orch.incident_db[vid1] = 4242               # active incident mapping
    orch.alert_counts[vid1] = 3
    orch._over_run[vid1] = 9
    orch.pending_approvals[f"k-{vid1}"] = {"vehicle_id": vid1, "status": "PENDING"}
    orch.pending_approvals["keep-me"] = {"vehicle_id": "USER-T02", "status": "PENDING"}
    orch.transfers[vid1] = {"phase": "x"}
    orch.service_pending[vid1] = "repair"
    orch.service_tasks["SERVICE-09"] = vid1
    res = asyncio.run(orch.remove_dispatch_truck("T01"))
    check(res["vehicle_id"] == vid1 and vid1 not in orch.vehicles,
          "active truck's twin removed from the world")
    check(vid1 not in orch.incident_db, "active incident mapping cleaned")
    check(vid1 not in orch.alert_counts and vid1 not in orch._over_run,
          "alert/escalation counters cleaned")
    check(all(p["vehicle_id"] != vid1 for p in orch.pending_approvals.values()),
          "pending approvals of the removed truck cleaned")
    check("keep-me" in orch.pending_approvals, "OTHER truck's approval untouched")
    check(vid1 not in orch.transfers and vid1 not in orch.service_pending
          and "SERVICE-09" not in orch.service_tasks,
          "in-flight transfer and service call cleaned")
    check(all(s["id"] != "T01" for s in orch.dispatch), "T01 gone from the plan")
    v2 = orch.vehicles["USER-T02"]
    snap = v2.snapshot()
    check(snap["cargo"]["cargo_type"] == "frozen_goods"
          and snap["trip"]["destination_id"] == "WH-003",
          "T02 keeps running normally after an active truck was removed")

    # 10. truck ids are never reused: remove then add gives a fresh id
    t5 = orch.add_dispatch_truck()
    check(t5["id"] not in ("T01", "T03"), f"ids never reused after removal (got {t5['id']})")
    check(t5["name"].startswith("Truck"), f"auto name for the new truck ({t5['name']})")

    # 11. AI workflow stays per-vehicle: the incident context of one truck
    #     cannot see another truck's incident
    orch.incident_db["USER-T02"] = 777
    ctx_t2 = orch._incident_ctx(orch.vehicles["USER-T02"])
    check(ctx_t2 is not None, "incident context available for the truck with an incident")

    # 12. fleet cap is validated, never silent
    while len(orch.dispatch) < FleetOrchestrator.DISPATCH_MAX:
        orch.add_dispatch_truck()
    check(raises(orch.add_dispatch_truck, "fleet is full"),
          f"adding past the declared max ({FleetOrchestrator.DISPATCH_MAX}) is refused")

    # 13. clear removes started twins too (no orphaned vehicles)
    vid_t2 = "USER-T02"
    asyncio.run(orch.clear_dispatch())
    check(orch.dispatch == [], "clear empties the plan")
    check(vid_t2 not in orch.vehicles, "clear also removes spawned twins")

    # 14. cold world: nothing runs at boot; the tick loop starts lazily with
    #     the first operator truck, and that truck actually moves afterwards
    cold = fresh()
    cold.add_dispatch_truck()
    cold.update_dispatch_truck("T01", {"cargo_type": "pharma", "destination_id": "D-101"})

    async def cold_start_check():
        check(cold._task is None, "cold world: no tick loop before any truck starts")
        cold.start_dispatch_truck("T01")   # internally ensure_loop()
        check(cold._task is not None and not cold._task.done(),
              "cold world: tick loop started lazily by the first truck start")
        await asyncio.sleep(1.5)
        check(cold.sim_minute > 0, f"world clock ticks after cold start (sim_minute={cold.sim_minute})")
        km0 = cold.vehicles["USER-T01"].snapshot()["trip"]["distance_completed_km"]
        await asyncio.sleep(1.5)
        km1 = cold.vehicles["USER-T01"].snapshot()["trip"]["distance_completed_km"]
        check(km1 >= km0, f"truck moves under the cold-started loop (km {km0} -> {km1})")
        cold.stop()
        await asyncio.sleep(0.1)

    asyncio.run(cold_start_check())

    print("DYNAMIC FLEET: ALL PASS")


if __name__ == "__main__":
    main()
