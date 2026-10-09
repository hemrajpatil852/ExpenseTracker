import { useCallback, useEffect, useState } from "react";
import api, { errorMessage } from "../api/client";
import { Alert, Card, PageHeader, Spinner, btn, input } from "../components/ui";
import { inr } from "../utils/format";

const bar = { ok: "bg-emerald-600", at_risk: "bg-amber-500", over: "bg-rose-600" };
const text = { ok: "text-emerald-700", at_risk: "text-amber-700", over: "text-rose-700" };
const label = { ok: "On track", at_risk: "Watch out", over: "Over budget" };
const thisMonth = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; };

export default function Budgets() {
  const [month, setMonth] = useState(thisMonth());
  const [data, setData] = useState(null);
  const [cats, setCats] = useState([]);
  const [form, setForm] = useState({ category_id: "", monthly_limit: "" });
  const [error, setError] = useState("");

  const load = useCallback(() =>
    api.post("/budgets/status", { month }).then((r) => setData(r.data)).catch((e) => setError(errorMessage(e))), [month]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.post("/categories/list").then((r) => setCats(r.data)).catch((e) => setError(errorMessage(e))); }, []);
const [msg, setMsg] = useState("");
  const save = async (e) => {
    e.preventDefault(); setError("");
    try {
      await api.post("/budgets/set", { category_id: Number(form.category_id), monthly_limit: form.monthly_limit });
      setForm({ category_id: "", monthly_limit: "" });
      load();
    } catch (err) { setError(errorMessage(err)); }
  };
  const remove = async (id) => {
    try { await api.post("/budgets/delete", { category_id: id }); load(); } catch (err) { setError(errorMessage(err)); }
  };
  const importCsv = async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  setError(""); setMsg("");
  const fd = new FormData();
  fd.append("file", file);
  try {
    const { data } = await api.post("/budgets/import", fd);
    const skipped = data.errors.map((x) => `row ${x.row} (${x.reason})`).join("; ");
    setMsg(`Saved ${data.saved} budgets.${skipped ? ` Skipped: ${skipped}` : ""}`);
    load();
  } catch (err) { setError(errorMessage(err)); }
};

const template = () => {
  const csv = "Category,Monthly Limit\n" + cats.filter((c) => c.name !== "Income").map((c) => `"${c.name}",`).join("\n") + "\n";
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  Object.assign(document.createElement("a"), { href: url, download: "budget-template.csv" }).click();
  URL.revokeObjectURL(url);
};

  return (
    <>
      <PageHeader title="Budgets">
        <label className="text-sm font-medium">Month
          <input type="month" className={`${input} mt-1`} value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} />
        </label>
      </PageHeader>
      <Alert>{error}</Alert>
      <div className="mt-4 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6">
  <Card title="Set budgets from a CSV" className="h-fit">
    <p className="mb-3 text-sm text-slate-600">Download the template, fill in limits for the categories you want, then upload it. Blank rows are skipped.</p>
    <div className="flex flex-wrap gap-2">
      <button type="button" className={btn.ghost} onClick={template} disabled={!cats.length}>Download template</button>
      <label className={`${btn.primary} cursor-pointer`}>
        Upload budget CSV
        <input type="file" accept=".csv,text/csv" className="sr-only" onChange={importCsv} />
      </label>
    </div>
    <div className="mt-3"><Alert tone="ok">{msg}</Alert></div>
  </Card>

  {/* your existing <Card title="Set a monthly budget"> ... </Card> stays here, unchanged */}

        <Card title="Set a monthly budget" className="h-fit">
          <form onSubmit={save} className="space-y-3">
            <label className="block text-sm font-medium">Category
              <select className={`${input} mt-1`} required value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
                <option value="">Choose a category</option>
                {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className="block text-sm font-medium">Monthly limit (₹)
              <input type="number" min="1" step="0.01" required className={`${input} mt-1`} value={form.monthly_limit} onChange={(e) => setForm({ ...form, monthly_limit: e.target.value })} />
            </label>
            <button className={btn.primary}>Save budget</button>
            <p className="text-xs text-slate-500">Setting a category again updates its limit.</p>
          </form>
        </Card>
        </div>
        <Card title={`Budget progress for ${month}`} className="lg:col-span-2">
          {!data ? <Spinner /> : data.items.length === 0 ? (
            <p className="text-sm text-slate-500">No budgets yet. Pick a category and a limit to start tracking.</p>
          ) : (
            <ul className="space-y-5">
              {data.items.map((b) => (
                <li key={b.category_id}>
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="font-medium">{b.category} <span className={`ml-2 text-xs font-medium ${text[b.state]}`}>{label[b.state]}</span></p>
                    <p className="text-sm text-slate-600">{inr(b.spent)} of {inr(b.limit)}</p>
                  </div>
                  <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={Math.round(b.percent)} aria-valuemin={0} aria-valuemax={100} aria-label={`${b.category} budget used`}>
                    <div className={`h-full ${bar[b.state]}`} style={{ width: `${Math.min(b.percent, 100)}%` }} />
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-2">
                    <p className={`text-sm ${text[b.state]}`}>{b.message}</p>
                    <button className={btn.danger} onClick={() => remove(b.category_id)}>Remove</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}