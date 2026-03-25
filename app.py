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
        dataset = pd.read_csv('upi_fraud_dataset.csv')

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
        model = tf.keras.models.load_model('model/project_model2.h5')
        print("Model loaded successfully.")
    except (FileNotFoundError, IOError):
        model = None
        print("Error: 'model/project_model2.h5' not found. Model not loaded.")
    except Exception as e:
        model = None
        print(f"Error loading model: {e}")

# --- Helper Functions ---
def send_otp_email(receiver_email, otp):
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
        input_array = np.array(transaction_features).reshape(1, -1)

        # Scale the input features using the loaded scaler
        scaled_features = scaler.transform(input_array)

        # Make prediction
        prediction_proba = model.predict(scaled_features)[0][0]
        # Assuming a binary classification model where output > 0.5 means fraud
        fraud_risk = 1 if prediction_proba > 0.5 else 0
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
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials.', 'danger')
        else:
            flash('Invalid form submission.', 'danger')

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
        return redirect(url_for('login'))

    if scaler is None or model is None:
        flash('Fraud detection system is not fully loaded. Please contact support.', 'danger')
        return redirect(url_for('user_make_payment_page'))

    merchant_upi = request.form.get('merchant_upi')
    trans_amount = float(request.form.get('trans_amount'))
    user_mobile = session['mobile']

    conn = get_db()
    if conn is None:
        flash('Database connection error. Cannot process payment.', 'danger')
        return redirect(url_for('user_make_payment_page'))

    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Get User Details (for age, state, zip)
        cursor.execute("SELECT dob, state, zip FROM bank_accounts WHERE mobile_number = %s", (user_mobile,))
        user_details = cursor.fetchone()
        if not user_details:
            flash('User details not found. Cannot process payment.', 'danger')
            return redirect(url_for('user_make_payment_page'))

        # 2. Get Merchant Details (for category)
        cursor.execute("SELECT category FROM merchants WHERE upi_number = %s", (merchant_upi,))
        merchant_details = cursor.fetchone()
        if not merchant_details:
            flash('Merchant not found. Please check UPI number.', 'danger')
            return redirect(url_for('user_make_payment_page'))

        # Prepare features for prediction
        now = datetime.now()
        trans_hour = now.hour
        trans_day = now.day
        trans_month = now.month
        trans_year = now.year
        category = merchant_details['category']
        
        # Calculate age from DOB
        # Ensure user_details['dob'] is a datetime.date object
        age = now.year - user_details['dob'].year - ((now.month, now.day) < (user_details['dob'].month, user_details['dob'].day))
        
        state = user_details['state'] # This needs to be the numerical representation used in the dataset
        zip_code = user_details['zip']

        # Construct the input array for the ML model
        # The order of features MUST match the training data:
        # [trans_hour, trans_day, trans_month, trans_year, category, upi_number (dummy), age, trans_amount, state, zip]
        # The 'upi_number' column in the original dataset was likely just an identifier, not a predictive feature.
        # We use a dummy value (e.g., 0) for it in the input to the model.
        transaction_features_for_model = [
            trans_hour,
            trans_day,
            trans_month,
            trans_year,
            category,
            0, # Dummy for 'upi_number' from dataset (which is an ID, not actual merchant UPI)
            age,
            trans_amount,
            state,
            zip_code
        ]

        # Predict fraud risk
        fraud_risk = predict_fraud(transaction_features_for_model)
        
        if fraud_risk == -1:
            flash('Error predicting fraud risk. Please try again later.', 'danger')
            return render_template('user_make_payment_page.html')

        status = 'FRAUDULENT' if fraud_risk == 1 else 'VALID'
        output_message = "Transaction is VALID and processed securely." if status == 'VALID' else "FRAUDULENT transaction detected! Payment blocked."

        # Record transaction in database
        cursor.execute(
            'INSERT INTO transactions (user_mobile, merchant_upi, trans_amount, status, trans_hour, trans_day, trans_month, trans_year, category, age, state, zip, trans_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (user_mobile, merchant_upi, trans_amount, status, trans_hour, trans_day, trans_month, trans_year, category, age, state, zip_code, now.date())
        )
        conn.commit()

        # Redirect to a result page
        return render_template('result.html', status=status.lower(), OUTPUT=output_message)

    except ValueError as ve:
        flash(f'Input data error: {ve}. Please check your input values.', 'danger')
        print(f"ValueError in user_pay: {ve}")
        return redirect(url_for('user_make_payment_page'))
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
        print(f"Database error in user_pay: {err}")
        return redirect(url_for('user_make_payment_page'))
    except Exception as e:
        flash(f'An unexpected error occurred: {e}', 'danger')
        print(f"General error in user_pay: {e}")
        return redirect(url_for('user_make_payment_page'))
    finally:
        if conn.is_connected():
            cursor.close()


