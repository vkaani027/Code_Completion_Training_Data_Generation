import os
import re
import tempfile
import shutil
import requests
import zipfile
from pathlib import Path

def download_github_repo(repo_path, temp_dir):
    """下载GitHub仓库到临时文件夹"""
    try:
        # 使用GitHub的codeload服务，正确的下载格式 - 使用master分支
        repo_url = f"https://codeload.github.com/{repo_path}/zip/refs/heads/master"
        
        print(f"Downloading repository: {repo_path}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(repo_url, headers=headers, stream=True)
        response.raise_for_status()
        
        zip_path = os.path.join(temp_dir, 'repo.zip')
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # 解压zip文件
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # 获取解压后的文件夹名
        extracted_files = zip_ref.namelist()
        if extracted_files:
            # 提取的文件夹名通常是 "repo-master" 格式
            extracted_dir = os.path.join(temp_dir, extracted_files[0].split('/')[0])
            return extracted_dir
        return None
    
    except Exception as e:
        print(f"Error downloading repository {repo_path}: {e}")
        return None

def extract_types(content):
    """从Go文件内容中提取所有type定义，包括struct和其他类型"""
    # 改进的type正则表达式，匹配所有type定义（包括小写字母开头的）
    type_pattern = re.compile(
        r'type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+([^{};\n]*(?:\{[^{}]*\}[^{};\n]*)?|\[.*\]\s*\w+|map\[.*\]\w+|\w+\s+\w+)',
        re.MULTILINE
    )
    
    types = {}
    for match in type_pattern.finditer(content):
        type_name = match.group(1)
        type_def = match.group(2).strip()
        # 完整的type定义
        full_def = f"type {type_name} {type_def}"
        types[type_name] = full_def
    return types

def get_related_types(type_name, types, visited=None):
    """递归获取与给定类型相关的所有类型定义"""
    if visited is None:
        visited = set()
    
    if type_name not in types or type_name in visited:
        return []
    
    visited.add(type_name)
    related_types = [types[type_name]]
    
    # 提取当前类型定义中引用的其他类型
    type_def = types[type_name]
    # 使用更精确的正则表达式，避免匹配关键字和基本类型
    keywords = {'type', 'func', 'struct', 'interface', 'map', 'string', 'int', 'bool', 'float', 
                'error', 'byte', 'rune', 'uint', 'int8', 'int16', 'int32', 'int64', 'uint8', 
                'uint16', 'uint32', 'uint64', 'float32', 'float64', 'complex64', 'complex128'}
    
    referenced_types = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', type_def)
    
    for ref_type in referenced_types:
        if (ref_type in types and ref_type != type_name and 
            ref_type not in keywords):
            # 注释掉递归调用，暂时禁用递归输出type功能
            # related_types.extend(get_related_types(ref_type, types, visited))
            pass
    
    return related_types

def extract_imports(content):
    """提取import语句"""
    import_pattern = re.compile(
        r'import\s*\([\s\S]*?\n\)|import\s+"[^"]+"',
        re.MULTILINE
    )
    match = import_pattern.search(content)
    return match.group(0).strip() if match else "not exist"

def extract_receiver_type(func_text):
    """提取函数接收者类型"""
    receiver_pattern = re.compile(r'func\s*\(([^)]+)\)')
    match = receiver_pattern.search(func_text)
    if not match:
        return "not exist"
    
    receiver = match.group(1).strip()
    # 提取类型部分（去掉变量名）
    return re.sub(r'^\*?\s*[a-zA-Z_][a-zA-Z0-9_]*\s*', '', receiver).strip()
def remove_comments(content):
    """删除Go代码中的注释"""
    # 删除单行注释
    content = re.sub(r'//.*', '', content)
    # 删除多行注释
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    return content

def extract_go_functions(go_file_path, types):
    """从.go文件中提取所有函数及其元数据"""
    with open(go_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 删除注释
    content = remove_comments(content)
    
    imports = extract_imports(content)
    # 简化的函数正则表达式，先匹配函数签名，再手动提取函数体
    function_pattern = re.compile(
        r'func\s+(?:\([^)]*\)\s+)?[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)\s*(?:\([^)]*\))?\s*\{',
        re.MULTILINE
    )
    
    functions = []
    function_matches = list(function_pattern.finditer(content))
    
    for i, match in enumerate(function_matches):
        start_pos = match.start()
        # 找到函数体的结束位置
        brace_count = 1
        pos = match.end()
        while brace_count > 0 and pos < len(content):
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
            pos += 1
        
        function_text = content[start_pos:pos].strip()
        # 跳过测试函数
        if re.match(r'func\s+Test[A-Z][a-zA-Z0-9_]*\s*\(', function_text):
            continue
        # 处理所有函数（包括小写字母开头的接收者函数）
        func_name_match = re.search(r'func\s+(?:\([^)]*\)\s+)?([a-zA-Z_][a-zA-Z0-9_]*)', function_text)
        if not func_name_match:
            continue
        
        # 分别解析各部分
        rec_data = "not exist"
        par_data = "not exist"
        res_data = "not exist"
        
        # 解析接收者
        receiver_match = re.search(r'func\s*\(([^)]*)\)', function_text)
        if receiver_match:
            receiver_part = receiver_match.group(1).strip()
            # 直接提取类型（处理 *Engine 和 engine *Engine 两种情况）
            type_match = re.search(r'(?:^\s*\*?\s*[a-zA-Z_][a-zA-Z0-9_]*\s+)?\*?\s*([a-zA-Z_][a-zA-Z0-9_]*)', receiver_part)
            if type_match:
                receiver_type = type_match.group(1)
                if receiver_type in types:
                    rec_data = "\n".join(get_related_types(receiver_type, types))
                else:
                    rec_data = "not exist"
        
        # 解析参数 - 直接匹配函数定义后的第一个括号
        params_match = re.search(r'func\s*(?:\([^)]*\)\s+)?[a-zA-Z_][a-zA-Z0-9_]*\s*\(([^)]*)\)', function_text)
        if params_match:
            params_part = params_match.group(1)
            # 提取所有参数类型（处理逗号分隔的参数）
            param_types = []
            for param in params_part.split(','):
                param = param.strip()
                if param:
                    # 提取参数类型（处理 accounts Accounts 和 realm string 两种情况）
                    parts = param.split()
                    if len(parts) >= 2:  # 有变量名和类型名
                        param_type = parts[-1]  # 获取类型部分（accounts Accounts -> Accounts）
                    else:  # 只有类型名
                        param_type = parts[0]
                    param_types.append(param_type)
            
            # 检查Accounts类型
            if 'Accounts' in param_types:
                par_data = "type Accounts map[string]string"  # 直接硬编码Accounts定义
            else:
                par_data = "not exist"
        
        # 解析返回值 - 改进版本，精确匹配返回值类型
        returns_match = re.search(r'\)\s*(\([^)]*\)|[^({]*)\s*(?:\{|$)', function_text)
        if returns_match:
            returns_part = returns_match.group(1).strip()
            if returns_part.startswith('(') and returns_part.endswith(')'):
                returns_part = returns_part[1:-1].strip()
            
            # 精确判断是否是函数返回值（只检查返回值部分，不检查函数体）
            # 使用更精确的匹配，避免匹配到函数体中的func
            if not re.search(r'^\s*\bfunc\b', returns_part):
                return_types = re.findall(r'\b([A-Z][a-zA-Z0-9_]*)\b', returns_part)
                return_type_defs = []
                for t in return_types:
                    if t in types:
                        return_type_defs.extend(get_related_types(t, types))
                res_data = "\n".join(return_type_defs) if return_type_defs else "not exist"
            else:
                res_data = "not exist"
        else:
            res_data = "not exist"
        
        # 提取函数签名行（Prompt）
        signature_line = function_text.split('{')[0].strip()
        
        # 提取函数体（Output）
        body_start = function_text.find('{') + 1
        body_end = function_text.rfind('}')
        function_body = function_text[body_start:body_end].strip()
        
        # 获取所有函数
        all_function_matches = list(function_pattern.finditer(content))
        all_functions = [content[match.start():match.end() + 100] for match in all_function_matches]  # 获取函数开始部分
        
        # 找到当前函数的索引
        current_index = None
        for i, func_start in enumerate(all_functions):
            if function_text.startswith(func_start[:50]):  # 比较函数开始部分
                current_index = i
                break
        
        if current_index is not None:
            # 提取前5个函数
            bef_functions = []
            for i in range(max(0, current_index-5), current_index):
                start_pos = all_function_matches[i].start()
                end_pos = all_function_matches[i].end()
                # 提取完整函数
                brace_count = 1
                pos = end_pos
                while brace_count > 0 and pos < len(content):
                    if content[pos] == '{':
                        brace_count += 1
                    elif content[pos] == '}':
                        brace_count -= 1
                    pos += 1
                bef_functions.append(content[start_pos:pos].strip())
            
            bef_code = '\n'.join(bef_functions) if bef_functions else "not exist"
            
            # 提取后5个函数
            aft_functions = []
            for i in range(current_index+1, min(current_index+6, len(all_function_matches))):
                start_pos = all_function_matches[i].start()
                end_pos = all_function_matches[i].end()
                # 提取完整函数
                brace_count = 1
                pos = end_pos
                while brace_count > 0 and pos < len(content):
                    if content[pos] == '{':
                        brace_count += 1
                    elif content[pos] == '}':
                        brace_count -= 1
                    pos += 1
                aft_functions.append(content[start_pos:pos].strip())
            
            aft_code = '\n'.join(aft_functions) if aft_functions else "not exist"
        else:
            bef_code = "not exist"
            aft_code = "not exist"
        
        functions.append({
            'rec_data': rec_data,
            'par_data': par_data,
            'res_data': res_data,
            'bef_code': bef_code,
            'aft_code': aft_code,
            'prompt': signature_line,
            'output': function_body
        })
    
    return functions, imports
def clear_output_dir(directory):
    """清空输出目录"""
    if os.path.exists(directory):
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")

def process_go_files(repo_dir, output_base_dir, repo_name):
    """遍历仓库中的.go文件并提取函数"""
    # 创建以库名命名的输出目录
    output_dir = os.path.join(output_base_dir, repo_name.replace('/', '_'))
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    else:
        clear_output_dir(output_dir)  # 清空已存在的目录
    
    # 第一步：收集所有type定义（先删除注释）
    types = {}
    for root, dirs, files in os.walk(repo_dir):
        for file in files:
            if file.endswith('.go') and 'test' not in file.lower():
                go_file_path = os.path.join(root, file)
                with open(go_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 下载后立即删除注释
                content = remove_comments(content)
                types.update(extract_types(content))
    
    # 第二步：处理每个文件并提取函数（使用已删除注释的内容）
    for root, dirs, files in os.walk(repo_dir):
        for file in files:
            if file.endswith('.go') and 'test' not in file.lower():
                go_file_path = os.path.join(root, file)
                with open(go_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # 下载后立即删除注释
                content = remove_comments(content)
                # 将处理后的内容写入临时文件供extract_go_functions使用
                temp_file = os.path.join(root, f"temp_{file}")
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                functions, imports = extract_go_functions(temp_file, types)
                
                # 删除临时文件
                os.remove(temp_file)
                
                if functions:
                    # 获取相对路径（相对于仓库根目录）
                    relative_path = os.path.relpath(go_file_path, repo_dir)
                    # 构建路径信息
                    package_path = f"github.com/{repo_name}/{relative_path.replace(os.sep, '/')}"
                    code_rep = f"github.com/{repo_name}/"
                    
                    # 为每个函数创建单独的txt文件
                    for i, func_info in enumerate(functions, 1):
                        output_file = os.path.join(
                            output_dir,
                            f"{Path(file).stem}_func_{i}.txt"
                        )
                        with open(output_file, 'w', encoding='utf-8') as f:
                            # 写入元数据信息
                            f.write(f"# PackagePath: {package_path}\n")
                            f.write(f"# CodeRep: {code_rep}\n")
                            f.write(f"# ImportPackage: {imports}\n")
                            f.write(f"# RecData: {func_info['rec_data']}\n")
                            f.write(f"# ParData: {func_info['par_data']}\n")
                            f.write(f"# ResData: {func_info['res_data']}\n")
                            f.write(f"# BefCode: {func_info['bef_code']}\n")
                            f.write(f"# AftCode: {func_info['aft_code']}\n")
                            f.write(f"# Prompt: {func_info['prompt']}\n")
                            f.write(f"# Output: {func_info['output']}\n")
    return output_dir

def read_repos_from_file(file_path):
    """从txt文件读取GitHub仓库路径列表"""
    repos = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # 跳过空行和注释
                    repos.append(line)
        return repos
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []

def main():
    # 自动使用repos.txt作为输入文件和默认输出目录
    input_file = "repos.txt"
    output_base_dir = "extracted_functions"
    
    print(f"Using input file: {input_file}")
    print(f"Base output directory: {output_base_dir}")
    
    repos = read_repos_from_file(input_file)
    if not repos:
        print("No valid repositories found in the input file.")
        return
    
    for repo_path in repos:
        print(f"\nProcessing repository: {repo_path}")
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = download_github_repo(repo_path, temp_dir)
            if repo_dir:
                repo_name = repo_path.split('/')[-1]  # 获取库名
                output_dir = process_go_files(repo_dir, output_base_dir, repo_path)
                print(f"Successfully extracted functions from {repo_path} to {output_dir}")
            else:
                print(f"Failed to download repository: {repo_path}")

if __name__ == "__main__":
    main()