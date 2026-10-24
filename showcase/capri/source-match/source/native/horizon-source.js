function createCapriHorizon(canvas,motionReduced){
/* MIT License

Copyright (c) 2026 Siddharth Meena

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

 */
const cv=canvas,stage=canvas.parentElement,el={mass:{textContent:''},stats:{textContent:''}};
function setSpec(){}function syncSpec(){}

/* ---------- glyphs ---------- */
const RAMPS = { classic: ' .:-=+*#%@', binary: ' 01' };
const ASCII = Array.from({ length: 95 }, (_, i) => String.fromCharCode(32 + i));
const STAR = '*'.charCodeAt(0) - 32;
const DOT = '.'.charCodeAt(0) - 32;
// six sampling points per cell, shared by the shape matcher and the scene shader
const SAMPLE_POINTS = [[0.28, 0.2], [0.72, 0.2], [0.28, 0.5], [0.72, 0.5], [0.28, 0.8], [0.72, 0.8]];

/* ---------- physics ---------- */
// lens scale, camera distance, page distance, inner and outer disk radius in units of rs
const K = 17.5, CAM_D = 50, PAGE_D = 25, RIN = 3.0, ROUT = 9.5;

/* ---------- particles ---------- */
const MAXP = 900, TRAIL = 4;

/* ---------- settings ---------- */
const STORAGE_KEY = 'ascii-horizon-v1';
const DEFAULTS = {
  mass: 0.45, bright: 1, spin: 1, tilt: 9, eat: true, drift: true, mouse: true,
  theme: 'stage', cell: innerWidth < 640 ? 8 : 10, ramp: 'shape', accent: true,
  aspect: 'fill', stats: false, ignoreReduced: false, text: ''
};

const THEMES = {
  paper: { bg: '#f7f7f4', ink: '#15140f', pink: '#f81a86', meta: '#f7f7f4' },
  stage: { bg: '#100a19', ink: '#a69ab1', pink: '#ff1265', meta: '#100a19' },
  pink: { bg: '#f81a86', ink: '#15140f', pink: '#f7f7f4', meta: '#f81a86' }
};
const THEME_ORDER = ['stage', 'paper', 'pink'];

const VIEWS = [
  { tilt: 9, roll: -0.09, name: 'Edge on' },
  { tilt: 30, roll: -0.26, name: 'Tilted' },
  { tilt: 78, roll: 0, name: 'Face on' }
];


const S=Object.assign({},DEFAULTS,{cell:6,theme:"stage",stats:false,ignoreReduced:false,text:"The current request, latest correction, relevant source and acceptance checks travel together. Keep original evidence retrievable. Hand off the task with its scope, write ownership, findings and limits. Review the candidate against the request before the human decides what ships."});
const reduced=()=>motionReduced();
const ESSAY=S.text;

const $ = (s) => document.querySelector(s);
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ss = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const bump = (x, a, b) => { const t = clamp((x - a) / (b - a)); return Math.sin(Math.PI * t); };
const lerp = (a, b, t) => a + (b - a) * t;
const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
const DEG = Math.PI / 180;





// grid, atlas and gpu resources
const G = {
  dpr: 1, cw: 8, ch: 13, cols: 1, rows: 1, offX: 0, offY: 0, gw: 1, gh: 1, unit: 1, W: 1, H: 1,
  fbo: null, tData: null, atlas: null, shape: null, perRow: 1, rampIdx: [], rect: null,
  page: null, tPage: null, pageDirty: false, pageTotal: 0, box: [0, 0, 1, 1]
};

// the hole: position, spring velocity, disk orientation, feed kick and pulse
const H = {
  x: 0, y: 0, vx: 0, vy: 0, tx: 0, ty: 0,
  tilt: S.tilt * DEG, roll: -0.09, rollT: -0.09,
  kick: 0, kickV: 0, eaten: 0, pulseT: 9, pulseA: 0, spinT: 0
};

// per frame values handed to the shaders
const U = { rs: 0, disk: 0, rout: ROUT, flash: 1, dot: 0 };

// clocks: intro timeline, sim time, smoothed hole speed
const st = { paused: false, intro: 0, sim: 0, speed: 0 };

const ptr = { down: false, dragging: false, sx: 0, sy: 0, lx: 0, ly: 0, t0: 0 };

// supersampling drops from 6 rays to 1 per cell if frames run slow
const perf = { ss: 6, slow: 0 };

const parts = [];

// current colors, eased toward the active theme every frame
const col = { bg: hex(THEMES.stage.bg), ink: hex(THEMES.stage.ink), pink: hex(THEMES.stage.pink) };


// one oversized triangle that covers the viewport, no vertex buffer needed
const FULLSCREEN_VS = `#version 300 es
void main(){ vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2)); gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0); }`;



// one fragment per glyph cell: bend rays around the hole, shade the disk, or read the page where the ray lands
const SCENE_FS = `#version 300 es
precision highp float;
precision highp int;
out vec4 o0;
uniform vec2 uGrid, uCell, uGridPx;
uniform float uUnit, uTime;
uniform vec2 uHole;
uniform float uK, uRs, uD, uDp;
uniform vec3 uN, uU, uV;
uniform float uDiskW, uRin, uRout, uSpinT, uBright, uHot;
uniform float uPageTone, uGlow, uThetaE, uLens;
uniform vec4 uBox;
uniform vec2 uTaper;
uniform vec4 uPulse;
uniform ivec2 uDotCell;
uniform float uDot;
uniform sampler2D uPage, uShape;
uniform int uSS, uShapeOn, uRampN;
uniform int uRamp[96];
uniform float uCon, uDith;

const vec2 SP[6] = vec2[6](vec2(0.28, 0.2), vec2(0.72, 0.2), vec2(0.28, 0.5), vec2(0.72, 0.5), vec2(0.28, 0.8), vec2(0.72, 0.8));

float hash(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float h3(vec3 p){ p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float vnoise(vec3 x){
  vec3 i = floor(x), f = fract(x); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(h3(i), h3(i + vec3(1, 0, 0)), f.x), mix(h3(i + vec3(0, 1, 0)), h3(i + vec3(1, 1, 0)), f.x), f.y),
             mix(mix(h3(i + vec3(0, 0, 1)), h3(i + vec3(1, 0, 1)), f.x), mix(h3(i + vec3(0, 1, 1)), h3(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}

// emission of the disk where a ray crosses its plane; dir points back toward the camera
float diskAt(vec3 x, vec3 dir){
  float rr = length(x);
  float rin = uRin * uRs, rout = uRout * uRs;
  if (rr < rin * 0.9 || rr > rout) return 0.0;
  float rn = rr / uRs;
  float ang = atan(dot(x, uV), dot(x, uU));
  // keplerian shear: inner rings lap the outer ones
  float a2 = ang - mod(2.4 * pow(rn, -1.5) * uSpinT, 6.2831853);
  vec3 c = vec3(cos(a2) * 1.6, sin(a2) * 1.6, rn * 1.25);
  float n = vnoise(c) * 0.5 + vnoise(c * vec3(2.0, 2.0, 3.4) + 7.0) * 0.32 + vnoise(c * vec3(4.0, 4.0, 8.0) + 13.0) * 0.18;
  float bands = 0.12 + 1.45 * smoothstep(0.34, 0.8, n);
  float prof = pow(rin / rr, 1.5) * smoothstep(rin * 0.9, rin * 1.15, rr) * (1.0 - smoothstep(rout * 0.42, rout, rr));
  vec3 vd = normalize(cross(uN, x));
  float beta = clamp(sqrt(0.5 / max(rn - 1.0, 0.4)), 0.0, 0.55);
  float dop = sqrt(1.0 - beta * beta) / (1.0 - beta * dot(vd, dir));
  float grav = sqrt(max(1.0 - 1.0 / rn, 0.05));
  return 2.6 * prof * bands * pow(dop * grav, 2.0);
}

// em: disk light, hp: how much of the page shows through, off: where on the page the ray lands, ring: photon ring
void trace(vec2 q, out float em, out float hp, out vec2 off, out float ring, out float cap){
  em = 0.0; hp = 1.0; off = vec2(0.0); ring = 0.0; cap = 0.0;
  if (uRs < 1e-4) return;
  vec3 ro = vec3(0.0, 0.0, -uD);
  vec3 rd = normalize(vec3(q * uK / uD, 1.0));
  vec3 p = ro, v = rd;
  vec3 hc = cross(p, v);
  float k = 1.5 * uRs * dot(hc, hc);
  float tr = 1.0, rmin = 1e3;
  hp = 0.0;
  for (int i = 0; i < 220; i++) {
    float r = length(p);
    rmin = min(rmin, r);
    if (r < uRs) { tr = 0.0; cap = 1.0; break; }
    float dt = clamp(0.065 * r, 0.04 * uRs, 4.0);
    vec3 a = -k * p / (r * r * r * r * r);
    vec3 pn = p + v * dt + 0.5 * a * dt * dt;
    float rn = length(pn);
    vec3 an = -k * pn / (rn * rn * rn * rn * rn);
    v += 0.5 * (a + an) * dt;
    float s0 = dot(p, uN), s1 = dot(pn, uN);
    if (uDiskW > 0.0 && s0 * s1 <= 0.0 && s0 != s1) {
      vec3 x = mix(p, pn, s0 / (s0 - s1));
      float e = diskAt(x, -normalize(v)) * uDiskW * uBright;
      em += tr * e;
      tr *= 1.0 - clamp(e * 0.45, 0.0, 0.94);
      if (tr < 0.02) break;
    }
    if (pn.z >= uDp) {
      vec3 x = mix(p, pn, (uDp - p.z) / (pn.z - p.z));
      vec3 x0 = ro + rd * ((uDp - ro.z) / rd.z);
      off = (x.xy - x0.xy) * uD / (uK * (uD + uDp));
      hp = tr;
      break;
    }
    p = pn;
    if (rn > uD * 1.7) break;
  }
  ring = uDiskW * 0.7 * exp(-pow((rmin / uRs - 1.53) / 0.045, 2.0));
}
float lumOf(float em, float ring){ return 1.0 - exp(-1.6 * (em + ring)); }

void main(){
  ivec2 fc = ivec2(gl_FragCoord.xy);
  float row = uGrid.y - 1.0 - float(fc.y);
  vec2 cid = vec2(float(fc.x), row);
  vec2 cellTL = cid * uCell;
  float hc = hash(cid + 17.0);
  vec2 qc = (cellTL + uCell * 0.5 - uGridPx * 0.5) / uUnit; qc.y = -qc.y; qc -= uHole;
  float em, hp, rg, cp; vec2 off;
  trace(qc, em, hp, off, rg, cp);
  float lc = lumOf(em, rg);
  float rq = length(qc);
  float rqr = rq * uK;
  bool near = uDiskW > 0.0 && rqr < uRout * uRs * 1.3 + 4.0 * uRs;
  bool full = uSS == 6 && near;
  float s[6];
  float m = lc, tone = lc;
  if (full) {
    m = 0.0; tone = 0.0;
    for (int i = 0; i < 6; i++) {
      vec2 q = (cellTL + uCell * SP[i] - uGridPx * 0.5) / uUnit; q.y = -q.y; q -= uHole;
      float e2, h2, r2, c2; vec2 o2;
      trace(q, e2, h2, o2, r2, c2);
      s[i] = lumOf(e2, r2); m = max(m, s[i]); tone += s[i];
    }
    tone /= 6.0;
  } else {
    for (int i = 0; i < 6; i++) s[i] = lc;
  }

  // the page as this cell sees it through the lens
  int pg_g = 0; float pageT = 0.0;
  bool inBox = cid.x >= uBox.x && cid.y >= uBox.y && cid.x < uBox.z && cid.y < uBox.w;
  if (hp > 0.03 && inBox) {
    // a real point lens shifts the whole page by 1/r; taper the tail so far text stays readable
    float tap = exp(-pow(max(rq - uTaper.x, 0.0) / uTaper.y, 2.0));
    vec2 pc = cid + 0.5 + vec2(off.x, -off.y) * tap * uUnit / uCell;
    float rip = 0.0;
    if (uPulse.y > 0.0) {
      rip = exp(-pow((rq - uPulse.x) / uPulse.z, 2.0));
      vec2 dir = qc / max(rq, 1e-4);
      pc += vec2(dir.x, -dir.y) * uPulse.y * rip;
      rip *= clamp(uPulse.y / 3.0, 0.0, 1.0);
    }
    ivec2 ip = ivec2(floor(pc));
    if (ip.x >= 0 && ip.y >= 0 && ip.x < int(uGrid.x) && ip.y < int(uGrid.y)) {
      vec4 pg = texelFetch(uPage, ip, 0);
      if (pg.g > 0.5) {
        pg_g = int(pg.r * 255.0 + 0.5);
        // the disk lights the page around it; stretched letters near the ring catch more of it
        // the far page stays quiet; letters lensed into the einstein ring light up
        float ringB = uThetaE > 0.0 ? exp(-pow((rq / uThetaE - 1.05) / 0.55, 2.0)) : 0.0;
        float glow = uGlow * uDiskW * exp(-rqr / (uRs * 7.0));
        pageT = mix(uPageTone, 1.0, 0.8 * ringB * uLens) + glow + 0.45 * rip;
        pageT *= min(1.0, hp * 1.15 + 0.05);
      }
    }
  }

  int gi = 0; float outT = 0.0, pink = 0.0, kind = 0.0;
  if (cp > 0.5 && lc < 0.3) { m = 0.0; pg_g = 0; }
  if (m > 0.07 && tone > 0.04) {
    if (uShapeOn == 1 && full && tone > 0.1) {
      vec4 v0 = vec4(s[0], s[1], s[2], s[3]); vec2 v1 = vec2(s[4], s[5]);
      v0 = pow(v0 / m, vec4(uCon)) * m; v1 = pow(v1 / m, vec2(uCon)) * m;
      vec4 dz = vec4(hash(cid + 3.1), hash(cid + 7.7), hash(cid + 11.3), hash(cid + 19.9)) - 0.5;
      vec2 dz2 = vec2(hash(cid + 23.5), hash(cid + 29.1)) - 0.5;
      v0 = max(v0 + dz * uDith * step(0.001, v0), 0.0); v1 = max(v1 + dz2 * uDith * step(0.001, v1), 0.0);
      float best = 1e9;
      for (int g = 1; g < 95; g++) {
        vec4 a = texelFetch(uShape, ivec2(g, 0), 0); vec2 b2 = texelFetch(uShape, ivec2(g, 1), 0).xy;
        vec4 da = a - v0; vec2 db = b2 - v1;
        float dd = dot(da, da) + dot(db, db);
        if (dd < best) { best = dd; gi = g; }
      }
      if (dot(v0, v0) + dot(v1, v1) < best) gi = 0;
    } else {
      int idx = int(clamp(floor(tone * float(uRampN - 1) + 0.5 + (hc - 0.5) * 0.3), 0.0, float(uRampN - 1)));
      gi = uRamp[idx];
    }
    outT = tone;
    pink = em > uHot && hc > 0.3 ? 1.0 : 0.0;
  }
  // a faint disk that resolves to a blank glyph lets the page through
  if (gi == 0 && pg_g > 0) { gi = pg_g; outT = max(pageT, lc); pink = 0.0; kind = 1.0; }
  if (uDot > 0.0 && fc.x == uDotCell.x && int(row) == uDotCell.y) { gi = ${STAR}; pink = 1.0; outT = uDot; kind = 0.0; }
  o0 = vec4(float(gi) / 255.0, clamp(outT, 0.0, 1.0), pink, kind);
}`;


// pass 2: expand each cell of the data texture into its glyph from the atlas
const GLYPH_FS = `#version 300 es
precision highp float;
precision highp int;
out vec4 o;
uniform sampler2D uData, uAtlas;
uniform int uPerRow;
uniform vec3 uBg, uInk, uPink;
uniform float uAccentOn;
uniform vec2 uOff, uCellD, uGrid, uCanvas;
void main(){
  vec2 px = vec2(gl_FragCoord.x, uCanvas.y - gl_FragCoord.y) - uOff;
  vec2 cf = floor(px / uCellD);
  if (cf.x < 0.0 || cf.y < 0.0 || cf.x >= uGrid.x || cf.y >= uGrid.y) { o = vec4(uBg, 1.0); return; }
  ivec2 cell = ivec2(cf);
  vec4 d = texelFetch(uData, ivec2(cell.x, int(uGrid.y) - 1 - cell.y), 0);
  int gi = int(floor(d.r * 255.0 + 0.5));
  if (gi == 0) { o = vec4(uBg, 1.0); return; }
  float tone = d.g;
  vec3 col = uInk; float k;
  if (d.b > 0.5 && uAccentOn > 0.5) { col = uPink; k = max(tone, 0.6); }
  else if (d.a > 0.5) k = tone;
  else k = 0.3 + 0.7 * smoothstep(0.0, 0.85, tone);
  vec2 lp = px - cf * uCellD;
  ivec2 ap = ivec2((gi % uPerRow) * int(uCellD.x) + int(lp.x), (gi / uPerRow) * int(uCellD.y) + int(lp.y));
  float a = texelFetch(uAtlas, ap, 0).a;
  o = vec4(mix(uBg, col, a * k), 1.0);
}`;


// eaten letters, drawn as point sprites over the grid
const PARTICLE_VS = `#version 300 es
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec3 aInfo;
uniform vec2 uCanvas;
uniform float uSize;
out vec3 vInfo;
void main(){ vInfo = aInfo; gl_Position = vec4(aPos.x / uCanvas.x * 2.0 - 1.0, 1.0 - aPos.y / uCanvas.y * 2.0, 0.0, 1.0); gl_PointSize = ceil(uSize * abs(aInfo.z)); }`;

const PARTICLE_FS = `#version 300 es
precision highp float;
precision highp int;
in vec3 vInfo;
out vec4 o;
uniform sampler2D uAtlas;
uniform int uPerRow;
uniform vec2 uCellD;
uniform float uSize, uAccentOn;
uniform vec3 uInk, uPink, uBg;
void main(){
  // z carries the letter's scale, its sign says pink
  float sc = abs(vInfo.z), ps = ceil(uSize * sc);
  vec2 lp = (gl_PointCoord * ps - (vec2(ps) - uCellD * sc) * 0.5) / sc;
  if (lp.x < 0.0 || lp.y < 0.0 || lp.x >= uCellD.x || lp.y >= uCellD.y) discard;
  int gi = int(vInfo.x + 0.5);
  ivec2 ap = ivec2((gi % uPerRow) * int(uCellD.x) + int(lp.x), (gi / uPerRow) * int(uCellD.y) + int(lp.y));
  float a = texelFetch(uAtlas, ap, 0).a;
  vec3 c = vInfo.z > 0.0 && uAccentOn > 0.5 ? uPink : uInk;
  // letters knock out the cell behind them so they read over the disk; trail dots do not
  if (vInfo.y > 1.5) { o = vec4(mix(uBg, c, a), (vInfo.y - 2.0) * (0.85 + 0.15 * a)); return; }
  a *= vInfo.y;
  if (a < 0.004) discard;
  o = vec4(c, a);
}`;



let gl = null;

function initGL(canvas) {
  gl = canvas.getContext('webgl2', { antialias: false, alpha: false, depth: false, stencil: false, premultipliedAlpha: false, powerPreference: 'high-performance', preserveDrawingBuffer: false });
  return gl;
}

function compile(type, src) {
  const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) { const log = gl.getShaderInfoLog(s); console.error(log); throw new Error(log); }
  return s;
}

