#!/bin/bash

# RealChart2Code Benchmark - Run Task1
# Configure the variables below before running

GENERATION_MODEL="your-generation-model-name"
EVALUATION_MODEL="your-evaluation-model-name"
API_BASE_URL="https://your-api-endpoint/v1"
API_KEY="your-api-key"

python -u evaluate_task1.py \
  --mode both \
  --generation_model_name "$GENERATION_MODEL" \
  --evaluation_model_name "$EVALUATION_MODEL" \
  --generation_base_url "$API_BASE_URL" \
  --evaluation_base_url "$API_BASE_URL" \
  --generation_api_key "$API_KEY" \
  --evaluation_api_key "$API_KEY" \
  --data_dir "data/data_task1_task2.json" \
  --results_dir "results_task1" \
  --generation_prompt_path "prompt_task1/benchmark_generate_prompt.txt" \
  --evaluation_prompt_path "prompt_task1/eval.txt" \
  --max_data_rows 5 \
  --timeout 120 \
  --max_retries 20 \
  --max_qps 15
