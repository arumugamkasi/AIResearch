import subprocess
import threading
import time
import yfinance as yf


class AlertMonitor:
    def __init__(self, db, config):
        self.db = db       # PortfolioMongo instance
        self.config = config  # AlertConfigMongo instance
        self._alerted = {}    # sym -> True
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self._check()
            except Exception:
                pass
            time.sleep(60)

    def _check(self):
        cfg = self.config.get_config()
        if not cfg:
            return
        threshold = float(cfg.get('threshold_pct', 5))
        email_enabled = bool(cfg.get('email_enabled', False))

        positions = self.db.get_all_positions()
        symbols = list({p['symbol'] for p in positions if p['symbol'] != 'CASH'})

        triggered = []
        for sym in symbols:
            try:
                info = yf.Ticker(sym).info
                current = info.get('currentPrice') or info.get('regularMarketPrice')
                prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
                if current is None or prev_close is None or prev_close == 0:
                    continue
                day_change_pct = (current / prev_close - 1) * 100
                if day_change_pct <= -threshold and sym not in self._alerted:
                    self._alerted[sym] = True
                    triggered.append({
                        'symbol': sym,
                        'day_change_pct': day_change_pct,
                        'price': current,
                        'threshold_pct': threshold,
                    })
                elif day_change_pct > -threshold * 0.5 and sym in self._alerted:
                    del self._alerted[sym]
            except Exception:
                continue

        if triggered and email_enabled:
            self._send_email(cfg, triggered)

    def _send_email(self, cfg, alerts):
        threshold = cfg.get('threshold_pct', 5)
        n = len(alerts)
        subject = f'\u26a0\ufe0f Portfolio Alert: {n} position(s) down >{threshold}%'
        lines = [f"{a['symbol']}: {a['day_change_pct']:.1f}% (${a['price']:.2f})" for a in alerts]
        body = '\n'.join(lines)
        email_to = cfg.get('email_to', 'arumugamkasi@gmail.com')

        script = f'''
tell application "Mail"
    set newMsg to make new outgoing message with properties {{subject:"{subject}", content:"{body}", visible:false}}
    tell newMsg
        make new to recipient at end of to recipients with properties {{address:"{email_to}"}}
    end tell
    send newMsg
end tell
'''
        try:
            subprocess.run(['osascript', '-e', script], timeout=10)
        except Exception:
            pass

    def get_active_alerts(self):
        """Return list of currently triggered alert dicts."""
        cfg = self.config.get_config()
        threshold = float(cfg.get('threshold_pct', 5)) if cfg else 5
        result = []
        for sym in list(self._alerted.keys()):
            try:
                info = yf.Ticker(sym).info
                current = info.get('currentPrice') or info.get('regularMarketPrice')
                prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
                if current is None or prev_close is None or prev_close == 0:
                    continue
                day_change_pct = (current / prev_close - 1) * 100
                result.append({
                    'symbol': sym,
                    'day_change_pct': day_change_pct,
                    'price': current,
                    'threshold_pct': threshold,
                })
            except Exception:
                continue
        return result
