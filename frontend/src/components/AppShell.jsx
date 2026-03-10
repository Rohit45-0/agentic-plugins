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
      className={({ isActive }) =>
        clsx(
          "flex items-center justify-center w-11 h-11 rounded-xl transition-all duration-100 cursor-pointer",
          isActive
            ? "bg-emerald-900 text-emerald-100"
            : "text-neutral-400 hover:bg-neutral-100 hover:text-neutral-900"
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
    <div className="flex h-screen bg-black overflow-hidden">
      {/* Icon-only Sidebar */}
      <aside className="flex flex-col items-center w-18 border-r border-neutral-900 bg-black py-4 gap-1 flex-shrink-0" style={{ width: '72px' }}>
        {/* Logo / Brand */}
        <div className="flex items-center justify-center w-11 h-11 bg-emerald-500/10 border border-emerald-500/20 rounded-xl mb-3 cursor-pointer" onClick={() => navigate("/dashboard")}>
          <Zap size={20} className="text-emerald-500" strokeWidth={2.5} />
        </div>

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
            className="flex items-center justify-center w-11 h-11 rounded-xl text-neutral-500 hover:bg-red-500/10 hover:text-red-500 transition-all duration-100"
          >
            <LogOut size={22} strokeWidth={1.75} />
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto bg-black">
        <Outlet />
      </main>
    </div>
  );
}
