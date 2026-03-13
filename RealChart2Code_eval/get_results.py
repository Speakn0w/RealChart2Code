import os
import json
from pathlib import Path

def find_statistics_files(base_dir):
    """
    在指定目录下递归查找所有statistics.json文件
    返回: {model_name: json_data}
    """
    results = {}
    base_path = Path(base_dir)
    
    if not base_path.exists():
        print(f"警告: 目录 {base_dir} 不存在")
        return results
    
    # 遍历所有子目录
    for subdir in base_path.iterdir():
        if subdir.is_dir():
            stats_file = subdir / "statistics.json"
            if stats_file.exists():
                try:
                    with open(stats_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        results[subdir.name] = data
                except Exception as e:
                    print(f"错误: 读取 {stats_file} 失败: {e}")
    
    return results

def main():
    # 定义三个任务目录
    task_dirs = [
        "results_task1_gemini3_eval",
        "results_task2_gemini3_eval",
        "results_task3_gemini3_eval"
    ]
    
    # 存储所有模型的结果
    all_models = set()
    task_results = {}
    
    # 读取每个任务的结果
    for task_dir in task_dirs:
        print(f"正在读取 {task_dir}...")
        results = find_statistics_files(task_dir)
        task_results[task_dir] = results
        all_models.update(results.keys())
        print(f"  找到 {len(results)} 个模型结果")
    
    # 排序模型名称
    sorted_models = sorted(all_models)
    
    # 生成输出文件
    output_file = "experiment_results.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # 写入表头
        header = ["Model"]
        for task_dir in task_dirs:
            task_name = task_dir.replace("results_", "").replace("_gemini3_eval", "")
            header.extend([
                f"{task_name}_code_execution_rate",
                f"{task_name}_visual_structure_avg"
            ])
        f.write("\t".join(header) + "\n")
        
        # 写入每个模型的数据
        for model in sorted_models:
            row = [model]
            
            for task_dir in task_dirs:
                if model in task_results[task_dir]:
                    data = task_results[task_dir][model]
                    overall = data.get("overall", {})
                    code_exec_rate = overall.get("code_execution_rate", "N/A")
                    visual_struct_avg = overall.get("visual_structure_avg", "N/A")
                    code_exec_rate = 100.0*code_exec_rate
                    # 格式化数值
                    if isinstance(code_exec_rate, (int, float)):
                        code_exec_rate = f"{code_exec_rate:.4f}"
                    if isinstance(visual_struct_avg, (int, float)):
                        visual_struct_avg = f"{visual_struct_avg:.4f}"
                    
                    row.extend([code_exec_rate, visual_struct_avg])
                else:
                    row.extend(["N/A", "N/A"])
            
            f.write("\t".join(row) + "\n")
    
    print(f"\n结果已保存到 {output_file}")
    print(f"共处理 {len(sorted_models)} 个模型")
    print("\n你可以直接打开此文件，复制内容并粘贴到Excel中")

if __name__ == "__main__":
    main()
