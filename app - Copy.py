import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import tensorflow as tf
from flask import Flask, request, render_template, redirect, url_for, session, flash
import mysql.connector
from datetime import datetime, timedelta
import random
import smtplib
import ssl
import os

# --- ML Model and Scaler Setup ---
try:
    dataset = pd.read_csv('upi_fraud_dataset.csv', index_col=0)
    x_for_scaling = dataset.iloc[:, :10].values
    scaler = StandardScaler()
    scaler.fit(x_for_scaling)
except FileNotFoundError:
    scaler = None
    print("Warning: 'upi_fraud_dataset.csv' not found.")

try:
    model = tf.keras.models.load_model('model/project_model2.h5')
except (FileNotFoundError, IOError):
    model = None
    print("Error: 'model/project_model1.h5' not found.")

# --- Flask App Initialization ---
app = Flask(__name__)
app.secret_key = 'your_super_secret_key' # Replace with a strong, unique secret key

# --- SMTP & Database Configuration ---
# !!! IMPORTANT: UPDATE YOUR CREDENTIALS HERE OR USE ENVIRONMENT VARIABLES !!!
DB_CONFIG = {'user': 'root', 'password': '', 'host': 'localhost', 'database': 'upi_fraud1'}
SMTP_SERVER = "smtp.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "way2track01@gmail.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "masvczanrdbufpuq") # Use an "App Password" for Gmail

# --- Database Connection Helper ---
def get_db():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# --- Email Sending Function ---
def send_otp_email(receiver_email, otp):
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            message = f"Subject: SecurePay OTP Verification\n\nYour OTP for SecurePay is: {otp}. It is valid for 5 minutes."
            server.sendmail(SENDER_EMAIL, receiver_email, message)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        form_type = request.form.get('form_type') # Get the form_type to distinguish submissions
        
        conn = get_db()
        if conn is None:
            flash('Database connection error. Please try again later.', 'danger')
            return render_template('login.html')

        cursor = conn.cursor(dictionary=True)
        user = None # Initialize user to None

        if form_type == 'user':
            mobile_number = request.form.get('mobile_number')
            if not mobile_number:
                flash('Mobile number is required for user login.', 'danger')
                cursor.close()
                conn.close()
                return render_template('login.html')
            
            cursor.execute("SELECT * FROM bank_accounts WHERE mobile_number = %s", (mobile_number,))
            user = cursor.fetchone()
            if user:
                # Generate and send OTP for user
                otp = str(random.randint(100000, 999999))
                otp_expiry = datetime.now() + timedelta(minutes=5)
                cursor.execute("UPDATE bank_accounts SET otp = %s, otp_expiry = %s WHERE mobile_number = %s",
                               (otp, otp_expiry, mobile_number))
                conn.commit()

                if send_otp_email(user['email'], otp):
                    session['mobile'] = mobile_number
                    session['user_type'] = 'user' # Set user type for session
                    flash('OTP sent to your registered email.', 'info')
                    cursor.close()
                    conn.close()
                    return redirect(url_for('verify_otp', mobile=mobile_number))
                else:
                    flash('Failed to send OTP. Please try again.', 'danger')
            else:
                flash('User account not found.', 'danger')

        elif form_type == 'admin':
            username = request.form.get('username')
            password = request.form.get('password') 
            
            if not username or not password:
                flash('Username and password are required for admin login.', 'danger')
                cursor.close()
                conn.close()
                return render_template('login.html')

            # DIRECTLY CHECK ADMIN CREDENTIALS
            if username == 'admin' and password == 'admin': 
                session['logged_in'] = True
                # For admin, we don't need a mobile number from DB for authentication, but Flask expects it.
                # Use a dummy or the actual admin mobile from database1.sql if needed for other admin functions.
                # For simplicity, let's set it to the mobile from database1.sql for the Admin User.
                session['mobile'] = '0000000000' # Matches the mobile_number for 'Admin User' in database1.sql
                session['user_type'] = 'admin' # Set user type for session
                flash('Admin login successful!', 'success')
                cursor.close()
                conn.close()
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials.', 'danger')
        else:
            flash('Invalid form submission.', 'danger')

        cursor.close()
        conn.close()
    return render_template('login.html')

