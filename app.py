import csv
import io
from cs50 import SQL
from flask import Flask, redirect, render_template, request, session, Response
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required

# Portions of this project were developed with assistance from ChatGPT.
# ChatGPT was used to discuss structure, explain syntax, debug errors,
# and support drafting of Flask routes and templates.
# All such code was reviewed, tested and adapted by the author.

# Configure application
app = Flask(__name__)

# Configure session to use filesystem instead of signed cookies
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure database
db = SQL("sqlite:///esg.db")

@app.after_request
def after_request(response):
    """Ensure responses are not cached."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/")
@login_required
def index():
    """Show landing page or dashboard."""
    if session.get("user_id") is None:
        return render_template("about.html")

    user = db.execute(
        "SELECT company_name FROM users WHERE id = ?",
        session["user_id"]
    )
    if len(user) != 1:
        session.clear()
        return redirect("/login")
    company_name = user[0]["company_name"]

    datapoint_count = db.execute(
        "SELECT COUNT(*) AS count FROM datapoints WHERE user_id = ?",
        session["user_id"]
    )[0]["count"]

    emission_count = db.execute(
        "SELECT COUNT(*) AS count FROM emissions WHERE user_id = ?",
        session["user_id"]
    )[0]["count"]
    total_items = datapoint_count + emission_count

    total_emissions_kg = db.execute(
        """
        SELECT COALESCE(SUM(calculated_emissions_kg), 0) AS total
        FROM emissions
        WHERE user_id = ?
        """,
        session["user_id"]
    )[0]["total"]

    total_emissions_t = total_emissions_kg / 1000
    scope_rows = db.execute(
        """
        SELECT scope, COALESCE(SUM(calculated_emissions_kg), 0) AS total
        FROM emissions
        WHERE user_id = ?
        GROUP BY scope
        """,
        session["user_id"]
    )

    emissions_by_scope = {
        "Scope 1": 0,
        "Scope 2": 0,
        "Scope 3": 0
    }

    for row in scope_rows:
        emissions_by_scope[row["scope"]] = row["total"] / 1000
    hotspot_rows = db.execute(
        """
        SELECT emissions_category, COALESCE(SUM(calculated_emissions_kg), 0) AS total
        FROM emissions
        WHERE user_id = ?
        GROUP BY emissions_category
        ORDER BY total DESC
        LIMIT 1
        """,
        session["user_id"]
    )

    if len(hotspot_rows) == 1:
        largest_category = hotspot_rows[0]["emissions_category"]
        largest_category_emissions_t = hotspot_rows[0]["total"] / 1000
    else:
        largest_category = None
        largest_category_emissions_t = 0

    datapoints_needing_review = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM datapoints
        WHERE user_id = ?
        AND status IN ('Missing', 'Needs review')
        """,
        session["user_id"]
    )[0]["count"]

    emissions_needing_review = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM emissions
        WHERE user_id = ?
        AND status IN ('Missing', 'Needs review')
        """,
        session["user_id"]
    )[0]["count"]

    records_needing_review = datapoints_needing_review + emissions_needing_review
    datapoints_missing_evidence = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM datapoints
        WHERE user_id = ?
        AND (evidence_link IS NULL OR evidence_link = '')
        """,
        session["user_id"]
    )[0]["count"]

    emissions_missing_evidence = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM emissions
        WHERE user_id = ?
        AND (evidence_link IS NULL OR evidence_link = '')
        """,
        session["user_id"]
    )[0]["count"]

    missing_evidence_links = datapoints_missing_evidence + emissions_missing_evidence
    datapoints_verified = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM datapoints
        WHERE user_id = ?
        AND status = 'Verified'
        """,
        session["user_id"]
    )[0]["count"]

    emissions_verified = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM emissions
        WHERE user_id = ?
        AND status = 'Verified'
        """,
        session["user_id"]
    )[0]["count"]

    verified_records = datapoints_verified + emissions_verified
    datapoint_status_rows = db.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM datapoints
        WHERE user_id = ?
        GROUP BY status
        """,
        session["user_id"]
    )

    emission_status_rows = db.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM emissions
        WHERE user_id = ?
        GROUP BY status
        """,
        session["user_id"]
    )

    statuses = ["Missing", "In progress", "Submitted", "Needs review", "Verified"]
    datapoint_status_counts = {status: 0 for status in statuses}
    emission_status_counts = {status: 0 for status in statuses}

    for row in datapoint_status_rows:
        datapoint_status_counts[row["status"]] = row["count"]

    for row in emission_status_rows:
        emission_status_counts[row["status"]] = row["count"]

    return render_template(
        "index.html",
        company_name=company_name,
        datapoint_count=datapoint_count,
        emission_count=emission_count,
        total_items=total_items,
        total_emissions_t=total_emissions_t,
        emissions_by_scope=emissions_by_scope,
        largest_category=largest_category,
        largest_category_emissions_t=largest_category_emissions_t,
        records_needing_review=records_needing_review,
        missing_evidence_links=missing_evidence_links,
        verified_records=verified_records,
        datapoint_status_counts=datapoint_status_counts,
        emission_status_counts=emission_status_counts
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    # Forget any current user
    session.clear()
    if request.method == "POST":
        username = request.form.get("username")
        company_name = request.form.get("company_name")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("must provide username", 400)

        if not company_name:
            return apology("must provide company name", 400)

        if not password:
            return apology("must provide password", 400)

        if not confirmation:
            return apology("must confirm password", 400)

        if password != confirmation:
            return apology("passwords do not match", 400)

        hash_value = generate_password_hash(password)
        try:
            user_id = db.execute(
                "INSERT INTO users (username, hash, company_name) VALUES (?, ?, ?)",
                username,
                hash_value,
                company_name
            )
        except ValueError:
            return apology("username already exists", 400)

        session["user_id"] = user_id
        return redirect("/")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""
    # Forget any current user
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            return apology("must provide username", 400)

        if not password:
            return apology("must provide password", 400)

        rows = db.execute(
            "SELECT * FROM users WHERE username = ?",
            username
        )

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            return apology("invalid username and/or password", 400)

        session["user_id"] = rows[0]["id"]
        return redirect("/")

    return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""
    session.clear()
    return redirect("/login")

@app.route("/about")
def about():
    """Show information about the project."""
    return render_template("about.html")

@app.route("/datapoints")
@login_required
def datapoints():
    """Show all datapoints for logged-in user with optional filters."""
    selected_year = request.args.get("year")
    selected_esrs_area = request.args.get("esrs_area")
    selected_topic = request.args.get("topic")
    selected_status = request.args.get("status")

    filters_active = bool(
        selected_year or selected_esrs_area or selected_topic or selected_status
    )

    query = "SELECT * FROM datapoints WHERE user_id = ?"
    params = [session["user_id"]]

    if selected_year:
        try:
            selected_year_int = int(selected_year)
        except ValueError:
            return apology("year filter must be a number", 400)
        query += " AND reporting_year = ?"
        params.append(selected_year_int)

    if selected_esrs_area:
        query += " AND esrs_area = ?"
        params.append(selected_esrs_area)

    if selected_topic:
        query += " AND topic = ?"
        params.append(selected_topic)

    if selected_status:
        query += " AND status = ?"
        params.append(selected_status)


    query += " ORDER BY reporting_year DESC, reporting_period"

    datapoints = db.execute(query, *params)

    return render_template(
        "datapoints.html",
        datapoints=datapoints,
        selected_year=selected_year,
        selected_esrs_area=selected_esrs_area,
        selected_topic=selected_topic,
        selected_status=selected_status,
        filters_active=filters_active
    )


@app.route("/datapoints/add", methods=["GET", "POST"])
@login_required
def add_datapoint():
    """Add a new sustainability datapoint."""
    if request.method == "POST":
        reporting_year = request.form.get("reporting_year")
        reporting_period = request.form.get("reporting_period")
        esrs_area = request.form.get("esrs_area")
        topic = request.form.get("topic")
        metric_name = request.form.get("metric_name")
        value = request.form.get("value")
        unit = request.form.get("unit")
        department = request.form.get("department")
        data_source = request.form.get("data_source")
        evidence_link = request.form.get("evidence_link")
        status = request.form.get("status")
        notes = request.form.get("notes")

        # Validate required fields
        if not reporting_year:
            return apology("must provide reporting year", 400)

        if not reporting_period:
            return apology("must select reporting period", 400)

        if not esrs_area:
            return apology("must select ESRS-relevant area", 400)

        if not topic:
            return apology("must select topic", 400)

        if not metric_name:
            return apology("must provide metric name", 400)

        if not department:
            return apology("must select department", 400)

        if not status:
            return apology("must select status", 400)

        # Validate year
        try:
            reporting_year = int(reporting_year)
        except ValueError:
            return apology("reporting year must be a number", 400)

        if reporting_year < 2020 or reporting_year > 2100:
            return apology("reporting year must be between 2020 and 2100", 400)

        # Validate value if provided
        if value:
            try:
                value = float(value)
            except ValueError:
                return apology("value must be a number", 400)

            if value < 0:
                return apology("value cannot be negative", 400)

        else:
            value = None

        db.execute(
            """
            INSERT INTO datapoints (
                user_id,
                reporting_year,
                reporting_period,
                esrs_area,
                topic,
                metric_name,
                value,
                unit,
                department,
                data_source,
                evidence_link,
                status,
                notes
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            session["user_id"],
            reporting_year,
            reporting_period,
            esrs_area,
            topic,
            metric_name,
            value,
            unit,
            department,
            data_source,
            evidence_link,
            status,
            notes
        )

        return redirect("/datapoints")

    return render_template("add_datapoint.html")

