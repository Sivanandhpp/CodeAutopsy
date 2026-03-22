/**
 * Archaeology Timeline — D3.js horizontal commit timeline
 * Shows commit nodes positioned chronologically with color-coding by change type.
 */

import { useEffect, useRef, useMemo } from 'react';
import * as d3 from 'd3';

const CHANGE_COLORS = {
  introduction: '#f43f5e',
  modification: '#f59e0b',
  refactor: '#10b981',
};

export default function ArchaeologyTimeline({ 
  evolutionChain = [], 
  currentIndex = 0, 
  onIndexChange,
  height = 140 
}) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);

  const data = useMemo(() => {
    return evolutionChain.map((commit, i) => ({
      ...commit,
      index: i,
      parsedDate: new Date(commit.date),
    }));
  }, [evolutionChain]);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || data.length === 0) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const margin = { top: 30, right: 30, bottom: 40, left: 30 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const midY = innerH / 2;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', width).attr('height', height);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Scales
    const xScale = data.length === 1
      ? d3.scaleLinear().domain([0, 1]).range([innerW / 2, innerW / 2])
      : d3.scaleLinear().domain([0, data.length - 1]).range([0, innerW]);

    // Connection line
    if (data.length > 1) {
      g.append('line')
        .attr('x1', xScale(0))
        .attr('y1', midY)
        .attr('x2', xScale(data.length - 1))
        .attr('y2', midY)
        .attr('stroke', 'rgba(99,102,241,0.2)')
        .attr('stroke-width', 2);

      // Progress fill line up to current index
      g.append('line')
        .attr('x1', xScale(0))
        .attr('y1', midY)
        .attr('x2', xScale(currentIndex))
        .attr('y2', midY)
        .attr('stroke', 'rgba(99,102,241,0.5)')
        .attr('stroke-width', 2)
        .attr('class', 'progress-line');
    }

    // Commit nodes
    const nodes = g.selectAll('.commit-node')
      .data(data)
      .enter()
      .append('g')
      .attr('class', 'commit-node')
      .attr('transform', d => `translate(${xScale(d.index)},${midY})`)
      .style('cursor', 'pointer')
      .on('click', (event, d) => onIndexChange?.(d.index));

    // Glow for active node
    nodes.filter(d => d.index === currentIndex)
      .append('circle')
      .attr('r', 16)
      .attr('fill', 'none')
      .attr('stroke', d => CHANGE_COLORS[d.change_type] || '#6366f1')
      .attr('stroke-width', 2)
      .attr('opacity', 0.3)
      .attr('class', 'glow-ring');

    // Node circles
    nodes.append('circle')
      .attr('r', d => d.index === currentIndex ? 10 : 6)
      .attr('fill', d => CHANGE_COLORS[d.change_type] || '#6366f1')
      .attr('stroke', d => d.index === currentIndex ? '#fff' : 'none')
      .attr('stroke-width', 2)
      .attr('opacity', d => d.index === currentIndex ? 1 : 0.7)
      .transition()
      .duration(300);

    // Hash labels on top (only for active and first/last)
    nodes.filter(d => d.index === currentIndex || d.index === 0 || d.index === data.length - 1)
      .append('text')
      .text(d => d.commit_hash)
      .attr('y', -20)
      .attr('text-anchor', 'middle')
      .attr('fill', d => d.index === currentIndex ? 'var(--ca-text)' : 'var(--ca-text-muted)')
      .attr('font-size', '11px')
      .attr('font-family', 'var(--ca-font-mono)');

    // Date labels on bottom (only a few to avoid clutter)
    const stride = Math.max(1, Math.floor(data.length / 5));
    nodes.filter((d, i) => i % stride === 0 || d.index === currentIndex)
      .append('text')
      .text(d => {
        const dt = d.parsedDate;
        return `${dt.getMonth() + 1}/${dt.getDate()}`;
      })
      .attr('y', 28)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--ca-text-muted)')
      .attr('font-size', '10px');

  }, [data, currentIndex, height, onIndexChange]);

  if (data.length === 0) {
    return (
      <div className="arch-timeline-empty">
        <p>No evolution history found</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="arch-timeline-wrap">
      <svg ref={svgRef} />
      <style>{`
        .arch-timeline-wrap {
          width: 100%;
          overflow-x: auto;
        }
        .arch-timeline-wrap svg {
          display: block;
        }
        .arch-timeline-empty {
          padding: 20px;
          text-align: center;
          color: var(--ca-text-muted);
          font-size: 0.85rem;
        }
        .commit-node:hover circle {
          filter: brightness(1.3);
        }
        .glow-ring {
          animation: glow-pulse 2s ease-in-out infinite;
        }
        @keyframes glow-pulse {
          0%, 100% { opacity: 0.2; r: 16; }
          50% { opacity: 0.5; r: 20; }
        }
      `}</style>
    </div>
  );
}
