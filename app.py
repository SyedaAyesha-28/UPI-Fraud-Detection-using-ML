import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import tensorflow as tf
from flask import Flask, request, render_template, redirect, url_for, session, flash, g
import mysql.connector
from datetime import datetime, timedelta
import random
import smtplib
import ssl
import os

# --- Database Configuration (IMPORTANT: Update your credentials here or use environment variables) ---
# This dictionary holds your MySQL database connection details.
# Replace 'root' with your MySQL username, '' with your password, and 'upi_fraud1' with your database name.
DB_CONFIG = {
    'user': 'root',
    'password': '',
    'host': 'localhost',
    'database': 'upi_fraud1'
}

# --- SMTP Configuration for Email (IMPORTANT: Update your credentials) ---
# These are used for sending OTPs via email.
# SENDER_EMAIL: The email address from which OTPs will be sent.
# SENDER_PASSWORD: The app password for the SENDER_EMAIL (NOT your regular email password).
# You should generate an app password for security if using Gmail.
SMTP_SERVER = "smtp.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "way2track01@gmail.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "masvczanrdbufpuq") # Use an "App Password" for Gmail

# --- Global Variables for ML Model and Scaler ---
# These variables will hold the loaded machine learning model and the StandardScaler.
# They are initialized to None and loaded when the application starts.
model = None
scaler = None

# --- Flask App Initialization ---
app = Flask(__name__)
# Set a strong, unique secret key for session management.
# This is crucial for security; never use a default or easily guessable key in production.
app.secret_key = 'your_super_secret_key_change_this_in_production'

# --- Database Connection Management ---
def get_db():
    """
    Establishes a new database connection if one doesn't exist for the current request.
    Stores the connection on Flask's 'g' object to reuse it within the same request.
    """
    if 'db' not in g:
        try:
            g.db = mysql.connector.connect(**DB_CONFIG)
        except mysql.connector.Error as err:
            print(f"Database connection error: {err}")
            g.db = None # Set to None if connection fails
    return g.db

def close_db(e=None):
    """
    Closes the database connection at the end of the request.
    """
    db = g.pop('db', None)
    if db is not None and db.is_connected():
        db.close()

# Register the close_db function to be called after each request, even if an error occurs.
app.teardown_appcontext(close_db)

# --- ML Model and Scaler Setup (Loaded once at app startup) ---
def load_ml_assets():
    """
    Loads the pre-trained machine learning model and scaler when the Flask app first starts.
    This prevents reloading them for every request, improving performance.
    """
    global model, scaler
    try:
        # Load the dataset to fit the scaler.
        # Ensure 'upi_fraud_dataset.csv' is in the same directory as app.py or provide a full path.
        dataset = pd.read_csv('dataset/upi_fraud_dataset.csv')


        # Features for scaling: all columns EXCEPT 'fraud_risk' (the last column).
        # This ensures the scaler is fitted on the same 10 features the model expects.
        # Columns: trans_hour, trans_day, trans_month, trans_year, category, upi_number, age, trans_amount, state, zip
        x_for_scaling = dataset.iloc[:, :10].values
        scaler = StandardScaler()
        scaler.fit(x_for_scaling) # Fit the scaler on the training data features
        print("Scaler fitted successfully.")

    except FileNotFoundError:
        scaler = None
        print("Warning: 'upi_fraud_dataset.csv' not found. Scaler not loaded.")
    except Exception as e:
        scaler = None
        print(f"Error loading or fitting scaler: {e}")

    try:
        # Load the Keras model.
        # Ensure 'model/project_model2.h5' exists relative to app.py or provide a full path.
        model = tf.keras.models.load_model(
    'model/project_model2.h5',
    compile=False
)
        print("Model loaded successfully.")
    except (FileNotFoundError, IOError):
        model = None
        print("Error: 'model/project_model2.h5' not found. Model not loaded.")
    except Exception as e:
        model = None
        print(f"Error loading model: {e}")

