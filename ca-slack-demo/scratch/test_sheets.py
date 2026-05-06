import sys
from src.mcp_server import create_and_export_sheet

def test_export():
    try:
        print("Attempting to create a Google Sheet...")
        result = create_and_export_sheet(
            title="Test Scratch Sheet",
            data_matrix=[["A", "B"], ["1", "2"]]
        )
        print("Success!")
        print(result)
    except Exception as e:
        print("Caught Exception:")
        print(e)

if __name__ == "__main__":
    test_export()
