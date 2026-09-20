// Design tokens pulled from the DronaHQ mockups so the React app matches the
// control-plane look (dark purple, radial-gradient panels).
export const theme = {
  bg: "#120b18",
  bgMain: "#150e1c",
  sidebar: "#1a0f24",
  card: "rgba(40,30,55,0.7)",
  cardSolid: "rgba(40,30,55,0.55)",
  panelGradient:
    "linear-gradient(135deg, rgba(120,60,160,0.35), rgba(60,40,120,0.35))",
  mainGradient:
    "radial-gradient(circle at 70% 20%, rgba(90,40,200,0.25) 0%, transparent 40%), #150e1c",
  sidebarGradient:
    "radial-gradient(circle at 30% 20%, rgba(220,30,90,0.35) 0%, transparent 45%), radial-gradient(circle at 60% 80%, rgba(80,40,200,0.3) 0%, transparent 45%), #1a0f24",
  border: "rgba(255,255,255,0.08)",
  borderStrong: "rgba(255,255,255,0.15)",
  purple: "#8b5cf6",
  purpleLight: "#a78bfa",
  purpleLighter: "#c4b0f7",
  pink: "#c81e50",
  green: "#4ade80",
  amber: "#e0b060",
  red: "#f28b96",
  text: "#ffffff",
  textDim: "#d8d3de",
  textMuted: "#a89fb3",
  textFaint: "#7a7484",
  font: "'Inter', system-ui, -apple-system, sans-serif",
} as const;

// Status → colors for campaign/prospect badges.
export const statusColors: Record<string, { bg: string; color: string; border: string }> = {
  live: { bg: "rgba(74,222,128,0.15)", color: "#4ade80", border: "rgba(74,222,128,0.4)" },
  draft: { bg: "rgba(100,116,139,0.15)", color: "#94a3b8", border: "rgba(100,116,139,0.3)" },
  paused: { bg: "rgba(230,170,60,0.15)", color: "#e0b060", border: "rgba(230,170,60,0.4)" },
  completed: { bg: "rgba(139,92,246,0.15)", color: "#c4b0f7", border: "rgba(139,92,246,0.4)" },
  archived: { bg: "rgba(100,116,139,0.1)", color: "#7a7484", border: "rgba(100,116,139,0.25)" },
  qualified: { bg: "rgba(37,99,235,0.15)", color: "#8fb2ff", border: "rgba(37,99,235,0.3)" },
  researched: { bg: "rgba(100,116,139,0.15)", color: "#94a3b8", border: "rgba(100,116,139,0.3)" },
  discovered: { bg: "rgba(100,116,139,0.1)", color: "#94a3b8", border: "rgba(100,116,139,0.25)" },
  rejected: { bg: "rgba(220,60,80,0.15)", color: "#f28b96", border: "rgba(220,60,80,0.3)" },
  contacted: { bg: "rgba(139,92,246,0.15)", color: "#c4b0f7", border: "rgba(139,92,246,0.3)" },
  engaged: { bg: "rgba(74,222,128,0.15)", color: "#4ade80", border: "rgba(74,222,128,0.4)" },
  meeting: { bg: "rgba(74,222,128,0.2)", color: "#4ade80", border: "rgba(74,222,128,0.5)" },
  opportunity: { bg: "rgba(139,92,246,0.2)", color: "#c4b0f7", border: "rgba(139,92,246,0.5)" },
};