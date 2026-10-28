# OmicHub 首页 Hero 动态背景动画方案 v3（扩展抽象动画库）

> 生成日期：2026-07-05
> 目标：扩展抽象动画库，提供 6 种去风格化、现代感的 Hero 背景动画

---

## 一、动画库总览

| 编号 | 名称 | 视觉特征 | 抽象隐喻 |
|------|------|----------|----------|
| A | 粒子网络 | 白点漂移 + 近距连线 | 神经网络、数据云 |
| B | 星空粒子 | 星点向上飘 + 十字光芒 | 星尘、银河 |
| C | 光晕脉冲 | 同心圆环从中心扩散 | 声波、心跳、能量场 |
| D | 噪点流场 | 流动线条如流体/烟雾 | 气流、磁场、数据流 |
| E | 轨道环 | 细圆环缓慢旋转 | 行星轨道、原子结构 |
| F | 渐变流光 | 色块缓慢流动变形 | 极光、液态金属、星云 |

每次加载随机从 6 种中选取一种。

---

## 二、原有动画（A + B）

见 `omicHub_hero_animation_v2.md`，此处不再重复。

---

## 三、新增动画

### 3.1 光晕脉冲（Aura Pulse）

**视觉描述**：
- 3-5 个同心圆环从画布中心（偏右）缓慢向外扩散
- 圆环到达边缘后消失，新的圆环从中心再生
- 圆环透明度从中心高到边缘低，边缘羽化
- 圆环之间速度略有差异，形成错位美感
- 偶尔有细光线从中心向边缘放射

**抽象感**：像声波扩散、心跳律动、能量释放——极简而有力。

```javascript
function initAura() {
  const rings = [];
  const maxRings = 5;

  for (let i = 0; i < maxRings; i++) {
    rings.push({
      radius: 0,
      maxRadius: Math.max(w, h) * 0.8,
      speed: 0.4 + Math.random() * 0.3,
      delay: i * 60,           // 错峰启动
      age: -i * 60,            // 负值表示等待中
      opacity: 0.3 + Math.random() * 0.2
    });
  }

  const rays = [];
  for (let i = 0; i < 12; i++) {
    rays.push({
      angle: (i / 12) * Math.PI * 2 + Math.random() * 0.3,
      length: 0,
      maxLength: Math.max(w, h) * 0.5,
      speed: 0.6 + Math.random() * 0.4,
      width: 0.5 + Math.random() * 1,
      delay: Math.random() * 200
    });
  }

  return { rings, rays, cx: w * 0.7, cy: h * 0.5 };
}

function drawAura(state) {
  ctx.clearRect(0, 0, w, h);

  // 绘制圆环
  state.rings.forEach(r => {
    r.age++;
    if (r.age < 0) return; // 还在等待

    r.radius += r.speed;
    if (r.radius > r.maxRadius) {
      r.radius = 0;
      r.age = -r.delay;
    }

    const progress = r.radius / r.maxRadius;
    const alpha = r.opacity * (1 - progress) * (1 - progress); // 边缘羽化

    ctx.beginPath();
    ctx.arc(state.cx, state.cy, r.radius, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
    ctx.lineWidth = 1.5 * (1 - progress * 0.5);
    ctx.stroke();
  });

  // 绘制放射线
  state.rays.forEach(ray => {
    ray.delay--;
    if (ray.delay > 0) return;

    ray.length += ray.speed;
    if (ray.length > ray.maxLength) {
      ray.length = 0;
      ray.delay = 100 + Math.random() * 150;
      ray.angle += (Math.random() - 0.5) * 0.5;
    }

    const progress = ray.length / ray.maxLength;
    const alpha = 0.15 * (1 - progress);
    const x2 = state.cx + Math.cos(ray.angle) * ray.length;
    const y2 = state.cy + Math.sin(ray.angle) * ray.length;

    ctx.beginPath();
    ctx.moveTo(state.cx, state.cy);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
    ctx.lineWidth = ray.width;
    ctx.stroke();
  });
}
```

---

### 3.2 噪点流场（Noise Field）

**视觉描述**：
- 细线条（0.5-1px）在画布上流动，方向受 Perlin noise 控制
- 线条颜色从白到淡紫渐变，与背景融合
- 线条长度 20-60px，透明度 0.1-0.3
- 整体如流体、烟雾、磁场线——有机而抽象

**抽象感**：像看不见的气流、磁场线、数据流——没有具体形状，但有流动感。

