import os
import random
from datetime import datetime

import pymysql
import pymysql.cursors
from flask import Flask, request, jsonify, session, send_file, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config.update(
    SECRET_KEY='cityserve-secret-key-2026',
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_HTTPONLY=True,
    UPLOAD_FOLDER=os.path.join(BASE_DIR, 'uploads'),
    MAX_CONTENT_LENGTH=5 * 1024 * 1024  # 5 MB max upload
)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DB_CONFIG = dict(
    host     = 'localhost',
    port     = 3306,
    user     = 'root',
    password = '',
    database = 'cityserve',
    charset  = 'utf8mb4',
    cursorclass = pymysql.cursors.DictCursor,   # rows returned as dicts
)

def get_db():
    """Open a fresh MySQL connection for each request."""
    return pymysql.connect(**DB_CONFIG)


@app.route('/')
def serve_index():
    return send_file(os.path.join(BASE_DIR, 'index.html'))

@app.route('/<filename>.html')
def serve_html(filename):
    path = os.path.join(BASE_DIR, f'{filename}.html')
    if os.path.exists(path):
        return send_file(path)
    return 'Page not found', 404

@app.route('/css/<path:fn>')
def serve_css(fn):
    return send_from_directory(os.path.join(BASE_DIR, 'css'), fn)

@app.route('/js/<path:fn>')
def serve_js(fn):
    return send_from_directory(os.path.join(BASE_DIR, 'js'), fn)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def _fresh_issue_number(cursor):
    """Generate a unique REQ-XXXX number."""
    while True:
        num = 'REQ-' + str(random.randint(1000, 9999))
        cursor.execute("SELECT id FROM issues WHERE issue_number = %s", (num,))
        if not cursor.fetchone():
            return num

def _user_to_dict(row):
    return dict(id=row['id'], name=row['name'], email=row['email'],
                phone=row.get('phone', ''), role='user')

def _authority_to_dict(row):
    return dict(id=row['id'], name=row['name'], email=row['email'],
                department=row['department'], role='authority')

def _issue_to_dict(row):
    created = row['created_at']
    date_str = created.strftime('%Y-%m-%d') if hasattr(created, 'strftime') else str(created)
    return dict(
        id           = row['id'],
        issue_number = row['issue_number'],
        category     = row['category'],
        description  = row['description'],
        location     = row['location'],
        lat          = row['lat'],
        lng          = row['lng'],
        status       = row['status'],
        date         = date_str,
        personnel    = row.get('personnel_name'),
        personnel_phone = row.get('personnel_phone'),
        personnel_id = row['personnel_id'],
        has_feedback = bool(row.get('has_feedback', 0)),
        image_url    = f"/uploads/{row['image_path']}" if row.get('image_path') else None,
        completion_image_url = f"/uploads/{row['completion_image_path']}" if row.get('completion_image_path') else None
    )


