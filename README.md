# RealChart2Code Benchmark

A comprehensive benchmark for evaluating LLM capabilities in generating Python visualization code from real-world chart images. The benchmark contains **1,016 chart tasks** sourced from Kaggle datasets, covering **3 task types** across **7 chart categories** and **3 difficulty levels**.

[中文版 README](README_CN.md)

## Overview

RealChart2Code evaluates how well large language models can:

1. **Task 1 - Replication**: Generate visualization code from a chart image alone (using synthetic data)
2. **Task 2 - Reproduction**: Generate visualization code from a chart image plus the original data files
3. **Task 3 - Refinement**: Improve flawed visualization code through multi-turn correction with natural language instructions

### Benchmark Statistics

| Item | Count |
|------|-------|
| Total chart samples | 5,529 |
| Task 1 & 2 tasks | 1,016 |
| Task 3 tasks | 864 |
| Chart categories | 7 (Change, Comparison, Composition, Distribution, Groups, Relationship, Spatial) |
| Difficulty levels | 3 (easy, middle, hard) |
| Visualization libraries | matplotlib, seaborn, plotly, bokeh, altair |

## Directory Structure

```
RealChart2Code/
├── README.md                         # English README
├── README_CN.md                      # Chinese README
├── to_excel_by_sub_score.py          # Per-sub-metric score aggregator
├── RealChart2Code_eval/
│   ├── evaluate_task1.py             # Task 1: Replication evaluation
│   ├── evaluate_task2.py             # Task 2: Reproduction evaluation
│   ├── evaluate_task3.py             # Task 3: Refinement evaluation
│   ├── run_task1.sh                  # Task 1 launch script
│   ├── run_task2.sh                  # Task 2 launch script
│   ├── run_task3.sh                  # Task 3 launch script
│   ├── get_results.py                # Aggregate results across models
│   ├── requirements.txt              # Python dependencies
│   ├── prompt_task1/                 # Prompt templates for Task 1
│   ├── prompt_task2/                 # Prompt templates for Task 2
│   ├── prompt_task3/                 # Prompt templates for Task 3
│   ├── data/
│   │   ├── data_task1_task2.json     # Task definitions for Task 1 & 2
│   │   ├── data_task3.json           # Task definitions for Task 3
│   │   └── selected_chart2code_benchmark_data/  # Benchmark dataset (from HuggingFace)
│   ├── results_task1/                # Pre-computed Task 1 results (from HuggingFace)
│   ├── results_task2/                # Pre-computed Task 2 results (from HuggingFace)
│   └── results_task3/                # Pre-computed Task 3 results (from HuggingFace)
```

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/Speakn0w/RealChart2Code.git
cd RealChart2Code
```

### 2. Python Environment

Requires **Python 3.10+**. We recommend creating a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
cd RealChart2Code_eval
pip install -r requirements.txt
```

Key dependencies:
- `fluxllm` (>=0.2.0) - Batch LLM request client with retry and rate limiting
- `matplotlib`, `seaborn`, `plotly`, `bokeh`, `altair` - Visualization libraries
- `pandas`, `numpy`, `Pillow` - Data and image processing

### 4. Download Benchmark Data from HuggingFace

The benchmark data and pre-computed results are hosted on HuggingFace due to their large size (~9.8GB compressed):

