/* Native scene clocks own art. Request inspection owns only mathematical state.
 * Graph exports stay still; mathematical rows never depend on art time. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('story-data').textContent);
  const query = new URLSearchParams(location.search), exporting = query.has('export');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');

  const requestInput = document.getElementById('story-request');
  const requestOutput = document.getElementById('story-values');
  const overheadInput = document.getElementById('story-overhead');
  const budgetOutput = document.getElementById('story-budget');
  const charts = [...document.querySelectorAll('.story-chart')].map(svg => ({
    svg, layout: svg.dataset.layout,
    rule: svg.querySelector('[data-current-rule]'),
    dots: [...svg.querySelectorAll('[data-current-dot]')],
    request: null, progress: null
  }));
  let request = 1, extra = data.config.overhead.initial, lastBudget = null;
  const k = value => (value / 1000).toLocaleString('en-US', {maximumFractionDigits: 1}) + 'k';
  const smooth = value => { const u = Math.max(0, Math.min(1, value)); return u * u * (3 - 2 * u); };
  function drawGuide(chart, progress, animate) {
    if (chart.progress === progress) return;
    const geometry = data.graphs[chart.layout], left = Math.floor(progress), right = Math.min(data.model.calls - 1, left + 1), u = progress - left;
    const mix = points => points[left] * (1 - u) + points[right] * u;
    const x = mix(geometry.x);
    chart.rule.style.transition = animate ? 'transform 160ms ease' : 'none';
    chart.rule.setAttribute('d', `M${geometry.x[0]},${geometry.top}V${geometry.bottom}`);
    chart.rule.style.transform = `translateX(${x - geometry.x[0]}px)`;
    for (const dot of chart.dots) {
      const points = geometry.points[dot.dataset.currentDot];
      dot.style.transition = animate ? 'cx 160ms ease, cy 160ms ease' : 'none';
      dot.style.cx = (points[left][0] * (1 - u) + points[right][0] * u) + 'px';
      dot.style.cy = (points[left][1] * (1 - u) + points[right][1] * u) + 'px';
    }
    chart.progress = progress;
  }
  function selectRequest(value, {progress = value - 1, animate = !reduce.matches && !exporting} = {}) {
    if (!Number.isInteger(value) || value < 1 || value > data.model.calls) return;
    if (request !== value || !requestOutput.textContent) {
      const row = data.model.requests[value - 1];
      requestInput.value = value;
      requestOutput.textContent = `Request ${value}: growing ${k(row.values.growing)}, curated ${k(row.values.curated)}, scoped ${k(row.values.scoped)} input.`;
    }
    request = value;
    if (window.sceneApp) sceneApp.scenes.horizon.storyRequest = value;
    const layout = requestInput.closest('[data-lesson]').querySelector('.story-frame').dataset.layout;
    for (const chart of charts) if (chart.layout === (layout === 'landscape' ? 'wide' : 'portrait')) drawGuide(chart, progress, animate);
  }
  function selectBudget(value) {
    const row = data.model.sensitivity.find(item => item.additional_input === value);
    if (!row || lastBudget === value) return;
    const element = overheadInput.closest('[data-lesson]');
    element.querySelector('[data-budget-total]').textContent = k(row.scoped_total) + ' input';
    element.querySelector('[data-budget-relation]').textContent = 'H = ' + k(value);
    const relation = row.relation === 'equal' ? 'equal to curated' : `${row.percent}% ${row.relation} than curated`;
    budgetOutput.textContent = `H ${k(value)} → scoped ${k(row.scoped_total)}, ${relation}. Already-budgeted handoffs are not counted twice.`;
    overheadInput.value = value; extra = value; lastBudget = value;
    if (window.sceneApp) { sceneApp.scenes.dots.storyBudget = row; sceneApp.scenes.dots.storyOverhead = value; }
  }
  function sizeFrame(frame) {
    const name = frame.closest('[data-lesson]').dataset.lesson;
    const lesson = data.config.lessons[name];
    const layout = exporting ? query.get('layout') : (lesson.family === 'graph' ? 'graph' : lesson.family === 'support' ? 'support' : 'portrait');
    frame.dataset.layout = layout;
    const size = data.formats.families[data.formats.layouts[layout]];
    frame.parentElement.style.width = size.width + 'px';
    frame.firstElementChild.style.transform = `scale(${frame.clientWidth / size.width})`;
  }
  const frames = [...document.querySelectorAll('.story-frame')];
  frames.forEach(sizeFrame);
  const resize = new ResizeObserver(entries => {
    for (const entry of entries) sizeFrame(entry.target);
    selectRequest(request, {animate: false});
  });
  frames.forEach(frame => resize.observe(frame));
  window.capriStory = {
    get request() { return request; }, selectRequest,
    paint() { /* Mathematical inspection has no dependency on art time. */ }
  };
  async function boot() {
    try {
      const app = window.sceneApp;
      const groups = Object.fromEntries(Object.entries(data.config.lessons).map(([name, lesson]) => [name, lesson.members]));
      const durations = Object.fromEntries(Object.entries(data.config.lessons).map(([name, lesson]) => [name, lesson.duration_ms]));
      app.scenes.horizon.duration = durations.horizon;
      requestInput.addEventListener('change', event => selectRequest(Number(event.target.value)));
      overheadInput.addEventListener('input', event => selectBudget(Number(event.target.value)));
      selectRequest(request, {animate: false}); selectBudget(extra);
      window.storyApp = {
        ready: true, data, groups, durations,
        get request() { return request; },
        async renderLesson(name, time) {
          if (!groups[name]) throw new Error('Unknown lesson: ' + name);
          app.pauseAll();
          const local = ((time % durations[name]) + durations[name]) % durations[name];
          await Promise.all(groups[name].map(scene => app.renderAt(scene, scene === 'rain' ? local % 500 : local)));
          if (name === 'coordination') {
            // A short export excerpt uses an explicit bridge; live source cadence is intact.
            app.scenes.dots.element.querySelector('[data-scene]').style.opacity = smooth(Math.min(local, durations.coordination - 40 - local) / 120);
          }
          return {lesson: name, time: local, request, budget: app.scenes.dots.storyBudget ?? null,
            guide_progress: charts.find(chart => chart.progress !== null)?.progress ?? null,
            scenes: Object.fromEntries(groups[name].map(scene => [scene, app.scenes[scene].state()]))};
        }
      };
      const lesson = query.get('lesson');
      if (lesson) {
        if (!groups[lesson]) throw new Error('Unknown export lesson');
        for (const element of document.querySelectorAll('[data-lesson]')) element.hidden = element.dataset.lesson !== lesson;
        document.getElementById('capri-source-scenes').hidden = false;
        document.getElementById('capri-reference-composites').hidden = false;
        for (const [name, scene] of Object.entries(app.scenes)) scene.element.hidden = !groups[lesson].includes(name);
        document.body.dataset.lesson = lesson;
        frames.forEach(sizeFrame);
        await storyApp.renderLesson(lesson, data.config.lessons[lesson].still_ms);
      }
      document.body.dataset.storyReady = 'true';
    } catch (error) { fail(error); }
  }
  function fail(error) { document.body.dataset.failed = error.message; console.error(error); }
  window.addEventListener('capri:ready', boot, {once: true});
  if (window.sceneApp?.ready) boot();
})();
