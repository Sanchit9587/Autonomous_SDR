import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import type { UserRole } from "../types";
import { Spinner } from "./ui";

export function ProtectedRoute({ children, roles }: { children: ReactNode; roles?: UserRole[] }) {
  const { user, loading } = useAuth();

  if (loading) return <Spinner label="Restoring session…" />;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role) && user.role !== "admin") {
    return (
      <div style={{ padding: 40, color: "#f28b96", fontFamily: "Inter, sans-serif" }}>
        You don’t have access to this area (requires: {roles.join(", ")}).
      </div>
    );
  }
  return <>{children}</>;
}