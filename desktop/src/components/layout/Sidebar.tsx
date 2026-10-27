import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  Activity,
  FolderGit2,
  ListTodo,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { useApprovalStore } from "@/store/approvalStore";

const navItems: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "/", label: "Chat", icon: MessageSquare },
  { to: "/tasks", label: "Tasks", icon: ListTodo },
  { to: "/approvals", label: "Approvals", icon: ShieldCheck },
  { to: "/projects", label: "Projects", icon: FolderGit2 },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
];

const COLLAPSE_KEY = "jarvis_sidebar_collapsed";

// The sidebar uses the slate scale, which the dark theme does not remap, so it
// stays dark in both themes.
export function Sidebar() {
  const pendingCount = useApprovalStore((s) => s.pending.length);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "true");

  const toggle = () => {
    setCollapsed((c) => {
      localStorage.setItem(COLLAPSE_KEY, String(!c));
      return !c;
    });
  };

  const ToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose;

  return (
    <aside
      className={`flex h-full shrink-0 flex-col bg-slate-900 text-slate-200 transition-[width] duration-150 ${
        collapsed ? "w-14" : "w-56"
      }`}
    >
      <div className={`flex h-12 items-center border-b border-slate-800 ${collapsed ? "justify-center" : "justify-between px-4"}`}>
        {!collapsed && <h1 className="text-base font-bold tracking-tight text-white">Jarvis</h1>}
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="rounded-md p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white focus-visible:outline-2 focus-visible:outline-blue-400"
        >
          <ToggleIcon size={16} aria-hidden />
        </button>
      </div>

      <nav aria-label="Main" className="flex-1 space-y-0.5 p-2">
        {navItems.map(({ to, label, icon: Icon }) => {
          const badge = to === "/approvals" && pendingCount > 0 ? pendingCount : 0;
          return (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              title={collapsed ? label : undefined}
              aria-label={badge ? `${label}, ${badge} pending` : label}
              className={({ isActive }) =>
                `relative flex items-center gap-3 rounded-lg py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-blue-400 ${
                  collapsed ? "justify-center px-0" : "px-3"
                } ${
                  isActive
                    ? "bg-slate-800 font-medium text-white before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-full before:bg-blue-400"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-100"
                }`
              }
            >
              <Icon size={17} aria-hidden className="shrink-0" />
              {!collapsed && <span>{label}</span>}
              {badge > 0 &&
                (collapsed ? (
                  <span className="absolute top-1 right-1.5 h-2 w-2 rounded-full bg-orange-500" aria-hidden />
                ) : (
                  <span className="ml-auto rounded-full bg-orange-500 px-1.5 py-0.5 text-xs font-semibold leading-none text-white" aria-hidden>
                    {badge}
                  </span>
                ))}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
