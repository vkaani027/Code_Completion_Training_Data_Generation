package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"io/ioutil"
	"os"
	"strings"
)

type TypeInfo struct {
	Name        string `json:"name"`
	Definition  string `json:"definition"`
	Methods     string `json:"methods,omitempty"`
}

type FunctionInfo struct {
	Name          string   `json:"name"`
	Receiver      string   `json:"receiver,omitempty"`
	ReceiverInfo  string   `json:"receiver_info,omitempty"`
	Params        string   `json:"params"`
	ParamsInfo    string   `json:"params_info,omitempty"`
	Returns       string   `json:"returns,omitempty"`
	ReturnsInfo   string   `json:"returns_info,omitempty"`
	Doc           string   `json:"doc,omitempty"`
	Body          string   `json:"body"`
	StartLine     int      `json:"start_line"`
	EndLine       int      `json:"end_line"`
	Signature     string   `json:"signature"`
	ImportPackage string   `json:"import_package"`
	BeforeFuncs   []string `json:"before_funcs,omitempty"`
	AfterFuncs    []string `json:"after_funcs,omitempty"`
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: go-ast-parser <go-file>")
		os.Exit(1)
	}
	
	filePath := os.Args[1]
	fset := token.NewFileSet()
	
	// Parse the Go file
	file, err := parser.ParseFile(fset, filePath, nil, parser.ParseComments)
	if err != nil {
		fmt.Printf("Error parsing file: %v\n", err)
		os.Exit(1)
	}
	
	// Extract imports
	var imports []string
	for _, imp := range file.Imports {
		imports = append(imports, imp.Path.Value)
	}
	importPkg := strings.Join(imports, "; ")
	
	// Read the source file content once
	sourceBytes, err := ioutil.ReadFile(filePath)
	if err != nil {
		fmt.Printf("Error reading source file: %v\n", err)
		os.Exit(1)
	}
	source := string(sourceBytes)
	lines := strings.Split(source, "\n")

	// Collect all type definitions first
	typeDefinitions := make(map[string]string)
	typeMethods := make(map[string][]string)
	
	ast.Inspect(file, func(n ast.Node) bool {
		// Collect type definitions
		if typeSpec, ok := n.(*ast.TypeSpec); ok {
			start := fset.Position(typeSpec.Pos()).Line
			end := fset.Position(typeSpec.End()).Line
			if start > 0 && end <= len(lines) {
				typeLines := lines[start-1:end]
				typeDefinitions[typeSpec.Name.Name] = strings.Join(typeLines, "\n")
			}
		}
		return true
	})
	
	// Collect methods for each type
	ast.Inspect(file, func(n ast.Node) bool {
		if fn, ok := n.(*ast.FuncDecl); ok && fn.Recv != nil {
			for _, field := range fn.Recv.List {
				typeName := exprToString(field.Type)
				// Remove * if present
				typeName = strings.TrimPrefix(typeName, "*")
				typeMethods[typeName] = append(typeMethods[typeName], fn.Name.Name)
			}
		}
		return true
	})
	
	// First pass: collect all functions with more info
	var allFuncs []FunctionInfo
	ast.Inspect(file, func(n ast.Node) bool {
		if fn, ok := n.(*ast.FuncDecl); ok {
			info := FunctionInfo{
				Name:      fn.Name.Name,
				StartLine: fset.Position(fn.Pos()).Line,
				EndLine:   fset.Position(fn.End()).Line,
			}
			
			// Extract receiver
			if fn.Recv != nil && len(fn.Recv.List) > 0 {
				recvType := exprToString(fn.Recv.List[0].Type)
				info.Receiver = recvType
				
				// Add receiver type info
				typeName := strings.TrimPrefix(recvType, "*")
				if def, ok := typeDefinitions[typeName]; ok {
					info.Receiver = def
					if methods, ok := typeMethods[typeName]; ok {
						info.Receiver += "\n\n// Methods:\n"
						for _, method := range methods {
							info.Receiver += fmt.Sprintf("- %s\n", method)
						}
					}
				}
			}
			
			// Extract parameters
			if fn.Type.Params != nil {
				params := fieldListToString(fn.Type.Params)
				if params != "" {
					info.Params = params
					
					// Add parameter type info
					for _, field := range fn.Type.Params.List {
						typeName := exprToString(field.Type)
						typeName = strings.TrimPrefix(typeName, "*")
						if def, ok := typeDefinitions[typeName]; ok {
							info.Params += fmt.Sprintf("\n\n// Type %s definition:\n%s", typeName, def)
							if methods, ok := typeMethods[typeName]; ok {
								info.Params += "\n// Methods:\n"
								for _, method := range methods {
									info.Params += fmt.Sprintf("- %s\n", method)
								}
							}
						}
					}
				} else {
					info.Params = "not exist"
				}
			} else {
				info.Params = "not exist"
			}
			
			// Extract return values
			if fn.Type.Results != nil {
				info.Returns = fieldListToString(fn.Type.Results)
				
				// Add return type info
				for _, field := range fn.Type.Results.List {
					typeName := exprToString(field.Type)
					typeName = strings.TrimPrefix(typeName, "*")
					if def, ok := typeDefinitions[typeName]; ok {
						info.Returns += fmt.Sprintf("\n\n// Type %s definition:\n%s", typeName, def)
						if methods, ok := typeMethods[typeName]; ok {
							info.Returns += "\n// Methods:\n"
							for _, method := range methods {
								info.Returns += fmt.Sprintf("- %s\n", method)
							}
						}
					}
				}
			}
			
			// Build signature
			info.Signature = buildSignature(fn)
			
			allFuncs = append(allFuncs, info)
		}
		return true
	})
	
