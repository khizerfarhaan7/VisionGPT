# VisionGPT Developer & API Integration Guide

## Overview

VisionGPT is an enterprise-grade, privacy-first **Multimodal Retrieval-Augmented Generation (RAG)** platform designed to unify documents (PDFs), images, voice audio recordings, video timelines, and web content into a single interactive context.

This document details the REST API endpoints, request correlation (`X-Request-ID`), error schema, asynchronous job queue lifecycle, RAG query routing, and metrics observability.

---

## 1. Base Configuration & Environments

* **Base URL**: `http://localhost:8000/api/v1` (Default local development)
* **Interactive Documentation (Swagger UI)**: `http://localhost:8000/docs`
* **OpenAPI 3.0 Specification**: `http://localhost:8000/api/v1/openapi.json`

### Environment Profiles (`VISIONGPT_PROFILE`)
1. **`local` (Default)**: Optimized for 4 GB RAM consumer laptops (`qwen2.5:3b`, `bge-small-en-v1.5`, Faster-Whisper CPU).
2. **`high_quality`**: GPU-accelerated server profile (`qwen2.5:14b`, `bge-large-en-v1.5`, Faster-Whisper CUDA).
3. **`custom`**: Configured via explicit environment variables.

---

## 2. Request Correlation & Privacy Protections

### Request Correlation ID (`X-Request-ID`)
Every HTTP request to VisionGPT automatically receives a UUID correlation ID.
* **Header Name**: `X-Request-ID`
* If passed in request headers, VisionGPT preserves and echoes the correlation ID in response headers.
* Every structured error response and log entry includes the `request_id` for tracing.

### Privacy & Security Directives
* **Zero Secret Exposure**: Passwords, API keys, database URLs, and token secrets are masked in server representations and logs.
* **No Request Body Logging**: Request payloads, user texts, and uploaded binary files are **never** logged to disk.
* **Local-First RAG Guarantee**: In `auto` RAG mode, queries default to local vector indices (`local` Ollama) if a local index exists, keeping document data on-premise.

---

## 3. Standardized Error Response Contract

All application, validation, and unhandled errors return a consistent JSON schema:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request payload or parameters.",
    "details": [
      {
        "field": "body -> question",
        "message": "field required",
        "type": "value_error.missing"
      }
    ],
    "request_id": "ad5ef7f4-8a47-4ff6-8c43-1bc2d603a110"
  }
}
```

### Machine-Readable Error Codes
* `NOT_FOUND` (HTTP 404): Resource or document missing.
* `VALIDATION_ERROR` (HTTP 422): Invalid request parameters or payload.
* `PAYLOAD_TOO_LARGE` (HTTP 413): Request body exceeds maximum upload limit (`MAX_UPLOAD_SIZE_MB`).
* `TOO_MANY_REQUESTS` (HTTP 429): Rate limit exceeded for sensitive operation.
* `UNAUTHORIZED` (HTTP 401): Missing or invalid credentials.
* `FORBIDDEN` (HTTP 403): Access denied or path traversal blocked.
* `RESOURCE_BUSY` (HTTP 429): AI model or queue worker is currently busy.
* `INTERNAL_SERVER_ERROR` (HTTP 500): Server error (sanitized message returned).

---

## 3. Security Hardening & Abuse Protections

### Security Response Headers
Every HTTP response automatically includes production security headers:
* `X-Content-Type-Options: nosniff` — Prevents MIME-type sniffing attacks.
* `X-Frame-Options: DENY` — Prevents clickjacking iframe embedding.
* `Referrer-Policy: strict-origin-when-cross-origin` — Protects cross-origin query leaks.

### Payload Size Protection (HTTP 413)
* Enforces centralized `MAX_UPLOAD_SIZE_MB` (Default 100 MB).
* Requests exceeding `Content-Length` limits are rejected with HTTP 413 before binary data is loaded into server RAM.

### In-Process Rate Limiter (HTTP 429)
* Lightweight sliding-window in-process rate limiter (`SECURITY_RATE_LIMIT_ENABLED=true`).
* Default window: 100 requests per 60 seconds (`SECURITY_RATE_LIMIT_REQUESTS=100`, `SECURITY_RATE_LIMIT_WINDOW_SECONDS=60`).
* Note: Limiter operates process-locally in memory without Redis/external infrastructure dependencies.

### Filename Sanitization & Path Traversal Guard
* Strips path control characters (`../`, `..\`, `/`, `\`).
* Rejects dangerous script/executable extensions (`.exe`, `.sh`, `.bat`, `.py`, `.js`, `.php`).
* Enforces `validate_safe_path()` to ensure files remain strictly contained inside designated `uploads/` directories.

---

## 4. Core Endpoint Reference

### A. Health & System Diagnostics

#### `GET /api/v1/health`
Returns full system health status (Database, Ollama, Gemini, CUDA, RAM).
```bash
curl -X GET "http://localhost:8000/api/v1/health" \
  -H "X-Request-ID: test-req-001"