// links a program and collects every active uniform location by name
function program(fs, vs = FULLSCREEN_VS) {
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl.VERTEX_SHADER, vs)); gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  const u = {};
  const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < n; i++) { const info = gl.getActiveUniform(p, i); const name = info.name.replace(/\[0\]$/, ''); u[name] = gl.getUniformLocation(p, info.name); }
  return { p, u };
}

function makeTex(w, h, data) {
  const t = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, t);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  if (data instanceof Uint8Array) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
  else if (data) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, data);
  else gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
  return t;
}

const fboFor = (tex) => { const f = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, f); gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0); gl.bindFramebuffer(gl.FRAMEBUFFER, null); return f; };







const fontsReady = Promise.race([document.fonts.load('400 22px "Martian Mono"'), new Promise((r) => setTimeout(r, 2500))]).catch(() => {});
const fontAt = (px) => `400 ${px}px "Martian Mono", ui-monospace, Menlo, monospace`;

function drawAtlasGlyphs(x, glyphs, cw, ch, fpx, perRow) {
  x.font = fontAt(fpx); x.textBaseline = 'middle'; x.textAlign = 'center'; x.fillStyle = '#fff';
  glyphs.forEach((g, i) => { const gx = (i % perRow) * cw, gy = Math.floor(i / perRow) * ch; x.fillText(g, gx + cw / 2, gy + ch / 2 + fpx * 0.04); });
}

