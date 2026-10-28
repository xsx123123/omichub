import subprocess,json,time,urllib.request
from pathlib import Path
root=Path('evidence/web-capacity-route-telemetry')
processes=[];logs=[]
try:
 for port,size,name in [(18401,0,'baseline'),(18402,1024,'optimized')]:
  log=(root/f'{name}-server.log').open('w');logs.append(log)
  processes.append(subprocess.Popen(['docker','exec','-e','APP_DEBUG=false','-e',f'TELEMETRY_ROUTE_CACHE_SIZE={size}','-e','DATABASE_POOL_SIZE=4','-e','DATABASE_MAX_OVERFLOW=0','-e','CYGNUSX_LOG_DIR=/tmp/webperf-route','cygnusx-web','python','-m','scripts.web_capacity_server','--port',str(port),'--manifest',f'/tmp/webperf-route-{port}.json','--query-stats',f'/tmp/webperf-route-{port}-stats.json','--stop-after','300'],stdout=log,stderr=subprocess.STDOUT))
 for port in [18401,18402]:
  for _ in range(50):
   try:
    with urllib.request.urlopen(f'http://192.168.64.7:{port}/health',timeout=1) as r:
     if r.status==200:break
   except OSError:time.sleep(1)
  else:raise RuntimeError('Route telemetry instance not ready')
 for name,port in [('baseline1',18401),('optimized1',18402),('baseline2',18401),('optimized2',18402)]:
  subprocess.run(['uv','run','--frozen','python','scripts/web_load_test.py','--base-url',f'http://192.168.64.7:{port}','--tokens-file','/tmp/webperf_20261027_d1.json','--users','20','--duration','30','--warmup','3','--think-time','0','--output',str(root/f'{name}.json')],check=True)
finally:
 for port in [18401,18402]:
  code=f'''import json,os,signal
from pathlib import Path
p=Path('/tmp/webperf-route-{port}.json')
if p.exists():
 d=json.loads(p.read_text());q=Path(f"/proc/{{d['pid']}}/cmdline")
 if q.exists():
  args=q.read_bytes().split(b'\\0')
  assert b'scripts.web_capacity_server' in args and {str(port).encode()!r} in args
  os.kill(d['pid'],signal.SIGINT)
'''
  subprocess.run(['docker','exec','-i','cygnusx-web','python','-'],input=code,text=True,capture_output=True)
 for p in processes:p.wait(timeout=30)
 for log in logs:log.close()
 for port,name in [(18401,'baseline'),(18402,'optimized')]:
  for suffix,destination in [('',f'{name}-manifest.json'),('-stats',f'{name}-stats.json')]:
   subprocess.run(['docker','cp',f'cygnusx-web:/tmp/webperf-route-{port}{suffix}.json',str(root/destination)],check=True,capture_output=True)
print('Completed route metadata cache A/B and stopped isolated instances.')
