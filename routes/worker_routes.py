from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, g
from flask_mail import Message
from datetime import datetime
import base64

worker_routes = Blueprint('worker_routes', __name__, template_folder='../templates/worker')

@worker_routes.route('/worker/dashboard', methods=['GET', 'POST'])
def worker_dashboard():
    # Ensure only logged-in workers can access
    if 'user_id' not in session or session.get('role') != 'worker':
        flash("Please log in first.", "warning")
        return redirect(url_for('central_routes.central_login'))

    ward_id = session.get('ward_id')

    if request.method == 'POST':
        visited_ids = request.form.getlist('visited_ids')
        if visited_ids:
            try:
                loc_cursor = g.location_db.cursor()
                staff_cursor = g.staff_db.cursor()
                mail = current_app.extensions['mail']

                for link_id in visited_ids:
                    # Fetch record from user_data
                    loc_cursor.execute("""
                        SELECT name, email, latitude, longitude, ward_id, ward_name, image
                        FROM user_data WHERE id = %s
                    """, (link_id,))
                    row = loc_cursor.fetchone()

                    if row:
                        name, email, lat, lon, ward_id, ward_name, image = row

                        # Get worker uploaded image file for this user
                        worker_file = request.files.get(f'new_image_{link_id}')
                        worker_image_data = None
                        if worker_file and worker_file.filename != '':
                            worker_image_data = worker_file.read()

                        # Insert into visited_links including worker_image if available
                        staff_cursor.execute("""
                            INSERT INTO visited_links (name, latitude, longitude, ward_id, visited_at, email, image, worker_image)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            name,
                            lat,
                            lon,
                            ward_id,
                            datetime.now(),
                            email,
                            image,
                            worker_image_data
                        ))

                        # Delete the visited user from original table
                        loc_cursor.execute("DELETE FROM user_data WHERE id = %s", (link_id,))

                        # Send notification email with worker image attached if exists
                        msg = Message(
                            subject="Your location has been visited!",
                            sender='swachhindiamission@gmail.com',
                            recipients=[email],
                            body=(
                                f"Dear {name},\n\n"
                                f"A worker has visited your submitted location in the area: {ward_name}.\n"
                                f"Visited At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                "Thank you for supporting the Swachh Bharat Mission. Keep encouraging others to participate!"
                            )
                        )
                        if worker_image_data:
                            msg.attach("worker_image.jpg", "image/jpeg", worker_image_data)

                        mail.send(msg)

                g.location_db.commit()
                g.staff_db.commit()
                flash("Selected locations marked as visited and emails sent.", "success")

            except Exception as e:
                g.location_db.rollback()
                g.staff_db.rollback()
                flash(f"Error processing visited entries: {e}", "danger")

            finally:
                loc_cursor.close()
                staff_cursor.close()

            return redirect(url_for('worker_routes.worker_dashboard'))

    # GET method – show user data
    try:
        cursor = g.location_db.cursor()
        cursor.execute("""
            SELECT id, name, longitude, latitude, ward_id, image, ward_name
            FROM user_data WHERE ward_id = %s
        """, (ward_id,))
        rows = cursor.fetchall()

        worker_data = []
        for row in rows:
            image_encoded = base64.b64encode(row[5]).decode('utf-8') if row[5] else ''
            worker_data.append({
                'id': row[0],
                'name': row[1],
                'longitude': row[2],
                'latitude': row[3],
                'ward_id': row[4],
                'image': image_encoded,
                'ward_name': row[6]
            })

    except Exception as e:
        flash(f"Error loading user data: {e}", "danger")
        worker_data = []

    finally:
        cursor.close()

    if not worker_data:
        flash("No user submissions available for your ward.", "info")

    return render_template('worker/worker_dashboard.html', worker_data=worker_data)


@worker_routes.route('/worker/logout')
def worker_logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('central_routes.central_login'))

