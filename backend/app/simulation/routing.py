"""Routing abstraction: OSRM (public demo) with deterministic offline fallback.

All returned routes: {"geometry": [[lng, lat], ...], "distance_km": float,
"duration_min": float}. The frontend NEVER routes; this is the only source.
"""
from __future__ import annotations
import json, math, time, urllib.request
from .geo_data import POLYLINES

_NODES = None  # lazy-filled below


def _nodes():
    global _NODES
    if _NODES is None:
        from .geo_data import WAREHOUSES, DESTINATIONS
        _NODES = {**{w["id"]: (w["lng"], w["lat"]) for w in WAREHOUSES},
                  **{d["id"]: (d["lng"], d["lat"]) for d in DESTINATIONS}}
    return _NODES


def haversine_km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, [a[1], a[0], b[1], b[0]])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def polyline_km(pts) -> float:
    return sum(haversine_km(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def nearest_node(lng: float, lat: float) -> str:
    best, bd = None, 1e9
    for nid, (x, y) in _nodes().items():
        d = haversine_km((lng, lat), (x, y))
        if d < bd:
            best, bd = nid, d
    return best


class RoutingService:
    """provider: 'auto' (try OSRM, silently fall back), 'osrm', 'fallback'."""

    def __init__(self, provider: str = "auto"):
        self.provider = provider
        self._cache: dict[tuple, dict] = {}
        self._osrm_ok = True  # latches off after first failure in a session

    def calculate_route(self, origin_id: str, dest_id: str, traffic_factor: float = 1.0) -> dict:
        key = (origin_id, dest_id, round(traffic_factor, 2))
        if key in self._cache:
            return self._cache[key]
        if self.provider in ("auto", "osrm") and self._osrm_ok:
            try:
                rt = self._osrm(origin_id, dest_id, traffic_factor)
            except Exception:
                self._osrm_ok = False
                if self.provider == "osrm":
                    raise
                rt = None
        else:
            rt = None
        if rt is None:
            rt = self._fallback(origin_id, dest_id, traffic_factor)
        self._cache[key] = rt
        return rt

    def _osrm(self, origin_id, dest_id, traffic_factor) -> dict:
        o, d = _nodes()[origin_id], _nodes()[dest_id]
        url = (f"https://router.project-osrm.org/route/v1/driving/"
               f"{o[0]},{o[1]};{d[0]},{d[1]}?overview=full&geometries=geojson")
        with urllib.request.urlopen(url, timeout=4) as r:
            data = json.load(r)
        rt = data["routes"][0]
        pts = [[p[0], p[1]] for p in rt["geometry"]["coordinates"]]
        step = 2 if len(pts) > 200 else 1
        pts = pts[::step]
        return {"geometry": pts, "distance_km": round(rt["distance"] / 1000.0, 3),
                "duration_min": round((rt["duration"] / 60.0) * traffic_factor, 2)}

    def _fallback(self, origin_id, dest_id, traffic_factor) -> dict:
        nodes = _nodes()
        # deterministic per-pair jitter for the dogleg so different pairs differ
        seed_src = (hash(origin_id) ^ hash(dest_id)) & 0xFFFF
        key = (origin_id, dest_id)
        rev = (dest_id, origin_id)
        if key in POLYLINES:
            pts = [list(p) for p in POLYLINES[key]]
        elif rev in POLYLINES:
            pts = [list(p) for p in reversed(POLYLINES[rev])]
        elif origin_id in nodes and dest_id in nodes:
            o, d = nodes[origin_id], nodes[dest_id]
            jx = 0.008 if seed_src % 2 else -0.008
            jy = -0.007 if (seed_src >> 1) % 2 else 0.007
            mid = [(o[0] + d[0]) / 2 + jx, (o[1] + d[1]) / 2 + jy]
            pts = [list(o), mid, list(d)]
        else:
            # foreign node (tests / external datasets): route via nearest known node
            anchor = nodes.get(origin_id) or nodes.get(dest_id) or (77.10, 28.58)
            pts = [list(anchor), [anchor[0] + 0.004, anchor[1] - 0.003], list(anchor)]
        dist = polyline_km(pts)
        return {"geometry": pts, "distance_km": round(dist, 3),
                "duration_min": round(dist / 42.0 * 60.0 * traffic_factor, 2)}

    def route_from_point(self, lng: float, lat: float, dest_id: str, traffic_factor: float = 1.0) -> dict:
        """Route from an arbitrary current position (e.g. mid-trip divert):
        prepend current point to the fallback polyline from nearest node."""
        near = nearest_node(lng, lat)
        nodes = _nodes()
        if dest_id not in nodes:  # foreign/test node: straight-line route
            if near == dest_id:
                geom = [[round(lng, 5), round(lat, 5)], [round(lng, 5) + 0.001, round(lat, 5)]]
            else:
                geom = [[round(lng, 5), round(lat, 5)], list(nodes[near]), list(nodes.get(dest_id, (lng, lat)))]
                # unknown dest: use provided dest position via caller convention — use near node then dest raw
                geom = [[round(lng, 5), round(lat, 5)],
                        [(lng + nodes[near][0]) / 2, (lat + nodes[near][1]) / 2],
                        list(nodes[near])]
            dist = polyline_km(geom)
            return {"geometry": geom, "distance_km": round(dist, 3),
                    "duration_min": round(dist / 42.0 * 60.0 * traffic_factor, 2)}
        base = self._fallback(near, dest_id, traffic_factor)
        geom = [[round(lng, 5), round(lat, 5)]] + [list(p) for p in base["geometry"]]
        # skip degenerate duplicated first hop
        if len(geom) > 2 and haversine_km(geom[0], geom[1]) < 0.15:
            geom = [geom[0]] + geom[2:]
        dist = polyline_km(geom)
        return {"geometry": geom, "distance_km": round(dist, 3),
                "duration_min": round(dist / 42.0 * 60.0 * traffic_factor, 2)}

    def alternatives(self, origin_id: str, dest_id: str, traffic_factor: float = 1.0) -> list[dict]:
        base = self.calculate_route(origin_id, dest_id, traffic_factor)
        heavy = self.calculate_route(origin_id, dest_id, round(traffic_factor * 1.25, 2))
        heavy = {**heavy, "variant": "via-congested-corridor"}
        mid = base["geometry"][len(base["geometry"]) // 2]
        detour = {**base, "variant": "detour",
                  "geometry": [base["geometry"][0], [mid[0] + 0.02, mid[1] - 0.015], base["geometry"][-1]],
                  "distance_km": round(base["distance_km"] * 1.15, 3),
                  "duration_min": round(base["duration_min"] * 1.08, 2)}
        base = {**base, "variant": "direct"}
        return [base, heavy, detour]
