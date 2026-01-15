# mini_lang_dynamic_v2.py

import os
import json
import requests
import traceback

variables = {}        # глобальные переменные
functions = {}        # функции
return_flag = None

# -------------------------------
# Приведение типов
# -------------------------------
def to_type(type_name, value):
    if type_name == "int": return int(value)
    if type_name == "float": return float(value)
    if type_name == "bool": return str(value).lower() in ["true","1"]
    if type_name == "string": return str(value)
    raise Exception(f"Неизвестный тип {type_name}")

# -------------------------------
# JSON функции
# -------------------------------
def json_encode(obj): return json.dumps(obj)
def json_decode(text): return json.loads(text)

# -------------------------------
# Преобразование массива в словарь
# -------------------------------
def array_to_dict(arr_str, local_vars):
    arr_str = arr_str.strip()[1:-1].strip()
    result = {}
    if not arr_str: return result
    items = arr_str.split(",")
    for item in items:
        if "=" not in item: continue
        key, val_expr = item.split("=", 1)
        key = key.strip()
        val = eval_expr(val_expr.strip(), local_vars)
        result[key] = val
    return result

# -------------------------------
# Eval выражений с арифметикой и логикой
# -------------------------------
def eval_expr(expr, local_vars=None):
    if local_vars is None: local_vars = {}
    expr = expr.strip()
    try:
        allowed_names = {
            **variables, **local_vars,
            "int": int, "float": float, "str": str, "bool": bool, "len": len,
            "True": True, "False": False, "input": input,
            "http_get": lambda url: requests.get(url).text,
            "http_post": lambda url, data: requests.post(url, json=json.loads(data) if isinstance(data,str) else data).text,
            "json_encode": json_encode,
            "json_decode": json_decode
        }
        return eval(expr, {"__builtins__":None}, allowed_names)
    except Exception as e:
        print(f"<Ошибка eval: {e}>")
        return None

# -------------------------------
# Парсинг блока {}
# -------------------------------
def parse_block(lines, start):
    block=[]
    i=start
    depth=0
    while i<len(lines):
        line=lines[i].strip()
        if "{" in line: depth+=1; i+=1; continue
        if "}" in line:
            depth-=1
            if depth==0: return block,i
        if depth>=1: block.append(lines[i])
        i+=1
    return block,i

# -------------------------------
# Выполнение блока
# -------------------------------
def run_block(lines):
    global return_flag
    i=0
    skip_elif_else=False
    while i<len(lines):
        if return_flag is not None: return
        line = lines[i].strip()
        if not line or line.startswith("//"): i+=1; continue

        try:
            # return
            if line.startswith("return "):
                return_flag = eval_expr(line[7:].strip())
                return

            # print
            if line.startswith("print"):
                expr=line[line.find("(")+1:line.rfind(")")]
                res=eval_expr(expr)
                variables["_"]=res
                print(res)
                i+=1
                continue

            # include
            if line.startswith("include "):
                fname=line[7:].strip().strip('"').strip("'")
                run_file(fname)
                i+=1
                continue

            # func
            if line.startswith("func "):
                name=line[5:line.find("(")].strip()
                args=line[line.find("(")+1:line.find(")")].split(",")
                args=[a.strip() for a in args if a.strip()]
                block,end=parse_block(lines,i)
                functions[name]=(args,block)
                i=end+1
                continue

            # вызов функции
            if "(" in line and line.endswith(")"):
                name=line[:line.find("(")].strip()
                params_raw=line[line.find("(")+1:line.rfind(")")].split(",")
                params=[eval_expr(p.strip()) for p in params_raw if p.strip()]
                if name in functions:
                    args,fblock=functions[name]
                    old_vars=variables.copy()
                    for a,v in zip(args,params): variables[a]=v
                    return_flag=None
                    run_block(fblock)
                    res=return_flag
                    return_flag=None
                    variables.update(old_vars)
                    if res is not None: variables["_"]=res
                    i+=1
                    continue

            # if/elif/else
            if line.startswith("if("):
                cond=line[line.find("(")+1:line.find(")")]
                block,end=parse_block(lines,i)
                if eval_expr(cond): run_block(block); skip_elif_else=True
                else: skip_elif_else=False
                i=end+1
                continue
            if line.startswith("elif("):
                if skip_elif_else: block,end=parse_block(lines,i); i=end+1; continue
                cond=line[line.find("(")+1:line.find(")")]
                block,end=parse_block(lines,i)
                if eval_expr(cond): run_block(block); skip_elif_else=True
                i=end+1
                continue
            if line.startswith("else"):
                if skip_elif_else: block,end=parse_block(lines,i); i=end+1; continue
                block,end=parse_block(lines,i)
                run_block(block)
                i=end+1
                continue

            # while loop
            if line.startswith("while("):
                cond=line[line.find("(")+1:line.find(")")]
                block,end=parse_block(lines,i)
                while eval_expr(cond):
                    run_block(block)
                i=end+1
                continue

            # for (lists as item)
            if line.startswith("foreach(") and " as " in line:
                header=line[line.find("(")+1:line.find(")")].strip()
                iterable_name, iter_var=[x.strip() for x in header.split(" as ")]
                iterable=eval_expr(iterable_name)
                if iterable is None: iterable=[]
                block,end=parse_block(lines,i)
                if isinstance(iterable,dict):
                    for k,v in iterable.items():
                        variables[iter_var]={"key":k,"value":v}
                        run_block(block)
                else:
                    for item in iterable:
                        variables[iter_var]=item
                        run_block(block)
                i=end+1
                continue

            # присвоение и сокращённые операции
            for op in ["+=", "-=", "*=", "/="]:
                if op in line:
                    var,expr=line.split(op,1)
                    var=var.strip()
                    val=eval_expr(expr.strip())
                    if var in variables and variables[var] is not None:
                        if op=="+=": variables[var]+=val
                        elif op=="-=": variables[var]-=val
                        elif op=="*=": variables[var]*=val
                        elif op=="/=": variables[var]/=val
                    else: variables[var]=val
                    break
            else:
                if "=" in line:
                    var,expr=line.split("=",1)
                    variables[var.strip()]=eval_expr(expr.strip())

        except Exception:
            print("<Ошибка исполнения>\n"+traceback.format_exc())

        i+=1

# -------------------------------
# Запуск кода
# -------------------------------
def run_code(code):
    lines=code.splitlines()
    run_block(lines)

# -------------------------------
# Запуск .bc файла
# -------------------------------
def run_file(filename):
    if not filename.endswith(".bc"): raise Exception("Файл должен иметь расширение .bc")
    if not os.path.exists(filename): raise Exception(f"Файл не найден: {filename}")
    with open(filename,"r",encoding="utf-8") as f:
        code=f.read()
    run_code(code)
    
def main():
    import sys
    if len(sys.argv) < 2:
        print("Использование: bcode файл.bc")
        exit(1)
    run_file(sys.argv[1])
# -------------------------------
# CLI
# -------------------------------
if __name__=="__main__":
    main()
    