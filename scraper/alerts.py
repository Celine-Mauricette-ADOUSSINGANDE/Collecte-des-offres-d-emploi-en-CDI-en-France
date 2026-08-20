# ═══════════════════════════════════════════════════════
#  alerts.py
#  Email quotidien récapitulatif via SendGrid
#  Inscription gratuite : https://sendgrid.com (100 emails/jour)
# ═══════════════════════════════════════════════════════

import os
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


def _build_html(new_offers: list[dict], stats: dict) -> str:
    """Construire le corps HTML de l'email récapitulatif."""

    # ── En-tête ──────────────────────────────────────────
    today = datetime.now().strftime("%d/%m/%Y")
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#2d2d2d">
      <div style="background:#1a1a2e;padding:24px 32px;border-radius:12px 12px 0 0">
        <h1 style="color:#fff;margin:0;font-size:20px">🎯 Veille offres Data Science</h1>
        <p style="color:#a0a0c0;margin:6px 0 0;font-size:14px">{today} — {len(new_offers)} nouvelles offres trouvées</p>
      </div>

      <div style="background:#f8f8fc;padding:20px 32px;border-bottom:1px solid #e0e0f0">
        <div style="display:flex;gap:16px;flex-wrap:wrap">
          <div style="background:#fff;border-radius:8px;padding:12px 20px;border:1px solid #e0e0f0;min-width:100px;text-align:center">
            <div style="font-size:24px;font-weight:700;color:#4f46e5">{stats.get('total', 0)}</div>
            <div style="font-size:12px;color:#666">Total en base</div>
          </div>
          <div style="background:#fff;border-radius:8px;padding:12px 20px;border:1px solid #e0e0f0;min-width:100px;text-align:center">
            <div style="font-size:24px;font-weight:700;color:#059669">{stats.get('by_status', {}).get('applied', 0)}</div>
            <div style="font-size:12px;color:#666">Candidatures</div>
          </div>
          <div style="background:#fff;border-radius:8px;padding:12px 20px;border:1px solid #e0e0f0;min-width:100px;text-align:center">
            <div style="font-size:24px;font-weight:700;color:#d97706">{stats.get('by_status', {}).get('interview', 0)}</div>
            <div style="font-size:12px;color:#666">Entretiens</div>
          </div>
        </div>
      </div>
    """

    if not new_offers:
        html += """
      <div style="padding:32px;text-align:center;color:#999">
        Aucune nouvelle offre depuis la dernière exécution.
      </div>
    """
    else:
        # ── Grouper par intitulé de recherche ────────────────
        by_label: dict[str, list] = {}
        for o in new_offers:
            label = o.get("search_label", "Autre")
            by_label.setdefault(label, []).append(o)

        html += '<div style="padding:20px 32px">'

        for label, group in by_label.items():
            html += f"""
          <h2 style="font-size:15px;color:#4f46e5;margin:20px 0 10px;
                     border-left:3px solid #4f46e5;padding-left:10px">{label} ({len(group)})</h2>
        """
            for o in group:
                salary_line = f"<span style='color:#059669'>💶 {o['salary']}</span> · " if o.get("salary") else ""
                html += f"""
            <div style="background:#fff;border:1px solid #e8e8f0;border-radius:8px;
                        padding:14px 16px;margin-bottom:10px">
              <div style="font-weight:600;font-size:14px">{o['title']}</div>
              <div style="font-size:13px;color:#555;margin:4px 0">
                🏢 {o['company']} &nbsp;·&nbsp; 📍 {o['location']}
              </div>
              <div style="font-size:12px;color:#888;margin:4px 0">
                {salary_line}📡 {o['source']}
              </div>
              <div style="font-size:12px;color:#aaa;margin:6px 0 8px">
                {o.get('description', '')[:200]}{'…' if len(o.get('description','')) > 200 else ''}
              </div>
              <a href="{o['url']}" style="display:inline-block;background:#4f46e5;color:#fff;
                 font-size:12px;padding:6px 14px;border-radius:6px;text-decoration:none">
                Voir l'offre →
              </a>
            </div>
          """
        html += "</div>"

    html += """
      <div style="background:#f0f0f8;padding:16px 32px;border-radius:0 0 12px 12px;
                  text-align:center;font-size:12px;color:#888">
        Job Tracker automatique · GitHub Actions · Données mises à jour toutes les 6h
      </div>
    </div>
    """
    return html


def send_alert(new_offers: list[dict], stats: dict) -> None:
    """Envoyer l'email récapitulatif si nouvelles offres ou 1x/jour."""
    api_key   = os.environ.get("SENDGRID_API_KEY")
    from_addr = os.environ.get("ALERT_EMAIL_FROM")
    to_addr   = os.environ.get("ALERT_EMAIL_TO")

    if not all([api_key, from_addr, to_addr]):
        print("[Email] Variables manquantes, email non envoyé.")
        return

    today   = datetime.now().strftime("%d/%m/%Y")
    subject = f"🎯 {len(new_offers)} nouvelles offres Data Science · {today}"

    message = Mail(
        from_email=from_addr,
        to_emails=to_addr,
        subject=subject,
        html_content=_build_html(new_offers, stats),
    )

    try:
        sg = SendGridAPIClient(api_key)
        sg.send(message)
        print(f"[Email] Récapitulatif envoyé à {to_addr}")
    except Exception as e:
        print(f"[Email] Erreur d'envoi : {e}")
