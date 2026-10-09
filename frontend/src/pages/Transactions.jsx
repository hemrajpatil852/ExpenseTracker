import { useCallback, useEffect, useState } from "react";
import api, { errorMessage } from "../api/client";
import { Alert, Card, PageHeader, Spinner, btn, input } from "../components/ui";
import { inr, nonEmpty } from "../utils/format";

const EMPTY = { search: "", category_id: "", txn_type: "", start_date: "", end_date: "" };

export default function Transactions() {
  const [filters, setFilters] = useState(EMPTY);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [cats, setCats] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => { api.post("/categories/list").then((r) => setCats(r.data)).catch((e) => setError(errorMessage(e))); }, []);
  useEffect(() => { const t = setTimeout(() => { setFilters((f) => ({ ...f, search })); setPage(1); }, 350); return () => clearTimeout(t); }, [search]);

  const load = useCallback(() => {
    const body = { ...nonEmpty(filters), page, page_size: 25 };
    if (body.category_id) body.category_id = Number(body.category_id);
    return api.post("/transactions/list", body).then((r) => { setData(r.data); setError(""); }).catch((e) => setError(errorMessage(e)));
  }, [filters, page]);
  useEffect(() => { load(); }, [load]);

  const setF = (k) => (e) => { setFilters({ ...filters, [k]: e.target.value }); setPage(1); };
  const recategorise = async (t, category_id) => {
    try {
      const { data: upd } = await api.post("/transactions/update-category", { transaction_id: t.id, category_id: Number(category_id) });
      setData((d) => ({ ...d, items: d.items.map((x) => (x.id === t.id ? upd : x)) }));
    } catch (e) { setError(errorMessage(e)); }
  };
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <>
      <PageHeader title="Transactions" />
      <Card className="mb-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <input className={`${input} lg:col-span-2`} placeholder="Search description" aria-label="Search description" value={search} onChange={(e) => setSearch(e.target.value)} />
          <select className={input} aria-label="Category" value={filters.category_id} onChange={setF("category_id")}>
            <option value="">All categories</option>
            {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select className={input} aria-label="Type" value={filters.txn_type} onChange={setF("txn_type")}>
            <option value="">Debits and credits</option><option value="debit">Debits</option><option value="credit">Credits</option>
          </select>
          <input type="date" className={input} aria-label="From date" value={filters.start_date} onChange={setF("start_date")} />
          <input type="date" className={input} aria-label="To date" value={filters.end_date} onChange={setF("end_date")} />
        </div>
      </Card>
      <Alert>{error}</Alert>
      {!data ? <Spinner /> : (
        <Card>
          {data.items.length === 0 ? <p className="py-6 text-center text-sm text-slate-500">No transactions match these filters.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="text-slate-500"><tr><th className="py-2 font-medium">Date</th><th className="font-medium">Description</th><th className="font-medium">Category</th><th className="text-right font-medium">Amount</th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((t) => (
                    <tr key={t.id}>
                      <td className="whitespace-nowrap py-2 pr-3">{t.date}</td>
                      <td className="max-w-xs truncate pr-3" title={t.description}>{t.description}</td>
                      <td className="pr-3">
                        <select aria-label={`Category for ${t.description}`} className="rounded border border-slate-200 bg-white px-2 py-1 text-xs" value={t.category_id} onChange={(e) => recategorise(t, e.target.value)}>
                          {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                        </select>
                      </td>
                      <td className={`whitespace-nowrap text-right font-medium ${t.type === "credit" ? "text-emerald-700" : "text-slate-900"}`}>{t.type === "credit" ? "+" : "-"}{inr(t.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-4 flex items-center justify-between text-sm">
            <span className="text-slate-500">{data.total} transactions</span>
            <div className="flex items-center gap-2">
              <button className={btn.ghost} disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
              <span>Page {page} of {pages}</span>
              <button className={btn.ghost} disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
            </div>
          </div>
        </Card>
      )}
    </>
  );
}
