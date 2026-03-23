/**
 * DotGrid — Interactive canvas of dots that repel from mouse cursor
 * Converted from the user's custom landing page design (TSX → JSX)
 */

import { useEffect, useRef } from 'react';

export default function DotGrid() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;
    const spacing = 15;
    const radius = 0.8;
    const mouse = { x: -1000, y: -1000 };
    let animFrame;

    class Dot {
      constructor(x, y) {
        this.x = x;
        this.y = y;
        this.baseX = x;
        this.baseY = y;
      }

      update() {
        const dx = mouse.x - this.baseX;
        const dy = mouse.y - this.baseY;
        const distance = Math.sqrt(dx * dx + dy * dy);

        const maxDist = 200;
        const force = Math.max(0, (maxDist - distance) / maxDist);

        const pushX = (dx / distance) * force * 50 || 0;
        const pushY = (dy / distance) * force * 50 || 0;

        this.x += (this.baseX - pushX - this.x) * 0.04;
        this.y += (this.baseY - pushY - this.y) * 0.04;

        const opacity = Math.max(0.1, 0.4 - (force * 0.35));

        ctx.fillStyle = `rgba(255, 255, 255, ${opacity})`;
        ctx.beginPath();
        ctx.arc(this.x, this.y, radius, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    let dots = [];

    const init = () => {
      dots = [];
      const cols = Math.floor(width / spacing);
      const rows = Math.floor(height / spacing);
      const offsetX = (width - cols * spacing) / 2;
      const offsetY = (height - rows * spacing) / 2;

      for (let i = 0; i <= cols; i++) {
        for (let j = 0; j <= rows; j++) {
          dots.push(new Dot(offsetX + i * spacing, offsetY + j * spacing));
        }
      }
    };

    const animate = () => {
      ctx.clearRect(0, 0, width, height);
      dots.forEach(dot => dot.update());
      animFrame = requestAnimationFrame(animate);
    };

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
      init();
    };

    const handleMouseMove = (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };

    const handleMouseLeave = () => {
      mouse.x = -1000;
      mouse.y = -1000;
    };

    init();
    animate();

    window.addEventListener('resize', handleResize);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      cancelAnimationFrame(animFrame);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        zIndex: 0,
        pointerEvents: 'none',
      }}
    />
  );
}
