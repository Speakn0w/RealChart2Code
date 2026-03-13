


import argparse
import os
import re
import json
import base64
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from fluxllm.clients import FluxOpenAIChat
from tqdm import tqdm
import traceback
import sys
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import io
from multiprocessing import Process, Queue
import logging
import seaborn
import plotly
import bokeh
import altair


matplotlib.use('Agg')
Image.MAX_IMAGE_PIXELS = None



JPEG_MAX_DIMENSION = 65000


class ExecutionTimeoutError(Exception):
    
    pass


def read_system_prompt(prompt_path: str) -> str:
    
    if not os.path.exists(prompt_path):
        if "generation" in prompt_path:
            return get_default_generation_prompt()
        else:
            raise FileNotFoundError(f"System prompt file not found: {prompt_path}")
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def get_default_generation_prompt() -> str:
    
    return """You are a professional Python data visualization developer proficient in matplotlib and seaborn libraries. Your core task is to generate high-quality, executable Python visualization code that precisely matches the provided chart images.
Work Requirements:
1. Strictly analyze all visual elements in the image, including: chart type, color scheme, axis configuration, label text, legend style, and all other visual components
2. Use matplotlib and/or seaborn to generate highly accurate reproduction code
3. Ensure the code is fully executable and includes all necessary import statements and data generation logic
4. When data in the image is unclear, create similar simulated data to reproduce the chart effect.
Output format:
- Provide only the Python code wrapped in ```python and ``` markers
- Ensure the code can run independently"""


def find_task_files(data_dir: Path, difficulty: str = None) -> List[Path]:
    
    task_files = []
    
    for dir_path in data_dir.iterdir():
        if not dir_path.is_dir():
            continue
            
        
        if not any(dir_path.glob("task_*.json")):
            continue
        
        
        difficulties = [difficulty] if difficulty else ["simple", "middle", "hard"]
        
        for diff in difficulties:
            
            standard_task = dir_path / f"task_{diff}_data.json"
            if standard_task.exists():
                task_files.append(standard_task)
            
            
            multi_task = dir_path / f"task_{diff}_mul_data.json"
            if multi_task.exists():
                task_files.append(multi_task)
    
    return task_files


def parse_task_file(task_file: Path) -> Tuple[str, str, List[str]]:
    
    with open(task_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    
    category_match = re.search(r'## Category\s*\n(.+)', content)
    category = category_match.group(1).strip() if category_match else ""
    
    
    instruction_match = re.search(r'## Instruction\s*\n(.+?)(?=\n##|\n---|$)', content, re.DOTALL)
    instruction = instruction_match.group(1).strip() if instruction_match else ""
    
    
    files_match = re.search(r'## Files\s*\n(.+?)(?=\n##|\n---|$)', content, re.DOTALL)
    files_text = files_match.group(1).strip() if files_match else ""
    
    data_files = []
    for f in files_text.split('\n'):
        f = f.strip()
        if f and (f.endswith('.csv') or f.endswith('.xlsx')):
            data_files.append(f)
    
    return category, instruction, data_files


def find_data_files(directory: Path, filenames: List[str]) -> Dict[str, Path]:
    
    found_files = {}
    
    def search_recursive(search_dir: Path, depth: int = 0):
        if depth > 5:
            return
            
        for item in search_dir.iterdir():
            if item.is_file() and item.suffix.lower() in ['.csv', '.xlsx']:
                if item.name in filenames:
                    found_files[item.name] = item
            elif item.is_dir() and not item.name.startswith('.'):
                search_recursive(item, depth + 1)
    
    search_recursive(directory)
    return found_files


def diagnose_task_file_issues(task_file: Path) -> Dict[str, any]:
    
    diagnosis = {
        'task_file': str(task_file),
        'exists': task_file.exists(),
        'readable': False,
        'has_category': False,
        'has_instruction': False,
        'has_files': False,
        'data_filenames': [],
        'data_directory': str(task_file.parent),
        'found_data_files': {},
        'missing_data_files': [],
        'errors': []
    }
    
    try:
        if not task_file.exists():
            diagnosis['errors'].append("task file does not exist")
            return diagnosis
        
        
        with open(task_file, 'r', encoding='utf-8') as f:
            content = f.read()
        diagnosis['readable'] = True
        
        
        category_match = re.search(r'## Category\s*\n(.+)', content)
        if category_match:
            diagnosis['has_category'] = True
        
        instruction_match = re.search(r'## Instruction\s*\n(.+?)(?=\n##|\n---|$)', content, re.DOTALL)
        if instruction_match and instruction_match.group(1).strip():
            diagnosis['has_instruction'] = True
        
        files_match = re.search(r'## Files\s*\n(.+?)(?=\n##|\n---|$)', content, re.DOTALL)
        if files_match:
            files_text = files_match.group(1).strip()
            if files_text:
                diagnosis['has_files'] = True
                data_files = []
                for f in files_text.split('\n'):
                    f = f.strip()
                    if f and (f.endswith('.csv') or f.endswith('.xlsx')):
                        data_files.append(f)
                diagnosis['data_filenames'] = data_files
        
        
        if diagnosis['data_filenames']:
            data_directory = task_file.parent
            found_files = find_data_files(data_directory, diagnosis['data_filenames'])
            diagnosis['found_data_files'] = {k: str(v) for k, v in found_files.items()}
            diagnosis['missing_data_files'] = list(set(diagnosis['data_filenames']) - set(found_files.keys()))
        
    except Exception as e:
        diagnosis['errors'].append(f"error reading file: {str(e)}")
    
    return diagnosis


def read_data_file(file_path: Path, max_rows: int = 10) -> str:
    
    try:
        if file_path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path)
        elif file_path.suffix.lower() == '.xlsx':
            df = pd.read_excel(file_path)
        else:
            return f"Unsupported file format: {file_path.suffix}"
        
        info = f"Dataset: {file_path.name}\n"
        info += f"Shape: {df.shape}\n"
        info += f"Columns: {list(df.columns)}\n\n"
        
        info += "Data types:\n"
        for col, dtype in df.dtypes.items():
            info += f"  {col}: {dtype}\n"
        info += "\n"
        
        info += f"First {min(max_rows, len(df))} rows:\n"
        info += df.head(max_rows).to_string(index=False)
        
        return info
        
    except Exception as e:
        return f"Error reading {file_path.name}: {str(e)}"


