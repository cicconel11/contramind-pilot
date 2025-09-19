import http from 'k6/http';
import { sleep, check } from 'k6';

export const options = { vus: 10, duration: '30s' };

export default function () {
  // worldcheck quick ping
  const r = http.post('http://localhost:8081/verify', JSON.stringify({type:'issuer_verify'}), {headers:{'content-type':'application/json'}});
  check(r, {'200': (res)=> res.status===200});
  sleep(0.2);
}
