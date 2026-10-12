"use client";
import Link from "next/link";
import {
  Thermometer, Route, Siren, ShieldCheck, Activity, Cpu,
} from "lucide-react";

const CAPABILITIES = [
  {
    n: "01",
    title: "Thermal integrity",
    body: "A least-squares fit over recent readings turns the warming trend into a safe-remaining-time projection, reported with its confidence and stated as a linear extrapolation rather than validated kinetics",
    href: "/twin",
    icon: Thermometer,
    tone: "var(--thermal-1)",
  },
  {
    n: "02",
    title: "Rescue dispatch",
    body: "A compressor failure routes a service vehicle, reserving a finite shared bay so concurrent requests cannot overbook capacity.",
    href: "/live-map",
    icon: Siren,
    tone: "var(--thermal-5)",
  },
  {
    n: "03",
    title: "Contested routing",
    body: "Facility ranking scores ETA, queue, capacity and cargo compatibility — never distance alone — and projects cargo condition at arrival.",
    href: "/dashboard",
    icon: Route,
    tone: "var(--thermal-3)",
  },
  {
    n: "04",
    title: "Verified recovery",
    body: "An incident closes only after a confirmed recovery window. A timeout is not recovery, and the decision is written to an audit trail.",
    href: "/incidents",
    icon: ShieldCheck,
    tone: "var(--thermal-2)",
  },
];

const PRINCIPLES = [
  { label: "Determinism", value: "No LLM in the decision path", icon: Cpu },
  { label: "Explainability", value: "Every decision carries its numbers", icon: Activity },
  { label: "Simulation", value: "No field deployment claimed", icon: Thermometer },
];

export default function OpsCapabilities() {
  return (
    <section className="px-[var(--gutter)] py-[var(--section-y)]">
      <div className="mx-auto max-w-[1400px]">
        <p className="ops-eyebrow">
          <span className="ops-eyebrow__num">02</span>
          <span>Capabilities</span>
        </p>

        <h2 className="ops-display mt-8 max-w-[18ch] text-[var(--text)]">
          Detect the excursion. <span className="text-[var(--text-dim)]">Then do something about it.</span>
        </h2>

        <div className="ops-reveal mt-14 grid gap-px border border-[var(--border)] bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-4">
          {CAPABILITIES.map(({ n, title, body, href, icon: Icon, tone }, i) => (
            <Link
              key={n}
              href={href}
              className="group relative flex flex-col bg-[var(--canvas)] p-7 transition-colors hover:bg-[var(--surface-card)]"
              style={{ "--i": i } as React.CSSProperties}
            >
              <div className="flex items-center justify-between">
                <span className="ops-num text-[var(--t-micro)] font-semibold text-[var(--text-dim)]">
                  {n}
                </span>
                <Icon size={17} style={{ color: tone }} aria-hidden />
              </div>

              <h3 className="mt-7 text-[var(--t-h3)] font-semibold tracking-tight text-[var(--text)]">
                {title}
              </h3>
              <p className="mt-3 flex-1 text-[var(--t-body)] leading-[1.6] text-[var(--text-secondary)]">
                {body}
              </p>

              <span className="ops-arrow-link mt-7">Open</span>

              <span
                aria-hidden
                className="absolute inset-x-0 bottom-0 h-px origin-left scale-x-0 transition-transform duration-300 group-hover:scale-x-100"
                style={{ background: tone }}
              />
            </Link>
          ))}
        </div>

        <div className="mt-16 grid gap-px border border-[var(--border)] bg-[var(--border)] md:grid-cols-3">
          {PRINCIPLES.map(({ label, value, icon: Icon }, i) => (
            <div
              key={label}
              className="flex items-center gap-4 bg-[var(--surface-subtle)] px-6 py-5"
              style={{ "--i": i } as React.CSSProperties}
            >
              <Icon size={16} className="shrink-0 text-[var(--text-dim)]" aria-hidden />
              <div className="min-w-0">
                <p className="ops-label">{label}</p>
                <p className="mt-1 truncate text-[var(--t-body)] text-[var(--text)]">{value}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
