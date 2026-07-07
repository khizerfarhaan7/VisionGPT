"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  Image as ImageIcon,
  FileText,
  Volume2,
  Video,
  Database,
  Cpu,
  ArrowUpRight,
  TrendingUp
} from "lucide-react";

export default function Home() {
  const features = [
    {
      id: "image-ai",
      title: "Image AI",
      description: "Analyze screenshots, classify photos, extract visual structures, and detect objects with precision.",
      icon: ImageIcon,
      color: "from-blue-500/20 to-cyan-500/20 text-blue-500 dark:text-blue-400 border-blue-500/30",
      stats: "OCR + Detection",
      badge: "High Accuracy"
    },
    {
      id: "pdf-ai",
      title: "PDF AI",
      description: "Query documents, extract key fields, parse tables, and summarize multi-page reports.",
      icon: FileText,
      color: "from-purple-500/20 to-pink-500/20 text-purple-500 dark:text-purple-400 border-purple-500/30",
      stats: "Multi-page RAG",
      badge: "Fast Parsing"
    },
    {
      id: "audio-ai",
      title: "Audio AI",
      description: "Transcribe voice memos, analyze waveforms, translate speech, and recognize speakers.",
      icon: Volume2,
      color: "from-emerald-500/20 to-teal-500/20 text-emerald-500 dark:text-emerald-400 border-emerald-500/30",
      stats: "Whisper Model",
      badge: "Voice-to-Text"
    },
    {
      id: "video-ai",
      title: "Video AI",
      description: "Scan video feeds, detect motion timelines, summarize scenes, and track objects.",
      icon: Video,
      color: "from-amber-500/20 to-orange-500/20 text-amber-500 dark:text-amber-400 border-amber-500/30",
      stats: "Frame-by-Frame",
      badge: "Beta"
    }
  ];

  return (
    <main className="p-6 md:p-10 max-w-7xl mx-auto w-full space-y-12">
      
      {/* Header Banner Section */}
      <div className="relative overflow-hidden rounded-3xl border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/40 p-8 md:p-10 shadow-sm">
        {/* Background elements */}
        <div className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-br from-violet-600/10 to-indigo-500/5 blur-3xl -z-10 rounded-full" />
        <div className="absolute -bottom-20 -left-20 w-80 h-80 bg-gradient-to-tr from-cyan-500/5 to-violet-500/5 blur-3xl -z-10 rounded-full" />
        
        <div className="max-w-2xl space-y-4">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium bg-violet-500/15 text-violet-600 dark:text-violet-400 border border-violet-500/20">
            <Cpu className="h-3 w-3 animate-spin" />
            Multi-Modal Intelligence Platform
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-slate-900 via-violet-950 to-indigo-950 dark:from-zinc-50 dark:via-zinc-100 dark:to-zinc-300 bg-clip-text text-transparent">
            Welcome to VisionGPT
          </h1>
          <p className="text-slate-500 dark:text-zinc-400 text-sm md:text-base leading-relaxed">
            Unlock advanced machine intuition. Seamlessly analyze complex visuals, query multi-page documents, transcribe voice instructions, and timeline events dynamically under a single SaaS workspace.
          </p>
          
          {/* Stat row */}
          <div className="flex flex-wrap gap-6 pt-4 border-t border-slate-100 dark:border-zinc-800/50 mt-6">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-violet-500" />
              <span className="text-xs text-slate-500 dark:text-zinc-400">PostgreSQL Session Status:</span>
              <span className="text-xs font-semibold text-emerald-500">Connected</span>
            </div>
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-violet-500" />
              <span className="text-xs text-slate-500 dark:text-zinc-400">System Latency:</span>
              <span className="text-xs font-semibold text-slate-700 dark:text-zinc-300">1.2ms (Nominal)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Feature Grid */}
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-bold tracking-tight">Select an Agent Capability</h2>
          <p className="text-xs text-slate-500 dark:text-zinc-400">Deploy modular vision, document intelligence, transcription, or animation workflows.</p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, idx) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={feature.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: idx * 0.1 }}
                whileHover={{ 
                  y: -8, 
                  scale: 1.02,
                  boxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.05), 0 8px 10px -6px rgb(0 0 0 / 0.05)"
                }}
                className="group relative flex flex-col justify-between p-6 rounded-2xl border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/30 transition-all duration-300 cursor-pointer overflow-hidden"
              >
                {/* Hover Glow Background */}
                <div className="absolute inset-0 bg-gradient-to-tr from-violet-600/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                
                <div className="space-y-4">
                  {/* Icon with colored wrapper */}
                  <div className={`h-12 w-12 rounded-xl bg-gradient-to-br ${feature.color} flex items-center justify-center border shadow-inner`}>
                    <Icon className="h-6 w-6 transition-transform duration-300 group-hover:scale-110 group-hover:rotate-6" />
                  </div>
                  
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-sm tracking-tight text-slate-900 dark:text-zinc-50 group-hover:text-violet-600 dark:group-hover:text-violet-400 transition-colors">
                        {feature.title}
                      </h3>
                      <span className="text-[9px] font-medium px-2 py-0.5 rounded-full bg-slate-100 dark:bg-zinc-850 text-slate-500 dark:text-zinc-400">
                        {feature.badge}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 dark:text-zinc-400 leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-6 border-t border-slate-100 dark:border-zinc-850/50 mt-6 text-[10px] text-slate-400">
                  <span>Model: {feature.stats}</span>
                  <div className="flex items-center gap-1 text-violet-500 dark:text-violet-400 opacity-0 group-hover:opacity-100 transition-all transform translate-x-2 group-hover:translate-x-0 font-medium">
                    Launch <ArrowUpRight className="h-3.5 w-3.5" />
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
      
    </main>
  );
}
