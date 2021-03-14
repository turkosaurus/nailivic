import os
import requests
import urllib.parse

from cs50 import SQL
from flask import Flask, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from functools import wraps
from dataclasses import dataclass

###### CONFIGURATION ######
# Initialize Flask App Ojbect
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure Heroku Postgres database
db = SQL(os.getenv('DATABASE_URL'))

###### DATA STRUCTURES ######
# Set type variables
# Loteria
colors = ['black', 'red', 'turquoise', 'yellow', 'green', 'purple']
sizes = ['s', 'm', 'l']
loterias = {
    'La Dama': ['Frida', 'Frida Flowers'],
    'La Sirena': ['Mermaid Body', 'Mermaid Hair', 'Mermaid Tail'],
    'La Mano': ['Hand', 'Hand Swirls'],
    'La Bota': ['Boot', 'Boot Swirls', 'Boot Flames'],
    'El Corazon': ['Heart', 'Heart Swirls'],
    'El Musico': ['Guitar', 'Guitar Hands'],
    'La Estrella': ['Star', 'Star Swirls'],
    'El Pulpo': ['Octopus', 'Octopus Swirls', 'Octopus Tentacles'],
    'La Rosa': ['Rose', 'Rose Swirls', 'Rose Leaves'],
    'La Calavera': ['Skull', 'Skull Flames', 'Skull Swirls'],
    'El Poder': ['Fist', 'Fist Swirls', 'Fist Wrist']
}

@dataclass
class loteria:
    size: str
    a: str
    b: str
    c: str

# Helper Functions
def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def dashboard():
    # print(loteria)
    for key in loterias:
        # i = 0
        print(f"{key}:")
        tmp = loterias[key]
        print(tmp)

    return render_template('index.html', colors=colors, sizes=sizes, loterias=loterias)

@app.route('/items')
def items():
    return render_template('items.html')

@app.route('/parts')
def parts():
    return render_template('parts.html')

@app.route('/projections')
def projections():
    return render_template('projections.html')

@app.route('/shipping')
def shipping():
    return render_template('shipping.html')

@app.route('/register')
def register():
    return "todo"
    # return render_template('register.html')

@app.route('/login')
def login():
    return 'hello login'


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function
