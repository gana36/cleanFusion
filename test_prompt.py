import json
from modules.prompts import operator

source_schema = {
    "Table1.HMD": [{"attribute1": ""}, {"attribute2": "Total N"}, {"attribute3": "Chemotherapy init delay", "children": [{"child_level1.attribute1": "N (%)"}, {"child_level1.attribute2": "RR"}]}],
    "Table1.VMD": ["Age", "Race"]
}
target_schema = {
    "Table2.HMD": [{"attribute1": ""}, {"attribute2": "Total N (N = 207)"}, {"attribute3": "Patients experiencing RDI <85%", "children": [{"child_level1.attribute1": "N (%)"}, {"child_level1.attribute2": "RR"}]}],
    "Table2.VMD": ["Age", "Race"]
}
match_result = {
    "HMD_matches": [{"source": "Total N", "target": "Total N (N = 207)"}],
    "VMD_matches": [{"source": "Age", "target": "Age"}, {"source": "Race", "target": "Race"}]
}

prompt = operator['json_default']['instance_merge']
prompt = prompt.replace('{source_schema_placeholder}', json.dumps(source_schema))
prompt = prompt.replace('{target_schema_placeholder}', json.dumps(target_schema))
prompt = prompt.replace('{match_results_placeholder}', json.dumps(match_result))

from groq import Groq
import os
import sys

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

try:
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1
    )
    print("RAW OUTPUT:\n")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
