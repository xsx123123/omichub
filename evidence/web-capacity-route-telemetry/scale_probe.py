"""Run four isolated real Web processes and an unpublished, unprivileged Nginx."""
import subprocess,json,time,urllib.request,os,signal
from pathlib import Path

root=Path('evidence/web-capacity-route-telemetry')
ports=list(range(18601,18617))
run_id='webperf_scale_20261027_d1'
remote=f'/tmp/{run_id}'
processes=[]
logs=[]
report={'scope':'same host/container, independent real Web processes; isolated read-only startup', 'stages':[]}

def execute(args, **kw):
 return subprocess.run(args,check=True,capture_output=True,text=True,**kw)

def nginx_config(n):
 servers='\n'.join(f'        server web:{p};' for p in ports[:n])
 return f'''pid {remote}/nginx.pid;
error_log {remote}/error.log warn;
worker_processes 1;
events {{ worker_connections 4096; }}
http {{
 log_format capacity 'n={n} $upstream_addr $status $request_time';
 access_log {remote}/access.log capacity;
 client_body_temp_path {remote}/client;
 proxy_temp_path {remote}/proxy;
 upstream capacity_backend {{
  least_conn;
{servers}
  keepalive 64;
 }}
 server {{
  listen 18680;
  location / {{
   proxy_pass http://capacity_backend;
   proxy_http_version 1.1;
   proxy_set_header Connection "";
   proxy_set_header Host $host;
   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   proxy_buffering off;
   proxy_read_timeout 20s;
   add_header X-Capacity-Replicas {n} always;
   add_header X-Capacity-Upstream $upstream_addr always;
  }}
 }}
}}
'''

def set_gateway(n):
 conf=nginx_config(n)
 (root/f'nginx-{n}.conf').write_text(conf)
 execute(['docker','exec','-i','--user','nginx','cygnusx-nginx','tee',f'{remote}/nginx.conf'],input=conf)
 execute(['docker','exec','--user','nginx','cygnusx-nginx','nginx','-t','-c',f'{remote}/nginx.conf'])

try:
 for port in ports:
  log=(root/f'scale-server-{port}.log').open('w');logs.append(log)
  process=subprocess.Popen(['docker','exec','-e','APP_DEBUG=false','-e','DATABASE_POOL_SIZE=3','-e','TELEMETRY_ROUTE_CACHE_SIZE=1024','-e','DATABASE_MAX_OVERFLOW=0','-e','CYGNUSX_LOG_DIR=/tmp/webperf-route','cygnusx-web','python','-m','scripts.web_capacity_server','--port',str(port),'--manifest',f'{remote}-{port}.json','--query-stats',f'{remote}-{port}-sql.json','--stop-after','600'],stdout=log,stderr=subprocess.STDOUT)
  processes.append(process)
 for port in ports:
  for _ in range(60):
   try:
    with urllib.request.urlopen(f'http://192.168.64.7:{port}/health',timeout=1) as response:
     if response.status==200: break
   except OSError: time.sleep(1)
  else: raise RuntimeError(f'Web {port} not ready')
  manifest=json.loads(execute(['docker','exec','cygnusx-web','cat',f'{remote}-{port}.json']).stdout)
  (root/f'scale-manifest-{port}.json').write_text(json.dumps(manifest,indent=2)+'\n')
 execute(['docker','exec','--user','nginx','cygnusx-nginx','mkdir','-p',remote])
 set_gateway(8)
 nginx_log=(root/'scale-nginx.log').open('w');logs.append(nginx_log)
 nginx=subprocess.Popen(['docker','exec','--user','nginx','cygnusx-nginx','nginx','-c',f'{remote}/nginx.conf','-g','daemon off;'],stdout=nginx_log,stderr=subprocess.STDOUT)
 for n in [8,16]:
  if n!=8:
   set_gateway(n)
   execute(['docker','exec','--user','nginx','cygnusx-nginx','nginx','-s','reload','-c',f'{remote}/nginx.conf'])
  for _ in range(20):
   try:
    with urllib.request.urlopen('http://192.168.80.6:18680/health',timeout=1) as response:
     if response.headers.get('X-Capacity-Replicas')==str(n): break
   except OSError: pass
   time.sleep(.5)
  else: raise RuntimeError('Isolated gateway config not ready')
  with (root/f'scale-{n}.log').open('w') as log:
   result=subprocess.run(['uv','run','--frozen','python','scripts/web_load_test.py','--base-url','http://192.168.80.6:18680','--tokens-file','/tmp/webperf_20261027_d1.json','--users','100','--duration','30','--warmup','3','--think-time','0','--output',str(root/f'scale-{n}.json')],stdout=log,stderr=subprocess.STDOUT)
  report['stages'].append({'processes':n,'exit_code':result.returncode})
  (root/'scale-run.json').write_text(json.dumps(report,indent=2)+'\n')
 # Fixed-rate acceptance against the four-process gateway. A failed threshold is
 # recorded as a failed trial, never relabeled as successful capacity.
 for rate in [1250,1500,2000]:
  with (root/f'k6-{rate}.log').open('w') as log:
   result=subprocess.run(['/tmp/cygnusx-k6-v2.3.0/k6','run','-e','TOKENS_FILE=/tmp/webperf_20261027_d1.json','-e','BASE_URL=http://192.168.80.6:18680','-e',f'RATE={rate}','-e','DURATION=30s','-e','PREALLOCATED_VUS=200','-e','MAX_VUS=500',f'--summary-export={root}/k6-{rate}-summary.json','tests/performance/k6_web.js'],stdout=log,stderr=subprocess.STDOUT)
  report.setdefault('fixed_rate_trials',[]).append({'rate':rate,'exit_code':result.returncode})
  (root/'scale-run.json').write_text(json.dumps(report,indent=2)+'\n')
finally:
 quit_result=subprocess.run(['docker','exec','--user','nginx','cygnusx-nginx','nginx','-s','quit','-c',f'{remote}/nginx.conf'],capture_output=True,text=True)
 report['gateway_quit_exit_code']=quit_result.returncode
 subprocess.run(['docker','cp',f'cygnusx-nginx:{remote}/access.log',str(root/'scale-access.log')],capture_output=True)
 for port in ports:
  # Verify identity before signaling a PID; never touch the production Uvicorn.
  code=f'''import os,signal,json
from pathlib import Path
p=Path({str(remote+'-'+str(port)+'.json')!r})
if p.exists():
 info=json.loads(p.read_text());pid=info['pid']
 cmd=Path(f'/proc/{{pid}}/cmdline')
 if cmd.exists():
  args=cmd.read_bytes().split(b'\\0')
  assert b'scripts.web_capacity_server' in args and {str(port).encode()!r} in args
  os.kill(pid,signal.SIGINT)
'''
  subprocess.run(['docker','exec','-i','cygnusx-web','python','-'],input=code,text=True,capture_output=True)
 for process in processes:
  try: process.wait(timeout=30)
  except subprocess.TimeoutExpired: pass
 for port in ports:
  subprocess.run(['docker','cp',f'cygnusx-web:{remote}-{port}-sql.json',str(root/f'scale-sql-{port}.json')],capture_output=True)
 if 'nginx' in locals():
  try: nginx.wait(timeout=20)
  except subprocess.TimeoutExpired: pass
 report['probe_client_exit_codes']=[p.poll() for p in processes]
 report['gateway_client_exit_code']=nginx.poll() if 'nginx' in locals() else None
 for log in logs: log.close()
 (root/'scale-run.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
