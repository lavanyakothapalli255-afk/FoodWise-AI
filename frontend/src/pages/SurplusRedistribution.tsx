import { useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

/* ---- Inline styles matching existing pages ---- */
const card: React.CSSProperties = {
  background: "var(--code-bg, #1f2028)",
  border: "1px solid var(--border, #2e303a)",
  borderRadius: 10,
  padding: "20px 24px",
  marginBottom: 18,
  textAlign: "left",
};

const label: React.CSSProperties = {
  display: "block",
  fontSize: 13,
  color: "var(--text, #9ca3af)",
  marginBottom: 4,
};

const input: React.CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  borderRadius: 6,
  border: "1px solid var(--border, #2e303a)",
  background: "var(--bg, #16171d)",
  color: "var(--text-h, #f3f4f6)",
  fontSize: 14,
  boxSizing: "border-box",
};

const btn = (accent = false): React.CSSProperties => ({
  padding: "9px 20px",
  borderRadius: 6,
  border: accent ? "none" : "1px solid var(--border, #2e303a)",
  background: accent
    ? "var(--accent, #c084fc)"
    : "var(--code-bg, #1f2028)",
  color: accent ? "#fff" : "var(--text-h, #f3f4f6)",
  fontSize: 14,
  fontWeight: 600,
  cursor: "pointer",
  transition: "opacity 0.2s",
});

const tag = (color: string): React.CSSProperties => ({
  display: "inline-block",
  padding: "3px 10px",
  borderRadius: 20,
  fontSize: 12,
  fontWeight: 600,
  background: color === "green"
    ? "rgba(34,197,94,0.15)"
    : color === "amber"
      ? "rgba(245,158,11,0.15)"
      : "rgba(156,163,175,0.15)",
  color: color === "green"
    ? "#22c55e"
    : color === "amber"
      ? "#f59e0b"
      : "#9ca3af",
});

/* ---- Types ---- */
interface SurplusResult {
  surplus_quantity: number;
  shortage_quantity: number;
  actual_production: number;
  actual_consumption: number;
  status: string;
  eligibility_advisory: string;
  usable_time_remaining_min: number | null;
}

interface Allocation {
  recipient_id: number;
  recipient_name: string;
  capacity: number;
  is_available: boolean;
  is_time_feasible: boolean;
  distance_km: number;
  transit_time_min: number;
  usable_time_remaining_min: number;
  priority: number;
  allocated_quantity: number;
  is_feasible: boolean;
}

interface OptimizeResult {
  surplus_quantity: number;
  total_allocated: number;
  unallocated_surplus: number;
  total_transport_distance: number;
  allocation_percentage: number;
  solver_status: string;
  constraint_violations: number;
  allocations: Allocation[];
  plan_ids: number[];
  authorization_status: string;
}

interface RecipientOverride {
  recipient_id: number;
  distance_km: number;
  transit_time_min: number;
  usable_time_remaining_min: number;
  priority: number;
}

