from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, jsonify)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta
import os, urllib.parse, smtplib, threading, secrets, json, re

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'nailsonboard-kavya-2024')

# ══════════════════════════════════════════════════════════════
#  DATABASE — Supabase (free forever)
#  Get your URL from: supabase.com → project → settings → database
#  Connection string format: postgresql://postgres:[password]@[host]:5432/postgres
# ══════════════════════════════════════════════════════════════
db_url = os.environ.get('DATABASE_URL', '')
if not db_url:
    basedir = os.path.abspath(os.path.dirname(__file__))
    os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
    db_url = 'sqlite:///' + os.path.join(basedir, 'instance', 'nailsonboard.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
IST = timezone(timedelta(hours=5, minutes=30))

# ══════════════════════════════════════════════════════════════
#  CLOUDINARY — Free image hosting (free forever, 25GB)
#  Get from: cloudinary.com → Dashboard → API Keys
# ══════════════════════════════════════════════════════════════
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
CLOUDINARY_API_KEY    = os.environ.get('CLOUDINARY_API_KEY', '')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')

def init_cloudinary():
    if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
        try:
            import cloudinary
            cloudinary.config(
                cloud_name=CLOUDINARY_CLOUD_NAME,
                api_key=CLOUDINARY_API_KEY,
                api_secret=CLOUDINARY_API_SECRET,
                secure=True
            )
            return True
        except Exception as e:
            print(f"[CLOUDINARY] Init error: {e}")
    return False

CLOUDINARY_ENABLED = init_cloudinary()

# ══════════════════════════════════════════════════════════════
#  EMAIL — Free Gmail SMTP
# ══════════════════════════════════════════════════════════════
EMAIL_SENDER   = os.environ.get('EMAIL_SENDER', 'your_gmail@gmail.com')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', 'xxxx xxxx xxxx xxxx')
EMAIL_NAME     = 'Nails on Board'
ADMIN_EMAIL    = os.environ.get('ADMIN_EMAIL', 'your_gmail@gmail.com')

# ══════════════════════════════════════════════════════════════
#  UPI PAYMENT
# ══════════════════════════════════════════════════════════════
UPI_ID          = os.environ.get('UPI_ID', 'yourname@upi')
UPI_NAME        = 'Nails on Board'
UPI_DESCRIPTION = 'Payment to Nails on Board'

db = SQLAlchemy(app)

# ─── IST helpers ──────────────────────────────────────────────
def fmt_ist(dt):
    if dt is None: return ''
    return dt.replace(tzinfo=timezone.utc).astimezone(IST).strftime('%d %b %Y, %I:%M %p IST')

app.jinja_env.globals['fmt_ist'] = fmt_ist

# ─── Models ───────────────────────────────────────────────────

class Admin(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)

class Customer(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    phone         = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class NailProduct(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(120), nullable=False)
    description    = db.Column(db.Text, nullable=False)
    price          = db.Column(db.Float, nullable=False)
    category       = db.Column(db.String(80), nullable=False)
    image_filename = db.Column(db.String(500), nullable=True)  # stores Cloudinary URL or filename
    image_public_id = db.Column(db.String(200), nullable=True) # Cloudinary public_id for deletion
    in_stock       = db.Column(db.Boolean, default=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

class Appointment(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    customer_name  = db.Column(db.String(120), nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    service        = db.Column(db.String(120), nullable=False)
    preferred_date = db.Column(db.String(50), nullable=False)
    preferred_time = db.Column(db.String(50), nullable=False)
    notes          = db.Column(db.Text, nullable=True)
    status         = db.Column(db.String(20), default='pending')
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    customer_name    = db.Column(db.String(120), nullable=False)
    customer_email   = db.Column(db.String(120), nullable=False)
    customer_phone   = db.Column(db.String(20), nullable=False)
    customer_address = db.Column(db.Text, nullable=False)
    product_id       = db.Column(db.Integer, db.ForeignKey('nail_product.id'), nullable=False)
    quantity         = db.Column(db.Integer, default=1)
    total_price      = db.Column(db.Float, nullable=False)
    status           = db.Column(db.String(20), default='pending_payment')
    payment_status   = db.Column(db.String(20), default='unpaid')
    payment_ref      = db.Column(db.String(100), nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    product          = db.relationship('NailProduct', backref='orders')

class Notification(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    message        = db.Column(db.Text, nullable=False)
    type           = db.Column(db.String(20), default='info')
    is_read        = db.Column(db.Boolean, default=False)
    target         = db.Column(db.String(20), default='admin')
    customer_email = db.Column(db.String(120), nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

class PasswordResetToken(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(120), nullable=False)
    token      = db.Column(db.String(100), unique=True, nullable=False)
    used       = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AppSetting(db.Model):
    id    = db.Column(db.Integer, primary_key=True)
    key   = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)

# ─── Settings helpers ─────────────────────────────────────────

def get_setting(key, default=None):
    try:
        s = AppSetting.query.filter_by(key=key).first()
        if s:
            try: return json.loads(s.value)
            except: return s.value
    except: pass
    return default

def set_setting(key, value):
    try:
        s = AppSetting.query.filter_by(key=key).first()
        if s: s.value = json.dumps(value)
        else: db.session.add(AppSetting(key=key, value=json.dumps(value)))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[SETTING ERROR] {e}")

DEFAULT_SERVICES   = ['Gel Nails','Acrylic Extension','Nail Art','Manicure','Pedicure','Nail Jewels','Custom Design']
DEFAULT_TIME_SLOTS = ['10:00 AM','11:00 AM','12:00 PM','2:00 PM','3:00 PM','4:00 PM','5:00 PM']

# ─── Image Upload (Cloudinary or local) ───────────────────────

def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_image(file):
    """Upload to Cloudinary if configured, else save locally. Returns (url_or_filename, public_id)."""
    if not file or not file.filename or not allowed_file(file.filename):
        return None, None
    if CLOUDINARY_ENABLED:
        try:
            import cloudinary.uploader
            result = cloudinary.uploader.upload(
                file,
                folder='nails_on_board',
                transformation=[{'width': 800, 'height': 800, 'crop': 'limit', 'quality': 'auto'}]
            )
            print(f"[CLOUDINARY] Uploaded: {result['secure_url']}")
            return result['secure_url'], result['public_id']
        except Exception as e:
            print(f"[CLOUDINARY UPLOAD ERROR] {e}")
            # Fall back to local
    # Local fallback
    try:
        upload_dir = os.path.join('static', 'uploads', 'nails')
        os.makedirs(upload_dir, exist_ok=True)
        fn = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
        file.save(os.path.join(upload_dir, fn))
        return fn, None
    except Exception as e:
        print(f"[LOCAL UPLOAD ERROR] {e}")
        return None, None

def delete_image(image_ref, public_id=None):
    """Delete from Cloudinary or local."""
    if public_id and CLOUDINARY_ENABLED:
        try:
            import cloudinary.uploader
            cloudinary.uploader.destroy(public_id)
            print(f"[CLOUDINARY] Deleted: {public_id}")
        except Exception as e:
            print(f"[CLOUDINARY DELETE ERROR] {e}")
    elif image_ref and not image_ref.startswith('http'):
        try:
            fp = os.path.join('static', 'uploads', 'nails', image_ref)
            if os.path.exists(fp): os.remove(fp)
        except Exception as e:
            print(f"[LOCAL DELETE ERROR] {e}")

def get_image_url(product):
    """Get display URL for product image."""
    if not product.image_filename:
        return None
    if product.image_filename.startswith('http'):
        return product.image_filename  # Cloudinary URL
    return url_for('static', filename='uploads/nails/' + product.image_filename)

app.jinja_env.globals['get_image_url'] = get_image_url

# ─── Email ────────────────────────────────────────────────────

def _send_thread(to, subject, body):
    try:
        sender = EMAIL_SENDER
        password = EMAIL_PASSWORD
        if 'your_gmail' in sender or 'xxxx' in password:
            print(f"[EMAIL SKIPPED - not configured] To:{to} | {subject}"); return
        print(f"[EMAIL ATTEMPTING] To:{to} | From:{sender}")
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f"{EMAIL_NAME} <{sender}>"
        msg['To']      = to
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=20) as s:
            s.ehlo()
            s.login(sender, password)
            s.sendmail(sender, to, msg.as_string())
        print(f"[EMAIL OK ✅] {to} | {subject}")
    except smtplib.SMTPAuthenticationError as e:
        print(f"[EMAIL AUTH ERROR ❌] Wrong App Password or Gmail security blocked. Details: {e}")
    except smtplib.SMTPException as e:
        print(f"[EMAIL SMTP ERROR ❌] {e}")
    except Exception as e:
        print(f"[EMAIL ERROR ❌] {type(e).__name__}: {e}")

def send_email(to, subject, body):
    threading.Thread(target=_send_thread, args=(to, subject, body), daemon=True).start()

def email_html(title, body_html, cta_url=None, cta_text=None):
    cta = (f'<div style="text-align:center;margin:22px 0"><a href="{cta_url}" '
           f'style="background:#c4687a;color:#fff;padding:12px 28px;border-radius:40px;'
           f'text-decoration:none;font-weight:600;font-size:14px;display:inline-block">'
           f'{cta_text}</a></div>') if cta_url else ''
    return (f'<div style="font-family:Arial,sans-serif;background:#fdf8f5;padding:24px 0">'
            f'<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:14px;overflow:hidden">'
            f'<div style="background:linear-gradient(135deg,#c4687a,#9b3d54);padding:22px 26px;text-align:center">'
            f'<p style="color:rgba(255,255,255,.7);font-size:11px;margin:0 0 3px;letter-spacing:.12em;text-transform:uppercase">✦ Nails on Board</p>'
            f'<h1 style="color:#fff;margin:0;font-size:19px;font-weight:400">{title}</h1></div>'
            f'<div style="padding:22px 26px;color:#4a3040;line-height:1.7;font-size:14px">{body_html}{cta}</div>'
            f'<div style="background:#f5dde2;padding:12px 26px;text-align:center;font-size:11px;color:#8a7080">'
            f'© Nails on Board</div></div></div>')

# ─── Helpers ──────────────────────────────────────────────────

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def d(*a, **kw):
        if not session.get('admin_logged_in'):
            flash('Please log in as admin.', 'error')
            return redirect(url_for('admin_login'))
        return f(*a, **kw)
    return d

def customer_login_required(f):
    from functools import wraps
    @wraps(f)
    def d(*a, **kw):
        if not session.get('customer_logged_in'):
            flash('Please log in to continue.', 'error')
            return redirect(url_for('customer_login'))
        return f(*a, **kw)
    return d

def add_notif(msg, t='info', target='admin', email=None):
    try:
        db.session.add(Notification(message=msg, type=t, target=target, customer_email=email))
        db.session.commit()
    except:
        db.session.rollback()

def validate_password(pw):
    if len(pw) < 8:          return 'Password must be at least 8 characters.'
    if not re.search(r'[A-Z]', pw): return 'Password must contain at least 1 uppercase letter.'
    if not re.search(r'[a-z]', pw): return 'Password must contain at least 1 lowercase letter.'
    return None

def make_upi_url(amount, ref):
    p = {'pa':UPI_ID,'pn':UPI_NAME,'am':f"{amount:.2f}",'cu':'INR','tn':f'Order #{ref}','tr':str(ref)}
    return 'upi://pay?' + urllib.parse.urlencode(p)

def make_qr(upi_url):
    return f"https://api.qrserver.com/v1/create-qr-code/?data={urllib.parse.quote(upi_url)}&size=250x250"

# ─── Customer Auth ────────────────────────────────────────────

@app.route('/signup', methods=['GET', 'POST'])
def customer_signup():
    if session.get('customer_logged_in'):
        return redirect(url_for('customer_dashboard'))
    if request.method == 'POST':
        name  = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        phone = request.form.get('phone', '').strip()
        pw    = request.form['password']
        err   = validate_password(pw)
        if err:
            flash(err, 'error')
            return render_template('customer_auth.html', mode='signup',
                                   form_name=name, form_email=email, form_phone=phone)
        if Customer.query.filter_by(email=email).first():
            flash('An account with this email already exists. Please log in.', 'error')
            return redirect(url_for('customer_login'))
        c = Customer(name=name, email=email, phone=phone,
                     password_hash=generate_password_hash(pw))
        db.session.add(c); db.session.commit()
        session['customer_logged_in'] = True
        session['customer_email']     = email
        session['customer_name']      = name
        send_email(email, 'Welcome to Nails on Board! 💅', email_html(
            'Welcome to Nails on Board!',
            f'<p>Hi <strong>{name}</strong>,</p><p>Your account is ready! Track orders & appointments anytime.</p>',
            url_for('customer_dashboard', _external=True), 'Go to My Account →'))
        flash(f'Welcome {name}! Account created.', 'success')
        return redirect(url_for('customer_dashboard'))
    return render_template('customer_auth.html', mode='signup')

@app.route('/login', methods=['GET', 'POST'])
def customer_login():
    if session.get('customer_logged_in'):
        return redirect(url_for('customer_dashboard'))
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        pw    = request.form['password']
        c     = Customer.query.filter_by(email=email).first()
        if c and check_password_hash(c.password_hash, pw):
            session['customer_logged_in'] = True
            session['customer_email']     = email
            session['customer_name']      = c.name
            flash(f'Welcome back, {c.name}!', 'success')
            return redirect(url_for('customer_dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('customer_auth.html', mode='login')

@app.route('/logout')
def customer_logout():
    session.pop('customer_logged_in', None)
    session.pop('customer_email', None)
    session.pop('customer_name', None)
    return redirect(url_for('index'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        c = Customer.query.filter_by(email=email).first()
        if c:
            PasswordResetToken.query.filter_by(email=email).delete()
            token  = secrets.token_urlsafe(32)
            expiry = datetime.utcnow() + timedelta(minutes=30)
            db.session.add(PasswordResetToken(email=email, token=token, expires_at=expiry))
            db.session.commit()
            reset_url = url_for('reset_password', token=token, _external=True)
            send_email(email, 'Reset Your Password — Nails on Board', email_html(
                'Password Reset 🔐',
                f'<p>Hi <strong>{c.name}</strong>,</p><p>Click below to reset your password. Link expires in 30 minutes.</p>',
                reset_url, 'Reset My Password →'))
        flash('If that email exists, a reset link has been sent.', 'success')
        return redirect(url_for('forgot_password'))
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    r = PasswordResetToken.query.filter_by(token=token, used=False).first()
    if not r or r.expires_at < datetime.utcnow():
        flash('This reset link has expired. Please request a new one.', 'error')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        pw  = request.form.get('password', '')
        pw2 = request.form.get('password2', '')
        err = validate_password(pw)
        if err:
            flash(err, 'error')
            return render_template('reset_password.html', token=token)
        if pw != pw2:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html', token=token)
        c = Customer.query.filter_by(email=r.email).first()
        if not c:
            flash('Account not found.', 'error')
            return redirect(url_for('customer_login'))
        c.password_hash = generate_password_hash(pw)
        r.used = True
        db.session.commit()
        flash('Password changed! Please login.', 'success')
        return redirect(url_for('customer_login'))
    return render_template('reset_password.html', token=token)

@app.route('/my-account')
@customer_login_required
def customer_dashboard():
    email  = session['customer_email']
    orders = Order.query.filter_by(customer_email=email).order_by(Order.created_at.desc()).all()
    appts  = Appointment.query.filter_by(customer_email=email).order_by(Appointment.created_at.desc()).all()
    notifs = Notification.query.filter_by(target='customer', customer_email=email).order_by(Notification.created_at.desc()).all()
    for n in notifs: n.is_read = True
    db.session.commit()
    return render_template('customer_dashboard.html', orders=orders, appointments=appts,
        notifications=notifs, customer_name=session['customer_name'], email=email)

# ─── Customer Public Routes ───────────────────────────────────

@app.route('/')
def index():
    products = NailProduct.query.filter_by(in_stock=True).order_by(NailProduct.created_at.desc()).all()
    hero_img = get_setting('hero_image_url', None)
    return render_template('index.html', products=products, hero_img=hero_img)

@app.route('/shop')
def shop():
    cat      = request.args.get('category', 'all')
    q        = NailProduct.query.filter_by(in_stock=True)
    products = q.all() if cat == 'all' else q.filter_by(category=cat).all()
    cats     = [c[0] for c in db.session.query(NailProduct.category).distinct().all()]
    return render_template('shop.html', products=products, categories=cats, current_category=cat)

@app.route('/product/<int:pid>')
def product_detail(pid):
    p = NailProduct.query.get_or_404(pid)
    related = NailProduct.query.filter_by(category=p.category, in_stock=True).filter(NailProduct.id != pid).limit(4).all()
    return render_template('product_detail.html', product=p, related=related)

@app.route('/order/<int:pid>', methods=['GET', 'POST'])
def place_order(pid):
    product  = NailProduct.query.get_or_404(pid)
    customer = Customer.query.filter_by(email=session['customer_email']).first() if session.get('customer_logged_in') else None
    if request.method == 'POST':
        qty = max(1, int(request.form.get('quantity', 1)))
        o = Order(
            customer_name=request.form['name'].strip(),
            customer_email=request.form['email'].strip().lower(),
            customer_phone=request.form['phone'].strip(),
            customer_address=request.form['address'].strip(),
            product_id=pid, quantity=qty,
            total_price=product.price * qty,
            status='pending_payment', payment_status='unpaid'
        )
        db.session.add(o); db.session.commit()
        add_notif(f"🛍️ New order #{o.id} from {o.customer_name} — {product.name} ×{qty} | ₹{o.total_price:.0f}", 'order', 'admin')
        add_notif(f"Order #{o.id} placed for {product.name} ×{qty}. Please complete UPI payment.", 'order', 'customer', o.customer_email)
        send_email(o.customer_email, f"Order #{o.id} Placed — Nails on Board", email_html(
            f"Order #{o.id} Received 💅",
            f"<p>Hi <strong>{o.customer_name}</strong>,</p>"
            f"<table style='width:100%;border-collapse:collapse;margin:12px 0'>"
            f"<tr style='background:#f5dde2'><td style='padding:8px 12px;font-weight:600'>Product</td><td style='padding:8px 12px'>{product.name}</td></tr>"
            f"<tr><td style='padding:8px 12px;font-weight:600;border-top:1px solid #f5dde2'>Qty</td><td style='padding:8px 12px;border-top:1px solid #f5dde2'>{qty}</td></tr>"
            f"<tr style='background:#f5dde2'><td style='padding:8px 12px;font-weight:600'>Total</td><td style='padding:8px 12px'>₹{o.total_price:.2f}</td></tr>"
            f"</table>",
            url_for('payment_page', order_id=o.id, _external=True), "Pay Now →"))
        send_email(ADMIN_EMAIL, f"🛍️ New Order #{o.id}", email_html(
            f"New Order #{o.id}",
            f"<p>{o.customer_name} · {o.customer_email} · {o.customer_phone}</p>"
            f"<p>{product.name} ×{qty} = ₹{o.total_price:.2f}</p>",
            url_for('admin_orders', _external=True), "View in Admin →"))
        return redirect(url_for('payment_page', order_id=o.id))
    return render_template('order.html', product=product, customer=customer)

@app.route('/payment/<int:order_id>')
def payment_page(order_id):
    order   = Order.query.get_or_404(order_id)
    upi_url = make_upi_url(order.total_price, order.id)
    return render_template('payment.html', order=order, upi_url=upi_url,
                           qr_url=make_qr(upi_url), upi_id=UPI_ID, upi_name=UPI_NAME)

@app.route('/payment/<int:order_id>/confirm', methods=['POST'])
def confirm_payment(order_id):
    order = Order.query.get_or_404(order_id)
    utr   = request.form.get('utr_ref', '').strip()
    if not utr:
        flash('Please enter your UPI Transaction ID.', 'error')
        return redirect(url_for('payment_page', order_id=order_id))
    order.payment_ref    = utr
    order.payment_status = 'verification_pending'
    order.status         = 'verification_pending'
    db.session.commit()
    add_notif(f"💳 Payment UTR for Order #{order.id}: {utr}", 'order', 'admin')
    add_notif(f"Payment ref {utr} received for Order #{order.id}.", 'order', 'customer', order.customer_email)
    send_email(order.customer_email, f"Payment Received — Order #{order.id}", email_html(
        "Payment Reference Received ✅",
        f"<p>Hi <strong>{order.customer_name}</strong>,</p>"
        f"<p>UTR: <strong style='font-family:monospace'>{utr}</strong></p>"
        f"<p>We'll verify and confirm shortly.</p>",
        url_for('customer_dashboard', _external=True), "Track My Order →"))
    send_email(ADMIN_EMAIL, f"💳 Verify Payment — Order #{order.id}", email_html(
        f"Verify Payment #{order.id}",
        f"<p>UTR: <strong style='font-family:monospace'>{utr}</strong></p>",
        url_for('admin_orders', _external=True), "Verify →"))
    flash('Payment submitted! We will verify and confirm your order.', 'success')
    return redirect(url_for('order_confirmation', order_id=order_id))

@app.route('/order/confirmation/<int:order_id>')
def order_confirmation(order_id):
    return render_template('order_confirmation.html', order=Order.query.get_or_404(order_id))

@app.route('/appointment', methods=['GET', 'POST'])
def appointment():
    customer   = Customer.query.filter_by(email=session['customer_email']).first() if session.get('customer_logged_in') else None
    services   = get_setting('appt_services', DEFAULT_SERVICES)
    time_slots = get_setting('appt_time_slots', DEFAULT_TIME_SLOTS)
    blocked    = get_setting('appt_blocked_dates', [])
    if request.method == 'POST':
        date = request.form['date']
        if date in blocked:
            flash('Sorry, that date is unavailable. Please choose another date.', 'error')
            return render_template('appointment.html', customer=customer,
                                   services=services, time_slots=time_slots, blocked_dates=blocked)
        a = Appointment(
            customer_name=request.form['name'].strip(),
            customer_email=request.form['email'].strip().lower(),
            customer_phone=request.form['phone'].strip(),
            service=request.form['service'],
            preferred_date=date,
            preferred_time=request.form['time'],
            notes=request.form.get('notes', '').strip()
        )
        db.session.add(a); db.session.commit()
        add_notif(f"📅 New appointment — {a.customer_name} | {a.service} on {a.preferred_date}", 'appointment', 'admin')
        add_notif(f"Appointment for {a.service} on {a.preferred_date} received!", 'appointment', 'customer', a.customer_email)
        send_email(a.customer_email, "Appointment Requested — Nails on Board", email_html(
            "Appointment Received 💅",
            f"<p>Hi <strong>{a.customer_name}</strong>,</p>"
            f"<table style='width:100%;border-collapse:collapse;margin:12px 0'>"
            f"<tr style='background:#f5dde2'><td style='padding:8px 12px;font-weight:600'>Service</td><td style='padding:8px 12px'>{a.service}</td></tr>"
            f"<tr><td style='padding:8px 12px;font-weight:600;border-top:1px solid #f5dde2'>Date</td><td style='padding:8px 12px;border-top:1px solid #f5dde2'>{a.preferred_date}</td></tr>"
            f"<tr style='background:#f5dde2'><td style='padding:8px 12px;font-weight:600'>Time</td><td style='padding:8px 12px'>{a.preferred_time}</td></tr>"
            f"</table>",
            url_for('customer_dashboard', _external=True), "Track Appointment →"))
        send_email(ADMIN_EMAIL, f"📅 New Appointment — {a.customer_name}", email_html(
            "New Appointment",
            f"<p>{a.customer_name} · {a.customer_email} · {a.customer_phone}</p>"
            f"<p>{a.service} on {a.preferred_date} at {a.preferred_time}</p>",
            url_for('admin_appointments', _external=True), "View →"))
        flash('Appointment submitted! Check your email.', 'success')
        return redirect(url_for('appointment_confirmation', appt_id=a.id))
    return render_template('appointment.html', customer=customer,
                           services=services, time_slots=time_slots, blocked_dates=blocked)

@app.route('/appointment/confirmation/<int:appt_id>')
def appointment_confirmation(appt_id):
    return render_template('appointment_confirmation.html', appt=Appointment.query.get_or_404(appt_id))

@app.route('/gallery')
def gallery():
    products = NailProduct.query.filter(NailProduct.image_filename != None).order_by(NailProduct.created_at.desc()).all()
    return render_template('gallery.html', products=products)

@app.route('/track', methods=['GET', 'POST'])
def customer_track():
    if session.get('customer_logged_in'):
        return redirect(url_for('customer_dashboard'))
    results, email = None, None
    if request.method == 'POST':
        email  = request.form.get('email', '').strip().lower()
        orders = Order.query.filter_by(customer_email=email).order_by(Order.created_at.desc()).all()
        appts  = Appointment.query.filter_by(customer_email=email).order_by(Appointment.created_at.desc()).all()
        notifs = Notification.query.filter_by(target='customer', customer_email=email).order_by(Notification.created_at.desc()).all()
        for n in notifs: n.is_read = True
        db.session.commit()
        results = {'orders': orders, 'appointments': appts, 'notifications': notifs}
        if not orders and not appts:
            flash('No records found for this email.', 'error')
            results = None
    return render_template('track.html', results=results, email=email)

# ─── Admin Routes ─────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        a = Admin.query.filter_by(username=request.form['username']).first()
        if a and check_password_hash(a.password_hash, request.form['password']):
            session['admin_logged_in'] = True
            session['admin_username']  = a.username
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear(); return redirect(url_for('admin_login'))

@app.route('/admin')
@app.route('/admin/')
@admin_required
def admin_dashboard():
    email_ok = 'your_gmail' not in EMAIL_SENDER
    cloud_ok = CLOUDINARY_ENABLED
    return render_template('admin/dashboard.html',
        total_products=NailProduct.query.count(),
        total_orders=Order.query.count(),
        total_appointments=Appointment.query.count(),
        total_customers=Customer.query.count(),
        pending_orders=Order.query.filter(Order.status.in_(['pending_payment','verification_pending'])).count(),
        pending_appointments=Appointment.query.filter_by(status='pending').count(),
        unread_notifs=Notification.query.filter_by(target='admin', is_read=False).count(),
        recent_orders=Order.query.order_by(Order.created_at.desc()).limit(5).all(),
        recent_appointments=Appointment.query.order_by(Appointment.created_at.desc()).limit(5).all(),
        email_configured=email_ok, upi_id=UPI_ID, cloudinary_enabled=cloud_ok)

@app.route('/admin/products')
@admin_required
def admin_products():
    return render_template('admin/products.html',
        products=NailProduct.query.order_by(NailProduct.created_at.desc()).all())

@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    if request.method == 'POST':
        img_url, pub_id = upload_image(request.files.get('image'))
        db.session.add(NailProduct(
            name=request.form['name'].strip(),
            description=request.form['description'].strip(),
            price=float(request.form['price']),
            category=request.form['category'].strip(),
            image_filename=img_url,
            image_public_id=pub_id,
            in_stock=bool(request.form.get('in_stock'))))
        db.session.commit()
        flash('Product added!', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin/add_product.html')

@app.route('/admin/products/edit/<int:pid>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(pid):
    p = NailProduct.query.get_or_404(pid)
    if request.method == 'POST':
        new_img, new_pub_id = upload_image(request.files.get('image'))
        if new_img:
            delete_image(p.image_filename, p.image_public_id)
            p.image_filename  = new_img
            p.image_public_id = new_pub_id
        p.name=request.form['name'].strip()
        p.description=request.form['description'].strip()
        p.price=float(request.form['price'])
        p.category=request.form['category'].strip()
        p.in_stock=bool(request.form.get('in_stock'))
        db.session.commit()
        flash('Product updated!', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin/edit_product.html', product=p)

@app.route('/admin/products/delete/<int:pid>', methods=['POST'])
@admin_required
def admin_delete_product(pid):
    try:
        p = NailProduct.query.get_or_404(pid)
        delete_image(p.image_filename, p.image_public_id)
        db.session.delete(p)
        db.session.commit()
        flash('Product deleted!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"[DELETE ERROR] {e}")
        flash('Error deleting product. Please try again.', 'error')
    return redirect(url_for('admin_products'))

@app.route('/admin/orders')
@admin_required
def admin_orders():
    return render_template('admin/orders.html',
        orders=Order.query.order_by(Order.created_at.desc()).all())

@app.route('/admin/orders/update/<int:oid>', methods=['POST'])
@admin_required
def admin_update_order(oid):
    o = Order.query.get_or_404(oid)
    o.status         = request.form['status']
    o.payment_status = request.form.get('payment_status', o.payment_status)
    db.session.commit()
    add_notif(f"Order #{o.id} → {o.status.replace('_',' ').title()} | Payment: {o.payment_status.replace('_',' ').title()}", 'order', 'customer', o.customer_email)
    send_email(o.customer_email, f"Order #{o.id} Update", email_html(
        f"Order #{o.id} Updated",
        f"<p>Hi <strong>{o.customer_name}</strong>,</p>"
        f"<p>Status: <strong>{o.status.replace('_',' ').title()}</strong> | Payment: <strong>{o.payment_status.replace('_',' ').title()}</strong></p>",
        url_for('customer_dashboard', _external=True), "Track →"))
    flash('Order updated!', 'success')
    return redirect(url_for('admin_orders'))

@app.route('/admin/orders/email/<int:oid>', methods=['POST'])
@admin_required
def admin_email_order(oid):
    o   = Order.query.get_or_404(oid)
    msg = request.form.get('custom_msg', '').strip() or f"Update on Order #{o.id}: {o.status.replace('_',' ')}."
    add_notif(msg, 'order', 'customer', o.customer_email)
    send_email(o.customer_email, f"Order #{o.id} Update", email_html(
        f"Order #{o.id}", f"<p>Hi <strong>{o.customer_name}</strong>,</p><p>{msg}</p>",
        url_for('customer_dashboard', _external=True), "Track →"))
    flash('Email sent!', 'success')
    return redirect(url_for('admin_orders'))

@app.route('/admin/appointments')
@admin_required
def admin_appointments():
    return render_template('admin/appointments.html',
        appointments=Appointment.query.order_by(Appointment.created_at.desc()).all())

@app.route('/admin/appointments/update/<int:aid>', methods=['POST'])
@admin_required
def admin_update_appointment(aid):
    a = Appointment.query.get_or_404(aid)
    a.status = request.form['status']
    db.session.commit()
    msgs = {
        'confirmed': f"Your {a.service} on {a.preferred_date} at {a.preferred_time} is CONFIRMED 💅",
        'completed': f"Thank you for visiting! Hope you love your {a.service}! 💅",
        'cancelled': f"Your {a.service} on {a.preferred_date} was cancelled. Please contact us.",
    }
    body = msgs.get(a.status, f"Your {a.service} appointment is now {a.status}.")
    add_notif(f"Appointment #{a.id} → {a.status.title()}", 'appointment', 'customer', a.customer_email)
    send_email(a.customer_email, "Appointment Update — Nails on Board", email_html(
        f"Appointment {a.status.title()} 💅",
        f"<p>Hi <strong>{a.customer_name}</strong>,</p><p>{body}</p>",
        url_for('customer_dashboard', _external=True), "View →"))
    flash('Appointment updated!', 'success')
    return redirect(url_for('admin_appointments'))

@app.route('/admin/appointments/email/<int:aid>', methods=['POST'])
@admin_required
def admin_email_appointment(aid):
    a   = Appointment.query.get_or_404(aid)
    msg = request.form.get('custom_msg', '').strip() or \
          f"Reminder: Your {a.service} on {a.preferred_date} at {a.preferred_time}."
    add_notif(msg, 'appointment', 'customer', a.customer_email)
    send_email(a.customer_email, "Appointment Reminder — Nails on Board", email_html(
        "Reminder 💅", f"<p>Hi <strong>{a.customer_name}</strong>,</p><p>{msg}</p>",
        url_for('customer_dashboard', _external=True), "View →"))
    flash('Email sent!', 'success')
    return redirect(url_for('admin_appointments'))

@app.route('/admin/appointment-settings', methods=['GET', 'POST'])
@admin_required
def admin_appt_settings():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_services':
            services = [s.strip() for s in request.form.get('services','').splitlines() if s.strip()]
            set_setting('appt_services', services)
            flash(f'{len(services)} services saved!', 'success')
        elif action == 'save_slots':
            slots = [s.strip() for s in request.form.get('time_slots','').splitlines() if s.strip()]
            set_setting('appt_time_slots', slots)
            flash(f'{len(slots)} time slots saved!', 'success')
        elif action == 'add_blocked':
            date = request.form.get('blocked_date','').strip()
            if date:
                blocked = get_setting('appt_blocked_dates', [])
                if date not in blocked:
                    blocked.append(date); blocked.sort()
                    set_setting('appt_blocked_dates', blocked)
                flash(f'{date} blocked.', 'success')
        elif action == 'remove_blocked':
            date = request.form.get('remove_date','').strip()
            if date:
                blocked = get_setting('appt_blocked_dates', [])
                if date in blocked: blocked.remove(date)
                set_setting('appt_blocked_dates', blocked)
                flash(f'{date} unblocked.', 'success')
        elif action == 'reset_defaults':
            set_setting('appt_services', DEFAULT_SERVICES)
            set_setting('appt_time_slots', DEFAULT_TIME_SLOTS)
            set_setting('appt_blocked_dates', [])
            flash('Reset to defaults.', 'success')
        return redirect(url_for('admin_appt_settings'))
    return render_template('admin/appt_settings.html',
        services=get_setting('appt_services', DEFAULT_SERVICES),
        time_slots=get_setting('appt_time_slots', DEFAULT_TIME_SLOTS),
        blocked_dates=get_setting('appt_blocked_dates', []))

@app.route('/admin/customers')
@admin_required
def admin_customers():
    return render_template('admin/customers.html',
        customers=Customer.query.order_by(Customer.created_at.desc()).all())

@app.route('/admin/notifications')
@admin_required
def admin_notifications():
    notifs = Notification.query.filter_by(target='admin').order_by(Notification.created_at.desc()).all()
    for n in notifs: n.is_read = True
    db.session.commit()
    return render_template('admin/notifications.html', notifs=notifs)

@app.route('/admin/notifications/count')
@admin_required
def notif_count():
    return jsonify({'count': Notification.query.filter_by(target='admin', is_read=False).count()})

@app.route('/admin/hero-image', methods=['POST'])
@admin_required
def admin_upload_hero():
    f = request.files.get('hero_image')
    if f and f.filename and allowed_file(f.filename):
        img_url, pub_id = upload_image(f)
        if img_url:
            set_setting('hero_image_url', img_url)
            set_setting('hero_image_pub_id', pub_id or '')
            flash('Hero image updated!', 'success')
        else:
            flash('Image upload failed. Please try again.', 'error')
    return redirect(url_for('admin_dashboard'))

# ─── Init DB ──────────────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        if not Admin.query.first():
            db.session.add(Admin(
                username='KavyaChheda0510',
                password_hash=generate_password_hash('KRC@2004'),
                email='admin@nailsonboard.com'))
            db.session.commit()
            print("✅ Admin created: KavyaChheda0510 / KRC@2004")
        print(f"✅ Database ready")
        print(f"✅ Cloudinary: {'Active' if CLOUDINARY_ENABLED else 'Not configured (using local)'}")

if __name__ == '__main__':
    init_db()
    email_ok = 'your_gmail' not in EMAIL_SENDER
    print(f"\n🌸 Nails on Board running!")
    print(f"   http://127.0.0.1:5000")
    print(f"   Admin: KavyaChheda0510 / KRC@2004")
    print(f"   Email: {'✅' if email_ok else '⚠️ Not configured'}")
    print(f"   Cloudinary: {'✅' if CLOUDINARY_ENABLED else '⚠️ Not configured'}\n")
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