var functions []FunctionInfo
	
	// 第二次遍历：提取所有函数体
	ast.Inspect(file, func(n ast.Node) bool {
		if fn, ok := n.(*ast.FuncDecl); ok {
			// 跳过测试函数
			if strings.HasPrefix(fn.Name.Name, "Test") {
				return true
			}
			
			// 在allFuncs中查找对应的函数信息
			var info *FunctionInfo
			for i := range allFuncs {
				if allFuncs[i].Name == fn.Name.Name && 
				   allFuncs[i].StartLine == fset.Position(fn.Pos()).Line {
					info = &allFuncs[i]
					break
				}
			}
			
			if info == nil {
				return true
			}
			
			// 提取函数体
			if fn.Body != nil {
				start := fset.Position(fn.Body.Pos()).Line
				end := fset.Position(fn.Body.End()).Line
				if start > 0 && end <= len(lines) {
					bodyLines := lines[start-1:end]
					info.Body = strings.Join(bodyLines, "\n")
				}
			}
		}
		return true
	})
	
	// 第三次遍历：设置导入包信息和前后函数
	for i := range allFuncs {
		info := &allFuncs[i]
		
		// 设置导入包信息
		info.ImportPackage = importPkg
		
		// 获取前面的5个函数体
		startIndex := max(0, i-5)
		for j := startIndex; j < i; j++ {
			if allFuncs[j].Name != info.Name && allFuncs[j].Body != "" {
				info.BeforeFuncs = append(info.BeforeFuncs, allFuncs[j].Body)
			}
		}
		
		// 获取后面的5个函数体
		endIndex := min(len(allFuncs), i+6) // 当前函数+后面5个
		for j := i+1; j < endIndex; j++ {
			if allFuncs[j].Name != info.Name && allFuncs[j].Body != "" {
				info.AfterFuncs = append(info.AfterFuncs, allFuncs[j].Body)
			}
		}
		
		// 确保最多只取5个后面的函数
		if len(info.AfterFuncs) > 5 {
			info.AfterFuncs = info.AfterFuncs[:5]
		}
		
		functions = append(functions, *info)
	}
	
	// 检查函数信息并输出到标准错误
	fmt.Fprintf(os.Stderr, "DEBUG: Number of functions found: %d\n", len(functions))
	
	for i, info := range functions {
		if info.ImportPackage == "" {
			info.ImportPackage = "not exist"
		}
		
		// 处理空字符串的前后函数体
		cleanedBeforeFuncs := make([]string, 0)
		for _, funcBody := range info.BeforeFuncs {
			if funcBody != "" {
				cleanedBeforeFuncs = append(cleanedBeforeFuncs, funcBody)
			}
		}
		if len(cleanedBeforeFuncs) == 0 {
			info.BeforeFuncs = []string{"not exist"}
		} else {
			info.BeforeFuncs = cleanedBeforeFuncs
		}
		
		cleanedAfterFuncs := make([]string, 0)
		for _, funcBody := range info.AfterFuncs {
			if funcBody != "" {
				cleanedAfterFuncs = append(cleanedAfterFuncs, funcBody)
			}
		}
		if len(cleanedAfterFuncs) == 0 {
			info.AfterFuncs = []string{"not exist"}
		} else {
			info.AfterFuncs = cleanedAfterFuncs
		}
		
		functions[i] = info
		
		// 输出调试信息到标准错误
		fmt.Fprintf(os.Stderr, "DEBUG: Function %s - ImportPackage: %s\n", info.Name, info.ImportPackage)
		fmt.Fprintf(os.Stderr, "DEBUG: Function %s - BeforeFuncs: %v\n", info.Name, info.BeforeFuncs)
		fmt.Fprintf(os.Stderr, "DEBUG: Function %s - AfterFuncs: %v\n", info.Name, info.AfterFuncs)
	}
	
	fmt.Fprintf(os.Stderr, "DEBUG: Finished processing functions\n")
	
	result, _ := json.MarshalIndent(functions, "", "  ")
	fmt.Println(string(result))
}