@app.route('/api/auth/register', methods=['POST'])
def register():
    d     = request.get_json(force=True)
    name  = d.get('name', '').strip()
    email = d.get('email', '').strip().lower()
    pwd   = d.get('password', '')
    phone = d.get('phone', '').strip()

    if not name or not email or not pwd:
        return jsonify({'error': 'Name, email and password are required.'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            # Check duplicate email
            cur.execute("SELECT id FROM users WHERE LOWER(email) = %s", (email,))
            if cur.fetchone():
                return jsonify({'error': 'An account with this email already exists.'}), 409

            pwd_hash = generate_password_hash(pwd)
            cur.execute(
                "INSERT INTO users (name, email, password_hash, phone, created_at) VALUES (%s, %s, %s, %s, NOW())",
                (name, email, pwd_hash, phone)
            )
            conn.commit()
            user_id = cur.lastrowid

        session['user_id'] = user_id
        session['role']    = 'user'
        return jsonify({'user': dict(id=user_id, name=name, email=email,
                                     phone=phone, role='user')}), 201
    finally:
        conn.close()


@app.route('/api/auth/login', methods=['POST'])
def login():
    d          = request.get_json(force=True)
    identifier = d.get('email', '').strip()   
    pwd        = d.get('password', '')
    role       = d.get('role', 'user')

    conn = get_db()
    try:
        with conn.cursor() as cur:
            if role == 'authority':
                cur.execute(
                    "SELECT * FROM authorities WHERE LOWER(email) = %s",
                    (identifier.lower(),)
                )
                auth = cur.fetchone()
                if not auth:
                    return jsonify({'error': 'Invalid credentials.'}), 401
                if not check_password_hash(auth['password_hash'], pwd):
                    return jsonify({'error': 'Invalid credentials.'}), 401
                session['authority_id'] = auth['id']
                session['role']         = 'authority'
                return jsonify({'user': _authority_to_dict(auth)})
            else:
                cur.execute(
                    "SELECT * FROM users WHERE LOWER(email) = %s",
                    (identifier.lower(),)
                )
                user = cur.fetchone()
                if not user:
                    cur.execute(
                        "SELECT * FROM users WHERE LOWER(name) = %s",
                        (identifier.lower(),)
                    )
                    user = cur.fetchone()

                if not user:
                    return jsonify({'error': 'Invalid email/username or password.'}), 401
                if not check_password_hash(user['password_hash'], pwd):
                    return jsonify({'error': 'Invalid email/username or password.'}), 401
                session['user_id'] = user['id']
                session['role']    = 'user'
                return jsonify({'user': _user_to_dict(user)})
    finally:
        conn.close()


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out.'})


@app.route('/api/auth/me')
def me():
    role = session.get('role')
    if not role:
        return jsonify({'user': None}), 401

    conn = get_db()
    try:
        with conn.cursor() as cur:
            if role == 'user':
                cur.execute("SELECT * FROM users WHERE id = %s", (session.get('user_id'),))
                row = cur.fetchone()
                if not row:
                    return jsonify({'user': None}), 401
                return jsonify({'user': _user_to_dict(row)})
            else:
                cur.execute("SELECT * FROM authorities WHERE id = %s", (session.get('authority_id'),))
                row = cur.fetchone()
                if not row:
                    return jsonify({'user': None}), 401
                return jsonify({'user': _authority_to_dict(row)})
    finally:
        conn.close()


@app.route('/api/issues', methods=['POST'])
def create_issue():
    if session.get('role') != 'user':
        return jsonify({'error': 'Login required.'}), 401

    if request.content_type and "multipart/form-data" in request.content_type:
        d = request.form
    else:
        d = request.get_json(force=True)

    category    = d.get('category', '').strip()
    description = d.get('description', '').strip()
    location    = d.get('location', '').strip()
    lat         = d.get('lat')
    lng         = d.get('lng')

    if not category or not description or not location:
        return jsonify({'error': 'Category, description and location are required.'}), 400

    image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            filename = secure_filename(file.filename)
            unique_filename = f"{int(datetime.utcnow().timestamp())}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            image_path = unique_filename

    conn = get_db()
    try:
        with conn.cursor() as cur:
            issue_num = _fresh_issue_number(cur)
            cur.execute(
                """INSERT INTO issues
                   (issue_number, user_id, category, description, location, lat, lng, image_path, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
                (issue_num, session['user_id'], category, description, location, lat, lng, image_path)
            )
            conn.commit()
            issue_id = cur.lastrowid

            cur.execute("SELECT * FROM issues WHERE id = %s", (issue_id,))
            row = cur.fetchone()
            row['personnel_name']  = None
            row['personnel_phone'] = None
            row['has_feedback']    = 0
            return jsonify({'issue': _issue_to_dict(row)}), 201
    finally:
        conn.close()


@app.route('/api/issues')
def get_issues():
    if session.get('role') != 'user':
        return jsonify({'error': 'Login required.'}), 401

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT i.*,
                          p.name  AS personnel_name,
                          p.phone AS personnel_phone,
                          (SELECT COUNT(*) FROM feedback f WHERE f.issue_id = i.id) AS has_feedback
                   FROM issues i
                   LEFT JOIN personnel p ON p.id = i.personnel_id
                   WHERE i.user_id = %s
                   ORDER BY i.created_at DESC""",
                (session['user_id'],)
            )
            rows = cur.fetchall()
        return jsonify({'issues': [_issue_to_dict(r) for r in rows]})
    finally:
        conn.close()


@app.route('/api/issues/<issue_ref>')
def get_issue(issue_ref):
    if not session.get('role'):
        return jsonify({'error': 'Login required.'}), 401

    conn = get_db()
    try:
        with conn.cursor() as cur:
            sql = """SELECT i.*,
                            p.name  AS personnel_name,
                            p.phone AS personnel_phone,
                            (SELECT COUNT(*) FROM feedback f WHERE f.issue_id = i.id) AS has_feedback
                     FROM issues i
                     LEFT JOIN personnel p ON p.id = i.personnel_id
                     WHERE {}"""

            if str(issue_ref).upper().startswith('REQ-'):
                cur.execute(sql.format("i.issue_number = %s"), (issue_ref.upper(),))
            else:
                cur.execute(sql.format("i.id = %s"), (int(issue_ref),))

            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'No request found with that ID.'}), 404
            return jsonify({'issue': _issue_to_dict(row)})
    finally:
        conn.close()

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    if session.get('role') != 'user':
        return jsonify({'error': 'Login required.'}), 401

    d        = request.get_json(force=True)
    issue_id = d.get('issue_id')
    rating   = d.get('rating')
    comments = d.get('comments', '')

    if not issue_id or not rating:
        return jsonify({'error': 'Issue ID and rating are required.'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM issues WHERE id = %s", (issue_id,))
            if not cur.fetchone():
                return jsonify({'error': 'Issue not found.'}), 404

            cur.execute(
                "SELECT id FROM feedback WHERE issue_id = %s AND user_id = %s",
                (issue_id, session['user_id'])
            )
            if cur.fetchone():
                return jsonify({'error': 'You have already submitted feedback for this issue.'}), 409

            cur.execute(
                "INSERT INTO feedback (issue_id, user_id, rating, comments, created_at) VALUES (%s, %s, %s, %s, NOW())",
                (issue_id, session['user_id'], int(rating), comments)
            )
            conn.commit()
        return jsonify({'message': 'Feedback submitted successfully.'})
    finally:
        conn.close()


DEPT_CATEGORY = {
    'Kerala Water Authority':        'Water Supply',
    'Waste Management Corporation':  'Waste Management',
    'Kerala State Electricity Board':'Street Lighting',
    'Public Works Department':       'Road Maintenance',
    'Municipality':                  'Sanitation',
}


@app.route('/api/authority/issues')
def authority_issues():
    if session.get('role') != 'authority':
        return jsonify({'error': 'Authority login required.'}), 401

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT department FROM authorities WHERE id = %s",
                        (session['authority_id'],))
            auth = cur.fetchone()
            if not auth:
                return jsonify({'error': 'Authority not found.'}), 404

            category = DEPT_CATEGORY.get(auth['department'])
            if not category:
                return jsonify({'issues': []})

            cur.execute(
                """SELECT i.*,
                          p.name  AS personnel_name,
                          p.phone AS personnel_phone,
                          (SELECT COUNT(*) FROM feedback f WHERE f.issue_id = i.id) AS has_feedback
                   FROM issues i
                   LEFT JOIN personnel p ON p.id = i.personnel_id
                   WHERE i.category = %s
                   ORDER BY i.created_at DESC""",
                (category,)
            )
            rows = cur.fetchall()
        return jsonify({'issues': [_issue_to_dict(r) for r in rows]})
    finally:
        conn.close()


@app.route('/api/authority/issues/<int:issue_id>', methods=['PUT'])
def update_issue(issue_id):
    if session.get('role') != 'authority':
        return jsonify({'error': 'Authority login required.'}), 401

    # Accept both JSON and multipart/form-data
    is_multipart = request.content_type and 'multipart/form-data' in request.content_type
    if is_multipart:
        d = request.form
    else:
        d = request.get_json(force=True)

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM issues WHERE id = %s", (issue_id,))
            if not cur.fetchone():
                return jsonify({'error': 'Issue not found.'}), 404

            fields, values = [], []
            if 'status' in d:
                fields.append("status = %s")
                values.append(d['status'])
            if 'personnel_id' in d:
                pid = d['personnel_id']
                fields.append("personnel_id = %s")
                values.append(int(pid) if pid else None)

            # Handle completion image upload
            if is_multipart and 'completion_image' in request.files:
                file = request.files['completion_image']
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    unique_filename = f"done_{issue_id}_{int(datetime.utcnow().timestamp())}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                    fields.append("completion_image_path = %s")
                    values.append(unique_filename)

            if fields:
                values.append(issue_id)
                cur.execute(
                    f"UPDATE issues SET {', '.join(fields)} WHERE id = %s",
                    values
                )
                conn.commit()

            cur.execute(
                """SELECT i.*,
                          p.name  AS personnel_name,
                          p.phone AS personnel_phone,
                          (SELECT COUNT(*) FROM feedback f WHERE f.issue_id = i.id) AS has_feedback
                   FROM issues i
                   LEFT JOIN personnel p ON p.id = i.personnel_id
                   WHERE i.id = %s""",
                (issue_id,)
            )
            row = cur.fetchone()
        return jsonify({'issue': _issue_to_dict(row)})
    finally:
        conn.close()


@app.route('/api/authority/personnel')
def get_personnel():
    if session.get('role') != 'authority':
        return jsonify({'error': 'Authority login required.'}), 401

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, phone FROM personnel WHERE authority_id = %s",
                (session['authority_id'],)
            )
            rows = cur.fetchall()
        return jsonify({'personnel': list(rows)})
    finally:
        conn.close()


