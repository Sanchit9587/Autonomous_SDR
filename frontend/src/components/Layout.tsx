import { useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useIsMobile } from "../hooks";
import { theme } from "../theme";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: "📊" },
  { to: "/campaigns", label: "Campaigns", icon: "🚩" },
  { to: "/profiles", label: "Customer Profiles", icon: "👤" },
  { to: "/assets", label: "Assets", icon: "📁" },
  { to: "/generative-edits", label: "Generative Edits", icon: "✨" },
];

// Cap content width on large screens so cards don't stretch absurdly wide on
// ultrawide monitors; content fills up to this and is centered.
const MAX_CONTENT = 1400;

function initialsOf(name: string) {
  return name.split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <>
      {NAV.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          onClick={onNavigate}
          style={({ isActive }) => ({
            color: isActive ? "#fff" : theme.textMuted,
            background: isActive ? "rgba(255,255,255,0.06)" : "transparent",
            fontSize: 12,
            textDecoration: "none",
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "10px 10px",
            borderRadius: 6,
          })}
        >
          {item.icon} {item.label}
        </NavLink>
      ))}
    </>
  );
}

function UserChip() {
  const { user } = useAuth();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ width: 26, height: 26, borderRadius: "50%", background: "#6a4a8a", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 10, fontWeight: 700, flexShrink: 0 }}>
        {initialsOf(user?.full_name ?? user?.email ?? "?")}
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ color: "#fff", fontSize: 11, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.full_name ?? user?.email}</div>
        <div style={{ color: theme.textMuted, fontSize: 8 }}>{user?.title ?? user?.role}</div>
      </div>
    </div>
  );
}

function LogoutLink({ onNavigate }: { onNavigate?: () => void }) {
  const { logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div
      onClick={() => { onNavigate?.(); logout(); navigate("/login"); }}
      style={{ color: theme.pink, fontSize: 11, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}
    >
      ⏻ Logout
    </div>
  );
}

function DesktopSidebar() {
  return (
    <div style={{ width: 180, background: theme.sidebarGradient, padding: "16px 12px", display: "flex", flexDirection: "column", gap: 20, minHeight: "100vh", flexShrink: 0 }}>
      <UserChip />
      <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
        <NavItems />
      </div>
      <div>
        <div style={{ color: theme.textFaint, fontSize: 8, textTransform: "uppercase", marginBottom: 8 }}>Account</div>
        <LogoutLink />
      </div>
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const isMobile = useIsMobile();
  const [menuOpen, setMenuOpen] = useState(false);

  const contentWrapper = (
    <div style={{ width: "100%", maxWidth: MAX_CONTENT, margin: "0 auto" }}>{children}</div>
  );

  if (isMobile) {
    return (
      <div style={{ display: "flex", flexDirection: "column", width: "100%", minHeight: "100vh", fontFamily: theme.font, background: theme.bg }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", background: theme.sidebarGradient, position: "sticky", top: 0, zIndex: 20 }}>
          <UserChip />
          <button
            onClick={() => setMenuOpen((v) => !v)}
            aria-label="Menu"
            style={{ background: "rgba(255,255,255,0.08)", border: `1px solid ${theme.borderStrong}`, color: "#fff", borderRadius: 8, padding: "8px 12px", fontSize: 16, cursor: "pointer", lineHeight: 1 }}
          >
            {menuOpen ? "\u2715" : "\u2630"}
          </button>
        </div>

        {menuOpen && (
          <div style={{ background: theme.sidebar, padding: "10px 12px", display: "flex", flexDirection: "column", gap: 4, borderBottom: `1px solid ${theme.border}` }}>
            <NavItems onNavigate={() => setMenuOpen(false)} />
            <div style={{ marginTop: 8, paddingTop: 8, borderTop: `1px solid ${theme.border}` }}>
              <LogoutLink onNavigate={() => setMenuOpen(false)} />
            </div>
          </div>
        )}

        <div style={{ flex: 1, padding: "16px", background: theme.mainGradient }}>{contentWrapper}</div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", width: "100%", minHeight: "100vh", fontFamily: theme.font, background: theme.bg }}>
      <DesktopSidebar />
      <div style={{ flex: 1, padding: "24px 32px", background: theme.mainGradient, overflowX: "hidden" }}>
        {contentWrapper}
      </div>
    </div>
  );
}