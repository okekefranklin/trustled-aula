"""Entry point. Used by `flask run` in development and by gunicorn in production
(see Procfile: `gunicorn wsgi:app`)."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
