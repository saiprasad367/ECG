import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { SECTIONS, Sidebar } from "@/components/ecg/Sidebar";
import { Topbar } from "@/components/ecg/Topbar";
import { CheckCircle2, Lock } from "lucide-react";
import {
  OverviewSection,
  UploadSection,
  ECGAnalysisSection,
  AISection,
  CNNSection,
  TrainingSection,
  PerformanceSection,
  QuantSection,
  HexSection,
  FPGAUploadSection,
  FPGASection,
  HWCompareSection,
  FinalSection,
} from "@/components/ecg/sections";
import { apiClient } from "@/services/api";

export const Route = createFileRoute("/dashboard")({
  component: Dashboard,
});

const COMPONENTS: Record<string, React.ComponentType<any>> = {
  overview: OverviewSection,
  upload: UploadSection,
  ecg: ECGAnalysisSection,
  ai: AISection,
  cnn: CNNSection,
  training: TrainingSection,
  performance: PerformanceSection,
  quant: QuantSection,
  hex: HexSection,
  "fpga-upload": FPGAUploadSection,
  fpga: FPGASection,
  "hw-compare": HWCompareSection,
  final: FinalSection,
};

function Dashboard() {
  const [active, setActive] = useState<string>("overview");
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = async () => {
    try {
      const data = await apiClient.getDashboardData();
      setDashboardData(data);
    } catch (e) {
      console.error("Failed to fetch dashboard metrics:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleHashChange = () => {
      const h = window.location.hash.replace("#", "");
      if (h && COMPONENTS[h]) {
        setActive(h);
      }
    };
    
    // Initial run
    handleHashChange();
    
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const Section = COMPONENTS[active] ?? OverviewSection;
  const label = SECTIONS.find((s) => s.id === active)?.label ?? "Dashboard";

  const handleSelectSection = (id: string) => {
    setActive(id);
    window.location.hash = id;
  };

  return (
    <div className="relative min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/40">
      <div className="pointer-events-none fixed inset-0 bg-aurora opacity-50" />
      <div className="relative flex">
        <Sidebar
          active={active}
          onSelect={(id) => {
            handleSelectSection(id);
            setMobileOpen(false);
          }}
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
          progress={dashboardData?.progress}
        />

        {/* Mobile drawer */}
        {mobileOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div
              className="absolute inset-0 bg-slate-900/30 backdrop-blur-sm"
              onClick={() => setMobileOpen(false)}
            />
            <div className="relative h-full w-72 bg-white shadow-2xl">
              <div className="flex h-16 items-center border-b border-slate-200 px-4 font-semibold">
                CardioFPGA
              </div>
              <nav className="flex flex-col gap-1 overflow-y-auto p-3" style={{ height: "calc(100% - 4rem)" }}>
                {SECTIONS.map((s) => {
                  const Icon = s.icon;
                  const progress = dashboardData?.progress;
                  let status = null;
                  if (progress) {
                    switch (s.id) {
                      case "upload":
                        status = progress.matlab_upload ? "complete" : "pending";
                        break;
                      case "ecg":
                        status = progress.matlab_upload ? "complete" : "locked";
                        break;
                      case "ai":
                        status = progress.inference ? "complete" : (progress.matlab_upload ? "pending" : "locked");
                        break;
                      case "cnn":
                        status = progress.matlab_upload ? "complete" : "locked";
                        break;
                      case "training":
                        status = "complete";
                        break;
                      case "performance":
                        status = progress.inference ? "complete" : "locked";
                        break;
                      case "quant":
                        status = progress.quantization ? "complete" : (progress.inference ? "pending" : "locked");
                        break;
                      case "hex":
                        status = progress.hex_generation ? "complete" : (progress.quantization ? "pending" : "locked");
                        break;
                      case "fpga-upload":
                        status = progress.fpga_analysis ? "complete" : (progress.hex_generation ? "pending" : "locked");
                        break;
                      case "fpga":
                      case "hw-compare":
                      case "final":
                        status = progress.fpga_analysis ? "complete" : "locked";
                        break;
                    }
                  }

                  return (
                    <button
                      key={s.id}
                      onClick={() => {
                        handleSelectSection(s.id);
                        setMobileOpen(false);
                      }}
                      className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all ${
                        active === s.id ? "bg-blue-50 text-blue-700 font-semibold" : "text-slate-600"
                      }`}
                    >
                      <Icon className={`h-4 w-4 shrink-0 ${active === s.id ? "text-blue-600" : ""}`} />
                      <span className="truncate">{s.label}</span>
                      
                      {status === "complete" && (
                        <CheckCircle2 className="ml-auto h-3.5 w-3.5 text-emerald-500 shrink-0" />
                      )}
                      {status === "pending" && (
                        <span className="ml-auto relative flex h-2 w-2 shrink-0">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                        </span>
                      )}
                      {status === "locked" && (
                        <Lock className="ml-auto h-3 w-3 text-slate-300 shrink-0" />
                      )}
                    </button>
                  );
                })}
              </nav>
            </div>
          </div>
        )}

        <div className="min-w-0 flex-1">
          <Topbar onMenu={() => setMobileOpen(true)} sectionLabel={label} />
          <main className="mx-auto max-w-7xl px-4 py-6 md:px-6 lg:px-8 lg:py-10">
            {loading ? (
              <div className="grid min-h-[50vh] place-items-center">
                <div className="flex flex-col items-center gap-3">
                  <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
                  <div className="text-sm font-medium text-slate-500">Connecting to workspace session...</div>
                </div>
              </div>
            ) : (
              <AnimatePresence mode="wait">
                <div key={active}>
                  <Section 
                    data={dashboardData} 
                    refreshDashboard={fetchDashboard}
                    setActiveSection={handleSelectSection}
                  />
                </div>
              </AnimatePresence>
            )}
            <footer className="mt-16 border-t border-slate-200/70 pt-6 text-center text-xs text-slate-500">
              CardioFPGA · AI-Powered ECG Arrhythmia & FPGA Analysis Platform
            </footer>
          </main>
        </div>
      </div>
    </div>
  );
}
