import { NavLink } from "react-router-dom";
import { useApprovalStore } from "@/store/approvalStore";

const navItems = [
  { to: "/", label: "Chat", icon: "💬" },
  { to: "/tasks", label: "Tasks", icon: "📋" },
  { to: "/approvals", label: "Approvals", icon: "🔒" },
  { to: "/projects", label: "Projects", icon: "📁" },
  { to: "/activity", label: "Activity", icon: "📡" },
  { to: "/settings", label: "Settings", icon: "⚙️" },
];

export function Sidebar() {
  const pendingCount = useApprovalStore((s) => s.pending.length);

  return (
    <aside className="w-56 bg-gray-900 text-gray-200 flex flex-col h-full">
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-lg font-bold tracking-tight">Jarvis</h1>
      </div>

      <nav className="flex-1 py-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-800 ${
                isActive ? "bg-gray-800 text-white" : "text-gray-400"
              }`
            }
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
            {item.to === "/approvals" && pendingCount > 0 && (
              <span className="ml-auto bg-orange-600 text-white text-xs px-1.5 py-0.5 rounded-full">
                {pendingCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
