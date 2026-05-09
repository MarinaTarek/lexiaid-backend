from flask import Flask
from flask_cors import CORS

# routes
from routes.auth_routes import auth
from routes.voice_routes import voice
from routes.correction_routes import correction_bp
from routes.reading_routes import reading_bp          # ← new
from routes.progress_routes import progress_bp

app = Flask(__name__)
CORS(app)

# register blueprints
app.register_blueprint(auth)
app.register_blueprint(voice)
app.register_blueprint(correction_bp)
app.register_blueprint(reading_bp)   
app.register_blueprint(progress_bp)# ← new


@app.route("/")
def home():
    return {"message": "LexiAid clean backend running"}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)