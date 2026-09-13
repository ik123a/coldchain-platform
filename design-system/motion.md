# ColdChain Rescue — Motion & Animation Principles

## Core Tenet
> **Motion must communicate state, priority, and cause-and-effect. It must never exist simply to look flashy.**

---

## 1. Timing Curves & Durations

| Motion Type | Duration | Easing Curve | Purpose |
|---|---|---|---|
| **Micro HUD transitions** | 180ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Hover badges, tooltip fades |
| **Drawer / Sheet Slide** | 320ms | `cubic-bezier(0.32, 0.72, 0, 1)` | Bottom sheet open/close |
| **Map Camera Push** | 800ms | `cubic-bezier(0.25, 1, 0.5, 1)` | Smooth vehicle focus |
| **Vehicle Heading Turn** | 400ms | `ease-out` | Smooth vehicle marker rotation on GPS tick |
| **Telemetry Metric Transition** | 300ms | `ease-out` | Smooth number counting on temperature change |
| **Route Path Draw** | 600ms | `ease-in-out` | Drawing calculated detour corridor |

---

## 2. Telemetry State Interpolation (Lerp)
- Vehicle positions on the map must interpolate smoothly between GPS updates rather than teleporting.
- Position updates apply linear interpolation with a lerp factor of `0.15` per animation frame.

---

## 3. Severity Transitions
- **Incident Escalation**: When temperature breaches 8.0°C, the badge transitions from Emerald to Amber to Rose over 600ms without flashing or jarring screen shakes.
- **Pulse Alert**: Critical vehicle markers pulse with a 2.0s sine wave cycle (gentle expansion from 18px to 28px, fading to 0 opacity).
- **Recovery Verification**: When recovery cooling is confirmed, the badge transitions through Amber into Emerald over 800ms with a solid confirm checkmark.

---

## 4. Prohibited Animations
- **No Floating Background Particles**: Zero canvas dust particles or floating nodes.
- **No Infinite Spinning Holograms**: All motion stops once the operational state is steady.
- **No Screen-wide Red Flashes**: Stress-inducing full-screen flashes are banned in operational environments.
