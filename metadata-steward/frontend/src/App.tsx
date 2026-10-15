import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ScrollRestoration from "./components/ScrollRestoration";
import Overview from "./pages/Overview";
import Findings from "./pages/Findings";
import FindingDetail from "./pages/FindingDetail";
import Recommendations from "./pages/Recommendations";
import Approvals from "./pages/Approvals";
import Agents from "./pages/Agents";
import GenerationLog from "./pages/GenerationLog";
import Changes from "./pages/Changes";
import Policies from "./pages/Policies";
import Activity from "./pages/Activity";
import Settings from "./pages/Settings";
import Catalog from "./pages/Catalog";
import Sources from "./pages/Sources";
import SourceDetail from "./pages/SourceDetail";
import Connections from "./pages/Connections";
import Knowledge from "./pages/Knowledge";
import Quality from "./pages/Quality";

export default function App() {
  return (
    <>
      <ScrollRestoration />
      <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Overview />} />
        <Route path="/findings" element={<Findings />} />
        <Route path="/findings/:id" element={<FindingDetail />} />
        <Route path="/recommendations" element={<Recommendations />} />
        <Route path="/approvals" element={<Approvals />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/history" element={<GenerationLog />} />
        <Route path="/changes" element={<Changes />} />
        <Route path="/policies" element={<Policies />} />
        <Route path="/activity" element={<Activity />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/catalog" element={<Catalog />} />
        <Route path="/sources" element={<Sources />} />
        <Route path="/sources/:id" element={<SourceDetail />} />
        <Route path="/connections" element={<Connections />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/quality" element={<Quality />} />
      </Route>
      </Routes>
    </>
  );
}