def create_user_prompt(category: str, instruction: str, data_info: Dict[str, str]) -> str:
    
    prompt = f"""# Task
Category: {category}
Instruction: {instruction}

# Data
"""
    
    for filename, data_content in data_info.items():
        prompt += f"## {filename}\n{data_content}\n\n"
    
    return prompt


def create_generation_request(category: str, data_info: Dict[str, str], image_path: str,
                            generation_prompt: str, model_name: str) -> Dict:
    
    # user_prompt = create_user_prompt(category, instruction, data_info)
    image_base64 = encode_image_to_base64(image_path)
    user_content = [
        {
            "type": "text",
            "text": f"# Task /n Category: {category}. Note that in this environment, the version of matplotlib is {matplotlib.__version__}, the version of seaborn is {seaborn.__version__}, the version of plotly is {plotly.__version__}, the version of bokeh is {bokeh.__version__}, the version of altair is {altair.__version__}."
        },
        {
            "type": "image_url",
            "image_url": {
                "url": image_base64
            }
        }
    ]
    
    return {
        "model": model_name,
        "messages": [
            {"role": "system", "content": generation_prompt},
            {"role": "user", "content": user_content}
        ],
        "max_tokens": 32768,
        "temperature": 0.0,
        "timeout": 1200
    }


def extract_python_code(response: str) -> str:
    
    pattern = r'```python\s*\n(.*?)\n```'
    matches = re.findall(pattern, response, re.DOTALL)
    
    if matches:
        return matches[0].strip()
    
    pattern = r'```\s*\n(.*?)\n```'
    matches = re.findall(pattern, response, re.DOTALL)
    
    if matches:
        return matches[0].strip()
    
    return ""


def preprocess_code_paths(code_content: str, data_directory: Path) -> str:
    
    
    patterns = [
        r"pd\.read_csv\s*\(\s*['\"]([^'\"]+)['\"]",
        r"pd\.read_excel\s*\(\s*['\"]([^'\"]+)['\"]",
        r"np\.loadtxt\s*\(\s*['\"]([^'\"]+)['\"]",
        r"open\s*\(\s*['\"]([^'\"]+)['\"]",
        
        r"(['\"])([^'\"]+\.(?:csv|xlsx|txt))(['\"])", 
    ]
    
    
    def replace_path_generic(match):
        start_quote = match.group(1)
        original_path = match.group(2)
        end_quote = match.group(3)

        if Path(original_path).is_absolute():
            return match.group(0)
            
        absolute_path = data_directory / original_path
        
        return f"r'{absolute_path}'"

    processed_code = code_content
    for pattern in patterns:
        
        if "csv|xlsx|txt" in pattern:
            processed_code = re.sub(pattern, replace_path_generic, processed_code)
        else:
            
            
            pass 

    
    final_code = code_content
    
    
    
    path_like_pattern = r"(['\"])([^'\"]+\.(?:csv|xlsx|txt|json))(['\"])"
    final_code = re.sub(path_like_pattern, replace_path_generic, final_code)

    return final_code


def execute_code_in_process(code_content: str, data_directory: Path, result_queue, timeout_seconds: int):
    
    try:
        import pandas as pd
        import numpy as np
        import matplotlib
        import matplotlib.pyplot as plt
        import os
        
        matplotlib.use('Agg')
        
        exec_globals = {
            '__name__': '__main__',
            'pd': pd,
            'np': np,
            'plt': plt,
            'matplotlib': matplotlib,
            'os': os,
        }
        
        try:
            import seaborn as sns
            exec_globals['sns'] = sns
        except ImportError:
            pass
        
        exec(code_content, exec_globals)
        result_queue.put(('success', 'Code execution completed'))
        
    except Exception as e:
        import traceback
        full_traceback = traceback.format_exc()
        result_queue.put(('error', f"Code execution failed: {str(e)}\n\nFull traceback:\n{full_traceback}"))


def execute_code_with_timeout(code_content: str, data_directory: Path, timeout_seconds: int = 120):
    
    result_queue = Queue()
    
    process = Process(target=execute_code_in_process, 
                     args=(code_content, data_directory, result_queue, timeout_seconds))
    
    process.start()
    process.join(timeout=timeout_seconds)
    
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        
        if process.is_alive():
            process.kill()
            process.join()
        
        raise ExecutionTimeoutError(f"Code execution timeout (exceeded {timeout_seconds} seconds)")
    
    if not result_queue.empty():
        result_type, result_message = result_queue.get()
        if result_type == 'error':
            raise Exception(result_message)
    else:
        raise Exception("Code execution terminated abnormally")


