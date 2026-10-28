# OmicHub 登录页综合优化 — 顶部引言 + 猫咪调整

## 一、修改目标（两项合并）

1. **顶部引言调整**：位置移至页面最顶部，样式与底部引言完全一致
2. **猫咪优化**：移除橘猫，仅保留黑猫，放大居中放置于 OmicHub 标题正上方

## 二、最终布局示意

```
┌────────────────────────────────────────┐
│                                        │
│   在某个地方，有某种不可思议的事物，      │  ← 顶部中文 14px
│   正等待着被知晓。                       │
│                                        │
│   "Somewhere, something incredible      │  ← 顶部英文 16px 斜体
│    is waiting to be known."            │
│                                        │
│   ┌──────────────────────────────┐   │
│   │        🐈‍⬛ 黑猫（放大）        │   │  ← 唯一吉祥物，探出卡片
│   │                                │   │
│   │         OmicHub                │   │
│   │      欢迎登录多组学分析平台     │   │
│   │             ...               │   │
│   └──────────────────────────────┘   │
│                                        │
│              ...                       │
│                                        │
│   "We are made of star-stuff"          │  ← 底部英文（样式基准）
│   我们只是借用了宇宙中的这些原子...      │  ← 底部中文（样式基准）
│                                        │
└────────────────────────────────────────┘
```

## 三、顶部引言（Part 1）

### 3.1 位置

- 页面**最顶端**，与浏览器上边缘间距 `24px`（桌面端）/ `18px`（移动端）
- 水平**居中**
- 使用绝对定位，不随页面滚动

```css
.login-page-top-quote {
  position: absolute;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 5;
  text-align: center;
  padding: 0 20px;
  width: 100%;
  max-width: 500px;
  pointer-events: none;
}
```

### 3.2 样式（与底部引言完全一致）

| 属性 | 中文 `.quote-cn` | 英文 `.quote-en` |
|------|------------------|------------------|
| 字号 | `14px` | `16px` |
| 字重 | `400` | `400` |
| 颜色 | `rgba(255,255,255,0.65)` | `rgba(255,255,255,0.85)` |
| 字体 | 系统无衬线 | 衬线或斜体 |
| 对齐 | 居中 | 居中 |
| 行高 | `1.5` | `1.5` |
| 字间距 | `0.02em` | `0.01em` |
| 文字阴影 | `0 1px 4px rgba(0,0,0,0.2)` | `0 1px 4px rgba(0,0,0,0.2)` |
| 特殊样式 | 正常体 | **斜体** `font-style: italic` |
| 引号 | 无 | 英文两侧保留 `"..."` |

```css
.login-page-top-quote .quote-cn {
  font-size: 14px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.65);
  line-height: 1.5;
  letter-spacing: 0.02em;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  margin: 0 0 6px 0;
}

.login-page-top-quote .quote-en {
  font-size: 16px;
  font-weight: 400;
  font-style: italic;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.5;
  letter-spacing: 0.01em;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  margin: 0;
}
```

### 3.3 入场动画

```css
.login-page-top-quote {
  opacity: 0;
  animation: topQuoteFadeIn 1.5s ease-out 0.2s forwards;
}

@keyframes topQuoteFadeIn {
  0% { opacity: 0; }
  100% { opacity: 1; }
}
```

## 四、猫咪优化（Part 2）

### 4.1 移除橘猫

- 删除橘猫相关的 DOM 元素、组件引用、图片资源、CSS 样式
- 确保构建产物中不再包含橘猫资源

### 4.2 黑猫位置与尺寸

黑猫放置于**登录卡片内部、OmicHub 标题正上方**，头部探出卡片：

```html
<div class="login-card-header">
  <div class="cat-mascot-wrapper">
    <img src="black-cat.svg" alt="OmicHub Mascot" class="cat-mascot" />
  </div>
  <h1 class="login-title">OmicHub</h1>
  <p class="login-subtitle">欢迎登录多组学分析平台</p>
</div>
```

```css
.cat-mascot-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: -55px;         /* 探出卡片顶部 */
  margin-bottom: 12px;
  position: relative;
  z-index: 10;
}

.cat-mascot {
  width: 130px;              /* 桌面端 */
  height: auto;
  filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.15));
  transition: transform 0.3s ease;
}

.cat-mascot:hover {
  transform: scale(1.05) translateY(-4px);
}
```

### 4.3 黑猫入场动画

