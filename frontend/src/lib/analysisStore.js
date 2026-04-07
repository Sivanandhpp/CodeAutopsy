/**
 * Analysis Store - Two-Phase Pipeline State Management
 * ====================================================
 * Manages static analysis hydration, SSE progress updates, and the streamed
 * AI executive summary without losing Phase 1 results on reconnects.
 */

import { create } from 'zustand';

function deriveAnalysisStatus(result) {
  const persistedStatus = result?.status || 'complete';
  const hasIssues = Array.isArray(result?.issues) && result.issues.length > 0;

  if (persistedStatus === 'analyzing' && hasIssues) {
    return 'static_done';
  }
  if (persistedStatus === 'failed' && hasIssues) {
    return 'error';
  }
  return persistedStatus;
}

function deriveAnalysisStatusWithFallback(result, currentState) {
  const persistedStatus = deriveAnalysisStatus(result);
  const hasCurrentIssues = Array.isArray(currentState?.staticIssues) && currentState.staticIssues.length > 0;

  if (persistedStatus === 'analyzing' && hasCurrentIssues) {
    return 'static_done';
  }
  if (persistedStatus === 'failed' && hasCurrentIssues) {
    return 'error';
  }
  return persistedStatus;
}

function deriveAiSummaryStatus(result, currentStatus) {
  if (result?.ai_summary) return 'complete';
  if (result?.status === 'analyzing') return currentStatus === 'complete' ? 'idle' : currentStatus;
  return currentStatus;
}

const useAnalysisStore = create((set, get) => ({
  analysisId: null,
  analysisResult: null,
  analysisStatus: 'idle',
  progress: 0,
  progressMessage: '',

  staticIssues: [],
  healthScore: null,
  fileTree: [],
  languages: {},
  totalLines: 0,
  repoName: '',

  aiSummary: '',
  aiSummaryStatus: 'idle', // idle | streaming | complete | unavailable | failed
  aiSummaryError: null,

  detectedStack: null,
  currentFile: null,
  currentFileContent: null,
  selectedIssue: null,

  setAnalysisId: (id) => set({ analysisId: id }),

  setAnalysisStatus: (status) => set({ analysisStatus: status }),

  updateProgress: (progress, message) => set({ progress, progressMessage: message }),

  handleStaticComplete: (data) => set({
    analysisStatus: 'static_done',
    staticIssues: Array.isArray(data.issues) ? data.issues : [],
    healthScore: data.health_score,
    fileTree: Array.isArray(data.file_tree) ? data.file_tree : [],
    languages: data.languages || {},
    totalLines: data.total_lines || 0,
    repoName: data.repo_name || '',
    progress: data.progress || 50,
    progressMessage: data.message || 'Static analysis complete',
  }),

  handleStackDetected: (data) => set({
    detectedStack: {
      language: data.language,
      frameworks: data.frameworks || [],
      manifest: data.manifest || 'none',
    },
  }),

  handleAiSummaryStart: (data) => set({
    analysisStatus: 'ai_scanning',
    aiSummary: '',
    aiSummaryStatus: 'streaming',
    aiSummaryError: null,
    progressMessage: data.message || 'Generating AI summary...',
  }),

  handleAiSummaryChunk: (data) => set((state) => ({
    aiSummary: state.aiSummary + (data.text || ''),
    aiSummaryStatus: 'streaming',
    progress: Math.max(state.progress || 0, 75),
  })),

  handleAiSummaryUnavailable: (data) => set({
    aiSummaryStatus: 'unavailable',
    aiSummaryError: data.message || 'AI summary unavailable. Static results are still available.',
  }),

  handleAiSummaryError: (data) => set({
    aiSummaryStatus: 'failed',
    aiSummaryError: data.message || 'AI summary unavailable. Static results are still available.',
    progressMessage: data.detail || data.message || 'AI summary unavailable',
  }),

  handleAiSummaryComplete: (data) => set((state) => ({
    aiSummary: typeof data.summary === 'string' ? data.summary : state.aiSummary,
    aiSummaryStatus: data.status === 'failed'
      ? 'failed'
      : (typeof data.summary === 'string' && data.summary
        ? 'complete'
        : state.aiSummaryStatus),
    aiSummaryError: typeof data.summary === 'string' && data.summary
      ? null
      : state.aiSummaryError,
    progressMessage: data.message || 'AI summary complete',
  })),

  handleComplete: (data) => set((state) => ({
    analysisStatus: 'complete',
    progress: 100,
    progressMessage: data.message || 'Analysis complete!',
    healthScore: data.health_score ?? state.healthScore,
    aiSummaryStatus: state.aiSummary
      ? 'complete'
      : (state.aiSummaryError ? state.aiSummaryStatus : state.aiSummaryStatus),
  })),

  handleError: (data) => set({
    analysisStatus: 'error',
    progressMessage: data.message || 'Analysis failed',
  }),

  setAnalysisResult: (result) => set((state) => ({
    analysisResult: result,
    staticIssues: Array.isArray(result?.issues) && result.issues.length > 0
      ? result.issues
      : state.staticIssues,
    aiSummary: result?.ai_summary || '',
    healthScore: result?.health_score ?? state.healthScore,
    fileTree: Array.isArray(result?.file_tree) && result.file_tree.length > 0
      ? result.file_tree
      : state.fileTree,
    languages: Object.keys(result?.languages || {}).length > 0
      ? result.languages
      : state.languages,
    totalLines: result?.total_lines || state.totalLines,
    repoName: result?.repo_name || state.repoName,
    analysisStatus: deriveAnalysisStatusWithFallback(result, state),
    aiSummaryStatus: deriveAiSummaryStatus(
      result,
      result?.ai_summary ? 'complete' : state.aiSummaryStatus
    ),
    aiSummaryError: result?.ai_summary ? null : state.aiSummaryError,
  })),

  setCurrentFile: (filePath, content) => set({
    currentFile: filePath,
    currentFileContent: content,
  }),

  setSelectedIssue: (issue) => set({ selectedIssue: issue }),

  getIssuesForFile: (filePath) => {
    const { staticIssues } = get();
    return [...staticIssues].filter((issue) => issue.file_path === filePath);
  },

  reset: () => set({
    analysisId: null,
    analysisResult: null,
    analysisStatus: 'idle',
    progress: 0,
    progressMessage: '',
    staticIssues: [],
    healthScore: null,
    fileTree: [],
    languages: {},
    totalLines: 0,
    repoName: '',
    aiSummary: '',
    aiSummaryStatus: 'idle',
    aiSummaryError: null,
    detectedStack: null,
    currentFile: null,
    currentFileContent: null,
    selectedIssue: null,
  }),
}));

export default useAnalysisStore;
