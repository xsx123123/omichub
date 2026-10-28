 j# OmicHub 节日彩蛋 — 每个节日完全独特的设计方案

> 目标：17个节日，17种完全不同的视觉体验、文案诗句、动画效果

---

## 设计概览

每个节日包含：
- **主题诗句** — 经典诗词或原创文案
- **视觉主题** — 独特的配色、背景、装饰
- **核心动画** — 该节日专属的 Canvas/CSS 动画
- **装饰元素** — 该节日特有的图标/图案
- **音效建议** — 可选的氛围音效

---

## 一、🎊 春节 — 爆竹迎新

```yaml
name: "🎊 春节"
title: "新春大吉"
poem: "爆竹声中一岁除，春风送暖入屠苏"
poem_author: "王安石《元日》"
message: "在这辞旧迎新的时刻，愿星光为你指引前路。OmicHub 送你 {amount} 额度，开启新一年的探索之旅！"
```

### 视觉设计
- **背景**：暗红渐变 `linear-gradient(145deg, #1a0505, #2d0a0a)`
- **装饰**：
  - 顶部悬挂两个红色春联竖幅，左边写"福"，右边写"春"
  - 底部飘落金色纸屑（模拟爆竹碎屑）
  - 角落点缀小灯笼 emoji 🏮
