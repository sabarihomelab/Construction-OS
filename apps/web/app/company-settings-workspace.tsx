"use client";

import { FormEvent, useEffect, useState } from "react";

type AccessContext = { permissions: string[] };
type Organization = {
  id: string;
  name: string;
  legal_name: string | null;
  slug: string;
  country_code: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};
type OrganizationSettings = {
  organization_id: string;
  locale: string;
  timezone: string;
  base_currency: string;
  unit_system: "metric" | "imperial" | "mixed";
  time_format: "12h" | "24h";
  first_day_of_week: number;
  storage_quota_bytes: number | null;
  settings_version: number;
};
type CompanyProfile = { organization: Organization; settings: OrganizationSettings };

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const entry = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith("construction_os_csrf="));
  return entry ? decodeURIComponent(entry.split("=").slice(1).join("=")) : null;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  if (init?.body) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = csrfToken();
    if (token) headers.set("X-CSRF-Token", token);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (body.detail) message = String(body.detail);
    } catch {}
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export default function CompanySettingsWorkspace() {
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [context, setContext] = useState<AccessContext | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setError("");
      const [nextProfile, nextContext] = await Promise.all([
        api<CompanyProfile>("/organization"),
        api<AccessContext>("/session/context"),
      ]);
      setProfile(nextProfile);
      setContext(nextContext);
    } catch (requestError) {
      setError((requestError as Error).message);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const canManage = context?.permissions.includes("admin.configuration.manage") ?? false;

  const updateProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!profile) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await api<Organization>("/organization", {
        method: "PATCH",
        body: JSON.stringify({
          expected_updated_at: profile.organization.updated_at,
          name: form.get("name"),
          legal_name: form.get("legal_name") || null,
        }),
      });
      await load();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const updateSettings = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!profile) return;
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await api<OrganizationSettings>("/organization/settings", {
        method: "PATCH",
        body: JSON.stringify({
          expected_settings_version: profile.settings.settings_version,
          locale: form.get("locale"),
          timezone: form.get("timezone"),
          base_currency: form.get("base_currency"),
          unit_system: form.get("unit_system"),
          time_format: form.get("time_format"),
          first_day_of_week: Number(form.get("first_day_of_week")),
        }),
      });
      await load();
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="workspace">
      <section className="page-frame">
        <div className="page-heading">
          <div><p className="eyebrow">ADMINISTRATION</p><h1>Company Settings</h1><p>Stable company identity and India localization defaults.</p></div>
        </div>
        {error && <div className="error-banner"><strong>Action not completed</strong><span>{error}</span></div>}
        {!profile ? <div className="empty-state"><strong>Loading company…</strong></div> : (
          <>
            <section className="workflow-card">
              <div><p className="eyebrow">COMPANY</p><h2>{profile.organization.name}</h2><small>{profile.organization.slug} · {profile.organization.country_code || "—"}</small></div>
              <form className="quick-form" onSubmit={updateProfile}>
                <input name="name" defaultValue={profile.organization.name} disabled={!canManage || busy} required />
                <input name="legal_name" defaultValue={profile.organization.legal_name || ""} placeholder="Legal name" disabled={!canManage || busy} />
                <button disabled={!canManage || busy}>Save company</button>
              </form>
            </section>
            <section className="workflow-card">
              <div><p className="eyebrow">LOCALIZATION</p><h2>India operating defaults</h2><small>Settings version {profile.settings.settings_version}</small></div>
              <form className="quick-form" onSubmit={updateSettings}>
                <input name="locale" defaultValue={profile.settings.locale} disabled={!canManage || busy} required />
                <input name="timezone" defaultValue={profile.settings.timezone} disabled={!canManage || busy} required />
                <input name="base_currency" defaultValue={profile.settings.base_currency} disabled={!canManage || busy} required maxLength={3} />
                <select name="unit_system" defaultValue={profile.settings.unit_system} disabled={!canManage || busy}><option value="metric">Metric</option><option value="mixed">Mixed</option><option value="imperial">Imperial</option></select>
                <select name="time_format" defaultValue={profile.settings.time_format} disabled={!canManage || busy}><option value="24h">24 hour</option><option value="12h">12 hour</option></select>
                <select name="first_day_of_week" defaultValue={String(profile.settings.first_day_of_week)} disabled={!canManage || busy}><option value="1">Monday</option><option value="7">Sunday</option></select>
                <button disabled={!canManage || busy}>Save settings</button>
              </form>
            </section>
          </>
        )}
      </section>
    </main>
  );
}
