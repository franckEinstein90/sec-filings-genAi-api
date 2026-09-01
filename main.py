"""Uvicorn entrypoint: python main.py  or  uvicorn main:app"""

from sec_filings.app import create_app
from sec_filings.config import FLASK_DEBUG, HOST, PORT

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT, reload=FLASK_DEBUG)
