# 💅 Nails on Board — Complete Website

## 🚀 Quick Start

### 1. Delete old database (IMPORTANT if upgrading)
Delete the file `instance/nailsonboard.db` if it exists.

### 2. Install dependencies
```
pip install -r requirements.txt
```

### 3. Run
```
python app.py
```

### 4. Open in browser
- **Customer Site:** http://127.0.0.1:5000
- **Admin Panel:**   http://127.0.0.1:5000/admin/login

### Admin Credentials
```
Username: KavyaChheda0510
Password: KRC@2004
```

---

## 📧 Email Setup (FREE — Gmail)

Open `app.py` and fill in these 3 lines:

```python
EMAIL_SENDER   = 'your_actual_email@gmail.com'
EMAIL_PASSWORD = 'xxxx xxxx xxxx xxxx'   # App Password (16 chars)
ADMIN_EMAIL    = 'your_actual_email@gmail.com'
```

### How to get Gmail App Password (one-time, 2 minutes):
1. Go to **myaccount.google.com**
2. Security → Turn ON **2-Step Verification**
3. Security → **App Passwords**
4. Select app: **Mail** → Generate
5. Copy the 16-character password → paste into `EMAIL_PASSWORD`

---

## 💳 UPI Setup

```python
UPI_ID   = 'yourname@paytm'   # or @ybl / @okaxis / @upi
UPI_NAME = 'Nails on Board'
```

---

## 🌙 Dark Mode
Click the 🌙 button in the top-right corner of any page. Dark mode uses a violet/purple theme and is remembered across visits.

---

## 📦 Features
- Customer signup/login with persistent account
- Order & appointment tracking dashboard (logged-in or by email)
- Full notification history (never lost)
- IST time on all timestamps
- UPI payment with QR code
- Free Gmail email notifications (customer + admin)
- Admin: manage products, orders, appointments, customers
- Mobile-friendly, dark mode
- Clickable hero image (opens full-size)
- Hero image stays circular (never goes square on hover)

---

## 📁 File Structure
```
app.py                    ← All routes & logic (edit EMAIL, UPI, admin password here)
requirements.txt          ← pip dependencies
static/css/style.css      ← Customer site styles + dark mode
static/css/admin.css      ← Admin panel styles
static/js/main.js         ← Dark toggle, mobile nav, animations
static/uploads/nails/     ← All uploaded images go here
templates/                ← All HTML pages
templates/admin/          ← Admin panel pages
```
