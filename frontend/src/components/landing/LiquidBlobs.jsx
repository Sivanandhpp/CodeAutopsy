/**
 * LiquidBlobs - WebGL liquid gradient focused at the bottom.
 */

import { useEffect, useRef } from 'react';
import './LiquidBlobs.css';

export default function LiquidBlobs() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext('webgl', {
      antialias: true,
      alpha: true,
      premultipliedAlpha: false,
      depth: false,
      stencil: false,
    });

    if (!gl) return;

    const vertexSource = `
      attribute vec2 aPosition;
      void main() {
        gl_Position = vec4(aPosition, 0.0, 1.0);
      }
    `;

    const fragmentSource = `
      precision highp float;

      uniform vec2 uResolution;
      uniform float uTime;

      float blob(vec2 p, vec2 center, float radius) {
        float d = length(p - center);
        return smoothstep(radius, 0.0, d);
      }

      float arcHeight(float x) {
        float xArc = x - 0.5;
        float height = 0.20 + 0.4 * (xArc * xArc * 4.0);
        return clamp(height, 0.12, 0.52);
      }

      void main() {
        vec2 uv = gl_FragCoord.xy / uResolution;
        vec2 uvExt = vec2((uv.x - 0.5) * 1.35 + 0.5, uv.y * 1.25 - 0.12);
        float aspect = uResolution.x / uResolution.y;
        vec2 p = vec2(uvExt.x * aspect, uvExt.y);

        float t = uTime * 0.7;

        float warpX = sin(p.x * 2.6 + t * 0.35) * 0.055;
        float warpY = sin(p.y * 3.2 - t * 0.28) * 0.05;
        p += vec2(warpX, warpY * 0.75);

        vec2 c1 = vec2((-0.08 + 0.06 * sin(t * 0.22)) * aspect, 0.12 + 0.04 * cos(t * 0.2));
        vec2 c2 = vec2((0.18 + 0.06 * cos(t * 0.18)) * aspect, 0.16 + 0.04 * sin(t * 0.24));
        vec2 c3 = vec2((0.5 + 0.05 * sin(t * 0.2)) * aspect, 0.11 + 0.04 * cos(t * 0.18));
        vec2 c4 = vec2((0.82 + 0.06 * cos(t * 0.16)) * aspect, 0.15 + 0.04 * sin(t * 0.2));
        vec2 c5 = vec2((1.08 + 0.05 * sin(t * 0.14)) * aspect, 0.12 + 0.04 * cos(t * 0.22));

        float x1 = clamp(c1.x / aspect, 0.0, 1.0);
        float x2 = clamp(c2.x / aspect, 0.0, 1.0);
        float x3 = clamp(c3.x / aspect, 0.0, 1.0);
        float x4 = clamp(c4.x / aspect, 0.0, 1.0);
        float x5 = clamp(c5.x / aspect, 0.0, 1.0);

        c1.y = arcHeight(x1) + 0.02 * cos(t * 0.24 + 0.3);
        c2.y = arcHeight(x2) + 0.02 * sin(t * 0.22 + 1.1);
        c3.y = arcHeight(x3) + 0.02 * cos(t * 0.26 + 2.2);
        c4.y = arcHeight(x4) + 0.02 * sin(t * 0.2 + 2.9);
        c5.y = arcHeight(x5) + 0.02 * cos(t * 0.18 + 3.6);

        float b1 = blob(p, c1, 0.68);
        float b2 = blob(p, c2, 0.66);
        float b3 = blob(p, c3, 0.64);
        float b4 = blob(p, c4, 0.66);
        float b5 = blob(p, c5, 0.68);

        vec2 s1 = vec2((0.02 + 0.07 * sin(t * 0.32)) * aspect, arcHeight(0.06) + 0.06);
        vec2 s2 = vec2((0.16 + 0.08 * cos(t * 0.28)) * aspect, arcHeight(0.18) + 0.05);
        vec2 s3 = vec2((0.3 + 0.08 * sin(t * 0.26)) * aspect, arcHeight(0.3) + 0.06);
        vec2 s4 = vec2((0.44 + 0.07 * cos(t * 0.24)) * aspect, arcHeight(0.44) + 0.05);
        vec2 s5 = vec2((0.58 + 0.08 * sin(t * 0.22)) * aspect, arcHeight(0.58) + 0.06);
        vec2 s6 = vec2((0.72 + 0.08 * cos(t * 0.2)) * aspect, arcHeight(0.72) + 0.05);
        vec2 s7 = vec2((0.86 + 0.07 * sin(t * 0.18)) * aspect, arcHeight(0.86) + 0.06);
        vec2 s8 = vec2((1.02 + 0.06 * cos(t * 0.2)) * aspect, arcHeight(0.94) + 0.06);

        float sb1 = blob(p, s1, 0.32);
        float sb2 = blob(p, s2, 0.31);
        float sb3 = blob(p, s3, 0.32);
        float sb4 = blob(p, s4, 0.3);
        float sb5 = blob(p, s5, 0.31);
        float sb6 = blob(p, s6, 0.32);
        float sb7 = blob(p, s7, 0.31);
        float sb8 = blob(p, s8, 0.33);

        vec2 v1 = vec2((0.12 + 0.06 * sin(t * 0.3)) * aspect, arcHeight(0.12) + 0.03);
        vec2 v2 = vec2((0.28 + 0.05 * cos(t * 0.26)) * aspect, arcHeight(0.28) + 0.02);
        vec2 v3 = vec2((0.44 + 0.06 * sin(t * 0.28)) * aspect, arcHeight(0.44) + 0.03);
        vec2 v4 = vec2((0.6 + 0.05 * cos(t * 0.24)) * aspect, arcHeight(0.6) + 0.02);
        vec2 v5 = vec2((0.76 + 0.06 * sin(t * 0.26)) * aspect, arcHeight(0.76) + 0.03);
        vec2 v6 = vec2((0.9 + 0.05 * cos(t * 0.22)) * aspect, arcHeight(0.9) + 0.02);

        float voids = blob(p, v1, 0.24) + blob(p, v2, 0.23) + blob(p, v3, 0.24) + blob(p, v4, 0.22) + blob(p, v5, 0.24) + blob(p, v6, 0.23);

        vec2 e1 = vec2((-0.22 + 0.04 * sin(t * 0.2)) * aspect, -0.05 + 0.02 * cos(t * 0.18));
        vec2 e2 = vec2((0.02 + 0.03 * cos(t * 0.22)) * aspect, -0.04 + 0.02 * sin(t * 0.2));
        vec2 e3 = vec2((0.98 + 0.03 * sin(t * 0.19)) * aspect, -0.04 + 0.02 * cos(t * 0.21));
        vec2 e4 = vec2((1.22 + 0.04 * cos(t * 0.17)) * aspect, -0.05 + 0.02 * sin(t * 0.19));

        float edgeFill = blob(p, e1, 0.5) + blob(p, e2, 0.48) + blob(p, e3, 0.48) + blob(p, e4, 0.5);

        float primary = (b1 + b2 + b3 + b4 + b5) * 1.1;
        float secondary = (sb1 + sb2 + sb3 + sb4 + sb5 + sb6 + sb7 + sb8) * 0.78;
        float field = clamp(primary + secondary + edgeFill * 0.8 - voids * 0.95, 0.0, 2.2);

        float arc = arcHeight(uv.x);
        float arcSoft = 0.09;
        float maskY = uv.y * 1.2 - 0.12;
        float arcMask = 1.0 - smoothstep(arc - arcSoft, arc + arcSoft, maskY);
        float bottomMask = 1.0 - smoothstep(0.2, 0.98, maskY);
        float mask = arcMask * bottomMask;

        float gapCurve = arc - 0.12;
        float gapSoft = 0.045;
        float gapBand = smoothstep(gapCurve - gapSoft, gapCurve + gapSoft, maskY);
        gapBand *= 1.0 - smoothstep(gapCurve + gapSoft, gapCurve + gapSoft * 2.6, maskY);
        float edgeFade = smoothstep(0.08, 0.24, uv.x) * smoothstep(0.92, 0.76, uv.x);
        float gap = gapBand * edgeFade;
        field = max(0.0, field - gap * 1.25);
        field *= mask;

        float centerBand = 1.0 - smoothstep(0.0, 0.1, abs(maskY - arc));
        float centerBoost = smoothstep(0.28, 0.72, uv.x) * smoothstep(0.15, 0.85, centerBand);
        field = clamp(field + centerBoost * 0.5, 0.0, 2.4);

        float ripple = sin(p.x * 3.1 + t * 0.35) * sin(p.y * 4.6 - t * 0.28);
        float ripple2 = sin(p.x * 6.2 - t * 0.2 + p.y * 1.4) * 0.6;
        float breakup = clamp((ripple + ripple2) * 0.5 + 0.5, 0.0, 1.0);
        float interior = smoothstep(0.14, 0.62, maskY);
        float holes = smoothstep(0.55, 0.78, breakup) * interior;
        field = max(0.0, field - holes * 0.7);
        float opacityMod = mix(0.55, 1.0, smoothstep(0.15, 0.8, breakup));

        vec3 navy = vec3(0.039, 0.055, 0.153);
        vec3 orange = vec3(0.945, 0.353, 0.133);
        vec3 amber = vec3(0.98, 0.52, 0.22);

        float warm = smoothstep(0.18, 0.95, field);
        vec3 col = mix(navy, orange, warm);
        col = mix(col, amber, smoothstep(0.45, 1.35, field) * 0.55);

        float ridge1 = pow(abs(sin((p.x * 2.8 + t * 0.18 + p.y * 0.9) * 8.5)), 10.0);
        float ridge2 = pow(abs(sin((p.x * 2.2 - t * 0.15 + p.y * 1.3) * 7.8)), 10.0);
        float ridges = (ridge1 + ridge2) * 0.3;
        col += ridges * vec3(0.22, 0.12, 0.05) * warm;

        float edge = smoothstep(0.35, 0.82, field) - smoothstep(0.82, 1.05, field);
        col += edge * vec3(0.22, 0.12, 0.06);

        col *= mask * opacityMod;
        col = pow(col, vec3(0.96));

        float alpha = clamp(mask * opacityMod * smoothstep(0.06, 0.97, field), 0.0, 1.0);
        gl_FragColor = vec4(col, alpha);
      }
    `;

    const createShader = (type, source) => {
      const shader = gl.createShader(type);
      if (!shader) return null;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error(gl.getShaderInfoLog(shader) || 'Shader compile failed.');
        gl.deleteShader(shader);
        return null;
      }
      return shader;
    };

    const vertexShader = createShader(gl.VERTEX_SHADER, vertexSource);
    const fragmentShader = createShader(gl.FRAGMENT_SHADER, fragmentSource);
    if (!vertexShader || !fragmentShader) return;

    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error(gl.getProgramInfoLog(program) || 'Program link failed.');
      return;
    }

    const positionLoc = gl.getAttribLocation(program, 'aPosition');
    const timeLoc = gl.getUniformLocation(program, 'uTime');
    const resolutionLoc = gl.getUniformLocation(program, 'uResolution');

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 3, -1, -1, 3]),
      gl.STATIC_DRAW
    );

    gl.useProgram(program);
    gl.enableVertexAttribArray(positionLoc);
    gl.vertexAttribPointer(positionLoc, 2, gl.FLOAT, false, 0, 0);

    gl.disable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    let width = 0;
    let height = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const nextWidth = Math.max(1, Math.floor(rect.width * dpr));
      const nextHeight = Math.max(1, Math.floor(rect.height * dpr));

      if (nextWidth !== width || nextHeight !== height) {
        width = nextWidth;
        height = nextHeight;
        canvas.width = width;
        canvas.height = height;
        gl.viewport(0, 0, width, height);
      }
    };

    let rafId = 0;
    const render = (time) => {
      resize();
      gl.useProgram(program);
      if (timeLoc) gl.uniform1f(timeLoc, time * 0.001);
      if (resolutionLoc) gl.uniform2f(resolutionLoc, width, height);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      rafId = requestAnimationFrame(render);
    };

    rafId = requestAnimationFrame(render);
    window.addEventListener('resize', resize);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener('resize', resize);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      gl.deleteShader(vertexShader);
      gl.deleteShader(fragmentShader);
    };
  }, []);

  return (
    <div className="nebula-container">
      <canvas ref={canvasRef} className="aurora-canvas" />
    </div>
  );
}