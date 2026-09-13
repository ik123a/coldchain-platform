"""
Curated prompt library for ColdChain Rescue visual reference generation.
Strictly adheres to Anti-AI-Slop design guidelines:
- Palette: Near-black #080A0F, charcoal #141B26, off-white text, emerald/amber/rose functional accents, restrained cyan.
- Aesthetics: Calm, spatial, technical, minimal, high-end editorial logistics software.
- Exclusions: No neon purple gradients, no glowing AI brains, no sci-fi holograms, no excessive glassmorphism.
"""

IMAGE_PROMPTS = {
    # 1. MAP REFERENCES
    "map-01-dark-command-center": {
        "title": "Minimal Dark Logistics Map",
        "category": "map",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Minimal dark logistics command center map interface for ColdChain Rescue. "
            "Predominantly deep charcoal near-black surface (#080A0F). Precision vector road network "
            "showing 15 discrete refrigerated truck markers along routes, 6 minimalist cold-storage warehouse hubs, "
            "and 8 delivery destinations. One truck is subtly highlighted. Faint route polylines, muted traffic density "
            "indicators in soft amber. Clean typography HUD with quiet operational hierarchy. No glowing holograms, "
            "no sci-fi cubes, no neon purple gradients. Believable enterprise logistics software."
        ),
    },
    "map-02-selected-truck": {
        "title": "Selected Refrigerated Truck Focus",
        "category": "map",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Dark logistics map interface focused on a single selected refrigerated vehicle. "
            "A small, elegant floating telemetry badge hovers near the vehicle marker: 'TRUCK-104 · 42 km/h · 4.8°C · ETA 14 min · LOW RISK'. "
            "Subtle directional heading arrow, clean route path leading toward destination. "
            "Dark charcoal map background (#0B0F17), muted road grid, restrained typography in Inter. Professional fleet software."
        ),
    },
    "map-03-high-risk-alert": {
        "title": "High-Risk Vehicle Incident Alert",
        "category": "map",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Dark logistics digital twin map showing an active cold-chain risk event. "
            "One vehicle marker subtly pulses with a restrained warm crimson/rose ring. "
            "A compact operational card indicates: 'Temperature: 10.4°C · Risk: HIGH · Time to Critical: 7m 42s'. "
            "Surrounding road network is subdued, nearest 2 cold-storage facilities subtly highlighted with dashed diversion vectors. "
            "Restrained visual urgency, calm operational software, no chaotic flashing lights."
        ),
    },
    "map-04-emergency-rerouting": {
        "title": "Autonomous Emergency Rerouting",
        "category": "map",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Dark logistics map depicting emergency rerouting. The original route line fades to a muted dashed gray, "
            "while a crisp, high-visibility solid route polyline branches off toward a nearby cold-storage facility. "
            "Candidate warehouses evaluated along the corridor with small travel-time tags (9 min, 14 min). "
            "Vehicle marker re-oriented along the new trajectory. Clean, analytical, executive decision-support interface."
        ),
    },
    "map-05-warehouse-selection": {
        "title": "AI Facility Selection Rationale",
        "category": "map",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Logistics command center map displaying facility matching for emergency offload. "
            "Three cold-storage hubs evaluated on the map: Facility A (Capacity Full, 98%), Facility B (Selected: 430/1000 units, 9 min ETA, cooling dock available), Facility C (22 min ETA). "
            "Facility B is highlighted with a crisp emerald border and subtle confidence badge '91% Match'. Clean data callout, dark minimal theme."
        ),
    },
    "map-06-fleet-overview": {
        "title": "Fleet Overview with Smart Clustering",
        "category": "map",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "High-density fleet overview on a dark city logistics map showing 30+ refrigerated vehicles. "
            "Subtle visual clustering for regional groups, color-coded status dots (green for nominal, amber for warning, single rose dot for critical). "
            "Muted road network, restrained information density. The interface breathes with ample whitespace and crisp hierarchy. Professional fleet operations."
        ),
    },
    "map-07-vehicle-follow": {
        "title": "Vehicle Follow / Chase Mode",
        "category": "map",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Dark logistics UI in vehicle-follow tracking mode. The camera is locked onto refrigerated truck TRUCK-082 cruising along a highway corridor. "
            "Minimalist HUD at the bottom edge showing: Speed 58 km/h, Compass Heading 042° NE, Reefer Temp 4.1°C, Remaining Distance 28.4 km. "
            "Smooth road perspective, dark charcoal aesthetic, zero decorative clutter."
        ),
    },
    "map-08-incident-mode": {
        "title": "Incident Focus & Response Mode",
        "category": "map",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Incident response command view. The map is centered on an isolated refrigerated vehicle experiencing thermal runaway. "
            "A structured bottom sheet displays incident telemetry: compressor degradation 84%, Arrhenius degradation projection curve, "
            "and an AI action prompt: 'Diversion to Alpha Hub Recommended'. Restrained enterprise incident response interface."
        ),
    },

    # 2. TEMPERATURE & REFRIGERATION TELEMETRY
    "temp-01-telemetry-panel": {
        "title": "Minimalist Cold-Chain Telemetry Panel",
        "category": "telemetry",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Minimalist cold-chain telemetry interface card. Deep charcoal surface (#0D121C) with fine 1px border. "
            "Clear typographic hierarchy: OUTSIDE 41.8°C, INSIDE 5.2°C, TARGET 2–8°C. "
            "A thin horizontal range bar indicates current temperature safely within the nominal zone. "
            "Monospace tabular data, crisp Inter labels, calm engineering aesthetic."
        ),
    },
    "temp-02-temp-graph": {
        "title": "Inside vs Outside Temperature Trajectory",
        "category": "telemetry",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Clean data visualization showing dual temperature curves over a 60-minute window. "
            "Dashed amber line representing rising outside ambient temperature (38°C to 42°C). "
            "Solid teal line representing refrigerated internal cargo temperature held steady at 4.6°C. "
            "Subtle shaded safe corridor (2°C to 8°C). Monospace axes, clean time markers, no excessive chart glow."
        ),
    },
    "temp-03-compressor-degradation": {
        "title": "Compressor Degradation & Thermal Spike",
        "category": "telemetry",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Data interface illustrating mechanical cooling failure. "
            "Telemetry timeline showing inside temperature rising: 5.1°C → 7.3°C → 9.2°C under 42°C outside heat. "
            "Refrigeration status tag: 'Compressor Degraded · Efficiency 32%'. "
            "Subtle projected dashed line crossing the critical 8°C threshold. Analytical, clear, calm warning styling."
        ),
    },
    "temp-04-recovery-curve": {
        "title": "Thermal Recovery & Stabilization",
        "category": "telemetry",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Temperature curve showing successful cold-chain recovery. "
            "Internal temperature descending from 10.4°C down to 9.1°C → 7.7°C → 5.2°C back inside the safe zone. "
            "A modest confirmation badge reads 'AI RECOVERY VERIFIED'. Soft emerald trajectory line on dark background."
        ),
    },

    # 3. VEHICLE TELEMETRY & HEALTH
    "telemetry-01-vehicle-details": {
        "title": "Vehicle Kinetic Details HUD",
        "category": "telemetry",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Restrained vehicle kinematics telemetry display. Dark charcoal card showing: "
            "Speed 42 km/h, Heading EAST (094°), Distance 12.7 km, ETA 18 min. "
            "Clean tabular layout, subtle monospace coordinates, high legibility, professional telematics."
        ),
    },
    "telemetry-02-vehicle-health": {
        "title": "Multi-System Vehicle Health Diagnostics",
        "category": "telemetry",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Subsystem health diagnostics panel for a refrigerated vehicle: "
            "Overall Health 94%, Engine 96%, Brakes 92%, Tires 89%, Cooling Compressor 87%. "
            "Thin horizontal progress gauges in muted neutral teal and off-white. No gaming HUD elements, no 3D chrome rendering."
        ),
    },
    "telemetry-03-driver-behavior": {
        "title": "Driver Safety & Telematics Metric",
        "category": "telemetry",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Driver behavior and route adherence analytics card: "
            "Safety Score 94, Speeding Events 0, Harsh Braking 1, Route Adherence 97%. "
            "Minimalist typography, clean tabular alignment, dark enterprise UI."
        ),
    },

    # 4. CARGO HEALTH & KINETICS
    "cargo-01-cargo-health": {
        "title": "Cargo Vulnerability & RSL Assessment",
        "category": "cargo",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Cargo health monitoring card: Cargo Type: Fresh Bio-Vaccines / Produce. "
            "Capacity Load: 74%, Current Health: 91%, Risk Rating: HIGH. "
            "Remaining Shelf Life countdown timer calculated via Arrhenius kinetics. Dark UI, precise numbers."
        ),
    },
    "cargo-02-thermal-exposure": {
        "title": "Cumulative Thermal Kinetic Exposure",
        "category": "cargo",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Technical visualization of cumulative temperature exposure (Degree-Minutes above 8°C). "
            "Discrete step graph showing accumulated thermal debt over transit time. Monospace legend and data tags."
        ),
    },
    "cargo-03-cargo-transfer": {
        "title": "Cross-Vehicle Cargo Offload Protocol",
        "category": "cargo",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Logistics operational schematic showing cargo transfer between two refrigerated trucks. "
            "Truck A (failing unit): 74% → 44% load. Truck B (relief unit): 38% → 68% load. "
            "Clean directional offload vector, load transfer progress bar, updated weight balance. Professional logistics transfer."
        ),
    },

    # 5. AI OPERATIONS & AGENT STATE
    "ai-01-operations-panel": {
        "title": "AI Operations Reasoning Feed",
        "category": "ai",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Autonomous AI operations feed for logistics command center. "
            "Structured chronological stream with discrete operational steps: "
            "● Monitoring: Analyzing temperature trend (+0.28°C/min) "
            "● Diagnosis: Compressor efficiency degraded to 34% "
            "● Prediction: Critical threshold breach in 7m 42s "
            "● Route Engine: 5 candidate facilities evaluated "
            "● Decision: Diversion to Hub Bravo recommended. "
            "Dark charcoal container, crisp typography, operational analyst tone. No humanoid robot avatar, no glowing brain."
        ),
    },
    "ai-02-agent-graph": {
        "title": "8-Stage Multi-Agent Orchestration Graph",
        "category": "ai",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Minimalist pipeline diagram showing 8 agent nodes: "
            "Monitoring → Diagnosis → Prediction → Risk → Facility → Route → Response → Verification. "
            "Clean geometric node pills connected by subtle hairline connectors. Active node highlighted in cyan. No sci-fi spiderwebs."
        ),
    },
    "ai-03-recommendation-card": {
        "title": "Decision-Support Recommendation Card",
        "category": "ai",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "High-stakes AI recommendation modal: 'Divert to Warehouse B · ETA 9 min · Risk: HIGH → MEDIUM · Confidence: 91%'. "
            "Reasoning summary: 'Warehouse B provides the lowest safe resolution time and confirmed pre-chilled staging dock.' "
            "Restrained action buttons: 'Approve Diversion' (solid) and 'Inspect Alternatives' (ghost). Dark minimal styling."
        ),
    },

    # 6. INCIDENTS & SEVERITY STATES
    "incident-01-severity-states": {
        "title": "Systematic Incident Severity Matrix",
        "category": "incidents",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Systematic design matrix of 4 incident severity badges: "
            "1. NOMINAL (muted emerald dot, 4.2°C), "
            "2. WARNING (amber border, 7.8°C trend up), "
            "3. CRITICAL (subtle rose indicator, 10.4°C breach), "
            "4. RECOVERING (cyan progress arc, descending to 5.8°C). "
            "Consistent typography, uniform spacing, enterprise design token showcase."
        ),
    },

    # 7. ROUTING & HUBS
    "route-01-comparison-matrix": {
        "title": "Multi-Route Feasibility Comparison",
        "category": "routes",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Comparative routing panel showing 3 evaluated options: "
            "Route 1: Original Destination (32 km, 44 min, Thermal Risk 98%), "
            "Route 2: Hub Gamma (18 km, 24 min, Thermal Risk 52%), "
            "Route 3: Hub Alpha (9 km, 11 min, Thermal Risk 8%, RECOMMENDED). "
            "Clean comparative columns with risk gauges and distance tags."
        ),
    },
    "warehouse-01-hub-details": {
        "title": "Cold-Storage Facility Capacity & Queue",
        "category": "warehouses",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Cold-storage warehouse facility profile card: Hub Beta. "
            "Capacity: 430 / 1000 pallets in active cold storage. Dock Queue: 2 reefers unloading, 1 bay reserved. "
            "Ambient Dock Temp: 3.8°C. Rapid turn-around capability badge. Clean dark UI with monospace metrics."
        ),
    },

    # 8. COMMAND CENTER & HERO
    "command-01-map-dominant": {
        "title": "Full-Spectrum Operations Command Center",
        "category": "hero",
        "aspect_ratio": "16:9",
        "model": "gemini-3-pro-image",
        "prompt": (
            "Full-screen dark logistics operations center for ColdChain Rescue. "
            "The dark vector city map occupies 70% of the viewport. A slim collapsible left navigation bar with subtle icons. "
            "A floating glass-neutral telemetry badge over an active reefer on the highway, and a bottom sheet displaying Arrhenius degradation curves and AI decision feed. "
            "Sophisticated, restrained, human-crafted design."
        ),
    },
    "hero-01-editorial-landing": {
        "title": "Editorial Hero: Keep Every Shipment Inside The Safe Zone",
        "category": "hero",
        "aspect_ratio": "16:9",
        "model": "gemini-3-pro-image",
        "prompt": (
            "High-end editorial web landing page hero for ColdChain Rescue. "
            "Headline: 'Keep every shipment inside the safe zone.' Subhead: 'See the problem before the cargo does.' "
            "Behind the text, a realistic digital twin view of a dark metropolis at dusk with glowing logistics trajectories and refrigerated fleet markers. "
            "Editorial typography, ample whitespace, deep navy and charcoal atmosphere, quiet confidence."
        ),
    },
    "empty-01-states": {
        "title": "Restrained Empty & Zero-Incident State",
        "category": "empty",
        "aspect_ratio": "16:9",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Restrained empty state card for logistics software: 'All 24 shipments operating within safe thermal thresholds. Zero active incidents.' "
            "Minimalist linear geometric icon of an unbroken cold chain. Charcoal container, soft muted text, no childish illustrations."
        ),
    },
    "mobile-01-bottom-sheet": {
        "title": "Mobile Field View with Drawer",
        "category": "mobile",
        "aspect_ratio": "9:16",
        "model": "gemini-3.1-flash-image",
        "prompt": (
            "Mobile interface for cold-chain fleet driver/dispatcher. Dark map background with vehicle position. "
            "A native bottom sheet pulled up halfway displaying reefer temperature (4.6°C), remaining distance (8.2 km), "
            "and active cold-chain health badge. Clean mobile touch targets, dark theme, Inter typography."
        ),
    },
}