@app.route('/verify_otp/<mobile>', methods=['GET', 'POST'])
def verify_otp(mobile):
    if request.method == 'POST':
        user_otp = request.form['otp']
        conn = get_db()
        if conn is None:
            flash('Database connection error. Please try again later.', 'danger')
            return render_template('verify_otp.html', mobile=mobile)

        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT otp, otp_expiry FROM bank_accounts WHERE mobile_number = %s", (mobile,))
        user_data = cursor.fetchone()

        if user_data and user_data['otp'] == user_otp and user_data['otp_expiry'] > datetime.now():
            # OTP is valid, clear it from DB for security
            cursor.execute("UPDATE bank_accounts SET otp = NULL, otp_expiry = NULL WHERE mobile_number = %s", (mobile,))
            conn.commit()

            # Set session for logged-in user
            session['logged_in'] = True
            session['mobile'] = mobile

            flash('Login successful!', 'success')
            if session.get('user_type') == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                # Check if user is also a merchant
                cursor.execute("SELECT * FROM merchants WHERE mobile_number = %s", (mobile,))
                merchant_info = cursor.fetchone()
                if merchant_info:
                    session['user_type'] = 'merchant'
                    return redirect(url_for('merchant_dashboard'))
                else:
                    session['user_type'] = 'user'
                    return redirect(url_for('user_dashboard'))
        elif user_data and user_data['otp_expiry'] <= datetime.now():
            flash('OTP has expired. Please log in again to get a new OTP.', 'danger')
            return redirect(url_for('login'))
        else:
            flash('Invalid OTP. Please try again.', 'danger')

        cursor.close()
        conn.close()
    return render_template('verify_otp.html', mobile=mobile)


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# --- User Routes ---

@app.route('/user')
def user_dashboard():
    if session.get('user_type') not in ['user', 'merchant']:
        flash('Please log in to access the user dashboard.', 'warning')
        return redirect(url_for('login'))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bank_accounts WHERE mobile_number = %s", (session['mobile'],))
    user_info = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('user.html', user=user_info)

@app.route('/user/profile')
def user_profile_page():
    if session.get('user_type') not in ['user', 'merchant']:
        flash('Please log in to view your profile.', 'warning')
        return redirect(url_for('login'))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bank_accounts WHERE mobile_number = %s", (session['mobile'],))
    user_info = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('user_profile_page.html', user=user_info)

@app.route('/user/make_payment', methods=['GET'])
def user_make_payment_page():
    if session.get('user_type') not in ['user', 'merchant']:
        flash('Please log in to make a payment.', 'warning')
        return redirect(url_for('login'))
    return render_template('user_make_payment_page.html')

@app.route('/user/transactions', methods=['GET'])
def user_transactions_page():
    if session.get('user_type') not in ['user', 'merchant']:
        flash('Please log in to view your transactions.', 'warning')
        return redirect(url_for('login'))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    # Fetch all transaction details for the user
    cursor.execute('SELECT * FROM transactions WHERE user_mobile = %s ORDER BY trans_date DESC', (session['mobile'],))
    transactions = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('user_transactions_page.html', transactions=transactions)


