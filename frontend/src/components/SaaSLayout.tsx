"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  Upload,
  MessageSquare,
  History,
  Settings,
  Search,
  Sun,
  Moon,
  Bell,
  X,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  User,
  LogOut
} from "lucide-react";

export default function SaaSLayout({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchFocused, setSearchFocused] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  const menuItems = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Workspace", href: "/workspace", icon: Upload },
    { name: "AI Chat", href: "/workspace?tab=chat", icon: MessageSquare },
    { name: "History", href: "#", icon: History },
    { name: "Settings", href: "#", icon: Settings },
  ];

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 text-slate-900 dark:text-zinc-50 font-sans transition-colors duration-300 flex overflow-hidden">
      
      {/* 1. RESPONSIVE LEFT SIDEBAR */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex flex-col border-r border-slate-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/70 backdrop-blur-md transition-all duration-300 ease-in-out lg:translate-x-0 ${
          sidebarOpen ? "w-64 translate-x-0" : "w-20 -translate-x-full lg:translate-x-0 lg:w-20"
        }`}
      >
        {/* Logo area */}
        <div className="flex h-16 items-center justify-between px-6 border-b border-slate-200/80 dark:border-zinc-800/80">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-violet-600 to-indigo-500 text-white shadow-md shadow-violet-600/25">
              <Sparkles className="h-5 w-5 animate-pulse" />
            </div>
            {sidebarOpen && (
              <span className="font-semibold text-lg tracking-tight bg-gradient-to-r from-violet-600 to-indigo-500 dark:from-violet-400 dark:to-indigo-300 bg-clip-text text-transparent">
                VisionGPT
              </span>
            )}
          </div>
          {sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 text-slate-500 dark:text-zinc-400"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 space-y-1.5 px-3 py-6">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all relative group ${
                  isActive
                    ? "text-violet-600 dark:text-violet-400 bg-violet-500/10 dark:bg-violet-400/10"
                    : "text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 hover:bg-slate-100/70 dark:hover:bg-zinc-850/70"
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="active-indicator"
                    className="absolute left-0 w-1 h-6 rounded-r bg-violet-600 dark:bg-violet-400"
                    transition={{ type: "spring", stiffness: 380, damping: 30 }}
                  />
                )}
                <Icon className={`h-5 w-5 transition-transform duration-200 group-hover:scale-110 ${isActive ? "text-violet-600 dark:text-violet-400" : ""}`} />
                {sidebarOpen && <span>{item.name}</span>}
              </Link>
            );
          })}
        </nav>

        {/* User Footer info */}
        <div className="p-4 border-t border-slate-200/80 dark:border-zinc-800/80 bg-slate-50/50 dark:bg-zinc-900/30">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-full bg-gradient-to-tr from-violet-600 to-indigo-500 text-white flex items-center justify-center font-bold text-sm">
              JD
            </div>
            {sidebarOpen && (
              <div className="flex-1 overflow-hidden">
                <p className="text-xs font-semibold truncate">John Doe</p>
                <p className="text-[10px] text-slate-500 dark:text-zinc-400 truncate">pro@visiongpt.ai</p>
              </div>
            )}
            {sidebarOpen && (
              <button className="text-slate-400 hover:text-slate-600 dark:hover:text-zinc-200">
                <LogOut className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* Main Container */}
      <div className={`flex-1 flex flex-col min-w-0 transition-all duration-300 ${sidebarOpen ? "lg:pl-64" : "lg:pl-20"}`}>
        
        {/* 2. TOP NAVIGATION BAR */}
        <header className="sticky top-0 z-40 flex h-16 w-full items-center justify-between px-6 border-b border-slate-200/80 dark:border-zinc-800/80 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1.5 rounded-lg border border-slate-200 dark:border-zinc-800 hover:bg-slate-100 dark:hover:bg-zinc-800 text-slate-500 dark:text-zinc-400"
            >
              {sidebarOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
            
            {/* Search Bar UI */}
            <div className={`hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl border transition-all ${
              searchFocused 
                ? "border-violet-500 ring-2 ring-violet-500/10 w-72 bg-white dark:bg-zinc-900" 
                : "border-slate-200 dark:border-zinc-800 w-60 bg-slate-50/50 dark:bg-zinc-900/50"
            }`}>
              <Search className="h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search models, files..."
                onFocus={() => setSearchFocused(true)}
                onBlur={() => setSearchFocused(false)}
                className="bg-transparent border-none outline-none text-xs w-full text-slate-600 dark:text-zinc-300 placeholder:text-slate-400"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Notifications Toggle */}
            <div className="relative">
              <button 
                onClick={() => setNotificationsOpen(!notificationsOpen)}
                className="relative p-2 rounded-xl border border-slate-200 dark:border-zinc-800 hover:bg-slate-100 dark:hover:bg-zinc-850 text-slate-600 dark:text-zinc-400 transition-colors"
              >
                <Bell className="h-4.5 w-4.5" />
                <span className="absolute top-1.5 right-1.5 flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500"></span>
                </span>
              </button>
              
              <AnimatePresence>
                {notificationsOpen && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="absolute right-0 mt-2 w-80 rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-xl p-4 z-50"
                  >
                    <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-100 dark:border-zinc-800">
                      <span className="font-semibold text-xs">Notifications</span>
                      <button className="text-[10px] text-violet-500 hover:underline">Mark all read</button>
                    </div>
                    <div className="space-y-2">
                      <div className="p-2 rounded-lg bg-slate-50 dark:bg-zinc-850 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-all text-[11px]">
                        <p className="font-medium text-slate-800 dark:text-zinc-200">Vision model updated</p>
                        <p className="text-slate-400 text-[10px]">Version 1.4 has been successfully deployed.</p>
                      </div>
                      <div className="p-2 rounded-lg bg-slate-50 dark:bg-zinc-850 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-all text-[11px]">
                        <p className="font-medium text-slate-800 dark:text-zinc-200">API connection validated</p>
                        <p className="text-slate-400 text-[10px]">Database latency is within nominal bounds (1.2ms).</p>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-xl border border-slate-200 dark:border-zinc-800 hover:bg-slate-100 dark:hover:bg-zinc-850 text-slate-600 dark:text-zinc-400 transition-colors"
            >
              {theme === "light" ? <Moon className="h-4.5 w-4.5" /> : <Sun className="h-4.5 w-4.5" />}
            </button>

            {/* User Avatar Shell */}
            <div className="h-8.5 w-8.5 rounded-xl bg-violet-600/10 text-violet-600 dark:text-violet-400 border border-violet-500/20 flex items-center justify-center">
              <User className="h-4.5 w-4.5" />
            </div>
          </div>
        </header>

        {/* Page Content injected here */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </div>

    </div>
  );
}
