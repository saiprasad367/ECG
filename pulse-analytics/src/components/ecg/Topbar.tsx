import { Bell, Menu, Search, Sparkles } from "lucide-react";
import { motion } from "framer-motion";

interface Props {
  onMenu: () => void;
  sectionLabel: string;
}

export function Topbar({ onMenu, sectionLabel }: Props) {
  return (
    <div className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200/70 bg-white/70 px-4 backdrop-blur-xl md:px-6">
      <button
        onClick={onMenu}
        className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>
      <div className="flex min-w-0 items-center gap-2">
        <div className="hidden text-xs font-medium uppercase tracking-widest text-slate-400 md:block">
          Workspace /
        </div>
        <div className="truncate text-sm font-semibold text-slate-900">{sectionLabel}</div>
      </div>

      <div className="ml-auto hidden items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-500 md:flex md:w-72">
        <Search className="h-4 w-4" />
        <input
          placeholder="Search beats, layers, reports…"
          className="w-full bg-transparent outline-none placeholder:text-slate-400"
        />
        <kbd className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-500">⌘K</kbd>
      </div>

      <motion.div
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700"
      >
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
        </span>
        Live inference
      </motion.div>

      <button className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100" aria-label="Notifications">
        <Bell className="h-5 w-5" />
        <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-rose-500" />
      </button>
      <div className="hidden h-9 items-center gap-2 rounded-xl bg-slate-900 px-3 text-sm font-medium text-white md:flex">
        <Sparkles className="h-4 w-4 text-cyan-300" />
        AI Copilot
      </div>
    </div>
  );
}
