import os, sqlite3, secrets, csv, io
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, Response
from werkzeug.security import generate_password_hash, check_password_hash

ROOT=os.path.dirname(os.path.abspath(__file__))
DB=os.environ.get('DATABASE_PATH',os.path.join(ROOT,'solarshare.db'))
os.makedirs(os.path.dirname(os.path.abspath(DB)),exist_ok=True)
app=Flask(__name__)
app.secret_key=os.environ.get('SECRET_KEY',secrets.token_hex(32))
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('PUBLIC_DEPLOYMENT')=='1')

def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init():
 with conn() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'resident', society TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS installations(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), label TEXT NOT NULL, capacity REAL NOT NULL CHECK(capacity>0), location TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), installation_id INTEGER REFERENCES installations(id), day TEXT NOT NULL, generated REAL NOT NULL CHECK(generated>=0), consumed REAL NOT NULL CHECK(consumed>=0), created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS shares(id INTEGER PRIMARY KEY, sender_id INTEGER NOT NULL REFERENCES users(id), receiver_id INTEGER NOT NULL REFERENCES users(id), kwh REAL NOT NULL CHECK(kwh>0), note TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS maintenance(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL, due TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending');''')
init()

def auth(fn):
 @wraps(fn)
 def inner(*a,**kw):
  if not session.get('uid'): return jsonify(error='Please sign in'),401
  return fn(*a,**kw)
 return inner

def admin(fn):
 @wraps(fn)
 @auth
 def inner(*a,**kw):
  if session.get('role')!='admin': return jsonify(error='Admin access required'),403
  return fn(*a,**kw)
 return inner

def payload(): return request.get_json(silent=True) or {}
def fail(msg,status=400): return jsonify(error=msg),status
def number(v):
 try: return float(v)
 except (ValueError,TypeError): return None

def user_info(uid):
 with conn() as c:
  u=c.execute('SELECT id,name,email,role,society FROM users WHERE id=?',(uid,)).fetchone()
 return dict(u) if u else None

@app.get('/')
def home(): return render_template('index.html')
@app.post('/api/register')
def register():
 d=payload(); name=str(d.get('name','')).strip(); email=str(d.get('email','')).lower().strip(); pw=str(d.get('password','')); society=str(d.get('society','')).strip()
 if not name or '@' not in email or len(pw)<8 or not society: return fail('Enter name, valid email, society and password (8+ characters).')
 try:
  with conn() as c:
   # Public deployments must not grant admin to an arbitrary first registrant.
   admin_email=os.environ.get('ADMIN_EMAIL','').strip().lower()
   role='admin' if admin_email and email==admin_email else 'resident'
   cur=c.execute('INSERT INTO users(name,email,password,role,society) VALUES(?,?,?,?,?)',(name,email,generate_password_hash(pw),role,society)); uid=cur.lastrowid
 except sqlite3.IntegrityError: return fail('Email already registered',409)
 session.update(uid=uid,role=role)
 return jsonify(user=user_info(uid)),201
@app.post('/api/login')
def login():
 d=payload(); email=str(d.get('email','')).strip().lower()
 with conn() as c: u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
 if not u or not check_password_hash(u['password'],str(d.get('password',''))): return fail('Invalid email or password',401)
 session.clear();session.update(uid=u['id'],role=u['role']);return jsonify(user=user_info(u['id']))
@app.post('/api/logout')
def logout(): session.clear();return jsonify(ok=True)
@app.get('/api/me')
def me(): return jsonify(user=user_info(session['uid']) if session.get('uid') else None)
@app.get('/api/overview')
@auth
def overview():
 uid=session['uid']
 with conn() as c:
  r=c.execute('SELECT COALESCE(SUM(generated),0) g,COALESCE(SUM(consumed),0) u,COUNT(*) n FROM readings WHERE user_id=?',(uid,)).fetchone()
  inst=c.execute('SELECT COUNT(*) n,COALESCE(SUM(capacity),0) cap FROM installations WHERE user_id=?',(uid,)).fetchone()
  series=[dict(x) for x in c.execute('SELECT day,ROUND(SUM(generated),2) generated,ROUND(SUM(consumed),2) consumed FROM readings WHERE user_id=? GROUP BY day ORDER BY day DESC LIMIT 14',(uid,))][::-1]
  share=c.execute('SELECT COALESCE(SUM(kwh),0) n FROM shares WHERE sender_id=?',(uid,)).fetchone()['n']
  received=c.execute('SELECT COALESCE(SUM(kwh),0) n FROM shares WHERE receiver_id=?',(uid,)).fetchone()['n']
  tasks=c.execute("SELECT COUNT(*) FROM maintenance WHERE user_id=? AND status='pending'",(uid,)).fetchone()[0]
 g=float(r['g']); used=min(g,float(r['u'])); return jsonify(generated=round(g,2),consumed=round(float(r['u']),2),surplus=round(max(0,g-float(r['u'])-share),2),savings=round(used*8,2),co2=round(g*.7,2),installations=inst['n'],capacity=inst['cap'],shared=share,received=received,tasks=tasks,series=series,tariff=8,emission_factor=.7)
@app.route('/api/installations',methods=['GET','POST'])
@auth
def installations():
 uid=session['uid']
 if request.method=='POST':
  d=payload(); cap=number(d.get('capacity')); label=str(d.get('label','')).strip()
  if not label or cap is None or cap<=0: return fail('Valid label and capacity required')
  with conn() as c: c.execute('INSERT INTO installations(user_id,label,capacity,location) VALUES(?,?,?,?)',(uid,label,cap,str(d.get('location',''))[:120]))
 with conn() as c: rows=[dict(r) for r in c.execute('SELECT * FROM installations WHERE user_id=? ORDER BY id DESC',(uid,))]
 return jsonify(items=rows)
@app.route('/api/readings',methods=['GET','POST'])
@auth
def readings():
 uid=session['uid']
 if request.method=='POST':
  d=payload(); g=number(d.get('generated')); u=number(d.get('consumed')); day=str(d.get('day',''))
  try: date.fromisoformat(day)
  except ValueError: return fail('Enter a valid date')
  if g is None or u is None or min(g,u)<0: return fail('Energy values must be nonnegative')
  with conn() as c: c.execute('INSERT INTO readings(user_id,day,generated,consumed) VALUES(?,?,?,?)',(uid,day,g,u))
 with conn() as c: rows=[dict(r) for r in c.execute('SELECT * FROM readings WHERE user_id=? ORDER BY day DESC,id DESC LIMIT 100',(uid,))]
 return jsonify(items=rows)
@app.get('/api/community')
@auth
def community():
 u=user_info(session['uid'])
 with conn() as c:
  people=[dict(x) for x in c.execute('SELECT id,name FROM users WHERE society=? AND id!=? ORDER BY name',(u['society'],u['id']))]
  rows=[dict(x) for x in c.execute('''SELECT s.id,s.kwh,s.note,s.created,a.name sender,b.name receiver FROM shares s JOIN users a ON a.id=s.sender_id JOIN users b ON b.id=s.receiver_id WHERE (s.sender_id=? OR s.receiver_id=?) ORDER BY s.id DESC LIMIT 50''',(u['id'],u['id']))]
 return jsonify(people=people,shares=rows)
@app.post('/api/share')
@auth
def share():
 uid=session['uid'];d=payload(); qty=number(d.get('kwh'))
 try: receiver=int(d.get('receiver_id'))
 except (ValueError,TypeError): return fail('Choose a resident')
 if receiver==uid or qty is None or qty<=0: return fail('Choose another resident and positive kWh')
 with conn() as c:
  sender=c.execute('SELECT society FROM users WHERE id=?',(uid,)).fetchone(); other=c.execute('SELECT society FROM users WHERE id=?',(receiver,)).fetchone()
  if not other or sender['society']!=other['society']: return fail('Sharing is limited to your society')
  totals=c.execute('SELECT COALESCE(SUM(generated),0) g,COALESCE(SUM(consumed),0) u FROM readings WHERE user_id=?',(uid,)).fetchone()
  already=c.execute('SELECT COALESCE(SUM(kwh),0) FROM shares WHERE sender_id=?',(uid,)).fetchone()[0]
  available=max(0,totals['g']-totals['u']-already)
  if qty>available+1e-8: return fail(f'Only {available:.2f} kWh simulated surplus available')
  c.execute('INSERT INTO shares(sender_id,receiver_id,kwh,note) VALUES(?,?,?,?)',(uid,receiver,qty,str(d.get('note',''))[:180]))
 return jsonify(ok=True)
@app.route('/api/maintenance',methods=['GET','POST','PATCH'])
@auth
def maintenance():
 uid=session['uid']
 with conn() as c:
  if request.method=='POST':
   d=payload(); title=str(d.get('title','')).strip(); due=str(d.get('due',''))
   try: date.fromisoformat(due)
   except ValueError: return fail('Valid due date required')
   if not title:return fail('Title required')
   c.execute('INSERT INTO maintenance(user_id,title,due) VALUES(?,?,?)',(uid,title,due))
  if request.method=='PATCH':
   d=payload();status=str(d.get('status',''))
   if status not in ('done','pending'):return fail('Invalid status')
   c.execute('UPDATE maintenance SET status=? WHERE id=? AND user_id=?',(status,d.get('id'),uid))
  rows=[dict(x) for x in c.execute('SELECT * FROM maintenance WHERE user_id=? ORDER BY due',(uid,))]
 return jsonify(items=rows)
@app.get('/api/admin')
@admin
def admin_data():
 u=user_info(session['uid'])
 with conn() as c:
  residents=[dict(x) for x in c.execute('SELECT id,name,email,role,created FROM users WHERE society=? ORDER BY id',(u['society'],))]
  totals=c.execute('''SELECT COUNT(DISTINCT i.id) installations,COALESCE(SUM(i.capacity),0) capacity FROM installations i JOIN users u ON u.id=i.user_id WHERE u.society=?''',(u['society'],)).fetchone()
  energy=c.execute('''SELECT COALESCE(SUM(r.generated),0) generated,COALESCE(SUM(r.consumed),0) consumed FROM readings r JOIN users u ON u.id=r.user_id WHERE u.society=?''',(u['society'],)).fetchone()
  shares=c.execute('''SELECT COALESCE(SUM(s.kwh),0) total FROM shares s JOIN users u ON u.id=s.sender_id WHERE u.society=?''',(u['society'],)).fetchone()
 return jsonify(residents=residents,installations=totals['installations'],capacity=totals['capacity'],generated=energy['generated'],consumed=energy['consumed'],shared=shares['total'])
@app.get('/api/export')
@auth
def export():
 with conn() as c: rows=c.execute('SELECT day,generated,consumed FROM readings WHERE user_id=? ORDER BY day',(session['uid'],)).fetchall()
 output=io.StringIO(); w=csv.writer(output);w.writerow(['Date','Generated kWh','Consumed kWh','Estimated savings INR (8/kWh)','Estimated CO2 avoided kg (0.7/kWh)'])
 for r in rows:w.writerow([r['day'],r['generated'],r['consumed'],round(min(r['generated'],r['consumed'])*8,2),round(r['generated']*.7,2)])
 return Response(output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=solarshare_report.csv'})
if __name__=='__main__':
 print('SolarShare running at http://127.0.0.1:5000')
 app.run(debug=False)
