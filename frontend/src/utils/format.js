export const inr = (n) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(n || 0);
export const inrShort = (n) => new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 }).format(n || 0);

export const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export const PRESETS = {
  this_month: "This month",
  last_month: "Last month",
  last_3_months: "Last 3 months",
  this_year: "This year",
  all: "All time",
  custom: "Custom",
};

export function presetRange(p) {
  const t = new Date();
  const y = t.getFullYear(), m = t.getMonth();
  switch (p) {
    case "this_month": return [ymd(new Date(y, m, 1)), ymd(new Date(y, m + 1, 0))];
    case "last_month": return [ymd(new Date(y, m - 1, 1)), ymd(new Date(y, m, 0))];
    case "last_3_months": return [ymd(new Date(y, m - 2, 1)), ymd(new Date(y, m + 1, 0))];
    case "this_year": return [ymd(new Date(y, 0, 1)), ymd(new Date(y, 11, 31))];
    default: return [null, null];
  }
}

export const nonEmpty = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== "" && v != null));