// coverage of each printable glyph in six sampling circles, matched against six rays per cell
function buildShapes() {
  const fpx = 48, c = document.createElement('canvas'), x = c.getContext('2d', { willReadFrequently: true });
  x.font = fontAt(fpx);
  const cw = Math.round(x.measureText('M').width), ch = Math.round(fpx * 13 / 11);
  c.width = cw * 95; c.height = ch;
  drawAtlasGlyphs(x, ASCII, cw, ch, fpx, 95);
  const img = x.getImageData(0, 0, c.width, c.height).data;
  const R = 0.21 * cw;
  const vec = ASCII.map((_, g) => SAMPLE_POINTS.map(([fx, fy]) => {
    const cx = g * cw + fx * cw, cy = fy * ch; let sum = 0, n = 0;
    for (let yy = Math.floor(cy - R); yy <= Math.ceil(cy + R); yy++) for (let xx = Math.floor(cx - R); xx <= Math.ceil(cx + R); xx++) {
      if ((xx - cx) ** 2 + (yy - cy) ** 2 > R * R) continue;
      sum += img[(yy * c.width + xx) * 4 + 3] / 255; n++;
    }
    return sum / n;
  }));
  const mx = [0, 1, 2, 3, 4, 5].map((k) => Math.max(1e-3, ...vec.map((v) => v[k])));
  const data = new Uint8Array(95 * 2 * 4);
  vec.forEach((v, g) => {
    for (let k = 0; k < 6; k++) { const row = k < 4 ? 0 : 1, ch2 = k < 4 ? k : k - 4; data[(row * 95 + g) * 4 + ch2] = Math.round(clamp(v[k] / mx[k]) * 255); }
  });
  if (G.shape) gl.deleteTexture(G.shape);
  G.shape = makeTex(95, 2, data);
}

