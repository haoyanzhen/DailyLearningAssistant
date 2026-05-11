# 日常学习推送助手

Author: haoyanzhen
Date:   2026-05-11

## 目标

通过一整套 Codex 连续的日常自动化任务，完成从每日更改到日常知识点推送的全流程。

## 依托平台

github 个人静态网页托管

## 检查每日更改范围

~/projects 下的全部`git`仓库，包括：
- interview_prepare
- ResearchPaperBase_cc
- ResearchPaperBase_codex

## 每日自动化流程

以下每个流程用不同的日常自动化 Agent 任务完成，每个 Agent 扮演不同角色，完成不同的任务，并拥有独立上下文：

1. 根据每个仓库的提交记录，生成当日更改的总结日报，并分别保存为 `./prework/[YYYY-MM-DD]/work_summary_[reponame].md` 文件。
2. 根据每日所有的总结日报，提炼数学、物理、计算机、软件工程以及大语言模型相关的概念和概念关联，并保存为 `./prework/YYYY-MM-DD/concept_relevance.md` 文件。
3. 根据每日的概念和概念关联性文件，生成对每个概念生动、完整且详细的知识讲解，保存为 `./prework/YYYY-MM-DD/knowledge_explaination.md` 文件。
4. 根据每日的知识讲解文件，生成学习日报，并更新在主页的导航栏和首页默认显示上。
