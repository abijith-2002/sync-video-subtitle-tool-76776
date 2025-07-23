# Troubleshooting "413 Payload Too Large" Errors with FastAPI

If you're still seeing HTTP 413 (Payload Too Large) errors **after raising the upload size limit in FastAPI (and the `MAX_UPLOAD_SIZE_MB` environment variable)**, the cause is often *outside* the app itself. This checklist will help you identify and resolve configuration limits in your deployment stack.

---

## 1. FastAPI Settings (Review)

- Confirm you restarted the backend *after* changing `MAX_UPLOAD_SIZE_MB`.
- Verify any upload size middleware is correctly using the updated environment variable.
- Check that there are **no additional upload size limits set by other FastAPI middlewares or dependencies**.

---

## 2. Reverse Proxy (NGINX, Apache, etc.)

If you're running FastAPI *behind* a reverse proxy (very common in production!):

**For NGINX:**
- Check your `nginx.conf` or site config for:
  ```nginx
  client_max_body_size 2G;   # or higher; set to match or exceed your FastAPI limit
  ```
- Place this directive in the `http`, `server`, or `location` block that proxies to FastAPI.

**For Apache:**
- Look for or add:
  ```
  LimitRequestBody 2147483647
  ```
- (Value is in bytes; 2 GB = 2147483648.)

**Reload or restart your proxy service after changing these settings.**

---

## 3. Cloud Hosting / PaaS / Container Services

Many cloud and container platforms also limit upload size:

- **Docker / Uvicorn / Gunicorn**:  
  - Check for `--limit-request-line`, `--limit-request-field_size`, or similar flags.
  - Gunicorn does *not* enforce body size by default but *may* via worker timeouts if upload is slow.
- **Cloud Run, Heroku, Vercel, AWS, Azure**:  
  - Consult their docs for inbound request size limits; some default as low as 10–100 MB.
  - You may need to adjust platform configuration or environment.

---

## 4. Load Balancers / Other Network Components

- If traffic passes through a load balancer (AWS ELB/ALB, GCP, etc.), check for any "max body size" or similar configuration.

---

## 5. Client-Side

- Make sure your client/web frontend isn't inadvertently chunking or capping uploads with its own JS or HTTP client limits.  
- Browsers typically allow large uploads, but if using a proxy (like a local dev server), check its settings.

---

## 6. Debugging: How to Confirm the Source

- Try uploading directly to the FastAPI backend (bypassing proxy) if possible.
- Set backend `MAX_UPLOAD_SIZE_MB` to a small value (like 2MB) and verify if you receive 413 from FastAPI or from the proxy (the error payload or headers *may* reveal which layer produced it).
- Check logs at every layer: FastAPI, proxy, cloud platform.

---

## 7. Other Common Gotchas

- **Multiple proxies**: If using both NGINX *and* a cloud proxy, *both* must be set to high limits!
- **Units mismatch**: Ensure all are using MB/GB/bytes consistently.
- **Configuration reload**: NGINX/Apache needs reload (`nginx -s reload`), as does your process manager (systemd, Docker, etc).

---

## 8. Example: Raising NGINX and FastAPI Limits to 2GB
```nginx
# in nginx.conf
server {
    ...
    client_max_body_size 2G;
    location / {
        proxy_pass http://127.0.0.1:8000;
        ...
    }
}
```
```bash
# before starting FastAPI
export MAX_UPLOAD_SIZE_MB=2048
```
Restart both NGINX and FastAPI.

---

## 9. Still Stuck?

- Document *all* layers between client and FastAPI.
- Look for errors in all logs.
- Test direct uploads.
- Share stack trace, headers, and the *exact* error format (the body may differ if sent by NGINX vs. FastAPI).
- [FastAPI docs on file upload limits](https://fastapi.tiangolo.com/tutorial/request-files/#requestfiles)

---

## Summary Checklist

- [ ] FastAPI `MAX_UPLOAD_SIZE_MB` matches your target.
- [ ] Any proxy (`nginx`, `apache`, cloud) set to at least the same size.
- [ ] All services reloaded after config changes.
- [ ] No frontend limit or chunking.
- [ ] Platform-specific (Docker, Heroku, etc.) limits checked.
- [ ] Logs checked at every hop.

---

*If after checking all of the above you still see this error, please collect logs, config details, and error payloads at every network layer and share with your devops or support team.*