@app.route("/datapoints/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_datapoint(id):
    """Edit an existing sustainability datapoint."""
    rows = db.execute(
        "SELECT * FROM datapoints WHERE id = ? AND user_id = ?",
        id,
        session["user_id"]
    )

    if len(rows) != 1:
        return apology("datapoint not found", 404)

    datapoint = rows[0]

    if request.method == "POST":
        reporting_year = request.form.get("reporting_year")
        reporting_period = request.form.get("reporting_period")
        esrs_area = request.form.get("esrs_area")
        topic = request.form.get("topic")
        metric_name = request.form.get("metric_name")
        value = request.form.get("value")
        unit = request.form.get("unit")
        department = request.form.get("department")
        data_source = request.form.get("data_source")
        evidence_link = request.form.get("evidence_link")
        status = request.form.get("status")
        notes = request.form.get("notes")

        if not reporting_year:
            return apology("must provide reporting year", 400)

        if not reporting_period:
            return apology("must select reporting period", 400)

        if not esrs_area:
            return apology("must select ESRS-relevant area", 400)

        if not topic:
            return apology("must select topic", 400)

        if not metric_name:
            return apology("must provide metric name", 400)

        if not department:
            return apology("must select department", 400)

        if not status:
            return apology("must select status", 400)

        try:
            reporting_year = int(reporting_year)
        except ValueError:
            return apology("reporting year must be a number", 400)

        if reporting_year < 2020 or reporting_year > 2100:
            return apology("reporting year must be between 2020 and 2100", 400)

        if value:
            try:
                value = float(value)
            except ValueError:
                return apology("value must be a number", 400)

            if value < 0:
                return apology("value cannot be negative", 400)
        else:
            value = None

        db.execute(
            """
            UPDATE datapoints
            SET reporting_year = ?,
                reporting_period = ?,
                esrs_area = ?,
                topic = ?,
                metric_name = ?,
                value = ?,
                unit = ?,
                department = ?,
                data_source = ?,
                evidence_link = ?,
                status = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP

            WHERE id = ? AND user_id = ?
            """,
            reporting_year,
            reporting_period,
            esrs_area,
            topic,
            metric_name,
            value,
            unit,
            department,
            data_source,
            evidence_link,
            status,
            notes,
            id,
            session["user_id"]
        )
        return redirect("/datapoints")

    return render_template("edit_datapoint.html", datapoint=datapoint)


@app.route("/datapoints/delete/<int:id>", methods=["GET", "POST"])
@login_required
def delete_datapoint(id):
    """Delete an existing sustainability datapoint after confirmation."""
    rows = db.execute(
        "SELECT * FROM datapoints WHERE id = ? AND user_id = ?",
        id,
        session["user_id"]
    )
    if len(rows) != 1:
        return apology("datapoint not found", 404)
    datapoint = rows[0]
    if request.method == "POST":
        db.execute(
            "DELETE FROM datapoints WHERE id = ? AND user_id = ?",
            id,
            session["user_id"]
        )
        return redirect("/datapoints")
    return render_template("delete_datapoint.html", datapoint=datapoint)


@app.route("/emissions")
@login_required
def emissions():
    """Show emissions records for logged-in user, with optional filters"""
    selected_year = request.args.get("year")
    selected_scope = request.args.get("scope")
    selected_emissions_category = request.args.get("emissions_category")
    filters_active = bool(
        selected_year or selected_scope or selected_emissions_category
    )

    query = "SELECT * FROM emissions WHERE user_id = ?"
    params = [session["user_id"]]

    if selected_year:
        try:
            selected_year_int = int(selected_year)
        except ValueError:
            return apology("year filter must be a number", 400)

        query += " AND reporting_year = ?"
        params.append(selected_year_int)

    if selected_scope:
        query += " AND scope = ?"
        params.append(selected_scope)

    if selected_emissions_category:
        query += " AND emissions_category = ?"
        params.append(selected_emissions_category)

    query += " ORDER BY reporting_year DESC, reporting_period, scope"
    emissions = db.execute(query, *params)
    return render_template(
        "emissions.html",
        emissions=emissions,
        selected_year=selected_year,
        selected_scope=selected_scope,
        selected_emissions_category=selected_emissions_category,
        filters_active=filters_active
    )

@app.route("/emissions/add", methods=["GET", "POST"])
@login_required
def add_emission():
    """Add a new emissions record."""
    if request.method == "POST":
        reporting_year = request.form.get("reporting_year")
        reporting_period = request.form.get("reporting_period")
        scope = request.form.get("scope")
        emissions_category = request.form.get("emissions_category")
        activity_type = request.form.get("activity_type")
        activity_value = request.form.get("activity_value")
        activity_unit = request.form.get("activity_unit")
        emission_factor = request.form.get("emission_factor")
        emission_factor_unit = request.form.get("emission_factor_unit")
        emission_factor_source = request.form.get("emission_factor_source")
        department = request.form.get("department")
        status = request.form.get("status")
        data_source = request.form.get("data_source")
        evidence_link = request.form.get("evidence_link")
        notes = request.form.get("notes")

        if not reporting_year:
            return apology("must provide reporting year", 400)

        try:
            reporting_year = int(reporting_year)
        except ValueError:
            return apology("reporting year must be a number", 400)

        if reporting_year < 2020 or reporting_year > 2100:
            return apology("reporting year must be between 2020 and 2100", 400)

        if not reporting_period:
            return apology("must select reporting period", 400)

        if not scope:
            return apology("must select scope", 400)

        if not emissions_category:
            return apology("must select emissions category", 400)

        if not activity_type:
            return apology("must provide activity type", 400)

        if not activity_value:
            return apology("must provide activity value", 400)

        try:
            activity_value = float(activity_value)
        except ValueError:
            return apology("activity value must be a number", 400)

        if activity_value < 0:
            return apology("activity value must be non-negative", 400)

        if not activity_unit:
            return apology("must select activity unit", 400)

        if not emission_factor:
            return apology("must provide emission factor", 400)

        try:
            emission_factor = float(emission_factor)
        except ValueError:
            return apology("emission factor must be a number", 400)

        if emission_factor < 0:
            return apology("emission factor must be non-negative", 400)

        if not emission_factor_unit:
            return apology("must select emission factor unit", 400)

        if not department:
            return apology("must select department", 400)

        if not status:
            return apology("must select status", 400)

        calculated_emissions_kg = activity_value * emission_factor
        db.execute(
            """
            INSERT INTO emissions (
                user_id,
                reporting_year,
                reporting_period,
                scope,
                emissions_category,
                activity_type,
                activity_value,
                activity_unit,
                emission_factor,
                emission_factor_unit,
                emission_factor_source,
                calculated_emissions_kg,
                department,
                data_source,
                evidence_link,
                status,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            session["user_id"],
            reporting_year,
            reporting_period,
            scope,
            emissions_category,
            activity_type,
            activity_value,
            activity_unit,
            emission_factor,
            emission_factor_unit,
            emission_factor_source,
            calculated_emissions_kg,
            department,
            data_source,
            evidence_link,
            status,
            notes
        )
        return redirect("/emissions")

    return render_template("add_emission.html")

@app.route("/emissions/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_emission(id):
    """Edit an existing emissions record"""
    rows = db.execute(
        "SELECT * FROM emissions WHERE id = ? AND user_id = ?",
        id,
        session["user_id"]
    )
    if len(rows) != 1:
        return apology("emission record not found", 404)
    emission = rows[0]

    if request.method == "POST":
        reporting_year = request.form.get("reporting_year")
        reporting_period = request.form.get("reporting_period")
        scope = request.form.get("scope")
        emissions_category = request.form.get("emissions_category")
        activity_type = request.form.get("activity_type")
        activity_value = request.form.get("activity_value")
        activity_unit = request.form.get("activity_unit")
        emission_factor = request.form.get("emission_factor")
        emission_factor_unit = request.form.get("emission_factor_unit")
        emission_factor_source = request.form.get("emission_factor_source")
        department = request.form.get("department")
        status = request.form.get("status")
        data_source = request.form.get("data_source")
        evidence_link = request.form.get("evidence_link")
        notes = request.form.get("notes")

        if not reporting_year:
            return apology("must provide reporting year", 400)

        try:
            reporting_year = int(reporting_year)
        except ValueError:
            return apology("reporting year must be a number", 400)

        if reporting_year < 2020 or reporting_year > 2100:
            return apology("reporting year must be between 2020 and 2100", 400)

        if not reporting_period:
            return apology("must select reporting period", 400)

        if not scope:
            return apology("must select scope", 400)

        if not emissions_category:
            return apology("must select emissions category", 400)

        if not activity_type:
            return apology("must provide activity type", 400)

        if not activity_value:
            return apology("must provide activity value", 400)

        try:
            activity_value = float(activity_value)
        except ValueError:
            return apology("activity value must be a number", 400)

        if activity_value < 0:
            return apology("activity value must be non-negative", 400)

        if not activity_unit:
            return apology("must select activity unit", 400)

        if not emission_factor:
            return apology("must provide emission factor", 400)

        try:
            emission_factor = float(emission_factor)
        except ValueError:
            return apology("emission factor must be a number", 400)

        if emission_factor < 0:
            return apology("emission factor must be non-negative", 400)

        if not emission_factor_unit:
            return apology("must select emission factor unit", 400)

        if not department:
            return apology("must select department", 400)

        if not status:
            return apology("must select status", 400)

        calculated_emissions_kg = activity_value * emission_factor

        db.execute(
            """
            UPDATE emissions
            SET reporting_year = ?,
                reporting_period = ?,
                scope = ?,
                emissions_category = ?,
                activity_type = ?,
                activity_value = ?,
                activity_unit = ?,
                emission_factor = ?,
                emission_factor_unit = ?,
                emission_factor_source = ?,
                calculated_emissions_kg = ?,
                department = ?,
                data_source = ?,
                evidence_link = ?,
                status = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP

            WHERE id = ? AND user_id = ?
            """,
            reporting_year,
            reporting_period,
            scope,
            emissions_category,
            activity_type,
            activity_value,
            activity_unit,
            emission_factor,
            emission_factor_unit,
            emission_factor_source,
            calculated_emissions_kg,
            department,
            data_source,
            evidence_link,
            status,
            notes,
            id,
            session["user_id"]
        )
        return redirect("/emissions")
    return render_template("edit_emission.html", emission=emission)

@app.route("/emissions/delete/<int:id>", methods=["GET", "POST"])
@login_required
def delete_emission(id):
    """Delete an existing emissions record after confirmation"""
    rows = db.execute(
        "SELECT * FROM emissions WHERE id = ? AND user_id = ?",
        id,
        session["user_id"]
    )

    if len(rows) != 1:
        return apology("emission record not found", 404)
    emission = rows[0]

    if request.method == "POST":
        db.execute(
            "DELETE FROM emissions WHERE id = ? AND user_id = ?",
            id,
            session["user_id"]
        )
        return redirect("/emissions")

    return render_template("delete_emission.html", emission=emission)


@app.route("/quality")
@login_required
def quality():
    """Show combined quality issues for datapoints and emissions."""
    quality_issues = []
    datapoints = db.execute(
        """
        SELECT *
        FROM datapoints
        WHERE user_id = ?
        ORDER BY reporting_year DESC, reporting_period
        """,
        session["user_id"]
    )

    emissions = db.execute(
        """
        SELECT *
        FROM emissions
        WHERE user_id = ?
        ORDER BY reporting_year DESC, reporting_period
        """,
        session["user_id"]
    )

    for datapoint in datapoints:
        issues = []
        if datapoint["status"] == "Missing":
            issues.append("Status: Missing")

        if datapoint["status"] == "Needs review":
            issues.append("Status: Needs review")

        if not datapoint["evidence_link"]:
            issues.append("Missing evidence link")

        if not datapoint["data_source"]:
            issues.append("Missing data source")

        if issues:
            quality_issues.append({
                "record_type": "Datapoint",
                "record_name": datapoint["metric_name"],
                "year": datapoint["reporting_year"],
                "period": datapoint["reporting_period"],
                "status": datapoint["status"],
                "issues": issues,
                "edit_url": f"/datapoints/edit/{datapoint['id']}"
            })

    for emission in emissions:
        issues = []
        if emission["status"] == "Missing":
            issues.append("Status: Missing")

        if emission["status"] == "Needs review":
            issues.append("Status: Needs review")

        if not emission["evidence_link"]:
            issues.append("Missing evidence link")

        if not emission["data_source"]:
            issues.append("Missing data source")

        if not emission["emission_factor_source"]:
            issues.append("Missing emission factor source")

        if issues:
            quality_issues.append({
                "record_type": "Emission",
                "record_name": emission["activity_type"],
                "year": emission["reporting_year"],
                "period": emission["reporting_period"],
                "status": emission["status"],
                "issues": issues,
                "edit_url": f"/emissions/edit/{emission['id']}"
            })

    total_issues = len(quality_issues)

    return render_template(
        "quality.html",
        quality_issues=quality_issues,
        total_issues=total_issues
    )


@app.route("/export")
@login_required
def export():
    """Show export options."""
    return render_template("export.html")

@app.route("/export/datapoints")
@login_required
def export_datapoints():
    """Export all datapoints for the logged-in user as a CSV file."""
    datapoints = db.execute(
        """
        SELECT
            reporting_year,
            reporting_period,
            esrs_area,
            topic,
            metric_name,
            value,
            unit,
            department,
            data_source,
            evidence_link,
            status,
            notes,
            created_at,
            updated_at
        FROM datapoints
        WHERE user_id = ?
        ORDER BY reporting_year DESC, reporting_period
        """,
        session["user_id"]
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "reporting_year",
        "reporting_period",
        "esrs_area",
        "topic",
        "metric_name",
        "value",
        "unit",
        "department",
        "data_source",
        "evidence_link",
        "status",
        "notes",
        "created_at",
        "updated_at"
    ])

    for datapoint in datapoints:
        writer.writerow([
            datapoint["reporting_year"],
            datapoint["reporting_period"],
            datapoint["esrs_area"],
            datapoint["topic"],
            datapoint["metric_name"],
            datapoint["value"],
            datapoint["unit"],
            datapoint["department"],
            datapoint["data_source"],
            datapoint["evidence_link"],
            datapoint["status"],
            datapoint["notes"],
            datapoint["created_at"],
            datapoint["updated_at"]
        ])
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=datapoints_export.csv"
    return response

@app.route("/export/emissions")
@login_required
def export_emissions():
    """Export all emissions records for the logged-in user as a CSV file."""
    emissions = db.execute(
        """
        SELECT
            reporting_year,
            reporting_period,
            scope,
            emissions_category,
            activity_type,
            activity_value,
            activity_unit,
            emission_factor,
            emission_factor_unit,
            emission_factor_source,
            calculated_emissions_kg,
            department,
            data_source,
            evidence_link,
            status,
            notes,
            created_at,
            updated_at

        FROM emissions
        WHERE user_id = ?
        ORDER BY reporting_year DESC, reporting_period, scope
        """,
        session["user_id"]
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "reporting_year",
        "reporting_period",
        "scope",
        "emissions_category",
        "activity_type",
        "activity_value",
        "activity_unit",
        "emission_factor",
        "emission_factor_unit",
        "emission_factor_source",
        "calculated_emissions_kg",
        "calculated_emissions_tCO2e",
        "department",
        "data_source",
        "evidence_link",
        "status",
        "notes",
        "created_at",
        "updated_at"
    ])

    for emission in emissions:
        calculated_emissions_t = emission["calculated_emissions_kg"] / 1000
        writer.writerow([
            emission["reporting_year"],
            emission["reporting_period"],
            emission["scope"],
            emission["emissions_category"],
            emission["activity_type"],
            emission["activity_value"],
            emission["activity_unit"],
            emission["emission_factor"],
            emission["emission_factor_unit"],
            emission["emission_factor_source"],
            emission["calculated_emissions_kg"],
            calculated_emissions_t,
            emission["department"],
            emission["data_source"],
            emission["evidence_link"],
            emission["status"],
            emission["notes"],
            emission["created_at"],
            emission["updated_at"]
        ])
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=emissions_export.csv"
    return response

