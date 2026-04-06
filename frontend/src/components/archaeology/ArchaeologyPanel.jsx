/**
 * Archaeology Panel
 * Main container that fetches trace data and renders the timeline + controls + commit detail.
 * Opened when user clicks "Trace Origin" on an issue.
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Microscope, AlertTriangle, Loader2, GitBranch, FileCode
} from 'lucide-react';

import ArchaeologyTimeline from './ArchaeologyTimeline';
import TimelineControls from './TimelineControls';
import CommitDetail from './CommitDetail';
import { traceBugOrigin } from '../../lib/api';

export default function ArchaeologyPanel({
  analysisId,
  filePath,
  lineNumber,
  defectFamily,
  onClose,
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [traceData, setTraceData] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    if (!analysisId || !filePath || !lineNumber) return;
    fetchTraceData();
  }, [analysisId, filePath, lineNumber]);

  async function fetchTraceData() {
    setLoading(true);
    setError(null);
    try {
      const data = await traceBugOrigin(analysisId, filePath, lineNumber);
      setTraceData(data);
      // Start at the origin (last in the chain, which is oldest)
      if (data.evolution_chain?.length > 0) {
        setCurrentIndex(0);
      }
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Failed to trace bug origin');
    } finally {
      setLoading(false);
    }
  }

  const chain = traceData?.evolution_chain || [];
  const currentCommit = chain[currentIndex] || null;
  const origin = traceData?.origin || null;

  return (
    <AnimatePresence>
      <motion.div
        className="ap-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.div
          className="ap-panel"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 30 }}
        >
          {/* Header */}
          <div className="ap-header">
            <div className="ap-title">
              <Microscope size={20} className="ap-icon" />
              <div>
                <h3>Code Archaeology</h3>
                <span className="ap-subtitle">
                  <FileCode size={13} />
                  {filePath}:{lineNumber}
                  {defectFamily && <span className="ap-issue-tag">{defectFamily}</span>}
                </span>
              </div>
            </div>
            <button className="ap-close" onClick={onClose}>
              <X size={18} />
            </button>
          </div>

          {/* Content */}
          <div className="ap-body">
            {loading && (
              <div className="ap-loading">
                <Loader2 size={28} className="ap-spin" />
                <p>Tracing bug origin...</p>
                <span>Analyzing git history for this line</span>
              </div>
            )}

            {error && (
              <div className="ap-error">
                <AlertTriangle size={24} />
                <p>{error}</p>
                <button onClick={fetchTraceData}>Retry</button>
              </div>
            )}

            {!loading && !error && traceData && (
              <>
                {/* Origin Summary */}
                <div className="ap-origin-summary">
                  <GitBranch size={16} />
                  <span>
                    Line was introduced by <strong>{origin?.author}</strong> in commit{' '}
                    <code>{origin?.commit_hash}</code>
                    {chain.length > 1 && ` and modified across ${chain.length} commits`}
                  </span>
                </div>

                {/* Timeline */}
                <div className="ap-timeline-section">
                  <ArchaeologyTimeline
                    evolutionChain={chain}
                    currentIndex={currentIndex}
                    onIndexChange={setCurrentIndex}
                  />
                  <TimelineControls
                    totalCommits={chain.length}
                    currentIndex={currentIndex}
                    onIndexChange={setCurrentIndex}
                  />
                </div>

                {/* Current commit detail */}
                <div className="ap-detail-section">
                  <CommitDetail
                    commit={currentCommit}
                    isOrigin={currentCommit?.change_type === 'introduction'}
                  />
                </div>
              </>
            )}
          </div>

          <style>{`
            .ap-overlay {
              position: fixed;
              inset: 0;
              background: rgba(0,0,0,0.6);
              backdrop-filter: blur(4px);
              z-index: 100;
              display: flex;
              align-items: center;
              justify-content: center;
              padding: 20px;
            }
            .ap-panel {
              background: var(--ca-bg);
              border: 1px solid var(--ca-border);
              border-radius: 16px;
              width: 100%;
              max-width: 780px;
              max-height: 90vh;
              overflow-y: auto;
              box-shadow: 0 20px 60px rgba(0,0,0,0.4);
            }
            .ap-header {
              display: flex;
              align-items: flex-start;
              justify-content: space-between;
              padding: 20px 24px 16px;
              border-bottom: 1px solid var(--ca-border);
            }
            .ap-title {
              display: flex;
              gap: 12px;
              align-items: flex-start;
            }
            .ap-icon {
              color: var(--ca-primary-light);
              margin-top: 2px;
            }
            .ap-title h3 {
              font-size: 1.05rem;
              font-weight: 700;
              color: var(--ca-text);
              margin: 0;
            }
            .ap-subtitle {
              display: flex;
              align-items: center;
              gap: 5px;
              font-size: 0.8rem;
              color: var(--ca-text-muted);
              font-family: var(--ca-font-mono);
              margin-top: 3px;
            }
            .ap-issue-tag {
              background: rgba(244,63,94,0.12);
              color: var(--ca-critical);
              font-size: 0.68rem;
              padding: 1px 7px;
              border-radius: 4px;
              font-weight: 600;
              text-transform: uppercase;
              margin-left: 6px;
            }
            .ap-close {
              background: var(--ca-bg-secondary);
              border: 1px solid var(--ca-border);
              color: var(--ca-text-muted);
              border-radius: 8px;
              padding: 6px;
              cursor: pointer;
              transition: all 0.15s;
            }
            .ap-close:hover {
              background: rgba(244,63,94,0.1);
              border-color: var(--ca-critical);
              color: var(--ca-critical);
            }
            .ap-body {
              padding: 20px 24px 24px;
            }
            .ap-loading {
              display: flex;
              flex-direction: column;
              align-items: center;
              justify-content: center;
              padding: 40px 0;
              gap: 10px;
            }
            .ap-spin {
              animation: spin 1s linear infinite;
              color: var(--ca-primary-light);
            }
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
            .ap-loading p {
              font-weight: 600;
              color: var(--ca-text);
              font-size: 0.95rem;
            }
            .ap-loading span {
              color: var(--ca-text-muted);
              font-size: 0.82rem;
            }
            .ap-error {
              display: flex;
              flex-direction: column;
              align-items: center;
              padding: 30px 0;
              gap: 10px;
              color: var(--ca-critical);
            }
            .ap-error button {
              margin-top: 6px;
              background: var(--ca-primary);
              color: white;
              border: none;
              padding: 6px 18px;
              border-radius: 8px;
              cursor: pointer;
            }
            .ap-origin-summary {
              display: flex;
              align-items: center;
              gap: 8px;
              padding: 10px 14px;
              background: var(--ca-bg-secondary);
              border: 1px solid var(--ca-border);
              border-radius: 10px;
              font-size: 0.85rem;
              color: var(--ca-text-secondary);
              margin-bottom: 16px;
            }
            .ap-origin-summary strong {
              color: var(--ca-primary-light);
            }
            .ap-origin-summary code {
              font-family: var(--ca-font-mono);
              font-size: 0.82rem;
              background: rgba(99,102,241,0.1);
              padding: 1px 6px;
              border-radius: 4px;
              color: var(--ca-primary-light);
            }
            .ap-timeline-section {
              margin-bottom: 16px;
            }
            .ap-detail-section {
              /* Commit card */
            }
          `}</style>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
