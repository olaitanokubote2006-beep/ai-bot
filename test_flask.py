from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Flask is working!"

@app.route('/signup')
def signup():
    return "✅ /signup route works!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc')