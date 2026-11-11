import os, sqlite3, secrets, csv, io, datetime
from flask import Flask, request, redirect, render_template_string, abort, Response
app=Flask(__name__)
DB=os.environ.get('DB_PATH','/tmp/t2music.db')
TOKEN=os.environ.get('ADMIN_TOKEN','')
def db():
 c=sqlite3.connect(DB)
 c.execute('CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY, platform TEXT, caption TEXT, link TEXT, scheduled_at TEXT, status TEXT DEFAULT "draft")')
 c.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)')
 return c
def authorized():
 return bool(TOKEN) and session.get('admin') is True
@app.get('/health')
def health(): return {'status':'ok','service':'T2 Music'}
@app.route('/',methods=['GET','POST'])
def home():
 if not TOKEN: return 'ADMIN_TOKEN must be configured.',503
 if not authorized(): return redirect('/login')
 con=db()
 if request.method=='POST':
  if request.form.get('csrf')!=session.get('csrf'): abort(403)
  platform=request.form.get('platform','')
  if platform not in ('facebook','instagram','tiktok','x','youtube'): abort(400)
  con.execute('INSERT INTO posts(platform,caption,link,scheduled_at) VALUES(?,?,?,?)',(platform,request.form.get('caption','')[:3000],request.form.get('link','')[:1000],request.form.get('scheduled_at','')))
  con.commit()
  return redirect('/')
 rows=con.execute('SELECT id,platform,caption,link,scheduled_at,status FROM posts ORDER BY id DESC').fetchall()
 return render_template_string('''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>T2 Music</title><style>body{background:#10121b;color:#eee;font:16px Arial;max-width:850px;margin:40px auto;padding:20px}input,textarea,select,button{box-sizing:border-box;width:100%;margin:8px 0;padding:12px;border-radius:7px;border:0}button{background:#a4ffb0;cursor:pointer}article{padding:16px;background:#222634;margin:14px 0;border-radius:10px}small{color:#b9c2d0}</style></head><body><h1>🎵 T2 Music</h1><p><a href="/auth/meta/start" style="color:#a4ffb0">Connect Facebook & Instagram</a></p><p>Campaign planner · Drafts only. Publishing requires official platform authorization.</p><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><select name="platform">{% for p in platforms %}<option>{{p}}</option>{% endfor %}</select><textarea name="caption" rows="5" required placeholder="Write promotional caption"></textarea><input name="link" placeholder="Music or video link"><label>Planned publishing time (local)</label><input type="datetime-local" name="scheduled_at"><button>Save draft</button></form><h2>Generate a music promotion</h2><form method="post" action="/campaign/generate"><input type="hidden" name="csrf" value="{{csrf}}"><input name="song" placeholder="Song title" required><input name="link" placeholder="Song or video link"><select name="platform">{% for p in platforms %}<option>{{p}}</option>{% endfor %}</select><button>Generate draft</button></form><p><a href="/campaign/export" style="color:#a4ffb0">Export all campaigns (CSV backup)</a> · <a href="/campaign/calendar" style="color:#a4ffb0">View schedule</a> · <a href="/campaign/stats" style="color:#a4ffb0">Campaign overview</a></p><h2>Campaign drafts</h2>{% for r in rows %}<article><b>{{r[1]|e}}</b> · <small>{{r[5]|e}} / {{r[4]|e}}</small><p>{{r[2]|e}}</p><small>{{r[3]|e}}</small><form method="post" action="/campaign/{{r[0]}}/delete" onsubmit="return confirm(\'Delete draft?\')"><input type="hidden" name="csrf" value="{{csrf}}"><button>Delete</button></form></article>{% endfor %}</body></html>''',rows=rows,csrf=session.get('csrf',''),token=TOKEN,platforms=['facebook','instagram','tiktok','x','youtube'])
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',10000)))


