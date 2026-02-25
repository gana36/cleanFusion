
try:
    from modules.dynamic_pdf import extract_tables_from_pdf
    print("SUCCESS: extract_tables_from_pdf imported.")
except ImportError as e:
    print(f"FAILURE: ImportError: {e}")
except Exception as e:
    print(f"FAILURE: {e}")
    
import inspect
from modules import dynamic_pdf
print("Dir(dynamic_pdf):", dir(dynamic_pdf))

if hasattr(dynamic_pdf, 'extract_tables_from_pdf'):
    print("Has attribute: Yes")
else:
    print("Has attribute: No")
