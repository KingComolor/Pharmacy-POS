from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from auth import license_required, same_pharmacy_required, role_required
from models import Sale, SaleItem, Drug, Expense
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, and_

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/')
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def index():
    """Reports dashboard"""
    return render_template('reports/index.html')

@reports_bp.route('/sales')
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def sales_report():
    """Sales report"""
    period = request.args.get('period', 'today')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Calculate date range
    if period == 'today':
        start_date = datetime.utcnow().date()
        end_date = start_date
    elif period == 'week':
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=7)
    elif period == 'month':
        end_date = datetime.utcnow().date()
        start_date = end_date.replace(day=1)
    elif period == 'custom' and date_from and date_to:
        try:
            start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            start_date = datetime.utcnow().date()
            end_date = start_date
    else:
        start_date = datetime.utcnow().date()
        end_date = start_date
    
    # Sales summary
    sales_query = Sale.query.filter(
        Sale.pharmacy_id == current_user.pharmacy_id,
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    )
    
    total_sales = sales_query.count()
    total_revenue = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.pharmacy_id == current_user.pharmacy_id,
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0
    
    # Payment method breakdown
    payment_breakdown = db.session.query(
        Sale.payment_method,
        func.count(Sale.id).label('count'),
        func.sum(Sale.total_amount).label('total')
    ).filter(
        Sale.pharmacy_id == current_user.pharmacy_id,
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(Sale.payment_method).all()
    
    # Top selling drugs
    top_drugs = db.session.query(
        Drug.name,
        func.sum(SaleItem.quantity).label('total_quantity'),
        func.sum(SaleItem.total_price).label('total_sales')
    ).join(SaleItem).join(Sale).filter(
        Sale.pharmacy_id == current_user.pharmacy_id,
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(Drug.id, Drug.name).order_by(
        func.sum(SaleItem.total_price).desc()
    ).limit(10).all()
    
    # Daily sales (for chart)
    daily_sales = db.session.query(
        func.date(Sale.created_at).label('date'),
        func.sum(Sale.total_amount).label('total')
    ).filter(
        Sale.pharmacy_id == current_user.pharmacy_id,
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(func.date(Sale.created_at)).order_by(
        func.date(Sale.created_at)
    ).all()
    
    return render_template('reports/sales_report.html',
                         period=period,
                         start_date=start_date,
                         end_date=end_date,
                         total_sales=total_sales,
                         total_revenue=total_revenue,
                         payment_breakdown=payment_breakdown,
                         top_drugs=top_drugs,
                         daily_sales=daily_sales,
                         date_from=date_from,
                         date_to=date_to)

@reports_bp.route('/profit-loss')
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def profit_loss():
    """Profit and loss report"""
    period = request.args.get('period', 'month')
    
    # Calculate date range
    if period == 'month':
        end_date = datetime.utcnow().date()
        start_date = end_date.replace(day=1)
    elif period == 'quarter':
        end_date = datetime.utcnow().date()
        quarter_start_month = ((end_date.month - 1) // 3) * 3 + 1
        start_date = end_date.replace(month=quarter_start_month, day=1)
    elif period == 'year':
        end_date = datetime.utcnow().date()
        start_date = end_date.replace(month=1, day=1)
    else:
        end_date = datetime.utcnow().date()
        start_date = end_date.replace(day=1)
    
    # Revenue
    revenue = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.pharmacy_id == current_user.pharmacy_id,
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0
    
    # Cost of goods sold
    cogs = db.session.query(func.sum(
        SaleItem.quantity * Drug.purchase_price
    )).join(Drug).join(Sale).filter(
        Sale.pharmacy_id == current_user.pharmacy_id,
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0
    
    # Expenses
    expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.pharmacy_id == current_user.pharmacy_id,
        Expense.date >= start_date,
        Expense.date <= end_date
    ).scalar() or 0
    
    # Calculations
    gross_profit = revenue - cogs
    net_profit = gross_profit - expenses
    gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0
    net_margin = (net_profit / revenue * 100) if revenue > 0 else 0
    
    # Expense breakdown
    expense_breakdown = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('total')
    ).filter(
        Expense.pharmacy_id == current_user.pharmacy_id,
        Expense.date >= start_date,
        Expense.date <= end_date
    ).group_by(Expense.category).all()
    
    return render_template('reports/profit_loss.html',
                         period=period,
                         start_date=start_date,
                         end_date=end_date,
                         revenue=revenue,
                         cogs=cogs,
                         expenses=expenses,
                         gross_profit=gross_profit,
                         net_profit=net_profit,
                         gross_margin=gross_margin,
                         net_margin=net_margin,
                         expense_breakdown=expense_breakdown)

@reports_bp.route('/expiring-drugs')
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def expiring_drugs():
    """Expiring drugs report"""
    days = request.args.get('days', 30, type=int)
    
    cutoff_date = datetime.utcnow().date() + timedelta(days=days)
    
    expiring_drugs = Drug.query.filter(
        Drug.pharmacy_id == current_user.pharmacy_id,
        Drug.expiry_date <= cutoff_date,
        Drug.expiry_date >= datetime.utcnow().date(),
        Drug.quantity > 0
    ).order_by(Drug.expiry_date).all()
    
    # Calculate total value of expiring drugs
    total_value = sum(drug.quantity * drug.purchase_price for drug in expiring_drugs)
    
    return render_template('reports/expiring_drugs.html',
                         expiring_drugs=expiring_drugs,
                         days=days,
                         total_value=total_value)

@reports_bp.route('/stock-valuation')
@login_required
@license_required
@same_pharmacy_required
@role_required('admin', 'pharmacist')
def stock_valuation():
    """Stock valuation report"""
    category = request.args.get('category', '')
    
    query = Drug.query.filter_by(pharmacy_id=current_user.pharmacy_id)
    
    if category:
        query = query.filter_by(category=category)
    
    drugs = query.filter(Drug.quantity > 0).all()
    
    # Calculate values
    total_purchase_value = sum(drug.quantity * drug.purchase_price for drug in drugs)
    total_selling_value = sum(drug.quantity * drug.selling_price for drug in drugs)
    potential_profit = total_selling_value - total_purchase_value
    
    # Category breakdown
    category_breakdown = db.session.query(
        Drug.category,
        func.sum(Drug.quantity * Drug.purchase_price).label('purchase_value'),
        func.sum(Drug.quantity * Drug.selling_price).label('selling_value'),
        func.count(Drug.id).label('drug_count')
    ).filter(
        Drug.pharmacy_id == current_user.pharmacy_id,
        Drug.quantity > 0
    ).group_by(Drug.category).all()
    
    # Get categories for filter
    categories = db.session.query(Drug.category).filter_by(
        pharmacy_id=current_user.pharmacy_id
    ).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    return render_template('reports/stock_valuation.html',
                         drugs=drugs,
                         total_purchase_value=total_purchase_value,
                         total_selling_value=total_selling_value,
                         potential_profit=potential_profit,
                         category_breakdown=category_breakdown,
                         categories=categories,
                         selected_category=category)