func exprToString(expr ast.Expr) string {
	if expr == nil {
		return ""
	}
	switch e := expr.(type) {
	case *ast.Ident:
		return e.Name
	case *ast.StarExpr:
		return "*" + exprToString(e.X)
	case *ast.SelectorExpr:
		return exprToString(e.X) + "." + exprToString(e.Sel)
	default:
		return fmt.Sprintf("%T", expr)
	}
}

func fieldListToString(fieldList *ast.FieldList) string {
	if fieldList == nil || len(fieldList.List) == 0 {
		return ""
	}
	
	var fields []string
	for _, field := range fieldList.List {
		if len(field.Names) > 0 {
			for _, name := range field.Names {
				fieldStr := name.Name
				if field.Type != nil {
					fieldStr += " " + exprToString(field.Type)
				}
				fields = append(fields, fieldStr)
			}
		} else {
			if field.Type != nil {
				fields = append(fields, exprToString(field.Type))
			}
		}
	}
	
	if len(fields) == 1 {
		return fields[0]
	}
	return "(" + strings.Join(fields, ", ") + ")"
}

func getSurroundingFuncs(allFuncs []FunctionInfo, current FunctionInfo, startOffset, endOffset int) []string {
	var surrounding []string
	for _, f := range allFuncs {
		if f.Name == current.Name {
			continue // 跳过当前函数
		}
		
		// 查找前面的函数 (在当前函数之前)
		if startOffset < 0 && f.EndLine < current.StartLine && f.EndLine >= current.StartLine+startOffset {
			surrounding = append(surrounding, f.Name)
		}
		
		// 查找后面的函数 (在当前函数之后)
		if endOffset > 0 && f.StartLine > current.EndLine && f.StartLine <= current.EndLine+endOffset {
			surrounding = append(surrounding, f.Name)
		}
	}
	return surrounding
}

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func buildSignature(fn *ast.FuncDecl) string {
	var sig strings.Builder
	sig.WriteString("func ")
	
	if fn.Recv != nil && len(fn.Recv.List) > 0 {
		sig.WriteString("(")
		sig.WriteString(fieldListToString(fn.Recv))
		sig.WriteString(") ")
	}
	
	sig.WriteString(fn.Name.Name)
	sig.WriteString("(")
	sig.WriteString(fieldListToString(fn.Type.Params))
	sig.WriteString(")")
	
	if fn.Type.Results != nil {
		returns := fieldListToString(fn.Type.Results)
		if strings.Contains(returns, ",") {
			sig.WriteString(" (")
			sig.WriteString(returns)
			sig.WriteString(")")
		} else {
			sig.WriteString(" ")
			sig.WriteString(returns)
		}
	}
	
	return sig.String()
}