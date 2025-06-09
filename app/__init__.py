from flask import Flask
import os

def create_app():
    app = Flask(__name__)
    from app.views import products_bp
    app.register_blueprint(products_bp)

    return app