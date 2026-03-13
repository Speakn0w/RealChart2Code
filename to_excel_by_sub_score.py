import os
import json
import glob
import argparse
from collections import defaultdict

def analyze_json_files(directory_path, pattern='*.json'):
    """
    遍历指定目录下的所有.json文件，计算评估分数的平均值和执行成功率。

    Args:
        directory_path (str): 要搜索JSON文件的目标目录。
        pattern (str): JSON文件的匹配模式，默认为'*.json'，可以使用如'score_*.json'等模式。
    """
    # 确保目录存在
    if not os.path.isdir(directory_path):
        print(f"错误：目录 '{directory_path}' 不存在。")
        return

    # 使用 glob 递归查找匹配模式的 JSON 文件
    json_files = glob.glob(os.path.join(directory_path, '**', pattern), recursive=True)

    if not json_files:
        print(f"在目录 '{directory_path}' 中没有找到匹配 '{pattern}' 的文件。")
        return

    total_files = 0
    execution_success_count = 0
    skipped_files = 0  # 跳过的文件计数（没有evaluation字段的文件）
    
    # 使用 defaultdict(float) 自动初始化新键的值为 0.0
    score_sums = defaultdict(float)
    
    # 定义需要追踪的评估子项的键名
    # 这也决定了输出文件中的列顺序
    score_keys = [
        # visual_structure_alignment 下的7个子项
        "chart_type_consistency",
        "spatial_layout_consistency",
        "text_element_consistency",
        "axis_configuration_consistency",
        "color_scheme_consistency",
        "style_and_format_consistency",
        "component_completeness",
        # data_alignment (旧格式在evaluation下) 或 data_pattern_consistency (新格式在visual_structure_alignment下)
        "data_alignment",
        # execution_quality 下的3个子项
        "visual_clarity",
        "compositional_balance",
        "typographic_quality"
    ]

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            total_files += 1

            # 1. 统计 execution_success
            if data.get('execution_success', False):
                execution_success_count += 1

            # 2. 累加 evaluation 下的各项小分
            evaluation_data = data.get('evaluation')
            if evaluation_data:
                # 遍历 visual_structure_alignment 下的子项
                visual_structure = evaluation_data.get('visual_structure_alignment', {})
                if visual_structure:
                    # 前7个标准子项
                    for key in score_keys[:7]: # 前7个key
                        score_sums[key] += visual_structure.get(key, {}).get('score', 0)
                    
                    # 尝试提取 data_pattern_consistency（新格式，在visual_structure_alignment下）
                    if 'data_pattern_consistency' in visual_structure:
                        score_sums['data_alignment'] += visual_structure.get('data_pattern_consistency', {}).get('score', 0)
                    # 如果visual_structure_alignment下没有data_pattern_consistency，
                    # 尝试从evaluation直接提取data_alignment（旧格式）
                    elif 'data_alignment' in evaluation_data:
                        data_alignment = evaluation_data.get('data_alignment', {})
                        if data_alignment:
                            score_sums['data_alignment'] += data_alignment.get('score', 0)

                # 遍历 execution_quality 下的3个子项
                execution_quality = evaluation_data.get('execution_quality', {})
                if execution_quality:
                    for key in score_keys[8:11]: # 第9-11个key (索引8-10)
                         score_sums[key] += execution_quality.get(key, {}).get('score', 0)
            else:
                # 如果没有evaluation字段，记录为跳过的文件
                skipped_files += 1

        except json.JSONDecodeError:
            print(f"警告：文件 '{file_path}' 不是有效的JSON，已跳过。")
        except Exception as e:
            print(f"处理文件 '{file_path}' 时发生未知错误：{e}，已跳过。")

    # 3. 计算最终结果
    if total_files == 0:
        print("没有可处理的文件来生成报告。")
        return
        
    # 计算平均分
    average_scores = {key: score_sums[key] / total_files for key in score_keys}
    
    # 计算执行成功率（pass rate）
    execution_pass_rate = (execution_success_count / total_files) * 100

    # 4. 将结果输出到文件
    output_filename = os.path.join(directory_path, 'evaluation_summary.txt')
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            # 写入表头 (Header)
            header_items = score_keys + ["execution_success_pass_rate(%)"]
            f.write('\t'.join(header_items) + '\n')
            
            # 准备要写入的数据行
            result_values = [f"{average_scores[key]:.4f}" for key in score_keys]
            result_values.append(f"{execution_pass_rate:.2f}")
            
            # 写入数据
            f.write('\t'.join(result_values) + '\n')
        
        print(f"\n分析完成！")
        print(f"- 匹配模式：{pattern}")
        print(f"- 总文件数：{total_files}")
        if skipped_files > 0:
            print(f"- 跳过文件：{skipped_files} (无evaluation字段)")
            print(f"- 有效文件：{total_files - skipped_files}")
        print(f"- 执行成功：{execution_success_count}/{total_files} ({execution_pass_rate:.2f}%)")
        print(f"\n结果已保存到：'{output_filename}'")

    except Exception as e:
        print(f"写入输出文件时出错：{e}")


if __name__ == '__main__':
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(
        description='遍历目录下的JSON文件，分析评估分数并输出总结报告。'
    )
    parser.add_argument(
        'directory', 
        type=str, 
        help='包含JSON文件的目标目录路径。'
    )
    parser.add_argument(
        '-p', '--pattern',
        type=str,
        default='*.json',
        help='JSON文件的匹配模式（例如：score_*.json）。默认为 *.json'
    )
    
    args = parser.parse_args()
    
    # 执行分析函数
    analyze_json_files(args.directory, args.pattern)
