export interface ImportAnalyzeResponse {
  success: boolean;
  message: string;
  content_type: string;
  status?: string;
  filename?: string;
  title?: string;
  channel?: string;
  duration?: number;
  transcript_length?: number;
  total_chunks?: number;
  total_vectors?: number;
  index_location?: string;
  metadata_location?: string;
}

export async function importAnalyzeResource(
  url: string,
  contentType: "pdf" | "youtube" | "audio"
): Promise<ImportAnalyzeResponse> {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  const response = await fetch(`${apiBaseUrl}/import/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      url: url.trim(),
      content_type: contentType,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMessage = errorData.detail || `Unable to import ${contentType.toUpperCase()}. Please try again.`;
    throw new Error(errorMessage);
  }

  return await response.json();
}
