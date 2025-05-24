from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response, g
from psycopg2.extras import RealDictCursor

central_routes = Blueprint('central_routes', __name__, template_folder='../templates/central')


@central_routes.route('/login', methods=['GET', 'POST'])
def central_login():
    if request.method == 'POST':
        name = request.form.get('name')
        password = request.form.get('password')

        print(f"Attempting login for user: {name}")  # Debug log

        # Use g.staff_db connection set up in app context
        conn = g.get('staff_db')
        if conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SELECT id, name, role, ward_id, password FROM staff WHERE name = %s", (name,))
                    user = cursor.fetchone()

                if user:
                    print(f"User found: {user}")  # Debug log

                    # Extract fields
                    user_id = user['id']
                    user_name = user['name']
                    user_role = user['role']
                    user_ward_id = user['ward_id']
                    user_password = user['password']

                    # Check password (plain text here; ideally hash check)
                    if user_password == password:
                        session.clear()
                        session['name'] = user_name
                        session['role'] = user_role
                        session['user_id'] = user_id
                        session['ward_id'] = user_ward_id if user_role == 'worker' else None

                        print(f"Session set for {user_name} with role {user_role}")  # Debug log

                        if user_role == 'worker':
                            flash("Worker login successful!", "success")
                            return redirect(url_for('worker_routes.worker_dashboard'))

                        elif user_role == 'admin':
                            flash("Admin login successful!", "success")
                            return redirect(url_for('staff_routes.admin_dashboard'))

                        else:
                            flash("Unknown role.", "danger")
                            return redirect(url_for('central_routes.central_login'))
                    else:
                        flash("Invalid credentials.", "danger")
                        print("Password mismatch!")  # Debug log
                else:
                    flash("User not found.", "danger")
                    print("User not found in database.")  # Debug log

            except Exception as e:
                flash(f"Database error: {e}", "danger")
                print(f"❌ Database error: {e}")
        else:
            flash("Database connection error.", "danger")

    return render_template('central_login.html')


@central_routes.route('/logout')
def central_logout():
    session.clear()
    session.modified = True

    response = make_response(redirect(url_for('central_routes.central_login')))
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    flash("You have been logged out successfully.", "info")
    return response
from flask_mail import Mail, Message