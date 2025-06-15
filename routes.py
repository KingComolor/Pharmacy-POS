# This file is intentionally left minimal as routes are organized in blueprints
from app import app

# Import all blueprints to register routes
from blueprints import main, auth, inventory, sales, customers, reports, expenses, settings, admin

# Global template filters and context processors can be added here
@app.template_filter('currency')
def currency_filter(amount):
    """Format currency for Kenyan Shillings"""
    return f"KES {amount:,.2f}"

@app.template_filter('date')
def date_filter(date):
    """Format date"""
    if date:
        return date.strftime('%d/%m/%Y')
    return ''

@app.template_filter('datetime')
def datetime_filter(datetime_obj):
    """Format datetime"""
    if datetime_obj:
        return datetime_obj.strftime('%d/%m/%Y %H:%M')
    return ''
