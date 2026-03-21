/**
 * CodeAutopsy API Client
 * Axios instance pre-configured for the backend API.
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60s for long analysis operations
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail || error.message || 'An error occurred';
    console.error(`[API Error] ${message}`);
    return Promise.reject(error);
  }
);

// ─── API Functions ───────────────────────────────────────────

/**
 * Start analysis of a GitHub repository
 */
export async function analyzeRepository(repoUrl) {
  const response = await api.post('/api/analyze/github', { repo_url: repoUrl });
  return response.data;
}

/**
 * Get analysis results by ID
 */
export async function getAnalysisResults(analysisId) {
  const response = await api.get(`/api/results/${analysisId}`);
  return response.data;
}

/**
 * Subscribe to analysis progress via SSE
 */
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

/**
 * Trace bug origin for a specific line
 */
export async function traceBugOrigin(analysisId, filePath, lineNumber) {
  const response = await api.post('/api/archaeology/trace', {
    analysis_id: analysisId,
    file_path: filePath,
    line_number: lineNumber,
  });
  return response.data;
}

/**
 * Get commit timeline for a file
 */
export async function getFileTimeline(analysisId, filePath, maxCommits = 50) {
  const response = await api.post('/api/archaeology/timeline', {
    analysis_id: analysisId,
    file_path: filePath,
    max_commits: maxCommits,
  });
  return response.data;
}

/**
 * Get blame data for a file
 */
export async function getFileBlame(analysisId, filePath) {
  const response = await api.post('/api/archaeology/blame', {
    analysis_id: analysisId,
    file_path: filePath,
  });
  return response.data;
}

/**
 * Get AI analysis for a code issue
 */
export async function analyzeWithAI(codeSnippet, issueType, language = 'python') {
  const response = await api.post('/api/ai/analyze', {
    code_snippet: codeSnippet,
    issue_type: issueType,
    language,
  });
  return response.data;
}

/**
 * Get file content from analyzed repo
 */
export async function getFileContent(analysisId, filePath) {
  const response = await api.get(`/api/files/${analysisId}`, {
    params: { file_path: filePath },
  });
  return response.data;
}

/**
 * Check API health
 */
export async function checkHealth() {
  const response = await api.get('/health');
  return response.data;
}

export default api;
