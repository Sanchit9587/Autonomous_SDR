import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { theme } from "../theme";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: "📊" },
  { to: "/campaigns", label: "Campaigns", icon: "🚩" },
  { to: "/profiles", label: "Customer Profiles", icon: "👤" },
  { to: "/assets", label: "Assets", icon: "📁" },
  { to: "/generative-edits", label: "Generative Edits", icon: "✨" },
];

function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const initials = (user?.full_name ?? user?.email ?? "?")
    .split(" ")
    .map((s) => s[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div
      style={{
        width: 170,
        background: theme.sidebarGradient,
        padding: "16px 12px",
        display: "flex",
        flexDirection: "column",
        gap: 20,
        minHeight: "100vh",
        flexShrink: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div
          style={{
            width: 26,
            height: 26,
            borderRadius: "50%",
            background: "#6a4a8a",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
            fontSize: 10,
            fontWeight: 700,
          }}
        >
          {initials}
        </div>
        <div>
          <div style={{ color: "#fff", fontSize: 11, fontWeight: 600 }}>{user?.full_name ?? user?.email}</div>
          <div style={{ color: theme.textMuted, fontSize: 8 }}>{user?.title ?? user?.role}</div>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              color: isActive ? "#fff" : theme.textMuted,
              background: isActive ? "rgba(255,255,255,0.06)" : "transparent",
              fontSize: 11,
              textDecoration: "none",
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "8px 8px",
              borderRadius: 6,
            })}
          >
            {item.icon} {item.label}
          </NavLink>
        ))}
      </div>

      <div>
        <div style={{ color: theme.textFaint, fontSize: 8, textTransform: "uppercase", marginBottom: 8 }}>
          Account
        </div>
        <div
          onClick={() => {
            logout();
            navigate("/login");
          }}
          style={{ color: theme.pink, fontSize: 10, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}
        >
          ⏻ Logout
        </div>
      </div>
    </div>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: "flex", width: "100%", minHeight: "100vh", fontFamily: theme.font, background: theme.bg }}>
      <Sidebar />
      <div style={{ flex: 1, padding: "24px 32px", background: theme.mainGradient, overflowX: "hidden" }}>
        {children}
      </div>
    </div>
  );
}