import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

// Rep app uses the light/teal palette from the Mark Anders mockups, distinct
// from the manager control plane's dark purple.
const teal = {
  primary: "#0d9488",
  primaryDark: "#0f766e",
  text: "#0f172a",
  textMuted: "#475569",
  textFaint: "#94a3b8",
  bgGradient:
    "radial-gradient(circle at 70% 15%, #b8f4d4 0%, transparent 40%), radial-gradient(circle at 55% 45%, #1a8fae 0%, transparent 35%), radial-gradient(circle at 30% 60%, #6ee7b7 0%, transparent 45%), linear-gradient(135deg, #a7f3d0 0%, #5eead4 45%, #2dd4bf 100%)",
  font: "'Inter', system-ui, sans-serif",
};

export const repTheme = teal;

const NAV = [
  { to: "/rep", label: "Dashboard", icon: "📊", end: true },
  { to: "/rep/activity", label: "Live Activity", icon: "⚡", end: false },
  { to: "/rep/prospects", label: "Prospects", icon: "👤", end: false },
  { to: "/rep/escalations", label: "Escalations", icon: "🚨", end: false },
];

function RepSidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const initials = (user?.full_name ?? user?.email ?? "?").split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div style={{ width: 160, background: "#fff", borderRight: "1px solid #e5e7eb", padding: "16px 12px", display: "flex", flexDirection: "column", gap: 22, minHeight: "100vh", flexShrink: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ width: 26, height: 26, borderRadius: "50%", background: teal.primary, display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 10, fontWeight: 700 }}>{initials}</div>
        <div>
          <div style={{ color: teal.text, fontSize: 11, fontWeight: 600 }}>{user?.full_name ?? user?.email}</div>
          <div style={{ color: "#6b7280", fontSize: 8 }}>{user?.title ?? user?.role}</div>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ color: teal.primary, fontSize: 8, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>Workspace</div>
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} style={({ isActive }) => ({
            color: isActive ? teal.primary : "#374151", fontWeight: isActive ? 600 : 400,
            fontSize: 11, textDecoration: "none", display: "flex", alignItems: "center", gap: 6,
          })}>{n.icon} {n.label}</NavLink>
        ))}
      </div>
      <div style={{ flex: 1 }} />
      <div>
        <div style={{ color: teal.primary, fontSize: 8, fontWeight: 700, textTransform: "uppercase", marginBottom: 8 }}>Account</div>
        <div onClick={() => { logout(); navigate("/login"); }} style={{ color: "#ef4444", fontSize: 10, cursor: "pointer" }}>⏻ Logout</div>
      </div>
    </div>
  );
}

export function RepLayout({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: "flex", width: "100%", minHeight: "100vh", fontFamily: teal.font, background: "#fff" }}>
      <RepSidebar />
      <div style={{ flex: 1, padding: "24px 28px", background: teal.bgGradient, overflowX: "hidden" }}>{children}</div>
    </div>
  );
}

// Light card matching the rep aesthetic (frosted white).
export function RepCard({ children, style }: { children: ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.78)", backdropFilter: "blur(6px)", border: "1px solid rgba(255,255,255,0.85)", borderRadius: 10, padding: 16, ...style }}>
      {children}
    </div>
  );
}