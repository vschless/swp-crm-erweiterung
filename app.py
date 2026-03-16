from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_restx import Api, Resource, fields
from sqlalchemy import func

from models import Customer, Lead, User
from db import db


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///crm.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "your-secret-key-change-this"

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in first."


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("login"))

        if current_user.role != "admin":
            flash("Access denied. Admins only.", "error")
            return redirect(url_for("index"))

        return view_func(*args, **kwargs)

    return wrapped_view


def init_sample_data():
    if Customer.query.count() == 0 and Lead.query.count() == 0:
        Customer.add_customer("John Doe", "john@example.com", "Acme Corp", "555-0001", "active")
        Customer.add_customer("Jane Smith", "jane@example.com", "Tech Solutions", "555-0002", "prospect")
        Customer.add_customer("Bob Wilson", "bob@example.com", "Global Industries", "555-0003", "inactive")

        Lead.add_lead("Alice Brown", "alice@example.com", "StartUp Inc", 50000, "Website")
        Lead.add_lead("Charlie Davis", "charlie@example.com", "Enterprise Ltd", 100000, "Referral")


def init_default_users():
    if User.query.filter_by(username="admin").first() is None:
        User.create_user("admin", "admin123", "admin")

    if User.query.filter_by(username="user").first() is None:
        User.create_user("user", "user123", "user")


def get_dashboard_data():
    total_customers = Customer.query.count()
    total_leads = Lead.query.count()

    lead_value_sum = db.session.query(func.coalesce(func.sum(Lead.value), 0)).scalar()
    lead_value_avg = db.session.query(func.coalesce(func.avg(Lead.value), 0)).scalar()

    customer_status_rows = (
        db.session.query(Customer.status, func.count(Customer.id))
        .group_by(Customer.status)
        .all()
    )
    customers_by_status = {status: count for status, count in customer_status_rows}

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
        "leads_by_source": leads_by_source,
    }


with app.app_context():
    db.create_all()
    init_sample_data()
    init_default_users()