// every printable glyph at the current cell size, packed into one texture
function buildAtlas() {
  const ramp = RAMPS[S.ramp] || RAMPS.classic;
  const dpr = G.dpr, fpx = S.cell * dpr;
  const c = document.createElement('canvas'), x = c.getContext('2d');
  x.font = fontAt(fpx);
  G.cw = Math.max(2, Math.round(x.measureText('M').width));
  G.ch = Math.max(3, Math.round(S.cell * (13 / 11) * dpr));
  G.perRow = Math.max(1, Math.floor(Math.min(4096, gl.getParameter(gl.MAX_TEXTURE_SIZE)) / G.cw));
  c.width = Math.min(ASCII.length, G.perRow) * G.cw; c.height = Math.ceil(ASCII.length / G.perRow) * G.ch;
  drawAtlasGlyphs(x, ASCII, G.cw, G.ch, fpx, G.perRow);
  if (G.atlas) gl.deleteTexture(G.atlas);
  G.atlas = makeTex(c.width, c.height, c);
  G.rampIdx = [...ramp].map((ch) => Math.max(0, ASCII.indexOf(ch)));
}







// keep to printable ascii, the atlas has nothing else
function cleanText(s) {
  return s.replace(/\r/g, '').replace(/[\u2018\u2019]/g, "'").replace(/[\u201c\u201d]/g, '"').replace(/\s*[\u2014\u2013]\s*/g, ', ')
    .replace(/\u2026/g, '...').replace(/\t/g, ' ').replace(/[^\x20-\x7e\n]/g, '');
}

