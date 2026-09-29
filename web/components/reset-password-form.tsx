"use client";

import { FormEvent, useId, useState } from "react";
import { useRouter } from "next/navigation";
import { authErrorMessage, validatePassword } from "@/lib/auth";
import { createClient } from "@/lib/supabase/client";
import { BookIcon } from "@/components/icons";

export function ResetPasswordForm() {
  const router = useRouter();
  const passwordHelpId = useId();
  const errorId = useId();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }
    if (password !== confirmation) {
      setError("The passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      const supabase = createClient();
      const { error: updateError } = await supabase.auth.updateUser({ password });
      if (updateError) throw updateError;
      setComplete(true);
    } catch (caught) {
      setError(authErrorMessage("reset", caught instanceof Error ? caught.message : undefined));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="reset-title">
        <div className="brand-mark brand-mark--large"><BookIcon /></div>
        <p className="eyebrow">Gita Guide</p>
        {complete ? (
          <div className="auth-success" role="status">
            <h1 id="reset-title">Password updated</h1>
            <p>Your new password is ready to use.</p>
            <button className="primary-button" type="button" onClick={() => { router.replace("/"); router.refresh(); }}>Continue to Gita Guide</button>
          </div>
        ) : (
          <>
            <h1 id="reset-title">Choose a new password</h1>
            <p className="auth-intro">Use a unique password you do not use for another account.</p>
            <form className="auth-form" onSubmit={submit}>
              <label htmlFor="new-password">New password</label>
              <div className="password-control">
                <input
                  id="new-password"
                  name="new-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  minLength={8}
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  aria-describedby={`${passwordHelpId}${error ? ` ${errorId}` : ""}`}
                />
                <button type="button" onClick={() => setShowPassword((current) => !current)} aria-pressed={showPassword}>
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
              <p className="field-help" id={passwordHelpId}>Use at least 8 characters. Password managers and paste are supported.</p>
              <label htmlFor="new-password-confirmation">Confirm new password</label>
              <input
                id="new-password-confirmation"
                name="new-password-confirmation"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                minLength={8}
                required
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                aria-describedby={error ? errorId : undefined}
              />
              {error ? <p id={errorId} className="form-error" role="alert">{error}</p> : null}
              <button className="primary-button" type="submit" disabled={submitting || !password || !confirmation}>
                {submitting ? <><span className="button-spinner" aria-hidden="true" />Updating…</> : "Update password"}
              </button>
            </form>
          </>
        )}
      </section>
    </main>
  );
}