```

#### `GET /api/v1/health/live` & `GET /api/v1/health/ready`
Kubernetes/container liveness and readiness probes (non-blocking, 0 model loading).

---

### B. Metrics & Observability

#### `GET /api/v1/metrics`
Returns in-memory API performance, latencies (average & p95), RAG query counts, job statuses, and model invocation counts.
```bash
curl -X GET "http://localhost:8000/api/v1/metrics"
```

---

### C. Persistent Asynchronous Job Management

Long-running PDF indexing, audio transcription, and video analytics return HTTP `202 Accepted` with a `job_id` immediately.

#### `GET /api/v1/jobs`
List recent background jobs.
```bash
curl -X GET "http://localhost:8000/api/v1/jobs?limit=20"
```

#### `GET /api/v1/jobs/{job_id}`
Query background job status and progress (0-100%).

#### `POST /api/v1/jobs/{job_id}/cancel`
Cancel an active or queued background processing job.
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/<JOB_UUID>/cancel"
```

---

### D. Grounded Answer & RAG Chat

#### `POST /api/v1/chat/query`
Execute a grounded multimodal RAG query over indexed documents.
```bash
curl -X POST "http://localhost:8000/api/v1/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main findings in the report?",
    "session_id": "session-xyz",
    "mode": "auto"
  }'
```

#### Response Structure:
```json
{
  "answer": "The quarterly report highlights a 25% growth in cloud services...",
  "citations": [
    {
      "citation_id": "cit_001",
      "document_id": "doc_123",
      "filename": "Q3_Report.pdf",
      "source_type": "pdf",
      "locator": {"page_number": 4},
      "relevance_score": 0.92,
      "content_snippet": "Cloud infrastructure revenue increased by 25%..."
    }
  ],
  "query_metadata": {
    "query_type": "multimodal",
    "selected_pipeline": "MultimodalRetrieverService",
    "mode": "auto"
  }
}
```

---

### E. Multimodal Document Pipelines

#### Async Document Endpoints (Recommended for large files):
* `POST /api/v1/pdf/index_async` — Async PDF text extraction and FAISS vector indexing.
* `POST /api/v1/audio/transcribe_async` — Async Faster-Whisper audio transcription.
* `POST /api/v1/video/index_async` — Async video keyframe extraction and vision analysis.

---

## 5. Developer Best Practices

1. **Include Correlation Headers**: Always supply or capture `X-Request-ID` when calling API endpoints to simplify debugging across client and server logs.
2. **Poll Background Jobs Safely**: When utilizing async endpoints (`_async`), poll `GET /api/v1/jobs/{job_id}` every 1–2 seconds until status becomes `completed`, `failed`, or `cancelled`.
3. **Respect Hardware Profiles**: For 4 GB RAM systems, keep `MAX_CONCURRENT_JOBS=1` to ensure worker tasks execute sequentially without memory pressure.
