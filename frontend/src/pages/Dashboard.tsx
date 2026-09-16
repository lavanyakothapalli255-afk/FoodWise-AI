import { useEffect, useState } from "react";

const API = "http://localhost:8000/api";

interface DashboardSummary {
  detail?: string;
  total_centers?: number;
  total_meals?: number;
  total_recipients?: number;
  total_forecasts?: number;
  total_production_decisions?: number;
  total_redistribution_plans?: number;
  authorized_plans?: number;
}

const card: React.CSSProperties = {
  background: "var(--code-bg, #1f2028)",
  border: "1px solid var(--border, #2e303a)",
  borderRadius: 10,
  padding: "20px 24px",
  marginBottom: 18,
  textAlign: "left",
};

const tag = (color: string): React.CSSProperties => ({
  display: "inline-block",
  padding: "3px 10px",
  borderRadius: 20,
  fontSize: 12,
  fontWeight: 600,
  background: color === "gray" ? "rgba(156,163,175,0.15)" : color === "red" ? "rgba(239,68,68,0.15)" : color === "blue" ? "rgba(59,130,246,0.15)" : "rgba(34,197,94,0.15)",
  color: color === "gray" ? "#9ca3af" : color === "red" ? "#ef4444" : color === "blue" ? "#3b82f6" : "#22c55e",
});

function Dashboard() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const res = await fetch(`${API}/dashboard/summary`);
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const json = await res.json();
        setData(json);
      } catch (e: any) {
        setError(e.message || "Failed to fetch dashboard summary");
      } finally {
        setLoading(false);
      }
    };
    fetchSummary();
  }, []);

  const hasData = data && !data.detail;

  return (
    <div>
      {/* 1. Header */}
      <h1 style={{ fontSize: 28, margin: "0 0 4px", color: "var(--text-h, #f3f4f6)" }}>
        FoodWise AI
      </h1>
      <p style={{ color: "var(--text, #9ca3af)", fontSize: 16, marginBottom: 24 }}>
        Predict demand. Decide production. Rescue unavoidable surplus.
      </p>

      {/* 2. Decision Pipeline Section (Centerpiece) */}
      <div style={{ ...card, border: "1px solid #3b82f6", background: "rgba(59, 130, 246, 0.05)" }}>
        <h2 style={{ fontSize: 18, margin: "0 0 16px", color: "#3b82f6" }}>
          FoodWise AI Decision Pipeline
        </h2>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginTop: 8 }}>
          <span style={{ ...tag("blue"), padding: "6px 14px", fontSize: 14 }}>Historical Data</span>
          <span style={{ color: "#3b82f6" }}>→</span>
          <span style={{ ...tag("blue"), padding: "6px 14px", fontSize: 14 }}>AI Forecast</span>
          <span style={{ color: "#3b82f6" }}>→</span>
          <span style={{ ...tag("blue"), padding: "6px 14px", fontSize: 14 }}>Production Decision</span>
          <span style={{ color: "#3b82f6" }}>→</span>
          <span style={{ ...tag("blue"), padding: "6px 14px", fontSize: 14 }}>Actual Outcome</span>
          <span style={{ color: "#3b82f6" }}>→</span>
          <span style={{ ...tag("blue"), padding: "6px 14px", fontSize: 14 }}>Surplus Response</span>
        </div>
      </div>

      {/* 2. KPI Section */}
      <div style={card}>
        <h2 style={{ fontSize: 17, margin: "0 0 14px", color: "var(--text-h, #f3f4f6)" }}>
          Network Overview
        </h2>
        {loading ? (
          <p style={{ fontSize: 14, color: "var(--text)" }}>Loading metrics...</p>
        ) : error ? (
          <p style={{ fontSize: 14, color: "#ef4444" }}>{error}</p>
        ) : data?.detail ? (
          <p style={{ fontSize: 14, color: "var(--text)", fontStyle: "italic" }}>
            Backend reports: "{data.detail}"
          </p>
        ) : hasData ? (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12 }}>
            <div>
              <div style={{ fontSize: 13, color: "var(--text)" }}>Centers</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: "var(--text-h)" }}>{data.total_centers ?? "-"}</div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: "var(--text)" }}>Meals</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: "var(--text-h)" }}>{data.total_meals ?? "-"}</div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: "var(--text)" }}>Recipients</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: "var(--text-h)" }}>{data.total_recipients ?? "-"}</div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: "var(--text)" }}>Authorized Plans</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: "var(--text-h)" }}>{data.authorized_plans ?? "-"}</div>
            </div>
          </div>
        ) : null}
      </div>

      {/* 3. Main Decision Section */}
      <div style={card}>
        <h2 style={{ fontSize: 17, margin: "0 0 4px", color: "var(--text-h, #f3f4f6)" }}>
          Prototype Activity
        </h2>
        <p style={{ fontSize: 13, color: "var(--text)", margin: "0 0 14px", fontStyle: "italic" }}>
          System activity recorded during testing. Not measured impact.
        </p>
        {hasData ? (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <div>
              <div style={{ fontSize: 13, color: "var(--text)" }}>Forecasts Generated</div>
              <div style={{ fontSize: 20, fontWeight: 500, color: "var(--text-h)" }}>{data.total_forecasts ?? 0}</div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: "var(--text)" }}>Production Decisions</div>
              <div style={{ fontSize: 20, fontWeight: 500, color: "var(--text-h)" }}>{data.total_production_decisions ?? 0}</div>
            </div>
            <div>
              <div style={{ fontSize: 13, color: "var(--text)" }}>Redistribution Plans</div>
              <div style={{ fontSize: 20, fontWeight: 500, color: "var(--text-h)" }}>{data.total_redistribution_plans ?? 0}</div>
            </div>
          </div>
        ) : (
          <p style={{ fontSize: 14, color: "var(--text)" }}>Awaiting operational data.</p>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
