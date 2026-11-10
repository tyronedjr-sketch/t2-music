import os, sqlite3, secrets
from flask import Flask, request, redirect, render_template_string, abort
app=Flask(__name__)
DB=os.environ.get('DB_PATH','/tmp/t2music.db')
TOKEN=os.environ.get('ADMIN_TOKEN','')
def db():
 c=sqlite3.connect(DB)
 c.execute('CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY, platform TEXT, caption TEXT, link TEXT, scheduled_at TEXT, status TEXT DEFAULT "draft")')
 return c
def authorized():
 return bool(TOKEN) and secrets.compare_digest(request.args.get('token','') or request.form.get('token',''),TOKEN)
@app.get('/health')
def health(): return {'status':'ok','service':'T2 Music'}
@app.route('/',methods=['GET','POST'])
def home():
 if not TOKEN: return 'ADMIN_TOKEN must be configured.',503
 if not authorized(): abort(401)
 con=db()
 if request.method=='POST':
  platform=request.form.get('platform','')
  if platform not in ('facebook','instagram','tiktok','x','youtube'): abort(400)
  con.execute('INSERT INTO posts(platform,caption,link,scheduled_at) VALUES(?,?,?,?)',(platform,request.form.get('caption','')[:3000],request.form.get('link','')[:1000],request.form.get('scheduled_at','')))
  con.commit()
  return redirect('/?token='+TOKEN)
 rows=con.execute('SELECT id,platform,caption,link,scheduled_at,status FROM posts ORDER BY id DESC').fetchall()
 return render_template_string('''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>T2 Music</title><style>body{background:#10121b;color:#eee;font:16px Arial;max-width:850px;margin:40px auto;padding:20px}input,textarea,select,button{box-sizing:border-box;width:100%;margin:8px 0;padding:12px;border-radius:7px;border:0}button{background:#a4ffb0;cursor:pointer}article{padding:16px;background:#222634;margin:14px 0;border-radius:10px}small{color:#b9c2d0}</style></head><body><h1>🎵 T2 Music</h1><p>Campaign planner · Drafts only. Publishing requires official platform authorization.</p><form method="post"><input type="hidden" name="token" value="{{token}}"><select name="platform">{% for p in platforms %}<option>{{p}}</option>{% endfor %}</select><textarea name="caption" rows="5" required placeholder="Write promotional caption"></textarea><input name="link" placeholder="Music or video link"><label>Planned publishing time (local)</label><input type="datetime-local" name="scheduled_at"><button>Save draft</button></form><h2>Campaign drafts</h2>{% for r in rows %}<article><b>{{r[1]|e}}</b> · <small>{{r[5]|e}} / {{r[4]|e}}</small><p>{{r[2]|e}}</p><small>{{r[3]|e}}</small></article>{% endfor %}</body></html>''',rows=rows,token=TOKEN,platforms=['facebook','instagram','tiktok','x','youtube'])
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',10000)))