- **配色**：红(#c41e1e) + 金(#FFD700) + 暗红底

### 核心动画 — 烟花绽放
```
效果：全屏烟花从底部随机位置发射
- 3-5个发射点同时升空
- 到达顶点后炸开成金色/红色/橙色的粒子
- 粒子带重力下落，逐渐消失
- 持续 8-10 秒后渐弱
- 使用 @fireworks-js/react 或 canvas-confetti 烟花模式
```

### 弹窗样式
- 边框：2px 金色光晕
- 标题：金色大字 + 红色描边
- 诗句区域：书法风格字体（可引入中文字体）
- 额度展示：金色发光数字

---

## 二、🏮 元宵节 — 灯火阑珊

```yaml
name: "🏮 元宵节"
title: "元宵喜乐"
poem: "众里寻他千百度，蓦然回首，那人却在，灯火阑珊处"
poem_author: "辛弃疾《青玉案·元夕》"
message: "花灯如昼，月圆人团圆。每一盏灯笼都是一颗坠落的星星，照亮我们短暂而美丽的旅程。送你 {amount} 额度！"
```

### 视觉设计
- **背景**：暖棕渐变 `linear-gradient(145deg, #1a1008, #2d1f12)`
- **装饰**：
  - 3-5个暖橙色灯笼从顶部缓缓飘落，左右摇摆
  - 灯笼带有穗子，底部发光
  - 背景有淡淡的圆月光晕
- **配色**：暖橙(#FFA500) + 金黄(#FFD700) + 暖棕底

### 核心动画 — 灯笼飘浮
```
效果：灯笼从屏幕上方缓缓飘落
- 每个灯笼有独立的摇摆路径（正弦波）
- 灯笼内部有微微发光效果（box-shadow 脉动）
- 底部有倒影效果
- 持续整个弹窗展示期间
- CSS animation + 绝对定位实现
```

### 弹窗样式
- 顶部诗引用斜体展示，暖橙色
- 文案区域带有淡淡的灯火纹理
- 按钮：橙底，悬停时灯笼摆动

---

## 三、🐲 端午节 — 龙舟竞渡

```yaml
name: "🐲 端午节"
title: "端午安康"
poem: "路漫漫其修远兮，吾将上下而求索"
poem_author: "屈原《离骚》"
message: "粽叶飘香，龙舟竞渡。我们如原子般短暂汇聚，又终将散入星河。送你 {amount} 额度，端午安康！"
```

### 视觉设计
- **背景**：墨绿渐变 `linear-gradient(145deg, #081a10, #122d1f)`
- **装饰**：
  - 底部有淡淡的水波纹效果（CSS 动画）
  - 水面上有简笔龙舟剪影划过
  - 角落有粽叶形状的装饰
- **配色**：青绿(#4ECDC4) + 粽叶绿(#2d6b3f) + 墨绿底

### 核心动画 — 龙舟划水
```
效果：水面波纹 + 龙舟划过
- 底部 30% 区域为水波效果（CSS sine wave）
- 一艘简笔龙舟从左到右缓缓划过
- 龙舟过后留下水波纹扩散
- 水面上有粽叶形状的叶片飘浮
- Canvas 绘制或使用 CSS animation
```

### 弹窗样式
- 水波纹从弹窗底部漫过
- 文案用清新的绿色调
- 按钮带有叶脉纹理

---

## 四、💕 七夕 — 星河鹊桥

```yaml
name: "💕 七夕"
title: "七夕快乐"
poem: "两情若是久长时，又岂在朝朝暮暮"
poem_author: "秦观《鹊桥仙》"
message: "在浩瀚宇宙中相遇，是千万分之一的奇迹。就像两颗原子在星云中偶然碰撞，绽放出独特的光芒。送你 {amount} 额度～"
```

### 视觉设计
- **背景**：深紫渐变 `linear-gradient(145deg, #1a0820, #2d1238)`
- **装饰**：
  - 背景是银河（白色星点密集带，斜跨屏幕）
  - 银河两侧有两颗特别亮的星星（牛郎织女）
  - 两颗星星之间有淡淡的连线（鹊桥）
  - 粉色爱心粒子在银河周围飘浮
- **配色**：粉紫(#FF85C0) + 星光白 + 深紫底

### 核心动画 — 银河鹊桥
```
效果：银河闪烁 + 爱心飘浮 + 星星连线脉动
- 银河区域的星星密度更高，随机闪烁
- 牛郎织女两颗星之间有渐变色连线
- 连线颜色在粉→紫→粉之间流动
- 粉色爱心从连线处向四周缓缓飘散
- 使用 Canvas 绘制星星 + CSS animation 连线
```

### 弹窗样式
- 诗句用浪漫的斜体+粉色
- 背景透出银河效果
- 额度数字粉红发光
- 按钮粉紫渐变

---

## 五、🌕 中秋 — 千里婵娟

```yaml
name: "🌕 中秋节"
title: "中秋团圆"
poem: "但愿人长久，千里共婵娟"
poem_author: "苏轼《水调歌头·明月几时有》"
message: "这一轮明月，不过是宇宙中一颗普通的卫星，却因为仰望它的人而被赋予了意义。就像 OmicHub 因为有你而特别。送你 {amount} 额度！"
```

### 视觉设计
- **背景**：深海蓝渐变 `linear-gradient(145deg, #080a1a, #0a1025)`
- **装饰**：
  - 右上角：一轮金色满月缓缓升起（从屏幕外升到右上）
  - 月亮表面有淡淡的光影纹理（CSS radial-gradient）
  - 月亮周围有光晕（box-shadow 多层）
  - 月亮旁有淡淡的兔子剪影
  - 底部有云朵缓缓飘过
- **配色**：月光金(#E8DCC8) + 月白(#C0D6F5) + 深海蓝底

### 核心动画 — 圆月升起 ★ 重点效果
```
效果：圆月从屏幕右下角缓缓升起
- 初始状态：月亮在屏幕右下方边缘外
- 动画过程：3-5秒内缓缓移动到右上角
- 移动过程中月亮逐渐变亮、变大
- 到达位置后月亮稳定发光，微微脉动
- 月光向四周散射（CSS 多层 box-shadow）
- 底部有半透明云朵缓缓从左向右飘过

实现方式：
- 月亮：一个圆形 div，background: radial-gradient
- 动画：CSS @keyframes rise 控制 transform: translate()
- 光晕：多层 box-shadow，白色 + 金色
- 云朵：半透明椭圆，CSS animation 横向移动
```

### 弹窗样式 ★ 最诗意的设计
- 诗句**但愿人长久，千里共婵娟**用大号书法字体居中展示
- 诗句下方是作者名"— 苏轼"
- 文案区域带有月光般的柔和光效
- 整个弹窗像是一封来自星空的信
- 按钮：银蓝渐变，像月光凝结

---

## 六、🍂 重阳节 — 登高望远

```yaml
name: "🍂 重阳节"
title: "重阳登高"
poem: "遥知兄弟登高处，遍插茱萸少一人"
poem_author: "王维《九月九日忆山东兄弟》"
message: "登高望远，秋风送爽。我们来自星辰，终将回归星辰。在这短暂的人生旅程中，愿你处处有温暖。送你 {amount} 额度！"
```

### 视觉设计
- **背景**：暖褐渐变 `linear-gradient(145deg, #1a1408, #2d2512)`
- **装饰**：
  - 底部有连绵的山峦剪影（CSS 绘制）
  - 山峦上有一个人影在登高
  - 空中飘落菊花和枫叶
  - 远处有淡淡的山雾效果
- **配色**：金黄(#DAA520) + 秋橙(#CD853F) + 暖褐底

### 核心动画 — 登高望远
```
效果：山峦剪影 + 枫叶/菊花飘落 + 山雾流动
- 底部有3层山峦剪影，远近不同透明度
- 一个人影在山路上缓缓向上移动
- 空中随机飘落菊花花瓣和枫叶
  - 枫叶：橙红色，旋转下落
  - 菊花：金黄色，缓缓飘落
- 山层之间有薄雾缓缓流动（CSS blur + opacity animation）
```

### 弹窗样式
- 诗句带有一丝思乡的诗意
- 文案带有秋日暖阳的感觉
- 按钮金黄底色

---

## 七、🎉 元旦 — 万象更新

```yaml
name: "🎉 元旦"
title: "新年快乐"
poem: "新年都未有芳华，二月初惊见草芽"
poem_author: "韩愈《春雪》"
message: "新的一年，新的宇宙。每一个新的开始，都像是一次超新星爆发，释放无限能量。OmicHub 送你 {amount} 额度，新年快乐！"
```

### 视觉设计
- **背景**：深空紫 `linear-gradient(145deg, #050520, #101040)`
- **装饰**：
  - 全屏烟花绽放（最华丽的版本）
  - 背景有倒计时的数字残影
  - 星星比平时更加闪烁
- **配色**：彩虹渐变 + 金色 + 深空底

### 核心动画 — 跨年烟花 ★ 最华丽的动画
```
效果：全屏多点烟花连续绽放
- 10+个发射点，不同高度、不同颜色
- 烟花颜色：金、红、蓝、绿、紫交替
- 每次绽放后有残影渐消
- 天空偶尔有流星的划过
- 持续 10-15 秒
- 使用 @fireworks-js/react，配置最丰富的参数
```

### 弹窗样式
- 标题用彩虹渐变文字
- 最华丽的边框光效
- 额度数字带彩虹渐变发光

---

## 八、🛠️ 劳动节 — 耕耘收获

```yaml
name: "🛠️ 劳动节"
title: "劳动节快乐"
poem: "锄禾日当午，汗滴禾下土。谁知盘中餐，粒粒皆辛苦"
poem_author: "李绅《悯农》"
message: "劳动最光荣！每一行代码、每一次实验，都是在为这个世界创造价值。送你 {amount} 额度，休息一下～"
```

### 视觉设计
- **背景**：深蓝灰 `linear-gradient(145deg, #0a0e1a, #151a28)`
- **装饰**：
  - 齿轮 ⚙️ 在角落缓缓转动
  - 麦穗图案装饰边框
  - 工具图标（锤子、扳手）半透明点缀
- **配色**：暖橙(#FFB732) + 麦穗金 + 深蓝灰底

### 核心动画 — 齿轮转动 + 麦穗摇曳
```
效果：工业感 + 丰收感
- 右上角齿轮持续缓慢转动（CSS rotate animation）
- 底部麦穗图案微微摇曳（CSS transform skew animation）
- 偶尔有金色粒子从麦穗上飘起
```

---

## 九、🇨🇳 国庆节 — 盛世华诞

```yaml
name: "🇨🇳 国庆节"
title: "国庆快乐"
poem: "山河无恙，烟火寻常，这盛世如您所愿"
poem_author: "——"
message: "盛世华诞，举国同庆。七十余年前的那声宣告，至今仍在我们心中回响。送你 {amount} 额度，祝福祖国！"
```

### 视觉设计
- **背景**：深红渐变 `linear-gradient(145deg, #1a0505, #2d0a0a)`
- **装饰**：
  - 左上角有五角星发光效果
  - 烟花在背景绽放（红+金配色）
  - 底部有天安门剪影轮廓
- **配色**：中国红(#FF0000) + 金色(#FFD700) + 深红底

### 核心动画 — 红旗飘扬 + 烟花绽放
```
效果：五角星闪耀 + 红金烟花
- 左上角五角星持续发光脉动
- 背景烟花红金配色连续绽放
- 底部天安门剪影上有光点流动
```

---

## 十、❤️ 情人节 — 心有灵犀

```yaml
name: "❤️ 情人节"
title: "情人节快乐"
poem: "身无彩凤双飞翼，心有灵犀一点通"
poem_author: "李商隐《无题》"
message: "爱与被爱，都是幸福。就像两颗恒星在引力中相互环绕，永不分离。送你 {amount} 额度，祝幸福！"
```

### 视觉设计
- **背景**：深紫红 `linear-gradient(145deg, #1a0810, #2d1218)`
- **装饰**：
  - 满屏粉色爱心缓缓升起（从底部向顶部飘）
  - 爱心大小不一，透明度不同
  - 偶尔有玫瑰花瓣飘落
- **配色**：玫瑰粉(#FF6B9D) + 深红 + 浪漫紫

### 核心动画 — 爱心升起
```
效果：爱心从底部缓缓升起，如同爱意升腾
- 爱心从屏幕底部边缘生成
- 以不同速度向顶部飘去
- 大小随机（10px - 40px）
- 颜色从粉到紫渐变
- 部分爱心带有微光效果
- 持续整个弹窗展示期间
- 使用 CSS animation + 绝对定位 + 随机延迟
```

---

## 十一、🎄 圣诞节 — 雪夜驯鹿

```yaml
name: "🎄 圣诞节"
title: "圣诞快乐"
poem: "Silent night, holy night, all is calm, all is bright"
poem_author: "《Silent Night》"
message: "Merry Christmas！愿你的代码永远无 bug，愿你的实验永远有阳性结果，愿你的论文永远一次过审！送你 {amount} 额度！"
```

### 视觉设计
- **背景**：冬夜蓝 `linear-gradient(145deg, #080a1a, #0f1528)`
- **装饰**：
  - 雪花从顶部缓缓飘落（大小不一，旋转）
  - 右上角有圣诞树剪影，树上的灯闪烁
  - 底部有驯鹿剪影拉雪橇飞过（偶尔）
- **配色**：冰蓝(#87CEEB) + 圣诞绿(#2d8a4e) + 暖白

### 核心动画 — 雪夜飘雪
```
效果：逼真的雪花飘落
- 雪花从屏幕顶部随机位置生成
- 每片雪花有独特的大小、速度、旋转角度
- 雪花下落路径有轻微左右漂移
- 部分雪花带有微光闪烁
- 地面逐渐积起薄薄的白雪层（底部渐变）
- 使用 react-snowfall 组件
```

---

## 十二、🌱 立春 — 万物复苏

```yaml
name: "🌱 立春"
title: "立春"
poem: "东风带雨逐西风，大地阳和暖气生"
poem_author: "左河水"
message: "春回大地，万物复苏。宇宙也开始新一轮的生命循环。那些沉睡的种子，终将在星光的滋养下破土而出。送你 {amount} 额度！"
```

### 视觉设计
- **背景**：暗绿渐变 `linear-gradient(145deg, #081a0a, #0a1e0c)`
- **装饰**：
  - 底部有嫩芽从土壤中钻出（CSS 动画）
  - 粉色花瓣从右侧飘入
  - 背景有淡淡的光斑（阳光穿透树叶）
- **配色**：嫩绿(#90EE90) + 花粉(#FFB6C1) + 暗绿底

### 核心动画 — 春芽破土
```
效果：嫩芽生长 + 花瓣飘落
- 底部有几株嫩芽缓缓生长（CSS scale + translateY）
- 粉色花瓣从右向左飘过
- 背景光斑微微移动（模拟阳光摇曳）
- 整体氛围清新温暖
```

---

## 十三、☀️ 夏至 — 烈日当空

```yaml
name: "☀️ 夏至"
title: "夏至"
poem: "昼晷已云极，宵漏自此长"
poem_author: "韦应物《夏至避暑北池》"
message: "昼最长，夜最短。恒星也以最炽烈的姿态燃烧自己，照亮周遭的黑暗。送你 {amount} 额度，夏日快乐！"
```

### 视觉设计
- **背景**：深暖渐变 `linear-gradient(145deg, #1a1208, #2d1f10)`
- **装饰**：
  - 右上角有一轮炽热的太阳（带光晕和射线）
  - 太阳的光芒微微脉动
  - 背景有热浪扭曲效果（CSS filter）
- **配色**：金黄(#FFD700) + 烈橙(#FF8C00) + 深暖底

### 核心动画 — 烈日脉动
```
效果：太阳发光 + 热浪扭曲 + 光斑
- 右上角太阳持续发光（box-shadow 多层脉动）
- 太阳周围有射线缓缓旋转（CSS rotate）
- 背景有热浪扭曲效果（CSS blur + opacity）
- 金色粒子从太阳向外辐射
```

---

## 十四、🍁 秋分 — 层林尽染

```yaml
name: "🍁 秋分"
title: "秋分"
poem: "自古逢秋悲寂寥，我言秋日胜春朝"
poem_author: "刘禹锡《秋词》"
message: "昼夜均分，秋意渐浓。每一片落叶都是大自然写给我们的一封信。送你 {amount} 额度！"
```

### 视觉设计
- **背景**：暖褐渐变 `linear-gradient(145deg, #1a1008, #1e140a)`
- **装饰**：
  - 枫叶从顶部飘落（红、橙、黄、棕色）
  - 底部有堆积的落叶层
  - 背景有淡淡的暖色调光晕
- **配色**：秋橙(#D2691E) + 枫红(#CD5C5C) + 金黄 + 暖褐底

### 核心动画 — 枫叶纷飞
```
效果：多彩枫叶飘落
- 枫叶从屏幕顶部随机位置生成
- 枫叶有红、橙、黄、棕多种颜色
- 每片枫叶旋转着缓缓下落
- 底部逐渐堆积落叶层（opacity 渐变）
- 整体色调温暖如秋日午后
```

---

## 十五、❄️ 冬至 — 饺子暖心

```yaml
name: "❄️ 冬至"
title: "冬至"
poem: "天时人事日相催，冬至阳生春又来"
poem_author: "杜甫《小至》"
message: "冬至大如年。在最长的黑夜里，愿 OmicHub 的一点点温暖，能照亮你的研究之路。记得吃饺子！送你 {amount} 额度！"
```

### 视觉设计
- **背景**：冬夜深蓝 `linear-gradient(145deg, #0a0a1a, #101028)`
- **装饰**：
  - 雪花缓缓飘落（比圣诞节的雪更轻柔）
  - 底部有热腾腾的饺子 🥟 图标
  - 饺子冒着热气（CSS 动画）
  - 窗户上有冰花纹理（CSS frost effect）
- **配色**：暖白(#F0F0FF) + 冰蓝(#B0C4DE) + 暖黄（饺子蒸汽）

### 核心动画 — 雪夜暖心
```
效果：轻柔雪花 + 热气腾腾
- 雪花比圣诞节更轻柔、更稀疏
- 底部有饺子图标，上面冒着热气（CSS translateY + opacity）
- 背景有淡淡的暖光（室内灯光的感觉）
- 整体氛围温馨、宁静
```

---

## 十六、💻 程序员节 — Hello World

```yaml
name: "💻 程序员节"
title: "1024 程序员节"
poem: "Hello World!"
poem_author: "每一个程序员的起点"
message: "// 在这个特别的日子里\n// 愿你代码无bug，实验有结果\n// 愿你编译通过，论文accepted\n// OmicHub.send(amount: {amount})\n// → 领取成功 ✓"
```

### 视觉设计
- **背景**：纯黑 `#000000`
- **装饰**：
  - 绿色代码雨从顶部下落（矩阵风格）
  - 代码雨由 0、1、{}、()、; 等字符组成
  - 左上角有终端光标闪烁 `_`
  - 弹窗边框是绿色像素风格
- **配色**：终端绿(#00FF66) + 矩阵暗绿(#008830) + 纯黑底

### 核心动画 — 代码雨 ★ 最酷的动画
```
效果：矩阵风格绿色代码雨
- 多列字符从屏幕顶部下落
- 每列速度不同，字符随机（0、1、{、}、(、)、;、/ 等）
- 每列底部有渐消效果（opacity 渐变）
- 整体色调绿色
- 弹窗出现时有一个"打字机"效果，逐字显示文案

实现方式：
- Canvas 绘制多列文字
- 每帧更新每列的位置
- 随机生成代码字符
- 底部字符逐渐消失
```

### 弹窗样式 ★ 最有个性的设计
- 所有文字使用等宽字体（JetBrains Mono / Fira Code）
- 文案以代码注释格式展示（// 开头）
- 按钮文案：`console.log("领取")` 或 `git commit -m "领取额度"`
- 领取成功后显示：`// Status: 200 OK`
- 底部 tagline：`/* We are made of star-stuff */`

---

## 十七、🎂 OmicHub 周年庆 — 星云汇聚

```yaml
name: "🎂 OmicHub 周年庆"
title: "OmicHub 一岁啦！"
poem: "We are made of star-stuff"
poem_author: "Carl Sagan"
message: "从第一行代码到今天，OmicHub 已经陪伴大家走过了一整年。感谢每一个在深夜还在分析数据的你。送你 {amount} 额度，未来我们继续一起探索宇宙！"
```

### 视觉设计
- **背景**：星云紫 `linear-gradient(145deg, #0a0e27, #1a1040, #0e0a30)`
- **装饰**：
  - 全屏星云旋转效果（使用 @flodlc/nebula）
  - 流星偶尔划过
  - 行星缓缓环绕
  - 最华丽的视觉效果
- **配色**：星云紫(#A78BFA) + 星光蓝(#818CF8) + 深紫底

### 核心动画 — 星云旋转 ★ 最盛大的动画
```
效果：全屏旋转星云 + 流星 + 行星环绕
- 使用 @flodlc/nebula 组件
- 星云缓慢旋转
- 偶尔有彗星/流星划过
- 多色星云交织（蓝、紫、粉）
- 行星在轨道上缓缓移动
- 整体效果宏大、梦幻
```

### 弹窗样式
- 最华丽的边框（多层光晕）
- 诗句用 Sagan 的原话
- 额度数字带星云渐变发光
- 按钮星云渐变，最大最醒目

---

## 十八、核心组件代码

### FestivalThemeProvider — 主题匹配

```typescript
// utils/festivalThemes.ts

export interface FestivalTheme {
  id: string;
  name: string;
  title: string;
  emoji: string;
  poem: string;
  poemAuthor: string;
  message: string;
  gradient: string;
  borderColor: string;
  titleColor: string;
  textColor: string;
  amountColor: string;
  amountGlow: string;
  buttonGradient: string;
  buttonTextColor: string;
  buttonShadow: string;
  taglineColor: string;
  particleColors: string[];
  animationType: 'fireworks' | 'lanterns' | 'dragon_boat' | 'milky_way' | 
                 'moon_rise' | 'climbing' | 'new_year_fireworks' | 'gears' | 
                 'flag_fireworks' | 'hearts_rise' | 'snowfall' | 'sprout' | 
                 'sun_pulse' | 'maple_fall' | 'snow_warm' | 'code_rain' | 'nebula';
  decoration: string;
  fontFamily?: string;
  buttonText: string;
  specialEffect?: string;
}

export const FESTIVAL_THEMES: FestivalTheme[] = [
  // 春节
  {
    id: 'spring_festival',
    name: '春节',
    title: '新春大吉',
    emoji: '🎊',
    poem: '爆竹声中一岁除，春风送暖入屠苏',
    poemAuthor: '王安石《元日》',
    message: '在这辞旧迎新的时刻，愿星光为你指引前路。OmicHub 送你 {amount} 额度，开启新一年的探索之旅！',
    gradient: 'linear-gradient(145deg, #1a0505 0%, #2d0a0a 40%, #1a0508 100%)',
    borderColor: 'rgba(255,215,0,0.45)',
    titleColor: '#FFD700',
    textColor: '#ffe4c4',
    amountColor: '#FFD700',
    amountGlow: '0 0 40px rgba(255,215,0,0.6), 0 0 80px rgba(255,215,0,0.2)',
    buttonGradient: 'linear-gradient(135deg, #c41e1e 0%, #e83030 100%)',
    buttonTextColor: '#FFD700',
    buttonShadow: '0 0 20px rgba(255,50,50,0.5)',
    taglineColor: '#d4a574',
    particleColors: ['#FFD700', '#FF6B35', '#FF4444', '#FFA500'],
    animationType: 'fireworks',
    decoration: 'spring_couplets',
    buttonText: '领取新年红包 🧧',
  },
  // 元宵节
  {
    id: 'lantern_festival',
    name: '元宵节',
    title: '元宵喜乐',
    emoji: '🏮',
    poem: '众里寻他千百度，蓦然回首，那人却在，灯火阑珊处',
    poemAuthor: '辛弃疾《青玉案·元夕》',
    message: '花灯如昼，月圆人团圆。每一盏灯笼都是一颗坠落的星星，照亮我们短暂而美丽的旅程。送你 {amount} 额度！',
    gradient: 'linear-gradient(145deg, #1a1008 0%, #2d1f12 40%, #1a140a 100%)',
    borderColor: 'rgba(255,165,0,0.4)',
    titleColor: '#FFA500',
    textColor: '#ffe8d6',
    amountColor: '#FFB347',
    amountGlow: '0 0 40px rgba(255,165,0,0.5)',
    buttonGradient: 'linear-gradient(135deg, #e8780a 0%, #ff9f2e 100%)',
    buttonTextColor: '#fff',
    buttonShadow: '0 0 20px rgba(255,165,0,0.4)',
    taglineColor: '#d4a574',
    particleColors: ['#FFA500', '#FFD700', '#FF8C00', '#FFB347'],
    animationType: 'lanterns',
    decoration: 'lanterns',
    buttonText: '收下这份星光 ✨',
  },
  // 端午节
  {
    id: 'dragon_boat',
    name: '端午节',
    title: '端午安康',
    emoji: '🐲',
    poem: '路漫漫其修远兮，吾将上下而求索',
    poemAuthor: '屈原《离骚》',
    message: '粽叶飘香，龙舟竞渡。我们如原子般短暂汇聚，又终将散入星河。送你 {amount} 额度，端午安康！',
    gradient: 'linear-gradient(145deg, #081a10 0%, #122d1f 40%, #0a1a12 100%)',
    borderColor: 'rgba(0,200,150,0.4)',
    titleColor: '#4ECDC4',
    textColor: '#d4f5e9',
    amountColor: '#4ECDC4',
    amountGlow: '0 0 40px rgba(78,205,196,0.5)',
    buttonGradient: 'linear-gradient(135deg, #0d8a6a 0%, #1aad8a 100%)',
    buttonTextColor: '#fff',
    buttonShadow: '0 0 20px rgba(0,200,150,0.4)',
    taglineColor: '#6ab09a',
    particleColors: ['#4ECDC4', '#44A08D', '#96E6A1', '#00C896'],
    animationType: 'dragon_boat',
    decoration: 'bamboo',
    buttonText: '领取 🎋',
  },
  // 七夕
  {
    id: 'qixi',
    name: '七夕节',
    title: '七夕快乐',
    emoji: '💕',
    poem: '两情若是久长时，又岂在朝朝暮暮',
    poemAuthor: '秦观《鹊桥仙》',
    message: '在浩瀚宇宙中相遇，是千万分之一的奇迹。就像两颗原子在星云中偶然碰撞，绽放出独特的光芒。送你 {amount} 额度～',
    gradient: 'linear-gradient(145deg, #1a0820 0%, #2d1238 40%, #1a0a2a 100%)',
    borderColor: 'rgba(200,100,255,0.4)',
    titleColor: '#FF85C0',
    textColor: '#f0d4ff',
    amountColor: '#FF69B4',
    amountGlow: '0 0 40px rgba(255,105,180,0.5)',
    buttonGradient: 'linear-gradient(135deg, #b030b0 0%, #e050a0 100%)',
    buttonTextColor: '#fff',
    buttonShadow: '0 0 20px rgba(200,80,200,0.4)',
    taglineColor: '#c090d0',
    particleColors: ['#FF85C0', '#DA70D6', '#DDA0DD', '#FF69B4'],
    animationType: 'milky_way',
    decoration: 'stars_heart',
    buttonText: '领取星河礼物 💕',
  },
  // 中秋节 ★ 重点
  {
    id: 'mid_autumn',
    name: '中秋节',
    title: '中秋团圆',
    emoji: '🌕',
    poem: '但愿人长久，千里共婵娟',
    poemAuthor: '苏轼《水调歌头》',
    message: '这一轮明月，不过是宇宙中一颗普通的卫星，却因为仰望它的人而被赋予了意义。送你 {amount} 额度！',
    gradient: 'linear-gradient(145deg, #080a1a 0%, #0a1025 40%, #060818 100%)',
    borderColor: 'rgba(200,200,255,0.35)',
    titleColor: '#E8DCC8',
    textColor: '#d0e0f8',
    amountColor: '#E8DCC8',
    amountGlow: '0 0 40px rgba(232,220,200,0.5), 0 0 80px rgba(150,180,255,0.15)',
    buttonGradient: 'linear-gradient(135deg, #3a5a8c 0%, #5a80b0 100%)',
    buttonTextColor: '#fff',
    buttonShadow: '0 0 20px rgba(100,150,255,0.3)',
    taglineColor: '#8aa0c0',
    particleColors: ['#E8DCC8', '#C0D6F5', '#B0C4DE', '#DDA0DD'],
    animationType: 'moon_rise',
    decoration: 'moon_rabbit',
    fontFamily: "'Noto Serif SC', 'STKaiti', 'KaiTi', serif",
    buttonText: '赏月领额度 🌙',
    specialEffect: 'moon_rising', // 圆月升起特效
  },
  // 重阳节
  {
    id: 'double_ninth',
    name: '重阳节',
    title: '重阳登高',
    emoji: '🍂',
    poem: '遥知兄弟登高处，遍插茱萸少一人',
    poemAuthor: '王维《九月九日忆山东兄弟》',
    message: '登高望远，秋风送爽。我们来自星辰，终将回归星辰。送你 {amount} 额度！',
    gradient: 'linear-gradient(145deg, #1a1408 0%, #2d2512 40%, #1a160a 100%)',
    borderColor: 'rgba(218,165,32,0.35)',
    titleColor: '#DAA520',
    textColor: '#f5e6c8',
    amountColor: '#DAA520',
    amountGlow: '0 0 40px rgba(218,165,32,0.5)',
    buttonGradient: 'linear-gradient(135deg, #b8860b 0%, #daa520 100%)',
    buttonTextColor: '#1a1408',
    buttonShadow: '0 0 20px rgba(218,165,32,0.4)',
    taglineColor: '#c0a060',
    particleColors: ['#DAA520', '#CD853F', '#DEB887', '#F4A460'],
    animationType: 'climbing',
    decoration: 'chrysanthemum',
    buttonText: '登高领取',
  },
  // 元旦
  {
    id: 'new_year',
    name: '元旦',
    title: '新年快乐',
    emoji: '🎉',
    poem: '新年都未有芳华，二月初惊见草芽',
    poemAuthor: '韩愈《春雪》',
    message: '新的一年，新的宇宙。每一个新的开始，都像是一次超新星爆发。OmicHub 送你 {amount} 额度，新年快乐！',
    gradient: 'linear-gradient(145deg, #050520 0%, #101040 40%, #080830 100%)',
    borderColor: 'rgba(100,150,255,0.5)',
    titleColor: '#ffffff',
    textColor: '#c8d8ff',
    amountColor: '#FFD700',
    amountGlow: '0 0 40px rgba(255,215,0,0.6)',
    buttonGradient: 'linear-gradient(135deg, #4a30d0 0%, #7a50ff 50%, #d040d0 100%)',
    buttonTextColor: '#fff',
    buttonShadow: '0 0 25px rgba(100,80,255,0.5)',
    taglineColor: '#8890ff',
    particleColors: ['#FFD700', '#FF6B6B', '#4ECDC4', '#A78BFA', '#FF85C0'],
    animationType: 'new_year_fireworks',
    decoration: 'fireworks_banner',
    buttonText: '开启新宇宙 🚀',
  },
  // 劳动节
  {
    id: 'labor_day',
    name: '劳动节',
    title: '劳动节快乐',
    emoji: '🛠️',
    poem: '锄禾日当午，汗滴禾下土。谁知盘中餐，粒粒皆辛苦',
    poemAuthor: '李绅《悯农》',
    message: '劳动最光荣！每一行代码、每一次实验，都是在为这个世界创造价值。送你 {amount} 额度！',
    gradient: 'linear-gradient(145deg, #0a0e1a 0%, #151a28 40%, #0a1020 100%)',
    borderColor: 'rgba(255,180,50,0.35)',
    titleColor: '#FFB732',
    textColor: '#d8e4f0',
    amountColor: '#FFB732',
    amountGlow: '0 0 40px rgba(255,183,50,0.5)',
    buttonGradient: 'linear-gradient(135deg, #d08000 0%, #ffa020 100%)',
    buttonTextColor: '#fff',
    buttonShadow: '0 0 20px rgba(255,160,0,0.4)',
    taglineColor: '#a0a8b8',
    particleColors: ['#FFB732', '#FFD700', '#FFA500'],
    animationType: 'gears',
    decoration: 'tools',
    buttonText: '领取',
  },
  // 国庆节
  {
    id: 'national_day',
    name: '国庆节',
    title: '国庆快乐',
    emoji: '🇨🇳',
    poem: '山河无恙，烟火寻常，这盛世如您所愿',
    poemAuthor: '——',
    message: '盛世华诞，举国同庆。送你 {amount} 额度，祝福祖国！',
    gradient: 'linear-gradient(145deg, #1a0505 0%, #2d0a0a 40%, #1a0508 100%)',
    borderColor: 'rgba(255,50,50,0.5)',
    titleColor: '#FF4444',
    textColor: '#ffd4d4',
    amountColor: '#FFD700',
    amountGlow: '0 0 40px rgba(255,215,0,0.6)',
    buttonGradient: 'linear-gradient(135deg, #cc0000 0%, #ff2222 100%)',
    buttonTextColor: '#FFD700',
    buttonShadow: '0 0 25px rgba(255,0,0,0.5)',
    taglineColor: '#d4a060',
    particleColors: ['#FF0000', '#FFD700', '#FF6B35', '#FF4444'],
    animationType: 'flag_fireworks',
    decoration: 'national_banner',
    buttonText: '庆祝 🎆',
  },
  // 情人节
  {
    id: 'valentine',
    name: '情人节',
    title: '情人节快乐',
    emoji: '❤️',
    poem: '身无彩凤双飞翼，心有灵犀一点通',
    poemAuthor: '李商隐《无题》',
    message: '爱与被爱，都是幸福。就像两颗恒星在引力中相互环绕，永不分离。送你 {amount} 额度！',
    gradient: 'linear-gradient(145deg, #1a0810 0%, #2d1218 40%, #1a0a12 100%)',
    borderColor: 'rgba(255,80,120,0.4)',
    titleColor: '#FF6B9D',
    textColor: '#ffd0e0',
    amountColor: '#FF6B9D',
    amountGlow: '0 0 40px rgba(255,107,157,0.5)',
    buttonGradient: 'linear-gradient(135deg, #c44569 0%, #e86890 100%)',
    buttonTextColor: '#fff',
    buttonShadow: '0 0 20px rgba(255,80,120,0.4)',
    taglineColor: '#d080a0',
    particleColors: ['#FF6B9D', '#FF85C0', '#FFB6C1', '#FF69B4'],
    animationType: 'hearts_rise',
    decoration: 'hearts',
    buttonText: '领取 💝',
  },
  // 圣诞节
  {
    id: 'christmas',
    name: '圣诞节',
    title: '圣诞快乐',
    emoji: '🎄',
    poem: 'Silent night, holy night, all is calm, all is bright',
    poemAuthor: '《Silent Night》',
    message: 'Merry Christmas！愿你的代码永远无 bug，愿你的实验永远有阳性结果！送你 {amount} 额度！',
    gradient: 'linear-gradient(145deg, #080a1a 0%, #0f1528 40%, #0a1020 100%)',
    borderColor: 'rgba(100,200,150,0.4)',
    titleColor: '#87CEEB',
    textColor: '#d0e8f0',
    amountColor: '#90EE90',
    amountGlow: '0 0 40px rgba(144,238,144,0.5)',
    buttonGradient: 'linear-gradient(135deg, #1a6b3a 0%, #2a9a5a 100%)',
    buttonTextColor: '#fff',
    buttonShadow: '0 0 20px rgba(50,150,80,0.4)',
    taglineColor: '#80b0a0',
    particleColors: ['#ffffff', '#87CEEB', '#90EE90', '#C0E8D0'],
    animationType: 'snowfall',
    decoration: 'christmas_tree',
    buttonText: 'Ho Ho Ho 🎁',
  },
  // 立春
  {
    id: 'li_chun',
    name: '立春',
    title: '立春',
    emoji: '🌱',
    poem: '东风带雨逐西风，大地阳和暖气生',
    poemAuthor: '左河水',
    message: '春回大地，万物复苏。那些沉睡的种子，终将在星光的滋养下破土而出。送你 {amount} 额度！',
    gradient: 'linear-gradient(145deg, #081a0a 0%, #0a1e0c 40%, #061808 100%)',
    borderColor: 'rgba(100,255,150,0.35)',
    titleColor: '#90EE90',
    textColor: '#d0f5d8',
    amountColor: '#90EE90',
    amountGlow: '0 0 40px rgba(144,238,144,0.5)',
    buttonGradient: 'linear-gradient(135deg, #2a8a3a 0%, #4aaa5a 100%)',
    buttonTextColor: '#fff',
    buttonShadow: '0 0 20px rgba(50,180,80,0.4)',
    taglineColor: '#70c080',
    particleColors: ['#90EE90', '#98FB98', '#FFB6C1', '#F0FFF0'],
    animationType: 'sprout',
    decoration: 'sprout',
    buttonText: '迎春 🌸',
  },
  // 夏至
  {
    id: 'xia_zhi',
    name: '夏至',
    title: '夏至',
    emoji: '☀️',
    poem: '昼晷已云极，宵漏自此长',
    poemAuthor: '韦应物',
    message: '昼最长，夜最短。恒星也以最炽烈的姿态燃烧自己，照亮周遭的黑暗。送你 {amount} 额度！',
    gradient: 'linear-gradient(145deg, #1a1208 0%, #2d1f10 40%, #1a1608 100%)',
    borderColor: 'rgba(255,200,50,0.35)',
    titleColor: '#FFD700',
    textColor: '#f5e8c0',
    amountColor: '#FFD700',
    amountGlow: '0 0 40px rgba(255,215,0,0.5)',
    buttonGradient: 'linear-gradient(135deg, #e0a000 0%, #ffd030 100%)',
    buttonTextColor: '#1a1208',
    buttonShadow: '0 0 20px rgba(255,200,0,0.4)',
    taglineColor: '#d0b870',
    particleColors: ['#FFD700', '#FFA500', '#FF8C00', '#F0E68C'],
    animationType: 'sun_pulse',
    decoration: 'sun',
    buttonText: '领取',
  },
  // 秋分
  {
    id: 'qiu_fen',
    name: '秋分',
    title: '秋分',
    emoji: '🍁',
    poem: '自古逢秋悲寂寥，我言秋日胜春朝',
    poemAuthor: '刘禹锡《秋词》',
    message: '昼夜均分，秋意渐浓。每一片落叶都是大自然写给我们的一封信。送你 {amount} 额度！',
    gradient: 'linear-gradient(145deg, #1a1008 0%, #1e140a 40%, #160e06 100%)',
    borderColor: 'rgba(210,130,50,0.35)',
    titleColor: '#D2691E',
    textColor: '#f5dcc8',
    amountColor: '#DAA520',
    amountGlow: '0 0 40px rgba(218,165,32,0.5)',
    buttonGradient: 'linear-gradient(135deg, #b8620a 0%, #d08020 100%)',
    buttonTextColor: '#fff',
    buttonShadow: '0 0 20px rgba(200,120,0,0.4)',
    taglineColor: '#c09860',
    particleColors: ['#D2691E', '#CD853F', '#DEB887', '#DAA520'],
    animationType: 'maple_fall',
    decoration: 'maple',
    buttonText: '拾叶领取 🍂',
  },
  // 冬至
  {
    id: 'dong_zhi',
    name: '冬至',
    title: '冬至',
    emoji: '❄️',
    poem: '天时人事日相催，冬至阳生春又来',
    poemAuthor: '杜甫《小至》',
    message: '冬至大如年。在最长的黑夜里，愿 OmicHub 的一点点温暖能照亮你的路。记得吃饺子！送你 {amount} 额度！',
    gradient: 'linear-gradient(145deg, #0a0a1a 0%, #101028 40%, #080820 100%)',
    borderColor: 'rgba(180,200,255,0.35)',
    titleColor: '#E0E8FF',
    textColor: '#c8d4f0',
    amountColor: '#B0C4DE',
    amountGlow: '0 0 40px rgba(176,196,222,0.5)',
    buttonGradient: 'linear-gradient(135deg, #3a4a7a 0%, #5a70a0 100%)',
    buttonTextColor: '#fff',
    buttonShadow: '0 0 20px rgba(100,130,200,0.4)',
    taglineColor: '#8090b0',
    particleColors: ['#ffffff', '#C0D6F5', '#B0C4DE', '#E0E8FF'],
    animationType: 'snow_warm',
    decoration: 'snowflake',
    buttonText: '吃饺子领额度 🥟',
  },
  // 程序员节 ★ 最酷
  {
    id: 'programmers_day',
    name: '程序员节',
    title: '1024 程序员节',
    emoji: '💻',
    poem: 'Hello World!',
    poemAuthor: '每一个程序员的起点',
    message: '// 在这个特别的日子里\n// 愿你代码无bug，实验有结果\n// 愿你编译通过，论文accepted\n// OmicHub.send(amount: {amount})\n// → 领取成功 ✓',
    gradient: 'linear-gradient(145deg, #000000 0%, #0a0a0a 40%, #050505 100%)',
    borderColor: 'rgba(0,255,100,0.5)',
    titleColor: '#00FF66',
    textColor: '#00cc44',
    amountColor: '#00FF66',
    amountGlow: '0 0 40px rgba(0,255,100,0.6)',
    buttonGradient: 'linear-gradient(135deg, #000000 0%, #001a00 100%)',
    buttonTextColor: '#00FF66',
    buttonShadow: '0 0 20px rgba(0,255,100,0.4)',
    taglineColor: '#008830',
    particleColors: ['#00FF66', '#00CC44', '#00AA33'],
    animationType: 'code_rain',
    decoration: 'terminal',
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
    buttonText: 'console.log("领取")',
  },
  // 周年庆 ★ 最盛大
  {
    id: 'anniversary',
    name: 'OmicHub 周年庆',
    title: 'OmicHub 一岁啦！',
    emoji: '🎂',
    poem: 'We are made of star-stuff',
    poemAuthor: 'Carl Sagan',
    message: '从第一行代码到今天，OmicHub 已经陪伴大家走过了一整年。感谢每一个深夜还在分析数据的你。送你 {amount} 额度！',
    gradient: 'linear-gradient(145deg, #0a0e27 0%, #1a1040 40%, #0e0a30 100%)',
    borderColor: 'rgba(167,139,250,0.5)',
    titleColor: '#A78BFA',
    textColor: '#d4c8ff',
    amountColor: '#A78BFA',
    amountGlow: '0 0 50px rgba(167,139,250,0.7)',
    buttonGradient: 'linear-gradient(135deg, #5b3ec0 0%, #8b5cf6 50%, #c084fc 100%)',
    buttonTextColor: '#fff',
    buttonShadow: '0 0 30px rgba(139,92,246,0.5)',
    taglineColor: '#9b8ad0',
    particleColors: ['#A78BFA', '#C084FC', '#818CF8', '#F472B6', '#FFD700'],
    animationType: 'nebula',
    decoration: 'galaxy',
    buttonText: '一起探索宇宙 🌌',
  },
];

// 根据节日名称查找主题
export function findFestivalTheme(name: string): FestivalTheme | undefined {
  return FESTIVAL_THEMES.find(t => name.includes(t.name));
}

// 获取默认主题
export function getDefaultTheme(): FestivalTheme {
  return FESTIVAL_THEMES[0]; // 春节作为默认
}
```

---

## 十九、弹窗组件核心代码

```tsx
// components/UniqueFestivalPopup.tsx
import { motion, AnimatePresence } from 'motion/react';
import confetti from 'canvas-confetti';
import { type FestivalTheme } from '../utils/festivalThemes';

interface Props {
  theme: FestivalTheme;
  amount: number;
  onClaim: () => void;
  onClose: () => void;
}

export function UniqueFestivalPopup({ theme, amount, onClaim, onClose }: Props) {
  const isCodeRain = theme.animationType === 'code_rain';
  const isMoonRise = theme.specialEffect === 'moon_rising';

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)',
          fontFamily: theme.fontFamily || "'Inter', sans-serif",
        }}
      >
        {/* 背景动画层 */}
        <FestivalBackgroundAnimation type={theme.animationType} colors={theme.particleColors} />

        <motion.div
          initial={{ scale: 0.3, opacity: 0, y: 60 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.5, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 350, damping: 22 }}
          onClick={e => e.stopPropagation()}
          style={{
            position: 'relative', width: '92%', maxWidth: 540,
            padding: '2.5rem 2rem', borderRadius: 24,
            background: theme.gradient,
            border: `1.5px solid ${theme.borderColor}`,
            boxShadow: `0 25px 60px rgba(0,0,0,0.6), 0 0 50px ${theme.borderColor}`,
            textAlign: 'center', overflow: 'hidden',
          }}
        >
          {/* 装饰元素 */}
          <FestivalDecoration theme={theme} />

          {/* 关闭按钮 */}
          <button onClick={onClose} style={{ /* 样式 */ }}>✕</button>

          {/* 节日标签 */}
          <div style={{
            display: 'inline-block', padding: '4px 16px', marginBottom: 10,
            borderRadius: 20, background: 'rgba(255,255,255,0.08)',
            border: `1px solid ${theme.borderColor}`,
            color: theme.taglineColor, fontSize: '0.85rem',
          }}>
            {theme.emoji} {theme.name}
          </div>

          {/* ===== 诗句区域（重点！） ===== */}
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2 }}
            style={{ marginBottom: 16 }}
          >
            {/* 诗句 */}
            <h2 style={{
              margin: '0 0 8px 0', fontSize: isCodeRain ? '1.8rem' : '2rem',
              fontWeight: 800, lineHeight: 1.3,
              color: theme.titleColor,
              textShadow: `0 0 30px ${theme.borderColor}`,
              letterSpacing: '1px',
              fontFamily: theme.fontFamily,
            }}>
              {theme.poem}
            </h2>
            {/* 作者 */}
            <p style={{
              margin: 0, fontSize: '0.9rem', color: theme.taglineColor,
              fontStyle: 'italic',
            }}>
              —— {theme.poemAuthor}
            </p>
          </motion.div>

          {/* 分隔线 */}
          <div style={{
            width: 100, height: 2, margin: '14px auto',
            background: `linear-gradient(90deg, transparent, ${theme.titleColor}, transparent)`,
            opacity: 0.4,
          }} />

          {/* 文案 */}
          <motion.p
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.35 }}
            style={{
              margin: '0 0 20px 0', fontSize: '1.1rem', lineHeight: 1.7,
              color: theme.textColor, maxWidth: 420,
              marginLeft: 'auto', marginRight: 'auto',
              whiteSpace: isCodeRain ? 'pre-line' : 'normal',
              fontFamily: theme.fontFamily,
            }}
          >
            {theme.message.replace(/\{amount\}/g, String(amount))}
          </motion.p>

          {/* 额度 */}
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.45, type: 'spring' }}
            style={{
              marginBottom: 24, padding: '16px 28px', borderRadius: 16,
              background: 'rgba(255,255,255,0.05)',
              border: `1px solid ${theme.borderColor}`,
              display: 'inline-block',
            }}
          >
            <div style={{ fontSize: '0.85rem', color: theme.taglineColor, marginBottom: 4 }}>
              节日专属额度
            </div>
            <div style={{
              fontSize: '3.5rem', fontWeight: 900, lineHeight: 1,
              color: theme.amountColor, textShadow: theme.amountGlow,
            }}>
              +{amount}
            </div>
          </motion.div>

          {/* 按钮 */}
          <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.55 }}>
            <motion.button
              whileHover={{ scale: 1.06 }}
              whileTap={{ scale: 0.94 }}
              onClick={onClaim}
              style={{
                padding: '14px 48px', fontSize: '1.1rem', fontWeight: 700,
                border: 'none', borderRadius: 14, cursor: 'pointer',
                background: theme.buttonGradient, color: theme.buttonTextColor,
                boxShadow: theme.buttonShadow, letterSpacing: '0.5px',
                fontFamily: theme.fontFamily,
              }}
            >
              {theme.buttonText}
            </motion.button>
          </motion.div>

          {/* tagline */}
          <p style={{
            marginTop: 20, fontSize: '0.8rem',
            color: theme.taglineColor, fontStyle: 'italic', letterSpacing: '1px',
          }}>
            {isCodeRain ? '/* We are made of star-stuff */' : '"We are made of star-stuff" ✨'}
          </p>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
```

---

## 二十、总结

| 节日 | 核心诗句 | 核心动画 | 独特装饰 |
|------|----------|----------|----------|
| **春节** | 爆竹声中一岁除 | 烟花绽放 | 春联福字 |
| **元宵节** | 灯火阑珊处 | 灯笼飘浮 | 灯笼摇摆 |
| **端午节** | 路漫漫其修远兮 | 龙舟划水 | 粽叶水波 |
| **七夕** | 两情若是久长时 | 银河鹊桥 | 星星连线 |
| **中秋** ★ | 但愿人长久 | **圆月升起** | **月亮兔子** |
| **重阳** | 遍插茱萸少一人 | 登高枫叶 | 山峦人影 |
| **元旦** | 二月初惊见草芽 | 跨年烟花 | 倒计时 |
| **劳动节** | 粒粒皆辛苦 | 齿轮麦穗 | 工具图标 |
| **国庆节** | 山河无恙 | 红金烟花 | 五角星 |
| **情人节** | 心有灵犀一点通 | 爱心升起 | 满屏爱心 |
| **圣诞节** | Silent Night | 雪花飘落 | 圣诞树 |
| **立春** | 大地阳和暖气生 | 春芽破土 | 嫩芽生长 |
| **夏至** | 宵漏自此长 | 烈日脉动 | 太阳光线 |
| **秋分** | 我言秋日胜春朝 | 枫叶纷飞 | 多层落叶 |
| **冬至** | 冬至阳生春又来 | 雪夜暖心 | 饺子热气 |
| **程序员节** ★ | Hello World | **代码雨** | **终端风格** |
| **周年庆** ★ | We are made of star-stuff | **星云旋转** | **全屏星云** |

**17个节日，17首诗，17种动画，17种完全不同的体验。**
