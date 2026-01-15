from interpreter import run_file
import sys

if len(sys.argv) < 2:
    print("Использование: python run.py имя_файла.bc")
else:
    run_file(sys.argv[1])