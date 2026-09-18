"use client";

import {
  FormEvent,
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import styles from "./web-session-gate.module.css";

export type VisibleFeature = {
  key: string;
  name: string;
  kind: "module" | "page" | "tile" | "action";
  parent_key: string | null;
  route: string | null;
  sensitivity: "standard" | "sensitive" | "high";
  display_order: number;
  mobile_enabled: boolean;
  offline_enabled: boolean;
  help_topic: string | null;
};

export type WebAccessContext = {
  organization_id: string;
  membership_id: string;
  authorization_revision: number;
  configuration_revision: number;
  permissions: string[];
  scopes: Record<string, string[]>;
  project_permissions: Record<string, string[]>;
  features: VisibleFeature[];
};

type MembershipOption = {
  membership_id: string;
  organization_id: string;
  organization_name: string;
};

type MembershipSelection = {
  status: "membership_selection_required";
  grant_token: string;
  memberships: MembershipOption[];
};

type AuthenticatedResponse = {
  status: "authenticated";
  membership_id: string;
};

type WebSessionValue = {
  context: WebAccessContext;
  hasPermission: (permission: string) => boolean;
  hasPermissionAnywhere: (permission: string) => boolean;
  hasFeature: (key: string) => boolean;
  logout: () => Promise<void>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const WebSessionContext = createContext<WebSessionValue | null>(null);

function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const entry = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith("construction_os_csrf="));
  return entry ? decodeURIComponent(entry.split("=").slice(1).join("=")) : null;
}

async function responseMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (body.detail) return String(body.detail);
  } catch {}
  return `${response.status} ${response.statusText}`;
}

export function useWebSession(): WebSessionValue {
  const value = useContext(WebSessionContext);
  if (!value) throw new Error("useWebSession must be used inside WebSessionGate");
  return value;
}

