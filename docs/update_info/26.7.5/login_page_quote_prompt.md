# OmicHub 登录页引言添加 — 前端修改提示词

## 一、修改目标

在登录卡片（白色卡片）的**正上方**添加一段双语引言，作为页面视觉层次的补充：
- **中文在上**：`在某个地方，有某种不可思议的事物，正等待着被知晓。`
- **英文在下**：`Somewhere, something incredible is waiting to be known.`

## 二、具体位置

```
┌──────────────────────────────────────┐
│                                      │
│   [新引言文字 - 本提示词添加区域]      │  ← 新增
│                                      │
│   ┌──────────────────────────────┐   │
│   │  🐱                    🐈‍⬛   │   │
│   │      OmicHub               │   │
│   │   欢迎登录多组学分析平台    │   │
│   │                              │   │
│   │   用户名 *                   │   │
│   │   [________________]         │   │
│   │                              │   │
│   │   密码 *                     │   │
│   │   [________________]         │   │
│   │                              │   │
│   │   [登录]        [注册]       │   │
│   └──────────────────────────────┘   │
│                                      │
│   "We are made of star-stuff"        │  ← 已有
│   我们只是借用了宇宙中的这些原子...   │  ← 已有
│                                      │
└──────────────────────────────────────┘
```

- **定位**：登录卡片（白色圆角卡片）正上方，水平居中
- **间距**：与登录卡片顶部保持 `32px` 距离，与页面顶部保持适当呼吸空间
- **层级**：在星空背景之上，登录卡片之下（`z-index` 介于背景和卡片之间）

## 三、文字内容与排版

### 3.1 文字内容
```html
<div class="login-page-quote">
  <p class="quote-cn">在某个地方，有某种不可思议的事物，正等待着被知晓。</p>
  <p class="quote-en">Somewhere, something incredible is waiting to be known.</p>
</div>
```

### 3.2 排版规范

| 属性 | 中文 `.quote-cn` | 英文 `.quote-en` |
|------|------------------|------------------|
| **字号** | `18px`（桌面端）/ `15px`（移动端） | `14px`（桌面端）/ `12px`（移动端） |
| **字重** | `300`（细体） | `400`（常规） |
| **字体** | 系统无衬线字体栈，优先使用 `"PingFang SC", "Microsoft YaHei", sans-serif` | 优先使用 `"Georgia", "Times New Roman", serif` 或 `"Inter", sans-serif` |
| **颜色** | `rgba(255, 255, 255, 0.85)` | `rgba(255, 255, 255, 0.55)` |
| **对齐** | `text-align: center` | `text-align: center` |
| **行高** | `1.6` | `1.5` |
| **字间距** | `0.05em`（中文适当加宽） | `0.02em` |
| **文字阴影** | `0 1px 8px rgba(0,0,0,0.15)`（增加在星空背景上的可读性） | `0 1px 6px rgba(0,0,0,0.1)` |

### 3.3 间距规范

```css
.login-page-quote {
  margin-bottom: 32px;           /* 与登录卡片的距离 */
  text-align: center;
  max-width: 420px;              /* 控制换行，保持美观 */
  padding: 0 20px;               /* 移动端左右留白 */
}

.quote-cn {
  margin-bottom: 8px;            /* 中英文间距 */
}

.quote-en {
  margin-top: 0;
  margin-bottom: 0;
}
```

## 四、动画效果

### 4.1 入场动画

页面加载时，引言文字应比登录卡片**提前 200ms** 淡入，营造层次感：

```css
.login-page-quote {
  opacity: 0;
  transform: translateY(-12px);
  animation: quoteFadeIn 1.2s ease-out 0.3s forwards;  /* delay 0.3s */
}

@keyframes quoteFadeIn {
  0% {
    opacity: 0;
    transform: translateY(-12px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}
```

### 4.2 微光呼吸效果（可选，推荐）

为英文部分添加极轻微的呼吸感，呼应星空主题：

```css
.quote-en {
  animation: quoteFadeIn 1.2s ease-out 0.3s forwards,
             gentlePulse 4s ease-in-out 2s infinite;
}

@keyframes gentlePulse {
  0%, 100% { opacity: 0.55; }
  50% { opacity: 0.75; }
}
```

> ⚠️ 注意：如果底部已有引言使用类似动画，请调整节奏避免同步闪烁。

## 五、响应式适配

```css
@media (max-width: 480px) {
  .login-page-quote {
    margin-bottom: 24px;
    max-width: 300px;
  }

  .quote-cn {
    font-size: 15px;
  }

  .quote-en {
    font-size: 12px;
  }
}
```

## 六、完整代码示例（React/Vue 通用结构）

```jsx
// 在登录页面的主容器内，登录卡片组件之前插入
<div className="login-page-wrapper">
  {/* 星空背景 canvas 或 div — 已有 */}

  {/* ===== 新增：引言区域 ===== */}
  <div className="login-page-quote">
    <p className="quote-cn">在某个地方，有某种不可思议的事物，正等待着被知晓。</p>
    <p className="quote-en">Somewhere, something incredible is waiting to be known.</p>
  </div>

  {/* 登录卡片 — 已有 */}
  <div className="login-card">
    {/* ... */}
  </div>

  {/* 底部引言 — 已有 */}
  <div className="bottom-quote">
    {/* ... */}
  </div>
</div>
```

## 七、样式注意事项

1. **避免与猫咪重叠**：确保引言容器的 `max-width` 不会导致文字在极宽屏幕上无限延伸，保持与登录卡片视觉宽度协调。
2. **颜色一致性**：白色文字在紫色星空背景上必须带有轻微阴影，确保可读性。如果背景某些区域偏亮，可适当加深阴影或降低背景亮度。
3. **字体回退**：中文优先使用系统字体，避免引入外部字体文件导致加载延迟。
4. **动画性能**：使用 `transform` 和 `opacity` 实现动画，避免触发重排（`layout`）。

## 八、验收标准

- [ ] 登录卡片正上方出现双语引言，中文在上、英文在下
- [ ] 中文 `18px` 细体，英文 `14px` 稍浅，均居中显示
- [ ] 与登录卡片间距 `32px`，与猫咪无重叠
- [ ] 页面加载时有淡入动画，不突兀
- [ ] 移动端字号适当缩小，不换行过乱
- [ ] 整体风格与星空主题协调，不破坏现有视觉层次
