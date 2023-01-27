import sqlite3

from flask import Flask, json, render_template, request, url_for, redirect, flash
import subprocess
import logging

DATABASE_FILE = 'database.db'
PORT = '3111'

# Function to get a database connection.
# This function connects to database with the name `database.db`
def get_db_connection():
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection

# Function to get a post using its ID
def get_post(post_id):
    connection = get_db_connection()
    post = connection.execute('SELECT * FROM posts WHERE id = ?',
                              (post_id,)).fetchone()
    connection.close()
    return post


def get_db_connection_count():
    """Counts the number of current connections to the DATABASE_FILE.

    get_db_connection_count() will list open files on DATABASE_FILE using lsof command and count the number of open connections.

    Returns:
        int: returns the number of current connections to the DATABASE_FILE and -1 on error
    """
    try:
        TIMEOUT = 20
        p1 = subprocess.Popen(["lsof", DATABASE_FILE], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(
            ["wc", "-l"], stdin=p1.stdout, stdout=subprocess.PIPE)
        # extract the the 1st element of the output tuple, then convert the bytes to string then remove the new line from string then subtract 1 to ignore header line
        db_connection_count = int(p2.communicate(timeout=TIMEOUT)[
                                  0].decode("utf-8").replace('\n', '')) - 1
        db_connection_count = 0 if db_connection_count == -1 else db_connection_count
        app.logger.debug(f"db_connection_count: {db_connection_count}")
    except subprocess.TimeoutExpired:
        p2.kill()
        app.logger.error(f"Error: process exceeded {TIMEOUT}")
        db_connection_count = -1
    except sqlite3.OperationalError as e:
        app.logger.error(f"Error: {e}")
        db_connection_count = -1
    return db_connection_count


def get_posts_count():
    """Counts the number of Posts available in the posts table.

    get_posts_count() will perform an SQL query against posts table to get the count of the current rows and will return
    the count on success and -1 on sqlite3.OperationalError Exception.

    Returns:
        int: returns the number of the posts rows in the posts table on success and -1 on failure
    """
    try:
        cur = get_db_connection().cursor()
        result = cur.execute(
            'SELECT count(*) AS post_count FROM posts').fetchone()
        app.logger.debug(f"post_count: {result['post_count']}")
    except sqlite3.OperationalError as e:
        result['post_count'] = -1
        app.logger.error(f"Error: {e}")
    finally:
        cur.close()
    return result['post_count']


# Define the Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your secret key'

# Define the main route of the web application
@app.route('/')
def index():
    connection = get_db_connection()
    posts = connection.execute('SELECT * FROM posts').fetchall()
    connection.close()
    return render_template('index.html', posts=posts)

# Define how each individual article is rendered
# If the post ID is not found a 404 page is shown
@app.route('/<int:post_id>')
def post(post_id):
    post = get_post(post_id)
    if post is None:
        app.logger.info(f"Article with id \"{post_id}\" is not found!")
        return render_template('404.html'), 404
    else:
        app.logger.info(f"Article \"{post['title']}\" retrieved!")
        return render_template('post.html', post=post)

# Define the About Us page
@app.route('/about')
def about():
    app.logger.info("About page retrieved!")
    return render_template('about.html')

# Define the post creation functionality
@app.route('/create', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title:
            flash('Title is required!')
        else:
            connection = get_db_connection()
            connection.execute('INSERT INTO posts (title, content) VALUES (?, ?)',
                               (title, content))
            connection.commit()
            connection.close()

            app.logger.info(f"New Article \"{title}\" created!")
            return redirect(url_for('index'))

    return render_template('create.html')


@app.route('/healthz')
def healthz():
    """Validates application health.

    healthz() will check the connection with SQLite database by starting a connection and performing a test query. healthz() will perform the
    following checks:
        - check if DATABASE_FILE exists.
        - execute simple test query
        - execute simple test query against 'posts' table

    Returns:
        json: a JSON object with 'result' key holding the state of the application health and 'reason' key in case the application is unhealthy
    """
    res = dict()
    status_code = 200
    conn = None
    try:
        app.logger.debug("Openning test database connection")
        # will fail if DATABASE_FILE doesn't exist
        conn = sqlite3.connect(f"file:{DATABASE_FILE}?mode=rw", uri=True)
        if conn:
            cur = conn.cursor()
            # simple test query
            app.logger.debug("Executing test query")
            cur.execute('SELECT 1').fetchone()
            app.logger.debug("Test query is successful")
            app.logger.debug("Executing test query on \"posts\" table")
            cur.execute('SELECT 1 FROM posts').fetchone()
            app.logger.debug("Test query is successful")
    except sqlite3.OperationalError as e:
        result = 'NOT OK - unhealthy'
        status_code = 500
        res['reason'] = str(e)
        app.logger.error(f"Error: failed healthcheck, {str(e)}")
    except Exception as e:
        result = 'NOT OK - unhealthy'
        status_code = 500
        res['reason'] = str(e)
        app.logger.error(f"Error: failed healthcheck, {str(e)}")
    else:
        result = 'OK - healthy'
    finally:
        if conn:
            app.logger.debug("Closing database connection")
            conn.close()
        res['result'] = result
        return app.response_class(
            response=json.dumps(res),
            status=status_code,
            mimetype='application/json'
        )


@app.route('/metrics')
def metrics():
    """Collects basic TechTrends basic metrics.

    metrics() will collect two metrics; the count of the current posts within posts table and the number of current database connections.

    Returns:
        json: a JSON object with 'db_connection_count' key holding the total amount of the current connections to DATABASE_FILE and 'post_count' key 
        holding the total amount of posts in the database
    """
    res = dict()
    status_code = 200
    try:
        db_connection_count = get_db_connection_count()
        post_count = get_posts_count()
    except Exception as e:
        status_code = 500
        res['error'] = str(e)
        app.logger.error(f"MetricsError: {e}")
    else:
        res['db_connection_count'] = db_connection_count
        res['post_count'] = post_count
        app.logger.debug(f"metrics: {json.dumps(res)}")
    finally:
        return app.response_class(
            response=json.dumps(res),
            status=status_code,
            mimetype='application/json'
        )


# start the application on port 3111
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)s:%(name)s:%(asctime)s, %(message)s",
                        datefmt='%d/%m/%y, %H:%M:%S')
    app.run(host='0.0.0.0', port=PORT)
