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
  decision_mode?: string;
  expected_decision_cost?: number;
  surplus_penalty_per_meal?: number;
  shortage_penalty_per_meal?: number;
  explanation?: string;
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

  const [smartMode, setSmartMode] = useState<boolean>(false);
  const [surplusPenalty, setSurplusPenalty] = useState<string>("10");
  const [shortagePenalty, setShortagePenalty] = useState<string>("25");

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

  const handleRecommend = async (selectedPolicy: string, sPen?: number, shPen?: number) => {
    clearMessages();
    setPolicy(selectedPolicy);
    setIsRecommending(true);
    try {
      const payload: any = {
        center_id: centerId,
        meal_id: mealId,
        date: date,
        policy: selectedPolicy,
      };
      if (selectedPolicy === "smart" && sPen !== undefined && shPen !== undefined) {
        payload.surplus_penalty_per_meal = sPen;
        payload.shortage_penalty_per_meal = shPen;
      }

      const res = await fetch(`${API}/production/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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

  const handleSmartRecommend = () => {
    const s = parseFloat(surplusPenalty);
    const sh = parseFloat(shortagePenalty);
    if (isNaN(s) || isNaN(sh) || s < 0 || sh < 0 || (s === 0 && sh === 0)) {
      setErrorMsg("Please provide valid non-negative penalties (both cannot be zero).");
      return;
    }
    handleRecommend("smart", s, sh);
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
      <h1 style={{ fontSize: 32, margin: "0 0 8px", color: "var(--text-h, #f3f4f6)" }}>
        Forecast &amp; Production
      </h1>
      <p style={{ color: "var(--text, #9ca3af)", fontSize: 16, marginBottom: 24 }}>
        Forecast demand, choose a production policy, and record the outcome.
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
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
            <div>
              <h2 style={{ fontSize: 18, margin: "0 0 4px", color: "#3b82f6" }}>
                AI Demand Forecast
              </h2>
              <p style={{ fontSize: 14, color: "var(--text)", margin: 0 }}>
                Empirical forecast range based on the validated prototype.
              </p>
            </div>
            <div style={tag("blue")}>
              Model: {forecast.model_version || "HistGradientBoosting"}
            </div>
          </div>
          
          <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 24, alignItems: "stretch" }}>
            <div style={{ background: "rgba(59, 130, 246, 0.05)", border: "1px solid rgba(59, 130, 246, 0.2)", padding: 24, borderRadius: 8, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
              <div style={{ fontSize: 13, color: "#3b82f6", fontWeight: 700, textTransform: "uppercase", marginBottom: 8, letterSpacing: 1 }}>Predicted Demand</div>
              <div style={{ fontSize: 64, color: "#3b82f6", fontWeight: 800 }}>{forecast.predicted_demand.toFixed(1)}</div>
              <div style={{ fontSize: 14, color: "var(--text)", marginTop: 8 }}>meals</div>
            </div>
            
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ background: "rgba(0,0,0,0.1)", padding: 16, borderRadius: 8 }}>
                <div style={{ fontSize: 13, color: "var(--text)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>Forecast Range</div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ fontSize: 12, color: "var(--text)" }}>Lower Bound</div>
                    <div style={{ fontSize: 20, color: "var(--text-h)" }}>{forecast.confidence_lower?.toFixed(1) ?? "-"}</div>
                  </div>
                  <div style={{ color: "var(--text)", fontSize: 24 }}>↔</div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 12, color: "var(--text)" }}>Upper Bound</div>
                    <div style={{ fontSize: 20, color: "var(--text-h)" }}>{forecast.confidence_upper?.toFixed(1) ?? "-"}</div>
                  </div>
                </div>
              </div>
              
              <div style={{ background: "rgba(0,0,0,0.1)", padding: 16, borderRadius: 8 }}>
                <div style={{ fontSize: 13, color: "var(--text)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>Validation Metric</div>
                <div style={{ fontSize: 15, color: "var(--text-h)" }}>16.9% lower demand-forecast MAE vs historical-mean baseline</div>
              </div>
            </div>
          </div>

          {historicalData && historicalData.length > 0 && (
            <div style={{ marginTop: 24, borderTop: "1px solid var(--border)", paddingTop: 16 }}>
              <h3 style={{ fontSize: 13, color: "var(--text)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 12 }}>Recent Historical Demand</h3>
              <div style={{ display: "flex", gap: 12, overflowX: "auto", paddingBottom: 8 }}>
                {historicalData.map((obs) => (
                  <div key={obs.week} style={{ minWidth: 80, textAlign: "center", background: "rgba(0,0,0,0.05)", border: "1px solid var(--border)", padding: "8px", borderRadius: 6 }}>
                    <div style={{ fontSize: 11, color: "var(--text)", textTransform: "uppercase", marginBottom: 4 }}>Wk {obs.week}</div>
                    <div style={{ fontSize: 16, fontWeight: 600, color: "var(--text-h)" }}>{obs.num_orders}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 4. Production Policy Section */}
      {forecast && (
        <div style={card}>
          <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            <div>
              <h3 style={{ fontSize: 14, color: "var(--text)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
                A. Standard Service-Level Policies
              </h3>
              <p style={{ fontSize: 14, color: "var(--text)", margin: "0 0 16px" }}>
                Choose a service-level policy based on your tolerance for shortage versus surplus.
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
                {["p50", "p70", "p80", "p90", "p95", "historical_mean"].map((pol) => (
                  <button
                    key={pol}
                    onClick={() => { setSmartMode(false); handleRecommend(pol); }}
                    disabled={isRecommending}
                    style={{
                      ...btnStyle,
                      background: policy === pol && !smartMode ? "#10b981" : "transparent",
                      border: policy === pol && !smartMode ? "2px solid #10b981" : "1px solid var(--border)",
                      color: policy === pol && !smartMode ? "#fff" : "var(--text-h)",
                      padding: "10px 20px",
                      borderRadius: 8,
                      fontSize: 15,
                      fontWeight: policy === pol && !smartMode ? 700 : 500,
                      boxShadow: policy === pol && !smartMode ? "0 0 12px rgba(16, 185, 129, 0.4)" : "none",
                      transition: "all 0.2s"
                    }}
                  >
                    {pol.toUpperCase().replace("_", " ")}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <h3 style={{ fontSize: 14, color: "var(--text)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
                B. Adaptive Smart Decision Engine
              </h3>
              <div style={{ background: "rgba(139, 92, 246, 0.05)", border: "1px solid #8b5cf6", padding: 24, borderRadius: 8 }}>
                <div style={{ marginBottom: 20 }}>
                  <h4 style={{ fontSize: 18, margin: "0 0 8px", color: "#8b5cf6" }}>Adaptive Decision Engine</h4>
                  <p style={{ fontSize: 14, color: "var(--text)", margin: 0 }}>
                    Select how strongly the operation should prioritize avoiding surplus versus avoiding shortage.
                  </p>
                </div>
                
                <div style={{ display: "flex", gap: 20, alignItems: "flex-end", flexWrap: "wrap" }}>
                  <div style={{ flex: "1 1 250px" }}>
                    <label style={{ display: "block", fontSize: 13, marginBottom: 8, color: "var(--text-h)", fontWeight: 500 }}>
                      Surplus penalty / meal
                    </label>
                    <div style={{ fontSize: 12, color: "var(--text)", marginBottom: 8 }}>Configurable decision penalty — not measured financial cost</div>
                    <input type="number" style={{...inputStyle, width: "100%", boxSizing: "border-box", marginRight: 0, padding: "10px 14px"}} value={surplusPenalty} onChange={(e) => setSurplusPenalty(e.target.value)} min="0" step="0.1" />
                  </div>
                  <div style={{ flex: "1 1 250px" }}>
                    <label style={{ display: "block", fontSize: 13, marginBottom: 8, color: "var(--text-h)", fontWeight: 500 }}>
                      Shortage penalty / meal
                    </label>
                    <div style={{ fontSize: 12, color: "var(--text)", marginBottom: 8 }}>Configurable decision penalty — not measured financial cost</div>
                    <input type="number" style={{...inputStyle, width: "100%", boxSizing: "border-box", marginRight: 0, padding: "10px 14px"}} value={shortagePenalty} onChange={(e) => setShortagePenalty(e.target.value)} min="0" step="0.1" />
                  </div>
                </div>
                <div style={{ marginTop: 24 }}>
                  <button 
                    style={{ ...btnStyle, background: "#8b5cf6", padding: "12px 24px", fontSize: 16, fontWeight: 600, width: "100%", borderRadius: 8 }}
                    onClick={() => { setSmartMode(true); handleSmartRecommend(); }}
                    disabled={isRecommending || !surplusPenalty || !shortagePenalty || (parseFloat(surplusPenalty) === 0 && parseFloat(shortagePenalty) === 0) || parseFloat(surplusPenalty) < 0 || parseFloat(shortagePenalty) < 0}
                  >
                    {isRecommending && smartMode ? "Calculating..." : "Calculate Smart Decision"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 5. Smart Result / Decision Result */}
      {recommendation && (
        <div style={{ ...card, border: recommendation.decision_mode === "smart_cost_minimization" ? "2px solid #8b5cf6" : "2px solid #10b981" }}>
          <h2 style={{ fontSize: 18, margin: "0 0 16px", color: recommendation.decision_mode === "smart_cost_minimization" ? "#8b5cf6" : "#10b981" }}>
            {recommendation.decision_mode === "smart_cost_minimization" ? "Adaptive Smart Decision Result" : "Standard Policy Result"}
          </h2>
          
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginBottom: 24 }}>
            <div style={{ background: "rgba(0,0,0,0.1)", padding: 24, borderRadius: 8, textAlign: "center", display: "flex", flexDirection: "column", justifyContent: "center" }}>
              <div style={{ fontSize: 13, color: "var(--text)", marginBottom: 8, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>
                Recommended Production
              </div>
              <div style={{ fontSize: 56, fontWeight: 800, color: "var(--text-h)" }}>
                {recommendation.recommended_quantity} <span style={{ fontSize: 16, fontWeight: 500, color: "var(--text)" }}>meals</span>
              </div>
              <div style={{ fontSize: 13, color: "var(--text)", marginTop: 8 }}>
                {recommendation.decision_mode === "smart_cost_minimization" ? "Recommended under these decision priorities." : "Selected via static service-level policy."}
              </div>
            </div>
            
            <div style={{ display: "flex", flexDirection: "column", gap: 16, justifyContent: "center" }}>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "12px", background: "rgba(0,0,0,0.1)", borderRadius: 8 }}>
                <span style={{ fontSize: 14, color: "var(--text)" }}>Forecast Demand</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-h)" }}>{recommendation.point_forecast?.toFixed(1) || "-"} meals</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "12px", background: "rgba(34,197,94,0.05)", borderLeft: "4px solid #22c55e", borderRadius: 8 }}>
                <span style={{ fontSize: 14, color: "var(--text)" }}>Expected Surplus</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: "#22c55e" }}>{recommendation.expected_surplus.toFixed(1)} meals</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "12px", background: "rgba(239,68,68,0.05)", borderLeft: "4px solid #ef4444", borderRadius: 8 }}>
                <span style={{ fontSize: 14, color: "var(--text)" }}>Expected Shortage</span>
                <span style={{ fontSize: 14, fontWeight: 600, color: "#ef4444" }}>{recommendation.expected_shortage.toFixed(1)} meals</span>
              </div>
              {recommendation.expected_decision_cost !== undefined && recommendation.expected_decision_cost !== null && (
                <div style={{ display: "flex", justifyContent: "space-between", padding: "12px", background: "rgba(139,92,246,0.05)", borderLeft: "4px solid #8b5cf6", borderRadius: 8 }}>
                  <span style={{ fontSize: 14, color: "var(--text)" }}>Expected Decision Penalty</span>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "#8b5cf6" }}>{recommendation.expected_decision_cost.toFixed(2)}</span>
                </div>
              )}
            </div>
          </div>
          
          <div style={{ background: "var(--bg)", border: "1px solid var(--border)", padding: 16, borderRadius: 8 }}>
            <h3 style={{ fontSize: 14, color: "var(--text-h)", margin: "0 0 8px" }}>Why this recommendation?</h3>
            <p style={{ fontSize: 14, color: "var(--text)", margin: 0, lineHeight: 1.5 }}>
              {recommendation.explanation || "FoodWise AI converts the demand forecast into a production recommendation. Different policies represent different trade-offs between surplus and shortage."}
            </p>
          </div>
        </div>
      )}

      {/* 7. Record Production */}
      {recommendation && (
        <div>
          <div style={{ textAlign: "center", fontSize: 24, color: "var(--border)", margin: "8px 0 24px" }}>
            ↓
          </div>
          <div style={{ ...card, borderTop: "4px solid #3b82f6" }}>
            <h2 style={{ fontSize: 18, margin: "0 0 16px", color: "var(--text-h)" }}>Operational Handoff: Record Production</h2>
            <div style={{ display: "flex", gap: 16, alignItems: "flex-end" }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: "block", fontSize: 14, marginBottom: 8, color: "var(--text)", fontWeight: 500 }}>Actual Production Quantity</label>
                <input
                  type="number"
                  style={{ ...inputStyle, width: "100%", padding: "12px 16px", fontSize: 16 }}
                  value={actualQuantity}
                  onChange={(e) => setActualQuantity(e.target.value)}
                />
              </div>
              <div>
                <button
                  style={{ ...btnStyle, background: "#3b82f6", padding: "13px 24px", fontSize: 16, fontWeight: 600 }}
                  onClick={handleRecord}
                  disabled={isRecording || !actualQuantity}
                >
                  {isRecording ? "Recording..." : "Record Production"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ForecastProduction;