export default function WebSessionGate({ children }: { children: ReactNode }) {
  const [context, setContext] = useState<WebAccessContext | null>(null);
  const [providers, setProviders] = useState<string[]>([]);
  const [membershipSelection, setMembershipSelection] = useState<MembershipSelection | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadProviders = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/web/providers`, {
        credentials: "include",
        cache: "no-store",
      });
      if (!response.ok) throw new Error(await responseMessage(response));
      const result = (await response.json()) as { providers: string[] };
      setProviders(result.providers);
    } catch (requestError) {
      setProviders([]);
      setError((requestError as Error).message || "Unable to load sign-in options.");
    }
  }, []);

  const loadSession = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/session/context`, {
        credentials: "include",
        cache: "no-store",
      });
      if (response.ok) {
        setContext((await response.json()) as WebAccessContext);
        setMembershipSelection(null);
        return;
      }
      if (response.status === 401) {
        setContext(null);
        await loadProviders();
        return;
      }
      throw new Error(await responseMessage(response));
    } catch (requestError) {
      setContext(null);
      setError((requestError as Error).message || "Unable to open your Construction OS session.");
    } finally {
      setLoading(false);
    }
  }, [loadProviders]);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  const authenticateDevelopment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/auth/web/authenticate`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider_key: "development",
          payload: {
            email: String(form.get("email") || "").trim(),
            display_name: String(form.get("display_name") || "").trim() || null,
            secret: String(form.get("secret") || ""),
          },
        }),
      });
      if (!response.ok) throw new Error(await responseMessage(response));
      const result = (await response.json()) as AuthenticatedResponse | MembershipSelection;
      if (result.status === "membership_selection_required") {
        setMembershipSelection(result);
      } else {
        await loadSession();
      }
    } catch (requestError) {
      setError((requestError as Error).message || "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  const selectMembership = async (membershipId: string) => {
    if (!membershipSelection) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/auth/web/select-membership`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          grant_token: membershipSelection.grant_token,
          membership_id: membershipId,
        }),
      });
      if (!response.ok) throw new Error(await responseMessage(response));
      await loadSession();
    } catch (requestError) {
      setError((requestError as Error).message || "Unable to open that company workspace.");
    } finally {
      setBusy(false);
    }
  };

  const logout = useCallback(async () => {
    setError("");
    try {
      const headers = new Headers();
      const token = csrfToken();
      if (token) headers.set("X-CSRF-Token", token);
      const response = await fetch(`${API_BASE}/session/logout`, {
        method: "POST",
        credentials: "include",
        headers,
      });
      if (!response.ok && response.status !== 401) throw new Error(await responseMessage(response));
    } finally {
      setContext(null);
      setMembershipSelection(null);
      await loadProviders();
    }
  }, [loadProviders]);

  const sessionValue = useMemo<WebSessionValue | null>(() => {
    if (!context) return null;
    const organizationPermissions = new Set(context.permissions);
    const allPermissions = new Set(context.permissions);
    Object.values(context.project_permissions).forEach((permissions) => {
      permissions.forEach((permission) => allPermissions.add(permission));
    });
    const features = new Set(context.features.map((feature) => feature.key));
    return {
      context,
      hasPermission: (permission: string) => organizationPermissions.has(permission),
      hasPermissionAnywhere: (permission: string) => allPermissions.has(permission),
      hasFeature: (key: string) => features.has(key),
      logout,
    };
  }, [context, logout]);

  if (loading) {
    return (
      <main className={styles.bootScreen}>
        <div className={styles.brandMark}>COS</div>
        <div>
          <strong>Construction OS</strong>
          <p>Opening your secure workspace…</p>
        </div>
      </main>
    );
  }

  if (sessionValue) {
    return <WebSessionContext.Provider value={sessionValue}>{children}</WebSessionContext.Provider>;
  }

  const developmentEnabled = providers.includes("development");

  return (
    <main className={styles.loginScreen}>
      <section className={styles.loginStory}>
        <div className={styles.brandLockup}>
          <span className={styles.brandMark}>COS</span>
          <span>
            <strong>Construction OS</strong>
            <small>Project delivery platform</small>
          </span>
        </div>
        <div className={styles.storyCopy}>
          <p className={styles.eyebrow}>SECURE COMPANY WORKSPACE</p>
          <h1>Run the project from one operating system.</h1>
          <p>
            Field execution, commercial controls and company administration stay connected to the same project and permission model.
          </p>
        </div>
        <div className={styles.securityNote}>
          <span aria-hidden="true">✓</span>
          <p><strong>Role-aware by design.</strong> After sign-in, you only see workspaces your company and project access allow.</p>
        </div>
      </section>

      <section className={styles.loginPanel}>
        <div className={styles.loginCard}>
          <div className={styles.mobileBrand}>
            <span className={styles.brandMark}>COS</span>
            <strong>Construction OS</strong>
          </div>

          {membershipSelection ? (
            <>
              <p className={styles.eyebrow}>CHOOSE COMPANY</p>
              <h2>Select your workspace</h2>
              <p className={styles.cardCopy}>Your identity is linked to more than one active company membership.</p>
              <div className={styles.membershipList}>
                {membershipSelection.memberships.map((membership) => (
                  <button
                    disabled={busy}
                    key={membership.membership_id}
                    onClick={() => void selectMembership(membership.membership_id)}
                    type="button"
                  >
                    <span>{membership.organization_name}</span>
                    <b aria-hidden="true">→</b>
                  </button>
                ))}
              </div>
              <button className={styles.textButton} onClick={() => setMembershipSelection(null)} type="button">Back to sign in</button>
            </>
          ) : developmentEnabled ? (
            <>
              <p className={styles.eyebrow}>DEVELOPMENT SIGN IN</p>
              <h2>Welcome back</h2>
              <p className={styles.cardCopy}>Use the local development identity configured for this installation.</p>
              <form className={styles.loginForm} onSubmit={authenticateDevelopment}>
                <label>
                  <span>Email</span>
                  <input autoComplete="username" name="email" placeholder="you@company.com" required type="email" />
                </label>
                <label>
                  <span>Display name <small>Optional</small></span>
                  <input autoComplete="name" name="display_name" placeholder="Your name" />
                </label>
                <label>
                  <span>Development secret</span>
                  <input autoComplete="current-password" name="secret" placeholder="Enter local sign-in secret" required type="password" />
                </label>
                {error && <div className={styles.errorMessage}>{error}</div>}
                <button className={styles.primaryButton} disabled={busy} type="submit">
                  {busy ? "Signing in…" : "Sign in to workspace"}
                </button>
              </form>
              <p className={styles.developmentNotice}>Development authentication is never available in production.</p>
            </>
          ) : (
            <>
              <p className={styles.eyebrow}>SIGN IN</p>
              <h2>Company sign-in is not configured</h2>
              <p className={styles.cardCopy}>
                This deployment is healthy, but it does not currently expose a browser identity provider. An administrator must configure an approved sign-in provider before project data can be opened.
              </p>
              {error && <div className={styles.errorMessage}>{error}</div>}
              <button className={styles.secondaryButton} onClick={() => void loadSession()} type="button">Check again</button>
            </>
          )}
        </div>
        <p className={styles.panelFoot}>Construction OS · Secure project access</p>
      </section>
    </main>
  );
}
