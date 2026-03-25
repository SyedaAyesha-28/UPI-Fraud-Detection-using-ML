-- This script is updated for MySQL with Email and OTP fields.

-- Drop existing tables if they exist to apply new schema
DROP TABLE IF EXISTS `transactions`;
DROP TABLE IF EXISTS `merchants`;
DROP TABLE IF EXISTS `bank_accounts`;

-- Stores user and bank account details, now with email and OTP fields.
CREATE TABLE IF NOT EXISTS `bank_accounts` (
    `id` INT PRIMARY KEY AUTO_INCREMENT,
    `full_name` TEXT NOT NULL,
    `dob` DATE NOT NULL,
    `mobile_number` VARCHAR(20) UNIQUE NOT NULL,
    `email` VARCHAR(255) UNIQUE NOT NULL, -- Added email field
    `location` VARCHAR(255) NOT NULL,
    `state` VARCHAR(100) NOT NULL,
    `zip` VARCHAR(20) NOT NULL,
    `otp` VARCHAR(6) NULL, -- To store the current OTP
    `otp_expiry` DATETIME NULL, -- To store OTP expiration time
    `creation_date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stores merchant-specific details.
CREATE TABLE IF NOT EXISTS `merchants` (
    `id` INT PRIMARY KEY AUTO_INCREMENT,
    `mobile_number` VARCHAR(20) UNIQUE NOT NULL,
    `upi_number` VARCHAR(50) UNIQUE NOT NULL,
    `category` INT NOT NULL,
    `setup_date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`mobile_number`) REFERENCES `bank_accounts` (`mobile_number`)
);

-- Stores all transaction features for auditing and prediction.
CREATE TABLE IF NOT EXISTS `transactions` (
    `id` INT PRIMARY KEY AUTO_INCREMENT,
    `user_mobile` VARCHAR(20) NOT NULL,
    `merchant_upi` VARCHAR(50) NOT NULL,
    `trans_amount` DECIMAL(10, 2) NOT NULL,
    `status` VARCHAR(20) NOT NULL,
    `trans_hour` INT NOT NULL,
    `trans_day` INT NOT NULL,
    `trans_month` INT NOT NULL,
    `trans_year` INT NOT NULL,
    `category` INT NOT NULL,
    `age` INT NOT NULL,
    `state` VARCHAR(100) NOT NULL,
    `zip` VARCHAR(20) NOT NULL,
    `trans_date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_mobile`) REFERENCES `bank_accounts` (`mobile_number`),
    FOREIGN KEY (`merchant_upi`) REFERENCES `merchants` (`upi_number`)
);

-- Inserting a default admin user. Note: Admin login is now handled in app.py, not the DB.
-- We still add a placeholder account for consistency.
INSERT IGNORE INTO `bank_accounts` (full_name, dob, mobile_number, email, location, state, zip) 
VALUES ('Admin User', '2000-01-01', '0000000000', 'admin@securepay.com', 'Bank HQ', 'System', '00000');