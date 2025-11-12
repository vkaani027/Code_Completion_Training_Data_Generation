# Go语言代码提取工具

这是一个Python脚本，用于从GitHub仓库中提取Go语言函数代码。

## 功能特点

1. **GitHub仓库下载**：支持输入GitHub链接，自动下载并解压仓库
2. **智能文件过滤**：自动排除包含"test"的文件名
3. **函数提取**：使用正则表达式提取Go函数定义
4. **批量输出**：每个函数保存为单独的txt文件

## 使用方法

1. 确保安装Python 3.6+ 和 requests 库：
   ```bash
   pip install requests
   ```

2. 创建一个文本文件(如repos.txt)，列出要提取的GitHub仓库，格式为`owner/repository`：
   ```text
   # 示例文件内容
   gin-gonic/gin
   golang/example
   ```

3. 运行脚本：
   ```bash
   python main.py
   ```

4. 按照提示输入：
   - 包含GitHub仓库列表的文件路径(如repos.txt)
   - 输出目录（可选，默认为"extracted_functions"）

## 示例

```bash
python main.py
Enter GitHub repository URL: https://github.com/golang/example
Enter output directory (default: extracted_functions): my_functions
```

## 输出格式

提取的函数将保存在指定目录中，文件名格式为：
`{源文件名}_func_{序号}.txt`

每个函数文件包含以下字段：
1. `PackagePath`: 函数所在的包路径
2. `CodeRep`: 代码仓库路径
3. `ImportPackage`: 导入的包
4. `RecData`: 接收者类型定义（如果有）
5. `ParData`: 参数类型定义
6. `ResData`: 返回值类型定义
7. `BefCode`: 前5个相关函数代码
8. `AftCode`: 后5个相关函数代码  
9. `Prompt`: 函数签名（左大括号所在行）
10. `Output`: 函数体内容（大括号之间的代码）

示例：
```text
# PackagePath: github.com/gin-gonic/gin/auth.go
# CodeRep: github.com/gin-gonic/gin/
# ImportPackage: import (...)
# RecData: type authPairs []authPair
# ParData: type Accounts map[string]string
# ResData: not exist
# BefCode: func (a authPairs) searchCredential(...) {...}
# AftCode: func BasicAuth(...) {...}
# Prompt: func BasicAuthForRealm(accounts Accounts, realm string) HandlerFunc {
# Output: if realm == "" {
    realm = "Authorization Required"
}
...
```

## 注意事项

- 脚本会自动排除测试文件（文件名包含"test"）
- 支持处理大型仓库，使用临时文件夹避免磁盘占用
- 网络连接需要稳定，以便下载GitHub仓库