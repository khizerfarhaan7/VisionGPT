"use client";

import React, { useState, useRef } from "react";
import { motion } from "framer-motion";
import {
  UploadCloud,
  Image as ImageIcon,
  FileText,
  Music,
  Film,
  FolderOpen,
  ArrowRight,
  Sparkles,
  Info
} from "lucide-react";

export default function WorkspacePage() {
  const [isDragActive, setIsDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const getFileIcon = (mimeType: string) => {
    if (mimeType.startsWith("image/")) return ImageIcon;
    if (mimeType === "application/pdf") return FileText;
    if (mimeType.startsWith("audio/")) return Music;
    if (mimeType.startsWith("video/")) return Film;
    return FileText;
  };

  const formatBytes = (bytes: number, decimals = 2) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
  };

  const handleButtonClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files);
      setSelectedFiles((prev) => [...prev, ...filesArray]);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const filesArray = Array.from(e.dataTransfer.files);
      setSelectedFiles((prev) => [...prev, ...filesArray]);
    }
  };

  const fileTypes = [
    {
      title: "Images",
      icon: ImageIcon,
      description: "JPEG, PNG, WEBP, SVG",
      extensions: ".png, .jpg, .jpeg, .webp, .svg",
      color: "text-blue-500 bg-blue-500/10 border-blue-500/20"
    },
    {
      title: "PDFs",
      icon: FileText,
      description: "Documents, Reports, Articles",
      extensions: ".pdf",
      color: "text-purple-500 bg-purple-500/10 border-purple-500/20"
    },
    {
      title: "Audio",
      icon: Music,
      description: "MP3, WAV, M4A, AAC",
      extensions: ".mp3, .wav, .m4a, .aac",
      color: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20"
    },
    {
      title: "Video",
      icon: Film,
      description: "MP4, MOV, AVI, WEBM",
      extensions: ".mp4, .mov, .avi, .webm",
      color: "text-amber-500 bg-amber-500/10 border-amber-500/20"
    }
  ];

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  };

  return (
    <main className="p-6 md:p-10 max-w-7xl mx-auto w-full space-y-10">
      
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: -15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="space-y-2"
      >
        <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
          <Sparkles className="h-3 w-3 animate-pulse" />
          Interactive Workspace
        </div>
        <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight">Upload Workspace</h1>
        <p className="text-xs text-slate-500 dark:text-zinc-400">
          Central hub to upload and preview multi-modal files before applying vision, document reading, voice transcription, or analysis.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Drag & Drop upload + File formats */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* 1. Large drag & drop upload area */}
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`relative rounded-3xl border-2 border-dashed p-10 md:p-12 transition-all duration-300 flex flex-col items-center justify-center text-center group cursor-pointer ${
              isDragActive
                ? "border-violet-500 bg-violet-500/5 ring-4 ring-violet-500/5 scale-[1.01]"
                : "border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20 hover:border-slate-300 dark:hover:border-zinc-700 hover:bg-slate-50/50 dark:hover:bg-zinc-900/30"
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              multiple
              accept="image/*,application/pdf,audio/*,video/*"
              className="hidden"
            />
            <div className="space-y-6 flex flex-col items-center">
              {/* Icon wrapper */}
              <div className={`h-16 w-16 rounded-2xl bg-slate-50 dark:bg-zinc-900 border border-slate-100 dark:border-zinc-800 flex items-center justify-center shadow-sm transition-all duration-300 group-hover:scale-110 group-hover:border-violet-500/30 ${
                isDragActive ? "border-violet-500/30 text-violet-500 bg-violet-50/20" : "text-slate-400"
              }`}>
                <UploadCloud className={`h-8 w-8 transition-transform duration-300 ${
                  isDragActive ? "scale-110 text-violet-500" : "group-hover:-translate-y-1"
                }`} />
              </div>

              <div className="space-y-2">
                <h3 className="font-bold text-sm tracking-tight">Drag & Drop your files here</h3>
                <p className="text-xs text-slate-400 dark:text-zinc-500 max-w-sm">
                  Supported formats: Images, PDFs, Audio, Videos. Maximum file size per batch is 50MB.
                </p>
              </div>

              {/* Upload Button */}
              <button 
                onClick={handleButtonClick}
                className="relative inline-flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-semibold text-white bg-gradient-to-tr from-violet-600 to-indigo-500 shadow-md shadow-violet-600/20 hover:shadow-lg hover:shadow-violet-600/25 transition-all transform active:scale-95 cursor-pointer"
              >
                <span>Select Files</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </motion.div>

          {/* Selected Files Display Area */}
          {selectedFiles.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-3 p-6 rounded-3xl border border-slate-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900/10 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold tracking-tight">Selected Files ({selectedFiles.length})</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedFiles([]);
                  }}
                  className="text-[10px] text-red-500 hover:text-red-650 font-medium hover:underline transition-colors"
                >
                  Clear All
                </button>
              </div>
              
              <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
                {selectedFiles.map((file, idx) => {
                  const Icon = getFileIcon(file.type);
                  return (
                    <div
                      key={`${file.name}-${idx}`}
                      className="flex items-center justify-between p-3 rounded-2xl border border-slate-100 dark:border-zinc-850/80 bg-slate-50/50 dark:bg-zinc-950/40 text-xs shadow-sm hover:border-slate-200 dark:hover:border-zinc-800 transition-all"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="h-8.5 w-8.5 rounded-xl bg-violet-500/10 dark:bg-violet-400/10 flex items-center justify-center shrink-0">
                          <Icon className="h-4.5 w-4.5 text-violet-600 dark:text-violet-400" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-semibold text-slate-700 dark:text-zinc-200 truncate max-w-[200px] sm:max-w-md">{file.name}</p>
                          <p className="text-[9px] text-slate-400 dark:text-zinc-500 uppercase">{file.type || 'unknown type'}</p>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="font-medium text-slate-500 dark:text-zinc-400 text-[11px]">{formatBytes(file.size)}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          )}

          {/* 2. Supported File Types section */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
            className="space-y-4"
          >
            <div className="flex items-center gap-2">
              <Info className="h-4.5 w-4.5 text-violet-500" />
              <h2 className="text-sm font-bold tracking-tight">Supported File Formats</h2>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {fileTypes.map((type) => {
                const Icon = type.icon;
                return (
                  <div
                    key={type.title}
                    className="p-4 rounded-2xl border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/10 flex flex-col justify-between space-y-3 shadow-sm hover:shadow-md transition-shadow"
                  >
                    <div className={`h-9 w-9 rounded-lg flex items-center justify-center border ${type.color}`}>
                      <Icon className="h-4.5 w-4.5" />
                    </div>
                    <div className="space-y-0.5">
                      <h4 className="text-xs font-bold">{type.title}</h4>
                      <p className="text-[10px] text-slate-400 dark:text-zinc-500 leading-tight">{type.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>

        </div>

        {/* Right Column: Empty Recent Uploads section */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="space-y-4"
        >
          <h2 className="text-sm font-bold tracking-tight">Recent Uploads</h2>
          
          {/* 3. Empty Recent Uploads section */}
          <div className="border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20 rounded-3xl p-8 flex flex-col items-center justify-center text-center min-h-[300px] shadow-sm">
            <div className="space-y-4 flex flex-col items-center">
              <div className="h-12 w-12 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-100 dark:border-zinc-800 flex items-center justify-center text-slate-400 shadow-sm">
                <FolderOpen className="h-5 w-5" />
              </div>
              <div className="space-y-1">
                <h4 className="text-xs font-semibold">No uploaded files yet</h4>
                <p className="text-[10px] text-slate-400 dark:text-zinc-500 max-w-[200px] leading-relaxed">
                  Files you upload in the workspace session will appear here for processing.
                </p>
              </div>
            </div>
          </div>
        </motion.div>

      </div>

    </main>
  );
}
