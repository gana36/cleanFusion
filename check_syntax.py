
import re

def check_syntax(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    stack = []
    in_template_string = False
    
    for i, line in enumerate(lines):
        line_num = i + 1
        for j, char in enumerate(line):
            # Simple comment check (flaky for strings but better)
            if line[j:j+2] == '//' and not in_template_string:
                break
                
            if char == '`':
                in_template_string = not in_template_string
                continue
            
            if in_template_string:
                continue
                
            if char in '{[(':
                stack.append((char, line_num, j))
            elif char in '}])':
                if not stack:
                    print(f"Error: Unmatched '{char}' at line {line_num} column {j+1}")
                    return
                
                last_char, last_line, last_col = stack.pop()
                expected = {'{': '}', '[': ']', '(': ')'}[last_char]
                if char != expected:
                    print(f"Error: Mismatched '{char}' at line {line_num} column {j+1}. Expected '{expected}' (opened at line {last_line})")
                    return

    if stack:
        char, line, col = stack[-1]
        print(f"Error: Unclosed '{char}' at line {line} column {col+1}")
    elif in_template_string:
        print("Error: Unclosed template string (backtick)")
    else:
        print("Syntax check passed: Braces, brackets, and backticks are balanced.")

check_syntax("static/js/main.js")
