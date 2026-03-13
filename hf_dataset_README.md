---
license: other
task_categories:
  - image-to-text
language:
  - en
tags:
  - chart
  - visualization
  - code-generation
  - benchmark
size_categories:
  - 1K<n<10K
---

# RealChart2Code Benchmark Data

Benchmark data and pre-computed evaluation results for **RealChart2Code** — a comprehensive benchmark for evaluating LLM capabilities in generating Python visualization code from real-world chart images.

**GitHub Repository**: [https://github.com/Speakn0w/RealChart2Code](https://github.com/Speakn0w/RealChart2Code)

## Contents

| File | Size | Description |
|------|------|-------------|
| `benchmark_data.tar.gz.aa` - `.ea` | ~9.8GB (105 files, 95MB each) | 5,529 chart sample directories (PNG images, metadata, code, scores) |
| `results_task1.tar.gz` | 9MB | Pre-computed Task 1 results (16 models) |
| `results_task2.tar.gz` | 23MB | Pre-computed Task 2 results (13 models) |
| `results_task3.tar.gz` | 8MB | Pre-computed Task 3 results (14 models) |

## Usage

```bash
# 1. Clone the GitHub repository
git clone https://github.com/Speakn0w/RealChart2Code.git
cd RealChart2Code/RealChart2Code_eval

# 2. Download data from HuggingFace
pip install huggingface_hub
huggingface-cli download zjj1233/RealChart2Code --repo-type dataset --local-dir hf_data

# 3. Decompress
cat hf_data/benchmark_data.tar.gz.* | tar -xzf - -C data/
tar -xzf hf_data/results_task1.tar.gz
tar -xzf hf_data/results_task2.tar.gz
tar -xzf hf_data/results_task3.tar.gz

# 4. Clean up
rm -rf hf_data
```

## Benchmark Data Structure

Each of the 5,529 sample directories contains:
- `complete_metadata.json` - Dataset metadata from Kaggle
- `generated_code_*.py` - Generated Python visualization code
- `generated_plot_*.png` / `refined_plot_*.png` - Chart images
- `score_*.json` - Evaluation scores
- `task_*.md` - Task descriptions

## License

Individual dataset licenses are recorded in each sample's `complete_metadata.json`. All datasets are sourced from publicly available Kaggle datasets.
