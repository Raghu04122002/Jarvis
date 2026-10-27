export type Theme = "light" | "dark" | "system";

const media = () => window.matchMedia("(prefers-color-scheme: dark)");

/** Toggle the `dark` class on <html>; "system" follows the OS setting. */
export function applyTheme(theme: Theme): void {
  const dark = theme === "dark" || (theme === "system" && media().matches);
  document.documentElement.classList.toggle("dark", dark);
  document.documentElement.style.colorScheme = dark ? "dark" : "light";
}

/** Apply the saved theme at startup and keep "system" in sync with the OS. */
export function initTheme(): void {
  const current = (): Theme => {
    const v = localStorage.getItem("jarvis_theme");
    return v === "light" || v === "dark" ? v : "system";
  };
  applyTheme(current());
  media().addEventListener("change", () => {
    if (current() === "system") applyTheme("system");
  });
}
