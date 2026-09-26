# AI Music Studio v2

## GitHub Pages + Render deployment

If the frontend is hosted separately from the API, set a global `window.__API_BASE__` before loading the page script, for example:

```html
<script>
  window.__API_BASE__ = "https://your-render-app.onrender.com";
</script>
```

Then the frontend will call `${API_BASE}/health` and `${API_BASE}/api/...` instead of the same-origin path.

If you do not set `window.__API_BASE__`, the frontend will use the same-origin URL as usual.
