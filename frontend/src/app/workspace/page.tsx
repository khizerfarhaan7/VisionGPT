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
  X,
  Copy,
  Download,
  Search,
  Globe
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
    start_time?: number;
    end_time?: number;
  }[];
}

export default function WorkspacePage() {
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<"upload" | "search">("upload");
  const [webSearchQuery, setWebSearchQuery] = useState("");
  const [selectedContentType, setSelectedContentType] = useState<"pdf" | "youtube" | "audio">("pdf");
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

  // States for Audio transcription module
  const [transcribeResults, setTranscribeResults] = useState<Record<string, string>>({});
  const [transcribeMetrics, setTranscribeMetrics] = useState<Record<string, {
    detected_language: string;
    duration: number;
    processing_time: number;
    word_count: number;
  }>>({});
  const [transcribeChunks, setTranscribeChunks] = useState<Record<string, {
    chunk_id: string;
    start_time: number;
    end_time: number;
    text: string;
  }[]>>({});
  const [transcribeLoading, setTranscribeLoading] = useState(false);

  // States for Audio RAG conversational chat module
  const [audioChatHistories, setAudioChatHistories] = useState<Record<string, PDFChatMessage[]>>({});
  const [audioChatLoading, setAudioChatLoading] = useState(false);
  const [audioChatInput, setAudioChatInput] = useState("");
  const [activeAudioTab, setActiveAudioTab] = useState<"chat" | "transcript">("chat");
  const [transcriptSearch, setTranscriptSearch] = useState("");

  // States for Video Intelligence module
  const [videoAnalyzeLoading, setVideoAnalyzeLoading] = useState(false);
  const [videoStage, setVideoStage] = useState("");
  const [videoDurations, setVideoDurations] = useState<Record<string, number>>({});
  const [videoIndexResults, setVideoIndexResults] = useState<Record<string, {
    success: boolean;
    video_id: string;
    total_chunks: number;
    index_location: string;
    metadata_location: string;
    processing_time: number;
  }>>({});
  const [videoDashboards, setVideoDashboards] = useState<Record<string, {
    filename: string;
    duration: number;
    fps: number;
    width: number;
    height: number;
    total_frames: number;
    codec: string;
    total_chunks: number;
    processing_time: number;
    transcript: string;
    timeline: Array<{
      timestamp: number;
      type: "vision" | "speech";
      content: string;
    }>;
    frames: Array<{
      frame_number: number;
      timestamp: number;
      filename: string;
      caption: string;
    }>;
  }>>({});
  const [videoDashboardLoading, setVideoDashboardLoading] = useState<Record<string, boolean>>({});
  const [activeDashboardTabs, setActiveDashboardTabs] = useState<Record<string, "overview" | "transcript" | "timeline" | "keyframes" | "chat">>({});
  const [videoTranscriptSearch, setVideoTranscriptSearch] = useState("");
  const [selectedKeyframe, setSelectedKeyframe] = useState<{
    frame_number: number;
    timestamp: number;
    filename: string;
    caption: string;
  } | null>(null);

  // States for Video RAG conversational chat module
  interface VideoChatMessage {
    role: "user" | "assistant";
    content: string;
    sources?: Array<{
      chunk_id: string;
      page: string;
      start_time: number;
      end_time: number;
      similarity_score: number;
    }>;
    error?: boolean;
  }
  const [videoChatHistories, setVideoChatHistories] = useState<Record<string, VideoChatMessage[]>>({});
  const [videoChatInput, setVideoChatInput] = useState("");
  const [videoChatLoading, setVideoChatLoading] = useState(false);

  const isVideoFile = (file: { type: string; name: string }) => {
    return file.type.startsWith("video/") ||
      file.name.toLowerCase().endsWith(".mp4") ||
      file.name.toLowerCase().endsWith(".mov") ||
      file.name.toLowerCase().endsWith(".avi") ||
      file.name.toLowerCase().endsWith(".mkv") ||
      file.name.toLowerCase().endsWith(".webm");
  };

  const isAudioFile = (file: { type: string; name: string }) => {
    return (file.type.startsWith("audio/") ||
      file.name.toLowerCase().endsWith(".mp3") ||
      file.name.toLowerCase().endsWith(".wav") ||
      file.name.toLowerCase().endsWith(".m4a") ||
      file.name.toLowerCase().endsWith(".ogg")) && !isVideoFile(file);
  };

  // Toast notification state
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const showToast = (message: string) => {
    setToastMessage(message);
    setTimeout(() => {
      setToastMessage((curr) => curr === message ? null : curr);
    }, 3000);
  };

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const highlightText = (text: string, query: string) => {
    if (!query) return text;
    const parts = text.split(new RegExp(`(${query.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&')})`, 'gi'));
    return parts.map((part, i) =>
      part.toLowerCase() === query.toLowerCase() ? (
        <mark key={i} className="bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 px-0.5 rounded font-semibold">{part}</mark>
      ) : part
    );
  };

  const highlightVideoText = (text: string, query: string) => {
    if (!query) return text;
    const parts = text.split(new RegExp(`(${query.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&')})`, 'gi'));
    return parts.map((part, i) =>
      part.toLowerCase() === query.toLowerCase() ? (
        <mark key={i} className="bg-amber-500/20 text-amber-650 dark:text-amber-300 px-0.5 rounded font-semibold">{part}</mark>
      ) : part
    );
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const chatScrollRef = useRef<HTMLDivElement>(null);
  const pdfChatScrollRef = useRef<HTMLDivElement>(null);
  const audioChatScrollRef = useRef<HTMLDivElement>(null);
  const videoChatScrollRef = useRef<HTMLDivElement>(null);
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

  // Scroll to bottom of Audio RAG chat history
  useEffect(() => {
    if (audioChatScrollRef.current) {
      audioChatScrollRef.current.scrollTop = audioChatScrollRef.current.scrollHeight;
    }
  }, [audioChatHistories, audioChatLoading, activeAudioTab, activeFileId]);

  // Scroll to bottom of Video RAG chat history
  useEffect(() => {
    if (videoChatScrollRef.current) {
      videoChatScrollRef.current.scrollTop = videoChatScrollRef.current.scrollHeight;
    }
  }, [videoChatHistories, videoChatLoading, activeDashboardTabs, activeFileId]);

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
    const isVideo = isVideoFile({ type: fileObj.file.type, name: fileObj.file.name });
    const isAudio = isAudioFile({ type: fileObj.file.type, name: fileObj.file.name });

    const url = isPdf
      ? `${apiBaseUrl}/upload/pdf`
      : (isAudio || isVideo)
        ? `${apiBaseUrl}/upload/audio`
        : `${apiBaseUrl}/upload/image`;

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

  const handleAnalyzeVideo = async (savedName: string) => {
    if (!activeFileId || videoAnalyzeLoading) return;
    
    setVideoAnalyzeLoading(true);
    setVideoStage("Extracting Frames...");
    
    // Setup a timed stage rotator to cycle through stages on the UI
    const stages = [
      { text: "Extracting Frames...", delay: 0 },
      { text: "Generating Captions...", delay: 3500 },
      { text: "Transcribing Audio...", delay: 7000 },
      { text: "Building Timeline...", delay: 10500 },
      { text: "Generating Embeddings...", delay: 13000 },
      { text: "Indexing...", delay: 15500 }
    ];
    
    const timers: NodeJS.Timeout[] = [];
    stages.forEach((stage) => {
      const t = setTimeout(() => {
        setVideoStage(stage.text);
      }, stage.delay);
      timers.push(t);
    });
    
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${apiBaseUrl}/video/index`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ filename: savedName }),
      });
      
      // Clear timers
      timers.forEach(clearTimeout);
      
      if (response.ok) {
        const data = await response.json();
        setVideoIndexResults((prev) => ({
          ...prev,
          [activeFileId]: data
        }));
        if (data.dashboard) {
          setVideoDashboards((prev) => ({
            ...prev,
            [activeFileId]: data.dashboard
          }));
        }
        showToast("Video indexed successfully.");
      } else {
        const errJson = await response.json().catch(() => ({}));
        const errMsg = errJson.detail || "Video indexing failed.";
        alert(`Analysis Error: ${errMsg}`);
      }
    } catch {
      timers.forEach(clearTimeout);
      alert("Error contacting the video intelligence service. Please make sure backend is online.");
    } finally {
      setVideoAnalyzeLoading(false);
      setVideoStage("");
    }
  };

  const fetchVideoDashboard = async (fileId: string, savedName: string) => {
    setVideoDashboardLoading((prev) => ({ ...prev, [fileId]: true }));
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${apiBaseUrl}/video/dashboard?filename=${encodeURIComponent(savedName)}`);
      if (response.ok) {
        const data = await response.json();
        setVideoDashboards((prev) => ({
          ...prev,
          [fileId]: data
        }));
      }
    } catch (err) {
      console.error("Failed to load video dashboard:", err);
    } finally {
      setVideoDashboardLoading((prev) => ({ ...prev, [fileId]: false }));
    }
  };

  useEffect(() => {
    if (activeFileId) {
      const file = selectedFiles.find((f) => f.id === activeFileId);
      if (file && isVideoFile(file) && file.savedName) {
        fetchVideoDashboard(file.id, file.savedName);
      }
    }
  }, [activeFileId, selectedFiles]);

  const triggerTranscription = async (savedName: string) => {
    if (!activeFileId || transcribeLoading) return;
    setTranscribeLoading(true);
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${apiBaseUrl}/audio/transcribe`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ filename: savedName }),
      });
      if (response.ok) {
        const data = await response.json();
        setTranscribeResults((prev) => ({
          ...prev,
          [activeFileId]: data.transcript,
        }));
        setTranscribeMetrics((prev) => ({
          ...prev,
          [activeFileId]: {
            detected_language: data.detected_language,
            duration: data.duration,
            processing_time: data.processing_time,
            word_count: data.word_count
          }
        }));
        setTranscribeChunks((prev) => ({
          ...prev,
          [activeFileId]: data.chunks || []
        }));
        // Initialize chat history for this audio file
        setAudioChatHistories((prev) => ({
          ...prev,
          [activeFileId]: [
            { role: "assistant", content: "Hello! I have transcribed and indexed this audio. Ask me anything about the transcript." }
          ]
        }));
      } else {
        alert("Failed to transcribe audio. Please verify model service status.");
      }
    } catch {
      alert("Error contacting the audio transcription service.");
    } finally {
      setTranscribeLoading(false);
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

  const handleSendAudioMessage = async () => {
    if (!activeFileId || !audioChatInput.trim() || audioChatLoading) return;

    const targetFile = selectedFiles.find((f) => f.id === activeFileId);
    if (!targetFile) return;

    const userMessageContent = audioChatInput.trim();
    setAudioChatInput("");

    const userMessage: PDFChatMessage = { role: "user", content: userMessageContent };
    const currentHistory = audioChatHistories[activeFileId] || [];

    setAudioChatHistories((prev) => ({
      ...prev,
      [activeFileId]: [...(prev[activeFileId] || []), userMessage]
    }));

    setAudioChatLoading(true);

    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${apiBaseUrl}/audio/chat`, {
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

        setAudioChatHistories((prev) => ({
          ...prev,
          [activeFileId]: [...(prev[activeFileId] || []), assistantMessage]
        }));
      } else {
        const errJson = await response.json();
        const errMsg = errJson.detail || "Failed to process RAG chat response.";
        alert(`RAG Error: ${errMsg}`);
      }
    } catch {
      alert("Error contacting the Audio chat RAG service. Make sure Ollama LLM is running locally.");
    } finally {
      setAudioChatLoading(false);
    }
  };

  const handleSendVideoMessage = async (retryMessageContent?: string) => {
    if (!activeFileId || videoChatLoading) return;

    const targetFile = selectedFiles.find((f) => f.id === activeFileId);
    if (!targetFile) return;

    const userMessageContent = retryMessageContent !== undefined ? retryMessageContent : videoChatInput.trim();
    if (!userMessageContent) return;
    
    if (retryMessageContent === undefined) {
      setVideoChatInput("");
    }

    const userMessage: VideoChatMessage = { role: "user", content: userMessageContent };
    
    // Get history excluding any errors
    let currentHistory = videoChatHistories[activeFileId] || [];
    if (retryMessageContent !== undefined) {
      // If retrying, remove the last assistant error message if it exists
      const lastMsg = currentHistory[currentHistory.length - 1];
      if (lastMsg && lastMsg.role === "assistant" && lastMsg.error) {
        currentHistory = currentHistory.slice(0, -1);
      }
    } else {
      currentHistory = [...currentHistory, userMessage];
    }

    setVideoChatHistories((prev) => ({
      ...prev,
      [activeFileId]: currentHistory
    }));

    setVideoChatLoading(true);

    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const response = await fetch(`${apiBaseUrl}/video/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          filename: targetFile.savedName || targetFile.name,
          question: userMessageContent,
          history: currentHistory
            .filter((m) => !m.error)
            .map((m) => ({ role: m.role, content: m.content }))
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const assistantMessage: VideoChatMessage = {
          role: "assistant",
          content: data.answer,
          sources: data.sources
        };

        setVideoChatHistories((prev) => ({
          ...prev,
          [activeFileId]: [...(prev[activeFileId] || []), assistantMessage]
        }));
      } else {
        const errJson = await response.json().catch(() => ({}));
        const errMsg = errJson.detail || "Failed to process Video Chat response.";
        const assistantMessage: VideoChatMessage = {
          role: "assistant",
          content: errMsg,
          error: true
        };
        setVideoChatHistories((prev) => ({
          ...prev,
          [activeFileId]: [...(prev[activeFileId] || []), assistantMessage]
        }));
      }
    } catch {
      const assistantMessage: VideoChatMessage = {
        role: "assistant",
        content: "Unable to contact Video AI.",
        error: true
      };
      setVideoChatHistories((prev) => ({
        ...prev,
        [activeFileId]: [...(prev[activeFileId] || []), assistantMessage]
      }));
    } finally {
      setVideoChatLoading(false);
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
    setTranscribeResults({});
    setTranscribeMetrics({});
    setTranscribeChunks({});
    setTranscriptSearch("");
    setAudioChatHistories({});
    setVideoIndexResults({});
    setVideoAnalyzeLoading(false);
    setVideoStage("");
    setVideoDurations({});
    setVideoDashboards({});
    setVideoDashboardLoading({});
    setActiveDashboardTabs({});
    setVideoTranscriptSearch("");
    setSelectedKeyframe(null);
    setVideoChatHistories({});
    setVideoChatInput("");
    setVideoChatLoading(false);
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
      description: "MP3, WAV, M4A, OGG, MP4",
      extensions: ".mp3, .wav, .m4a, .ogg, .mp4",
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

      {/* Workspace Tabs */}
      <div className="flex border-b border-slate-200 dark:border-zinc-800/80 gap-6">
        <button
          onClick={() => setActiveWorkspaceTab("upload")}
          className={`pb-3 text-sm font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-2 ${
            activeWorkspaceTab === "upload"
              ? "border-indigo-500 text-indigo-650 dark:text-indigo-400 dark:border-indigo-400 font-bold"
              : "border-transparent text-slate-400 dark:text-zinc-500 hover:text-slate-600 dark:hover:text-zinc-300"
          }`}
        >
          <UploadCloud className="h-4 w-4" />
          <span>Upload File</span>
        </button>
        <button
          onClick={() => setActiveWorkspaceTab("search")}
          className={`pb-3 text-sm font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-2 ${
            activeWorkspaceTab === "search"
              ? "border-indigo-500 text-indigo-650 dark:text-indigo-400 dark:border-indigo-400 font-bold"
              : "border-transparent text-slate-400 dark:text-zinc-500 hover:text-slate-600 dark:hover:text-zinc-300"
          }`}
        >
          <Globe className="h-4 w-4" />
          <span>Search from Web</span>
        </button>
      </div>

      {activeWorkspaceTab === "upload" ? (
        activeFileId && selectedFiles.find(f => f.id === activeFileId && isVideoFile(f)) && videoDashboardLoading[activeFileId] ? (
        /* Video Intelligence Dashboard Skeleton Loader */
        <div className="border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20 rounded-3xl p-6 md:p-8 shadow-md flex flex-col space-y-6 animate-pulse">
          {/* Header Skeleton */}
          <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-zinc-800/50">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 bg-slate-250 dark:bg-zinc-800 rounded-xl" />
              <div className="space-y-2">
                <div className="h-4 w-48 bg-slate-250 dark:bg-zinc-800 rounded-md" />
                <div className="h-3 w-32 bg-slate-250 dark:bg-zinc-800 rounded-md" />
              </div>
            </div>
            <div className="h-8 w-28 bg-slate-250 dark:bg-zinc-800 rounded-xl" />
          </div>
          {/* Grid Skeleton */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            <div className="lg:col-span-5 space-y-4">
              <div className="aspect-video w-full bg-slate-250 dark:bg-zinc-800 rounded-2xl" />
              <div className="h-20 w-full bg-slate-250 dark:bg-zinc-800 rounded-2xl" />
            </div>
            <div className="lg:col-span-7 h-[400px] bg-slate-200/50 dark:bg-zinc-950/20 border border-slate-250 dark:border-zinc-800 rounded-2xl p-5 flex flex-col space-y-4">
              <div className="flex gap-2 pb-2 border-b border-slate-200 dark:border-zinc-800/80">
                <div className="h-8 w-20 bg-slate-250 dark:bg-zinc-800 rounded-xl" />
                <div className="h-8 w-24 bg-slate-250 dark:bg-zinc-800 rounded-xl" />
                <div className="h-8 w-20 bg-slate-250 dark:bg-zinc-800 rounded-xl" />
              </div>
              <div className="flex-1 space-y-3">
                <div className="h-4 w-full bg-slate-250 dark:bg-zinc-800 rounded-md" />
                <div className="h-4 w-5/6 bg-slate-250 dark:bg-zinc-800 rounded-md" />
                <div className="h-4 w-4/5 bg-slate-250 dark:bg-zinc-800 rounded-md" />
              </div>
            </div>
          </div>
        </div>
      ) : activeFileId && selectedFiles.find(f => f.id === activeFileId && isVideoFile(f)) && videoDashboards[activeFileId] ? (
        /* Video Intelligence Dashboard split view */
        (() => {
          const dashboard = videoDashboards[activeFileId];
          const activeTab = activeDashboardTabs[activeFileId] || "overview";
          const setActiveTab = (tab: "overview" | "transcript" | "timeline" | "keyframes" | "chat") => {
            setActiveDashboardTabs(prev => ({ ...prev, [activeFileId]: tab }));
          };
          
          const getFrameUrl = (filename: string) => {
            const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
            const backendRootUrl = apiBaseUrl.replace("/api/v1", "");
            const file = selectedFiles.find(f => f.id === activeFileId);
            if (!file?.savedName) return "";
            const videoId = file.savedName.replace(/\.[^/.]+$/, "");
            return `${backendRootUrl}/uploads/vector_store/video/${videoId}/frames/${filename}`;
          };

          const seekVideo = (time: number) => {
            if (videoRef.current) {
              videoRef.current.currentTime = time;
              videoRef.current.play().catch(() => {});
            }
          };

          const timelineTranscript = dashboard.timeline ? dashboard.timeline.filter(e => e.type === "speech") : [];
          
          return (
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              className="border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20 rounded-3xl p-6 md:p-8 shadow-md flex flex-col space-y-6 animate-fade-in"
            >
              {/* Header */}
              <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-zinc-800/50">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-amber-500/10 flex items-center justify-center border border-amber-500/20">
                    <Film className="h-5 w-5 text-amber-500" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h2 className="text-base font-bold tracking-tight text-slate-800 dark:text-zinc-100">Video Intelligence Dashboard</h2>
                      <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                        ✓ Analyzed
                      </div>
                    </div>
                    <p className="text-xs text-slate-405 dark:text-zinc-500 truncate max-w-[200px] sm:max-w-xs md:max-w-md">
                      {dashboard.filename}
                    </p>
                  </div>
                </div>
                
                <button
                  onClick={() => setActiveFileId(null)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-zinc-800 hover:bg-slate-100 dark:hover:bg-zinc-800 text-slate-500 dark:text-zinc-400 text-xs font-semibold transition-all cursor-pointer"
                >
                  <X className="h-3.5 w-3.5" />
                  <span>Close Dashboard</span>
                </button>
              </div>

              {/* Grid content */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                {/* Left side: Video Player */}
                <div className="lg:col-span-5 flex flex-col space-y-4">
                  <div className="relative rounded-2xl overflow-hidden bg-black border border-slate-100 dark:border-zinc-855 shadow-md">
                    <video
                      ref={videoRef}
                      src={`${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace("/api/v1", "")}/uploads/audio/${selectedFiles.find((f) => f.id === activeFileId)?.savedName}`}
                      controls
                      className="w-full max-h-[340px] object-contain focus:outline-none"
                    />
                  </div>
                  
                  {/* Resolution, duration metadata card */}
                  <div className="p-4 rounded-2xl bg-slate-50/50 dark:bg-zinc-950/20 border border-slate-100 dark:border-zinc-850 space-y-2">
                    <h4 className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase tracking-wider">Video Details</h4>
                    <div className="grid grid-cols-2 gap-3 text-xs text-slate-650 dark:text-zinc-400">
                      <div>Resolution: <span className="font-semibold text-slate-800 dark:text-zinc-200">{dashboard.width} x {dashboard.height}</span></div>
                      <div>FPS: <span className="font-semibold text-slate-800 dark:text-zinc-200">{dashboard.fps}</span></div>
                      <div>Codec: <span className="font-semibold text-slate-800 dark:text-zinc-200 uppercase">{dashboard.codec || "unknown"}</span></div>
                      <div>Duration: <span className="font-semibold text-slate-800 dark:text-zinc-200">{formatTime(dashboard.duration)}</span></div>
                    </div>
                  </div>
                </div>

                {/* Right side: Tabs */}
                <div className="lg:col-span-7 flex flex-col min-h-[460px] border border-slate-100 dark:border-zinc-800/60 rounded-2xl bg-slate-50/50 dark:bg-zinc-950/20 p-5 shadow-inner">
                  {/* Tab switches */}
                  <div className="flex border-b border-slate-200 dark:border-zinc-800/80 pb-2 mb-4 overflow-x-auto gap-2">
                    {[
                      { id: "overview", label: "Overview", icon: Info },
                      { id: "transcript", label: "Transcript", icon: FileText },
                      { id: "timeline", label: "Timeline", icon: Film },
                      { id: "keyframes", label: "Key Frames", icon: ImageIcon },
                      { id: "chat", label: "Chat", icon: Sparkles }
                    ].map(t => {
                      const Icon = t.icon;
                      const isActive = activeTab === t.id;
                      return (
                        <button
                          key={t.id}
                          onClick={() => setActiveTab(t.id as "overview" | "transcript" | "timeline" | "keyframes" | "chat")}
                          className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition-all border-0 cursor-pointer ${
                            isActive
                              ? "bg-amber-500 text-white shadow-md shadow-amber-500/15"
                              : "text-slate-405 hover:text-slate-700 dark:text-zinc-500 dark:hover:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-900/50"
                          }`}
                        >
                          <Icon className="h-3.5 w-3.5" />
                          <span>{t.label}</span>
                        </button>
                      );
                    })}
                  </div>

                  {/* Tab View Content */}
                  <div className="flex-1 flex flex-col min-h-0">
                    {/* 1. Overview Tab */}
                    {activeTab === "overview" && (
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 animate-fade-in">
                        {[
                          { label: "File Name", value: dashboard.filename, subtitle: "Raw Video File", isLong: true },
                          { label: "Duration", value: formatTime(dashboard.duration), subtitle: "Timeline Bounds" },
                          { label: "Resolution", value: `${dashboard.width} x ${dashboard.height}`, subtitle: "Visual Scale" },
                          { label: "Key Frames", value: dashboard.frames ? dashboard.frames.length.toString() : "0", subtitle: "Florence-2 Extracts" },
                          { label: "Transcript Words", value: dashboard.transcript ? dashboard.transcript.split(/\s+/).filter(Boolean).length.toString() : "0", subtitle: "Whisper Segments" },
                          { label: "Semantic Chunks", value: dashboard.total_chunks ? dashboard.total_chunks.toString() : "0", subtitle: "FAISS Vectors" },
                          { label: "Processing Speed", value: `${dashboard.processing_time}s`, subtitle: "GPU Compute Time" }
                        ].map((stat, idx) => (
                          <div
                            key={idx}
                            className={`p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200/60 dark:border-zinc-800 shadow-sm space-y-1.5 ${
                              stat.isLong ? "col-span-2 md:col-span-3" : ""
                            }`}
                          >
                            <p className="text-[10px] font-bold text-slate-400 dark:text-zinc-550 uppercase tracking-wider">{stat.label}</p>
                            <p className="text-sm font-extrabold text-slate-855 dark:text-zinc-100 truncate">{stat.value}</p>
                            <p className="text-[9px] text-slate-400 dark:text-zinc-550">{stat.subtitle}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 2. Transcript Tab */}
                    {activeTab === "transcript" && (
                      <div className="flex-1 flex flex-col min-h-0 space-y-4 animate-fade-in">
                        {/* Search bar */}
                        <div className="relative">
                          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                          <input
                            type="text"
                            value={videoTranscriptSearch}
                            onChange={(e) => setVideoTranscriptSearch(e.target.value)}
                            placeholder="Search transcript segment..."
                            className="w-full pl-9 pr-4 py-2 text-xs border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-500/30 transition-all"
                          />
                        </div>

                        {/* List of segments */}
                        {timelineTranscript.length > 0 ? (
                          <div className="flex-1 max-h-[300px] overflow-y-auto space-y-2.5 pr-1 text-xs">
                            {timelineTranscript
                              .filter(segment =>
                                segment.content.toLowerCase().includes(videoTranscriptSearch.toLowerCase())
                              )
                              .map((segment, idx) => (
                                <div
                                  key={idx}
                                  className="flex gap-3 p-3 rounded-2xl border border-slate-100 dark:border-zinc-855 bg-white dark:bg-zinc-900 hover:border-amber-500/30 dark:hover:border-amber-500/20 transition-all group"
                                >
                                  <button
                                    onClick={() => seekVideo(segment.timestamp)}
                                    className="px-2 py-1 h-fit rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold border-0 hover:bg-emerald-500/20 transition-all shrink-0 cursor-pointer text-[10px]"
                                  >
                                    {formatTime(segment.timestamp)}
                                  </button>
                                  <div className="text-slate-705 dark:text-zinc-300 leading-relaxed pt-0.5">
                                    {highlightVideoText(segment.content, videoTranscriptSearch)}
                                  </div>
                                </div>
                              ))}
                          </div>
                        ) : (
                          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-slate-400 dark:text-zinc-500">
                            <FileText className="h-8 w-8 mb-2 text-slate-300" />
                            <p className="text-xs font-semibold">No transcript generated for this video</p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* 3. Timeline Tab */}
                    {activeTab === "timeline" && (
                      <div className="flex-1 flex flex-col min-h-0 animate-fade-in">
                        {dashboard.timeline && dashboard.timeline.length > 0 ? (
                          <div className="flex-1 max-h-[340px] overflow-y-auto space-y-3.5 pr-1 pl-2 border-l border-slate-200 dark:border-zinc-800 text-xs">
                            {dashboard.timeline.map((event, idx) => {
                              const isVision = event.type === "vision";
                              return (
                                <div key={idx} className="relative flex gap-3 group">
                                  {/* Bullet point on border line */}
                                  <div className={`absolute -left-[14px] top-1.5 h-2 w-2 rounded-full border-2 bg-white dark:bg-zinc-900 ${
                                    isVision ? "border-amber-500" : "border-emerald-500"
                                  }`} />
                                  
                                  {/* Timestamp trigger */}
                                  <button
                                    onClick={() => seekVideo(event.timestamp)}
                                    className={`px-2 py-0.5 h-fit rounded-md text-[10px] font-bold border-0 transition-all shrink-0 cursor-pointer ${
                                      isVision
                                        ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 hover:bg-amber-500/20"
                                        : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20"
                                    }`}
                                  >
                                    {formatTime(event.timestamp)}
                                  </button>

                                  <div className="flex-1 bg-white dark:bg-zinc-900 p-2.5 rounded-xl border border-slate-100 dark:border-zinc-850 hover:border-slate-200 dark:hover:border-zinc-800 transition-all">
                                    <span className={`inline-flex items-center px-1.5 py-0.2 rounded text-[8px] font-extrabold uppercase mr-1.5 ${
                                      isVision
                                        ? "bg-amber-500/10 text-amber-500"
                                        : "bg-emerald-500/10 text-emerald-500"
                                    }`}>
                                      {event.type}
                                    </span>
                                    <span className="text-slate-705 dark:text-zinc-300 leading-relaxed font-medium">
                                      {event.content}
                                    </span>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-slate-400 dark:text-zinc-500">
                            <Film className="h-8 w-8 mb-2 text-slate-300" />
                            <p className="text-xs font-semibold">No timeline events found</p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* 4. Key Frames Tab */}
                    {activeTab === "keyframes" && (
                      <div className="flex-1 flex flex-col min-h-0 animate-fade-in">
                        {dashboard.frames && dashboard.frames.length > 0 ? (
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3.5 overflow-y-auto max-h-[340px] pr-1">
                            {dashboard.frames.map((frame, idx) => (
                              <div
                                key={idx}
                                onClick={() => {
                                  seekVideo(frame.timestamp);
                                  setSelectedKeyframe(frame);
                                }}
                                className="group relative rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 shadow-sm cursor-pointer hover:border-amber-500/40 hover:-translate-y-0.5 transition-all flex flex-col"
                              >
                                {/* Frame Thumbnail */}
                                <div className="relative aspect-video w-full overflow-hidden bg-slate-900">
                                  <img
                                    src={getFrameUrl(frame.filename)}
                                    alt={`Frame ${frame.frame_number}`}
                                    className="h-full w-full object-cover group-hover:scale-105 transition-all"
                                  />
                                  <div className="absolute bottom-1.5 right-1.5 px-1.5 py-0.5 bg-black/65 backdrop-blur-sm rounded text-[9px] font-bold text-white">
                                    {formatTime(frame.timestamp)}
                                  </div>
                                </div>
                                {/* Frame Caption details */}
                                <div className="p-2 flex-1">
                                  <p className="text-[10px] text-slate-700 dark:text-zinc-300 font-semibold line-clamp-2 leading-relaxed">
                                    {frame.caption}
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-slate-400 dark:text-zinc-500">
                            <ImageIcon className="h-8 w-8 mb-2 text-slate-300" />
                            <p className="text-xs font-semibold">No keyframes extracted</p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* 5. Chat Tab */}
                    {activeTab === "chat" && (
                      <div className="flex-1 flex flex-col min-h-0 space-y-4 animate-fade-in">
                        {/* Conversation Area */}
                        <div
                          ref={videoChatScrollRef}
                          className="flex-1 overflow-y-auto space-y-3.5 pr-1 text-xs max-h-[300px]"
                        >
                          {/* Initial message */}
                          <div className="flex flex-col space-y-1">
                            <span className="font-extrabold text-amber-500 flex items-center gap-1">
                              🤖 VisionGPT
                            </span>
                            <div className="p-3.5 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200/60 dark:border-zinc-800 leading-relaxed text-slate-700 dark:text-zinc-300">
                              Hello! Ask me anything about this video.
                            </div>
                          </div>

                          {(videoChatHistories[activeFileId] || []).map((msg, index) => {
                            const isUser = msg.role === "user";
                            return (
                              <div key={index} className="flex flex-col space-y-1">
                                <span className={`font-extrabold flex items-center gap-1 ${
                                  isUser ? "text-indigo-500" : "text-amber-500"
                                }`}>
                                  {isUser ? "👤 User" : "🤖 VisionGPT"}
                                </span>
                                <div className={`p-3.5 rounded-2xl border leading-relaxed text-slate-750 dark:text-zinc-350 ${
                                  isUser
                                    ? "bg-indigo-500/5 border-indigo-500/10 dark:border-indigo-500/15"
                                    : msg.error
                                      ? "bg-red-500/5 border-red-500/20 text-red-650 dark:text-red-400"
                                      : "bg-white dark:bg-zinc-900 border-slate-200/60 dark:border-zinc-800"
                                }`}>
                                  <div className="whitespace-pre-wrap">{msg.content}</div>

                                  {/* Referenced sources timeline citation links */}
                                  {!isUser && msg.sources && msg.sources.length > 0 && (
                                    <div className="mt-3.5 pt-3 border-t border-slate-100 dark:border-zinc-800/80 space-y-2">
                                      <p className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase tracking-wider">
                                        Referenced Timeline
                                      </p>
                                      <div className="flex flex-wrap gap-2">
                                        {msg.sources.map((source, sIdx) => (
                                          <button
                                            key={sIdx}
                                            onClick={() => seekVideo(source.start_time)}
                                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:hover:bg-zinc-700 text-[10px] font-bold text-slate-650 dark:text-zinc-300 transition-all border-0 cursor-pointer"
                                          >
                                            {formatTime(source.start_time)} → {formatTime(source.end_time)}
                                          </button>
                                        ))}
                                      </div>
                                    </div>
                                  )}

                                  {/* Retry button for errors */}
                                  {!isUser && msg.error && (
                                    <div className="mt-2 flex">
                                      <button
                                        onClick={() => {
                                          const history = videoChatHistories[activeFileId] || [];
                                          const userMsgs = history.filter((m) => m.role === "user");
                                          if (userMsgs.length > 0) {
                                            const lastUserContent = userMsgs[userMsgs.length - 1].content;
                                            handleSendVideoMessage(lastUserContent);
                                          }
                                        }}
                                        className="px-3.5 py-1.5 rounded-xl bg-red-500 hover:bg-red-655 text-white font-bold text-[10px] border-0 transition-all cursor-pointer"
                                      >
                                        Retry Request
                                      </button>
                                    </div>
                                  )}
                                </div>
                              </div>
                            );
                          })}

                          {/* Loading indicator */}
                          {videoChatLoading && (
                            <div className="flex flex-col space-y-1 animate-pulse">
                              <span className="font-extrabold text-amber-500">🤖 VisionGPT</span>
                              <div className="p-3.5 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200/60 dark:border-zinc-800 text-slate-400 dark:text-zinc-500 flex items-center gap-2">
                                <div className="h-2 w-2 animate-bounce rounded-full bg-amber-500" />
                                <div className="h-2 w-2 animate-bounce rounded-full bg-amber-500 [animation-delay:0.2s]" />
                                <div className="h-2 w-2 animate-bounce rounded-full bg-amber-500 [animation-delay:0.4s]" />
                                <span className="ml-1 text-[11px] font-semibold text-slate-500 dark:text-zinc-400">
                                  VisionGPT is analyzing the video...
                                </span>
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Input Box Area */}
                        <div className="flex gap-2 pt-2 border-t border-slate-200 dark:border-zinc-800/80 shrink-0">
                          <textarea
                            value={videoChatInput}
                            onChange={(e) => setVideoChatInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                if (!videoChatLoading && videoChatInput.trim()) {
                                  handleSendVideoMessage();
                                }
                              }
                            }}
                            placeholder="Ask anything about this video..."
                            disabled={videoChatLoading}
                            rows={1}
                            className="flex-1 px-3.5 py-2.5 rounded-xl text-xs border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-amber-500/30 disabled:opacity-60 transition-all resize-none max-h-20"
                          />
                          <button
                            onClick={() => handleSendVideoMessage()}
                            disabled={videoChatLoading || !videoChatInput.trim()}
                            className="px-4.5 py-2 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-[11px] font-bold shadow-md hover:shadow-orange-500/20 hover:shadow-lg transition-all shrink-0 flex items-center justify-center cursor-pointer border-0"
                          >
                            Send
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Lightbox enlarge modal for Keyframe */}
              <AnimatePresence>
                {selectedKeyframe && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
                    onClick={() => setSelectedKeyframe(null)}
                  >
                    <motion.div
                      initial={{ scale: 0.95, y: 15 }}
                      animate={{ scale: 1, y: 0 }}
                      exit={{ scale: 0.95, y: 15 }}
                      transition={{ type: "spring", duration: 0.4 }}
                      onClick={(e) => e.stopPropagation()}
                      className="relative max-w-2xl w-full rounded-3xl border border-slate-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6 shadow-2xl flex flex-col gap-4 overflow-hidden"
                    >
                      {/* Close Button */}
                      <button
                        onClick={() => setSelectedKeyframe(null)}
                        className="absolute top-4 right-4 p-1.5 rounded-xl border border-slate-200 dark:border-zinc-800 hover:bg-slate-100 dark:hover:bg-zinc-800 text-slate-500 dark:text-zinc-400 z-10 transition-colors cursor-pointer"
                      >
                        <X className="h-4 w-4" />
                      </button>

                      <div className="flex items-center justify-between pr-10">
                        <div className="min-w-0">
                          <h3 className="text-sm font-bold text-slate-805 dark:text-zinc-200">
                            Keyframe Frame #{selectedKeyframe.frame_number}
                          </h3>
                          <p className="text-[10px] text-amber-550 font-semibold">
                            Timestamp: {formatTime(selectedKeyframe.timestamp)}
                          </p>
                        </div>
                      </div>

                      <div className="relative rounded-2xl overflow-hidden bg-slate-900 border border-slate-150 dark:border-zinc-900 flex items-center justify-center max-h-[50vh]">
                        <img
                          src={getFrameUrl(selectedKeyframe.filename)}
                          alt={`Enlarged Frame ${selectedKeyframe.frame_number}`}
                          className="max-h-[45vh] max-w-full object-contain"
                        />
                      </div>

                      <div className="p-3 bg-slate-50 dark:bg-zinc-955/40 border border-slate-150 dark:border-zinc-850 rounded-2xl">
                        <p className="text-[10px] font-bold text-slate-400 dark:text-zinc-550 uppercase tracking-wider mb-1">Florence Caption</p>
                        <p className="text-xs text-slate-705 dark:text-zinc-300 leading-relaxed font-semibold">
                          {selectedKeyframe.caption}
                        </p>
                      </div>
                    </motion.div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })()
      ) : (
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
            className={`relative rounded-3xl border-2 border-dashed p-10 md:p-12 transition-all duration-300 flex flex-col items-center justify-center text-center group ${isUploading ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-slate-300 dark:hover:border-zinc-700 hover:bg-slate-50/50 dark:hover:bg-zinc-900/30"
              } ${isDragActive && !isUploading
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
              <div className={`h-16 w-16 rounded-2xl bg-slate-50 dark:bg-zinc-900 border border-slate-100 dark:border-zinc-800 flex items-center justify-center shadow-sm transition-all duration-300 group-hover:scale-110 group-hover:border-violet-500/30 ${isDragActive && !isUploading ? "border-violet-500/30 text-violet-500 bg-violet-50/20" : "text-slate-400"
                }`}>
                <UploadCloud className={`h-8 w-8 transition-transform duration-300 ${isDragActive && !isUploading ? "scale-110 text-violet-500" : "group-hover:-translate-y-1"
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
                className={`relative inline-flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-semibold text-white bg-gradient-to-tr from-violet-650 to-indigo-500 shadow-md shadow-violet-650/20 hover:shadow-lg hover:shadow-violet-650/25 transition-all transform active:scale-95 ${isUploading ? "opacity-50 cursor-not-allowed active:scale-100" : "cursor-pointer"
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
                  className={`text-[10px] font-medium hover:underline transition-colors ${isUploading ? "text-slate-400 cursor-not-allowed" : "text-red-500 hover:text-red-650"
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
                                className={`px-2.5 py-0.5 rounded-md text-[9px] font-bold shadow-sm transition-all transform active:scale-95 cursor-pointer disabled:cursor-not-allowed ${activeFileId === file.id
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
                                className={`px-2.5 py-0.5 rounded-md text-[9px] font-bold shadow-sm transition-all transform active:scale-95 cursor-pointer ${activeFileId === file.id
                                  ? "bg-red-650 text-white"
                                  : "bg-slate-200/80 hover:bg-slate-300/85 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300"
                                  }`}
                              >
                                {activeFileId === file.id ? "Viewing Info" : "Preview"}
                              </button>
                            )}
                            {isAudioFile(file) && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setActiveFileId(file.id);
                                }}
                                className={`px-2.5 py-0.5 rounded-md text-[9px] font-bold shadow-sm transition-all transform active:scale-95 cursor-pointer ${activeFileId === file.id
                                  ? "bg-emerald-600 text-white"
                                  : "bg-slate-200/80 hover:bg-slate-350/80 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300"
                                  }`}
                              >
                                {activeFileId === file.id ? "Viewing Audio" : "Preview"}
                              </button>
                            )}
                            {isVideoFile(file) && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setActiveFileId(file.id);
                                }}
                                className={`px-2.5 py-0.5 rounded-md text-[9px] font-bold shadow-sm transition-all transform active:scale-95 cursor-pointer ${activeFileId === file.id
                                  ? "bg-amber-600 text-white"
                                  : "bg-slate-200/80 hover:bg-slate-350/80 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-slate-700 dark:text-zinc-300"
                                  }`}
                              >
                                {activeFileId === file.id ? "Viewing Video" : "Preview"}
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
                        className={`flex-1 pb-2 text-xs font-bold text-center border-b-2 transition-colors cursor-pointer ${activePdfTab === "chat"
                          ? "border-red-500 text-slate-800 dark:text-zinc-150"
                          : "border-transparent text-slate-400 dark:text-zinc-500"
                          }`}
                      >
                        Ask Document
                      </button>
                      <button
                        onClick={() => setActivePdfTab("chunks")}
                        className={`flex-1 pb-2 text-xs font-bold text-center border-b-2 transition-colors cursor-pointer ${activePdfTab === "chunks"
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
                            <p className={`text-[11px] leading-relaxed text-slate-600 dark:text-zinc-350 ${isExpanded ? "whitespace-pre-wrap font-mono text-[10px] bg-slate-100/50 dark:bg-zinc-955/50 p-2 rounded-xl border border-slate-200/30 dark:border-zinc-900/30" : "truncate"
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
                                className={`max-w-[85%] rounded-2xl px-3 py-2 shadow-sm leading-relaxed whitespace-pre-wrap break-words ${isUser
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

          {/* Audio Preview Card Display */}
          {activeFileId && selectedFiles.find((f) => f.id === activeFileId && isAudioFile(f)) && (
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                className="border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20 rounded-3xl p-6 shadow-sm space-y-5 flex flex-col animate-fade-in"
              >
                {/* Header */}
                <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-zinc-800/50">
                  <div className="min-w-0">
                    <h2 className="text-xs font-bold tracking-tight uppercase text-slate-500 dark:text-zinc-400">Audio Intelligence</h2>
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

                {/* Audio Details / Player Cover */}
                <div className="flex flex-col items-center justify-center p-4 border border-slate-100 dark:border-zinc-855 bg-slate-50/50 dark:bg-zinc-950/40 rounded-2xl text-center space-y-3">
                  <div className="h-12 w-12 rounded-2xl bg-emerald-500/10 dark:bg-emerald-400/10 flex items-center justify-center border border-emerald-500/20 shrink-0">
                    <Music className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
                  </div>

                  <div className="space-y-0.5 w-full px-2">
                    <h3 className="text-xs font-bold truncate max-w-full text-slate-800 dark:text-zinc-200">
                      {selectedFiles.find((f) => f.id === activeFileId)?.name}
                    </h3>
                    <p className="text-[9px] text-slate-400 dark:text-zinc-500">
                      Size: {formatBytes(selectedFiles.find((f) => f.id === activeFileId)?.size || 0)}
                    </p>
                  </div>

                  {/* HTML5 Audio/Video Player */}
                  {selectedFiles.find((f) => f.id === activeFileId)?.savedName && (
                    selectedFiles.find((f) => f.id === activeFileId)?.name.toLowerCase().endsWith(".mp4") ? (
                      <video
                        ref={videoRef}
                        src={`${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace("/api/v1", "")}/uploads/audio/${selectedFiles.find((f) => f.id === activeFileId)?.savedName}`}
                        controls
                        className="w-full max-h-36 rounded-xl mt-1 bg-black focus:outline-none"
                      />
                    ) : (
                      <audio
                        ref={audioRef}
                        src={`${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace("/api/v1", "")}/uploads/audio/${selectedFiles.find((f) => f.id === activeFileId)?.savedName}`}
                        controls
                        className="w-full h-10 mt-1 focus:outline-none"
                      />
                    )
                  )}
                </div>

                {/* Transcription & RAG Chat Layout */}
                {transcribeResults[activeFileId] ? (
                  <div className="flex-1 flex flex-col min-h-0 space-y-4">
                    {/* Metrics Grid */}
                    {transcribeMetrics[activeFileId] && (
                      <div className="grid grid-cols-4 gap-2 text-center">
                        <div className="p-2 rounded-xl bg-slate-50 dark:bg-zinc-955/40 border border-slate-100 dark:border-zinc-850">
                          <p className="text-[8px] text-slate-400 dark:text-zinc-500 font-medium">Language</p>
                          <p className="text-[10px] font-bold text-slate-700 dark:text-zinc-250 uppercase">{transcribeMetrics[activeFileId].detected_language}</p>
                        </div>
                        <div className="p-2 rounded-xl bg-slate-50 dark:bg-zinc-955/40 border border-slate-100 dark:border-zinc-850">
                          <p className="text-[8px] text-slate-400 dark:text-zinc-500 font-medium">Duration</p>
                          <p className="text-[10px] font-bold text-slate-700 dark:text-zinc-255 text-center">
                            {Math.floor(transcribeMetrics[activeFileId].duration / 60)}:
                            {Math.floor(transcribeMetrics[activeFileId].duration % 60).toString().padStart(2, "0")}
                          </p>
                        </div>
                        <div className="p-2 rounded-xl bg-slate-50 dark:bg-zinc-955/40 border border-slate-100 dark:border-zinc-850">
                          <p className="text-[8px] text-slate-400 dark:text-zinc-500 font-medium">Time Taken</p>
                          <p className="text-[10px] font-bold text-slate-700 dark:text-zinc-255">{transcribeMetrics[activeFileId].processing_time}s</p>
                        </div>
                        <div className="p-2 rounded-xl bg-slate-50 dark:bg-zinc-955/40 border border-slate-100 dark:border-zinc-850">
                          <p className="text-[8px] text-slate-400 dark:text-zinc-500 font-medium">Words</p>
                          <p className="text-[10px] font-bold text-slate-700 dark:text-zinc-255">{transcribeMetrics[activeFileId].word_count}</p>
                        </div>
                      </div>
                    )}

                    {/* Tabs Switcher for Chat with Audio vs Transcript View */}
                    <div className="flex border-b border-slate-100 dark:border-zinc-800">
                      <button
                        onClick={() => setActiveAudioTab("chat")}
                        className={`flex-1 pb-2 text-xs font-bold text-center border-b-2 transition-colors cursor-pointer ${activeAudioTab === "chat"
                          ? "border-emerald-500 text-slate-800 dark:text-zinc-150"
                          : "border-transparent text-slate-400 dark:text-zinc-500"
                          }`}
                      >
                        Chat with Audio
                      </button>
                      <button
                        onClick={() => setActiveAudioTab("transcript")}
                        className={`flex-1 pb-2 text-xs font-bold text-center border-b-2 transition-colors cursor-pointer ${activeAudioTab === "transcript"
                          ? "border-emerald-500 text-slate-800 dark:text-zinc-150"
                          : "border-transparent text-slate-400 dark:text-zinc-500"
                          }`}
                      >
                        View Transcript
                      </button>
                    </div>

                    {/* Tab View Contents */}
                    {activeAudioTab === "transcript" ? (
                      <div className="flex-1 flex flex-col min-h-0 space-y-3">
                        {/* Top Action Bar */}
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold text-slate-550 dark:text-zinc-400 uppercase tracking-wider">Timeline Transcript</span>
                          <div className="flex gap-2">
                            <button
                              onClick={() => {
                                if (transcribeResults[activeFileId]) {
                                  navigator.clipboard.writeText(transcribeResults[activeFileId]);
                                  showToast("Transcript copied successfully.");
                                }
                              }}
                              className="px-2.5 py-1 rounded-lg border border-slate-200 dark:border-zinc-800 text-slate-700 dark:text-zinc-300 bg-white dark:bg-zinc-900 hover:bg-slate-50 text-[10px] font-bold shadow-sm transition-all transform active:scale-95 flex items-center gap-1 cursor-pointer"
                            >
                              <Copy className="h-3 w-3 text-emerald-600" />
                              <span>Copy</span>
                            </button>
                            <button
                              onClick={() => {
                                if (transcribeResults[activeFileId]) {
                                  const element = document.createElement("a");
                                  const file = new Blob([transcribeResults[activeFileId]], { type: "text/plain;charset=utf-8" });
                                  element.href = URL.createObjectURL(file);
                                  const originalName = selectedFiles.find((f) => f.id === activeFileId)?.name || "transcript";
                                  element.download = `${originalName.substring(0, originalName.lastIndexOf('.')) || originalName}_transcript.txt`;
                                  document.body.appendChild(element);
                                  element.click();
                                  document.body.removeChild(element);
                                  showToast("Transcript downloaded successfully.");
                                }
                              }}
                              className="px-2.5 py-1 rounded-lg border border-slate-200 dark:border-zinc-800 text-slate-700 dark:text-zinc-300 bg-white dark:bg-zinc-900 hover:bg-slate-50 text-[10px] font-bold shadow-sm transition-all transform active:scale-95 flex items-center gap-1 cursor-pointer"
                            >
                              <Download className="h-3 w-3 text-emerald-600" />
                              <span>Download</span>
                            </button>
                          </div>
                        </div>

                        {/* Transcript Search Input */}
                        <div className="relative">
                          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400 dark:text-zinc-555" />
                          <input
                            type="text"
                            placeholder="Search transcript..."
                            value={transcriptSearch}
                            onChange={(e) => setTranscriptSearch(e.target.value)}
                            className="w-full pl-8.5 pr-8 py-1.5 rounded-xl text-[10px] border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500/50 transition-all font-sans"
                          />
                          {transcriptSearch && (
                            <button
                              onClick={() => setTranscriptSearch("")}
                              className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-650 cursor-pointer border-0 bg-transparent p-0 flex items-center"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </div>

                        <div className="flex-1 min-h-[140px] max-h-[220px] overflow-y-auto space-y-3 pr-1 text-xs">
                          {(() => {
                            const chunks = transcribeChunks[activeFileId] || [];
                            const filtered = transcriptSearch
                              ? chunks.filter((c) => c.text.toLowerCase().includes(transcriptSearch.toLowerCase()))
                              : chunks;

                            if (transcriptSearch && filtered.length === 0) {
                              return (
                                <div className="text-center p-8 text-slate-400 dark:text-zinc-500 text-[10px] font-semibold bg-slate-50/50 dark:bg-zinc-950/20 rounded-2xl border border-slate-100 dark:border-zinc-900">
                                  No matching segments found for <strong>{transcriptSearch}</strong>
                                </div>
                              );
                            }

                            if (filtered.length > 0) {
                              return filtered.map((chunk) => {
                                const formatTime = (secs: number) => {
                                  const m = Math.floor(secs / 60);
                                  const sec = Math.floor(secs % 60);
                                  return `${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
                                };
                                return (
                                  <div
                                    key={chunk.chunk_id}
                                    onClick={() => {
                                      const player = videoRef.current ?? audioRef.current;

                                      if (player) {
                                        player.currentTime = chunk.start_time;
                                        player.play().catch(() => { });
                                      }
                                    }}
                                    className="flex gap-4 p-3.5 rounded-2xl border border-slate-100 dark:border-zinc-855 bg-slate-50/50 dark:bg-zinc-950/40 hover:bg-emerald-500/[0.03] dark:hover:bg-emerald-500/[0.05] hover:border-emerald-500/20 hover:shadow-sm cursor-pointer select-text transition-all active:scale-[0.99]"
                                  >
                                    <span className="font-mono text-[10px] font-bold text-emerald-600 dark:text-emerald-400 select-none shrink-0 align-top mt-0.5">
                                      {formatTime(chunk.start_time)}
                                    </span>
                                    <p className="text-[11px] leading-relaxed text-slate-600 dark:text-zinc-355 font-sans whitespace-pre-wrap break-words flex-1">
                                      {highlightText(chunk.text, transcriptSearch)}
                                    </p>
                                  </div>
                                );
                              });
                            }

                            return (
                              <div className="p-3.5 rounded-xl border border-slate-150 dark:border-zinc-855 bg-slate-50/50 dark:bg-zinc-950/40 font-mono text-[10px] text-slate-600 dark:text-zinc-350 leading-normal whitespace-pre-wrap break-words">
                                {transcribeResults[activeFileId]}
                              </div>
                            );
                          })()}
                        </div>

                        {/* Action buttons: Copy & Download */}
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(transcribeResults[activeFileId]);
                              showToast("Transcript copied successfully.");
                            }}
                            className="flex-1 py-2 rounded-xl border border-slate-200 dark:border-zinc-800 text-slate-700 dark:text-zinc-300 bg-white dark:bg-zinc-900 hover:bg-slate-50 text-[10px] font-bold shadow-sm transition-all transform active:scale-95 flex items-center justify-center gap-1.5 cursor-pointer border-0"
                          >
                            <Copy className="h-3.5 w-3.5" />
                            <span>Copy Transcript</span>
                          </button>
                          <button
                            onClick={() => {
                              const element = document.createElement("a");
                              const file = new Blob([transcribeResults[activeFileId]], { type: "text/plain;charset=utf-8" });
                              element.href = URL.createObjectURL(file);
                              const originalName = selectedFiles.find((f) => f.id === activeFileId)?.name || "transcript";
                              element.download = `${originalName.substring(0, originalName.lastIndexOf('.')) || originalName}_transcript.txt`;
                              document.body.appendChild(element);
                              element.click();
                              document.body.removeChild(element);
                              showToast("Transcript downloaded successfully.");
                            }}
                            className="flex-1 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-[10px] font-bold shadow-sm transition-all transform active:scale-95 flex items-center justify-center gap-1.5 cursor-pointer border-0"
                          >
                            <Download className="h-3.5 w-3.5" />
                            <span>Download .txt</span>
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Audio Chat Interface View */
                      <div className="flex flex-col flex-1 min-h-0 space-y-3.5">
                        <div
                          ref={audioChatScrollRef}
                          className="flex-1 overflow-y-auto space-y-3.5 pr-1 text-xs scroll-smooth max-h-[280px] min-h-[140px]"
                        >
                          {(audioChatHistories[activeFileId] || []).map((msg, idx) => {
                            const isUser = msg.role === "user";
                            return (
                              <div
                                key={idx}
                                className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
                              >
                                <div
                                  className={`max-w-[85%] shadow-sm leading-relaxed whitespace-pre-wrap break-words ${isUser
                                    ? "bg-gradient-to-br from-emerald-500 to-teal-600 dark:from-emerald-600 dark:to-teal-700 text-white rounded-2xl rounded-tr-none px-4 py-2.5 border-0 select-text"
                                    : "bg-slate-50 dark:bg-zinc-850/60 backdrop-blur-sm text-slate-800 dark:text-zinc-200 rounded-2xl rounded-tl-none border border-slate-100 dark:border-zinc-800/40 px-4 py-2.5 select-text"
                                    }`}
                                >
                                  {msg.content}
                                </div>

                                {/* Sources display */}
                                {!isUser && msg.sources && msg.sources.length > 0 && (
                                  <div className="mt-1 flex flex-wrap gap-1.5 px-1 items-center">
                                    <span className="text-[8px] text-slate-400 dark:text-zinc-500 font-semibold self-center">Sources:</span>
                                    {msg.sources.map((s, sIdx) => {
                                      const formatTime = (secs?: number) => {
                                        if (secs === undefined) return "";
                                        const m = Math.floor(secs / 60);
                                        const sec = Math.floor(secs % 60);
                                        return `${m}:${sec.toString().padStart(2, "0")}`;
                                      };
                                      return (
                                        <span
                                          key={sIdx}
                                          className="inline-flex items-center px-2 py-0.5 rounded-full text-[8px] font-bold bg-slate-100 dark:bg-zinc-800/80 hover:bg-emerald-500/10 dark:hover:bg-emerald-500/15 hover:text-emerald-600 dark:hover:text-emerald-400 text-slate-500 dark:text-zinc-400 border border-slate-200/50 dark:border-zinc-800/50 cursor-default transition-all"
                                        >
                                          {s.chunk_id} {s.start_time !== undefined && s.end_time !== undefined ? `(${formatTime(s.start_time)} - ${formatTime(s.end_time)})` : `(${s.page})`}
                                        </span>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            );
                          })}

                          {/* Typing indicator */}
                          {audioChatLoading && (
                            <div className="flex justify-start">
                              <div className="bg-slate-100 dark:bg-zinc-850/80 backdrop-blur-sm text-slate-500 dark:text-zinc-400 rounded-2xl rounded-tl-none px-4 py-2 border border-slate-200/20 dark:border-zinc-800/20 shadow-sm flex items-center gap-2">
                                <div className="flex gap-1">
                                  <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></span>
                                  <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></span>
                                  <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></span>
                                </div>
                                <span className="text-[9px] font-semibold italic">VisionGPT is typing...</span>
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Input & Clear */}
                        <div className="pt-2 border-t border-slate-100 dark:border-zinc-855 flex gap-2 items-center">
                          <button
                            onClick={() => {
                              setAudioChatHistories((prev) => ({
                                ...prev,
                                [activeFileId]: [
                                  { role: "assistant", content: "Chat cleared. Ask me anything about the transcript!" }
                                ]
                              }));
                            }}
                            className="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 hover:text-red-500 text-slate-600 dark:text-zinc-300 text-[10px] font-bold transition-all shrink-0 cursor-pointer border-0 shadow-sm"
                          >
                            Clear
                          </button>

                          <input
                            value={audioChatInput}
                            onChange={(e) => setAudioChatInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleSendAudioMessage();
                              }
                            }}
                            placeholder="Ask about this audio..."
                            disabled={audioChatLoading}
                            className="flex-1 px-3 py-2.5 rounded-xl text-[11px] border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 disabled:opacity-60 transition-all"
                          />

                          <button
                            onClick={handleSendAudioMessage}
                            disabled={audioChatLoading || !audioChatInput.trim()}
                            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-[10px] font-bold shadow-md hover:shadow-emerald-500/20 hover:shadow-lg transition-all transform active:scale-95 shrink-0 flex items-center justify-center cursor-pointer border-0"
                          >
                            Send
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  /* Action Button: Transcribe Audio */
                  <div className="space-y-2.5">
                    <button
                      onClick={() => {
                        const target = selectedFiles.find((f) => f.id === activeFileId);
                        if (target?.savedName) {
                          triggerTranscription(target.savedName);
                        }
                      }}
                      disabled={transcribeLoading}
                      className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-bold shadow-sm transition-all transform active:scale-95 flex items-center justify-center gap-2 cursor-pointer border-0 disabled:cursor-not-allowed"
                    >
                      {transcribeLoading ? (
                        <>
                          <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                          <span>Transcribing Audio...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-3.5 w-3.5" />
                          <span>Transcribe Audio</span>
                        </>
                      )}
                    </button>
                  </div>
                 )}
               </motion.div>
             )}

          {/* Video Preview Card Display */}
          {activeFileId && selectedFiles.find((f) => f.id === activeFileId && isVideoFile(f)) && (
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              className="border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20 rounded-3xl p-6 shadow-sm space-y-5 flex flex-col animate-fade-in"
            >
              {/* Header */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-zinc-800/50">
                <div className="min-w-0">
                  <h2 className="text-xs font-bold tracking-tight uppercase text-amber-500">Video Intelligence</h2>
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

              {/* Video Details / Player Cover */}
              <div className="flex flex-col items-center justify-center p-4 border border-slate-100 dark:border-zinc-855 bg-slate-50/50 dark:bg-zinc-950/40 rounded-2xl text-center space-y-3">
                <div className="h-12 w-12 rounded-2xl bg-amber-500/10 dark:bg-amber-400/10 flex items-center justify-center border border-amber-500/20 shrink-0">
                  <Film className="h-6 w-6 text-amber-600 dark:text-amber-400" />
                </div>

                <div className="space-y-0.5 w-full px-2">
                  <h3 className="text-xs font-bold truncate max-w-full text-slate-800 dark:text-zinc-200">
                    {selectedFiles.find((f) => f.id === activeFileId)?.name}
                  </h3>
                  <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-0.5 text-[9px] text-slate-400 dark:text-zinc-500">
                    <span>Size: {formatBytes(selectedFiles.find((f) => f.id === activeFileId)?.size || 0)}</span>
                    <span>•</span>
                    <span>
                      Duration: {videoDurations[activeFileId]
                        ? `${Math.floor(videoDurations[activeFileId] / 60)}:${Math.floor(videoDurations[activeFileId] % 60).toString().padStart(2, "0")}`
                        : "Reading metadata..."}
                    </span>
                  </div>
                </div>

                {/* HTML5 Video Player */}
                {selectedFiles.find((f) => f.id === activeFileId)?.savedName && (
                  <video
                    ref={videoRef}
                    src={`${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace("/api/v1", "")}/uploads/audio/${selectedFiles.find((f) => f.id === activeFileId)?.savedName}`}
                    controls
                    onLoadedMetadata={(e) => {
                      const dur = e.currentTarget.duration;
                      if (dur) {
                        setVideoDurations((prev) => ({ ...prev, [activeFileId]: dur }));
                      }
                    }}
                    className="w-full max-h-48 rounded-xl mt-1 bg-black focus:outline-none shadow-md border border-slate-100 dark:border-zinc-800"
                  />
                )}
              </div>

              {/* Indexing status & Action Button */}
              {videoIndexResults[activeFileId] ? (
                <div className="flex-1 flex flex-col min-h-0 space-y-4 animate-fade-in">
                  {/* Status complete banner */}
                  <div className="p-3.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-[10px] space-y-3">
                    <div className="flex items-center gap-2 font-bold text-emerald-600 dark:text-emerald-400">
                      <span>✓ Processing Complete</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-slate-500 dark:text-zinc-450 leading-relaxed">
                      <div>Video ID: <span className="font-semibold text-slate-700 dark:text-zinc-300 truncate block max-w-[100px]">{videoIndexResults[activeFileId].video_id}</span></div>
                      <div>Total Chunks: <span className="font-semibold text-slate-700 dark:text-zinc-300">{videoIndexResults[activeFileId].total_chunks}</span></div>
                      <div>Processing Time: <span className="font-semibold text-slate-700 dark:text-zinc-300">{videoIndexResults[activeFileId].processing_time}s</span></div>
                      <div>FAISS Index: <span className="font-semibold text-slate-700 dark:text-zinc-300">IndexFlatL2 (384)</span></div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {videoAnalyzeLoading ? (
                    <div className="flex flex-col items-center justify-center py-6 space-y-4 bg-slate-50/50 dark:bg-zinc-950/40 border border-slate-100 dark:border-zinc-855 rounded-2xl">
                      <div className="h-8 w-8 animate-spin rounded-full border-3 border-amber-500 border-t-transparent animate-spin" />
                      <div className="space-y-1 text-center">
                        <p className="text-xs font-bold text-slate-700 dark:text-zinc-300">{videoStage}</p>
                        <p className="text-[10px] text-slate-400 dark:text-zinc-500 italic animate-pulse">This may take a moment...</p>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => {
                        const target = selectedFiles.find((f) => f.id === activeFileId);
                        if (target?.savedName) {
                          handleAnalyzeVideo(target.savedName);
                        }
                      }}
                      className="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold shadow-sm transition-all transform active:scale-95 flex items-center justify-center gap-2 cursor-pointer border-0"
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      <span>Analyze Video</span>
                    </button>
                  )}
                </div>
              )}
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
                        className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 shadow-sm leading-relaxed whitespace-pre-wrap break-words ${isUser
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
                    className={`flex items-center gap-3 p-3 rounded-2xl border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20 shadow-sm transition-all ${upload.type.startsWith("image/")
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
      )) : (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          className="border border-slate-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/20 rounded-3xl p-8 md:p-16 flex flex-col items-center justify-center text-center min-h-[450px] shadow-sm w-full space-y-8"
        >
          <div className="space-y-3 flex flex-col items-center max-w-2xl">
            <div className="h-16 w-16 rounded-2xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 flex items-center justify-center border border-indigo-500/20 shadow-sm">
              <Globe className="h-8 w-8 text-indigo-500" />
            </div>
            <div className="space-y-2">
              <h2 className="text-2xl font-extrabold tracking-tight">Search from Web</h2>
              <p className="text-sm text-slate-500 dark:text-zinc-400 leading-relaxed">
                Search online resources and import them into VisionGPT for AI-powered analysis.
              </p>
            </div>
          </div>

          {/* Search Box Container */}
          <div className="w-full max-w-2xl space-y-4">
            <div className="flex gap-2 items-center bg-slate-50 dark:bg-zinc-950 p-2 rounded-2xl border border-slate-200/80 dark:border-zinc-800/80 focus-within:ring-2 focus-within:ring-indigo-500/25 focus-within:border-indigo-500 transition-all shadow-inner">
              <div className="pl-3 text-slate-400">
                <Search className="h-5 w-5" />
              </div>
              <input
                type="text"
                value={webSearchQuery}
                onChange={(e) => setWebSearchQuery(e.target.value)}
                placeholder="Search for any topic..."
                className="flex-1 px-2 py-3 bg-transparent text-sm focus:outline-none text-slate-800 dark:text-zinc-200 placeholder-slate-450 dark:placeholder-zinc-550"
              />
              <button
                type="button"
                className="px-6 py-3 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 text-white font-semibold text-xs shadow-md shadow-indigo-500/20 hover:shadow-lg transition-all active:scale-95 cursor-pointer flex items-center gap-1.5 border-0"
              >
                <span>Search</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Example Queries */}
            <div className="flex flex-wrap items-center justify-center gap-2.5 pt-2 text-xs">
              <span className="text-slate-400 dark:text-zinc-500">Try searching:</span>
              {[
                "Machine Learning",
                "Operating Systems Notes",
                "React Tutorial",
                "CNN Lecture"
              ].map((query) => (
                <button
                  key={query}
                  type="button"
                  onClick={() => setWebSearchQuery(query)}
                  className="px-3 py-1.5 rounded-full border border-slate-200 dark:border-zinc-800 bg-white hover:bg-slate-50 dark:bg-zinc-900 dark:hover:bg-zinc-800 text-slate-600 dark:text-zinc-350 cursor-pointer transition-all hover:border-indigo-500/30 hover:scale-[1.02]"
                >
                  {query}
                </button>
              ))}
            </div>

            {/* Content Type Selector */}
            <div className="pt-6 border-t border-slate-100 dark:border-zinc-800/60 space-y-3 w-full text-left">
              <h3 className="text-xs font-bold tracking-wider text-slate-400 dark:text-zinc-500 uppercase">
                Content Type
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
                {[
                  {
                    id: "pdf",
                    icon: "📄",
                    title: "PDF",
                    description: "Search research papers, notes, books and PDF documents."
                  },
                  {
                    id: "youtube",
                    icon: "▶️",
                    title: "YouTube",
                    description: "Search YouTube videos and educational lectures."
                  },
                  {
                    id: "audio",
                    icon: "🎵",
                    title: "Audio",
                    description: "Search podcasts, audio lectures and recordings."
                  }
                ].map((type) => {
                  const isSelected = selectedContentType === type.id;
                  return (
                    <button
                      key={type.id}
                      type="button"
                      onClick={() => setSelectedContentType(type.id as "pdf" | "youtube" | "audio")}
                      className={`p-4 rounded-2xl text-left transition-all duration-200 cursor-pointer relative overflow-hidden flex flex-col justify-between space-y-2 border ${
                        isSelected
                          ? "border-indigo-500 dark:border-indigo-400 bg-indigo-500/10 dark:bg-indigo-500/15 shadow-lg shadow-indigo-500/10 ring-1 ring-indigo-500/20 scale-[1.01]"
                          : "border-slate-200/80 dark:border-zinc-800/80 bg-white/80 dark:bg-zinc-900/40 hover:border-slate-300 dark:hover:border-zinc-700 hover:bg-slate-50/80 dark:hover:bg-zinc-800/50 hover:scale-[1.01]"
                      }`}
                    >
                      <div className="flex items-center gap-2 text-sm font-bold text-slate-800 dark:text-zinc-100">
                        <span className="text-base">{type.icon}</span>
                        <span>{type.title}</span>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-zinc-400 leading-relaxed font-normal">
                        {type.description}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </motion.div>
      )}

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

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-900/90 dark:bg-zinc-800/90 backdrop-blur-md text-white text-xs font-semibold py-3 px-4.5 rounded-2xl shadow-xl border border-slate-700/35 dark:border-zinc-700/35 flex items-center gap-2 animate-fade-in">
          <Info className="h-4 w-4 text-emerald-500" />
          <span>{toastMessage}</span>
        </div>
      )}

    </main>
  );
}