# --- Admin Routes ---

@app.route('/admin_dashboard')
def admin_dashboard():
    """
    Displays the admin dashboard.
    Requires user to be logged in as 'admin'.
    """
    if session.get('user_type') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    return render_template('admin.html')

@app.route('/admin/users')
def admin_users_page():
    """
    Displays a list of all bank accounts (users).
    """
    if session.get('user_type') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    if conn is None:
        flash('Database error. Cannot retrieve users.', 'danger')
        return render_template('admin_users.html', users=[])

    users = []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM bank_accounts")
        users = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
    finally:
        if conn.is_connected():
            cursor.close()
    return render_template('admin_users.html', users=users)

@app.route('/admin/merchants')
def admin_merchants_page():
    """
    Displays a list of all registered merchants.
    """
    if session.get('user_type') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    if conn is None:
        flash('Database error. Cannot retrieve merchants.', 'danger')
        return render_template('admin_merchants.html', merchants=[])

    merchants = []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM merchants")
        merchants = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
    finally:
        if conn.is_connected():
            cursor.close()
    return render_template('admin_merchants.html', merchants=merchants)

@app.route('/admin/transactions')
def admin_transactions_page():
    """
    Displays all transactions in the system.
    """
    if session.get('user_type') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db()
    if conn is None:
        flash('Database error. Cannot retrieve transactions.', 'danger')
        return render_template('admin_transactions.html', transactions=[])

    transactions = []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM transactions ORDER BY trans_date DESC")
        transactions = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
    finally:
        if conn.is_connected():
            cursor.close()
    return render_template('admin_transactions.html', transactions=transactions)

@app.route('/admin/create_account', methods=['GET', 'POST'])
def admin_create_account():
    """
    Allows admin to create new bank accounts.
    """
    if session.get('user_type') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        dob_str = request.form.get('dob')
        mobile_number = request.form.get('mobile_number')
        email = request.form.get('email')
        location = request.form.get('location')
        state = request.form.get('state') # This needs to be the numerical ID for consistency with dataset
        zip_code = request.form.get('zip')

        # Basic validation
        if not all([full_name, dob_str, mobile_number, email, location, state, zip_code]):
            flash('All fields are required!', 'danger')
            return render_template('admin_create_account.html')

        try:
            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format for Date of Birth. Please use YYYY-MM-DD.', 'danger')
            return render_template('admin_create_account.html')

        conn = get_db()
        if conn is None:
            flash('Database error. Cannot create account.', 'danger')
            return render_template('admin_create_account.html')

        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO bank_accounts (full_name, dob, mobile_number, email, location, state, zip) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (full_name, dob, mobile_number, email, location, state, zip_code)
            )
            conn.commit()
            flash('Account created successfully!', 'success')
            return redirect(url_for('admin_users_page'))
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
    return render_template('admin_create_account.html')

# --- Merchant Routes ---

