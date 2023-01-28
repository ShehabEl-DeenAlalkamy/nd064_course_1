import sqlite3

from flask import Flask, json, render_template, request, url_for, redirect, flash
import subprocess
import logging
import platform
import sys

DATABASE_FILE = 'database.db'
PORT = '3111'


class DB_Connection:
    """
    A class to represent SQLite database open connection counter.

    ...

    Attributes
    ----------
    count_healthchecks : bool
        whether to count open connections made at /healthz

    Methods
    -------
    increment():
        increase self.counter by 1.
    """

    def __init__(self, count_healthchecks=False):
        self.count = 0
        self.count_healthchecks = count_healthchecks

    def __str__(self):
        return f"{self.count}"

    def increment(self):
        """Increments self.count by 1

        Returns:
            None
        """
        self.count += 1
        return


class SingleLevelFilter(logging.Filter):
    """
    A class to represent a single logging level filter.

    ...

    Attributes
    ----------
    passlevel : int
        log level to pass
    reject : bool
        whether to reject self.passlevel 

    Methods
    -------
    filter(record):
        compares incoming logging records level no and either filter them to self.passlevel only and if self.reject=True it will reject those with 
        same self.passlevel.
    """

    def __init__(self, passlevel, reject):
        self.passlevel = passlevel
        self.reject = reject

    def filter(self, record):
        """Filters incoming logging record.

        Returns:
            compares incoming logging records level no and either filter them to self.passlevel only and if self.reject=True it will reject those with 
            same self.passlevel.
        """
        if self.reject:
            return (record.levelno != self.passlevel)
        else:
            return (record.levelno == self.passlevel)


class MaxLevelFilter(logging.Filter):
    """
    A class to represent a maximum logging level filter.

    ...

    Attributes
    ----------
    maxlevel : int
        maximum log level

    Methods
    -------
    filter(record):
        compares incoming logging records level no and accept it if record.levelno < self.maxlevel.
    """

    def __init__(self, maxlevel):
        self.maxlevel = maxlevel

    def filter(self, record):
        """Filters incoming logging record.

        Returns:
            compares incoming logging records level no and accept it if record.levelno < self.maxlevel.
        """
        return record.levelno < self.maxlevel

# Function to get a database connection.
# This function connects to database with the name `database.db`
def get_db_connection():
    connection = None
    try:
        connection = sqlite3.connect(f"file:{DATABASE_FILE}?mode=rw", uri=True)
    except sqlite3.OperationalError as e:
        raise RuntimeError(f"unable to open {DATABASE_FILE} database file")
    if connection:
        connection.row_factory = sqlite3.Row
    return connection

# Function to get a post using its ID
def get_post(post_id):
    connection = get_db_connection()
    post = connection.execute('SELECT * FROM posts WHERE id = ?',
                              (post_id,)).fetchone()
    connection.close()
    db_conn.increment()
    return post


def get_open_db_connections_count():
    """Counts the number of current connections to the DATABASE_FILE.

    if platform.system() not in ['Java', 'Windows'], get_open_db_connections_count() will list open files on DATABASE_FILE using lsof command and
    count the number of open connections.

    Returns:
        int: returns the number of current connections to the DATABASE_FILE and -1 on error
    """
    if platform.system() not in ['Windows', 'Java']:
        try:
            app.logger.debug(f"\"{platform.system()}\" os detected")
            app.logger.debug(
                f"collecting current open connections to {DATABASE_FILE}")
            TIMEOUT = 20
            p1 = subprocess.Popen(["lsof", DATABASE_FILE],
                                  stdout=subprocess.PIPE)
            p2 = subprocess.Popen(
                ["wc", "-l"], stdin=p1.stdout, stdout=subprocess.PIPE)
            # extract the the 1st element of the output tuple, then convert the bytes to string then remove the new line from string then subtract 1 to ignore header line
            open_db_connections_count = int(p2.communicate(timeout=TIMEOUT)[
                0].decode("utf-8").replace('\n', '')) - 1
            open_db_connections_count = 0 if open_db_connections_count == - \
                1 else open_db_connections_count
            app.logger.debug(
                f"open_db_connections_count: {open_db_connections_count}")
        except subprocess.TimeoutExpired:
            p2.kill()
            app.logger.error(f"Error: process exceeded {TIMEOUT}")
            open_db_connections_count = -1
        except sqlite3.OperationalError as e:
            app.logger.error(f"Error: {e}")
            open_db_connections_count = -1
        return open_db_connections_count
    else:
        app.logger.debug(f"\"{platform.system()}\" os detected")
        app.logger.debug("ignoring current open connections metric")
        return None


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
        if db_conn.count_healthchecks:
            db_conn.increment()
    return result['post_count']


# Define the Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your secret key'

# Create DB_Connection() obj
db_conn = DB_Connection()

# Define the main route of the web application
@app.route('/')
def index():
    connection = get_db_connection()
    posts = connection.execute('SELECT * FROM posts').fetchall()
    connection.close()
    db_conn.increment()
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

            db_conn.increment()

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
            if db_conn.count_healthchecks:
                db_conn.increment()
            app.logger.debug("Executing test query on \"posts\" table")
            cur.execute('SELECT 1 FROM posts').fetchone()
            app.logger.debug("Test query is successful")
            if db_conn.count_healthchecks:
                db_conn.increment()
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
        json: a JSON object with:
            - 'db_connection_count' key holding the total amount of the current connections made to DATABASE_FILE
            - 'post_count' key holding the total amount of posts in the database
            - 'open_db_connections_count' key holding the total amount of the current open connections to DATABASE_FILE
    """
    res = dict()
    status_code = 200
    try:
        open_db_connections_count = get_open_db_connections_count()
        post_count = get_posts_count()
    except Exception as e:
        status_code = 500
        res['error'] = str(e)
        app.logger.error(f"MetricsError: {e}")
    else:
        if isinstance(open_db_connections_count, int):
            res['open_db_connections_count'] = open_db_connections_count
        res['db_connection_count'] = db_conn.count
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
    # set logger to handle STDOUT and STDERR
    stdout_handler = logging.StreamHandler(sys.stdout)
    stderr_handler = logging.StreamHandler(sys.stderr)
    handlers = [stderr_handler, stdout_handler]
    
    info_lvl_filter = SingleLevelFilter(logging.INFO, False)
    info_lvl_filter_inverter = SingleLevelFilter(logging.INFO, True)
    
    stdout_handler.addFilter(info_lvl_filter)
    stderr_handler.addFilter(info_lvl_filter_inverter)

    logging.basicConfig(level=logging.DEBUG,
                        format="[%(levelname)s]:%(name)s:%(asctime)s, %(message)s",
                        datefmt='%d/%m/%y, %H:%M:%S',
                        handlers=handlers)
    
    app.run(host='0.0.0.0', port=PORT)
