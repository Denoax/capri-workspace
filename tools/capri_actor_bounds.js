/* Export-only pixel evidence. Not loaded by the interactive presentation. */
(() => {
  const actor = sceneApp.actor, draw = actor.draw.bind(actor);
  const probe = document.createElement('canvas');
  window.capriActorBounds = [];
  actor.draw = (ctx, ...args) => {
    const pad = 128, width = ctx.canvas.width, height = ctx.canvas.height;
    probe.width = width + pad * 2; probe.height = height + pad * 2;
    const test = probe.getContext('2d'), matrix = ctx.getTransform();
    test.setTransform(matrix.a, matrix.b, matrix.c, matrix.d, matrix.e + pad, matrix.f + pad);
    test.globalAlpha = ctx.globalAlpha;
    draw(test, ...args);
    const pixels = test.getImageData(0, 0, probe.width, probe.height).data;
    let left = probe.width, top = probe.height, right = -1, bottom = -1;
    for (let y = 0; y < probe.height; y++) for (let x = 0; x < probe.width; x++) {
      if (pixels[4 * (y * probe.width + x) + 3] <= 3) continue;
      left = Math.min(left, x); top = Math.min(top, y);
      right = Math.max(right, x); bottom = Math.max(bottom, y);
    }
    if (right >= 0) capriActorBounds.push({pose: args[0],
      margins: [left - pad, top - pad, pad + width - 1 - right, pad + height - 1 - bottom],
      size: [right - left + 1, bottom - top + 1],
      uniform_surface: Math.abs(matrix.a / matrix.d - 1) < .01});
    return draw(ctx, ...args);
  };
})();
