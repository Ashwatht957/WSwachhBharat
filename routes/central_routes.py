import mysql.connector
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response

# Initialize central_routes blueprint
central_routes = Blueprint('central_routes', __name__, template_folder='../templates/central')

# MySQL config
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'staff'
}

# Database connection function
def get_db_connection():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as e:
        print(f"❌ Database connection error: {e}")
        return None

# Central login route for staff (admin/worker)
@central_routes.route('/login', methods=['GET', 'POST'])
def central_login():
    if request.method == 'POST':
        name = request.form.get('name')
        password = request.form.get('password')

        print(f"Attempting login for user: {name}")  # Debug log

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, role, ward_id, password FROM staff WHERE name=%s", (name,))
                user = cursor.fetchone()

                if user:
                    print(f"User found: {user}")  # Debug log

                    user_id, user_name, user_role, user_ward_id, user_password = user

                    # Check password
                    if user_password == password:
                        # Set session variables
                        session.clear()  # Clear previous session data
                        session['name'] = user_name
                        session['role'] = user_role
                        session['user_id'] = user_id  # Unified user_id for both admin and worker
                        session['ward_id'] = user_ward_id if user_role == 'worker' else None

                        print(f"Session set for {user_name} with role {user_role}")  # Debug log

                        # Redirect based on role
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

            except mysql.connector.Error as e:
                flash(f"Database error: {e}", "danger")
                print(f"❌ Database error: {e}")
            finally:
                cursor.close()
                conn.close()
        else:
            flash("Database connection error.", "danger")

    return render_template('central_login.html')


# Logout route to clear session
@central_routes.route('/logout')
def central_logout():
    session.clear()  # Clear the session to log out the user
    session.modified = True  # Force session modification
    
    # Disable browser caching after logout
    response = make_response(redirect(url_for('central_routes.central_login')))
    response.headers['Cache-Control'] = 'no-store'  # Prevent caching
    response.headers['Pragma'] = 'no-cache'  # Prevent caching
    response.headers['Expires'] = '0'  # Prevent caching

    flash("You have been logged out successfully.", "info")
    return response
