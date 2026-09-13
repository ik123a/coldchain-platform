"""Delhi-NCR demo dataset: warehouses, destinations, route polyline templates,
drivers. Coordinates are realistic-looking demo data around Delhi NCR.
POLYLINE keys are ordered (origin, dest) node ids; points are [lng, lat]."""

REGION = {"name": "Delhi NCR", "center": [77.10, 28.58], "zoom": 9.5}

WAREHOUSES = [
    {"id": "WH-001", "name": "Delhi Central Cold Storage", "lat": 28.6139, "lng": 77.2090,
     "capacity": 1000, "available_capacity": 430, "cargo_types": ["fresh_produce", "dairy", "frozen_goods"],
     "docks": 4, "busy_docks": 1, "queue_min": 4, "proc_min": 12, "status": "OPERATIONAL"},
    {"id": "WH-002", "name": "Gurugram Distribution Hub", "lat": 28.4595, "lng": 77.0266,
     "capacity": 1200, "available_capacity": 700, "cargo_types": ["fresh_produce", "dairy", "pharma"],
     "docks": 5, "busy_docks": 1, "queue_min": 3, "proc_min": 10, "status": "OPERATIONAL"},
    {"id": "WH-003", "name": "Noida Cold Warehouse", "lat": 28.5355, "lng": 77.3910,
     "capacity": 900, "available_capacity": 210, "cargo_types": ["frozen_goods", "dairy"],
     "docks": 3, "busy_docks": 2, "queue_min": 9, "proc_min": 15, "status": "OPERATIONAL"},
    {"id": "WH-004", "name": "Ghaziabad Distribution Center", "lat": 28.6692, "lng": 77.4570,
     "capacity": 1100, "available_capacity": 640, "cargo_types": ["fresh_produce", "frozen_goods"],
     "docks": 4, "busy_docks": 1, "queue_min": 5, "proc_min": 11, "status": "OPERATIONAL"},
    {"id": "WH-005", "name": "Faridabad Cold Facility", "lat": 28.4089, "lng": 77.3178,
     "capacity": 800, "available_capacity": 90, "cargo_types": ["fresh_produce", "dairy"],
     "docks": 3, "busy_docks": 3, "queue_min": 18, "proc_min": 20, "status": "OPERATIONAL"},
    {"id": "WH-006", "name": "Airport Cold Storage", "lat": 28.5562, "lng": 77.0800,
     "capacity": 1400, "available_capacity": 980, "cargo_types": ["pharma", "frozen_goods", "fresh_produce"],
     "docks": 6, "busy_docks": 1, "queue_min": 2, "proc_min": 8, "status": "OPERATIONAL"},
    {"id": "WH-007", "name": "Hospital Distribution Center", "lat": 28.6330, "lng": 77.2820,
     "capacity": 600, "available_capacity": 150, "cargo_types": ["pharma", "dairy"],
     "docks": 2, "busy_docks": 1, "queue_min": 7, "proc_min": 14, "status": "OPERATIONAL"},
    {"id": "WH-008", "name": "Retail Distribution Hub", "lat": 28.5450, "lng": 77.2550,
     "capacity": 1000, "available_capacity": 520, "cargo_types": ["fresh_produce", "dairy", "frozen_goods", "pharma"],
     "docks": 4, "busy_docks": 2, "queue_min": 6, "proc_min": 13, "status": "OPERATIONAL"},
]