```javascript
// 简化版 Perlin noise（无需外部库）
const PERLIN = {
  p: new Uint8Array(512),
  init() {
    for (let i = 0; i < 256; i++) this.p[i] = this.p[i + 256] = Math.floor(Math.random() * 256);
  },
  fade(t) { return t * t * t * (t * (t * 6 - 15) + 10); },
  lerp(t, a, b) { return a + t * (b - a); },
  grad(hash, x, y) {
    const h = hash & 15;
    const u = h < 8 ? x : y;
    const v = h < 4 ? y : h === 12 || h === 14 ? x : 0;
    return ((h & 1) === 0 ? u : -u) + ((h & 2) === 0 ? v : -v);
  },
  noise(x, y) {
    const X = Math.floor(x) & 255;
    const Y = Math.floor(y) & 255;
    x -= Math.floor(x);
    y -= Math.floor(y);
    const u = this.fade(x);
    const v = this.fade(y);
    const A = this.p[X] + Y, B = this.p[X + 1] + Y;
    return this.lerp(v, this.lerp(u, this.grad(this.p[A], x, y), this.grad(this.p[B], x - 1, y)),
                          this.lerp(u, this.grad(this.p[A + 1], x, y - 1), this.grad(this.p[B + 1], x - 1, y - 1)));
  }
};
PERLIN.init();

function initNoiseField() {
  const lines = [];
  const count = Math.floor((w * h) / 6000);

  for (let i = 0; i < count; i++) {
    lines.push({
      x: Math.random() * w,
      y: Math.random() * h,
      length: 20 + Math.random() * 40,
      speed: 0.2 + Math.random() * 0.3,
      opacity: 0.08 + Math.random() * 0.15,
      width: 0.5 + Math.random() * 0.8,
      noiseScale: 0.003 + Math.random() * 0.002,
      time: Math.random() * 100
    });
  }
  return { lines, time: 0 };
}

function drawNoiseField(state) {
  ctx.clearRect(0, 0, w, h);
  state.time += 0.008;

  state.lines.forEach(line => {
    line.time += line.speed * 0.01;

    // 用 Perlin noise 计算方向
    const angle = PERLIN.noise(line.x * line.noiseScale, line.y * line.noiseScale + state.time) * Math.PI * 2;
    const x2 = line.x + Math.cos(angle) * line.length;
    const y2 = line.y + Math.sin(angle) * line.length;

    // 颜色：纯白到淡紫
    const purpleTint = Math.abs(PERLIN.noise(line.x * 0.005, line.y * 0.005)) * 0.3;

    ctx.beginPath();
    ctx.moveTo(line.x, line.y);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = `rgba(${255}, ${255 - purpleTint * 100}, ${255}, ${line.opacity})`;
    ctx.lineWidth = line.width;
    ctx.lineCap = 'round';
    ctx.stroke();

    // 缓慢移动
    line.x += Math.cos(angle) * 0.3;
    line.y += Math.sin(angle) * 0.3;

    // 边界循环
    if (line.x < -50) line.x = w + 50;
    if (line.x > w + 50) line.x = -50;
    if (line.y < -50) line.y = h + 50;
    if (line.y > h + 50) line.y = -50;
  });
}
```

---

### 3.3 轨道环（Orbital Rings）

**视觉描述**：
- 3-4 个细圆环（1px 线宽）在画布右侧缓慢旋转
- 圆环不同心，有轻微倾斜和错位
- 圆环上各有一个小白点沿轨道运行
- 偶尔有细线从环心向外放射，如原子结构

**抽象感**：像行星轨道、原子模型、几何美学——极简几何。

