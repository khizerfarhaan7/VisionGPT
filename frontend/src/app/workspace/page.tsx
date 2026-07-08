"use client";

import React, { useState, useRef, useEffect } from "react";
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
  pageCount?: number;
}

interface RecentUpload {
  id: string;
  name: string;
  url: string;
  uploadTime: string;
  type: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ExtractResult {
  pageCount: number;
  wordCount: number;
  characterCount: number;
  extractedText: string;
}

interface ChunkItem {
  chunk_id: string;
  page: string;
  text: string;
}

interface ChunkResult {
  total_chunks: number;
  average_chunk_size: number;
  chunks: ChunkItem[];
}

interface IndexResult {
  embedding_model: string;
  vector_dimension: number;
  total_vectors: number;
  index_location: string;
  metadata_location: string;
}

interface PDFChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: {
    chunk_id: string;
    page: string;
    similarity_score: number;
  }[];
}

export default function WorkspacePage() {
  const [isDragActive, setIsDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);
  const [recentUploads, setRecentUploads] = useState<RecentUpload[]>([]);
  const [previewImage, setPreviewImage] = useState<RecentUpload | null>(null);
  
  // Conversational states for visual reasoning chat
  const [activeFileId, setActiveFileId] = useState<string | null>(null);
  const [chatHistories, setChatHistories] = useState<Record<string, ChatMessage[]>>({});
  const [currentInput, setCurrentInput] = useState("");
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // States for PDF text extraction module
  const [extractResults, setExtractResults] = useState<Record<string, ExtractResult>>({});
  const [extractLoading, setExtractLoading] = useState(false);

  // States for PDF intelligent chunking module
  const [chunkResults, setChunkResults] = useState<Record<string, ChunkResult>>({});
  const [chunkLoading, setChunkLoading] = useState(false);
  const [expandedChunks, setExpandedChunks] = useState<Record<string, boolean>>({});

  // States for PDF FAISS indexing module
  const [indexResults, setIndexResults] = useState<Record<string, IndexResult>>({});
  const [indexLoading, setIndexLoading] = useState(false);

  // States for PDF RAG conversational chat module
  const [pdfChatHistories, setPdfChatHistories] = useState<Record<string, PDFChatMessage[]>>({});
  const [pdfChatLoading, setPdfChatLoading] = useState(false);
  const [pdfChatInput, setPdfChatInput] = useState("");
  const [activePdfTab, setActivePdfTab] = useState<"chat" | "chunks">("chat");

  const chatScrollRef = useRef<HTMLDivElement>(null);
  const pdfChatScrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isUploading = selectedFiles.some((f) => f.status === "uploading");

  // Scroll to bottom of visual chat history when message list or loading state changes
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [chatHistories, analysisLoading, activeFileId]);

  // Scroll to bottom of PDF RAG chat history
  useEffect(() => {
    if (pdfChatScrollRef.current) {
      pdfChatScrollRef.current.scrollTop = pdfChatScrollRef.current.scrollHeight;
    }
  }, [pdfChatHistories, pdfChatLoading, activePdfTab, activeFileId]);

  const toggleChunk = (chunkId: string) => {
    setExpandedChunks((prev) => ({ ...prev, [chunkId]: !prev[chunkId] }));
  };

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
    
    // Dynamically route based on type
    const isPdf = fileObj.file.type === "application/pdf" || fileObj.file.name.toLowerCase().endsWith(".pdf");
    const url = isPdf ? `${apiBaseUrl}/upload/pdf` : `${apiBaseUrl}/upload/image`;

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
            prev.map((f) => (f.id === fileObj.id ? { 
              ...f, 
              status: "success", 
              progress: 100, 
              savedName: res.filename,
              pageCount: res.page_count 
            } : f))
          );

          const newUpload: RecentUpload = {
            id: res.filename || Math.random().toString(36).substring(2, 9),
            name: res.original_name || fileObj.file.name,
            url: fileUrl,
            uploadTime: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            type: fileObj.file.type || (isPdf ? "application/pdf" : "unknown")
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

  const handleAnalyzeClick = (file: SelectedFile) => {
    setActiveFileId(file.id);
    if (!chatHistories[file.id]) {
      setChatHistories((prev) => ({
        ...prev,
        [file.id]: [
          { role: "assistant", content: `Hello! I am VisionGPT. Ask me anything about "${file.name}".` }
        ]
      }));
    }
  };

  const triggerTextExtraction = async (savedName: string) => {
    if (!activeFileId || extractLoading) return;
    setExtractLoading(true);
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${apiBaseUrl}/pdf/extract`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ filename: savedName }),
      });
      if (response.ok) {
        const data = await response.json();
        setExtractResults((prev) => ({
          ...prev,
          [activeFileId]: {
            pageCount: data.page_count,
            wordCount: data.word_count,
            characterCount: data.character_count,
            extractedText: data.extracted_text,
          }
        }));
      } else {
        alert("Failed to extract text from PDF. Please check document formatting.");
      }
    } catch {
      alert("Error contacting the text extraction service.");
    } finally {
      setExtractLoading(false);
    }
  };

  const triggerTextChunking = async (extractedText: string) => {
    if (!activeFileId || chunkLoading) return;
    setChunkLoading(true);
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${apiBaseUrl}/pdf/chunk`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: extractedText }),
      });
      if (response.ok) {
        const data = await response.json();
        setChunkResults((prev) => ({
          ...prev,
          [activeFileId]: {
            total_chunks: data.total_chunks,
            average_chunk_size: data.average_chunk_size,
            chunks: data.chunks,
          }
        }));
      } else {
        alert("Failed to create text chunks. Please verify format.");
      }
    } catch {
      alert("Error contacting the text chunking service.");
    } finally {
      setChunkLoading(false);
    }
  };

  const triggerIndexing = async (savedName: string) => {
    if (!activeFileId || indexLoading) return;
    setIndexLoading(true);
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${apiBaseUrl}/pdf/index`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ filename: savedName }),
      });
      if (response.ok) {
        const data = await response.json();
        setIndexResults((prev) => ({
          ...prev,
          [activeFileId]: {
            embedding_model: data.embedding_model,
            vector_dimension: data.vector_dimension,
            total_vectors: data.total_vectors,
            index_location: data.index_location,
            metadata_location: data.metadata_location,
          }
        }));
        
        // Auto-switch to chat tab and initialize welcome message
        setActivePdfTab("chat");
        setPdfChatHistories((prev) => ({
          ...prev,
          [activeFileId]: [
            { role: "assistant", content: "Welcome! I have finished indexing your PDF into the local knowledge base. Ask me anything!" }
          ]
        }));
      } else {
        alert("Failed to build local knowledge base index.");
      }
    } catch {
      alert("Error contacting the indexing service.");
    } finally {
      setIndexLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!activeFileId || !currentInput.trim() || analysisLoading) return;

    const targetFile = selectedFiles.find((f) => f.id === activeFileId);
    if (!targetFile) return;

    const userMessageContent = currentInput.trim();
    setCurrentInput("");

    const userMessage: ChatMessage = { role: "user", content: userMessageContent };
    const previousHistory = chatHistories[activeFileId] || [];

    setChatHistories((prev) => ({
      ...prev,
      [activeFileId]: [...(prev[activeFileId] || []), userMessage]
    }));

    setAnalysisLoading(true);

    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${apiBaseUrl}/analyze/image`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          filename: targetFile.savedName || targetFile.name,
          user_prompt: userMessageContent,
          history: previousHistory.map((m) => ({ role: m.role, content: m.content }))
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const assistantMessage: ChatMessage = { role: "assistant", content: data.answer };
        
        setChatHistories((prev) => ({
          ...prev,
          [activeFileId]: [...(prev[activeFileId] || []), assistantMessage]
        }));
      } else {
        alert("Failed to analyze image file. Please verify model service status.");
      }
    } catch {
      alert("Error contacting the vision reasoning service.");
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleSendPdfMessage = async () => {
    if (!activeFileId || !pdfChatInput.trim() || pdfChatLoading) return;

    const targetFile = selectedFiles.find((f) => f.id === activeFileId);
    if (!targetFile) return;

    const userMessageContent = pdfChatInput.trim();
    setPdfChatInput("");

    const userMessage: PDFChatMessage = { role: "user", content: userMessageContent };
    const currentHistory = pdfChatHistories[activeFileId] || [];

    setPdfChatHistories((prev) => ({
      ...prev,
      [activeFileId]: [...(prev[activeFileId] || []), userMessage]
    }));

    setPdfChatLoading(true);

    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${apiBaseUrl}/pdf/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          filename: targetFile.savedName || targetFile.name,
          question: userMessageContent,
          history: currentHistory.map((m) => ({ role: m.role, content: m.content }))
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const assistantMessage: PDFChatMessage = { 
          role: "assistant", 
          content: data.answer,
          sources: data.sources 
        };
        
        setPdfChatHistories((prev) => ({
          ...prev,
          [activeFileId]: [...(prev[activeFileId] || []), assistantMessage]
        }));
      } else {
        const errJson = await response.json();
        const errMsg = errJson.detail || "Failed to process RAG chat response.";
        alert(`RAG Error: ${errMsg}`);
      }
    } catch {
      alert("Error contacting the PDF chat RAG service. Make sure Ollama LLM is running locally.");
    } finally {
      setPdfChatLoading(false);
    }
  };

  const handleFilesAdded = (files: File[]) => {
    // Preserve chat histories until new files are uploaded, then clear them
    setChatHistories({});
    setExtractResults({});
    setChunkResults({});
    setIndexResults({});
    setPdfChatHistories({});
    setExpandedChunks({});
    setActiveFileId(null);

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
      color: "text-red-500 bg-red-500/10 border-red-500/20"
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
                className={`relative inline-flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-semibold text-white bg-gradient-to-tr from-violet-650 to-indigo-500 shadow-md shadow-violet-650/20 hover:shadow-lg hover:shadow-violet-650/25 transition-all transform active:scale-95 ${
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
                      className="flex items-center justify-between p-3.5 rounded-2xl border border-slate-100 dark:border-zinc-855 bg-slate-50/50 dark:bg-zinc-950/40 text-xs shadow-sm hover:border-slate-200 dark:hover:border-zinc-800 transition-all"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="h-8.5 w-8.5 rounded-xl bg-violet-500/10 dark:bg-violet-400/10 flex items-center justify-center shrink-0">
                          <Icon className="h-4.5 w-4.5 text-violet-600 dark:text-violet-400" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-semibold text-slate-700 dark:text-zinc-200 truncate max-w-[150px] sm:max-w-xs md:max-w-sm">{file.name}</p>
                          <p className="text-[9px] text-slate-400 dark:text-zinc-500 uppercase">
                            {file.type || 'unknown type'} {file.pageCount !== undefined ? `• ${file.pageCount} page(s)` : ''}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {file.status === "uploading" && (
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-slate-200 dark:bg-zinc-855 rounded-full overflow-hidden">
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
                                  handleAnalyzeClick(file);
                                }}
                                disabled={analysisLoading}
                                className={`px-2.5 py-0.5 rounded-md text-[9px] font-bold shadow-sm transition-all transform active:scale-95 cursor-pointer disabled:cursor-not-allowed ${
                                  activeFileId === file.id
                                    ? "bg-violet-650 text-white"
                                    : "bg-slate-200/80 hover:bg-slate-350/80 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300"
                                }`}
                              >
                                {activeFileId === file.id ? "Active Chat" : "Analyze"}
                              </button>
                            )}
                            {(file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setActiveFileId(file.id);
                                }}
                                className={`px-2.5 py-0.5 rounded-md text-[9px] font-bold shadow-sm transition-all transform active:scale-95 cursor-pointer ${
                                  activeFileId === file.id
                                    ? "bg-red-650 text-white"
                                    : "bg-slate-200/80 hover:bg-slate-300/85 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300"
                                }`}
                              >
                                {activeFileId === file.id ? "Viewing Info" : "Preview"}
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

        {/* Right Column: Recent Uploads & Conversational Chat / PDF Preview Panel */}
        <div className="space-y-8">
          
          {/* PDF Preview Card Display */}
          {activeFileId && selectedFiles.find((f) => f.id === activeFileId)?.type === "application/pdf" && (
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              className="border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20 rounded-3xl p-6 shadow-sm space-y-6 flex flex-col"
            >
              {/* Header */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-zinc-800/50">
                <div className="min-w-0">
                  <h2 className="text-xs font-bold tracking-tight uppercase text-slate-500 dark:text-zinc-400">PDF Document</h2>
                  <p className="text-[10px] text-slate-400 dark:text-zinc-500 truncate max-w-[180px]">
                    {selectedFiles.find((f) => f.id === activeFileId)?.name}
                  </p>
                </div>
                <button
                  onClick={() => setActiveFileId(null)}
                  className="text-slate-400 hover:text-slate-650 dark:hover:text-zinc-200 cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* PDF Preview details block / Scrollable Text / Chunk Viewer */}
              {chunkResults[activeFileId] ? (
                <div className="flex-1 flex flex-col min-h-0 space-y-4 animate-fade-in">
                  
                  {/* Index Status Panel */}
                  {indexResults[activeFileId] ? (
                    <div className="p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-[10px] space-y-2.5">
                      <div className="flex items-center justify-between font-bold text-emerald-600 dark:text-emerald-400">
                        <span>Status: Knowledge Base Ready</span>
                        <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500 animate-ping"></span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-slate-500 dark:text-zinc-450">
                        <div>Model: <span className="font-semibold text-slate-700 dark:text-zinc-300">{indexResults[activeFileId].embedding_model}</span></div>
                        <div>Vectors: <span className="font-semibold text-slate-700 dark:text-zinc-300">{indexResults[activeFileId].total_vectors}</span></div>
                        <div>Dimension: <span className="font-semibold text-slate-700 dark:text-zinc-300">{indexResults[activeFileId].vector_dimension}</span></div>
                        <div>Index: <span className="font-semibold text-slate-700 dark:text-zinc-300">FAISS IndexFlatL2</span></div>
                      </div>
                    </div>
                  ) : (
                    /* Chunk Metrics Grid */
                    <div className="grid grid-cols-2 gap-2 text-center">
                      <div className="p-2 rounded-xl bg-slate-50 dark:bg-zinc-950/40 border border-slate-100 dark:border-zinc-850">
                        <p className="text-[9px] text-slate-400 dark:text-zinc-500 font-medium">Total Chunks</p>
                        <p className="text-xs font-bold text-slate-700 dark:text-zinc-250">{chunkResults[activeFileId].total_chunks}</p>
                      </div>
                      <div className="p-2 rounded-xl bg-slate-50 dark:bg-zinc-950/40 border border-slate-100 dark:border-zinc-850">
                        <p className="text-[9px] text-slate-400 dark:text-zinc-500 font-medium">Avg Size (Chars)</p>
                        <p className="text-xs font-bold text-slate-700 dark:text-zinc-250">{chunkResults[activeFileId].average_chunk_size}</p>
                      </div>
                    </div>
                  )}

                  {/* Tabs Switcher for Chunk Explorer vs RAG Chat */}
                  {indexResults[activeFileId] && (
                    <div className="flex border-b border-slate-100 dark:border-zinc-800">
                      <button
                        onClick={() => setActivePdfTab("chat")}
                        className={`flex-1 pb-2 text-xs font-bold text-center border-b-2 transition-colors cursor-pointer ${
                          activePdfTab === "chat"
                            ? "border-red-500 text-slate-800 dark:text-zinc-150"
                            : "border-transparent text-slate-400 dark:text-zinc-500"
                        }`}
                      >
                        Ask Document
                      </button>
                      <button
                        onClick={() => setActivePdfTab("chunks")}
                        className={`flex-1 pb-2 text-xs font-bold text-center border-b-2 transition-colors cursor-pointer ${
                          activePdfTab === "chunks"
                            ? "border-red-500 text-slate-800 dark:text-zinc-150"
                            : "border-transparent text-slate-400 dark:text-zinc-500"
                        }`}
                      >
                        Browse Chunks
                      </button>
                    </div>
                  )}

                  {/* Tab View Contents */}
                  {(!indexResults[activeFileId] || activePdfTab === "chunks") ? (
                    /* Scrollable Chunks List */
                    <div className="flex-1 min-h-[160px] max-h-[220px] overflow-y-auto space-y-2 pr-1 font-sans text-xs">
                      {chunkResults[activeFileId].chunks.map((chunk) => {
                        const isExpanded = !!expandedChunks[chunk.chunk_id];
                        return (
                          <div
                            key={chunk.chunk_id}
                            onClick={() => toggleChunk(chunk.chunk_id)}
                            className="p-3 rounded-2xl border border-slate-100 dark:border-zinc-855 bg-slate-50/50 dark:bg-zinc-950/40 cursor-pointer hover:border-slate-200 dark:hover:border-zinc-800 transition-all space-y-2"
                          >
                            <div className="flex items-center justify-between font-semibold text-[9px] text-slate-500 dark:text-zinc-405">
                              <span className="uppercase tracking-wider font-bold text-violet-600 dark:text-violet-400">{chunk.chunk_id}</span>
                              <span>Page(s): {chunk.page} • {chunk.text.length} chars</span>
                            </div>
                            <p className={`text-[11px] leading-relaxed text-slate-600 dark:text-zinc-350 ${
                              isExpanded ? "whitespace-pre-wrap font-mono text-[10px] bg-slate-100/50 dark:bg-zinc-955/50 p-2 rounded-xl border border-slate-200/30 dark:border-zinc-900/30" : "truncate"
                            }`}>
                              {isExpanded ? chunk.text : `${chunk.text.slice(0, 150)}${chunk.text.length > 150 ? '...' : ''}`}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    /* RAG Chat interface view */
                    <div className="flex flex-col flex-1 min-h-0 space-y-3">
                      {/* Chat Messages scroll area */}
                      <div
                        ref={pdfChatScrollRef}
                        className="flex-1 overflow-y-auto space-y-3.5 pr-1 text-xs scroll-smooth max-h-[180px] min-h-[140px]"
                      >
                        {(pdfChatHistories[activeFileId] || []).map((msg, idx) => {
                          const isUser = msg.role === "user";
                          return (
                            <div
                              key={idx}
                              className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
                            >
                              <div
                                className={`max-w-[85%] rounded-2xl px-3 py-2 shadow-sm leading-relaxed whitespace-pre-wrap break-words ${
                                  isUser
                                    ? "bg-red-650 text-white rounded-tr-none"
                                    : "bg-slate-100 dark:bg-zinc-850 text-slate-800 dark:text-zinc-250 rounded-tl-none border border-slate-200/20 dark:border-zinc-800/30"
                                }`}
                              >
                                {msg.content}
                              </div>
                              
                              {/* Sources list details */}
                              {!isUser && msg.sources && msg.sources.length > 0 && (
                                <div className="mt-1 flex flex-wrap gap-1 px-1">
                                  <span className="text-[8px] text-slate-400 dark:text-zinc-500 font-semibold self-center">Sources:</span>
                                  {msg.sources.map((s, sIdx) => (
                                    <span
                                      key={sIdx}
                                      className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[8px] font-semibold bg-slate-200/60 dark:bg-zinc-800/80 text-slate-500 dark:text-zinc-400 border border-slate-300/10"
                                    >
                                      {s.chunk_id} (p. {s.page})
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })}

                        {/* Typing Animation */}
                        {pdfChatLoading && (
                          <div className="flex justify-start">
                            <div className="bg-slate-100 dark:bg-zinc-855 text-slate-500 dark:text-zinc-455 rounded-2xl rounded-tl-none px-3 py-1.5 border border-slate-200/20 dark:border-zinc-800/30 shadow-sm flex items-center gap-2">
                              <div className="flex gap-1">
                                <span className="w-1.5 h-1.5 bg-slate-400 dark:bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></span>
                                <span className="w-1.5 h-1.5 bg-slate-400 dark:bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></span>
                                <span className="w-1.5 h-1.5 bg-slate-400 dark:bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></span>
                              </div>
                              <span className="text-[9px] font-semibold italic">VisionGPT is typing...</span>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Chat Input & Clear Chat wrapper */}
                      <div className="pt-2 border-t border-slate-100 dark:border-zinc-855 flex gap-2 items-center">
                        <button
                          onClick={() => {
                            setPdfChatHistories((prev) => ({
                              ...prev,
                              [activeFileId]: [
                                { role: "assistant", content: "Chat cleared. Ask me anything about the document!" }
                              ]
                            }));
                          }}
                          className="px-2.5 py-2 rounded-xl bg-slate-250 dark:bg-zinc-800 hover:bg-slate-300 dark:hover:bg-zinc-700 text-slate-600 dark:text-zinc-300 text-[10px] font-bold transition-all shrink-0 cursor-pointer border-0"
                        >
                          Clear
                        </button>
                        
                        <input
                          value={pdfChatInput}
                          onChange={(e) => setPdfChatInput(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                              e.preventDefault();
                              handleSendPdfMessage();
                            }
                          }}
                          placeholder="Ask anything about the PDF..."
                          disabled={pdfChatLoading}
                          className="flex-1 px-3 py-2 rounded-xl text-[11px] border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-red-500/30 disabled:opacity-60 disabled:cursor-not-allowed h-9"
                        />
                        
                        <button
                          onClick={handleSendPdfMessage}
                          disabled={pdfChatLoading || !pdfChatInput.trim()}
                          className="px-3.5 py-2 rounded-xl bg-red-650 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-[11px] font-bold shadow-sm transition-all transform active:scale-95 flex items-center justify-center h-9 cursor-pointer border-0"
                        >
                          Send
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : extractResults[activeFileId] ? (
                /* Text Extraction results block */
                <div className="flex-1 flex flex-col min-h-0 space-y-4">
                  {/* Extraction Metrics Grid */}
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="p-2 rounded-xl bg-slate-50 dark:bg-zinc-950/40 border border-slate-100 dark:border-zinc-850">
                      <p className="text-[9px] text-slate-400 dark:text-zinc-500 font-medium">Pages</p>
                      <p className="text-xs font-bold text-slate-700 dark:text-zinc-255">{extractResults[activeFileId].pageCount}</p>
                    </div>
                    <div className="p-2 rounded-xl bg-slate-50 dark:bg-zinc-950/40 border border-slate-100 dark:border-zinc-850">
                      <p className="text-[9px] text-slate-400 dark:text-zinc-500 font-medium">Words</p>
                      <p className="text-xs font-bold text-slate-700 dark:text-zinc-255">{extractResults[activeFileId].wordCount}</p>
                    </div>
                    <div className="p-2 rounded-xl bg-slate-50 dark:bg-zinc-950/40 border border-slate-100 dark:border-zinc-850">
                      <p className="text-[9px] text-slate-400 dark:text-zinc-500 font-medium">Chars</p>
                      <p className="text-xs font-bold text-slate-700 dark:text-zinc-255">{extractResults[activeFileId].characterCount}</p>
                    </div>
                  </div>

                  {/* Scrollable Text Viewer */}
                  <div className="flex-1 min-h-[220px] max-h-[300px] overflow-y-auto p-3 rounded-xl border border-slate-150 dark:border-zinc-855 bg-slate-50/50 dark:bg-zinc-950/40 font-mono text-[10px] text-slate-600 dark:text-zinc-350 leading-normal whitespace-pre-wrap break-words">
                    {extractResults[activeFileId].extractedText}
                  </div>
                </div>
              ) : (
                /* Standard PDF Details Cover */
                <div className="flex-1 flex flex-col items-center justify-center p-6 border border-slate-100 dark:border-zinc-850 bg-slate-50/50 dark:bg-zinc-950/40 rounded-2xl text-center space-y-4">
                  <div className="h-16 w-16 rounded-2xl bg-red-500/10 dark:bg-red-400/10 flex items-center justify-center border border-red-500/20">
                    <FileText className="h-8 w-8 text-red-650 dark:text-red-400" />
                  </div>
                  
                  <div className="space-y-1 w-full px-2">
                    <h3 className="text-xs font-bold truncate max-w-full text-slate-800 dark:text-zinc-200">
                      {selectedFiles.find((f) => f.id === activeFileId)?.name}
                    </h3>
                    <p className="text-[10px] text-slate-400 dark:text-zinc-500">
                      Size: {formatBytes(selectedFiles.find((f) => f.id === activeFileId)?.size || 0)}
                    </p>
                    <p className="text-[10px] text-slate-400 dark:text-zinc-500 font-semibold">
                      Pages: {selectedFiles.find((f) => f.id === activeFileId)?.pageCount || "Unknown"}
                    </p>
                  </div>
                </div>
              )}

              {/* Action Buttons: Build Knowledge Base, Create Chunks, Extract Text, Open PDF */}
              <div className="space-y-2.5">
                {chunkResults[activeFileId] && !indexResults[activeFileId] && (
                  <button
                    onClick={() => {
                      const target = selectedFiles.find((f) => f.id === activeFileId);
                      if (target?.savedName) {
                        triggerIndexing(target.savedName);
                      }
                    }}
                    disabled={indexLoading}
                    className="w-full py-2.5 rounded-xl bg-violet-650 hover:bg-violet-755 disabled:opacity-50 text-white text-xs font-bold shadow-sm transition-all transform active:scale-95 flex items-center justify-center gap-2 cursor-pointer border-0 disabled:cursor-not-allowed"
                  >
                    {indexLoading ? (
                      <>
                        <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                        <span>Building Knowledge Base...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-3.5 w-3.5" />
                        <span>Build Knowledge Base</span>
                      </>
                    )}
                  </button>
                )}

                {extractResults[activeFileId] && !chunkResults[activeFileId] && (
                  <button
                    onClick={() => {
                      triggerTextChunking(extractResults[activeFileId].extractedText);
                    }}
                    disabled={chunkLoading}
                    className="w-full py-2.5 rounded-xl bg-violet-650 hover:bg-violet-755 disabled:opacity-50 text-white text-xs font-bold shadow-sm transition-all transform active:scale-95 flex items-center justify-center gap-2 cursor-pointer border-0 disabled:cursor-not-allowed"
                  >
                    {chunkLoading ? (
                      <>
                        <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                        <span>Creating Chunks...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-3.5 w-3.5" />
                        <span>Create Chunks</span>
                      </>
                    )}
                  </button>
                )}

                {!extractResults[activeFileId] && (
                  <button
                    onClick={() => {
                      const target = selectedFiles.find((f) => f.id === activeFileId);
                      if (target?.savedName) {
                        triggerTextExtraction(target.savedName);
                      }
                    }}
                    disabled={extractLoading}
                    className="w-full py-2.5 rounded-xl bg-violet-650 hover:bg-violet-755 disabled:opacity-50 text-white text-xs font-bold shadow-sm transition-all transform active:scale-95 flex items-center justify-center gap-2 cursor-pointer border-0 disabled:cursor-not-allowed"
                  >
                    {extractLoading ? (
                      <>
                        <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                        <span>Extracting Text...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-3.5 w-3.5" />
                        <span>Extract Text</span>
                      </>
                    )}
                  </button>
                )}

                <button
                  onClick={() => {
                    const target = selectedFiles.find((f) => f.id === activeFileId);
                    if (target?.savedName) {
                      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
                      const backendRootUrl = apiBaseUrl.replace("/api/v1", "");
                      window.open(`${backendRootUrl}/uploads/pdfs/${target.savedName}`, "_blank");
                    } else {
                      alert("Document is still processing or upload was not completed.");
                    }
                  }}
                  className="w-full py-2.5 rounded-xl bg-red-655 hover:bg-red-700 text-white text-xs font-bold shadow-sm transition-all transform active:scale-95 flex items-center justify-center gap-2 cursor-pointer border-0"
                >
                  <FolderOpen className="h-4 w-4" />
                  <span>Open PDF</span>
                </button>
              </div>
            </motion.div>
          )}

          {/* Analysis Results Display as Conversational Chat */}
          {activeFileId && selectedFiles.find((f) => f.id === activeFileId)?.type.startsWith("image/") && (
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              className="border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20 rounded-3xl shadow-sm flex flex-col h-[500px] overflow-hidden"
            >
              {/* Chat Header */}
              <div className="flex items-center justify-between p-4 border-b border-slate-100 dark:border-zinc-800/50 bg-slate-50/50 dark:bg-zinc-950/20">
                <div className="min-w-0">
                  <h2 className="text-xs font-bold tracking-tight uppercase text-slate-500 dark:text-zinc-400">VisionGPT Chat</h2>
                  <p className="text-[10px] text-slate-400 dark:text-zinc-500 truncate max-w-[180px]">
                    {selectedFiles.find((f) => f.id === activeFileId)?.name || "Image Reasoning"}
                  </p>
                </div>
                <button
                  onClick={() => {
                    setActiveFileId(null);
                  }}
                  className="text-slate-400 hover:text-slate-655 dark:hover:text-zinc-200 cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Chat Message Scrollable Area */}
              <div 
                ref={chatScrollRef}
                className="flex-1 overflow-y-auto p-4 space-y-4 text-xs scroll-smooth"
              >
                {(chatHistories[activeFileId] || []).map((msg, idx) => {
                  const isUser = msg.role === "user";
                  return (
                    <div
                      key={idx}
                      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 shadow-sm leading-relaxed whitespace-pre-wrap break-words ${
                          isUser
                            ? "bg-violet-600 text-white rounded-tr-none"
                            : "bg-slate-100 dark:bg-zinc-850 text-slate-800 dark:text-zinc-250 rounded-tl-none border border-slate-200/20 dark:border-zinc-800/30"
                        }`}
                      >
                        {msg.content}
                      </div>
                    </div>
                  );
                })}

                {/* Animated Thinking Indicator */}
                {analysisLoading && (
                  <div className="flex justify-start">
                    <div className="bg-slate-100 dark:bg-zinc-855 text-slate-500 dark:text-zinc-455 rounded-2xl rounded-tl-none px-3.5 py-2.5 border border-slate-200/20 dark:border-zinc-800/30 shadow-sm flex items-center gap-2">
                      <div className="flex gap-1">
                        <span className="w-1.5 h-1.5 bg-slate-400 dark:bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></span>
                        <span className="w-1.5 h-1.5 bg-slate-400 dark:bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></span>
                        <span className="w-1.5 h-1.5 bg-slate-400 dark:bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></span>
                      </div>
                      <span className="text-[10px] font-semibold italic">VisionGPT is thinking...</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Chat Input Area (Fixed at bottom) */}
              <div className="p-3 border-t border-slate-100 dark:border-zinc-855 bg-slate-50/50 dark:bg-zinc-955/20">
                <div className="flex gap-2 items-end">
                  <textarea
                    value={currentInput}
                    onChange={(e) => setCurrentInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                    placeholder="Ask anything about this image..."
                    rows={2}
                    disabled={analysisLoading}
                    className="flex-1 px-3 py-2 rounded-xl text-xs border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-violet-500/30 resize-none disabled:opacity-60 disabled:cursor-not-allowed max-h-20"
                  />
                  <button
                    onClick={handleSendMessage}
                    disabled={analysisLoading || !currentInput.trim()}
                    className="px-4 py-2 rounded-xl bg-violet-650 hover:bg-violet-755 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-bold shadow-sm transition-all transform active:scale-95 flex items-center justify-center min-w-[70px] h-9 cursor-pointer"
                  >
                    Send
                  </button>
                </div>
              </div>
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