# Meta OAuth connection diagnostic (does not store access tokens or publish).
from flask import session, url_for
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
app.secret_key = os.environ.get('SESSION_SECRET') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_SECURE=True,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax')
META_APP_ID=os.environ.get('META_APP_ID','1451099540472136')
META_GRAPH_VERSION=os.environ.get('META_GRAPH_VERSION','v23.0')
META_REDIRECT='https://t2-music.onrender.com/auth/meta/callback'
@app.get('/auth/meta/start')
def meta_start():
 if not authorized(): return redirect('/login')
 if not os.environ.get('META_APP_SECRET') or not os.environ.get('SESSION_SECRET'):
  return 'Meta authorization not configured: set META_APP_SECRET and SESSION_SECRET in Render.',503
 state=secrets.token_urlsafe(32)
 session['meta_state']=state
 scopes='pages_show_list,pages_read_engagement,pages_manage_posts,instagram_basic,instagram_content_publish'
 params={'client_id':META_APP_ID,'redirect_uri':META_REDIRECT,'state':state,'response_type':'code','scope':scopes}
 return redirect('https://www.facebook.com/'+META_GRAPH_VERSION+'/dialog/oauth?'+urlencode(params))
@app.get('/auth/meta/callback')
def meta_callback():
 expected=session.pop('meta_state',None)
 received=request.args.get('state','')
 if not expected or not secrets.compare_digest(expected,received):
  return 'Invalid or expired authorization state. Start again from T2 Music.',400
 if request.args.get('error'): return 'Meta authorization was declined or failed.',400
 code=request.args.get('code')
 if not code: return 'No authorization code returned.',400
 secret=os.environ.get('META_APP_SECRET')
 if not secret: return 'Meta App Secret missing in Render.',503
 params=urlencode({'client_id':META_APP_ID,'client_secret':secret,'redirect_uri':META_REDIRECT,'code':code})
 try:
  with urlopen(Request('https://graph.facebook.com/'+META_GRAPH_VERSION+'/oauth/access_token?'+params),timeout=12) as resp:
   result=json.loads(resp.read())
  if not result.get('access_token'): return 'Meta returned no access token.',502
 except Exception:
  return 'Meta token exchange failed. Verify redirect URI, app configuration, and permissions.',502
 # Never persist, log, or expose the short-lived token in this starter.
 return 'Meta authorization succeeded. Secure token storage and account selection are still required before publishing.'

@app.route('/login',methods=['GET','POST'])
def login():
 if not TOKEN: return 'ADMIN_TOKEN not configured.',503
 if request.method=='POST':
  submitted=request.form.get('password','')
  if secrets.compare_digest(submitted,TOKEN):
   session.clear()
   session['admin']=True
   session['csrf']=secrets.token_urlsafe(24)
   return redirect('/')
  return 'Incorrect admin access token.',401
 return render_template_string("""<!doctype html><title>T2 Music Login</title><meta name="viewport" content="width=device-width,initial-scale=1"><body style="font:18px Arial;max-width:450px;margin:80px auto;padding:20px"><h1>T2 Music</h1><p>Enter your administrator access token from Render's ADMIN_TOKEN environment variable.</p><form method="post"><input type="password" name="password" required style="padding:12px;width:95%"><button style="padding:12px;margin-top:12px">Sign in</button></form></body>""")
@app.post('/logout')
def logout():
 session.clear()
 return redirect('/login')

@app.post('/campaign/generate')
def generate_campaign():
 if not authorized(): return redirect('/login')
 if request.form.get('csrf')!=session.get('csrf'): abort(403)
 platform=request.form.get('platform','instagram').lower()
 if platform not in ('facebook','instagram','tiktok','x','youtube'): abort(400)
 title=request.form.get('song','T2 Compton').strip()[:120] or 'T2 Compton'
 link=request.form.get('link','').strip()[:1000]
 captions={
 'facebook':f'Compton sound, independent energy. 🔥 Check out {title} by T2 Compton. Listen and share! #T2Compton #DirtyDPosse',
 'instagram':f'🎵 Now playing: {title} — T2 Compton. Tap in and share with someone who loves West Coast music. 🔥 #T2Compton #ComptonMusic #IndependentArtist',
 'tiktok':f'POV: You just found your new West Coast track 🔥 {title} by T2 Compton. #T2Compton #NewMusic #WestCoastHipHop',
 'x':f'🎵 {title} — T2 Compton. Independent music straight out of Compton. Listen and repost 🔥 #T2Compton',
 'youtube':f'Check out {title} by T2 Compton! Subscribe for more music from Dirty D Posse Entertainment. #T2Compton'
 }
 con=db()
 con.execute('INSERT INTO posts(platform,caption,link,scheduled_at,status) VALUES(?,?,?,?,?)',(platform,captions[platform],link,'','draft'))
 con.commit()
 return redirect('/')

