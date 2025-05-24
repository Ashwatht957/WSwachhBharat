import base64
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, g
import psycopg2
from psycopg2.extras import RealDictCursor

staff_routes = Blueprint('staff_routes', __name__, template_folder='../templates/staff')


# Initialize staff database with default admin
def init_db():
    try:
        with g.staff_db.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS staff (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    role VARCHAR(10) CHECK(role IN ('worker', 'admin')) NOT NULL,
                    ward_id INT,
                    email VARCHAR(255)
                );
            """)
            cursor.execute("SELECT COUNT(*) FROM staff WHERE name = 'admin' AND role = 'admin'")
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO staff (name, password, role) VALUES ('admin', 'admin123', 'admin')")
            g.staff_db.commit()
    except Exception as e:
        print(f"❌ PostgreSQL error during init: {e}")


@staff_routes.before_app_first_request
def initialize():
    # Call init_db only once when the app starts (requires g.staff_db already set in app context)
    init_db()


@staff_routes.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('central_routes.central_login'))

    with g.staff_db.cursor() as cursor_staff:
        cursor_staff.execute("SELECT COUNT(*) FROM staff WHERE role != 'admin'")
        staff_count = cursor_staff.fetchone()[0]

        cursor_staff.execute("SELECT COUNT(*) FROM visited_links")
        worker_details_count = cursor_staff.fetchone()[0]

        cursor_staff.execute("SELECT id, name, role, ward_id FROM staff WHERE role != 'admin'")
        staff_data = cursor_staff.fetchall()

    with g.location_db.cursor() as cursor_location:
        cursor_location.execute("SELECT COUNT(*) FROM user_data")
        user_data_count = cursor_location.fetchone()[0]

    return render_template('staff/admin_dashboard.html',
                           staff_count=staff_count,
                           worker_details_count=worker_details_count,
                           staff_data=staff_data,
                           user_data_count=user_data_count)


@staff_routes.route('/add_staff', methods=['GET', 'POST'])
def add_new_staff():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        role = request.form.get('role', 'worker')  # default role = worker
        ward_id = request.form['ward_id']
        email = request.form['email']

        try:
            with g.staff_db.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO staff (name, password, role, ward_id, email)
                    VALUES (%s, %s, %s, %s, %s)
                """, (name, password, role, ward_id, email))
                g.staff_db.commit()
            return jsonify(success=True, message="Staff member added successfully!")
        except psycopg2.IntegrityError as e:
            g.staff_db.rollback()
            if "duplicate key value" in str(e).lower():
                return jsonify(success=False, message="A staff member with this name already exists.")
            return jsonify(success=False, message="Database error: " + str(e))

    return render_template('staff/add_staff.html')


@staff_routes.route('/edit_staff/<int:staff_id>', methods=['GET', 'POST'])
def edit_staff(staff_id):
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        ward_id = request.form['ward_id']
        email = request.form['email']
        role = request.form.get('role', 'worker')  # Default role is 'worker'

        try:
            with g.staff_db.cursor() as cursor:
                cursor.execute("""
                    UPDATE staff
                    SET name=%s, password=%s, role=%s, ward_id=%s, email=%s
                    WHERE id=%s
                """, (name, password, role, ward_id, email, staff_id))
                g.staff_db.commit()
            flash('Staff member updated successfully!', 'success')
            return redirect(url_for('staff_routes.admin_dashboard'))
        except Exception as e:
            g.staff_db.rollback()
            flash('Error updating staff: ' + str(e), 'danger')

    with g.staff_db.cursor() as cursor:
        cursor.execute("SELECT id, name, password, role, ward_id, email FROM staff WHERE id = %s", (staff_id,))
        staff = cursor.fetchone()

    return render_template('staff/edit_staff.html', staff=staff)


@staff_routes.route('/delete_staff/<int:staff_id>', methods=['POST'])
def remove_staff(staff_id):
    try:
        with g.staff_db.cursor() as cursor:
            cursor.execute("DELETE FROM staff WHERE id = %s", (staff_id,))
            g.staff_db.commit()
        flash("Staff member deleted successfully!", "success")
    except Exception as e:
        g.staff_db.rollback()
        flash(f"Error deleting staff member: {e}", "danger")

    return redirect(url_for('staff_routes.admin_dashboard'))


@staff_routes.route('/worker_details')
def worker_details():
    with g.staff_db.cursor() as cursor:
        cursor.execute("SELECT id, name, image, ward_id, visited_at FROM visited_links")
        rows = cursor.fetchall()

    data = []
    for row in rows:
        image = base64.b64encode(row[2]).decode('utf-8') if row[2] else None
        data.append((row[0], row[1], f"data:image/jpeg;base64,{image}" if image else None, row[3], row[4]))

    return render_template('staff/worker_details.html', visited_links_data=data)


@staff_routes.route('/user_data')
def view_user_data():
    try:
        with g.location_db.cursor() as cursor:
            cursor.execute("SELECT id, name, latitude, longitude, ward_id, image FROM user_data")
            rows = cursor.fetchall()

        data = []
        for row in rows:
            image = base64.b64encode(row[5]).decode('utf-8') if row[5] else None
            data.append((row[0], row[1], row[2], row[3], row[4], f"data:image/jpeg;base64,{image}" if image else None))
    except Exception as e:
        flash(f"PostgreSQL error: {e}", "danger")
        data = []

    return render_template('staff/user_data.html', user_data=data)


@staff_routes.route('/staff_table')
def staff_table():
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('central_routes.central_login'))

    with g.staff_db.cursor() as cursor:
        cursor.execute("SELECT id, name, role, ward_id FROM staff WHERE role != 'admin'")
        staff_data = cursor.fetchall()

    return render_template('staff/staff_table.html', staff_data=staff_data)


@staff_routes.route('/admin/logout')
def admin_logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('index'))
