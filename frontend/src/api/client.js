import axios from "axios";

const ACCESS = "rl_access";
const REFRESH = "rl_refresh";

export const tokens = {
  get access() { return localStorage.getItem(ACCESS); },
  get refresh() { return localStorage.getItem(REFRESH); },
  set({ access_token, refresh_token }) {
    localStorage.setItem(ACCESS, access_token);
    localStorage.setItem(REFRESH, refresh_token);
  },
  clear() { localStorage.removeItem(ACCESS); localStorage.removeItem(REFRESH); },
};

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || "/api", timeout: 120000 });

api.interceptors.request.use((cfg) => {
  if (tokens.access) cfg.headers.Authorization = `Bearer ${tokens.access}`;
  return cfg;
});

// One shared refresh call, so parallel 401s don't each trigger their own refresh.
let refreshing = null;
const refreshSession = () => {
  if (!tokens.refresh) return Promise.reject(new Error("no refresh token"));
  refreshing ??= axios
    .post(`${api.defaults.baseURL}/auth/refresh`, { refresh_token: tokens.refresh })
    .then((r) => { tokens.set(r.data); return r.data; })
    .finally(() => { refreshing = null; });
  return refreshing;
};

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const cfg = err.config;
    const isAuthCall = cfg?.url?.startsWith("/auth/login") || cfg?.url?.startsWith("/auth/signup") || cfg?.url?.startsWith("/auth/refresh");
    if (err.response?.status === 401 && cfg && !cfg._retried && !isAuthCall) {
      cfg._retried = true;
      try {
        await refreshSession();
        return api(cfg); // replays the original request, including a multipart upload body
      } catch {
        tokens.clear();
        window.dispatchEvent(new Event("auth:expired"));
      }
    }
    return Promise.reject(err);
  }
);

/** Turn any axios/FastAPI error into a readable sentence. */
export function errorMessage(err) {
  if (!err.response) return err.code === "ECONNABORTED" ? "The request timed out. Try again." : "Can't reach the server. Check your connection.";
  const d = err.response.data?.detail;
  if (Array.isArray(d)) return d.map((x) => x.msg?.replace("Value error, ", "")).join(" ");
  return typeof d === "string" ? d : `Request failed (${err.response.status}).`;
}

/** POST with blob response -> browser download. */
export async function download(path, body, filename) {
  try {
    const res = await api.post(path, body, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = Object.assign(document.createElement("a"), { href: url, download: filename });
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    if (err.response?.data instanceof Blob) {
      try { err.response.data = JSON.parse(await err.response.data.text()); } catch { /* keep as is */ }
    }
    throw err;
  }
}

export default api;
