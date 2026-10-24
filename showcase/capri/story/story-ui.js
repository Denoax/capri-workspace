/* V3 presentation state: the existing scene clock owns request/actor/effect time.
 * Numbers come from Python's canonical calculation; controls select its rows.
 */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('story-data').textContent);
  const k = value => (value / 1000).toLocaleString('en-US', {maximumFractionDigits: 1}) + 'k';
  const smooth = x => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };
  window.capriStory = {
    paint(scene, time) {
      if (scene.name === 'horizon') {
        const index = Math.min(data.model.calls - 1, Math.floor(time / scene.duration * data.model.calls));
        for (const svg of scene.element.querySelectorAll('.story-chart')) {
          const geometry = data.graphs[svg.dataset.layout];
          svg.querySelector('[data-current-rule]').setAttribute('d', `M${geometry.x[index]},${geometry.top}V${geometry.bottom}`);
          for (const dot of svg.querySelectorAll('[data-current-dot]')) {
            const point = geometry.points[dot.dataset.currentDot][index]; dot.setAttribute('cx', point[0]); dot.setAttribute('cy', point[1]);
          }
        }
        const row = data.model.requests[index];
        document.getElementById('story-request').value = row.request;
        document.getElementById('story-values').textContent = `Request ${row.request}: growing ${k(row.values.growing)}, curated ${k(row.values.curated)}, scoped ${k(row.values.scoped)} input.`;
        scene.storyRequest = row.request;
      }
      if (scene.name === 'dots') {
        const extra = scene.storyOverhead ?? data.config.overhead.initial;
        const row = data.model.sensitivity.find(item => item.additional_input === extra);
        if (!row) throw new Error('Additional input is outside the authored range');
        scene.element.querySelector('[data-budget-total]').textContent = k(row.scoped_total) + ' input';
        scene.element.querySelector('[data-budget-relation]').textContent = 'H = ' + k(extra);
        const relation = row.relation === 'equal' ? 'equal to curated' : `${row.percent}% ${row.relation} than curated`;
        document.getElementById('story-budget').textContent = `H ${k(extra)} → scoped ${k(row.scoped_total)}, ${relation}. Already-budgeted handoffs are not counted twice.`;
        document.getElementById('story-overhead').value = extra;
        scene.storyBudget = row;
      }
    }
  };
  async function boot() {
    try {
      const app = window.sceneApp, query = new URLSearchParams(location.search);
      const groups = Object.fromEntries(Object.entries(data.config.lessons).map(([name, lesson]) => [name, lesson.members]));
      const durations = Object.fromEntries(Object.entries(data.config.lessons).map(([name, lesson]) => [name, lesson.duration_ms]));
      const stills = Object.fromEntries(Object.entries(data.config.lessons).map(([name, lesson]) => [name, lesson.still_ms]));
      app.scenes.horizon.duration = durations.contexts;
      document.getElementById('story-request').addEventListener('change', event => {
        const request = Number(event.target.value);
        if (!Number.isInteger(request) || request < 1 || request > data.model.calls) return;
        app.renderAt('horizon', (request - .5) * app.scenes.horizon.duration / data.model.calls).catch(fail);
      });
      document.getElementById('story-overhead').addEventListener('input', event => {
        const extra = Number(event.target.value);
        if (!data.model.sensitivity.some(row => row.additional_input === extra)) return;
        const scene = app.scenes.dots; scene.storyOverhead = extra;
        scene.initialize().then(() => scene.paint()).catch(fail);
      });
      window.storyApp = {
        ready: true, data, groups, durations,
        async renderLesson(name, time) {
          if (!groups[name]) throw new Error('Unknown lesson: ' + name);
          app.pauseAll();
          const local = ((time % durations[name]) + durations[name]) % durations[name];
          if (name === 'contexts') app.scenes.sharks.duration = durations.contexts;
          await Promise.all(groups[name].map(scene => app.renderAt(scene, scene === 'rain' ? local % 500 : local)));
          if (name === 'retained') {
            // Keep the rain pace and reading labels stable; bridge the shorter dotted excerpt.
            app.scenes.dots.element.querySelector('[data-scene]').style.opacity = smooth(Math.min(local, durations.retained - 40 - local) / 120);
          }
          return {lesson: name, time: local, request: app.scenes.horizon.storyRequest ?? null,
            budget: app.scenes.dots.storyBudget ?? null,
            scenes: Object.fromEntries(groups[name].map(scene => [scene, app.scenes[scene].state()]))};
        }
      };
      const lesson = query.get('lesson');
      if (lesson) {
        if (!groups[lesson]) throw new Error('Unknown export lesson');
        for (const element of document.querySelectorAll('[data-lesson]')) element.hidden = element.dataset.lesson !== lesson;
        document.getElementById('capri-source-scenes').hidden = lesson !== 'contexts';
        document.getElementById('capri-reference-composites').hidden = ['workflow', 'contexts'].includes(lesson);
        for (const [name, scene] of Object.entries(app.scenes)) scene.element.hidden = !groups[lesson].includes(name);
        document.body.dataset.lesson = lesson;
        await storyApp.renderLesson(lesson, stills[lesson]);
      }
      document.body.dataset.storyReady = 'true';
    } catch (error) { fail(error); }
  }
  function fail(error) { document.body.dataset.failed = error.message; console.error(error); }
  window.addEventListener('capri:ready', boot, {once: true});
  if (window.sceneApp?.ready) boot();
})();
