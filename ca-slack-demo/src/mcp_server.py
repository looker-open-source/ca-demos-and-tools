from mcp.server.fastmcp import FastMCP
import gspread
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import vl_convert as vlc
import json
import os

# Initialize FastMCP server
mcp = FastMCP("Google Sheets Server")

@mcp.tool()
def create_and_export_sheet(title: str, data_matrix: list, user_email: str | None = None) -> str:
    """
    Creates a new Google Sheet and populates it with the provided data matrix.
    Shares the sheet with the user's email for immediate access.
    
    :param title: Title of the generated Google Sheet
    :param data_matrix: A list of lists containing the tabular metrics to insert
    :param user_email: The email address of the user to share the sheet with
    """
    # Authenticate using Application Default Credentials (ADC)
    credentials, project = default(
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    
    # Connect to Google Sheets
    client = gspread.authorize(credentials)
    
    # Create the spreadsheet inside the Shared Drive
    SHARED_DRIVE_ID = os.environ.get("SHARED_DRIVE_ID")
    if SHARED_DRIVE_ID:
        spreadsheet = client.create(title, folder_id=SHARED_DRIVE_ID)
    else:
        spreadsheet = client.create(title)
    
    # Populate the first worksheet
    worksheet = spreadsheet.get_worksheet(0)
    worksheet.append_rows(data_matrix)
    
    return f"Sheet '{title}' created successfully inside Shared Drive! Open it here: {spreadsheet.url}"


@mcp.tool()
def create_and_export_slides(presentation_title: str, slides: list, user_email: str | None = None) -> str:
    """
    Creates a Google Slides presentation with multiple slides.
    
    Args:
        presentation_title: The title of the presentation file.
        slides: A list of dictionaries, each representing a slide.
                Structure: [{"title": "Slide Title", "data": [["Row1Col1", ...], ...], "bullets": ["Bullet 1", ...]}]
                The 'bullets' field is optional.
        user_email: Optional user email.
    """
    # Authenticate using Application Default Credentials (ADC)
    credentials, project = default(
        scopes=[
            "https://www.googleapis.com/auth/presentations",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets"
        ]
    )
    
    drive_service = build('drive', 'v3', credentials=credentials)
    slides_service = build('slides', 'v1', credentials=credentials)
    sheets_service = build('sheets', 'v4', credentials=credentials)
    
    SHARED_DRIVE_ID = os.environ.get("SHARED_DRIVE_ID")
    
    # Create presentation
    file_metadata = {
        'name': presentation_title,
        'mimeType': 'application/vnd.google-apps.presentation',
    }
    if SHARED_DRIVE_ID:
        file_metadata['parents'] = [SHARED_DRIVE_ID]
    
    file = drive_service.files().create(
        body=file_metadata,
        supportsAllDrives=True,
        fields='id'
    ).execute()
    presentation_id = file.get('id')
    
    # Get default first slide ID
    presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
    default_slide_id = presentation.get('slides')[0].get('objectId')
    # Pre-process charts: create Sheets and Charts
    slide_charts = {} # {slide_idx: {'spreadsheet_id': ..., 'chart_id': ...}}
    for idx, slide in enumerate(slides):
        chart_spec = slide.get('chart_spec')
        data_matrix = slide.get('data', [])
        rows = len(data_matrix)
        
        if chart_spec and rows > 1: # Need at least data rows (header + 1 row)
            try:
                slide_title = slide.get('title', f"Slide {idx+1}")
                
                # 1. Create Spreadsheet via Drive API in Shared Drive
                file_metadata = {
                    'name': f"Chart Data for {slide_title}",
                    'mimeType': 'application/vnd.google-apps.spreadsheet',
                    'parents': [SHARED_DRIVE_ID]
                }
                file = drive_service.files().create(
                    body=file_metadata,
                    supportsAllDrives=True,
                    fields='id'
                ).execute()
                sheet_id = file.get('id')
                
                # 2. Write data to Sheet
                sheets_service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range="Sheet1!A1",
                    valueInputOption="USER_ENTERED",
                    body={'values': data_matrix}
                ).execute()
                
                # 3. Create Chart in Sheet
                chart_request = {
                    'addChart': {
                        'chart': {
                            'spec': {
                                'title': slide_title,
                                'basicChart': {
                                    'chartType': 'COLUMN',
                                    'legendPosition': 'BOTTOM_LEGEND',
                                    'axis': [
                                        {'position': 'BOTTOM_AXIS', 'title': data_matrix[0][0]},
                                        {'position': 'LEFT_AXIS', 'title': data_matrix[0][1]}
                                    ],
                                    'domains': [
                                        {
                                            'domain': {
                                                'sourceRange': {
                                                    'sources': [
                                                        {
                                                            'sheetId': 0,
                                                            'startRowIndex': 1,
                                                            'endRowIndex': rows,
                                                            'startColumnIndex': 0,
                                                            'endColumnIndex': 1
                                                        }
                                                    ]
                                                }
                                            }
                                        }
                                    ],
                                    'series': [
                                        {
                                            'series': {
                                                'sourceRange': {
                                                    'sources': [
                                                        {
                                                            'sheetId': 0,
                                                            'startRowIndex': 0, # Include header for series name
                                                            'endRowIndex': rows,
                                                            'startColumnIndex': 1,
                                                            'endColumnIndex': 2
                                                        }
                                                    ]
                                                }
                                            },
                                            'targetAxis': 'LEFT_AXIS'
                                        }
                                    ]
                                }
                            },
                            'position': {
                                'newSheet': True
                            }
                        }
                    }
                }
                
                response = sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=sheet_id,
                    body={'requests': [chart_request]}
                ).execute()
                
                chart_id = response['replies'][0]['addChart']['chart']['chartId']
                
                slide_charts[idx] = {
                    'spreadsheet_id': sheet_id,
                    'chart_id': chart_id
                }
                print(f"Created chart for slide {idx} in Sheet {sheet_id}, Chart ID: {chart_id}")
            except Exception as e:
                print(f"Error creating chart for slide {idx}: {e}")
                
    requests = [
        # 1. Create fresh Title Slide
        {
            'createSlide': {
                'objectId': 'slide_title',
                'slideLayoutReference': {'predefinedLayout': 'BLANK'}
            }
        },
        # 2. Delete default slide
        {
            'deleteObject': {'objectId': default_slide_id}
        },
        # 3. Add Main Title on Title Slide
        {
            'createShape': {
                'objectId': 'box_main_title',
                'shapeType': 'TEXT_BOX',
                'elementProperties': {
                    'pageObjectId': 'slide_title',
                    'size': {'height': {'magnitude': 100, 'unit': 'PT'}, 'width': {'magnitude': 700, 'unit': 'PT'}},
                    'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 50, 'translateY': 150, 'unit': 'PT'}
                }
            }
        },
        # 4. Add AI Hint on Title Slide
        {
            'createShape': {
                'objectId': 'box_ai_hint',
                'shapeType': 'TEXT_BOX',
                'elementProperties': {
                    'pageObjectId': 'slide_title',
                    'size': {'height': {'magnitude': 50, 'unit': 'PT'}, 'width': {'magnitude': 620, 'unit': 'PT'}},
                    'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 50, 'translateY': 250, 'unit': 'PT'}
                }
            }
        }
    ]
    
    # Loop through slides data to create slides and shapes
    for idx, slide in enumerate(slides):
        slide_id = f"slide_data_{idx}"
        title_box_id = f"box_data_title_{idx}"
        bullets_box_id = f"box_bullets_{idx}"
        
        data_matrix = slide.get('data', [])
        rows = len(data_matrix)
        table_height = max(50, rows * 30)
        
        # Create Slide
        requests.append({
            'createSlide': {
                'objectId': slide_id,
                'slideLayoutReference': {'predefinedLayout': 'BLANK'}
            }
        })
        
        # Add Title Shape
        requests.append({
            'createShape': {
                'objectId': title_box_id,
                'shapeType': 'TEXT_BOX',
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {'height': {'magnitude': 50, 'unit': 'PT'}, 'width': {'magnitude': 800, 'unit': 'PT'}},
                    'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 50, 'translateY': 30, 'unit': 'PT'}
                }
            }
        })
        
        # Add Chart if available
        chart_info = slide_charts.get(idx)
        if chart_info:
            requests.append({
                'createSheetsChart': {
                    'objectId': f"chart_{idx}",
                    'spreadsheetId': chart_info['spreadsheet_id'],
                    'chartId': chart_info['chart_id'],
                    'linkingMode': 'LINKED',
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {'height': {'magnitude': 200, 'unit': 'PT'}, 'width': {'magnitude': 300, 'unit': 'PT'}},
                        'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 370, 'translateY': 100, 'unit': 'PT'}
                    }
                }
            })
            bullets_translate_y = 100 + max(table_height, 200) + 20
        else:
            bullets_translate_y = 100 + table_height + 30
            
        # Add Bullets Shape if provided
        bullets = slide.get('bullets', [])
        if bullets:
            requests.append({
                'createShape': {
                    'objectId': bullets_box_id,
                    'shapeType': 'TEXT_BOX',
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {'height': {'magnitude': 150, 'unit': 'PT'}, 'width': {'magnitude': 620, 'unit': 'PT'}},
                        'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 50, 'translateY': bullets_translate_y, 'unit': 'PT'}
                    }
                }
            })
            
    # Execute all slide and shape creations
    slides_service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={'requests': requests}
    ).execute()
    
    # Now insert text and tables
    text_requests = [
        {'insertText': {'objectId': 'box_main_title', 'text': presentation_title, 'insertionIndex': 0}},
        {'insertText': {'objectId': 'box_ai_hint', 'text': "Generated by Conversational Analytics Bot", 'insertionIndex': 0}}
    ]
    
    for idx, slide in enumerate(slides):
        slide_id = f"slide_data_{idx}"
        title_box_id = f"box_data_title_{idx}"
        bullets_box_id = f"box_bullets_{idx}"
        table_id = f"table_data_{idx}"
        
        slide_title = slide.get('title', f"Slide {idx+1}")
        data_matrix = slide.get('data', [])
        rows = len(data_matrix)
        cols = len(data_matrix[0]) if rows > 0 else 0
        table_height = max(50, rows * 30)
        
        # Insert Title Text
        text_requests.append({'insertText': {'objectId': title_box_id, 'text': slide_title, 'insertionIndex': 0}})
        text_requests.append({
            'updateTextStyle': {
                'objectId': title_box_id,
                'style': {'fontSize': {'magnitude': 18, 'unit': 'PT'}, 'bold': True},
                'fields': 'fontSize,bold'
            }
        })
        
        # Insert Bullets Text if provided
        bullets = slide.get('bullets', [])
        if bullets:
            bullet_text = "Key Takeaways:\n" + "\n".join([f"• {b}" for b in bullets])
            text_requests.append({'insertText': {'objectId': bullets_box_id, 'text': bullet_text, 'insertionIndex': 0}})
            text_requests.append({
                'updateTextStyle': {
                    'objectId': bullets_box_id,
                    'style': {'fontSize': {'magnitude': 14, 'unit': 'PT'}},
                    'fields': 'fontSize'
                }
            })
            
        # Create and Fill Table
        if rows > 0 and cols > 0:
            chart_info = slide_charts.get(idx)
            table_width = 300 if chart_info else 620
            
            table_requests = [{
                'createTable': {
                    'objectId': table_id,
                    'elementProperties': {
                        'pageObjectId': slide_id,
                        'size': {'height': {'magnitude': table_height, 'unit': 'PT'}, 'width': {'magnitude': table_width, 'unit': 'PT'}},
                        'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': 50, 'translateY': 100, 'unit': 'PT'}
                    },
                    'rows': rows,
                    'columns': cols
                }
            }]
            
            slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': table_requests}
            ).execute()
            
            # Center text in cells
            center_request = [{
                'updateTableCellProperties': {
                    'objectId': table_id,
                    'tableRange': {'location': {'rowIndex': 0, 'columnIndex': 0}, 'rowSpan': rows, 'columnSpan': cols},
                    'tableCellProperties': {'contentAlignment': 'MIDDLE'},
                    'fields': 'contentAlignment'
                }
            }]
            slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': center_request}
            ).execute()
            
            # Fill Table Text
            fill_requests = []
            for row_idx, row in enumerate(data_matrix):
                for col_idx, val in enumerate(row):
                    fill_requests.append({
                        'insertText': {
                            'objectId': table_id,
                            'cellLocation': {'rowIndex': row_idx, 'columnIndex': col_idx},
                            'text': str(val),
                            'insertionIndex': 0
                        }
                    })
            text_requests.extend(fill_requests)
            
    # Execute all text insertions
    if text_requests:
        slides_service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': text_requests}
        ).execute()
        
    return f"Presentation '{presentation_title}' created successfully with {len(slides)} data slides! Open it here: https://docs.google.com/presentation/d/{presentation_id}/edit"


if __name__ == "__main__":
    mcp.run(transport="stdio")
