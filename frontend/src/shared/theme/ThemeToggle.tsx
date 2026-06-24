// frontend/src/shared/theme/ThemeToggle.tsx
import { useTheme } from "./useTheme";
import type { Theme } from "./ThemeContext";

const SUN = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
    <circle cx="12" cy="12" r="5" />
    <path d="M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
  </svg>
);
const MOON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  </svg>
);
const SYSTEM = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
    <rect x="2" y="3" width="20" height="14" rx="2" />
    <path d="M8 21h8M12 17v4" />
  </svg>
);

const OPTIONS: { value: Theme; label: string; icon: typeof SUN }[] = [
  { value: "light", label: "Light", icon: SUN },
  { value: "dark", label: "Dark", icon: MOON },
  { value: "system", label: "System", icon: SYSTEM },
];

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="ds-theme-switch" role="group" aria-label="Color theme">
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          className={"ds-theme-switch-btn" + (theme === o.value ? " is-active" : "")}
          aria-pressed={theme === o.value}
          aria-label={o.label}
          title={o.label}
          onClick={() => setTheme(o.value)}
        >
          {o.icon}
        </button>
      ))}
    </div>
  );
}
