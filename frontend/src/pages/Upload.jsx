import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api/client";
import { Alert, Card, PageHeader, btn } from "../components/ui";

const MAX_MB = 10;

export default function Upload() {
  const inputRef = useRef(null);
  const [drag, setDrag] = useState(false);
  const [progress, setProgress] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);

  const loadHistory = useCallback(() => api.post("/uploads/list").then((r) => setHistory(r.data)).catch(() => {}), []);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  const send = async (file) => {
    setError(""); setResult(null);
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) return setError("Only .csv files are supported. Export your statement from net banking as CSV.");
    if (file.size > MAX_MB * 1024 * 1024) return setError(`This file is larger than ${MAX_MB} MB. Export a shorter date range and upload again.`);
    if (file.size === 0) return setError("This file is empty.");
    const fd = new FormData();
    fd.append("file", file);
    setProgress(0);
    try {
      const { data } = await api.post("/uploads/create", fd, { onUploadProgress: (e) => setProgress(Math.round((e.loaded / (e.total || file.size)) * 100)) });
      setResult(data);
      loadHistory();
    } catch (err) {
      setError(errorMessage(err));
      loadHistory();
    } finally {
      setProgress(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const remove = async (u) => {
    if (!window.confirm(`Delete ${u.filename} and the ${u.inserted} transactions it added?`)) return;
    try { await api.post("/uploads/delete", { id: u.id }); loadHistory(); } catch (err) { setError(errorMessage(err)); }
  };

  return (
    <>
      <PageHeader title="Upload bank statement" />
      <div className="space-y-6">
        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); send(e.dataTransfer.files[0]); }}
          className={`rounded-lg border-2 border-dashed p-8 text-center sm:p-12 ${drag ? "border-amber-500 bg-amber-50" : "border-slate-300 bg-white"}`}
        >
          <p className="text-lg font-medium">Drop your statement CSV here</p>
          <p className="mt-1 text-sm text-slate-500">or choose a file. Up to {MAX_MB} MB. Needs Date, Description and Debit/Credit (or Amount) columns.</p>
          <input ref={inputRef} type="file" accept=".csv,text/csv" className="sr-only" id="file" onChange={(e) => send(e.target.files[0])} />
          <label htmlFor="file" className={`${btn.primary} mt-5 cursor-pointer ${progress !== null ? "pointer-events-none opacity-50" : ""}`}>Choose CSV file</label>
          {progress !== null && (
            <div className="mx-auto mt-5 max-w-sm" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-indigo-800" style={{ width: `${progress}%` }} /></div>
              <p className="mt-1 text-xs text-slate-500">{progress < 100 ? `Uploading ${progress}%` : "Reading and categorising transactions"}</p>
            </div>
          )}
        </div>

        <Alert>{error}</Alert>

        {result && (
          <Card title={`Imported ${result.filename}`}>
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              {[["Added", result.inserted, "text-emerald-700"], ["Already imported", result.duplicates, "text-slate-700"], ["Skipped", result.skipped, "text-amber-700"], ["Rows read", result.total_rows, "text-slate-700"]].map(([l, v, c]) => (
                <div key={l} className="rounded-md bg-slate-50 p-3"><dt className="text-slate-500">{l}</dt><dd className={`text-2xl font-semibold ${c}`}>{v}</dd></div>
              ))}
            </dl>
            {result.errors.length > 0 && (
              <details className="mt-4 text-sm">
                <summary className="cursor-pointer font-medium text-amber-800">{result.skipped} rows could not be read</summary>
                <ul className="mt-2 max-h-40 space-y-1 overflow-auto text-slate-600">
                  {result.errors.map((e, i) => <li key={i}>Row {e.row}: {e.reason}</li>)}
                </ul>
              </details>
            )}
            <Link to="/" className={`${btn.primary} mt-4`}>View dashboard</Link>
          </Card>
        )}

        <Card title="Upload history">
          {history.length === 0 ? <p className="text-sm text-slate-500">No uploads yet. Your first statement will show up here.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="text-slate-500"><tr><th className="py-2 pr-3 font-medium">File</th><th className="font-medium">Status</th><th className="font-medium">Added</th><th className="font-medium">Duplicates</th><th className="font-medium">Uploaded</th><th /></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {history.map((u) => (
                    <tr key={u.id}>
                      <td className="max-w-[220px] truncate py-2 pr-3" title={u.message || u.filename}>{u.filename}</td>
                      <td><span className={u.status === "failed" ? "text-rose-700" : "text-emerald-700"}>{u.status === "failed" ? "Failed" : "Imported"}</span></td>
                      <td>{u.inserted}</td><td>{u.duplicates}</td>
                      <td>{new Date(u.created_at + "Z").toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</td>
                      <td className="text-right"><button className={btn.danger} onClick={() => remove(u)}>Delete</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
