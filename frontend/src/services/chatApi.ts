export interface ChatQueryRequest {
  vector_store_id: string;
  question: string;
}

export interface ChatSource {
  chunk_id: string | number;
  score: number;
  preview: string;
}

export interface ChatQueryResponse {
  success: boolean;
  answer: string;
  retrieved_chunks: number;
  sources: ChatSource[];
}

export async function queryRAGChat(
  vectorStoreId: string,
  question: string
): Promise<ChatQueryResponse> {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  const response = await fetch(`${apiBaseUrl}/chat/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      vector_store_id: vectorStoreId.trim(),
      question: question.trim(),
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMessage = errorData.detail || "Failed to query AI assistant. Please try again.";
    throw new Error(errorMessage);
  }

  return await response.json();
}
