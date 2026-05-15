# 产品截图说明

## 文件命名规则

将产品截图放在此目录下，按主题命名：

```
screenshot-light.png      # 明亮主题截图
screenshot-dark.png       # 暗黑主题截图
screenshot-sepia.png      # 复古主题截图
screenshot-midnight.png   # 午夜主题截图
screenshot-frost.png      # 霜白主题截图
screenshot-rose.png       # 玫瑰主题截图
```

## 截图要求

- **尺寸**：建议宽度 1200-1920px，高度 600-1000px
- **格式**：PNG（推荐）或 JPG
- **内容**：展示 CraftFlow 主界面，包含核心功能区域

## 主题切换

当用户切换主题时，截图会自动切换为对应主题的版本。

如果某个主题的截图不存在，会自动回退到 `screenshot-light.png`。

## 兜底内容

当所有截图都不存在时，会显示一个兜底的占位内容：
- 一个表示界面预览的 SVG 图标
- 文字提示："CraftFlow 产品界面预览"
- 副标题："截图即将上线"

## 示例

如果只想使用一张通用截图，可以：

1. 将截图命名为 `screenshot-light.png`
2. 复制一份命名为其他主题名称（如 `screenshot-dark.png`）

或者修改 `index.html` 中的 `data-theme-srcs` 属性，让所有主题指向同一张图片。