# --- Helper Functions ---
def send_otp_email(receiver_email, otp):
    print("DEBUG OTP (for demo):", otp) 
    """
    Sends an OTP to the specified email address.
    """
    subject = "Your SecurePay OTP Verification"
    body = f"Your One-Time Password (OTP) for SecurePay is: {otp}. It is valid for 5 minutes."
    message = f"Subject: {subject}\n\n{body}"

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, receiver_email, message)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def generate_otp():
    """
    Generates a 6-digit numeric OTP.
    """
    return str(random.randint(100000, 999999))

def predict_fraud(transaction_features):
    """
    Predicts fraud risk using the loaded ML model and scaler.
    Args:
        transaction_features (list): A list of 10 numerical features for the transaction.
                                     Order must match the training data:
                                     [trans_hour, trans_day, trans_month, trans_year, category,
                                      upi_number_dummy, age, trans_amount, state, zip]
                                      Note: upi_number_dummy is a placeholder for the dataset's upi_number column,
                                      which was likely an identifier and not a predictive feature.
    Returns:
        int: 1 if fraud is predicted, 0 otherwise.
             Returns -1 if model or scaler is not loaded.
    """
    global model, scaler
    if model is None or scaler is None:
        print("ML model or scaler not loaded. Cannot predict fraud.")
        return -1 # Indicate an error state

    try:
        # Reshape the input data to be a 2D array (1 sample, 10 features)
        input_array = np.array(transaction_features, dtype=float).reshape(1, -1)

        # Scale the input features using the loaded scaler
        scaled_features = scaler.transform(input_array)

        # Make prediction
        prediction_proba = model.predict(scaled_features)[0][0]
        print("FRAUD PROBABILITY =", prediction_proba)
        trans_amount = transaction_features[7]  # amount index
        
        # Assuming a binary classification model where output > 0.5 means fraud
        "fraud_risk = 1 if prediction_proba > 0.8 else 0"
         # -------- HYBRID FRAUD LOGIC (DEMO SAFE) --------

# Rule 1: Very small transactions are safe
        if trans_amount <= 3000:
         return 0  # NOT fraud

# Rule 2: Medium transactions → ML decides
        elif trans_amount <= 7000:
         return 1 if prediction_proba > 0.9 else 0

# Rule 3: High-value transactions → always fraud
        else:
         fraud_risk=1


        return fraud_risk
    except Exception as e:
        print(f"Error during fraud prediction: {e}")
        return -1 # Indicate an error state

# --- Routes ---

