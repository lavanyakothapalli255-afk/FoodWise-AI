import { useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

interface ForecastRead {
  id: number;
  center_id: number;
  meal_id: number;
  forecast_date: string;
  predicted_demand: number;
  confidence_lower?: number;
  confidence_upper?: number;
  model_version?: string;
}

interface HistoricalObservation {
  week: number;
  num_orders: number;
}

interface ProductionRecommendResponse {
  id: number;
  center_id: number;
  meal_id: number;
  date: string;
  recommended_quantity: number;
  actual_quantity?: number;
  decision_status: string;
  policy_used: string;
  point_forecast: number;
  expected_surplus: number;
  expected_shortage: number;
}

const card: React.CSSProperties = {
  background: "var(--code-bg, #1f2028)",
  border: "1px solid var(--border, #2e303a)",
  borderRadius: 10,
  padding: "20px 24px",
  marginBottom: 18,
  textAlign: "left",
};

const inputStyle: React.CSSProperties = {
  background: "#121212",
  color: "#f3f4f6",
  border: "1px solid #374151",
  padding: "8px 12px",
  borderRadius: 6,
  marginRight: 12,
};

const btnStyle: React.CSSProperties = {
  background: "#3b82f6",
  color: "#fff",
  border: "none",
  padding: "8px 16px",
  borderRadius: 6,
  cursor: "pointer",
  fontWeight: 500,
};

const tag = (color: string): React.CSSProperties => ({
  display: "inline-block",
  padding: "3px 10px",
  borderRadius: 20,
  fontSize: 12,
  fontWeight: 600,
  background: color === "gray" ? "rgba(156,163,175,0.15)" : color === "red" ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)",
  color: color === "gray" ? "#9ca3af" : color === "red" ? "#ef4444" : "#22c55e",
});

