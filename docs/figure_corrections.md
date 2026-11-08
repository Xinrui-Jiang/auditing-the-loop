# 方法图需要修改的地方（以手绘图为底，最小改动）

1. 框 "Analyser"：加第二行小字 "writes the checklist once; after each round reads the trajectory and revises the prompt"。
2. 框 "checklist"：改为 "Checklist: items to verify for this shot, fixed for the whole loop"。原文字 "Identify the issues to be evaluated in this instance" 可保留为副标题。
3. 框 "video generation model"：下面加一行小字 "Seedance 2.0"。
4. 框 "generated video"：改为 "Take k"。
5. "Group of evaluation expert"：改为 "Verifier panel"，三个小人下面分别标 "A script fidelity", "B rendering integrity", "C dramatic performance"。再在旁边加一个小方框 "tools: ASR, ffprobe, cut detection"，也指向同一个输出。
6. 框 "Feedback & todo"：改为两层。上层 "Feedback sheet k: per item severity, uncertainty, fixability"。下层 "Trajectory: prompts and sheets of all rounds"，画成一叠纸。原文字 "memory maintained over each loop" 可去掉。
7. 顶部回环箭头的文字：改为 "Analyser reads the trajectory, chooses the round to branch from, revises the prompt"。
8. 在 feedback sheet 右边加一个菱形 "Stop rule"，三个出口：向右 "no error: release the take"；向下 "every remaining error is backend-limited: hand off to a human"；向上接回环箭头 "otherwise: next round"。
9. 加一条从 checklist 指向 Analyser 回环的细线，或在 Analyser 框里注明它也读 checklist。
10. 事实性错误：图里没有体现 "只有说话人一个人" 这类默认规则，这是对的，不要加；不要出现 "contract"、"ledger"、"planner" 这些词；不要写 "consensus" 或 "vote"，现在每类只有一个验证器。
11. 全图统一用 "round k" 表示轮次；K = 8 为轮数上限，可写在 Stop rule 旁边。