@app.route('/')
def index():
    """
    Renders the index page.
    """
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user and admin login.
    Users log in with mobile number and OTP. Admins log in with username/password.
    """
    if 'mobile' in session:
        if session.get('user_type') == 'user':
            return redirect(url_for('user_dashboard'))
        elif session.get('user_type') == 'merchant':
            return redirect(url_for('merchant_dashboard'))
        elif session.get('user_type') == 'admin':
            return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        form_type = request.form.get('form_type') # Distinguish between user and admin login forms
        
        conn = get_db()
        if conn is None:
            flash('Database connection error. Please try again later.', 'danger')
            return render_template('login.html')

        cursor = conn.cursor(dictionary=True)

        if form_type == 'user':
            mobile_number = request.form.get('mobile_number')
            if not mobile_number:
                flash('Mobile number is required for user login.', 'danger')
                cursor.close()
                return render_template('login.html')
            
            try:
                cursor.execute("SELECT * FROM bank_accounts WHERE mobile_number = %s", (mobile_number,))
                user = cursor.fetchone()
                if user:
                    # Generate and send OTP for user
                    otp = generate_otp()
                    otp_expiry = datetime.now() + timedelta(minutes=5)
                    cursor.execute("UPDATE bank_accounts SET otp = %s, otp_expiry = %s WHERE mobile_number = %s",
                                   (otp, otp_expiry, mobile_number))
                    conn.commit()

                    if send_otp_email(user['email'], otp):
                        session['mobile'] = mobile_number
                        session['user_type'] = 'user' # Temporarily set user type for session
                        flash('OTP sent to your registered email. Please verify to log in.', 'info')
                        cursor.close()
                        return redirect(url_for('verify_otp', mobile=mobile_number))
                    else:
                        flash('Failed to send OTP. Please try again.', 'danger')
                else:
                    flash('User account not found. Please register.', 'danger')
            except mysql.connector.Error as err:
                flash(f'Database error: {err}', 'danger')
            finally:
                if conn.is_connected():
                    cursor.close()

        elif form_type == 'admin':
            username = request.form.get('username')
            password = request.form.get('password') 
            
            if not username or not password:
                flash('Username and password are required for admin login.', 'danger')
                cursor.close()
                return render_template('login.html')

            # --- Admin Credentials (Hardcoded - Replace with DB lookup in production) ---
            if username == 'admin' and password == 'admin': 
                session['mobile'] = '0000000000' # Dummy mobile for admin
                session['user_type'] = 'admin'
                flash('Admin login successful!', 'success')
                cursor.close()
                conn.close()
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials.', 'danger')
                conn.close()
        else:
            flash('Invalid form submission.', 'danger')
            conn.close()

    return render_template('login.html')

@app.route('/verify_otp/<mobile>', methods=['GET', 'POST'])
def verify_otp(mobile):
    """
    Handles OTP verification for user login.
    """
    if 'mobile' not in session or session['mobile'] != mobile:
        flash('Invalid request. Please log in again.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        user_otp = request.form.get('otp')
        conn = get_db()
        if conn is None:
            flash('Database connection error. Please try again later.', 'danger')
            return render_template('verify_otp.html', mobile=mobile)

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT otp, otp_expiry FROM bank_accounts WHERE mobile_number = %s", (mobile,))
            user_data = cursor.fetchone()

            if user_data and user_data['otp'] == user_otp and user_data['otp_expiry'] > datetime.now():
                # OTP is valid, clear it from DB for security
                cursor.execute("UPDATE bank_accounts SET otp = NULL, otp_expiry = NULL WHERE mobile_number = %s", (mobile,))
                conn.commit()

                # Check if user is also a merchant
                cursor.execute("SELECT * FROM merchants WHERE mobile_number = %s", (mobile,))
                merchant_info = cursor.fetchone()
                if merchant_info:
                    session['user_type'] = 'merchant'
                    flash('Login successful as Merchant!', 'success')
                    return redirect(url_for('merchant_dashboard'))
                else:
                    session['user_type'] = 'user'
                    flash('Login successful as User!', 'success')
                    return redirect(url_for('user_dashboard'))
            elif user_data and user_data['otp_expiry'] <= datetime.now():
                flash('OTP has expired. Please log in again to get a new OTP.', 'danger')
                return redirect(url_for('login'))
            else:
                flash('Invalid OTP. Please try again.', 'danger')
        except mysql.connector.Error as err:
            flash(f'Database error: {err}', 'danger')
        finally:
            if conn.is_connected():
                cursor.close()
    return render_template('verify_otp.html', mobile=mobile)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles new user registration into the bank_accounts table.
    """
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        dob_str = request.form.get('dob') # Date of Birth as string
        mobile_number = request.form.get('mobile_number')
        email = request.form.get('email')
        location = request.form.get('location')
        state = request.form.get('state') # This should be the numerical ID
        zip_code = request.form.get('zip')

        # Basic validation
        if not all([full_name, dob_str, mobile_number, email, location, state, zip_code]):
            flash('All fields are required!', 'danger')
            return render_template('register.html')

        try:
            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format for Date of Birth. Please use YYYY-MM-DD.', 'danger')
            return render_template('register.html')

        conn = get_db()
        if conn is None:
            flash('Database error. Cannot create account.', 'danger')
            return render_template('register.html')

        cursor = conn.cursor()
        try:
            # Check for duplicate mobile or email
            cursor.execute('SELECT * FROM bank_accounts WHERE mobile_number = %s OR email = %s', (mobile_number, email))
            if cursor.fetchone():
                flash('Mobile number or email already registered.', 'danger')
                return render_template('register.html')

            cursor.execute(
                'INSERT INTO bank_accounts (full_name, dob, mobile_number, email, location, state, zip) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (full_name, dob, mobile_number, email, location, state, zip_code)
            )
            conn.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError as e:
            if "Duplicate entry" in str(e) and ("'mobile_number'" in str(e) or "'email'" in str(e)):
                flash('Mobile number or email already registered.', 'danger')
            else:
                flash(f'Database error: {e}', 'danger')
        except Exception as e:
            flash(f'An unexpected error occurred: {e}', 'danger')
        finally:
            if conn.is_connected():
                cursor.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    """
    Logs out the current user by clearing the session.
    """
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# --- User Routes ---

