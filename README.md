Tiger_leads\Scripts\activate.bat
uvicorn src.app.main:app --reload

F:\Tiger_lead_backend\Tiger_leads\Scripts\python.exe migrate_contractor_fields.py
F:\Tiger_lead_backend\Tiger_leads\Scripts\python.exe migrate_supplier_fields.py
F:\Tiger_lead_backend\Tiger_leads\Scripts\python.exe add_user_approval_column.py

Tiger_leads\Scripts\activate.bat
Tiger_leads\Scripts\python.exe -m pip install stripe==7.8.0
uvicorn src.app.main:app --reload

