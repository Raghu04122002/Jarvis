import { useEffect } from "react";
import { AppRoutes } from "./routes";
import { AppShell } from "./components/layout/AppShell";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import { Toaster } from "sonner";
import { useSSE } from "./hooks/useSSE";
import { useNotifications } from "./hooks/useNotifications";
import { useSettingsStore } from "./store/settingsStore";

export default function App() {
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const theme = useSettingsStore((s) => s.theme);

  useSSE(backendUrl);
  useNotifications();

  useEffect(() => {
    document.title = "Jarvis";
  }, []);

  return (
    <ErrorBoundary>
      <AppShell>
        <AppRoutes />
      </AppShell>
      <Toaster theme={theme} position="bottom-right" closeButton richColors />
    </ErrorBoundary>
  );
}
