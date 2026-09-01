"""Development / gunicorn entrypoint."""

from sec_filings.app import create_app
from sec_filings.config import FLASK_DEBUG, HOST, PORT

app = create_app()

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=FLASK_DEBUG)
