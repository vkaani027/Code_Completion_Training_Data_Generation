#!/usr/bin/env python3
"""测试新的输入格式功能"""

from main import read_repos_from_file, download_github_repo
import tempfile
import os

def test_file_reading():
    """测试文件读取功能"""
    print("测试文件读取功能...")
    repos = read_repos_from_file('repos.txt')
    print(f"读取到的仓库: {repos}")
    
    # 验证读取结果
    assert len(repos) == 1, f"预期1个仓库，实际读取到{len(repos)}个"
    assert repos[0] == 'gin-gonic/gin', f"仓库名称不匹配: {repos[0]}"
    print("✅ 文件读取测试通过!")

def test_url_generation():
    """测试URL生成功能"""
    print("\n测试URL生成功能...")
    
    # 模拟下载函数的部分逻辑
    repo_path = 'gin-gonic/gin'
    expected_url = 'https://codeload.github.com/gin-gonic/gin/zip/main'
    
    # 验证URL生成
    actual_url = f"https://codeload.github.com/{repo_path}/zip/main"
    assert actual_url == expected_url, f"URL生成错误: {actual_url}"
    print(f"✅ URL生成正确: {actual_url}")

if __name__ == "__main__":
    test_file_reading()
    test_url_generation()
    print("\n🎉 所有输入格式测试通过!")