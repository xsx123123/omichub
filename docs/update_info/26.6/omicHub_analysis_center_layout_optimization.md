# OmicHub 分析中心布局优化方案

> 生成日期：2026-07-05
> 目标：解决分析中心 emoji 过大、布局松散、视觉层级混乱的问题

---

## 一、问题诊断

| 问题 | 现状 | 优化方向 |
|------|------|----------|
| emoji 过大 | 图标占据视觉中心，喧宾夺主 | 缩小至 36–44px，作为类型标识而非主角 |
| 推荐流程卡片 | 蓝色渐变背景突兀，与平台整体风格割裂 | 去掉渐变，改用顶部细 accent 线 + 浅色图标底色 |
| 全部流程卡片 | 单列排列，空间利用率低 | 改为 `grid` 双列/三列自适应 |
| 标签 | 字体大、间距松，信息密度低 | 缩小至 11–12px，紧凑排列 |
| 缺少交互反馈 | 静态卡片，无 hover 状态 | 添加微上浮 + 边框高亮 + 左侧色条 |

---

## 二、推荐流程卡片（Hero Card）

### 2.1 CSS

```css
.hero-card {
  position: relative;
  border: 1px solid var(--kimi-color-border);
  border-radius: 12px;
  padding: 20px;
  background: var(--kimi-color-surface-raised);
  overflow: hidden;
  cursor: pointer;
  transition: all var(--t-fast) var(--ease-out);
}

/* 顶部 accent 线替代渐变背景 */
.hero-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(
    90deg,
    var(--kimi-chart-1),
    color-mix(in srgb, var(--kimi-chart-4) 60%, transparent)
  );
}

/* emoji 容器：44px，浅色背景衬托 */
.hero-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--kimi-chart-1) 10%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;  /* emoji 实际大小 */
  flex-shrink: 0;
}

/* hover 效果 */
.hero-card:hover {
  border-color: var(--kimi-color-text-primary);
  transform: translateY(-1px);
}

/* GitHub 链接：默认隐藏，hover 显示 */
.github-link {
  opacity: 0;
  transition: opacity var(--t-fast) var(--ease-out);
}
.hero-card:hover .github-link {
  opacity: 1;
}
```

### 2.2 布局结构（flex：左图标 - 中内容 - 右 GitHub）

```html
<div class="hero-card">
  <div style="display: flex; align-items: flex-start; gap: 16px;">
    <!-- 左侧：小 emoji -->
    <div class="hero-icon">🧬</div>

    <!-- 中间：标题 + 描述 + 标签 -->
    <div style="flex: 1; min-width: 0;">
      <div style="display: flex; align-items: center; gap: 8px;">
        <h3 style="font-size: 17px; font-weight: 500; color: var(--kimi-color-text-primary); margin: 0;">
          RNA-seq 差异表达分析
        </h3>
        <span class="version-badge" style="font-size: 12px; color: var(--kimi-color-text-quaternary); background: var(--kimi-color-surface-muted); padding: 2px 8px; border-radius: 4px;">
          v2.2.0
        </span>
      </div>
      <p class="description" style="font-size: 14px; color: var(--kimi-color-text-secondary); margin: 6px 0 12px 0; line-height: 1.5;">
        基于已搭建好的 RNAFlow 流程（STAR + RSEM + DESeq2）的标准 RNA-seq 差异表达分析。提交后自动生成 RNAFlow 所需 config.yaml、samples.csv、contrasts.csv。
      </p>
      <div class="tags" style="display: flex; flex-wrap: wrap; gap: 6px;">
        <span class="tag" style="font-size: 12px; padding: 3px 10px; border-radius: 6px; background: color-mix(in srgb, var(--kimi-chart-1) 12%, transparent); color: var(--kimi-chart-1); font-weight: 500;">rnaseq</span>
        <span class="tag" style="font-size: 12px; padding: 3px 10px; border-radius: 6px; background: color-mix(in srgb, var(--kimi-chart-1) 12%, transparent); color: var(--kimi-chart-1); font-weight: 500;">differential-expression</span>
        <span class="tag" style="font-size: 12px; padding: 3px 10px; border-radius: 6px; background: color-mix(in srgb, var(--kimi-chart-1) 12%, transparent); color: var(--kimi-chart-1); font-weight: 500;">STAR</span>
        <span class="tag" style="font-size: 12px; padding: 3px 10px; border-radius: 6px; background: color-mix(in srgb, var(--kimi-chart-1) 12%, transparent); color: var(--kimi-chart-1); font-weight: 500;">RSEM</span>
        <span class="tag" style="font-size: 12px; padding: 3px 10px; border-radius: 6px; background: color-mix(in srgb, var(--kimi-chart-1) 12%, transparent); color: var(--kimi-chart-1); font-weight: 500;">DESeq2</span>
        <span class="tag" style="font-size: 12px; padding: 3px 10px; border-radius: 6px; background: color-mix(in srgb, var(--kimi-chart-1) 12%, transparent); color: var(--kimi-chart-1); font-weight: 500;">RNAFlow</span>
      </div>
    </div>

    <!-- 右侧：GitHub 图标 -->
    <div class="github-link" style="flex-shrink: 0;">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--kimi-color-text-tertiary)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
      </svg>
    </div>
  </div>
</div>
```

---

## 三、全部流程卡片（Grid Card）

### 3.1 CSS

