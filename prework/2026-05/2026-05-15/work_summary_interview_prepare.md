# 2026-05-15 interview_prepare 工作总结

本总结基于 `interview_prepare` 仓库在 2026-05-14 00:00 至 2026-05-15 00:00（Asia/Shanghai）的 Git 提交记录生成。

## 提交概览

| 项目 | 内容 |
| --- | --- |
| 仓库 | `interview_prepare` |
| 统计窗口 | 2026-05-14 00:00 至 2026-05-15 00:00 |
| 提交数量 | 1 次 |
| 涉及文件 | `outputs/create_llm_ppt.py`、`outputs/llm-architecture.pptx`、`outputs/manual-transformer-ppt/attention-is-all-you-need-paper-intro-cn.pptx` |
| 核心主题 | LLM 架构讲解 PPT、Transformer 前向流程、注意力机制教学材料 |

- `a4d5c67`（20:01）：新增 LLM 架构 PPT 生成脚本与 PPT 文件，并加入一份 Attention Is All You Need 论文介绍 PPT。

## 关键文件变更

### `outputs/create_llm_ppt.py`

新增约 929 行 Python 脚本，使用 `python-pptx` 生成一套 15 页的大语言模型基础架构讲解幻灯片。脚本先定义深色背景、卡片、强调色、标题和页码等可复用绘图函数，再逐页构建内容。

已能从 diff 确认的主题包括：

- LLM 架构全景图：从输入文本、Tokenization、Embedding、Positional Encoding、Transformer Block 到 LM Head 和下一个 Token 概率分布。
- Tokenization：解释 BPE 算法、词表大小、特殊 token 和多语言编码效率。
- Token Embedding：解释嵌入矩阵、查表机制、语义向量空间和余弦相似度。
- Positional Encoding：介绍正弦位置编码与 RoPE 等位置表示思想。

脚本中还包含统一的视觉组件函数，说明这份材料不是手工拼接，而是以代码方式生成可复用、可迭代的教学 PPT。

### `outputs/llm-architecture.pptx`

新增由脚本生成的 LLM 架构演示文稿，面向“从 Token 输入到文本生成”的完整前向推理流程。该文件是二进制 PPT 产物，具体视觉细节无法从 Git 文本 diff 完整确认，但可从生成脚本确认其主题和结构。

### `outputs/manual-transformer-ppt/attention-is-all-you-need-paper-intro-cn.pptx`

新增一份中文的 Attention Is All You Need 论文介绍 PPT。由于该文件为二进制产物，具体每页内容未能从 Git 文本记录中直接确认；但从文件名可确认其用于 Transformer 经典论文介绍。

## 主要工作主题

### 将 LLM 架构拆成可教学的前向流程

本次提交把 LLM 从抽象概念拆成输入文本、分词、嵌入、位置编码、Transformer Block、LM Head、概率输出等连续步骤。这种组织方式适合面试准备和课程讲解，因为它按数据流解释模型，而不是只罗列名词。

### 用代码生成演示材料

`create_llm_ppt.py` 使用统一函数生成文本框、卡片、强调条、页码和配色。这为后续批量修改主题、替换内容或扩展页数提供了更稳定的维护方式，也体现了“教学材料工程化”的思路。

### 注意力机制与 Transformer 学习线索增强

新增 Attention Is All You Need 论文介绍 PPT，和 LLM 架构 PPT 形成互补：一个讲现代 LLM 的整体推理流程，一个回到 Transformer 注意力机制的经典来源。

## 可能涉及的知识点线索

- BPE 分词与 token 词表
- Token embedding 与语义向量空间
- 位置编码、Sinusoidal PE、RoPE
- Transformer Block、Self-Attention、FFN
- 自回归语言模型和下一个 token 概率
- `python-pptx` 自动生成演示材料
- 教学内容的可视化组织与工程化生成

## 对后续概念提炼任务有帮助的备注

这次提交非常适合提炼偏计算机和大语言模型方向的概念，尤其是“Tokenization”“Embedding”“位置编码”“Transformer 前向推理流程”。它也可以和 `AInote` 的“渐进披露”关联：LLM 架构 PPT 本身就是把复杂模型按层级逐步展开的教学实践。

数据来源：`git log --since="2026-05-14 00:00:00 +0800" --until="2026-05-15 00:00:00 +0800"`，以及提交 `a4d5c67` 对 `outputs/create_llm_ppt.py`、`outputs/llm-architecture.pptx`、`outputs/manual-transformer-ppt/attention-is-all-you-need-paper-intro-cn.pptx` 的新增记录。
