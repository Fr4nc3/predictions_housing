import os
import flask
from flask import (
    Flask,
    flash,
    request,
    redirect,
    url_for,
    session,
    render_template,
    jsonify,
)
from flask.helpers import make_response
from forms import LoginForm, SignupForm
from models import db, User, Properties, Like 
import joblib
import numpy as np
from werkzeug.security import check_password_hash, generate_password_hash


from helpers import apology

app = Flask(__name__)

#######################
# DATABASEVARIABLES
#######################
PROPERTIES_TABLE = os.environ.get("PROPERTIES_TABLE'", "properties")
USERS_TABLE = os.environ.get("USERS_TABLE", "users")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "database")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "db_username")
POSTGRES_PASSW = os.environ.get("POSTGRES_PASSW", "db_password")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
IS_SERVER = os.environ.get("IS_SERVER", False)
server = IS_SERVER 
if server:
    DB_URL = 'postgresql://{user}:{pw}@{url}/{db}'.format(user=POSTGRES_USER,pw=POSTGRES_PASSW,url=POSTGRES_HOST,db=POSTGRES_DB)
    app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # silence the deprecation warning

else:
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "POSTGES_DATABASE_URI'", "postgresql://localhost/postgres_public_properties"
    )

SECRET_KEY = os.urandom(32)
app.config["SECRET_KEY"] = SECRET_KEY

db.init_app(app)


@app.route("/")
@app.route("/index")
def index():
    print('cookie:', request.cookies.get('username'))
    username_value = session['username'] if 'username' in session else request.cookies.get('username')
    if username_value  is not None:
        username = User.query.filter_by(username=username_value).first()
        return flask.render_template("index.html", showSearchBox=True, restuls=False, username=username)
    else:
        return flask.render_template("index.html", showSearchBox=True, restuls=False)


@app.route("/predict", methods=["POST"])
def make_prediction():
    if request.method == "POST":
        
        # load ML model
        model = joblib.load("pp-model.pkl")
        house_data = []

        # request zipcode, need to add a check for valid zipcode and not start with 0
        zipCode = request.form["zipCode"]  if request.form["zipCode"] else 2420

        house_data.append(float(zipCode))

        # request numbers of bad, baths, sqft and prototype
        beds = request.form["beds"]
        baths = request.form["baths"]
        sqft = request.form["sqft"] if request.form["sqft"]!='' else 750 # defaul 750 sqft
        proptype = request.form["proptype"]
        house_data.append(int(beds))
        house_data.append(float(baths))
        house_data.append(float(sqft))
        house_data.append(int(proptype))

        # add some fix value to the following field: hasotherfeatures
        # hasproptype, hasstreetname, hashousenum1, hashousenum2,
        # hasagentname, hasofficename, hasofficephone, hasshowinginstructions,

        for i in [1, 1, 1, 1, 1, 1, 1, 1, 1]:
            house_data.append(i)

        # request otherfeature information from the user
        has_Style = request.form["hasStyle"]
        has_Level = request.form["hasLevel"]
        has_Garage = request.form["hasGarage"]
        # add heating 1 in the array
        has_Cooling = request.form["hasCooling"]
        has_elemSchool = request.form["hasElemSchool"]
        has_junSchool = request.form["hasJunSchool"]
        has_highSchool = request.form["hasHighSchool"]

        # appending the fields to array
        house_data.append(int(has_Style))
        house_data.append(int(has_Level))
        house_data.append(int(has_Garage))
        # adding heat as true
        house_data.append(1)
        house_data.append(int(has_Cooling))
        house_data.append(int(has_elemSchool))
        house_data.append(int(has_junSchool))
        house_data.append(int(has_highSchool))
        # add haslistprice always true
        house_data.append(1)

        # add haslistdate to see if house is on market
        has_ListDate = request.form["hasListDate"]
        house_data.append(int(has_ListDate))

        # add the remaining fields as default value
        # hasaddress, hascity, hasstate, hasarea
        for j in [1, 1, 1, 1]:
            house_data.append(j)

        # printing array for debugging
        # for data in house_data:
            # print(data)

        prediction = model.predict(np.array(house_data).reshape(1, -1))
        label = np.squeeze(prediction.round(2))
        if label is not None:
            results = True
        else:
            results = False
        price = int(label)

        # query the houses with a list price < of the results
        # then sent the listing to the html page by adding houses=houses
        search = "%{}%".format("http")

        houses = Properties.query.filter(Properties.listprice <= price, Properties.zip == zipCode, Properties.photourl.like(search)).limit(100)
        return render_template("index.html", label="${:,.2f}".format(label), results=results, zipcode=zipCode, houses=houses)


