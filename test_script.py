#!/usr/bin/env python3
"""
测试脚本 - 验证Go函数提取功能
"""

import os
import tempfile
from pathlib import Path

# 创建一个临时的Go文件用于测试
test_go_content = '''
package main

import "fmt"

// 普通函数
func helloWorld() {
    fmt.Println("Hello, World!")
}

// 带参数和返回值的函数
func add(a, b int) int {
    return a + b
}

// 方法（接收器函数）
type Calculator struct{}

func (c *Calculator) Multiply(x, y int) int {
    return x * y
}

// 测试函数（应该被排除）
func TestAdd(t *testing.T) {
    // 测试代码
}
'''

def create_test_environment():
    """创建测试环境"""
    temp_dir = tempfile.mkdtemp()
    
    # 创建测试Go文件
    go_file_path = os.path.join(temp_dir, "example.go")
    with open(go_file_path, 'w', encoding='utf-8') as f:
        f.write(test_go_content)
    
    return temp_dir, go_file_path

def test_function_extraction():
    """测试函数提取功能"""
    from main import extract_go_functions
    
    temp_dir, go_file_path = create_test_environment()
    
    try:
        functions = extract_go_functions(go_file_path)
        print(f"提取到 {len(functions)} 个函数:")
        
        for i, func in enumerate(functions, 1):
            print(f"\n--- 函数 {i} ---")
            print(func)
        
        # 验证至少提取到1个函数（排除测试函数）
        assert len(functions) >= 1, f"预期至少1个函数，实际提取到{len(functions)}个"
        
        # 验证测试函数被正确排除
        test_functions = [f for f in functions if 'TestAdd' in f]
        assert len(test_functions) == 0, "测试函数没有被正确排除"
        
        print("\n✅ 函数提取测试通过！")
        
    finally:
        # 清理临时文件
        import shutil
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_function_extraction()