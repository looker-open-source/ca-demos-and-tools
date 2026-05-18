import asyncio
from google.cloud import geminidataanalytics_v1beta as gda
from google.protobuf.json_format import ParseDict

def main():
    print("Testing ParseDict with None...")
    try:
        ParseDict(None, gda.Message())
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
