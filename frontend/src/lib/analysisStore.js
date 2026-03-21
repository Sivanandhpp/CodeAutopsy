/**
 * Analysis Store
 * Global state for analysis results, current file, and issues using Zustand.
 */

import { create } from 'zustand';

const useAnalysisStore = create((set, get) => ({
  // Current analysis
  analysisId: null,
  analysisResult: null,
  analysisStatus: 'idle', // idle, loading, analyzing, complete, error
  progress: 0,
  progressMessage: '',
  
  // Current file
  currentFile: null,
  currentFileContent: null,
  
  // Issues
  issues: [],
  selectedIssue: null,
  
  // Actions
  setAnalysisId: (id) => set({ analysisId: id }),
  
  setAnalysisResult: (result) => set({ 
    analysisResult: result, 
    issues: result?.issues || [],
    analysisStatus: result?.status || 'complete',
  }),
  
  setAnalysisStatus: (status) => set({ analysisStatus: status }),
  
  updateProgress: (progress, message) => set({ progress, progressMessage: message }),
  
  setCurrentFile: (filePath, content) => set({ 
    currentFile: filePath, 
    currentFileContent: content,
  }),
  
  setSelectedIssue: (issue) => set({ selectedIssue: issue }),
  
  getIssuesForFile: (filePath) => {
    return get().issues.filter(i => i.file_path === filePath);
  },
  
  reset: () => set({
    analysisId: null,
    analysisResult: null,
    analysisStatus: 'idle',
    progress: 0,
    progressMessage: '',
    currentFile: null,
    currentFileContent: null,
    issues: [],
    selectedIssue: null,
  }),
}));

export default useAnalysisStore;