function ForecastProduction() {
  const [centerId, setCenterId] = useState<number>(1);
  const [mealId, setMealId] = useState<number>(1);
  const [date, setDate] = useState<string>(new Date().toISOString().split("T")[0]);

  const [forecast, setForecast] = useState<ForecastRead | null>(null);
  const [historicalData, setHistoricalData] = useState<HistoricalObservation[] | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const [policy, setPolicy] = useState<string>("p80");
  const [recommendation, setRecommendation] = useState<ProductionRecommendResponse | null>(null);
  const [isRecommending, setIsRecommending] = useState(false);

  const [actualQuantity, setActualQuantity] = useState<string>("");
  const [isRecording, setIsRecording] = useState(false);

  const [errorMsg, setErrorMsg] = useState<string>("");
  const [successMsg, setSuccessMsg] = useState<string>("");

  const clearMessages = () => {
    setErrorMsg("");
    setSuccessMsg("");
  };

  const handleGenerateForecast = async () => {
    clearMessages();
    setIsGenerating(true);
    setForecast(null);
    setHistoricalData(null);
    setRecommendation(null);
    try {
      const res = await fetch(`${API}/forecast/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          center_id: centerId,
          meal_id: mealId,
          target_date: date,
        }),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setForecast(data);

      const histRes = await fetch(`${API}/forecast/history/${centerId}/${mealId}`);
      if (histRes.ok) {
        const histData = await histRes.json();
        setHistoricalData(histData);
      }
    } catch (err: any) {
      setErrorMsg("Failed to generate forecast: " + err.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRecommend = async (selectedPolicy: string) => {
    clearMessages();
    setPolicy(selectedPolicy);
    setIsRecommending(true);
    try {
      const res = await fetch(`${API}/production/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          center_id: centerId,
          meal_id: mealId,
          date: date,
          policy: selectedPolicy,
        }),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setRecommendation(data);
      setActualQuantity(data.recommended_quantity.toString());
    } catch (err: any) {
      setErrorMsg("Failed to fetch recommendation: " + err.message);
    } finally {
      setIsRecommending(false);
    }
  };

  const handleRecord = async () => {
    if (!actualQuantity) return;
    clearMessages();
    setIsRecording(true);
    try {
      const res = await fetch(`${API}/production/record`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          center_id: centerId,
          meal_id: mealId,
          date: date,
          actual_quantity: parseInt(actualQuantity, 10),
        }),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `HTTP ${res.status}`);
      }
      setSuccessMsg("Production recorded successfully.");
    } catch (err: any) {
      setErrorMsg("Failed to record production: " + err.message);
    } finally {
      setIsRecording(false);
    }
  };

  return (
    <div>
      {/* 1. Header */}
      <h1 style={{ fontSize: 28, margin: "0 0 4px", color: "var(--text-h, #f3f4f6)" }}>
        Forecast &amp; Production
      </h1>
      <p style={{ color: "var(--text, #9ca3af)", fontSize: 16, marginBottom: 24 }}>
        Demand Intelligence â†’ Production Decision
      </p>

      {/* Messaging */}
      {errorMsg && (
        <div style={{ padding: 12, background: "rgba(239,68,68,0.15)", color: "#ef4444", borderRadius: 6, marginBottom: 16 }}>
          {errorMsg}
        </div>
      )}
      {successMsg && (
        <div style={{ padding: 12, background: "rgba(34,197,94,0.15)", color: "#22c55e", borderRadius: 6, marginBottom: 16 }}>
          {successMsg}
        </div>
      )}

      {/* 2. Input / Scenario Panel */}
      <div style={card}>
        <h2 style={{ fontSize: 17, margin: "0 0 14px", color: "var(--text-h)" }}>Scenario Parameters</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
          <div>
            <label style={{ display: "block", fontSize: 13, marginBottom: 4 }}>Center ID</label>
            <select style={inputStyle} value={centerId} onChange={(e) => setCenterId(Number(e.target.value))}>
              <option value={1}>Center 1</option>
              <option value={2}>Center 2</option>
              <option value={3}>Center 3</option>
            </select>
          </div>
          <div>
            <label style={{ display: "block", fontSize: 13, marginBottom: 4 }}>Meal ID</label>
            <select style={inputStyle} value={mealId} onChange={(e) => setMealId(Number(e.target.value))}>
              <option value={1}>Meal 1</option>
              <option value={2}>Meal 2</option>
              <option value={3}>Meal 3</option>
              <option value={4}>Meal 4</option>
            </select>
          </div>
          <div>
            <label style={{ display: "block", fontSize: 13, marginBottom: 4 }}>Target Date</label>
            <input type="date" style={inputStyle} value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div style={{ marginTop: 18 }}>
            <button style={btnStyle} onClick={handleGenerateForecast} disabled={isGenerating}>
              {isGenerating ? "Generating..." : "Generate AI Forecast"}
            </button>
          </div>
        </div>
      </div>

      {/* 3. Demand Forecast Card */}
      {forecast && (
        <div style={card}>
          {historicalData && historicalData.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 14, margin: "0 0 12px", color: "var(--text-h)", textTransform: "uppercase", letterSpacing: 0.5 }}>
                Historical Demand Context
              </h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, background: "rgba(0,0,0,0.2)", padding: 16, borderRadius: 8 }}>
                {historicalData.map((obs) => (
                  <div key={obs.week} style={{ textAlign: "center", background: "#ffffff", padding: "10px 6px", borderRadius: 6, border: "1px solid #e5e7eb", boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}>
                    <div style={{ fontSize: 11, color: "#6b7280", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 }}>Wk {obs.week}</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: "#111827" }}>{obs.num_orders}</div>
                  </div>
                ))}
              </div>
              <div style={{ textAlign: "center", marginTop: 16, color: "var(--text)", fontSize: 20 }}>
                &darr;
              </div>
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <h2 style={{ fontSize: 14, margin: "0 0 4px", color: "var(--text-h)", textTransform: "uppercase", letterSpacing: 0.5 }}>
                AI Demand Forecast
              </h2>
              <p style={{ fontSize: 13, color: "var(--text)", margin: "0 0 16px" }}>
                Empirical forecast range based on the validated prototype.
              </p>
            </div>
            <div style={tag("gray")}>
              {forecast.model_version || "HistGradientBoosting"}
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr 1fr", gap: 12, background: "rgba(0,0,0,0.2)", padding: 24, borderRadius: 8, alignItems: "center" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 12, color: "var(--text)" }}>Lower Bound</div>
              <div style={{ fontSize: 20, color: "#9ca3af" }}>{forecast.confidence_lower?.toFixed(1) ?? "-"}</div>
            </div>
            <div style={{ textAlign: "center", borderLeft: "1px solid #374151", borderRight: "1px solid #374151" }}>
              <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 600, textTransform: "uppercase", marginBottom: 4, letterSpacing: 1 }}>Predicted Demand</div>
              <div style={{ fontSize: 56, color: "#3b82f6", fontWeight: 800, textShadow: "0 0 20px rgba(59,130,246,0.4)" }}>{forecast.predicted_demand.toFixed(1)}</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 12, color: "var(--text)" }}>Upper Bound</div>
              <div style={{ fontSize: 20, color: "#9ca3af" }}>{forecast.confidence_upper?.toFixed(1) ?? "-"}</div>
            </div>
          </div>
          <div style={{ marginTop: 12, fontSize: 13, color: "var(--text)", borderLeft: "3px solid #3b82f6", paddingLeft: 12 }}>
            <strong>16.9% lower demand-forecast MAE vs historical-mean baseline</strong>
          </div>

          <div style={{ textAlign: "center", marginTop: 24, color: "var(--text)", fontSize: 20 }}>
            &darr;
          </div>
        </div>
      )}

      {/* 4. Production Policy Section */}
      {forecast && (
        <div style={card}>
          <h2 style={{ fontSize: 17, margin: "0 0 4px", color: "var(--text-h)" }}>Production Policy Trade-off</h2>
          <p style={{ fontSize: 14, color: "var(--text)", margin: "0 0 16px" }}>
            Select a service-level policy. Lower policies reduce overproduction risk but increase shortage risk.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 28 }}>
            {["p50", "p70", "p80", "p90", "p95", "historical_mean"].map((pol) => (
              <button
                key={pol}
                onClick={() => handleRecommend(pol)}
                disabled={isRecommending}
                style={{
                  ...btnStyle,
                  background: policy === pol ? "#10b981" : "transparent",
                  border: policy === pol ? "2px solid #10b981" : "1px solid #374151",
                  color: policy === pol ? "#fff" : "#d1d5db",
                  padding: "10px 20px",
                  borderRadius: 8,
                  fontSize: 15,
                  fontWeight: policy === pol ? 700 : 500,
                  boxShadow: policy === pol ? "0 0 12px rgba(16, 185, 129, 0.4)" : "none",
                  transition: "all 0.2s"
                }}
              >
                {pol.toUpperCase().replace("_", " ")}
              </button>
            ))}
          </div>

          {recommendation && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
              <div style={{ background: "rgba(16, 185, 129, 0.1)", border: "1px solid #10b981", padding: 24, borderRadius: 8, textAlign: "center" }}>
                <div style={{ fontSize: 13, color: "#10b981", marginBottom: 8, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>Recommended Production</div>
                <div style={{ fontSize: 48, fontWeight: 800, color: "#10b981", textShadow: "0 0 15px rgba(16,185,129,0.3)" }}>
                  {recommendation.recommended_quantity} <span style={{ fontSize: 16, fontWeight: 500, color: "var(--text)" }}>meals</span>
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12, justifyContent: "center" }}>
                <div>
                  <span style={tag("green")}>Expected Surplus: {recommendation.expected_surplus.toFixed(1)} meals</span>
                </div>
                <div>
                  <span style={tag("red")}>Expected Shortage: {recommendation.expected_shortage.toFixed(1)} meals</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 6. Decision Explanation */}
      {recommendation && (
        <div style={card}>
          <h2 style={{ fontSize: 16, margin: "0 0 8px", color: "var(--text-h)" }}>Why this recommendation?</h2>
          <p style={{ fontSize: 14, color: "var(--text)", margin: 0, lineHeight: 1.5 }}>
            FoodWise AI converts the demand forecast into a production recommendation. Different policies represent different trade-offs between surplus and shortage.
          </p>
        </div>
      )}

      {/* 7. Record Production */}
      {recommendation && (
        <div style={card}>
          <h2 style={{ fontSize: 17, margin: "0 0 14px", color: "var(--text-h)" }}>Record Production</h2>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <div>
              <label style={{ display: "block", fontSize: 13, marginBottom: 4 }}>Actual Production Quantity</label>
              <input
                type="number"
                style={inputStyle}
                value={actualQuantity}
                onChange={(e) => setActualQuantity(e.target.value)}
              />
            </div>
            <div style={{ marginTop: 18 }}>
              <button
                style={{ ...btnStyle, background: "#10b981" }}
                onClick={handleRecord}
                disabled={isRecording || !actualQuantity}
              >
                {isRecording ? "Recording..." : "Record Production"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ForecastProduction;

