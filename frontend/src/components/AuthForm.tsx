import { FormEvent, useState } from "react";
import { getGoogleLoginUrl } from "../api";

const PASSWORD_MIN = 5;
const PASSWORD_MAX = 20;

type Props = {
  busy: boolean;
  error: string | null;
  info: string | null;
  pendingVerifyEmail: string | null;
  onSubmit: (mode: "login" | "register", email: string, password: string) => Promise<void>;
  onVerifyCode: (email: string, code: string) => Promise<void>;
  onResendVerification: (email: string) => Promise<void>;
  onBackToLogin: () => void;
};

function WaitLabel({ label }: { label: string }) {
  return <span className="auth-wait-label">{label}</span>;
}

export function AuthForm({
  busy,
  error,
  info,
  pendingVerifyEmail,
  onSubmit,
  onVerifyCode,
  onResendVerification,
  onBackToLogin,
}: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const formError = localError || error;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLocalError(null);
    const trimmedEmail = email.trim();
    if (!trimmedEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      setLocalError("Enter a valid email address.");
      return;
    }
    if (!password) {
      setLocalError("Enter your password.");
      return;
    }
    if (mode === "register") {
      if (password.length < PASSWORD_MIN || password.length > PASSWORD_MAX) {
        setLocalError(`Password must be ${PASSWORD_MIN}–${PASSWORD_MAX} characters.`);
        return;
      }
      if (password !== confirmPassword) {
        setLocalError("Passwords do not match.");
        return;
      }
    }
    await onSubmit(mode, trimmedEmail, password);
  }

  async function handleVerify(event: FormEvent) {
    event.preventDefault();
    setLocalError(null);
    if (!pendingVerifyEmail) {
      return;
    }
    if (code.trim().length !== 6) {
      setLocalError("Enter the 6-digit verification code.");
      return;
    }
    await onVerifyCode(pendingVerifyEmail, code.trim());
  }

  if (pendingVerifyEmail) {
    return (
      <section className="panel auth-panel">
        <h2 className="auth-verify-title">Check your email</h2>
        <p className="muted auth-verify-copy">
          We sent a verification link and a 6-digit code to{" "}
          <strong>{pendingVerifyEmail}</strong>. Open the link, or enter the code
          below.
        </p>
        <form onSubmit={handleVerify} className="stack" noValidate>
          <label>
            Verification code
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(event) => {
                setCode(event.target.value.replace(/\D/g, "").slice(0, 6));
                setLocalError(null);
              }}
              autoComplete="one-time-code"
              disabled={busy}
              placeholder="123456"
            />
          </label>
          <div className="auth-message-slot" aria-live="polite">
            {formError ? (
              <p className="form-error">{formError}</p>
            ) : info ? (
              <p className="form-info">{info}</p>
            ) : null}
          </div>
          <button
            type="submit"
            className={busy ? "auth-submit is-waiting" : "auth-submit"}
            disabled={busy || code.length !== 6}
          >
            {busy ? <WaitLabel label="Please wait…" /> : "Verify email"}
          </button>
        </form>
        <div className="auth-verify-actions">
          <button
            type="button"
            className="linkish"
            disabled={busy}
            onClick={() => {
              void onResendVerification(pendingVerifyEmail);
            }}
          >
            Resend email
          </button>
          <button
            type="button"
            className="linkish"
            disabled={busy}
            onClick={() => {
              setCode("");
              onBackToLogin();
            }}
          >
            Back to sign in
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="panel auth-panel">
      <div className="tabs">
        <button
          type="button"
          className={mode === "login" ? "active" : ""}
          onClick={() => {
            setMode("login");
            setLocalError(null);
          }}
        >
          Sign in
        </button>
        <button
          type="button"
          className={mode === "register" ? "active" : ""}
          onClick={() => {
            setMode("register");
            setLocalError(null);
          }}
        >
          Create account
        </button>
      </div>
      <a className="google-btn" href={getGoogleLoginUrl()}>
        <span className="google-btn-icon" aria-hidden="true">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="20" height="20">
            <path
              fill="#FFC107"
              d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 8 3.1l5.7-5.7C34.2 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.5-.4-3.5z"
            />
            <path
              fill="#FF3D00"
              d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.1 8 3.1l5.7-5.7C34.2 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
            />
            <path
              fill="#4CAF50"
              d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.3 35.3 26.8 36 24 36c-5.3 0-9.7-3.3-11.3-8l-6.5 5C9.6 39.6 16.2 44 24 44z"
            />
            <path
              fill="#1976D2"
              d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.5l.1.1 6.2 5.2C39.2 36.3 44 31 44 24c0-1.3-.1-2.5-.4-3.5z"
            />
          </svg>
        </span>
        Continue with Google
      </a>
      <p className="auth-divider muted">or use email</p>
      <form onSubmit={handleSubmit} className="stack" noValidate>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              setLocalError(null);
            }}
            autoComplete="email"
            disabled={busy}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value.slice(0, mode === "register" ? PASSWORD_MAX : 128));
              setLocalError(null);
            }}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            disabled={busy}
          />
        </label>
        {mode === "register" ? (
          <label>
            Confirm password
            <input
              type="password"
              value={confirmPassword}
              onChange={(event) => {
                setConfirmPassword(event.target.value.slice(0, PASSWORD_MAX));
                setLocalError(null);
              }}
              autoComplete="new-password"
              disabled={busy}
            />
          </label>
        ) : null}
        <div className="auth-message-slot" aria-live="polite">
          {formError ? (
            <p className="form-error">{formError}</p>
          ) : info ? (
            <p className="form-info">{info}</p>
          ) : mode === "register" ? (
            <p className="form-info">
              Password must be {PASSWORD_MIN}–{PASSWORD_MAX} characters.
            </p>
          ) : null}
        </div>
        <button
          type="submit"
          className={busy ? "auth-submit is-waiting" : "auth-submit"}
          disabled={busy}
        >
          {busy ? (
            <WaitLabel label="Please wait…" />
          ) : mode === "login" ? (
            "Sign in"
          ) : (
            "Create account"
          )}
        </button>
      </form>
    </section>
  );
}
