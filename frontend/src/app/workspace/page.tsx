"use client";

import React, { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  UploadCloud,
  Image as ImageIcon,
  FileText,
  Music,
  Film,
  FolderOpen,
  ArrowRight,
  Sparkles,
  Info,
  X
} from "lucide-react";

interface SelectedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  progress: number;
  status: "idle" | "uploading" | "success" | "error";
  savedName?: string;
}

interface RecentUpload {
  id: string;
  name: string;
  url: string;
  uploadTime: string;
  type: string;
}

interface AnalysisResult {
  caption: string;
  objects_detected: string[];
  ocr_text: string;
  confidence: number;
  filename: string;
}

export default function WorkspacePage() {
  const [isDragActive, setIsDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);
  const [recentUploads, setRecentUploads] = useState<RecentUpload[]>([]);
  const [previewImage, setPreviewImage] = useState<RecentUpload | null>(null);
  
  // New modular states for visual AI analysis
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isUploading = selectedFiles.some((f) => f.status === "uploading");

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

  const startUpload = (fileObj: { id: string; file: File }) => {
    const xhr = new XMLHttpRequest();
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    const url = `${apiBaseUrl}/upload/image`;

    const formData = new FormData();
    formData.append("file", fileObj.file);

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        const percentage = Math.round((event.loaded * 100) / event.total);
        setSelectedFiles((prev) =>
          prev.map((f) => (f.id === fileObj.id ? { ...f, progress: percentage } : f))
        );
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const res = JSON.parse(xhr.responseText);
          const backendRootUrl = apiBaseUrl.replace("/api/v1", "");
          const fileUrl = `${backendRootUrl}/${res.path}`;

          setSelectedFiles((prev) =>
            prev.map((f) => (f.id === fileObj.id ? { ...f, status: "success", progress: 100, savedName: res.filename } : f))
          );

          const newUpload: RecentUpload = {
            id: res.filename || Math.random().toString(36).substring(2, 9),
            name: res.original_name || fileObj.file.name,
            url: fileUrl,
            uploadTime: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            type: fileObj.file.type
          };

          setRecentUploads((prev) => {
            const updated = [newUpload, ...prev];
            return updated.slice(0, 10);
          });
        } catch {
          setSelectedFiles((prev) =>
            prev.map((f) => (f.id === fileObj.id ? { ...f, status: "success", progress: 100 } : f))
          );
        }
      } else {
        setSelectedFiles((prev) =>
          prev.map((f) => (f.id === fileObj.id ? { ...f, status: "error", progress: 0 } : f))
        );
      }
    });

    xhr.addEventListener("error", () => {
      setSelectedFiles((prev) =>
        prev.map((f) => (f.id === fileObj.id ? { ...f, status: "error", progress: 0 } : f))
      );
    });

    xhr.open("POST", url, true);
    xhr.send(formData);
  };

  const triggerAnalysis = async (savedName: string, originalName: string) => {
    setAnalysisLoading(true);
    setAnalysisResult(null);
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${apiBaseUrl}/analyze/image`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ filename: savedName }),
      });
      if (response.ok) {
        const data = await response.json();
        setAnalysisResult({
          caption: data.caption,
          objects_detected: data.objects_detected,
          ocr_text: data.ocr_text,
          confidence: data.confidence,
          filename: originalName
        });
      } else {
        alert("Failed to analyze image file. Please verify model service status.");
      }
    } catch {
      alert("Error contacting the vision analysis service.");
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleFilesAdded = (files: File[]) => {
    const newFiles = files.map((file) => ({
      id: Math.random().toString(36).substring(2, 9),
      name: file.name,
      size: file.size,
      type: file.type,
      progress: 0,
      status: "uploading" as const
    }));

    setSelectedFiles((prev) => [...prev, ...newFiles]);

    newFiles.forEach((newFile, index) => {
      startUpload({ id: newFile.id, file: files[index] });
    });
  };

  const handleButtonClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isUploading) {
      fileInputRef.current?.click();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (isUploading) return;
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files);
      handleFilesAdded(filesArray);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    if (isUploading) return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const filesArray = Array.from(e.dataTransfer.files);
      handleFilesAdded(filesArray);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (isUploading) return;
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
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
            onClick={() => !isUploading && fileInputRef.current?.click()}
            className={`relative rounded-3xl border-2 border-dashed p-10 md:p-12 transition-all duration-300 flex flex-col items-center justify-center text-center group ${
              isUploading ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-slate-300 dark:hover:border-zinc-700 hover:bg-slate-50/50 dark:hover:bg-zinc-900/30"
            } ${
              isDragActive && !isUploading
                ? "border-violet-500 bg-violet-500/5 ring-4 ring-violet-500/5 scale-[1.01]"
                : "border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20"
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              multiple
              accept="image/*,application/pdf,audio/*,video/*"
              className="hidden"
              disabled={isUploading}
            />
            <div className="space-y-6 flex flex-col items-center">
              {/* Icon wrapper */}
              <div className={`h-16 w-16 rounded-2xl bg-slate-50 dark:bg-zinc-900 border border-slate-100 dark:border-zinc-800 flex items-center justify-center shadow-sm transition-all duration-300 group-hover:scale-110 group-hover:border-violet-500/30 ${
                isDragActive && !isUploading ? "border-violet-500/30 text-violet-500 bg-violet-50/20" : "text-slate-400"
              }`}>
                <UploadCloud className={`h-8 w-8 transition-transform duration-300 ${
                  isDragActive && !isUploading ? "scale-110 text-violet-500" : "group-hover:-translate-y-1"
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
                disabled={isUploading}
                className={`relative inline-flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-semibold text-white bg-gradient-to-tr from-violet-600 to-indigo-500 shadow-md shadow-violet-600/20 hover:shadow-lg hover:shadow-violet-600/25 transition-all transform active:scale-95 ${
                  isUploading ? "opacity-50 cursor-not-allowed active:scale-100" : "cursor-pointer"
                }`}
              >
                <span>{isUploading ? "Uploading..." : "Select Files"}</span>
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
                    if (!isUploading) setSelectedFiles([]);
                  }}
                  disabled={isUploading}
                  className={`text-[10px] font-medium hover:underline transition-colors ${
                    isUploading ? "text-slate-400 cursor-not-allowed" : "text-red-500 hover:text-red-650"
                  }`}
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
                          <p className="font-semibold text-slate-700 dark:text-zinc-200 truncate max-w-[150px] sm:max-w-xs md:max-w-sm">{file.name}</p>
                          <p className="text-[9px] text-slate-400 dark:text-zinc-500 uppercase">{file.type || 'unknown type'}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {file.status === "uploading" && (
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-slate-200 dark:bg-zinc-850 rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-violet-500 transition-all duration-300" 
                                style={{ width: `${file.progress}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-slate-400 dark:text-zinc-500 font-semibold">{file.progress}%</span>
                          </div>
                        )}
                        {file.status === "success" && (
                          <div className="flex items-center gap-2">
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                              Uploaded
                            </span>
                            {file.type.startsWith("image/") && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  triggerAnalysis(file.savedName || file.name, file.name);
                                }}
                                disabled={analysisLoading}
                                className="px-2 py-0.5 rounded-md bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white text-[9px] font-bold shadow-sm transition-all transform active:scale-95 cursor-pointer disabled:cursor-not-allowed"
                              >
                                Analyze
                              </button>
                            )}
                          </div>
                        )}
                        {file.status === "error" && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-semibold bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20">
                            Failed
                          </span>
                        )}
                        <p className="font-medium text-slate-500 dark:text-zinc-400 text-[11px] min-w-[50px] text-right">
                          {formatBytes(file.size)}
                        </p>
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

        {/* Right Column: Recent Uploads & Analysis Panel */}
        <div className="space-y-8">
          
          {/* Analysis Results Display */}
          {(analysisLoading || analysisResult) && (
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              className="border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20 rounded-3xl p-6 shadow-sm space-y-4"
            >
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-zinc-800/50">
                <h2 className="text-xs font-bold tracking-tight uppercase text-slate-500 dark:text-zinc-400">Analysis Results</h2>
                {analysisResult && (
                  <button
                    onClick={() => setAnalysisResult(null)}
                    className="text-slate-400 hover:text-slate-650 dark:hover:text-zinc-200 cursor-pointer"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>

              {analysisLoading ? (
                <div className="flex flex-col items-center justify-center py-10 space-y-3">
                  <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
                  <p className="text-[11px] text-slate-400 dark:text-zinc-500">AI Model reasoning in progress...</p>
                </div>
              ) : (
                analysisResult && (
                  <div className="space-y-4 text-xs">
                    <div>
                      <p className="text-[10px] text-slate-400 dark:text-zinc-500 uppercase tracking-wider font-semibold">Source File</p>
                      <p className="font-semibold mt-0.5 text-slate-700 dark:text-zinc-200 truncate">{analysisResult.filename}</p>
                    </div>

                    <div>
                      <p className="text-[10px] text-slate-400 dark:text-zinc-500 uppercase tracking-wider font-semibold">Visual Caption</p>
                      <p className="mt-1 leading-relaxed text-slate-600 dark:text-zinc-300 bg-slate-50/50 dark:bg-zinc-950/40 p-2.5 rounded-xl border border-slate-100 dark:border-zinc-850/50">
                        {analysisResult.caption}
                      </p>
                    </div>

                    <div>
                      <p className="text-[10px] text-slate-400 dark:text-zinc-500 uppercase tracking-wider font-semibold mb-1.5">Objects Detected</p>
                      <div className="flex flex-wrap gap-1.5">
                        {analysisResult.objects_detected.map((obj, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded-md bg-violet-500/10 text-violet-650 dark:text-violet-400 border border-violet-500/20 text-[10px] font-medium animate-fade-in"
                          >
                            {obj}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div>
                      <p className="text-[10px] text-slate-400 dark:text-zinc-500 uppercase tracking-wider font-semibold">Extracted OCR Text</p>
                      <p className="mt-1 leading-relaxed font-mono text-[10px] text-slate-600 dark:text-zinc-300 bg-slate-50/50 dark:bg-zinc-950/40 p-2.5 rounded-xl border border-slate-100 dark:border-zinc-850/50 break-words">
                        {analysisResult.ocr_text}
                      </p>
                    </div>

                    <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-zinc-850/50">
                      <span className="text-slate-400">Confidence Metric</span>
                      <span className="font-semibold text-emerald-500">{(analysisResult.confidence * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                )
              )}
            </motion.div>
          )}

          {/* Recent Uploads Section */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="space-y-4"
          >
            <h2 className="text-sm font-bold tracking-tight">Recent Uploads</h2>
            
            {recentUploads.length > 0 ? (
              <div className="space-y-3">
                {recentUploads.map((upload) => (
                  <div
                    key={upload.id}
                    onClick={() => {
                      if (upload.type.startsWith("image/")) {
                        setPreviewImage(upload);
                      }
                    }}
                    className={`flex items-center gap-3 p-3 rounded-2xl border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20 shadow-sm transition-all ${
                      upload.type.startsWith("image/") 
                        ? "cursor-pointer hover:border-violet-500/30 hover:bg-slate-100/50 dark:hover:bg-zinc-900/40" 
                        : ""
                    }`}
                  >
                    {/* Thumbnail / Icon wrapper */}
                    <div className="h-12 w-12 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-100 dark:border-zinc-800 overflow-hidden flex items-center justify-center shrink-0">
                      {upload.type.startsWith("image/") ? (
                        <img 
                          src={upload.url} 
                          alt={upload.name} 
                          className="h-full w-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                      ) : (
                        React.createElement(getFileIcon(upload.type), { className: "h-5 w-5 text-slate-400" })
                      )}
                    </div>
                    
                    {/* Metadata */}
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-slate-700 dark:text-zinc-200 truncate">{upload.name}</p>
                      <p className="text-[9px] text-slate-400 dark:text-zinc-500">{upload.uploadTime}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              /* 3. Empty Recent Uploads section */
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
            )}
          </motion.div>
        </div>

      </div>

      {/* Image Preview Modal */}
      <AnimatePresence>
        {previewImage && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            onClick={() => setPreviewImage(null)}
          >
            <motion.div
              initial={{ scale: 0.95, y: 15 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 15 }}
              transition={{ type: "spring", duration: 0.4 }}
              onClick={(e) => e.stopPropagation()}
              className="relative max-w-3xl w-full rounded-3xl border border-slate-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6 shadow-2xl flex flex-col gap-4 overflow-hidden"
            >
              {/* Close Button */}
              <button
                onClick={() => setPreviewImage(null)}
                className="absolute top-4 right-4 p-1.5 rounded-xl border border-slate-200 dark:border-zinc-800 hover:bg-slate-100 dark:hover:bg-zinc-800 text-slate-500 dark:text-zinc-400 z-10 transition-colors cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>

              <div className="flex items-center justify-between pr-10">
                <div className="min-w-0">
                  <h3 className="text-sm font-bold truncate">{previewImage.name}</h3>
                  <p className="text-[10px] text-slate-400 dark:text-zinc-500">Uploaded at {previewImage.uploadTime}</p>
                </div>
              </div>
              
              <div className="relative rounded-2xl overflow-hidden bg-slate-50 dark:bg-zinc-950 border border-slate-100 dark:border-zinc-900 flex items-center justify-center max-h-[70vh]">
                <img
                  src={previewImage.url}
                  alt={previewImage.name}
                  className="max-h-[60vh] max-w-full object-contain"
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </main>
  );
}