```javascript
function initOrbitals() {
  const rings = [];
  const count = 3 + Math.floor(Math.random() * 2);

  for (let i = 0; i < count; i++) {
    rings.push({
      cx: w * 0.7 + (Math.random() - 0.5) * 40,
      cy: h * 0.5 + (Math.random() - 0.5) * 30,
      radius: 40 + i * 35 + Math.random() * 20,
      tilt: (Math.random() - 0.5) * 0.4, // 倾斜角度
      rotation: Math.random() * Math.PI * 2,
      rotSpeed: (Math.random() - 0.5) * 0.003,
      opacity: 0.15 + Math.random() * 0.1,
      dotAngle: Math.random() * Math.PI * 2,
      dotSpeed: 0.005 + Math.random() * 0.005
    });
  }

  return { rings };
}

function drawOrbitals(state) {
  ctx.clearRect(0, 0, w, h);

  state.rings.forEach(r => {
    r.rotation += r.rotSpeed;
    r.dotAngle += r.dotSpeed;

    ctx.save();
    ctx.translate(r.cx, r.cy);
    ctx.rotate(r.rotation);
    ctx.scale(1, Math.cos(r.tilt)); // 倾斜效果

    // 绘制圆环
    ctx.beginPath();
    ctx.arc(0, 0, r.radius, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(255, 255, 255, ${r.opacity})`;
    ctx.lineWidth = 1;
    ctx.stroke();

    // 绘制轨道上的点
    const dotX = Math.cos(r.dotAngle) * r.radius;
    const dotY = Math.sin(r.dotAngle) * r.radius;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
    ctx.beginPath();
    ctx.arc(dotX, dotY, 2.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  });

  // 中心发光点
  ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
  ctx.beginPath();
  ctx.arc(w * 0.7, h * 0.5, 3, 0, Math.PI * 2);
  ctx.fill();
}
```

---

### 3.4 渐变流光（Gradient Flow）

**视觉描述**：
- 2-3 个大型半透明色块（径向渐变）在画布上缓慢漂移
- 色块颜色从蓝到紫到粉，与背景渐变呼应
- 色块边缘羽化，相互叠加时产生新的颜色
- 整体如极光、液态金属、星云——流动而梦幻

**抽象感**：没有具体形状，只有颜色在流动，像宇宙背景辐射。

```javascript
function initGradientFlow() {
  const blobs = [];
  const colors = [
    ['rgba(100, 150, 255, 0.15)', 'rgba(100, 150, 255, 0)'],
    ['rgba(180, 100, 255, 0.12)', 'rgba(180, 100, 255, 0)'],
    ['rgba(255, 120, 200, 0.1)', 'rgba(255, 120, 200, 0)']
  ];

  for (let i = 0; i < 3; i++) {
    blobs.push({
      x: w * (0.3 + Math.random() * 0.5),
      y: h * (0.2 + Math.random() * 0.6),
      radius: 100 + Math.random() * 150,
      vx: (Math.random() - 0.5) * 0.15,
      vy: (Math.random() - 0.5) * 0.15,
      colorStart: colors[i][0],
      colorEnd: colors[i][1],
      pulse: Math.random() * Math.PI * 2,
      pulseSpeed: 0.005 + Math.random() * 0.005
    });
  }

  return { blobs };
}

function drawGradientFlow(state) {
  ctx.clearRect(0, 0, w, h);

  state.blobs.forEach(b => {
    b.x += b.vx;
    b.y += b.vy;
    b.pulse += b.pulseSpeed;

    // 软边界回弹
    if (b.x < -b.radius) b.vx = Math.abs(b.vx);
    if (b.x > w + b.radius) b.vx = -Math.abs(b.vx);
    if (b.y < -b.radius) b.vy = Math.abs(b.vy);
    if (b.y > h + b.radius) b.vy = -Math.abs(b.vy);

    const radius = b.radius * (0.9 + 0.1 * Math.sin(b.pulse));

    const gradient = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, radius);
    gradient.addColorStop(0, b.colorStart);
    gradient.addColorStop(1, b.colorEnd);

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, w, h);
  });
}
```

---

## 四、完整调度器（6 种模式）

```javascript
const MODES = ['particles', 'stars', 'aura', 'noise', 'orbitals', 'gradient'];
const currentMode = MODES[Math.floor(Math.random() * MODES.length)];

let state = null;

function animate() {
  switch (currentMode) {
    case 'particles':
      if (!state) state = initParticles();
      drawParticles(state);
      break;
    case 'stars':
      if (!state) state = initStars();
      drawStars(state);
      break;
    case 'aura':
      if (!state) state = initAura();
      drawAura(state);
      break;
    case 'noise':
      if (!state) state = initNoiseField();
      drawNoiseField(state);
      break;
    case 'orbitals':
      if (!state) state = initOrbitals();
      drawOrbitals(state);
      break;
    case 'gradient':
      if (!state) state = initGradientFlow();
      drawGradientFlow(state);
      break;
  }
  animationId = requestAnimationFrame(animate);
}
```

---

## 五、推荐组合

| 场景 | 推荐动画 | 原因 |
|------|----------|------|
| 默认随机 | 6 种全部启用 | 每次打开都有新鲜感 |
| 科技感强调 | particles + orbitals + noise | 几何 + 网络 + 流体 |
| 浪漫感强调 | stars + aura + gradient | 星空 + 脉冲 + 流光 |
| 极简主义 | aura + orbitals | 只有几何，没有粒子 |
| 数据感 | particles + noise | 网络 + 流场 |

---

## 六、性能对比

| 动画 | 粒子/元素数 | CPU 占用 | 推荐度 |
|------|------------|----------|--------|
| particles | 30-50 | 低 | ⭐⭐⭐⭐⭐ |
| stars | 60-100 | 低 | ⭐⭐⭐⭐⭐ |
| aura | 5 环 + 12 线 | 极低 | ⭐⭐⭐⭐⭐ |
| noise | 80-120 线 | 中 | ⭐⭐⭐⭐ |
| orbitals | 3-4 环 | 极低 | ⭐⭐⭐⭐⭐ |
| gradient | 3 个渐变 | 极低 | ⭐⭐⭐⭐⭐ |

---

*方案由 Kimi 生成，6 种抽象动画全部纯 Canvas 实现，零外部依赖。*
