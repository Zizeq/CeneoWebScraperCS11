from flask import Blueprint, render_template, redirect, url_for, request, send_file, Response
import os
import json
import io
import pandas as pd
from app.forms import ExtractForm
from app.models import Product, Opinion

products_bp = Blueprint('products', __name__)

@products_bp.route("/")
def index():
    return render_template("index.html")

@products_bp.route("/extract", methods=['GET'])
def render_form():
    form = ExtractForm()
    return render_template("extract.html", form=form)

@products_bp.route("/extract", methods=['POST'])
def extract():
    form = ExtractForm(request.form)
    if form.validate():
        product_id = form.product_id.data
        product = Product(product_id)
        if product.extract_name():
            product.extract_opinions()
            product.analyze()
            product.export_info()
            product.export_opinions()
            return redirect(url_for('products.product_detail_page', product_id=product_id))
        form.product_id.errors.append('There is no product for provided id or product has no opinions')
        return render_template('extract.html', form=form)
    return render_template('extract.html', form=form)


@products_bp.route("/products")
def product_list_page():
    products_data = []
    products_dir = os.path.join(os.path.dirname(__file__), 'data', 'products')

    if os.path.exists(products_dir):
        for filename in os.listdir(products_dir):
            if filename.endswith(".json"):
                product_id = filename.replace(".json", "")
                product = Product(product_id)
                try:
                    product.import_info()
                    products_data.append(product)
                except FileNotFoundError:
                    print(f"DEBUG: Info file not found for product {product_id}. Skipping.")
                except json.JSONDecodeError:
                    print(f"DEBUG: Error decoding JSON for product {product_id}. Skipping.")
    return render_template("products.html", products=products_data)

@products_bp.route("/products/<product_id>")
def product_detail_page(product_id):
    product = Product(product_id)
    try:
        product.import_info()
        product.import_opinions()
    except FileNotFoundError:
        return "Product or opinions not found", 404
    except json.JSONDecodeError:
        return "Error loading product data.", 500
    return render_template("product.html", product=product)

@products_bp.route("/download/<product_id>/<file_format>")
def download_opinions(product_id, file_format):
    product = Product(product_id)
    try:
        product.import_info()
        product.import_opinions()
    except FileNotFoundError:
        return "Product or opinions not found for download.", 404
    except json.JSONDecodeError:
        return "Error loading product data for download.", 500
    
    opinions_data = [opinion.transform_to_dict() for opinion in product.opinions]
    df = pd.DataFrame(opinions_data)

    if file_format == 'csv':
        buffer = io.BytesIO()
        df.to_csv(buffer, index=False, encoding='utf-8')
        buffer.seek(0)
        return send_file(buffer, mimetype='text/csv', as_attachment=True, download_name=f"{product.product_name}_opinions.csv")
    elif file_format == 'xlsx':
        buffer = io.BytesIO()
        for col in ['pros_pl', 'pros_en', 'cons_pl', 'cons_en']:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: ', '.join(map(str, x)) if isinstance(x, list) else x if x is not None else '')

        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Opinions')
        buffer.seek(0)
        return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f"{product.product_name}_opinions.xlsx")
    elif file_format == 'json':
        json_string = json.dumps(opinions_data, indent=4, ensure_ascii=False)
        buffer = io.BytesIO(json_string.encode('utf-8'))
        return send_file(buffer, mimetype='application/json', as_attachment=True, download_name=f"{product.product_name}_opinions.json")
    else:
        return "Unsupported file format.", 400

@products_bp.route("/about")
def about():
    return render_template("about.html")