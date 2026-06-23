"""Live run monitor: subscribes to the WebSocket stream and shows real-time progress.

Streamlit does not support raw WebSockets in Python, so the subscription
is done from a small embedded HTML/JS component. The component posts
events into the page DOM, which is read back by ``st.html`` via
``st_javascript`` or, in our case, by simply rendering a styled
``<pre>`` that the component keeps updated.

Usage:

    from marketsignal.ui.components.run_monitor import render_live_run
    render_live_run("abcd1234efgh")
"""
from __future__ import annotations

import json

import streamlit as st

_LIVE_RUN_HTML = """
<div id="ms-live-{run_id}" style="font-family: monospace; font-size: 13px;
                                   background: #0e1117; color: #fafafa;
                                   padding: 12px; border-radius: 6px;
                                   max-height: 360px; overflow-y: auto;">
  <div style="opacity:.7;">connecting to ws://{host}/ws/runs/{run_id} ...</div>
</div>
<script>
(function () {
  var root = document.getElementById("ms-live-{run_id}");
  var wsUrl = "ws://" + window.location.host + "/ws/runs/{run_id}";
  var nodes = {{}};
  var status = "unknown";
  var errorMessage = null;
  function render() {{
    var html = "<div style='margin-bottom:6px;'><b>status:</b> " + status
      + (errorMessage ? " <span style='color:#ff8080;'>(" + errorMessage + ")</span>" : "")
      + "</div>";
    var keys = Object.keys(nodes);
    if (keys.length === 0) {{
      html += "<div style='opacity:.6;'>no nodes completed yet</div>";
    }} else {{
      for (var i = 0; i < keys.length; i++) {{
        var n = nodes[keys[i]];
        var color = n.status === "ok" ? "#5be37c" : (n.status === "error" ? "#ff8080" : "#f0c674");
        var dur = n.duration_ms != null ? (" (" + n.duration_ms.toFixed(1) + " ms)") : "";
        html += "<div><span style='color:" + color + ";'>" + (n.status === "ok" ? "ok" : n.status) + "</span>"
          + " &nbsp; " + n.node + dur + "</div>";
      }}
    }}
    root.innerHTML = html;
  }}
  function connect() {{
    try {{
      var ws = new WebSocket(wsUrl);
      ws.onmessage = function (ev) {{
        try {{
          var msg = JSON.parse(ev.data);
          if (msg.type === "snapshot") {{
            var spans = (msg.trace && msg.trace.spans) || [];
            for (var i = 0; i < spans.length; i++) {{
              var s = spans[i];
              if (s.status === "ok" || s.status === "error") {{ nodes[s.node] = s; }}
            }}
          }} else if (msg.type === "node") {{
            nodes[msg.span.node] = msg.span;
          }} else if (msg.type === "status") {{
            status = msg.status;
            errorMessage = msg.error_message;
          }} else if (msg.type === "heartbeat") {{
            /* keep alive */
          }} else if (msg.type === "done") {{
            root.innerHTML += "<div style='margin-top:8px;color:#5be37c;'>stream closed</div>";
            try {{ ws.close(); }} catch (e) {{}}
            return;
          }} else if (msg.type === "error") {{
            root.innerHTML += "<div style='margin-top:8px;color:#ff8080;'>error: " + msg.detail + "</div>";
          }}
          render();
        }} catch (e) {{
          root.innerHTML = "<div style='color:#ff8080;'>parse error: " + e + "</div>";
        }}
      }};
      ws.onerror = function () {{
        root.innerHTML = "<div style='color:#ff8080;'>websocket error (is the API running?)</div>";
      }};
      ws.onclose = function () {{
        if (status !== "completed" && status !== "failed") {{
          /* reconnect once after 2s if the run is still going */
          setTimeout(connect, 2000);
        }}
      }};
    }} catch (e) {{
      root.innerHTML = "<div style='color:#ff8080;'>connect failed: " + e + "</div>";
    }}
  }}
  connect();
  render();
})();
</script>
"""


def render_live_run(run_id: str) -> None:
    """Render a live progress panel that subscribes to ``/ws/runs/{run_id}``.

    The component is fully self-contained: it opens a WebSocket, paints
    each completed node span as it arrives, and reconnects automatically
    if the run is still in progress when the socket closes.
    """
    # Streamlit's st.components.v1.html lets us run arbitrary JS.
    # The host window.location.host will resolve to wherever the API is
    # served from (same origin in dev).
    import streamlit.components.v1 as components

    components.html(_LIVE_RUN_HTML.format(run_id=run_id, host="window.location.host"), height=380)


def render_run_monitor() -> None:
    """Render the run history table + an optional live-monitor for a selected run."""
    from sqlalchemy import desc

    from marketsignal.db.session import get_session
    from marketsignal.models.crawl_run import CrawlRun
    from marketsignal.models.eval_run import EvalRun

    st.subheader("Run history")
    with get_session() as s:
        runs = list(s.query(CrawlRun).order_by(desc(CrawlRun.started_at)).limit(20).all())
    if not runs:
        st.info("No runs yet. Trigger one from the sidebar.")
        return

    options = [r.id for r in runs]
    sel = st.selectbox("Inspect a run", options, index=0, key="run_monitor_select")
    selected = next((r for r in runs if r.id == sel), None)
    if selected is None:
        return

    st.markdown(f"**status:** `{selected.status}` &nbsp; **started:** `{selected.started_at}`")
    if selected.error_message:
        st.error(selected.error_message)

    with get_session() as s:
        row = (
            s.query(EvalRun)
            .filter_by(crawl_run_id=sel)
            .order_by(desc(EvalRun.created_at))
            .first()
        )
    if row is not None:
        cols = st.columns(4)
        cols[0].metric("citation_coverage", f"{row.citation_coverage:.2%}")
        cols[1].metric("unsupported_claim_rate", f"{row.unsupported_claim_rate:.2%}")
        cols[2].metric("dedup_rate", f"{row.dedup_rate:.2%}")
        cols[3].metric("token_cost_usd", f"${row.token_cost_usd:.4f}")

    st.markdown("**Live progress**")
    render_live_run(sel)


__all__ = ["render_live_run", "render_run_monitor"]


# Self-test: if executed directly, print the rendered HTML (no Streamlit run).
if __name__ == "__main__":
    print(json.dumps({"html_chars": len(_LIVE_RUN_HTML), "preview": _LIVE_RUN_HTML[:200]}))
