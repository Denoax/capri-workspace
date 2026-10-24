/* Pose-specific rigid cutout animation. Source, masks and keys remain editable. */
class CapriActor {
  constructor(data) {
    this.data = data;
    this.images = new Map();
    this.ready = Promise.all(Object.entries(data.poses).flatMap(([name, pose]) =>
      pose.parts.map(part => new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = resolve;
        image.onerror = () => reject(new Error('Actor layer unavailable: ' + part.src));
        image.src = part.src;
        this.images.set(name + ':' + part.tag, image);
      }))));
  }
  static point(p, m) { return [m[0] * p[0] - m[1] * p[1] + m[2], m[1] * p[0] + m[0] * p[1] + m[3]]; }
  static around(origin, target, degrees) {
    const angle = degrees * Math.PI / 180, c = Math.cos(angle), s = Math.sin(angle);
    return [c, s, target[0] - c * origin[0] + s * origin[1], target[1] - s * origin[0] - c * origin[1]];
  }
  sample(name, time) {
    const p = this.data.poses[name], keys = p.keys;
    const t = ((time % p.duration_ms) + p.duration_ms) % p.duration_ms;
    let i = 0;
    while (i < keys.length - 2 && t > keys[i + 1][0]) i++;
    let u = Math.max(0, Math.min(1, (t - keys[i][0]) / (keys[i + 1][0] - keys[i][0])));
    u = u * u * (3 - 2 * u);
    const v = keys[i].map((a, j) => a * (1 - u) + keys[i + 1][j] * u);
    const body = v[1], torso = CapriActor.around(p.hip, [p.hip[0] + v[11], p.hip[1] + v[12]], body);
    const upper = (origin, a) => CapriActor.around(origin, CapriActor.point(origin, torso), body + a);
    const lower = (origin, joint, a, b) => CapriActor.around(joint, CapriActor.point(joint, upper(origin, a)), body + a + b);
    const parts = {
      1: CapriActor.around(p.neck, CapriActor.point(p.neck, torso), body + v[2]), 2: torso,
      3: upper(p.rs, v[3]), 4: lower(p.rs, p.re, v[3], v[4]),
      5: upper(p.ls, v[5]), 6: lower(p.ls, p.le, v[5], v[6]),
      7: upper(p.gh, v[7]), 8: lower(p.gh, p.gk, v[7], v[8]),
      9: upper(p.ph, v[9]), 10: lower(p.ph, p.pk, v[9], v[10])
    };
    return {time: t, parts, values: v, pose: name};
  }
  draw(ctx, name, time, eyeX, eyeY, scale, rotation = 0) {
    const p = this.data.poses[name], state = this.sample(name, time);
    // A common eye span calibrates the camera; source bounds never drive scale.
    const normalized = scale * this.data.poses.plan.eye_span / p.eye_span;
    ctx.save(); ctx.translate(eyeX, eyeY); ctx.rotate(rotation); ctx.scale(normalized, normalized); ctx.translate(-p.eye[0], -p.eye[1]);
    // Small angular closures use colors sampled at this master's joints.
    // They sit behind cutouts and repair exposed seams without a body warp.
    for (const [joint, tag] of [['neck', 1], ['rs', 3], ['re', 4], ['ls', 5], ['le', 6], ['gh', 7], ['gk', 8], ['ph', 9], ['pk', 10]]) {
      const [x, y] = CapriActor.point(p[joint], state.parts[tag]);
      ctx.fillStyle = p.joint_colors[joint]; ctx.beginPath(); ctx.moveTo(x - 11, y - 5); ctx.lineTo(x + 2, y - 12); ctx.lineTo(x + 12, y + 4); ctx.lineTo(x - 2, y + 12); ctx.closePath(); ctx.fill();
    }
    for (const tag of [1, 9, 10, 7, 8, 2, 5, 6, 3, 4]) {
      const meta = p.parts.find(part => part.tag === tag), m = state.parts[tag];
      ctx.save(); ctx.transform(m[0], m[1], -m[1], m[0], m[2], m[3]);
      ctx.drawImage(this.images.get(name + ':' + tag), ...meta.origin, ...meta.size);
      if (tag === 1 && ((state.time >= 1370 && state.time < 1450) || (name === 'review' && state.time >= 2490 && state.time < 2590))) {
        // Independent eyelids use this pose's eye centers, never Plan's coordinates.
        for (const eye of p.eyes) {
          ctx.fillStyle = '#20f78c'; ctx.beginPath(); ctx.ellipse(eye[0], eye[1], 17, 19, .25, 0, Math.PI * 2); ctx.fill();
          ctx.strokeStyle = '#100a19'; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(eye[0] - 15, eye[1]); ctx.lineTo(eye[0], eye[1] + 5); ctx.lineTo(eye[0] + 15, eye[1] - 1); ctx.stroke();
        }
      }
      ctx.restore();
    }
    ctx.restore();
    const world = (point, tag) => {
      const a = CapriActor.point(point, state.parts[tag]), dx = (a[0] - p.eye[0]) * normalized, dy = (a[1] - p.eye[1]) * normalized;
      return [eyeX + dx * Math.cos(rotation) - dy * Math.sin(rotation), eyeY + dx * Math.sin(rotation) + dy * Math.cos(rotation)];
    };
    return {eye: world(p.eye, 1), mouth: world(p.mouth, 1), hand: world(p.tip, name === 'review' ? 6 : 4), receive: world(p.lw, 6), chest: world(p.hip, 2)};
  }
}
