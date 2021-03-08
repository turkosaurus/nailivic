from flask import Flask, redirect, render_template, url_for
app = Flask(__name__)

@app.route('/')
def dashboard():
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
