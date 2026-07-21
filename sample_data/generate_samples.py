"""
Generates synthetic industrial sample documents for testing the ingestion pipeline.
Deliberately reuses equipment tags (P-204, B-102, V-310) across formats so the
knowledge graph visibly cross-links them - this is the core demo proof point.

Run inside the backend container (has PyMuPDF, Pillow, pandas, openpyxl already installed):
    docker compose exec backend python3 /app/sample_data/generate_samples.py
"""
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT = Path(__file__).parent


def pdf_page_with_text(doc, title, body_lines, fontsize=11):
    page = doc.new_page()
    y = 60
    page.insert_text((50, y), title, fontsize=16, fontname="helv")
    y += 30
    for line in body_lines:
        if line == "":
            y += 10
            continue
        page.insert_text((50, y), line, fontsize=fontsize, fontname="helv")
        y += 18
    return page


def make_pump_procedure():
    doc = fitz.open()
    pdf_page_with_text(doc, "Pump P-204 Preventive Maintenance Procedure", [
        "Equipment Tag: P-204 (Centrifugal Pump)",
        "Location: Process Area 3, Unit 200",
        "Standard Reference: OISD-STD-105",
        "Prepared by: Rajesh Kumar, Maintenance Engineer",
        "Approved Date: 2026-01-10",
        "",
        "1. SAFETY PRECAUTIONS",
        "   - Obtain lockout-tagout (LOTO) permit before starting work.",
        "   - Wear PPE: safety glasses, gloves, steel-toe boots.",
        "   - Verify pump is isolated from process and depressurized.",
        "",
        "2. PROCEDURE",
        "   Step 1: Isolate electrical power at MCC and apply LOTO.",
        "   Step 2: Inspect mechanical seal for leaks or wear.",
        "   Step 3: Check vibration readings against baseline (max 4.5 mm/s RMS).",
        "   Step 4: Lubricate bearings per OEM schedule.",
        "   Step 5: Verify shaft alignment within 0.05mm tolerance.",
        "   Step 6: Remove LOTO and restart pump; confirm normal operation.",
        "",
        "3. NEXT SCHEDULED MAINTENANCE",
        "   Next inspection due: 2026-07-10",
        "   Reference work order: WO-2039",
    ])
    doc.save(OUT / "pdf" / "pump_maintenance_procedure.pdf")
    doc.close()


def make_boiler_inspection():
    doc = fitz.open()
    pdf_page_with_text(doc, "Boiler B-102 Annual Shutdown Inspection Report", [
        "Equipment Tag: B-102 (Package Boiler)",
        "Inspected by: Priya Sharma, Inspection Engineer",
        "Inspection Date: 2026-03-10",
        "Standard Reference: PESO / Indian Boiler Regulations (IBR)",
        "Related Work Order: WO-2041",
        "",
        "1. SCOPE",
        "   Annual internal and external shutdown inspection covering shell,",
        "   tubes, safety valves, and refractory.",
        "",
        "2. FINDINGS",
        "   - Minor surface corrosion observed on external shell (non-critical).",
        "   - Tube wall thickness measured within acceptable limits (min 4.2mm).",
        "   - Safety relief valve tested and set-pressure verified at 10.5 bar.",
        "   - Refractory lining in good condition, no spalling observed.",
        "   - No evidence of tube leakage or scaling beyond normal limits.",
        "",
        "3. RECOMMENDATIONS",
        "   - Repaint external shell surface within 3 months.",
        "   - Continue current water treatment program.",
        "   - Re-inspect per statutory schedule in 12 months (2027-03-10).",
        "",
        "4. SIGN-OFF",
        "   Inspector: Priya Sharma        Date: 2026-03-10",
        "   Approved by: Rajesh Kumar, Maintenance Engineer",
    ])
    doc.save(OUT / "pdf" / "boiler_inspection_report.pdf")
    doc.close()


