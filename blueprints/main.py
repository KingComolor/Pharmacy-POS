from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from auth import license_required, same_pharmacy_required
from models import Drug, Sale, Customer, License
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Landing page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
@license_required
@same_pharmacy_required
def dashboard():
    """Main dashboard"""
    if current_user.role == 'superadmin':
        return redirect(url_for('admin.dashboard'))
    
    pharmacy_id = current_user.pharmacy_id
    
    # Dashboard statistics
    stats = {}
    
    # Total drugs
    stats['total_drugs'] = Drug.query.filter_by(pharmacy_id=pharmacy_id).count()
    
    # Low stock drugs
    stats['low_stock'] = Drug.query.filter_by(pharmacy_id=pharmacy_id).filter(
        Drug.quantity <= Drug.reorder_level
    ).count()
    
    # Expiring drugs (next 30 days)
    thirty_days_from_now = datetime.utcnow().date() + timedelta(days=30)
    stats['expiring_drugs'] = Drug.query.filter_by(pharmacy_id=pharmacy_id).filter(
        Drug.expiry_date <= thirty_days_from_now,
        Drug.expiry_date >= datetime.utcnow().date()
    ).count()
    
    # Today's sales
    today = datetime.utcnow().date()
    today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.pharmacy_id == pharmacy_id,
        func.date(Sale.created_at) == today
    ).scalar() or 0
    stats['today_sales'] = today_sales
    
    # This month's sales
    month_start = datetime.utcnow().replace(day=1).date()
    month_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.pharmacy_id == pharmacy_id,
        func.date(Sale.created_at) >= month_start
    ).scalar() or 0
    stats['month_sales'] = month_sales
    
    # Total customers
    stats['total_customers'] = Customer.query.filter_by(pharmacy_id=pharmacy_id).count()
    
    # Recent sales
    recent_sales = Sale.query.filter_by(pharmacy_id=pharmacy_id).order_by(
        Sale.created_at.desc()
    ).limit(5).all()
    
    # Low stock alerts
    low_stock_drugs = Drug.query.filter_by(pharmacy_id=pharmacy_id).filter(
        Drug.quantity <= Drug.reorder_level
    ).limit(10).all()
    
    # Expiring drugs
    expiring_drugs = Drug.query.filter_by(pharmacy_id=pharmacy_id).filter(
        Drug.expiry_date <= thirty_days_from_now,
        Drug.expiry_date >= datetime.utcnow().date()
    ).limit(10).all()
    
    return render_template('dashboard.html',
                         stats=stats,
                         recent_sales=recent_sales,
                         low_stock_drugs=low_stock_drugs,
                         expiring_drugs=expiring_drugs)
