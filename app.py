from flask import Flask, render_template, request, url_for, redirect, jsonify
from pathlib import Path
import qrcode
import pandas as pd
import os
import traceback
import pathlib
import imgkit
from brother_ql.raster import BrotherQLRaster
from brother_ql.backends.helpers import send
from brother_ql.conversion import convert

app = Flask(__name__)

# Paths
BASE_DIR = pathlib.Path(__file__).parent.resolve()
EXCEL_DB_PATH = os.path.join(BASE_DIR, 'RESMED_DATABASE_060525.xlsx')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
SKU_DIR = os.path.join(STATIC_DIR, 'sku')
SERIAL_DIR = os.path.join(STATIC_DIR, 'serialno')
LABEL_DIR = os.path.join(STATIC_DIR, 'label')

# Ensure directories exist
os.makedirs(SKU_DIR, exist_ok=True)
os.makedirs(SERIAL_DIR, exist_ok=True)
os.makedirs(LABEL_DIR, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/lmt/', methods=['POST'])
def lmt():
    try:
        # Get barcode from form
        barcode = request.form['barcode']
        
        # Extract GTIN and tracking info
        UDI_trimmed = barcode[4:]
        gtin_from_udi = int(UDI_trimmed[:12])
        item_type_length = len(barcode)

        # Load Excel database
        df = pd.read_excel(EXCEL_DB_PATH)
        df = pd.read_excel(EXCEL_DB_PATH)
        df['RESMED GTIN'] = pd.to_numeric(df['RESMED GTIN'], errors='coerce')
        df.dropna(subset=['RESMED GTIN'], inplace=True)
        df['RESMED GTIN'] = df['RESMED GTIN'].astype(int)

        row = df[df['RESMED GTIN'] == gtin_from_udi]
        
        if row.empty:
            raise ValueError(f"GTIN {gtin_from_udi} not found in the database.")

        # Extract product details
        product_type = row.iloc[0]['ITEM TRACKING CODE']
        product_sku = str(row.iloc[0]['RESMED SKU'])
        product_name = row.iloc[0]['RESMED DESCRIPTION']

        # Determine serial or lot number
        if item_type_length == 33:
            tracking_value = barcode[-7:]
        elif item_type_length > 33:
            tracking_value = barcode[-11:]
        else:
            raise ValueError("Invalid UDI length.")

        # Generate QR codes
        sku_path = os.path.join(SKU_DIR, f"{product_sku}.png")
        serial_path = os.path.join(SERIAL_DIR, f"{tracking_value}.png")
        generate_qr_code(product_sku, sku_path)
        generate_qr_code(tracking_value, serial_path)

        # Render the label image
        template_string = render_template(
            'lmtresults.html',
            product_name=product_name,
            product_sku=product_sku,
            serialno=tracking_value,
            sku_url=f'/static/sku/{product_sku}.png',
            serialno_url=f'/static/serialno/{tracking_value}.png'
        )

        label_path = os.path.join(LABEL_DIR, f"{barcode}.png")
        imgkit.from_string(template_string, label_path, options={
            "enable-local-file-access": "",
            "crop-h": "696",
            "crop-w": "271"
        })

        # Print label (optional, can be commented out if not needed)
        backend = 'pyusb'
        model = 'QL-800'
        printer = 'usb://0x04f9:0x209b'
        qlr = BrotherQLRaster(model)
        qlr.exception_on_warning = True

        instructions = convert(
            qlr=qlr,
            images=[label_path],
            label='62x29',
            rotate='90',
            threshold=70.0,
            dither=False,
            compress=False,
            red=False,
            dpi_600=False,
            hq=True,
            cut=True
        )

        send(instructions=instructions, printer_identifier=printer, backend_identifier=backend, blocking=True)

        return render_template('lmtresults.html', product_name=product_name, product_sku=product_sku, serialno=tracking_value, sku_url=f'/static/sku/{product_sku}.png', serialno_url=f'/static/serialno/{tracking_value}.png')

    except Exception as e:
        error_message = traceback.format_exc()
        print(error_message)
        return render_template('lmterror.html', error_message=error_message), 500

@app.route('/lmtpreview/', methods=['POST'])
def lmtpreview():
    try:
        barcode = request.form['barcode']
        UDI_trimmed = barcode[4:]
        gtin_from_udi = int(UDI_trimmed[:12])

        df = pd.read_excel(EXCEL_DB_PATH)
        df['RESMED GTIN'] = df['RESMED GTIN'].astype(int)
        row = df[df['RESMED GTIN'] == gtin_from_udi]

        if row.empty:
            raise ValueError(f"GTIN {gtin_from_udi} not found in the database.")

        product_name = row.iloc[0]['RESMED DESCRIPTION']
        product_sku = str(row.iloc[0]['RESMED SKU'])

        return jsonify({
            "product_name": product_name,
            "product_sku": product_sku,
            "sku_url": url_for('static', filename=f'sku/{product_sku}.png'),
            "serialno_url": url_for('static', filename=f'serialno/{product_sku}.png')
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/lmtclear/', methods=['POST'])
def lmtclear():
    for folder in [SKU_DIR, SERIAL_DIR, LABEL_DIR]:
        for file in Path(folder).glob('*'):
            if file.is_file():
                file.unlink()
    return jsonify({"message": "All labels cleared successfully."})

def generate_qr_code(data, output_path):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    img.save(output_path)

if __name__ == '__main__':
    app.run(debug=True)
