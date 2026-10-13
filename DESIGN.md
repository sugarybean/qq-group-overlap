# DESIGN.md — 圈层交集

## 1. Objective

这套工具要像一张安静、可核对的工作台：选择多个对等群，找出可能的兴趣交集，再用可读公式排序。质量标准是本地日常工具，高密度但不刺眼，任何操作都不应把整份名单倾倒到终端。

## 2. Product Context

- **What the product does:** 从本地 QQ 群成员快照中，找出多个已选群的重合成员，并按可配置公式排序。
- **Who it's for:** 不想翻阅几十个 QQ 群、只想用几分钟找到同好线索的大学生。
- **Adjacent brands (feel like these):** Linear 的信息层级、Notion 的安静中性、Datawrapper 的可解释数据表达。
- **Distant brand (do not feel like this):** 营销式 BI 大屏，它用大量饰品和指标卡压过真正任务。
- **Cultural register:** 实用、技术性、克制；结果是线索，不冒充社交结论。

## 3. Visual Foundations

### 3a. Color

- **Neutral scale:** `n-50 #F6F5F1`, `n-100 #ECEAE3`, `n-300 #C9C7BE`, `n-500 #74736C`, `n-700 #373936`, `n-900 #171A18`.
- **Accent(s):** `accent-primary #0C756B`, `accent-soft #DCECE8`.
- **Semantic:** `success #2F7D4A`, `warning #9A6400`, `error #B13A34`, `info #315E8A`.
- **Usage rules:** 绿青色只标识已选群、主操作和当前焦点；排名高低只用位置与数字表达，不用彩虹色。

### 3b. Typography

- **Display face:** 系统无衬线字体，700，仅用于页面标题。
- **Body face:** `Noto Sans CJK SC`, `Microsoft YaHei UI`, `sans-serif`，400/600。
- **Fallback stack:** `TkDefaultFont`, `sans-serif`.
- **Type scale:** `11 / 12 / 14 / 16 / 22 px`.
- **Weight discipline:** 400 用于表格与说明，600 用于标签和按钮，700 只用于主标题。

### 3c. Spacing & rhythm

- **Base unit:** 4 px.
- **Spacing scale:** `4, 8, 12, 16, 24, 32 px`.
- **What "generous" whitespace means in numbers:** 窗口外边距 20 px，主区域间距 16 px；数据表保持紧凑行高。

### 3d. Component seeds

- **Button:** 只有一个实心主按钮“开始评价”；刷新、清空、导出都是中性描边按钮，4 px 圆角。
- **Card / container:** 不用阴影卡片；用单像素分隔线和标题栏划分左右工作区。
- **Iconography:** 不使用装饰图标或 emoji，按钮用明确动词。
- **Data table:** 固定表头、隔行浅色、数值列右对齐；只绘制当前页，完整结果保留在内存中。

## 4. Accessibility

- **Text contrast:** 正文与背景至少 4.5:1，大文字和界面控件至少 3:1。
- **Motion:** 无自动动画；加载状态只改变文字和控件可用性。
- **Focus indicators:** 键盘焦点使用 2 px 绿青轮廓，表格选中行同时改变背景与文字色。
- **Alt text policy:** 界面无装饰图像；数据意义直接写入列名和状态文字。
- **Keyboard:** 搜索、群列表、参数、主按钮和结果表均可 Tab 访问。

## 5. Voice & Tone

- **Register:** 直接、技术性但不吹嘘。
- **Sentence rhythm:** 短句为主，错误文案同时给出下一步。
- **Words this brand uses:** 已选群、共同群、当前页、等级覆盖率、评分公式。
- **Words this brand refuses:** 智能洞察、无缝、解锁、精准人脉、知己知彼。
- **Address:** 你。

## 6. Implementation Practices

- **Token format:** Python 常量字典，统一映射到 Tkinter/ttk 样式。
- **Component library convention:** Python 标准库 Tkinter/ttk，不引入网络依赖。
- **Image treatment rules:** 主工具不使用装饰图像；登录小窗只显示本机生成的二维码，并明确说明不会写入报告。
- **Grid system:** 左侧选择器约 34%，右侧结果约 66%；小窗口优先保留结果区。
- **Motion rules:** 不做装饰动画；后台网络请求期间不阻塞界面。
- **Data boundary:** 界面分页显示；完整结果仅在用户明确点击导出时写盘；终端日志只打印计数与路径。

## 7. Anti-Patterns

- **No KPI 卡片排。** 这是查询工具，不是展示数字的仪表盘。
- **No 大圆角阴影卡片。** 边界用对齐和细线表达，避免模板感。
- **No 彩虹排名。** 分数的差异已由位置与数字承担。
- **No 默认全选。** 用户必须明确选择至少两个群，避免重新扫描整份名单。
- **No 自动全量名单输出。** 分页只渲染当前页；只有明确点击“导出全部结果”才写出完整 CSV，错误日志不包含成员记录。
- **No 不解释的分数。** 公式、等级缺失和并列规则都在界面中说明。

## 8. Decision-Making

1. **显式导出先于自动倾倒。** 计算可无上限，但完整名单只在用户明确操作后写盘。
2. **所有已选群对等。** 用最少共同群数控制候选范围，不再设置目标群。
3. **可解释先于模型复杂度。** 自定义公式只使用公开聚合变量和安全数学函数，不猜测兴趣或亲密度。
4. **常用路径先于设置完备。** 搜索群名、Ctrl/Shift 多选、改公式、开始评价必须在一屏完成。
5. **稳定先于新奇。** 界面采用标准本地控件，在无网络和无额外依赖时仍可运行。

## 9. Workflow

1. 读取本地快照，只展示群级元数据。
2. 用群名或群号搜索，选择至少两个对等群。
3. 确认每页数量、最少共同群数和评分公式。
4. 如等级覆盖不足，只从 NapCat 刷新已选群。
5. 执行本地评价，仅绘制当前页。
6. 检查等级覆盖率和公式说明，再解读排名。
7. 如需保存，明确点击“导出全部结果”生成完整 CSV。
