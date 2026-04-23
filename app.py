from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = 'owlswap-secret-key-change-in-production'

DB_PATH = 'owlswap.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT    UNIQUE NOT NULL,
        email    TEXT    UNIQUE NOT NULL,
        password TEXT    NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS listings (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        title      TEXT    NOT NULL,
        course     TEXT    NOT NULL,
        dept       TEXT    NOT NULL,
        category   TEXT    NOT NULL,
        type       TEXT    NOT NULL,
        price      TEXT    NOT NULL,
        emoji      TEXT    DEFAULT '��',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS threads (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        title      TEXT    NOT NULL,
        course     TEXT    NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id  INTEGER NOT NULL,
        user_id    INTEGER NOT NULL,
        body       TEXT    NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (thread_id) REFERENCES threads(id),
        FOREIGN KEY (user_id)   REFERENCES users(id))''')
    conn.commit()
    conn.close()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if 'user_id' in session:
        return redirect(url_for('marketplace'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'signup':
            username = request.form.get('username', '').strip()
            email    = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            if not username or not email or not password:
                flash('All fields are required.', 'error')
                return redirect(url_for('auth') + '?tab=signup')
            conn = get_db()
            try:
                conn.execute(
                    'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                    (username, email, generate_password_hash(password)))
                conn.commit()
                user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
                session['user_id']  = user['id']
                session['username'] = user['username']
                return redirect(url_for('marketplace'))
            except sqlite3.IntegrityError:
                flash('Username or email already taken.', 'error')
                return redirect(url_for('auth') + '?tab=signup')
            finally:
                conn.close()
        elif action == 'login':
            email    = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            conn = get_db()
            user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            conn.close()
            if user and check_password_hash(user['password'], password):
                session['user_id']  = user['id']
                session['username'] = user['username']
                return redirect(url_for('marketplace'))
            else:
                flash('Invalid email or password.', 'error')
                return redirect(url_for('auth') + '?tab=login')
    return render_template('auth.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/marketplace')
@login_required
def marketplace():
    dept     = request.args.get('dept', 'all')
    type_    = request.args.get('type', 'all')
    category = request.args.get('category', 'all')
    search   = request.args.get('search', '').strip()
    conn  = get_db()
    query = 'SELECT listings.*, users.username FROM listings JOIN users ON listings.user_id = users.id WHERE 1=1'
    params = []
    if dept != 'all':
        query += ' AND dept = ?'
        params.append(dept)
    if type_ != 'all':
        query += ' AND type = ?'
        params.append(type_)
    if category != 'all':
        query += ' AND category = ?'
        params.append(category)
    if search:
        query += ' AND (title LIKE ? OR course LIKE ?)'
        params += [f'%{search}%', f'%{search}%']
    query += ' ORDER BY created_at DESC'
    listings = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('marketplace.html',
                           listings=listings,
                           active_dept=dept,
                           active_type=type_,
                           active_category=category,
                           search=search)

@app.route('/my-listings')
@login_required
def my_listings():
    conn = get_db()
    listings = conn.execute(
        'SELECT * FROM listings WHERE user_id = ? ORDER BY created_at DESC',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('my_listings.html', listings=listings)

@app.route('/listing/new', methods=['GET', 'POST'])
@login_required
def new_listing():
    if request.method == 'POST':
        title    = request.form.get('title', '').strip()
        course   = request.form.get('course', '').strip()
        dept     = request.form.get('dept', '').strip()
        category = request.form.get('category', '').strip()
        type_    = request.form.get('type', '').strip()
        price    = request.form.get('price', '').strip()
        emoji    = request.form.get('emoji', '📚').strip()
        if not all([title, course, dept, category, type_, price]):
            flash('All fields are required.', 'error')
            return redirect(url_for('new_listing'))
        conn = get_db()
        conn.execute(
            'INSERT INTO listings (user_id, title, course, dept, category, type, price, emoji) VALUES (?,?,?,?,?,?,?,?)',
            (session['user_id'], title, course, dept, category, type_, price, emoji))
        conn.commit()
        conn.close()
        return redirect(url_for('marketplace'))
    return render_template('new_listing.html')

@app.route('/listing/delete/<int:listing_id>', methods=['POST'])
@login_required
def delete_listing(listing_id):
    conn    = get_db()
    listing = conn.execute('SELECT * FROM listings WHERE id = ?', (listing_id,)).fetchone()
    if listing and listing['user_id'] == session['user_id']:
        conn.execute('DELETE FROM listings WHERE id = ?', (listing_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('my_listings'))

@app.route('/threads')
@login_required
def threads():
    conn = get_db()
    threads = conn.execute('''
        SELECT threads.*, users.username,
               COUNT(posts.id) AS reply_count
        FROM threads
        JOIN users ON threads.user_id = users.id
        LEFT JOIN posts ON posts.thread_id = threads.id
        GROUP BY threads.id
        ORDER BY threads.created_at DESC''').fetchall()
    conn.close()
    return render_template('threads.html', threads=threads)

@app.route('/thread/new', methods=['GET', 'POST'])
@login_required
def new_thread():
    if request.method == 'POST':
        title  = request.form.get('title', '').strip()
        course = request.form.get('course', '').strip()
        body   = request.form.get('body', '').strip()
        if not title or not course or not body:
            flash('All fields are required.', 'error')
            return redirect(url_for('new_thread'))
        conn = get_db()
        cur  = conn.execute(
            'INSERT INTO threads (user_id, title, course) VALUES (?,?,?)',
            (session['user_id'], title, course))
        thread_id = cur.lastrowid
        conn.execute(
            'INSERT INTO posts (thread_id, user_id, body) VALUES (?,?,?)',
            (thread_id, session['user_id'], body))
        conn.commit()
        conn.close()
        return redirect(url_for('thread', thread_id=thread_id))
    return render_template('new_thread.html')

@app.route('/thread/<int:thread_id>', methods=['GET', 'POST'])
@login_required
def thread(thread_id):
    conn = get_db()
    t = conn.execute(
        'SELECT threads.*, users.username FROM threads JOIN users ON threads.user_id = users.id WHERE threads.id = ?',
        (thread_id,)).fetchone()
    if not t:
        conn.close()
        return redirect(url_for('threads'))
    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if body:
            conn.execute(
                'INSERT INTO posts (thread_id, user_id, body) VALUES (?,?,?)',
                (thread_id, session['user_id'], body))
            conn.commit()
        conn.close()
        return redirect(url_for('thread', thread_id=thread_id))
    posts = conn.execute('''
        SELECT posts.*, users.username
        FROM posts JOIN users ON posts.user_id = users.id
        WHERE posts.thread_id = ?
        ORDER BY posts.created_at ASC''', (thread_id,)).fetchall()
    related = conn.execute(
        'SELECT * FROM listings WHERE course LIKE ? LIMIT 3',
        (f'%{t["course"]}%',)).fetchall()
    conn.close()
    return render_template('thread.html', thread=t, posts=posts, related=related)

@app.route('/post/delete/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    conn = get_db()
    post = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    if post and post['user_id'] == session['user_id']:
        thread_id = post['thread_id']
        conn.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('thread', thread_id=thread_id))
    conn.close()
    return redirect(url_for('threads'))

if __name__ == '__main__':
    init_db()
    print("OwlSwap running at http://127.0.0.1:5000")
    app.run(debug=True)