@app.route('/api/authority/personnel', methods=['POST'])
def add_personnel():
    if session.get('role') != 'authority':
        return jsonify({'error': 'Authority login required.'}), 401

    d     = request.get_json(force=True)
    name  = d.get('name', '').strip()
    phone = d.get('phone', '').strip()

    if not name or not phone:
        return jsonify({'error': 'Name and phone are required.'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO personnel (authority_id, name, phone) VALUES (%s, %s, %s)",
                (session['authority_id'], name, phone)
            )
            conn.commit()
            pid = cur.lastrowid
        return jsonify({'person': dict(id=pid, name=name, phone=phone)}), 201
    finally:
        conn.close()

@app.route('/api/authority/report')
def authority_report():
    if session.get('role') != 'authority':
        return jsonify({'error': 'Authority login required.'}), 401

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT department FROM authorities WHERE id = %s",
                        (session['authority_id'],))
            auth = cur.fetchone()
            if not auth:
                return jsonify({'error': 'Authority not found.'}), 404

            category = DEPT_CATEGORY.get(auth['department'])
            if not category:
                return jsonify({'error': 'No category mapped.'}), 404

            cur.execute("SELECT COUNT(*) AS cnt FROM issues WHERE category = %s", (category,))
            total_all = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) AS cnt FROM issues WHERE category = %s AND status = 'Work done'", (category,))
            resolved_all = cur.fetchone()['cnt']

            cur.execute("SELECT COUNT(*) AS cnt FROM issues WHERE category = %s AND status != 'Work done'", (category,))
            pending_all = cur.fetchone()['cnt']

            cur.execute(
                """SELECT AVG(f.rating) AS avg_rating, COUNT(f.id) AS feedback_count
                   FROM feedback f
                   JOIN issues i ON i.id = f.issue_id
                   WHERE i.category = %s""", (category,))
            fb_all = cur.fetchone()

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM issues WHERE category = %s AND MONTH(created_at) = MONTH(NOW()) AND YEAR(created_at) = YEAR(NOW())",
                (category,))
            total_month = cur.fetchone()['cnt']

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM issues WHERE category = %s AND status = 'Work done' AND MONTH(created_at) = MONTH(NOW()) AND YEAR(created_at) = YEAR(NOW())",
                (category,))
            resolved_month = cur.fetchone()['cnt']

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM issues WHERE category = %s AND status != 'Work done' AND MONTH(created_at) = MONTH(NOW()) AND YEAR(created_at) = YEAR(NOW())",
                (category,))
            pending_month = cur.fetchone()['cnt']

            cur.execute(
                """SELECT AVG(f.rating) AS avg_rating, COUNT(f.id) AS feedback_count
                   FROM feedback f
                   JOIN issues i ON i.id = f.issue_id
                   WHERE i.category = %s
                   AND MONTH(f.created_at) = MONTH(NOW()) AND YEAR(f.created_at) = YEAR(NOW())""",
                (category,))
            fb_month = cur.fetchone()

            cur.execute(
                "SELECT id, name, phone FROM personnel WHERE authority_id = %s",
                (session['authority_id'],))
            personnel = cur.fetchall()

            cur.execute(
                """SELECT i.issue_number, i.description, i.location, i.status,
                          i.created_at AS issue_date,
                          p.name AS personnel_name,
                          f.rating, f.comments AS feedback_comment, f.created_at AS feedback_date
                   FROM issues i
                   LEFT JOIN personnel p ON p.id = i.personnel_id
                   LEFT JOIN feedback f ON f.issue_id = i.id
                   WHERE i.category = %s
                   ORDER BY i.created_at DESC
                   LIMIT 50""",
                (category,))
            recent = cur.fetchall()
            for r in recent:
                if r.get('issue_date') and hasattr(r['issue_date'], 'strftime'):
                    r['issue_date'] = r['issue_date'].strftime('%Y-%m-%d')
                if r.get('feedback_date') and hasattr(r['feedback_date'], 'strftime'):
                    r['feedback_date'] = r['feedback_date'].strftime('%Y-%m-%d')

        return jsonify({
            'department': auth['department'],
            'category': category,
            'all_time': {
                'total': total_all,
                'resolved': resolved_all,
                'pending': pending_all,
                'avg_rating': round(float(fb_all['avg_rating']), 1) if fb_all['avg_rating'] else None,
                'feedback_count': fb_all['feedback_count'],
            },
            'this_month': {
                'total': total_month,
                'resolved': resolved_month,
                'pending': pending_month,
                'avg_rating': round(float(fb_month['avg_rating']), 1) if fb_month['avg_rating'] else None,
                'feedback_count': fb_month['feedback_count'],
            },
            'personnel': list(personnel),
            'recent_issues': list(recent),
        })
    finally:
        conn.close()


