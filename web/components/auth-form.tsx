"use client";

import { FormEvent, useId, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authErrorMessage, type AuthMode, validatePassword } from "@/lib/auth";
import { createClient } from "@/lib/supabase/client";
import { BookIcon } from "@/components/icons";

type Status = "idle" | "submitting" | "confirmation-sent" | "recovery-sent";

function successCopy(status: Status, email: string) {
  if (status === "confirmation-sent") {
    return {
      title: "Confirm your email",
      body: `We sent account confirmation instructions to ${email}.`,
    };
  }
  return {
    title: "Check your inbox",
    body: `If an account is available for ${email}, we sent password recovery instructions.`,
  };
}

export function AuthForm({ initialError }: { initialError?: string }) {
  const router = useRouter();
  const passwordHelpId = useId();
  const [mode, setMode] = useState<AuthMode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState(initialError || "");
  const passwordDescription = [mode === "sign-up" ? passwordHelpId : null, error ? "auth-error" : null]
    .filter(Boolean)
    .join(" ") || undefined;

  const submitting = status === "submitting";
  const sent = status === "confirmation-sent" || status === "recovery-sent";

  function selectMode(nextMode: AuthMode) {
    setMode(nextMode);
    setStatus("idle");
    setError("");
    setPassword("");
    setConfirmation("");
    setShowPassword(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    const normalizedEmail = email.trim();
    if (!normalizedEmail) return;

    if (mode !== "recover") {
      const passwordError = validatePassword(password);
      if (passwordError) {
        setError(passwordError);
        return;
      }
      if (mode === "sign-up" && password !== confirmation) {
        setError("The passwords do not match.");
        return;
      }
    }

    setStatus("submitting");
    try {
      const supabase = createClient();
      if (mode === "sign-in") {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email: normalizedEmail,
          password,
        });
        if (signInError) throw signInError;
        router.replace("/");
        router.refresh();
        return;
      }

      if (mode === "sign-up") {
        const { data, error: signUpError } = await supabase.auth.signUp({
          email: normalizedEmail,
          password,
          options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
        });
        if (signUpError) throw signUpError;
        if (data.session) {
          router.replace("/");
          router.refresh();
          return;
        }
        setStatus("confirmation-sent");
        return;
      }

      const { error: recoveryError } = await supabase.auth.resetPasswordForEmail(
        normalizedEmail,
        { redirectTo: `${window.location.origin}/auth/callback?next=/reset-password` },
      );
      if (recoveryError) throw recoveryError;
      setStatus("recovery-sent");
    } catch (caught) {
      setStatus("idle");
      setError(authErrorMessage(mode, caught instanceof Error ? caught.message : undefined));
    }
  }

  const success = sent ? successCopy(status, email.trim()) : null;

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="sign-in-title">
        <div className="brand-mark brand-mark--large"><BookIcon /></div>
        <p className="eyebrow">Gita Guide</p>
        <h1 id="sign-in-title">A quieter place to find perspective</h1>
        <p className="auth-intro">Create an account to save and sync your reflections, or continue privately as a guest.</p>

        {success ? (
          <div className="auth-success" role="status" aria-live="polite">
            <h2>{success.title}</h2>
            <p>{success.body}</p>
            <button className="text-button" type="button" onClick={() => selectMode("sign-in")}>Return to sign in</button>
          </div>
        ) : (
          <>
            <div className="auth-mode-tabs" aria-label="Account access">
              <button type="button" aria-pressed={mode === "sign-in"} onClick={() => selectMode("sign-in")}>Sign in</button>
              <button type="button" aria-pressed={mode === "sign-up"} onClick={() => selectMode("sign-up")}>Create account</button>
            </div>

            {mode === "recover" ? (
              <div className="auth-section-heading">
                <h2>Reset your password</h2>
                <p>Enter your account email and we will send a recovery link.</p>
              </div>
            ) : null}

            <form onSubmit={submit} className="auth-form">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                aria-describedby={error ? "auth-error" : undefined}
              />

              {mode !== "recover" ? (
                <>
                  <div className="auth-label-row">
                    <label htmlFor="password">Password</label>
                    {mode === "sign-in" ? <button type="button" onClick={() => selectMode("recover")}>Forgot password?</button> : null}
                  </div>
                  <div className="password-control">
                    <input
                      id="password"
                      name="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete={mode === "sign-in" ? "current-password" : "new-password"}
                      minLength={8}
                      required
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      aria-describedby={passwordDescription}
                    />
                    <button type="button" onClick={() => setShowPassword((current) => !current)} aria-pressed={showPassword}>
                      {showPassword ? "Hide" : "Show"}
                    </button>
                  </div>
                  {mode === "sign-up" ? <p className="field-help" id={passwordHelpId}>Use at least 8 characters. Password managers and paste are supported.</p> : null}
                </>
              ) : null}

              {mode === "sign-up" ? (
                <>
                  <label htmlFor="password-confirmation">Confirm password</label>
                  <input
                    id="password-confirmation"
                    name="password-confirmation"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    minLength={8}
                    required
                    value={confirmation}
                    onChange={(event) => setConfirmation(event.target.value)}
                    aria-describedby={error ? "auth-error" : undefined}
                  />
                </>
              ) : null}

              {error ? <p id="auth-error" className="form-error" role="alert">{error}</p> : null}
              <button className="primary-button" type="submit" disabled={submitting || !email.trim() || (mode !== "recover" && !password)}>
                {submitting ? <><span className="button-spinner" aria-hidden="true" />Please wait…</> : mode === "sign-in" ? "Sign in" : mode === "sign-up" ? "Create account" : "Send recovery link"}
              </button>
            </form>

            {mode === "recover" ? <button className="auth-back-button" type="button" onClick={() => selectMode("sign-in")}>Back to sign in</button> : null}
          </>
        )}
        <div className="auth-divider"><span>or</span></div>
        <Link className="secondary-button" href="/">Continue without an account</Link>
        <p className="privacy-note">Your reflections are sensitive. Use this guide for perspective, not as a substitute for professional mental-health or emergency support.</p>
      </section>
    </main>
  );
}
