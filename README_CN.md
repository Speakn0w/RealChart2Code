# RealChart2Code 基准测试

一个用于评估大语言模型从真实图表图像生成 Python 可视化代码能力的综合基准。包含来自 Kaggle 数据集的 **1,016 个图表任务**，涵盖 **3 种任务类型**、**7 种图表类别**和 **3 个难度级别**。

[English README](README.md)

## 概述

RealChart2Code 评估大语言模型在以下任务上的表现：

1. **任务1 - 复制**：仅从图表图像生成可视化代码（使用合成数据）
2. **任务2 - 复现**：从图表图像加原始数据文件生成可视化代码
3. **任务3 - 修正**：通过多轮自然语言指令改进有缺陷的可视化代码

### 基准统计

| 项目 | 数量 |
|------|------|
| 图表样本总数 | 5,529 |
| 任务1和2的任务数 | 1,016 |
| 任务3的任务数 | 864 |
| 图表类别 | 7 种（变化、比较、组成、分布、分组、关系、空间） |
| 难度级别 | 3 级（简单、中等、困难） |
| 可视化库 | matplotlib、seaborn、plotly、bokeh、altair |

## 目录结构

```
RealChart2Code/
├── README.md                         # 英文 README
├── README_CN.md                      # 中文 README
├── to_excel_by_sub_score.py          # 子指标分数汇总工具
├── RealChart2Code_eval/
│   ├── evaluate_task1.py             # 任务1：复制评估
│   ├── evaluate_task2.py             # 任务2：复现评估
│   ├── evaluate_task3.py             # 任务3：修正评估
│   ├── run_task1.sh                  # 任务1启动脚本
│   ├── run_task2.sh                  # 任务2启动脚本
│   ├── run_task3.sh                  # 任务3启动脚本
│   ├── get_results.py                # 跨模型结果汇总
│   ├── requirements.txt              # Python 依赖
│   ├── prompt_task1/                 # 任务1提示词模板
│   ├── prompt_task2/                 # 任务2提示词模板
│   ├── prompt_task3/                 # 任务3提示词模板
│   ├── data/
│   │   ├── data_task1_task2.json     # 任务1和2的任务定义
│   │   ├── data_task3.json           # 任务3的任务定义
│   │   └── selected_chart2code_benchmark_data/  # 基准数据集（从 HuggingFace 下载）
│   ├── results_task1/                # 预计算的任务1结果（从 HuggingFace 下载）
│   ├── results_task2/                # 预计算的任务2结果（从 HuggingFace 下载）
│   └── results_task3/                # 预计算的任务3结果（从 HuggingFace 下载）
```

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/Speakn0w/RealChart2Code.git
cd RealChart2Code
```

### 2. Python 环境

需要 **Python 3.10+**，建议创建虚拟环境：

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
cd RealChart2Code_eval
pip install -r requirements.txt
```

关键依赖：
- `fluxllm`（>=0.2.0）- 批量 LLM 请求客户端，支持重试和限速
- `matplotlib`、`seaborn`、`plotly`、`bokeh`、`altair` - 可视化库
- `pandas`、`numpy`、`Pillow` - 数据和图像处理

### 4. 从 HuggingFace 下载基准数据

基准数据和预计算结果因体积较大（压缩后约 9.8GB）托管在 HuggingFace：