function SurplusRedistribution() {
  /* Surplus detection state */
  const [centerId, setCenterId] = useState("1");
  const [mealId, setMealId] = useState("1");
  const [dateVal, setDateVal] = useState("2026-09-13");
  const [consumption, setConsumption] = useState("");
  const [surplus, setSurplus] = useState<SurplusResult | null>(null);
  const [surplusErr, setSurplusErr] = useState("");

  /* Redistribution state */
  const [overrides, setOverrides] = useState<RecipientOverride[]>([
    { recipient_id: 2, distance_km: 5, transit_time_min: 15, usable_time_remaining_min: 120, priority: 3 },
    { recipient_id: 3, distance_km: 10, transit_time_min: 30, usable_time_remaining_min: 120, priority: 1 },
    { recipient_id: 4, distance_km: 15, transit_time_min: 45, usable_time_remaining_min: 120, priority: 4 },
    { recipient_id: 5, distance_km: 5, transit_time_min: 18, usable_time_remaining_min: 120, priority: 1 },
  ]);
  const [optResult, setOptResult] = useState<OptimizeResult | null>(null);
  const [optErr, setOptErr] = useState("");

  /* Authorization state */
  const [authBy, setAuthBy] = useState("");
  const [authResult, setAuthResult] = useState<string | null>(null);
  const [authErr, setAuthErr] = useState("");

  /* ---- Handlers ---- */
  const detectSurplus = async () => {
    setSurplusErr("");
    setSurplus(null);
    setOptResult(null);
    setAuthResult(null);
    try {
      const body: Record<string, unknown> = {
        center_id: Number(centerId),
        meal_id: Number(mealId),
        date: dateVal,
      };
      if (consumption.trim()) body.actual_consumption = Number(consumption);
      const res = await fetch(`${API}/surplus/detect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      setSurplus(await res.json());
    } catch (e: unknown) {
      setSurplusErr(e instanceof Error ? e.message : String(e));
    }
  };

  const runOptimize = async () => {
    if (!surplus || surplus.surplus_quantity <= 0) return;
    setOptErr("");
    setOptResult(null);
    setAuthResult(null);
    try {
      const res = await fetch(`${API}/redistribution/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          center_id: Number(centerId),
          meal_id: Number(mealId),
          date: dateVal,
          surplus_quantity: surplus.surplus_quantity,
          recipient_overrides: overrides,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setOptResult(await res.json());
    } catch (e: unknown) {
      setOptErr(e instanceof Error ? e.message : String(e));
    }
  };

  const authorize = async (planId: number) => {
    if (!authBy.trim()) { setAuthErr("Operator name is required."); return; }
    setAuthErr("");
    setAuthResult(null);
    try {
      const res = await fetch(`${API}/redistribution/authorize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: planId, authorized_by: authBy }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setAuthResult(`Plan #${data.id} authorized by ${data.authorized_by} â€” status: ${data.status}`);
    } catch (e: unknown) {
      setAuthErr(e instanceof Error ? e.message : String(e));
    }
  };

  const updateOverride = (idx: number, field: keyof RecipientOverride, val: string) => {
    setOverrides(prev => prev.map((o, i) => i === idx ? { ...o, [field]: Number(val) } : o));
  };

  const addOverride = () => {
    setOverrides(prev => [...prev, { recipient_id: 0, distance_km: 0, transit_time_min: 0, usable_time_remaining_min: 120, priority: 1 }]);
  };

  const removeOverride = (idx: number) => {
    setOverrides(prev => prev.filter((_, i) => i !== idx));
  };

  return (
    <div>
      <h1 style={{ fontSize: 28, margin: "0 0 12px" }}>
        Surplus &amp; Redistribution
      </h1>
      <p style={{ color: "var(--text, #9ca3af)", marginBottom: 24, fontSize: 14 }}>
        Detect â†’ Decide â†’ Rescue: detect surplus, optimize redistribution, authorize the plan.
      </p>

      {/* ---- Step 1: Surplus Detection ---- */}
      <div style={card}>
        <h2 style={{ fontSize: 17, margin: "0 0 14px", color: "var(--text-h, #f3f4f6)" }}>
          â‘  Detect Surplus
        </h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12, marginBottom: 14 }}>
          <div><label style={label}>Center ID</label><input style={input} value={centerId} onChange={e => setCenterId(e.target.value)} /></div>
          <div><label style={label}>Meal ID</label><input style={input} value={mealId} onChange={e => setMealId(e.target.value)} /></div>
          <div><label style={label}>Date</label><input style={input} type="date" value={dateVal} onChange={e => setDateVal(e.target.value)} /></div>
          <div><label style={label}>Actual Consumption (opt)</label><input style={input} placeholder="Leave blank for forecast" value={consumption} onChange={e => setConsumption(e.target.value)} /></div>
        </div>
        <button style={btn(true)} onClick={detectSurplus}>Detect Surplus</button>
        {surplusErr && <p style={{ color: "#ef4444", marginTop: 8, fontSize: 13 }}>{surplusErr}</p>}

        {surplus && (
          <div style={{ marginTop: 16, padding: 14, background: "var(--bg, #16171d)", borderRadius: 8, fontSize: 13 }}>
            <div style={{ marginBottom: 8 }}>
              <span style={tag(surplus.status === "surplus_detected" ? "green" : surplus.status === "no_surplus" ? "amber" : "gray")}>
                {surplus.status.replace(/_/g, " ").toUpperCase()}
              </span>
            </div>
            <div style={{ display: "flex", gap: 24, alignItems: "center", marginBottom: 12, marginTop: 12 }}>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 13, color: "var(--text)" }}>Production</div>
                <div style={{ fontSize: 20, color: "var(--text-h)", fontWeight: 600 }}>{surplus.actual_production}</div>
              </div>
              <div style={{ color: "var(--text)" }}>-</div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 13, color: "var(--text)" }}>Consumption</div>
                <div style={{ fontSize: 20, color: "var(--text-h)", fontWeight: 600 }}>{surplus.actual_consumption}</div>
              </div>
              <div style={{ color: "var(--text)" }}>=</div>
              <div style={{ textAlign: "center", padding: "8px 24px", background: surplus.surplus_quantity > 0 ? "rgba(34, 197, 94, 0.1)" : "transparent", borderRadius: 8, border: surplus.surplus_quantity > 0 ? "1px solid #22c55e" : "none" }}>
                <div style={{ fontSize: 13, color: surplus.surplus_quantity > 0 ? "#22c55e" : "var(--text)", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  {surplus.surplus_quantity > 0 ? "Meals Available For Redistribution" : "Surplus"}
                </div>
                <div style={{ fontSize: 36, color: surplus.surplus_quantity > 0 ? "#22c55e" : "var(--text-h)", fontWeight: 800 }}>
                  {surplus.surplus_quantity}
                </div>
              </div>
            </div>
            <p style={{ marginTop: 10, color: "var(--text)", lineHeight: 1.5, fontStyle: "italic" }}>
              {surplus.eligibility_advisory}
            </p>
          </div>
        )}
      </div>

      {/* ---- Step 2: Redistribution Optimization ---- */}
      {surplus && surplus.status === "surplus_detected" && (
        <div style={card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
            <h2 style={{ fontSize: 17, margin: 0, color: "var(--text-h, #f3f4f6)" }}>
              â‘¡ Optimize Redistribution
            </h2>
            <span style={tag("amber")}>Demo Scenario</span>
          </div>
          <p style={{ fontSize: 13, color: "var(--text)", marginBottom: 12 }}>
            <strong>Operational feasibility optimization:</strong> Pre-populated with validated Experiment 3 demo operational inputs. (Not live recipient data).
          </p>

          {/* Recipient overrides table */}
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginBottom: 10 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text)" }}>
                  <th style={{ padding: "6px 8px", textAlign: "left" }}>Recipient ID</th>
                  <th style={{ padding: "6px 8px", textAlign: "left" }}>Distance (km)</th>
                  <th style={{ padding: "6px 8px", textAlign: "left" }}>Transit (min)</th>
                  <th style={{ padding: "6px 8px", textAlign: "left" }}>Usable Time (min)</th>
                  <th style={{ padding: "6px 8px", textAlign: "left" }}>Priority</th>
                  <th style={{ padding: "6px 8px" }}></th>
                </tr>
              </thead>
              <tbody>
                {overrides.map((o, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: 4 }}><input style={{ ...input, width: 60 }} type="number" min={1} value={o.recipient_id} onChange={e => updateOverride(i, "recipient_id", e.target.value)} /></td>
                    <td style={{ padding: 4 }}><input style={{ ...input, width: 70 }} type="number" min={0} step={0.1} value={o.distance_km} onChange={e => updateOverride(i, "distance_km", e.target.value)} /></td>
                    <td style={{ padding: 4 }}><input style={{ ...input, width: 70 }} type="number" min={0} value={o.transit_time_min} onChange={e => updateOverride(i, "transit_time_min", e.target.value)} /></td>
                    <td style={{ padding: 4 }}><input style={{ ...input, width: 80 }} type="number" min={0} value={o.usable_time_remaining_min} onChange={e => updateOverride(i, "usable_time_remaining_min", e.target.value)} /></td>
                    <td style={{ padding: 4 }}><input style={{ ...input, width: 60 }} type="number" min={1} value={o.priority} onChange={e => updateOverride(i, "priority", e.target.value)} /></td>
                    <td style={{ padding: 4 }}><button style={{ ...btn(), padding: "4px 10px", fontSize: 12 }} onClick={() => removeOverride(i)}>âœ•</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
            <button style={btn()} onClick={addOverride}>+ Add Recipient</button>
            <button style={btn(true)} onClick={runOptimize}>Run Optimization</button>
          </div>
          {optErr && <p style={{ color: "#ef4444", fontSize: 13 }}>{optErr}</p>}

          {optResult && (
            <div style={{ marginTop: 14, padding: 14, background: "var(--bg, #16171d)", borderRadius: 8, fontSize: 13 }}>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
                <span style={tag("green")}>SOLVER: {optResult.solver_status.toUpperCase()}</span>
                <span style={{ fontSize: 13, color: "var(--text)", marginLeft: "auto" }}>
                  <strong>Distance:</strong> {optResult.total_transport_distance} meal-km | <strong>Coverage:</strong> {optResult.allocation_percentage}%
                </span>
              </div>
              <div style={{ display: "flex", gap: 16, marginBottom: 20, background: "rgba(0,0,0,0.2)", padding: 16, borderRadius: 8 }}>
                <div style={{ flex: 1, textAlign: "center" }}>
                  <div style={{ fontSize: 28, fontWeight: 700, color: "#f3f4f6" }}>{optResult.surplus_quantity}</div>
                  <div style={{ fontSize: 12, color: "var(--text)", textTransform: "uppercase", letterSpacing: 0.5, marginTop: 4 }}>Meals Available</div>
                </div>
                <div style={{ width: 1, background: "var(--border)" }}></div>
                <div style={{ flex: 1, textAlign: "center" }}>
                  <div style={{ fontSize: 28, fontWeight: 700, color: "#22c55e" }}>{optResult.total_allocated}</div>
                  <div style={{ fontSize: 12, color: "var(--text)", textTransform: "uppercase", letterSpacing: 0.5, marginTop: 4 }}>Allocated</div>
                </div>
                <div style={{ width: 1, background: "var(--border)" }}></div>
                <div style={{ flex: 1, textAlign: "center" }}>
                  <div style={{ fontSize: 28, fontWeight: 700, color: optResult.unallocated_surplus === 0 ? "#22c55e" : "#ef4444" }}>{optResult.unallocated_surplus}</div>
                  <div style={{ fontSize: 12, color: "var(--text)", textTransform: "uppercase", letterSpacing: 0.5, marginTop: 4 }}>Unallocated</div>
                </div>
                <div style={{ width: 1, background: "var(--border)" }}></div>
                <div style={{ flex: 1, textAlign: "center" }}>
                  <div style={{ fontSize: 28, fontWeight: 700, color: optResult.constraint_violations === 0 ? "#22c55e" : "#f59e0b" }}>{optResult.constraint_violations}</div>
                  <div style={{ fontSize: 12, color: "var(--text)", textTransform: "uppercase", letterSpacing: 0.5, marginTop: 4 }}>Hard Violations</div>
                </div>
              </div>

              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text)" }}>
                    <th style={{ padding: "6px 6px", textAlign: "left" }}>Recipient</th>
                    <th style={{ padding: "6px 6px", textAlign: "right" }}>Cap</th>
                    <th style={{ padding: "6px 6px", textAlign: "center" }}>Avail</th>
                    <th style={{ padding: "6px 6px", textAlign: "center" }}>Time OK</th>
                    <th style={{ padding: "6px 6px", textAlign: "right" }}>Dist</th>
                    <th style={{ padding: "6px 6px", textAlign: "right" }}>Pri</th>
                    <th style={{ padding: "6px 6px", textAlign: "right" }}>Alloc</th>
                  </tr>
                </thead>
                <tbody>
                  {optResult.allocations.map(a => (
                    <tr key={a.recipient_id} style={{ borderBottom: "1px solid var(--border)", opacity: a.is_feasible ? 1 : 0.5 }}>
                      <td style={{ padding: "5px 6px" }}>{a.recipient_name}</td>
                      <td style={{ padding: "5px 6px", textAlign: "right" }}>{a.capacity}</td>
                      <td style={{ padding: "5px 6px", textAlign: "center" }}>{a.is_available ? "âœ“" : "âœ—"}</td>
                      <td style={{ padding: "5px 6px", textAlign: "center" }}>{a.is_time_feasible ? "âœ“" : "âœ—"}</td>
                      <td style={{ padding: "5px 6px", textAlign: "right" }}>{a.distance_km}</td>
                      <td style={{ padding: "5px 6px", textAlign: "right" }}>{a.priority}</td>
                      <td style={{ padding: "5px 6px", textAlign: "right", fontWeight: 600, color: a.allocated_quantity > 0 ? "#22c55e" : "var(--text)" }}>{a.allocated_quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ---- Step 3: Authorization ---- */}
      {optResult && optResult.plan_ids.length > 0 && (
        <div style={card}>
          <h2 style={{ fontSize: 17, margin: "0 0 14px", color: "var(--text-h, #f3f4f6)" }}>
            â‘¢ Authorize Plan
          </h2>
          <p style={{ fontSize: 12, color: "var(--text)", marginBottom: 12 }}>
            Review the plan above then authorize. Food-safety eligibility check â€” human authorization required.
          </p>
          <div style={{ display: "flex", gap: 12, alignItems: "end" }}>
            <div style={{ flex: 1 }}>
              <label style={label}>Authorized By (operator name)</label>
              <input style={input} value={authBy} onChange={e => setAuthBy(e.target.value)} placeholder="Enter operator name" />
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {optResult.plan_ids.map(pid => (
                <button key={pid} style={btn(true)} onClick={() => authorize(pid)}>
                  Authorize Plan #{pid}
                </button>
              ))}
            </div>
          </div>
          {authErr && <p style={{ color: "#ef4444", marginTop: 8, fontSize: 13 }}>{authErr}</p>}
          {authResult && (
            <p style={{ marginTop: 10, color: "#22c55e", fontSize: 13, fontWeight: 600 }}>
              âœ“ {authResult}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default SurplusRedistribution;

