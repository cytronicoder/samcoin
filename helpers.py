import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """Escape special characters."""
        for old, new in [("&", "&"), (">", ">"), ("<", "<"), ('"', '"')]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.
    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def sgd(value):
    """Format value as SGD."""
    return f"${value:,.2f}"


def lookup():
    """Look up quote for Ethereum (ETH)

    Right now, Samcoin is a mockup of Ethereum, so we're using the same API. 
    In the future, we'll have our own API, with a dynamic token economy.
    """
    # Contact API (CoinGecko)
    try:
        # no api key needed
        data = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=sgd").json()

        # Parse response
        price = data["ethereum"]["sgd"]

        return {
            "name": "Samcoin",
            "price": price,
            "symbol": "SAM"
        }
    except:
        return None