@app.route('/user_dashboard')
def user_dashboard():
    """
    Displays the user dashboard.
    Requires user to be logged in as 'user' or 'merchant' (as merchants also have user accounts).
    """
    if session.get('user_type') not in ['user', 'merchant']:
        flash('Please log in to access your dashboard.', 'warning')
        return redirect(url_for('login'))
    
    user_mobile = session['mobile']
    conn = get_db()
    if conn is None:
        flash('Database error. Cannot retrieve user info.', 'danger')
        return render_template('user.html', user=None) # Changed to user.html

    cursor = conn.cursor(dictionary=True)
    user_info = None
    try:
        cursor.execute("SELECT * FROM bank_accounts WHERE mobile_number = %s", (user_mobile,))
        user_info = cursor.fetchone()
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
    finally:
        if conn.is_connected():
            cursor.close()
    return render_template('user.html', user=user_info) # Changed to user.html

@app.route('/user/profile')
def user_profile_page():
    """
    Displays the user's profile information.
    """
    if session.get('user_type') not in ['user', 'merchant']:
        flash('Please log in to view your profile.', 'warning')
        return redirect(url_for('login'))
    
    user_mobile = session['mobile']
    conn = get_db()
    if conn is None:
        flash('Database error. Cannot retrieve user profile.', 'danger')
        return render_template('user_profile_page.html', user=None)

    cursor = conn.cursor(dictionary=True)
    user_info = None
    try:
        cursor.execute("SELECT * FROM bank_accounts WHERE mobile_number = %s", (user_mobile,))
        user_info = cursor.fetchone()
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
    finally:
        if conn.is_connected():
            cursor.close()
    return render_template('user_profile_page.html', user=user_info)

@app.route('/user/make_payment', methods=['GET'])
def user_make_payment_page():
    """
    Renders the page for making a new payment.
    """
    if session.get('user_type') not in ['user', 'merchant']:
        flash('Please log in to make a payment.', 'warning')
        return redirect(url_for('login'))
    return render_template('user_make_payment_page.html')

@app.route('/user/transactions', methods=['GET'])
def user_transactions_page():
    """
    Displays the user's transaction history.
    """
    if session.get('user_type') not in ['user', 'merchant']:
        flash('Please log in to view your transactions.', 'warning')
        return redirect(url_for('login'))
    
    user_mobile = session['mobile']
    conn = get_db()
    if conn is None:
        flash('Database error. Cannot retrieve transactions.', 'danger')
        return render_template('user_transactions_page.html', transactions=[])

    transactions = []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM transactions WHERE user_mobile = %s ORDER BY trans_date DESC', (user_mobile,))
        transactions = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
    finally:
        if conn.is_connected():
            cursor.close()
    return render_template('user_transactions_page.html', transactions=transactions)


@app.route('/user/pay', methods=['POST'])
def user_pay():
    """
    Processes a payment, performs fraud detection, and records the transaction.
    """
    if session.get('user_type') not in ['user', 'merchant']:
        flash('Please log in to make a payment.', 'warning')