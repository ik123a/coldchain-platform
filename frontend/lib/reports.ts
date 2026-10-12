"use client";
// Report downloads against a fail-closed backend.
//
// The report routes now require authentication. A plain <a href> cannot attach
// an `Authorization` header, so a naive `href="/api/reports/1.pdf"` would 401.
// Rather than leaving the endpoint open, we mint a short-lived signed ticket via
// POST /api/reports/{id}/ticket and download through that.
//
// The ticket is the SAME signed JWT the api() client already carries — same HMAC,
// same expiry, same claims — so no new credential type or trust surface exists.
// The server validates it on the download, so a tampered href fails closed.
import { getToken } from "./auth";

async function ticketFor(reportId: number): Promise<string> {
  const token = getToken();
  if (!token) throw new Error("Not signed in — sign in to download reports.");

  const res = await fetch(`/api/reports/${reportId}/ticket`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Could not authorize the download (HTTP ${res.status}).`);
  }
  const data = await res.json();
  if (!data?.ticket) throw new Error("Server returned no download ticket.");
  return data.ticket as string;
}

/** Download a report, attaching authorization via a ticket. */
export async function downloadReport(reportId: number, format: "json" | "pdf") {
  const ticket = await ticketFor(reportId);
  const url = `/api/reports/${reportId}.${format}?ticket=${encodeURIComponent(ticket)}`;
  // A programmatic navigation so the browser handles Content-Disposition.
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
