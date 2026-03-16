import { useState, useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearAccessToken, getCurrentUser } from "../services/auth";
import {
  Bot,
  Settings,
  LogOut,
  Zap,
} from "lucide-react";
import clsx from "clsx";

const navItems = [
  { to: "/dashboard", icon: Bot, label: "WhatsApp Bot Dashboard" },
];

const bottomItems = [
  { to: "/settings", icon: Settings, label: "Settings" },
];

function SidebarLink({ to, icon: Icon, label, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      title={label}
      aria-label={label}
      className={({ isActive }) =>
        clsx(
          "flex items-center justify-center w-11 h-11 rounded-xl transition-all duration-100 cursor-pointer",
          isActive
            ? "bg-cyan-400/15 text-cyan-200 border border-cyan-300/20"
            : "text-slate-400 hover:bg-slate-700/40 hover:text-slate-100"
        )
      }
    >
      <Icon size={22} strokeWidth={1.75} />
    </NavLink>
  );
}

export default function AppShell({ onLogout }) {
  const navigate = useNavigate();

  const logout = () => {
    onLogout?.();
    navigate("/login");
  };

  useEffect(() => {
    getCurrentUser()
      .catch((err) => {
        console.warn("Auth check failed:", err.message);
        logout();
      });
  }, []);

  return (
    <div className="flex h-screen app-shell-base overflow-hidden">
      {/* Icon-only Sidebar */}
      <aside className="flex flex-col items-center w-18 border-r py-4 gap-1 flex-shrink-0 surface-1" style={{ width: "72px" }}>
        {/* Logo / Brand */}
        <button
          type="button"
          aria-label="Open dashboard"
          className="flex items-center justify-center w-11 h-11 rounded-xl mb-3 cursor-pointer surface-2"
          onClick={() => navigate("/dashboard")}
        >
          <Zap size={20} className="text-cyan-300" strokeWidth={2.5} />
        </button>

        {/* Nav Items */}
        <nav className="flex flex-col gap-0.5 flex-1 mt-4">
          {navItems.map((item) => (
            <SidebarLink key={item.to} {...item} />
          ))}
        </nav>

        {/* Bottom Items */}
        <div className="flex flex-col gap-0.5 mt-auto">
          {bottomItems.map((item) => (
            <SidebarLink key={item.to} {...item} />
          ))}
          <button
            onClick={logout}
            title="Logout"
            aria-label="Logout"
            className="flex items-center justify-center w-11 h-11 rounded-xl text-slate-500 hover:bg-red-500/10 hover:text-red-300 transition-all duration-100"
          >
            <LogOut size={22} strokeWidth={1.75} />
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto app-shell-bg">
        <Outlet />
      </main>
    </div>
  );
}
