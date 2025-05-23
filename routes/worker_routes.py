import base64
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_mail import Message
from datetime import datetime
import mysql.connector

worker_routes = Blueprint('worker_routes', __name__, template_folder='../templates/worker')

def get_staff_db():
    return mysql.connector.connect(host='localhost', user='root', password='', database='staff')

def get_location_db():
    return mysql.connector.connect(host='localhost', user='root', password='', database='location')

@worker_routes.route('/worker/dashboard', methods=['GET', 'POST'])
def worker_dashboard():
    if 'user_id' not in session or session.get('role') != 'worker':
        flash("Please log in first.", "warning")
        return redirect(url_for('central_routes.central_login'))

    ward_id = session.get('ward_id')

    if request.method == 'POST':
        visited_ids = request.form.getlist('visited_ids')
        if visited_ids:
            try:
                loc_conn = get_location_db()
                staff_conn = get_staff_db()
                loc_cursor = loc_conn.cursor(dictionary=True)
                staff_cursor = staff_conn.cursor()
                mail = current_app.extensions['mail']

                for link_id in visited_ids:
                    loc_cursor.execute("""
                        SELECT name, email, latitude, longitude, ward_id, ward_name, image
                        FROM user_data WHERE id = %s
                    """, (link_id,))
                    row = loc_cursor.fetchone()

                    if row:
                        # Insert into visited_links
                        staff_cursor.execute("""
                            INSERT INTO visited_links (name, latitude, longitude, ward_id, visited_at, image)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (row['name'], row['latitude'], row['longitude'], row['ward_id'], datetime.now(), row['image']))

                        # Delete from user_data
                        loc_cursor.execute("DELETE FROM user_data WHERE id = %s", (link_id,))
                        loc_conn.commit()
                        staff_conn.commit()

                        # Send email
                        msg = Message(
                            subject="Your location has been visited!",
                            sender='swachhindiamission@gmail.com',
                            recipients=[row['email']],
                            body=(
                                f"Dear {row['name']},\n\n"
                                f"A worker has visited your submitted location in the area: {row['ward_name']}.\n"
                                f"Visited At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                "Thank you for supporting the Swachh Bharat Mission. Keep encouraging others to participate!"
                            )
                        )
                        mail.send(msg)

                flash("Visited links processed and emails sent.", "success")

            except mysql.connector.Error as err:
                flash(f"Database error: {err}", "danger")

            finally:
                loc_cursor.close()
                staff_cursor.close()
                loc_conn.close()
                staff_conn.close()

        return redirect(url_for('worker_routes.worker_dashboard'))

    # GET method - load user data for this ward
    try:
        conn = get_location_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, name, longitude, latitude, ward_id, image, ward_name
            FROM user_data WHERE ward_id = %s
        """, (ward_id,))
        worker_data_raw = cursor.fetchall()

        worker_data = []
        for row in worker_data_raw:
            row['image'] = base64.b64encode(row['image']).decode('utf-8') if row['image'] else ''
            worker_data.append(row)

    except mysql.connector.Error as err:
        flash(f"Error loading data: {err}", "danger")
        worker_data = []

    finally:
        cursor.close()
        conn.close()

    if not worker_data:
        flash("No user data found for your ward.", "info")

    return render_template('worker/worker_dashboard.html', worker_data=worker_data)

@worker_routes.route('/worker/logout')
def worker_logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('central_routes.central_login'))
