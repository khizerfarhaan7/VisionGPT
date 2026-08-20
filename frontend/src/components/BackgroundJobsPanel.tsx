"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { BackgroundJob, listJobs, cancelJob } from "@/services/jobApi";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  FileText,
  Music,
  Film,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Clock,
  Ban,
  RefreshCw,
  ChevronDown,
  ChevronUp
} from "lucide-react";

interface BackgroundJobsPanelProps {
  sessionId?: string;
  onJobCompleted?: (job: BackgroundJob) => void;
  className?: string;
}

export default function BackgroundJobsPanel({
  sessionId,
  onJobCompleted,
  className = ""
}: BackgroundJobsPanelProps) {
  const [jobs, setJobs] = useState<BackgroundJob[]>([]);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const [cancellingIds, setCancellingIds] = useState<Record<string, boolean>>({});

  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const completedJobsSetRef = useRef<Set<string>>(new Set());

  const fetchJobs = useCallback(async () => {
    try {
      const res = await listJobs(sessionId, 20);
      const newJobs = res.jobs || [];

      // Check for newly completed jobs to notify parent component
      newJobs.forEach((job) => {
        if (job.status === "completed" && !completedJobsSetRef.current.has(job.job_id)) {
          completedJobsSetRef.current.add(job.job_id);
          if (onJobCompleted) {
            onJobCompleted(job);
          }
        }
      });

      setJobs(newJobs);
      return newJobs;
    } catch (err: unknown) {
      console.warn("BackgroundJobsPanel: Failed to fetch jobs:", err);
      return [];
    }
  }, [sessionId, onJobCompleted]);

  // Main Polling Lifecycle
  useEffect(() => {
    let isMounted = true;

    const runPollingLoop = async () => {
      if (!isMounted) return;
      const currentJobs = await fetchJobs();

      // Determine if active jobs (queued or running) exist
      const hasActive = currentJobs.some(
        (j) => j.status === "queued" || j.status === "running"
      );

      // If active jobs exist, schedule next poll in 1500ms
      if (hasActive && isMounted) {
        pollingTimerRef.current = setTimeout(runPollingLoop, 1500);
      }
    };

    runPollingLoop();

    return () => {
      isMounted = false;
      if (pollingTimerRef.current) {
        clearTimeout(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };
  }, [fetchJobs]);

  const handleCancel = async (jobId: string) => {
    setCancellingIds((prev) => ({ ...prev, [jobId]: true }));
    try {
      await cancelJob(jobId);
      await fetchJobs();
    } catch (err: unknown) {
      console.error("Failed to cancel job:", err);
    } finally {
      setCancellingIds((prev) => ({ ...prev, [jobId]: false }));
    }
  };

  const getJobIcon = (type: string) => {
    if (type.includes("pdf")) return <FileText className="w-4 h-4 text-emerald-400" />;
    if (type.includes("audio")) return <Music className="w-4 h-4 text-purple-400" />;
    if (type.includes("video")) return <Film className="w-4 h-4 text-cyan-400" />;
    return <Activity className="w-4 h-4 text-indigo-400" />;
  };

  const getStatusBadge = (status: BackgroundJob["status"]) => {
    switch (status) {
      case "queued":
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Clock className="w-3 h-3 animate-pulse" /> Queued
          </span>
        );
      case "running":
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <RefreshCw className="w-3 h-3 animate-spin" /> Processing
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" /> Completed
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertCircle className="w-3 h-3" /> Failed
          </span>
        );
      case "cancelled":
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/20">
            <Ban className="w-3 h-3" /> Cancelled
          </span>
        );
      case "interrupted":
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/20">
            <XCircle className="w-3 h-3" /> Interrupted
          </span>
        );
    }
  };

  const activeCount = jobs.filter(
    (j) => j.status === "queued" || j.status === "running"
  ).length;

  if (jobs.length === 0) {
    return null;
  }

  return (
    <div className={`bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-xl backdrop-blur-md ${className}`}>
      {/* Panel Header */}
      <div className="flex items-center justify-between mb-3 border-b border-slate-800/80 pb-2.5">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-indigo-400 animate-pulse" />
          <h3 className="text-sm font-semibold text-slate-200">
            Background Processing Tasks
          </h3>
          {activeCount > 0 && (
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              {activeCount} active
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => fetchJobs()}
            className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-200 transition-colors"
            title="Refresh jobs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-200 transition-colors"
          >
            {isCollapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Jobs List */}
      <AnimatePresence>
        {!isCollapsed && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-2.5 max-h-64 overflow-y-auto pr-1"
          >
            {jobs.map((job) => {
              const filename =
                (job.metadata?.filename as string) || job.document_id || job.job_type;
              const stage = (job.metadata?.stage as string) || job.job_type;
              const isActive =
                job.status === "queued" || job.status === "running";

              return (
                <div
                  key={job.job_id}
                  className="bg-slate-950/60 border border-slate-800/90 rounded-lg p-3 space-y-2 hover:border-slate-700/80 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 overflow-hidden">
                      {getJobIcon(job.job_type)}
                      <span
                        className="text-xs font-medium text-slate-300 truncate max-w-[180px]"
                        title={filename}
                      >
                        {filename}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {getStatusBadge(job.status)}
                      {isActive && (
                        <button
                          onClick={() => handleCancel(job.job_id)}
                          disabled={cancellingIds[job.job_id]}
                          className="text-xs font-medium px-2 py-0.5 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition-colors disabled:opacity-50"
                        >
                          {cancellingIds[job.job_id] ? "Cancelling..." : "Cancel"}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Progress Bar */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                      <span>{stage}</span>
                      <span>{job.progress}%</span>
                    </div>
                    <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 rounded-full ${
                          job.status === "completed"
                            ? "bg-emerald-500"
                            : job.status === "failed" || job.status === "interrupted"
                            ? "bg-rose-500"
                            : job.status === "cancelled"
                            ? "bg-slate-600"
                            : "bg-gradient-to-r from-indigo-500 to-cyan-400"
                        }`}
                        style={{ width: `${job.progress}%` }}
                      />
                    </div>
                  </div>

                  {/* Error display */}
                  {job.error && (
                    <p className="text-[11px] text-rose-400/90 bg-rose-950/40 p-1.5 rounded border border-rose-900/50">
                      {job.error}
                    </p>
                  )}
                </div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