// typesets the text into the grid; r holds the glyph, g says a letter is still on the page
function buildPage() {
  const cols = G.cols, rows = G.rows;
  const src = cleanText(S.text && S.text.trim().length > 1 ? S.text : ESSAY);
  let paras = src.split(/\n\s*\n/).map((p) => p.replace(/\s*\n\s*/g, ' ').trim()).filter(Boolean);
  // a short text, like a tweet, runs on as one long paragraph instead of stacking copies
  const len = paras.join(' ').length;
  if (len && len < 900) paras = [Array(Math.ceil(cols * rows / len) + 1).fill(paras.join(' ')).join(' ')];
  const mx = Math.max(2, Math.round(cols * 0.045));
  const top = Math.ceil(8 * G.dpr / G.ch), bot = Math.ceil(8 * G.dpr / G.ch);
  const width = Math.max(8, cols - mx * 2);
  const lines = [];
  let guard = 0;
  while (lines.length < rows && guard++ < 60) {
    for (const [pi, p] of paras.entries()) {
      if (guard > 1 && pi === 0 && p === p.toUpperCase()) continue;
      // set like a book: indented paragraphs, no blank lines, so the lens always has letters to bend
      const head = pi === 0 && p === p.toUpperCase();
      const words = p.split(/ +/);
      let line = head || (pi === 0 && lines.length === 0) ? '' : '  ';
      for (let w of words) {
        while (w.length > width) { if (line) { lines.push(line); line = ''; } lines.push(w.slice(0, width)); w = w.slice(width); }
        if (!line.trim()) line += w;
        else if (line.length + 1 + w.length <= width) line += ' ' + w;
        else { lines.push(line); line = w; }
      }
      if (line) lines.push(line);
      if (head) lines.push('');
    }
  }
  G.box = [mx, top, cols - mx, rows - bot];
  const data = new Uint8Array(cols * rows * 4);
  let li = 0;
  for (let r = top; r < rows - bot && li < lines.length; r++, li++) {
    const s = lines[li];
    for (let i = 0; i < s.length && mx + i < cols; i++) {
      const g = s.charCodeAt(i) - 32;
      if (g <= 0) continue;
      const o = (r * cols + mx + i) * 4;
      data[o] = g; data[o + 1] = 255; data[o + 3] = 255;
    }
  }
  G.page = data;
  G.pageTotal = data.reduce((n, v, i) => n + (i % 4 === 1 && v ? 1 : 0), 0);
  if (G.tPage) gl.deleteTexture(G.tPage);
  G.tPage = makeTex(cols, rows, data);
  G.pageDirty = false;
  H.eaten = 0; parts.length = 0;
  setSpec();
}








// the stage rect for the chosen aspect, leaving room for the header and footer
function stageBox(){return {x:0,y:0,w:960,h:600};}

function layout() {
  const box = stageBox();


  const dpr = G.dpr;
  G.W = Math.max(1, Math.round(box.w * dpr)); G.H = Math.max(1, Math.round(box.h * dpr));
  if (cv.width !== G.W || cv.height !== G.H) { cv.width = G.W; cv.height = G.H; }
  G.cols = Math.max(1, Math.floor(G.W / G.cw)); G.rows = Math.max(1, Math.floor(G.H / G.ch));
  G.gw = G.cols * G.cw; G.gh = G.rows * G.ch;
  G.offX = Math.floor((G.W - G.gw) / 2); G.offY = Math.floor((G.H - G.gh) / 2);
  G.unit = Math.min(G.gw * (G.gh > G.gw ? 1.12 : 1), G.gh);
  G.rect = box;
  if (G.tData) { gl.deleteTexture(G.tData); gl.deleteFramebuffer(G.fbo); }
  G.tData = makeTex(G.cols, G.rows); G.fbo = fboFor(G.tData);
  buildPage();
}