**Dataset**: [https://huggingface.co/datasets/zjj1233/RealChart2Code](https://huggingface.co/datasets/zjj1233/RealChart2Code)

#### Option A: Using huggingface-cli (Recommended)

```bash
pip install huggingface_hub

# Download all data to RealChart2Code_eval/
huggingface-cli download zjj1233/RealChart2Code --repo-type dataset --local-dir hf_data

# Decompress benchmark data
cat hf_data/benchmark_data.tar.gz.* | tar -xzf - -C data/

# Decompress pre-computed evaluation results
tar -xzf hf_data/results_task1.tar.gz
tar -xzf hf_data/results_task2.tar.gz
tar -xzf hf_data/results_task3.tar.gz

# Clean up (optional)
rm -rf hf_data
```

#### Option B: Manual Download

1. Visit [https://huggingface.co/datasets/zjj1233/RealChart2Code](https://huggingface.co/datasets/zjj1233/RealChart2Code)
2. Download all `benchmark_data.tar.gz.*` files and `results_task*.tar.gz` files
3. Place them in `RealChart2Code_eval/` and run the decompression commands above

After decompression, you should have:
- `data/selected_chart2code_benchmark_data/` - 5,529 chart sample directories (~12GB)
- `results_task1/`, `results_task2/`, `results_task3/` - Pre-computed evaluation results (~241MB)

### 5. API Configuration

The benchmark uses an **OpenAI-compatible API endpoint**. You need:
- **API Base URL**: Your API endpoint (e.g., `https://api.openai.com/v1`)
- **API Key**: Your API key
- **Generation Model**: The model to generate visualization code (must support vision/image input)
- **Evaluation Model**: The model to judge generated charts (must support vision/image input)

## Quick Start

### Run Evaluation

Edit the shell script variables and run:

```bash
cd RealChart2Code_eval

# Edit run_task1.sh to configure:
#   GENERATION_MODEL="your-generation-model-name"
#   EVALUATION_MODEL="your-evaluation-model-name"
#   API_BASE_URL="https://your-api-endpoint/v1"
#   API_KEY="your-api-key"

bash run_task1.sh   # Task 1: Replication
bash run_task2.sh   # Task 2: Reproduction
bash run_task3.sh   # Task 3: Refinement
```

### Run with Custom Parameters

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

### Key Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--mode` | `generate`, `evaluate`, or `both` | `both` |
| `--generation_model_name` | Model for code generation | `gpt-4o` |
| `--evaluation_model_name` | Model for evaluation (judge) | `gpt-4o` |
| `--data_dir` | Path to task data JSON | `data` |
| `--results_dir` | Output directory for results | `results` |
| `--max_data_rows` | Max data rows included in prompt | `10` |
| `--timeout` | Code execution timeout (seconds) | `120` |
| `--max_retries` | API retry limit | `5` |
| `--max_qps` | Max queries per second | `20` |
| `--diagnose` | Enable verbose diagnostics | `false` |

## Task Types

### Task 1 - Replication (Image-Only to Code)
- **Input**: Chart image + category label
- **Goal**: Generate Python code that replicates the chart using synthetic data
- **Evaluation**: Visual structure alignment + execution quality
- **Script**: `evaluate_task1.py`

### Task 2 - Reproduction (Image + Data to Code)
- **Input**: Chart image + category label + actual data files
- **Goal**: Generate Python code using the provided data files
- **Evaluation**: Visual structure alignment + execution quality + data alignment
- **Script**: `evaluate_task2.py`

### Task 3 - Refinement (Multi-Turn Correction)
- **Input**: Target chart image + flawed code + improvement instructions
- **Goal**: Fix/improve the code based on natural language correction instructions
- **Evaluation**: Visual structure alignment + execution quality
- **Script**: `evaluate_task3.py`

## Evaluation Metrics

### Visual Structure Alignment (8 metrics, each scored 0/1/2)
1. **Chart Type Consistency** - Correct chart type
2. **Spatial Layout Consistency** - Layout and subplot arrangement
3. **Text Element Consistency** - Titles, labels, legends
4. **Axis Configuration Consistency** - Axis scales, ranges, ticks
5. **Color Scheme Consistency** - Color palette matching
6. **Style and Format Consistency** - Grid, borders, themes
7. **Data Pattern Consistency** - Data trends and patterns
8. **Component Completeness** - All visual elements present

### Execution Quality (3 metrics, each scored 0/1/2)
1. **Visual Clarity** - Clean, readable output
2. **Compositional Balance** - Proper spacing and proportions
3. **Typographic Quality** - Text readability, no overlaps

### Data Alignment (Task 2 only, scored 0 or 2)
- Verifies correct data usage from provided files

**Maximum Scores**: Task 1/3 = 22 points, Task 2 = 24 points

## Aggregating Results

```bash
# Aggregate statistics across all models
python get_results.py

# Per-sub-metric summary for a specific model
python ../to_excel_by_sub_score.py <results_directory> -p "score_*.json"
```

## Pre-computed Results

Pre-computed evaluation results (downloaded from HuggingFace) cover multiple models:

- **results_task1/**: 16 models evaluated
- **results_task2/**: 13 models evaluated
- **results_task3/**: 14 models evaluated

Each model directory contains `statistics.json` with aggregated scores and individual `score_*.json` files for each task.

## Troubleshooting

1. **429 Rate Limit Errors**: Increase `--max_retries` or decrease `--max_qps`
2. **Code Execution Failures**: Ensure all visualization library versions match (matplotlib, seaborn, plotly, bokeh, altair)
3. **Font Warnings**: Install Arial font or ignore `findfont` warnings (cosmetic only)
4. **API Compatibility**: The evaluation requires an OpenAI-compatible chat API format with `messages` and `max_tokens` fields

## License

This benchmark uses publicly available datasets from Kaggle. Individual dataset licenses are recorded in each sample's `complete_metadata.json`.

## Citation
If you use RealChart2Code in your research, please cite our paper:

```bibtex
@article{zhang2026realchart2code,
  title={RealChart2Code: Advancing Chart-to-Code Generation with Real Data and Multi-Task Evaluation},
  author={Zhang, Jiajun and Li, Yuying and Li, Zhixun and Guo, Xingyu and Wu, Jingzhuo and Zheng, Leqi and Yang, Yiran and Zhang, Jianke and Li, Qingbin and Yan, Shannan and others},
  journal={arXiv preprint arXiv:2603.25804},
  year={2026}
}
```
