from flask import Flask, render_template, request, url_for, redirect
from pathlib import Path
import qrcode
import pandas as pd
from brother_ql.raster import BrotherQLRaster
from brother_ql.backends.helpers import send
from brother_ql.conversion import convert
import imgkit
import pathlib
import traceback

app = Flask(__name__)

EXCEL_DB_PATH = r"C:\Users\TAS Xavier\Downloads\RESMED_DATABASE_060525.xlsx"

@app.route('/')
def index():
    return render_template('lmtform.html')

@app.route('/lmt/', methods=['GET', 'POST'])
def lmt():
    if request.method == 'POST':
        try:
            fp = pathlib.Path(__file__).parent.resolve()
            barcode = request.form['barcode']

            # Trim UDI
            UDI_trimmed = barcode[4:]
            gtin_from_udi = int(UDI_trimmed[0:12])
            item_type_length = len(barcode)

            # Load and filter Excel
            df = pd.read_excel(EXCEL_DB_PATH)
            df['RESMED GTIN'] = df['RESMED GTIN'].astype(int)
            row = df[df['RESMED GTIN'] == gtin_from_udi]

            if row.empty:
                raise ValueError(f"GTIN {gtin_from_udi} not found in database.")

            product_type = row.iloc[0]['ITEM TRACKING CODE']
            product_sku = str(row.iloc[0]['RESMED SKU'])  # Updated to RESMED SKU
            product_name = row.iloc[0]['RESMED DESCRIPTION']  # Updated to RESMED DESCRIPTION

            # Serial or Lot logic
            if item_type_length == 33:
                tracking_value = barcode[-7:]
            elif item_type_length > 33:
                tracking_value = barcode[-11:]
            else:
                raise ValueError("Invalid UDI length.")

            # Generate QR codes
            generate_qr_code(product_sku, f'./static/sku/{product_sku}.png')
            generate_qr_code(tracking_value, f'./static/serialno/{tracking_value}.png')
            sku_url = f'{fp}/static/sku/{product_sku}.png'
            serialno_url = f'{fp}/static/serialno/{tracking_value}.png'

            # Printer setup
            backend = 'pyusb'
            model = 'QL-800'
            printer = 'usb://0x04f9:0x209b'
            qlr = BrotherQLRaster(model)
            qlr.exception_on_warning = True

            # Render label
            template_string = render_template(
                'lmtresults.html',
                product_name=product_name,
                product_sku=product_sku,
                serialno=tracking_value,
                sku_url=sku_url,
                serialno_url=serialno_url
            )

            label_path = f'./static/label/{barcode}.png'
            imgkit.from_string(template_string, label_path, options={
                "enable-local-file-access": "",
                "crop-h": "696",
                "crop-w": "271"
            })

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
            return render_template('lmtform.html')

        except Exception:
            error_message = traceback.format_exc()
            print(error_message)
            return f"<pre>{error_message}</pre>"

@app.route('/lmtpreview/', methods=['POST'])
def lmtpreview():
    if request.method == 'POST':
        try:
            barcode = request.form['barcode']
            UDI_trimmed = barcode[4:]
            gtin_from_udi = int(UDI_trimmed[0:12])
            item_type_length = len(barcode)

            df = pd.read_excel(EXCEL_DB_PATH)
            df['RESMED GTIN'] = df['RESMED GTIN'].astype(int)
            row = df[df['RESMED GTIN'] == gtin_from_udi]

            if row.empty:
                raise ValueError(f"GTIN {gtin_from_udi} not found in database.")

            product_type = row.iloc[0]['ITEM TRACKING CODE']
            product_sku = str(row.iloc[0]['RESMED SKU'])  # Updated to RESMED SKU
            product_name = row.iloc[0]['RESMED DESCRIPTION']  # Updated to RESMED DESCRIPTION

            if item_type_length == 33:
                tracking_value = barcode[-7:]
            elif item_type_length > 33:
                tracking_value = barcode[-11:]
            else:
                raise ValueError("Invalid UDI length.")

            generate_qr_code(product_sku, f'./static/sku/{product_sku}.png')
            generate_qr_code(tracking_value, f'./static/serialno/{tracking_value}.png')

            sku_url = url_for('static', filename=f'sku/{product_sku}.png')
            serialno_url = url_for('static', filename=f'serialno/{tracking_value}.png')

            return render_template(
                'lmtresults.html',
                product_name=product_name,
                product_sku=product_sku,
                serialno=tracking_value,
                sku_url=sku_url,
                serialno_url=serialno_url
            )

        except Exception:
            ex = traceback.format_exc()
            return render_template('lmterror.html', error_message=ex)

    return render_template('lmtform.html')

@app.route('/lmtclear/', methods=['POST'])
def lmtclear():
    if request.method == 'POST':
        sku_folder = Path('./static/sku/')
        for file in sku_folder.glob('*'):
            if file.is_file() and file.name != '.gitkeep':
                file.unlink()

        serialno_folder = Path('./static/serialno/')
        for file in serialno_folder.glob('*'):
            if file.is_file() and file.name != '.gitkeep':
                file.unlink()

    return redirect('/lmt')

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
    return img

if __name__ == '__main__':
    app.run(debug=True)