@app.route("/register", methods=["GET", "POST"])
def register_user():
    # register a new account into the database
    print('cookie:', request.cookies.get('username'))
    username_value = session['username'] if 'username' in session else request.cookies.get('username')
    if username_value  is not None:
        session['username'] = username_value 
        return redirect(url_for("index"))

    form = SignupForm()
    if request.method == "POST" and form.validate_on_submit():
        username = request.form["username"]
        password = request.form["password"]
        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            flash("This username is already taken, please try again")
            return redirect(url_for("register_user"))
        else:
            user = User(username=username, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            
            flash("Congratulations, you are now registered")
            session["username"] = username
            response = make_response(redirect(url_for("index")))
            response.set_cookie('username', session["username"])
            print('cookie login pass:', request.cookies.get('username'))
            return response

    else:
        return render_template("register.html", title="register", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "username" in session:
        return redirect(url_for("index"))

    form = LoginForm()
    if request.method == "POST" and form.validate_on_submit():
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        ## TODO pull out hash password from the database to the correspond user
        if user is not None:
            check_pwd = check_password_hash(user.password, password)
            if check_pwd:
                session["username"] = username
                response = make_response(redirect(url_for("index")))
                response.set_cookie('username', session["username"])
                print('cookie login pass:', request.cookies.get('username'))
                return response
            else:
                flash("invalid password or username")
                return redirect(url_for("login"))
        else:
            flash("invalid password or username")
            return redirect(url_for("login"))

    else:
        return render_template("login.html", title=login, form=form)


@app.route("/logout", methods=["POST"])
def logout():
    response = make_response(redirect(url_for("index")))
    response.set_cookie('username', '', expires=0)
    session.clear()
    return response

@app.route('/info/<row_id>')
def info(row_id):
    listing = Properties.query.filter_by(row_id=row_id).first()

    # round listing prices
    listing.listprice = '{0:.2f}'.format(listing.listprice)

    if listing is None:
        flash('Invalid MLS #')
        return redirect(url_for('index'))
    else:  # listing is found
        print('cookie:', request.cookies.get('username'))
        username_value = session['username'] if 'username' in session else request.cookies.get('username')
        if username_value  is not None:
            session['username'] = username_value # reinit the session 
            session_user = User.query.filter_by(username=session['username']).first()
            # check if listing is a favorite
            search_fave = Like.query.filter_by(usered=session_user.uid, house=listing.row_id).first()
            is_fave = False
            if search_fave:
                is_fave = True
            return render_template('info.html', title=listing.row_id, listing=listing, username=session_user.username, is_fave=is_fave)
        else:
            return render_template('info.html', title=listing.row_id, listing=listing)


        
@app.route('/like/<row_id>', methods=['POST'])
def like(row_id):
    if request.method == 'POST':
        print('cookie:', request.cookies.get('username'))
        username_value = session['username'] if 'username' in session else request.cookies.get('username')
        session['username'] = username_value
        session_user = User.query.filter_by(username=session['username']).first()
        listing = Properties.query.filter_by(row_id=row_id).first()
        search_fave = Like.query.filter_by(usered=session_user.uid, house=listing.row_id).first()
        if search_fave:
            flash('Listing is already saved')
        else:
            new_fave = Like(usered=session_user.uid, house=listing.row_id)
            db.session.add(new_fave)
            db.session.commit()
            flash('You\'ve successfully saved this property to Favorites')
    return redirect(url_for('info', row_id=row_id))



@app.route('/unlike/<row_id>', methods=['POST'])
def unlike(row_id):
    if request.method == 'POST':
        print('request: ', request.form)
        print('session:',session)
        print('cookie:', request.cookies.get('username'))
        username_value = session['username'] if 'username' in session else request.cookies.get('username')
        session['username'] = username_value
        session_user = User.query.filter_by(username=session['username']).first()
        listing = Properties.query.filter_by(row_id=row_id).first()
        delete_fave = Like.query.filter_by(usered=session_user.uid, house=listing.row_id).first()
        if not delete_fave:
            flash('Listing is has not been saved')
        else:
            db.session.delete(delete_fave)
            db.session.commit()
            flash('You\'ve successfully deleted this property from Favorites')
    current_url = request.form['current_url']
    if current_url == "info":
        return redirect(url_for(current_url, row_id=row_id))
    elif current_url == "profile":
        return redirect(url_for(current_url, username=session_user.username))
    else:
        return redirect(url_for('index'))

@app.route('/profile/<username>')
def profile(username):
    print('cookie:', request.cookies.get('username'))
    username_value = session['username'] if 'username' in session else request.cookies.get('username')
    if username_value is not None:  # user-session
        session['username'] = username_value # reset session 
        session_user = User.query.filter_by(username=session['username']).first()
        user_faves = Like.query.filter_by(usered=session_user.uid).all()
        fave_listing_ids = [l.house for l in user_faves]
        fave_listings = Properties.query.filter(Properties.row_id.in_(fave_listing_ids)).all()

        # format list prices
        for listing in fave_listings:
            listing.listprice = '{0:.2f}'.format(listing.listprice)

        return render_template('profile.html', title='Favorites', fave_listings=fave_listings, session_username=session_user.username)
    else:
        return redirect(url_for('index'))


if __name__ == "__main__":
    # start API
    app.run(host="0.0.0.0", port=8000, debug=True)
