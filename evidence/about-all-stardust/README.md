# 关于页全部品牌英文统一样式

AboutView 内两处 “FROM STARDUST, TO DISCOVERY” / “From Stardust, to Discovery.” 均复用 `.stardust-text`，与 “We are made of star-stuff.” 及中文落款共享衬线斜体、700 字重、1.5px 字距、蓝白渐变、10px 辉光、10s shimmer 流光。保留文案和原字号层级。

顶部英文样式位于内部 span，流光不受外层 Hero 入场动画覆盖。减少动态时四处均停用动画。

浏览器使用真实 AboutView 与空配置 API 桩。browser-result.json 逐项比较 4 处计算样式（除字号外一致），确认动画会变化、手机不溢出、减少动态时四处均为 none。header-* 为首屏，desktop.png/mobile.png 为愿景区。

类型检查和 697 项前端测试通过；build.log 为生产构建日志。
