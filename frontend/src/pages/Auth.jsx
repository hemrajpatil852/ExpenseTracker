import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { Alert, btn, input } from "../components/ui";

export default function Auth({ mode }) {
  const isSignup = mode === "signup";
  const { login, signup, notice } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await (isSignup ? signup(form) : login({ email: form.email, password: form.password }));
      nav(loc.state?.from || "/", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden bg-indigo-950 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <p className="text-lg font-semibold">Rupee Ledger</p>
        <div>
          <p className="max-w-md text-4xl font-semibold leading-tight">Upload a statement. See where every rupee went.</p>
          <ul className="mt-6 space-y-2 text-indigo-200">
            <li>Works with UPI, debit card and net banking exports</li>
            <li>Sorts Swiggy, Uber, electricity and more automatically</li>
            <li>Your statements stay private to your account</li>
          </ul>
        </div>
        <p className="text-sm text-indigo-300">Built for personal and family budgets</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-4" noValidate>
          <h1 className="text-2xl font-semibold">{isSignup ? "Create your account" : "Log in"}</h1>
          <Alert tone="warn">{!error && notice}</Alert>
          <Alert>{error}</Alert>
          {isSignup && (
            <label className="block text-sm font-medium">Full name
              <input className={`${input} mt-1`} value={form.name} onChange={set("name")} autoComplete="name" required />
            </label>
          )}
          <label className="block text-sm font-medium">Email
            <input type="email" className={`${input} mt-1`} value={form.email} onChange={set("email")} autoComplete="email" required />
          </label>
          <label className="block text-sm font-medium">Password
            <input type="password" className={`${input} mt-1`} value={form.password} onChange={set("password")}
              autoComplete={isSignup ? "new-password" : "current-password"} required minLength={isSignup ? 8 : undefined} />
            {isSignup && <span className="mt-1 block text-xs font-normal text-slate-500">At least 8 characters with a letter and a number.</span>}
          </label>
          <button disabled={busy} className={`${btn.primary} w-full`}>{busy ? "Please wait" : isSignup ? "Create account" : "Log in"}</button>
          <p className="text-sm text-slate-600">
            {isSignup ? "Already have an account? " : "New here? "}
            <Link className="font-medium text-indigo-800 underline" to={isSignup ? "/login" : "/signup"}>{isSignup ? "Log in" : "Create an account"}</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
