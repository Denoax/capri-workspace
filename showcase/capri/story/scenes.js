/* Approved compositions, shared scene clocks and source-based effects.
 * Native sharks/horizon are executable source; the other five effects are
 * reference-footage composites. Playback controls never imply runtime approval.
 */
(async function () {
  'use strict';
  const data = JSON.parse(document.getElementById('scene-data').textContent);
  data.rig = window.CAPRI_RIG; data.storyFormats = JSON.parse(document.getElementById('story-data').textContent).formats;
  const actor = new CapriActor(data.rig), reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const ink = '#100a19', pink = '#ff1265', green = '#28fb86';
  const clamp = value => Math.max(0, Math.min(1, value));
  const smooth = value => { const x = clamp(value); return x * x * (3 - 2 * x); };
  const query = new URLSearchParams(location.search), exportName = query.get('export');
  const nativeRoot = document.getElementById('capri-source-scenes');
  const platesRoot = document.getElementById('capri-reference-composites');
  const comicRoot = document.getElementById('handoff-comic-full-sprites');
  document.querySelectorAll('.viz-controls').forEach(node => node.remove());
  const definitions = {
    comic: {element: comicRoot, duration: 9600, still: 800},
    sharks: {element: nativeRoot.querySelector('[data-story-scene="sharks"]'), duration: 4800, still: 1200, native: true},
    horizon: {element: nativeRoot.querySelector('[data-story-scene="horizon"]'), duration: 6400, still: 2200, native: true},
    hands: {duration: 5040, still: 2620, plate: true}, cat: {duration: 8600, still: 3800, plate: true},
    rain: {duration: 500, still: 250, plate: true}, dots: {duration: 4680, still: 2600, plate: true},
    stack: {duration: 10800, still: 2200, plate: true}
  };
  for (const [name, def] of Object.entries(definitions)) {
    if (def.plate) def.element = platesRoot.querySelector(`[data-scene="${name}"]`).closest('.cp-panel');
    def.element.dataset.panel = name;
    if (!def.element.id) def.element.id = 'scene-' + name;
  }
  if (exportName) {
    if (!definitions[exportName]) throw new Error('Unknown export scene');
    document.documentElement.classList.add('export');
    if (query.get('layout') === 'portrait') document.documentElement.classList.add('portrait');
    for (const [name, def] of Object.entries(definitions)) if (name !== exportName) def.element.hidden = true;
    if (exportName !== 'comic') comicRoot.hidden = true;


  }
  // Browser-native shaping uses the locally bundled fonts for every output.
  await Promise.all([actor.ready, document.fonts.ready,
    document.fonts.load('500 30px Manrope'), document.fonts.load('400 18px Inter'),
    document.fonts.load('400 22px "Martian Mono"')]);

  function surface(canvas, width, height) {
    const box = canvas.getBoundingClientRect();
    if (!box.width || !box.height) return null;
    const dpr = exportName ? 1 : Math.min(2, devicePixelRatio || 1);
    const w = Math.round(box.width * dpr), h = Math.round(box.height * dpr);
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    const ctx = canvas.getContext('2d'); ctx.setTransform(w / width, 0, 0, h / height, 0, 0); ctx.clearRect(0, 0, width, height);
    return ctx;
  }
  function eyeAt(time) {
    const samples = data.catEyes;
    let j = 0;
    while (j < samples.length - 2 && time > samples[j + 1].time) j++;
    const a = samples[j], b = samples[j + 1], u = clamp((time - a.time) / (b.time - a.time));
    return a.eyes.map((p, i) => [p[0] * (1 - u) + b.eyes[i][0] * u, p[1] * (1 - u) + b.eyes[i][1] * u]);
  }
  function recolour(name, video, cache, seconds) {
    const frame = Math.floor(seconds * 30);
    if (cache.frame === frame) return cache.canvas;
    const w = video.videoWidth, h = video.videoHeight;
    cache.canvas.width = w; cache.canvas.height = h;
    const ctx = cache.canvas.getContext('2d', {willReadFrequently: true}); ctx.drawImage(video, 0, 0);
    const image = ctx.getImageData(0, 0, w, h), a = image.data;
    const q = smooth((seconds - 1.1) / .85) * (1 - smooth((seconds - 7.1) / 1.3));
    const sample = 4 * (Math.min(h - 1, 12) * w + Math.min(w - 1, 12));
    const blueHands = a[sample + 2] > a[sample] + 12 && a[sample + 2] > 70;
    const catSample = 4 * (Math.min(h - 1, Math.round(h * 78 / 316)) * w + Math.round(w * 5 / 320));
    const catBg = [a[catSample], a[catSample + 1], a[catSample + 2]];
    const catLum = (.2126 * catBg[0] + .7152 * catBg[1] + .0722 * catBg[2]) / 255;
    if (name === 'cat') {
      cache.eyes = eyeAt(seconds).map(prior => {
        const cx = prior[0] * w, cy = prior[1] * h, radius = Math.round(w * .027), sigma = radius * .65;
        let weight = 0, sx = 0, sy = 0;
        for (let y = Math.max(0, Math.floor(cy - radius)); y <= Math.min(h - 1, Math.ceil(cy + radius)); y++) for (let x = Math.max(0, Math.floor(cx - radius)); x <= Math.min(w - 1, Math.ceil(cx + radius)); x++) {
          const i = 4 * (y * w + x), darkness = 1 - (.2126 * a[i] + .7152 * a[i + 1] + .0722 * a[i + 2]) / 255;
          const q = darkness ** 4 * Math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma * sigma));
          weight += q; sx += x * q; sy += y * q;
        }
        if (weight < 1) return prior;
        const max = w * .0125, dx = Math.max(-max, Math.min(max, sx / weight - cx)), dy = Math.max(-max, Math.min(max, sy / weight - cy));
        return [(cx + dx) / w, (cy + dy) / h];
      });
    }
    for (let p = 0; p < a.length; p += 4) {
      const r = a[p], g = a[p + 1], b = a[p + 2], lum = (.2126 * r + .7152 * g + .0722 * b) / 255;
      const x = (p / 4) % w, y = Math.floor(p / 4 / w);
      if (name === 'cat') {
        const cover = x < w * 34 / 320 && y >= h * 80 / 316 && y < h * 130 / 316;
        const inv = 1 - (cover ? catLum : lum), scan = q === 0 ? 0 : clamp((q * 1.3 - x / w) * 4);
        a[p] = (cover ? catBg[0] : r) * (1 - scan) + (16 + 239 * inv) * scan;
        a[p + 1] = (cover ? catBg[1] : g) * (1 - scan) + (10 + 8 * inv) * scan;
        a[p + 2] = (cover ? catBg[2] : b) * (1 - scan) + (25 + 76 * inv) * scan;
      } else if (name === 'rain') {
        const intensity = r / 255, blade = Math.abs(x / w - .5) < .022 && y / h < .61;
        a[p] = 16 + intensity * (blade ? 24 : 239); a[p + 1] = 10 + intensity * (blade ? 241 : 8); a[p + 2] = 25 + intensity * (blade ? 109 : 76);
      } else if (name === 'dots') {
        const orbit = x / w > .30 && x / w < .71 && y / h > .25 && y / h < .55;
        const c = orbit ? (x / w < .50 ? [255, 18, 101] : [40, 251, 134]) : [174, 155, 188];
        a[p] = 16 + lum * (c[0] - 16); a[p + 1] = 10 + lum * (c[1] - 10); a[p + 2] = 25 + lum * (c[2] - 25);
      } else if (name === 'stack') {
        if (lum > .94) { a[p] = 16; a[p + 1] = 10; a[p + 2] = 25; }
        else { const c = b > r + 25 ? [244, 241, 238] : (r > g * 1.15 && g > 45 ? [40, 251, 134] : [255, 18, 101]), k = .60 + .40 * (1 - lum); a[p] = c[0] * k; a[p + 1] = c[1] * k; a[p + 2] = c[2] * k; }
      } else if (name === 'hands' && blueHands) {
        if (b > r + 10) { a[p] = 14 + r * .18; a[p + 1] = 8 + g * .10; a[p + 2] = 20 + b * .24; }
        else { const c = x < w / 2 ? [255, 18, 101] : [40, 251, 134], k = .18 + .82 * lum; a[p] = c[0] * k; a[p + 1] = c[1] * k; a[p + 2] = c[2] * k; }
      }
    }
    ctx.putImageData(image, 0, 0); cache.frame = frame; return cache.canvas;
  }
  function showBeams(ctx, seconds, width, height, refined) {
    const q = smooth((seconds - 2) / .2) * (1 - smooth((seconds - 6.9) / .25));
    if (!q || data.catEyes[Math.min(data.catEyes.length - 1, Math.floor(seconds * 30))].visible === false) return;
    ctx.save(); ctx.globalAlpha = q; ctx.lineCap = 'round';
    for (const [i, p] of (refined || eyeAt(seconds)).entries()) {
      const x = p[0] * width, y = p[1] * height;
      ctx.strokeStyle = green; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(i ? width * 1.15 : -width * .15, y - height * .18); ctx.stroke();
      ctx.strokeStyle = '#eafff1'; ctx.lineWidth = 1; ctx.stroke();
    }
    ctx.restore();
  }
  class Scene {
    constructor(name, def) {
      Object.assign(this, def); this.name = name; this.time = def.still; this.running = false; this.visible = false; this.last = 0; this.frames = 0;
      this.controls = document.createElement('div'); this.controls.className = 'scene-tools';
      this.controls.innerHTML = `<button type="button" data-play>Play</button><button type="button" data-restart>Replay</button><label for="seek-${name}">Time</label><input id="seek-${name}" type="range" min="0" max="${this.duration - 1}" value="${this.time}" step="1"><output aria-live="off"></output>`;
      this.element.appendChild(this.controls); this.status = document.createElement('p'); this.status.className = 'scene-status'; this.status.setAttribute('role', 'status'); this.element.appendChild(this.status);
      this.controls.querySelector('[data-play]').onclick = () => this.running ? this.pause() : this.play();
      this.controls.querySelector('[data-restart]').onclick = async () => { await this.renderAt(0); if (!reduce.matches) this.play(); };
      this.controls.querySelector('input').oninput = event => this.renderAt(Number(event.target.value)).catch(reportError);
      if (name === 'comic') {
        this.cards = [...this.element.querySelectorAll('[data-card]')];
        this.cards.forEach(card => { const button = card.querySelector('button'), details = this.element.querySelector('#hcf-' + card.dataset.card + '-brief'); button.onclick = () => { details.open = !details.open; }; details.addEventListener('toggle', () => button.setAttribute('aria-expanded', String(details.open))); });
        const pass = document.createElement('button'); pass.type = 'button'; pass.textContent = 'Pass the brief'; pass.onclick = async () => { await this.renderAt(2200); if (!reduce.matches) this.play(); else this.status.textContent = 'Plan → Build → Review. The human decides.'; }; this.controls.appendChild(pass);
      }
      if (name === 'sharks' || name === 'horizon') this.wireNativeInteraction();
    }
    async initialize() {
      if (this.initializing) return this.initializing;
      this.initializing = (async () => {
        if (this.plate) {
          const video = document.createElement('video'); video.muted = true; video.loop = true; video.playsInline = true; video.preload = 'auto';
          video.src = data.plates[this.name].src; this.video = video; this.cache = {canvas: document.createElement('canvas'), frame: -1};
          await new Promise((resolve, reject) => { if (video.readyState >= 2) resolve(); video.addEventListener('loadeddata', resolve, {once: true}); video.addEventListener('error', () => reject(new Error('Reference plate unavailable: ' + this.name)), {once: true}); });
        } else if (this.native) this.resetNative();
      })();
      return this.initializing;
    }
    resetNative() {
      const selector = this.name === 'sharks' ? '[data-ocean]' : '[data-horizon]';
      let canvas = this.element.querySelector(selector);
      if (this.engine) {
        if (this.name === 'horizon') canvas.getContext('webgl2')?.getExtension('WEBGL_lose_context')?.loseContext();
        const fresh = canvas.cloneNode(); canvas.replaceWith(fresh); canvas = fresh;
      }
      this.engine = this.name === 'sharks' ? createCapriOcean(canvas) : createCapriHorizon(canvas, () => !this.running);
      this.nativeTime = 0;
      if (!this.engine) {
        this.status.textContent = 'WebGL 2 unavailable: source still fallback shown; native execution unverified.'; this.controls.querySelector('button:last-child').disabled=true;
        const fallback = this.element.querySelector('[data-horizon-fallback]'); if (fallback) { fallback.src = data.horizonPoster; fallback.hidden = false; }
      }
    }
    wireNativeInteraction() {
      const button = document.createElement('button'); button.type = 'button'; button.textContent = this.name === 'sharks' ? 'Send a ripple' : 'Tilt the disk';
      button.onclick = async () => { await this.initialize(); if (this.name === 'sharks') this.engine?.splash(.5, .5); else this.engine?.tilt(12); this.paint(); };
      this.controls.appendChild(button);
      let previousY = null;
      this.element.addEventListener('pointermove', event => {
        if (!event.target.matches('[data-ocean],[data-horizon]') || !this.engine) return;
        const b = event.target.getBoundingClientRect();
        if (this.name === 'sharks') this.engine.pointer((event.clientX - b.left) / b.width, (event.clientY - b.top) / b.height, true);
        else if (previousY !== null) { this.engine.tilt((event.clientY - previousY) * .3); previousY = event.clientY; }
      });
      this.element.addEventListener('pointerdown', event => { if (!this.engine || !event.target.matches('[data-ocean],[data-horizon]')) return; const b = event.target.getBoundingClientRect(); if (this.name === 'sharks') this.engine.splash((event.clientX - b.left) / b.width, (event.clientY - b.top) / b.height); else { previousY = event.clientY; this.engine.feed(); event.target.setPointerCapture(event.pointerId); } });
      for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) this.element.addEventListener(type, () => { previousY = null; });
      this.element.addEventListener('pointerleave', () => { if (this.name === 'sharks') this.engine?.pointer(0, 0, false); });
    }
    async renderAt(time) {
      this.hasStill = true; // An explicit seek owns the scene; visibility must not reset it.
      const version = this.seekVersion = (this.seekVersion || 0) + 1;
      this.pause(); await this.initialize(); if (version !== this.seekVersion) return this.state(); this.time = Math.max(0, time); const local = this.time % this.duration;
      if (this.video) {
        const target = (local / 1000) % this.video.duration;
        if (this.video.seeking || Math.abs(this.video.currentTime - target) > .0005) await new Promise((resolve, reject) => {
          this.video.addEventListener('seeked', resolve, {once: true}); this.video.addEventListener('error', () => reject(new Error('Plate seek failed')), {once: true}); this.video.currentTime = target;
        });
        if (version !== this.seekVersion) return this.state();
        if (Math.abs(this.video.currentTime - target) > .02) throw new Error('Reference seek did not reach requested source time: ' + this.name);
        this.cache.frame = -1; this.videoOffset = this.time - target * 1000; this.lastVideo = target;
      } else if (this.native && this.engine) {
        if (time < this.nativeTime) this.resetNative();
        while (this.nativeTime + 1000 / 60 < time - .001) { this.engine.step(1 / 60); this.nativeTime += 1000 / 60; }
        const remaining = (time - this.nativeTime) / 1000; if (remaining > 0) this.engine.step(remaining); this.nativeTime = time;
      }
      this.paint(); return this.state();
    }
    state() { return {time: this.time, running: this.running, visible: this.visible, frames: this.frames, native: this.native ? !!this.engine : null, sourceTime: this.video?.currentTime ?? null, sourceDuration: this.video?.duration ?? null, sceneDuration: this.duration, seekVersion: this.seekVersion || 0}; }
    pause() { this.running = false; this.video?.pause(); this.controls.querySelector('[data-play]').textContent = 'Play'; }
    async play() {
      this.hasStill = true;
      await this.initialize(); this.running = true; this.last = performance.now(); this.controls.querySelector('[data-play]').textContent = 'Pause';
      if (this.video && this.visible && !document.hidden) { this.lastVideo = this.video.currentTime; this.videoOffset = this.time - this.lastVideo * 1000; try { await this.video.play(); } catch (error) { this.pause(); this.status.replaceChildren(document.createTextNode(this.video?.error ? 'Reference media unavailable. ' : 'Playback needs a user Play action. ')); const link=document.createElement('a'); link.href='../../../../docs/README_STATIC.md'; link.textContent='Open complete static edition'; this.status.append(link); } }
    }
    paint() {
      const t = ((this.time % this.duration) + this.duration) % this.duration;
      if (this.name === 'comic') this.paintComic(t);
      else if (this.native) this.paintNative(t);
      else this.paintPlate(t);
      window.capriStory?.paint(this, t);
      this.controls.querySelector('input').value = Math.floor(t); this.controls.querySelector('output').textContent = (t / 1000).toFixed(1) + ' / ' + (this.duration / 1000).toFixed(1) + ' s'; this.frames++;
    }
    paintComic(time) {
      const phase = Math.min(2, Math.floor(time / 3200)), local = time % 3200, anchors = [], rootBox = this.element.querySelector('.hcf-comic').getBoundingClientRect();
      this.cards.forEach((card, i) => {
        const canvas = card.querySelector('canvas'), ctx = surface(canvas, 240, 220); if (!ctx) return;
        card.dataset.selected = String(i === phase); const pose = card.dataset.card;
        const sample = i === phase ? local : 0;
        const css = canvas.getBoundingClientRect(), fit = Math.min(css.width / 240, css.height / 220), dpr = exportName ? 1 : Math.min(2, devicePixelRatio || 1);
        ctx.setTransform(dpr * fit, 0, 0, dpr * fit, dpr * (css.width - 240 * fit) / 2, dpr * (css.height - 220 * fit) / 2);
        const a = actor.draw(ctx, pose, sample, data.storyFormats.actor_placement.workflow.x, data.storyFormats.actor_placement.workflow.y, data.storyFormats.actor_placement.workflow.scale);
        const box = canvas.getBoundingClientRect(); const world = p => [box.left - rootBox.left + (box.width - 240 * fit) / 2 + p[0] * fit, box.top - rootBox.top + (box.height - 220 * fit) / 2 + p[1] * fit];
        anchors.push({hand: world(a.hand), receive: world(a.receive)});
      });
      const packet = this.element.querySelector('.hcf-packet'); packet.style.visibility = 'hidden';
      if (phase < 2 && local >= 2400 && anchors.length === 3) {
        const u = clamp((local - 2400) / 800), q = smooth(u), a = anchors[phase].hand, b = anchors[phase + 1].receive;
        const portrait = this.cards[1].getBoundingClientRect().top - this.cards[0].getBoundingClientRect().top > 150;
        const x = portrait ? a[0] + 20 * q : a[0] * (1 - q) + b[0] * q;
        const y = portrait ? a[1] - 12 * q : a[1] * (1 - q) + b[1] * q - 12 * Math.sin(Math.PI * q);
        packet.style.visibility = 'visible'; packet.style.opacity = String(smooth(u * 8) * (1 - smooth((u - .85) / .15)));
        packet.style.transform = `translate(${x / (this.element.querySelector('.story-artboard').getBoundingClientRect().width / this.element.querySelector('.story-artboard').offsetWidth) - packet.offsetWidth / 2}px,${y / (this.element.querySelector('.story-artboard').getBoundingClientRect().height / this.element.querySelector('.story-artboard').offsetHeight) - packet.offsetHeight / 2}px)`;
      }
    }
    paintNative(time) {
      const canvas = this.element.querySelector('[data-actor]'), horizon = this.name === 'horizon', w = horizon ? data.storyFormats.native_world.horizon[0] : data.storyFormats.native_world.sharks[0], h = horizon ? data.storyFormats.native_world.horizon[1] : data.storyFormats.native_world.sharks[1], ctx = surface(canvas, w, h);
      if (!ctx) return;
      const phase = time / this.duration;
      ctx.save(); ctx.globalAlpha = 1;
      if (horizon) {
        const p = data.storyFormats.actor_placement.horizon, q = smooth(phase < .5 ? phase * 2 : (1 - phase) * 2), x = p.x - p.x_travel * q, y = p.y + p.y_travel * Math.sin(Math.PI * q);
        actor.draw(ctx, 'plan', time, x, y, data.storyFormats.actor_placement.horizon.scale, -.15 + .27 * q);
      } else actor.draw(ctx, 'plan', time * 6400 / this.duration, data.storyFormats.actor_placement.sharks.x, data.storyFormats.actor_placement.sharks.y, data.storyFormats.actor_placement.sharks.scale);
      ctx.restore();
      // Native simulations remain unbounded live. Only exported excerpts have a
      // short explicit dark bridge, covering an otherwise nonperiodic world seam.
      let bridge = this.element.querySelector('.export-bridge');
      if (exportName && !bridge) { bridge = document.createElement('div'); bridge.className = 'export-bridge'; bridge.style.cssText = 'position:absolute;inset:0;background:#100a19;pointer-events:none;z-index:1'; this.element.querySelector('.cs-stage').appendChild(bridge); }
      if (bridge) bridge.style.opacity = String(1 - smooth(Math.min(time, this.duration - 40 - time) / 240));
    }
    paintPlate(time) {
      if (!this.video || this.video.readyState < 2) return;
      const canvas = this.element.querySelector('[data-scene]'), name = this.name, w = name === 'stack' ? 640 : 320, h = name === 'cat' ? 316 : name === 'dots' ? 294 : name === 'stack' ? 360 : 320;
      const ctx = surface(canvas, w, h); if (!ctx) return;
      const seconds = this.video.currentTime, plate = recolour(name, this.video, this.cache, seconds); ctx.drawImage(plate, 0, 0, w, h);
      if (name === 'hands') {
        actor.draw(ctx, 'build', time * 6400 / this.duration, data.storyFormats.actor_placement.hands.x, data.storyFormats.actor_placement.hands.y, data.storyFormats.actor_placement.hands.scale);
        // Measured source contact sits near (0.52, 0.48); preserve the hands,
        // not an invented arrow. The packet appears only through the contact.
        const packet = this.element.querySelector('.cp-packet'), q = smooth((seconds - 1.6) / .5), x = .46 + .10 * q, y = .48;
        packet.style.left = (x * 100) + '%'; packet.style.top = (y * 100) + '%'; packet.style.opacity = String(smooth((seconds - 1.65) / .25) * (1 - smooth((seconds - 4.65) / .25)));
      } else if (name === 'cat') {
        const arrival = smooth((seconds - .9) / .5) * (1 - smooth((seconds - 7.4) / .7));
        ctx.save(); ctx.globalAlpha = arrival; actor.draw(ctx, 'review', time, data.storyFormats.actor_placement.cat.x - 25 * (1 - arrival), data.storyFormats.actor_placement.cat.y, data.storyFormats.actor_placement.cat.scale, -.06); ctx.restore(); showBeams(ctx, seconds, w, h, this.cache.eyes);
      } else if (name === 'rain') actor.draw(ctx, 'review', 900, 251, 91, .088, -.04);
      else if (name === 'stack') actor.draw(ctx, 'plan', time, 535, 205, .10);
    }
    tick(now) {
      if (!this.running || !this.visible || document.hidden) { this.last = now; return; }
      const dt = Math.min(.05, Math.max(0, (now - this.last) / 1000)); this.last = now;
      if (this.video) {
        const current = this.video.currentTime;
        if (current + .1 < this.lastVideo) this.videoOffset += this.video.duration * 1000;
        this.lastVideo = current; this.time = this.videoOffset + current * 1000;
      } else { this.time += dt * 1000; if (this.native && this.engine) { this.engine.step(dt); this.nativeTime += dt * 1000; } }
      this.paint();
    }
  }
  function reportError(error) { document.body.dataset.failed = error.message; console.error(error); }
  const scenes = Object.fromEntries(Object.entries(definitions).map(([name, def]) => [name, new Scene(name, def)]));
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      const scene = scenes[entry.target.dataset.panel]; scene.visible = entry.isIntersecting; scene.last = performance.now();
      if (scene.visible && !exportName) scene.initialize().then(async () => {
        if (!scene.hasStill) { await scene.renderAt(scene.still); scene.hasStill = true; if (!reduce.matches) scene.play(); }
        else if (scene.running) scene.play();
      }).catch(reportError);
      else scene.video?.pause();
    }
  }, {rootMargin: '0px'});
  for (const scene of Object.values(scenes)) observer.observe(scene.element);
  document.addEventListener('visibilitychange', () => { for (const scene of Object.values(scenes)) { scene.last = performance.now(); if (document.hidden) scene.video?.pause(); else if (scene.running && scene.visible) scene.play(); } });
  reduce.addEventListener('change', () => { if (reduce.matches) for (const scene of Object.values(scenes)) scene.renderAt(scene.still).catch(reportError); });
  new ResizeObserver(() => { for (const scene of Object.values(scenes)) if (scene.visible && scene.initializing) scene.paint(); }).observe(document.querySelector('main'));
  window.sceneApp = {ready: true, scenes, actor, eyeAt, renderAt: (name, time) => scenes[name].renderAt(time), pauseAll: () => Object.values(scenes).forEach(scene => scene.pause()), states: () => Object.fromEntries(Object.entries(scenes).map(([name, scene]) => [name, scene.state()]))};
  if (exportName) { await scenes[exportName].renderAt(definitions[exportName].still); document.body.dataset.ready = 'true'; }
  window.dispatchEvent(new Event('capri:ready'));
  function tick(now) { for (const scene of Object.values(scenes)) scene.tick(now); requestAnimationFrame(tick); } requestAnimationFrame(tick);
})().catch(error => { document.body.dataset.failed = error.message; console.error(error); });