```css
.cat-mascot-wrapper {
  opacity: 0;
  transform: translateY(-20px);
  animation: catDropIn 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) 0.5s forwards;
}

@keyframes catDropIn {
  0% { opacity: 0; transform: translateY(-20px) scale(0.9); }
  70% { transform: translateY(4px) scale(1.02); }
  100% { opacity: 1; transform: translateY(0) scale(1); }
}
```

> 黑猫动画延迟 `0.5s`，在顶部引言（`0.2s`）之后出现，形成层次。

## 五、完整页面结构

```jsx
<div className="login-page-container">
  {/* 星空背景 */}
  <canvas className="star-bg" />

  {/* ===== 顶部引言 ===== */}
  <div className="login-page-top-quote">
    <p className="quote-cn">在某个地方，有某种不可思议的事物，正等待着被知晓。</p>
    <p className="quote-en">"Somewhere, something incredible is waiting to be known."</p>
  </div>

  {/* 登录卡片 */}
  <div className="login-card">
    <div className="login-card-header">
      {/* 黑猫（唯一吉祥物） */}
      <div className="cat-mascot-wrapper">
        <img src="black-cat.svg" alt="OmicHub Mascot" className="cat-mascot" />
      </div>
      <h1 className="login-title">OmicHub</h1>
      <p className="login-subtitle">欢迎登录多组学分析平台</p>
    </div>
    {/* 表单内容 ... */}
  </div>

  {/* 底部引言 */}
  <div className="login-page-bottom-quote">
    <p className="quote-en">"We are made of star-stuff"</p>
    <p className="quote-cn">我们只是借用了宇宙中的这些原子，短暂地体验了一次这个世界。</p>
  </div>
</div>
```

## 六、响应式适配

```css
@media (max-width: 768px) {
  .login-page-top-quote {
    top: 20px;
  }

  .login-page-top-quote .quote-cn {
    font-size: 13px;
  }

  .login-page-top-quote .quote-en {
    font-size: 14px;
  }

  .cat-mascot-wrapper {
    margin-top: -40px;
    margin-bottom: 8px;
  }

  .cat-mascot {
    width: 100px;
  }
}

@media (max-width: 480px) {
  .login-page-top-quote {
    top: 18px;
    padding: 0 16px;
  }

  .cat-mascot-wrapper {
    margin-top: -30px;
    margin-bottom: 6px;
  }

  .cat-mascot {
    width: 85px;
  }
}
```

## 七、z-index 层级管理

确保各元素层级正确，互不遮挡：

| 元素 | z-index | 说明 |
|------|---------|------|
| 星空背景 | `0` | 最底层 |
| 顶部引言 | `5` | 在背景之上，不阻挡交互 |
| 登录卡片 | `10` | 主要内容层 |
| 黑猫 | `15` | 探出卡片，需高于卡片 |
| 底部引言 | `5` | 与顶部一致 |
| 弹窗/下拉 | `100+` | 最高交互层 |

## 八、注意事项

1. **顶部引言与黑猫不重叠**：顶部引言在页面最顶端，黑猫在登录卡片顶部，两者垂直方向有足够距离，互不干扰。
2. **父容器定位**：顶部引言使用 `position: absolute` 时，确保 `.login-page-container` 设置 `position: relative`。
3. **pointer-events**：顶部引言设置 `pointer-events: none`，不阻挡星空背景交互。
4. **图片清晰度**：放大后的黑猫如为 PNG，需确认分辨率足够；SVG 则无需担心。
5. **动画顺序**：顶部引言先出现（`0.2s`），黑猫后出现（`0.5s`），登录卡片最后（`0.8s`），形成自然的视觉层次。
6. **文字阴影**：星空背景有动态粒子，所有白色文字必须带轻微阴影确保可读性。

## 九、验收标准

### 顶部引言
- [ ] 位于页面最顶部，与上边缘间距 `24px`
- [ ] 中文 `14px`、英文 `16px` 斜体，字号与底部完全一致
- [ ] 中文颜色 `rgba(255,255,255,0.65)`、英文 `rgba(255,255,255,0.85)`
- [ ] 英文两侧保留双引号 `"..."`
- [ ] 入场淡入动画，不突兀

### 猫咪
- [ ] 橘猫已完全移除，无残留代码/资源
- [ ] 黑猫居中于 OmicHub 标题正上方
- [ ] 黑猫宽度 `130px`（桌面端），等比例缩放
- [ ] 黑猫头部探出卡片顶部（负边距效果）
- [ ] 弹性入场动画，鼠标悬停有微上浮反馈
- [ ] 移动端尺寸适当缩小，布局不崩

### 整体
- [ ] 顶部引言、黑猫、登录卡片、底部引言四层视觉节奏清晰
- [ ] 整体风格与星空主题协调统一