function rebuildGlyphs() { buildAtlas(); buildShapes(); layout(); }






// intro: a calm page, a pink point, then the mass arrives and the disk lights from the inside out
function introAt(t) {
  if (reduced()) t = 99;
  return {
    m: ss(0.42, 2.05, t),
    dot: ss(0.28, 0.42, t) * (1 - ss(0.95, 1.35, t)),
    disk: ss(0.8, 1.55, t),
    rout: lerp(RIN + 0.6, ROUT, ss(0.85, 2.35, t)),
    flash: 1 + 0.4 * bump(t, 1.85, 3.0),
    eat: t > 2.8
  };
}

// disk normal n and in-plane axes u, v from the current tilt and roll
function diskBasis() {
  const a = H.tilt, r = H.roll;
  const n0 = [0, Math.cos(a), -Math.sin(a)];
  const rz = (v) => [v[0] * Math.cos(r) - v[1] * Math.sin(r), v[0] * Math.sin(r) + v[1] * Math.cos(r), v[2]];
  const n = rz(n0), u = rz([1, 0, 0]);
  const v = [n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0]];
  return { n, u, v };
}

// squared einstein radius of the page plane, in screen units
const thetaE2 = (rs) => 2 * rs * PAGE_D * CAM_D / (K * K * (CAM_D + PAGE_D));

// screen units to grid cells
const cellOf = (x, y) => [(G.gw / 2 + x * G.unit) / G.cw, (G.gh / 2 - y * G.unit) / G.ch];







// pull letters off the page near the hole; faster motion eats a wider, hungrier path
function eat(dt, burst) {
  const rs = U.rs;
  if (!rs || !G.page) return;
  const e2 = thetaE2(rs);
  const R = burst ? 0.11 * Math.sqrt(rs) : 0.04 * Math.sqrt(rs) + 0.015 * clamp(st.speed / 0.6);
  const rate = burst ? 1e9 : 0.7 + 7 * clamp(st.speed / 0.5);
  const [cx, cy] = cellOf(H.x, H.y);
  const rx = Math.ceil(R * G.unit / G.cw) + 1, ry = Math.ceil(R * G.unit / G.ch) + 1;
  const cols = G.cols, rows = G.rows, page = G.page;
  let budget = burst ? 80 : 16;
  for (let r = Math.max(0, Math.floor(cy - ry)); r <= Math.min(rows - 1, Math.ceil(cy + ry)); r++) {
    for (let c = Math.max(0, Math.floor(cx - rx)); c <= Math.min(cols - 1, Math.ceil(cx + rx)); c++) {
      const o = (r * cols + c) * 4;
      if (!page[o + 1]) continue;
      const ux = ((c + 0.5) * G.cw - G.gw / 2) / G.unit - H.x, uy = -((r + 0.5) * G.ch - G.gh / 2) / G.unit - H.y;
      const d = Math.hypot(ux, uy);
      if (d > R) continue;
      const p = burst ? 0.65 : rate * dt * Math.sqrt(1 - d / R);
      if (Math.random() > p) continue;
      page[o + 1] = 0; G.pageDirty = true; H.eaten++;
      spawn(page[o], ux, uy, d, e2);
      if (--budget <= 0) return;
    }
  }
}

// the letter's visible image sits outside the einstein ring, so it peels off from there
function spawn(g, ux, uy, d, e2) {
  if (parts.length >= MAXP || reduced()) return;
  const dir = d > 1e-4 ? [ux / d, uy / d] : [1, 0];
  const th = (d + Math.sqrt(d * d + 4 * e2)) / 2;
  const rel = [dir[0] * th, dir[1] * th];
  const { u, v } = diskBasis();
  const up = [u[0], u[1]], vp = [v[0], v[1] + (v[1] >= 0 ? 0.07 : -0.07)];
  const det = up[0] * vp[1] - up[1] * vp[0];
  let cx = 1, sy = 0;
  if (Math.abs(det) > 1e-3) { cx = (rel[0] * vp[1] - rel[1] * vp[0]) / det; sy = (up[0] * rel[1] - up[1] * rel[0]) / det; }
  else { cx = rel[0]; sy = 0; }
  parts.push({ g, rel, up, vp, phi: Math.atan2(sy, cx), r0: th, age: 0, life: 1.3 + Math.random() * 0.9, hist: [] });
}

// eaten letters spiral in along the disk plane, faster as they get closer
function stepParts(dt) {
  const rEnd = 2.9 * U.rs / K;
  for (let i = parts.length - 1; i >= 0; i--) {
    const p = parts[i];
    p.age += dt;
    const e = p.age / p.life;
    if (e >= 1) { parts.splice(i, 1); continue; }
    const rho = lerp(p.r0, rEnd, e * e * (1.6 - 0.6 * e));
    p.phi += dt * 2.2 * Math.pow(p.r0 / Math.max(rho, 1e-3), 1.5) * (0.4 + 0.6 * S.spin);
    const ox = rho * (Math.cos(p.phi) * p.up[0] + Math.sin(p.phi) * p.vp[0]);
    const oy = rho * (Math.cos(p.phi) * p.up[1] + Math.sin(p.phi) * p.vp[1]);
    const b = ss(0, 0.4, e);
    p.x = H.x + lerp(p.rel[0], ox, b); p.y = H.y + lerp(p.rel[1], oy, b);
    p.hist.unshift([p.x, p.y]); if (p.hist.length > TRAIL * 2) p.hist.pop();
  }
}










let fpsE = 60, statT = 0;

