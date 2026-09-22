import { useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useIsMobile } from "../hooks";

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

const MAX_CONTENT = 1400;

const NAV = [
  { to: "/rep", label: "Dashboard", icon: "📊", end: true },
  { to: "/rep/activity", label: "Live Activity", icon: "⚡", end: false },
  { to: "/rep/prospects", label: "Prospects", icon: "👤", end: false },
  { to: "/rep/escalations", label: "Escalations", icon: "🚨", end: false },
];

function initialsOf(name: string) {
  return name.split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <>
      {NAV.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.end} onClick={onNavigate} style={({ isActive }) => ({
          color: isActive ? teal.primary : "#374151", fontWeight: isActive ? 600 : 400,
          fontSize: 12, textDecoration: "none", display: "flex", alignItems: "center", gap: 8, padding: "8px 6px",
        })}>{n.icon} {n.label}</NavLink>
      ))}
    </>
  );
}

function UserChip() {
  const { user } = useAuth();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ width: 26, height: 26, borderRadius: "50%", background: teal.primary, display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 10, fontWeight: 700, flexShrink: 0 }}>{initialsOf(user?.full_name ?? user?.email ?? "?")}</div>
      <div style={{ minWidth: 0 }}>
        <div style={{ color: teal.text, fontSize: 11, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.full_name ?? user?.email}</div>
        <div style={{ color: "#6b7280", fontSize: 8 }}>{user?.title ?? user?.role}</div>
      </div>
    </div>
  );
}

function LogoutLink({ onNavigate }: { onNavigate?: () => void }) {
  const { logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div onClick={() => { onNavigate?.(); logout(); navigate("/login"); }} style={{ color: "#ef4444", fontSize: 11, cursor: "pointer" }}>⏻ Logout</div>
  );
}

function DesktopSidebar() {
  return (
    <div style={{ width: 170, background: "#fff", borderRight: "1px solid #e5e7eb", padding: "16px 12px", display: "flex", flexDirection: "column", gap: 20, minHeight: "100vh", flexShrink: 0 }}>
      <UserChip />
      <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
        <div style={{ color: teal.primary, fontSize: 8, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>Workspace</div>
        <NavItems />
      </div>
      <div>
        <div style={{ color: teal.primary, fontSize: 8, fontWeight: 700, textTransform: "uppercase", marginBottom: 8 }}>Account</div>
        <LogoutLink />
      </div>
    </div>
  );
}

export function RepLayout({ children }: { children: ReactNode }) {
  const isMobile = useIsMobile();
  const [menuOpen, setMenuOpen] = useState(false);

  const contentWrapper = (
    <div style={{ width: "100%", maxWidth: MAX_CONTENT, margin: "0 auto" }}>{children}</div>
  );

  if (isMobile) {
    return (
      <div style={{ display: "flex", flexDirection: "column", width: "100%", minHeight: "100vh", fontFamily: teal.font, background: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", background: "#fff", borderBottom: "1px solid #e5e7eb", position: "sticky", top: 0, zIndex: 20 }}>
          <UserChip />
          <button onClick={() => setMenuOpen((v) => !v)} aria-label="Menu"
            style={{ background: "rgba(13,148,136,0.1)", border: "1px solid rgba(13,148,136,0.3)", color: teal.primary, borderRadius: 8, padding: "8px 12px", fontSize: 16, cursor: "pointer", lineHeight: 1 }}>
            {menuOpen ? "\u2715" : "\u2630"}
          </button>
        </div>

        {menuOpen && (
          <div style={{ background: "#fff", padding: "10px 14px", display: "flex", flexDirection: "column", gap: 6, borderBottom: "1px solid #e5e7eb" }}>
            <NavItems onNavigate={() => setMenuOpen(false)} />
            <div style={{ marginTop: 6, paddingTop: 8, borderTop: "1px solid #e5e7eb" }}>
              <LogoutLink onNavigate={() => setMenuOpen(false)} />
            </div>
          </div>
        )}

        <div style={{ flex: 1, padding: "16px", background: teal.bgGradient }}>{contentWrapper}</div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", width: "100%", minHeight: "100vh", fontFamily: teal.font, background: "#fff" }}>
      <DesktopSidebar />
      <div style={{ flex: 1, padding: "24px 28px", background: teal.bgGradient, overflowX: "hidden" }}>{contentWrapper}</div>
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