VIDEO_PROMPTS = {
    "vid-01-live-map-push": {
        "title": "Live Map Exploration & Vehicle Push-In",
        "category": "motion",
        "duration": "7s",
        "aspect_ratio": "16:9",
        "prompt": (
            "Slow, ultra-smooth push-in camera motion across a dark logistics city map. Several refrigerated trucks move along subtle road routes. "
            "Telemetry numbers update smoothly. Camera gently glides toward one truck which receives a crisp selection outline. "
            "Professional enterprise fleet software motion, calm and restrained."
        ),
    },
    "vid-02-vehicle-tracking": {
        "title": "Precision Vehicle Tracking Along Route",
        "category": "motion",
        "duration": "8s",
        "aspect_ratio": "16:9",
        "prompt": (
            "A refrigerated logistics truck marker smoothly traverses a dark city map, rotating naturally at road intersections. "
            "A thin route line behind it remains illuminated, speed metric adjusts smoothly between 42 and 48 km/h, and ETA ticks down. "
            "Clean digital twin simulation aesthetic."
        ),
    },
    "vid-03-incident-escalation": {
        "title": "Thermal Runaway Incident Escalation",
        "category": "motion",
        "duration": "8s",
        "aspect_ratio": "16:9",
        "prompt": (
            "A moving vehicle marker transitions from normal green to amber, then to a subtle pulsing rose as its internal temperature climbs from 5.4°C to 9.2°C. "
            "A compact incident panel smoothly glides in from the right edge, and the map camera softly re-centers on the truck."
        ),
    },
    "vid-04-ai-route-decision": {
        "title": "Autonomous Route Evaluation & Selection",
        "category": "motion",
        "duration": "7s",
        "aspect_ratio": "16:9",
        "prompt": (
            "Three candidate detour route polylines draw simultaneously outward from a distressed vehicle toward three cold hubs. "
            "Two routes fade with rejected tags, while the optimal route to Hub Beta pulses once and locks into place with an emerald path."
        ),
    },
    "vid-05-rerouting-transition": {
        "title": "Dynamic Vehicle Rerouting Turn",
        "category": "motion",
        "duration": "8s",
        "aspect_ratio": "16:9",
        "prompt": (
            "A refrigerated vehicle navigating Route A encounters a virtual road obstacle. Route A turns muted gray, the diversion path to Hub Alpha illuminates, "
            "and the vehicle executes a smooth 90-degree turn onto the relief corridor. ETA updates from 42 min to 9 min."
        ),
    },
    "vid-06-temperature-failure": {
        "title": "Ambient Heatwave & Compressor Failure",
        "category": "motion",
        "duration": "7s",
        "aspect_ratio": "16:9",
        "prompt": (
            "A split telemetry graph where outside temperature line climbs rapidly to 42°C. The reefer compressor status changes to 'DEGRADED', "
            "and the inside temperature curve gradually breaches the 8°C red ceiling line with smooth animated numbers."
        ),
    },
    "vid-07-recovery-transition": {
        "title": "Thermal Recovery & Stabilization",
        "category": "motion",
        "duration": "8s",
        "aspect_ratio": "16:9",
        "prompt": (
            "Cold-chain incident resolving in real-time. Temperature readings descend smoothly: 10.4°C → 8.2°C → 5.2°C. "
            "The status pill transitions smoothly from critical rose to amber to calm emerald. Text displays: 'AI Recovery Verified'."
        ),
    },
    "vid-08-cargo-transfer": {
        "title": "Cross-Truck Cargo Transfer",
        "category": "motion",
        "duration": "8s",
        "aspect_ratio": "16:9",
        "prompt": (
            "Motion diagram of two refrigerated trucks parked at a rendezvous point. A digital offload progress bar flows between them, "
            "Truck A load drops from 74% to 44% while Truck B load increases from 38% to 68%. Thermal risk metric drops to zero."
        ),
    },
    "vid-09-warehouse-docking": {
        "title": "Warehouse Geofence Arrival & Docking",
        "category": "motion",
        "duration": "7s",
        "aspect_ratio": "16:9",
        "prompt": (
            "Reefer vehicle approaches a cold-storage facility boundary. As it crosses the soft dashed geofence perimeter, status switches: "
            "'En Route' → 'Arrived' → 'Docking at Bay 3'. Smooth UI state transition."
        ),
    },
    "vid-10-fleet-overview": {
        "title": "Multi-Vehicle Citywide Fleet Movement",
        "category": "motion",
        "duration": "8s",
        "aspect_ratio": "16:9",
        "prompt": (
            "Citywide bird's-eye view of 20+ simulated refrigerated vehicles moving smoothly across urban arterials at night. "
            "Subtle route trails, calm dark cartography, synchronized telemetry updates."
        ),
    },
    "vid-11-ai-agent-state": {
        "title": "Multi-Agent State Pipeline Progression",
        "category": "motion",
        "duration": "7s",
        "aspect_ratio": "16:9",
        "prompt": (
            "A horizontal agent pipeline where active state flows across nodes: "
            "Monitoring → Diagnosis → Prediction → Risk → Route → Response → Verification. "
            "Each node lights up with a calm, subtle illumination as reasoning progresses."
        ),
    },
    "vid-12-what-if-simulation": {
        "title": "What-If Scenario Divergence",
        "category": "motion",
        "duration": "8s",
        "aspect_ratio": "16:9",
        "prompt": (
            "Simulation screen where a single timeline splits into two branching paths: Path A (Continue, temperature reaches 14°C, cargo ruined) "
            "and Path B (Divert, temperature stabilizes at 5.2°C). The AI outlines Path B in emerald."
        ),
    },
    "vid-13-traffic-congestion": {
        "title": "Traffic Gridlock & Autonomous Recalibration",
        "category": "motion",
        "duration": "7s",
        "aspect_ratio": "16:9",
        "prompt": (
            "A road segment turns amber then dark red representing sudden traffic gridlock. Reefer speed slows, ETA extends, "
            "triggering an automated AI prompt and instantaneous detour reroute around the bottleneck."
        ),
    },
    "vid-14-warehouse-comparison": {
        "title": "Dynamic Facility Ranking Animation",
        "category": "motion",
        "duration": "7s",
        "aspect_ratio": "16:9",
        "prompt": (
            "Three warehouse cards animate into comparison view. Bars for Distance, Queue, and Temperature compatibility populate. "
            "Warehouse Beta is highlighted with highest score."
        ),
    },
    "vid-15-full-autonomous-demo": {
        "title": "Full Autonomous Rescue Lifecycle Sequence",
        "category": "motion",
        "duration": "8s",
        "aspect_ratio": "16:9",
        "prompt": (
            "A condensed 8-second sequence: Vehicle cruising → Temperature anomaly alert → AI agent diagnosis → "
            "Facility search → Automated detour → Safe arrival & temperature restoration. High-end product trailer feeling."
        ),
    },
}