function tick(dt) {
  if (perf.ss === 6) { perf.slow = dt > 0.022 ? perf.slow + dt : Math.max(0, perf.slow - dt * 0.5); if (perf.slow > 1.5) perf.ss = 1; }
  const rm = reduced();
  const sdt = st.paused ? 0 : dt;
  st.intro += sdt; st.sim += sdt;
  const I = introAt(st.intro);

  // the hole wanders on a slow looping path, or holds still with drift off
  let tx = H.tx, ty = H.ty;
  if (S.drift && !rm) {
    const t = st.sim, w = ss(3.2, 6.5, st.intro);
    tx = w * (0.3 * Math.sin(t * 0.17) + 0.07 * Math.sin(t * 0.43 + 1));
    ty = w * (0.1 * Math.sin(t * 0.23 + 0.6) + 0.04 * Math.sin(t * 0.51));
  }
  const lim = [G.gw / 2 / G.unit - 0.04, G.gh / 2 / G.unit - 0.04];
  H.tx = clamp(tx, -lim[0], lim[0]); H.ty = clamp(ty, -lim[1], lim[1]);
  // a slightly underdamped spring follows the target
  if (!ptr.dragging && sdt > 0) {
    const k = 34, c = 2 * Math.sqrt(k) * 0.92;
    const h = Math.min(sdt, 1 / 30);
    H.vx += ((H.tx - H.x) * k - H.vx * c) * h; H.vy += ((H.ty - H.y) * k - H.vy * c) * h;
    H.x += H.vx * h; H.y += H.vy * h;
  }
  st.speed += (Math.hypot(H.vx, H.vy) - st.speed) * (1 - Math.exp(-dt * 8));

  // tilt and roll settle toward their targets
  H.tilt += (S.tilt * DEG - H.tilt) * (1 - Math.exp(-dt * 6));
  H.roll += (H.rollT - H.roll) * (1 - Math.exp(-dt * 6));

  // feeding kicks the mass, a damped spring brings it back
  H.kickV += (-H.kick * 60 - H.kickV * 9) * Math.min(sdt, 1 / 30);
  H.kick += H.kickV * Math.min(sdt, 1 / 30);
  H.pulseT += sdt;
  H.spinT += sdt * (rm ? 0 : S.spin);

  U.rs = S.mass * I.m * (1 + H.kick);
  U.disk = I.disk; U.rout = I.rout; U.flash = I.flash; U.dot = I.dot;

  if (I.eat && S.eat && sdt > 0 && !rm) eat(sdt, false);
  stepParts(sdt);

  const t = THEMES[S.theme] || THEMES.stage;
  const tk = 1 - Math.exp(-dt * 7);
  for (const key of ['bg', 'ink', 'pink']) { const target = hex(t[key]); for (let i = 0; i < 3; i++) col[key][i] += (target[i] - col[key][i]) * tk; }

  if (S.stats) {
    fpsE += (1 / Math.max(dt, 1e-3) - fpsE) * 0.05;
    if ((statT += dt) > 0.5) { statT = 0; el.stats.textContent = `${Math.round(fpsE)} fps, ${G.cols} by ${G.rows} cells`; }
  }
  syncSpec();
  const mtxt = `M ${(S.mass * (1 + H.kick)).toFixed(2)}`;
  if (el.mass.textContent !== mtxt) el.mass.textContent = mtxt;
}











let P1, P2, P3, vao, pvao, pbuf, pdata;
const ramp = new Int32Array(96);

function initRenderer() {
  P1 = program(SCENE_FS); P2 = program(GLYPH_FS); P3 = program(PARTICLE_FS, PARTICLE_VS);
  vao = gl.createVertexArray();
  pvao = gl.createVertexArray(); pbuf = gl.createBuffer();
  // per point: x, y, glyph, alpha, signed scale
  pdata = new Float32Array(MAXP * (TRAIL + 1) * 5);
  gl.bindVertexArray(pvao);
  gl.bindBuffer(gl.ARRAY_BUFFER, pbuf);
  gl.bufferData(gl.ARRAY_BUFFER, pdata.byteLength, gl.DYNAMIC_DRAW);
  gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 20, 0);
  gl.enableVertexAttribArray(1); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 20, 8);
  gl.bindVertexArray(null);
}

