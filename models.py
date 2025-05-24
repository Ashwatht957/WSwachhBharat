from app import db

# Default DB (location)
class UserData(db.Model):
    __tablename__ = 'user_data'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    image = db.Column(db.LargeBinary)
    ward_id = db.Column(db.Integer, db.ForeignKey('wards.id'), nullable=True)
    ward_name = db.Column(db.String(255), nullable=False)

class Ward(db.Model):
    __tablename__ = 'wards'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

# Staff DB
class Staff(db.Model):
    __bind_key__ = 'staff'
    __tablename__ = 'staff'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum('worker', 'admin', name='role_enum'), nullable=False)
    ward_id = db.Column(db.Integer)
    email = db.Column(db.String(255), nullable=False)

class VisitedLink(db.Model):
    __bind_key__ = 'staff'
    __tablename__ = 'visited_links'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    ward_id = db.Column(db.Integer, nullable=False)
    visited_at = db.Column(db.DateTime, server_default=db.func.now())
    email = db.Column(db.String(255), nullable=False)
    image = db.Column(db.LargeBinary, nullable=False)
    worker_image = db.Column(db.LargeBinary, nullable=False)