@app.route('/merchant_dashboard')
def merchant_dashboard():
    """
    Displays the merchant dashboard, showing transactions received by them.
    Requires user to be logged in as 'merchant'.
    """
    if session.get('user_type') not in ['user', 'merchant']: # Allow users to become merchants
        flash('Please log in to access the merchant panel.', 'warning')
        return redirect(url_for('login'))

    merchant_mobile = session['mobile']
    conn = get_db()
    if conn is None:
        flash('Database connection error. Cannot retrieve merchant details.', 'danger')
        return redirect(url_for('user_dashboard')) # Redirect to user dashboard if merchant details fail

    cursor = conn.cursor(dictionary=True)
    user_info = None
    merchant_info = None
    transactions = []

    try:
        cursor.execute("SELECT * FROM bank_accounts WHERE mobile_number = %s", (merchant_mobile,))
        user_info = cursor.fetchone()

        cursor.execute("SELECT * FROM merchants WHERE mobile_number = %s", (merchant_mobile,))
        merchant_info = cursor.fetchone()

        if not merchant_info:
            flash('You need to set up your merchant account first.', 'info')
            return redirect(url_for('merchant_setup'))

        # Fetch transactions received by this merchant
        cursor.execute('SELECT * FROM transactions WHERE merchant_upi = %s ORDER BY trans_date DESC', (merchant_info['upi_number'],))
        transactions = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
    finally:
        if conn.is_connected():
            cursor.close()
    return render_template('merchant.html', user=user_info, merchant=merchant_info, transactions=transactions)

@app.route('/merchant_setup', methods=['GET', 'POST'])
def merchant_setup():
    """
    Allows a logged-in user to set up their merchant account (UPI number and category).
    """
    if session.get('user_type') not in ['user', 'merchant']:
        flash('Please log in to set up a merchant account.', 'warning')
        return redirect(url_for('login'))
    
    # Check if the user is already a merchant
    conn = get_db()
    if conn is None:
        flash('Database connection error. Cannot set up merchant account.', 'danger')
        return render_template('merchant_setup.html')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM merchants WHERE mobile_number = %s", (session['mobile'],))
        existing_merchant = cursor.fetchone()
        if existing_merchant:
            flash('You have already set up your merchant account.', 'info')
            return redirect(url_for('merchant_dashboard'))
    except mysql.connector.Error as err:
        flash(f'Database error: {err}', 'danger')
    finally:
        if conn.is_connected():
            cursor.close()

    if request.method == 'POST':
        conn = get_db() # Re-get connection as it might have been closed by previous finally
        if conn is None:
            flash('Database error. Cannot set up merchant account.', 'danger')
            return render_template('merchant_setup.html')
        try:
            cursor = conn.cursor()
            upi_number = request.form.get('upi_number')
            category = request.form.get('category') # Assuming category is an integer ID or similar

            if not upi_number or not category:
                flash('UPI Number and Category are required.', 'danger')
                return render_template('merchant_setup.html')

            cursor.execute('INSERT INTO merchants (mobile_number, upi_number, category) VALUES (%s, %s, %s)',
                         (session['mobile'], upi_number, category))
            conn.commit()
            session['user_type'] = 'merchant' # Update session to reflect merchant status
            flash('Merchant account set up successfully!', 'success')
            return redirect(url_for('merchant_dashboard'))
        except mysql.connector.IntegrityError as e:
            if "Duplicate entry" in str(e) and "'upi_number'" in str(e):
                flash('This UPI number is already taken. Please choose another.', 'danger')
            else:
                flash(f'Database error: {e}', 'danger')
        except Exception as e:
            flash(f'An unexpected error occurred: {e}', 'danger')
        finally:
            if conn.is_connected():
                cursor.close()
    return render_template('merchant_setup.html')

if __name__ == '__main__':
    # Create the 'model' directory if it doesn't exist
    if not os.path.exists('model'):
        os.makedirs('model')
    load_ml_assets() # Call the function directly here
    app.run(debug=True) # Run the Flask application in debug mode (set to False in production)
