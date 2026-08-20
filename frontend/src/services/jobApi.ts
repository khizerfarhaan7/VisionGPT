export interface BackgroundJob {
  job_id: string;
  job_type: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | "interrupted";
  progress: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  result?: Record<string, unknown> | null;
  session_id?: string | null;
  document_id?: string | null;
  metadata?: Record<string, unknown>;
  cancel_requested?: boolean;
}

export interface JobListResponse {
  jobs: BackgroundJob[];
  total_count: number;
}

export interface JobCancelResponse {
  message: string;
  job: BackgroundJob;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function getJobStatus(jobId: string): Promise<BackgroundJob> {
  const response = await fetch(`${BASE_URL}/jobs/${encodeURIComponent(jobId)}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch job status: ${response.statusText}`);
  }
  return response.json();
}

export async function listJobs(sessionId?: string, limit: number = 50): Promise<JobListResponse> {
  const url = new URL(`${BASE_URL}/jobs`);
  if (sessionId) url.searchParams.append("session_id", sessionId);
  url.searchParams.append("limit", limit.toString());

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Failed to list jobs: ${response.statusText}`);
  }
  return response.json();
}

export async function cancelJob(jobId: string): Promise<JobCancelResponse> {
  const response = await fetch(`${BASE_URL}/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  if (!response.ok) {
    throw new Error(`Failed to cancel job: ${response.statusText}`);
  }
  return response.json();
}