def execute_and_save_plot(code: str, task_info: Dict, results_dir: Path, timeout: int) -> Tuple[bool, str, Optional[Path]]:
    
    if not code:
        return False, "No code generated", None
    
    
    task_dir = task_info['data_directory'].name
    difficulty = task_info['difficulty']
    is_multi = task_info['is_multi']
    
    task_result_dir = results_dir / task_dir
    task_result_dir.mkdir(exist_ok=True)
    
    
    code_filename = f"generated_code_{difficulty}_mul.py" if is_multi else f"generated_code_{difficulty}.py"
    code_file = task_result_dir / code_filename
    
    with open(code_file, 'w', encoding='utf-8') as f:
        f.write(code)

    raw_response = task_info['raw_generation_response']
    raw_response_filename = f"raw_response_{difficulty}_mul.txt" if is_multi else f"raw_response_{difficulty}.txt"
    raw_response_file = task_result_dir / raw_response_filename
    with open(raw_response_file, 'w', encoding='utf-8') as f:
        f.write(raw_response)
    
    
    processed_code = preprocess_code_paths(code, task_info['data_directory'])
    
    
    plot_filename = f"generated_plot_{difficulty}_mul.png" if is_multi else f"generated_plot_{difficulty}.png"
    plot_file = task_result_dir / plot_filename
    
    if 'plt.savefig' not in processed_code and 'plt.show' not in processed_code:
        processed_code += f"\nplt.tight_layout()\nplt.savefig(r'{plot_file}', dpi=300, bbox_inches='tight')\nplt.close()"
    elif 'plt.show' in processed_code:
        processed_code = processed_code.replace('plt.show()', 
            f"plt.tight_layout()\nplt.savefig(r'{plot_file}', dpi=300, bbox_inches='tight')\nplt.close()")
    elif 'plt.savefig' in processed_code:
        pattern = re.compile(r"plt\.savefig\s*\((.*?)\)")
        replacement_string = f"plt.savefig(r'{plot_file}', dpi=300, bbox_inches='tight')\nplt.close()"
        processed_code = pattern.sub(replacement_string, processed_code)
    
    
    try:
        execute_code_with_timeout(processed_code, task_info['data_directory'], timeout)
        
        
        if plot_file.exists():
            return True, "Code executed successfully", plot_file
        else:
            return False, "Code execution completed but no plot file was generated", None
            
    except Exception as e:
        return False, f"Code execution failed: {str(e)}", None

def compress_image_if_needed(image_path: Path, max_size_bytes: int = 5 * 1024 * 1024) -> bytes:
    
    actual_target = int(max_size_bytes * 0.75)
    original_size = image_path.stat().st_size
    
    with Image.open(image_path) as img:
        if img.mode != 'RGB':
            img = img.convert('RGB')
            width, height = img.size
            if width > JPEG_MAX_DIMENSION or height > JPEG_MAX_DIMENSION:
                logging.warning(
                    f"Image '{image_path}' has dimensions ({width}x{height}) "
                    f"exceeding JPEG limit. Resizing it down."
                )
                aspect_ratio = width / height
                if width > height:
                    new_width = JPEG_MAX_DIMENSION
                    new_height = int(new_width / aspect_ratio)
                else:
                    new_height = JPEG_MAX_DIMENSION
                    new_width = int(new_height * aspect_ratio)
                
                
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logging.info(f"Resized to ({img.width}x{img.height})")
        
        
        if original_size <= actual_target:
            with open(image_path, 'rb') as f:
                return f.read()
        
        
        for quality in [85, 75, 65, 55, 45, 35, 25]:
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            compressed_data = buffer.getvalue()
            
            if len(compressed_data) <= actual_target:
                return compressed_data
        
        
        current_width, current_height = img.size
        for scale in [0.8, 0.6, 0.4, 0.2]:
            new_width = int(current_width * scale)
            new_height = int(current_height * scale)
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            resized_img.save(buffer, format='JPEG', quality=25, optimize=True)
            compressed_data = buffer.getvalue()
            
            if len(compressed_data) <= actual_target:
                return compressed_data
        
        
        buffer = io.BytesIO()
        resized_img.save(buffer, format='JPEG', quality=10, optimize=True)
        return buffer.getvalue()

def encode_image_to_base64(image_path: Path) -> str:
    
    image_data = compress_image_if_needed(image_path)
    encoded_string = base64.b64encode(image_data).decode('utf-8')
    
    if image_data.startswith(b'\xff\xd8\xff'):
        return f"data:image/jpeg;base64,{encoded_string}"
    else:
        return f"data:image/png;base64,{encoded_string}"


def create_evaluation_request(difficulty: str, category: str, instruction: str, image_path:Path,
                            image_base64: str, evaluation_prompt: str, model_name: str) -> Dict:
    
    task_prompt = f"""# Task
    Category: {category}
    """
    # Instruction: {instruction}
    image_chart = encode_image_to_base64(image_path)
    
    user_content = [
        {
            "type": "text",
            "text": f"**Task**:\n{task_prompt}\n\n**Generated Chart**: Please evaluate based on the following generated chart image."
        },
        {
            "type": "image_url",
            "image_url": {
                "url": image_base64
            }
        },
        {
            "type": "text",
            "text": f"**Provided Chart**: Please evaluate based on the following provided chart image. "
        },
        {
            "type": "image_url",
            "image_url": {
                "url": image_chart
            }
        }
    ]

    return {
        "model": model_name,
        "messages": [
            {"role": "system", "content": evaluation_prompt},
            {"role": "user", "content": user_content}
        ],
        "max_tokens": 8192,
        "temperature": 0.0,
    }


