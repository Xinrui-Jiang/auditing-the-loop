# Midway demo, 3 minutes

## 录制前准备（约 10 分钟）
1. 打开三样东西：Overleaf 的 report PDF、方法图、终端。终端先 `cd` 到项目目录。
2. 终端里预先跑一次，让缓存热起来（不花钱）：
   ```bash
   uv run pytest -q
   uv run auditloop checklist DB-35
   ```
3. 浏览器打开 `docs/pages/trajectories.html`（本地文件），滚到 DB-35 那一行；再开 `docs/figures/fig_db35_before_after.png`。
4. 录屏工具：QuickTime 新建屏幕录制，选"内置麦克风"。按下面的讲稿念，总时长控制在 2 分 50 秒。

## 讲稿（对着念；括号里是动作）

（0:00，屏幕放 report 第一页）
这个项目叫 Auditing the Loop。它解决的问题是：视频生成模型拍短剧镜头时，经常漏掉剧本里的动作、说错台词、或者演过了头，而且每次生成都是随机的。我们做的是一个接在生成模型后面的验证闭环：自动检查、自动改 prompt、自动重拍，直到通过，修不好的交给人。

（0:25，切到方法图，用鼠标顺着箭头指）
流程是这样的。输入是一条短剧 prompt。Analyser 先读 prompt，写出一份 checklist：这条镜头要检查什么。checklist 分三类：剧本忠实度，比如台词是否逐字、动作有没有发生；成像完整性，比如手、脸、切镜；表演，比如情绪类别和强度。checklist 定好以后整个循环不再改。
然后生成模型出一条视频。三个验证器各负责一类，对着 checklist 给每一项打标。每个问题带三个标签：严重度、不确定状态、可修复性。结果写进一张 feedback sheet，所有轮次的 sheet 和 prompt 合起来是 trajectory。
Analyser 读整条 trajectory，决定从哪一轮出发、怎么改 prompt，再生成。没有 error 就放行；剩下的 error 都是改 prompt 修不了的，就交给人。

（1:10，切到终端）
代码在这里。数据是 30 条镜头，来自三个公开的短剧和电影剧本数据集，台词和动作原文不改。
（输入）`uv run auditloop checklist DB-35`
这是 Analyser 为一条镜头写出的 checklist，20 条左右。可以看到人物表是从剧本里读出来的：He Xi、她丈夫、还有床上的 Zhao Wanru。
（输入）`uv run auditloop run --shot DB-35`
完整循环就是这一条命令。一轮大约四分钟，这里不等它跑完，直接看已经跑完的结果。

（1:50，切到对比图）
这是 DB-35。上面是第一次生成：只有一个男人推床，镜头切来切去，台词也不对。下面是第三轮：Analyser 在 prompt 里加了这些绿色的句子，只有一个连续镜头，He Xi 和丈夫一起跑，床上的人在挣扎，说话的是 He Xi。台词还是差一个词，所以这条最后交给了人，没有放行。

（2:20，切到 trajectories 页面，滚动）
这是全部五条镜头的轨迹页面。每张卡片是一轮：prompt、视频、feedback sheet，红色是拦住输出的问题。五条里一条放行，四条在两到四轮后交人，平均 3.2 轮、每条不到两美元。

（2:40，回到 report 最后一节）
下一步是人工标注，用来衡量验证器本身的准确率，并和单次 VLM 判定的基线比较。谢谢。

## 每一步要做什么
| 时间 | 屏幕 | 动作 |
|---|---|---|
| 0:00 | report 首页 | 念第一段 |
| 0:25 | 方法图 | 鼠标沿箭头移动，念第二段 |
| 1:10 | 终端 | 敲 `uv run auditloop checklist DB-35`，等输出滚完；敲 `uv run auditloop run --shot DB-35`，出现第一行日志后不等，继续念 |
| 1:50 | 对比图 | 先指上排，再指下排的绿色句子 |
| 2:20 | trajectories.html | 横向滚动 DB-35 那一行，点开一张 feedback sheet |
| 2:40 | report 第 4 节 | 念结尾 |

run 那条命令会真的开始生成（约 $0.57）。不想花钱就只敲 checklist 那条，口头说明 run 的用法。