# -----------------------------
# WEB ROUTES
# -----------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f"Welcome, {user.username}!", "success")
            return redirect(url_for("index"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    dashboard_data = get_dashboard_data()
    return render_template("index.html", **dashboard_data)


@app.route("/customers")
@login_required
def customers():
    return render_template("customers.html", customers=Customer.get_all_customers())


@app.route("/customers/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_customer():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        company = request.form.get("company")
        phone = request.form.get("phone")
        status = request.form.get("status", "prospect")

        if not all([name, email, company, phone]):
            flash("All fields are required!", "error")
            return redirect(url_for("add_customer"))

        Customer.add_customer(name, email, company, phone, status)
        flash(f"Customer {name} added successfully!", "success")
        return redirect(url_for("customers"))

    return render_template("add_customer.html")


@app.route("/customers/<int:customer_id>")
@login_required
def customer_detail(customer_id):
    customer = Customer.get_customer_by_id(customer_id)
    if not customer:
        flash("Customer not found!", "error")
        return redirect(url_for("customers"))
    return render_template("customer_detail.html", customer=customer)


@app.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_customer(customer_id):
    customer = Customer.get_customer_by_id(customer_id)
    if not customer:
        flash("Customer not found!", "error")
        return redirect(url_for("customers"))

    if request.method == "POST":
        Customer.update_customer(
            customer_id,
            request.form.get("name"),
            request.form.get("email"),
            request.form.get("company"),
            request.form.get("phone"),
            request.form.get("status"),
        )
        flash("Customer updated successfully!", "success")
        return redirect(url_for("customer_detail", customer_id=customer_id))

    return render_template("edit_customer.html", customer=customer)


@app.route("/customers/<int:customer_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_customer(customer_id):
    Customer.delete_customer(customer_id)
    flash("Customer deleted successfully!", "success")
    return redirect(url_for("customers"))


@app.route("/leads")
@login_required
def leads():
    return render_template("leads.html", leads=Lead.get_all_leads())


@app.route("/leads/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_lead():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        company = request.form.get("company")
        value = request.form.get("value")
        source = request.form.get("source")

        if not all([name, email, company, value, source]):
            flash("All fields are required!", "error")
            return redirect(url_for("add_lead"))

        try:
            Lead.add_lead(name, email, company, float(value), source)
            flash(f"Lead {name} added successfully!", "success")
        except ValueError:
            flash("Deal value must be a number!", "error")

        return redirect(url_for("leads"))

    return render_template("add_lead.html")


@app.route("/leads/<int:lead_id>")
@login_required
def lead_detail(lead_id):
    lead = Lead.get_lead_by_id(lead_id)
    if not lead:
        flash("Lead not found!", "error")
        return redirect(url_for("leads"))
    return render_template("lead_detail.html", lead=lead)


@app.route("/leads/<int:lead_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_lead(lead_id):
    Lead.delete_lead(lead_id)
    flash("Lead deleted successfully!", "success")
    return redirect(url_for("leads"))


# -----------------------------
# API + SWAGGER
# -----------------------------

api = Api(
    app,
    version="1.0",
    title="Pink CRM API",
    description="Detailed REST API for the Pink CRM project",
    doc="/api/docs",
    prefix="/api"
)

customers_ns = api.namespace("customers", description="Customer operations")
leads_ns = api.namespace("leads", description="Lead operations")
dashboard_ns = api.namespace("dashboard", description="Dashboard analytics")


customer_model = api.model("Customer", {
    "id": fields.Integer(readOnly=True, description="Customer ID"),
    "name": fields.String(required=True, description="Customer name"),
    "email": fields.String(required=True, description="Customer email"),
    "company": fields.String(required=True, description="Company name"),
    "phone": fields.String(required=True, description="Phone number"),
    "status": fields.String(required=True, description="Customer status")
})

lead_model = api.model("Lead", {
    "id": fields.Integer(readOnly=True, description="Lead ID"),
    "name": fields.String(required=True, description="Lead name"),
    "email": fields.String(required=True, description="Lead email"),
    "company": fields.String(required=True, description="Lead company"),
    "value": fields.Float(required=True, description="Estimated deal value"),
    "source": fields.String(required=True, description="Lead source"),
    "status": fields.String(required=True, description="Lead status")
})

dashboard_model = api.model("Dashboard", {
    "total_customers": fields.Integer(description="Total number of customers"),
    "total_leads": fields.Integer(description="Total number of leads"),
    "lead_value_sum": fields.Float(description="Sum of all lead values"),
    "lead_value_avg": fields.Float(description="Average lead value"),
    "customers_by_status": fields.Raw(description="Customer counts grouped by status"),
    "leads_by_source": fields.Raw(description="Lead counts grouped by source")
})

customer_input_model = api.model("CustomerInput", {
    "name": fields.String(required=True),
    "email": fields.String(required=True),
    "company": fields.String(required=True),
    "phone": fields.String(required=True),
    "status": fields.String(required=True, default="prospect")
})

lead_input_model = api.model("LeadInput", {
    "name": fields.String(required=True),
    "email": fields.String(required=True),
    "company": fields.String(required=True),
    "value": fields.Float(required=True),
    "source": fields.String(required=True)
})


@customers_ns.route("")
class CustomerListResource(Resource):
    @customers_ns.marshal_list_with(customer_model)
    @customers_ns.doc(description="Get all customers")
    def get(self):
        return Customer.query.all()

    @customers_ns.expect(customer_input_model, validate=True)
    @customers_ns.marshal_with(customer_model, code=201)
    @customers_ns.doc(description="Create a new customer")
    def post(self):
        data = api.payload
        customer = Customer.add_customer(
            data["name"],
            data["email"],
            data["company"],
            data["phone"],
            data.get("status", "prospect")
        )
        return customer, 201


@customers_ns.route("/<int:customer_id>")
@customers_ns.param("customer_id", "The customer identifier")
class CustomerResource(Resource):
    @customers_ns.marshal_with(customer_model)
    @customers_ns.doc(description="Get a customer by ID")
    def get(self, customer_id):
        customer = Customer.get_customer_by_id(customer_id)
        if not customer:
            api.abort(404, "Customer not found")
        return customer

    @customers_ns.expect(customer_input_model, validate=True)
    @customers_ns.marshal_with(customer_model)
    @customers_ns.doc(description="Update a customer")
    def put(self, customer_id):
        customer = Customer.get_customer_by_id(customer_id)
        if not customer:
            api.abort(404, "Customer not found")

        data = api.payload
        Customer.update_customer(
            customer_id,
            data["name"],
            data["email"],
            data["company"],
            data["phone"],
            data["status"]
        )

        updated_customer = Customer.get_customer_by_id(customer_id)
        return updated_customer

    @customers_ns.doc(description="Delete a customer")
    @customers_ns.response(204, "Customer deleted")
    def delete(self, customer_id):
        customer = Customer.get_customer_by_id(customer_id)
        if not customer:
            api.abort(404, "Customer not found")

        Customer.delete_customer(customer_id)
        return "", 204


@leads_ns.route("")
class LeadListResource(Resource):
    @leads_ns.marshal_list_with(lead_model)
    @leads_ns.doc(description="Get all leads")
    def get(self):
        return Lead.query.all()

    @leads_ns.expect(lead_input_model, validate=True)
    @leads_ns.marshal_with(lead_model, code=201)
    @leads_ns.doc(description="Create a new lead")
    def post(self):
        data = api.payload
        lead = Lead.add_lead(
            data["name"],
            data["email"],
            data["company"],
            float(data["value"]),
            data["source"]
        )
        return lead, 201


@leads_ns.route("/<int:lead_id>")
@leads_ns.param("lead_id", "The lead identifier")
class LeadResource(Resource):
    @leads_ns.marshal_with(lead_model)
    @leads_ns.doc(description="Get a lead by ID")
    def get(self, lead_id):
        lead = Lead.get_lead_by_id(lead_id)
        if not lead:
            api.abort(404, "Lead not found")
        return lead

    @leads_ns.doc(description="Delete a lead")
    @leads_ns.response(204, "Lead deleted")
    def delete(self, lead_id):
        lead = Lead.get_lead_by_id(lead_id)
        if not lead:
            api.abort(404, "Lead not found")

        Lead.delete_lead(lead_id)
        return "", 204


@dashboard_ns.route("")
class DashboardResource(Resource):
    @dashboard_ns.marshal_with(dashboard_model)
    @dashboard_ns.doc(description="Get dashboard KPIs and analytics")
    def get(self):
        return get_dashboard_data()


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)