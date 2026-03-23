/**
 * LiquidBlobs — Animated fluid gradient blobs at the bottom of the page
 * Converted from the user's custom landing page design
 */

import './LiquidBlobs.css';

export default function LiquidBlobs() {
  return (
    <div className="nebula-container">
      {/* Base Abstract Liquid Vectors */}
      <div className="blob-layer">
        <div className="blob blob-purple"></div>
        <div className="blob blob-blue"></div>
        <div className="blob blob-cyan"></div>
        <div className="blob blob-magenta"></div>

        {/* Voids that punch random gaps into the liquid */}
        <div className="void void-1"></div>
        <div className="void void-2"></div>
        <div className="void void-3"></div>
      </div>

      {/* Sharp Floating Geometries & Sweeping Lines */}
      <div className="sharp-shape shape-slice-1"></div>
      <div className="sharp-shape shape-slice-2"></div>
      <div className="sharp-shape shape-tumble-1"></div>
      <div className="sharp-shape shape-tumble-2"></div>

      {/* Overlay Noise */}
      <div className="nebula-dust"></div>
    </div>
  );
}
