import { useState, useEffect } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

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
  transition: "all 0.2s",
};

const checkboxStyle: React.CSSProperties = {
  cursor: "pointer",
  width: 16,
  height: 16,
};

interface Recipient {
  id: number;
  name: string;
  is_active: boolean;
}

function ScenarioSimulator() {
  const [centerId, setCenterId] = useState<number>(1);
  const [mealId, setMealId] = useState<number>(1);
  const [date, setDate] = useState<string>(new Date().toISOString().split("T")[0]);

  // What-If Controls
  const [demandAdjustment, setDemandAdjustment] = useState<number>(1.0); // 1.0 = 0%
  const [surplusPenalty, setSurplusPenalty] = useState<string>("10");
  const [shortagePenalty, setShortagePenalty] = useState<string>("25");

  const [recipients, setRecipients] = useState<Recipient[]>([]);
  const [recipientOverrides, setRecipientOverrides] = useState<Record<number, boolean>>({});

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [simulationResult, setSimulationResult] = useState<any>(null);

  // Fetch recipients on mount
  useEffect(() => {
    const fetchRecipients = async () => {
      try {
        const res = await fetch(`${API}/recipients`);
        if (res.ok) {
          const data = await res.json();
          setRecipients(data);
          const initialOverrides: Record<number, boolean> = {};
          data.forEach((r: Recipient) => {
            initialOverrides[r.id] = true;
          });
          setRecipientOverrides(initialOverrides);
        }
      } catch (err) {
        console.error("Failed to load recipients", err);
      }
    };
    fetchRecipients();
  }, []);

  const handleReset = () => {
    setCenterId(1);
    setMealId(1);
    setDate(new Date().toISOString().split("T")[0]);
    setDemandAdjustment(1.0);
    setSurplusPenalty("10");
    setShortagePenalty("25");
    const initialOverrides: Record<number, boolean> = {};
    recipients.forEach((r: Recipient) => {
      initialOverrides[r.id] = true;
    });
    setRecipientOverrides(initialOverrides);
    setSimulationResult(null);
    setErrorMsg("");
  };

  const handleRunSimulation = async () => {
    setErrorMsg("");
    setIsLoading(true);
    setSimulationResult(null);

    const s = parseFloat(surplusPenalty);
    const sh = parseFloat(shortagePenalty);
    if (isNaN(s) || isNaN(sh) || s < 0 || sh < 0 || (s === 0 && sh === 0)) {
      setErrorMsg("Please provide valid non-negative penalties (both cannot be zero).");
      setIsLoading(false);
      return;
    }

    const overrides = Object.keys(recipientOverrides).map((id) => ({
      recipient_id: parseInt(id, 10),
      is_available: recipientOverrides[parseInt(id, 10)],
    }));

    try {
      const payload = {
        center_id: centerId,
        meal_id: mealId,
        target_date: date,
        demand_multiplier: demandAdjustment,
        surplus_penalty_per_meal: s,
        shortage_penalty_per_meal: sh,
        recipient_availability_overrides: overrides,
      };

      const res = await fetch(`${API}/scenario/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setSimulationResult(data);
    } catch (err: any) {
      setErrorMsg("Failed to run simulation: " + err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleRecipient = (id: number) => {
    setRecipientOverrides((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const adjustmentOptions = [
    { label: "-20%", value: 0.8 },
    { label: "-10%", value: 0.9 },
    { label: "0%", value: 1.0 },
    { label: "+10%", value: 1.1 },
    { label: "+20%", value: 1.2 },
  ];

  return (
    <div>
      {/* 1. Header */}
      <h1 style={{ fontSize: 32, margin: "0 0 8px", color: "var(--text-h, #f3f4f6)" }}>
        What-If Decision Simulator
      </h1>
      <p style={{ color: "var(--text, #9ca3af)", fontSize: 16, marginBottom: 8 }}>
        Explore how changing demand, decision priorities, or recipient availability affects operational decisions.
      </p>
      <div style={{ fontSize: 13, color: "#d97706", background: "rgba(217, 119, 6, 0.1)", padding: "8px 12px", borderRadius: 6, display: "inline-block", marginBottom: 24, border: "1px solid rgba(217,119,6,0.2)" }}>
        Scenario results are simulations, not measured food waste or live operational outcomes.
      </div>

      {errorMsg && (
        <div style={{ padding: 12, background: "rgba(239,68,68,0.15)", color: "#ef4444", borderRadius: 6, marginBottom: 16 }}>
          {errorMsg}
        </div>
      )}

      {/* 2. BASELINE DEFINITION */}
      <div style={card}>
        <h2 style={{ fontSize: 17, margin: "0 0 14px", color: "var(--text-h)" }}>Baseline Parameters</h2>
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
        </div>
      </div>

      <div style={{ textAlign: "center", fontSize: 24, color: "var(--border)", margin: "8px 0 16px" }}>
        ↓
      </div>

      {/* 3. WHAT-IF CONTROLS */}
      <div style={{ ...card, border: "1px solid #d97706" }}>
        <h2 style={{ fontSize: 18, margin: "0 0 20px", color: "#d97706" }}>What-If Assumptions</h2>
        
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {/* A. Demand Scenario */}
          <div>
            <h3 style={{ fontSize: 14, color: "var(--text)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
              A. Demand adjustment
            </h3>
            <p style={{ fontSize: 13, color: "var(--text)", marginBottom: 12 }}>
              Adjust expected demand. This is a scenario assumption, not an AI forecast.
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              {adjustmentOptions.map((opt) => (
                <button
                  key={opt.label}
                  onClick={() => setDemandAdjustment(opt.value)}
                  style={{
                    ...btnStyle,
                    background: demandAdjustment === opt.value ? "#d97706" : "transparent",
                    color: demandAdjustment === opt.value ? "#fff" : "var(--text-h)",
                    border: demandAdjustment === opt.value ? "none" : "1px solid var(--border)",
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* B. Decision Priorities */}
          <div>
            <h3 style={{ fontSize: 14, color: "var(--text)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
              B. Decision Priorities
            </h3>
            <div style={{ background: "rgba(139, 92, 246, 0.05)", border: "1px solid #8b5cf6", padding: 16, borderRadius: 8 }}>
              <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
                <div style={{ flex: "1 1 250px" }}>
                  <label style={{ display: "block", fontSize: 13, marginBottom: 4, color: "var(--text-h)", fontWeight: 500 }}>
                    Surplus penalty / meal
                  </label>
                  <div style={{ fontSize: 12, color: "var(--text)", marginBottom: 8 }}>Configurable decision penalty — not measured financial cost</div>
                  <input type="number" style={{...inputStyle, width: "100%", boxSizing: "border-box"}} value={surplusPenalty} onChange={(e) => setSurplusPenalty(e.target.value)} min="0" step="0.1" />
                </div>
                <div style={{ flex: "1 1 250px" }}>
                  <label style={{ display: "block", fontSize: 13, marginBottom: 4, color: "var(--text-h)", fontWeight: 500 }}>
                    Shortage penalty / meal
                  </label>
                  <div style={{ fontSize: 12, color: "var(--text)", marginBottom: 8 }}>Configurable decision penalty — not measured financial cost</div>
                  <input type="number" style={{...inputStyle, width: "100%", boxSizing: "border-box"}} value={shortagePenalty} onChange={(e) => setShortagePenalty(e.target.value)} min="0" step="0.1" />
                </div>
              </div>
            </div>
          </div>

          {/* C. Recipient Availability */}
          <div>
            <h3 style={{ fontSize: 14, color: "var(--text)", textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
              C. Recipient Availability
            </h3>
            <p style={{ fontSize: 13, color: "var(--text)", marginBottom: 12 }}>
              Availability changes apply only to this simulation.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
              {recipients.map((r) => (
                <label key={r.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: 12, background: "rgba(0,0,0,0.2)", borderRadius: 6, border: "1px solid var(--border)" }}>
                  <input
                    type="checkbox"
                    checked={recipientOverrides[r.id] ?? true}
                    onChange={() => toggleRecipient(r.id)}
                    style={checkboxStyle}
                  />
                  <span style={{ fontSize: 14, color: recipientOverrides[r.id] ? "var(--text-h)" : "var(--text)", textDecoration: recipientOverrides[r.id] ? "none" : "line-through" }}>
                    {r.name}
                  </span>
                </label>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div style={{ textAlign: "center", fontSize: 24, color: "var(--border)", margin: "8px 0 16px" }}>
        ↓
      </div>

      {/* 4. RUN BUTTON */}
      <div style={{ display: "flex", gap: 16 }}>
        <button
          style={{ ...btnStyle, background: "#d97706", padding: "12px 24px", fontSize: 16, fontWeight: 600, flex: 1 }}
          onClick={handleRunSimulation}
          disabled={isLoading}
        >
          {isLoading ? "Running..." : "Run What-If Scenario"}
        </button>
        <button
          style={{ ...btnStyle, background: "transparent", border: "1px solid var(--border)", color: "var(--text-h)", padding: "12px 24px" }}
          onClick={handleReset}
        >
          Reset Scenario
        </button>
      </div>

      {simulationResult && (
        <div style={{ marginTop: 32 }}>
          <div style={{ textAlign: "center", fontSize: 24, color: "var(--border)", margin: "8px 0 16px" }}>
            ↓
          </div>
          
          {/* 5. RESULT COMPARISON */}
          <div style={{ ...card, border: "2px solid #3b82f6" }}>
            <h2 style={{ fontSize: 20, margin: "0 0 20px", color: "#3b82f6" }}>Scenario Result</h2>
            
            <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr", gap: 16, marginBottom: 24 }}>
              <div style={{ fontWeight: 600, color: "var(--text)", textTransform: "uppercase", fontSize: 12, borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>Metric</div>
              <div style={{ fontWeight: 600, color: "var(--text-h)", textTransform: "uppercase", fontSize: 12, borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>Baseline</div>
              <div style={{ fontWeight: 600, color: "#d97706", textTransform: "uppercase", fontSize: 12, borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>What-If</div>
              
              <div style={{ color: "var(--text-h)" }}>ML Point Forecast</div>
              <div style={{ color: "var(--text)" }}>{simulationResult.baseline.point_forecast.toFixed(1)}</div>
              <div style={{ color: "#d97706", fontWeight: 500 }}>{simulationResult.scenario.point_forecast.toFixed(1)}</div>
              
              <div style={{ color: "var(--text-h)" }}>Simulated Mean Demand</div>
              <div style={{ color: "var(--text)" }}>{simulationResult.baseline.simulated_demand_mean.toFixed(1)}</div>
              <div style={{ color: "#d97706", fontWeight: 500 }}>{simulationResult.scenario.simulated_demand_mean.toFixed(1)}</div>
              
              <div style={{ color: "var(--text-h)" }}>Recommended Production</div>
              <div style={{ color: "var(--text)" }}>{simulationResult.baseline.recommended_quantity}</div>
              <div style={{ color: "#d97706", fontWeight: 500 }}>{simulationResult.scenario.recommended_quantity}</div>
              
              <div style={{ color: "var(--text-h)" }}>Expected Surplus</div>
              <div style={{ color: "var(--text)" }}>{simulationResult.baseline.expected_surplus.toFixed(1)}</div>
              <div style={{ color: "#d97706", fontWeight: 500 }}>{simulationResult.scenario.expected_surplus.toFixed(1)}</div>
              
              <div style={{ color: "var(--text-h)" }}>Expected Shortage</div>
              <div style={{ color: "var(--text)" }}>{simulationResult.baseline.expected_shortage.toFixed(1)}</div>
              <div style={{ color: "#d97706", fontWeight: 500 }}>{simulationResult.scenario.expected_shortage.toFixed(1)}</div>
              
              <div style={{ color: "var(--text-h)" }}>Decision Cost</div>
              <div style={{ color: "var(--text)" }}>{simulationResult.baseline.decision_cost.toFixed(2)}</div>
              <div style={{ color: "#d97706", fontWeight: 500 }}>{simulationResult.scenario.decision_cost.toFixed(2)}</div>
            </div>

            <div style={{ background: "rgba(0,0,0,0.15)", padding: 16, borderRadius: 8, marginBottom: 16 }}>
              <h4 style={{ fontSize: 13, color: "var(--text)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>Decision Change</h4>
              <div style={{ fontSize: 18, color: "var(--text-h)" }}>
                Production: {simulationResult.baseline.recommended_quantity} → {simulationResult.scenario.recommended_quantity} 
                <span style={{ color: simulationResult.changes.production_change > 0 ? "#10b981" : simulationResult.changes.production_change < 0 ? "#ef4444" : "var(--text)", marginLeft: 8 }}>
                  ({simulationResult.changes.production_change > 0 ? "+" : ""}{simulationResult.changes.production_change} meals)
                </span>
              </div>
            </div>

            <div style={{ background: "var(--bg)", border: "1px solid var(--border)", padding: 16, borderRadius: 8 }}>
              <h3 style={{ fontSize: 14, color: "var(--text-h)", margin: "0 0 8px" }}>Why did it change?</h3>
              <p style={{ fontSize: 14, color: "var(--text)", margin: 0, lineHeight: 1.5 }}>
                {simulationResult.explanation}
              </p>
            </div>
          </div>

          {/* 6. REDISTRIBUTION SCENARIO */}
          {simulationResult.redistribution && (
            <div>
              <div style={{ textAlign: "center", fontSize: 24, color: "var(--border)", margin: "8px 0 16px" }}>
                ↓
              </div>
              <div style={{ ...card, border: "2px solid #10b981" }}>
                <h2 style={{ fontSize: 20, margin: "0 0 4px", color: "#10b981" }}>Scenario Redistribution</h2>
                <div style={{ fontSize: 13, color: "var(--text)", marginBottom: 16 }}>Scenario simulation</div>
                
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 16, marginBottom: 24 }}>
                  <div style={{ background: "rgba(0,0,0,0.1)", padding: 16, borderRadius: 8, textAlign: "center" }}>
                    <div style={{ fontSize: 12, color: "var(--text)", textTransform: "uppercase", marginBottom: 8 }}>Meals Available</div>
                    <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text-h)" }}>{simulationResult.redistribution.surplus_quantity}</div>
                  </div>
                  <div style={{ background: "rgba(16,185,129,0.1)", padding: 16, borderRadius: 8, textAlign: "center", border: "1px solid rgba(16,185,129,0.2)" }}>
                    <div style={{ fontSize: 12, color: "#10b981", textTransform: "uppercase", marginBottom: 8 }}>Allocated</div>
                    <div style={{ fontSize: 24, fontWeight: 700, color: "#10b981" }}>{simulationResult.redistribution.total_allocated}</div>
                  </div>
                  <div style={{ background: "rgba(0,0,0,0.1)", padding: 16, borderRadius: 8, textAlign: "center" }}>
                    <div style={{ fontSize: 12, color: "var(--text)", textTransform: "uppercase", marginBottom: 8 }}>Unallocated</div>
                    <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text-h)" }}>{simulationResult.redistribution.unallocated_surplus}</div>
                  </div>
                  <div style={{ background: "rgba(0,0,0,0.1)", padding: 16, borderRadius: 8, textAlign: "center" }}>
                    <div style={{ fontSize: 12, color: "var(--text)", textTransform: "uppercase", marginBottom: 8 }}>Distance</div>
                    <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text-h)" }}>{simulationResult.redistribution.total_transport_distance.toFixed(0)} <span style={{fontSize:14, fontWeight:400}}>km</span></div>
                  </div>
                </div>

                <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: 8, overflow: "hidden", marginBottom: 16 }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                    <thead style={{ background: "rgba(255,255,255,0.05)", fontSize: 13, color: "var(--text)" }}>
                      <tr>
                        <th style={{ padding: "12px 16px", fontWeight: 500 }}>Recipient</th>
                        <th style={{ padding: "12px 16px", fontWeight: 500 }}>Capacity</th>
                        <th style={{ padding: "12px 16px", fontWeight: 500 }}>Scenario Allocation</th>
                      </tr>
                    </thead>
                    <tbody>
                      {simulationResult.redistribution.allocations.map((alloc: any, idx: number) => (
                        <tr key={idx} style={{ borderTop: "1px solid rgba(255,255,255,0.05)", opacity: alloc.is_available ? 1 : 0.4 }}>
                          <td style={{ padding: "12px 16px", color: "var(--text-h)", display: "flex", alignItems: "center", gap: 8 }}>
                            {alloc.recipient_name}
                            {!alloc.is_available && (
                              <span style={{ fontSize: 11, background: "rgba(239,68,68,0.15)", color: "#ef4444", padding: "2px 6px", borderRadius: 4 }}>
                                Unavailable in scenario
                              </span>
                            )}
                          </td>
                          <td style={{ padding: "12px 16px", color: "var(--text)" }}>{alloc.capacity}</td>
                          <td style={{ padding: "12px 16px", fontWeight: 600, color: alloc.allocated_quantity > 0 ? "#10b981" : "var(--text)" }}>
                            {alloc.allocated_quantity}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <p style={{ fontSize: 12, color: "var(--text)", fontStyle: "italic", margin: 0 }}>
                  Scenario routing currently uses prototype/demo operational inputs for distance, transit time, usable time, and priority.
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ScenarioSimulator;
