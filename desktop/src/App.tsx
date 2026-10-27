import { useEffect } from "react";
import { AppRoutes } from "./routes";
import { AppShell } from "./components/layout/AppShell";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import { useSSE } from "./hooks/useSSE";
import { useSettingsStore } from "./store/settingsStore";

export default function App() {
  const backendUrl = useSettingsStore((s) => s.backendUrl);

  useSSE(backendUrl);

  useEffect(() => {
    document.title = "Jarvis";
  }, []);

  return (
    <ErrorBoundary>
      <AppShell>
        <AppRoutes />
      </AppShell>
    </ErrorBoundary>
  );
}
