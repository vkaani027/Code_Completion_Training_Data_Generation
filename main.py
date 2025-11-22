import os
import tempfile
import shutil
import requests
import zipfile
import subprocess
import json
import re
from pathlib import Path

def download_github_repo(repo_path, temp_dir):
    """下载GitHub仓库到临时文件夹"""
    try:
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
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        extracted_files = zip_ref.namelist()
        if extracted_files:
            extracted_dir = os.path.join(temp_dir, extracted_files[0].split('/')[0])
            return extracted_dir
        return None
    
    except Exception as e:
        print(f"Error downloading repository {repo_path}: {e}")
        return None

def run_go_ast_tool(go_file_path):
    """使用Go工具解析AST"""
    try:
        # 使用项目中的go_ast_parser.go文件
        parser_file = "go_ast_parser.go"
        executable = "go_ast_parser"
        
        # 检查是否需要重新编译
        if not os.path.exists(executable) or \
           os.path.getmtime(executable) < os.path.getmtime(parser_file):
            print("Compiling Go AST parser...")
            compile_cmd = ["go", "build", "-o", executable, parser_file]
            result = subprocess.run(compile_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Go compilation failed: {result.stderr}")
                return None
        
        # 运行AST解析器
        ast_cmd = [executable, go_file_path]
        result = subprocess.run(ast_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"AST parsing failed: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"Error in Go AST parsing: {e}")
        return None

def process_go_files_with_ast(repo_dir, output_base_dir, repo_name):
    """使用真正的AST解析处理Go文件"""
    output_dir = os.path.join(output_base_dir, repo_name.replace('/', '_'))
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    else:
        # 清空已存在的目录
        for filename in os.listdir(output_dir):
            file_path = os.path.join(output_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")
    
    # 第一步：收集所有type定义（简化版本）
    types = {}
    for root, dirs, files in os.walk(repo_dir):
        for file in files:
            if file.endswith('.go') and 'test' not in file.lower():
                go_file_path = os.path.join(root, file)
                with open(go_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                file_types = extract_go_types(content)
                types.update(file_types)
                if file_types:
                    print(f"Found {len(file_types)} types in {file}")
    
    # 第二步：处理每个文件并提取函数
    for root, dirs, files in os.walk(repo_dir):
        for file in files:
            if file.endswith('.go') and 'test' not in file.lower():
                go_file_path = os.path.join(root, file)
                print(f"Processing with AST: {go_file_path}")
                
                functions = run_go_ast_tool(go_file_path)
                if functions:
                    relative_path = os.path.relpath(go_file_path, repo_dir)
                    package_path = f"github.com/{repo_name}/{relative_path.replace(os.sep, '/')}"
                    code_rep = f"github.com/{repo_name}/"
                    
                    for i, func_info in enumerate(functions, 1):
                        output_file = os.path.join(
                            output_dir, 
                            f"{Path(file).stem}_func_{i}.txt"
                        )
                        
                        with open(output_file, 'w', encoding='utf-8') as f:
                            # 写入与正则表达式版本相同的格式
                            f.write(f"# PackagePath: {package_path}\n")
                            f.write(f"# CodeRep: {code_rep}\n")
                            f.write(f"# ImportPackage: {func_info.get('import_package', 'not exist')}\n")
                            f.write(f"# RecData: {func_info.get('receiver', 'not exist')}\n")
                            f.write(f"# ParData: {func_info.get('params', 'not exist')}\n")
                            f.write(f"# ResData: {func_info.get('returns', 'not exist')}\n")
                            
                            # 处理前后函数信息
                            bef_funcs = func_info.get('before_funcs', [])
                            aft_funcs = func_info.get('after_funcs', [])
                            
                            bef_code = "\n".join(bef_funcs) if bef_funcs else "not exist"
                            aft_code = "\n".join(aft_funcs) if aft_funcs else "not exist"
                            
                            f.write(f"# BefCode: {bef_code}\n")
                            f.write(f"# AftCode: {aft_code}\n")
                            f.write(f"# Prompt: {func_info.get('signature', 'not exist')}\n")
                            f.write(f"# Output: {func_info.get('body', 'not exist')}\n")
    
    return output_dir

def extract_go_types(content):
    """使用正则表达式暂时提取type定义（简化版本）"""
    types = {}
    type_pattern = re.compile(r'type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+(\w+|struct\s*\{[^{}]*\}|interface\s*\{[^{}]*\}|\[.*\])', re.MULTILINE)
    
    for match in type_pattern.finditer(content):
        type_name = match.group(1)
        type_def = match.group(2).strip()
        full_def = f"type {type_name} {type_def}"
        types[type_name] = full_def
    
    return types

def read_repos_from_file(file_path):
    """从txt文件读取GitHub仓库路径列表"""
    repos = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    repos.append(line)
        return repos
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []

def main():
    input_file = "repos.txt"
    output_base_dir = "extracted_functions_ast"
    
    print(f"Using input file: {input_file}")
    print(f"AST output directory: {output_base_dir}")
    
    # 简化的测试 - 只处理一个文件来演示AST解析
    test_go_file = "test.go"
    if os.path.exists(test_go_file):
        print(f"Testing AST parsing on: {test_go_file}")
        result = run_go_ast_tool(test_go_file)
        if result:
            print("AST parsing successful!")
            for func_info in result:
                print(f"Function: {func_info['name']}")
    else:
        print("No test.go file found for AST demonstration")
    
    # 处理完整的仓库
    repos = read_repos_from_file(input_file)
    if not repos:
        print("No valid repositories found in the input file.")
        return
    
    for repo_path in repos:
        print(f"\nProcessing repository: {repo_path}")
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = download_github_repo(repo_path, temp_dir)
            if repo_dir:
                output_dir = process_go_files_with_ast(repo_dir, output_base_dir, repo_path)
                print(f"Successfully extracted functions from {repo_path} to {output_dir}")
            else:
                print(f"Failed to download repository: {repo_path}")

if __name__ == "__main__":
    main()