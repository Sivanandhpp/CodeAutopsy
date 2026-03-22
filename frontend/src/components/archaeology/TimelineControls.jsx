/**
 * Timeline Playback Controls
 * Play/pause, prev/next, speed control for stepping through commit history.
 */

import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import {
  Play, Pause, SkipBack, SkipForward,
  ChevronsLeft, ChevronsRight, Gauge
} from 'lucide-react';

const SPEEDS = [1, 2, 4];

export default function TimelineControls({
  totalCommits,
  currentIndex,
  onIndexChange,
}) {
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(() => {
        onIndexChange?.((prev) => {
          const next = typeof prev === 'function' ? prev : currentIndex + 1;
          // If we get a number, advance it
          if (typeof next === 'number' && next >= totalCommits - 1) {
            setPlaying(false);
            return totalCommits - 1;
          }
          return typeof next === 'number' ? next : currentIndex + 1;
        });
      }, 2000 / speed);
    }
    return () => clearInterval(intervalRef.current);
  }, [playing, speed, currentIndex, totalCommits, onIndexChange]);

  // Auto-advance: call onIndexChange with next value
  useEffect(() => {
    if (playing && currentIndex < totalCommits - 1) {
      const timer = setTimeout(() => {
        onIndexChange(currentIndex + 1);
      }, 2000 / speed);
      return () => clearTimeout(timer);
    }
    if (playing && currentIndex >= totalCommits - 1) {
      setPlaying(false);
    }
  }, [playing, currentIndex, totalCommits, speed]);

  // Clear the interval effect since we use the timeout above
  useEffect(() => {
    return () => clearInterval(intervalRef.current);
  }, []);

  const goFirst = () => { setPlaying(false); onIndexChange(0); };
  const goPrev = () => { setPlaying(false); onIndexChange(Math.max(0, currentIndex - 1)); };
  const goNext = () => { setPlaying(false); onIndexChange(Math.min(totalCommits - 1, currentIndex + 1)); };
  const goLast = () => { setPlaying(false); onIndexChange(totalCommits - 1); };
  const togglePlay = () => setPlaying(!playing);
  const cycleSpeed = () => {
    const idx = SPEEDS.indexOf(speed);
    setSpeed(SPEEDS[(idx + 1) % SPEEDS.length]);
  };

  return (
    <div className="tc-wrap">
      <div className="tc-buttons">
        <button onClick={goFirst} disabled={currentIndex === 0} title="First commit">
          <ChevronsLeft size={16} />
        </button>
        <button onClick={goPrev} disabled={currentIndex === 0} title="Previous">
          <SkipBack size={16} />
        </button>
        <motion.button
          className={`tc-play ${playing ? 'active' : ''}`}
          onClick={togglePlay}
          whileTap={{ scale: 0.9 }}
          title={playing ? 'Pause' : 'Play'}
        >
          {playing ? <Pause size={18} /> : <Play size={18} />}
        </motion.button>
        <button onClick={goNext} disabled={currentIndex >= totalCommits - 1} title="Next">
          <SkipForward size={16} />
        </button>
        <button onClick={goLast} disabled={currentIndex >= totalCommits - 1} title="Last commit">
          <ChevronsRight size={16} />
        </button>
      </div>

      <span className="tc-counter">
        Commit <strong>{currentIndex + 1}</strong> of <strong>{totalCommits}</strong>
      </span>

      <button className="tc-speed" onClick={cycleSpeed} title="Playback speed">
        <Gauge size={14} />
        {speed}×
      </button>

      <style>{`
        .tc-wrap {
          display: flex;
          align-items: center;
          gap: 16px;
          padding: 8px 0;
          flex-wrap: wrap;
        }
        .tc-buttons {
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .tc-buttons button, .tc-speed {
          background: var(--ca-bg-secondary);
          border: 1px solid var(--ca-border);
          color: var(--ca-text-secondary);
          border-radius: 8px;
          padding: 6px 8px;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 4px;
          font-family: var(--ca-font-sans);
          font-size: 0.8rem;
          transition: all 0.15s;
        }
        .tc-buttons button:hover:not(:disabled), .tc-speed:hover {
          background: rgba(99,102,241,0.1);
          border-color: var(--ca-primary);
          color: var(--ca-primary-light);
        }
        .tc-buttons button:disabled {
          opacity: 0.3;
          cursor: not-allowed;
        }
        .tc-play {
          padding: 8px 12px !important;
          background: var(--ca-primary) !important;
          color: white !important;
          border-color: var(--ca-primary) !important;
        }
        .tc-play.active {
          background: var(--ca-high) !important;
          border-color: var(--ca-high) !important;
        }
        .tc-counter {
          font-size: 0.82rem;
          color: var(--ca-text-muted);
          font-family: var(--ca-font-mono);
        }
        .tc-counter strong {
          color: var(--ca-text);
        }
        .tc-speed {
          margin-left: auto;
          font-weight: 600;
        }
      `}</style>
    </div>
  );
}