DESTINATIONS = [
    {"id": "D-101", "name": "Apollo Hospital Delhi", "lat": 28.6297, "lng": 77.2080,
     "required_cargo": ["pharma"], "priority": "CRITICAL", "capacity": 220,
     "temp_min": 2, "temp_max": 8},
    {"id": "D-102", "name": "Big Bazaar Rajouri", "lat": 28.6420, "lng": 77.1200,
     "required_cargo": ["fresh_produce", "dairy"], "priority": "HIGH", "capacity": 300,
     "temp_min": 2, "temp_max": 8},
    {"id": "D-103", "name": "Sector 18 Market Noida", "lat": 28.5700, "lng": 77.3260,
     "required_cargo": ["fresh_produce"], "priority": "NORMAL", "capacity": 250,
     "temp_min": 2, "temp_max": 8},
    {"id": "D-104", "name": "DLF Cyber Hub Gurugram", "lat": 28.4950, "lng": 77.0900,
     "required_cargo": ["dairy", "frozen_goods"], "priority": "HIGH", "capacity": 200,
     "temp_min": -20, "temp_max": 5},
    {"id": "D-105", "name": "Indirapuram Hypermarket", "lat": 28.6410, "lng": 77.3710,
     "required_cargo": ["fresh_produce", "dairy"], "priority": "NORMAL", "capacity": 280,
     "temp_min": 2, "temp_max": 8},
    {"id": "D-106", "name": "Faridabad Retail Cluster", "lat": 28.3800, "lng": 77.3100,
     "required_cargo": ["fresh_produce"], "priority": "NORMAL", "capacity": 240,
     "temp_min": 2, "temp_max": 8},
    {"id": "D-107", "name": "IGI Airport Cargo Terminal", "lat": 28.5620, "lng": 77.1100,
     "required_cargo": ["pharma", "frozen_goods"], "priority": "URGENT", "capacity": 350,
     "temp_min": -22, "temp_max": 8},
    {"id": "D-108", "name": "Safdarjung Hospital", "lat": 28.5670, "lng": 77.2070,
     "required_cargo": ["pharma"], "priority": "CRITICAL", "capacity": 180,
     "temp_min": 2, "temp_max": 8},
]

# [lng, lat] polylines between hub nodes. 3-7 points each.
POLYLINES = {
    ("WH-001", "WH-002"): [[77.209, 28.614], [77.160, 28.580], [77.090, 28.520], [77.027, 28.460]],
    ("WH-001", "WH-003"): [[77.209, 28.614], [77.260, 28.600], [77.330, 28.560], [77.391, 28.536]],
    ("WH-001", "WH-004"): [[77.209, 28.614], [77.280, 28.640], [77.380, 28.660], [77.457, 28.669]],
    ("WH-001", "WH-005"): [[77.209, 28.614], [77.220, 28.550], [77.300, 28.450], [77.318, 28.409]],
    ("WH-001", "WH-006"): [[77.209, 28.614], [77.170, 28.585], [77.120, 28.560], [77.080, 28.556]],
    ("WH-001", "WH-007"): [[77.209, 28.614], [77.240, 28.620], [77.282, 28.633]],
    ("WH-001", "WH-008"): [[77.209, 28.614], [77.230, 28.580], [77.255, 28.545]],
    ("WH-001", "D-101"): [[77.209, 28.614], [77.208, 28.629]],
    ("WH-001", "D-102"): [[77.209, 28.614], [77.160, 28.630], [77.120, 28.642]],
    ("WH-001", "D-108"): [[77.209, 28.614], [77.205, 28.590], [77.207, 28.567]],
    ("WH-002", "WH-006"): [[77.027, 28.460], [77.050, 28.500], [77.080, 28.556]],
    ("WH-002", "D-104"): [[77.027, 28.460], [77.060, 28.480], [77.090, 28.495]],
    ("WH-003", "WH-004"): [[77.391, 28.536], [77.410, 28.580], [77.440, 28.630], [77.457, 28.669]],
    ("WH-003", "D-103"): [[77.391, 28.536], [77.370, 28.550], [77.326, 28.570]],
    ("WH-004", "D-105"): [[77.457, 28.669], [77.420, 28.655], [77.371, 28.641]],
    ("WH-005", "D-106"): [[77.318, 28.409], [77.312, 28.395], [77.310, 28.380]],
    ("WH-006", "D-107"): [[77.080, 28.556], [77.095, 28.560], [77.110, 28.562]],
    ("WH-007", "D-108"): [[77.282, 28.633], [77.260, 28.610], [77.230, 28.590], [77.207, 28.567]],
    ("WH-008", "WH-003"): [[77.255, 28.545], [77.310, 28.540], [77.391, 28.536]],
    ("WH-008", "D-103"): [[77.255, 28.545], [77.290, 28.555], [77.326, 28.570]],
}

DRIVERS = [
    "R. Verma", "S. Khan", "A. Yadav", "P. Singh", "M. Hussain",
    "K. Reddy", "V. Sharma", "D. Patel", "N. Gupta", "T. Bose",
    "L. Chauhan", "J. Mehta",
]

CARGO_TYPES = ["fresh_produce", "dairy", "frozen_goods", "pharma"]
