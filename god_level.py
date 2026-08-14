import os, json, re
from datetime import datetime

print("Starting God Level SEO...")

# 1. Create llms-full.txt
llms = """# Udyog Growth Knowledge Base
Updated: """ + datetime.now().strftime('%Y-%m-%d') + """

## Services
- GST Defence (DRC-01, GSTAT)
- Subsidies (PMFME, PMEGP, MSME)
- Pollution NOC (DPCC, UPPCB, HSPCB)
- Delhi School Admissions (DPS, Modern, British School)

## Methodology
We provide procedural mastery and bank-ready documentation. We do not guarantee seats or approvals; we guarantee flawless, compliant applications.

## Contact
Phone: +91 93105 26505
"""
with open('llms-full.txt', 'w') as f:
    f.write(llms)
print("Created llms-full.txt")

# 2. Inject Advanced Schema and E-E-A-T Sources
count = 0
for root, dirs, files in os.walk('.'):
    if '.git' in root: continue
    for file in files:
        if file.endswith('.html'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original = content
            
            # Add Breadcrumb Schema
            if '"@type": "BreadcrumbList"' not in content:
                schema = '{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://udyoggrowth.com/"}]}'
                content = content.replace('</head>', f'<script type="application/ld+json">{schema}</script></head>')
            
            # Add Official Sources (E-E-A-T)
            sources = """<div style="background:#f8f9fa; padding:15px; border-radius:5px; margin-top:30px; font-size:0.9em;"><h4 style="color:#8b2138;">Official Sources:</h4><ul><li><a href="https://www.cbic.gov.in/" target="_blank">CBIC (GST)</a></li><li><a href="https://www.fssai.gov.in/" target="_blank">FSSAI</a></li><li><a href="https://udyamregistration.gov.in/" target="_blank">Udyam (MSME)</a></li></ul></div>"""
            if 'Official Sources' not in content:
                content = content.replace('</body>', sources + '</body>')
                
            if content != original:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                count += 1

print(f"Optimized {count} files.")
