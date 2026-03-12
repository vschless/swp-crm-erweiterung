from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from models import Customer, Lead
from db import db
from sqlalchemy import func


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///crm.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
app.secret_key = 'your-secret-key-change-this'


def init_sample_data():
    # only seed if tables are empty (prevents duplicates on restart)
    if Customer.query.count() == 0 and Lead.query.count() == 0:
        Customer.add_customer('John Doe', 'john@example.com', 'Acme Corp', '555-0001', 'active')
        Customer.add_customer('Jane Smith', 'jane@example.com', 'Tech Solutions', '555-0002', 'prospect')
        Customer.add_customer('Bob Wilson', 'bob@example.com', 'Global Industries', '555-0003', 'inactive')

        Lead.add_lead('Alice Brown', 'alice@example.com', 'StartUp Inc', 50000, 'Website')
        Lead.add_lead('Charlie Davis', 'charlie@example.com', 'Enterprise Ltd', 100000, 'Referral')


def get_dashboard_data():
    # KPI: totals
    total_customers = Customer.query.count()
    total_leads = Lead.query.count()

    # KPI: lead value stats
    lead_value_sum = db.session.query(func.coalesce(func.sum(Lead.value), 0)).scalar()
    lead_value_avg = db.session.query(func.coalesce(func.avg(Lead.value), 0)).scalar()

    # Chart 1: customers by status
    customer_status_rows = (
        db.session.query(Customer.status, func.count(Customer.id))
        .group_by(Customer.status)
        .all()
    )
    customers_by_status = {status: count for status, count in customer_status_rows}

    # Chart 2: leads by source
    lead_source_rows = (
        db.session.query(Lead.source, func.count(Lead.id))
        .group_by(Lead.source)
        .all()
    )
    leads_by_source = {source: count for source, count in lead_source_rows}

    return {
        "total_customers": total_customers,
        "total_leads": total_leads,
        "lead_value_sum": float(lead_value_sum),
        "lead_value_avg": float(lead_value_avg),
        "customers_by_status": customers_by_status,
        "leads_by_source": leads_by_source
    }


with app.app_context():
    db.create_all()
    init_sample_data()


@app.route('/')
def index():
    dashboard_data = get_dashboard_data()
    return render_template('index.html', **dashboard_data)


@app.route('/api/dashboard')
def api_dashboard():
    return jsonify(get_dashboard_data())


@app.route('/customers')
def customers():
    return render_template('customers.html', customers=Customer.get_all_customers())


@app.route('/customers/add', methods=['GET', 'POST'])
def add_customer():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        company = request.form.get('company')
        phone = request.form.get('phone')
        status = request.form.get('status', 'prospect')

        if not all([name, email, company, phone]):
            flash('All fields are required!', 'error')
            return redirect(url_for('add_customer'))

        Customer.add_customer(name, email, company, phone, status)
        flash(f'Customer {name} added successfully!', 'success')
        return redirect(url_for('customers'))

    return render_template('add_customer.html')


@app.route('/customers/<int:customer_id>')
def customer_detail(customer_id):
    customer = Customer.get_customer_by_id(customer_id)
    if not customer:
        flash('Customer not found!', 'error')
        return redirect(url_for('customers'))
    return render_template('customer_detail.html', customer=customer)


@app.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
def edit_customer(customer_id):
    customer = Customer.get_customer_by_id(customer_id)
    if not customer:
        flash('Customer not found!', 'error')
        return redirect(url_for('customers'))

    if request.method == 'POST':
        Customer.update_customer(
            customer_id,
            request.form.get('name'),
            request.form.get('email'),
            request.form.get('company'),
            request.form.get('phone'),
            request.form.get('status')
        )
        flash('Customer updated successfully!', 'success')
        return redirect(url_for('customer_detail', customer_id=customer_id))

    return render_template('edit_customer.html', customer=customer)


@app.route('/customers/<int:customer_id>/delete', methods=['POST'])
def delete_customer(customer_id):
    Customer.delete_customer(customer_id)
    flash('Customer deleted successfully!', 'success')
    return redirect(url_for('customers'))


@app.route('/leads')
def leads():
    return render_template('leads.html', leads=Lead.get_all_leads())


@app.route('/leads/add', methods=['GET', 'POST'])
def add_lead():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        company = request.form.get('company')
        value = request.form.get('value')
        source = request.form.get('source')

        if not all([name, email, company, value, source]):
            flash('All fields are required!', 'error')
            return redirect(url_for('add_lead'))

        try:
            Lead.add_lead(name, email, company, float(value), source)
            flash(f'Lead {name} added successfully!', 'success')
        except ValueError:
            flash('Deal value must be a number!', 'error')

        return redirect(url_for('leads'))

    return render_template('add_lead.html')


@app.route('/leads/<int:lead_id>')
def lead_detail(lead_id):
    lead = Lead.get_lead_by_id(lead_id)
    if not lead:
        flash('Lead not found!', 'error')
        return redirect(url_for('leads'))
    return render_template('lead_detail.html', lead=lead)


@app.route('/leads/<int:lead_id>/delete', methods=['POST'])
def delete_lead(lead_id):
    Lead.delete_lead(lead_id)
    flash('Lead deleted successfully!', 'success')
    return redirect(url_for('leads'))


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)