def parse_evaluation_response(response_content: str) -> Dict:
    
    
    try:
        return json.loads(response_content)
    except json.JSONDecodeError:
        pass
    
    
    json_match = re.search(r'```json\s*\n(.*?)\n```', response_content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    
    json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    
    return create_empty_evaluation()


def create_empty_evaluation() -> Dict:
    return {
        'visual_structure_alignment': {
            'chart_type_consistency': {'score': 0, 'reason': ''},
            'spatial_layout_consistency': {'score': 0, 'reason': ''},
            'text_element_consistency': {'score': 0, 'reason': ''},
            'axis_configuration_consistency': {'score': 0, 'reason': ''},
            'color_scheme_consistency': {'score': 0, 'reason': ''},
            'style_and_format_consistency': {'score': 0, 'reason': ''},
            'component_completeness': {'score': 0, 'reason': ''}
        },
        'execution_quality': {
            'visual_clarity': {'score': 0, 'reason': ''},
            'compositional_balance': {'score': 0, 'reason': ''},
            'data_integrity': {'score': 0, 'reason': ''}
        },
        'improvement_recommendations': ''
    }
    
def calculate_overall_score(evaluation: Dict) -> Dict:
    # Visual Structure Alignment scores (0-1 scale)
    visual_structure = evaluation.get('visual_structure_alignment', {})
    visual_structure_scores = {
        'chart_type_consistency': visual_structure.get('chart_type_consistency', {}).get('score', 0),
        'spatial_layout_consistency': visual_structure.get('spatial_layout_consistency', {}).get('score', 0),
        'text_element_consistency': visual_structure.get('text_element_consistency', {}).get('score', 0),
        'axis_configuration_consistency': visual_structure.get('axis_configuration_consistency', {}).get('score', 0),
        'color_scheme_consistency': visual_structure.get('color_scheme_consistency', {}).get('score', 0),
        'style_and_format_consistency': visual_structure.get('style_and_format_consistency', {}).get('score', 0),
        'component_completeness': visual_structure.get('component_completeness', {}).get('score', 0)
    }
    
    # Execution Quality scores (0-2 scale)
    execution_quality = evaluation.get('execution_quality', {})
    execution_scores = {
        'visual_clarity': execution_quality.get('visual_clarity', {}).get('score', 0),
        'compositional_balance': execution_quality.get('compositional_balance', {}).get('score', 0),
        'data_integrity': execution_quality.get('data_integrity', {}).get('score', 0)
    }
    
    # Calculate totals
    visual_structure_total = sum(visual_structure_scores.values())
    execution_total = sum(execution_scores.values())
    
    # Overall scoring
    total_possible_visual_structure = len(visual_structure_scores) * 2  # 16 points max (0-2 scale)
    total_possible_execution = len(execution_scores) * 2  # 6 points max (0-2 scale)
    
    total_score = visual_structure_total + execution_total
    total_possible = total_possible_visual_structure + total_possible_execution
    
    return {
        'visual_structure_scores': visual_structure_scores,
        'execution_quality_scores': execution_scores,
        'visual_structure_total': visual_structure_total,
        'visual_structure_max': total_possible_visual_structure,
        'execution_quality_total': execution_total,
        'execution_quality_max': total_possible_execution,
        'overall_total_score': total_score,
        'overall_max_score': total_possible,
        'visual_structure_rate': visual_structure_total / total_possible_visual_structure if total_possible_visual_structure > 0 else 0,
        'execution_quality_avg': execution_total / len(execution_scores) if execution_scores else 0,
        'overall_percentage': total_score / total_possible if total_possible > 0 else 0
    }


def save_score_result(task_info: Dict, evaluation: Dict, raw_response: str, plot_file: Path, 
                     results_dir: Path, generation_model: str, evaluation_model: str, 
                     execution_success: bool, execution_message: str) -> Path:
    
    
    task_dir = task_info['data_directory'].name
    task_result_dir = results_dir / task_dir
    task_result_dir.mkdir(exist_ok=True)
    
    
    difficulty = task_info['difficulty']
    is_multi = task_info['is_multi']
    score_filename = f"score_{difficulty}_mul.json" if is_multi else f"score_{difficulty}.json"
    
    
    overall_score = calculate_overall_score(evaluation)
    
    
    result = {
        "generation_model": generation_model,
        "evaluation_model": evaluation_model,
        "task_file": str(task_info['task_file']),
        "category": task_info['category'],
        "instruction": task_info['instruction'],
        "difficulty": difficulty,
        "is_multi": is_multi,
        "timestamp": datetime.now().isoformat(),
        
        
        "execution_success": execution_success,
        "execution_message": execution_message,
        "code_generated": bool(task_info.get('code')),
        "plot_generated": plot_file is not None,
        
        
        "evaluation": evaluation,
        "overall_score": overall_score,
        "raw_response": raw_response
    }
    
    
    if plot_file:
        result["plot_file"] = str(plot_file)
    
    score_file = task_result_dir / score_filename
    with open(score_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return score_file


def prepare_task_info(task_file: Path, max_data_rows: int) -> Optional[Dict]:
    
    try:
        
        category, instruction, data_filenames = parse_task_file(task_file)
        
        if not instruction:
            print(f"⚠️  Skip task {task_file}: missing instruction content")
            return None
        
        if not data_filenames:
            print(f"⚠️  Skip task {task_file}: missing data file list")
            return None
        
        data_directory = task_file.parent
        data_files = find_data_files(data_directory, data_filenames)
        
        if not data_files:
            print(f"⚠️  Skip task {task_file}: data files not found {data_filenames} in directory {data_directory}")
            return None
        
        
        missing_files = set(data_filenames) - set(data_files.keys())
        if missing_files:
            print(f"⚠️  Skip task {task_file}: missing data files {missing_files}")
            return None
        
        
        data_info = {}
        for filename, filepath in data_files.items():
            try:
                data_info[filename] = read_data_file(filepath, max_data_rows)
            except Exception as e:
                print(f"⚠️  Skip task {task_file}: read data file {filename} Failed: {e}")
                return None
        
        difficulty = task_file.stem.split('_')[-1] if not task_file.stem.endswith('_mul') else task_file.stem.split('_')[-2]
        print(difficulty)
        print(data_directory)
        is_multi = task_file.stem.endswith('_mul')
        
        image_path=None
        refine_folders = [f for f in data_directory.glob("refine*") if f.is_dir()]
        if refine_folders:
            for refine_folder in refine_folders:
                if refine_folder.is_dir():
                    if not is_multi:
                        png_files = list(refine_folder.glob(f"*{difficulty}.png"))
                        if png_files:
                            image_path = png_files[0]
                    else:
                        png_files = list(refine_folder.glob(f"*{difficulty}_mul.png"))
                        if png_files:
                            image_path = png_files[0]
        if not image_path:
            if not is_multi:
                png_files = list(data_directory.glob(f"*{difficulty}.png"))
                if png_files:
                    image_path = png_files[0]
            else:
                png_files = list(data_directory.glob(f"*{difficulty}_mul.png"))
                if png_files:
                    image_path = png_files[0]
        print(task_file)
        print(image_path)
        
        return {
            'task_file': task_file,
            'category': category,
            'instruction': instruction,
            'data_files': data_files,
            'data_directory': data_directory,
            'image_path': Path(image_path),
            'difficulty': difficulty,
            'is_multi': is_multi,
            'data_info': data_info
        }
        
    except Exception as e:
        print(f"❌ prepare task info {task_file} error occurred: {e}")
        import traceback
        print(f"   detailed error: {traceback.format_exc()}")
        return None


def process_generation_responses(task_infos: List[Dict], generation_responses: List, 
                               results_dir: Path, timeout: int) -> List[Dict]:
    
    processed_tasks = []
    
    for task_info, generation_response in zip(task_infos, generation_responses):
        try:
            
            if hasattr(generation_response, 'choices') and generation_response.choices:
                content = generation_response.choices[0].message.content
            elif isinstance(generation_response, dict) and 'choices' in generation_response:
                content = generation_response['choices'][0]['message']['content']
            else:
                content = ""
            
            
            code = extract_python_code(content)
            task_info['code'] = code
            task_info['raw_generation_response'] = content
            
            
            execution_success, execution_message, plot_file = execute_and_save_plot(code, task_info, results_dir, timeout)
            
            task_info['execution_success'] = execution_success
            task_info['execution_message'] = execution_message
            task_info['plot_file'] = plot_file
            
            processed_tasks.append(task_info)
            
        except Exception as e:
            print(f"❌ error processing generation response: {e}")
            task_info['execution_success'] = False
            task_info['execution_message'] = f"Response processing error: {str(e)}"
            task_info['plot_file'] = None
            processed_tasks.append(task_info)
    
    return processed_tasks


def process_evaluation_responses(processed_tasks: List[Dict], evaluation_responses: List,
                               results_dir: Path, generation_model: str, evaluation_model: str) -> List[Dict]:
    
    final_results = []
    
    
    tasks_with_plots = [task for task in processed_tasks if task.get('execution_success') and task.get('plot_file')]
    
    eval_idx = 0
    for task_info in processed_tasks:
        try:
            if task_info.get('execution_success') and task_info.get('plot_file'):
                
                evaluation_response = evaluation_responses[eval_idx]
                eval_idx += 1
                
                
                if hasattr(evaluation_response, 'choices') and evaluation_response.choices:
                    eval_content = evaluation_response.choices[0].message.content
                elif isinstance(evaluation_response, dict) and 'choices' in evaluation_response:
                    eval_content = evaluation_response['choices'][0]['message']['content']
                else:
                    eval_content = ""
                
                
                evaluation = parse_evaluation_response(eval_content)
            else:
                
                evaluation = create_empty_evaluation()
                eval_content = "Execution failed, no evaluation performed"
            
            
            score_file = save_score_result(task_info, evaluation, eval_content, task_info.get('plot_file'), 
                                         results_dir, generation_model, evaluation_model, 
                                         task_info.get('execution_success', False), task_info.get('execution_message', ''))
            
            result = {
                'task_info': task_info,
                'execution_success': task_info.get('execution_success', False),
                'execution_message': task_info.get('execution_message', ''),
                'plot_file': task_info.get('plot_file'),
                'evaluation': evaluation,
                'score_file': score_file
            }
            
            final_results.append(result)
            
        except Exception as e:
            print(f"❌ error processing evaluation response: {e}")
            
            evaluation = create_empty_evaluation()
            score_file = save_score_result(task_info, evaluation, f"Error: {str(e)}", task_info.get('plot_file'), 
                                         results_dir, generation_model, evaluation_model, 
                                         False, f"Evaluation error: {str(e)}")
            
            result = {
                'task_info': task_info,
                'execution_success': False,
                'execution_message': f"Evaluation error: {str(e)}",
                'plot_file': task_info.get('plot_file'),
                'evaluation': evaluation,
                'score_file': score_file
            }
            
            final_results.append(result)
    
    return final_results


def generate_statistics(results_dir: Path, generation_model: str, evaluation_model: str) -> Dict:
    
    
    score_files = list(results_dir.glob("**/score_*.json"))
    
    if not score_files:
        return {}
    
    all_scores = []
    stats_by_difficulty = {}
    stats_by_category = {}
    
    
    execution_stats = {
        'total_tasks': 0,
        'code_generated': 0,
        'code_executed': 0,
        'plot_generated': 0,
        'evaluation_completed': 0
    }
    
    
    for score_file in score_files:
        with open(score_file, 'r', encoding='utf-8') as f:
            score = json.load(f)
        
        difficulty = score['difficulty']
        category = score['category']
        is_multi = score['is_multi']
        
        
        execution_stats['total_tasks'] += 1
        if score.get('code_generated', False):
            execution_stats['code_generated'] += 1
        if score.get('execution_success', False):
            execution_stats['code_executed'] += 1
        if score.get('plot_generated', False):
            execution_stats['plot_generated'] += 1
        if score.get('plot_generated', False):  
            execution_stats['evaluation_completed'] += 1
        
        
        overall_score = score.get('overall_score')
        if overall_score:
            score_data = {
                'visual_structure_total': overall_score['visual_structure_total'],
                'visual_structure_max': overall_score['visual_structure_max'],
                'execution_quality_total': overall_score['execution_quality_total'],
                'execution_quality_max': overall_score['execution_quality_max'],
                'overall_total_score': overall_score['overall_total_score'],
                'overall_max_score': overall_score['overall_max_score'],
                'visual_structure_rate': overall_score['visual_structure_rate'],
                'execution_quality_avg': overall_score['execution_quality_avg'],
                'overall_percentage': overall_score['overall_percentage'],
                'difficulty': difficulty,
                'category': category,
                'is_multi': is_multi,
                'execution_success': score.get('execution_success', False),
                'plot_generated': score.get('plot_generated', False)
            }
            
            all_scores.append(score_data)
            
            if difficulty not in stats_by_difficulty:
                stats_by_difficulty[difficulty] = []
            stats_by_difficulty[difficulty].append(score_data)
            
            if category not in stats_by_category:
                stats_by_category[category] = []
            stats_by_category[category].append(score_data)


    def calc_stats(scores):
        if not scores:
            return {}
        
        visual_structure_scores = [s['visual_structure_total'] for s in scores]
        execution_scores = [s['execution_quality_total'] for s in scores]
        overall_scores = [s['overall_total_score'] for s in scores]
        
        total_count = len(scores)
        code_executed_count = sum(1 for s in scores if s.get('execution_success', False))
        plot_generated_count = sum(1 for s in scores if s.get('plot_generated', False))
        
        return {
            'count': total_count,
            'visual_structure_avg': sum(visual_structure_scores) / len(visual_structure_scores),
            'visual_structure_max': scores[0]['visual_structure_max'],
            'execution_quality_avg': sum(execution_scores) / len(execution_scores),
            'execution_quality_max': scores[0]['execution_quality_max'],
            'overall_score_avg': sum(overall_scores) / len(overall_scores),
            'overall_max_score': scores[0]['overall_max_score'],
            'visual_structure_perfect_rate': sum(1 for s in visual_structure_scores if s == scores[0]['visual_structure_max']) / len(visual_structure_scores),
            'execution_quality_perfect_rate': sum(1 for s in execution_scores if s == scores[0]['execution_quality_max']) / len(execution_scores),
            'code_execution_rate': code_executed_count / total_count,
            'plot_generation_rate': plot_generated_count / total_count,
            'overall_success_rate': plot_generated_count / total_count,
            'overall_percentage_avg': sum(s['overall_percentage'] for s in scores) / len(scores) if scores else 0
        }
    
    execution_rates = {
        'code_generation_rate': execution_stats['code_generated'] / execution_stats['total_tasks'] if execution_stats['total_tasks'] > 0 else 0,
        'code_execution_rate': execution_stats['code_executed'] / execution_stats['total_tasks'] if execution_stats['total_tasks'] > 0 else 0,
        'plot_generation_rate': execution_stats['plot_generated'] / execution_stats['total_tasks'] if execution_stats['total_tasks'] > 0 else 0,
        'evaluation_completion_rate': execution_stats['evaluation_completed'] / execution_stats['total_tasks'] if execution_stats['total_tasks'] > 0 else 0
    }
    
    statistics = {
        'overall': calc_stats(all_scores),
        'by_difficulty': {k: calc_stats(v) for k, v in stats_by_difficulty.items()},
        'by_category': {k: calc_stats(v) for k, v in stats_by_category.items()},
        'execution_stats': execution_stats,
        'execution_rates': execution_rates,
        'timestamp': datetime.now().isoformat(),
        'generation_model': generation_model,
        'evaluation_model': evaluation_model,
        'total_tasks': len(all_scores)
    }
    
    
    stats_file = results_dir / "statistics.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(statistics, f, ensure_ascii=False, indent=2)
    
    return statistics


def fix_path(path_str: str) -> str:
    """
    Fix common path issues in the JSON data:
    1. Replace 'selected_chart2code_benchmark_data' in directory names with '-data'
    2. Handle duplicated path segments
    """
    if not path_str or not isinstance(path_str, str):
        return path_str
    
    import re
    
    # Fix pattern 1: xxx-selected_chart2code_benchmark_data -> xxx-data
    # Example: yukawithdata_taylor-swift-the-eras-tour-official-setlist-selected_chart2code_benchmark_data
    pattern1 = r'([\w-]+)-selected_chart2code_benchmark_data'
    path_str = re.sub(pattern1, r'\1-data', path_str)
    
    # Fix pattern 2: xxxselected_chart2code_benchmark_data (without dash) -> xxx-data
    # Example: zyrkzys_beaverselected_chart2code_benchmark_data
    pattern2 = r'([\w]+)selected_chart2code_benchmark_data'
    path_str = re.sub(pattern2, r'\1-data', path_str)
    
    return path_str


def run_benchmark(args):
    
    data_file = Path(args.data_dir)
    results_dir = Path(args.results_dir) / args.generation_model_name
    results_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🚀 Starting PlotCraft Benchmark Evaluation")
    print(f"Generation Model: {args.generation_model_name}")
    print(f"Evaluation Model: {args.evaluation_model_name}")
    print(f"Data Directory: {data_file}")
    print(f"Results Directory: {results_dir}")
    print("=" * 60)
    
    
    generation_cache_file = results_dir / "generation_cache.jsonl"
    generation_client = FluxOpenAIChat(
        base_url=args.generation_base_url,
        api_key=args.generation_api_key,
        cache_file=str(generation_cache_file),
        max_retries=args.max_retries,
        max_qps=args.max_qps,
        max_qpm=args.max_qpm,
    )
    
    evaluation_cache_file = results_dir / "evaluation_cache.jsonl"
    evaluation_client = FluxOpenAIChat(
        base_url=args.evaluation_base_url,
        api_key=args.evaluation_api_key,
        cache_file=str(evaluation_cache_file),
        max_retries=args.max_retries,
        max_qps=args.max_qps,
        max_qpm=args.max_qpm,
    )
    
    generation_prompt = read_system_prompt(args.generation_prompt_path)
    evaluation_prompt = read_system_prompt(args.evaluation_prompt_path)
    
    print("🔄 Preparing task information...")
    print("🔄 Loading task information...")
    task_infos = []
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 直接读取JSON中的任务列表并转换路径
        for task_key, task_info in data.items():
            # 先修复路径字符串
            if 'task_file' in task_info and task_info['task_file']:
                task_info['task_file'] = fix_path(task_info['task_file'])
            if 'data_directory' in task_info and task_info['data_directory']:
                task_info['data_directory'] = fix_path(task_info['data_directory'])
            if 'image_path' in task_info and task_info['image_path']:
                task_info['image_path'] = fix_path(task_info['image_path'])
            
            # 修复data_files字典中的路径
            if 'data_files' in task_info and isinstance(task_info['data_files'], dict):
                fixed_data_files = {}
                for filename, filepath in task_info['data_files'].items():
                    if filepath:
                        fixed_data_files[filename] = fix_path(filepath)
                    else:
                        fixed_data_files[filename] = filepath
                task_info['data_files'] = fixed_data_files
            
            # 转换路径字段为Path对象
            if 'task_file' in task_info and task_info['task_file']:
                task_info['task_file'] = Path(task_info['task_file'])
            if 'data_directory' in task_info and task_info['data_directory']:
                task_info['data_directory'] = Path(task_info['data_directory'])
            if 'image_path' in task_info and task_info['image_path']:
                task_info['image_path'] = Path(task_info['image_path'])
            
            # 转换data_files字典中的路径为Path对象
            if 'data_files' in task_info and isinstance(task_info['data_files'], dict):
                new_data_files = {}
                for filename, filepath in task_info['data_files'].items():
                    if filepath:
                        new_data_files[filename] = Path(filepath)
                    else:
                        new_data_files[filename] = filepath
                task_info['data_files'] = new_data_files
            
            if args.difficulty is None or task_info['difficulty'] in args.difficulty:
                task_infos.append(task_info)
        
        print(f"✓ Loaded {len(data)} tasks from {data_file.name}")
        
    except Exception as e:
        print(f"✗ Error loading {data_file}: {e}")
    
    print(f"📤 Prepared {len(task_infos)} valid tasks")
    
    
    print("🚀 Sending batch code generation requests...")
    generation_requests = []
    for task_info in task_infos:
        request = create_generation_request(
            task_info['category'], task_info['data_info'], task_info['image_path'],
            generation_prompt, args.generation_model_name
        )
        generation_requests.append(request)
    
    print(f"📤 Sending {len(generation_requests)} generation requests...")
    generation_responses = generation_client.request(generation_requests)
    
    
    print("💻 Processing generation responses and executing code...")
    processed_tasks = process_generation_responses(task_infos, generation_responses, results_dir, args.timeout)
    
    
    tasks_with_plots = [task for task in processed_tasks if task.get('execution_success') and task.get('plot_file')]
    print(f"📊 Preparing to evaluate {len(tasks_with_plots)} tasks with successfully generated plots...")
    
    if tasks_with_plots:
        print("🚀 Sending batch evaluation requests...")
        evaluation_requests = []
        for task_info in tasks_with_plots:
            image_base64 = encode_image_to_base64(task_info['plot_file'])
            request = create_evaluation_request(
                task_info['difficulty'], task_info['category'], task_info['instruction'], task_info['image_path'],
                image_base64, evaluation_prompt, args.evaluation_model_name
            )
            evaluation_requests.append(request)
        
        print(f"📤 Sending {len(evaluation_requests)} evaluation requests...")
        evaluation_responses = evaluation_client.request(evaluation_requests)
        
        
        print("💾 Processing evaluation responses and saving results...")
        final_results = process_evaluation_responses(processed_tasks, evaluation_responses, 
                                                   results_dir, args.generation_model_name, args.evaluation_model_name)
    else:
        print("⚠️  No tasks with successfully generated plots, skipping evaluation phase")
        
        final_results = process_evaluation_responses(processed_tasks, [], 
                                                   results_dir, args.generation_model_name, args.evaluation_model_name)
    
    
    successful_tasks = sum(1 for result in final_results if result['execution_success'])
    print(f"🎉 Task processing completed! Successful: {successful_tasks}/{len(final_results)}")
    
    
    for result in final_results:
        task_info = result['task_info']
        if result['execution_success']:
            print(f"✅ Success: {task_info['data_directory'].name} - {task_info['difficulty']}")
        else:
            print(f"❌ Failed: {task_info['data_directory'].name} - {task_info['difficulty']}: {result['execution_message']}")
    
    
    print("\n📊 Generating statistics...")
    statistics = generate_statistics(results_dir, args.generation_model_name, args.evaluation_model_name)
    
    if statistics:
        execution_stats = statistics.get('execution_stats', {})
        execution_rates = statistics.get('execution_rates', {})
        
        print(f"\n📈 Overall Statistics (total {execution_stats.get('total_tasks', 0)} tasks):")
        print(f"   Code Generation Rate: {execution_rates.get('code_generation_rate', 0):.1%} ({execution_stats.get('code_generated', 0)}/{execution_stats.get('total_tasks', 0)})")
        print(f"   Code Execution Rate: {execution_rates.get('code_execution_rate', 0):.1%} ({execution_stats.get('code_executed', 0)}/{execution_stats.get('total_tasks', 0)})")
        print(f"   Plot Generation Rate: {execution_rates.get('plot_generation_rate', 0):.1%} ({execution_stats.get('plot_generated', 0)}/{execution_stats.get('total_tasks', 0)})")
        print(f"   Evaluation Completion Rate: {execution_rates.get('evaluation_completion_rate', 0):.1%} ({execution_stats.get('evaluation_completed', 0)}/{execution_stats.get('total_tasks', 0)})")
        
        if 'overall' in statistics and statistics['overall']:
            overall = statistics['overall']
            print(f"   Visual Structure Average Score: {overall['visual_structure_avg']:.2f}/{overall['visual_structure_max']}")
            print(f"   Execution Quality Average Score: {overall['execution_quality_avg']:.2f}/{overall['execution_quality_max']}")
            print(f"   Overall Average Score: {overall['overall_score_avg']:.2f}/{overall['overall_max_score']}")
            print(f"   Overall Percentage: {overall['overall_percentage_avg']:.1%}")
            print(f"   Visual Structure Perfect Rate: {overall['visual_structure_perfect_rate']:.1%}")
            print(f"   Execution Quality Perfect Rate: {overall['execution_quality_perfect_rate']:.1%}")
            
            print(f"\n📊 Statistics by Difficulty:")
            for difficulty, stats in statistics['by_difficulty'].items():
                print(f"   {difficulty}: {stats['count']} tasks")
                print(f"     Code Execution Rate: {stats.get('code_execution_rate', 0):.1%}")
                print(f"     Plot Generation Rate: {stats.get('plot_generation_rate', 0):.1%}")
                print(f"     Visual Structure Average Score: {stats['visual_structure_avg']:.2f}/{stats['visual_structure_max']}")
                print(f"     Execution Quality Average Score: {stats['execution_quality_avg']:.2f}/{stats['execution_quality_max']}")
                print(f"     Overall Average Score: {stats['overall_score_avg']:.2f}/{stats['overall_max_score']}")
                print(f"     Overall Percentage: {stats['overall_percentage_avg']:.1%}")
        else:
            print("   Note: No completed evaluation tasks, unable to calculate score statistics")
    
    print(f"\n✅ Benchmark evaluation completed!")
    print(f"📁 Results saved in: {results_dir}")


def main():
    parser = argparse.ArgumentParser(description="PlotCraft Benchmark Evaluation - Simplified")
    parser.add_argument("--mode", type=str, choices=["generate", "evaluate", "both"], default="both",
                        help="Run mode: generate (generation only), evaluate (evaluation only), both (full pipeline)")
    parser.add_argument("--data_dir", type=str, 
                        default="data",
                        help="Data directory path")
    parser.add_argument("--results_dir", type=str, default="results",
                        help="Results root directory")
    parser.add_argument("--difficulty", type=str, choices=["simple", "middle", "hard"], default=None,
                        help="Specify difficulty level (default: all)")
    
    
    parser.add_argument("--generation_model_name", type=str, default="gpt-4o",
                        help="Code generation model name")
    parser.add_argument("--generation_base_url", type=str, default="https://api.openai.com/v1",
                        help="Code generation API base URL")
    parser.add_argument("--generation_api_key", type=str, default=None,
                        help="Code generation API key (use OPENAI_API_KEY env var if not provided)")
    
    
    parser.add_argument("--evaluation_model_name", type=str, default="gpt-4o",
                        help="Evaluation model name")
    parser.add_argument("--evaluation_base_url", type=str, default="https://api.openai.com/v1",
                        help="Evaluation API base URL")
    parser.add_argument("--evaluation_api_key", type=str, default=None,
                        help="Evaluation API key (use OPENAI_API_KEY env var if not provided)")
    
    
    parser.add_argument("--max_retries", type=int, default=5,
                        help="Maximum retry count")
    parser.add_argument("--max_qpm", type=int, default=1000,
                        help="Maximum requests per minute")
    parser.add_argument("--max_qps", type=int, default=20,
                        help="Maximum requests per second")
    
    
    parser.add_argument("--generation_prompt_path", type=str, 
                        default="prompts/generate_code_prompt.txt",
                        help="Code generation system prompt file path")
    parser.add_argument("--evaluation_prompt_path", type=str, 
                        default="prompts/eval.txt",
                        help="Evaluation system prompt file path")
    
    
    parser.add_argument("--max_data_rows", type=int, default=10,
                        help="Maximum rows for data preview")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Code execution timeout (seconds)")
    parser.add_argument("--diagnose", action="store_true",
                        help="Enable diagnostic mode to output detailed information about skipped tasks")
    
    args = parser.parse_args()
    
    
    if args.generation_api_key is None:
        args.generation_api_key = os.getenv("OPENAI_API_KEY")
        if not args.generation_api_key:
            raise ValueError("Please provide code generation API key or set OPENAI_API_KEY environment variable")
    
    if args.evaluation_api_key is None:
        args.evaluation_api_key = os.getenv("OPENAI_API_KEY")
        if not args.evaluation_api_key:
            raise ValueError("Please provide evaluation API key or set OPENAI_API_KEY environment variable")
    
    
    run_benchmark(args)


if __name__ == "__main__":
    main()
