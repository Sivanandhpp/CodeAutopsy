/**
 * CodeAutopsy API Client (v2.0)
 * ==============================
 * Axios instance with JWT auth headers, auto-logout on 401,
 * and all API functions for auth, projects, analysis, and more.
 */

import axios from 'axios';
import useAuthStore from './authStore';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 2min for long analysis operations
  headers: {
    'Content-Type': 'application/json',
  },
});

// ─── Request Interceptor: Attach JWT ────────────────────────
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ─── Response Interceptor: Handle 401 ───────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid — auto logout
      useAuthStore.getState().logout();
    }
    const message = error.response?.data?.detail || error.message || 'An error occurred';
    console.error(`[API Error] ${message}`);
    return Promise.reject(error);
  }
);


// ═════════════════════════════════════════════════════════════
// AUTH API
// ═════════════════════════════════════════════════════════════

export async function checkEmail(email) {
  const response = await api.post('/api/auth/check-email', { email });
  return response.data;
}

export async function sendOtp(email) {
  const response = await api.post('/api/auth/send-otp', { email });
  return response.data;
}

export async function verifyOtp(email, otpCode) {
  const response = await api.post('/api/auth/verify-otp', { email, otp_code: otpCode });
  return response.data;
}

export async function registerUser(email, username, password, tempToken) {
  const response = await api.post('/api/auth/register', {
    email, username, password, temp_token: tempToken,
  });
  return response.data;
}

export async function loginUser(email, password) {
  const response = await api.post('/api/auth/login', { email, password });
  return response.data;
}

export async function forgotPassword(email) {
  const response = await api.post('/api/auth/forgot-password', { email });
  return response.data;
}

export async function resetPassword(email, otpCode, newPassword) {
  const response = await api.post('/api/auth/reset-password', {
    email, otp_code: otpCode, new_password: newPassword,
  });
  return response.data;
}

export async function getMe() {
  const response = await api.get('/api/auth/me');
  return response.data;
}


// ═════════════════════════════════════════════════════════════
// PROJECTS API
// ═════════════════════════════════════════════════════════════

export async function getProjects() {
  const response = await api.get('/api/projects');
  return response.data;
}

export async function createProject(repoUrl, description = '') {
  const response = await api.post('/api/projects', { repo_url: repoUrl, description });
  return response.data;
}

export async function getProject(projectId) {
  const response = await api.get(`/api/projects/${projectId}`);
  return response.data;
}

export async function addCollaborator(projectId, username, role = 'viewer') {
  const response = await api.post(`/api/projects/${projectId}/collaborators`, { username, role });
  return response.data;
}

export async function removeCollaborator(projectId, userId) {
  const response = await api.delete(`/api/projects/${projectId}/collaborators/${userId}`);
  return response.data;
}

export async function searchUsers(query) {
  const response = await api.get('/api/users/search', { params: { q: query } });
  return response.data;
}


// ═════════════════════════════════════════════════════════════
// ANALYSIS API
// ═════════════════════════════════════════════════════════════

export async function analyzeRepository(repoUrl, projectId = null) {
  const response = await api.post('/api/analyze/github', {
    repo_url: repoUrl,
    project_id: projectId,
  });
  return response.data;
}

export async function cancelAnalysis(analysisId) {
  const response = await api.post(`/api/analyze/cancel/${analysisId}`);
  return response.data;
}

export async function getAnalysisResults(analysisId) {
  const response = await api.get(`/api/results/${analysisId}`);
  return response.data;
}

export function subscribeToProgress(analysisId, onMessage, onError) {
  const eventSource = new EventSource(`${API_BASE_URL}/api/analyze/stream/${analysisId}`);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (e) {
      console.error('[SSE] Parse error:', e);
    }
  };

  eventSource.onerror = (error) => {
    console.error('[SSE] Connection error:', error);
    if (onError) onError(error);
    eventSource.close();
  };

  return eventSource;
}


// ═════════════════════════════════════════════════════════════
// ARCHAEOLOGY API
// ═════════════════════════════════════════════════════════════

export async function traceBugOrigin(analysisId, filePath, lineNumber) {
  const response = await api.get(`/api/archaeology/trace/${analysisId}`, {
    params: { file_path: filePath, line: lineNumber },
  });
  return response.data;
}

export async function getFileTimeline(analysisId, filePath, maxCommits = 50) {
  const response = await api.get(`/api/archaeology/timeline/${analysisId}`, {
    params: { file_path: filePath, max_commits: maxCommits },
  });
  return response.data;
}

export async function getFileBlame(analysisId, filePath) {
  const response = await api.get(`/api/archaeology/blame/${analysisId}`, {
    params: { file_path: filePath },
  });
  return response.data;
}

export async function getBlameHeatmap(analysisId, filePath) {
  const response = await api.get(`/api/archaeology/heatmap/${analysisId}`, {
    params: { file_path: filePath },
  });
  return response.data;
}


// ═════════════════════════════════════════════════════════════
// AI API
// ═════════════════════════════════════════════════════════════

export async function analyzeWithAI(codeSnippet, issueType, language = 'python') {
  const response = await api.post('/api/ai/analyze', {
    code_snippet: codeSnippet,
    issue_type: issueType,
    language,
  });
  return response.data;
}


// ═════════════════════════════════════════════════════════════
// FILE & REPORT API
// ═════════════════════════════════════════════════════════════

export async function getFileContent(analysisId, filePath) {
  const response = await api.get(`/api/files/${analysisId}`, {
    params: { file_path: filePath },
  });
  return response.data;
}

export async function downloadReport(analysisId, format = 'json') {
  const token = useAuthStore.getState().token;
  const url = `${API_BASE_URL}/api/report/${analysisId}/${format}`;

  const response = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new Error(`Failed to download report: ${response.statusText}`);

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = downloadUrl;

  const contentDisposition = response.headers.get('Content-Disposition');
  let filename = `codeautopsy_report_${analysisId.substring(0, 8)}.${format}`;
  if (contentDisposition?.includes('filename=')) {
    const match = contentDisposition.match(/filename="?([^"]+)"?/);
    if (match?.[1]) filename = match[1];
  }

  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(downloadUrl);
}

export async function checkHealth() {
  const response = await api.get('/health');
  return response.data;
}

export default api;
