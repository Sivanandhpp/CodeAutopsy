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

export async function analyzeRepository(repoUrl, projectId = null, options = {}) {
  const response = await api.post('/api/analyze/github', {
    repo_url: repoUrl,
    project_id: projectId,
    force: Boolean(options.force),
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

/**
 * Subscribe to analysis progress via Server-Sent Events.
 * 
 * The backend emits named events for each pipeline phase:
 *   - status          → cloning/analyzing progress
 *   - static_complete → Phase 1 done (static issues + health score)
 *   - stack_detected  → detected language + frameworks
 *   - ollama_start    → AI analysis beginning (total file count)
 *   - file_result     → one file analyzed by AI (streamed progressively)
 *   - file_error      → one file failed (non-fatal)
 *   - ollama_complete → Phase 2 done
 *   - complete        → everything finished
 *   - error           → fatal error
 *
 * @param {string} analysisId - The analysis UUID
 * @param {object} store - The Zustand analysis store instance
 * @returns {EventSource} - The event source (call .close() to disconnect)
 */
export function subscribeToProgress(analysisId, store) {
  const eventSource = new EventSource(`${API_BASE_URL}/api/analyze/stream/${analysisId}`);

  // ─── Phase 1: Generic progress (cloning, scanning) ────
  eventSource.addEventListener('status', (e) => {
    try {
      const data = JSON.parse(e.data);
      store.updateProgress(data.progress || 0, data.message || '');
      if (data.status) store.setAnalysisStatus(data.status);
    } catch (err) {
      console.warn('[SSE] Failed to parse status event:', err);
    }
  });

  // ─── Phase 1 Complete: Static results ─────────────────
  eventSource.addEventListener('static_complete', (e) => {
    try {
      const data = JSON.parse(e.data);
      store.handleStaticComplete(data);
    } catch (err) {
      console.warn('[SSE] Failed to parse static_complete event:', err);
    }
  });

  // ─── Stack Detection ──────────────────────────────────
  eventSource.addEventListener('stack_detected', (e) => {
    try {
      const data = JSON.parse(e.data);
      store.handleStackDetected(data);
    } catch (err) {
      console.warn('[SSE] Failed to parse stack_detected event:', err);
    }
  });

  // ─── Phase 2: AI Analysis Starting ────────────────────
  eventSource.addEventListener('ai_summary_start', (e) => {
    try {
      const data = JSON.parse(e.data);
      store.handleAiSummaryStart(data);
    } catch (err) {
      console.warn('[SSE] Failed to parse ai_summary_start event:', err);
    }
  });

  // ─── Phase 2: Per-file AI Result (streaming) ──────────
  eventSource.addEventListener('ai_summary_chunk', (e) => {
    try {
      const data = JSON.parse(e.data);
      store.handleAiSummaryChunk(data);
    } catch (err) {
      console.warn('[SSE] Failed to parse ai_summary_chunk event:', err);
    }
  });

  // ─── Phase 2: File Error (non-fatal) ──────────────────
  eventSource.addEventListener('ai_summary_error', (e) => {
    try {
      const data = JSON.parse(e.data);
      store.handleAiSummaryError(data);
    } catch (err) {
      console.warn('[SSE] Failed to parse ai_summary_error event:', err);
    }
  });

  // ─── Phase 2: AI Analysis Complete ────────────────────
  eventSource.addEventListener('ai_summary_complete', (e) => {
    try {
      const data = JSON.parse(e.data);
      store.handleAiSummaryComplete(data);
    } catch (err) {
      console.warn('[SSE] Failed to parse ai_summary_complete event:', err);
    }
  });

  // ─── Ollama Unavailable ───────────────────────────────
  eventSource.addEventListener('ollama_unavailable', (e) => {
    try {
      const data = JSON.parse(e.data);
      store.handleAiSummaryUnavailable(data);
      console.info('[AI] Ollama unavailable:', data.message);
    } catch {
      // Silently ignore
    }
  });

  // ─── Final Completion ─────────────────────────────────
  eventSource.addEventListener('complete', (e) => {
    try {
      const data = JSON.parse(e.data);
      store.handleComplete(data);
    } catch (err) {
      console.warn('[SSE] Failed to parse complete event:', err);
    }
    eventSource.close();
  });

  // ─── Error Event ──────────────────────────────────────
  eventSource.addEventListener('analysis_error', (e) => {
    // Check if this is a named error event from the server
    if (e.data) {
      try {
        const data = JSON.parse(e.data);
        store.handleError(data);
      } catch (err) {
        console.warn('[SSE] Failed to parse analysis_error event:', err);
      }
    }
    eventSource.close();
  });

  // ─── Native connection error ──────────────────────────
  eventSource.onerror = () => {
    // Connection lost — only treat as error if we haven't completed
    const currentStatus = store.getState?.()?.analysisStatus;
    if (currentStatus && !['complete', 'error'].includes(currentStatus)) {
      console.error('[SSE] Connection lost');
    }
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

export async function analyzeWithAI(codeSnippet, defectFamily, language = 'python') {
  const response = await api.post('/api/ai/analyze', {
    code_snippet: codeSnippet,
    defect_family: defectFamily,
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

export async function updateFileContent(analysisId, filePath, content) {
  const response = await api.put(`/api/files/${analysisId}`, {
    file_path: filePath,
    content: content,
  });
  return response.data;
}

export async function deleteProject(projectId) {
  const response = await api.delete(`/api/projects/${projectId}`);
  return response.data;
}

// ═════════════════════════════════════════════════════════════
// ADMIN API
// ═════════════════════════════════════════════════════════════

export async function getAdminStats() {
  const response = await api.get('/api/admin/stats');
  return response.data;
}

export async function getAdminUsers() {
  const response = await api.get('/api/admin/users');
  return response.data;
}

export async function adminDeleteUser(userId) {
  const response = await api.delete(`/api/admin/users/${userId}`);
  return response.data;
}

export async function getAdminRepos() {
  const response = await api.get('/api/admin/repos');
  return response.data;
}

export async function adminDeleteRepo(projectId) {
  const response = await api.delete(`/api/admin/repos/${projectId}`);
  return response.data;
}

export async function adminDeleteAllRepos() {
  const response = await api.delete('/api/admin/repos-all');
  return response.data;
}

export async function getAdminAuditLogs() {
  const response = await api.get('/api/admin/audit-logs');
  return response.data;
}

export async function getAdminRules() {
    const response = await api.get('/api/admin/rules');
    return response.data;
}

export async function adminBulkImportRulesJson(rules) {
  const response = await api.post('/api/admin/rules/bulk-json', rules);
  return response.data;
}

export async function adminBulkImportRulesCsv(file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post('/api/admin/rules/bulk-csv', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  return response.data;
}

export async function adminToggleRule(ruleId) {
    const response = await api.patch(`/api/admin/rules/${ruleId}/toggle`);
    return response.data;
}

export async function adminDeleteRule(ruleId) {
    const response = await api.delete(`/api/admin/rules/${ruleId}`);
    return response.data;
}

export default api;