@app.get('/campaign/export')
def export_campaigns():
 if not authorized(): return redirect('/login')
 rows=db().execute('SELECT id,platform,caption,link,scheduled_at,status FROM posts ORDER BY id').fetchall()
 out=io.StringIO()
 writer=csv.writer(out)
 writer.writerow(['id','platform','caption','link','scheduled_at','status'])
 writer.writerows(rows)
 return Response(out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=t2-music-campaigns.csv','Cache-Control':'no-store'})

@app.get('/campaign/calendar')
def campaign_calendar():
 if not authorized(): return redirect('/login')
 rows=db().execute("SELECT platform,caption,link,scheduled_at,status FROM posts WHERE scheduled_at IS NOT NULL AND scheduled_at!='' ORDER BY scheduled_at").fetchall()
 items=[]
 for platform,caption,link,scheduled_at,status in rows:
  try:
   start=datetime.datetime.fromisoformat(scheduled_at).strftime('%Y%m%dT%H%M%S')
  except ValueError: continue
  def escape(value):
   return str(value).replace('\\','\\\\').replace('\n','\\n').replace(',','\\,').replace(';','\\;')
  items.extend(['BEGIN:VEVENT','UID:'+secrets.token_hex(12)+'@t2music','DTSTAMP:'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),'DTSTART:'+start,'SUMMARY:'+escape('T2 Music draft - '+platform),'DESCRIPTION:'+escape(caption+' '+link+' (not auto-published)'),'END:VEVENT'])
 data='\r\n'.join(['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//T2 Music//Campaign Planner//EN',*items,'END:VCALENDAR'])+'\r\n'
 return Response(data,mimetype='text/calendar',headers={'Content-Disposition':'attachment; filename=t2-music-schedule.ics','Cache-Control':'no-store'})

@app.post('/campaign/<int:post_id>/delete')
def delete_campaign(post_id):
 if not authorized(): return redirect('/login')
 if request.form.get('csrf')!=session.get('csrf'): abort(403)
 con=db()
 con.execute('DELETE FROM posts WHERE id=?',(post_id,))
 con.commit()
 return redirect('/')

@app.get('/campaign/stats')
def campaign_stats():
 if not authorized(): return redirect('/login')
 con=db()
 total=con.execute('SELECT COUNT(*) FROM posts').fetchone()[0]
 breakdown=con.execute('SELECT platform,status,COUNT(*) FROM posts GROUP BY platform,status ORDER BY platform,status').fetchall()
 return render_template_string("""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>T2 Music Campaign Overview</title><style>body{font:17px Arial;background:#10121b;color:#eee;max-width:700px;margin:40px auto;padding:20px}a{color:#a4ffb0}table{width:100%;border-collapse:collapse}td,th{padding:12px;border-bottom:1px solid #444;text-align:left}</style></head><body><a href="/">← Dashboard</a><h1>Campaign overview</h1><h2>{{total}} saved campaigns</h2><p>These are internal campaign counts, not social media reach, plays, impressions, or engagement. Platform analytics will require account authorization.</p><table><tr><th>Platform</th><th>Status</th><th>Count</th></tr>{% for row in breakdown %}<tr><td>{{row[0]}}</td><td>{{row[1]}}</td><td>{{row[2]}}</td></tr>{% endfor %}</table></body></html>""",total=total,breakdown=breakdown)
