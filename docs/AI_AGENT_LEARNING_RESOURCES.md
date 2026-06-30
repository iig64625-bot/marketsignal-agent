# 🧠 AI Agent 高质量学习资源大全

> 整理时间：2026-06-24 | 语言：中文+英文 | 标准：通俗易懂+实战上手

---

## 📌 推荐学习顺序

```
第1周：建立全景认知
  → Andrew Ng 4门Agent短课（免费，共4-6h）
  → 3Blue1Brown Transformer可视化（2h）

第2周：深入原理
  → Karpathy "Let's build GPT"（2h）
  → 李沐 ReAct/CoT 论文精读（2h）

第3周：框架实战
  → LangChain Academy 官方教程（6h+）
  → 用你的 SignalPulse 项目练手

第4周：进阶+项目
  → Multi-Agent 教程
  → 用你的 PawPal 项目练手（AI健康咨询=Multi-Agent）
```

---

## 一、LLM 基础原理

### 🎬 视频课程

| 资源 | 平台 | 语言 | 时长 | 链接 |
|---|---|---|---|---|
| **3Blue1Brown — Transformer可视化** | B站/YouTube | 中/英 | ~2h | 搜"3B1B Transformer" |
| **Andrej Karpathy — Let's build GPT** | YouTube | 英文 | 2h | youtube.com/@AndrejKarpathy |
| **Andrej Karpathy — State of GPT** | B站(有字幕) | 英/中字 | 45min | 搜"Karpathy State of GPT" |
| **李沐 — 论文逐段精读系列** | B站 | 中文 | 40-60min/篇 | 搜"李沐 Attention Is All You Need" |
| **MIT 6.S191 — Intro to Deep Learning** | MIT OpenCourseWare | 英文 | 全学期 | ocw.mit.edu |

### 📖 图文必读

| 资源 | 链接 | 说明 |
|---|---|---|
| **Illustrated Transformer** | jalammar.github.io/illustrated-transformer | 5分钟图解，全网最通俗 |
| **LLM Visualization** | bbycroft.net/llm | 3D交互式LLM内部结构 |
| **The Illustrated GPT-2** | jalammar.github.io/illustrated-gpt2 | GPT架构可视化 |

---

## 二、Chain of Thought (CoT)

### 🎬 视频课程

| 资源 | 平台 | 时长 | 链接 |
|---|---|---|---|
| **李沐 — CoT论文精读** | B站 | 30min | 搜"李沐 Chain-of-Thought" |
| **Andrew Ng — CoT in Prompt Engineering** | DeepLearning.AI | 15min | deeplearning.ai/short-courses |
| **Prompt Engineering Guide** | YouTube | 20min | 搜"CoT prompt engineering" |

### 🔑 2分钟掌握CoT

```
普通提问：  "125 × 37 = ?"             → LLM容易算错
CoT提问：  "请一步步计算 125 × 37"     → LLM拆步骤算对

Zero-shot CoT：加 "Let's think step by step"（万能提示词）
Few-shot CoT：给几个带推理过程的示例
Auto-CoT：   让LLM自己生成推理链
```

### 📄 原论文

| 论文 | 链接 |
|---|---|
| Chain-of-Thought Prompting (Wei et al., 2022) | arxiv.org/abs/2201.11903 |
| Tree-of-Thought (Yao et al., 2023) | arxiv.org/abs/2305.10601 |

---

## 三、ReAct 范式

### 🎬 视频课程

| 资源 | 平台 | 时长 | 链接 |
|---|---|---|---|
| **李沐 — ReAct论文精读** | B站 | 35min | 搜"李沐 ReAct" |
| **LangChain — ReAct Agent实战** | YouTube | 40min | 搜"LangChain ReAct agent" |
| **Yao Fu — ReAct解读** | Blog | 10min阅读 | 搜"Yao Fu ReAct" |

### 🔑 ReAct核心逻辑

```
用户问题 → [思考Thought] 我需要搜索XXX
         → [行动Action] 调用搜索工具
         → [观察Observation] 搜索结果...
         → [思考Thought] 还需要查YYY
         → [行动Action] 调用另一个工具
         → [观察Observation] 结果...
         → [思考Thought] 信息够了
         → [回答Answer] 最终答案

关键：推理(Reasoning)和行动(Acting)交替进行，
     而不是纯推理(CoT)或纯行动(盲目调工具)
```

### 📄 原论文

| 论文 | 链接 |
|---|---|
| ReAct: Synergizing Reasoning and Acting (Yao et al., 2022) | arxiv.org/abs/2210.03629 |
| GitHub 实现 | github.com/ysymyth/ReAct |