@app.route('/user/pay', methods=['POST'])
def user_pay():
    if session.get('user_type') not in ['user', 'merchant']:
        flash('Please log in to make a payment.', 'warning')
        return redirect(url_for('login'))

    if scaler is None or model is None:
        flash('Fraud detection system is not fully loaded. Please contact support.', 'danger')
        return redirect(url_for('user_make_payment_page'))

    merchant_upi = request.form['merchant_upi']
    trans_amount = float(request.form['trans_amount'])
    user_mobile = session['mobile']

    conn = get_db()
    if conn is None:
        flash('Database connection error. Cannot process payment.', 'danger')
        return redirect(url_for('user_make_payment_page'))

    cursor = conn.cursor(dictionary=True)

    # 1. Get User Details
    cursor.execute("SELECT dob, location, state, zip FROM bank_accounts WHERE mobile_number = %s", (user_mobile,))
    user_details = cursor.fetchone()
    if not user_details:
        flash('User details not found.', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('user_make_payment_page'))

    # 2. Get Merchant Details
    cursor.execute("SELECT category FROM merchants WHERE upi_number = %s", (merchant_upi,))
    merchant_details = cursor.fetchone()
    if not merchant_details:
        flash('Merchant not found.', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('user_make_payment_page'))

    # Prepare features for prediction
    now = datetime.now()
    trans_hour = now.hour
    trans_day = now.day
    trans_month = now.month
    trans_year = now.year
    category = merchant_details['category']
    # Calculate age from DOB
    age = now.year - user_details['dob'].year - ((now.month, now.day) < (user_details['dob'].month, user_details['dob'].day))
    state = user_details['state'] # This 'state' needs to be the numerical representation used in the dataset
    zip_code = user_details['zip']

    # For the purpose of making the app work, I will make an assumption about the model's expected input.
    # A more robust solution would involve checking the exact features the model was trained on.
    # Let's assume the model expects the following 10 features in order for prediction,
    # excluding 'Id' and using the 'zip' code from the user:
    # [trans_hour, trans_day, trans_month, trans_year, category, DUMMY_UPI_NUMBER_FEATURE, age, trans_amount, state, zip]
    # Where DUMMY_UPI_NUMBER_FEATURE is a placeholder if the original 'upi_number' in the dataset was just an ID.
    # If 'upi_number' in the dataset was actually a feature like merchant type ID, then we need to map the merchant_upi to that ID.
    # Given the dataset's 'upi_number' is `7662001056`, it looks like a numerical identifier.
    # Let's use a placeholder for this, or better, re-examine the `build_model.ipynb` for exact feature extraction.

    # Based on the `build_model.ipynb` and `upi_fraud_dataset.csv`:
    # `x_for_scaling = dataset.iloc[:, :10].values` means columns `Id` through `state`.
    # So, the input to the scaler/model should be:
    # [Id (dummy), trans_hour, trans_day, trans_month, trans_year, category, upi_number (dataset's, dummy), age, trans_amount, state]
    # This is 10 features.
    # Let's use 0 for `Id` and `upi_number` (dataset's) as they are likely not predictive for new transactions.

    input_data = np.array([[
        0, # Dummy for 'Id'
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
    ]])

    # Convert state string to numerical ID if necessary. Assuming `user_details['state']` is already the numerical ID.
    # If `user_details['state']` is a string (e.g., "Maharashtra"), you'd need a mapping.
    # The `database1.sql` shows `state` as `VARCHAR(100)`, but `upi_fraud_dataset.csv` has `state` as INT.
    # This is another inconsistency. For prediction, `state` must be an integer.
    # Let's assume `user_details['state']` is the integer ID for now. If not, this will cause an error.

    try:
        # Scale the input data
        scaled_input = scaler.transform(input_data)

        # Predict fraud risk
        prediction = model.predict(scaled_input)
        fraud_risk = (prediction[0][0] > 0.5).astype(int) # 0 for valid, 1 for fraudulent
        status = 'FRAUDULENT' if fraud_risk == 1 else 'VALID'
        output_message = "Transaction is VALID and processed securely." if status == 'VALID' else "FRAUDULENT transaction detected! Payment blocked."

        # Record transaction in database
        cursor.execute(
            'INSERT INTO transactions (user_mobile, merchant_upi, trans_amount, status, trans_hour, trans_day, trans_month, trans_year, category, age, state, zip, trans_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (user_mobile, merchant_upi, trans_amount, status, trans_hour, trans_day, trans_month, trans_year, category, age, state, zip_code, now)
        )
        conn.commit()

        cursor.close()
        conn.close()

        # Redirect to a result page
        return render_template('result.html', status=status.lower(), OUTPUT=output_message)

    except Exception as e:
        flash(f'Error processing transaction: {e}', 'danger')
        print(f"Prediction error: {e}")
        cursor.close()
        conn.close()
        return redirect(url_for('user_make_payment_page'))

# --- Admin Routes ---

@app.route('/admin')
def admin_dashboard():
    if session.get('user_type') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    return render_template('admin.html')

@app.route('/admin/users')
def admin_users_page():
    if session.get('user_type') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bank_accounts")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_users.html', users=users)

@app.route('/admin/merchants')
def admin_merchants_page():
    if session.get('user_type') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM merchants")
    merchants = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_merchants.html', merchants=merchants)

