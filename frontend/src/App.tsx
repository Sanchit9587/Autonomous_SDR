import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Login } from "./pages/Login";
import { Campaigns } from "./pages/Campaigns";
import { CampaignConfiguration } from "./pages/CampaignConfiguration";
import { CampaignSummary } from "./pages/CampaignSummary";
import { CustomerProfiles } from "./pages/CustomerProfiles";
import { Assets } from "./pages/Assets";
import { Prospects } from "./pages/Prospects";

// Wrap a manager page in the auth gate + sidebar layout.
function Managed({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute roles={["manager"]}>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route path="/campaigns" element={<Managed><Campaigns /></Managed>} />
      <Route path="/campaigns/new" element={<Managed><CampaignConfiguration mode="create" /></Managed>} />
      <Route path="/campaigns/:id" element={<Managed><CampaignSummary /></Managed>} />
      <Route path="/campaigns/:id/edit" element={<Managed><CampaignConfiguration mode="edit" /></Managed>} />
      <Route path="/campaigns/:id/prospects" element={<Managed><Prospects /></Managed>} />
      <Route path="/profiles" element={<Managed><CustomerProfiles /></Managed>} />
      <Route path="/assets" element={<Managed><Assets /></Managed>} />

      <Route path="/" element={<Navigate to="/campaigns" replace />} />
      <Route path="*" element={<Navigate to="/campaigns" replace />} />
    </Routes>
  );
}