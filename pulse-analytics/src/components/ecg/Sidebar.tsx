import { motion } from "framer-motion";
import {
  Activity,
  Brain,
  ChevronLeft,
  Cpu,
  Download,
  FileUp,
  Gauge,
  LayoutDashboard,
  LineChart,
  Network,
  ShieldCheck,
  Sparkles,
  Upload,
  Waves,
  Zap,
  CheckCircle2,
  Lock,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface SidebarSection {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  group?: string;
}

export const SECTIONS: SidebarSection[] = [
  { id: "overview", label: "Dashboard Overview", icon: LayoutDashboard, group: "Workspace" },
  { id: "upload", label: "MATLAB Upload", icon: Upload, group: "Workspace" },
  { id: "ecg", label: "ECG Signal Analysis", icon: Waves, group: "Analysis" },
  { id: "ai", label: "AI Prediction Engine", icon: Sparkles, group: "Analysis" },
  { id: "cnn", label: "CNN Visualization", icon: Network, group: "Analysis" },
  { id: "training", label: "Training Analytics", icon: LineChart, group: "Model" },
  { id: "performance", label: "Model Performance", icon: Activity, group: "Model" },
  { id: "quant", label: "Quantization", icon: Brain, group: "Model" },
  { id: "hex", label: "HEX Generator", icon: Download, group: "Hardware" },
  { id: "fpga-upload", label: "FPGA Upload", icon: FileUp, group: "Hardware" },
  { id: "fpga", label: "FPGA Analysis", icon: Cpu, group: "Hardware" },
  { id: "hw-compare", label: "HW Performance", icon: Gauge, group: "Hardware" },
  { id: "final", label: "Final Validation", icon: ShieldCheck, group: "System" },
];

interface Props {
  active: string;
  onSelect: (id: string) => void;
  collapsed: boolean;
  onToggle: () => void;
  progress?: any;
}

const getStatus = (id: string, progress: any) => {
  if (!progress) return null;
  switch (id) {
    case "overview":
      return null;
    case "upload":
      return progress.matlab_upload ? "complete" : "pending";
    case "ecg":
      return progress.matlab_upload ? "complete" : "locked";
    case "ai":
      if (progress.inference) return "complete";
      return progress.matlab_upload ? "pending" : "locked";
    case "cnn":
      return progress.matlab_upload ? "complete" : "locked";
    case "training":
      return "complete"; // static/pre-trained model visualization
    case "performance":
      if (progress.inference) return "complete";
      return "locked";
    case "quant":
      if (progress.quantization) return "complete";
      return progress.inference ? "pending" : "locked";
    case "hex":
      if (progress.hex_generation) return "complete";
      return progress.quantization ? "pending" : "locked";
    case "fpga-upload":
      if (progress.fpga_analysis) return "complete";
      return progress.hex_generation ? "pending" : "locked";
    case "fpga":
    case "hw-compare":
    case "final":
      if (progress.fpga_analysis) return "complete";
      return "locked";
    default:
      return null;
  }
};

export function Sidebar({ active, onSelect, collapsed, onToggle, progress }: Props) {
  const groups = SECTIONS.reduce<Record<string, SidebarSection[]>>((acc, s) => {
    const g = s.group ?? "Other";
    (acc[g] ||= []).push(s);
    return acc;
  }, {});

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 72 : 264 }}
      transition={{ type: "spring", stiffness: 220, damping: 26 }}
      className="sticky top-0 z-30 hidden h-screen shrink-0 border-r border-slate-200/70 bg-white/70 backdrop-blur-xl lg:block"
    >
      <div className="flex h-16 items-center gap-2 border-b border-slate-200/70 px-4">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-blue-500 via-cyan-500 to-violet-500 text-white shadow-glow-blue">
          <Zap className="h-4 w-4" />
        </div>
        {!collapsed && (
          <div className="flex-1 leading-tight">
            <div className="text-sm font-semibold tracking-tight">CardioFPGA</div>
            <div className="text-[10px] uppercase tracking-widest text-slate-500">
              AI · ECG · FPGA
            </div>
          </div>
        )}
        <button
          aria-label="Collapse sidebar"
          onClick={onToggle}
          className="ml-auto rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"
        >
          <ChevronLeft
            className={cn(
              "h-4 w-4 transition-transform",
              collapsed && "rotate-180",
            )}
          />
        </button>
      </div>

      <nav className="flex flex-col gap-4 overflow-y-auto p-3 pb-24" style={{ height: "calc(100vh - 4rem)" }}>
        {Object.entries(groups).map(([g, items]) => (
          <div key={g}>
            {!collapsed && (
              <div className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                {g}
              </div>
            )}
            <div className="flex flex-col gap-1">
              {items.map((s) => {
                const Icon = s.icon;
                const isActive = active === s.id;
                const status = getStatus(s.id, progress);
                return (
                  <button
                    key={s.id}
                    onClick={() => onSelect(s.id)}
                    className={cn(
                      "group relative flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-all",
                      isActive
                        ? "bg-gradient-to-r from-blue-500/10 via-cyan-500/10 to-violet-500/10 text-slate-900"
                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                    )}
                  >
                    {isActive && (
                      <motion.span
                        layoutId="sb-active"
                        className="absolute inset-y-1 left-0 w-1 rounded-full bg-gradient-to-b from-blue-500 to-violet-500"
                        transition={{ type: "spring", stiffness: 320, damping: 28 }}
                      />
                    )}
                    <Icon className={cn("h-4 w-4 shrink-0", isActive && "text-blue-600")} />
                    {!collapsed && <span className="truncate">{s.label}</span>}
                    
                    {!collapsed && status === "complete" && (
                      <CheckCircle2 className="ml-auto h-3.5 w-3.5 text-emerald-500 shrink-0" />
                    )}
                    {!collapsed && status === "pending" && (
                      <span className="ml-auto relative flex h-2 w-2 shrink-0">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                      </span>
                    )}
                    {!collapsed && status === "locked" && (
                      <Lock className="ml-auto h-3 w-3 text-slate-300 shrink-0" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </motion.aside>
  );
}