// pass 1: trace one ray bundle per cell into a cols x rows data texture
function drawScene() {
  gl.bindVertexArray(vao);
  gl.disable(gl.BLEND);
  gl.bindFramebuffer(gl.FRAMEBUFFER, G.fbo);
  gl.viewport(0, 0, G.cols, G.rows);
  gl.useProgram(P1.p);
  const u = P1.u;
  gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, G.tPage); gl.uniform1i(u.uPage, 0);
  gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, G.shape); gl.uniform1i(u.uShape, 1);
  gl.uniform2f(u.uGrid, G.cols, G.rows);
  gl.uniform2f(u.uCell, G.cw, G.ch);
  gl.uniform2f(u.uGridPx, G.gw, G.gh);
  gl.uniform1f(u.uUnit, G.unit);
  gl.uniform1f(u.uTime, st.sim);
  gl.uniform2f(u.uHole, H.x, H.y);
  gl.uniform1f(u.uK, K); gl.uniform1f(u.uRs, U.rs); gl.uniform1f(u.uD, CAM_D); gl.uniform1f(u.uDp, PAGE_D);
  const B = diskBasis();
  gl.uniform3fv(u.uN, B.n); gl.uniform3fv(u.uU, B.u); gl.uniform3fv(u.uV, B.v);
  gl.uniform1f(u.uDiskW, U.disk);
  gl.uniform1f(u.uRin, RIN * (1 - 0.18 * clamp(S.spin - 1, 0, 1)));
  gl.uniform1f(u.uRout, U.rout);
  gl.uniform1f(u.uSpinT, H.spinT);
  gl.uniform1f(u.uBright, S.bright * U.flash);
  gl.uniform1f(u.uHot, 3.0);
  const dark = S.theme === 'stage';
  gl.uniform1f(u.uPageTone, dark ? 0.4 : 0.5);
  gl.uniform1f(u.uGlow, dark ? 0.16 : 0.1);
  gl.uniform1f(u.uThetaE, Math.sqrt(thetaE2(U.rs)));
  gl.uniform1f(u.uLens, ss(0.05, 0.6, U.rs / Math.max(S.mass, 0.01)));
  gl.uniform4f(u.uBox, G.box[0], G.box[1], G.box[2], G.box[3]);
  const tE = Math.sqrt(thetaE2(Math.max(U.rs, 0.02)));
  gl.uniform2f(u.uTaper, tE * 1.0, tE * 0.38 + 0.015);
  const pr = H.pulseT * 0.95 + 0.05, pa = H.pulseA * Math.exp(-H.pulseT * 1.6);
  gl.uniform4f(u.uPulse, pr, pa > 0.02 ? pa : 0, 0.07, 0);
  const [dcx, dcy] = cellOf(H.x, H.y);
  gl.uniform2i(u.uDotCell, Math.floor(dcx), Math.floor(dcy));
  gl.uniform1f(u.uDot, U.dot);
  gl.uniform1i(u.uSS, perf.ss);
  gl.uniform1i(u.uShapeOn, S.ramp === 'shape' ? 1 : 0);
  ramp.fill(0); G.rampIdx.forEach((x, i) => { ramp[i] = x; });
  gl.uniform1iv(u.uRamp, ramp);
  gl.uniform1i(u.uRampN, G.rampIdx.length);
  gl.uniform1f(u.uCon, 2.1); gl.uniform1f(u.uDith, 0.2);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
}

// pass 2: draw the glyph for every cell to the screen
function drawGlyphs() {
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  gl.viewport(0, 0, G.W, G.H);
  gl.useProgram(P2.p);
  const v = P2.u;
  gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, G.tData); gl.uniform1i(v.uData, 0);
  gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, G.atlas); gl.uniform1i(v.uAtlas, 2);
  gl.uniform1i(v.uPerRow, G.perRow);
  gl.uniform3fv(v.uBg, col.bg); gl.uniform3fv(v.uInk, col.ink); gl.uniform3fv(v.uPink, col.pink);
  gl.uniform1f(v.uAccentOn, S.accent ? 1 : 0);
  gl.uniform2f(v.uOff, G.offX, G.offY);
  gl.uniform2f(v.uCellD, G.cw, G.ch);
  gl.uniform2f(v.uGrid, G.cols, G.rows);
  gl.uniform2f(v.uCanvas, G.W, G.H);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
}

// pass 3: eaten letters on top, pink while they are pulled, ink as they fall, a short trail behind
function drawParticles() {
  if (!parts.length) return;
  let n = 0;
  const toPx = (x, y) => [G.offX + G.gw / 2 + x * G.unit, G.offY + G.gh / 2 - y * G.unit];
  for (const p of parts) {
    const e = p.age / p.life;
    const a = ss(0, 0.06, e) * (1 - ss(0.65, 0.92, e));
    for (let k = TRAIL; k >= 1; k--) {
      const h = p.hist[k * 2 - 1]; if (!h) continue;
      const [x, y] = toPx(h[0], h[1]);
      pdata.set([x, y, DOT, a * 0.75 * (1 - k / (TRAIL + 1)), 1], n * 5); n++;
    }
    const [x, y] = toPx(p.x, p.y);
    // lifts off the page toward you, then shrinks as it falls in
    const sc = 1 + 0.45 * bump(e, 0, 0.7) - 0.45 * ss(0.6, 1, e);
    pdata.set([x, y, p.g, 2 + a, (e < 0.8 ? 1 : -1) * sc], n * 5); n++;
  }
  gl.bindVertexArray(pvao);
  gl.bindBuffer(gl.ARRAY_BUFFER, pbuf);
  gl.bufferSubData(gl.ARRAY_BUFFER, 0, pdata, 0, n * 5);
  gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  gl.useProgram(P3.p);
  const w = P3.u;
  gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, G.atlas); gl.uniform1i(w.uAtlas, 2);
  gl.uniform1i(w.uPerRow, G.perRow);
  gl.uniform2f(w.uCellD, G.cw, G.ch);
  gl.uniform2f(w.uCanvas, G.W, G.H);
  gl.uniform1f(w.uSize, Math.max(G.cw, G.ch));
  gl.uniform1f(w.uAccentOn, S.accent ? 1 : 0);
  gl.uniform3fv(w.uInk, col.ink); gl.uniform3fv(w.uPink, col.pink); gl.uniform3fv(w.uBg, col.bg);
  gl.drawArrays(gl.POINTS, 0, n);
  gl.disable(gl.BLEND);
  gl.bindVertexArray(null);
}

function render() {
  if (G.pageDirty) {
    gl.bindTexture(gl.TEXTURE_2D, G.tPage);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, G.cols, G.rows, gl.RGBA, gl.UNSIGNED_BYTE, G.page);
    G.pageDirty = false;
  }
  drawScene();
  drawGlyphs();
  drawParticles();
}



 if(!initGL(cv))return null;
 G.dpr=1;st.intro=7;initRenderer();rebuildGlyphs();tick(0);render();
 fontsReady.then(()=>rebuildGlyphs());
 return {step(dt){tick(dt);render();},replay(){st.intro=0;st.sim=0;H.kick=0;H.kickV=0;parts.length=0;buildPage();},feed(){H.kickV+=1.2;H.pulseT=0;H.pulseA=.12;eat(1/60,true);},tilt(d){S.tilt=clamp(S.tilt+d,0,78);}};
}