```css
.flow-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

.flow-card {
  position: relative;
  border: 1px solid var(--kimi-color-border);
  border-radius: 10px;
  padding: 16px;
  background: var(--kimi-color-surface);
  cursor: pointer;
  transition: all var(--t-fast) var(--ease-out);
  overflow: hidden;
}

/* 左侧色条：默认隐藏，hover 显示 */
.flow-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 3px; height: 100%;
  background: var(--kimi-chart-3); /* 每个卡片用不同 chart 色 */
  opacity: 0;
  transition: opacity var(--t-fast) var(--ease-out);
}

.flow-card:hover::before {
  opacity: 1;
}

.flow-card:hover {
  border-color: var(--kimi-color-text-primary);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px color-mix(in srgb, var(--kimi-color-text-primary) 6%, transparent);
}

/* 小卡片 emoji：36px */
.flow-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--kimi-chart-3) 10%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

/* 标签 */
.flow-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--kimi-chart-3) 10%, transparent);
  color: var(--kimi-chart-3);
  font-weight: 500;
}

/* 描述文字截断（2行） */
.flow-desc {
  font-size: 13px;
  color: var(--kimi-color-text-secondary);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
```

### 3.2 布局结构

```html
<div class="flow-grid">
  <!-- Card 1 -->
  <div class="flow-card">
    <div style="display: flex; align-items: flex-start; gap: 12px;">
      <div class="flow-icon">🧪</div>
      <div style="flex: 1; min-width: 0;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
          <h4 style="font-size: 15px; font-weight: 500; color: var(--kimi-color-text-primary); margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            ATAC-seq 染色质可及性分析
          </h4>
          <span style="font-size: 11px; color: var(--kimi-color-text-quaternary); flex-shrink: 0; margin-left: 8px;">
            v0.0.5
          </span>
        </div>
        <p class="flow-desc" style="margin: 0 0 10px 0;">
          基于已搭建好的 ATACFlow 流程（Bowtie2/Chromap + MACS2 + TOBIAS）的标准 ATAC-seq 染色质可及性分析。
        </p>
        <div style="display: flex; flex-wrap: wrap; gap: 4px;">
          <span class="flow-tag">atacseq</span>
          <span class="flow-tag">chromatin-accessibility</span>
          <span class="flow-tag">Bowtie2</span>
          <span class="flow-tag">MACS2</span>
          <span class="flow-tag">TOBIAS</span>
          <span class="flow-tag">ATACFlow</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Card 2 ... -->
</div>
```

---

## 四、标签（Tag）统一规范

```css
.tag, .flow-tag {
  font-size: 11px;              /* 原尺寸过大，缩小 */
  padding: 2px 8px;             /* 更紧凑 */
  border-radius: 4px;           /* 小圆角 */
  background: color-mix(in srgb, var(--chart-color) 10%, transparent);
  color: var(--chart-color);
  font-weight: 500;
}
```

---

## 五、配色与图标映射（从 yaml meta 读取）

在流程的 `meta` 中定义图标和主题色，前端动态渲染：

```yaml
# 示例：rna_seq.yaml
meta:
  id: rna_seq
  name: "RNA-seq 差异表达分析"
  icon: "🧬"           # 或 SVG icon name
  color: "chart-1"     # 映射到 --kimi-chart-1
  github_url: "https://github.com/xxx/RNAFlow"
  tags:
    - rnaseq
    - differential-expression
    - STAR
    - RSEM
    - DESeq2
    - RNAFlow
```

前端映射表：

```js
const COLOR_MAP = {
  'chart-1': 'var(--kimi-chart-1)',  // 蓝
  'chart-2': 'var(--kimi-chart-2)',  // 红
  'chart-3': 'var(--kimi-chart-3)',  // 绿
  'chart-4': 'var(--kimi-chart-4)',  // 紫
};
```

---

## 六、修改清单（TODO）

- [ ] **缩小 emoji**：推荐流程 22px（容器 44px），普通卡片 18px（容器 36px）
- [ ] **去掉推荐流程渐变背景**，改为顶部 3px accent 线
- [ ] **全部流程改为 grid 布局**，`minmax(320px, 1fr)` 自适应列数
- [ ] **标签缩小到 11px**，padding 改为 `2px 8px`
- [ ] **添加 hover 动效**：卡片 `translateY(-1px)` + 边框变色 + 左侧色条显现
- [ ] **GitHub 链接改为 hover 显示**，减少视觉噪音
- [ ] **描述文字限制 2 行**，防止卡片高度不齐
- [ ] **版本号**移到标题右侧，用 `font-size: 11–12px` + 灰色背景小 badge
- [ ] **从 yaml meta 读取 `icon` 和 `color`**，实现动态配色

---

## 七、设计原则速查

| 原则 | 说明 |
|------|------|
| 黑白优先 | 主文字用 `--kimi-color-text-primary`，交互高亮也用黑色系 |
| 灰色做层次 | 次级文字、边框、分隔线用 gray token |
| accent 只做语义 | 标签、状态、图表系列才用彩色，不做大面积背景 |
| 间距对齐 4px 栅格 | 4 / 8 / 12 / 16 / 20 / 24 / 32px，不用奇数 |
| 圆角嵌套规则 | 外层 > 内层，如 12px 面板包 8px 子元素 |
| 动效克制 | 只保留 hover 微上浮 + 边框变色，不做过渡动画 |

---

*方案由 Kimi 生成，可直接交付前端实现。*