AUTHORITY_SEEDS = [
    ('Kerala Water Authority Admin',       'admin@kwa.kerala.gov.in',          'kwa@1234',  'Kerala Water Authority'),
    ('Waste Management Corporation Admin', 'admin@wmc.kerala.gov.in',          'wmc@1234',  'Waste Management Corporation'),
    ('KSEB Admin',                         'admin@kseb.kerala.gov.in',         'kseb@1234', 'Kerala State Electricity Board'),
    ('Public Works Department Admin',      'admin@pwd.kerala.gov.in',          'pwd@1234',  'Public Works Department'),
    ('Municipality Admin',                 'admin@municipality.kerala.gov.in', 'mun@1234',  'Municipality'),
]


def seed_authorities():
    """Insert default authority accounts if they don't already exist."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            for name, email, pwd, dept in AUTHORITY_SEEDS:
                cur.execute("SELECT id FROM authorities WHERE email = %s", (email,))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO authorities (name, email, password_hash, department) VALUES (%s,%s,%s,%s)",
                        (name, email, generate_password_hash(pwd), dept)
                    )
        conn.commit()
    finally:
        conn.close()

if __name__ == '__main__':
    seed_authorities()
    print("\n[OK] CityServe backend ready at http://localhost:5000")
    print("     Authority credentials:")
    for _, email, pwd, dept in AUTHORITY_SEEDS:
        print(f"     {dept:<40} {email}  /  {pwd}")
    print()
    app.run(debug=True, port=5000)
