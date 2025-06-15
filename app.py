import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = os.environ.get("SESSION_SECRET")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Database configuration with fallback
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        # Fallback to replit.db for development
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pharmacy.db"
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Import models
    from models import User, Pharmacy, Drug, Sale, Customer, Expense, License, Payment
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Create tables
    with app.app_context():
        db.create_all()
        
        # Create superadmin user if not exists
        superadmin = User.query.filter_by(email='admin@comolor.com').first()
        if not superadmin:
            from werkzeug.security import generate_password_hash
            superadmin = User(
                email='admin@comolor.com',
                password_hash=generate_password_hash('admin123'),
                role='superadmin',
                first_name='Super',
                last_name='Admin'
            )
            db.session.add(superadmin)
            db.session.commit()
            logging.info("Superadmin user created")
    
    # Initialize system configurations
    with app.app_context():
        from models import SystemConfiguration
        default_configs = [
            ('license_price', '3000', 'Monthly license price in KES'),
            ('mpesa_till', '123456', 'Official M-PESA Till Number'),
            ('system_name', 'Comolor Pharmacy', 'System display name'),
            ('allow_registrations', 'true', 'Allow new pharmacy registrations'),
            ('license_duration_days', '30', 'License duration in days'),
            ('terms_conditions', '''# Comolor Pharmacy Management System - Terms and Conditions

## 1. Service Agreement
By registering for Comolor Pharmacy Management System, you agree to pay the monthly licensing fee of KES 3,000.

## 2. Payment Terms
- Monthly license fee: KES 3,000
- Payment via M-PESA to Till Number: 123456
- License expires 30 days from activation
- No refunds for partial months

## 3. System Usage
- One pharmacy per license
- Responsible for data backup
- Must comply with Kenyan pharmacy regulations

## 4. Support
For technical support, contact: support@comolor.com

## 5. Termination
We reserve the right to suspend accounts for non-payment or misuse.''', 'System terms and conditions')
        ]
        
        for key, value, description in default_configs:
            existing = SystemConfiguration.query.filter_by(key=key).first()
            if not existing:
                config = SystemConfiguration()
                config.key = key
                config.value = value
                config.description = description
                db.session.add(config)
        
        db.session.commit()
        logging.info("System configurations initialized")
    
    # Register blueprints
    from blueprints.main import main_bp
    from blueprints.auth import auth_bp
    from blueprints.inventory import inventory_bp
    from blueprints.sales import sales_bp
    from blueprints.customers import customers_bp
    from blueprints.reports import reports_bp
    from blueprints.expenses import expenses_bp
    from blueprints.settings import settings_bp
    from blueprints.admin import admin_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(sales_bp, url_prefix='/sales')
    app.register_blueprint(customers_bp, url_prefix='/customers')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(expenses_bp, url_prefix='/expenses')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    return app

# Create the app instance
app = create_app()
