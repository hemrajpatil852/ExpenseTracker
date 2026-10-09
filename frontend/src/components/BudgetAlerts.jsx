import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client";
import { Alert } from "./ui";

export default function BudgetAlerts() {
  const [items, setItems] = useState([]);
  useEffect(() => {
    api.post("/budgets/status", {}).then((r) => setItems(r.data.items.filter((i) => i.state !== "ok"))).catch(() => {});
  }, []);
  if (!items.length) return null;
  return (
    <div className="mb-6 space-y-2">
      {items.map((i) => (
        <Alert key={i.category_id} tone={i.state === "over" ? "error" : "warn"}>
          <strong>{i.category}:</strong> {i.message}{" "}
          <Link to="/budgets" className="font-medium underline">Review budgets</Link>
        </Alert>
      ))}
    </div>
  );
}