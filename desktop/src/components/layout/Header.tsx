import { ConnectionStatus } from "@/components/settings/ConnectionStatus";

export function Header() {
  return (
    <header className="h-10 border-b border-gray-200 bg-white flex items-center justify-between px-4">
      <div />
      <ConnectionStatus />
    </header>
  );
}
