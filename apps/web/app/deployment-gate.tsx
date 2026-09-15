"use client";

import { ReactNode, useEffect, useState } from "react";

type DeploymentOrganization = {
  id: string;
  name: string;
  slug: string;
};

type DeploymentBootstrap = {
  deployment_id: string;
  dedicated_company: boolean;
  organization: DeploymentOrganization | null;
  environment: string;
  environment_name: string;
  api_path: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function deploymentError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (body.detail) return String(body.detail);
  } catch {}
  return `${response.status} ${response.statusText}`;
}

export default function DeploymentGate({ children }: { children: ReactNode }) {
  const [deployment, setDeployment] = useState<DeploymentBootstrap | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    const verify = async () => {
      setError("");
      try {
        const response = await fetch(`${API_BASE}/deployment/bootstrap`, {
          credentials: "include",
          cache: "no-store",
        });
        if (!response.ok) throw new Error(await deploymentError(response));

        const result = (await response.json()) as DeploymentBootstrap;
        if (!result.deployment_id?.trim()) throw new Error("Deployment ID is missing.");
        if (result.api_path !== "/api/v1/") throw new Error("Unsupported Construction OS API contract.");
        if (result.dedicated_company !== Boolean(result.organization)) {
          throw new Error("The server returned an invalid company binding.");
        }
        if (result.environment === "production" && (!result.dedicated_company || !result.organization)) {
          throw new Error("This production deployment is not bound to a company.");
        }

        if (!cancelled) {
          setDeployment(result);
          if (result.organization?.name) {
            document.title = `Construction OS · ${result.organization.name}`;
          }
        }
      } catch (requestError) {
        if (!cancelled) setError((requestError as Error).message || "Unable to verify this Construction OS deployment.");
      }
    };

    void verify();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <main className="auth-screen">
        <section className="auth-card">
          <div className="boot-mark">COS</div>
          <p className="eyebrow">DEPLOYMENT VERIFICATION</p>
          <h1>Company workspace unavailable.</h1>
          <p>{error}</p>
          <p>The browser will not open project data until this deployment is verified and bound correctly.</p>
          <button onClick={() => window.location.reload()}>Check again</button>
        </section>
      </main>
    );
  }

  if (!deployment) {
    return (
      <main className="boot-screen">
        <div className="boot-mark">COS</div>
        <p>Verifying company workspace…</p>
      </main>
    );
  }

  return <>{children}</>;
}
