import json
import os
import sys

sys.path.append(os.getcwd())
try:
    from modules import html_utils
except ImportError as e:
    print("Could not import html_utils:", e)
    sys.exit(1)

with open('Preload_Pairs/AITQA_case13/table12.json', 'r') as f:
    data = json.load(f)

try:
    html = html_utils.convert_hmd_vmd_to_html_enhanced(data)
    import re
    matches = re.finditer(r'<th[^>]*>([^<]*)</th>', html)
    print("Found headers:")
    for match in matches:
        print(f"th tag text: '{match.group(1)}'")

    matches = re.finditer(r'<th[^>]*data-header="([^"]*)"[^>]*>([^<]*)</th>', html)
    print("\nHeaders with data-header:")
    for match in matches:
        print(f"data-header: '{match.group(1)}' | text: '{match.group(2)}'")
except Exception as e:
    print("Error:", e)
