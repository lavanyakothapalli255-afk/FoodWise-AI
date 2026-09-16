import { BrowserRouter, Route, Routes } from "react-router-dom";
import MainLayout from "./layout/MainLayout";
import Dashboard from "./pages/Dashboard";
import ForecastProduction from "./pages/ForecastProduction";
import SurplusRedistribution from "./pages/SurplusRedistribution";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/forecast" element={<ForecastProduction />} />
          <Route path="/surplus" element={<SurplusRedistribution />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