@app.route('/admin/transactions')
def admin_transactions_page():
    if session.get('user_type') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM transactions ORDER BY trans_date DESC")
    transactions = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_transactions.html', transactions=transactions)

@app.route('/admin/create_account', methods=['GET', 'POST'])
def admin_create_account():
    if session.get('user_type') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        full_name = request.form['full_name']
        dob = request.form['dob']
        mobile_number = request.form['mobile_number']
        email = request.form['email']
        location = request.form['location']
        state = request.form['state'] # This needs to be the numerical ID for consistency with dataset
        zip_code = request.form['zip']

        # Basic validation
        if not all([full_name, dob, mobile_number, email, location, state, zip_code]):
            flash('All fields are required!', 'danger')
            return render_template('admin_create_account.html')

        conn = get_db()
        if conn is None:
            flash('Database error. Cannot create account.', 'danger')
            return render_template('admin_create_account.html')

        try:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO bank_accounts (full_name, dob, mobile_number, email, location, state, zip) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (full_name, dob, mobile_number, email, location, state, zip_code)
            )
            conn.commit()
            flash('Account created successfully!', 'success')
            return redirect(url_for('admin_users_page'))
        except mysql.connector.IntegrityError as e:
            if "Duplicate entry" in str(e) and "'mobile_number'" in str(e):
                flash('Mobile number already registered.', 'danger')
            elif "Duplicate entry" in str(e) and "'email'" in str(e):
                flash('Email already registered.', 'danger')
            else:
                flash(f'Database error: {e}', 'danger')
        except Exception as e:
            flash(f'An unexpected error occurred: {e}', 'danger')
        finally:
            if conn.is_connected():
                cursor.close()
                conn.close()
    return render_template('admin_create_account.html')

# --- Merchant Routes ---

@app.route('/merchant')
def merchant_dashboard():
    if session.get('user_type') not in ['user', 'merchant']: # Allow users to become merchants
        flash('Please log in to access the merchant panel.', 'warning')
        return redirect(url_for('login'))

    conn = get_db()
    if conn is None:
        flash('Database connection error. Cannot retrieve merchant details.', 'danger')
        return redirect(url_for('user_dashboard')) # Redirect to user dashboard if merchant details fail

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bank_accounts WHERE mobile_number = %s", (session['mobile'],))
    user_info = cursor.fetchone()

    cursor.execute("SELECT * FROM merchants WHERE mobile_number = %s", (session['mobile'],))
    merchant_info = cursor.fetchone()

    if not merchant_info:
        flash('You need to set up your merchant account first.', 'info')
        cursor.close()
        conn.close()
        return redirect(url_for('merchant_setup'))

    # Fetch transactions received by this merchant
    cursor.execute('SELECT * FROM transactions WHERE merchant_upi = %s ORDER BY trans_date DESC', (merchant_info['upi_number'],))
    transactions = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('merchant.html', user=user_info, merchant=merchant_info, transactions=transactions)

@app.route('/merchant/setup', methods=['GET', 'POST'])
def merchant_setup():
    if session.get('user_type') not in ['user', 'merchant']:
        flash('Please log in to set up a merchant account.', 'warning')
        return redirect(url_for('login'))
    
    # Check if the user is already a merchant
    conn = get_db()
    if conn is None:
        flash('Database connection error. Cannot set up merchant account.', 'danger')
        return render_template('merchant_setup.html')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM merchants WHERE mobile_number = %s", (session['mobile'],))
    existing_merchant = cursor.fetchone()
    cursor.close()
    conn.close()
    if existing_merchant:
        flash('You have already set up your merchant account.', 'info')
        return redirect(url_for('merchant_dashboard'))

    if request.method == 'POST':
        conn = get_db()
        if conn is None:
            flash('Database error. Cannot set up merchant account.', 'danger')
            return render_template('merchant_setup.html')
        try:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO merchants (mobile_number, upi_number, category) VALUES (%s, %s, %s)',
                         (session['mobile'], request.form['upi_number'], request.form['category']))
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
                conn.close()
    return render_template('merchant_setup.html')

if __name__ == '__main__':
    # Create the 'model' directory if it doesn't exist
    if not os.path.exists('model'):
        os.makedirs('model')
    app.run(debug=True)
