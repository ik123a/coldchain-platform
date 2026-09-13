"""Smoke runner: real server boot + full demo loop + WS observer. Run with python smoke_run.py"""
import asyncio, json, time
import httpx, uvicorn, websockets
from app.main import app

PORT = 8401
results = {"steps": [], "ws": 0}


async def main():
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error")
    server = uvicorn.Server(config)
    t = asyncio.create_task(server.serve())
    await asyncio.sleep(2.5)
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{PORT}", timeout=30) as c:
        results["steps"].append(("status", (await c.get("/api/status")).json()))
        results["steps"].append(("demo_base", (await c.post("/api/demo/base")).json().get("facility", {}).get("name")))
        r = (await c.post("/api/demo/launch?autopilot=false&failure=compressor_failure&after_ticks=8")).json()
        sid = r["simulation_id"]
        results["steps"].append(("demo_launch", r))
        results["steps"].append(("start", (await c.post(f"/api/simulations/{sid}/start")).json()))

        async def ws_listen():
            try:
                async with websockets.connect(f"ws://127.0.0.1:{PORT}/ws") as w:
                    async for msg in w:
                        results["ws"] += 1
            except asyncio.CancelledError:
                pass
            except Exception as e:
                results["ws_err"] = str(e)

        wt = asyncio.create_task(ws_listen())

        await asyncio.sleep(5)
        results["steps"].append(("inject", (await c.post(f"/api/simulations/{sid}/failure/compressor_failure")).json()))

        st = {}
        for _ in range(12):
            await asyncio.sleep(2)
            st = (await c.get(f"/api/simulations/{sid}")).json()
            if st.get("incident_status"):
                break
        results["steps"].append(("incident_status", st.get("incident_status"), "peak", st.get("peak_temperature")))

        incs = (await c.get("/api/incidents")).json()
        results["steps"].append(("incidents_count", len(incs)))
        if incs:
            iid = incs[0]["id"]
            d = (await c.get(f"/api/incidents/{iid}")).json()
            results["steps"].append(("incident_detail", {"status": d["status"], "root": d["root_cause"],
                                                          "conf": d["root_cause_confidence"],
                                                          "actions": [a["action"] for a in d["actions"][:3]]}))
            act_to = next((a["action"] for a in d["actions"] if a["action"] != "monitor"), "activate_backup_cooling")
            results["steps"].append(("execute_primary", act_to, (await c.post(f"/api/incidents/{iid}/action", json={"action": act_to})).json()))
            await asyncio.sleep(2)
            results["steps"].append(("execute_support", "close_door", (await c.post(f"/api/incidents/{iid}/action", json={"action": "close_door"})).json()))

            for _ in range(20):
                await asyncio.sleep(2)
                d = (await c.get(f"/api/incidents/{iid}")).json()
                if d["status"] == "RESOLVED":
                    break
            results["steps"].append(("final_incident_status", d["status"]))
            results["steps"].append(("analyses_agents", [a["agent_name"] for a in d["analyses"]]))

            wf = (await c.post(f"/api/incidents/{iid}/what-if?ticks=8")).json()
            results["steps"].append(("what_if", {"cur": wf["current_risk"], "proj": wf["proj_final_risk"], "proj_temp": wf["proj_final_temp"]}))
            ask = (await c.post(f"/api/incidents/{iid}/ask-ai", json={"question": "What is the most likely cause?"})).json()
            results["steps"].append(("ask_ai", ask["answer"][:160]))
            results["steps"].append(("report_json_bytes", len((await c.get(f"/api/reports/{iid}.json")).content)))
            rp = (await c.get(f"/api/reports/{iid}.pdf"))
            results["steps"].append(("report_pdf_bytes", len(rp.content), rp.headers.get("content-type")))
        results["steps"].append(("dashboard", (await c.get("/api/dashboard")).json()))
        results["steps"].append(("analytics", (await c.get("/api/analytics")).json()))
        results["steps"].append(("ws_events_total", results["ws"]))
        wt.cancel()
    await server.shutdown()
    t.cancel()


if __name__ == "__main__":
    asyncio.run(main())
    for s in results["steps"]:
        print(" •", s)
    print("ws_events observed:", results.get("ws"))
    if "ws_err" in results: print("ws_error:", results["ws_err"])
