import { createFileRoute, Link } from "@tanstack/react-router";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Brain,
  ChevronRight,
  Cpu,
  HeartPulse,
  LayoutDashboard,
  Sparkles,
  Upload,
  Waves,
  Zap,
} from "lucide-react";
import { ECGWave } from "@/components/ecg/ECGWave";
import { Particles } from "@/components/ecg/Particles";
import { Counter } from "@/components/ecg/Counter";

export const Route = createFileRoute("/")({
  component: Landing,
  head: () => ({
    meta: [
      { title: "CardioFPGA — AI-Powered ECG Arrhythmia & FPGA Analysis Platform" },
      {
        name: "description",
        content:
          "Real-time ECG signal analysis, intelligent arrhythmia prediction, CNN visualization, FPGA hardware validation, and complete AI-to-hardware workflow analytics.",
      },
    ],
  }),
});

function Landing() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-white text-slate-900">
      {/* NAV */}
      <header className="sticky top-0 z-40 border-b border-slate-200/60 bg-white/70 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center px-4 md:px-6">
          <Link to="/" className="flex items-center gap-2">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-blue-500 via-cyan-500 to-violet-500 text-white shadow-glow-blue">
              <Zap className="h-4 w-4" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold">CardioFPGA</div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500">
                AI · ECG · FPGA
              </div>
            </div>
          </Link>
          <nav className="ml-10 hidden gap-6 text-sm text-slate-600 md:flex">
            <a href="#features" className="hover:text-slate-900">Features</a>
            <a href="#workflow" className="hover:text-slate-900">Workflow</a>
            <a href="#hardware" className="hover:text-slate-900">Hardware</a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Link
              to="/dashboard"
              className="hidden rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 md:inline-flex"
            >
              Open Dashboard
            </Link>
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Start <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="relative isolate overflow-hidden">
        <div className="absolute inset-0 bg-aurora" />
        <div className="absolute inset-0 bg-grid opacity-40" />
        <Particles count={28} />
        <ECGWave className="absolute inset-x-0 bottom-12 h-40 w-full opacity-50" color="#06b6d4" />

        <div className="relative mx-auto max-w-7xl px-4 pb-20 pt-16 md:px-6 md:pt-24 lg:pt-32">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700"
          >
            <span className="h-2 w-2 animate-ecg-pulse rounded-full bg-blue-600" />
            Live · CNN inference · 1.8 ms latency on Zynq-7020
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="mt-6 max-w-4xl text-4xl font-semibold tracking-tight md:text-6xl"
          >
            <span className="text-gradient">AI-Powered ECG Arrhythmia</span>
            <br />
            <span>& FPGA Analysis Platform</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.15 }}
            className="mt-5 max-w-2xl text-base text-slate-600 md:text-lg"
          >
            Real-time ECG signal analysis, intelligent arrhythmia prediction, CNN visualization,
            FPGA hardware validation, and complete AI-to-hardware workflow analytics — in one
            elegant platform.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="mt-8 flex flex-wrap items-center gap-3"
          >
            <Link
              to="/dashboard"
              hash="upload"
              className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-glow-blue hover:bg-slate-800"
            >
              <Upload className="h-4 w-4" /> Upload MATLAB Outputs
            </Link>
            <Link
              to="/dashboard"
              hash="ai"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-800 hover:bg-slate-50"
            >
              <Sparkles className="h-4 w-4" /> Start AI Analysis
            </Link>
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 via-cyan-500 to-violet-600 px-5 py-3 text-sm font-semibold text-white hover:opacity-95"
            >
              <LayoutDashboard className="h-4 w-4" /> Explore Dashboard
            </Link>
          </motion.div>

          {/* Hero stats */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
            className="mt-14 grid grid-cols-2 gap-4 md:grid-cols-4"
          >
            {[
              { k: "Accuracy", v: 98.7, suf: "%", dec: 1, c: "text-blue-600" },
              { k: "Latency", v: 1.8, suf: " ms", dec: 1, c: "text-cyan-600" },
              { k: "FPGA power", v: 1.42, suf: " W", dec: 2, c: "text-violet-600" },
              { k: "Compression", v: 4, suf: "×", c: "text-emerald-600" },
            ].map((s) => (
              <div
                key={s.k}
                className="rounded-2xl border border-slate-200 bg-white/70 p-5 backdrop-blur-sm"
              >
                <div className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                  {s.k}
                </div>
                <div className={`mt-1 text-2xl font-semibold ${s.c}`}>
                  <Counter to={s.v} decimals={s.dec ?? 0} suffix={s.suf} />
                </div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="relative mx-auto max-w-7xl px-4 py-20 md:px-6">
        <div className="mb-10 max-w-2xl">
          <div className="text-xs font-semibold uppercase tracking-widest text-blue-600">
            Capabilities
          </div>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
            One platform. The full ECG-to-FPGA workflow.
          </h2>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            {
              icon: Waves,
              title: "ECG Signal Analysis",
              desc: "Raw, filtered, R-peak and beat-segment visualization with playback.",
              color: "from-blue-500 to-cyan-500",
            },
            {
              icon: Brain,
              title: "AI Prediction",
              desc: "Beat-by-beat CNN inference with confidence and probability distribution.",
              color: "from-violet-500 to-fuchsia-500",
            },
            {
              icon: HeartPulse,
              title: "Live Monitoring",
              desc: "Real-time anomaly alerts, smart insights and adaptive scaling.",
              color: "from-rose-500 to-orange-500",
            },
            {
              icon: Cpu,
              title: "FPGA Validation",
              desc: "Vivado synthesis report parsing, utilization, timing and power.",
              color: "from-cyan-500 to-emerald-500",
            },
            {
              icon: Sparkles,
              title: "CNN Visualization",
              desc: "Interactive layers, activations, parameter counts and data flow.",
              color: "from-blue-500 to-violet-500",
            },
            {
              icon: Zap,
              title: "Quantization & HEX",
              desc: "FP32 → INT8 with 4× compression, hex weights ready for bitstream.",
              color: "from-amber-500 to-rose-500",
            },
          ].map((f, i) => {
            const Icon = f.icon;
            return (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ delay: i * 0.05 }}
                className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 transition-all hover:-translate-y-0.5 hover:shadow-xl"
              >
                <div className={`absolute -right-10 -top-10 h-28 w-28 rounded-full bg-gradient-to-br ${f.color} opacity-20 blur-2xl`} />
                <div className={`inline-grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br ${f.color} text-white shadow-lg`}>
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-base font-semibold text-slate-900">{f.title}</h3>
                <p className="mt-1 text-sm text-slate-600">{f.desc}</p>
              </motion.div>
            );
          })}
        </div>
      </section>

      {/* WORKFLOW */}
      <section id="workflow" className="relative border-y border-slate-200/70 bg-gradient-to-b from-slate-50 to-white py-20">
        <div className="mx-auto max-w-7xl px-4 md:px-6">
          <div className="mb-12 max-w-2xl">
            <div className="text-xs font-semibold uppercase tracking-widest text-blue-600">
              Workflow
            </div>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              MATLAB → CNN → INT8 → FPGA
            </h2>
            <p className="mt-3 text-slate-600">
              A continuous, instrumented pipeline from raw ECG to deployed hardware.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-4">
            {[
              { n: 1, t: "Upload MATLAB outputs", d: "Filtered signals, R-peaks, beat windows." },
              { n: 2, t: "AI prediction", d: "1D CNN classifies each beat in real time." },
              { n: 3, t: "Quantize & generate HEX", d: "FP32→INT8 weights packed for BRAM." },
              { n: 4, t: "FPGA validation", d: "Vivado reports + on-chip monitoring." },
            ].map((s, i) => (
              <motion.div
                key={s.n}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="relative rounded-2xl border border-slate-200 bg-white p-5"
              >
                <div className="grid h-9 w-9 place-items-center rounded-xl bg-slate-900 text-sm font-semibold text-white">
                  {s.n}
                </div>
                <div className="mt-3 text-sm font-semibold text-slate-900">{s.t}</div>
                <div className="mt-1 text-sm text-slate-600">{s.d}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section id="hardware" className="relative mx-auto max-w-7xl px-4 py-20 md:px-6">
        <div className="relative overflow-hidden rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-900 via-slate-900 to-blue-950 p-10 text-white md:p-14">
          <div className="absolute inset-0 opacity-30">
            <ECGWave className="h-full w-full" color="#06b6d4" />
          </div>
          <div className="relative max-w-2xl">
            <div className="text-xs font-semibold uppercase tracking-widest text-cyan-300">
              Ready when you are
            </div>
            <h2 className="mt-2 text-3xl font-semibold md:text-4xl">
              Open the live dashboard
            </h2>
            <p className="mt-3 text-slate-300">
              Inspect every signal, layer, weight and FPGA resource — all in one intelligent
              workspace.
            </p>
            <Link
              to="/dashboard"
              className="mt-6 inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-slate-900 hover:bg-slate-100"
            >
              Enter Dashboard <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200 py-8 text-center text-xs text-slate-500">
        © {new Date().getFullYear()} CardioFPGA · AI · ECG · FPGA
      </footer>
    </div>
  );
}
