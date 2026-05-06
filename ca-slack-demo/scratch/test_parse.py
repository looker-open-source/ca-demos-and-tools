import sys
import os
import json
from google.protobuf.json_format import ParseDict
from google.cloud import geminidataanalytics_v1beta as gda

# Add src to path
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(base_dir, 'src'))

raw_data = {'timestamp': '2026-04-14T23:24:13.469450Z', 'systemMessage': {'data': {'query': {'name': 'list_all_stores', 'looker': {'model': 'gadgets_alloydb', 'explore': 'transactions', 'fields': ['d_stores.storename'], 'sorts': ['d_stores.storename asc'], 'limit': '1000'}}}}}

msg = gda.Message()
print(f"Type of gda.Message: {type(gda.Message)}")
print(f"Type of msg: {type(msg)}")

print("\nTrying to parse whole data with ParseDict...")
try:
    ParseDict(raw_data, msg, ignore_unknown_fields=True)
    print("Successfully parsed with ignore_unknown_fields=True!")
except Exception as e:
    print(f"Failed to parse with ignore_unknown_fields=True: {e}")

print("\nTrying to parse by passing dict to constructor...")
try:
    msg2 = gda.Message(raw_data)
    print("Successfully parsed by passing dict to constructor!")
    print(f"Parsed message: {msg2}")
except Exception as e:
    print(f"Failed to parse by passing dict to constructor: {e}")

print("\nTrying to parse systemMessage directly...")
try:
    ParseDict(raw_data['systemMessage'], msg.system_message, ignore_unknown_fields=True)
    print("Successfully parsed systemMessage directly!")
except Exception as e:
    print(f"Failed to parse systemMessage directly: {e}")

