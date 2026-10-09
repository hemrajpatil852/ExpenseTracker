import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import api, { download, errorMessage } from "../api/client";
import { Alert, Card, PageHeader, Spinner, btn, input } from "../components/ui";
import { PRESETS, inr, inrShort, presetRange } from "../utils/format";
import BudgetAlerts from "../components/BudgetAlerts";
const COLORS = ["#312e81", "#f59e0b", "#0d9488", "#be123c", "#7c3aed", "#0369a1", "#65a30d", "#c2410c", "#475569", "#db2777", "#0891b2", "#a16207"];

export default function Dashboard() {
  const [preset, setPreset] = useState("all");
  const [custom, setCustom] = useState({ start: "", end: "" });
  const [groupBy, setGroupBy] = useState("day");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [start, end] = useMemo(() => (preset === "custom" ? [custom.start || null, custom.end || null] : presetRange(preset)), [preset, custom]);

  useEffect(() => {
    if (preset === "custom" && start && end && start > end) return setError("Start date must be before the end date.");
    let live = true;
    setError(""); setBusy(true);
    api.post("/dashboard/summary", { start_date: start, end_date: end, group_by: groupBy })
      .then((r) => live && setData(r.data))
      .catch((e) => live && setError(errorMessage(e)))
      .finally(() => live && setBusy(false));
    return () => { live = false; };
  }, [start, end, groupBy, preset]);

  const exportAs = async (kind) => {
    try { await download(`/export/${kind}`, { start_date: start, end_date: end }, kind === "csv" ? "transactions.csv" : "spending-report.pdf"); }
    catch (e) { setError(errorMessage(e)); }
  };

  const top = data?.categories?.[0];
  const stats = data && [
    ["Spent", inr(data.total_spent), "text-rose-700"],
    ["Income", inr(data.total_income), "text-emerald-700"],
    ["Net", inr(data.net), data.net >= 0 ? "text-emerald-700" : "text-rose-700"],
    ["Biggest category", top ? `${top.category} (${top.percent}%)` : "None", "text-slate-900"],
  ];

  return (
    <>
      <PageHeader title="Dashboard">
        <div className="flex flex-wrap gap-2">
          <button className={btn.ghost} onClick={() => exportAs("csv")}>Download CSV</button>
          <button className={btn.ghost} onClick={() => exportAs("pdf")}>Download PDF</button>
        </div>
      </PageHeader>

      <div className="mb-6 flex flex-wrap items-end gap-3">
        <label className="text-sm font-medium">Period
          <select className={`${input} mt-1`} value={preset} onChange={(e) => setPreset(e.target.value)}>
            {Object.entries(PRESETS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        {preset === "custom" && ["start", "end"].map((k) => (
          <label key={k} className="text-sm font-medium">{k === "start" ? "From" : "To"}
            <input type="date" className={`${input} mt-1`} value={custom[k]} onChange={(e) => setCustom({ ...custom, [k]: e.target.value })} />
          </label>
        ))}
        <label className="text-sm font-medium">Group by
          <select className={`${input} mt-1`} value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
            <option value="day">Day</option><option value="week">Week</option><option value="month">Month</option>
          </select>
        </label>
      </div>
        <BudgetAlerts />
      <Alert>{error}</Alert>
      {!data && !error && <Spinner />}
      {data && data.transaction_count === 0 && (
        <Card>
          <p className="font-medium">No transactions in this period.</p>
          <p className="mt-1 text-sm text-slate-600">
            {data.data_range.min ? `Your data covers ${data.data_range.min} to ${data.data_range.max}. Try "All time".` : "Upload a bank statement to get started."}
          </p>
          <Link to="/upload" className={`${btn.primary} mt-4`}>Upload statement</Link>
        </Card>
      )}

      {data && data.transaction_count > 0 && (
        <div className={`space-y-6 ${busy ? "opacity-60" : ""}`}>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {stats.map(([l, v, c]) => (
              <div key={l} className="rounded-lg border border-slate-200 bg-white p-4">
                <dt className="text-sm text-slate-500">{l}</dt>
                <dd className={`mt-1 truncate text-xl font-semibold ${c}`}>{v}</dd>
              </div>
            ))}
          </dl>

          <div className="grid gap-6 xl:grid-cols-5">
            <Card title="Spending by category" className="xl:col-span-2">
              <div className="h-72" role="img" aria-label="Donut chart of spending by category">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={data.categories} dataKey="spent" nameKey="category" innerRadius="55%" outerRadius="85%" paddingAngle={1}>
                      {data.categories.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v) => inr(v)} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card title={`Spent vs income by ${groupBy}`} className="xl:col-span-3">
              <div className="h-72" role="img" aria-label="Bar chart of spending and income over time">
                <ResponsiveContainer>
                  <BarChart data={data.timeline}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={inrShort} tick={{ fontSize: 11 }} width={50} />
                    <Tooltip formatter={(v) => inr(v)} />
                    <Legend />
                    <Bar dataKey="spent" name="Spent" fill="#312e81" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="income" name="Income" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <Card title="Category breakdown">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-left text-sm">
                <thead className="text-slate-500"><tr><th className="py-2 font-medium">Category</th><th className="font-medium">Share</th><th className="text-right font-medium">Transactions</th><th className="text-right font-medium">Spent</th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {data.categories.map((c, i) => (
                    <tr key={c.category_id}>
                      <td className="py-2"><span className="mr-2 inline-block h-2.5 w-2.5 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />{c.category}</td>
                      <td className="w-1/3"><div className="flex items-center gap-2"><div className="h-2 flex-1 rounded-full bg-slate-100"><div className="h-full rounded-full bg-indigo-800" style={{ width: `${c.percent}%` }} /></div><span className="w-12 text-right text-xs text-slate-500">{c.percent}%</span></div></td>
                      <td className="text-right">{c.count}</td>
                      <td className="text-right font-medium">{inr(c.spent)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
