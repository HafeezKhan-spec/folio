import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, api } from "../api";
import type { BillingInfo, User } from "../types";

export function Billing() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [info, setInfo] = useState<BillingInfo | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const checkout = params.get("checkout");

  useEffect(() => {
    api<User>("/api/auth/me")
      .then(async (me) => {
        setUser(me);
        setInfo(await api<BillingInfo>("/api/billing"));
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          navigate("/login");
          return;
        }
        setError(err instanceof Error ? err.message : "Billing could not be loaded.");
      });
  }, [navigate]);

  async function startCheckout() {
    setBusy(true);
    setError(null);
    try {
      const result = await api<{ url: string }>("/api/billing/checkout", { method: "POST" });
      window.location.href = result.url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Checkout could not be started.");
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <section className="auth-card">
        <Link className="wordmark" to="/">
          Folio
        </Link>
        <h1>Billing</h1>
        {user ? <p className="muted">{user.email}</p> : null}
        {checkout === "success" ? (
          <p className="notice">
            If checkout finished, this page updates when the payment notice arrives.
          </p>
        ) : null}
        {checkout === "cancel" ? <p className="notice">Checkout was canceled.</p> : null}
        {error ? <p className="notice error">{error}</p> : null}
        {info ? (
          <>
            <p className="price">{info.price_label}</p>
            <p>
              This account is <strong>{info.plan === "pro" ? "Pro" : "Free"}</strong>.
              Free keeps 1 resume and 1 version. Pro keeps up to 25 resumes and 30
              versions each, plus every template, rewrite, and tailor.
            </p>
            {info.plan === "pro" ? <p>Pro is already on for this account.</p> : null}
            {info.missing.length > 0 ? (
              <>
                <p>
                  Checkout is not ready yet. Add the missing settings to the
                  environment and restart. Nothing here will crash while they are
                  empty.
                </p>
                <ul>
                  {info.missing.map((name) => (
                    <li key={name}>
                      <code>{name}</code>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            {info.plan !== "pro" && info.checkout_available ? (
              <button className="button primary" type="button" onClick={startCheckout} disabled={busy}>
                {busy ? "Opening checkout" : `Continue to checkout · ${info.price_label}`}
              </button>
            ) : null}
          </>
        ) : (
          <p>Loading billing.</p>
        )}
        <p>
          <Link to="/app">Back to the studio</Link>
        </p>
      </section>
    </div>
  );
}
