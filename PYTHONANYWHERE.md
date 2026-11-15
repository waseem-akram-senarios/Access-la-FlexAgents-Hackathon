# Deploy free on PythonAnywhere (no credit card)

PythonAnywhere’s **Beginner** plan is free forever and does **not** ask for a card.  
Your API will be at: `https://YOUR_USERNAME.pythonanywhere.com`

## Steps (about 5 minutes)

1. Sign up (free): https://www.pythonanywhere.com/registration/register/beginner/
2. Open a **Bash** console and run:

```bash
git clone https://github.com/waseem-akram-senarios/Access-la-FlexAgents-Hackathon.git
cd Access-la-FlexAgents-Hackathon
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Go to **Web** → **Add a new web app** → **Manual configuration** → **Python 3.10**
4. Set:
   - **Source code:** `/home/YOUR_USERNAME/Access-la-FlexAgents-Hackathon`
   - **Working directory:** `/home/YOUR_USERNAME/Access-la-FlexAgents-Hackathon`
   - **Virtualenv:** `/home/YOUR_USERNAME/Access-la-FlexAgents-Hackathon/venv`
   - **WSGI file:** edit it to:

```python
import sys
path = "/home/YOUR_USERNAME/Access-la-FlexAgents-Hackathon"
if path not in sys.path:
    sys.path.insert(0, path)

from wsgi import application  # noqa: E402
```

5. Click **Reload** on the Web tab.
6. Open `https://YOUR_USERNAME.pythonanywhere.com/health`  
   Docs: `https://YOUR_USERNAME.pythonanywhere.com/docs`

Use that base URL in FlexAgents Connections.

### Limits (free plan)

- One web app, custom domain not included
- App may be slower; free accounts sleep if unused for a long time
- Enough for the hackathon demo
