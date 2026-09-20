import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { theme } from "../theme";
import { ApiError } from "../api/client";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("ava@sdrhq.io");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError(null);
    setBusy(true);
    try {
      const user = await login(email, password);
      // Managers → control plane; reps → operational app.
      navigate(user.role === "rep" ? "/rep" : "/campaigns");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      style={{
        width: "100%",
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: theme.font,
        background:
          "radial-gradient(circle at 15% 30%, rgba(220,30,60,0.55) 0%, transparent 35%), radial-gradient(circle at 30% 70%, rgba(90,40,220,0.5) 0%, transparent 40%), radial-gradient(circle at 75% 60%, rgba(60,60,220,0.45) 0%, transparent 45%), #150a20",
      }}
    >
      <div
        style={{
          background: "rgba(60,45,80,0.45)",
          backdropFilter: "blur(14px)",
          border: `1px solid ${theme.borderStrong}`,
          borderRadius: 10,
          padding: "28px",
          width: 300,
          boxShadow: "0 8px 30px rgba(0,0,0,0.35)",
        }}
      >
        <h1 style={{ color: "#fff", fontSize: 20, fontWeight: 700, margin: "0 0 18px 0" }}>Login</h1>

        <label style={{ display: "block", color: "#cfc9d6", fontSize: 11, marginBottom: 5 }}>Email</label>
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          style={inputStyle}
        />

        <label style={{ display: "block", color: "#cfc9d6", fontSize: 11, margin: "12px 0 5px" }}>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          style={inputStyle}
        />

        {error && <div style={{ color: "#f28b96", fontSize: 11, marginTop: 12 }}>{error}</div>}

        <button
          onClick={submit}
          disabled={busy}
          style={{
            width: "100%",
            padding: 10,
            marginTop: 18,
            background: theme.pink,
            color: "#fff",
            border: "none",
            borderRadius: 5,
            fontWeight: 700,
            fontSize: 13,
            cursor: busy ? "wait" : "pointer",
            fontFamily: theme.font,
          }}
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>

        <div style={{ color: "#8a8494", fontSize: 9, marginTop: 14, lineHeight: 1.5 }}>
          Demo: ava@sdrhq.io (manager) · mark@sdrhq.io (rep) — password demo1234
        </div>
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  border: "none",
  borderRadius: 4,
  background: "#fff",
  fontSize: 12,
  boxSizing: "border-box",
  color: "#333",
  fontFamily: theme.font,
};