def make_work_orders_spreadsheet():
    work_orders = pd.DataFrame([
        {"WorkOrderID": "WO-2038", "AssetTag": "V-310", "Description": "Valve actuator replacement",
         "ReportedBy": "Amit Verma", "AssignedTo": "Suresh Nair", "Status": "Closed",
         "OpenDate": "2025-11-02", "CloseDate": "2025-11-05", "Priority": "Medium"},
        {"WorkOrderID": "WO-2039", "AssetTag": "P-204", "Description": "Preventive maintenance - seal and bearing check",
         "ReportedBy": "Rajesh Kumar", "AssignedTo": "Suresh Nair", "Status": "Closed",
         "OpenDate": "2026-01-08", "CloseDate": "2026-01-10", "Priority": "Medium"},
        {"WorkOrderID": "WO-2040", "AssetTag": "P-204", "Description": "Vibration alarm investigation",
         "ReportedBy": "Shift Operator", "AssignedTo": "Rajesh Kumar", "Status": "Open",
         "OpenDate": "2026-02-14", "CloseDate": "", "Priority": "High"},
        {"WorkOrderID": "WO-2041", "AssetTag": "B-102", "Description": "Annual shutdown inspection",
         "ReportedBy": "Priya Sharma", "AssignedTo": "Priya Sharma", "Status": "Closed",
         "OpenDate": "2026-03-08", "CloseDate": "2026-03-10", "Priority": "High"},
        {"WorkOrderID": "WO-2042", "AssetTag": "B-102", "Description": "External shell repainting",
         "ReportedBy": "Priya Sharma", "AssignedTo": "Contractor - CoatTech", "Status": "Open",
         "OpenDate": "2026-03-11", "CloseDate": "", "Priority": "Low"},
        {"WorkOrderID": "WO-2043", "AssetTag": "C-501", "Description": "Compressor oil change",
         "ReportedBy": "Amit Verma", "AssignedTo": "Suresh Nair", "Status": "Closed",
         "OpenDate": "2026-01-20", "CloseDate": "2026-01-20", "Priority": "Low"},
    ])

    spare_parts = pd.DataFrame([
        {"PartNumber": "SK-P204-01", "Description": "Mechanical seal kit for P-204", "UsedInWorkOrder": "WO-2039", "Quantity": 1},
        {"PartNumber": "BRG-P204-02", "Description": "Bearing set for P-204", "UsedInWorkOrder": "WO-2039", "Quantity": 2},
        {"PartNumber": "RV-B102-01", "Description": "Safety relief valve service kit for B-102", "UsedInWorkOrder": "WO-2041", "Quantity": 1},
        {"PartNumber": "ACT-V310-01", "Description": "Pneumatic actuator for V-310", "UsedInWorkOrder": "WO-2038", "Quantity": 1},
    ])

    with pd.ExcelWriter(OUT / "spreadsheets" / "work_orders.xlsx", engine="openpyxl") as writer:
        work_orders.to_excel(writer, sheet_name="WorkOrders", index=False)
        spare_parts.to_excel(writer, sheet_name="SparePartsUsage", index=False)


def make_nameplate_image():
    img = Image.new("RGB", (560, 340), color="white")
    d = ImageDraw.Draw(img)
    d.rectangle([15, 15, 545, 325], outline="black", width=4)
    d.rectangle([15, 15, 545, 60], fill="#1E3A8A")
    d.text((30, 28), "EQUIPMENT NAMEPLATE", fill="white")
    lines = [
        "Equipment Tag: B-102",
        "Type: Package Boiler",
        "Manufacturer: Cleaver-Brooks",
        "Model: CB-700-HP",
        "Serial Number: SN-88213",
        "Max Operating Pressure: 10.5 Bar",
        "Fuel Type: Natural Gas",
        "Year Manufactured: 2019",
        "Statutory Body: PESO / IBR Registered",
    ]
    y = 85
    for line in lines:
        d.text((35, y), line, fill="black")
        y += 26
    img.save(OUT / "images" / "equipment_nameplate.png")


def make_pid_diagram_image():
    img = Image.new("RGB", (700, 420), color="white")
    d = ImageDraw.Draw(img)

    def box(xy, label, fill="#E0F2FE"):
        d.rectangle(xy, outline="black", width=2, fill=fill)
        cx = (xy[0] + xy[2]) // 2
        cy = (xy[1] + xy[3]) // 2
        d.text((xy[0] + 10, cy - 6), label, fill="black")

    d.text((20, 15), "Process Area 3 - Simplified P&ID", fill="black")

    box((40, 70, 180, 130), "T-100\nFeed Tank")
    box((240, 70, 380, 130), "P-204\nCentrifugal Pump")
    box((440, 70, 580, 130), "V-310\nControl Valve")
    box((240, 220, 380, 280), "B-102\nPackage Boiler")

    # Arrows / connecting lines
    d.line([180, 100, 240, 100], fill="black", width=3)
    d.line([380, 100, 440, 100], fill="black", width=3)
    d.line([580, 100, 620, 100], fill="black", width=3)
    d.line([620, 100, 620, 250], fill="black", width=3)
    d.line([620, 250, 380, 250], fill="black", width=3)
    d.line([310, 130, 310, 220], fill="black", width=3)

    d.text((20, 340), "Flow: T-100 -> P-204 -> V-310 -> B-102 (feedwater supply loop)", fill="black")
    d.text((20, 365), "Tag references: P-204, V-310, B-102", fill="black")

    img.save(OUT / "images" / "simple_pid_diagram.png")


if __name__ == "__main__":
    make_pump_procedure()
    make_boiler_inspection()
    make_work_orders_spreadsheet()
    make_nameplate_image()
    make_pid_diagram_image()
    print("Generated sample documents in", OUT)
