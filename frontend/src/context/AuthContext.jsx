import { createContext, useCallback, useContext, useEffect, useState } from "react";
import api, { tokens } from "../api/client";

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!tokens.access);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!tokens.access) return;
    api.post("/auth/me").then((r) => setUser(r.data)).catch(() => tokens.clear()).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const onExpired = () => { setUser(null); setNotice("Your session expired. Log in again to continue."); };
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, []);

  const authenticate = useCallback(async (path, payload) => {
    const { data } = await api.post(path, payload);
    tokens.set(data);
    setNotice("");
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch { /* token may already be dead */ }
    tokens.clear();
    setUser(null);
  }, []);

  return (
    <Ctx.Provider value={{ user, loading, notice, logout, login: (p) => authenticate("/auth/login", p), signup: (p) => authenticate("/auth/signup", p) }}>
      {children}
    </Ctx.Provider>
  );
}
