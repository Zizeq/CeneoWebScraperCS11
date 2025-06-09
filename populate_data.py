from app.models import Product
import os

product_ids_to_extract = ["39562616"]

for p_id in product_ids_to_extract:
    print(f"Processing product ID: {p_id}")
    product = Product(p_id)
    if product.extract_name():
        print(f"Found product: {product.product_name}. Extracting opinions...")
        product.extract_opinions()
        product.analyze()
        product.export_info()
        product.export_opinions()
        print(f"Successfully processed and saved data for {product.product_name}.")
    else:
        print(f"Could not find product or no opinions for ID: {p_id}.")
    print("-" * 30)