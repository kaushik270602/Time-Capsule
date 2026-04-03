import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

// Cookies are sent automatically via withCredentials: true.
// No need to manually attach tokens from localStorage.

export interface UserResponse {
  id: number;
  email: string;
  is_verified: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface MessageResponse {
  message: string;
}

export const authApi = {
  register: (email: string, password: string) =>
    api.post<UserResponse>("/api/auth/register", { email, password }),

  login: (email: string, password: string) =>
    api.post<TokenResponse>("/api/auth/login", { email, password }),

  logout: () => api.post<MessageResponse>("/api/auth/logout"),

  verifyEmail: (token: string) =>
    api.post<MessageResponse>("/api/auth/verify-email", { token }),

  requestPasswordReset: (email: string) =>
    api.post<MessageResponse>("/api/auth/password-reset-request", { email }),

  resetPassword: (token: string, new_password: string) =>
    api.post<MessageResponse>("/api/auth/password-reset", { token, new_password }),

  me: () => api.get<UserResponse>("/api/auth/me"),
};

// --- Capsule types ---

export interface CapsuleCreateRequest {
  title: string;
  text_content?: string;
  unlock_date: string; // ISO 8601
  timezone?: string; // IANA timezone identifier
  is_public: boolean;
}

export interface ImageAnalysis {
  media_url: string;
  caption: string;
  tags: string[];
}

export interface VideoSummary {
  media_url: string;
  transcription: string;
  summary: string;
}

export interface AIAnalysisResponse {
  summary: string | null;
  sentiment_label: string | null;
  sentiment_confidence: number | null;
  tone_description: string | null;
  image_analyses: ImageAnalysis[] | null;
  video_summaries: VideoSummary[] | null;
  recap_text: string | null;
  processing_status: string;
  created_at: string;
}

export interface CapsuleResponse {
  id: number;
  title: string;
  text_content: string | null;
  media_urls: string[];
  transcriptions: string[];
  unlock_date: string;
  timezone: string; // IANA timezone identifier
  status: string;
  is_public: boolean;
  created_at: string;
  time_until_unlock: number | null;
  user_id: number | null;
  ai_analysis?: AIAnalysisResponse | null;
  unlock_date_local?: string; // Formatted in stored timezone
}

export interface MediaUploadResponse {
  url: string;
  message: string;
}

export interface CapsuleListResponse {
  capsules: CapsuleResponse[];
  total: number;
}

// --- Public feed types ---

export interface PublicCapsuleResponse {
  id: number;
  title: string;
  text_content: string | null;
  unlock_date: string;
  timezone: string; // IANA timezone identifier
  unlock_date_local?: string; // Formatted in stored timezone
  created_at: string;
  user_id: number;
}

export interface PublicFeedResponse {
  capsules: PublicCapsuleResponse[];
  total: number;
}

export const capsuleApi = {
  create: (data: CapsuleCreateRequest) =>
    api.post<CapsuleResponse>("/api/capsules", data),

  get: (id: number) =>
    api.get<CapsuleResponse>(`/api/capsules/${id}`),

  list: () => api.get<CapsuleListResponse>("/api/capsules"),

  uploadMedia: (
    capsuleId: number,
    file: File,
    onProgress?: (pct: number) => void
  ) => {
    const form = new FormData();
    form.append("file", file);
    return api.post<MediaUploadResponse>(
      `/api/capsules/${capsuleId}/media`,
      form,
      {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (onProgress && e.total) {
            onProgress(Math.round((e.loaded * 100) / e.total));
          }
        },
      }
    );
  },

  publicFeed: (limit = 20, offset = 0) =>
    api.get<PublicFeedResponse>("/api/public/capsules", {
      params: { limit, offset },
    }),

  triggerAnalysis: (capsuleId: number) =>
    api.post(`/api/capsules/${capsuleId}/analyze`),
};

// --- Notification types ---

export interface NotificationResponse {
  id: number;
  capsule_id: number;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: NotificationResponse[];
  total: number;
}

export const notificationApi = {
  list: () =>
    api.get<NotificationListResponse>("/api/notifications"),

  markRead: (id: number) =>
    api.put<NotificationResponse>(`/api/notifications/${id}/read`),
};

export default api;