**数据集地址**：[https://huggingface.co/datasets/zjj1233/RealChart2Code](https://huggingface.co/datasets/zjj1233/RealChart2Code)

#### 方式A：使用 huggingface-cli（推荐）

```bash
pip install huggingface_hub

# 下载所有数据
huggingface-cli download zjj1233/RealChart2Code --repo-type dataset --local-dir hf_data

# 解压基准数据
cat hf_data/benchmark_data.tar.gz.* | tar -xzf - -C data/

# 解压预计算的评估结果
tar -xzf hf_data/results_task1.tar.gz
tar -xzf hf_data/results_task2.tar.gz
tar -xzf hf_data/results_task3.tar.gz

# 清理下载文件（可选）
rm -rf hf_data
```

#### 方式B：手动下载

1. 访问 [https://huggingface.co/datasets/zjj1233/RealChart2Code](https://huggingface.co/datasets/zjj1233/RealChart2Code)
2. 下载所有 `benchmark_data.tar.gz.*` 文件和 `results_task*.tar.gz` 文件
3. 放置到 `RealChart2Code_eval/` 目录，执行上述解压命令

解压后将得到：
- `data/selected_chart2code_benchmark_data/` - 5,529 个图表样本目录（约 12GB）
- `results_task1/`、`results_task2/`、`results_task3/` - 预计算的评估结果（约 241MB）

### 5. API 配置

基准测试使用 **OpenAI 兼容的 API 接口**，需要配置：
- **API Base URL**：API 接口地址（如 `https://api.openai.com/v1`）
- **API Key**：API 密钥
- **生成模型**：用于生成可视化代码的模型（需支持图像输入）
- **评估模型**：用于评判生成图表的模型（需支持图像输入）

## 快速开始

### 运行评估

编辑脚本变量后运行：

```bash
cd RealChart2Code_eval

# 编辑 run_task1.sh 配置以下变量：
#   GENERATION_MODEL="your-generation-model-name"
#   EVALUATION_MODEL="your-evaluation-model-name"
#   API_BASE_URL="https://your-api-endpoint/v1"
#   API_KEY="your-api-key"

bash run_task1.sh   # 任务1：复制
bash run_task2.sh   # 任务2：复现
bash run_task3.sh   # 任务3：修正
```

### 自定义参数运行

```bash
python evaluate_task1.py \
  --mode both \
  --generation_model_name "gpt-4o" \
  --evaluation_model_name "gpt-4o" \
  --generation_base_url "https://api.openai.com/v1" \
  --evaluation_base_url "https://api.openai.com/v1" \
  --generation_api_key "YOUR_API_KEY" \
  --evaluation_api_key "YOUR_API_KEY" \
  --data_dir "data/data_task1_task2.json" \
  --results_dir "results_task1" \
  --generation_prompt_path "prompt_task1/benchmark_generate_prompt.txt" \
  --evaluation_prompt_path "prompt_task1/eval.txt" \
  --max_data_rows 5 \
  --timeout 120 \
  --max_retries 20 \
  --max_qps 15
```

### 主要参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--mode` | `generate`（仅生成）、`evaluate`（仅评估）、`both`（全流程） | `both` |
| `--generation_model_name` | 代码生成模型 | `gpt-4o` |
| `--evaluation_model_name` | 评估模型（裁判模型） | `gpt-4o` |
| `--data_dir` | 任务数据 JSON 路径 | `data` |
| `--results_dir` | 输出目录 | `results` |
| `--max_data_rows` | 提示词中最大数据行数 | `10` |
| `--timeout` | 代码执行超时（秒） | `120` |
| `--max_retries` | API 最大重试次数 | `5` |
| `--max_qps` | 每秒最大请求数 | `20` |
| `--diagnose` | 启用详细诊断输出 | `false` |

## 任务类型

### 任务1 - 复制（仅图像 → 代码）
- **输入**：图表图像 + 类别标签
- **目标**：使用合成数据生成复制图表的 Python 代码
- **评估**：视觉结构对齐 + 执行质量
- **脚本**：`evaluate_task1.py`

### 任务2 - 复现（图像 + 数据 → 代码）
- **输入**：图表图像 + 类别 + 实际数据文件
- **目标**：使用提供的数据文件生成 Python 代码
- **评估**：视觉结构对齐 + 执行质量 + 数据对齐
- **脚本**：`evaluate_task2.py`

### 任务3 - 修正（多轮修正）
- **输入**：目标图表图像 + 有缺陷的代码 + 改进指令
- **目标**：根据自然语言修正指令修复/改进代码
- **评估**：视觉结构对齐 + 执行质量
- **脚本**：`evaluate_task3.py`

## 评估指标

### 视觉结构对齐（8 个指标，每个 0/1/2 分）
1. **图表类型一致性** - 图表类型正确
2. **空间布局一致性** - 布局和子图排列
3. **文本元素一致性** - 标题、标签、图例
4. **轴配置一致性** - 轴刻度、范围、标记
5. **颜色方案一致性** - 颜色方案匹配
6. **样式和格式一致性** - 网格、边框、主题
7. **数据模式一致性** - 数据趋势和模式
8. **组件完整性** - 所有视觉元素完整

### 执行质量（3 个指标，每个 0/1/2 分）
1. **视觉清晰度** - 输出清晰易读
2. **构图平衡** - 间距和比例合理
3. **排版质量** - 文字可读、无重叠

### 数据对齐（仅任务2，0 或 2 分）
- 验证是否正确使用了提供的数据文件

**最高分**：任务1/3 = 22 分，任务2 = 24 分

## 汇总结果

```bash
# 跨模型汇总统计
python get_results.py

# 特定模型的子指标汇总
python ../to_excel_by_sub_score.py <results_directory> -p "score_*.json"
```

## 预计算结果

预计算评估结果（从 HuggingFace 下载）涵盖多个模型：

- **results_task1/**：16 个模型的评估结果
- **results_task2/**：13 个模型的评估结果
- **results_task3/**：14 个模型的评估结果

每个模型目录包含 `statistics.json`（汇总分数）和各任务的 `score_*.json` 文件。

## 常见问题

1. **429 速率限制错误**：增加 `--max_retries` 或减少 `--max_qps`
2. **代码执行失败**：检查可视化库版本是否匹配（matplotlib、seaborn、plotly、bokeh、altair）
3. **字体警告**：安装 Arial 字体或忽略 `findfont` 警告（仅影响外观）
4. **API 兼容性**：评估需要 OpenAI 兼容的聊天 API 格式，支持 `messages` 和 `max_tokens` 字段

## 许可

本基准测试使用 Kaggle 上公开可用的数据集。各数据集的许可信息记录在每个样本的 `complete_metadata.json` 中。
