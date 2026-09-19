import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/forecast", label: "Forecast & Production" },
  { to: "/surplus", label: "Surplus & Redistribution" },
  { to: "/scenario", label: "What-If Simulator" },
];

function MainLayout() {
  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      {/* Sidebar */}
      <nav
        style={{
          width: 240,
          background: "var(--code-bg, #1f2028)",
          borderRight: "1px solid var(--border, #2e303a)",
          padding: "24px 16px",
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <h2
          style={{
            fontSize: 18,
            fontWeight: 600,
            color: "var(--text-h, #f3f4f6)",
            margin: "0 0 20px 0",
            letterSpacing: "-0.3px",
          }}
        >
          🍽️ FoodWise AI
        </h2>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            style={({ isActive }) => ({
              display: "block",
              padding: "10px 14px",
              borderRadius: 6,
              textDecoration: "none",
              fontSize: 15,
              color: isActive
                ? "var(--accent, #c084fc)"
                : "var(--text, #9ca3af)",
              background: isActive
                ? "var(--accent-bg, rgba(192,132,252,0.15))"
                : "transparent",
              fontWeight: isActive ? 600 : 400,
              transition: "all 0.2s",
            })}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Main content */}
      <main style={{ flex: 1, padding: "32px 40px", overflow: "auto" }}>
        <Outlet />
      </main>
    </div>
  );
}

export default MainLayout;
