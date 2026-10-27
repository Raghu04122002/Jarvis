import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { ApprovalBanner } from "@/components/approvals/ApprovalBanner";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <ApprovalBanner />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
