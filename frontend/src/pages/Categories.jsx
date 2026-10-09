import { useEffect, useState } from "react";
import api, { errorMessage } from "../api/client";
import { Alert, Card, PageHeader, Spinner, btn, input } from "../components/ui";

export default function Categories() {
  const [cats, setCats] = useState(null);
  const [form, setForm] = useState({ name: "", keywords: "", reapply: true });
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const load = () => api.post("/categories/list").then((r) => setCats(r.data)).catch((e) => setError(errorMessage(e)));
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault(); setError(""); setOk("");
    try {
      const { data } = await api.post("/categories/create", { name: form.name, reapply: form.reapply, keywords: form.keywords.split(",").map((k) => k.trim()).filter(Boolean) });
      setOk(`Created "${data.name}"${data.reassigned ? ` and moved ${data.reassigned} uncategorized transactions into it` : ""}.`);
      setForm({ name: "", keywords: "", reapply: true });
      load();
    } catch (err) { setError(errorMessage(err)); }
  };
  const remove = async (c) => {
    if (!window.confirm(`Delete "${c.name}"? Its transactions move to Uncategorized.`)) return;
    try { await api.post("/categories/delete", { id: c.id }); load(); } catch (err) { setError(errorMessage(err)); }
  };

  return (
    <>
      <PageHeader title="Categories" />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Add your own category" className="h-fit">
          <form onSubmit={create} className="space-y-3">
            <label className="block text-sm font-medium">Name
              <input className={`${input} mt-1`} value={form.name} maxLength={60} required onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <label className="block text-sm font-medium">Match words
              <input className={`${input} mt-1`} placeholder="gym, cult.fit, yoga" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} />
              <span className="mt-1 block text-xs font-normal text-slate-500">Separate with commas. Your words win over built-in rules.</span>
            </label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.reapply} onChange={(e) => setForm({ ...form, reapply: e.target.checked })} />Apply to existing uncategorized transactions</label>
            <Alert>{error}</Alert><Alert tone="ok">{ok}</Alert>
            <button className={btn.primary}>Add category</button>
          </form>
        </Card>
        <Card title="All categories" className="lg:col-span-2">
          {!cats ? <Spinner /> : (
            <ul className="divide-y divide-slate-100">
              {cats.map((c) => (
                <li key={c.id} className="flex items-start justify-between gap-3 py-2 text-sm">
                  <div className="min-w-0">
                    <p className="font-medium">{c.name} {!c.is_system && <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-normal text-amber-900">Yours</span>}</p>
                    <p className="truncate text-xs text-slate-500" title={c.keywords.join(", ")}>{c.keywords.length ? c.keywords.join(", ") : "No match words"}</p>
                  </div>
                  {!c.is_system && <button className={btn.danger} onClick={() => remove(c)}>Delete</button>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
