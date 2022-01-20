from flask import redirect, render_template, request, session


def apology(message):
    return render_template("error.html", message=message)