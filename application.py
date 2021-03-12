import os
import requests
import urllib.parse

from flask import Flask, redirect, render_template, request, session, url_for
from flask_session import Session
from functools import wraps
from dataclasses import dataclass









app = Flask(__name__)



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
    'El Pulpo': ['Octoups', 'Octopus Swirls', 'Octopus Tentacles'],
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


@app.route('/')
def dashboard():
    # print(loteria)
    for key in loterias:
        # i = 0
        print(f"{key}:")
        tmp = loterias[key]
        print(tmp)

    return render_template('index.html')

@app.route('/parts')
def parts():
    return 'hello parts'

@app.route('/items')
def items():
    return 'hello items'

@app.route('/shipping')
def shipping():
    return 'hello shipping'

@app.route('/register')
def register():
    return 'hello register'

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
