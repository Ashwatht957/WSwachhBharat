import base64
import mysql.connector
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from mysql.connector import IntegrityError

staff_routes = Blueprint('staff_routes', __name__, template_folder='../templates/staff')

# MySQL Configurations
staff_db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'staff'
}

location_db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'location'
}

# Initialize staff database with default admin
def init_db():
    try:
        conn = mysql.connector.connect(**staff_db_config)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                password VARCHAR(255) NOT NULL,
                role ENUM('worker', 'admin') NOT NULL,
                ward_id INT,
                email VARCHAR(255)
            )
        """)
        cursor.execute("SELECT COUNT(*) FROM staff WHERE name = 'admin' AND role = 'admin'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO staff (name, password, role) VALUES ('admin', 'admin123', 'admin')")
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as e:
        print(f"❌ MySQL Error during init: {e}")

init_db()

@staff_routes.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('central_routes.central_login'))

    conn_staff = mysql.connector.connect(**staff_db_config)
    cursor_staff = conn_staff.cursor()
    cursor_staff.execute("SELECT COUNT(*) FROM staff WHERE role != 'admin'")
    staff_count = cursor_staff.fetchone()[0]
    cursor_staff.execute("SELECT COUNT(*) FROM visited_links")
    worker_details_count = cursor_staff.fetchone()[0]
    cursor_staff.execute("SELECT id, name, role, ward_id FROM staff WHERE role != 'admin'")
    staff_data = cursor_staff.fetchall()
    cursor_staff.close()
    conn_staff.close()

    conn_location = mysql.connector.connect(**location_db_config)
    cursor_location = conn_location.cursor()
    cursor_location.execute("SELECT COUNT(*) FROM user_data")
    user_data_count = cursor_location.fetchone()[0]
    cursor_location.close()
    conn_location.close()

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
            conn = mysql.connector.connect(**staff_db_config)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO staff (name, password, role, ward_id, email)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, password, role, ward_id, email))
            conn.commit()
            return jsonify(success=True, message="Staff member added successfully!")
        except IntegrityError as e:
            if "Duplicate entry" in str(e):
                return jsonify(success=False, message="A staff member with this name already exists.")
            return jsonify(success=False, message="Database error: " + str(e))
        finally:
            cursor.close()
            conn.close()

    return render_template('staff/add_staff.html')


@staff_routes.route('/edit_staff/<int:staff_id>', methods=['GET', 'POST'])
def edit_staff(staff_id):
    conn = mysql.connector.connect(**staff_db_config)
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']
        ward_id = request.form['ward_id']
        email = request.form['email']
        role = request.form.get('role', 'worker')  # Default role is 'worker'

        try:
            cursor.execute("""
                UPDATE staff
                SET name=%s, password=%s, role=%s, ward_id=%s, email=%s
                WHERE id=%s
            """, (name, password, role, ward_id, email, staff_id))
            conn.commit()
            flash('Staff member updated successfully!', 'success')
            return redirect(url_for('staff_routes.admin_dashboard'))
        except Exception as e:
            flash('Error updating staff: ' + str(e), 'danger')

    # On GET, fetch the current staff details
    cursor.execute("SELECT * FROM staff WHERE id = %s", (staff_id,))
    staff = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('staff/edit_staff.html', staff=staff)


@staff_routes.route('/delete_staff/<int:staff_id>', methods=['POST'])
def remove_staff(staff_id):
    conn = mysql.connector.connect(**staff_db_config)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM staff WHERE id = %s", (staff_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Staff member deleted successfully!", "success")
    return redirect(url_for('staff_routes.admin_dashboard'))

@staff_routes.route('/worker_details')
def worker_details():
    conn = mysql.connector.connect(**staff_db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, image, ward_id, visited_at FROM visited_links")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    data = []
    for row in rows:
        image = base64.b64encode(row[2]).decode('utf-8') if row[2] else None
        data.append((row[0], row[1], f"data:image/jpeg;base64,{image}" if image else None, row[3], row[4]))

    return render_template('staff/worker_details.html', visited_links_data=data)

@staff_routes.route('/user_data')
def view_user_data():
    try:
        conn = mysql.connector.connect(**location_db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, latitude, longitude, ward_id, image FROM user_data")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        data = []
        for row in rows:
            image = base64.b64encode(row[5]).decode('utf-8') if row[5] else None
            data.append((row[0], row[1], row[2], row[3], row[4], f"data:image/jpeg;base64,{image}" if image else None))
    except mysql.connector.Error as e:
        flash(f"MySQL error: {e}", "danger")
        data = []

    return render_template('staff/user_data.html', user_data=data)

@staff_routes.route('/staff_table')
def staff_table():
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('central_routes.central_login'))

    conn = mysql.connector.connect(**staff_db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, role, ward_id FROM staff WHERE role != 'admin'")
    staff_data = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('staff/staff_table.html', staff_data=staff_data)

@staff_routes.route('/admin/logout')
def admin_logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('index'))
