import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { btn } from "./ui";

const links = [
  ["/", "Dashboard"],
  ["/upload", "Upload statement"],
  ["/transactions", "Transactions"],
  ["/categories", "Categories"],
  ["/budgets", "Budgets"]
];

export default function Layout() {
  const { user, logout } = useAuth();
  const item = ({ isActive }) =>
    `block whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 ${
      isActive ? "bg-amber-400 text-indigo-950" : "text-indigo-100 hover:bg-indigo-900"
    }`;
  return (
    <div className="min-h-screen md:flex">
      <aside className="bg-indigo-950 p-4 md:sticky md:top-0 md:h-screen md:w-60 md:shrink-0 md:flex md:flex-col">
        <div className="mb-4 flex items-center justify-between md:mb-8 md:block">
          <p className="text-lg font-semibold text-white">Rupee Ledger</p>
          <p className="hidden text-xs text-indigo-300 md:mt-1 md:block">Know where the money went</p>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto md:flex-col">
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"} className={item}>{label}</NavLink>
          ))}
        </nav>
        <div className="mt-4 flex items-center justify-between gap-2 border-t border-indigo-900 pt-4 md:mt-auto md:flex-col md:items-start">
          <p className="truncate text-sm text-indigo-200">{user?.name}</p>
          <button onClick={logout} className={`${btn.ghost} !py-1`}>Log out</button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8"><Outlet /></main>
    </div>
  );
}
