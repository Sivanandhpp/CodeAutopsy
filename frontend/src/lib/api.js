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
  const response = await api.get(`/api/archaeology/trace/${analysisId}`, {
    params: { file_path: filePath, line: lineNumber },
  });
  return response.data;
}

/**
 * Get commit timeline for a file
 */
export async function getFileTimeline(analysisId, filePath, maxCommits = 50) {
  const response = await api.get(`/api/archaeology/timeline/${analysisId}`, {
    params: { file_path: filePath, max_commits: maxCommits },
  });
  return response.data;
}

/**
 * Get blame data for a file
 */
export async function getFileBlame(analysisId, filePath) {
  const response = await api.get(`/api/archaeology/blame/${analysisId}`, {
    params: { file_path: filePath },
  });
  return response.data;
}

/**
 * Get blame heatmap data for a file
 */
export async function getBlameHeatmap(analysisId, filePath) {
  const response = await api.get(`/api/archaeology/heatmap/${analysisId}`, {
    params: { file_path: filePath },
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
 * Download a report (json or pdf)
 */
export async function downloadReport(analysisId, format = 'json') {
  const url = `${API_BASE_URL}/api/report/${analysisId}/${format}`;
  
  // Use fetch to handle Blob download properly
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to download report: ${response.statusText}`);
  }
  
  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = downloadUrl;
  
  // Extract filename from headers if possible, otherwise use fallback
  const contentDisposition = response.headers.get('Content-Disposition');
  let filename = `codeautopsy_report_${analysisId.substring(0, 8)}.${format}`;
  if (contentDisposition && contentDisposition.includes('filename=')) {
    const match = contentDisposition.match(/filename="?([^"]+)"?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }
  
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(downloadUrl);
}

/**
 * Check API health
 */
export async function checkHealth() {
  const response = await api.get('/health');
  return response.data;
}

export default api;
